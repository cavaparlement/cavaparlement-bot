"""
shared/supabase_sync.py — CavaParlement — version finale
Toutes les tables vérifiées le 14/04/2026 :
  - actif n'existe PAS → utiliser date_fin IS NULL
  - mouvements : pas de groupe_sigle → groupe
  - push_events : champs texte uniquement, pas de FK UUID
"""

import os, re, unicodedata, logging
from datetime import date
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

CHAMBRE_DB = {
    "AN": "assemblee", "Senat": "senat", "Europarl": "europarl",
    "assemblee": "assemblee", "senat": "senat", "europarl": "europarl",
}
TYPE_DB = {
    "arrivée": "arrivée", "arrivee": "arrivée", "arrival": "arrivée",
    "départ":  "départ",  "depart":  "départ",  "departure": "départ",
    "transfert": "transfert",
}


def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "https://pmnlfzwfolqeoxaottit.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise EnvironmentError("SUPABASE_SERVICE_KEY manquant")
    return create_client(url, key)


def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    ascii_ = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^a-z0-9 ]", "", ascii_.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# ── LECTURE DU SNAPSHOT ────────────────────────────────────────────────────────

def load_snapshot(chambre_bot: str) -> dict:
    """Snapshot actuel depuis Supabase. Mandats actifs = date_fin IS NULL."""
    chambre = CHAMBRE_DB[chambre_bot]
    db = _client()
    resp = (
        db.table("mandats_collaborateurs")
        .select("elus(nom_complet), collaborateurs(nom_complet)")
        .eq("chambre", chambre)
        .is_("date_fin", "null")
        .execute()
    )
    snapshot = {}
    for row in resp.data:
        elu_nom    = (row.get("elus")          or {}).get("nom_complet", "")
        collab_nom = (row.get("collaborateurs") or {}).get("nom_complet", "")
        if elu_nom and collab_nom:
            snapshot.setdefault(elu_nom, []).append(collab_nom)
    logger.info("Snapshot %s : %d élus, %d collabs",
                chambre, len(snapshot), sum(len(v) for v in snapshot.values()))
    return snapshot


def load_ep_state() -> dict:
    """État Europarl depuis Supabase. Mandats actifs = date_fin IS NULL."""
    db = _client()
    elus_resp = (
        db.table("elus")
        .select("id, ep_id, nom_complet, groupe_label")
        .eq("chambre", "europarl")
        .not_.is_("ep_id", "null")
        .execute()
    )
    if not elus_resp.data:
        return {}
    elu_ids = [e["id"] for e in elus_resp.data]
    mandats_resp = (
        db.table("mandats_collaborateurs")
        .select("elu_id, collaborateurs(nom_complet), notes")
        .eq("chambre", "europarl")
        .is_("date_fin", "null")
        .in_("elu_id", elu_ids)
        .execute()
    )
    assistants_by_elu = {}
    for m in mandats_resp.data:
        eid   = m["elu_id"]
        name  = (m.get("collaborateurs") or {}).get("nom_complet", "")
        atype = m.get("notes") or "Assistant"
        if name:
            assistants_by_elu.setdefault(eid, []).append({"name": name, "type": atype})
    state = {}
    for elu in elus_resp.data:
        ep_id = str(elu["ep_id"])
        state[ep_id] = {
            "name":       elu["nom_complet"],
            "group":      elu.get("groupe_label", ""),
            "assistants": assistants_by_elu.get(elu["id"], []),
        }
    logger.info("EP state Supabase : %d MEPs", len(state))
    return state


# ── PUSH EVENTS — AN / SÉNAT ──────────────────────────────────────────────────

