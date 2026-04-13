"""
scripts/debug_schema.py
Affiche les colonnes réelles des tables Supabase.
Lancer une fois : python -m scripts.debug_schema
"""
import os
from supabase import create_client

db = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

for table in ["mandats_collaborateurs", "elus", "mouvements", "collaborateurs"]:
    print(f"\n=== {table} ===")
    try:
        resp = db.table(table).select("*").limit(1).execute()
        if resp.data:
            print("Colonnes :", list(resp.data[0].keys()))
            print("Exemple  :", resp.data[0])
        else:
            print("(table vide)")
    except Exception as e:
        print("Erreur :", e)
