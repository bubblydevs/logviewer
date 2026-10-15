"""
Ticket list shown on the home page to logged in staff (only when Discord auth is enabled).
"""

import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import dateutil.parser
from natural.date import duration

PAGE_SIZE = int(os.getenv("DASHBOARD_PAGE_SIZE", "25"))
MAX_PAGE = 40

TABS = ("recent", "mine")
# Modmail message types that are actual replies to the user (not internal notes or system messages).
REPLY_TYPES = ["thread_message", "anonymous"]
STATUSES = ("all", "open", "closed")


def _id_values(user_id):
    # Modmail stores ids as strings, but accept ints too in case an older version wrote them.
    values = [str(user_id)]
    if str(user_id).isdigit():
        values.append(int(user_id))
    return values


def build_match(tab, status, query, user_id):
    conditions = []

    if tab == "mine":
        ids = {"$in": _id_values(user_id)}
        # Tickets this staff member closed or replied to.
        conditions.append({"$or": [
            {"closer.id": ids},
            {"messages": {"$elemMatch": {"author.id": ids, "type": {"$in": REPLY_TYPES}}}},
        ]})

    if status == "open":
        conditions.append({"open": True})
    elif status == "closed":
        conditions.append({"open": False})

    if query:
        pattern = {"$regex": re.escape(query), "$options": "i"}
        conditions.append({"$or": [
            {"key": query},
            {"recipient.id": {"$in": _id_values(query)}},
            {"recipient.name": pattern},
            {"creator.name": pattern},
            {"closer.name": pattern},
            {"title": pattern},
        ]})

    return {"$and": conditions} if conditions else {}


def _pipeline(match, limit, user_id):
    return [
        {"$match": match},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "key": 1,
            "open": 1,
            "title": 1,
            "created_at": 1,
            "closed_at": 1,
            "recipient": 1,
            "closer": 1,
            "you_replied": {"$anyElementTrue": [{"$map": {
                "input": {"$ifNull": ["$messages", []]},
                "in": {"$and": [
                    {"$in": ["$$this.author.id", _id_values(user_id)]},
                    {"$in": ["$$this.type", REPLY_TYPES]},
                ]},
            }}]},
            "message_count": {"$size": {"$filter": {
                "input": {"$ifNull": ["$messages", []]},
                "cond": {"$not": [{"$in": ["$$this.type", ["internal", "system"]]}]},
            }}},
        }},
    ]


def _default_avatar(user):
    try:
        return "https://cdn.discordapp.com/embed/avatars/{}.png".format((int(user.get("id")) >> 22) % 6)
    except (TypeError, ValueError):
        return "https://cdn.discordapp.com/embed/avatars/0.png"


def _ago(value):
    if not value:
        return None
    try:
        when = dateutil.parser.parse(value).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
    return {
        "human": duration(when, now=datetime.now(timezone.utc)),
        "exact": when.strftime("%d %b %Y, %H:%M UTC"),
    }


def _to_ticket(doc, path, log_prefix, user_id):
    recipient = doc.get("recipient") or {}
    closer = doc.get("closer") or {}
    return {
        "url": f"{log_prefix}/{path}/{doc['key']}" if path else f"{log_prefix}/{doc['key']}",
        "key": doc["key"],
        "path": path,
        "open": doc.get("open", False),
        "title": doc.get("title"),
        "recipient_name": recipient.get("name") or "Unknown user",
        "recipient_id": recipient.get("id"),
        "recipient_avatar": recipient.get("avatar_url") or _default_avatar(recipient),
        "recipient_default_avatar": _default_avatar(recipient),
        "closer_name": closer.get("name") if not doc.get("open") else None,
        "closer_is_you": not doc.get("open") and str(closer.get("id")) == str(user_id),
        "you_replied": bool(doc.get("you_replied")),
        "message_count": doc.get("message_count", 0),
        "created": _ago(doc.get("created_at")),
        "closed": _ago(doc.get("closed_at")) if not doc.get("open") else None,
    }


async def list_tickets(sources, log_prefix, user_id, tab, status, query, page):
    """
    sources: list of (path, db) pairs, path is None in single database mode.
    Returns (tickets, has_next).
    """
    match = build_match(tab, status, query, user_id)
    skip = (page - 1) * PAGE_SIZE
    # Every database has to return enough rows to cover this page once they're merged together.
    limit = skip + PAGE_SIZE + 1

    docs = []
    for path, db in sources:
        cursor = db.logs.aggregate(_pipeline(match, limit, user_id), allowDiskUse=True)
        async for doc in cursor:
            docs.append((path, doc))

    docs.sort(key=lambda item: item[1].get("created_at") or "", reverse=True)
    window = docs[skip:skip + PAGE_SIZE]

    return [_to_ticket(doc, path, log_prefix, user_id) for path, doc in window], len(docs) > skip + PAGE_SIZE


def parse_args(args, server_paths):
    tab = args.get("tab", "recent")
    status = args.get("status", "all")
    server = args.get("server") or None
    query = (args.get("q") or "").strip()[:100]

    try:
        page = min(max(int(args.get("page", 1)), 1), MAX_PAGE)
    except ValueError:
        page = 1

    return {
        "tab": tab if tab in TABS else "recent",
        "status": status if status in STATUSES else "all",
        "server": server if server in server_paths else None,
        "q": query,
        "page": page,
    }


def link(filters, **changes):
    """Builds a home page URL from the current filters, leaving out defaults."""
    params = {**filters, **changes}
    if "page" not in changes:
        params["page"] = 1
    defaults = {"tab": "recent", "status": "all", "server": None, "q": "", "page": 1}
    query = urlencode({k: v for k, v in params.items() if v != defaults.get(k)})
    return "/?" + query if query else "/"
