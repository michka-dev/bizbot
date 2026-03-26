import os
import hmac
import hashlib
import json
import logging
from aiohttp import web

logger = logging.getLogger(__name__)

TODOIST_CLIENT_SECRET = os.environ.get("TODOIST_CLIENT_SECRET", "")

PRIORITY_MULTIPLIER = {4: 2.0, 3: 1.5, 2: 1.2, 1: 1.0}

def verify_signature(body: bytes, signature: str) -> bool:
    if not TODOIST_CLIENT_SECRET:
        return True
    expected = hmac.new(
        TODOIST_CLIENT_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")

async def handle_todoist_webhook(request, bot, db, process_todoist_task):
    try:
        body = await request.read()
        sig = request.headers.get("X-Todoist-Hmac-SHA256", "")
        if TODOIST_CLIENT_SECRET and not verify_signature(body, sig):
            logger.warning("Invalid Todoist webhook signature")
            return web.Response(status=403, text="Invalid signature")

        data = json.loads(body)
        event_type = data.get("event_name", "")
        item = data.get("event_data", {})

        if event_type == "item:completed":
            todoist_user_id = str(data.get("user_id", ""))
            await process_todoist_task(todoist_user_id, item, bot, db)

        return web.Response(status=200, text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text="Error")

def get_task_difficulty_from_priority(priority):
    if priority == 4:
        return "hard"
    elif priority == 3:
        return "medium"
    else:
        return "simple"
