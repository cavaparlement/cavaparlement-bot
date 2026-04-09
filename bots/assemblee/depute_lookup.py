"""
depute_lookup.py
Lookup groupe parlementaire + handle Bluesky pour les députés de l'AN.
Compatible Python 3.9+

Les clés de DEPUTE_HANDLES suivent le format du history.json : "Nom Prénom"
(ex: "Soudais Ersilia", "Cernon Bérenger").
"""

import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Groupes parlementaires
# ---------------------------------------------------------------------------

GROUP_SHORT = {
    "La France insoumise - Nouveau Front Populaire": "LFI-NFP",
    "Rassemblement National": "RN",
    "Les Démocrates": "Dem",
    "Droite Républicaine": "DR",
    "Socialistes et apparentés": "SOC",
    "Horizons & Indépendants": "HOR",
    "Ensemble pour la République": "EPR",
    "Écologistes et Social": "EcoS",
    "Gauche Démocrate et Républicaine": "GDR",
    "Libertés, Indépendants, Outre-mer et Territoires": "LIOT",
    "Non-inscrit": "NI",
}

GROUP_EMOJI = {
    "La France insoumise - Nouveau Front Populaire": "🔴",
    "Rassemblement National": "⚫",
    "Les Démocrates": "🟡",
    "Droite Républicaine": "🔵",
    "Socialistes et apparentés": "🌹",
    "Horizons & Indépendants": "🟠",
    "Ensemble pour la République": "🟣",
    "Écologistes et Social": "🌿",
    "Gauche Démocrate et Républicaine": "🔴",
    "Libertés, Indépendants, Outre-mer et Territoires": "⚪",
    "Non-inscrit": "🏛️",
}

GROUP_HASHTAG = {
    "La France insoumise - Nouveau Front Populaire": "LFI",
    "Rassemblement National": "RN",
    "Les Démocrates": "LesDemocrates",
    "Droite Républicaine": "DroiteRepublicaine",
    "Socialistes et apparentés": "Socialistes",
    "Horizons & Indépendants": "Horizons",
    "Ensemble pour la République": "EnsemblePourLaRepublique",
    "Écologistes et Social": "Ecologistes",
    "Gauche Démocrate et Républicaine": "GDR",
    "Libertés, Indépendants, Outre-mer et Territoires": "LIOT",
    "Non-inscrit": "NonInscrit",
}

# ---------------------------------------------------------------------------
# Handles Bluesky
# Clé : "Nom Prénom" tel qu'il apparaît dans history.json
# ---------------------------------------------------------------------------

