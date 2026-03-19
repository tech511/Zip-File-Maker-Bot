import os, re, asyncio, time, math, subprocess

from pyrogram import Client
from telegram import *
from telegram.ext import *

# ============ CONFIG ============
BOT_TOKEN = "YOUR_BOT_TOKEN"
API_ID = 123456
API_HASH = "YOUR_API_HASH"

OWNER_ID = 123456789
FORCE_CHANNEL = "your_channel"
OWNER_USERNAME = "your_username"
UPDATE_CHANNEL = "https://t.me/your_channel"
LOG_CHANNEL = -100xxxxxxxx

MAX_USERS = 4
TIMEOUT = 600
SPLIT_SIZE = 2 * 1024 * 1024 * 1024

# ============ DB ============
admins = set()
banned = set()
sessions = {}
prefix_db = {}
pending = {}

queue = asyncio.Queue()
active = set()
cancel_flag = {}

START_IMAGE = None

pyro = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ============ AUTH ============
def is_owner(x): return x == OWNER_ID
def is_admin(x): return x in admins
def is_auth(x): return is_owner(x) or is_admin(x)

async def deny(update):
    await update.message.reply_text("<b><i>You Are Not Authorized 🙄</i></b>", parse_mode="HTML")

# ============ START ============
async def start(update, context):
    user = update.effective_user

    txt = f"<b><i>Hello {user.first_name}\n\nI Am A Simple File Convertor Bot. I Can Converter All Files Or Videos In Zip Files.\n\nMaintained By :- @AniWorld_Bot_Hub</i></b>"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Owner", url=f"https://t.me/{OWNER_USERNAME}")],
        [InlineKeyboardButton("Update Channel", url=UPDATE_CHANNEL)]
    ])

    if START_IMAGE:
        await update.message.reply_photo(START_IMAGE, caption=txt, reply_markup=btn, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=btn, parse_mode="HTML")

# ============ ADD IMAGE ============
async def add_image(update, context):
    if not is_owner(update.effective_user.id):
        return await deny(update)

    pending["img"] = True
    await update.message.reply_text("<b><i>Send Me The Image😊</i></b>", parse_mode="HTML")

async def save_img(update, context):
    global START_IMAGE
    if pending.get("img"):
        f = await update.message.photo[-1].get_file()
        await f.download_to_drive("start.jpg")
        START_IMAGE = "start.jpg"
        pending["img"] = False

# ============ ADD ADMIN ============
async def add_admin(update, context):
    if not is_owner(update.effective_user.id):
        return await deny(update)

    pending["admin"] = True
    await update.message.reply_text("<b><i>Send Your ID🥴</i></b>", parse_mode="HTML")

async def set_admin(update, context):
    if pending.get("admin"):
        admins.add(int(update.message.text))
        pending["admin"] = False
        await update.message.reply_text("<b><i>Admin Added🙂</i></b>", parse_mode="HTML")

# ============ PREFIX ============
async def prefix(update, context):
    if not is_auth(update.effective_user.id):
        return await deny(update)

    pending["prefix"] = update.effective_user.id
    await update.message.reply_text("<b><i>Send Your Prefix 🤧</i></b>", parse_mode="HTML")

async def set_prefix(update, context):
    uid = update.effective_user.id
    if pending.get("prefix") == uid:
        prefix_db[uid] = update.message.text
        pending["prefix"] = None
        await update.message.reply_text("<b><i>Your Prefix Added🙃</i></b>", parse_mode="HTML")

# ============ BATCH ============
async def batch(update, context):
    uid = update.effective_user.id
    if not is_auth(uid): return await deny(update)

    sessions[uid] = {"files": [], "time": time.time()}
    await update.message.reply_text("<b><i>Send Your Videos One By One😮‍💨</i></b>", parse_mode="HTML")

