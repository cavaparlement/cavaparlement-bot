"""
mep_lookup.py — utilise shared/bluesky_lookup.py (data/bluesky_handles.json)
Garde la dict MEP_HANDLES comme fallback pour compatibilité.
"""

import unicodedata
from typing import Optional
from shared.bluesky_lookup import get_handle as _get_handle_shared

# Fallback hardcodé (conservé pour compatibilité)
MEP_HANDLES = {
    "Thomas Pellerin-Carlin": "@tpellerincarlin.bsky.social",
    "Raphaël Glucksmann": "@raphaelglucksmann.bsky.social",
    "Pierre Jouvet": "@pierrejouvet.fr",
    "David Cormand": "@davidcormand.bsky.social",
    "Christophe Grudler": "@grudlerch.bsky.social",
    "Arash Saeidi": "@arashsaeidi.bsky.social",
    "Grégory Allione": "@gregoryallione.bsky.social",
    "Pascal Canfin": "@pcanfin.bsky.social",
    "Damien Carême": "@damiencareme.bsky.social",
    "Sandro Gozi": "@sandrogozi.bsky.social",
    "Mounir Satouri": "@mounirsatouri.bsky.social",
    "Christophe Clergeau": "@christopheclergeau.bsky.social",
    "Anthony Smith": "@smithanthony.bsky.social",
    "Pierre Larrouturou": "@pierrelarrouturou.bsky.social",
    "Jérémy Decerle": "@jdecerle.bsky.social",
    "François Kalfon": "@francoiskalfon.bsky.social",
    "Eric Sargiacomo": "@erics40.bsky.social",
    "Gilles Boyer": "@gillesboyer.bsky.social",
    "Nathalie Loiseau": "@nathalieloiseau.bsky.social",
    "Valérie Hayer": "@valeriehayer.bsky.social",
    "Valérie Devaux": "@devauxvalerie.bsky.social",
    "Emma Rafowicz": "@emmarafowicz.bsky.social",
    "Mélissa Camara": "@melissacamara.bsky.social",
    "Marina Mesure": "@marinamesure.bsky.social",
    "Majdouline Sbaï": "@majdoulinesbai.bsky.social",
    "Nora Mebarek": "@noramebarek.bsky.social",
    "Fabienne Keller": "@fabiennekeller.bsky.social",
    "Salima Yenbou": "@salimayenbou.bsky.social",
    "Irène Tolleret": "@itolleret.bsky.social",
    "Chloé Ridel": "@chloe-ridel.fr",
    "Claire Fita": "@clairefita.bsky.social",
    "Murielle Laurent": "@muriellelaurent.bsky.social",
    "Aurore Lalucq": "@aurorelalucq.bsky.social",
    "Manon Aubry": "@manonaubryfr.bsky.social",
    "Leïla Chaibi": "@leilachaibi.bsky.social",
    "Laurence Farreng": "@laurencefarreng.bsky.social",
    "Emma Fourreau": "@emma-fourreau.bsky.social",
    "Jean-Marc Germain": "@jmgermain.bsky.social",
    "Bernard Guetta": "@dodolasaumure.bsky.social",
    "Younous Omarjee": "@younousomarjee.bsky.social",
    "Marie Toussaint": "@marietouss1.bsky.social",
    "Stéphanie Yon-Courtin": "@syoncourtin.bsky.social",
}


def _normalize(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def get_mep_handle(mep_name):
    # type: (str) -> Optional[str]
    # 1. Cherche dans le JSON unifié (source principale)
    handle = _get_handle_shared(mep_name, "europarl")
    if handle:
        return handle

    # 2. Fallback dict hardcodé
    mep_name = mep_name.strip()
    if mep_name in MEP_HANDLES:
        return MEP_HANDLES[mep_name].lstrip("@")
    name_norm = _normalize(mep_name)
    for k, v in MEP_HANDLES.items():
        if _normalize(k) == name_norm:
            return v.lstrip("@")
    parts = mep_name.split(" ", 1)
    if len(parts) == 2:
        inverted = "{} {}".format(parts[1], parts[0])
        if inverted in MEP_HANDLES:
            return MEP_HANDLES[inverted].lstrip("@")
        inv_norm = _normalize(inverted)
        for k, v in MEP_HANDLES.items():
            if _normalize(k) == inv_norm:
                return v.lstrip("@")
    return None
