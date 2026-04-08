import os, json, requests, time, datetime, random
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GITHUB_HISTORY_URL = os.getenv("GITHUB_HISTORY_URL", "")
GITHUB_SNAPSHOT_SENAT_URL = os.getenv("GITHUB_SNAPSHOT_SENAT_URL", "")
GITHUB_SNAPSHOT_AN_URL = os.getenv("GITHUB_SNAPSHOT_AN_URL", "")
GITHUB_SENATEURS_INFO_URL = os.getenv("GITHUB_SENATEURS_INFO_URL", "")
GITHUB_DEPUTES_INFO_URL = os.getenv("GITHUB_DEPUTES_INFO_URL", "")

client = OpenAI(api_key=OPENAI_API_KEY)
BASE_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"

CHOICES_CACHE = {}

EXEMPLES_NOMS = [
    "Dantec", "Retailleau", "Buffet", "Jadot", "Faure",
    "Rossignol", "Kanner", "Larcher", "Brossat", "Salmon",
    "Rousseau", "Glucksmann", "Bayrou", "Ciotti", "Bellamy"
]

def tg(method, **kwargs):
    try:
        r = requests.post(BASE_URL + method, json=kwargs, timeout=60)
        return r.json()
    except Exception as e:
        print("Erreur tg " + method + ": " + str(e))
        return {}

def tg_buttons(chat_id, text, buttons):
    keyboard = {"inline_keyboard": [[{"text": b[0], "callback_data": b[1]}] for b in buttons]}
    try:
        r = requests.post(BASE_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": keyboard,
        }, timeout=60)
        return r.json()
    except Exception as e:
        print("Erreur tg_buttons: " + str(e))
        return {}

def save_choices(chat_id, choices):
    CHOICES_CACHE[str(chat_id)] = choices

def get_choice(chat_id, index):
    return CHOICES_CACHE.get(str(chat_id), {}).get(index)

def get_updates(offset):
    try:
        params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
        if offset:
            params["offset"] = offset
        r = requests.post(BASE_URL + "getUpdates", json=params, timeout=40)
        return r.json()
    except Exception as e:
        print("Erreur getUpdates: " + str(e))
        return {}

