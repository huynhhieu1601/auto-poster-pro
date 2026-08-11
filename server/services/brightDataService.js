/**
 * Bright Data SERP API Service — Dữ liệu tra cứu thời gian thực (Grounding Data)
 * cho AI trước khi sinh bài viết.
 *
 * Endpoint: https://api.brightdata.com/request
 * Curl mẫu:
 *   curl https://api.brightdata.com/request \
 *     -H "Content-Type: application/json" \
 *     -H "Authorization: Bearer <API_KEY>" \
 *     -d '{"zone":"serp_api1","url":"https://www.google.com/search?q=pizza","format":"json","data_format":"parsed"}'
 */
const axios = require('axios');

const BRIGHTDATA_API_URL = 'https://api.brightdata.com/request';
const API_KEY = process.env.BRIGHTDATA_API_KEY || '';
const ZONE = process.env.BRIGHTDATA_SERP_ZONE || 'serp_api1';
const MAX_RESULTS = 5;

/**
 * Tự động tạo URL Google Search tiếng Việt cho từ khóa sản phẩm.
 * @param {string} keyword - Từ khóa sản phẩm (VD: 'iPad Air M3')
 * @returns {string}
 */
function buildSearchUrl(keyword) {
    const query = encodeURIComponent(`${keyword || ''} thông số kỹ thuật giá bán mới nhất`);
    return `https://www.google.com/search?q=${query}&hl=vi&gl=vn`;
}

/**
 * Bóc tách mảng organic (top 5) từ response Bright Data.
 * Bright Data sync response bọc trong { status_code, headers, body } với body là JSON string
 * chứa SERP thật (organic = [{ title, link, description, ... }]).
 */
function extractOrganicResults(data) {
    let payload = data;
    if (data && typeof data.body === 'string') {
        try {
            payload = JSON.parse(data.body);
        } catch (e) {
            payload = data;
        }
    } else if (data && data.body && typeof data.body === 'object') {
        payload = data.body;
    }
    const organic = (payload && (payload.organic || payload.organic_results)) || [];
    return organic.slice(0, MAX_RESULTS);
}

/** Lấy snippet/description từ một kết quả organic. */
function formatSnippet(result) {
    return result.snippet || result.description || '';
}

/** Lấy giá bán (nếu có) từ một kết quả organic. */
function extractPrice(result) {
    let price = result.price
        || result.extensions?.price
        || result.rich_snippet?.top?.detected_extensions?.price;
    if (price && typeof price === 'object') price = JSON.stringify(price);
    return price ? String(price) : '';
}

/**
 * Tổng hợp các kết quả organic thành chuỗi văn bản nền (Context):
 * Tiêu đề + Snippet + Giá bán (nếu có).
 */
function buildContextText(results) {
    const lines = [];
    results.forEach((r, i) => {
        const title = r.title || 'Không có tiêu đề';
        const url = r.url || r.link || '';
        const snippet = formatSnippet(r);
        const price = extractPrice(r);
        lines.push(`${i + 1}. ${title}`);
        if (price) lines.push(`   💰 Giá: ${price}`);
        if (url) lines.push(`   🔗 ${url}`);
        if (snippet) lines.push(`   📝 ${snippet}`);
    });
    return lines.join('\n');
}

/**
 * Tra cứu thời gian thực thông tin sản phẩm theo từ khóa.
 * @param {string} keyword - Từ khóa sản phẩm (VD: 'iPad Air M3')
 * @returns {Promise<string>} Chuỗi context (top 5 kết quả) hoặc "" nếu lỗi — không bao giờ throw.
 */
async function getRealtimeProductData(keyword) {
    try {
        if (!API_KEY) {
            console.warn('[brightDataService] Thiếu BRIGHTDATA_API_KEY trong .env — bỏ qua grounding.');
            return '';
        }
        const targetUrl = buildSearchUrl(keyword || '');
        console.log(`[brightDataService] Tra cứu SERP cho "${keyword || ''}": ${targetUrl}`);

        const { data } = await axios.post(
            BRIGHTDATA_API_URL,
            {
                zone: ZONE,
                url: targetUrl,
                format: 'json',
                data_format: 'parsed'
            },
            {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${API_KEY}`
                },
                timeout: 60000 // 60s (SERP sync thường 5-30s)
            }
        );

        const results = extractOrganicResults(data);
        if (!results.length) {
            console.warn(`[brightDataService] Không có kết quả organic cho "${keyword || ''}".`);
            return '';
        }

        const context = buildContextText(results);
        console.log(`[brightDataService] Lấy được ${results.length}/${MAX_RESULTS} kết quả cho "${keyword || ''}" (${context.length} ký tự).`);
        return context;
    } catch (error) {
        // Log đầy đủ nhưng KHÔNG làm crash server — trả về chuỗi rỗng
        const detail = error.response
            ? `HTTP ${error.response.status}: ${JSON.stringify(error.response.data || {}).slice(0, 300)}`
            : error.message;
        console.error(`[brightDataService] Lỗi tra cứu SERP cho "${keyword || ''}":`, detail);
        return '';
    }
}

module.exports = {
    getRealtimeProductData,
    buildSearchUrl,
    buildContextText,
    extractOrganicResults,
    extractPrice
};
