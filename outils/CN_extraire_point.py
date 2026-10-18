# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Extraire un point d'évolution d'un module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #57dad0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : sort d'un fichier de module les fonctions pures d'un point d'évolution : écrit la référence EC (avec ses dépendances copiées), le contrat, le corpus doré et la déclaration au manifeste.
# MÉTHODE    : fermeture transitive des noms de premier niveau par l'arbre syntaxique ; le corpus doré est la sortie de la référence extraite, copiée mot pour mot de l'ancien code ; rien n'est écrasé sans --forcer.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=57dad0 ▼▼▼
"""Usage : un script `spec` appelle extraire(spec). Le spec décrit le point ; l'outil écrit quatre choses :
   modules/<m>/points/EC_<point>.py · contrats/CN_<point>.json · contrats/CN_<point>.corpus.json · l'entrée [[points_evolution]] du manifeste.
   La façade du module (CN_module.py) et la liste des tests restent à la main : c'est là que se décide ce qui voyage dans l'entrée."""
import ast
import json
import sys
import textwrap
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


def _avec_imbriquees(src, noms):
    """Les fonctions imbriquées (dans brancher() par exemple) sont HISSÉES au premier niveau du texte de travail : elles deviennent des fonctions ordinaires pour la fermeture."""
    arbre = ast.parse(src)
    lignes = src.split("\n")
    for nom in noms:
        n = next((x for x in ast.walk(arbre) if isinstance(x, ast.FunctionDef) and x.name == nom), None)
        if n is None:
            raise SystemExit("fonction imbriquée introuvable : " + nom)
        src += "\n\n" + textwrap.dedent("\n".join(lignes[n.lineno - 1:n.end_lineno])) + "\n"
    return src


def corps_de_reference(spec):
    src = (RACINE / spec["source"]).read_text(encoding="utf-8")
    if spec.get("imbriquees"):
        src = _avec_imbriquees(src, spec["imbriquees"])
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
        entree = json.loads(json.dumps(c["entree"], ensure_ascii=False))          # le tour JSON GARDE l'ordre des clés : un résultat peut en dépendre
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


def _preparer(spec):
    """Forme courte : spec["appel"] = {"fn": nom, "params": [...], "sortie": "valeur"} et des cas (nom, [arguments]).
    L'outil dérive l'adaptateur, le schéma d'entrée et les entrées des cas."""
    ap = spec.get("appel")
    if not ap:
        return spec
    fn, params, sortie = ap["fn"], ap["params"], ap.get("sortie", "valeur")
    spec = dict(spec)
    spec["fonctions"] = [fn]
    spec["fonction"] = "point_" + spec["point"]
    arguments = ", ".join('entree["%s"]' % q for q in params)
    spec["adaptateur"] = ('def point_%s(entree):\n    """Le point d\'évolution `%s` (contrat %s)."""\n    return {"%s": %s}\n'
                          % (spec["point"], spec["point"], spec.get("contrat", "1.0"), sortie, ("sorted(%s(%s))" if ap.get("ensemble") else "%s(%s)") % (fn, arguments)))
    spec["entree"] = {"type": "object", "required": list(params)}
    spec["sortie"] = {"type": "object", "required": [sortie]}
    spec["cas"] = [{"cas": n, "entree": dict(zip(params, args))} for n, args in spec["cas"]]
    return spec


