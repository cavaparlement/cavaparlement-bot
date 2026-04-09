"""
mep_lookup.py
Lookup handle Bluesky pour les eurodéputés français.
Compatible Python 3.9+

Les clés de MEP_HANDLES suivent le format retourné par l'API EP Open Data :
"Prénom Nom" (ex: "Raphaël Glucksmann", "Manon Aubry").

La fonction get_mep_handle() essaie aussi le format inversé "Nom Prénom"
et la normalisation sans accents pour couvrir les variantes.
"""

import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Handles Bluesky
# Clé : "Prénom Nom" tel que retourné par l'API EP (foaf:givenName + foaf:familyName)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def _normalize(s):
    # type: (str) -> str
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def get_mep_handle(mep_name):
    # type: (str) -> Optional[str]
    """
    Retourne le handle Bluesky d'un eurodéputé à partir de son nom.

    Essaie dans l'ordre :
    1. Correspondance directe (format API : "Prénom Nom")
    2. Correspondance normalisée sans accents
    3. Format inversé "Nom Prénom" (au cas où l'API renverrait ce format)

    Ex:
        get_mep_handle("Raphaël Glucksmann") -> "@raphaelglucksmann.bsky.social"
        get_mep_handle("GLUCKSMANN Raphaël") -> "@raphaelglucksmann.bsky.social"
    """
    mep_name = mep_name.strip()

    # 1. Correspondance directe
    if mep_name in MEP_HANDLES:
        return MEP_HANDLES[mep_name]

    # 2. Sans accents
    name_norm = _normalize(mep_name)
    for k, v in MEP_HANDLES.items():
        if _normalize(k) == name_norm:
            return v

    # 3. Format inversé "Nom Prénom" -> essaie "Prénom Nom"
    parts = mep_name.split(" ", 1)
    if len(parts) == 2:
        inverted = "{} {}".format(parts[1], parts[0])
        if inverted in MEP_HANDLES:
            return MEP_HANDLES[inverted]
        inv_norm = _normalize(inverted)
        for k, v in MEP_HANDLES.items():
            if _normalize(k) == inv_norm:
                return v

    return None
