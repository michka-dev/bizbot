# 🚀 BizTracker Bot — Telegram

Un bot Telegram qui gamifie ton business : tâches, revenus, habitudes, objectifs hebdo, coins et boutique de récompenses.

---

## ⚡ Installation rapide (5 min)

### 1. Crée ton bot Telegram
1. Ouvre Telegram, cherche **@BotFather**
2. Envoie `/newbot`
3. Donne un nom : ex. `Mon BizTracker`
4. Donne un username : ex. `monbiztracker_bot`
5. Copie le **token** qu'il te donne (ressemble à : `123456789:ABCdef...`)

---

### 2. Déploie sur Railway (gratuit)

1. Va sur [railway.app](https://railway.app) et connecte ton GitHub
2. Clique **New Project → Deploy from GitHub repo**
3. Upload ou push ce dossier sur un repo GitHub public/privé
4. Dans Railway → ton projet → **Variables** → Ajoute :
   ```
   BOT_TOKEN = ton_token_ici
   ```
5. Railway démarre automatiquement ton bot ✅

**Alternative : Render.com**
1. Va sur [render.com](https://render.com)
2. New → Web Service → connecte ton repo
3. Build Command : `pip install -r requirements.txt`
4. Start Command : `python bot.py`
5. Ajoute la variable d'environnement `BOT_TOKEN`

---

### 3. Option locale (pour tester)

```bash
# Installe les dépendances
pip install -r requirements.txt

# Crée un fichier .env (optionnel, ou exporte directement)
export BOT_TOKEN="ton_token_ici"

# Lance le bot
python bot.py
```

---

## 📱 Commandes disponibles

### Tracker
| Commande | Description | Coins gagnés |
|---|---|---|
| `/done [tâche]` | Logger une tâche complétée | 20-80 🪙 |
| `/revenue [montant] [source]` | Ajouter des revenus | 10🪙 / 100$ |
| `/habit` | Cocher habitudes du jour | 15 🪙 chacune |

### Setup
| Commande | Description |
|---|---|
| `/addhabit [nom]` | Ajouter une habitude quotidienne |
| `/addgoal [texte]` | Ajouter un objectif hebdo |

### Stats
| Commande | Description |
|---|---|
| `/status` | Dashboard complet avec barres de progression |
| `/weekly` | Voir et cocher objectifs de la semaine |
| `/history` | Historique des 7 derniers jours |
| `/coins` | Voir ton solde |

### Récompenses
| Commande | Description |
|---|---|
| `/shop` | Boutique — dépenser ses coins |

---

## 🪙 Système de coins

| Action | Coins |
|---|---|
| Tâche simple | +20 🪙 |
| Tâche moyenne | +40 🪙 |
| Tâche difficile | +80 🪙 |
| Habitude cochée | +15 🪙 |
| Objectif hebdo | +150 🪙 |
| Revenus (par 100$) | +10 🪙 |
| Streak 7 jours | +200 🪙 bonus |
| Streak 30 jours | +500 🪙 bonus |
| Level up | +100 🪙 bonus |

---

## 🏪 Boutique par défaut

| Récompense | Coût |
|---|---|
| ☕ Café de luxe | 30 🪙 |
| 🏋️ Session sport | 60 🪙 |
| 🍦 Dessert premium | 80 🪙 |
| 🎬 Movie night | 150 🪙 |
| 🍕 Resto de luxe | 250 🪙 |
| 🌴 Free day | 350 🪙 |
| 🎧 Nouvel accessoire | 400 🪙 |
| 🎮 Nouveau jeu | 500 🪙 |

> Tu peux modifier les items du shop directement dans `database.py` → `DEFAULT_SHOP_ITEMS`

---

## 🎮 Système de niveaux (XP)

| Niveau | XP requis |
|---|---|
| 🌱 Débutant | 0 |
| ⚡ Hustle Mode | 500 |
| 🔥 En Feu | 1 500 |
| 💎 Diamant | 3 000 |
| 🚀 Entrepreneur | 6 000 |
| 👑 Business King | 10 000 |
| 🌍 Empire Builder | 20 000 |

---

## 🛠 Personnaliser

### Modifier les récompenses du shop
Dans `database.py`, modifie `DEFAULT_SHOP_ITEMS` :
```python
DEFAULT_SHOP_ITEMS = [
    (1, "🎮", "Nouveau jeu", "Steam / PS Store", 500),
    (2, "🌴", "Free day",   "Journée sans boulot", 350),
    # Ajoute tes propres récompenses ici !
]
```

### Modifier les gains de coins
Dans `bot.py`, modifie le dict `COINS` :
```python
COINS = {
    "task_simple": 20,   # Augmente si tu veux gagner plus vite
    "task_medium": 40,
    ...
}
```

---

## 📁 Structure du projet

```
bizbot/
├── bot.py          # Logique principale du bot
├── database.py     # Base de données SQLite
├── requirements.txt
├── Procfile        # Pour Railway/Render
└── README.md
```

---

## 💡 Tips d'utilisation

**Pour le clipping :**
```
/addgoal Poster 5 clips cette semaine
/addhabit Éditer 1 clip par jour
/done Montage clip #12 pour @compte
```

**Pour le trading :**
```
/addhabit Revue marché 30min le matin
/revenue 250 Day trading
/done Backtesté nouvelle stratégie
```

**Pour les réseaux sociaux :**
```
/addgoal Atteindre 1000 vues sur TikTok
/addhabit Poster 1 contenu par jour
/done Reel Instagram — 3 prises
```
