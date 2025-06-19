import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # 加载本地 .env 环境变量

DB_URL = os.getenv("DATABASE_URL") or "postgresql://telegram_dice_bot_user:xxx@dpg-xxx/telegram_dice_bot"

def init_db():
    conn = psycopg2.connect(DB_URL)
    c = conn.cursor()

    # 创建 users 表
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone TEXT,
            points INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_play TEXT,
            invited_by BIGINT,
            inviter_rewarded INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )
    """)

    # 创建 game_history 表（可根据后续功能扩展）
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            game_result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully.")

if __name__ == "__main__":
    init_db()
