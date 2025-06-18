import logging
import sqlite3
import asyncio
from datetime import datetime, date
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import nest_asyncio

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "7751711985:AAFNUH0Sur1abtPM2RYaXznG-aMrjAjdmUo"  # ⚠️ 请替换为你自己的
DB_PATH = "data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, username TEXT, phone TEXT, points INTEGER DEFAULT 0, plays INTEGER DEFAULT 0, created_at TEXT, last_play TEXT, invited_by INTEGER, inviter_rewarded INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS game_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game_type TEXT, result TEXT, points_change INTEGER, timestamp TEXT)")
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    inviter_id = None
    if context.args:
        try:
            inviter_id = int(context.args[0])
        except:
            pass

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone FROM users WHERE user_id = ?", (user.id,))
    row = c.fetchone()

    if not row:
        now = datetime.now().isoformat()
        c.execute("INSERT INTO users (user_id, first_name, last_name, username, plays, points, created_at, invited_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (user.id, user.first_name, user.last_name, user.username, 0, 0, now, inviter_id))
        conn.commit()
        phone = None
    else:
        phone = row[0]
    conn.close()

    if phone:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 掷骰子开始", callback_data="roll")]
        ])
        await update.message.reply_text(
            "✅ 你已授权手机号，可以发送 🎲 掷骰子开始游戏啦～",
            reply_markup=keyboard
        )
        return

    if update.message.chat.type == "private":
        button = KeyboardButton("📱 授权手机号", request_contact=True)
        keyboard = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("⚠️ 请授权手机号后才能参与游戏：", reply_markup=keyboard)
    else:
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}"
        await update.message.reply_text(
            f"📲 请点击我头像或直接 [点此私聊我]({link})，授权手机号才能参与游戏",
            parse_mode="Markdown"
        )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.contact.phone_number
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user.id))
    conn.commit()
    conn.close()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 掷骰子开始", callback_data="roll")]
    ])
    await update.message.reply_text("✅ 手机号授权成功！你现在可以点击下方按钮开始游戏", reply_markup=keyboard)
    check_and_reward_inviter(user.id, context)

async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_dice = update.message.dice.value
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_blocked, phone, plays FROM users WHERE user_id = ?", (user.id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("⚠️ 请先发送 /start 注册")
        return
    is_blocked, phone, plays = row
    if is_blocked:
        await update.message.reply_text("🚫 你已被封禁，无法参与游戏")
        return
    if not phone:
        await update.message.reply_text("📵 请先私聊我授权手机号再参与游戏")
        return
    if plays >= 10:
        await update.message.reply_text("📴 今日游戏次数已达上限（10 次）")
        return

    bot_msg = await update.message.reply_dice()
    await asyncio.sleep(3)
    bot_dice = bot_msg.dice.value

    if user_dice > bot_dice:
        score = 10
        result = "胜利"
        msg = f"🎉 你掷出 {user_dice}，我掷出 {bot_dice}，你赢了！+10积分"
    elif user_dice < bot_dice:
        score = -5
        result = "失败"
        msg = f"😢 你掷出 {user_dice}，我掷出 {bot_dice}，你输了 -5积分"
    else:
        score = 0
        result = "平局"
        msg = f"⚖️ 双方都掷出 {user_dice}，平局，积分不变"

    now = datetime.now().isoformat()
    c.execute("UPDATE users SET points = points + ?, plays = plays + 1, last_play = ? WHERE user_id = ?", (score, now, user.id))
    c.execute("INSERT INTO game_history (user_id, game_type, result, points_change, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user.id, "骰子", result, score, now))
    conn.commit()
    conn.close()

    await update.message.reply_text(msg)
    check_and_reward_inviter(user.id, context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "roll":
        await query.message.reply_text("🎲 请点击输入栏旁边的 🎲 按钮开始游戏！")

async def roll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎲 请点击输入栏旁边的骰子按钮掷骰开始游戏！")

async def show_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, first_name, points FROM users WHERE last_play LIKE ? ORDER BY points DESC LIMIT 10", (f"{today}%",))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 今日暂无积分记录")
        return
    medals = ["🥇", "🥈", "🥉"] + ["🎖"] * 7
    msg = "📊 今日排行榜：\n"
    for i, row in enumerate(rows):
        name = row[0] or row[1] or "匿名"
        msg += f"{medals[i]} {name[:4]}*** - {row[2]}分\n"
    await update.message.reply_text(msg)

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user.id}"
    await update.message.reply_text(f"🔗 你的邀请链接：\n{link}\n🎁 成功邀请他人可获得 +10 积分")

def reset_daily_plays():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET plays = 0")
    conn.commit()
    conn.close()

def check_and_reward_inviter(user_id, context):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT invited_by, phone, inviter_rewarded, plays FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        inviter_id, phone, rewarded, plays = row
        if inviter_id and phone and not rewarded and plays > 0:
            c.execute("UPDATE users SET points = points + 10 WHERE user_id = ?", (inviter_id,))
            c.execute("UPDATE users SET inviter_rewarded = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            try:
                context.bot.send_message(chat_id=inviter_id, text="🎁 你邀请的用户已完成游戏，获得 +10 积分奖励！")
            except:
                pass
    conn.close()

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.dice:
        await handle_dice(update, context)
    elif update.message.contact:
        await contact_handler(update, context)

async def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rank", show_rank))
    app.add_handler(CommandHandler("share", share))
    app.add_handler(CommandHandler("roll", roll_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.ALL, router))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(reset_daily_plays, "cron", hour=0)
    scheduler.start()
    print("🤖 Bot 启动成功")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
