from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)
DB_PATH = "data.db"

def get_users():
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute("""
        SELECT username, first_name, points
        FROM users
        WHERE last_play LIKE ?
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET points = ?, plays = ?, is_blocked = ? WHERE user_id = ?",
              (points, plays, is_blocked, user_id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form.get('user_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/game_history/<int:user_id>')
def game_history(user_id):
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM game_history WHERE user_id = ?", (user_id,))
    total_count = c.fetchone()[0]
    c.execute("""
        SELECT game_type, result, points_change, timestamp
        FROM game_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (user_id, per_page, offset))
    records = c.fetchall()
    conn.close()
    return jsonify({
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "records": [
            {
                "game_type": r[0],
                "result": r[1],
                "points_change": r[2],
                "timestamp": r[3]
            } for r in records
        ]
    })

if __name__ == '__main__':
    app.run(debug=True)
