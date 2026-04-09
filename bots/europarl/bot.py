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
EP_SITE_BASE = "https://www.europarl.europa.eu"

HEADERS = {
    "User-Agent": "CavaEuroparl/1.0 (@cavaeuroparl.bsky.social) - Civic transparency bot",
    "Accept": "text/html,application/xhtml+xml",
}

SESSION  = make_session()


# ─── Récupération des eurodéputés français ────────────────────────────────────

def get_french_meps() -> dict:
    """
    Récupère les eurodéputés français depuis la page HTML full-list du site EP.
    Beaucoup plus fiable que l'API Open Data qui timeout fréquemment.
    """
    print("-> Récupération des eurodéputés français via full-list EP...")
    url = f"{EP_SITE_BASE}/meps/en/full-list/html"
    for attempt in range(1, 4):
        try:
            resp = SESSION.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 3:
                print(f"  [tentative {attempt}/3] : {e} — retry dans {10 * attempt}s")
                time.sleep(10 * attempt)
            else:
                raise

    soup  = BeautifulSoup(resp.text, "html.parser")
    meps  = {}

    for card in soup.select("div.erpl_member-list-item"):
        # ID depuis le lien
        link  = card.select_one("a[href*='/meps/en/']")
        if not link:
            continue
        m = re.search(r"/meps/en/(\d+)/", link["href"])
        if not m:
            continue
        mep_id = m.group(1)

        # Pays : on filtre sur la France
        country = card.select_one("span.erpl_member-list-item-country")
        if not country or "France" not in country.get_text():
            continue

        # Nom
        name_el = card.select_one("span.erpl_member-list-item-name, .erpl_title-h5")
        mep_name = name_el.get_text(strip=True) if name_el else f"MEP#{mep_id}"

        # Groupe
        group_el = card.select_one("span.erpl_member-list-item-group")
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
    else:
        # Runs suivants : on repart du state.json, pas besoin de l'API EP
        print(f"-> MEPs chargés depuis state.json ({len(state)} MEPs)")
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
    else:
        if not is_first_run:
            print("\n  Aucun changement aujourd'hui.")

    save_state(new_state)
    print("\n✅ Terminé")


if __name__ == "__main__":
    main()
