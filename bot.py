import os
import time
import asyncio
import zipfile
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
API_ID = 123456
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"

OWNER_ID = 123456789
OWNER_USERNAME = "AniWorld_Bot_Hub"
CHANNEL_LINK = "https://t.me/YOUR_CHANNEL"

DOWNLOAD_DIR = "downloads"
OUTPUT_DIR = "output"

MAX_SPLIT = 2000000000
AUTO_DELETE_TIME = 300

MAX_PARALLEL_DOWNLOADS = 1
THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= DATABASE =================
admins = set()
banned = set()
start_image = None
batch_mode = {}

# ================= QUEUE =================
task_queue = asyncio.Queue()
download_semaphore = asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS)

async def worker():
    while True:
        task = await task_queue.get()
        try:
            await task()
        except Exception as e:
            print("Queue Error:", e)
        task_queue.task_done()

asyncio.get_event_loop().create_task(worker())
asyncio.get_event_loop().create_task(worker())

# ================= AUTO DELETE =================
async def auto_delete(file_path):
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print("Delete Error:", e)

# ================= PROGRESS WITH ETA =================
last_update_time = {}

async def progress(current, total, message, start):
    msg_id = message.id
    now = time.time()

    # Update every 5 seconds
    if msg_id in last_update_time and now - last_update_time[msg_id] < 5:
        return
    last_update_time[msg_id] = now

    diff = now - start
    speed = current / diff if diff else 0
    percent = (current / total) * 100 if total else 0

    # ETA calculation
    eta = (total - current) / speed if speed > 0 else 0
    eta_min, eta_sec = divmod(int(eta), 60)

    # Pretty small progress bar
    bar_len = 20
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    text = f"""
📦 [{bar}] {percent:.2f}%
⚡ {speed/1024/1024:.2f} MB/s
⏱ ETA: {eta_min}m {eta_sec}s
"""
    try:
        await message.edit_text(text)
    except:
        pass

# ================= FILE SPLITTER =================
def split_file(file_path):
    parts = []
    if os.path.getsize(file_path) <= MAX_SPLIT:
        return [file_path]

    with open(file_path, "rb") as f:
        i = 1
        while True:
            chunk = f.read(MAX_SPLIT)
            if not chunk:
                break
            part_name = f"{file_path}.part{i}"
            with open(part_name, "wb") as p:
                p.write(chunk)
            parts.append(part_name)
            i += 1
    return parts

# ================= BOT =================
app = Client(
    "termux_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=24
)

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id in banned:
        return

    text = f"""
Hi {message.from_user.first_name}

_I Am Advance Zip File Maker And Extractor Bot.
I Can Convert Any Video Or Files Into Zip Files._

Maintain By:- @{OWNER_USERNAME}
"""

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Owner", url=f"https://t.me/{OWNER_USERNAME}")],
        [InlineKeyboardButton("Update Channel", url=CHANNEL_LINK)]
    ])

    if start_image:
        await message.reply_photo(start_image, caption=text, reply_markup=buttons)
    else:
        await message.reply_text(text, reply_markup=buttons)

# ================= BATCH =================
@app.on_message(filters.command("batch"))
async def batch(client, message):
    if message.from_user.id in banned:
        return
    batch_mode[message.from_user.id] = []
    await message.reply_text("Send me video one by one 😗")

# ================= DONE =================
@app.on_message(filters.command("done"))
async def done_batch(client, message):
    user = message.from_user.id
    files = batch_mode.get(user)
    if not files:
        return await message.reply_text("No batch files")

    msg = await message.reply_text("Creating batch zip...")
    zip_path = OUTPUT_DIR + "/batch.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for f in files:
            z.write(f)

    parts = split_file(zip_path)
    for part in parts:
        await client.send_document(message.chat.id, part)
        asyncio.create_task(auto_delete(part))

    batch_mode.pop(user, None)

# ================= ADMIN =================
@app.on_message(filters.command("add_admin"))
async def add_admin(client, message):
    if message.from_user.id != OWNER_ID:
        return
    uid = int(message.text.split()[1])
    admins.add(uid)
    await message.reply_text("Admin added")

@app.on_message(filters.command("ban"))
async def ban_user(client, message):
    if message.from_user.id != OWNER_ID:
        return
    uid = int(message.text.split()[1])
    banned.add(uid)
    await message.reply_text("User banned")

@app.on_message(filters.command("unban"))
async def unban_user(client, message):
    if message.from_user.id != OWNER_ID:
        return
    uid = int(message.text.split()[1])
    banned.discard(uid)
    await message.reply_text("User unbanned")

# ================= SET IMAGE =================
@app.on_message(filters.command("add_image"))
async def set_image_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return
    await message.reply_text("Send me the image 😁")

    @app.on_message(filters.photo)
    async def save_img(client, msg):
        global start_image
        start_image = msg.photo.file_id
        await msg.reply_text("Start image saved")

# ================= FILE HANDLER =================
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_file(client, message):
    if message.from_user.id in banned:
        return

    async def task():
        async with download_semaphore:
            msg = await message.reply_text("Downloading...")
            start_time = time.time()

            # PYROGRAM DOWNLOAD (Telegram only)
            file_path = await message.download(file_name=f"{DOWNLOAD_DIR}/")
            asyncio.create_task(auto_delete(file_path))

            # AUTO BATCH
            batch_mode.setdefault(message.from_user.id, []).append(file_path)
            await msg.edit_text("Added to batch automatically ✅")

    await task_queue.put(task)

# ================= BUTTON =================
@app.on_callback_query()
async def buttons(client, callback_query):
    data = callback_query.data
    msg = callback_query.message

    if data.startswith("zip"):
        file_path = data.split("|")[1]
        zip_path = OUTPUT_DIR + "/output.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
            z.write(file_path)
        parts = split_file(zip_path)
        for part in parts:
            await client.send_document(msg.chat.id, part)
            asyncio.create_task(auto_delete(part))

    elif data.startswith("extract"):
        file_path = data.split("|")[1]
        extract_dir = OUTPUT_DIR + "/extracted"
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(extract_dir)
            for root, _, files in os.walk(extract_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    await client.send_document(msg.chat.id, full_path)
                    asyncio.create_task(auto_delete(full_path))
        except:
            await msg.reply_text("Extraction failed ❌")
    else:
        input_file = data
        output = OUTPUT_DIR + "/audio.mp3"
        os.system(f'ffmpeg -i "{input_file}" -vn -ab 192k "{output}"')
        parts = split_file(output)
        for part in parts:
            await client.send_document(msg.chat.id, part)
            asyncio.create_task(auto_delete(part))

# ================= RUN =================
print("Bot Running...")
app.run()