# ============ FILE ============
async def file_handler(update, context):
    uid = update.effective_user.id
    if uid not in sessions: return

    msg = await update.message.reply_text("Downloading...")

    file = await pyro.download_media(update.message.document.file_id)
    sessions[uid]["files"].append(file)

    count = len(sessions[uid]["files"])
    size = sum(os.path.getsize(f) for f in sessions[uid]["files"])

    await msg.edit_text(
        f"<b><i>{count} Files Added ✅\nTotal Size: {size//(1024*1024)} MB\n\n/lzip -n [File name] [All EP] [File Quality]</i></b>",
        parse_mode="HTML"
    )

# ============ WATERMARK ============
def watermark(inp, out):
    subprocess.run([
        "ffmpeg", "-i", inp,
        "-vf", "drawtext=text='Powered By @AniWorld_Zone':x=10:y=H-th-10:fontsize=24:fontcolor=white",
        "-c:a", "copy", out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ============ SPLIT ============
def split_file(file):
    if os.path.getsize(file) < SPLIT_SIZE:
        return [file]

    parts = []
    with open(file, "rb") as f:
        i = 0
        while True:
            chunk = f.read(SPLIT_SIZE)
            if not chunk: break
            part = f"{file}.part{i}"
            with open(part, "wb") as p:
                p.write(chunk)
            parts.append(part)
            i += 1
    return parts

# ============ LZIP ============
async def lzip(update, context):
    uid = update.effective_user.id
    if not is_auth(uid): return await deny(update)

    if uid not in sessions: return

    if time.time() - sessions[uid]["time"] > TIMEOUT:
        return await update.message.reply_text("<b><i>Time Limit Reached 😆</i></b>", parse_mode="HTML")

    meta = re.findall(r"\[(.*?)\]", update.message.text)
    if len(meta) < 3: return

    await update.message.reply_text("<b><i>Strating...🚀</i></b>", parse_mode="HTML")
    await queue.put((uid, meta, sessions[uid]["files"]))

# ============ WORKER ============
async def worker(app):
    while True:
        uid, meta, files = await queue.get()
        active.add(uid)
        cancel_flag[uid] = False

        msg = await app.bot.send_message(uid, "Processing...")

        try:
            prefix = prefix_db.get(uid, "")
            name, ep, quality = meta[0], meta[1], meta[2]

            for i, f in enumerate(files):
                if cancel_flag[uid]: break

                wm = f"{f}_wm.mp4"
                watermark(f, wm)

                zipname = f"{uid}_{i}.zip"
                subprocess.run(["zip", zipname, wm])

                parts = split_file(zipname)

                for part in parts:
                    await app.bot.send_document(
                        uid,
                        open(part, "rb"),
                        caption=f"{prefix} [{name}] [EP {i+1}] [{quality}]"
                    )
                    os.remove(part)

                os.remove(wm)
                os.remove(zipname)

                await msg.edit_text(f"Processed {i+1}/{len(files)}")

        finally:
            active.remove(uid)
            sessions.pop(uid, None)
            await msg.delete()
            queue.task_done()

# ============ CANCEL ============
async def cancel(update, context):
    uid = update.effective_user.id
    if uid in active:
        cancel_flag[uid] = True
        await update.message.reply_text("<b><i>All Progress Are Stopped 😑</i></b>", parse_mode="HTML")
    else:
        await update.message.reply_text("<b><i>No Task Was Running 😁</i></b>", parse_mode="HTML")

# ============ MAIN ============
async def main():
    await pyro.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_image", add_image))
    app.add_handler(CommandHandler("add_admin", add_admin))
    app.add_handler(CommandHandler("batch", batch))
    app.add_handler(CommandHandler("lzip", lzip))
    app.add_handler(CommandHandler("prefix", prefix))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(MessageHandler(filters.PHOTO, save_img))
    app.add_handler(MessageHandler(filters.TEXT, set_admin))
    app.add_handler(MessageHandler(filters.TEXT, set_prefix))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

    asyncio.create_task(worker(app))

    print("Bot Running...")
    await app.run_polling()

asyncio.run(main())
