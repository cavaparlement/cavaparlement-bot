import os, json, requests
from datetime import date
from pathlib import Path
from atproto import Client
from bots.senat.senator_lookup import lookup_senator as lookup_senator_info, format_political_line
from bots.senat.senator_reply import post_senator_reply_bluesky

HANDLE = os.getenv("BLUESKY_SENAT_IDENTIFIER", "")
APP_PASSWORD = os.getenv("BLUESKY_SENAT_PASSWORD", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = "@cavaparlement"
DATES_FILE = "data/senat/dates.json"

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

def lookup_senator(sen, senateurs_info):
    key = sen.upper().replace("M. ", "").replace("MME ", "")
    return senateurs_info.get(key, {})

def parse_nom_prenom(sen_str):
    """
    Extrait (NOM, prenom) depuis une chaîne comme "M. CANEVET Michel"
    ou "Mme NARASSIGUIN Corinne".
    Retourne ("", "") si non parsable.
    """
    cleaned = sen_str.replace("M. ", "").replace("Mme ", "").replace("MME ", "").strip()
    parts = cleaned.split()
    nom_parts = [p for p in parts if p == p.upper() and p.isalpha() or "-" in p and p.replace("-","").isupper()]
    prenom_parts = [p for p in parts if p not in nom_parts]
    if nom_parts and prenom_parts:
        return " ".join(nom_parts), " ".join(prenom_parts)
    # Fallback : premier mot = NOM
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return "", ""

def post_telegram(text):
    if not TELEGRAM_TOKEN:
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": text}, timeout=10)
    except Exception as e:
        print("Erreur Telegram: " + str(e))

def format_post(event, senateurs_info, dates):
    collab = event["collaborateur"]
    today_str = date.today().isoformat()

    if event["type"] in ["arrivee", "arrivée"]:
        sen = event["senateur"]
        nom, prenom = parse_nom_prenom(sen)
        info = lookup_senator_info(nom, prenom)  # nouveau lookup

        # Ligne politique depuis senator_lookup
        if info:
            politique = info["emoji"] + " " + info["groupe_court"]
            hashtag = "#Senat " + info["hashtag"]
        else:
            politique = ""
            hashtag = "#Senat"

        dates[collab] = today_str
        lines = [
            "📥 Arrivée · Sénat",
            "🟢 " + collab,
            "➡️ Rejoint l'équipe de " + sen,
        ]
        if politique:
            lines.append(politique)
        lines += [
            "📅 Depuis : " + fmt_date(today_str),
            "",
            hashtag,
        ]
        return "\n".join(lines).strip()

    elif event["type"] in ["depart", "départ"]:
        sen = event["senateur"]
        nom, prenom = parse_nom_prenom(sen)
        info = lookup_senator_info(nom, prenom)  # nouveau lookup

        if info:
            politique = info["emoji"] + " " + info["groupe_court"]
            hashtag = "#Senat " + info["hashtag"]
        else:
            politique = ""
            hashtag = "#Senat"

        date_fin = fmt_date(today_str)
        date_debut = fmt_date(dates.get(collab, "")) if collab in dates else ""
        dates.pop(collab, None)
        lines = [
            "📤 Départ · Sénat",
            "⚪ " + collab,
            "❌ Quitte l'équipe de " + sen,
        ]
        if politique:
            lines.append(politique)
        if date_debut:
            lines.append("📅 En poste depuis : " + date_debut)
        lines += [
            "📅 Fin : " + date_fin,
            "",
            hashtag,
        ]
        return "\n".join(lines).strip()

    elif event["type"] == "transfert":
        sen_from = event["from"]
        sen_to = event["to"]
        nom, prenom = parse_nom_prenom(sen_to)
        info = lookup_senator_info(nom, prenom)  # nouveau lookup

        if info:
            politique = info["emoji"] + " " + info["groupe_court"] + " · " + info["groupe"]
            hashtag = "#Senat " + info["hashtag"]
        else:
            politique = ""
            hashtag = "#Senat"

        dates[collab] = today_str
        lines = [
            "🔁 Changement · Sénat",
            "🔄 " + collab,
            "➡️ Passe de " + sen_from + " à " + sen_to,
        ]
        if politique:
            lines.append(politique)
        lines += [
            "📅 Depuis : " + fmt_date(today_str),
            "",
            hashtag,
        ]
        return "\n".join(lines).strip()

def post_events(events, senateurs_info={}):
    client = Client()
    client.login(HANDLE, APP_PASSWORD)
    dates = load_dates()

    for event in events:
        text = format_post(event, senateurs_info, dates)

        # Post Bluesky principal
        response = client.send_post(text=text)
        print("Post Bluesky envoye : " + text[:80] + "...")

        # Reply Bluesky avec @handle du sénateur si disponible
        sen = event.get("senateur") or event.get("to", "")
        if sen:
            nom, prenom = parse_nom_prenom(sen)
            if nom:
                post_senator_reply_bluesky(client, response.uri, response.cid, nom, prenom)

        # Post Telegram (même texte, pas de reply)
        post_telegram(text)

    save_dates(dates)
