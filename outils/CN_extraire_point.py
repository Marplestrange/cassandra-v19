# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Extraire un point d'évolution d'un module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #25df70
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : sort d'un fichier de module les fonctions pures d'un point d'évolution : écrit la référence EC (avec ses dépendances copiées), le contrat, le corpus doré et la déclaration au manifeste.
# MÉTHODE    : fermeture transitive des noms de premier niveau par l'arbre syntaxique ; le corpus doré est la sortie de la référence extraite, copiée mot pour mot de l'ancien code ; rien n'est écrasé sans --forcer.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=25df70 ▼▼▼
"""Usage : un script `spec` appelle extraire(spec). Le spec décrit le point ; l'outil écrit quatre choses :
   modules/<m>/points/EC_<point>.py · contrats/CN_<point>.json · contrats/CN_<point>.corpus.json · l'entrée [[points_evolution]] du manifeste.
   La façade du module (CN_module.py) et la liste des tests restent à la main : c'est là que se décide ce qui voyage dans l'entrée."""
import ast
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau.CN_points import STDLIB_PURE, analyser_purete  # noqa: E402


def _niveau_module(arbre):
    """nom -> (noeud, rang) pour les fonctions et les affectations de premier niveau ; les imports à part."""
    noms, imports = {}, {}
    for rang, n in enumerate(arbre.body):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            noms[n.name] = (n, rang)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        noms[x.id] = (n, rang)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            noms[n.target.id] = (n, rang)
        elif isinstance(n, ast.Import):
            for a in n.names:
                imports[(a.asname or a.name).split(".")[0]] = n
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = n
    return noms, imports


def _fermeture(noms, imports, racines):
    vus, pile, utilises = {}, list(racines), set()
    while pile:
        nom = pile.pop()
        if nom in vus:
            continue
        if nom not in noms:
            raise SystemExit("nom introuvable au premier niveau du module : " + nom)
        noeud, rang = noms[nom]
        vus[nom] = (noeud, rang)
        for x in ast.walk(noeud):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
                if x.id in noms and x.id not in vus:
                    pile.append(x.id)
                elif x.id in imports:
                    utilises.add(x.id)
    return vus, utilises


def corps_de_reference(spec):
    src = (RACINE / spec["source"]).read_text(encoding="utf-8")
    arbre = ast.parse(src)
    noms, imports = _niveau_module(arbre)
    vus, utilises = _fermeture(noms, imports, spec["fonctions"])
    uniques = {}
    for nom, (noeud, rang) in vus.items():
        uniques[id(noeud)] = (rang, noeud)
    morceaux = [ast.get_source_segment(src, n) for _, n in sorted(uniques.values(), key=lambda t: t[0])]
    lignes_imports = []
    for nom in sorted(utilises):
        n = imports[nom]
        base = (n.names[0].name if isinstance(n, ast.Import) else n.module or "").split(".")[0]
        if base not in STDLIB_PURE:
            raise SystemExit("import non pur dans la fermeture : %s (%s)" % (nom, base))
        ligne = ast.get_source_segment(src, n)
        if ligne not in lignes_imports:
            lignes_imports.append(ligne)
    return lignes_imports, morceaux


def _entete(spec, num_ligne_borne):
    m, p, c = spec["module"], spec["point"], spec.get("contrat", "1.0")
    L = ["# " + "═" * 78,
         "# TITRE      : %s : %s (référence)" % (m.capitalize(), spec["titre"]), "# LICENCE    : AGPL-3.0", "# AUTEUR     : Atek Drisse", "# GIT        : github.com/Marplestrange",
         "# MAIL       : marplestrange@cassandra.center", "# MODULE     : " + m, "# ZONE       : EC", "# RUNTIME    : python", "# VERSION CN : néant", "# VERSION EC : EC0 (référence 0.3.0)  #000000",
         "# HÔTE CN    : CN_module.py · %s @%s" % (p, c), "# RÔLE       : " + spec["role"], "# MÉTHODE    : " + spec["methode"], "# " + "═" * 78,
         "# ▼▼▼ BORNE EC point=%s contrat=@%s version=EC0 empreinte=000000 ▼▼▼" % (p, c)]
    return L


