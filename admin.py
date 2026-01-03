import os
from telegram import Update
from telegram.ext import ContextTypes
import database

# You should move ADMIN_ID to .env logic in main bot, but here we can check specific IDs
# or a list of IDs.
ADMIN_IDS = [int(os.getenv("ADMIN_ID", "0"))] 

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /admin command."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return # Silent ignore
    
    total, premium = database.get_stats()
    msg = (
        f"🕵️‍♂️ **Admin Panel**\n\n"
        f"👥 Total Users: {total}\n"
        f"💎 Premium Users: {premium}\n\n"
        f"Commands:\n"
        f"`/add_premium <user_id>` - Give premium\n"
        f"`/remove_premium <user_id>` - Remove premium"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def add_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium to a user."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    try:
        target_id = int(context.args[0])
        database.set_subscription(target_id, 1)
        await update.message.reply_text(f"✅ Premium granted to user {target_id}")
        # Notify user (optional, requires bot to have chat with user)
        try:
            await context.bot.send_message(target_id, "🎉 You have been upgraded to PREMIUM! Enjoy unlimited access and all voices.")
        except:
            await update.message.reply_text("⚠️ User updated in DB, but could not send notification.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add_premium <user_id>")

async def remove_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove premium from a user."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    try:
        target_id = int(context.args[0])
        database.set_subscription(target_id, 0)
        await update.message.reply_text(f"❌ Premium removed from user {target_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /remove_premium <user_id>")
