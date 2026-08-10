# auto-poster-pro
Hệ thống tự động hóa bài viết WordPress &amp; WooCommerce.

## Cấu trúc

```
├── app.py                  # App Streamlit (client) — gọi /v1/chat/completions
├── telegram_bot.py         # Bot Telegram nhận lệnh /viet
├── server/                 # Express proxy (Kira Agent Platform, OpenAI-compatible /v1/*)
│   ├── app.js              # Entry point Express
│   ├── middleware/         # proxyAuth (kira_sk_* / JWT / fallback credentials hệ thống)
│   ├── routes/api/proxy.js # POST /v1/chat/completions, /v1/images/generations, ...
│   ├── routes/auth.js      # Register tự khởi tạo API key mặc định + credits
│   └── .env.example        # PROXY_ALLOW_FALLBACK, GEMINI_API_KEY, DEFAULT_USER_CREDITS...
└── requirements.txt
```

## Chạy Express server (proxy /v1/*)

```bash
cd server
cp .env.example .env   # chỉnh MONGODB_URI, JWT_SECRET, GEMINI_API_KEY...
npm install
npm run seed           # tạo admin + model mặc định
npm start              # mặc định cổng 3001 (xem PORT trong .env)
```

> App Streamlit mặc định gọi `http://localhost:3003/v1` — đổi `LOCAL_API_BASE`/`PORT` cho khớp nhau.

## Xác thực & Fallback cho tài khoản mới

- **Server** (`server/middleware/proxyAuth.js`): chấp nhận `Authorization: Bearer kira_sk_*`, hoặc **JWT**, hoặc **fallback** (không có token hợp lệ / tài khoản mới chưa có key) → tự dùng API Key mặc định hệ thống (`ApiKey` trong DB hoặc `GEMINI_API_KEY` trong env) thay vì trả 401/drop connection. Tắt bằng `PROXY_ALLOW_FALLBACK=false`.
- **Register** (`server/routes/auth.js`): tự tạo `kira_sk_*` key mặc định + gán `DEFAULT_USER_CREDITS`.
- **Client** (`app.py`): khi đăng ký tự khởi tạo credits=2000 + session token + API base/key/project mặc định; `generate_text`/`generate_image` tự **fallback** về credentials mặc định hệ thống nếu gặp 401/missing credentials/connection error, kèm log chi tiết từng lần gọi.

## Streamlit app

```bash
pip install -r requirements.txt
streamlit run app.py
```
