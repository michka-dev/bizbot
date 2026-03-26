import os
import requests
from datetime import date, datetime

NOTION_VERSION = "2022-06-28"

def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

def test_connection(token):
    try:
        r = requests.get("https://api.notion.com/v1/users/me", headers=_headers(token), timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def get_databases(token):
    try:
        r = requests.post(
            "https://api.notion.com/v1/search",
            headers=_headers(token),
            json={"filter": {"value": "database", "property": "object"}, "page_size": 20},
            timeout=5
        )
        if r.status_code == 200:
            return r.json().get("results", [])
    except Exception:
        pass
    return []

def create_journal_database(token, parent_page_id=None):
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id} if parent_page_id else {"type": "workspace", "workspace": True},
        "title": [{"type": "text", "text": {"content": "📓 BizTracker — Journal"}}],
        "properties": {
            "Date": {"title": {}},
            "Tâches": {"number": {"format": "number"}},
            "Revenus": {"number": {"format": "dollar"}},
            "Coins gagnés": {"number": {"format": "number"}},
            "XP gagné": {"number": {"format": "number"}},
            "Streak": {"number": {"format": "number"}},
            "Notes": {"rich_text": {}},
            "Humeur": {"select": {"options": [
                {"name": "🔥 En feu", "color": "red"},
                {"name": "💪 Motivé", "color": "green"},
                {"name": "😐 Neutre", "color": "yellow"},
                {"name": "😴 Fatigue", "color": "gray"},
            ]}},
        }
    }
    try:
        r = requests.post("https://api.notion.com/v1/databases", headers=_headers(token), json=payload, timeout=5)
        if r.status_code == 200:
            return r.json().get("id")
    except Exception:
        pass
    return None

def log_daily_journal(token, db_id, data):
    today_str = date.today().isoformat()
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Date": {"title": [{"text": {"content": today_str}}]},
            "Tâches": {"number": data.get("tasks", 0)},
            "Revenus": {"number": float(data.get("revenue", 0))},
            "Coins gagnés": {"number": data.get("coins", 0)},
            "XP gagné": {"number": data.get("xp", 0)},
            "Streak": {"number": data.get("streak", 0)},
        }
    }
    if data.get("notes"):
        payload["properties"]["Notes"] = {"rich_text": [{"text": {"content": data["notes"]}}]}
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=_headers(token), json=payload, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def log_weekly_recap(token, db_id, week_data):
    from datetime import date, timedelta
    ws = date.today() - timedelta(days=date.today().weekday())
    title = f"Semaine du {ws.strftime('%d/%m/%Y')}"
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Date": {"title": [{"text": {"content": title}}]},
            "Tâches": {"number": week_data.get("tasks", 0)},
            "Revenus": {"number": float(week_data.get("revenue", 0))},
            "Coins gagnés": {"number": week_data.get("coins", 0)},
            "XP gagné": {"number": week_data.get("xp", 0)},
            "Notes": {"rich_text": [{"text": {"content": f"Récap auto — {title}"}}]},
        }
    }
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=_headers(token), json=payload, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