def _patcher_sites(chemin, fn, nreq, exclure=None):
    """Ajoute `, ctx.point` aux appels de `fn` (fn(...) ou objet.fn(...)) qui ont un ctx en portée. Rend (lignes, restes) ; `exclure` = (début, fin) de la fonction elle-même."""
    brut = chemin.read_bytes().decode("utf-8")
    src = brut.replace("\r\n", "\n")
    arbre = ast.parse(src)
    lignes = src.split("\n")
    parents = {}
    for p_ in ast.walk(arbre):
        for e in ast.iter_child_nodes(p_):
            parents[id(e)] = p_
    sites = [c for c in ast.walk(arbre) if isinstance(c, ast.Call) and ((isinstance(c.func, ast.Name) and c.func.id == fn) or (isinstance(c.func, ast.Attribute) and c.func.attr == fn))
             and not (exclure and exclure[0] <= c.lineno <= exclure[1])]
    restes = []
    for c in sorted(sites, key=lambda c: (-c.end_lineno, -c.end_col_offset)):
        chaine, q = [], parents.get(id(c))
        while q is not None:
            if isinstance(q, ast.FunctionDef):
                chaine.append(q)
            q = parents.get(id(q))
        if not any(x.name == "brancher" or any(y.arg == "ctx" for y in x.args.args) for x in chaine):
            restes.append("%s : site sans ctx, ligne %d" % (chemin.name, c.lineno))
            continue
        if len(c.args) < nreq or any(isinstance(a, ast.Starred) for a in c.args):
            restes.append("%s : arguments par mot-clé ou étoilés, ligne %d" % (chemin.name, c.lineno))
            continue
        dernier = c.args[nreq - 1] if nreq else None
        if dernier is None:
            restes.append("%s : fonction sans argument requis, ligne %d" % (chemin.name, c.lineno))
            continue
        i = dernier.end_lineno - 1
        octets = lignes[i].encode("utf-8")
        j = dernier.end_col_offset
        lignes[i] = (octets[:j] + b", ctx.point" + octets[j:]).decode("utf-8")
    return lignes, restes, ("\r\n" if "\r\n" in brut else "\n")


def poser_facade_globale(spec):
    """Mode « point global » : la façade GARDE la signature d'origine et lit `_point`, posé par brancher() (`<objet>._point = ctx.point` dans le module qui branche).
    Pour les fonctions que d'autres fonctions du même fichier appellent, sans ctx : aucun site d'appel n'est touché."""
    ap = spec["appel"]
    fn, params, sortie = ap["fn"], ap["params"], ap.get("sortie", "valeur")
    f = RACINE / spec["facade_fichier"]
    brut = f.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in brut else "\n"
    src = brut.replace("\r\n", "\n")
    arbre = ast.parse(src)
    corps = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == fn]
    if not corps:
        return ["déjà converti ou introuvable : " + fn]
    n = corps[0]
    if "_point(" in ast.get_source_segment(src, n):
        return []
    lignes = src.split("\n")
    entete_def = lignes[n.lineno - 1]
    doc = (ast.get_docstring(n) or "").split("\n")[0].rstrip(".")
    fac = [entete_def, '    """%s. Le calcul est un POINT D\'ÉVOLUTION : points/EC_%s.py."""' % (doc or fn, spec["point"]),
           ('    return set(_point("%s", {%s})["%s"])' if ap.get("ensemble") else '    return _point("%s", {%s})["%s"]') % (spec["point"], ", ".join('"%s": %s' % (q, q) for q in params), sortie)]
    lignes[n.lineno - 1 - len(n.decorator_list):n.end_lineno] = fac
    texte = "\n".join(lignes)
    if "\n_point = None" not in texte:
        i = next(k for k, l in enumerate(lignes) if l == entete_def)
        lignes[i:i] = ["_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)", "", ""]
        texte = "\n".join(lignes)
    ast.parse(texte)
    f.write_bytes(texte.replace("\n", nl).encode("utf-8"))
    restes = []
    if spec.get("brancher_fichier"):
        g = RACINE / spec["brancher_fichier"]
        b2 = g.read_bytes().decode("utf-8")
        nl2 = "\r\n" if "\r\n" in b2 else "\n"
        t2 = b2.replace("\r\n", "\n")
        if spec["brancher_objet"] == "ce module":                     # les façades sont dans le module qui branche : `_point` est son propre global
            ligne = "    global _point\n    _point = ctx.point"
        else:
            ligne = "    %s._point = ctx.point" % spec["brancher_objet"]
        if ligne not in t2:
            marque = "def brancher(ctx):\n"
            if marque not in t2:
                return ["brancher(ctx) introuvable dans " + spec["brancher_fichier"]]
            t2 = t2.replace(marque, marque + ligne + "\n", 1)
            ast.parse(t2)
            g.write_bytes(t2.replace("\n", nl2).encode("utf-8"))
    return restes


