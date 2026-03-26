import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.environ.get("DB_PATH", "biztracker.db")

DEFAULT_SHOP_ITEMS = [
    (1, "🎮", "Nouveau jeu",        "Steam, PS Store ou autre — ton choix !",    500),
    (2, "🌴", "Free day",           "Une journée complète sans travailler",       350),
    (3, "🎬", "Movie night",        "Soirée films / série de ton choix",          150),
    (4, "🍕", "Resto de luxe",      "Le restau que tu veux !",                    250),
    (5, "🎧", "Nouvel accessoire",  "Gadget, accessoire, achat plaisir",          400),
    (6, "🍦", "Dessert premium",    "Sushi, glace fancy, peu importe",             80),
    (7, "🏋️", "Session sport",     "Séance de sport ou activité physique",        60),
    (8, "☕", "Café de luxe",       "Starbucks ou café haut de gamme",             30),
]

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        self._seed_shop()

    def _init_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY,
                name        TEXT,
                coins       INTEGER DEFAULT 0,
                xp          INTEGER DEFAULT 0,
                streak      INTEGER DEFAULT 0,
                last_activity TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                description TEXT,
                difficulty  TEXT,
                coins_earned INTEGER,
                xp_earned   INTEGER,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
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

            CREATE TABLE IF NOT EXISTS shop_items (
                id          INTEGER PRIMARY KEY,
                emoji       TEXT,
                name        TEXT,
                description TEXT,
                cost        INTEGER
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                item_id     INTEGER,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    def _seed_shop(self):
        c = self.conn.cursor()
        for item in DEFAULT_SHOP_ITEMS:
            c.execute("INSERT OR IGNORE INTO shop_items VALUES (?,?,?,?,?)", item)
        self.conn.commit()

    def _week_start(self):
        today = date.today()
        return (today - timedelta(days=today.weekday())).isoformat()

    # ── USERS ──
    def ensure_user(self, uid, name):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?,?)", (uid, name))
        self.conn.commit()

    def get_user(self, uid):
        c = self.conn.cursor()
        return dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

    def add_coins(self, uid, amount):
        self.conn.execute("UPDATE users SET coins = coins + ? WHERE id=?", (amount, uid))
        self.conn.commit()

    def spend_coins(self, uid, amount):
        self.conn.execute("UPDATE users SET coins = MAX(0, coins - ?) WHERE id=?", (amount, uid))
        self.conn.commit()

    def add_xp(self, uid, amount):
        self.conn.execute("UPDATE users SET xp = xp + ? WHERE id=?", (amount, uid))
        self.conn.commit()

    def update_streak(self, uid):
        c = self.conn.cursor()
        user = dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()

        last = user.get("last_activity")
        if last == today_str:
            return  # Already updated today
        elif last == yesterday_str:
            new_streak = user["streak"] + 1
        else:
            new_streak = 1  # Reset streak

        self.conn.execute(
            "UPDATE users SET streak=?, last_activity=? WHERE id=?",
            (new_streak, today_str, uid)
        )
        self.conn.commit()

    def get_streak(self, uid):
        c = self.conn.cursor()
        row = c.execute("SELECT streak FROM users WHERE id=?", (uid,)).fetchone()
        return row["streak"] if row else 0

    # ── TASKS ──
    def add_task(self, uid, description, difficulty, coins, xp):
        self.conn.execute(
            "INSERT INTO tasks (user_id, description, difficulty, coins_earned, xp_earned) VALUES (?,?,?,?,?)",
            (uid, description, difficulty, coins, xp)
        )
        self.conn.commit()

    def get_today_tasks(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND DATE(created_at)=?",
            (uid, today)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_tasks(self, uid, days=7):
        since = (date.today() - timedelta(days=days)).isoformat()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM tasks WHERE user_id=? AND DATE(created_at)>=? ORDER BY created_at DESC",
            (uid, since)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── REVENUE ──
    def add_revenue(self, uid, amount, source):
        self.conn.execute(
            "INSERT INTO revenues (user_id, amount, source) VALUES (?,?,?)",
            (uid, amount, source)
        )
        self.conn.commit()

    def get_today_revenue(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM revenues WHERE user_id=? AND DATE(created_at)=?",
            (uid, today)
        ).fetchone()
        return row["total"]

    def get_week_revenue(self, uid):
        week_start = self._week_start()
        c = self.conn.cursor()
        row = c.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM revenues WHERE user_id=? AND DATE(created_at)>=?",
            (uid, week_start)
        ).fetchone()
        return row["total"]

    def get_recent_revenues(self, uid, days=7):
        since = (date.today() - timedelta(days=days)).isoformat()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM revenues WHERE user_id=? AND DATE(created_at)>=? ORDER BY created_at DESC",
            (uid, since)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── HABITS ──
    def add_habit(self, uid, name):
        self.conn.execute(
            "INSERT INTO habits (user_id, name) VALUES (?,?)",
            (uid, name)
        )
        self.conn.commit()

    def get_habits(self, uid):
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM habits WHERE user_id=? AND active=1",
            (uid,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_today_habits(self, uid):
        today = date.today().isoformat()
        c = self.conn.cursor()
        habits = c.execute(
            "SELECT * FROM habits WHERE user_id=? AND active=1",
            (uid,)
        ).fetchall()
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
        row = c.execute(
            "SELECT id FROM habit_logs WHERE user_id=? AND habit_id=? AND done_date=?",
            (uid, habit_id, today)
        ).fetchone()
        return row is not None

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
        week_start = self._week_start()
        self.conn.execute(
            "INSERT INTO weekly_goals (user_id, text, week_start) VALUES (?,?,?)",
            (uid, text, week_start)
        )
        self.conn.commit()

    def get_weekly_goals(self, uid):
        week_start = self._week_start()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM weekly_goals WHERE user_id=? AND week_start=? ORDER BY id",
            (uid, week_start)
        ).fetchall()
        return [dict(r) for r in rows]

    def is_goal_done(self, uid, goal_id):
        c = self.conn.cursor()
        row = c.execute("SELECT done FROM weekly_goals WHERE id=? AND user_id=?", (goal_id, uid)).fetchone()
        return row and row["done"] == 1

    def complete_goal(self, uid, goal_id):
        self.conn.execute(
            "UPDATE weekly_goals SET done=1 WHERE id=? AND user_id=?",
            (goal_id, uid)
        )
        self.conn.commit()
        c = self.conn.cursor()
        row = c.execute("SELECT text FROM weekly_goals WHERE id=?", (goal_id,)).fetchone()
        return row["text"] if row else "Objectif"

    # ── SHOP ──
    def get_shop_items(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT * FROM shop_items ORDER BY cost").fetchall()
        return [dict(r) for r in rows]

    def get_shop_item(self, item_id):
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM shop_items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def add_purchase(self, uid, item_id):
        self.conn.execute(
            "INSERT INTO purchases (user_id, item_id) VALUES (?,?)",
            (uid, item_id)
        )
        self.conn.commit()
