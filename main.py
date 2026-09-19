import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from aiohttp import web

# Environment Variables
API_ID = int(os.environ.get("API_ID", "2040"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("yt_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# --- Render Sleep မဝင်စေရန် Web Server ---
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

# --- Bot Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Welcome! Send me a YouTube link. You can choose to download as MP3 or select your preferred video quality.")

@app.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply_text("Dev- @ZMK_112")

@app.on_message(filters.text & ~filters.forwarded)
async def handle_link(client, message):
    url = message.text.strip()
    if not ("youtube.com" in url or "youtu.be" in url):
        return

    user_id = message.from_user.id
    user_data[user_id] = url

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎧 MP3 (Audio)", callback_data="mp3")],
        [InlineKeyboardButton("🎬 360p (Fast & Small)", callback_data="360p"),
         InlineKeyboardButton("🎬 720p (HD)", callback_data="720p")]
    ])

    await message.reply_text("Please select the Format / Quality you want to download:", reply_markup=markup)

@app.on_callback_query()
async def callback_query(client, call):
    user_id = call.from_user.id
    url = user_data.get(user_id)

    if not url:
        await call.answer("Link has expired. Please send a new link.", show_alert=True)
        return

    await call.answer(f"Starting download for {call.data.upper()}...")
    status_msg = await call.message.reply_text("⏳ Downloading from YouTube...")

    base_opts = {
        'source_address': '0.0.0.0',
        'retries': 10,
        'concurrent_fragment_downloads': 5,
        'outtmpl': '%(id)s.%(ext)s',
    }

    if call.data == "mp3":
        ydl_opts = {
            **base_opts,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }
    elif call.data == "360p":
        ydl_opts = {
            **base_opts,
            'format': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
            'merge_output_format': 'mp4',
        }
    else:  # 720p
        ydl_opts = {
            **base_opts,
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'merge_output_format': 'mp4',
        }

    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if call.data == "mp3":
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            else:
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            return filename, info.get('title', 'Video')

    try:
        # Download ဆွဲစဉ် Bot မဟန်းသွားစေရန် asyncio.to_thread သုံးထားပါသည်
        filename, title = await asyncio.to_thread(download)

        await status_msg.edit_text("⬆️ Uploading to Telegram...")

        if call.data == "mp3":
            await client.send_audio(call.message.chat.id, audio=filename, title=title)
        else:
            await client.send_video(call.message.chat.id, video=filename, caption=title)

        if os.path.exists(filename):
            os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ An error occurred: {str(e)}")

# --- Execution ---
if __name__ == "__main__":
    # Event Loop တစ်ခုတည်းထဲတွင် Web Server နှင့် Pyrogram Bot တွဲဖက် Run ခြင်း
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    print("Pyrogram Bot is starting...")
    app.run()
