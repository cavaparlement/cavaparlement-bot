from bots.assemblee.scraper import download_and_parse, save_snapshot, load_snapshot, fetch_deputes_info
from bots.assemblee.publisher import post_events
from bots.senat.diff import compute_diff
from bots.senat.update_history import append_events
from atproto import Client
from datetime import date
from pathlib import Path
import os, json, random

COMPTEUR_FILE = "data/assemblee/compteur_ras.json"
MESSAGES_RAS = [
    "RAS aujourd'hui côté collaborateurs",
    "Silence radio à l'Assemblée aujourd'hui 👀",
    "Pas de mouvement aujourd'hui... pour l'instant",
    "Journée calme au Palais Bourbon 🏛️",
    "Aucun mouvement aujourd'hui à l'Assemblée",
    "Le Palais Bourbon est au calme 😴",
    "Pas de changement dans les cabinets aujourd'hui",
    "Tout est stable du côté des collaborateurs",
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
    handle = os.getenv("BLUESKY_ASSEMBLEE_IDENTIFIER", "")
    password = os.getenv("BLUESKY_ASSEMBLEE_PASSWORD", "")
    today = date.today().strftime("%d/%m/%Y")
    compteur = load_compteur() + 1
    save_compteur(compteur)
    message = random.choice(MESSAGES_RAS)
    compteur_txt = ("1 jour" if compteur == 1 else str(compteur) + " jours") + " sans changement"
    text = "🟡 Ça va l'Assemblée ?\n📅 " + today + " 👉 " + message + "\n📊 " + compteur_txt + "\n\n🤖 Mise à jour automatique #Assemblee"
    client = Client()
    client.login(handle, password)
    client.send_post(text=text)
    print("Post RAS AN envoyé ! (" + compteur_txt + ")")

def run():
    print("Téléchargement des données AN...")
    new_data = download_and_parse()
    total = sum(len(v) for v in new_data.values())
    print(str(len(new_data)) + " députés, " + str(total) + " collaborateurs trouvés")
    print("Récupération infos députés...")
    deputes_info = fetch_deputes_info()
    print(str(len(deputes_info)) + " députés enrichis")
    with open("data/assemblee/deputes_info.json", "w", encoding="utf-8") as f:
        json.dump(deputes_info, f, ensure_ascii=False, indent=2)
    old_data = load_snapshot()
    if not old_data:
        print("Premier run - snapshot sauvegardé, aucun post.")
        save_snapshot(new_data)
        return
    events = compute_diff(old_data, new_data)
    print(str(len(events)) + " changement(s) détecté(s)")
    if events:
        save_compteur(0)
        append_events(events, deputes_info, chambre="assemblee")
        post_events(events, deputes_info)
    else:
        post_ras()
    save_snapshot(new_data)
    print("Done.")

if __name__ == "__main__":
    run()
