/**
 * Google Sheets API Service — Lên lịch đăng bài & Quản lý lịch xuất bản tự động.
 *
 * - Xác thực bằng GoogleAuth + service-account.json (scope spreadsheets).
 * - appendScheduleToSheet(postData): ghi 1 dòng mới (12 cột A→L) vào Sheet1.
 *
 * Cấu trúc 12 cột (theo giao diện thực tế):
 *   A STT | B Tên Website | C Từ khoá chính | D Loại nội dung | E Prompt
 *   | F Số từ viết | G Ngày đăng (YYYY-MM-DD) | H Giờ đăng (HH:mm)
 *   | I Trạng thái | J Link bài viết | K Audit (TRUE/FALSE) | L Internal Link
 */
const path = require('path');
const fs = require('fs');
const { google } = require('googleapis');

const SHEET_ID = process.env.GOOGLE_SHEET_ID || '16TMNNZRF6kzyDNYZU4L_FZtyX16qPcACuhJ6HxGJrSg';
// Ưu tiên: env → service-account.json ở gốc repo (vertex-express, mới nhất)
//          → service_account.json ở gốc repo → server/service-account.json
const CREDENTIAL_CANDIDATES = [
    process.env.GOOGLE_SERVICE_ACCOUNT_FILE,
    path.join(__dirname, '..', '..', 'service-account.json'),
    path.join(__dirname, '..', '..', 'service_account.json'),
    path.join(__dirname, '..', 'service-account.json')
].filter(Boolean);
const SHEET_NAME = process.env.GOOGLE_SHEET_NAME || 'Trang tính1'; // tab thực tế (default "Sheet1" của Google VN)
const SCOPE = ['https://www.googleapis.com/auth/spreadsheets'];

let _sheetsClient = null;
let _sheetName = SHEET_NAME;

/** Tìm file credentials đầu tiên tồn tại trên đĩa. */
function resolveCredentialsPath() {
    for (const p of CREDENTIAL_CANDIDATES) {
        try {
            if (p && fs.existsSync(p)) return p;
        } catch (e) { /* ignore */ }
    }
    return CREDENTIAL_CANDIDATES[0] || null;
}

/**
 * Khởi tạo (lazy) Google Sheets client.
 * Credentials ưu tiên: env GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON) → file service-account.json
 * (gốc repo hoặc server/). Tự dò tab: nếu SHEET_NAME không tồn tại → tab đầu tiên.
 * @returns {Promise<object>} google.sheets({ version:'v4' })
 */
async function getSheetsClient() {
    if (_sheetsClient) return _sheetsClient;

    let auth;
    const envJson = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
    if (envJson && envJson.trim()) {
        try {
            // Dùng cho deploy (Streamlit Cloud Secrets) — không cần commit file key
            auth = new google.auth.GoogleAuth({
                credentials: JSON.parse(envJson),
                scopes: SCOPE,
            });
        } catch (e) {
            console.error('[googleSheetService] GOOGLE_SERVICE_ACCOUNT_JSON không hợp lệ:', e.message);
            throw new Error('GOOGLE_SERVICE_ACCOUNT_JSON không phải JSON hợp lệ của service account.');
        }
    } else {
        const keyFile = resolveCredentialsPath();
        if (!keyFile) {
            throw new Error('Không tìm thấy file service-account.json (gốc repo hoặc server/) hoặc biến GOOGLE_SERVICE_ACCOUNT_JSON.');
        }
        auth = new google.auth.GoogleAuth({
            keyFile,
            scopes: SCOPE,
        });
    }

    const authClient = await auth.getClient();
    _sheetsClient = google.sheets({ version: 'v4', auth: authClient });

    // Dò tên tab thực tế (mặc định 'Sheet1' của Google VN là 'Trang tính1')
    try {
        const meta = await _sheetsClient.spreadsheets.get({ spreadsheetId: SHEET_ID });
        const tabs = (meta.data.sheets || []).map(s => s.properties && s.properties.title).filter(Boolean);
        if (tabs.length && !tabs.includes(_sheetName)) {
            console.warn(`[googleSheetService] Không tìm thấy tab "${_sheetName}", tự dùng tab đầu tiên "${tabs[0]}".`);
            _sheetName = tabs[0];
        }
    } catch (e) {
        console.warn('[googleSheetService] Không đọc được danh sách tab, giữ mặc định:', e.message);
    }
    return _sheetsClient;
}

/**
 * Đọc toàn bộ giá trị trong một vùng (dùng để kiểm tra header / debug).
 */
