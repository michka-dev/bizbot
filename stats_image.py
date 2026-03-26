import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from datetime import date, timedelta

DARK_BG     = "#0d1117"
CARD_BG     = "#161b22"
ACCENT      = "#7c3aed"
ACCENT2     = "#10b981"
ACCENT3     = "#f59e0b"
TEXT_MAIN   = "#e6edf3"
TEXT_DIM    = "#7d8590"
GRID_COLOR  = "#21262d"

def make_stats_image(user_data, daily_stats, week_now, week_prev, leaderboard, challenges):
    fig = plt.figure(figsize=(10, 12), facecolor=DARK_BG)
    fig.patch.set_facecolor(DARK_BG)
    gs = GridSpec(4, 2, figure=fig, hspace=0.55, wspace=0.35,
                  left=0.08, right=0.95, top=0.93, bottom=0.05)

    name = user_data.get("name", "Toi")
    xp = user_data.get("xp", 0)
    coins = user_data.get("coins", 0)
    streak = user_data.get("streak", 0)

    # ── TITLE ──
    fig.text(0.5, 0.965, f"📊 {name} — Rapport hebdo", ha="center", fontsize=16,
             color=TEXT_MAIN, fontweight="bold")
    fig.text(0.5, 0.945, date.today().strftime("%d %B %Y"), ha="center",
             fontsize=11, color=TEXT_DIM)

    # ── 1. TÂCHES PAR JOUR (bar chart) ──
    ax1 = fig.add_subplot(gs[0, :])
    ax1.set_facecolor(CARD_BG)
    days_labels, tasks_vals, coins_vals = [], [], []
    day_names = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    today = date.today()
    for i in range(7):
        d = today - timedelta(days=6 - i)
        days_labels.append(day_names[d.weekday()])
        stat = next((s for s in daily_stats if s["stat_date"] == d.isoformat()), None)
        tasks_vals.append(stat["tasks_done"] if stat else 0)
        coins_vals.append(stat["coins_earned"] if stat else 0)

    x = range(7)
    bars = ax1.bar(x, tasks_vals, color=ACCENT, alpha=0.85, width=0.55, zorder=3)
    ax1.set_xticks(x)
    ax1.set_xticklabels(days_labels, color=TEXT_DIM, fontsize=10)
    ax1.set_ylabel("Tâches", color=TEXT_DIM, fontsize=9)
    ax1.tick_params(colors=TEXT_DIM, labelsize=9)
    ax1.spines[:].set_color(GRID_COLOR)
    ax1.set_title("Tâches complétées — 7 derniers jours", color=TEXT_MAIN, fontsize=11, pad=8)
    ax1.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, zorder=0)
    ax1.set_axisbelow(True)
    for bar, val in zip(bars, tasks_vals):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                     str(val), ha="center", va="bottom", color=TEXT_MAIN, fontsize=9, fontweight="bold")

    # ── 2. COMPARAISON SEMAINES (week-over-week) ──
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.set_facecolor(CARD_BG)
    categories = ["Tâches", "Coins", "XP"]
    prev_vals = [week_prev.get("tasks", 0), week_prev.get("coins", 0) // 10, week_prev.get("xp", 0) // 20]
    now_vals  = [week_now.get("tasks", 0),  week_now.get("coins", 0) // 10,  week_now.get("xp", 0) // 20]
    x2 = [0, 1.2, 2.4]
    w = 0.45
    ax2.bar([xi - w/2 for xi in x2], prev_vals, width=w, color=TEXT_DIM,  alpha=0.6, label="Sem. passée", zorder=3)
    ax2.bar([xi + w/2 for xi in x2], now_vals,  width=w, color=ACCENT2, alpha=0.85, label="Cette sem.", zorder=3)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(categories, color=TEXT_DIM, fontsize=9)
    ax2.tick_params(colors=TEXT_DIM, labelsize=8)
    ax2.spines[:].set_color(GRID_COLOR)
    ax2.set_title("Sem. passée vs actuelle", color=TEXT_MAIN, fontsize=10, pad=8)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, zorder=0)
    ax2.set_axisbelow(True)
    ax2.legend(fontsize=8, facecolor=DARK_BG, labelcolor=TEXT_DIM, edgecolor=GRID_COLOR)

    # % change badge
    if week_prev.get("tasks", 0) > 0:
        pct = int((week_now.get("tasks", 0) - week_prev.get("tasks", 0)) / week_prev["tasks"] * 100)
        color = ACCENT2 if pct >= 0 else "#ef4444"
        sign = "+" if pct >= 0 else ""
        ax2.text(0.98, 0.95, f"{sign}{pct}%", transform=ax2.transAxes,
                 ha="right", va="top", color=color, fontsize=12, fontweight="bold")

    # ── 3. COINS CUMULÉS (line chart) ──
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.set_facecolor(CARD_BG)
    cum_coins = []
    running = 0
    for i in range(7):
        d = today - timedelta(days=6 - i)
        stat = next((s for s in daily_stats if s["stat_date"] == d.isoformat()), None)
        running += stat["coins_earned"] if stat else 0
        cum_coins.append(running)
    ax3.plot(range(7), cum_coins, color=ACCENT3, linewidth=2.5, marker="o",
             markersize=5, markerfacecolor=ACCENT3, zorder=3)
    ax3.fill_between(range(7), cum_coins, alpha=0.15, color=ACCENT3)
    ax3.set_xticks(range(7))
    ax3.set_xticklabels(days_labels, color=TEXT_DIM, fontsize=9)
    ax3.tick_params(colors=TEXT_DIM, labelsize=8)
    ax3.spines[:].set_color(GRID_COLOR)
    ax3.set_title("Coins accumulés (semaine)", color=TEXT_MAIN, fontsize=10, pad=8)
    ax3.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, zorder=0)
    ax3.set_axisbelow(True)

    # ── 4. DÉFIS HEBDO (progress bars) ──
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.set_facecolor(CARD_BG)
    ax4.set_xlim(0, 1)
    ax4.axis("off")
    ax4.set_title("Défis de la semaine", color=TEXT_MAIN, fontsize=10, pad=8)
    if challenges:
        for i, ch in enumerate(challenges[:4]):
            y = 0.85 - i * 0.22
            pct = min(1.0, ch["progress"] / ch["target"]) if ch["target"] > 0 else 0
            color = ACCENT2 if ch["done"] else ACCENT
            ax4.barh(y, 1.0, height=0.12, color=GRID_COLOR, left=0)
            ax4.barh(y, pct, height=0.12, color=color, left=0, alpha=0.85)
            label = ch["title"][:22] + "…" if len(ch["title"]) > 22 else ch["title"]
            ax4.text(0.01, y + 0.01, label, va="center", color=TEXT_MAIN, fontsize=8)
            ax4.text(0.99, y + 0.01, f"{ch['progress']}/{ch['target']}", va="center",
                     ha="right", color=TEXT_DIM, fontsize=8)
    else:
        ax4.text(0.5, 0.5, "Aucun défi actif\n/challenge pour en créer",
                 ha="center", va="center", color=TEXT_DIM, fontsize=9)

    # ── 5. LEADERBOARD ──
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.set_facecolor(CARD_BG)
    ax5.axis("off")
    ax5.set_title("🏆 Leaderboard semaine", color=TEXT_MAIN, fontsize=10, pad=8)
    if leaderboard:
        medals = ["🥇", "🥈", "🥉"]
        for i, entry in enumerate(leaderboard[:5]):
            y = 0.85 - i * 0.18
            medal = medals[i] if i < 3 else f"#{i+1}"
            color = [ACCENT3, TEXT_DIM, "#cd7f32", TEXT_DIM, TEXT_DIM][i]
            ax5.text(0.02, y, f"{medal} {entry['name']}", va="center",
                     color=color, fontsize=9, fontweight="bold" if i == 0 else "normal")
            ax5.text(0.98, y, f"{entry['week_xp']} XP", va="center",
                     ha="right", color=TEXT_DIM, fontsize=8)
    else:
        ax5.text(0.5, 0.5, "Seul pour l'instant\nInvite des amis !",
                 ha="center", va="center", color=TEXT_DIM, fontsize=9)

    # ── 6. STATS GLOBALES (KPI cards) ──
    ax6 = fig.add_subplot(gs[3, :])
    ax6.set_facecolor(CARD_BG)
    ax6.axis("off")

    kpis = [
        ("⭐ XP Total",  f"{xp:,}",    ACCENT),
        ("🪙 Coins",     f"{coins:,}",  ACCENT3),
        ("🔥 Streak",    f"{streak}j",  "#ef4444"),
        ("✅ Cette sem.", f"{week_now.get('tasks',0)} tâches", ACCENT2),
        ("💰 Revenus",   f"${week_now.get('revenue',0):.0f}", ACCENT2),
    ]
    for i, (label, val, color) in enumerate(kpis):
        cx = 0.1 + i * 0.2
        ax6.add_patch(mpatches.FancyBboxPatch(
            (cx - 0.085, 0.1), 0.17, 0.8,
            boxstyle="round,pad=0.02", facecolor=DARK_BG, edgecolor=GRID_COLOR, linewidth=0.8
        ))
        ax6.text(cx, 0.65, val, ha="center", va="center", color=color,
                 fontsize=14, fontweight="bold")
        ax6.text(cx, 0.28, label, ha="center", va="center", color=TEXT_DIM, fontsize=8)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
