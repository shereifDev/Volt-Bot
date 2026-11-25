# El Nazer Bot v3 — IEEE Al-Azhar

## What's new in v3
- Group creator (`creator`) and group administrators (`administrator`) can both use `/setup`, `/lock`, and `/unlock`.
- Global replies support text, photo, video, audio, and voice.
- Global replies are managed in the bot's private chat and work in every group containing the bot.
- Existing v2 SQLite text replies are migrated automatically.

## Configure
Python 3.10+ recommended.

1. Create the bot with @BotFather and turn Group Privacy OFF.
2. Add the bot to each group as an admin. Grant Restrict Members permission if you want locking.
3. Create and activate a virtual environment, then install:
   `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`.
5. Set `BOT_TOKEN` and `OWNER_IDS` (your numeric Telegram user ID; multiple IDs separated by commas).
6. Run `python bot.py`.

## Manage global replies in private chat
Text:
`/addreply deadline | آخر موعد للتسليم الخميس`

Media:
- Send a photo, video, audio file, or voice note to the bot in private.
- Put this in the media caption: `keyword | optional caption`
- Example: `welcome | أهلاً بيكم في IEEE Al-Azhar`
- The bot stores Telegram's file_id, not a local file.

Commands:
- `/editreply old_keyword | new_keyword | new_text_response` (converts that reply to text)
- `/delreply keyword`
- `/replies`
- `/enable keyword`
- `/disable keyword`

## Group commands
- `/setup` — register the group and schedule midnight lock / 8 AM unlock.
- `/lock` — lock now.
- `/unlock` — unlock now.
- `/help`

## Notes
- Only IDs in OWNER_IDS can manage global replies.
- Group creator and group admins are both accepted for group commands.
- The bot must be an admin with Restrict Members permission to change group permissions.
- Test in a test group before broad deployment.
- Do not share BOT_TOKEN or upload `.env` to GitHub.
- The scheduler cannot replay missed jobs if the process was offline at the scheduled time.