DEPUTE_HANDLES = {
    "Bovet Jorys": "@jorysb3.bsky.social",
    "De Pélichy Constance": "@cdepelichy.bsky.social",
    "Faucillon Elsa": "@elsafaucillon.bsky.social",
    "Gillet Yoann": "@yoanngillet30.bsky.social",
    "Lepers Guillaume": "@lepers.bsky.social",
    "Maillard Sylvain": "@sylvain-maillard.bsky.social",
    "Plassard Christophe": "@cplassard.bsky.social",
    "Portarrieu Jean-François": "@jfportarrieu.bsky.social",
    "Rimane Davy": "@davyrimane.bsky.social",
    "Huyghe Sébastien": "@sebastienhuyghe.bsky.social",
    "Pancher Bertrand": "@bertrandpancher.bsky.social",
    "Sansu Nicolas": "@nicolas-sansu.bsky.social",
    "Chassaigne André": "@andrechassaigne.bsky.social",
    "Hervieu Catherine": "@cathervieu.bsky.social",
    "Arrighi Christine": "@christinearrighi.bsky.social",
    "Batho Delphine": "@delphinebatho.bsky.social",
    "Roumégas Jean-Louis": "@jeanlouisroumegas.bsky.social",
    "Autain Clémentine": "@clementineautain.bsky.social",
    "Pochon Marie": "@mariepochon.fr",
    "Ozenne Julie": "@julieozenne.bsky.social",
    "Bonnet Arnaud": "@arnaud-bonnet.bsky.social",
    "Simonnet Danielle": "@daniellesimonnet.fr",
    "Lahais Tristan": "@tristanlahais.fr",
    "Girard Damien": "@damiengirard.bsky.social",
    "Balage El Mariky Léa": "@leabalage.bsky.social",
    "Taillé-Polian Sophie": "@sophietaillepolian.bsky.social",
    "Sebaihi Sabrina": "@sabrinasebaihi.bsky.social",
    "Sas Eva": "@eva-sas.fr",
    "Regol Sandra": "@sandraregol.bsky.social",
    "Laernoes Julie": "@julielaernoes.bsky.social",
    "Belluco Lisa": "@lisabelluco.bsky.social",
    "Ruffin François": "@francoisruffin.fr",
    "Garin Marie-Charlotte": "@mcgarin.bsky.social",
    "Rousseau Sandrine": "@sandrousseau.bsky.social",
    "Chatelain Cyrielle": "@cyriellechatelain.fr",
    "Lhardit Laurent": "@laurent-lhardit.bsky.social",
    "Baumel Laurent": "@laurentbaumel.bsky.social",
    "Pic Anna": "@annapic.fr",
    "Hadizadeh Ayda": "@aydahadi.bsky.social",
    "Herouin Léautey Florence": "@fleautey.bsky.social",
    "Rouaux Claudia": "@claudiarouaux.bsky.social",
    "Roussel Fabrice": "@froussel44240.bsky.social",
    "Vicot Roger": "@rogervicot.bsky.social",
    "Dombre-Coste Fanny": "@fannydombrecoste.bsky.social",
    "Sother Thierry": "@thierrysother.bsky.social",
    "Jourdan Chantal": "@chantaljourdan.bsky.social",
    "Hervieu Céline": "@celinehervieu.bsky.social",
    "Aviragnet Joël": "@joelaviragnet.bsky.social",
    "Christophle Paul": "@paulchristophle.bsky.social",
    "Oberti Jacques": "@jacquesoberti.bsky.social",
    "Runel Sandrine": "@sandrinerunel.bsky.social",
    "Mercier Estelle": "@estellemercieran.bsky.social",
    "Hollande François": "@fhollande.bsky.social",
    "Delautrette Stéphane": "@sdelautrette.bsky.social",
    "Simion Arnaud": "@arnaudsimion.bsky.social",
    "Keloua Hachi Fatiha": "@kelouaf.bsky.social",
    "Thomin Mélanie": "@melaniethomin.bsky.social",
    "Echaniz Iñaki": "@inakiechaniz.bsky.social",
    "Battistel Marie-Noëlle": "@mnbattistel.bsky.social",
    "David Alain": "@alaindavid.bsky.social",
    "Dufau Peio": "@peiodufau.bsky.social",
    "Pirès Beaune Christine": "@c-piresbeaune.bsky.social",
    "Pribetich Pierre": "@pierrepribetich.bsky.social",
    "Saulignac Hervé": "@hsaulignac.bsky.social",
    "Thiébauld-Martinez Céline": "@thiebaultceline.bsky.social",
    "Eskenazi Romain": "@romaineskenazi.bsky.social",
    "Potier Dominique": "@dominiquepotier.bsky.social",
    "Santiago Isabelle": "@isadef-enf94.bsky.social",
    "Bellay Béatrice": "@beabellay972.bsky.social",
    "Brun Philippe": "@philippebrun.bsky.social",
    "Rossi Valérie": "@vrossi-deputee05.bsky.social",
    "Panot Mathilde": "@mathildepanot.bsky.social",
    "Taurinya Andrée": "@andreetaurinya.bsky.social",
    "Arnault Raphaël": "@arnaultraphael.bsky.social",
    "Guetté Clémence": "@clemenceguette.bsky.social",
    "Cathala Gabrielle": "@gabriellecthl.bsky.social",
    "Feld Mathilde": "@mathildefeld.bsky.social",
    "Belouassa-Cherifi Anaïs": "@anaisbelouassa.bsky.social",
    "Hamdane Zahia": "@zahiahamdane.bsky.social",
    "Legavre Jérôme": "@legavrejerome.bsky.social",
    "Leboucher Élise": "@eliseleboucher.bsky.social",
    "Oziol Nathalie": "@nathalieoziol.bsky.social",
    "Mesmeur Marie": "@mariemesmeur.bsky.social",
    "Hignet Mathilde": "@mathilde-hignet.bsky.social",
    "Cernon Bérenger": "@slappy-w.bsky.social",
    "Clouet Hadrien": "@hadrienclouet.bsky.social",
    "Maximi Marianne": "@mariannemaximi.bsky.social",
    "Trouvé Aurélie": "@trouveaurelie.bsky.social",
    "Abomangoli Nadège": "@nadege-abomangoli.bsky.social",
    "Stambach-Terrenoir Anne": "@annestambach.bsky.social",
    "Amiot Ségolène": "@segoleneamiot.bsky.social",
    "Meunier Manon": "@manonmeunier.bsky.social",
    "Nosbé Sandrine": "@snosbe.bsky.social",
    "Maudet Damien": "@damienmaudet.bsky.social",
    "Dufour Alma": "@almadufour.bsky.social",
    "Lepvraud Murielle": "@muriellelepvraud.bsky.social",
    "Soudais Ersilia": "@ersiliasoudais.bsky.social",
    "Ferrer Sylvie": "@sylvieferrer.bsky.social",
    "Pilato René": "@renepilato.bsky.social",
    "Alexandre Laurent": "@deputealexandre.bsky.social",
    "Raux Jean-Claude": "@jeanclauderaux.fr",
    "Delaporte Arthur": "@arthurdelaporte.bsky.social",
    "Bonnet Nicolas": "@nicolasbonnet.fr",
    "Boumertit Idir": "@idirboumertit.bsky.social",
    "Houlié Sacha": "@sachahoulie.bsky.social",
    "Peytavie Sébastien": "@peytavie.fr",
    "Amard Gabriel": "@gabrielamard.bsky.social",
    "Corbière Alexis": "@alexiscorbiere.bsky.social",
    "Biteau Benoît": "@benoit-biteau.bsky.social",
    "Lahmar Abdelkader": "@abdelkaderlahmar.bsky.social",
    "Latombe Philippe": "@platombe.bsky.social",
    "Laisney Maxime": "@maximelaisney.bsky.social",
    "Thierry Nicolas": "@nicolas-thierry.bsky.social",
    "Tavernier Boris": "@boristavernier.bsky.social",
    "Davi Hendrik": "@hendrikdavi.bsky.social",
    "Bernalicis Ugo": "@ugobernalicis.bsky.social",
    "Le Gall Arnaud": "@arnaudlegall.bsky.social",
    "Carême Damien": "@damiencareme.bsky.social",
    "Carrière Sylvain": "@sylvaincarriere.bsky.social",
    "Amirshahi Pouria": "@pouriaamirshahi.fr",
    "Coulomme Jean-François": "@jfcoulomme.bsky.social",
    "Fernandes Emmanuel": "@emmanfernandes.bsky.social",
    "Iordanoff Jérémie": "@iordanoff.bsky.social",
    "Martens Bilongo Carlos": "@cmbilongo.bsky.social",
    "Petit Frédéric": "@fpetit.bsky.social",
    "Vannier Paul": "@paulvannier.bsky.social",
    "Le Coq Aurélien": "@aurelienlecoq.bsky.social",
    "Vallaud Boris": "@borisvallaud.bsky.social",
    "Bex Christophe": "@christophebex.bsky.social",
    "Tavel Matthias": "@matthiastavel.bsky.social",
    "Prud'homme Loïc": "@loicprudhomme.bsky.social",
    "Saintoul Aurélien": "@asaintoul.bsky.social",
    "Piquemal François": "@francoispiquemal.bsky.social",
    "Bothorel Eric": "@ericbothorel.fr",
    "Obono Danièle": "@deputeeobono.bsky.social",
    "Lachaud Bastien": "@blachaud.bsky.social",
    "Lucas Benjamin": "@benjaminlucas.fr",
    "Boyard Louis": "@louisboyard.bsky.social",
    "Delogu Sébastien": "@delogusebastien.bsky.social",
    "Portes Thomas": "@thomasportes.bsky.social",
    "Saint-Martin Arnaud": "@arnaudsaint-martin.bsky.social",
    "Léaument Antoine": "@antoine-leaument.bsky.social",
    "Guiraud David": "@davidguiraud.bsky.social",
    "Faure Olivier": "@olivierfaure.bsky.social",
    "Coquerel Eric": "@ericcoquerel.bsky.social",
    "Bompard Manuel": "@mbompard.bsky.social",
}


