import os
import json
import logging
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ─── COIN REWARDS ─────────────────────────────────────────────────
COINS = {
    "task_simple": 20,
    "task_medium": 40,
    "task_hard": 80,
    "habit_done": 15,
    "revenue_per_100": 10,
    "weekly_goal_bonus": 150,
    "streak_7": 200,
    "streak_30": 500,
    "level_up": 100,
}

LEVELS = [
    (0,    "🌱 Débutant"),
    (500,  "⚡ Hustle Mode"),
    (1500, "🔥 En Feu"),
    (3000, "💎 Diamant"),
    (6000, "🚀 Entrepreneur"),
    (10000,"👑 Business King"),
    (20000,"🌍 Empire Builder"),
]

def get_level(xp):
    level = 0
    name = LEVELS[0][1]
    for i, (threshold, lname) in enumerate(LEVELS):
        if xp >= threshold:
            level = i
            name = lname
    return level, name

def get_progress_bar(pct, length=15):
    filled = int(length * pct / 100)
    bar = "█" * filled + "░" * (length - filled)
    return bar

# ─── /start ───────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name)
    await update.message.reply_text(
        f"👋 Salut *{user.first_name}* !\n\n"
        "Bienvenue sur ton *BizTracker Bot* 🚀\n"
        "Je suis là pour tracker ton grind et te récompenser vraiment.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📋 *Commandes rapides :*\n"
        "▸ /status — Ton dashboard complet\n"
        "▸ /done — Logger une tâche\n"
        "▸ /habit — Cocher une habitude\n"
        "▸ /revenue — Ajouter des revenus\n"
        "▸ /shop — Dépenser tes coins 🪙\n"
        "▸ /weekly — Voir tes objectifs hebdo\n"
        "▸ /addgoal — Ajouter un objectif\n"
        "▸ /history — Historique\n"
        "▸ /help — Aide complète\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Lance /status pour voir où t'en es ! 💪",
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
    revenue_today = db.get_today_revenue(uid)
    revenue_week = db.get_week_revenue(uid)

    xp = data["xp"]
    coins = data["coins"]
    level_idx, level_name = get_level(xp)

    # XP progress to next level
    current_threshold = LEVELS[level_idx][0]
    next_threshold = LEVELS[level_idx + 1][0] if level_idx + 1 < len(LEVELS) else LEVELS[-1][0] + 5000
    xp_in_level = xp - current_threshold
    xp_needed = next_threshold - current_threshold
    xp_pct = min(100, int(xp_in_level / xp_needed * 100))
    xp_bar = get_progress_bar(xp_pct)

    # Weekly goals progress
    goals_done = sum(1 for g in weekly_goals if g["done"])
    goals_total = len(weekly_goals)
    goals_pct = int(goals_done / goals_total * 100) if goals_total > 0 else 0
    goals_bar = get_progress_bar(goals_pct)

    # Habits today
    habits_done = sum(1 for h in today_habits if h["done_today"])
    habits_total = len(today_habits)
    habits_bar = get_progress_bar(int(habits_done / habits_total * 100) if habits_total else 0)

    streak_emoji = "🔥" if streak >= 3 else "📅"
    streak_msg = f"{streak_emoji} *Streak :* {streak} jour{'s' if streak > 1 else ''}"
    if streak >= 7:
        streak_msg += " 🏆"
    elif streak >= 3:
        streak_msg += " 💪"

    tasks_today_count = len(today_tasks)

    msg = (
        f"╔══════════════════╗\n"
        f"    📊 *TON DASHBOARD*\n"
        f"╚══════════════════╝\n\n"
        f"*{level_name}*\n"
        f"`{xp_bar}` {xp_pct}%\n"
        f"_{xp_in_level} / {xp_needed} XP pour niveau suivant_\n\n"
        f"🪙 *Coins :* {coins}\n"
        f"{streak_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 *AUJOURD'HUI*\n"
        f"▸ Tâches : {tasks_today_count} complétées\n"
        f"▸ Revenus : ${revenue_today:.2f}\n\n"
        f"🏋️ *HABITUDES*  {habits_done}/{habits_total}\n"
        f"`{habits_bar}` {int(habits_done/habits_total*100) if habits_total else 0}%\n\n"
        f"🎯 *OBJECTIFS HEBDO*  {goals_done}/{goals_total}\n"
        f"`{goals_bar}` {goals_pct}%\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Revenus cette semaine :* ${revenue_week:.2f}\n"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Logger tâche", callback_data="prompt_task"),
         InlineKeyboardButton("🏋️ Habitudes", callback_data="show_habits")],
        [InlineKeyboardButton("🎯 Objectifs", callback_data="show_goals"),
         InlineKeyboardButton("🛒 Shop", callback_data="show_shop")],
        [InlineKeyboardButton("📈 Historique", callback_data="show_history")],
    ]
    await update.message.reply_text(msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ─── /done ────────────────────────────────────────────────────────
async def done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)

    args = ctx.args
    if not args:
        keyboard = [
            [InlineKeyboardButton("🟢 Simple (+20🪙)", callback_data="task_simple"),
             InlineKeyboardButton("🟡 Moyen (+40🪙)", callback_data="task_medium")],
            [InlineKeyboardButton("🔴 Difficile (+80🪙)", callback_data="task_hard")],
        ]
        await update.message.reply_text(
            "✅ *Logger une tâche*\n\n"
            "Utilise : `/done [description]`\n"
            "Exemple : `/done Posté 3 clips TikTok`\n\n"
            "Ou choisis la difficulté :",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    description = " ".join(args)
    await _log_task(update, ctx, uid, description, "medium")

async def _log_task(update, ctx, uid, description, difficulty):
    coins_earned = COINS[f"task_{difficulty}"]
    xp_earned = coins_earned * 2

    old_data = db.get_user(uid)
    old_level, _ = get_level(old_data["xp"])

    db.add_task(uid, description, difficulty, coins_earned, xp_earned)
    db.add_coins(uid, coins_earned)
    db.add_xp(uid, xp_earned)
    db.update_streak(uid)

    new_data = db.get_user(uid)
    new_level, new_level_name = get_level(new_data["xp"])

    streak = db.get_streak(uid)
    bonus_msg = ""

    # Streak bonus
    if streak == 7:
        db.add_coins(uid, COINS["streak_7"])
        bonus_msg += f"\n🏆 *STREAK 7 JOURS !* +{COINS['streak_7']}🪙 bonus !"
    elif streak == 30:
        db.add_coins(uid, COINS["streak_30"])
        bonus_msg += f"\n👑 *STREAK 30 JOURS !* +{COINS['streak_30']}🪙 bonus !"

    # Level up
    level_up_msg = ""
    if new_level > old_level:
        db.add_coins(uid, COINS["level_up"])
        level_up_msg = f"\n\n🎉 *LEVEL UP !* Tu es maintenant {new_level_name} !\n+{COINS['level_up']}🪙 bonus !"

    diff_labels = {"simple": "Simple", "medium": "Moyen", "hard": "Difficile"}
    msg_obj = update.message or update.callback_query.message

    await msg_obj.reply_text(
        f"✅ *Tâche validée !*\n\n"
        f"📝 _{description}_\n"
        f"⚡ Difficulté : {diff_labels[difficulty]}\n\n"
        f"🪙 +{coins_earned} coins\n"
        f"⭐ +{xp_earned} XP\n"
        f"🔥 Streak : {streak} jour{'s' if streak > 1 else ''}"
        f"{bonus_msg}{level_up_msg}",
        parse_mode="Markdown"
    )

# ─── /habit ───────────────────────────────────────────────────────
async def habit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    habits = db.get_habits(uid)

    if not habits:
        await update.message.reply_text(
            "🏋️ *Tes habitudes*\n\n"
            "Tu n'as pas encore d'habitudes configurées.\n\n"
            "Ajoute-en une avec :\n`/addhabit [nom]`\n"
            "Exemple : `/addhabit Trading matinal`",
            parse_mode="Markdown"
        )
        return

    today_habits = db.get_today_habits(uid)
    keyboard = []
    for h in today_habits:
        status_emoji = "✅" if h["done_today"] else "⬜"
        label = f"{status_emoji} {h['name']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"habit_{h['id']}")])

    done_count = sum(1 for h in today_habits if h["done_today"])
    bar = get_progress_bar(int(done_count / len(today_habits) * 100) if today_habits else 0)

    await update.message.reply_text(
        f"🏋️ *Habitudes du jour*\n\n"
        f"`{bar}` {done_count}/{len(today_habits)}\n\n"
        f"Clique pour cocher :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /addhabit ────────────────────────────────────────────────────
async def addhabit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)

    if not ctx.args:
        await update.message.reply_text(
            "Usage : `/addhabit [nom]`\n\n"
            "Exemples :\n"
            "• `/addhabit Revue trading 30min`\n"
            "• `/addhabit Poster 1 clip`\n"
            "• `/addhabit Reels research 1h`",
            parse_mode="Markdown"
        )
        return

    name = " ".join(ctx.args)
    db.add_habit(uid, name)
    await update.message.reply_text(
        f"✅ Habitude ajoutée : *{name}*\n\n"
        f"Chaque fois que tu la coches → +{COINS['habit_done']}🪙",
        parse_mode="Markdown"
    )

# ─── /revenue ─────────────────────────────────────────────────────
async def revenue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)

    if not ctx.args:
        await update.message.reply_text(
            "💰 *Ajouter des revenus*\n\n"
            "Usage : `/revenue [montant] [source]`\n\n"
            "Exemples :\n"
            "• `/revenue 150 Clipping`\n"
            "• `/revenue 320.50 Trading`\n"
            "• `/revenue 80 Freelance`",
            parse_mode="Markdown"
        )
        return

    try:
        amount = float(ctx.args[0])
        source = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "Divers"
    except ValueError:
        await update.message.reply_text("❌ Montant invalide. Exemple : `/revenue 150 Clipping`", parse_mode="Markdown")
        return

    coins_earned = int(amount / 100 * COINS["revenue_per_100"])
    xp_earned = coins_earned * 2

    db.add_revenue(uid, amount, source)
    db.add_coins(uid, coins_earned)
    db.add_xp(uid, xp_earned)

    week_total = db.get_week_revenue(uid)

    await update.message.reply_text(
        f"💰 *Revenus ajoutés !*\n\n"
        f"💵 Montant : *${amount:.2f}*\n"
        f"📌 Source : {source}\n\n"
        f"🪙 +{coins_earned} coins\n"
        f"⭐ +{xp_earned} XP\n\n"
        f"📈 Total cette semaine : *${week_total:.2f}*",
        parse_mode="Markdown"
    )

