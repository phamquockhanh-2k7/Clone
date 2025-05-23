import requests
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackContext
import asyncio
import nest_asyncio
import random
from keep_alive import keep_alive

# Cho phép nest_asyncio để tránh xung đột vòng lặp
nest_asyncio.apply()

BOT_TOKEN = "8064426886:AAE5Zr980N-8LhGgnXGqUXwqlPthvdKA9H0"
API_KEY = "5d2e33c19847dea76f4fdb49695fd81aa669af86"
API_URL = "https://vuotlink.vip/api"

bot = Bot(token=BOT_TOKEN)
media_groups = {}
processing_tasks = {}

async def start(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "**👋 Chào mừng bạn!😍**\n"
        "**🔗 Gửi link bất kỳ để rút gọn.**\n"
        "**📷 Chuyển tiếp bài viết kèm ảnh/video, bot sẽ giữ nguyên caption & rút gọn link trong caption.**\n"
        "**💬 Mọi thắc mắc, hãy liên hệ admin.**",
        parse_mode="Markdown"
    )

async def format_text(text: str) -> str:
    lines = text.splitlines()
    new_lines = []
    for line in lines:
        words = line.split()
        new_words = []
        for word in words:
            if word.startswith("http"):
                params = {"api": API_KEY, "url": word, "format": "text"}
                response = requests.get(API_URL, params=params)
                short_link = response.text.strip() if response.status_code == 200 else word
                word = f"<s>{short_link}</s>"
            else:
                word = f"<b>{word}</b>"
            new_words.append(word)
        new_lines.append(" ".join(new_words))

    new_lines.append(
        '\n<b>Báo lỗi + đóng góp video tại đây</b> @nothinginthissss (có lỗi sẽ đền bù)\n'
        '<b>Theo dõi thông báo tại đây</b> @linkdinhcaovn\n'
        '<b>CÁCH XEM LINK(lỗi bot không gửi video):</b> @HuongDanVuotLink_SachKhongChu\n\n'
        '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/linkdinhcaovn/4">ấn vào đây!</a>'
    )

    return "\n".join(new_lines)

async def process_media_group(mgid: str, chat_id: int):
    await asyncio.sleep(random.uniform(3, 5))
    group = media_groups.pop(mgid, [])
    if not group:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không hợp lệ hoặc thiếu ảnh/video.")
        return

    group.sort(key=lambda m: m.message_id)
    caption = await format_text(group[0].caption) if group[0].caption else None
    media = []

    for i, msg in enumerate(group):
        if msg.photo:
            file_id = msg.photo[-1].file_id
            media.append(InputMediaPhoto(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))
        elif msg.video:
            file_id = msg.video.file_id
            media.append(InputMediaVideo(file_id, caption=caption if i == 0 else None, parse_mode="HTML"))

    if not media:
        await bot.send_message(chat_id=chat_id, text="⚠️ Bài viết không có ảnh hoặc video hợp lệ.")
        return

    try:
        await bot.send_media_group(chat_id=chat_id, media=media)
    except Exception as e:
        print(f"Lỗi khi gửi media_group: {e}")
        await bot.send_message(chat_id=chat_id, text="⚠️ Gửi bài viết thất bại. Có thể do file lỗi hoặc Telegram bị giới hạn.")

async def shorten_link(update: Update, context: CallbackContext):
    if not update.message or update.effective_chat.type != "private":
        return

    if update.message.media_group_id:
        mgid = update.message.media_group_id
        if mgid not in media_groups:
            media_groups[mgid] = []
            processing_tasks[mgid] = asyncio.create_task(process_media_group(mgid, update.effective_chat.id))
        media_groups[mgid].append(update.message)
        return

    if update.message.text and update.message.text.startswith("http"):
        params = {"api": API_KEY, "url": update.message.text.strip(), "format": "text"}
        response = requests.get(API_URL, params=params)
        if response.status_code == 200:
            short_link = response.text.strip()
            message = (
                "📢 <b>Bạn có link rút gọn mới</b>\n"
                f"🔗 <b>Link gốc:</b> <s>{update.message.text}</s>\n"
                f"🔍 <b>Link rút gọn:</b> {short_link}\n\n"
                '⚠️<b>Kênh xem không cần vượt :</b> <a href="https://t.me/sachkhongchuu/299">ấn vào đây</a>'
            )
            await update.message.reply_text(message, parse_mode="HTML")
        return

    if update.message.forward_origin:
        caption = update.message.caption or ""
        new_caption = await format_text(caption)
        await update.message.copy(chat_id=update.effective_chat.id, caption=new_caption, parse_mode="HTML")

def main():
    # 1) Giữ bot luôn "sống" qua Flask
    keep_alive()

    # 2) Khởi tạo và đăng ký handlers
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shorten_link))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.FORWARDED, shorten_link))

    print("✅ Bot đang chạy...")

    # 3) Bắt đầu polling, không đóng loop khi kết thúc
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
