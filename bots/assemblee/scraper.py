import requests
import json
import csv
import io
from pathlib import Path

AN_CSV_COLLABS = "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/collaborateurs_csv_opendata/liste_collaborateurs_libre_office.csv"
AN_CSV_DEPUTES = "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_csv_opendata/liste_deputes_libre_office.csv"

def fetch_csv(url, delimiter=","):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    content = r.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content), delimiter=delimiter))

def download_and_parse() -> dict:
    result = {}
    try:
        rows = fetch_csv(AN_CSV_COLLABS, delimiter=",")
        print("Colonnes collabs:", list(rows[0].keys()) if rows else "vide")
        for row in rows:
            nom_dep = row.get("Nom du député", "").strip()
            prenom_dep = row.get("Prénom du député", "").strip()
            if not nom_dep:
                continue
            depute = nom_dep + " " + prenom_dep
            nom_col = row.get("Nom du collaborateur", "").strip()
            prenom_col = row.get("Prénom du collaborateur", "").strip()
            if not nom_col:
                continue
            collab = nom_col + " " + prenom_col
            result.setdefault(depute, [])
            if collab not in result[depute]:
                result[depute].append(collab)
    except Exception as e:
        print("Erreur CSV collaborateurs: " + str(e))
    return result

def fetch_deputes_info() -> dict:
    # Charger l'existant pour préserver les mandats clos
    existing = {}
    try:
        with open("data/assemblee/deputes_info.json", encoding="utf-8") as f:
            existing = json.load(f)
    except Exception:
        pass

    info = {}
    try:
        rows = fetch_csv(AN_CSV_DEPUTES, delimiter=",")
        print("Colonnes députés:", list(rows[0].keys()) if rows else "vide")
        for row in rows:
            prenom = row.get("Prénom", "").strip()
            nom    = row.get("Nom", "").strip()
            an_id  = row.get("identifiant", "").strip()
            if not nom:
                continue
            # Clé format "Nom Prénom" (mixte) — identique au snapshot des collabs
            cle = nom + " " + prenom
            info[cle] = {
                "an_id":        an_id,
                "groupe":       row.get("Groupe politique (abrégé)", "").strip(),
                "groupe_label": row.get("Groupe politique (complet)", "").strip(),
                "departement":  row.get("Département", "").strip(),
                "region":       row.get("Région", "").strip(),
                "circo":        row.get("Numéro de circonscription", "").strip(),
            }
    except Exception as e:
        print("Erreur CSV députés: " + str(e))

    # Réinjecter les mandats clos depuis l'existant (ils ne sont plus dans le CSV actifs)
    for k, v in existing.items():
        if v.get("mandat_clos") and k not in info:
            info[k] = v

    print(f"fetch_deputes_info: {len(info)} entrées ({sum(1 for v in info.values() if v.get('groupe_label'))} avec groupe)")
    return info

def save_snapshot(data: dict, path="data/assemblee/snapshot.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_snapshot(path="data/assemblee/snapshot.json") -> dict:
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)
