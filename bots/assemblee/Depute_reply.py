"""
depute_reply.py
Poste un reply Bluesky avec le @handle du député/de la députée si disponible.
Compatible Python 3.9+
"""

from bots.assemblee.depute_lookup import get_depute_handle


def post_depute_reply_bluesky(client, parent_uri, parent_cid, parlementaire):
    """
    Poste un reply au post principal avec le @handle du député.

    Args:
        client        : instance atproto Client (déjà authentifiée)
        parent_uri    : URI du post principal (response.uri)
        parent_cid    : CID du post principal (response.cid)
        parlementaire : nom complet tel qu'il apparaît dans history.json
                        (ex: "Soudais Ersilia", "Cernon Bérenger")

    Returns:
        True si reply posté, False sinon
    """
    handle = get_depute_handle(parlementaire)
    if not handle:
        return False

    try:
        from atproto import models

        handle_clean = handle.lstrip("@")
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
