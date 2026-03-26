import os
import asyncio
import logging
from datetime import datetime, date, timedelta
from io import BytesIO
from sched import scheduler
import token

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web
import aiohttp

from database import Database
from stats_image import make_stats_image
import notion_client as notion
from todoist_handler import get_task_difficulty_from_priority, handle_todoist_webhook

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

# ─── CONSTANTS ────────────────────────────────────────────────────
COINS = {
    "task_simple": 20, "task_medium": 40, "task_hard": 80,
    "habit_done": 15,
    "revenue_per_100": 10,
    "weekly_goal_bonus": 150,
    "streak_7": 200, "streak_14": 350, "streak_30": 500,
    "level_up": 100,
    "challenge_bonus": 200,
}

LEVELS = [
    (0,     "🌱 Débutant"),
    (500,   "⚡ Hustle Mode"),
    (1500,  "🔥 En Feu"),
    (3000,  "💎 Diamant"),
    (6000,  "🚀 Entrepreneur"),
    (10000, "👑 Business King"),
    (20000, "🌍 Empire Builder"),
    (50000, "🏛️ Légende"),
]

WEEKLY_CHALLENGES_POOL = [
    {"title": "Grind week",       "description": "Complète 20 tâches cette semaine", "target": 20, "reward": 300},
    {"title": "Revenue hunter",   "description": "Génère 500$ de revenus",           "target": 500, "reward": 400},
    {"title": "Habit master",     "description": "Coche toutes tes habitudes 5 jours", "target": 5,  "reward": 250},
    {"title": "Consistency king", "description": "Sois actif 7 jours de suite",       "target": 7,  "reward": 350},
    {"title": "Clip machine",     "description": "Log 10 tâches Clipping/Contenu",    "target": 10, "reward": 200},
    {"title": "Trading focus",    "description": "Log 5 sessions de trading",         "target": 5,  "reward": 180},
    {"title": "XP rush",          "description": "Gagne 500 XP cette semaine",        "target": 500,"reward": 280},
    {"title": "Early bird",       "description": "Valide une tâche avant 9h, 5 fois", "target": 5,  "reward": 220},
]

MOTIVATIONAL_QUOTES = [
    "🔥 Chaque tâche comptée. Chaque coin mérité. Lance-toi.",
    "💎 Les diamants se forment sous pression. Continue.",
    "🚀 T'es pas en train de travailler. T'es en train de level up.",
    "👑 Personne ne te voit bosser. Mais les résultats parleront.",
    "⚡ Petit effort aujourd'hui = gros edge demain.",
    "🎯 Un coup à la fois. Une tâche à la fois. Un niveau à la fois.",
    "🔑 La discipline bat la motivation. Chaque. Seul. Jour.",
]

def get_level(xp):
    level, name = 0, LEVELS[0][1]
    for i, (threshold, lname) in enumerate(LEVELS):
        if xp >= threshold:
            level, name = i, lname
    return level, name

def get_progress_bar(pct, length=15):
    filled = int(length * pct / 100)
    return "█" * filled + "░" * (length - filled)

def get_tier(coins_total):
    if coins_total >= 5000: return "legend"
    if coins_total >= 2000: return "gold"
    if coins_total >= 500:  return "silver"
    return "bronze"

async def _award_task(uid, description, difficulty, source="manual", todoist_id=None):
    coins_earned = COINS[f"task_{difficulty}"]
    xp_earned = coins_earned * 2
    old = db.get_user(uid)
    old_level, _ = get_level(old["xp"])
    db.add_task(uid, description, difficulty, coins_earned, xp_earned, source, todoist_id)
    db.add_coins(uid, coins_earned)
    db.add_xp(uid, xp_earned)
    new_streak = db.update_streak(uid)
    new = db.get_user(uid)
    new_level, new_level_name = get_level(new["xp"])
    bonus_msgs = []
    if new_streak == 7:
        db.add_coins(uid, COINS["streak_7"])
        bonus_msgs.append(f"🏆 *STREAK 7 JOURS !* +{COINS['streak_7']}🪙 bonus !")
    elif new_streak == 14:
        db.add_coins(uid, COINS["streak_14"])
        bonus_msgs.append(f"💥 *STREAK 14 JOURS !* +{COINS['streak_14']}🪙 bonus !")
    elif new_streak == 30:
        db.add_coins(uid, COINS["streak_30"])
        bonus_msgs.append(f"👑 *STREAK 30 JOURS !* +{COINS['streak_30']}🪙 bonus !")
    if new_level > old_level:
        db.add_coins(uid, COINS["level_up"])
        bonus_msgs.append(f"🎉 *LEVEL UP → {new_level_name}* ! +{COINS['level_up']}🪙 !")
    # Auto-progress challenges
    challenges = db.get_active_challenges(uid)
    for ch in challenges:
        completed = db.update_challenge_progress(uid, ch["id"])
        if completed:
            db.add_coins(uid, ch["reward_coins"])
            bonus_msgs.append(f"🏅 *DÉFI COMPLÉTÉ : {ch['title']}* ! +{ch['reward_coins']}🪙 !")
    return coins_earned, xp_earned, new_streak, "\n".join(bonus_msgs)