def poser_facade_imbriquee(spec):
    """La fonction imbriquée (dans brancher()) garde sa place et sa signature : son corps devient un appel à ctx.point."""
    ap = spec["appel"]
    fn, params, sortie = ap["fn"], ap["params"], ap.get("sortie", "valeur")
    f = RACINE / spec["facade_fichier"]
    brut = f.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in brut else "\n"
    src = brut.replace("\r\n", "\n")
    arbre = ast.parse(src)
    n = next((x for x in ast.walk(arbre) if isinstance(x, ast.FunctionDef) and x.name == fn), None)
    if n is None:
        return ["fonction imbriquée introuvable : " + fn]
    lignes = src.split("\n")
    if "ctx.point(" in "\n".join(lignes[n.lineno - 1:n.end_lineno]):
        return []
    entete = lignes[n.lineno - 1]
    marge = entete[:len(entete) - len(entete.lstrip())]
    doc = (ast.get_docstring(n) or "").split("\n")[0].rstrip(".")
    fac = [entete, marge + '    """%s. Le calcul est un POINT D\'ÉVOLUTION : points/EC_%s.py."""' % (doc or fn, spec["point"]),
           marge + '    return ctx.point("%s", {%s})["%s"]' % (spec["point"], ", ".join('"%s": %s' % (q, q) for q in params), sortie)]
    lignes[n.lineno - 1 - len(n.decorator_list):n.end_lineno] = fac
    neuf = "\n".join(lignes)
    ast.parse(neuf)
    f.write_bytes(neuf.replace("\n", nl).encode("utf-8"))
    return []


def poser_facade(spec):
    """Remplace la fonction d'origine par sa façade et passe ctx.point aux sites d'appel qui ont un ctx (dans le fichier et dans spec["sites_fichiers"]) ; rend ce qui reste à la main."""
    ap = spec["appel"]
    if ap.get("mode") == "global":
        return poser_facade_globale(spec)
    if ap.get("mode") == "imbriquee":
        return poser_facade_imbriquee(spec)
    fn, params, sortie = ap["fn"], ap["params"], ap.get("sortie", "valeur")
    f = RACINE / spec["facade_fichier"]
    arbre = ast.parse(f.read_bytes().decode("utf-8").replace("\r\n", "\n"))
    corps = [n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == fn]
    if not corps or "appeler" in [a.arg for a in corps[0].args.args]:
        return ["déjà converti ou introuvable : " + fn]
    n = corps[0]
    defauts = ap.get("defauts", {})
    requis = [q for q in params if q not in defauts]
    lignes, restes, nl = _patcher_sites(f, fn, len(requis), (n.lineno, n.end_lineno))
    doc = (ast.get_docstring(n) or "").split("\n")[0].rstrip(".")
    fac = ["def %s(%s):" % (fn, ", ".join(requis + ["appeler"] + ["%s=%s" % (q, defauts[q]) for q in params if q in defauts])),
           '    """%s. Le calcul est un POINT D\'ÉVOLUTION : points/EC_%s.py."""' % (doc or fn, spec["point"]),
           '    return appeler("%s", {%s})["%s"]' % (spec["point"], ", ".join('"%s": %s' % (q, q) for q in params), sortie)]
    lignes[n.lineno - 1 - len(n.decorator_list):n.end_lineno] = fac
    neuf = "\n".join(lignes)
    ast.parse(neuf)
    f.write_bytes(neuf.replace("\n", nl).encode("utf-8"))
    for extra in spec.get("sites_fichiers", []):
        g = RACINE / extra
        lg, rs, nl2 = _patcher_sites(g, fn, len(requis))
        restes += rs
        texte = "\n".join(lg)
        ast.parse(texte)
        g.write_bytes(texte.replace("\n", nl2).encode("utf-8"))
    return restes


