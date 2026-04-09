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
from bots.europarl.mep_lookup import get_mep_handle

# ─── Configuration ────────────────────────────────────────────────────────────

BLUESKY_HANDLE   = "cavaeuroparl.bsky.social"
BLUESKY_PASSWORD = os.environ.get("BLUESKY_EUROPARL_PASSWORD")
TELEGRAM_CHANNEL = "@cavaparlement"

STATE_FILE   = "data/europarl/state.json"
EP_API_BASE  = "https://data.europarl.europa.eu/api/v2"
EP_SITE_BASE = "https://www.europarl.europa.eu"
CURRENT_TERM = 10

HEADERS = {
    "User-Agent": "CavaEuroparl/1.0 (@cavaeuroparl.bsky.social) - Civic transparency bot",
    "Accept": "text/html,application/xhtml+xml",
}
API_HEADERS = {
    "User-Agent": "CavaEuroparl/1.0 (@cavaeuroparl.bsky.social)",
    "Accept": "application/ld+json",
}

SESSION  = make_session()


# ─── Helpers groupes ──────────────────────────────────────────────────────────

def _extract_group_key(item: dict) -> str:
    for field in ("ep-core:politicalGroup", "politicalGroup", "hasGroup"):
        val = item.get(field)
        if isinstance(val, str):
            return val.rstrip("/").split("/")[-1].upper()
        if isinstance(val, dict):
            return (val.get("notation") or val.get("label") or "").upper()
    for field in ("hasMembership", "memberOf", "ep-core:hasMembership"):
        memberships = item.get(field, [])
        if isinstance(memberships, dict):
            memberships = [memberships]
        for m in memberships:
            if isinstance(m, dict):
                role = m.get("role", m.get("ep-core:role", ""))
                if "political" in str(role).lower() or "group" in str(role).lower():
                    org = m.get("organization", m.get("ep-core:organization", {}))
                    if isinstance(org, dict):
                        key = org.get("notation") or org.get("label") or ""
                        return str(key).upper()
                    if isinstance(org, str):
                        return org.rstrip("/").split("/")[-1].upper()
    return ""


# ─── Récupération des eurodéputés français ────────────────────────────────────

def get_french_meps() -> dict:
    print("-> Récupération des eurodéputés français via EP Open Data API...")
    url = f"{EP_API_BASE}/meps"
    params = {
        "country-of-representation": "FR",
        "format":             "application/ld+json",
        "parliamentary-term": CURRENT_TERM,
        "json-layout":        "framed",
        "limit":              200,
        "offset":             0,
    }
    last_exc = None
    for attempt in range(1, 5):  # 4 tentatives max
        try:
            resp = SESSION.get(url, params=params, headers=API_HEADERS, timeout=90)
            resp.raise_for_status()
            break
        except Exception as e:
            last_exc = e
            wait = 15 * attempt
            print(f"  [tentative {attempt}/4] Erreur API EP : {e} — retry dans {wait}s")
            time.sleep(wait)
    else:
        raise last_exc
    data = resp.json()
    items = data.get("data", [])
    meps = {}
    for item in items:
        at_id  = item.get("@id", "")
        mep_id = at_id.rstrip("/").split("/")[-1] if at_id else ""
        if not mep_id or not mep_id.isdigit():
            mep_id = str(item.get("identifier", ""))
        mep_name = (
            item.get("label")
            or item.get("foaf:name")
            or item.get("skos:prefLabel")
            or f"{item.get('foaf:givenName', '')} {item.get('foaf:familyName', '')}".strip()
            or f"MEP#{mep_id}"
        )
        group_key = _extract_group_key(item)
        if mep_id and mep_id.isdigit():
            meps[mep_id] = {"name": mep_name, "group": group_key}
    print(f"  {len(meps)} eurodéputés français trouvés")
    return meps


# ─── Récupération des assistants ──────────────────────────────────────────────

