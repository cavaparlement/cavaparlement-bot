"""
shared/supabase_sync.py
=======================
Accès Supabase pour tous les bots CavaParlement.

Remplace :
  - load_snapshot() / save_snapshot()  → load_snapshot() / push_events()
  - append_events() / update_history() → push_events()
  - load_state() / save_state()        → load_ep_state() / push_ep_events()

Secrets GitHub Actions requis :
  SUPABASE_URL         https://pmnlfzwfolqeoxaottit.supabase.co
  SUPABASE_SERVICE_KEY <service_role key — à régénérer dans le Dashboard>
"""

import os
import re
import unicodedata
import logging
from datetime import date
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ── IDs table `sources` ───────────────────────────────────────────────────────
SOURCE_ID = {"AN": 1, "Senat": 2, "Europarl": 3}


# ── Connexion ─────────────────────────────────────────────────────────────────
def _client() -> Client:
    url = os.environ.get("SUPABASE_URL", "https://pmnlfzwfolqeoxaottit.supabase.co")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise EnvironmentError("SUPABASE_SERVICE_KEY manquant")
    return create_client(url, key)


# ── Normalisation (miroir de normalize_nom() SQL) ────────────────────────────
def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    ascii_ = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9 ]", "", ascii_.upper()).strip()


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE DU SNAPSHOT (remplace load_snapshot / load_state)
# ─────────────────────────────────────────────────────────────────────────────

def load_snapshot(chambre: str) -> dict:
    """
    Retourne le snapshot actuel depuis Supabase (mandats actifs).

    Format retourné identique aux anciens snapshot.json :
        {"Nom Elu": ["Collab A", "Collab B", ...], ...}

    chambre : "AN" | "Senat"
    """
    db = _client()
    resp = (
        db.table("mandats_collaborateurs")
        .select("elus(nom_complet), collaborateurs(nom_complet)")
        .eq("chambre", chambre)
        .eq("actif", True)
        .execute()
    )
    snapshot = {}
    for row in resp.data:
        elu_nom   = (row.get("elus")   or {}).get("nom_complet", "")
        collab_nom = (row.get("collaborateurs") or {}).get("nom_complet", "")
        if elu_nom and collab_nom:
            snapshot.setdefault(elu_nom, []).append(collab_nom)
    logger.info("Snapshot Supabase %s : %d élus, %d collabs",
                chambre, len(snapshot), sum(len(v) for v in snapshot.values()))
    return snapshot


def load_ep_state() -> dict:
    """
    Retourne l'état Europarl depuis Supabase.

    Format retourné identique à l'ancien state.json :
        {
          "ep_id": {
            "name": "...",
            "group": "...",
            "assistants": [{"name": "...", "type": "..."}, ...]
          }
        }

    La colonne `ep_id` contient l'identifiant numérique EP (ex: "256869"),
    cohérent avec `an_id` (AN) et `matricule` (Sénat).
    """
    db = _client()
    # Récupère les élus EP avec leur ep_id (identifiant numérique EP)
    elus_resp = (
        db.table("elus")
        .select("id, ep_id, nom_complet, groupe_label")
        .eq("chambre", "Europarl")
        .not_.is_("ep_id", "null")
        .execute()
    )
    if not elus_resp.data:
        return {}

    elu_ids = [e["id"] for e in elus_resp.data]
    mandats_resp = (
        db.table("mandats_collaborateurs")
        .select("elu_id, collaborateurs(nom_complet), type_collab")
        .eq("chambre", "Europarl")
        .eq("actif", True)
        .in_("elu_id", elu_ids)
        .execute()
    )

    # Index des assistants par elu_id (interne Supabase)
    assistants_by_elu = {}
    for m in mandats_resp.data:
        eid   = m["elu_id"]
        name  = (m.get("collaborateurs") or {}).get("nom_complet", "")
        atype = m.get("type_collab", "Assistant")
        if name:
            assistants_by_elu.setdefault(eid, []).append({"name": name, "type": atype})

    state = {}
    for elu in elus_resp.data:
        ep_id = str(elu["ep_id"])   # identifiant numérique EP ("256869", "197691", ...)
        state[ep_id] = {
            "name":       elu["nom_complet"],
            "group":      elu.get("groupe_label", ""),
            "assistants": assistants_by_elu.get(elu["id"], []),
        }

    logger.info("EP state Supabase : %d MEPs", len(state))
    return state


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — lookup / upsert collaborateurs et élus
# ─────────────────────────────────────────────────────────────────────────────

