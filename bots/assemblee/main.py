from bots.assemblee.scraper import download_and_parse, fetch_deputes_info
from bots.assemblee.publisher import post_events
from shared.diff import compute_diff
from shared.supabase_sync import load_snapshot, push_events
from atproto import Client
from datetime import date
from pathlib import Path
import os, json, random, unicodedata, re

COMPTEUR_FILE = "data/assemblee/compteur_ras.json"
MAX_EVENTS_PAR_RUN = 30

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


def _norm_key(s: str) -> str:
    """Normalise un nom pour comparaison : minuscules, sans accents, sans ponctuation."""
    nfd = unicodedata.normalize("NFD", s or "")
    ascii_ = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^a-z0-9 ]", "", ascii_.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_snapshot(snapshot: dict) -> dict:
    """
    Normalise les clés (élus) ET valeurs (collabs) du snapshot Supabase
    pour qu'elles soient comparables aux données du scraper CSV.
    Retourne {norm_elu: [norm_collab, ...]}
    """
    normalized = {}
    for elu, collabs in snapshot.items():
        key = _norm_key(elu)
        normalized[key] = [_norm_key(c) for c in collabs]
    return normalized


def normalize_scraped(data: dict) -> dict:
    """Normalise les clés ET valeurs des données scraper pour la comparaison."""
    normalized = {}
    for elu, collabs in data.items():
        key = _norm_key(elu)
        normalized[key] = [_norm_key(c) for c in collabs]
    return normalized


def run():
    print("Téléchargement des données AN...")
    new_data = download_and_parse()
    total = sum(len(v) for v in new_data.values())
    print(f"{len(new_data)} députés, {total} collaborateurs trouvés")

    print("Récupération infos députés...")
    deputes_info = fetch_deputes_info()
    print(f"{len(deputes_info)} députés enrichis")

    print("Chargement snapshot depuis Supabase...")
    old_data_raw = load_snapshot("AN")
    print(f"Snapshot : {len(old_data_raw)} élus, {sum(len(v) for v in old_data_raw.values())} collabs")

    if not old_data_raw:
        print("Snapshot vide — initialisation des mandats dans Supabase, aucun post.")
        fake_events = [
            {"type": "arrivée", "collaborateur": collab, "senateur": depute}
            for depute, collabs in new_data.items()
            for collab in collabs
        ]
        push_events(fake_events, deputes_info, "AN")
        return

    # ── Normalisation des deux côtés pour comparaison ─────────────────────────
    old_norm = normalize_snapshot(old_data_raw)
    new_norm = normalize_scraped(new_data)

    # Diff sur les versions normalisées (clés/valeurs comparables)
    events_norm = compute_diff(old_norm, new_norm)
    print(f"{len(events_norm)} changement(s) détecté(s) (après normalisation)")

    # ── GARDE-FOU ─────────────────────────────────────────────────────────────
    if len(events_norm) > MAX_EVENTS_PAR_RUN:
        print(f"🚨 ABORT : {len(events_norm)} events — seuil max {MAX_EVENTS_PAR_RUN}.")
        print("Snapshot désynchronisé ? Aucun post envoyé.")
        for ev in events_norm[:5]:
            print(" ", ev)
        return
    # ─────────────────────────────────────────────────────────────────────────

    if events_norm:
        # Reconstruire les events avec les vrais noms du scraper (pour les posts)
        # On remappe norm_elu → vrai nom elu dans new_data
        norm_to_real_elu = {_norm_key(k): k for k in new_data}
        norm_to_real_collab = {
            _norm_key(c): c
            for collabs in new_data.values()
            for c in collabs
        }

        events_real = []
        for ev in events_norm:
            real_ev = dict(ev)
            real_ev["collaborateur"] = norm_to_real_collab.get(ev["collaborateur"], ev["collaborateur"])
            if ev["type"] in ("arrivée", "départ"):
                real_ev["senateur"] = norm_to_real_elu.get(ev["senateur"], ev["senateur"])
            elif ev["type"] == "transfert":
                real_ev["from"] = norm_to_real_elu.get(ev.get("from", ""), ev.get("from", ""))
                real_ev["to"]   = norm_to_real_elu.get(ev.get("to", ""), ev.get("to", ""))
            events_real.append(real_ev)

        save_compteur(0)
        post_events(events_real, deputes_info)
        stats = push_events(events_real, deputes_info, "AN")
        print(f"Supabase AN — {stats['inseres']} insérés, {stats['doublons']} doublons, {stats['erreurs']} erreurs")
    else:
        post_ras()

    print("Done.")

if __name__ == "__main__":
    run()