# ─── /start ───────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name)
    import random
    quote = random.choice(MOTIVATIONAL_QUOTES)
    await update.message.reply_text(
        f"👋 Salut *{user.first_name}* ! Bienvenue sur *BizTracker v2* 🚀\n\n"
        f"_{quote}_\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎮 *C'est un jeu. T'es le personnage.*\n\n"
        "▸ /status — Ton dashboard\n"
        "▸ /done — Logger une tâche\n"
        "▸ /revenue — Ajouter des revenus\n"
        "▸ /habit — Habitudes du jour\n"
        "▸ /weekly — Objectifs hebdo\n"
        "▸ /challenge — Défis de la semaine\n"
        "▸ /shop — Dépenser tes coins 🪙\n"
        "▸ /stats — Graphique de ta semaine 📊\n"
        "▸ /leaderboard — Classement 🏆\n"
        "▸ /setup — Connecter Todoist & Notion\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Commence par /setup pour connecter tes apps !",
        parse_mode="Markdown"
    )

# ─── /status ──────────────────────────────────────────────────────
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    data = db.get_user(uid)
    today_tasks = db.get_today_tasks(uid)
    today_habits = db.get_today_habits(uid)
    weekly_goals = db.get_weekly_goals(uid)
    streak = db.get_streak(uid)
    rev_today = db.get_today_revenue(uid)
    rev_week = db.get_week_revenue(uid)
    week_now = db.get_week_stats(uid, 0)
    week_prev = db.get_week_stats(uid, 1)
    challenges = db.get_active_challenges(uid)

    xp, coins = data["xp"], data["coins"]
    level_idx, level_name = get_level(xp)
    cur = LEVELS[level_idx][0]
    nxt = LEVELS[level_idx + 1][0] if level_idx + 1 < len(LEVELS) else cur + 5000
    xp_pct = min(100, int((xp - cur) / (nxt - cur) * 100))
    xp_bar = get_progress_bar(xp_pct)

    goals_done = sum(1 for g in weekly_goals if g["done"])
    habits_done = sum(1 for h in today_habits if h["done_today"])
    habits_total = len(today_habits)

    # Week-over-week
    prev_tasks = week_prev.get("tasks", 0)
    now_tasks = week_now.get("tasks", 0)
    if prev_tasks > 0:
        wow = int((now_tasks - prev_tasks) / prev_tasks * 100)
        wow_str = f"{'📈' if wow >= 0 else '📉'} vs sem. passée : {'+'if wow>=0 else ''}{wow}%"
    else:
        wow_str = "📅 Première semaine trackée !"

    streak_fire = "🔥" * min(streak, 5) if streak >= 1 else "💤"

    active_ch = len(challenges)
    done_ch = sum(1 for c in db.get_all_challenges(uid) if c["done"])

    msg = (
        f"╔══════════════════╗\n"
        f"  📊 *DASHBOARD*\n"
        f"╚══════════════════╝\n\n"
        f"*{level_name}*\n"
        f"`{xp_bar}` {xp_pct}%\n"
        f"_{xp - cur} / {nxt - cur} XP_\n\n"
        f"🪙 *{coins}* coins  •  ⭐ *{xp:,}* XP\n"
        f"{streak_fire} Streak : *{streak}* jour{'s' if streak != 1 else ''}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 *AUJOURD'HUI*\n"
        f"✅ {len(today_tasks)} tâches  •  💰 ${rev_today:.0f}\n"
        f"🏋️ Habitudes : {habits_done}/{habits_total}\n\n"
        f"📆 *CETTE SEMAINE*\n"
        f"✅ {now_tasks} tâches  •  💰 ${rev_week:.0f}\n"
        f"{wow_str}\n\n"
        f"🎯 Objectifs : {goals_done}/{len(weekly_goals)}\n"
        f"🏅 Défis : {done_ch}/{done_ch + active_ch}\n"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Tâche", callback_data="prompt_task"),
         InlineKeyboardButton("🏋️ Habitudes", callback_data="show_habits")],
        [InlineKeyboardButton("🎯 Objectifs", callback_data="show_goals"),
         InlineKeyboardButton("🏅 Défis", callback_data="show_challenges")],
        [InlineKeyboardButton("📊 Stats visuelles", callback_data="show_stats"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")],
        [InlineKeyboardButton("🛒 Shop", callback_data="show_shop")],
    ]
    await update.message.reply_text(msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ─── /done ────────────────────────────────────────────────────────
async def done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if not ctx.args:
        keyboard = [
            [InlineKeyboardButton("🟢 Simple (+20🪙)", callback_data="task_simple"),
             InlineKeyboardButton("🟡 Moyen (+40🪙)", callback_data="task_medium")],
            [InlineKeyboardButton("🔴 Difficile (+80🪙)", callback_data="task_hard")],
        ]
        await update.message.reply_text(
            "✅ *Logger une tâche*\n\n"
            "Usage : `/done [description]`\n"
            "Exemple : `/done Posté 3 clips TikTok`\n\n"
            "Ou choisis la difficulté ci-dessous :",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    description = " ".join(ctx.args)
    await _send_task_result(update.message, uid, description, "medium")

async def _send_task_result(msg_obj, uid, description, difficulty):
    coins, xp, streak, bonus = await _award_task(uid, description, difficulty)
    diff_map = {"simple": "🟢 Simple", "medium": "🟡 Moyen", "hard": "🔴 Difficile"}
    text = (
        f"✅ *Tâche validée !*\n\n"
        f"📝 _{description}_\n"
        f"⚡ {diff_map[difficulty]}\n\n"
        f"🪙 +{coins} coins  •  ⭐ +{xp} XP\n"
        f"🔥 Streak : {streak} jour{'s' if streak != 1 else ''}"
    )
    if bonus:
        text += f"\n\n{bonus}"
    await msg_obj.reply_text(text, parse_mode="Markdown")

# ─── /revenue ─────────────────────────────────────────────────────
async def revenue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if not ctx.args:
        await update.message.reply_text(
            "💰 Usage : `/revenue [montant] [source]`\n\n"
            "• `/revenue 150 Clipping`\n• `/revenue 320 Trading`\n• `/revenue 80 Freelance`",
            parse_mode="Markdown"
        )
        return
    try:
        amount = float(ctx.args[0])
        source = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Divers"
    except ValueError:
        await update.message.reply_text("❌ Montant invalide.", parse_mode="Markdown")
        return
    coins_earned = max(1, int(amount / 100 * COINS["revenue_per_100"]))
    xp_earned = coins_earned * 2
    db.add_revenue(uid, amount, source)
    db.add_coins(uid, coins_earned)
    db.add_xp(uid, xp_earned)
    week_total = db.get_week_revenue(uid)
    await update.message.reply_text(
        f"💰 *Revenus ajoutés !*\n\n"
        f"💵 *${amount:.2f}* — {source}\n\n"
        f"🪙 +{coins_earned} coins  •  ⭐ +{xp_earned} XP\n"
        f"📈 Cette semaine : *${week_total:.2f}*",
        parse_mode="Markdown"
    )
    # Log to Notion
    user = db.get_user(uid)
    if user.get("notion_token") and user.get("notion_db_id"):
        today_stats = db.get_week_stats(uid, 0)
        notion.log_daily_journal(user["notion_token"], user["notion_db_id"], {
            "tasks": len(db.get_today_tasks(uid)),
            "revenue": db.get_today_revenue(uid),
            "coins": today_stats.get("coins", 0),
            "xp": today_stats.get("xp", 0),
            "streak": db.get_streak(uid),
        })

# ─── /habit & /addhabit ───────────────────────────────────────────
async def habit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    today_habits = db.get_today_habits(uid)
    if not today_habits:
        await update.message.reply_text(
            "🏋️ Aucune habitude. Ajoute-en : `/addhabit [nom]`",
            parse_mode="Markdown"
        )
        return
    done_count = sum(1 for h in today_habits if h["done_today"])
    bar = get_progress_bar(int(done_count / len(today_habits) * 100))
    keyboard = []
    for h in today_habits:
        emoji = "✅" if h["done_today"] else "⬜"
        keyboard.append([InlineKeyboardButton(f"{emoji} {h['name']}", callback_data=f"habit_{h['id']}")])
    await update.message.reply_text(
        f"🏋️ *Habitudes du jour*\n`{bar}` {done_count}/{len(today_habits)}\n\nClique pour cocher :",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def addhabit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if not ctx.args:
        await update.message.reply_text("Usage : `/addhabit [nom]`", parse_mode="Markdown")
        return
    name = " ".join(ctx.args)
    db.add_habit(uid, name)
    await update.message.reply_text(f"✅ Habitude : *{name}* (+{COINS['habit_done']}🪙/jour)", parse_mode="Markdown")

# ─── /weekly & /addgoal ───────────────────────────────────────────
async def weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    goals = db.get_weekly_goals(uid)
    if not goals:
        await update.message.reply_text(
            "🎯 Aucun objectif. Ajoute : `/addgoal [texte]`",
            parse_mode="Markdown"
        )
        return
    done_c = sum(1 for g in goals if g["done"])
    bar = get_progress_bar(int(done_c / len(goals) * 100))
    keyboard = [[InlineKeyboardButton(
        f"{'✅' if g['done'] else '⬜'} {g['text']}", callback_data=f"goal_{g['id']}"
    )] for g in goals]
    await update.message.reply_text(
        f"🎯 *Objectifs hebdo*\n`{bar}` {done_c}/{len(goals)}\n\nClique pour valider :",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def addgoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if not ctx.args:
        await update.message.reply_text("Usage : `/addgoal [texte]`", parse_mode="Markdown")
        return
    text = " ".join(ctx.args)
    db.add_weekly_goal(uid, text)
    await update.message.reply_text(f"🎯 Objectif ajouté : *{text}*", parse_mode="Markdown")

# ─── /challenge ───────────────────────────────────────────────────
async def challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if not db.challenges_exist_this_week(uid):
        import random
        pool = random.sample(WEEKLY_CHALLENGES_POOL, min(3, len(WEEKLY_CHALLENGES_POOL)))
        for ch in pool:
            db.create_challenge(uid, ch["title"], ch["description"], ch["target"], ch["reward"])
        await update.message.reply_text("🏅 *3 nouveaux défis générés !*", parse_mode="Markdown")

    challenges = db.get_all_challenges(uid)
    msg = "🏅 *DÉFIS DE LA SEMAINE*\n\n"
    for ch in challenges:
        if ch["done"]:
            msg += f"✅ ~~{ch['title']}~~ _{ch['description']}_\n+{ch['reward_coins']}🪙 *COMPLÉTÉ*\n\n"
        else:
            pct = int(ch["progress"] / ch["target"] * 100) if ch["target"] > 0 else 0
            bar = get_progress_bar(pct, 10)
            msg += f"🏅 *{ch['title']}*\n_{ch['description']}_\n`{bar}` {ch['progress']}/{ch['target']}\nRécompense : +{ch['reward_coins']}🪙\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── /stats ───────────────────────────────────────────────────────
async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    msg = await update.message.reply_text("📊 Génération de ton rapport... ⏳")
    try:
        user_data = db.get_user(uid)
        daily_stats = db.get_daily_stats(uid, days=7)
        week_now = db.get_week_stats(uid, 0)
        week_prev = db.get_week_stats(uid, 1)
        leaderboard = db.get_leaderboard()
        challenges = db.get_all_challenges(uid)
        img_buf = make_stats_image(user_data, daily_stats, week_now, week_prev, leaderboard, challenges)
        await msg.delete()
        await update.message.reply_photo(
            photo=img_buf,
            caption=f"📊 *Rapport semaine — {update.effective_user.first_name}*\n_Généré le {date.today().strftime('%d/%m/%Y')}_",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await msg.edit_text("❌ Erreur lors de la génération. Réessaie dans un moment.")

# ─── /leaderboard ─────────────────────────────────────────────────
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    board = db.get_leaderboard()
    medals = ["🥇", "🥈", "🥉"]
    msg = "🏆 *LEADERBOARD — CETTE SEMAINE*\n\n"
    for i, entry in enumerate(board):
        medal = medals[i] if i < 3 else f"#{i+1}"
        msg += f"{medal} *{entry['name']}* — {entry['week_xp']} XP  🔥{entry['streak']}j\n"
    if not board:
        msg += "_Aucun joueur encore. Invite des amis !_"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── /shop ────────────────────────────────────────────────────────
async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    data = db.get_user(uid)
    coins = data["coins"]
    items = db.get_shop_items()
    tier = get_tier(coins)
    tier_labels = {"bronze": "🥉 Bronze", "silver": "🥈 Silver", "gold": "🥇 Gold", "legend": "👑 Legend"}
    keyboard = []
    for item in items:
        can_afford = "✅" if coins >= item["cost"] else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{can_afford} {item['emoji']} {item['name']} — 🪙{item['cost']}",
            callback_data=f"buy_{item['id']}"
        )])
    await update.message.reply_text(
        f"🏪 *BOUTIQUE*\n\n"
        f"🪙 Solde : *{coins}* coins\n"
        f"Statut : *{tier_labels.get(tier, '🥉 Bronze')}*\n\n"
        f"✅ = Disponible  •  ❌ = Pas assez de coins\n\n"
        f"Clique pour acheter :",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /history ─────────────────────────────────────────────────────
async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    tasks = db.get_recent_tasks(uid, days=7)
    revenues = db.get_recent_revenues(uid, days=7)
    msg = "📈 *Historique — 7 derniers jours*\n\n"
    if tasks:
        msg += "✅ *Tâches :*\n"
        for t in tasks[:8]:
            d = datetime.fromisoformat(t["created_at"]).strftime("%d/%m")
            src = " 🤖" if t["source"] == "todoist" else ""
            diff_map = {"simple": "🟢", "medium": "🟡", "hard": "🔴"}
            msg += f"{diff_map.get(t['difficulty'],'🟡')} `{d}` {t['description']}{src} _(+{t['coins_earned']}🪙)_\n"
        msg += "\n"
    if revenues:
        msg += "💰 *Revenus :*\n"
        for r in revenues[:6]:
            d = datetime.fromisoformat(r["created_at"]).strftime("%d/%m")
            msg += f"💵 `{d}` ${r['amount']:.2f} — {r['source']}\n"
    if not tasks and not revenues:
        msg += "_Rien encore. Lance-toi !_ 💪"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── /setup ───────────────────────────────────────────────────────
async def setup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    user = db.get_user(uid)
    todoist_ok = "✅" if user.get("todoist_token") else "❌"
    notion_ok = "✅" if user.get("notion_token") else "❌"
    keyboard = [
        [InlineKeyboardButton("🔗 Connecter Todoist", callback_data="setup_todoist")],
        [InlineKeyboardButton("📓 Connecter Notion", callback_data="setup_notion")],
        [InlineKeyboardButton("⏰ Rappels", callback_data="setup_reminders")],
    ]
    await update.message.reply_text(
        f"⚙️ *CONFIGURATION*\n\n"
        f"{todoist_ok} Todoist\n"
        f"{notion_ok} Notion\n\n"
        f"Clique pour configurer :",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /coins ───────────────────────────────────────────────────────
async def coins_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    data = db.get_user(uid)
    level_idx, level_name = get_level(data["xp"])
    tier = get_tier(data["coins"])
    tier_labels = {"bronze": "🥉 Bronze", "silver": "🥈 Silver", "gold": "🥇 Gold", "legend": "👑 Legend"}
    await update.message.reply_text(
        f"🪙 *{data['coins']} coins*\n"
        f"⭐ {data['xp']:,} XP — {level_name}\n"
        f"🏷️ Statut : {tier_labels.get(tier)}\n"
        f"🔥 Streak : {data['streak']}j (record : {data.get('best_streak', 0)}j)\n\n"
        f"Utilise /shop pour dépenser !",
        parse_mode="Markdown"
    )

# ─── CALLBACKS ────────────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data in ("task_simple", "task_medium", "task_hard"):
        ctx.user_data["pending_task"] = data.replace("task_", "")
        await query.message.reply_text(
            f"📝 Décris ta tâche *{data.replace('task_', '')}* :",
            parse_mode="Markdown"
        )
        return

    if data == "prompt_task":
        keyboard = [
            [InlineKeyboardButton("🟢 Simple (+20🪙)", callback_data="task_simple"),
             InlineKeyboardButton("🟡 Moyen (+40🪙)", callback_data="task_medium")],
            [InlineKeyboardButton("🔴 Difficile (+80🪙)", callback_data="task_hard")],
        ]
        await query.message.reply_text("✅ Difficulté :", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("habit_"):
        habit_id = int(data.replace("habit_", ""))
        if db.is_habit_done_today(uid, habit_id):
            await query.message.reply_text("✅ Déjà cochée aujourd'hui !")
            return
        name = db.complete_habit_today(uid, habit_id)
        db.add_coins(uid, COINS["habit_done"])
        db.add_xp(uid, COINS["habit_done"])
        new_streak = db.update_streak(uid)
        await query.message.reply_text(
            f"🏋️ *{name}* cochée !\n🪙 +{COINS['habit_done']} coins  •  🔥 Streak {new_streak}j",
            parse_mode="Markdown"
        )
        return

    if data.startswith("goal_"):
        goal_id = int(data.replace("goal_", ""))
        if db.is_goal_done(uid, goal_id):
            await query.message.reply_text("✅ Déjà complété !")
            return
        goal_text = db.complete_goal(uid, goal_id)
        db.add_coins(uid, COINS["weekly_goal_bonus"])
        db.add_xp(uid, COINS["weekly_goal_bonus"] * 2)
        await query.message.reply_text(
            f"🎯 *Objectif complété !*\n_{goal_text}_\n🪙 +{COINS['weekly_goal_bonus']} coins",
            parse_mode="Markdown"
        )
        return

    if data == "show_stats":
        await stats_cmd_from_callback(query, uid)
        return

    if data == "show_leaderboard":
        board = db.get_leaderboard()
        medals = ["🥇", "🥈", "🥉"]
        msg = "🏆 *LEADERBOARD*\n\n"
        for i, entry in enumerate(board[:5]):
            medal = medals[i] if i < 3 else f"#{i+1}"
            msg += f"{medal} *{entry['name']}* — {entry['week_xp']} XP\n"
        if not board:
            msg += "_Aucun joueur._"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    if data == "show_shop":
        user_data = db.get_user(uid)
        coins = user_data["coins"]
        items = db.get_shop_items()
        keyboard = []
        for item in items:
            can_afford = "✅" if coins >= item["cost"] else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{can_afford} {item['emoji']} {item['name']} — 🪙{item['cost']}",
                callback_data=f"buy_{item['id']}"
            )])
        await query.message.reply_text(
            f"🏪 *SHOP* — 🪙 {coins} coins\n\nClique pour acheter :",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("buy_"):
        item_id = int(data.replace("buy_", ""))
        item = db.get_shop_item(item_id)
        user_data = db.get_user(uid)
        if user_data["coins"] < item["cost"]:
            missing = item["cost"] - user_data["coins"]
            await query.message.reply_text(
                f"❌ Il te manque *{missing}🪙*\nContinue à bosser ! 💪",
                parse_mode="Markdown"
            )
            return
        db.spend_coins(uid, item["cost"])
        db.add_purchase(uid, item_id)
        remaining = user_data["coins"] - item["cost"]
        await query.message.reply_text(
            f"🎉 *{item['emoji']} {item['name']}* acheté !\n_{item['description']}_\n\n"
            f"🪙 -{item['cost']}  •  Solde : {remaining}🪙\n\nTu l'as MÉRITÉ ! 😎",
            parse_mode="Markdown"
        )
        return

    if data == "show_habits":
        today_habits = db.get_today_habits(uid)
        if not today_habits:
            await query.message.reply_text("Ajoute des habitudes : `/addhabit [nom]`", parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(
            f"{'✅' if h['done_today'] else '⬜'} {h['name']}", callback_data=f"habit_{h['id']}"
        )] for h in today_habits]
        await query.message.reply_text("🏋️ *Habitudes :*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_goals":
        goals = db.get_weekly_goals(uid)
        if not goals:
            await query.message.reply_text("Ajoute des objectifs : `/addgoal [texte]`", parse_mode="Markdown")
            return
        keyboard = [[InlineKeyboardButton(
            f"{'✅' if g['done'] else '⬜'} {g['text']}", callback_data=f"goal_{g['id']}"
        )] for g in goals]
        await query.message.reply_text("🎯 *Objectifs :*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "show_challenges":
        challenges = db.get_all_challenges(uid)
        if not challenges:
            await query.message.reply_text("Lance `/challenge` pour générer tes défis !", parse_mode="Markdown")
            return
        msg = "🏅 *Défis :*\n\n"
        for ch in challenges:
            emoji = "✅" if ch["done"] else "🏅"
            bar = get_progress_bar(int(ch["progress"] / ch["target"] * 100) if ch["target"] else 0, 8)
            msg += f"{emoji} *{ch['title']}* — {ch['progress']}/{ch['target']}\n`{bar}`\n"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    if data == "setup_todoist":
        await query.message.reply_text(
            "🔗 *Connecter Todoist*\n\n"
            "1. Va sur *todoist.com/app/settings/integrations*\n"
            "2. Copie ton *API Token*\n"
            "3. Envoie-le ici avec : `/settoken todoist TON_TOKEN`\n\n"
            "Une fois connecté, chaque tâche cochée dans Todoist = coins automatiques 🎯",
            parse_mode="Markdown"
        )
        return

    if data == "setup_notion":
        await query.message.reply_text(
            "📓 *Connecter Notion*\n\n"
            "1. Va sur *notion.so/my-integrations*\n"
            "2. Crée une nouvelle intégration\n"
            "3. Copie le *Secret* (commence par `secret_`)\n"
            "4. Envoie : `/settoken notion TON_SECRET`\n\n"
            "Je créerai automatiquement une base de données journal dans Notion !",
            parse_mode="Markdown"
        )
        return

    if data == "setup_reminders":
        user = db.get_user(uid)
        am_on = "✅" if user.get("morning_remind", 1) else "❌"
        pm_on = "✅" if user.get("evening_remind", 1) else "❌"
        keyboard = [
            [InlineKeyboardButton(f"{am_on} Rappel matin (8h)", callback_data="toggle_am")],
            [InlineKeyboardButton(f"{pm_on} Rappel soir (21h)", callback_data="toggle_pm")],
        ]
        await query.message.reply_text(
            "⏰ *Rappels automatiques*\n\nClique pour activer/désactiver :",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "toggle_am":
        user = db.get_user(uid)
        new_val = 0 if user.get("morning_remind", 1) else 1
        db.set_user_field(uid, "morning_remind", new_val)
        await query.answer(f"Rappel matin {'activé ✅' if new_val else 'désactivé ❌'}")
        return

    if data == "toggle_pm":
        user = db.get_user(uid)
        new_val = 0 if user.get("evening_remind", 1) else 1
        db.set_user_field(uid, "evening_remind", new_val)
        await query.answer(f"Rappel soir {'activé ✅' if new_val else 'désactivé ❌'}")
        return

async def stats_cmd_from_callback(query, uid):
    await query.message.reply_text("📊 Génération... ⏳")
    try:
        user_data = db.get_user(uid)
        daily_stats = db.get_daily_stats(uid, days=7)
        week_now = db.get_week_stats(uid, 0)
        week_prev = db.get_week_stats(uid, 1)
        leaderboard_data = db.get_leaderboard()
        challenges = db.get_all_challenges(uid)
        img_buf = make_stats_image(user_data, daily_stats, week_now, week_prev, leaderboard_data, challenges)
        await query.message.reply_photo(photo=img_buf, caption="📊 *Ton rapport*", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Stats cb error: {e}")
        await query.message.reply_text("❌ Erreur génération stats.")

# ─── /settoken ────────────────────────────────────────────────────
async def settoken(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage : `/settoken todoist TON_TOKEN`\nou `/settoken notion TON_SECRET`",
            parse_mode="Markdown"
        )
        return
    service = ctx.args[0].lower()
    token = ctx.args[1]
    if service == "todoist":
        db.set_user_field(uid, "todoist_token", token)
        await update.message.reply_text(
            "✅ *Todoist connecté !*\n\n"
            "Maintenant configure le webhook dans Todoist :\n"
            f"`https://TON-BOT-URL.railway.app/webhook/todoist`\n\n"
            "_(Remplace par l'URL Railway de ton bot)_",
            parse_mode="Markdown"
        )
    elif service == "notion":
        if notion.test_connection(token):
            db.set_user_field(uid, "notion_token", token)
            db.set_user_field(uid, "notion_db_id", "")
            await update.message.reply_text(
                "✅ *Notion connecté !*\n\n"
                "Création de ta base de données journal...",
                parse_mode="Markdown"
            )
            db_id = notion.create_journal_database(token)
            if db_id:
                db.set_user_field(uid, "notion_db_id", db_id)
                await update.message.reply_text(
                    "📓 *Base de données créée dans Notion !*\n\n"
                    "Chaque soir à 21h, ton journal sera mis à jour automatiquement.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "⚠️ Notion connecté mais impossible de créer la DB.\n"
                    "Assure-toi que ton intégration a accès à une page.",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Token Notion invalide. Vérifie et réessaie.")
    else:
        await update.message.reply_text("Service inconnu. Utilise `todoist` ou `notion`.", parse_mode="Markdown")

# ─── /help ────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *AIDE COMPLÈTE v2*\n\n"
        "━━ *TRACKER* ━━\n"
        "`/done [tâche]` — Logger une tâche\n"
        "`/revenue [montant] [source]` — Revenus\n"
        "`/habit` — Habitudes du jour\n"
        "`/addhabit [nom]` — Ajouter habitude\n\n"
        "━━ *OBJECTIFS & DÉFIS* ━━\n"
        "`/weekly` — Objectifs hebdo\n"
        "`/addgoal [texte]` — Ajouter objectif\n"
        "`/challenge` — Défis de la semaine\n\n"
        "━━ *STATS & PROGRESSION* ━━\n"
        "`/status` — Dashboard complet\n"
        "`/stats` — Graphique visuel 📊\n"
        "`/leaderboard` — Classement 🏆\n"
        "`/history` — Historique 7 jours\n"
        "`/coins` — Ton solde\n\n"
        "━━ *RÉCOMPENSES* ━━\n"
        "`/shop` — Boutique\n\n"
        "━━ *INTÉGRATIONS* ━━\n"
        "`/setup` — Todoist & Notion\n"
        "`/settoken [service] [token]` — Connecter\n\n"
        "━━ *COINS GAGNÉS* ━━\n"
        f"🟢 Simple : {COINS['task_simple']}🪙  🟡 Moyen : {COINS['task_medium']}🪙  🔴 Difficile : {COINS['task_hard']}🪙\n"
        f"🏋️ Habitude : {COINS['habit_done']}🪙  🎯 Objectif hebdo : {COINS['weekly_goal_bonus']}🪙\n"
        f"🔥 Streak 7j : {COINS['streak_7']}🪙  Streak 30j : {COINS['streak_30']}🪙",
        parse_mode="Markdown"
    )

# ─── TEXT MESSAGES ────────────────────────────────────────────────
async def text_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if "pending_task" in ctx.user_data:
        difficulty = ctx.user_data.pop("pending_task")
        await _send_task_result(update.message, uid, update.message.text, difficulty)
    else:
        import random
        await update.message.reply_text(
            f"_{random.choice(MOTIVATIONAL_QUOTES)}_\n\nUtilise /help pour voir les commandes 😊",
            parse_mode="Markdown"
        )

# ─── TODOIST WEBHOOK PROCESSOR ────────────────────────────────────
async def process_todoist_task(todoist_user_id, item, bot, db_instance):
    users = db_instance.get_all_users()
    for user in users:
        u = db_instance.get_user(user["id"])
        if not u.get("todoist_token"):
            continue
        if db_instance.todoist_task_exists(str(item.get("id", ""))):
            continue
        priority = item.get("priority", 1)
        difficulty = get_task_difficulty_from_priority(priority)
        description = item.get("content", "Tâche Todoist")
        coins, xp, streak, bonus = await _award_task(
            user["id"], description, difficulty,
            source="todoist", todoist_id=str(item.get("id", ""))
        )
        priority_labels = {4: "P1 🔴", 3: "P2 🟡", 2: "P3 🟢", 1: "P4 ⚪"}
        text = (
            f"🤖 *Todoist sync !*\n\n"
            f"✅ _{description}_\n"
            f"Priorité : {priority_labels.get(priority, 'Normal')}\n\n"
            f"🪙 +{coins} coins  •  ⭐ +{xp} XP\n"
            f"🔥 Streak : {streak}j"
        )
        if bonus:
            text += f"\n\n{bonus}"
        try:
            await bot.send_message(chat_id=user["id"], text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify user {user['id']}: {e}")
        break

# ─── SCHEDULERS ───────────────────────────────────────────────────
async def send_morning_reminder(bot):
    import random
    users = db.get_all_users()
    for user in users:
        u = db.get_user(user["id"])
        if not u.get("morning_remind", 1):
            continue
        streak = db.get_streak(user["id"])
        week_stats = db.get_week_stats(user["id"], 0)
        challenges = db.get_active_challenges(user["id"])
        quote = random.choice(MOTIVATIONAL_QUOTES)
        ch_text = f"🏅 {len(challenges)} défi{'s' if len(challenges) > 1 else ''} actif{'s' if len(challenges) > 1 else ''}" if challenges else ""
        msg = (
            f"☀️ *Bonjour {u['name']} !*\n\n"
            f"_{quote}_\n\n"
            f"━━━━━━━━━━━━\n"
            f"🔥 Streak actuel : *{streak}j*\n"
            f"✅ Tâches cette semaine : *{week_stats.get('tasks', 0)}*\n"
            f"🪙 Coins : *{u['coins']}*\n"
            f"{ch_text}\n\n"
            f"*Lance-toi !* /done pour logger ta première tâche 💪"
        )
        try:
            await bot.send_message(chat_id=user["id"], text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Morning reminder error for {user['id']}: {e}")

async def send_evening_checkin(bot):
    users = db.get_all_users()
    for user in users:
        u = db.get_user(user["id"])
        if not u.get("evening_remind", 1):
            continue
        today_tasks = db.get_today_tasks(user["id"])
        today_rev = db.get_today_revenue(user["id"])
        habits = db.get_today_habits(user["id"])
        habits_done = sum(1 for h in habits if h["done_today"])
        if len(today_tasks) == 0:
            msg = (
                f"🌙 *Check-in soir — {u['name']}*\n\n"
                f"⚠️ Aucune tâche aujourd'hui...\n"
                f"🔥 Ton streak est en danger !\n\n"
                f"Log au moins une tâche avant minuit : /done"
            )
        else:
            week_prev = db.get_week_stats(user["id"], 1)
            week_now = db.get_week_stats(user["id"], 0)
            wow = 0
            if week_prev.get("tasks", 0) > 0:
                wow = int((week_now.get("tasks", 0) - week_prev["tasks"]) / week_prev["tasks"] * 100)
            msg = (
                f"🌙 *Check-in soir — {u['name']}*\n\n"
                f"✅ {len(today_tasks)} tâches aujourd'hui\n"
                f"🏋️ Habitudes : {habits_done}/{len(habits)}\n"
                f"💰 Revenus : ${today_rev:.0f}\n\n"
                f"{'📈' if wow >= 0 else '📉'} vs sem. passée : {'+'if wow>=0 else ''}{wow}%\n\n"
                f"Génère ton rapport : /stats 📊"
            )
        # Log to Notion if configured
        if u.get("notion_token") and u.get("notion_db_id"):
            week_stats = db.get_week_stats(user["id"], 0)
            notion.log_daily_journal(u["notion_token"], u["notion_db_id"], {
                "tasks": len(today_tasks),
                "revenue": today_rev,
                "coins": week_stats.get("coins", 0),
                "xp": week_stats.get("xp", 0),
                "streak": db.get_streak(user["id"]),
            })
        try:
            await bot.send_message(chat_id=user["id"], text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Evening checkin error for {user['id']}: {e}")

async def send_weekly_recap(bot):
    users = db.get_all_users()
    for user in users:
        u = db.get_user(user["id"])
        week_now = db.get_week_stats(user["id"], 0)
        week_prev = db.get_week_stats(user["id"], 1)
        wow = 0
        if week_prev.get("tasks", 0) > 0:
            wow = int((week_now.get("tasks", 0) - week_prev["tasks"]) / week_prev["tasks"] * 100)
        level_idx, level_name = get_level(u["xp"])
        msg = (
            f"📆 *RÉCAP DE LA SEMAINE*\n\n"
            f"✅ {week_now.get('tasks', 0)} tâches\n"
            f"💰 ${week_now.get('revenue', 0):.0f} de revenus\n"
            f"🪙 {week_now.get('coins', 0)} coins gagnés\n"
            f"⭐ {week_now.get('xp', 0)} XP\n"
            f"🔥 Streak : {u['streak']}j\n\n"
            f"{'📈' if wow >= 0 else '📉'} vs semaine passée : {'+'if wow>=0 else ''}{wow}%\n\n"
            f"Niveau actuel : *{level_name}*\n\n"
            f"/stats pour le rapport visuel 📊\nBonne semaine ! 🚀"
        )
        if u.get("notion_token") and u.get("notion_db_id"):
            notion.log_weekly_recap(u["notion_token"], u["notion_db_id"], week_now)
        try:
            await bot.send_message(chat_id=user["id"], text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Weekly recap error for {user['id']}: {e}")

# ─── AIOHTTP WEB SERVER (for Todoist webhook) ─────────────────────
async def run_web_server(bot):
    async def todoist_webhook(request):
        return await handle_todoist_webhook(request, bot, db, process_todoist_task)

    async def health(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post("/webhook/todoist", todoist_webhook)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

# ─── MAIN ─────────────────────────────────────────────────────────
async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN manquant !")

    app = Application.builder().token(token).build()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(send_morning_reminder(app.bot)), "cron", hour=8)
    scheduler.add_job(lambda: asyncio.create_task(send_evening_checkin(app.bot)), "cron", hour=21)
    scheduler.add_job(lambda: asyncio.create_task(send_weekly_recap(app.bot)), "cron", day_of_week="sun", hour=20)
    scheduler.start()

    asyncio.create_task(run_web_server(app.bot))

    print("🚀 Bot lancé")

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())