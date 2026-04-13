"""
shared/supabase_sync.py — CavaParlement
Accès Supabase basé sur le schéma réel (vérifié le 13/04/2026).

Corrections vs version initiale :
  - mandats_collaborateurs : pas de colonne `actif` → actif = date_fin IS NULL
  - chambre en DB : 'assemblee' / 'senat' / 'europarl'  (minuscules, pas 'AN')
  - nom_normalise : lowercase  (ex: 'alexandre allegret pilot')
  - mouvements : colonnes dénormalisées collaborateur_nom, elu_nom,
                 elu_from_id/nom, elu_to_id/nom  (pas elu_precedent_id)
  - type sans accents : 'arrivee' / 'depart' / 'transfert'
  - source_id dans mouvements : UUID → on utilise le champ `source` text
"""

import os
import re
import unicodedata
import logging
from datetime import date
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── Mapping chambre bot → chambre DB ─────────────────────────────────────────
CHAMBRE_DB = {
    "AN":        "assemblee",
    "Senat":     "senat",
    "Europarl":  "europarl",
    "assemblee": "assemblee",
    "senat":     "senat",
    "europarl":  "europarl",
}

# ── Mapping type avec accents → sans accents ─────────────────────────────────
TYPE_DB = {
    "arrivée":   "arrivee",
    "arrivee":   "arrivee",
    "arrival":   "arrivee",
    "départ":    "depart",
    "depart":    "depart",
    "departure": "depart",
    "transfert": "transfert",
}


# ── Connexion ─────────────────────────────────────────────────────────────────
def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "https://pmnlfzwfolqeoxaottit.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise EnvironmentError("SUPABASE_SERVICE_KEY manquant")
    return create_client(url, key)


# ── Normalisation (miroir du SQL : lowercase, sans accents, sans ponctuation) ─
def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    ascii_ = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^a-z0-9 ]", "", ascii_.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE DU SNAPSHOT
# ─────────────────────────────────────────────────────────────────────────────

def load_snapshot(chambre_bot: str) -> dict:
    """
    Retourne le snapshot actuel depuis Supabase (mandats actifs = date_fin IS NULL).
    Format : {"Nom Elu": ["Collab A", "Collab B", ...], ...}
    """
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

    logger.info("Snapshot Supabase %s : %d élus, %d collabs",
                chambre, len(snapshot), sum(len(v) for v in snapshot.values()))
    return snapshot


