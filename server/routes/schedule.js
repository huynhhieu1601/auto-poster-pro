/**
 * Route Lên Lịch Đăng Bài — ghi lịch xuất bản vào Google Sheet.
 *
 * POST /api/v1/schedule
 * Body: { title, url, publishDate, status, ... }
 * → gọi appendScheduleToSheet() và trả { success: true, message: 'Đã lên lịch thành công' }
 */
const express = require('express');
const router = express.Router();
const { appendScheduleToSheet } = require('../services/googleSheetService');

router.post('/', async (req, res) => {
    try {
        const body = req.body || {};
        const title = (body.title || body.keyword || '').trim();

        if (!title) {
            return res.status(400).json({
                success: false,
                message: 'Thiếu trường bắt buộc: title (từ khoá / tiêu đề bài viết)'
            });
        }

        // Map body { title, url, publishDate, status } → postData theo 12 cột
        const postData = {
            websiteName: body.websiteName || 'HieuTapHoa',
            keyword: title,                        // Cột C — Từ khoá chính
            contentType: body.contentType || 'blog',
            prompt: body.prompt || '',
            wordCount: body.wordCount || '',
            publishDate: body.publishDate || '',   // YYYY-MM-DD
            publishTime: body.publishTime || '',   // HH:mm
            status: body.status || 'Scheduled',
            postUrl: body.url || body.postUrl || '',
            audit: body.audit === undefined ? true : !!body.audit,
            internalLink: body.internalLink || ''
        };

        const result = await appendScheduleToSheet(postData);

        return res.json({
            success: true,
            message: 'Đã lên lịch thành công',
            updatedRange: result.updatedRange || null
        });
    } catch (error) {
        console.error('[schedule] Lỗi xử lý lên lịch:', error.message);
        return res.status(500).json({
            success: false,
            message: 'Lỗi khi lên lịch: ' + (error.message || 'Lỗi không xác định')
        });
    }
});

module.exports = router;
