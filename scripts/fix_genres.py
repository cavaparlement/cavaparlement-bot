#!/usr/bin/env python3
"""scripts/fix_genres.py
Complete le genre des collaborateurs inconnus via dictionnaire prenom + terminaisons.
"""
import os, re, unicodedata
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

FEMMES = set("""marie anne isabelle sophie claire julie laura celine nathalie valerie
florence sandrine aurelie laurence caroline sylvie virginie martine delphine
stephanie amelie camille lucie alice emma charlotte manon ines lea zoe pauline
mathilde emilie helene catherine francoise dominique brigitte nicole monique
corinne veronique nadine annick ghislaine chantal patricia michele evelyne
cecile genevieve odile elise marguerite louise victoire rose madeleine bernadette
colette danielle odette simone jeanne denise yvette huguette arlette mireille
josette pierrette georgette henriette renee suzanne therese joelle adeline agnes
alexia aline allegra alma amandine ambre anaelle anais anastasia angele angelique
anissa anna annabelle apolline ariane arielle assia astrid audrey aurore axelle
beatrice benedicte betty blandine capucine carla carole cassandre celeste chloe
christelle christiane clara claudine clemence clotilde coraline coralie cyrielle
deborah diane dina dorothee eleonore elisa elisabeth ella elena emeline estelle
esther eugenie eva eve fanny fatima faustine felicite flore flora flavie france
frederique gabrielle gaelle garance geraldine gladys grace gwenaelle gwenola
hannah harmonie hortense imane ingrid irene iris isadora jade jasmine jessica
joanna josephine judith julia juliette karine katia kristelle laetitia laure
laurie leonie leila lena lilou lina linda lisa lise lola lorraine lou louane
louisa luce lucile lucille luna lydie maelle maelys maeva magali malika marine
marion marlene marthe maryse mathilde maud maureen maya melodie morgane muriel
nadia naomi natacha noemie oceane olivia ornella pascale patricia perrine
priscilla rachel rebecca regine roxane sabine salome sandra sara sarah selena
selma sonia tiphaine valentine vanessa victoria violette viviane yasmine
ysaline yvonne zahra zara zelie manuela noura rania samira amira asma chaima
dalia dounia fatou hadja khadija mariam nawel nora randa rima siham souad
wahiba yasmine zainab zineb""".split())

HOMMES = set("""jean pierre michel andre claude philippe patrick jacques francois nicolas
olivier laurent thierry christophe xavier guillaume thomas alexandre julien
maxime raphael antoine mathieu sebastien frederic eric alain gerard bernard
robert henri louis paul rene marcel roger gilles serge marc emmanuel yves
charles denis stephane benoit arnaud fabrice pascal vincent remi luc thibault
damien david cedric gregoire remy anthony kevin gael hugo nathan clement
baptiste adrien romain quentin simon alexis florian lucas leo baptiste bastien
mathis mateo theo noah noa antoine ethan adam mael gabin antonin titouan
corentin erwan alan ronan yoann loic gwenael pierrick cyril matthieu matthias
nicolas stanislas amaury valentin victor florent samuel benjamin joachim
edouard maximilien bertrand francois pierre marc yann tanguy gaetan thibaut
abdel amine ayoub bilal farid hassan ibrahim karim khalid mehdi nassim omar
rachid said sofiane yanis youssef felix august augustin basile etienne eudes
eustache gauthier gonzague leo leon leopold luc lucien maxence norbert octave
oscar patrice prosper raoul regis renaud roland sylvain timothee tristan ugo
urban valery vivien wilfried yannis""".split())

FEM_END = ("ine","ette","elle","ee","ane","ance","ence","ise","ice","ille","oise","aine","ienne")
MASC_END = ("ard","ert","and","ent","ien","ois","eux","oud","aud","ald","in","on","an")

def norm_prenom(s):
    nfd = unicodedata.normalize("NFD", s or "")
    asc = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return asc.lower().strip()

def detect_genre(nom_complet):
    s = (nom_complet or "").strip()
    if s.upper().startswith("MME") or "mme" in s.lower()[:4]: return "F"
    if s.startswith("M. ") or s[:2] == "M ": return "M"
    parts = s.split()
    candidates = [parts[0], parts[-1]] if len(parts) > 1 else parts
    for p in candidates:
        for pp in re.split(r"[-\s]", norm_prenom(p)):
            if pp in FEMMES: return "F"
            if pp in HOMMES: return "M"
    for p in candidates:
        for pp in re.split(r"[-\s]", norm_prenom(p)):
            if any(pp.endswith(e) for e in FEM_END): return "F"
            if any(pp.endswith(e) for e in MASC_END): return "M"
    return "inconnu"

def run():
    resp = sb.table("collaborateurs").select("id,nom_complet,prenom,genre")        .or_("genre.eq.inconnu,genre.is.null").limit(5000).execute()
    rows = resp.data or []
    print(f"{len(rows)} collaborateurs avec genre inconnu")
    ids_f, ids_m, still = [], [], 0
    for r in rows:
        g = detect_genre(r.get("prenom") or r.get("nom_complet") or "")
        if g == "F": ids_f.append(r["id"])
        elif g == "M": ids_m.append(r["id"])
        else: still += 1
    for ids, genre in [(ids_f,"F"),(ids_m,"M")]:
        for i in range(0, len(ids), 100):
            sb.table("collaborateurs").update({"genre":genre}).in_("id",ids[i:i+100]).execute()
        print(f"  {genre}: {len(ids)} mis a jour")
    print(f"  Encore inconnu: {still}")
    print("Done.")

if __name__ == "__main__":
    run()

