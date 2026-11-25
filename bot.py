import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from config import BOT_TOKEN, TIMEZONE, LOCK_TIME, UNLOCK_TIME, OWNER_IDS
from database import (
    init_db, register_group, get_groups, add_global_reply, delete_global_reply,
    edit_global_reply, list_global_replies, set_reply_enabled,
    get_saved_permissions, save_permissions, clear_saved_permissions
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("el_nazer")
TZ = ZoneInfo(TIMEZONE)


def is_bot_owner(user_id):
    return user_id in OWNER_IDS


async def owner_private_only(update):
    user, chat = update.effective_user, update.effective_chat
    if not user or not chat or chat.type != "private" or not is_bot_owner(user.id):
        await update.effective_message.reply_text("الأمر ده متاح لمدير البوت من الخاص فقط.")
        return False
    return True


async def group_admin_or_creator(update, context):
    """Both Telegram group administrators and the group creator may use group controls."""
    chat, user = update.effective_chat, update.effective_user
    if not chat or chat.type not in ("group", "supergroup") or not user:
        await update.effective_message.reply_text("استخدم الأمر داخل الجروب.")
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        allowed = member.status in ("administrator", "creator")
    except Exception:
        allowed = False
    if not allowed:
        await update.effective_message.reply_text("الأمر ده متاح لأدمن الجروب أو الـ Owner فقط.")
    return allowed


def split_pair(value):
    if "|" not in value:
        return None, None
    keyword, response = value.split("|", 1)
    return keyword.strip(), response.strip()


async def start(update, context):
    user, chat = update.effective_user, update.effective_chat
    if chat.type == "private" and user and is_bot_owner(user.id):
        await update.effective_message.reply_text(
            "أهلاً بيك في لوحة تحكم El Nazer Bot 🤖\n\n"
            "رد نصي عام:\n/addreply keyword | response\n\n"
            "رد بصورة/فيديو/صوت:\n"
            "ابعت الميديا في الخاص واكتب في الـ Caption:\n"
            "keyword | caption اختياري\n\n"
            "إدارة الردود:\n"
            "/editreply old_keyword | new_keyword | new_text_response\n"
            "/delreply keyword\n/replies\n/enable keyword\n/disable keyword\n\n"
            "كل الردود بتشتغل في كل الجروبات."
        )
    else:
        await update.effective_message.reply_text(
            "أنا El Nazer Bot 🤖\nضيفني لجروب IEEE Al-Azhar كأدمن وبعدها نفّذ /setup."
        )


# ---------- Global text replies: owner private chat ----------

async def addreply(update, context):
    if not await owner_private_only(update):
        return
    keyword, response = split_pair(" ".join(context.args))
    if not keyword or not response:
        await update.effective_message.reply_text("الصيغة: /addreply keyword | response")
        return
    add_global_reply(keyword, "text", None, response)
    await update.effective_message.reply_text(f"✅ اتضاف الرد النصي: {keyword}\nالنطاق: كل الجروبات")


async def delreply(update, context):
    if not await owner_private_only(update):
        return
    keyword = " ".join(context.args).strip()
    if not keyword:
        await update.effective_message.reply_text("استخدم: /delreply keyword")
        return
    await update.effective_message.reply_text(
        "🗑️ تم حذف الرد." if delete_global_reply(keyword) else "الكلمة دي مش موجودة."
    )


async def editreply(update, context):
    if not await owner_private_only(update):
        return
    parts = [x.strip() for x in " ".join(context.args).split("|")]
    if len(parts) != 3 or not all(parts):
        await update.effective_message.reply_text(
            "الصيغة: /editreply old_keyword | new_keyword | new_text_response"
        )
        return
    if edit_global_reply(parts[0], parts[1], "text", None, parts[2]):
        await update.effective_message.reply_text("✏️ تم تعديل الرد وتحويله إلى رد نصي.")
    else:
        await update.effective_message.reply_text("الكلمة القديمة مش موجودة.")


async def media_reply_upload(update, context):
    """Owner sends media in private chat with caption: keyword | optional caption."""
    if not await owner_private_only(update):
        return

    message = update.effective_message
    keyword, caption = split_pair(message.caption or "")
    if not keyword:
        await message.reply_text(
            "لازم تضيف Caption بالشكل ده:\nkeyword | caption اختياري\n\n"
            "مثال: deadline | آخر موعد للتسليم الخميس"
        )
        return

    media_type, file_id = None, None
    if message.photo:
        media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.audio:
        media_type, file_id = "audio", message.audio.file_id
    elif message.voice:
        media_type, file_id = "voice", message.voice.file_id

    if not media_type or not file_id:
        await message.reply_text("نوع الملف ده مش مدعوم حاليًا. ابعت صورة أو فيديو أو Audio أو Voice.")
        return

    add_global_reply(keyword, media_type, file_id, caption or None)
    await message.reply_text(
        f"✅ تم حفظ الرد بنجاح!\nالكلمة: {keyword}\nالنوع: {media_type}\nالنطاق: كل الجروبات"
    )


async def replies(update, context):
    if not await owner_private_only(update):
        return
    rows = list_global_replies()
    if not rows:
        await update.effective_message.reply_text("مفيش ردود عامة مضافة لسه.")
        return
    lines = ["📚 الردود العامة:"]
    for keyword, media_type, caption, enabled in rows:
        state = "🟢 شغال" if enabled else "⚪ متوقف"
        preview = (caption or "").replace("\n", " ")[:55]
        lines.append(f"{state} | {keyword} | {media_type} | {preview}")
    await update.effective_message.reply_text("\n".join(lines))


async def toggle_reply(update, context, enabled):
    if not await owner_private_only(update):
        return
    keyword = " ".join(context.args).strip()
    if not keyword:
        await update.effective_message.reply_text("اكتب الكلمة بعد الأمر.")
        return
    ok = set_reply_enabled(keyword, enabled)
    if not ok:
        await update.effective_message.reply_text("الكلمة دي مش موجودة.")
    else:
        await update.effective_message.reply_text("🟢 تم التفعيل." if enabled else "⚪ تم الإيقاف.")


async def enable(update, context):
    await toggle_reply(update, context, True)


async def disable(update, context):
    await toggle_reply(update, context, False)


# ---------- Group permissions and schedule ----------

def schedule_group(app, chat_id):
    for name in (f"lock_{chat_id}", f"unlock_{chat_id}"):
        for job in app.job_queue.get_jobs_by_name(name):
            job.schedule_removal()

    lock_h, lock_m = map(int, LOCK_TIME.split(":"))
    unlock_h, unlock_m = map(int, UNLOCK_TIME.split(":"))
    app.job_queue.run_daily(
        lock_job, time=time(lock_h, lock_m, tzinfo=TZ), days=tuple(range(7)),
        data=chat_id, name=f"lock_{chat_id}"
    )
    app.job_queue.run_daily(
        unlock_job, time=time(unlock_h, unlock_m, tzinfo=TZ), days=tuple(range(7)),
        data=chat_id, name=f"unlock_{chat_id}"
    )


async def lock_group(bot, chat_id):
    if get_saved_permissions(chat_id) is None:
        chat = await bot.get_chat(chat_id)
        if chat.permissions is not None:
            save_permissions(chat_id, chat.permissions.to_dict())

    blocked = ChatPermissions(
        can_send_messages=False, can_send_audios=False, can_send_documents=False,
        can_send_photos=False, can_send_videos=False, can_send_video_notes=False,
        can_send_voice_notes=False, can_send_polls=False,
        can_send_other_messages=False, can_add_web_page_previews=False
    )
    await bot.set_chat_permissions(chat_id, blocked)


async def unlock_group(bot, chat_id):
    saved = get_saved_permissions(chat_id)
    if saved is not None:
        await bot.set_chat_permissions(chat_id, ChatPermissions(**saved))
        clear_saved_permissions(chat_id)
    else:
        open_permissions = ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True
        )
        await bot.set_chat_permissions(chat_id, open_permissions)


