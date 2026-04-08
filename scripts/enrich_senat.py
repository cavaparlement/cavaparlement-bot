import json, csv, io, urllib.request
from pathlib import Path

SENAT_INFO_PATH = Path("data/senat/senateurs_info.json")
HISTORY_PATH = Path("data/senat/history.json")
URL = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"

def main():
    known_names = set()
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)
        for m in history:
            if m.get("chambre") == "senat" and m.get("parlementaire"):
                known_names.add(m["parlementaire"])

    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    content = raw.decode("latin-1")
    lines = content.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if "Matricule" in l and not l.startswith("%"))
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])), delimiter=",")
    rows = list(reader)
    print(f"{len(rows)} lignes")

    info = {}
    en_exercice = 0
    for row in rows:
        mat = row.get("Matricule", "").strip()
        civ_raw = row.get("Qualité", "").strip()
        nom = row.get("Nom usuel", "").strip().upper()
        prenom = row.get("Prénom usuel", "").strip()
        groupe = row.get("Groupe politique", "").strip()
        circo = row.get("Circonscription", "").strip()
        etat = row.get("État", "").strip()

        if not nom or not prenom or not mat:
            continue

        civ = "Mme" if civ_raw.lower() in ["mme", "mme."] else "M."
        key_base = f"{nom} {prenom}"
        key = next((k for k in known_names if k.replace("Mme ","").replace("M. ","").strip().upper() == key_base), f"{civ} {key_base}")
        info[key] = {
            "matricule": mat,
            "groupe_label": groupe,
            "departement": circo,
            "en_exercice": etat != "ANCIEN"
        }
        if etat != "ANCIEN":
            en_exercice += 1

    print(f"{len(info)} total, {en_exercice} en exercice")
    with open(SENAT_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    examples = [(n, d) for n, d in info.items() if d.get("en_exercice") and d.get("matricule")][:5]
    print("\nExemples en exercice :")
    for nom, d in examples:
        print(f"  {nom} | {d.get('groupe_label','')} | {d.get('departement','')}")

if __name__ == "__main__":
    main()