def load_ep_state() -> dict:
    """
    Retourne l'état Europarl depuis Supabase.
    Format : {"ep_id": {"name": "...", "group": "...", "assistants": [...]}}
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _find_elu_id(db: Client, nom: str, chambre: str) -> Optional[str]:
    # Stratégie 1 : ilike sur nom_complet
    resp = (
        db.table("elus")
        .select("id")
        .eq("chambre", chambre)
        .ilike("nom_complet", nom.strip())
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["id"]

    # Stratégie 2 : tous les mots significatifs dans nom_normalise
    norm = _norm(nom)
    mots = [m for m in norm.split() if len(m) > 2]
    if mots:
        resp2 = (
            db.table("elus")
            .select("id, nom_normalise")
            .eq("chambre", chambre)
            .ilike("nom_normalise", f"%{mots[0]}%")
            .execute()
        )
        for row in resp2.data:
            if all(m in row["nom_normalise"] for m in mots):
                return row["id"]

    logger.warning("Élu introuvable : %s (%s)", nom, chambre)
    return None


def _upsert_collab(db: Client, nom: str) -> str:
    norm = _norm(nom)
    resp = (
        db.table("collaborateurs")
        .select("id")
        .eq("nom_normalise", norm)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["id"]
    ins = (
        db.table("collaborateurs")
        .insert({"nom_complet": nom.strip()})
        .execute()
    )
    return ins.data[0]["id"]


def _is_duplicate(db: Client, collab_id: str, type_mv: str,
                  chambre: str, today: str) -> bool:
    resp = (
        db.table("mouvements")
        .select("id")
        .eq("collaborateur_id", collab_id)
        .eq("type", type_mv)
        .eq("chambre", chambre)
        .eq("date", today)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _open_mandat(db: Client, collab_id: str, elu_id: Optional[str],
                 chambre: str, today: str, notes: str = "") -> None:
    db.table("mandats_collaborateurs").insert({
        "collaborateur_id": collab_id,
        "elu_id":           elu_id,
        "chambre":          chambre,
        "date_debut":       today,
        "confiance":        "bot",
        "notes":            notes or None,
    }).execute()


def _close_mandat(db: Client, collab_id: str, chambre: str, today: str) -> None:
    resp = (
        db.table("mandats_collaborateurs")
        .select("id")
        .eq("collaborateur_id", collab_id)
        .eq("chambre", chambre)
        .is_("date_fin", "null")
        .limit(1)
        .execute()
    )
    if resp.data:
        db.table("mandats_collaborateurs").update(
            {"date_fin": today}
        ).eq("id", resp.data[0]["id"]).execute()


# ─────────────────────────────────────────────────────────────────────────────
# ÉCRITURE DES EVENTS — AN / SÉNAT
# ─────────────────────────────────────────────────────────────────────────────

def push_events(events: list, parlementaires_info: dict, chambre_bot: str) -> dict:
    """
    Pousse les events AN/Sénat vers Supabase.
    chambre_bot : "AN" | "Senat"
    """
    if not events:
        return {"inseres": 0, "doublons": 0, "erreurs": 0}

    chambre = CHAMBRE_DB[chambre_bot]
    db      = _client()
    today   = date.today().isoformat()
    stats   = {"inseres": 0, "doublons": 0, "erreurs": 0}

    def _get_info(nom_elu: str) -> dict:
        key = nom_elu.upper().replace("M. ", "").replace("MME ", "").strip()
        return parlementaires_info.get(key, {})

    for ev in events:
        try:
            type_mv   = TYPE_DB.get(ev["type"], ev["type"])
            collab    = ev["collaborateur"]
            collab_id = _upsert_collab(db, collab)

            if type_mv in ("arrivee", "depart"):
                elu_nom      = ev["senateur"]
                elu_id       = _find_elu_id(db, elu_nom, chambre)
                info         = _get_info(elu_nom)
                elu_from_id  = None
                elu_from_nom = None
                elu_to_id    = None
                elu_to_nom   = None

            elif type_mv == "transfert":
                elu_from_nom = ev["from"]
                elu_to_nom   = ev["to"]
                elu_nom      = elu_to_nom
                elu_id       = _find_elu_id(db, elu_to_nom, chambre)
                elu_from_id  = _find_elu_id(db, elu_from_nom, chambre)
                elu_to_id    = elu_id
                info         = _get_info(elu_to_nom)
            else:
                logger.warning("Type inconnu : %s", ev["type"])
                stats["erreurs"] += 1
                continue

            if _is_duplicate(db, collab_id, type_mv, chambre, today):
                stats["doublons"] += 1
                continue

            db.table("mouvements").insert({
                "chambre":           chambre,
                "type":              type_mv,
                "date":              today,
                "collaborateur_id":  collab_id,
                "collaborateur_nom": collab,
                "elu_id":            elu_id,
                "elu_nom":           elu_nom,
                "elu_from_id":       elu_from_id,
                "elu_from_nom":      elu_from_nom,
                "elu_to_id":         elu_to_id,
                "elu_to_nom":        elu_to_nom,
                "groupe":            info.get("groupe") or None,
                "groupe_label":      info.get("groupe_label") or None,
                "departement":       info.get("departement") or None,
                "source":            f"bot_{chambre}",
            }).execute()

            if type_mv == "arrivee":
                _open_mandat(db, collab_id, elu_id, chambre, today)
            elif type_mv == "depart":
                _close_mandat(db, collab_id, chambre, today)
            elif type_mv == "transfert":
                _close_mandat(db, collab_id, chambre, today)
                _open_mandat(db, collab_id, elu_id, chambre, today)

            stats["inseres"] += 1

        except Exception as exc:
            logger.error("Erreur Supabase event %s : %s", ev, exc)
            stats["erreurs"] += 1

    logger.info("Supabase %s — insérés: %d | doublons: %d | erreurs: %d",
                chambre, stats["inseres"], stats["doublons"], stats["erreurs"])
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# ÉCRITURE DES EVENTS — EUROPARL
# ─────────────────────────────────────────────────────────────────────────────

def push_ep_events(changes: list) -> dict:
    """
    Pousse les changements Europarl vers Supabase.
    changes : [{"type": "arrival"|"departure", "mep_name": str,
                "mep_group": str, "assistant_name": str, "assistant_type": str}]
    """
    if not changes:
        return {"inseres": 0, "doublons": 0, "erreurs": 0}

    db    = _client()
    today = date.today().isoformat()
    stats = {"inseres": 0, "doublons": 0, "erreurs": 0}

    for ch in changes:
        try:
            type_mv   = TYPE_DB.get(ch["type"], ch["type"])
            collab_id = _upsert_collab(db, ch["assistant_name"])
            elu_id    = _find_elu_id(db, ch["mep_name"], "europarl")

            if _is_duplicate(db, collab_id, type_mv, "europarl", today):
                stats["doublons"] += 1
                continue

            db.table("mouvements").insert({
                "chambre":           "europarl",
                "type":              type_mv,
                "date":              today,
                "collaborateur_id":  collab_id,
                "collaborateur_nom": ch["assistant_name"],
                "elu_id":            elu_id,
                "elu_nom":           ch["mep_name"],
                "groupe_label":      ch.get("mep_group") or None,
                "source":            "bot_europarl",
            }).execute()

            if type_mv == "arrivee":
                _open_mandat(db, collab_id, elu_id, "europarl", today,
                             notes=ch.get("assistant_type", ""))
            else:
                _close_mandat(db, collab_id, "europarl", today)

            stats["inseres"] += 1

        except Exception as exc:
            logger.error("Erreur Supabase EP event %s : %s", ch, exc)
            stats["erreurs"] += 1

    logger.info("Supabase europarl — insérés: %d | doublons: %d | erreurs: %d",
                stats["inseres"], stats["doublons"], stats["erreurs"])
    return stats
