"""
scripts/fix_genres.py — v2 avec fallback OpenAI
1. Dictionnaire étendu + terminaisons (rapide, gratuit)
2. Pour les "inconnu" restants : appel GPT-4o-mini en batch de 50
"""
import os, re, json, unicodedata
from supabase import create_client
from openai import OpenAI

sb  = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
gpt = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── Dictionnaire prénoms ──────────────────────────────────────────────────────
FEMMES = set("""marie anne isabelle sophie claire julie laura celine nathalie valerie
florence sandrine aurelie laurence caroline sylvie virginie martine delphine
stephanie amelie camille lucie alice emma charlotte manon ines lea zoe pauline
mathilde emilie helene catherine francoise dominique brigitte nicole monique
corinne veronique nadine annick chantal patricia michele cecile genevieve
elise marguerite louise victoire rose madeleine bernadette colette danielle
simone jeanne denise yvette mireille josette pierrette georgette henriette
renee suzanne therese joelle adeline agnes alexia aline alma amandine ambre
anaelle anais anastasia angele angelique anna annabelle apolline ariane
assia astrid audrey aurore axelle beatrice benedicte betty blandine capucine
carla carole cassandre celeste chloe christelle clara claudine clemence
clotilde coraline coralie cyrielle deborah diane dorothee eleonore elisa
elisabeth ella elena emeline estelle esther eugenie eva eve fanny fatima
faustine felicite flore flora flavie france frederique gabrielle gaelle
garance geraldine gladys grace gwenaelle gwenola hannah hortense imane
ingrid irene iris jade jasmine jessica joanna josephine judith julia
juliette karine katia kristelle laetitia laure laurie leonie leila lena
lilou lina linda lisa lise lola lorraine lou louane louisa luce lucile
lucille luna lydie maelle maelys maeva magali malika marine marion marlene
marthe maryse mathilde maud maureen maya melodie morgane muriel nadia
naomi natacha noemie oceane olivia ornella pascale patricia perrine
priscilla rachel rebecca regine roxane sabine salome sandra sara sarah
selena selma sonia tiphaine valentine vanessa victoria violette viviane
yasmine yvonne zahra zara zelie manuela noura rania samira amira asma
chaima dalia dounia fatou hadja khadija mariam nawel nora randa rima
siham souad wahiba zineb odile odette arlette colette huguette evelyne
nadege noemie clemence lola morgane eva lucie inès lea zoe chloe jade
emma alice charlotte ambre clara julia camille manon pauline mathilde""".split())

HOMMES = set("""jean pierre michel andre claude philippe patrick jacques francois nicolas
olivier laurent thierry christophe xavier guillaume thomas alexandre julien
maxime raphael antoine mathieu sebastien frederic eric alain gerard bernard
robert henri louis paul rene marcel roger gilles serge marc emmanuel yves
charles denis stephane benoit arnaud fabrice pascal vincent remi luc
thibault damien david cedric gregoire anthony kevin gael hugo nathan
clement baptiste adrien romain quentin simon alexis florian lucas leo
baptiste bastien mathis mateo theo noah noa ethan adam mael gabin antonin
titouan corentin erwan alan ronan yoann loic gwenael pierrick cyril
matthieu matthias stanislas amaury valentin victor florent samuel benjamin
joachim edouard maximilien bertrand felix august augustin basile etienne
gauthier gonzague leon leopold lucien maxence norbert octave oscar pascal
patrice pierre prosper raoul regis renaud roland sylvain timothee tristan
ugo ulric valery vivien wilfried xavier yann yannis abdel amine ayoub
bilal farid hassan ibrahim karim khalid mehdi nassim omar rachid said
sofiane yanis youssef tanguy gaetan thibaut noe elie eliott titouan
sylvain damien ludovic florent franck frederic gerald herve hugo jerome
lionel mickael nathanael patrice philippe quentin remi romain rudy samuel
steeve stephane thierry tristan xavier yannick patrice pascal christian
didier dominique raymond gerard robert raymond fernand armand gustave
emile gaston leon edmond albert ernest alfred georges lucien fernand
clement achille aristide antonin eustache hippolyte paul-emile
jean-luc jean-pierre jean-paul jean-claude jean-marie jean-michel
jean-marc jean-louis jean-baptiste jean-christophe jean-francois
jean-noel jean-philippe jean-yves jean-remi jean-sebastien
pierre-yves pierre-alain pierre-marie pierre-olivier pierre-louis
francois-xavier marc-antoine charles-edouard anne-pierre""".split())

FEM_END  = ("ine","ette","elle","ee","ane","ance","ence","ise","ice","ille","oise","aine","ienne","ienne")
MASC_END = ("ard","ert","and","ent","ien","ois","eux","oud","aud","ald","in","on","an","oul")