# ---------------------------------------------------------------------------
# Fonctions de lookup
# ---------------------------------------------------------------------------

def _normalize(s):
    # type: (str) -> str
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def get_depute_handle(parlementaire):
    # type: (str) -> Optional[str]
    """
    Retourne le handle Bluesky d'un député à partir de son nom complet
    tel qu'il apparaît dans history.json : "Nom Prénom".

    Ex: get_depute_handle("Soudais Ersilia") -> "@ersiliasoudais.bsky.social"
        get_depute_handle("Cernon Bérenger") -> "@slappy-w.bsky.social"
    """
    if parlementaire in DEPUTE_HANDLES:
        return DEPUTE_HANDLES[parlementaire]
    key_norm = _normalize(parlementaire)
    for k, v in DEPUTE_HANDLES.items():
        if _normalize(k) == key_norm:
            return v
    return None


def format_group_line(groupe_label, short=False):
    # type: (str, bool) -> str
    """
    Formate la ligne groupe à partir du groupe_label du history.json.
    Ex: format_group_line("La France insoumise - Nouveau Front Populaire")
    -> "🔴 LFI-NFP · La France insoumise - Nouveau Front Populaire"
    """
    emoji = GROUP_EMOJI.get(groupe_label, "🏛️")
    short_name = GROUP_SHORT.get(groupe_label, groupe_label)
    if short:
        return "{} {}".format(emoji, short_name)
    return "{} {} · {}".format(emoji, short_name, groupe_label)


def get_group_hashtag(groupe_label):
    # type: (str) -> str
    tag = GROUP_HASHTAG.get(groupe_label, groupe_label.replace(" ", ""))
    return "#" + tag