def ecrire_reference(spec):
    imports, morceaux = corps_de_reference(spec)
    pied = ["# ▲▲▲ FIN BORNE EC ▲▲▲", "", "# ═══ EXPLICATIF CN / EC " + "═" * 55,
            "# EC : `%s(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure." % spec["fonction"],
            "#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.",
            "# CN : appelée par la façade de %s (CN_module.py) par ctx.point, qui ne transmet que les champs utiles." % spec["module"],
            "# LIEN : contrat dans contrats/CN_%s.json ; corpus doré dans contrats/CN_%s.corpus.json (sorties de l'ancien code, données synthétiques)." % (spec["point"], spec["point"])]
    texte = "\n".join(_entete(spec, 0) + imports + [""] + ["\n\n".join(morceaux), "", spec["adaptateur"].strip("\n"), ""] + pied) + "\n"
    fautes = analyser_purete(texte)
    if fautes:
        raise SystemExit("la référence n'est pas pure : %s" % fautes)
    cible = RACINE / "modules" / spec["module"] / "points" / ("EC_%s.py" % spec["point"])
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(texte, encoding="utf-8", newline="\n")
    return cible, texte


def ecrire_contrat_et_corpus(spec, texte):
    espace = {}
    exec(compile(texte, "EC_" + spec["point"], "exec"), espace)
    f = espace[spec["fonction"]]
    cas, vus = [], set()
    for c in spec["cas"]:
        brut = json.dumps(c["entree"], ensure_ascii=False, sort_keys=True)
        if brut in vus:
            raise SystemExit("cas en double : " + c["cas"])
        vus.add(brut)
        entree = json.loads(brut)
        cas.append({"cas": c["cas"], "entree": c["entree"], "sortie": json.loads(json.dumps(f(entree), ensure_ascii=False))})
    d = RACINE / "modules" / spec["module"] / "contrats"
    d.mkdir(parents=True, exist_ok=True)
    contrat = {"point": "%s.%s" % (spec["module"], spec["point"]), "contrat": spec.get("contrat", "1.0"), "delai_ms": spec.get("delai_ms", 2000), "entree": spec["entree"], "sortie": spec["sortie"], "invariants": spec["invariants"]}
    (d / ("CN_%s.json" % spec["point"])).write_text(json.dumps(contrat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (d / ("CN_%s.corpus.json" % spec["point"])).write_text(json.dumps({"point": contrat["point"], "contrat": contrat["contrat"], "origine": "sorties de la référence copiée mot pour mot de l'ancien code de %s, données synthétiques" % spec["module"], "cas": cas},
                                                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return len(cas)


def declarer(spec):
    f = RACINE / "modules" / spec["module"] / "CN_manifeste.toml"
    t = f.read_text(encoding="utf-8")
    marque = 'id = "%s"' % spec["point"]
    if marque in t.split("[[points_evolution]]", 1)[-1] and "[[points_evolution]]" in t and ('[[points_evolution]]\n' + marque) in t.replace("\r\n", "\n"):
        return False
    bloc = '\n[[points_evolution]]\nid = "%s"\nlibelle = "%s"\ncontrat = "%s"\nreference = "points/EC_%s"\nfonction = "%s"\nruntime = "python"\n' % (
        spec["point"], spec["libelle"].replace('"', "'"), spec.get("contrat", "1.0"), spec["point"], spec["fonction"])
    f.write_text(t.rstrip("\n") + "\n" + bloc, encoding="utf-8", newline="\n")
    return True


def extraire(spec):
    cible, texte = ecrire_reference(spec)
    n = ecrire_contrat_et_corpus(spec, texte)
    nouveau = declarer(spec)
    print("%s.%s : référence %s · %d cas · manifeste %s" % (spec["module"], spec["point"], cible.relative_to(RACINE), n, "déclaré" if nouveau else "déjà déclaré"))
    return cible
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : outil de développement : écrit des fichiers du dépôt ; n'est jamais chargé par le noyau.
# EC : néant.
# LIEN : docs/CN_EVOLUTION.md (les points réels), tests/CN_test_points_reels.py (la liste des points et leurs planchers).
