import logging
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
from sqlalchemy import create_engine, text
import nest_asyncio

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "7751711985:AAFNUH0Sur1abtPM2RYaXznG-aMrjAjdmUo"  # 🔁 Replace with your bot token

# ✅ PostgreSQL DB
PG_URL = "postgresql://telegram_dice_bot_user:8VDuBQoqcwTXxENfkay0SfQTOJoVfFka@dpg-d197poh5pdvs73e1s1sg-a.oregon-postgres.render.com/telegram_dice_bot"
engine = create_engine(PG_URL)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone TEXT,
            points INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0,
            created_at TEXT,
            last_play TEXT,
            invited_by BIGINT,
            inviter_rewarded INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )"""))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS game_history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            game_type TEXT,
            result TEXT,
            points_change INTEGER,
            timestamp TEXT
        )"""))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    inviter_id = int(context.args[0]) if context.args else None

    with engine.begin() as conn:
        res = conn.execute(text("SELECT phone FROM users WHERE user_id = :id"), {"id": user.id}).fetchone()
        if not res:
            now = datetime.now().isoformat()
            conn.execute(text("""
                INSERT INTO users (user_id, first_name, last_name, username, plays, points, created_at, invited_by)
                VALUES (:uid, :fn, :ln, :un, 0, 0, :created, :inv)
            """), {
                "uid": user.id, "fn": user.first_name, "ln": user.last_name,
                "un": user.username, "created": now, "inv": inviter_id
            })
            phone = None
        else:
            phone = res[0]

    if phone:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 掷骰子开始", callback_data="roll")]
        ])
        await update.message.reply_text("✅ 你已授权手机号，可以开始游戏：", reply_markup=keyboard)
    elif update.message.chat.type == "private":
        keyboard = ReplyKeyboardMarkup([[KeyboardButton("📱 授权手机号", request_contact=True)]], resize_keyboard=True)
        await update.message.reply_text("⚠️ 请授权手机号才能玩游戏：", reply_markup=keyboard)
    else:
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}"
        await update.message.reply_text(
            f"📲 请 [点此私聊我]({link}) 授权手机号后参与游戏。",
            parse_mode="Markdown"
        )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.contact.phone_number
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET phone = :p WHERE user_id = :uid"), {"p": phone, "uid": user.id})

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 掷骰子开始", callback_data="roll")]
    ])
    await update.message.reply_text("✅ 手机号授权成功！你可以开始游戏：", reply_markup=keyboard)
    check_and_reward_inviter(user.id, context)

async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_dice = update.message.dice.value

    with engine.begin() as conn:
        row = conn.execute(text("SELECT is_blocked, phone, plays FROM users WHERE user_id = :id"), {"id": user.id}).fetchone()
        if not row:
            await update.message.reply_text("⚠️ 请先 /start 注册")
            return
        is_blocked, phone, plays = row
        if is_blocked:
            await update.message.reply_text("🚫 你已被封禁")
            return
        if not phone:
            await update.message.reply_text("📱 请私聊我授权手机号")
            return
        if plays >= 10:
            await update.message.reply_text("📴 今日游戏已达上限")
            return

    bot_msg = await update.message.reply_dice()
    await asyncio.sleep(3)
    bot_dice = bot_msg.dice.value

    if user_dice > bot_dice:
        score = 10
        result = "胜利"
        msg = f"🎉 你赢了！+10积分"
    elif user_dice < bot_dice:
        score = -5
        result = "失败"
        msg = f"😢 你输了 -5积分"
    else:
        score = 0
        result = "平局"
        msg = f"⚖️ 平局，积分不变"

    now = datetime.now().isoformat()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE users SET points = points + :s, plays = plays + 1, last_play = :t WHERE user_id = :uid
        """), {"s": score, "t": now, "uid": user.id})
        conn.execute(text("""
            INSERT INTO game_history (user_id, game_type, result, points_change, timestamp)
            VALUES (:uid, '骰子', :r, :s, :t)
        """), {"uid": user.id, "r": result, "s": score, "t": now})

    await update.message.reply_text(msg)
    check_and_reward_inviter(user.id, context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("🎲 请点下方骰子按钮掷骰！")

async def roll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎲 请点输入栏旁边的骰子按钮")

async def show_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = date.today().isoformat()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT username, first_name, points FROM users
            WHERE last_play LIKE :t ORDER BY points DESC LIMIT 10
        """), {"t": f"{today}%"}).fetchall()

    if not rows:
        await update.message.reply_text("📭 今日暂无积分")
        return

    medals = ["🥇", "🥈", "🥉"] + ["🎖"] * 7
    msg = "📊 今日排行榜：\n"
    for i, (username, first_name, points) in enumerate(rows):
        name = username or first_name or "匿名"
        msg += f"{medals[i]} {name[:4]}*** - {points}分\n"
    await update.message.reply_text(msg)

async def share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user.id}"
    await update.message.reply_text(f"🔗 邀请链接：\n{link}\n🎁 邀请好友可获得 +10 积分")

def reset_daily_plays():
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET plays = 0"))

def check_and_reward_inviter(user_id, context):
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT invited_by, phone, inviter_rewarded, plays FROM users WHERE user_id = :id
        """), {"id": user_id}).fetchone()
        if row:
            inviter_id, phone, rewarded, plays = row
            if inviter_id and phone and not rewarded and plays > 0:
                conn.execute(text("UPDATE users SET points = points + 10 WHERE user_id = :id"), {"id": inviter_id})
                conn.execute(text("UPDATE users SET inviter_rewarded = 1 WHERE user_id = :id"), {"id": user_id})
                try:
                    context.bot.send_message(chat_id=inviter_id, text="🎁 你邀请的用户已完成游戏，获得 +10积分奖励！")
                except:
                    pass

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
