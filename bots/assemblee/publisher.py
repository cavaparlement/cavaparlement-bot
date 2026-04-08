import os, json, requests
from datetime import date
from pathlib import Path
from atproto import Client

HANDLE = os.getenv("BLUESKY_HANDLE_AN", "")
APP_PASSWORD = os.getenv("BLUESKY_PASSWORD_AN", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = "@cavaparlement"
DATES_FILE = "dates_an.json"

GROUPES = {
    "RN":    {"tag": "#RN",    "emoji": "🔵"},
    "NFP":   {"tag": "#NFP",   "emoji": "🌹"},
    "LFI":   {"tag": "#LFI",   "emoji": "🔴"},
    "SOC":   {"tag": "#PS",    "emoji": "🌹"},
    "RE":    {"tag": "#RE",    "emoji": "🟡"},
    "MODEM": {"tag": "#MoDem", "emoji": "🟡"},
    "HOR":   {"tag": "#HOR",   "emoji": "🟠"},
    "LR":    {"tag": "#LR",    "emoji": "🔵"},
    "LIOT":  {"tag": "#LIOT",  "emoji": "🟤"},
    "GDR":   {"tag": "#GDR",   "emoji": "🔴"},
    "ECOLO": {"tag": "#GEST",  "emoji": "🟢"},
    "NI":    {"tag": "",       "emoji": "⚪️"},
}

def get_groupe_info(groupe_sigle):
    if groupe_sigle in GROUPES:
        return GROUPES[groupe_sigle]
    for key, val in GROUPES.items():
        if key.lower() in groupe_sigle.lower():
            return val
    return {"tag": "", "emoji": "⚪️"}

def get_groupe_display(info):
    groupe_sigle = info.get("groupe", "")
    groupe_label = info.get("groupe_label", "")
    dept = info.get("departement", "")
    circo = info.get("circo", "")
    if groupe_label and groupe_sigle:
        txt = groupe_label + " (" + groupe_sigle + ")"
    elif groupe_label:
        txt = groupe_label
    elif groupe_sigle:
        txt = groupe_sigle
    else:
        txt = "N/A"
    if dept:
        txt += " · " + dept
        if circo:
            txt += " · " + circo + "e circ."
    return txt

def load_dates():
    if not Path(DATES_FILE).exists():
        return {}
    with open(DATES_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_dates(dates):
    with open(DATES_FILE, "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False, indent=2)

def fmt_date(date_str):
    try:
        d = date.fromisoformat(date_str)
        return d.strftime("%d/%m/%Y")
    except:
        return date_str

def lookup_depute(dep, deputes_info):
    key = dep.upper().replace("M. ", "").replace("MME ", "").strip()
    if key in deputes_info:
        return deputes_info[key]
    mots = [m for m in key.split() if len(m) > 2]
    for k, v in deputes_info.items():
        if all(m in k for m in mots):
            return v
    return {}

def post_telegram(text):
    if not TELEGRAM_TOKEN:
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": text}, timeout=10)
    except Exception as e:
        print("Erreur Telegram: " + str(e))

def format_post(event, deputes_info, dates):
    collab = event["collaborateur"]
    today_str = date.today().isoformat()

    if event["type"] in ["arrivee", "arrivée"]:
        dep = event["senateur"]
        info = lookup_depute(dep, deputes_info)
        ginfo = get_groupe_info(info.get("groupe", ""))
        groupe_txt = get_groupe_display(info)
        dates[collab] = today_str
        lines = [
            "📥 Arrivée · Assemblée nationale",
            ginfo["emoji"] + " " + collab + " ➡️ Collaborateur/trice de " + dep,
            "🏛️ " + groupe_txt,
            "📅 Depuis : " + fmt_date(today_str),
            "",
            "#Assemblee " + ginfo["tag"],
        ]
        return "\n".join(lines).strip()

    elif event["type"] in ["depart", "départ"]:
        dep = event["senateur"]
        info = lookup_depute(dep, deputes_info)
        ginfo = get_groupe_info(info.get("groupe", ""))
        groupe_txt = get_groupe_display(info)
        date_fin = fmt_date(today_str)
        date_debut = fmt_date(dates.get(collab, "")) if collab in dates else ""
        depuis_txt = ("📅 En poste depuis : " + date_debut + "\n") if date_debut else ""
        dates.pop(collab, None)
        lines = [
            "📤 Départ · Assemblée nationale",
            ginfo["emoji"] + " " + collab + " ❌ Quitte l'équipe de " + dep,
            "🏛️ " + groupe_txt,
            depuis_txt + "📅 Fin : " + date_fin,
            "",
            "#Assemblee " + ginfo["tag"],
        ]
        return "\n".join(lines).strip()

    elif event["type"] == "transfert":
        dep_from = event["from"]
        dep_to = event["to"]
        info_to = lookup_depute(dep_to, deputes_info)
        ginfo = get_groupe_info(info_to.get("groupe", ""))
        groupe_txt = get_groupe_display(info_to)
        dates[collab] = today_str
        lines = [
            "🔁 Changement · Assemblée nationale",
            "🔄 " + collab + " ➡️ Passe de " + dep_from + " à " + dep_to,
            "🏛️ Nouveau groupe : " + groupe_txt,
            "📅 Depuis : " + fmt_date(today_str),
            "",
            "#Assemblee " + ginfo["tag"],
        ]
        return "\n".join(lines).strip()

def post_events(events, deputes_info={}):
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    dates = load_dates()
    for event in events:
        text = format_post(event, deputes_info, dates)
        client.send_post(text=text)
        print("Post Bluesky AN envoyé : " + text[:80] + "...")
        post_telegram(text)
    save_dates(dates)