def inscrire_test(spec, score, mutants, cas):
    """Ajoute le point à la liste des points réels, avec un plancher de score mesuré (par 0,05 en dessous) et des seuils d'effectif adaptés aux très petites fonctions."""
    f = RACINE / "tests" / "CN_test_points_reels.py"
    t = f.read_text(encoding="utf-8")
    if '"EC_%s"' % spec["point"] in t:
        return False
    plancher = int(score * 20) / 20.0
    marque = "]\n# (cas dorés, variantes fausses)"
    assert marque in t, "marque introuvable dans le test"
    t = t.replace(marque, ',\n          ("%s", "%s", "EC_%s", %.2f)%s' % (spec["module"], spec["point"], spec["point"], plancher, marque), 1)
    mini = (min(20, max(8, cas - 2)), min(30, max(3, mutants - 2)))
    if mini != (20, 30):
        t = t.replace("SEUILS = {", 'SEUILS = {("%s", "%s"): (%d, %d), ' % (spec["module"], spec["point"], mini[0], mini[1]), 1)
    f.write_text(t, encoding="utf-8", newline="\n")
    return True


def mesurer(spec):
    import tempfile
    from noyau import CN_evaluateur as EV, CN_points as P, CN_rejeu as R, CN_manifeste as M
    d = RACINE / "modules" / spec["module"]
    tmp = Path(tempfile.mkdtemp())
    svc = P.ServicePoints(tmp / "ec")
    defauts = svc.declarer(M.charger(d / "CN_manifeste.toml"), d)
    if defauts:
        raise SystemExit("manifeste : %s" % defauts)
    rj = R.Rejeu(tmp / "r.db")
    c = json.loads((d / "contrats" / ("CN_%s.corpus.json" % spec["point"])).read_text(encoding="utf-8"))
    rj.importer("%s.%s" % (spec["module"], spec["point"]), c["cas"], "dore")
    ev = EV.Evaluateur(svc, rj, minimum=max(3, min(10, len(c["cas"]) - 1)))
    r = ev.evaluer(spec["module"], spec["point"], (d / "points" / ("EC_%s.py" % spec["point"])).read_text(encoding="utf-8"))
    z = ev.pieges(spec["module"], spec["point"], maximum=200)
    return r["verdict"], z["score"], z["mutants"], len(c["cas"]), [(x["ligne"], x["mutation"][:28]) for x in z["survivants"][:6]]


def extraire(spec):
    spec = _preparer(spec)
    cible, texte = ecrire_reference(spec)
    n = ecrire_contrat_et_corpus(spec, texte)
    nouveau = declarer(spec)
    print("%s.%s : référence %s · %d cas · manifeste %s" % (spec["module"], spec["point"], cible.relative_to(RACINE), n, "déclaré" if nouveau else "déjà déclaré"))
    if spec.get("facade_fichier") and spec.get("appel"):
        restes = poser_facade(spec)
        print("   façade posée" + ((" ; À FAIRE À LA MAIN : " + "; ".join(restes)) if restes else ""))
    verdict, score, mutants, ncas, survivants = mesurer(spec)
    print("   verdict %s · %d variantes fausses · score %.3f · survivants %s" % (verdict, mutants, score, survivants or "aucun"))
    if verdict != "equivalente":
        raise SystemExit("la référence n'est pas équivalente à elle-même : " + verdict)
    inscrire_test(spec, score, mutants, ncas)
    return {"score": score, "mutants": mutants, "cas": ncas}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : outil de développement : écrit des fichiers du dépôt ; n'est jamais chargé par le noyau.
# EC : néant.
# LIEN : docs/CN_EVOLUTION.md (les points réels), tests/CN_test_points_reels.py (la liste des points et leurs planchers).
