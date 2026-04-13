"""
CavaEuroparl - Bot Bluesky + Telegram suivant les mouvements de collaborateurs
des eurodéputés français au Parlement européen.

Source MEPs  : EP Open Data API (data.europarl.europa.eu/api/v2)
Source staff : EP website (europarl.europa.eu/meps/en/assistants)
"""

import json
import os
import sys
import time
import re

import requests
from bs4 import BeautifulSoup
from atproto import Client
from shared.utils import make_session, post_telegram
from shared.political_mapping import (
    EP_GROUP_LABELS, EP_GROUP_EMOJIS,
    EP_TYPE_EMOJIS, EP_TYPE_LABELS_FR,
    format_ep_group,
)
from shared.supabase_sync import load_ep_state, push_ep_events
from bots.europarl.mep_lookup import get_mep_handle

# ─── Configuration ────────────────────────────────────────────────────────────

BLUESKY_HANDLE   = "pe.cavaparlement.eu"
BLUESKY_PASSWORD = os.environ.get("BLUESKY_EUROPARL_PASSWORD")
TELEGRAM_CHANNEL = "@cavaparlement"

STATE_FILE   = "data/europarl/state.json"
EP_SITE_BASE = "https://www.europarl.europa.eu"

HEADERS = {
    "User-Agent": "CavaEuroparl/1.0 (@cavaeuroparl.bsky.social) - Civic transparency bot",
    "Accept": "text/html,application/xhtml+xml",
}

SESSION  = make_session()

# ─── Hashtags Bluesky ─────────────────────────────────────────────────────────

GROUP_HASHTAGS = {
    "Renew Europe Group":                                            "#RenewEurope #RenewEU",
    "European People's Party Group":                                 "#EPP #PPE",
    "Group of the Progressive Alliance of Socialists and Democrats": "#SND #SocialistsAndDemocrats",
    "European Conservatives and Reformists Group":                   "#ECR #ECRGroup",
    "The Greens–European Free Alliance":                             "#GreensEFA #VertsALE",
    "The Left group in the European Parliament":                     "#TheLeft #GUE",
    "Patriots for Europe Group":                                     "#PatriotsForEurope #PfE",
    "Europe of Sovereign Nations Group":                             "#ESN #SovereignNations",
    "Non-attached Members":                                          "",
}

FIXED_TAGS = "#ParlementEuropéen #UE"


def build_bluesky_post(body: str, group_key: str) -> str:
    """
    Assemble le post Bluesky avec hashtags groupe + tags fixes.
    Troncature progressive si > 300 graphèmes :
      1. Corps + hashtags groupe + tags fixes
      2. Corps + tags fixes seulement
      3. Corps seul (tronqué si nécessaire)
    """
    group_tags = GROUP_HASHTAGS.get(group_key, "")

    tags_full    = f"{group_tags} {FIXED_TAGS}".strip()
    tags_reduced = FIXED_TAGS

    full = f"{body}\n\n{tags_full}".strip()
    if len(full) <= 300:
        return full

    reduced = f"{body}\n\n{tags_reduced}".strip()
    if len(reduced) <= 300:
        return reduced

    if len(body) > 300:
        return body[:297] + "[…]"
    return body


# ─── Récupération des eurodéputés français ────────────────────────────────────

def get_french_meps() -> dict:
    """
    Récupère les eurodéputés français depuis la page de recherche EP filtrée sur FR.
    Structure : div.es_member-list-item[id="member-block-{id}"]
    """
    print("-> Récupération des eurodéputés français (search EP)...")
    url    = f"{EP_SITE_BASE}/meps/en/search/advanced"
    params = {"countryCode": "FR", "leg": "10"}
    for attempt in range(1, 4):
        try:
            resp = SESSION.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 3:
                print(f"  [tentative {attempt}/3] : {e} — retry dans {10 * attempt}s")
                time.sleep(10 * attempt)
            else:
                raise

    soup = BeautifulSoup(resp.text, "html.parser")
    meps = {}

    for card in soup.select("div.es_member-list-item[id^='member-block-']"):
        mep_id   = card["id"].replace("member-block-", "")
        name_el  = card.select_one("div.es_title-h4")
        group_el = card.select_one("span.sln-additional-info")
        mep_name  = name_el.get_text(strip=True)  if name_el  else f"MEP#{mep_id}"
        group_key = group_el.get_text(strip=True) if group_el else ""
        meps[mep_id] = {"name": mep_name, "group": group_key}

    print(f"  {len(meps)} eurodéputés français trouvés")
    return meps


