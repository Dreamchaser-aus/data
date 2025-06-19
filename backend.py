from flask import Flask, render_template, request, jsonify
import psycopg2
from datetime import date
import os

app = Flask(__name__)

# ✅ 从环境变量读取数据库连接
DB_URL = os.getenv("postgresql://telegram_dice_bot_user:8VDuBQoqcwTXxENfkay0SfQTOJoVfFka@dpg-d197poh5pdvs73e1s1sg-a/telegram_dice_bot")

def get_conn():
    return psycopg2.connect(DB_URL)

def get_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.first_name, u.last_name, u.username, u.phone,
               u.points, u.plays, u.created_at, u.last_play,
               u.invited_by, u.inviter_rewarded, u.is_blocked,
               i.username
        FROM users u
        LEFT JOIN users i ON u.invited_by = i.user_id
    """)
    users = c.fetchall()
    conn.close()
    return users

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL AND phone != ''")
    authorized_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = c.fetchone()[0]
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    conn.close()
    return {
        'total_users': total_users,
        'authorized_users': authorized_users,
        'blocked_users': blocked_users,
        'total_points': total_points
    }

def get_rankings():
    conn = get_conn()
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute("""
        SELECT username, first_name, points
        FROM users
        WHERE last_play LIKE %s
        ORDER BY points DESC
        LIMIT 10
    """, (f"{today}%",))
    today_rank = c.fetchall()

    c.execute("""
        SELECT username, first_name, points
        FROM users
        ORDER BY points DESC
        LIMIT 10
    """)
    total_rank = c.fetchall()
    conn.close()
    return today_rank, total_rank

@app.route('/')
def dashboard():
    users = get_users()
    stats = get_stats()
    today_rank, total_rank = get_rankings()
    return render_template('dashboard.html', users=users, stats=stats, today_rank=today_rank, total_rank=total_rank)

@app.route('/update_user', methods=['POST'])
def update_user():
    user_id = request.form.get('user_id')
    points = request.form.get('points')
    plays = request.form.get('plays')
    is_blocked = request.form.get('is_blocked')
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET points = %s, plays = %s, is_blocked = %s WHERE user_id = %s",
              (points, plays, is_blocked, user_id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form.get('user_id')
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/game_history/<int:user_id>')
def game_history(user_id):
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    # 可扩展分页历史记录查询
    return '📄 Game history page is under construction.'

# ✅ 本地测试使用，Render 部署用 gunicorn 启动（不用这段）
if __name__ == '__main__':
    app.run(debug=True, port=5000)
