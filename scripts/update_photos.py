"""
update_photos.py
Détecte les nouveaux élu·e·s dans les snapshots et télécharge leurs photos.
Marque les ancien·ne·s élu·e·s dont le mandat n'est plus effectif.

Usage : python3 scripts/update_photos.py
À intégrer dans le workflow GitHub Actions après chaque run de bot.
"""

import json
import urllib.request
import urllib.error
import time
import unicodedata
import re
from pathlib import Path

# ─── Chemins ─────────────────────────────────────────────────────────────────

DEPUTES_INFO    = Path("data/assemblee/deputes_info.json")
SENATEURS_INFO  = Path("data/senat/senateurs_info.json")
EUROPARL_STATE  = Path("data/europarl/state.json")
SNAPSHOT_AN     = Path("data/assemblee/snapshot.json")
SNAPSHOT_SENAT  = Path("data/senat/snapshot.json")

PHOTOS_AN       = Path("data/photos/assemblee")
PHOTOS_SENAT    = Path("data/photos/senat")
PHOTOS_EP       = Path("data/photos/europarl")

for p in [PHOTOS_AN, PHOTOS_SENAT, PHOTOS_EP]:
    p.mkdir(parents=True, exist_ok=True)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)

def slugify_senat(key: str, matricule: str) -> str:
    key = key.replace("Mme ", "").replace("M. ", "").strip()
    parts = key.split()
    if len(parts) >= 2:
        nom   = re.sub(r"[^a-z0-9_]", "", re.sub(r"[-\s]+", "_",
                unicodedata.normalize("NFD", parts[0]).encode("ascii", "ignore").decode().lower())).strip("_")
        prenom = re.sub(r"[^a-z0-9_]", "", re.sub(r"[-\s]+", "_",
                unicodedata.normalize("NFD", " ".join(parts[1:])).encode("ascii", "ignore").decode().lower())).strip("_")
        return f"{nom}_{prenom}{matricule.lower()}"
    return matricule.lower()

# ─── Assemblée nationale ──────────────────────────────────────────────────────

def update_assemblee():
    print("\n── Assemblée nationale ──")
    deputes_info = load_json(DEPUTES_INFO)
    snapshot     = load_json(SNAPSHOT_AN)
    if not snapshot:
        print("  Snapshot AN introuvable, skipping.")
        return

    snapshot_noms = set(snapshot.keys())
    info_noms     = set(deputes_info.keys())

    # Nouveaux élu·e·s détectés dans le snapshot
    nouveaux = snapshot_noms - info_noms
    if nouveaux:
        print(f"  {len(nouveaux)} nouveau·x élu·e·s détecté·e·s : {list(nouveaux)[:5]}")
        for nom in nouveaux:
            # Tenter de trouver le PA ID via l'API AN (recherche par nom)
            an_id = find_an_id(nom)
            deputes_info[nom] = {"an_id": an_id} if an_id else {}
            if an_id:
                numeric = an_id.replace("PA", "")
                url = f"https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/{numeric}.jpg"
                ok = download(url, PHOTOS_AN / f"{numeric}.jpg")
                print(f"  {'✓' if ok else '✗'} Photo {nom} ({an_id})")
    else:
        print("  Aucun nouvel élu détecté.")

    # Ancien·ne·s élu·e·s (présent·e·s dans info mais plus dans snapshot)
    anciens = info_noms - snapshot_noms
    updated = 0
    for nom in anciens:
        if not deputes_info[nom].get("mandat_clos"):
            deputes_info[nom]["mandat_clos"] = True
            updated += 1
    if updated:
        print(f"  {updated} élu·e·s marqué·e·s comme 'mandat clos'.")

    # Photos manquantes pour les élu·e·s en poste
    manquantes = 0
    for nom in snapshot_noms:
        info = deputes_info.get(nom, {})
        an_id = info.get("an_id", "")
        if not an_id:
            continue
        numeric = an_id.replace("PA", "")
        if not (PHOTOS_AN / f"{numeric}.jpg").exists():
            url = f"https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/{numeric}.jpg"
            if download(url, PHOTOS_AN / f"{numeric}.jpg"):
                manquantes += 1

    if manquantes:
        print(f"  {manquantes} photos manquantes téléchargées.")

    save_json(DEPUTES_INFO, deputes_info)


