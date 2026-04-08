"""
enrich_assemblee.py — corrigé
Colonnes réelles du CSV AN : identifiant, Prénom, Nom, Région, Département, ...

Usage : python3 scripts/enrich_assemblee.py
"""

import json, csv, io, urllib.request
from pathlib import Path

AN_CSV_URL = "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_csv_opendata/liste_deputes_libre_office.csv"
DEPUTES_INFO_PATH = Path("data/assemblee/deputes_info.json")


def main():
    if not DEPUTES_INFO_PATH.exists():
        print(f"Fichier introuvable : {DEPUTES_INFO_PATH}")
        return

    with open(DEPUTES_INFO_PATH, encoding="utf-8") as f:
        deputes_info = json.load(f)

    print(f"{len(deputes_info)} député·e·s dans deputes_info.json")

    req = urllib.request.Request(AN_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8-sig")

    sep = ";" if content.count(";") > content.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    rows = list(reader)

    print(f"Colonnes : {list(rows[0].keys()) if rows else '(vide)'}")

    # Colonnes réelles : identifiant, Prénom, Nom
    id_map: dict[str, str] = {}
    for row in rows:
        uid = row.get("identifiant", "").strip()
        prenom = row.get("Prénom", row.get("prenom", "")).strip()
        nom = row.get("Nom", row.get("nom", "")).strip()
        if uid and prenom and nom:
            id_map[f"{prenom} {nom}"] = uid

    print(f"{len(id_map)} identifiants extraits")

    enriched = 0
    for nom_site in deputes_info:
        if "an_id" in deputes_info[nom_site]:
            continue
        if nom_site in id_map:
            deputes_info[nom_site]["an_id"] = id_map[nom_site]
            enriched += 1
            continue
        # Correspondance approximative
        parts_site = set(nom_site.lower().split())
        for key, uid in id_map.items():
            parts_key = set(key.lower().split())
            if len(parts_site & parts_key) >= 2:
                deputes_info[nom_site]["an_id"] = uid
                enriched += 1
                break

    print(f"{enriched} député·e·s enrichi·e·s")

    with open(DEPUTES_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(deputes_info, f, ensure_ascii=False, indent=2)

    examples = [(n, d["an_id"]) for n, d in deputes_info.items() if "an_id" in d][:5]
    print("\nExemples :")
    for nom, an_id in examples:
        numeric = an_id.replace("PA", "")
        print(f"  {nom} → {an_id} → photo: /dyn/static/tribun/photos/17/{numeric}.jpg")


if __name__ == "__main__":
    main()