def fetch_json(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Erreur fetch_json " + url + ": " + str(e))
        return None

def fetch_data():
    history = fetch_json(GITHUB_HISTORY_URL) or []
    snapshot_senat = fetch_json(GITHUB_SNAPSHOT_SENAT_URL) or {}
    snapshot_an = fetch_json(GITHUB_SNAPSHOT_AN_URL) or {}
    senateurs_info = fetch_json(GITHUB_SENATEURS_INFO_URL) or {}
    deputes_info = fetch_json(GITHUB_DEPUTES_INFO_URL) or {}
    return history, snapshot_senat, snapshot_an, senateurs_info, deputes_info

def analyse_question(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[
                {
                    "role": "system",
                    "content": "Tu analyses des questions en français sur les collaborateurs parlementaires. Réponds UNIQUEMENT en JSON avec ce format : {\"intent\": \"mouvements\" | \"collaborateurs\" | \"historique_jour\" | \"stats\" | \"historique_recent\" | \"aide\", \"nom\": \"NOM DE FAMILLE EN MAJUSCULES ou null\", \"chambre\": \"senat\" | \"assemblee\" | \"les deux\" | null}. Le nom doit être UNIQUEMENT le nom de famille, pas le prénom. Exemples: 'mouvements pour Dupont' -> intent=mouvements nom=DUPONT. 'collaborateurs de Martin' -> intent=collaborateurs nom=MARTIN. 'collaborateurs de Jean Dupont' -> intent=collaborateurs nom=DUPONT. 'mouvements du jour' -> intent=historique_jour. 'stats par groupe' -> intent=stats. 'derniers mouvements' -> intent=historique_recent. 'aide' ou 'help' ou 'bonjour' ou '/start' -> intent=aide."
                },
                {"role": "user", "content": message}
            ]
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print("Erreur analyse: " + str(e))
        return {"intent": "aide", "nom": None, "chambre": None}

def get_emoji(t):
    if t in ["arrivee", "arrivée"]:
        return "📥"
    if t in ["depart", "départ"]:
        return "📤"
    return "🔁"

def extraire_nom_famille(cle):
    cle_clean = cle.strip()
    for prefix in ["Mme ", "M. ", "MME ", "M."]:
        if cle_clean.startswith(prefix):
            cle_clean = cle_clean[len(prefix):].strip()
            break
    mots = cle_clean.split()
    if not mots:
        return ""
    noms = []
    for m in mots:
        if m == m.upper() and len(m) > 1:
            noms.append(m)
        else:
            break
    if noms:
        return " ".join(noms)
    return mots[0].upper()

def match_strict(nom, cle):
    nom_famille = extraire_nom_famille(cle)
    mots_recherche = [m for m in nom.upper().split() if len(m) > 1]
    return all(m in nom_famille.split() for m in mots_recherche)

def match_partiel(nom, cle):
    nom_famille = extraire_nom_famille(cle)
    mots_recherche = [m for m in nom.upper().split() if len(m) > 1]
    noms_famille = nom_famille.split()
    return any(m in noms_famille for m in mots_recherche)

def find_keys(nom, snapshot):
    resultats = [k for k in snapshot if match_strict(nom, k)]
    if not resultats:
        resultats = [k for k in snapshot if match_partiel(nom, k)]
    return resultats

def format_info(groupe, localisation):
    info = ""
    if groupe:
        info += groupe
    if localisation:
        info += (" · " if info else "") + localisation
    return info

def format_circo(dept, circo):
    if not dept:
        return ""
    if not circo:
        return dept
    n = int(circo) if str(circo).isdigit() else 0
    if n == 1:
        suffix = "1ère"
    else:
        suffix = str(n) + "e"
    return suffix + " circonscription de la " + dept

def get_info_senat(key, senateurs_info):
    cle = key.upper().replace("M. ", "").replace("MME ", "").strip()
    if cle in senateurs_info:
        return senateurs_info[cle]
    mots = [m for m in cle.split() if len(m) > 2]
    for k, v in senateurs_info.items():
        if all(m in k for m in mots):
            return v
    return {}

def get_info_an(key, deputes_info):
    cle = key.upper().strip()
    if cle in deputes_info:
        return deputes_info[cle]
    mots = [m for m in cle.split() if len(m) > 2]
    for k, v in deputes_info.items():
        if all(m in k for m in mots):
            return v
    return {}

def afficher_collabs_par_key(chat_id, chambre, key, snapshot_senat, snapshot_an, senateurs_info, deputes_info):
    snapshot = snapshot_senat if chambre == "SENAT" else snapshot_an
    collabs = snapshot.get(key, [])
    chambre_label = "Sénat" if chambre == "SENAT" else "Assemblée nationale"

    if not collabs:
        tg("sendMessage", chat_id=chat_id, text="Aucun collaborateur trouvé pour " + key + ".")
        return

    if chambre == "SENAT":
        info_parl = get_info_senat(key, senateurs_info)
        groupe = info_parl.get("groupe", "")
        dept = info_parl.get("departement", "")
        localisation = dept
    else:
        info_parl = get_info_an(key, deputes_info)
        groupe = info_parl.get("groupe", "")
        dept = info_parl.get("departement", "")
        circo = info_parl.get("circo", "")
        localisation = format_circo(dept, circo)

    info = format_info(groupe, localisation)
    titre_info = " _(" + info + ")_" if info else ""

    lignes = ["👥 *Collaborateurs de " + key + "* :\n"]
    lignes.append("🏛 *" + chambre_label + "*" + titre_info + " :")
    for c in collabs:
        lignes.append("  • " + c)
    tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

def repondre(chat_id, message):
    history, snapshot_senat, snapshot_an, senateurs_info, deputes_info = fetch_data()
    analyse = analyse_question(message)
    intent = analyse.get("intent")
    nom = analyse.get("nom")
    today = datetime.date.today().isoformat()
    today_fr = datetime.date.today().strftime("%d/%m/%Y")

    if intent == "mouvements" and nom:
        resultats = [
            e for e in history
            if nom in (
                e.get("parlementaire", "") +
                e.get("parlementaire_from", "") +
                e.get("parlementaire_to", "")
            ).upper()
        ]
        if not resultats:
            tg("sendMessage", chat_id=chat_id,
               text="🔍 Aucun mouvement trouvé pour *" + nom + "*.\n\nEssaie avec un autre nom ou vérifie l'orthographe !",
               parse_mode="Markdown")
            return
        lignes = ["📋 *Mouvements pour " + nom + "* (" + str(len(resultats)) + " au total)\n"]
        for e in resultats[-10:]:
            chambre = "Sénat" if e["chambre"] == "senat" else "An"
            dept = e.get("departement", "")
            circo = e.get("circo", "")
            groupe = e.get("groupe", "")
            localisation = dept if e["chambre"] == "senat" else format_circo(dept, circo)
            info = format_info(groupe, localisation)
            parl = e.get("parlementaire", e.get("parlementaire_to", ""))
            parl_txt = parl + (" _(" + info + ")_" if info else "")
            lignes.append(get_emoji(e["type"]) + " " + e["date"] + " · " + chambre + "\n   👤 " + e["collaborateur"] + "\n   ↳ " + parl_txt)
        if len(resultats) > 10:
            lignes.append("\n_(10 derniers sur " + str(len(resultats)) + " affichés)_")
        tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

    elif intent == "collaborateurs" and nom:
        keys_senat = find_keys(nom, snapshot_senat)
        keys_an = find_keys(nom, snapshot_an)
        tous_les_keys = keys_senat + keys_an

        if len(tous_les_keys) > 1:
            noms_famille = set()
            for k in tous_les_keys:
                noms_famille.add(extraire_nom_famille(k))
            if len(noms_famille) == 1:
                choices = {}
                boutons = []
                idx = 0
                for k in keys_senat:
                    index = str(idx)
                    choices[index] = ("SENAT", k)
                    boutons.append((k + " (Sénat)", index))
                    idx += 1
                for k in keys_an:
                    index = str(idx)
                    choices[index] = ("AN", k)
                    boutons.append((k + " (An)", index))
                    idx += 1
                save_choices(chat_id, choices)
                tg_buttons(chat_id,
                    "⚠️ Plusieurs parlementaires trouvés pour " + nom + " - lequel ?",
                    boutons)
                return

        if not keys_senat and not keys_an:
            tg("sendMessage", chat_id=chat_id,
               text="🔍 Aucun collaborateur trouvé pour *" + nom + "*.\n\nEssaie avec un autre nom ou vérifie l'orthographe !",
               parse_mode="Markdown")
            return

        lignes = ["👥 *Collaborateurs actuels de " + nom + "* :\n"]

        for key in keys_senat:
            collabs = snapshot_senat[key]
            info_parl = get_info_senat(key, senateurs_info)
            groupe = info_parl.get("groupe", "")
            dept = info_parl.get("departement", "")
            info = format_info(groupe, dept)
            titre = "🏛 *Sénat* · " + key + (" _(" + info + ")_" if info else "") + " :"
            lignes.append(titre)
            for c in collabs:
                lignes.append("  • " + c)

        for key in keys_an:
            collabs = snapshot_an[key]
            info_parl = get_info_an(key, deputes_info)
            groupe = info_parl.get("groupe", "")
            dept = info_parl.get("departement", "")
            circo = info_parl.get("circo", "")
            circo_txt = format_circo(dept, circo)
            info = format_info(groupe, circo_txt)
            titre = "🏛 *Assemblée nationale* · " + key + (" _(" + info + ")_" if info else "") + " :"
            lignes.append(titre)
            for c in collabs:
                lignes.append("  • " + c)

        tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

    elif intent == "historique_jour":
        resultats = [e for e in history if e["date"] == today]
        if not resultats:
            tg("sendMessage", chat_id=chat_id,
               text="📅 Aucun mouvement détecté aujourd'hui (" + today_fr + ").\n\nReviens demain matin !")
            return
        lignes = ["📅 *Mouvements du " + today_fr + "* (" + str(len(resultats)) + ") :\n"]
        for e in resultats:
            chambre = "Sénat" if e["chambre"] == "senat" else "An"
            dept = e.get("departement", "")
            circo = e.get("circo", "")
            groupe = e.get("groupe", "")
            localisation = dept if e["chambre"] == "senat" else format_circo(dept, circo)
            info = format_info(groupe, localisation)
            parl = e.get("parlementaire", e.get("parlementaire_to", ""))
            parl_txt = parl + (" _(" + info + ")_" if info else "")
            lignes.append(get_emoji(e["type"]) + " " + e["collaborateur"] + "\n   ↳ " + parl_txt + " (" + chambre + ")")
        tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

    elif intent == "historique_recent":
        resultats = history[-15:]
        if not resultats:
            tg("sendMessage", chat_id=chat_id,
               text="🕐 Pas encore de mouvements enregistrés.\n\nLe bot vient d'être lancé, reviens dans quelques jours !")
            return
        lignes = ["🕐 *15 derniers mouvements* :\n"]
        for e in resultats:
            chambre = "Sénat" if e["chambre"] == "senat" else "An"
            dept = e.get("departement", "")
            circo = e.get("circo", "")
            groupe = e.get("groupe", "")
            localisation = dept if e["chambre"] == "senat" else format_circo(dept, circo)
            info = format_info(groupe, localisation)
            parl = e.get("parlementaire", e.get("parlementaire_to", ""))
            parl_txt = parl + (" _(" + info + ")_" if info else "")
            lignes.append(get_emoji(e["type"]) + " " + e["date"] + " · " + e["collaborateur"] + "\n   ↳ " + parl_txt + " (" + chambre + ")")
        tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

    elif intent == "stats":
        from collections import Counter
        groupes = Counter(e.get("groupe", "N/A") for e in history if e.get("groupe"))
        if not groupes:
            tg("sendMessage", chat_id=chat_id,
               text="📊 Pas encore assez de données pour les stats.\n\nReviens dans quelques jours !")
            return
        lignes = ["📊 *Mouvements par groupe politique* (depuis le début) :\n"]
        for groupe, count in groupes.most_common(10):
            barre = "█" * min(count, 10)
            lignes.append(barre + " " + groupe + " : " + str(count))
        tg("sendMessage", chat_id=chat_id, text="\n".join(lignes), parse_mode="Markdown")

    else:
        exemple = random.choice(EXEMPLES_NOMS)
        tg("sendMessage", chat_id=chat_id, text=(
            "👋 Bonjour ! Je suis le bot Ca va le Parlement ?\n\n"
            "Je surveille les mouvements de collaborateurs au Sénat et à l'Assemblée nationale.\n\n"
            "Voici ce que tu peux me demander :\n\n"
            "📋 mouvements pour [nom]\n"
            "👥 collaborateurs de [nom]\n"
            "📅 mouvements du jour\n"
            "🕐 derniers mouvements\n"
            "📊 stats par groupe\n\n"
            "Exemple : collaborateurs de " + exemple
        ))

def main():
    print("Bot démarré, polling...")
    offset = None
    while True:
        try:
            result = get_updates(offset)
            updates = result.get("result", [])
            for update in updates:
                offset = update["update_id"] + 1

                if "message" in update:
                    message = update["message"]
                    chat = message.get("chat", {})
                    if chat.get("type") != "private":
                        continue
                    text = message.get("text", "").strip()
                    chat_id = chat["id"]
                    if text:
                        print("Message reçu : " + text)
                        try:
                            repondre(chat_id, text)
                        except Exception as e:
                            print("Erreur repondre : " + str(e))
                            tg("sendMessage", chat_id=chat_id,
                               text="⚠️ Une erreur est survenue, réessaie dans quelques instants.")

                elif "callback_query" in update:
                    cb = update["callback_query"]
                    chat_id = cb["message"]["chat"]["id"]
                    index = cb.get("data", "").strip()
                    cb_id = cb["id"]
                    tg("answerCallbackQuery", callback_query_id=cb_id)
                    print("Bouton cliqué, index : " + index)
                    try:
                        choice = get_choice(chat_id, index)
                        if choice:
                            chambre, key = choice
                            _, snapshot_senat, snapshot_an, senateurs_info, deputes_info = fetch_data()
                            afficher_collabs_par_key(chat_id, chambre, key, snapshot_senat, snapshot_an, senateurs_info, deputes_info)
                        else:
                            tg("sendMessage", chat_id=chat_id,
                               text="⚠️ Session expirée, réessaie ta recherche.")
                    except Exception as e:
                        print("Erreur callback : " + str(e))
                        tg("sendMessage", chat_id=chat_id,
                           text="⚠️ Une erreur est survenue, réessaie.")

        except Exception as e:
            print("Erreur boucle principale : " + str(e))
            time.sleep(5)

if __name__ == "__main__":
    main()
