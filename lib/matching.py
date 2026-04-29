"""Logique de matching cross-chambre des collaborateurs.

Règle (validée avec Théo) :
  - 0 homonyme (même nom_normalise + prenom_normalise) → CREATE
  - target_famille_code is NULL (NI/inconnu) → REVIEW (même si 0 homonyme,
    on flag pour validation manuelle)
  - homonymes existent + au moins 1 avec même famille politique du dernier
    mandat :
      * 1 candidat exact → REUSE
      * 2+ candidats → REVIEW (cas rare, deux personnes même nom même famille)
  - homonymes existent mais aucun avec même famille → CREATE
    (deux personnes différentes selon la règle de Théo)
"""

from __future__ import annotations

from datetime import date
from typing import Any

ACTION_CREATE = "create"
ACTION_REUSE = "reuse"
ACTION_REVIEW = "review"

REASON_NULL_FAMILY = "null_family"
REASON_MULTIPLE_SAME_FAMILY = "multiple_same_family"


def find_or_create_collab_action(
    sb,
    *,
    nom_normalise: str,
    prenom_normalise: str,
    target_famille_code: str | None,
) -> dict[str, Any]:
    """Détermine l'action à effectuer pour un assistant détecté.

    Args:
        sb: client Supabase
        nom_normalise: nom normalisé via normalize_for_matching()
        prenom_normalise: prénom normalisé idem
        target_famille_code: code de la famille politique du nouvel élu cible
            (None si inconnu / NI)

    Returns:
        dict avec :
          - action: 'create' | 'reuse' | 'review'
          - collab_id: uuid si action='reuse', sinon None
          - candidates: liste d'uuid si action='review', sinon None
          - reason: code raison si action='review', sinon None
    """
    # 1. Trouver tous les homonymes canoniques (non fusionnés)
    homonyms_res = sb.table("collaborateurs") \
        .select("id") \
        .eq("nom_normalise", nom_normalise) \
        .eq("prenom_normalise", prenom_normalise) \
        .is_("merged_into_id", "null") \
        .execute()

    homonym_ids = [h["id"] for h in (homonyms_res.data or [])]

    # 2. Si famille cible inconnue (NI/NULL) → review systématique seulement
    #    s'il y a des homonymes (sinon créer simple)
    if not target_famille_code:
        if homonym_ids:
            return {
                "action": ACTION_REVIEW,
                "collab_id": None,
                "candidates": homonym_ids,
                "reason": REASON_NULL_FAMILY,
            }
        return {"action": ACTION_CREATE, "collab_id": None,
                "candidates": None, "reason": None}

    # 3. Pas d'homonyme du tout → simple create
    if not homonym_ids:
        return {"action": ACTION_CREATE, "collab_id": None,
                "candidates": None, "reason": None}

    # 4. Pour chaque homonyme : famille politique de son dernier mandat
    matching = []
    for collab_id in homonym_ids:
        last_famille = _get_last_mandat_famille(sb, collab_id)
        if last_famille == target_famille_code:
            matching.append(collab_id)

    if not matching:
        # Homonymes existent mais aucun avec même famille → c'est une autre personne
        return {"action": ACTION_CREATE, "collab_id": None,
                "candidates": None, "reason": None}

    if len(matching) == 1:
        return {"action": ACTION_REUSE, "collab_id": matching[0],
                "candidates": None, "reason": None}

    return {"action": ACTION_REVIEW, "collab_id": None,
            "candidates": matching, "reason": REASON_MULTIPLE_SAME_FAMILY}


def _get_last_mandat_famille(sb, collab_id: str) -> str | None:
    """Famille politique du dernier mandat (ouvert ou clos) d'un collab.

    'Dernier' = celui avec la plus grande `date_debut`.
    Famille = celle du groupe de l'élu pendant la période du mandat collab.
    Retourne None si pas de mandat, ou si le groupe n'a pas de famille (NI).
    """
    # 1. Récupérer le dernier mandat collab
    last_mc_res = sb.table("mandats_collaborateurs") \
        .select("elu_id, date_debut, date_fin") \
        .eq("collab_id", collab_id) \
        .order("date_debut", desc=True) \
        .limit(1) \
        .execute()

    if not last_mc_res.data:
        return None

    mc = last_mc_res.data[0]
    elu_id = mc["elu_id"]
    ref_date = mc.get("date_fin") or date.today().isoformat()

    # 2. Tous les mandats de l'élu (en pratique 1 ou 2), filtre côté Python
    elu_mandats_res = sb.table("mandats_elus") \
        .select("groupe_id, date_debut, date_fin") \
        .eq("elu_id", elu_id) \
        .execute()

    matching_me = None
    for me in (elu_mandats_res.data or []):
        deb = me.get("date_debut") or "0000-00-00"
        fin = me.get("date_fin")
        if deb <= ref_date and (fin is None or fin >= ref_date):
            matching_me = me
            break

    if not matching_me or not matching_me.get("groupe_id"):
        return None

    # 3. Famille du groupe
    groupe_res = sb.table("groupes_politiques") \
        .select("famille_id") \
        .eq("id", matching_me["groupe_id"]) \
        .limit(1) \
        .execute()

    if not groupe_res.data or not groupe_res.data[0].get("famille_id"):
        return None  # Groupe sans famille (NI, etc.)

    famille_res = sb.table("familles_politiques") \
        .select("code") \
        .eq("id", groupe_res.data[0]["famille_id"]) \
        .limit(1) \
        .execute()

    if not famille_res.data:
        return None
    return famille_res.data[0].get("code")


def insert_match_candidate(
    sb,
    *,
    nom: str,
    prenom: str,
    elu_target_id: str,
    candidate_collab_ids: list[str],
    reason: str,
    scrape_run_id: str,
    dry_run: bool,
) -> None:
    """Insère un cas ambigu dans collab_match_candidates pour review manuelle."""
    payload = {
        "scrape_run_id": scrape_run_id,
        "nom": nom,
        "prenom": prenom,
        "elu_target_id": elu_target_id,
        "candidate_collab_ids": candidate_collab_ids,
        "candidate_reason": reason,
        "status": "needs_review",
    }
    if dry_run:
        return
    sb.table("collab_match_candidates").insert(payload).execute()