# ─── /addgoal ─────────────────────────────────────────────────────
async def addgoal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)

    if not ctx.args:
        await update.message.reply_text(
            "🎯 *Ajouter un objectif hebdo*\n\n"
            "Usage : `/addgoal [objectif]`\n\n"
            "Exemples :\n"
            "• `/addgoal Poster 5 clips TikTok`\n"
            "• `/addgoal 3 trades rentables`\n"
            "• `/addgoal Trouver 2 nouveaux clients`",
            parse_mode="Markdown"
        )
        return

    goal = " ".join(ctx.args)
    db.add_weekly_goal(uid, goal)
    await update.message.reply_text(
        f"🎯 Objectif ajouté : *{goal}*\n\n"
        f"Complète-le avec /weekly pour +{COINS['weekly_goal_bonus']}🪙 bonus !",
        parse_mode="Markdown"
    )

# ─── /weekly ──────────────────────────────────────────────────────
async def weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    goals = db.get_weekly_goals(uid)

    if not goals:
        await update.message.reply_text(
            "🎯 *Objectifs de la semaine*\n\n"
            "Aucun objectif défini.\n"
            "Ajoute-en un avec `/addgoal [objectif]`",
            parse_mode="Markdown"
        )
        return

    keyboard = []
    for g in goals:
        emoji = "✅" if g["done"] else "⬜"
        keyboard.append([InlineKeyboardButton(f"{emoji} {g['text']}", callback_data=f"goal_{g['id']}")])

    done_count = sum(1 for g in goals if g["done"])
    bar = get_progress_bar(int(done_count / len(goals) * 100))

    await update.message.reply_text(
        f"🎯 *Objectifs de la semaine*\n\n"
        f"`{bar}` {done_count}/{len(goals)}\n\n"
        f"Clique pour marquer comme fait :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /shop ────────────────────────────────────────────────────────
async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    data = db.get_user(uid)
    coins = data["coins"]

    shop_items = db.get_shop_items()
    keyboard = []
    for item in shop_items:
        can_afford = "✅" if coins >= item["cost"] else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{can_afford} {item['emoji']} {item['name']} — 🪙{item['cost']}",
            callback_data=f"buy_{item['id']}"
        )])

    await update.message.reply_text(
        f"🏪 *BOUTIQUE DES RÉCOMPENSES*\n\n"
        f"💰 Ton solde : *{coins} 🪙*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ = Tu peux acheter\n"
        f"❌ = Coins insuffisants\n\n"
        f"Clique pour acheter :",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /history ─────────────────────────────────────────────────────
async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    tasks = db.get_recent_tasks(uid, days=7)
    revenues = db.get_recent_revenues(uid, days=7)

    msg = "📈 *Historique des 7 derniers jours*\n\n"

    if tasks:
        msg += "✅ *Tâches récentes :*\n"
        for t in tasks[:8]:
            d = datetime.fromisoformat(t["created_at"]).strftime("%d/%m")
            diff_map = {"simple": "🟢", "medium": "🟡", "hard": "🔴"}
            emoji = diff_map.get(t["difficulty"], "🟡")
            msg += f"{emoji} `{d}` {t['description']} _(+{t['coins_earned']}🪙)_\n"
        msg += "\n"

    if revenues:
        msg += "💰 *Revenus récents :*\n"
        for r in revenues[:6]:
            d = datetime.fromisoformat(r["created_at"]).strftime("%d/%m")
            msg += f"💵 `{d}` ${r['amount']:.2f} — {r['source']}\n"

    if not tasks and not revenues:
        msg += "_Rien encore cette semaine. Lance-toi !_ 💪"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── /help ────────────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *AIDE COMPLÈTE*\n\n"
        "━━ *TRACKER* ━━\n"
        "`/done [tâche]` — Logger une tâche\n"
        "`/revenue [montant] [source]` — Ajouter revenus\n"
        "`/habit` — Cocher habitudes du jour\n\n"
        "━━ *OBJECTIFS* ━━\n"
        "`/weekly` — Voir objectifs hebdo\n"
        "`/addgoal [texte]` — Ajouter objectif\n"
        "`/addhabit [texte]` — Ajouter habitude\n\n"
        "━━ *COINS & RÉCOMPENSES* ━━\n"
        "`/shop` — Boutique des récompenses\n"
        "`/coins` — Voir ton solde\n\n"
        "━━ *STATS* ━━\n"
        "`/status` — Dashboard complet\n"
        "`/history` — Historique 7 jours\n\n"
        "━━ *GAINS DE COINS* ━━\n"
        f"🟢 Tâche simple : {COINS['task_simple']}🪙\n"
        f"🟡 Tâche moyenne : {COINS['task_medium']}🪙\n"
        f"🔴 Tâche difficile : {COINS['task_hard']}🪙\n"
        f"🏋️ Habitude : {COINS['habit_done']}🪙\n"
        f"🎯 Objectif hebdo : {COINS['weekly_goal_bonus']}🪙\n"
        f"🔥 Streak 7j : {COINS['streak_7']}🪙\n"
        f"🔥 Streak 30j : {COINS['streak_30']}🪙",
        parse_mode="Markdown"
    )