# ─── Récupération des assistants ──────────────────────────────────────────────

def _parse_mep_assistants_page(soup: BeautifulSoup) -> list:
    """
    Parse la page /assistants d'un MEP individuel.
    Structure EP : div.erpl_type-assistants > h4 (type) + span.erpl_assistant (noms)
    """
    results = []
    for section in soup.select("div.erpl_type-assistants"):
        type_el   = section.select_one("h4.es_title-h4")
        type_text = type_el.get_text(strip=True) if type_el else "Assistant"
        for item in section.select("span.erpl_assistant"):
            name = item.get_text(strip=True)
            if name:
                results.append({"name": name, "type": type_text})
    return results


def get_assistants_for_mep(mep_id: str) -> list:
    """
    Scrape la page assistants d'un MEP via son ID.
    URL pattern : /meps/en/{mep_id}/HOME/assistants
    """
    url = f"{EP_SITE_BASE}/meps/en/{mep_id}/HOME/assistants"
    for attempt in range(1, 4):
        try:
            resp = SESSION.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return _parse_mep_assistants_page(BeautifulSoup(resp.text, "html.parser"))
        except Exception as e:
            if attempt < 3:
                time.sleep(5 * attempt)
            else:
                print(f"  [ERREUR] MEP {mep_id} : {e}")
                return []


def get_all_assistants_by_mep(french_mep_ids: set) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print(f"-> Scraping des pages assistants ({len(french_mep_ids)} MEPs, 5 workers)...")
    mep_to_assistants = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_assistants_for_mep, mep_id): mep_id for mep_id in sorted(french_mep_ids)}
        done = 0
        for future in as_completed(futures):
            mep_id = futures[future]
            assistants = future.result() or []
            mep_to_assistants[mep_id] = assistants
            done += 1
            print(f"  [{done}/{len(french_mep_ids)}] MEP {mep_id} : {len(assistants)} assistant(s)")

    total = sum(len(v) for v in mep_to_assistants.values())
    print(f"  {total} entrées trouvées au total")
    return mep_to_assistants


# ─── State (Supabase) ─────────────────────────────────────────────────────────
# load_state()  → shared.supabase_sync.load_ep_state()
# save_state()  → shared.supabase_sync.push_ep_events()  (implicite dans main)


# ─── Formatage des posts ──────────────────────────────────────────────────────

def _build_message(change: dict) -> dict:
    emoji_type  = EP_TYPE_EMOJIS.get(change["assistant_type"].lower(), "👤")
    type_label  = EP_TYPE_LABELS_FR.get(change["assistant_type"].lower(), change["assistant_type"])
    group_key   = change.get("mep_group", "")
    group_emoji, group_label = format_ep_group(group_key)

    if change["type"] == "arrival":
        header = "🇪🇺 Nouvelle arrivée au Parlement européen"
        action = (
            f"{emoji_type} {change['assistant_name']} rejoint l'équipe de "
            f"{change['mep_name']} ({group_emoji} {group_label})"
        )
    else:
        header = "🇪🇺 Départ au Parlement européen"
        action = (
            f"{emoji_type} {change['assistant_name']} quitte l'équipe de "
            f"{change['mep_name']} ({group_emoji} {group_label})"
        )

    # ── Telegram : plain text, aucun HTML, aucun lien ──
    telegram = (
        f"{header}\n\n"
        f"{action}\n"
        f"📋 {type_label}"
    )

    # ── Bluesky : hashtags avec troncature progressive ──
    body = f"{header}\n\n{action}\n📋 {type_label}"
    bluesky = build_bluesky_post(body, group_key)

    return {"bluesky": bluesky, "telegram": telegram}


# ─── Publication ──────────────────────────────────────────────────────────────

def post_to_bluesky(client: Client, text: str):
    """
    Poste sur Bluesky et retourne la réponse (uri + cid pour le reply).
    """
    response = client.send_post(text=text)
    print(f"  ✓ Bluesky ({len(text)} car.)")
    return response


