"""
mep_lookup.py
Lookup groupe politique + handle Bluesky pour les eurodéputés français.
Compatible Python 3.9+

Les clés de MEP_HANDLES suivent le format "Nom Prénom"
(ex: "Glucksmann Raphaël", "Aubry Manon").
"""

import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Groupes politiques PE (10e législature 2024-2029)
# ---------------------------------------------------------------------------

GROUP_SHORT = {
    "Groupe des Socialistes et Démocrates": "S&D",
    "Groupe du Parti Populaire Européen": "PPE",
    "Groupe Renew Europe": "Renew",
    "Les Verts / Alliance Libre Européenne": "Verts/ALE",
    "Gauche de l'Europe": "GUE/NGL",
    "Groupe des Conservateurs et Réformistes Européens": "CRE",
    "Groupe Patriotes pour l'Europe": "PfE",
    "Groupe Europe des Nations Souveraines": "ENS",
    "Non-inscrit": "NI",
}

GROUP_EMOJI = {
    "Groupe des Socialistes et Démocrates": "🌹",
    "Groupe du Parti Populaire Européen": "🔵",
    "Groupe Renew Europe": "🟡",
    "Les Verts / Alliance Libre Européenne": "🌿",
    "Gauche de l'Europe": "🔴",
    "Groupe des Conservateurs et Réformistes Européens": "🟤",
    "Groupe Patriotes pour l'Europe": "⚫",
    "Groupe Europe des Nations Souveraines": "⚫",
    "Non-inscrit": "🏛️",
}

GROUP_HASHTAG = {
    "Groupe des Socialistes et Démocrates": "SD",
    "Groupe du Parti Populaire Européen": "PPE",
    "Groupe Renew Europe": "Renew",
    "Les Verts / Alliance Libre Européenne": "VertsALE",
    "Gauche de l'Europe": "GUE",
    "Groupe des Conservateurs et Réformistes Européens": "CRE",
    "Groupe Patriotes pour l'Europe": "PatriotesEurope",
    "Groupe Europe des Nations Souveraines": "ENS",
    "Non-inscrit": "NonInscrit",
}

# ---------------------------------------------------------------------------
# Handles Bluesky
# Clé : "Nom Prénom" (format attendu dans history.json Europarl)
# ---------------------------------------------------------------------------

MEP_HANDLES = {
    "Pellerin-Carlin Thomas": "@tpellerincarlin.bsky.social",
    "Glucksmann Raphaël": "@raphaelglucksmann.bsky.social",
    "Jouvet Pierre": "@pierrejouvet.fr",
    "Cormand David": "@davidcormand.bsky.social",
    "Grudler Christophe": "@grudlerch.bsky.social",
    "Saeidi Arash": "@arashsaeidi.bsky.social",
    "Allione Grégory": "@gregoryallione.bsky.social",
    "Canfin Pascal": "@pcanfin.bsky.social",
    "Carême Damien": "@damiencareme.bsky.social",
    "Gozi Sandro": "@sandrogozi.bsky.social",
    "Satouri Mounir": "@mounirsatouri.bsky.social",
    "Clergeau Christophe": "@christopheclergeau.bsky.social",
    "Smith Anthony": "@smithanthony.bsky.social",
    "Larrouturou Pierre": "@pierrelarrouturou.bsky.social",
    "Decerle Jérémy": "@jdecerle.bsky.social",
    "Kalfon François": "@francoiskalfon.bsky.social",
    "Sargiacomo Eric": "@erics40.bsky.social",
    "Boyer Gilles": "@gillesboyer.bsky.social",
    "Loiseau Nathalie": "@nathalieloiseau.bsky.social",
    "Hayer Valérie": "@valeriehayer.bsky.social",
    "Devaux Valérie": "@devauxvalerie.bsky.social",
    "Rafowicz Emma": "@emmarafowicz.bsky.social",
    "Camara Mélissa": "@melissacamara.bsky.social",
    "Mesure Marina": "@marinamesure.bsky.social",
    "Sbaï Majdouline": "@majdoulinesbai.bsky.social",
    "Mebarek Nora": "@noramebarek.bsky.social",
    "Keller Fabienne": "@fabiennekeller.bsky.social",
    "Yenbou Salima": "@salimayenbou.bsky.social",
    "Tolleret Irène": "@itolleret.bsky.social",
    "Ridel Chloé": "@chloe-ridel.fr",
    "Fita Claire": "@clairefita.bsky.social",
    "Laurent Murielle": "@muriellelaurent.bsky.social",
    "Lalucq Aurore": "@aurorelalucq.bsky.social",
    "Aubry Manon": "@manonaubryfr.bsky.social",
    "Chaibi Leïla": "@leilachaibi.bsky.social",
    "Farreng Laurence": "@laurencefarreng.bsky.social",
    "Fourreau Emma": "@emma-fourreau.bsky.social",
    "Germain Jean-Marc": "@jmgermain.bsky.social",
    "Guetta Bernard": "@dodolasaumure.bsky.social",
    "Omarjee Younous": "@younousomarjee.bsky.social",
    "Toussaint Marie": "@marietouss1.bsky.social",
    "Yon-Courtin Stéphanie": "@syoncourtin.bsky.social",
}


# ---------------------------------------------------------------------------
# Fonctions de lookup
# ---------------------------------------------------------------------------

def _normalize(s):
    # type: (str) -> str
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def get_mep_handle(parlementaire):
    # type: (str) -> Optional[str]
    """
    Retourne le handle Bluesky d'un eurodéputé à partir de son nom complet.
    Format attendu : "Nom Prénom" (ex: "Glucksmann Raphaël", "Aubry Manon").
    """
    if parlementaire in MEP_HANDLES:
        return MEP_HANDLES[parlementaire]
    key_norm = _normalize(parlementaire)
    for k, v in MEP_HANDLES.items():
        if _normalize(k) == key_norm:
            return v
    return None


def format_group_line(groupe_label, short=False):
    # type: (str, bool) -> str
    emoji = GROUP_EMOJI.get(groupe_label, "🏛️")
    short_name = GROUP_SHORT.get(groupe_label, groupe_label)
    if short:
        return "{} {}".format(emoji, short_name)
    return "{} {} · {}".format(emoji, short_name, groupe_label)


def get_group_hashtag(groupe_label):
    # type: (str) -> str
    tag = GROUP_HASHTAG.get(groupe_label, groupe_label.replace(" ", ""))
    return "#" + tag