def find_an_id(nom: str) -> str | None:
    """Tente de trouver le PA ID d'un député via l'API AN."""
    try:
        url = "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_csv_opendata/liste_deputes_libre_office.csv"
        import csv, io
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8-sig")
        sep = ";" if content.count(";") > content.count(",") else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=sep)
        norm_nom = normalize(nom)
        for row in reader:
            prenom = row.get("Prénom", "").strip()
            nom_csv = row.get("Nom", "").strip()
            if normalize(f"{prenom} {nom_csv}") == norm_nom or normalize(f"{nom_csv} {prenom}") == norm_nom:
                return row.get("identifiant", "").strip()
    except Exception:
        pass
    return None


# ─── Sénat ────────────────────────────────────────────────────────────────────

def update_senat():
    print("\n── Sénat ──")
    senateurs_info = load_json(SENATEURS_INFO)
    snapshot       = load_json(SNAPSHOT_SENAT)
    if not snapshot:
        print("  Snapshot Sénat introuvable, skipping.")
        return

    snapshot_noms = set(snapshot.keys())
    info_noms     = set(k for k, v in senateurs_info.items() if v.get("en_exercice"))

    nouveaux = snapshot_noms - info_noms
    if nouveaux:
        print(f"  {len(nouveaux)} nouveau·x sénateur·rice·s : {list(nouveaux)[:5]}")
        for nom in nouveaux:
            # Cherche dans senateurs_info (peut être marqué ANCIEN)
            mat = None
            norm = normalize(nom.replace("Mme ", "").replace("M. ", ""))
            for k, v in senateurs_info.items():
                if normalize(k.replace("Mme ", "").replace("M. ", "")) == norm:
                    v["en_exercice"] = True
                    mat = v.get("matricule")
                    break
            if not mat:
                senateurs_info[nom] = {"en_exercice": True}
                continue
            slug = slugify_senat(nom, mat)
            url  = f"https://www.senat.fr/senimg/{slug}_carre.jpg"
            ok   = download(url, PHOTOS_SENAT / f"{mat}.jpg")
            print(f"  {'✓' if ok else '✗'} Photo {nom}")
    else:
        print("  Aucun nouveau·x sénateur·rice détecté.")

    # Ancien·ne·s
    anciens = 0
    for nom, info in senateurs_info.items():
        norm = normalize(nom.replace("Mme ", "").replace("M. ", ""))
        still_in = any(normalize(k.replace("Mme ", "").replace("M. ", "")) == norm for k in snapshot_noms)
        if info.get("en_exercice") and not still_in:
            info["en_exercice"] = False
            anciens += 1
    if anciens:
        print(f"  {anciens} sénateur·rice·s marqué·e·s comme ancien·ne·s.")

    # Photos manquantes
    manquantes = 0
    for nom in snapshot_noms:
        norm = normalize(nom.replace("Mme ", "").replace("M. ", ""))
        for k, v in senateurs_info.items():
            if normalize(k.replace("Mme ", "").replace("M. ", "")) == norm:
                mat = v.get("matricule")
                if mat and not (PHOTOS_SENAT / f"{mat}.jpg").exists():
                    slug = slugify_senat(k, mat)
                    url  = f"https://www.senat.fr/senimg/{slug}_carre.jpg"
                    if download(url, PHOTOS_SENAT / f"{mat}.jpg"):
                        manquantes += 1
                break

    if manquantes:
        print(f"  {manquantes} photos manquantes téléchargées.")

    save_json(SENATEURS_INFO, senateurs_info)


# ─── Parlement européen ───────────────────────────────────────────────────────

def update_europarl():
    print("\n── Parlement européen ──")
    state = load_json(EUROPARL_STATE)
    if not state:
        print("  state.json introuvable, skipping.")
        return

    manquantes = 0
    for ep_id in state:
        dest = PHOTOS_EP / f"{ep_id}.jpg"
        if not dest.exists():
            url = f"https://www.europarl.europa.eu/mepphoto/{ep_id}.jpg"
            if download(url, dest):
                manquantes += 1
            time.sleep(0.05)

    if manquantes:
        print(f"  {manquantes} nouvelles photos téléchargées.")
    else:
        print("  Toutes les photos sont à jour.")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Mise à jour des photos et des mandats...")
    update_assemblee()
    update_senat()
    update_europarl()
    print("\nTerminé.")
