const ApiKey = require('../models/ApiKey');

/**
 * API Key Manager – Quản lý xoay vòng API Key
 * Hỗ trợ 2 chiến lược: sequential (tuần tự) và random (ngẫu nhiên)
 */
class ApiKeyManager {
    constructor() {
        this.keys = [];
        this.currentIndex = 0;
        this.lastRefresh = 0;
        this.refreshInterval = 5 * 60 * 1000; // Refresh cache mỗi 5 phút
        this.strategy = 'sequential'; // Mặc định tuần tự
    }

    /**
     * Refresh danh sách key từ database
     */
    async refreshKeys() {
        const now = Date.now();
        if (this.keys.length > 0 && now - this.lastRefresh < this.refreshInterval) {
            return; // Chưa cần refresh
        }

        this.keys = await ApiKey.find({ isActive: true }).lean();
        this.lastRefresh = now;

        if (this.currentIndex >= this.keys.length) {
            this.currentIndex = 0;
        }
    }

    /**
     * Lấy API Key tiếp theo
     * @param {string} strategy - 'sequential' hoặc 'random'
     * @returns {Object} { key, projectNumber, name, _id }
     */
    async getNextKey(strategy) {
        await this.refreshKeys();

        if (this.keys.length === 0) {
            // Fallback: dùng API Key mặc định của hệ thống từ env khi chưa cấu hình ApiKey trong DB
            const envKey = process.env.GEMINI_API_KEY || process.env.DEFAULT_GEMINI_API_KEY;
            if (envKey) {
                console.warn('[apiKeyManager] Không có ApiKey trong DB — fallback dùng GEMINI_API_KEY/DEFAULT_GEMINI_API_KEY từ env (credentials mặc định hệ thống).');
                return {
                    key: envKey,
                    projectNumber: process.env.GEMINI_PROJECT_ID || process.env.DEFAULT_GEMINI_PROJECT_ID || '',
                    name: 'env-default',
                    _id: null
                };
            }
            throw new Error('Không có API Key nào được cấu hình. Vui lòng thêm API Key trong trang quản trị hoặc đặt GEMINI_API_KEY trong .env.');
        }

        const useStrategy = strategy || this.strategy;
        let selectedKey;

        if (useStrategy === 'random') {
            const randomIndex = Math.floor(Math.random() * this.keys.length);
            selectedKey = this.keys[randomIndex];
        } else {
            // Sequential
            selectedKey = this.keys[this.currentIndex];
            this.currentIndex = (this.currentIndex + 1) % this.keys.length;
        }

        // Cập nhật usage count (async, không chờ)
        ApiKey.findByIdAndUpdate(selectedKey._id, {
            $inc: { usageCount: 1 },
            lastUsedAt: new Date()
        }).catch(err => console.error('Lỗi cập nhật usage count:', err));

        return {
            key: selectedKey.key,
            projectNumber: selectedKey.projectNumber,
            name: selectedKey.name,
            _id: selectedKey._id
        };
    }

    /**
     * Đánh dấu key bị lỗi (rate limit 429, etc.)
     */
    async markKeyError(keyId, errorMessage) {
        await ApiKey.findByIdAndUpdate(keyId, {
            lastError: errorMessage,
            lastErrorAt: new Date()
        });
    }

    /**
     * Force refresh cache
     */
    invalidateCache() {
        this.lastRefresh = 0;
        this.keys = [];
    }

    /**
     * Đặt chiến lược xoay vòng
     */
    setStrategy(strategy) {
        if (['sequential', 'random'].includes(strategy)) {
            this.strategy = strategy;
        }
    }
}

// Singleton instance
module.exports = new ApiKeyManager();
