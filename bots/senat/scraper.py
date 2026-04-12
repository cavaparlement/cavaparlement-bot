import pdfplumber
import requests
import json
import csv
import io
import unicodedata
import re
from pathlib import Path

PDF_URL = "https://www.senat.fr/pubagas/liste_senateurs_collaborateurs.pdf"

SENAT_GROUPE_MAP = {
    "Les Républicains":                                            ("LR",     "Les Républicains"),
    "Rassemblement National":                                      ("RN",     "Rassemblement National"),
    "Socialiste, Écologiste et Républicain":                       ("SER",    "Socialiste, Écologiste et Républicain"),
    "Rassemblement des démocrates, progressistes et indépendants": ("RDPI",   "Rassemblement des démocrates, progressistes et indépendants"),
    "Union Centriste":                                             ("UC",     "Union Centriste"),
    "Rassemblement Démocratique et Social Européen":               ("RDSE",   "Rassemblement Démocratique et Social Européen"),
    "Les Indépendants":                                            ("INDEP",  "Les Indépendants — République et Territoires"),
    "Les Indépendants — République et Territoires":                ("INDEP",  "Les Indépendants — République et Territoires"),
    "Groupe Écologiste — Solidarité et Territoires":               ("GEST",   "Groupe Écologiste — Solidarité et Territoires"),
    "Communiste Républicain Citoyen et Écologiste — Kanaky":       ("CRCE-K", "Communiste Républicain Citoyen et Écologiste — Kanaky"),
    "Non inscrit":                                                 ("NI",     "Non inscrit"),
    "CRCE-K":                                                      ("CRCE-K", "Communiste Républicain Citoyen et Écologiste — Kanaky"),
    "GEST":                                                        ("GEST",   "Groupe Écologiste — Solidarité et Territoires"),
    "NI":                                                          ("NI",     "Non inscrit"),
}

def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(sorted(s.split()))

def download_pdf(path="data/senat/collab_today.pdf"):
    r = requests.get(PDF_URL, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    return path

def parse_pdf(pdf_path) -> dict:
    result = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            if not words:
                continue
            lines = {}
            for w in words:
                y = round(w["top"] / 3) * 3
                lines.setdefault(y, []).append(w)
            current_senator = None
            for y in sorted(lines.keys()):
                row_words = sorted(lines[y], key=lambda w: w["x0"])
                left_words  = [w for w in row_words if w["x0"] < 260]
                right_words = [w for w in row_words if w["x0"] >= 260]
                left_text  = " ".join(w["text"] for w in left_words).strip()
                right_text = " ".join(w["text"] for w in right_words).strip()
                if left_text in ("A.G.A.S.", "Employeur", "Liste") or "collaborateur" in left_text.lower():
                    continue
                if left_text and any(left_text.startswith(p) for p in ["M.", "Mme"]):
                    current_senator = left_text
                    result.setdefault(current_senator, [])
                if right_text and any(right_text.startswith(p) for p in ["M.", "Mme"]) and current_senator:
                    result[current_senator].append(right_text)
    return result

def save_snapshot(data: dict, path="data/senat/snapshot.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_snapshot(path="data/senat/snapshot.json") -> dict:
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def fetch_senateurs_info() -> dict:
    info = {}
    try:
        url = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        raw = r.content.decode("latin-1", errors="replace")

        # Sauter les lignes de commentaire (commencent par %)
        lines = [l for l in raw.splitlines() if not l.startswith("%")]
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=",")
        rows = list(reader)

        # Filtrer les sénateurs actifs uniquement
        actifs = [row for row in rows if row.get("État", "").strip() not in ("ANCIEN", "")]
        print(f"CSV Sénat: {len(actifs)} sénateurs actifs / {len(rows)} total")

        # Construire un index normalisé nom+prénom → données
        sen_idx = {}
        for row in actifs:
            nom     = row.get("Nom usuel", "").strip()
            prenom  = row.get("Prénom usuel", "").strip()
            groupe  = row.get("Groupe politique", "").strip()
            mat     = row.get("Matricule", "").strip()
            circo   = row.get("Circonscription", "").strip()
            qualite = row.get("Qualité", "").strip()
            if not nom or not groupe:
                continue
            civ = "Mme" if qualite in ("Mme", "Madame") else "M."
            sigle, label = SENAT_GROUPE_MAP.get(groupe, ("", groupe))
            sen_idx[_norm(nom + " " + prenom)] = {
                "cle_csv": f"{civ} {nom} {prenom}",
                "groupe": sigle,
                "groupe_label": label,
                "departement": circo,
                "matricule": mat,
                "en_exercice": True,
            }

        # Charger l'existant pour matcher les clés du snapshot (format "Mme NOM Prénom")
        existing = {}
        try:
            with open("data/senat/senateurs_info.json", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

        # Partir de l'existant et enrichir chaque entrée
        if existing:
            for nom_cle, data in existing.items():
                nom_clean = re.sub(r"^(Mme|M\.)\s+", "", nom_cle).strip()
                match = sen_idx.get(_norm(nom_clean))
                if match:
                    entry = {k: v for k, v in match.items() if k != "cle_csv"}
                    data.update(entry)
                    info[nom_cle] = data
                else:
                    info[nom_cle] = data
        else:
            # Premier run : utiliser les clés du CSV directement
            for entry in sen_idx.values():
                cle = entry.pop("cle_csv")
                info[cle] = entry

    except Exception as e:
        print("Erreur CSV Sénat: " + str(e))
        # Fallback : retourner l'existant si disponible
        try:
            with open("data/senat/senateurs_info.json", encoding="utf-8") as f:
                info = json.load(f)
            print("Fallback: utilisation de senateurs_info.json existant")
        except Exception:
            pass

    enrichis = sum(1 for v in info.values() if v.get("groupe_label"))
    print(f"fetch_senateurs_info: {enrichis}/{len(info)} avec groupe")
    return info