def _find_elu_id(db: Client, nom: str, chambre: str) -> Optional[int]:
    norm = _norm(nom)
    resp = (
        db.table("elus")
        .select("id")
        .eq("chambre", chambre)
        .eq("nom_normalise", norm)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["id"]
    # Fallback : match partiel sur le premier mot (nom de famille)
    parts = norm.split()
    if parts:
        resp2 = (
            db.table("elus")
            .select("id")
            .eq("chambre", chambre)
            .ilike("nom_normalise", f"{parts[0]}%")
            .limit(1)
            .execute()
        )
        if resp2.data:
            return resp2.data[0]["id"]
    logger.warning("Élu introuvable : %s (%s)", nom, chambre)
    return None


def _upsert_collab(db: Client, nom: str) -> int:
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


def _open_mandat(db: Client, collab_id: int, elu_id: Optional[int],
                 chambre: str, today: str, type_collab: str = "") -> None:
    db.table("mandats_collaborateurs").upsert(
        {
            "collaborateur_id": collab_id,
            "elu_id":           elu_id,
            "chambre":          chambre,
            "date_debut":       today,
            "actif":            True,
            "confiance":        "bot",
            "type_collab":      type_collab or None,
        },
        on_conflict="collaborateur_id,elu_id,chambre,date_debut",
    ).execute()


def _close_mandat(db: Client, collab_id: int, chambre: str, today: str) -> None:
    resp = (
        db.table("mandats_collaborateurs")
        .select("id")
        .eq("collaborateur_id", collab_id)
        .eq("chambre", chambre)
        .eq("actif", True)
        .limit(1)
        .execute()
    )
    if resp.data:
        db.table("mandats_collaborateurs").update(
            {"actif": False, "date_fin": today}
        ).eq("id", resp.data[0]["id"]).execute()


def _is_duplicate(db: Client, collab_id: int, type_mv: str,
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


# ─────────────────────────────────────────────────────────────────────────────
# ÉCRITURE DES EVENTS (remplace append_events + save_snapshot)
# ─────────────────────────────────────────────────────────────────────────────

def push_events(events: list, parlementaires_info: dict, chambre_bot: str) -> dict:
    """Écrit les mouvements dans Supabase. Utilise uniquement les champs texte (pas de FK UUID)."""
    if not events:
        return {"inseres": 0, "doublons": 0, "erreurs": 0}

    chambre = CHAMBRE_DB[chambre_bot]
    db      = _client()
    today   = date.today().isoformat()
    stats   = {"inseres": 0, "doublons": 0, "erreurs": 0}

    def _get_info(nom_elu: str) -> dict:
        for key in [nom_elu.upper(), nom_elu,
                    nom_elu.upper().replace("M. ", "").replace("MME ", "").strip()]:
            if key in parlementaires_info:
                return parlementaires_info[key]
        n = _norm(nom_elu)
        for k, v in parlementaires_info.items():
            if _norm(k) == n:
                return v
        return {}

    for ev in events:
        try:
            type_mv = TYPE_DB.get(ev["type"], ev["type"])
            collab  = ev["collaborateur"]

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
                logger.warning("Type inconnu : %s", ev["type"])
                stats["erreurs"] += 1
                continue

            # Vérif doublon sur champs texte
            dup = (db.table("mouvements").select("id")
                   .eq("collaborateur_nom", collab).eq("type", type_mv)
                   .eq("chambre", chambre).eq("date", today).limit(1).execute())
            if dup.data:
                stats["doublons"] += 1
                continue

            # Récupérer infos groupe/dept depuis parlementaires_info
            grp   = info.get("groupe") or info.get("Groupe politique (abrégé)") or ""
            label = info.get("groupe_label") or info.get("Groupe politique (complet)") or ""
            dept  = info.get("departement") or info.get("Département") or ""

            db.table("mouvements").insert({
                "chambre":          chambre,
                "type":             type_mv,
                "date":             today,
                "collaborateur_nom": collab,
                "elu_nom":          elu_nom,
                "elu_from_nom":     elu_from_nom,
                "elu_to_nom":       elu_to_nom,
                "groupe":           grp or None,
                "groupe_label":     label or None,
                "departement":      dept or None,
                "source":           f"bot_{chambre}",
            }).execute()

            stats["inseres"] += 1

        except Exception as exc:
            logger.error("Erreur event %s : %s", ev, exc)
            stats["erreurs"] += 1

    logger.info("Supabase %s — insérés:%d doublons:%d erreurs:%d",
                chambre, stats["inseres"], stats["doublons"], stats["erreurs"])
    return stats


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
            collab  = ch["assistant_name"]
            dup = (db.table("mouvements").select("id")
                   .eq("collaborateur_nom", collab).eq("type", type_mv)
                   .eq("chambre", "europarl").eq("date", today).limit(1).execute())
            if dup.data:
                stats["doublons"] += 1
                continue
            db.table("mouvements").insert({
                "chambre":           "europarl",
                "type":              type_mv,
                "date":              today,
                "collaborateur_nom": collab,
                "elu_nom":           ch["mep_name"],
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

