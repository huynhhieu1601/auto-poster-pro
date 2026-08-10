const jwt = require('jsonwebtoken');
const UserApiKey = require('../models/UserApiKey');
const User = require('../models/User');

/**
 * Cấu hình fallback cho Proxy API (/v1/*)
 * - Nếu client gọi API KHÔNG mang `kira_sk_*` (User API Key) hoặc JWT hợp lệ
 *   (ví dụ: tài khoản mới đăng ký chưa có key, hoặc app gọi với API key ngoài),
 *   middleware KHÔNG quăng lỗi ngắt kết nối mà cho request đi tiếp và dùng
 *   API Key/Credentials MẶC ĐỊNH của hệ thống (ApiKey trong DB hoặc GEMINI_API_KEY trong .env).
 * - Đặt PROXY_ALLOW_FALLBACK=false để tắt fallback khi cần xác thực nghiêm ngặt.
 */
const ALLOW_FALLBACK = process.env.PROXY_ALLOW_FALLBACK !== 'false';

/** Log chi tiết sự kiện xác thực để debug, không bao giờ drop kết nối. */
function logAuthEvent(req, level, message, extra = {}) {
    const entry = {
        method: req.method,
        path: req.originalUrl,
        ip: req.ip,
        tokenPrefix: extra.tokenPrefix || null,
        ...extra
    };
    const line = `[proxyAuth] ${message} | ${JSON.stringify(entry)}`;
    if (level === 'error') console.error(line);
    else console.warn(line);
}

/** Trả lỗi theo chuẩn OpenAI-compatible (JSON, không drop kết nối). */
function sendAuthError(req, res, status, message, code) {
    return res.status(status).json({
        error: { message, type: code, code }
    });
}

/** Xác thực bằng User API Key dạng kira_sk_* */
async function authenticateByApiKey(req, token) {
    const userApiKey = await UserApiKey.findOne({ key: token });
    if (!userApiKey) {
        logAuthEvent(req, 'error', 'API key không tồn tại trong database', { tokenPrefix: token.slice(0, 12) });
        return { ok: false, status: 401, code: 'invalid_api_key', message: 'API key không tồn tại' };
    }
    if (!userApiKey.isValid()) {
        const reason = !userApiKey.isActive ? 'đã bị vô hiệu hoá' : 'đã hết hạn';
        logAuthEvent(req, 'error', `API key ${reason}`, { tokenPrefix: token.slice(0, 12) });
        return { ok: false, status: 401, code: 'expired_api_key', message: `API key ${reason}` };
    }
    const user = await User.findById(userApiKey.userId);
    if (!user || !user.isActive) {
        logAuthEvent(req, 'error', 'Tài khoản không hợp lệ hoặc đã bị khoá', { tokenPrefix: token.slice(0, 12) });
        return { ok: false, status: 401, code: 'account_disabled', message: 'Tài khoản không hợp lệ hoặc đã bị khoá' };
    }
    return { ok: true, user, apiKey: userApiKey, method: 'api_key' };
}

/** Xác thực bằng JWT (session token) — dành cho client đã đăng nhập web */
async function authenticateByJwt(req, token) {
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        const user = await User.findById(decoded.id);
        if (!user) {
            logAuthEvent(req, 'error', 'JWT hợp lệ nhưng user không tồn tại');
            return { ok: false, status: 401, code: 'invalid_token', message: 'Token không hợp lệ, người dùng không tồn tại' };
        }
        if (!user.isActive) {
            logAuthEvent(req, 'error', 'Tài khoản JWT đã bị khoá');
            return { ok: false, status: 403, code: 'account_disabled', message: 'Tài khoản của bạn đã bị khoá' };
        }
        return { ok: true, user, apiKey: null, method: 'jwt' };
    } catch (error) {
        if (error.name === 'TokenExpiredError') {
            logAuthEvent(req, 'error', 'JWT đã hết hạn', { tokenPrefix: token.slice(0, 12) });
            return { ok: false, status: 401, code: 'token_expired', message: 'Token đã hết hạn' };
        }
        logAuthEvent(req, 'error', 'JWT không hợp lệ', { tokenPrefix: token.slice(0, 12) });
        return { ok: false, status: 401, code: 'invalid_token', message: 'Token không hợp lệ' };
    }
}

const proxyAuth = async (req, res, next) => {
    try {
        let token = null;

        // Lấy token từ header Authorization
        if (req.headers.authorization && req.headers.authorization.startsWith('Bearer ')) {
            token = req.headers.authorization.split(' ')[1].trim();
        }

        let result = null;

        if (token && token.startsWith('kira_sk_')) {
            result = await authenticateByApiKey(req, token);
        } else if (token) {
            // Token không phải kira_sk_* → thử xác thực như JWT (session token)
            result = await authenticateByJwt(req, token);
        } else {
            logAuthEvent(req, 'warn', 'Không có Authorization header (missing credentials)');
        }

        // Không xác thực được → fallback dùng credentials mặc định của hệ thống
        if (!result || !result.ok) {
            if (!ALLOW_FALLBACK) {
                logAuthEvent(req, 'error', 'Xác thực thất bại & fallback đã bị tắt (PROXY_ALLOW_FALLBACK=false)');
                return sendAuthError(
                    req, res,
                    (result && result.status) || 401,
                    (result && result.message) || 'API key không hợp lệ. Vui lòng dùng Authorization: Bearer kira_sk_xxxxx hoặc Bearer <JWT>',
                    (result && result.code) || 'invalid_api_key'
                );
            }
            logAuthEvent(req, 'warn', '⚠️ FALLBACK: request không có xác thực hợp lệ → dùng API Key mặc định của hệ thống');
            req.user = null;
            req.apiKey = null;
            req.authMethod = 'fallback';
            req.authFallback = true;
            return next();
        }

        // Xác thực thành công (kira_sk_* hoặc JWT)
        req.user = result.user;
        req.apiKey = result.apiKey;
        req.authMethod = result.method;

        // Cập nhật usage (async, không làm drop kết nối)
        if (result.apiKey) {
            UserApiKey.findByIdAndUpdate(result.apiKey._id, {
                $inc: { usageCount: 1 },
                lastUsedAt: new Date()
            }).catch(err => console.error('[proxyAuth] Lỗi cập nhật usage:', err));
        }

        next();
    } catch (error) {
        // Luôn trả JSON thay vì để kết nối rớt
        console.error('[proxyAuth] Lỗi không mong muốn trong middleware xác thực:', error);
        return sendAuthError(req, res, 500, 'Lỗi xác thực API key', 'server_error');
    }
};

module.exports = proxyAuth;
