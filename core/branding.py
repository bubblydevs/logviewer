"""
Per-community branding, picked with BRANDING=java|billow|none in .env.

Tailwind scans this file for class names (see tailwind.config.js), so any class
used here must be written out in full.
"""

import os


def _truthy(val):
    return str(val).strip().lower() in ("y", "yes", "t", "true", "on", "1")


def _env(name, default=None):
    return os.getenv(name) or default


def _java():
    return {
        "key": "java",
        "name": "Java",
        "site_title": "Java Transcripts",
        "logo_url": _env("JAVA_LOGO_URL", "https://payhip.com/cdn-cgi/image/format=auto,width=1500/https://pe56d.s3.amazonaws.com/o_1hkesjldmd5bk2917qcavsq0uu.png"),
        "logo_class": "h-8 w-auto",
        "logo_text": None,
        "hero_url": _env("JAVA_HERO_URL", "https://pe56d.s3.amazonaws.com/o_1k21acu1p9fsg7lmopmanhmu1o.png"),
        "hero_overlay": "bg-black/55",
        "heading_class": "tracking-tight",
        "button_class": "bg-white text-black hover:bg-white/90",
        "home_title": "Staff transcripts",
        "home_text": "Every ticket transcript in one place. Sign in with your Discord account to see them.",
        "notice": "Java follows data protection laws.",
        "policy_url": _env("JAVA_POLICY_URL", "https://docs.google.com/document/d/1BwLS66KzTESwoaGdqKYqJysGHHBW4-jqWvM3920O9yQ/edit?tab=t.0"),
        "policy_label": "Java Staff Code of Conduct",
        "policy_label_short": "Code of Conduct",
        "credit": None,
    }


def _billow():
    policy_url = _env("BILLOW_POLICY_URL")
    return {
        "key": "billow",
        "name": "Billow Productions",
        "site_title": "Billow Transcripts",
        "logo_url": _env("BILLOW_LOGO_URL", "https://www.nottinghamshirerpc.co.uk/NewBillowLogo.png"),
        "logo_class": "-ml-2 h-12 w-12",
        "logo_text": "Billow Productions",
        "hero_url": _env("BILLOW_HERO_URL", "https://www.nottinghamshirerpc.co.uk/Background.png"),
        "hero_overlay": "bg-black/70",
        "heading_class": "uppercase tracking-tight",
        "button_class": "bg-white text-blue-900 hover:bg-white/90",
        "home_title": "Ticket transcripts",
        "home_text": "Support ticket records for Nottinghamshire RPC and the other Billow Productions communities. Open the link from your ticket to view its transcript.",
        "notice": "Billow Productions follows data protection laws.",
        "policy_url": policy_url,
        "policy_label": _env("BILLOW_POLICY_LABEL", "Privacy policy"),
        "policy_label_short": _env("BILLOW_POLICY_LABEL", "Privacy policy"),
        "credit": {
            "label": "Billow Productions",
            "url": _env("BILLOW_LINK_URL", "https://discord.gg/Qz34zJUeR6"),
        },
    }


def _none():
    return {
        "key": "none",
        "name": "Logviewer",
        "site_title": "Logviewer",
        "logo_url": None,
        "logo_class": "",
        "logo_text": "Logviewer",
        "hero_url": None,
        "hero_overlay": "bg-raised",
        "heading_class": "tracking-tight",
        "button_class": "bg-white text-black hover:bg-white/90",
        "home_title": "Logviewer",
        "home_text": "This site is used to display Modmail log entries.",
        "notice": None,
        "policy_url": None,
        "policy_label": None,
        "policy_label_short": None,
        "credit": None,
    }


PRESETS = {"java": _java, "billow": _billow, "none": _none}


def load_brand():
    key = (os.getenv("BRANDING") or "").strip().lower()

    # JAVA_BRANDING=yes from before BRANDING existed still works.
    if not key:
        key = "java" if _truthy(os.getenv("JAVA_BRANDING", "no")) else "none"

    if key not in PRESETS:
        print(f"Unknown BRANDING '{key}', expected one of: {', '.join(PRESETS)}. Using none.")
        key = "none"

    return PRESETS[key]()