def post_mep_reply(client: Client, parent_uri: str, parent_cid: str, mep_name: str) -> None:
    """
    Poste un reply avec le @handle du MEP si disponible.
    """
    handle = get_mep_handle(mep_name)
    if not handle:
        return

    try:
        from atproto import models

        handle_clean = handle.lstrip("@")
        resolved = client.resolve_handle(handle_clean)
        did = resolved.did

        text     = handle
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
        print(f"  ✓ Reply Bluesky : {handle}")

    except Exception as e:
        print(f"  ✗ Reply Bluesky : {e}")


def publish_change(change: dict) -> None:
    messages = _build_message(change)

    if BLUESKY_PASSWORD:
        try:
            client = Client()
            client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
            response = post_to_bluesky(client, messages["bluesky"])
            # Reply avec le @handle du MEP si connu
            post_mep_reply(client, response.uri, response.cid, change["mep_name"])
        except Exception as e:
            print(f"  ✗ Bluesky : {e}")
    else:
        print("  ⚠️  BLUESKY_EUROPARL_PASSWORD absent")

    post_telegram(messages["telegram"])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  CavaEuroparl — suivi des collaborateurs des MEPs FR")
    print("=" * 55)

    print("-> Chargement de l'état depuis Supabase...")
    state        = load_ep_state()
    is_first_run = len(state) == 0

    if is_first_run:
        print("⚠️  Premier run (Supabase vide) : construction de l'état initial, aucun post")
        try:
            french_meps = get_french_meps()
        except Exception as e:
            print(f"Erreur fatale (MEPs) : {e}")
            sys.exit(1)
        if not french_meps:
            print("Aucun MEP trouvé — vérifier l'API EP")
            sys.exit(1)
    else:
        print(f"-> MEPs chargés depuis Supabase ({len(state)} MEPs)")
        french_meps = {
            mep_id: {"name": info["name"], "group": info["group"]}
            for mep_id, info in state.items()
        }

    try:
        current_by_mep = get_all_assistants_by_mep(set(french_meps.keys()))
    except Exception as e:
        print(f"Erreur fatale (assistants) : {e}")
        sys.exit(1)

    new_state = {}
    changes   = []

    for mep_id, mep_info in french_meps.items():
        mep_name  = mep_info["name"]
        mep_group = mep_info["group"]
        current_set = {(a["name"], a["type"]) for a in current_by_mep.get(mep_id, [])}
        new_state[mep_id] = {
            "name":       mep_name,
            "group":      mep_group,
            "assistants": [{"name": n, "type": t} for n, t in sorted(current_set)],
        }
        if not is_first_run and mep_id in state:
            prev_set = {(a["name"], a["type"]) for a in state[mep_id].get("assistants", [])}
            for name, atype in (current_set - prev_set):
                changes.append({
                    "type": "arrival", "mep_id": mep_id, "mep_name": mep_name,
                    "mep_group": mep_group, "assistant_name": name, "assistant_type": atype,
                })
            for name, atype in (prev_set - current_set):
                changes.append({
                    "type": "departure", "mep_id": mep_id, "mep_name": mep_name,
                    "mep_group": mep_group, "assistant_name": name, "assistant_type": atype,
                })

    print(f"\n{'─'*55}")
    print(f"  MEPs suivis : {len(new_state)}")
    print(f"  Changements : {len(changes)}")

    if changes:
        print(f"\nPublication de {len(changes)} changement(s)...")
        for change in changes:
            arrow = "->" if change["type"] == "arrival" else "<-"
            print(f"  [{change['type'].upper()}] {arrow} {change['assistant_name']} | "
                  f"{change['mep_name']} ({change['mep_group']})")
            publish_change(change)
            time.sleep(3)

        # Écriture dans Supabase (remplace save_state)
        stats = push_ep_events(changes)
        print(f"Supabase EP — {stats['inseres']} insérés, {stats['doublons']} doublons, {stats['erreurs']} erreurs")

    else:
        if is_first_run:
            # Premier run : initialise tous les mandats dans Supabase
            init_changes = [
                {
                    "type": "arrival",
                    "mep_id": mep_id,
                    "mep_name": info["name"],
                    "mep_group": info["group"],
                    "assistant_name": a["name"],
                    "assistant_type": a["type"],
                }
                for mep_id, info in new_state.items()
                for a in info["assistants"]
            ]
            if init_changes:
                push_ep_events(init_changes)
                print(f"  Initialisation Supabase : {len(init_changes)} mandats créés")
        else:
            print("\n  Aucun changement aujourd'hui.")

    print("\n✅ Terminé")


if __name__ == "__main__":
    main()
