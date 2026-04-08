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

    for enc in ["latin-1", "iso-8859-1", "cp1252", "utf-8"]:
        try:
            content = raw.decode(enc)
            break
        except Exception:
            continue

    sep = ";" if content.count(";") > content.count(",") else ","
    lines = content.splitlines()

    header_idx = next((i for i, l in enumerate(lines) if "Matricule" in l and not l.startswith("%")), None)
    if header_idx is None:
        print("Header introuvable"); return

    print(f"Header: {lines[header_idx]}")
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])), delimiter=sep)
    rows = [{k.strip().strip('"'): v.strip() for k, v in row.items()} for row in reader if row]
    print(f"{len(rows)} lignes, colonnes: {list(rows[0].keys()) if rows else []}")

    info = {}
    enriched = 0
    for row in rows:
        mat = row.get("Matricule", "").strip()
        civ_raw = row.get("Qualité", "").strip()
        nom = row.get("Nom usuel", "").strip().upper()
        prenom = row.get("Prénom usuel", "").strip()
        if not nom or not prenom or not mat:
            continue
        civ = "Mme" if "f" in civ_raw.lower() else "M."
        key_base = f"{nom} {prenom}"
        key = next((k for k in known_names if k.replace("Mme ","").replace("M. ","").strip().upper() == key_base), f"{civ} {key_base}")
        info[key] = {"matricule": mat}
        enriched += 1

    print(f"{enriched} sénateurs·trices enrichi·e·s")
    with open(SENAT_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("Exemples:")
    for n, d in list(info.items())[:3]:
        print(f"  {n} → {d['matricule']}")

if __name__ == "__main__":
    main()