async def lock_job(context):
    chat_id = context.job.data
    try:
        await lock_group(context.bot, chat_id)
        await context.bot.send_message(chat_id, "🌙 الجروب اتقفل لحد الساعة 8 صباحًا.")
    except Exception:
        log.exception("Scheduled lock failed for %s", chat_id)


async def unlock_job(context):
    chat_id = context.job.data
    try:
        await unlock_group(context.bot, chat_id)
        await context.bot.send_message(chat_id, "☀️ صباح الخير! الجروب اتفتح.")
    except Exception:
        log.exception("Scheduled unlock failed for %s", chat_id)


async def setup(update, context):
    if not await group_admin_or_creator(update, context):
        return
    chat = update.effective_chat
    register_group(chat.id, chat.title or str(chat.id))
    schedule_group(context.application, chat.id)
    await update.effective_message.reply_text(
        "✅ اتسجل الجروب.\nالردود العامة شغالة هنا تلقائيًا.\n"
        "القفل 12 منتصف الليل والفتح 8 صباحًا بتوقيت القاهرة."
    )


async def lock_cmd(update, context):
    if not await group_admin_or_creator(update, context):
        return
    try:
        await lock_group(context.bot, update.effective_chat.id)
        await update.effective_message.reply_text("🔒 تم قفل الجروب.")
    except Exception:
        log.exception("Manual lock failed")
        await update.effective_message.reply_text("فشل القفل. تأكد إن البوت Admin ومعاه Restrict Members.")


