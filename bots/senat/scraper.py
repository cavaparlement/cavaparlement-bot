import pdfplumber
import requests
import json
from pathlib import Path

PDF_URL = "https://www.senat.fr/pubagas/liste_senateurs_collaborateurs.pdf"

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
        r = requests.get("https://www.nossenateurs.fr/senateurs/json", timeout=30)
        r.raise_for_status()
        data = r.json()
        for s in data.get("senateurs", []):
            sen = s.get("senateur", {})
            nom = (sen.get("nom", "") + " " + sen.get("prenom", "")).strip().upper()
            groupe_sigle = sen.get("groupe_sigle", "")
            groupe_label = sen.get("groupe_label", "") or sen.get("groupe", "")
            dept = sen.get("circo", "")
            info[nom] = {
                "groupe": groupe_sigle,
                "groupe_label": groupe_label,
                "departement": dept
            }
    except Exception as e:
        print("Erreur API nossenateurs: " + str(e))
    return info
