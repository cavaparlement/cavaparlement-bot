"""
shared/bluesky_lookup.py
Lookup unifié des handles Bluesky pour les 3 chambres.
Lit data/bluesky_handles.json (généré depuis les CSV).
Compatible Python 3.9+
"""

import json
import unicodedata
import re
from pathlib import Path
from typing import Optional

HANDLES_FILE = Path("data/bluesky_handles.json")
_cache: dict = {}


def _load() -> dict:
    global _cache
    if not _cache and HANDLES_FILE.exists():
        with open(HANDLES_FILE, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z\s]", "", s).strip()


def get_handle(nom: str, chambre: Optional[str] = None) -> Optional[str]:
    """
    Cherche le handle Bluesky d'un parlementaire par son nom.

    Args:
        nom     : nom tel qu'il apparaît dans les données du bot
                  (ex: "Guiraud David", "M. JADOT Yannick", "Raphaël Glucksmann")
        chambre : "assemblee" | "senat" | "europarl" (optionnel, pour filtrer)

    Returns:
        Handle sans @ (ex: "davidguiraud.bsky.social") ou None
    """
    handles = _load()
    if not handles:
        return None

    # Nettoie les civilités et normalise
    clean = nom.replace("M. ", "").replace("Mme ", "").replace("MME ", "").strip()
    norm = _normalize(clean)

    # 1. Correspondance exacte sur la clé normalisée
    if norm in handles:
        entry = handles[norm]
        if chambre is None or entry.get("chambre") == chambre:
            return entry["handle"]

    # 2. Correspondance partielle (2+ mots en commun)
    parts = set(norm.split())
    best_handle = None
    best_score = 0
    for key, entry in handles.items():
        if chambre and entry.get("chambre") != chambre:
            continue
        key_parts = set(key.split())
        score = len(parts & key_parts)
        if score >= 2 and score > best_score:
            best_score = score
            best_handle = entry["handle"]

    return best_handle


def post_reply_with_mention(client, parent_uri: str, parent_cid: str, nom: str, chambre: Optional[str] = None) -> bool:
    """
    Poste un reply avec une vraie mention AT Protocol cliquable.

    Args:
        client      : instance atproto Client authentifiée
        parent_uri  : URI du post principal
        parent_cid  : CID du post principal
        nom         : nom du parlementaire
        chambre     : "assemblee" | "senat" | "europarl"

    Returns:
        True si reply posté, False sinon
    """
    handle = get_handle(nom, chambre)
    if not handle:
        return False

    try:
        from atproto import models

        handle_clean = handle.lstrip("@")
        resolved = client.resolve_handle(handle_clean)
        did = resolved.did

        mention_text = f"@{handle_clean}"
        byte_end = len(mention_text.encode("utf-8"))

        reply_ref = models.AppBskyFeedPost.ReplyRef(
            root=models.ComAtprotoRepoStrongRef.Main(uri=parent_uri, cid=parent_cid),
            parent=models.ComAtprotoRepoStrongRef.Main(uri=parent_uri, cid=parent_cid),
        )
        facets = [
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=0, byte_end=byte_end),
                features=[models.AppBskyRichtextFacet.Mention(did=did)],
            )
        ]

        client.send_post(text=mention_text, reply_to=reply_ref, facets=facets)
        print(f"  ✓ Reply mention : @{handle_clean}")
        return True

    except Exception as e:
        print(f"  ✗ Reply mention @{handle_clean} : {e}")
        return False
