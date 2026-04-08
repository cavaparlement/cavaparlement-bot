# ─── Sénat ────────────────────────────────────────────────────────────────────

SENAT_GROUP_SHORT = {
    "Groupe Les Républicains": "LR",
    "Groupe Union Centriste": "UC",
    "Groupe Socialiste, Écologiste et Républicain": "SER",
    "Groupe Communiste Républicain Citoyen et Écologiste - Kanaky": "CRCE-K",
    "Groupe Écologiste - Solidarité et Territoires": "EST",
    "Groupe du Rassemblement Démocratique et Social Européen": "RDSE",
    "Groupe Rassemblement des démocrates, progressistes et indépendants": "RDPI",
    "Groupe Les Indépendants - République et Territoires": "LIRT",
}

SENAT_GROUP_EMOJI = {
    "Groupe Les Républicains": "🔵",
    "Groupe Union Centriste": "🟠",
    "Groupe Socialiste, Écologiste et Républicain": "🌹",
    "Groupe Communiste Républicain Citoyen et Écologiste - Kanaky": "🔴",
    "Groupe Écologiste - Solidarité et Territoires": "🌿",
    "Groupe du Rassemblement Démocratique et Social Européen": "🟡",
    "Groupe Rassemblement des démocrates, progressistes et indépendants": "🟣",
    "Groupe Les Indépendants - République et Territoires": "⚪",
}

SENAT_GROUP_HASHTAG = {
    "Groupe Les Républicains": "LesRepublicains",
    "Groupe Union Centriste": "UnionCentriste",
    "Groupe Socialiste, Écologiste et Républicain": "GroupeSER",
    "Groupe Communiste Républicain Citoyen et Écologiste - Kanaky": "CRCE",
    "Groupe Écologiste - Solidarité et Territoires": "Ecologistes",
    "Groupe du Rassemblement Démocratique et Social Européen": "RDSE",
    "Groupe Rassemblement des démocrates, progressistes et indépendants": "RDPI",
    "Groupe Les Indépendants - République et Territoires": "LesIndependants",
}

# ─── Assemblée nationale ──────────────────────────────────────────────────────

AN_GROUPES = {
    "RN":    {"tag": "#RN",    "emoji": "🔵"},
    "NFP":   {"tag": "#NFP",   "emoji": "🌹"},
    "LFI":   {"tag": "#LFI",   "emoji": "🔴"},
    "SOC":   {"tag": "#PS",    "emoji": "🌹"},
    "RE":    {"tag": "#RE",    "emoji": "🟡"},
    "MODEM": {"tag": "#MoDem", "emoji": "🟡"},
    "HOR":   {"tag": "#HOR",   "emoji": "🟠"},
    "LR":    {"tag": "#LR",    "emoji": "🔵"},
    "LIOT":  {"tag": "#LIOT",  "emoji": "🟤"},
    "GDR":   {"tag": "#GDR",   "emoji": "🔴"},
    "ECOLO": {"tag": "#GEST",  "emoji": "🟢"},
    "NI":    {"tag": "",       "emoji": "⚪️"},
}


def get_an_groupe_info(groupe_sigle: str) -> dict:
    if groupe_sigle in AN_GROUPES:
        return AN_GROUPES[groupe_sigle]
    for key, val in AN_GROUPES.items():
        if key.lower() in groupe_sigle.lower():
            return val
    return {"tag": "", "emoji": "⚪️"}


# ─── Parlement européen ───────────────────────────────────────────────────────

EP_GROUP_LABELS = {
    "PPE":       "PPE",
    "SD":        "S&D",
    "S-D":       "S&D",
    "RENEW":     "Renew Europe",
    "VERTS-ALE": "Verts/ALE",
    "ECR":       "ECR",
    "THE-LEFT":  "La Gauche",
    "LEFT":      "La Gauche",
    "ESN":       "ESN",
    "PFE":       "Patriotes pour l'Europe",
    "NI":        "Non-inscrit·e",
}

EP_GROUP_EMOJIS = {
    "PPE":       "🔵",
    "SD":        "🔴",
    "S-D":       "🔴",
    "RENEW":     "🟡",
    "VERTS-ALE": "🟢",
    "ECR":       "🟤",
    "THE-LEFT":  "☭",
    "LEFT":      "☭",
    "ESN":       "⚫",
    "PFE":       "🟠",
    "NI":        "⚪",
}

EP_TYPE_EMOJIS = {
    "accredited assistants":            "🏛️",
    "accredited assistants (grouping)": "🏛️",
    "local assistants":                 "📍",
    "local assistants (grouping)":      "📍",
    "specialised service providers":    "🔧",
    "paying agents":                    "💶",
    "paying agents (grouping)":         "💶",
    "trainees":                         "🎓",
    "assistants to the vice-presidency/to the quaestorate": "⭐",
}

EP_TYPE_LABELS_FR = {
    "accredited assistants":            "Accrédité·e (Bruxelles/Strasbourg)",
    "accredited assistants (grouping)": "Accrédité·e mutualisé·e",
    "local assistants":                 "Assistant·e local·e (France)",
    "local assistants (grouping)":      "Assistant·e local·e mutualisé·e",
    "specialised service providers":    "Prestataire de services",
    "paying agents":                    "Agent payeur",
    "paying agents (grouping)":         "Agent payeur mutualisé",
    "trainees":                         "Stagiaire",
    "assistants to the vice-presidency/to the quaestorate": "Assistant·e VP/Questeur",
}


def format_ep_group(group_key: str) -> tuple:
    key = group_key.upper().replace("_", "-")
    emoji = EP_GROUP_EMOJIS.get(key, "🏛️")
    label = EP_GROUP_LABELS.get(key, group_key if group_key else "Groupe inconnu")
    return emoji, label
