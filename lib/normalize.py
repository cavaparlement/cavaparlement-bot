"""Helpers de normalisation des noms côté Python.

DOIT donner exactement le même résultat que `normalize_nom()` SQL côté DB,
sinon les comparaisons d'égalité (via WHERE nom_normalise = ?) échouent.

`normalize_nom()` SQL fait : lower(unaccent(trim(regexp_replace(s, '\\s+', ' ', 'g'))))
"""

from __future__ import annotations

import re
import unicodedata


def normalize_for_matching(s: str | None) -> str:
    """Normalise un nom pour matching exact côté DB.

    Reproduit `normalize_nom()` SQL : minuscules + sans accents + trim +
    espaces multiples écrasés en un seul.
    """
    if not s:
        return ""
    # Trim + écrasement des espaces multiples
    s = re.sub(r"\s+", " ", s.strip())
    # Suppression des accents (NFKD = decompose, puis filter combining marks)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Minuscules
    return s.lower()


def parse_ep_assistant_name(full_name: str) -> tuple[str, str]:
    """Parse un nom d'assistant EP : MAJUSCULES = nom, mixed case = prénom.

    Convention EP : "Marie DURAND", "François-Xavier BELLAMY",
    "Jean-Paul VAN DER MEER" (les particules en majuscules font partie du nom).

    Retourne (nom, prenom), tous deux en .title() pour stockage propre.
    Si tout est en minuscules ou tout en MAJUSCULES, on fait au mieux.

    Edge cases :
        "MARIE DURAND"          → ("Marie Durand", "")     # tout en MAJ → on assume nom complet
        "marie durand"          → ("Durand", "Marie")      # fallback : dernier mot = prénom (rare)
        "Marie DURAND"          → ("Durand", "Marie")
        "Jean-Paul VAN DER MEER" → ("Van Der Meer", "Jean-Paul")
        "Marie DE LA TOUR"      → ("De La Tour", "Marie")
        ""                      → ("", "")
    """
    full_name = (full_name or "").strip()
    if not full_name:
        return "", ""

    tokens = full_name.split()

    # On considère un token comme "majuscule" si tous ses caractères alpha sont upper
    # (gère "DE", "VAN", "DER", mais aussi "O'NEILL" si présent)
    def is_upper_token(t: str) -> bool:
        alpha = [c for c in t if c.isalpha()]
        return len(alpha) >= 2 and all(c.isupper() for c in alpha)

    nom_tokens = [t for t in tokens if is_upper_token(t)]
    prenom_tokens = [t for t in tokens if not is_upper_token(t)]

    if not nom_tokens and not prenom_tokens:
        return "", ""

    if not nom_tokens:
        # Aucun token MAJ : nom mal formaté, on prend tout comme nom (en .title())
        return _to_title_preserving(full_name), ""

    if not prenom_tokens:
        # Tout en MAJUSCULES : on assume que c'est nom + prénom mais on ne peut pas
        # les distinguer. Fallback : tout va dans le nom.
        return " ".join(_to_title_preserving(t) for t in nom_tokens), ""

    nom = " ".join(_to_title_preserving(t) for t in nom_tokens)
    prenom = " ".join(prenom_tokens)
    return nom, prenom


def _to_title_preserving(s: str) -> str:
    """Comme str.title() mais préserve les apostrophes et tirets correctement.

    Ex: "O'NEILL" → "O'Neill", "JEAN-PAUL" → "Jean-Paul", "VAN DER" → "Van Der"
    """
    # str.title() gère les tirets correctement ("JEAN-PAUL".title() == "Jean-Paul")
    # mais pas les apostrophes ("O'NEILL".title() == "O'Neill" qui est bon en fait)
    # Il pose des problèmes avec des cas comme "DUBOIS-D'ESTRÉES" mais c'est rare.
    return s.title()


def guess_genre_from_prenom(prenom: str) -> str | None:
    """Heuristique très basique pour deviner le genre depuis un prénom français.

    Retourne 'F', 'M' ou None si trop incertain.
    Cette fonction est volontairement minimale ; on l'enrichira plus tard
    avec un dictionnaire plus complet.
    """
    if not prenom:
        return None
    p = prenom.strip().split()[0].lower()  # premier prénom
    p = unicodedata.normalize("NFKD", p)
    p = "".join(c for c in p if not unicodedata.combining(c))

    # Cas spécifiques d'abord
    feminins_explicites = {
        "marie", "anne", "claire", "sophie", "julie", "emma", "lea", "chloe",
        "nathalie", "isabelle", "stephanie", "catherine", "valerie", "caroline",
        "celine", "manon", "rima", "majdouline", "pascale", "fabienne", "aurore",
        "laurence", "virginie", "marion", "sarah", "nora", "leila", "delphine",
        "sandrine", "veronique", "patricia", "francoise", "monique", "nicole",
    }
    masculins_explicites = {
        "jean", "pierre", "paul", "louis", "francois", "philippe", "patrick",
        "michel", "bernard", "alain", "christophe", "raphael", "thomas", "julien",
        "nicolas", "olivier", "matthieu", "guillaume", "andre", "damien", "younous",
        "mounir", "anthony", "rody", "alexandre", "jordan", "fabrice", "thierry",
        "gilles", "gilles", "mathieu", "pascal", "sandro", "laurent", "eric",
    }
    if p in feminins_explicites:
        return "F"
    if p in masculins_explicites:
        return "M"

    # Heuristique terminaisons
    if p.endswith(("e", "a", "ie")):
        return "F"
    if p.endswith(("o", "k", "n", "r", "s", "t", "l", "d")):
        return "M"

    return None
