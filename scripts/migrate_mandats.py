"""
scripts/migrate_mandats.py
Remigre les mandats actifs pour les 3 chambres depuis les sources officielles.
Lance via : python -m scripts.migrate_mandats

Secrets requis :
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
"""

import os, json, re, csv, io, time, requests, unicodedata
from supabase import create_client

# ── Client Supabase ───────────────────────────────────────────────────────────
sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

# ── Normalisation ─────────────────────────────────────────────────────────────
def norm(s):
    s = s or ""
    nfd = unicodedata.normalize("NFD", s)
    asc = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", asc.lower()).strip()

# ── Upsert collaborateur ──────────────────────────────────────────────────────
_collab_cache = {}

def get_or_create_collab(nom_complet: str) -> str:
    n = norm(nom_complet)
    if n in _collab_cache:
        return _collab_cache[n]
    r = sb.table("collaborateurs").select("id").eq("nom_normalise", n).limit(1).execute()
    if r.data:
        _collab_cache[n] = r.data[0]["id"]
        return r.data[0]["id"]
    ins = sb.table("collaborateurs").insert({"nom_complet": nom_complet.strip()}).execute()
    _collab_cache[n] = ins.data[0]["id"]
    return _collab_cache[n]

# ── Upsert élu ───────────────────────────────────────────────────────────────
_elu_cache = {}

def find_elu(nom_complet: str, chambre: str):
    key = norm(nom_complet) + "|" + chambre
    if key in _elu_cache:
        return _elu_cache[key]
    n = norm(nom_complet)
    r = sb.table("elus").select("id").eq("chambre", chambre).ilike("nom_complet", nom_complet.strip()).limit(1).execute()
    if r.data:
        _elu_cache[key] = r.data[0]["id"]
        return r.data[0]["id"]
    # Fallback partiel
    parts = n.split()
    if parts:
        r2 = sb.table("elus").select("id, nom_normalise").eq("chambre", chambre)\
            .ilike("nom_normalise", f"%{parts[0]}%").execute()
        for row in r2.data:
            if all(p in row["nom_normalise"] for p in parts):
                _elu_cache[key] = row["id"]
                return row["id"]
    print(f"  ⚠️  Élu introuvable : {nom_complet} ({chambre})")
    _elu_cache[key] = None
    return None

# ── Insert mandat par batch ───────────────────────────────────────────────────
def insert_mandats(batch: list, chambre: str):
    """Insert en ignorant les doublons (upsert sur collab+elu+chambre+date_debut)."""
    if not batch:
        return 0
    # Utiliser upsert avec on_conflict pour ignorer les doublons
    try:
        sb.table("mandats_collaborateurs").upsert(
            batch,
            on_conflict="collaborateur_id,elu_id,chambre,date_debut",
            ignore_duplicates=True,
        ).execute()
        return len(batch)
    except Exception as e:
        print(f"  Erreur batch: {e}")
        # Fallback : insert un par un
        ok = 0
        for row in batch:
            try:
                sb.table("mandats_collaborateurs").insert(row).execute()
                ok += 1
            except:
                pass
        return ok

# ═════════════════════════════════════════════════════════════════════════════
# 1. ASSEMBLÉE NATIONALE
# ═════════════════════════════════════════════════════════════════════════════
def migrate_assemblee():
    print("\n🏛️  Migration Assemblée nationale...")
    url = "https://data.assemblee-nationale.fr/static/openData/repository/17/amo/collaborateurs_csv_opendata/liste_collaborateurs_libre_office.csv"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    print(f"  {len(rows)} lignes CSV")

    # Effacer les anciens mandats assemblee actifs avant de remigrér
    sb.table("mandats_collaborateurs").delete().eq("chambre", "assemblee").is_("date_fin", "null").execute()
    print("  Anciens mandats actifs supprimés")

    batch, total = [], 0
    for row in rows:
        nom_dep  = row.get("Nom du député", "").strip()
        prenom_dep = row.get("Prénom du député", "").strip()
        nom_col  = row.get("Nom du collaborateur", "").strip()
        prenom_col = row.get("Prénom du collaborateur", "").strip()
        if not nom_dep or not nom_col:
            continue
        elu_nom   = f"{nom_dep} {prenom_dep}".strip()
        collab_nom = f"{nom_col} {prenom_col}".strip()

        elu_id    = find_elu(elu_nom, "assemblee")
        collab_id = get_or_create_collab(collab_nom)

        batch.append({
            "collaborateur_id": collab_id,
            "elu_id":           elu_id,
            "chambre":          "assemblee",
            "date_debut":       None,
            "confiance":        "migration",
            "notes":            "Importé depuis snapshot AN",
        })

        if len(batch) >= 100:
            total += insert_mandats(batch, "assemblee")
            batch = []
            print(f"  {total} mandats insérés...", end="\r")

    if batch:
        total += insert_mandats(batch, "assemblee")

    print(f"  ✅ {total} mandats AN insérés")


