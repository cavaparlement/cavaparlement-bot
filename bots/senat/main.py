from bots.senat.scraper import download_pdf, parse_pdf, save_snapshot, load_snapshot, fetch_senateurs_info
from bots.senat.diff import compute_diff
from bots.senat.publisher import post_events
from bots.senat.update_history import append_events
from atproto import Client
from datetime import date
from pathlib import Path
import os, json, random

COMPTEUR_FILE = "compteur_ras.json"
MESSAGES_RAS = [
    "RAS aujourd'hui cote collaborateurs",
    "Silence radio au Senat aujourd'hui 👀",
    "Pas de mouvement aujourd'hui... pour l'instant",
    "Journee calme au Senat 🏛️",
    "Aucun mouvement aujourd'hui au Senat",
    "Le Palais du Luxembourg est au calme 😴",
    "Pas de changement dans les cabinets aujourd'hui",
    "Tout est stable du cote des collaborateurs",
]

def load_compteur():
    if not Path(COMPTEUR_FILE).exists():
        return 0
    with open(COMPTEUR_FILE, encoding="utf-8") as f:
        return json.load(f).get("jours", 0)

def save_compteur(n):
    with open(COMPTEUR_FILE, "w", encoding="utf-8") as f:
        json.dump({"jours": n}, f)

def post_ras():
    handle = os.getenv("BLUESKY_HANDLE", "")
    password = os.getenv("BLUESKY_PASSWORD", "")
    today = date.today().strftime("%d/%m/%Y")
    compteur = load_compteur() + 1
    save_compteur(compteur)
    message = random.choice(MESSAGES_RAS)
    compteur_txt = ("1 jour" if compteur == 1 else str(compteur) + " jours") + " sans changement"
    text = "🟡 Ca va Senat ?\n📅 " + today + " 👉 " + message + "\n📊 " + compteur_txt + "\n\n🤖 Mise a jour automatique #Senat"
    client = Client()
    client.login(handle, password)
    client.send_post(text=text)
    print("Post RAS envoye ! (" + compteur_txt + ")")

def run():
    print("Telechargement du PDF...")
    pdf = download_pdf()
    print("Parsing...")
    new_data = parse_pdf(pdf)
    total = sum(len(v) for v in new_data.values())
    print(str(len(new_data)) + " senateurs, " + str(total) + " collaborateurs trouves")
    print("Recuperation infos senateurs...")
    senateurs_info = fetch_senateurs_info()
    print(str(len(senateurs_info)) + " senateurs enrichis")
    with open("senateurs_info.json", "w", encoding="utf-8") as f:
        json.dump(senateurs_info, f, ensure_ascii=False, indent=2)
    old_data = load_snapshot()
    if not old_data:
        print("Premier run - snapshot sauvegarde, aucun post.")
        save_snapshot(new_data)
        return
    events = compute_diff(old_data, new_data)
    print(str(len(events)) + " changement(s) detecte(s)")
    if events:
        save_compteur(0)
        append_events(events, senateurs_info, chambre="senat")
        post_events(events, senateurs_info)
    else:
        post_ras()
    save_snapshot(new_data)
    print("Done.")

if __name__ == "__main__":
    run()
