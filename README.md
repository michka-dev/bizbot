# 🚀 BizTracker Bot v2

Bot Telegram ultra-complet pour gamifier ton business.
Todoist sync, Notion journal, graphiques visuels, défis hebdo, leaderboard, rappels auto.

---

## ⚡ Setup Railway (5 min)

### 1. Variables d'environnement sur Railway
```
BOT_TOKEN     = ton token BotFather
```

### 2. Variables optionnelles
```
DB_PATH       = biztracker.db   (chemin base de données)
PORT          = 8080            (pour le webhook Todoist)
TODOIST_CLIENT_SECRET = ...     (optionnel, pour sécuriser les webhooks)
```

---

## 🔗 Connecter Todoist

1. Dans le bot → `/setup` → "Connecter Todoist"
2. Va sur todoist.com → Settings → Integrations → API token
3. Dans le bot : `/settoken todoist TON_API_TOKEN`
4. Configure le webhook dans Todoist Developer Console :
   - URL : `https://TON-APP.railway.app/webhook/todoist`
   - Événement : `item:completed`

---

## 📓 Connecter Notion

1. Va sur notion.so/my-integrations → "New integration"
2. Copie le "Internal Integration Secret"
3. Dans le bot : `/settoken notion secret_XXXXX`
4. Le bot crée automatiquement une DB "BizTracker Journal" dans Notion

---

## 📊 Fonctionnalités

### Commandes
| Commande | Description |
|---|---|
| `/status` | Dashboard avec XP, coins, streak, stats hebdo |
| `/done [tâche]` | Logger une tâche (simple/moyen/difficile) |
| `/revenue [montant] [source]` | Ajouter revenus |
| `/habit` | Cocher habitudes du jour |
| `/addhabit [nom]` | Créer une habitude |
| `/weekly` | Objectifs de la semaine |
| `/addgoal [texte]` | Créer un objectif |
| `/challenge` | Voir/générer défis hebdo |
| `/stats` | Graphique visuel complet 📊 |
| `/leaderboard` | Classement XP semaine |
| `/shop` | Boutique récompenses |
| `/history` | Historique 7 jours |
| `/setup` | Configurer Todoist/Notion/Rappels |
| `/settoken [service] [token]` | Connecter un service |
| `/coins` | Voir solde + niveau + statut |

### Coins gagnés
| Action | Coins |
|---|---|
| Tâche simple | +20 🪙 |
| Tâche moyenne | +40 🪙 |
| Tâche difficile | +80 🪙 |
| Todoist P1 (urgent) | +80 🪙 |
| Todoist P2 | +40 🪙 |
| Habitude cochée | +15 🪙 |
| Objectif hebdo | +150 🪙 |
| Défi complété | +200-400 🪙 |
| Streak 7 jours | +200 🪙 |
| Streak 30 jours | +500 🪙 |
| Level up | +100 🪙 |

### Boutique (shop)
| Récompense | Coût | Tier |
|---|---|---|
| ☕ Café de luxe | 30 🪙 | Bronze |
| 🏋️ Session sport | 60 🪙 | Bronze |
| 🍦 Dessert premium | 80 🪙 | Bronze |
| 🎬 Movie night | 150 🪙 | Bronze |
| 🍕 Resto de luxe | 250 🪙 | Silver |
| 🌴 Free day | 350 🪙 | Silver |
| 🎧 Nouvel accessoire | 400 🪙 | Silver |
| 🎮 Nouveau jeu | 500 🪙 | Gold |
| ✈️ Weekend trip | 1500 🪙 | Gold |
| 👑 Big reward | 3000 🪙 | Legend |

### Niveaux XP
| Niveau | XP |
|---|---|
| 🌱 Débutant | 0 |
| ⚡ Hustle Mode | 500 |
| 🔥 En Feu | 1 500 |
| 💎 Diamant | 3 000 |
| 🚀 Entrepreneur | 6 000 |
| 👑 Business King | 10 000 |
| 🌍 Empire Builder | 20 000 |
| 🏛️ Légende | 50 000 |

### Automatisations
- ☀️ **Rappel matin 8h** — quote motivante + stats + défis actifs
- 🌙 **Check-in soir 21h** — récap + alerte si streak en danger + sync Notion
- 📆 **Récap dimanche 20h** — bilan semaine complet + comparaison % + sync Notion

---

## 📁 Structure
```
bizbot_v2/
├── bot.py              # Logique principale + schedulers + webhook
├── database.py         # SQLite — toutes les tables
├── stats_image.py      # Génération graphiques matplotlib
├── notion_client.py    # API Notion
├── todoist_handler.py  # Webhook Todoist
├── requirements.txt
├── Procfile
└── README.md
```