async function getSheetValues(range = 'A:L') {
    try {
        const sheets = await getSheetsClient();
        const res = await sheets.spreadsheets.values.get({
            spreadsheetId: SHEET_ID,
            range: `${_sheetName}!${range}`,
        });
        return res.data.values || [];
    } catch (error) {
        console.error('[googleSheetService] Lỗi đọc Google Sheet:', error.message);
        throw error;
    }
}

/**
 * Tính STT tiếp theo: đọc cột A, lấy giá trị số lớn nhất + 1.
 * Nếu không đọc được (chưa có dữ liệu / thiếu quyền) → trả về chuỗi rỗng.
 * @returns {Promise<number|string>}
 */
async function getNextStt() {
    try {
        const sheets = await getSheetsClient();
        const res = await sheets.spreadsheets.values.get({
            spreadsheetId: SHEET_ID,
            range: `${_sheetName}!A:A`,
        });
        const rows = res.data.values || [];
        let max = 0;
        for (const r of rows) {
            const n = parseInt(String(r && r[0]).replace(/[^\d]/g, ''), 10);
            if (!isNaN(n) && n > max) max = n;
        }
        return max + 1;
    } catch (error) {
        console.warn('[googleSheetService] Không tính được STT:', error.message);
        return '';
    }
}

/**
 * Ghi thêm 1 dòng mới (12 cột A→L) vào Google Sheet.
 * @param {object} postData
 * @param {string}  [postData.websiteName]  - B: Tên Website (VD 'HieuTapHoa')
 * @param {string}  [postData.keyword]      - C: Từ khoá chính
 * @param {string}  [postData.contentType]  - D: Loại nội dung ('product' | 'blog')
 * @param {string}  [postData.prompt]       - E: Prompt đã dùng
 * @param {number}  [postData.wordCount]    - F: Số từ viết
 * @param {string}  [postData.publishDate]  - G: Ngày đăng YYYY-MM-DD
 * @param {string}  [postData.publishTime]  - H: Giờ đăng HH:mm
 * @param {string}  [postData.status]       - I: Trạng thái ('Success'|'Scheduled')
 * @param {string}  [postData.postUrl]      - J: Link bài viết (WordPress)
 * @param {boolean} [postData.audit]        - K: Audit (TRUE/FALSE)
 * @param {string}  [postData.internalLink] - L: Internal Link
 * @returns {Promise<{success: boolean, updatedRange?: string}>}
 * @throws {Error} nếu lỗi mạng / thiếu quyền (để route xử lý).
 */
async function appendScheduleToSheet(postData) {
    const data = postData || {};
    const stt = await getNextStt();
    const values = [[
        stt,                                            // A STT
        data.websiteName || '',                          // B Tên Website
        data.keyword || '',                              // C Từ khoá chính
        data.contentType || '',                          // D Loại nội dung
        data.prompt || '',                               // E Prompt
        data.wordCount || '',                            // F Số từ viết
        data.publishDate || '',                          // G Ngày đăng
        data.publishTime || '',                          // H Giờ đăng
        data.status || 'Scheduled',                      // I Trạng thái
        data.postUrl || '',                              // J Link bài viết
        data.audit === false ? 'FALSE' : 'TRUE',         // K Audit (tick box / boolean)
        data.internalLink || ''                          // L Internal Link
    ]];

    try {
        const sheets = await getSheetsClient();
        const res = await sheets.spreadsheets.values.append({
            spreadsheetId: SHEET_ID,
            range: `${_sheetName}!A:L`,
            valueInputOption: 'USER_ENTERED',
            insertDataOption: 'INSERT_ROWS',
            requestBody: { values },
        });
        const updatedRange = res.data.updates && res.data.updates.updatedRange;
        console.log(`[googleSheetService] ✅ Đã ghi lịch vào Google Sheet (${updatedRange || _sheetName}) cho "${data.keyword || ''}".`);
        return { success: true, updatedRange };
    } catch (error) {
        // Bọc try-catch: log rõ lỗi (mạng / quyền truy cập / sai scope)
        const detail = error.response && error.response.data
            ? JSON.stringify(error.response.data).slice(0, 400)
            : error.message;
        console.error(`[googleSheetService] ❌ Lỗi ghi Google Sheet cho "${data.keyword || ''}":`, detail);
        throw error;
    }
}

module.exports = {
    getSheetsClient,
    getSheetValues,
    getNextStt,
    appendScheduleToSheet,
    SHEET_ID,
};