def push_events(events: list, parlementaires_info: dict, chambre_bot: str) -> dict:
    """
    Écrit les mouvements dans Supabase.
    Champs texte UNIQUEMENT — pas de FK UUID (collab_id, elu_id).
    """
    if not events:
        return {"inseres": 0, "doublons": 0, "erreurs": 0}

    chambre = CHAMBRE_DB[chambre_bot]
    db      = _client()
    today   = date.today().isoformat()
    stats   = {"inseres": 0, "doublons": 0, "erreurs": 0}

    def _get_info(nom_elu: str) -> dict:
        """Recherche les infos d'un élu dans parlementaires_info."""
        for key in [
            nom_elu.upper(),
            nom_elu,
            nom_elu.upper().replace("M. ", "").replace("MME ", "").strip(),
        ]:
            if key in parlementaires_info:
                return parlementaires_info[key]
        # Recherche normalisée
        n = _norm(nom_elu)
        for k, v in parlementaires_info.items():
            if _norm(k) == n:
                return v
        return {}

    for ev in events:
        try:
            type_mv = TYPE_DB.get(ev["type"], ev["type"])
            collab  = ev.get("collaborateur", "")

            if type_mv in ("arrivée", "départ"):
                elu_nom      = ev.get("senateur", ev.get("elu", ""))
                elu_from_nom = None
                elu_to_nom   = None
                info         = _get_info(elu_nom)
            elif type_mv == "transfert":
                elu_from_nom = ev.get("from", "")
                elu_to_nom   = ev.get("to", "")
                elu_nom      = elu_to_nom
                info         = _get_info(elu_to_nom)
            else:
                logger.warning("Type inconnu : %s", ev.get("type"))
                stats["erreurs"] += 1
                continue

            # Vérif doublon sur champs texte
            dup = (
                db.table("mouvements").select("id")
                .eq("collaborateur_nom", collab)
                .eq("type", type_mv)
                .eq("chambre", chambre)
                .eq("date", today)
                .limit(1).execute()
            )
            if dup.data:
                stats["doublons"] += 1
                continue

            # Récupérer groupe/dept depuis les infos AN (clés CSV)
            grp   = (info.get("groupe")
                     or info.get("Groupe politique (abrégé)")
                     or "")
            label = (info.get("groupe_label")
                     or info.get("Groupe politique (complet)")
                     or "")
            dept  = (info.get("departement")
                     or info.get("Département")
                     or "")

            db.table("mouvements").insert({
                "chambre":          chambre,
                "type":             type_mv,
                "date":             today,
                "collaborateur_nom": collab,
                "elu_nom":          elu_nom,
                "elu_from_nom":     elu_from_nom,
                "elu_to_nom":       elu_to_nom,
                "groupe":           grp   or None,
                "groupe_label":     label or None,
                "departement":      dept  or None,
                "source":           f"bot_{chambre}",
            }).execute()

            stats["inseres"] += 1

        except Exception as exc:
            logger.error("Erreur event %s : %s", ev, exc)
            stats["erreurs"] += 1

    logger.info("Supabase %s — insérés:%d doublons:%d erreurs:%d",
                chambre, stats["inseres"], stats["doublons"], stats["erreurs"])
    return stats


# ── PUSH EVENTS — EUROPARL ────────────────────────────────────────────────────

def push_ep_events(changes: list) -> dict:
    """Écrit les mouvements Europarl. Champs texte uniquement."""
    if not changes:
        return {"inseres": 0, "doublons": 0, "erreurs": 0}
    db    = _client()
    today = date.today().isoformat()
    stats = {"inseres": 0, "doublons": 0, "erreurs": 0}
    for ch in changes:
        try:
            type_mv = TYPE_DB.get(ch["type"], ch["type"])
            collab  = ch.get("assistant_name", "")
            mep_nom = ch.get("mep_name", "")
            dup = (
                db.table("mouvements").select("id")
                .eq("collaborateur_nom", collab)
                .eq("type", type_mv)
                .eq("chambre", "europarl")
                .eq("date", today)
                .limit(1).execute()
            )
            if dup.data:
                stats["doublons"] += 1
                continue
            db.table("mouvements").insert({
                "chambre":           "europarl",
                "type":              type_mv,
                "date":              today,
                "collaborateur_nom": collab,
                "elu_nom":           mep_nom,
                "groupe_label":      ch.get("mep_group") or None,
                "source":            "bot_europarl",
            }).execute()
            stats["inseres"] += 1
        except Exception as exc:
            logger.error("Erreur EP event %s : %s", ch, exc)
            stats["erreurs"] += 1
    logger.info("Supabase europarl — insérés:%d doublons:%d erreurs:%d",
                stats["inseres"], stats["doublons"], stats["erreurs"])
    return stats

