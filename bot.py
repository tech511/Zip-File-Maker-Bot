import os
import re
import time
import zipfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ CONFIG ============
API_ID = 123456
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 8207582785

DOWNLOAD_DIR = "downloads"
ZIP_DIR = "zips"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(ZIP_DIR, exist_ok=True)

app = Client("final_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ============ DATA ============
admins = set()
approved_users = set()
banned_users = set()
users_batch = {}
prefix_data = {}
active_tasks = set()
start_image = None

# ============ HELPERS ============
def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid in admins or is_owner(uid)
def is_approved(uid): return uid in approved_users or is_admin(uid)

def extract_episode(text):
    patterns = [
        r"S(\d+)[\s._-]?E(\d+)",
        r"Season\s*(\d+)\s*Episode\s*(\d+)",
        r"E(\d+)"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            if len(m.groups()) == 2:
                return f"S{int(m.group(1)):02d}E{int(m.group(2)):02d}"
            else:
                return f"E{int(m.group(1)):02d}"
    return None

def progress_bar(done, total, speed, status):
    percent = int((done/total)*100)
    bar = "█"*(percent//10) + "░"*(10-percent//10)
    return f"""
{status}

[{bar}] {percent}%
⚡ Speed: {speed:.2f} MB/s
📦 {done}/{total}
"""

# ============ START ============
@app.on_message(filters.command("start"))
async def start(client, message):

    text = f"""**╔═══『 🤖 ZIP MAKER BOT 』═══╗**

**👋 Hello, {message.from_user.first_name}**

__I Am An Advanced File To Zip Maker Bot.__  
__I Can Convert Your Videos & Files Into Zip Easily.__

***⚡ Fast • Smart • Reliable ⚡***

> **Maintain By:** @AniWorld_Bot_Hub

**╚═══════════════════════╝**"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Owner", url="https://t.me/AniWorld_Bot_Hub"),
            InlineKeyboardButton("📜 Commands", callback_data="cmd")
        ],
        [
            InlineKeyboardButton("📢 Update Channel", url="https://t.me/AniWorld_Bot_Hub")
        ]
    ])

    if start_image:
        await message.reply_photo(start_image, caption=text, reply_markup=buttons)
    else:
        await message.reply_text(text, reply_markup=buttons)

# ============ COMMAND UI ============
@app.on_callback_query(filters.regex("cmd"))
async def cmd(client, query):
    text = """**📜 Commands**

/start To Check Bot Alive Or Not😵‍💫
/batch To Convert Multiple Files😗
/lzip To Convert Files Into Zip📦
/prefix To Set Prefix🏷️
/add_admin To Add Admin {Only Owner Can Use}👑
/add_image To Add Image {Only Owner Can Use}🖼️
/panel To See Bot Dashboard {Only Owner Can Use}📊"""

    await query.message.edit_text(text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back")]
        ])
    )

@app.on_callback_query(filters.regex("back"))
async def back(client, query):
    await start(client, query.message)

# ============ ADD ADMIN ============
@app.on_message(filters.command("add_admin"))
async def add_admin(client, message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("**You're Not Authorized 😤**")

    try:
        uid = int(message.text.split()[1])
        admins.add(uid)
        await message.reply_text(f"✅ Admin Added: {uid}")
    except:
        await message.reply_text("Usage: /add_admin user_id")

# ============ ADD IMAGE ============
@app.on_message(filters.command("add_image"))
async def add_image(client, message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("**You're Not Authorized 😤**")

    await message.reply_text("Send Image 🖼️")

# SINGLE PHOTO HANDLER (NO DUPLICATE)
@app.on_message(filters.photo)
async def save_image(client, message):
    global start_image

    if message.from_user.id != OWNER_ID:
        return

    start_image = message.photo.file_id
    await message.reply_text("✅ Image Saved")

# ============ PREFIX ============
@app.on_message(filters.command("prefix"))
async def prefix(client, message):
    prefix_data[message.from_user.id] = message.text.replace("/prefix", "").strip()
    await message.reply_text("Prefix Saved 🏷️")

# ============ PANEL ============
@app.on_message(filters.command("panel"))
async def panel(client, message):
    if not is_owner(message.from_user.id):
        return

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Approve User", callback_data="approve")],
        [InlineKeyboardButton("Ban User", callback_data="ban")],
        [InlineKeyboardButton("Clean Disk", callback_data="clean")]
    ])

    await message.reply_text("Admin Panel ⚙️", reply_markup=buttons)

@app.on_callback_query(filters.regex("clean"))
async def clean_disk(client, query):
    for f in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, f))
    for f in os.listdir(ZIP_DIR):
        os.remove(os.path.join(ZIP_DIR, f))
    await query.answer("Disk Cleaned 🧹", show_alert=True)

# ============ BATCH ============
@app.on_message(filters.command("batch"))
async def batch(client, message):
    uid = message.from_user.id

    if uid in banned_users:
        return await message.reply_text("Banned ❌")

    if not is_approved(uid):
        return await message.reply_text("Not Approved ❌")

    if len(active_tasks) >= 4:
        return await message.reply_text("Bot Busy 😵‍💫")

    users_batch[uid] = []
    await message.reply_text("Send Files 📂")

# ============ COLLECT ============
@app.on_message(filters.video | filters.document | filters.audio)
async def collect(client, message):
    uid = message.from_user.id
    if uid not in users_batch:
        return

    users_batch[uid].append(message)
    await message.reply_text(f"File Added ✅ Total: {len(users_batch[uid])}")

# ============ LZIP ============
@app.on_message(filters.command("lzip"))
async def lzip(client, message):
    uid = message.from_user.id

    if not is_approved(uid):
        return await message.reply_text("Not Approved ❌")

    files = users_batch.get(uid)
    if not files:
        return await message.reply_text("No Files ❌")

    match = re.findall(r"\[(.*?)\]", message.text)
    name = match[0] if len(match)>0 else "Series"
    quality = match[-1] if len(match)>1 else ""

    prefix = prefix_data.get(uid, "")

    msg = await message.reply_text("Starting... ⏳")
    start_time = time.time()

    zip_path = f"{ZIP_DIR}/{uid}.zip"
    z = zipfile.ZipFile(zip_path, "w")

    for i, m in enumerate(files):
        speed = (i+1)/(time.time()-start_time+1)

        await msg.edit_text(progress_bar(i+1, len(files), speed, "📥 Downloading"))

        file_path = await m.download(file_name=f"{DOWNLOAD_DIR}/{uid}_{i}")

        ep = extract_episode(m.caption or "") or f"E{i+1:02d}"
        new_name = f"{prefix} {name} {ep} {quality}.mkv"
        new_path = f"{DOWNLOAD_DIR}/{new_name}"

        os.rename(file_path, new_path)

        await msg.edit_text(progress_bar(i+1, len(files), speed, "📦 Zipping"))
        z.write(new_path, new_name)

    z.close()

    # SPLIT 2GB
    parts = []
    size = os.path.getsize(zip_path)

    if size > 2*1024*1024*1024:
        part_size = 2*1024*1024*1024
        with open(zip_path, "rb") as f:
            i = 1
            while True:
                chunk = f.read(part_size)
                if not chunk:
                    break
                part = f"{zip_path}.{i:03d}"
                with open(part, "wb") as p:
                    p.write(chunk)
                parts.append(part)
                i += 1
    else:
        parts.append(zip_path)

    for p in parts:
        await msg.edit_text("📤 Uploading...")
        await message.reply_document(p)

    # CLEAN
    for f in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, f))
    for p in parts:
        os.remove(p)

    users_batch[uid] = []
    active_tasks.discard(uid)

# ============ RUN ============
print("Bot Running...")
app.run()
