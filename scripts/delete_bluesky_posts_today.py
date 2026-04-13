"""
scripts/delete_bluesky_posts_today.py
Supprime TOUS les posts publiés aujourd'hui par le bot AN sur Bluesky.
À lancer une seule fois via GitHub Actions (workflow delete_bluesky.yml).
"""

import os
import time
from datetime import date
from atproto import Client

TODAY = date.today().isoformat()  # "2026-04-13"

BOTS = [
    {
        "handle":   os.getenv("BLUESKY_ASSEMBLEE_IDENTIFIER", ""),
        "password": os.getenv("BLUESKY_ASSEMBLEE_PASSWORD", ""),
        "label":    "CavaAssemblée",
    },
]

def delete_today_posts(handle: str, password: str, label: str):
    if not handle or not password:
        print(f"[{label}] Identifiants manquants — skip")
        return

    client = Client()
    client.login(handle, password)
    did = client.me.did
    print(f"[{label}] Connecté : {handle} ({did})")

    deleted = 0
    cursor = None

    while True:
        # Récupère les posts par page de 100
        params = {"repo": did, "collection": "app.bsky.feed.post", "limit": 100}
        if cursor:
            params["cursor"] = cursor

        resp = client.com.atproto.repo.list_records(params)
        records = resp.records

        if not records:
            break

        for record in records:
            created_at = getattr(record.value, "created_at", "") or ""
            if created_at.startswith(TODAY):
                try:
                    client.com.atproto.repo.delete_record({
                        "repo":       did,
                        "collection": "app.bsky.feed.post",
                        "rkey":       record.uri.split("/")[-1],
                    })
                    deleted += 1
                    print(f"  ✓ Supprimé ({deleted}) : {record.uri}")
                    time.sleep(0.3)  # respecte le rate limit
                except Exception as e:
                    print(f"  ✗ Erreur sur {record.uri} : {e}")

        cursor = getattr(resp, "cursor", None)
        if not cursor:
            break

    print(f"[{label}] Terminé — {deleted} posts supprimés.")


if __name__ == "__main__":
    print(f"Suppression des posts du {TODAY}...\n")
    for bot in BOTS:
        delete_today_posts(bot["handle"], bot["password"], bot["label"])
