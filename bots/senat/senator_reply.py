"""
senator_reply.py
Poste un reply Bluesky avec le @handle du sénateur si disponible.
Compatible Python 3.9+
"""

import unicodedata
from bots.senat.senator_lookup import SENATOR_HANDLES


def _normalize(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def get_senator_handle(nom, prenom):
    # type: (str, str) -> Optional[str]
    key = "{} {}".format(nom.strip().upper(), prenom.strip())
    # Tentative directe
    if key in SENATOR_HANDLES:
        return SENATOR_HANDLES[key]
    # Tentative sans accents
    key_norm = _normalize(key)
    for k, v in SENATOR_HANDLES.items():
        if _normalize(k) == key_norm:
            return v
    return None


def post_senator_reply_bluesky(client, parent_uri, parent_cid, nom, prenom):
    """
    Poste un reply au post principal avec le @handle du sénateur.

    Args:
        client      : votre instance atproto Client (déjà authentifiée)
        parent_uri  : URI du post principal (response.uri)
        parent_cid  : CID du post principal (response.cid)
        nom         : NOM du sénateur en majuscules (ex: "NARASSIGUIN")
        prenom      : Prénom (ex: "Corinne")

    Returns:
        True si reply posté, False sinon
    """
    handle = get_senator_handle(nom, prenom)
    if not handle:
        return False

    try:
        from atproto import Client, models

        handle_clean = handle.lstrip("@")

        # Résolution DID
        resolved = client.resolve_handle(handle_clean)
        did = resolved.did

        text = handle
        byte_end = len(handle.encode("utf-8"))

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

        client.send_post(text=text, reply_to=reply_ref, facets=facets)
        print("[Bluesky] Reply posté : {}".format(handle))
        return True

    except Exception as e:
        print("[Bluesky] Erreur reply : {}".format(e))
        return False