# ─── /coins ───────────────────────────────────────────────────────
async def coins_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_user.first_name)
    data = db.get_user(uid)
    await update.message.reply_text(
        f"🪙 *Ton solde : {data['coins']} coins*\n\n"
        f"⭐ XP total : {data['xp']}\n"
        f"Niveau : {get_level(data['xp'])[1]}\n\n"
        f"Dépense tes coins avec /shop !",
        parse_mode="Markdown"
    )

# ─── CALLBACKS ────────────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    # Task difficulty
    if data in ("task_simple", "task_medium", "task_hard"):
        difficulty = data.replace("task_", "")
        await query.message.reply_text(
            f"📝 Envoie la description de ta tâche *{difficulty}* :",
            parse_mode="Markdown"
        )
        ctx.user_data["pending_task"] = difficulty
        return

    if data == "prompt_task":
        keyboard = [
            [InlineKeyboardButton("🟢 Simple (+20🪙)", callback_data="task_simple"),
             InlineKeyboardButton("🟡 Moyen (+40🪙)", callback_data="task_medium")],
            [InlineKeyboardButton("🔴 Difficile (+80🪙)", callback_data="task_hard")],
        ]
        await query.message.reply_text(
            "✅ *Nouvelle tâche — choisis la difficulté :*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Habit toggle
    if data.startswith("habit_"):
        habit_id = int(data.replace("habit_", ""))
        already_done = db.is_habit_done_today(uid, habit_id)
        if already_done:
            await query.message.reply_text("✅ Cette habitude est déjà cochée aujourd'hui !")
            return
        habit_name = db.complete_habit_today(uid, habit_id)
        db.add_coins(uid, COINS["habit_done"])
        db.add_xp(uid, COINS["habit_done"])
        db.update_streak(uid)
        streak = db.get_streak(uid)
        await query.message.reply_text(
            f"🏋️ *Habitude cochée !*\n\n"
            f"✅ _{habit_name}_\n"
            f"🪙 +{COINS['habit_done']} coins\n"
            f"🔥 Streak : {streak} jour{'s' if streak > 1 else ''}",
            parse_mode="Markdown"
        )
        return

    # Goal toggle
    if data.startswith("goal_"):
        goal_id = int(data.replace("goal_", ""))
        already_done = db.is_goal_done(uid, goal_id)
        if already_done:
            await query.message.reply_text("✅ Cet objectif est déjà complété !")
            return
        goal_text = db.complete_goal(uid, goal_id)
        db.add_coins(uid, COINS["weekly_goal_bonus"])
        db.add_xp(uid, COINS["weekly_goal_bonus"] * 2)
        await query.message.reply_text(
            f"🎯 *Objectif complété !*\n\n"
            f"✅ _{goal_text}_\n"
            f"🪙 +{COINS['weekly_goal_bonus']} coins\n"
            f"⭐ +{COINS['weekly_goal_bonus'] * 2} XP",
            parse_mode="Markdown"
        )
        return

    # Shop display
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
            f"🏪 *BOUTIQUE*\n\n💰 Solde : *{coins}🪙*\n\nClique pour acheter :",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Buy item
    if data.startswith("buy_"):
        item_id = int(data.replace("buy_", ""))
        item = db.get_shop_item(item_id)
        user_data = db.get_user(uid)

        if user_data["coins"] < item["cost"]:
            missing = item["cost"] - user_data["coins"]
            await query.message.reply_text(
                f"❌ Pas assez de coins !\n\n"
                f"Il te manque *{missing}🪙*\n"
                f"Continue à bosser pour en gagner ! 💪",
                parse_mode="Markdown"
            )
            return

        db.spend_coins(uid, item["cost"])
        db.add_purchase(uid, item_id)
        remaining = user_data["coins"] - item["cost"]

        await query.message.reply_text(
            f"🎉 *Achat confirmé !*\n\n"
            f"{item['emoji']} *{item['name']}*\n"
            f"_{item['description']}_\n\n"
            f"🪙 -{item['cost']} coins\n"
            f"💰 Solde restant : {remaining}🪙\n\n"
            f"Tu l'as mérité ! Profites-en 😎",
            parse_mode="Markdown"
        )
        return

    # Show habits
    if data == "show_habits":
        today_habits = db.get_today_habits(uid)
        if not today_habits:
            await query.message.reply_text(
                "Aucune habitude. Ajoute-en avec `/addhabit [nom]`",
                parse_mode="Markdown"
            )
            return
        keyboard = []
        for h in today_habits:
            emoji = "✅" if h["done_today"] else "⬜"
            keyboard.append([InlineKeyboardButton(f"{emoji} {h['name']}", callback_data=f"habit_{h['id']}")])
        await query.message.reply_text("🏋️ *Habitudes du jour :*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Show goals
    if data == "show_goals":
        goals = db.get_weekly_goals(uid)
        if not goals:
            await query.message.reply_text(
                "Aucun objectif. Ajoute-en avec `/addgoal [texte]`",
                parse_mode="Markdown"
            )
            return
        keyboard = []
        for g in goals:
            emoji = "✅" if g["done"] else "⬜"
            keyboard.append([InlineKeyboardButton(f"{emoji} {g['text']}", callback_data=f"goal_{g['id']}")])
        await query.message.reply_text("🎯 *Objectifs de la semaine :*", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Show history
    if data == "show_history":
        tasks = db.get_recent_tasks(uid, days=7)
        msg = "📈 *Dernières tâches :*\n\n"
        if tasks:
            for t in tasks[:6]:
                d = datetime.fromisoformat(t["created_at"]).strftime("%d/%m")
                msg += f"✅ `{d}` {t['description']}\n"
        else:
            msg += "_Aucune tâche cette semaine._"
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

# ─── TEXT MESSAGE (for pending task) ──────────────────────────────
async def text_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if "pending_task" in ctx.user_data:
        difficulty = ctx.user_data.pop("pending_task")
        description = update.message.text
        await _log_task(update, ctx, uid, description, difficulty)
    else:
        await update.message.reply_text(
            "Utilise une commande ! Tape /help pour voir toutes les commandes. 😊"
        )

# ─── MAIN ─────────────────────────────────────────────────────────
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN manquant dans les variables d'environnement !")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("habit", habit))
    app.add_handler(CommandHandler("addhabit", addhabit))
    app.add_handler(CommandHandler("revenue", revenue))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("addgoal", addgoal))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("coins", coins_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    logger.info("🚀 BizTracker Bot démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
