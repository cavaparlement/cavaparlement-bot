from bots.assemblee.scraper import download_and_parse, fetch_deputes_info
from bots.assemblee.publisher import post_events
from shared.diff import compute_diff
from shared.supabase_sync import load_snapshot, push_events
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

    print("Chargement snapshot depuis Supabase...")
    old_data = load_snapshot("AN")

    if not old_data:
        print("Premier run (Supabase vide) — initialisation des mandats, aucun post.")
        # Initialise les mandats actifs dans Supabase depuis le scrape actuel
        fake_events = [
            {"type": "arrivée", "collaborateur": collab, "senateur": depute}
            for depute, collabs in new_data.items()
            for collab in collabs
        ]
        push_events(fake_events, deputes_info, "AN")
        return

    events = compute_diff(old_data, new_data)
    print(str(len(events)) + " changement(s) détecté(s)")

    if events:
        save_compteur(0)
        # Bluesky + Telegram (inchangé)
        post_events(events, deputes_info)
        # Supabase : mouvements + mandats (remplace save_snapshot + append_events)
        stats = push_events(events, deputes_info, "AN")
        print(f"Supabase AN — {stats['inseres']} insérés, {stats['doublons']} doublons, {stats['erreurs']} erreurs")
    else:
        post_ras()

    print("Done.")

if __name__ == "__main__":
    run()
