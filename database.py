import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DB_PATH", "biztracker.db")

DEFAULT_SHOP_ITEMS = [
    (1,  "☕", "Café de luxe",       "Starbucks ou café haut de gamme",            30,  "bronze"),
    (2,  "🏋️","Session sport",      "Séance de sport ou activité physique",        60,  "bronze"),
    (3,  "🍦", "Dessert premium",    "Sushi, glace fancy, peu importe",             80,  "bronze"),
    (4,  "🎬", "Movie night",        "Soirée films / série de ton choix",          150,  "bronze"),
    (5,  "🍕", "Resto de luxe",      "Le restau que tu veux",                      250,  "silver"),
    (6,  "🌴", "Free day",           "Journée complète sans travailler",           350,  "silver"),
    (7,  "🎧", "Nouvel accessoire",  "Gadget, accessoire, achat plaisir",          400,  "silver"),
    (8,  "🎮", "Nouveau jeu",        "Steam, PS Store ou autre",                   500,  "gold"),
    (9,  "✈️", "Weekend trip",       "Une nuit quelque part",                     1500,  "gold"),
    (10, "👑", "Big reward",         "Ton plus gros rêve — tu le mérites",        3000,  "legend"),
]

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()
        self._seed_shop()

    def _init_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                name            TEXT,
                coins           INTEGER DEFAULT 0,
                xp              INTEGER DEFAULT 0,
                streak          INTEGER DEFAULT 0,
                best_streak     INTEGER DEFAULT 0,
                last_activity   TEXT,
                todoist_token   TEXT,
                notion_token    TEXT,
                notion_db_id    TEXT,
                morning_remind  INTEGER DEFAULT 1,
                evening_remind  INTEGER DEFAULT 1,
                remind_hour_am  INTEGER DEFAULT 8,
                remind_hour_pm  INTEGER DEFAULT 21,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER,
                description     TEXT,
                difficulty      TEXT DEFAULT 'medium',
                source          TEXT DEFAULT 'manual',
                coins_earned    INTEGER,
                xp_earned       INTEGER,
                todoist_id      TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS revenues (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                amount      REAL,
                source      TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                name        TEXT,
                active      INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                habit_id    INTEGER,
                done_date   TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS weekly_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                text        TEXT,
                done        INTEGER DEFAULT 0,
                week_start  TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS weekly_challenges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                title       TEXT,
                description TEXT,
                target      INTEGER,
                progress    INTEGER DEFAULT 0,
                reward_coins INTEGER,
                week_start  TEXT,
                done        INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS shop_items (
                id          INTEGER PRIMARY KEY,
                emoji       TEXT,
                name        TEXT,
                description TEXT,
                cost        INTEGER,
                tier        TEXT DEFAULT 'bronze'
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                item_id     INTEGER,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                stat_date   TEXT,
                tasks_done  INTEGER DEFAULT 0,
                coins_earned INTEGER DEFAULT 0,
                xp_earned   INTEGER DEFAULT 0,
                revenue     REAL DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, stat_date)
            );
        """)
        self.conn.commit()

    def _seed_shop(self):
        c = self.conn.cursor()
        for item in DEFAULT_SHOP_ITEMS:
            c.execute("INSERT OR IGNORE INTO shop_items VALUES (?,?,?,?,?,?)", item)
        self.conn.commit()

    def _week_start(self):
        today = date.today()
        return (today - timedelta(days=today.weekday())).isoformat()

    def _update_daily_stats(self, uid, coins=0, xp=0, tasks=0, revenue=0):
        today = date.today().isoformat()
        self.conn.execute("""
            INSERT INTO daily_stats (user_id, stat_date, tasks_done, coins_earned, xp_earned, revenue)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, stat_date) DO UPDATE SET
                tasks_done = tasks_done + excluded.tasks_done,
                coins_earned = coins_earned + excluded.coins_earned,
                xp_earned = xp_earned + excluded.xp_earned,
                revenue = revenue + excluded.revenue
        """, (uid, today, tasks, coins, xp, revenue))
        self.conn.commit()

    # ── USERS ──
    def ensure_user(self, uid, name):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?,?)", (uid, name))
        self.conn.commit()

    def get_user(self, uid):
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def get_all_users(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT id, name FROM users").fetchall()
        return [dict(r) for r in rows]

    def set_user_field(self, uid, field, value):
        self.conn.execute(f"UPDATE users SET {field}=? WHERE id=?", (value, uid))
        self.conn.commit()

    def add_coins(self, uid, amount):
        self.conn.execute("UPDATE users SET coins = coins + ? WHERE id=?", (amount, uid))
        self.conn.commit()
        self._update_daily_stats(uid, coins=amount)

    def spend_coins(self, uid, amount):
        self.conn.execute("UPDATE users SET coins = MAX(0, coins - ?) WHERE id=?", (amount, uid))
        self.conn.commit()

    def add_xp(self, uid, amount):
        self.conn.execute("UPDATE users SET xp = xp + ? WHERE id=?", (amount, uid))
        self.conn.commit()
        self._update_daily_stats(uid, xp=amount)

    def update_streak(self, uid):
        c = self.conn.cursor()
        user = dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        last = user.get("last_activity")
        if last == today_str:
            return user["streak"]
        elif last == yesterday_str:
            new_streak = user["streak"] + 1
        else:
            new_streak = 1
        best = max(new_streak, user.get("best_streak", 0))
        self.conn.execute(
            "UPDATE users SET streak=?, best_streak=?, last_activity=? WHERE id=?",
            (new_streak, best, today_str, uid)
        )
        self.conn.commit()
        return new_streak

    def get_streak(self, uid):
        c = self.conn.cursor()
        row = c.execute("SELECT streak FROM users WHERE id=?", (uid,)).fetchone()
        return row["streak"] if row else 0

    # ── TASKS ──
    def add_task(self, uid, description, difficulty, coins, xp, source="manual", todoist_id=None):
        self.conn.execute(
            "INSERT INTO tasks (user_id, description, difficulty, coins_earned, xp_earned, source, todoist_id) VALUES (?,?,?,?,?,?,?)",
            (uid, description, difficulty, coins, xp, source, todoist_id)
        )
        self.conn.commit()
        self._update_daily_stats(uid, tasks=1)

    def todoist_task_exists(self, todoist_id):
        c = self.conn.cursor()
        row = c.execute("SELECT id FROM tasks WHERE todoist_id=?", (todoist_id,)).fetchone()
        return row is not None

    def get_today_tasks(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND DATE(created_at)=?", (uid, today)
        ).fetchall()]

    def get_recent_tasks(self, uid, days=7):
        since = (date.today() - timedelta(days=days)).isoformat()
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND DATE(created_at)>=? ORDER BY created_at DESC",
            (uid, since)
        ).fetchall()]

    def get_weekly_task_count(self, uid, weeks_ago=0):
        ws = date.today() - timedelta(days=date.today().weekday() + weeks_ago * 7)
        we = ws + timedelta(days=6)
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE user_id=? AND DATE(created_at)>=? AND DATE(created_at)<=?",
            (uid, ws.isoformat(), we.isoformat())
        ).fetchone()
        return row["cnt"]

    # ── REVENUE ──
    def add_revenue(self, uid, amount, source):
        self.conn.execute(
            "INSERT INTO revenues (user_id, amount, source) VALUES (?,?,?)",
            (uid, amount, source)
        )
        self.conn.commit()
        self._update_daily_stats(uid, revenue=amount)

    def get_today_revenue(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM revenues WHERE user_id=? AND DATE(created_at)=?",
            (uid, today)
        ).fetchone()
        return row["total"]

    def get_week_revenue(self, uid, weeks_ago=0):
        ws = date.today() - timedelta(days=date.today().weekday() + weeks_ago * 7)
        we = ws + timedelta(days=6)
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM revenues WHERE user_id=? AND DATE(created_at)>=? AND DATE(created_at)<=?",
            (uid, ws.isoformat(), we.isoformat())
        ).fetchone()
        return row["total"]

    def get_recent_revenues(self, uid, days=7):
        since = (date.today() - timedelta(days=days)).isoformat()
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM revenues WHERE user_id=? AND DATE(created_at)>=? ORDER BY created_at DESC",
            (uid, since)
        ).fetchall()]

    # ── HABITS ──
    def add_habit(self, uid, name):
        self.conn.execute("INSERT INTO habits (user_id, name) VALUES (?,?)", (uid, name))
        self.conn.commit()

    def get_habits(self, uid):
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM habits WHERE user_id=? AND active=1", (uid,)
        ).fetchall()]

    def get_today_habits(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        habits = c.execute("SELECT * FROM habits WHERE user_id=? AND active=1", (uid,)).fetchall()
        result = []
        for h in habits:
            log = c.execute(
                "SELECT id FROM habit_logs WHERE user_id=? AND habit_id=? AND done_date=?",
                (uid, h["id"], today)
            ).fetchone()
            d = dict(h)
            d["done_today"] = log is not None
            result.append(d)
        return result

    def is_habit_done_today(self, uid, habit_id):
        today = date.today().isoformat()
        c = self.conn.cursor()
        return c.execute(
            "SELECT id FROM habit_logs WHERE user_id=? AND habit_id=? AND done_date=?",
            (uid, habit_id, today)
        ).fetchone() is not None

    def complete_habit_today(self, uid, habit_id):
        today = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO habit_logs (user_id, habit_id, done_date) VALUES (?,?,?)",
            (uid, habit_id, today)
        )
        self.conn.commit()
        c = self.conn.cursor()
        row = c.execute("SELECT name FROM habits WHERE id=?", (habit_id,)).fetchone()
        return row["name"] if row else "Habitude"

    # ── WEEKLY GOALS ──
    def add_weekly_goal(self, uid, text):
        self.conn.execute(
            "INSERT INTO weekly_goals (user_id, text, week_start) VALUES (?,?,?)",
            (uid, text, self._week_start())
        )
        self.conn.commit()

    def get_weekly_goals(self, uid):
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM weekly_goals WHERE user_id=? AND week_start=? ORDER BY id",
            (uid, self._week_start())
        ).fetchall()]

    def is_goal_done(self, uid, goal_id):
        c = self.conn.cursor()
        row = c.execute("SELECT done FROM weekly_goals WHERE id=? AND user_id=?", (goal_id, uid)).fetchone()
        return row and row["done"] == 1

    def complete_goal(self, uid, goal_id):
        self.conn.execute("UPDATE weekly_goals SET done=1 WHERE id=? AND user_id=?", (goal_id, uid))
        self.conn.commit()
        c = self.conn.cursor()
        row = c.execute("SELECT text FROM weekly_goals WHERE id=?", (goal_id,)).fetchone()
        return row["text"] if row else "Objectif"

    # ── WEEKLY CHALLENGES ──
    def get_active_challenges(self, uid):
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM weekly_challenges WHERE user_id=? AND week_start=? AND done=0",
            (uid, self._week_start())
        ).fetchall()]

    def get_all_challenges(self, uid):
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM weekly_challenges WHERE user_id=? AND week_start=?",
            (uid, self._week_start())
        ).fetchall()]

    def create_challenge(self, uid, title, description, target, reward_coins):
        self.conn.execute(
            "INSERT INTO weekly_challenges (user_id, title, description, target, reward_coins, week_start) VALUES (?,?,?,?,?,?)",
            (uid, title, description, target, reward_coins, self._week_start())
        )
        self.conn.commit()

    def update_challenge_progress(self, uid, challenge_id, increment=1):
        c = self.conn.cursor()
        ch = c.execute("SELECT * FROM weekly_challenges WHERE id=? AND user_id=?", (challenge_id, uid)).fetchone()
        if not ch:
            return None
        new_progress = min(ch["progress"] + increment, ch["target"])
        done = 1 if new_progress >= ch["target"] else 0
        self.conn.execute(
            "UPDATE weekly_challenges SET progress=?, done=? WHERE id=?",
            (new_progress, done, challenge_id)
        )
        self.conn.commit()
        return dict(ch) if done else None

    def challenges_exist_this_week(self, uid):
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COUNT(*) as cnt FROM weekly_challenges WHERE user_id=? AND week_start=?",
            (uid, self._week_start())
        ).fetchone()
        return row["cnt"] > 0

    # ── SHOP ──
    def get_shop_items(self):
        c = self.conn.cursor()
        return [dict(r) for r in c.execute("SELECT * FROM shop_items ORDER BY cost").fetchall()]

    def get_shop_item(self, item_id):
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM shop_items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def add_purchase(self, uid, item_id):
        self.conn.execute("INSERT INTO purchases (user_id, item_id) VALUES (?,?)", (uid, item_id))
        self.conn.commit()

    # ── STATS ──
    def get_daily_stats(self, uid, days=14):
        since = (date.today() - timedelta(days=days)).isoformat()
        c = self.conn.cursor()
        return [dict(r) for r in c.execute(
            "SELECT * FROM daily_stats WHERE user_id=? AND stat_date>=? ORDER BY stat_date",
            (uid, since)
        ).fetchall()]

    def get_week_stats(self, uid, weeks_ago=0):
        ws = date.today() - timedelta(days=date.today().weekday() + weeks_ago * 7)
        we = ws + timedelta(days=6)
        c = self.conn.cursor()
        row = c.execute("""
            SELECT
                COALESCE(SUM(tasks_done),0) as tasks,
                COALESCE(SUM(coins_earned),0) as coins,
                COALESCE(SUM(xp_earned),0) as xp,
                COALESCE(SUM(revenue),0) as revenue
            FROM daily_stats
            WHERE user_id=? AND stat_date>=? AND stat_date<=?
        """, (uid, ws.isoformat(), we.isoformat())).fetchone()
        return dict(row) if row else {"tasks": 0, "coins": 0, "xp": 0, "revenue": 0}

    def get_leaderboard(self):
        c = self.conn.cursor()
        ws = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        rows = c.execute("""
            SELECT u.name, u.xp, u.streak,
                COALESCE(SUM(d.xp_earned),0) as week_xp
            FROM users u
            LEFT JOIN daily_stats d ON d.user_id=u.id AND d.stat_date>=?
            GROUP BY u.id
            ORDER BY week_xp DESC
            LIMIT 10
        """, (ws,)).fetchall()
        return [dict(r) for r in rows]
