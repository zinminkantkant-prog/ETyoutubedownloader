import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# --- Render Port / Sleep Mode မဝင်စေရန် Background Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running smoothly!")

    def log_message(self, format, *args):
        pass # Console logs ရှုပ်မသွားစေရန် ပိတ်ထားပါသည်

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Background Thread သီးသန့်ဖြင့် Web Server ကို Run ခြင်း (Pyrogram Async Loop ကို လုံးဝ မထိခိုက်ပါ)
threading.Thread(target=run_health_check_server, daemon=True).start()


# --- သင့် မူရင်း Code (၁၀၀% မူလအတိုင်း) ---
API_ID = int(os.environ.get("API_ID", "2040"))
API_HASH = os.environ.get("API_HASH", "b18441a1ff607e10a989891a5462e627")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

app = Client("yt_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

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

    # Format / Quality Selection Buttons
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

    # Speed Optimization Settings
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

    loop = asyncio.get_event_loop()

    try:
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if call.data == "mp3":
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                else:
                    filename = filename.rsplit('.', 1)[0] + '.mp4'
                return filename, info.get('title', 'Video')

        filename, title = await loop.run_in_executor(None, download)

        await status_msg.edit_text("⬆️ Uploading to Telegram (Supports up to 2GB)...")

        # Direct sending via Pyrogram up to 2GB
        if call.data == "mp3":
            await client.send_audio(call.message.chat.id, audio=filename, title=title)
        else:
            await client.send_video(call.message.chat.id, video=filename, caption=title)

        if os.path.exists(filename):
            os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ An error occurred: {str(e)}")

print("Pyrogram Bot is running...")
app.run()
