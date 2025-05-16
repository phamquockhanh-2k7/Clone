import secrets
import string
import asyncio
import threading
from datetime import datetime
from threading import Lock
import requests
from flask import Flask
from telegram import Update, InputMediaPhoto, InputMediaVideo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Config
BOT_TOKEN = "7851783179:AAFu58Cs9w1Z7i-xU4pPhnISgg0Sq3vfaPs"
FIREBASE_URL = "https://bot-telegram-99852-default-rtdb.firebaseio.com/shared"
CHANNEL_USERNAME = "@hoahocduong_vip"  # Đổi thành username kênh thực tế

# Thread-safe storage
user_files = {}
user_alias = {}
user_protection = {}  # user_id: True = bảo vệ, False = không bảo vệ
data_lock = Lock()

def generate_alias(length=7):
    date_prefix = datetime.now().strftime("%d%m%Y")
    random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))
    return date_prefix + random_part

async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not user:
            return False
            
        # Kiểm tra thành viên kênh
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user.id)
        if member.status in ['member', 'administrator', 'creator']:
            return True

        # Tạo link xác nhận động
        start_args = context.args
        if update.message and update.message.text.startswith('/start') and start_args:
            confirm_link = f"https://t.me/{context.bot.username}?start={start_args[0]}"
        else:
            confirm_link = f"https://t.me/{context.bot.username}?start=start"

        # Tạo nút bấm
        keyboard = [
            [InlineKeyboardButton("🔥 THAM GIA KÊNH NGAY", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("🔓 XÁC NHẬN ĐÃ THAM GIA", url=confirm_link)]
        ]
        
        await update.message.reply_text(
            "📛 BẠN PHẢI THAM GIA KÊNH TRƯỚC KHI SỬ DỤNG BOT!\n"
            f"👉 Kênh yêu cầu: {CHANNEL_USERNAME}\n"
            "✅ Sau khi tham gia, nhấn nút XÁC NHẬN để tiếp tục",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return False
        
    except Exception as e:
        print(f"Lỗi kiểm tra kênh: {e}")
        await update.message.reply_text("⚠️ Chết mẹ bot lỗi rồi, nhờ bạn báo cho admin @nothinginthissss (admin sẽ free cho bạn 1 link, cảm ơn bạn)")
        return False

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    protect = user_protection.get(user_id, True)

    args = context.args
    if args:
        alias = args[0]
        url = f"{FIREBASE_URL}/{alias}.json"

        try:
            res = await asyncio.to_thread(requests.get, url)
            if res.status_code == 200 and res.json():
                media_items = res.json()
                media_group = []
                text_content = []

                for item in media_items:
                    if item["type"] == "photo":
                        media_group.append(InputMediaPhoto(item["file_id"]))
                    elif item["type"] == "video":
                        media_group.append(InputMediaVideo(item["file_id"]))
                    elif item["type"] == "text":
                        text_content.append(item["file_id"])

                if text_content:
                    await update.message.reply_text("\n\n".join(text_content), protect_content=protect)

                for i in range(0, len(media_group), 10):
                    await update.message.reply_media_group(media_group[i:i+10], protect_content=protect)
                    await asyncio.sleep(0.5)
            else:
                await update.message.reply_text("❌ Không tìm thấy dữ liệu với mã này.")
        except Exception:
            await update.message.reply_text("🔒 Lỗi kết nối database")
    else:
        await update.message.reply_text("📥 Gửi lệnh để bắt đầu tạo liên kết lưu trữ nội dung. Nếu bạn muốn sử dụng miễn phí hãy liên hệ @nothinginthissss để được cấp quyền")

# /newlink handler
async def newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    with data_lock:
        user_files[user_id] = []
        user_alias[user_id] = generate_alias()
    await update.message.reply_text("✅ Bây giờ bạn có thể gửi ảnh, video hoặc text. Khi xong hãy nhắn /done để tạo link.")

# handle ảnh/video/text
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    with data_lock:
        if user_id not in user_files:
            return

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        entry = {"file_id": file_id, "type": "photo"}
    elif update.message.video:
        file_id = update.message.video.file_id
        entry = {"file_id": file_id, "type": "video"}
    elif update.message.text:
        text = update.message.text
        entry = {"file_id": text, "type": "text"}
    else:
        return

    with data_lock:
        if entry not in user_files[user_id]:
            user_files[user_id].append(entry)

# /done handler
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return

    user_id = update.message.from_user.id
    with data_lock:
        files = user_files.get(user_id, [])
        alias = user_alias.get(user_id)
        user_files.pop(user_id, None)
        user_alias.pop(user_id, None)

    if not files or not alias:
        await update.message.reply_text("❌ Bạn chưa bắt đầu bằng link hoặc chưa gửi nội dung.")
        return

    url = f"{FIREBASE_URL}/{alias}.json"

    try:
        response = await asyncio.to_thread(requests.put, url, json=files)
        if response.status_code == 200:
            link = f"https://t.me/upbaiviet_bot?start={alias}"
            await update.message.reply_text(
                f"✅ Đã lưu thành công!\n🔗 Link truy cập: {link}\n"
                f"📦 Tổng số nội dung: {len(files)} (Ảnh/Video/Text)"
            )
        else:
            await update.message.reply_text("❌ Có vẻ link này bị lỗi, báo lỗi cho @nothinginthissss")
    except Exception:
        await update.message.reply_text("🔒Nếu bạn chưa thấy video, báo ngay cho admin @nothinginthissss để được hỗ trợ nhé, cảm ơn bạn!")

# /sigmaboy on/off
async def sigmaboy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not await check_channel_membership(update, context):
        return
    user_id = update.message.from_user.id
    args = context.args
    if args and args[0].lower() == "on":
        user_protection[user_id] = False  # Mở khóa
    elif args and args[0].lower() == "off":
        user_protection[user_id] = True   # Bảo vệ
    await update.message.reply_text(".")  # Phản hồi ngầm

# Flask web server
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_web():
    app_web.run(host="0.0.0.0", port=8000)

# Chạy bot Telegram
def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newlink", newlink))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("sigmaboy", sigmaboy))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & ~filters.COMMAND), handle_message))
    app.run_polling()

# Chạy cả bot và web server
if __name__ == '__main__':
    threading.Thread(target=run_web).start()
    run_bot()
