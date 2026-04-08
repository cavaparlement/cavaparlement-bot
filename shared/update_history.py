import json
from pathlib import Path
from datetime import date

HISTORY_FILE = "data/unified/history.json"


def load_history():
    if not Path(HISTORY_FILE).exists():
        return []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    Path(HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def append_events(events, parlementaires_info, chambre="senat"):
    history = load_history()
    today = date.today().isoformat()
    for event in events:
        entry = {
            "date": today,
            "chambre": chambre,
            "type": event["type"],
            "collaborateur": event["collaborateur"],
        }
        if event["type"] in ["arrivee", "arrivée", "depart", "départ"]:
            sen = event["senateur"]
            key = sen.upper().replace("M. ", "").replace("MME ", "")
            info = parlementaires_info.get(key, {})
            entry["parlementaire"] = sen
            entry["groupe"] = info.get("groupe", "")
            entry["groupe_label"] = info.get("groupe_label", "")
            entry["departement"] = info.get("departement", "")
        elif event["type"] == "transfert":
            key_to = event["to"].upper().replace("M. ", "").replace("MME ", "")
            info = parlementaires_info.get(key_to, {})
            entry["parlementaire_from"] = event["from"]
            entry["parlementaire_to"] = event["to"]
            entry["groupe"] = info.get("groupe", "")
            entry["groupe_label"] = info.get("groupe_label", "")
            entry["departement"] = info.get("departement", "")
        history.append(entry)
    save_history(history)