async def unlock_cmd(update, context):
    if not await group_admin_or_creator(update, context):
        return
    try:
        await unlock_group(context.bot, update.effective_chat.id)
        await update.effective_message.reply_text("🔓 تم فتح الجروب.")
    except Exception:
        log.exception("Manual unlock failed")
        await update.effective_message.reply_text("فشل الفتح. راجع صلاحيات البوت.")


async def help_cmd(update, context):
    await update.effective_message.reply_text(
        "🤖 El Nazer Bot | IEEE Al-Azhar\n"
        "/setup — تسجيل الجروب وتفعيل الجدول\n/lock — قفل الآن\n"
        "/unlock — فتح الآن\n/help — المساعدة\n"
        "الأوامر الإدارية متاحة لأدمن الجروب والـ Owner (Creator)."
    )


# ---------- Send saved media/text into any group ----------

async def send_reply(bot, chat_id, media_type, file_id, caption):
    if media_type == "text":
        await bot.send_message(chat_id=chat_id, text=caption or "")
    elif media_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
    elif media_type == "video":
        await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
    elif media_type == "audio":
        await bot.send_audio(chat_id=chat_id, audio=file_id, caption=caption)
    elif media_type == "voice":
        await bot.send_voice(chat_id=chat_id, voice=file_id, caption=caption)


async def auto_reply(update, context):
    message, chat, user = update.effective_message, update.effective_chat, update.effective_user
    if not message or not message.text or not chat or chat.type not in ("group", "supergroup"):
        return
    if message.text.startswith("/") or (user and user.is_bot):
        return

    text_lower = message.text.casefold()
    for keyword, media_type, file_id, caption, enabled in list_global_replies():
        if enabled and keyword.casefold() in text_lower:
            try:
                await send_reply(context.bot, chat.id, media_type, file_id, caption)
            except Exception:
                log.exception("Could not send global reply for keyword %s", keyword)
            return


async def post_init(app):
    init_db()
    for chat_id in get_groups():
        schedule_group(app, chat_id)
    log.info("El Nazer Bot started. Scheduled groups: %s", len(get_groups()))



class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Alive")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Health server listening on port %s", port)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not OWNER_IDS:
        raise RuntimeError("Set OWNER_IDS in .env before starting.")

    start_health_server()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    private = filters.ChatType.PRIVATE
    for command, handler in [
        ("addreply", addreply), ("delreply", delreply), ("editreply", editreply),
        ("replies", replies), ("enable", enable), ("disable", disable)
    ]:
        app.add_handler(CommandHandler(command, handler, filters=private))

    media_filter = filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
    app.add_handler(MessageHandler(private & media_filter, media_reply_upload))

    groups = filters.ChatType.GROUPS
    app.add_handler(CommandHandler("setup", setup, filters=groups))
    app.add_handler(CommandHandler("lock", lock_cmd, filters=groups))
    app.add_handler(CommandHandler("unlock", unlock_cmd, filters=groups))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