def norm(s):
    nfd = unicodedata.normalize("NFD", s or "")
    asc = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return asc.lower().strip()

def detect_dict(nom_complet):
    s = (nom_complet or "").strip()
    sl = s.lower()
    if sl.startswith("mme") or sl.startswith("mme "): return "F"
    if sl.startswith("m. ") or sl[:2] == "m ": return "M"
    parts = s.split()
    candidates = [parts[0]] + ([parts[-1]] if len(parts) > 1 else [])
    for p in candidates:
        for pp in re.split(r"[-\s]", norm(p)):
            if pp in FEMMES: return "F"
            if pp in HOMMES: return "M"
    for p in candidates:
        for pp in re.split(r"[-\s]", norm(p)):
            if any(pp.endswith(e) for e in FEM_END):  return "F"
            if any(pp.endswith(e) for e in MASC_END): return "M"
    return "inconnu"


# ── GPT fallback ──────────────────────────────────────────────────────────────
def detect_gpt_batch(noms: list[str]) -> dict[str, str]:
    """Envoie un batch de noms à GPT-4o-mini. Retourne {nom: 'F'|'M'|'inconnu'}"""
    if not noms:
        return {}

    prompt = (
        "Tu es un expert en prénoms français et internationaux.\n"
        "Pour chaque nom complet ci-dessous, détermine le genre de la personne : F (féminin), M (masculin), ou ? (inconnu/ambigu).\n"
        "Réponds UNIQUEMENT avec un objet JSON : {\"Nom Complet\": \"F\"|\"M\"|\"?\"}\n"
        "Ne rajoute aucun texte avant ou après le JSON.\n\n"
        "Noms :\n" + "\n".join(f"- {n}" for n in noms)
    )

    resp = gpt.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
        return {k: ("F" if v == "F" else "M" if v == "M" else "inconnu")
                for k, v in data.items()}
    except Exception as e:
        print(f"  Erreur parse GPT : {e}\n  Réponse : {raw[:200]}")
        return {}


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    # 1. Charger tous les inconnus
    resp = (
        sb.table("collaborateurs")
        .select("id,nom_complet,prenom,genre")
        .or_("genre.eq.inconnu,genre.is.null")
        .limit(5000)
        .execute()
    )
    rows = resp.data or []
    print(f"📊 {len(rows)} collaborateurs avec genre inconnu")

    ids_f, ids_m, still_inconnu = [], [], []

    # 2. Passe 1 : dictionnaire
    for r in rows:
        nom = r.get("prenom") or r.get("nom_complet") or ""
        g = detect_dict(nom)
        if g == "F":   ids_f.append(r["id"])
        elif g == "M": ids_m.append(r["id"])
        else:          still_inconnu.append(r)

    print(f"  Dictionnaire → F:{len(ids_f)} M:{len(ids_m)} restants:{len(still_inconnu)}")

    # 3. Passe 2 : GPT-4o-mini
    if still_inconnu:
        print(f"\n🤖 GPT-4o-mini pour {len(still_inconnu)} restants (batch 50)...")
        for i in range(0, len(still_inconnu), 50):
            batch = still_inconnu[i:i+50]
            noms  = [r.get("nom_complet") or "" for r in batch]
            print(f"  Batch {i//50+1} ({len(batch)} noms)...", end=" ")
            results = detect_gpt_batch(noms)
            for r in batch:
                g = results.get(r.get("nom_complet",""), "inconnu")
                if g == "F":   ids_f.append(r["id"])
                elif g == "M": ids_m.append(r["id"])
            print(f"F:{sum(1 for r in batch if results.get(r.get('nom_complet',''))=='F')} "
                  f"M:{sum(1 for r in batch if results.get(r.get('nom_complet',''))=='M')}")

    # 4. Mise à jour Supabase
    print(f"\n💾 Mise à jour Supabase...")
    for ids, genre in [(ids_f, "F"), (ids_m, "M")]:
        for i in range(0, len(ids), 100):
            sb.table("collaborateurs").update({"genre": genre}).in_("id", ids[i:i+100]).execute()
        if ids:
            print(f"  ✅ {genre}: {len(ids)} mis à jour")

    # 5. Résumé
    encore = sb.table("collaborateurs").select("id", count="exact", head=True)\
        .or_("genre.eq.inconnu,genre.is.null").execute()
    print(f"\n📊 Résumé final :")
    print(f"  F: {len(ids_f)}")
    print(f"  M: {len(ids_m)}")
    print(f"  Encore inconnu en base: {encore.count}")
    print("✅ Done.")

if __name__ == "__main__":
    run()