# ═════════════════════════════════════════════════════════════════════════════
# 2. SÉNAT — depuis snapshot.json du repo
# ═════════════════════════════════════════════════════════════════════════════
def migrate_senat():
    print("\n⚖️  Migration Sénat...")
    url = "https://raw.githubusercontent.com/cavaparlement/cavaparlement-bot/main/data/senat/snapshot.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    snapshot = r.json()
    print(f"  {len(snapshot)} sénateurs dans le snapshot")

    sb.table("mandats_collaborateurs").delete().eq("chambre", "senat").is_("date_fin", "null").execute()
    print("  Anciens mandats actifs supprimés")

    batch, total = [], 0
    for elu_nom, collabs in snapshot.items():
        elu_id = find_elu(elu_nom, "senat")
        for collab_nom in collabs:
            collab_id = get_or_create_collab(collab_nom)
            batch.append({
                "collaborateur_id": collab_id,
                "elu_id":           elu_id,
                "chambre":          "senat",
                "date_debut":       None,
                "confiance":        "migration",
                "notes":            "Importé depuis snapshot Sénat",
            })
            if len(batch) >= 100:
                total += insert_mandats(batch, "senat")
                batch = []
                print(f"  {total} mandats insérés...", end="\r")

    if batch:
        total += insert_mandats(batch, "senat")
    print(f"  ✅ {total} mandats Sénat insérés")


# ═════════════════════════════════════════════════════════════════════════════
# 3. EUROPARL — depuis state.json du repo
# ═════════════════════════════════════════════════════════════════════════════
def migrate_europarl():
    print("\n🇪🇺 Migration Parlement européen...")
    url = "https://raw.githubusercontent.com/cavaparlement/cavaparlement-bot/main/data/europarl/state.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    state = r.json()
    print(f"  {len(state)} MEPs dans le state")

    sb.table("mandats_collaborateurs").delete().eq("chambre", "europarl").is_("date_fin", "null").execute()
    print("  Anciens mandats actifs supprimés")

    batch, total = [], 0
    for mep_id, info in state.items():
        mep_nom    = info.get("name", "")
        assistants = info.get("assistants", [])
        elu_id     = find_elu(mep_nom, "europarl")

        for assistant in assistants:
            collab_nom = assistant.get("name", "").strip()
            atype      = assistant.get("type", "")
            if not collab_nom:
                continue
            collab_id = get_or_create_collab(collab_nom)
            batch.append({
                "collaborateur_id": collab_id,
                "elu_id":           elu_id,
                "chambre":          "europarl",
                "date_debut":       None,
                "confiance":        "migration",
                "notes":            atype or "Importé depuis state EP",
            })
            if len(batch) >= 100:
                total += insert_mandats(batch, "europarl")
                batch = []
                print(f"  {total} mandats insérés...", end="\r")

    if batch:
        total += insert_mandats(batch, "europarl")
    print(f"  ✅ {total} mandats EP insérés")


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    migrate_assemblee()
    migrate_senat()
    migrate_europarl()

    # Résumé final
    r = sb.table("mandats_collaborateurs")\
        .select("chambre", count="exact")\
        .is_("date_fin", "null")\
        .execute()
    print("\n📊 Résumé final :")
    total_query = """
SELECT chambre, count(*) 
FROM mandats_collaborateurs 
WHERE date_fin IS NULL 
GROUP BY chambre
"""
    # Affichage simple
    for ch in ["assemblee", "senat", "europarl"]:
        n = sb.table("mandats_collaborateurs")\
            .select("id", count="exact", head=True)\
            .eq("chambre", ch).is_("date_fin", "null").execute()
        print(f"  {ch}: {n.count} mandats actifs")
    print("\n✅ Migration terminée")

