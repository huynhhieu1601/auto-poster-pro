import logging
import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
BOT_TOKEN = "8694016442:AAHEV5iSsOTX1X-a-nTHrnvQrk3dIBWjE5g" # Đã tự điền token của bạn
SERVICE_ACCOUNT_FILE = "service_account.json"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/16TMNNZRF6kzyDNYZU4L_FZtyX16qPcACuhJ6HxGJrSg/edit"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def get_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(GOOGLE_SHEET_URL).sheet1
    return sheet

async def viet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Lấy nội dung sau câu lệnh /viet
        raw_text = update.message.text[5:].strip()
        if not raw_text:
            raise ValueError("Empty text")

        parts = [p.strip() for p in raw_text.split('|')]
        
        # Mặc định dữ liệu
        website = parts[0] if len(parts) > 0 else ""
        keyword = parts[1] if len(parts) > 1 else ""
        content_type = parts[2] if len(parts) > 2 else "post"
        word_count = parts[3] if len(parts) > 3 else "1500"
        
        now = datetime.datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))  # giờ VN (UTC+7), không lệch khi server chạy UTC
        post_date = parts[4] if len(parts) > 4 and parts[4] else now.strftime("%Y-%m-%d")
        post_time = parts[5].strip(". ") if len(parts) > 5 and parts[5] else now.strftime("%H:%M")
        
        if not website or not keyword:
            await update.message.reply_text("❌ Thiếu thông tin! Cú pháp chuẩn:\n`/viet TênWeb | Từ khóa | Type | SốTừ | Ngày | Giờ`", parse_mode='Markdown')
            return

        # Ghi vào Sheet (10 cột)
        sheet = get_sheet()
        new_row = [
            "",             # Col A: STT
            website,        # Col B: Tên Website
            keyword,        # Col C: Từ khoá chính
            content_type,   # Col D: Loại nội dung
            "",             # Col E: Prompt
            word_count,     # Col F: Số từ viết
            post_date,      # Col G: Ngày đăng
            post_time,      # Col H: Giờ đăng
            "",             # Col I: Trạng thái
            ""              # Col J: Link bài viết
        ]
        
        sheet.append_row(new_row)

        reply_msg = (
            f"✅ **Đã thêm lệnh viết bài lên lịch thành công!**\n\n"
            f"🌐 **Website:** {website}\n"
            f"📝 **Từ khóa:** {keyword}\n"
            f"📋 **Loại:** {content_type.upper()}\n"
            f"📏 **Số từ:** {word_count}\n"
            f"📅 **Lịch đăng:** {post_date} lúc {post_time}\n\n"
            f"⏳ Bot tự động sẽ quét và xuất bản đúng khung giờ trên!"
        )
        await update.message.reply_text(reply_msg, parse_mode='Markdown')

    except Exception as e:
        error_guide = (
            "❌ **Cú pháp chưa chính xác!**\n\n"
            "Hãy nhập theo định dạng phân cách bởi dấu `|`:\n"
            "`/viet HieuTapHoa | Cắt Bao Quy Đầu | post | 2000 | 2026-08-08 | 11:05`\n\n"
            "💡 *Mẹo:* Bạn có thể bỏ trống ngày/giờ để đăng ngay lập tức:\n"
            "`/viet HieuTapHoa | Cắt Bao Quy Đầu | post | 2000`"
        )
        await update.message.reply_text(error_guide, parse_mode='Markdown')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("viet", viet_command))
    print("🤖 Telegram Bot đang chạy...")
    app.run_polling()