def _parse_mep_assistants_page(soup: BeautifulSoup) -> list:
    """
    Parse la page /assistants d'un MEP individuel.
    Essaie plusieurs structures HTML connues du site EP.
    """
    results = []

    # Structure principale : blocs par type d'assistant
    for section in soup.select("div.erpl_mep-assistants-type, div.ep_gridrow"):
        type_el   = section.select_one("h3, span.erpl_mep-assistants-type-title, strong")
        type_text = type_el.get_text(strip=True) if type_el else "Assistant"
        for item in section.select("li, div.erpl_mep-assistants-name, span.ep_name"):
            name = item.get_text(strip=True)
            if name and name != type_text:
                results.append({"name": name, "type": type_text})

    # Fallback : table classique
    if not results:
        table = soup.find("table")
        if table:
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    name      = cols[0].get_text(strip=True)
                    type_text = cols[1].get_text(strip=True)
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
    print(f"-> Scraping des pages assistants ({len(french_mep_ids)} MEPs)...")
    mep_to_assistants = {}
    for i, mep_id in enumerate(sorted(french_mep_ids), 1):
        assistants = get_assistants_for_mep(mep_id)
        mep_to_assistants[mep_id] = assistants
        print(f"  [{i}/{len(french_mep_ids)}] MEP {mep_id} : {len(assistants)} assistant(s)")
        time.sleep(0.5)
    total = sum(len(v) for v in mep_to_assistants.values())
    print(f"  {total} entrées trouvées au total")
    return mep_to_assistants


# ─── State ────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if os.path.exists(STATE_FILE) and os.path.getsize(STATE_FILE) > 5:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"  State sauvegardé ({len(state)} MEPs)")


# ─── Formatage des posts ──────────────────────────────────────────────────────

def _build_message(change: dict) -> dict:
    emoji_type       = EP_TYPE_EMOJIS.get(change["assistant_type"].lower(), "👤")
    type_label       = EP_TYPE_LABELS_FR.get(change["assistant_type"].lower(), change["assistant_type"])
    mep_url          = f"{EP_SITE_BASE}/meps/en/{change['mep_id']}/ASSISTANTS"
    group_key        = change.get("mep_group", "")
    group_emoji, group_label = format_ep_group(group_key)

    if change["type"] == "arrival":
        header    = "🇪🇺 Nouvelle arrivée au Parlement européen"
        action_bs = (
            f"{emoji_type} {change['assistant_name']} rejoint l'équipe de "
            f"{change['mep_name']} ({group_emoji} {group_label})"
        )
        action_tg = (
            f"{emoji_type} <b>{change['assistant_name']}</b> rejoint l'équipe de "
            f"<b>{change['mep_name']}</b> ({group_emoji} {group_label})"
        )
    else:
        header    = "🇪🇺 Départ au Parlement européen"
        action_bs = (
            f"{emoji_type} {change['assistant_name']} quitte l'équipe de "
            f"{change['mep_name']} ({group_emoji} {group_label})"
        )
        action_tg = (
            f"{emoji_type} <b>{change['assistant_name']}</b> quitte l'équipe de "
            f"<b>{change['mep_name']}</b> ({group_emoji} {group_label})"
        )

    bluesky = f"{header}\n\n{action_bs}\n📋 {type_label}\n\n➡️ {mep_url}"
    if len(bluesky) > 300:
        bluesky = bluesky[:297] + "..."

    telegram = (
        f"{header}\n\n"
        f"{action_tg}\n"
        f"📋 {type_label}\n\n"
        f'➡️ <a href="{mep_url}">Voir la fiche EP</a>'
    )
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

    state        = load_state()
    is_first_run = len(state) == 0

    if is_first_run:
        print("⚠️  Premier run : construction de l'état initial, aucun post")

    try:
        french_meps = get_french_meps()
    except Exception as e:
        print(f"Erreur fatale (MEPs) : {e}")
        sys.exit(1)

    if not french_meps:
        print("Aucun MEP trouvé — vérifier l'API EP")
        sys.exit(1)

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
    else:
        if not is_first_run:
            print("\n  Aucun changement aujourd'hui.")

    save_state(new_state)
    print("\n✅ Terminé")


if __name__ == "__main__":
    main()
