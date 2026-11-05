# ══════════════════════════════════════════════
# TITRE      : Frugal, le moteur économe d'Orfan
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #7a56f1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le moins de jetons possible : les règles gratuites d'abord ; sinon un modèle fort propose 2-3 stratégies en texte, un modèle économe les écrit en code, chaque version est vérifiée ici et affinée sur sa raison d'échec.
# MÉTHODE    : règles, puis stratégies (rôle strategie) → code (rôle executant) → vérification locale → affinage borné ; s'arrête dès qu'une variante prouvée existe ; sans point chaud, aucune dépense.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7a56f1 ▼▼▼
"""Frugal : notre version de l'idée de FrugalEvo (docs/CN_FRUGALEVO.md).

  étage 1 · règles déterministes : zéro jeton ; si l'une est prouvée plus rapide, on la rend et on s'arrête ;
  étage 2 · seulement si le profil montre un point chaud (>= 40 % du travail sur une ligne) : le modèle FORT (rôle « strategie ») propose 2-3 stratégies en texte, sans code ;
  étage 3 · le modèle ÉCONOME (rôle « executant ») écrit chaque stratégie en code ; chaque version est vérifiée ICI (même sortie que la référence sur les entrées visibles ET plus rapide) ;
  étage 4 · une version fausse ou pas plus rapide est renvoyée au modèle économe AVEC sa raison, pour qu'il l'affine, tant que le budget le permet (tours, appels, jetons, durée).

Il ne rend que des versions vérifiées et ne juge jamais : le contrôleur du noyau décide, ensuite, sur tout le corpus et le jeu réservé. Il tourne dans la cage (orfan/CN_moteur_hote.py).
"""
import ast
import json
import re
import sys
import time

_STRATEGIE = re.compile(r"<STRATEGIE>\s*(.*?)\s*</STRATEGIE>", re.S | re.I)
_CODE = re.compile(r"```.*?```", re.S)
_INTERDITS = frozenset(("os", "sys", "subprocess", "socket", "multiprocessing", "threading", "ctypes", "shutil", "pathlib", "urllib", "http", "asyncio", "concurrent", "importlib", "builtins", "numpy", "pandas", "scipy"))
_VIDE = re.compile(r"^\s*[(\[]\s*(empty|vide)", re.I)                  # « (empty response)… » : la passerelle rend ça quand le modèle n'a rien écrit


class MoteurFrugal:
    nom = "frugal"

    def __init__(self, orfan, appeler_modele=None, seuil_chaud_pct: float = 40.0, plancher_us: float = 50.0, strategies: int = 3, tours: int = 2, appels_max: int = 6, jetons_max: int = 30000, duree_max_s: float = 90.0):
        self.orfan, self.appeler_modele, self.seuil = orfan, appeler_modele, float(seuil_chaud_pct)
        self.plancher_us = float(plancher_us)                 # sous ce temps moyen par appel, un gain relatif ne vaut aucun jeton
        self.strategies, self.tours = max(1, int(strategies)), max(0, int(tours))
        self.appels_max, self.jetons_max, self.duree_max_s = max(1, int(appels_max)), int(jetons_max), float(duree_max_s)
        self.etages = []                                        # ce que chaque étage a fait, dit au journal
        self.fiches = []                                        # ce que CET appel a appris, rendu au serveur qui le garde sur le disque (le moteur ne garde rien d'un appel à l'autre)
        self.appels = self.jetons = 0
        self._debut = 0.0
        self._plein = False
        self._memoire = []
        self._toutes_ratees = False
        self._plus_long = {}                                    # par rôle, l'appel le plus lent de cet appel du moteur, en secondes (le fort et l'économe n'ont pas le même pas)

    # ── le budget : tours (self.tours), appels, jetons, durée ───────────────
    def _reste(self, role: str = "executant") -> bool:
        # le prochain appel doit tenir dans le temps qui reste, au pas du plus long déjà vu : un appel qui finirait après le délai du relais ferait tuer le moteur et perdre ce qui est déjà prouvé
        return (not self._plein and self.appels < self.appels_max and self.jetons < self.jetons_max and time.monotonic() - self._debut + self._plus_long.get(role, 0.0) < self.duree_max_s)

    def _appeler(self, prompt: str, role: str):
        if not self._reste(role):
            return None
        self.appels += 1
        self.jetons += (len(prompt) + 3) // 4
        t0 = time.monotonic()
        try:
            texte = str(self.appeler_modele(prompt, role) or "")
            self._plus_long[role] = max(self._plus_long.get(role, 0.0), time.monotonic() - t0)
        except Exception as e:
            self._plein = self._plein or "plafond" in str(e)
            self.etages.append("modèle %s indisponible : %s" % (role, str(e)[:80]))
            return None
        self.jetons += (len(texte) + 3) // 4
        return texte

    @staticmethod
    def _import_interdit(texte):
        """Le premier module importé qui n'est pas de la bibliothèque standard, ou qui sort de la fonction pure (processus, fil, fichier, réseau) ; None si tout va bien. Le modèle fort aime numpy et multiprocessing."""
        try:
            arbre = ast.parse(texte)
        except SyntaxError:
            return None
        standard = getattr(sys, "stdlib_module_names", None)
        for n in ast.walk(arbre):
            noms = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module or ""] if isinstance(n, ast.ImportFrom) and not n.level else [])
            for nom in noms:
                racine = nom.split(".")[0]
                if racine in _INTERDITS or (standard is not None and racine and racine not in standard):
                    return racine
        return None

    @staticmethod
    def _temps_moyen_us(source, fonction, entrees):
        """Le temps moyen d'un appel de la fonction sur les entrées visibles, en microsecondes (le meilleur de deux passes) ; None si on ne peut pas le mesurer.
        Le profil dit où va le travail, pas combien il y en a : sur le vrai code de Cassandra, des fonctions « chaudes à 80 % » durent 10 à 40 µs, et doubler leur vitesse ne gagne rien."""
        try:
            ns = {}
            exec(compile(source, "<orfan>", "exec"), ns)
            f = ns[fonction]
            echantillon = [json.dumps(e) for e in entrees[:20]]
            meilleur = None
            for _ in range(2):
                n, t0 = 0, time.perf_counter()
                for e in echantillon:
                    try:
                        f(json.loads(e))
                    except Exception:
                        pass
                    n += 1
                d = (time.perf_counter() - t0) / max(1, n) * 1e6
                meilleur = d if meilleur is None else min(meilleur, d)
            return meilleur
        except Exception:
            return None

    def _region_chaude(self, source, fonction, entrees):
        """Une boucle dont le corps tient sur plusieurs lignes n'a aucune ligne à 40 % (trois lignes à 33 %) : le profil ligne à ligne la rate. On additionne donc par boucle et on garde la plus
        petite qui porte assez du travail ; rend {ligne, part_pct, fois, texte} comme `point_chaud`, ou None."""
        try:
            lignes = source.splitlines()
            par = {p["ligne"]: p["fois"] for p in self.orfan.profil(source, fonction, entrees, top=400)}
            total = sum(par.values())
            if not total:
                return None
            meilleur = None
            for n in ast.walk(ast.parse(source)):
                if isinstance(n, (ast.For, ast.While, ast.AsyncFor)):
                    part = sum(c for l, c in par.items() if n.lineno <= l <= n.end_lineno)
                    pct, fois = round(100 * part / total, 1), par.get(n.lineno, 0)
                    taille = n.end_lineno - n.lineno
                    if pct >= self.seuil and fois >= 50 and (meilleur is None or taille < meilleur[0]):
                        meilleur = (taille, {"ligne": n.lineno, "part_pct": pct, "fois": fois, "texte": chr(10).join(lignes[n.lineno - 1:n.end_lineno])[:600]})
            return meilleur[1] if meilleur else None
        except Exception:
            return None

    # ── la vérification : seul juge du moteur, jamais rendu comme verdict ────
    def _verifier(self, source, texte, fonction, entrees):
        """(valide, rapport, raison) : la raison dit au modèle économe ce qui ne va pas."""
        try:
            compile(texte, "<candidat>", "exec")
        except SyntaxError as e:
            return False, 0.0, "erreur de syntaxe ligne %s : %s" % (e.lineno, str(e.msg)[:80])
        interdit = self._import_interdit(texte)
        if interdit:
            return False, 0.0, "le module « %s » est interdit : bibliothèque standard pure seulement, sans processus, fil, fichier ni réseau" % interdit
        try:
            if ast.dump(ast.parse(texte)) == ast.dump(ast.parse(source)):
                return False, 0.0, "la version est identique à la référence : propose un vrai changement"
        except SyntaxError:
            pass
        ok, rapport = self.orfan.comparer_local(source, texte, fonction, entrees)
        if ok and rapport > 1.0:
            ok2, rapport2 = self.orfan.comparer_local(source, texte, fonction, entrees)       # une seule mesure peut flatter (chauffe, bruit) : il faut la tenir deux fois
            rapport = min(rapport, rapport2) if ok2 else 0.0
            if rapport > 1.0:
                return True, rapport, ""
            ok = ok2
        if ok:
            return False, rapport, "la version rend les mêmes valeurs mais n'est pas plus rapide (×%.2f de la référence) : change la façon de faire, pas seulement l'écriture" % rapport
        return False, 0.0, self._diagnostic(source, texte, fonction, entrees)

    def _diagnostic(self, source, texte, fonction, entrees):
        import copy
        O = self.orfan
        try:
            ref, cand = O.charger_local(source, fonction), O.charger_local(texte, fonction)
        except Exception as e:
            return "le code ne se charge pas ou ne définit pas « %s » : %s" % (fonction, str(e)[:100])
        for i, e in enumerate(list(entrees)[:24]):
            try:
                attendu = O._canon(ref(copy.deepcopy(e)))
            except Exception:
                continue
            try:
                obtenu = O._canon(cand(copy.deepcopy(e)))
            except Exception as ex:
                return "sur l'entrée visible n°%d la version lève %s : %s" % (i + 1, type(ex).__name__, str(ex)[:100])
            if attendu != obtenu:
                return "sur l'entrée visible n°%d la référence rend %s et ta version rend %s" % (i + 1, attendu[:100], obtenu[:100])
        return "la version ne rend pas les mêmes valeurs que la référence"

    # ── les stratégies : du texte seulement ─────────────────────────────────
    def _memoire_texte(self, memoire) -> str:
        """Ce que les recherches précédentes sur ce point ont appris, dit au modèle fort : les idées prouvées, les ratées avec leur raison, et l'ordre de changer de terrain après une série d'échecs."""
        if not memoire:
            return ""
        lignes = ["", "Idées DÉJÀ essayées sur cette fonction (ne les repropose pas telles quelles) :"]
        for f in memoire[-16:]:
            if f["issue"] == "retenue":
                lignes.append("- « %s » : le juge l'a RETENUE (gain %s %%) ; ne la refais pas, ajoute un vrai degré de liberté nouveau." % (f["famille"], f.get("rapport")))
            elif f["issue"] == "prouvee":
                lignes.append("- « %s » : a donné une version plus rapide (×%.2f) ; ne la refais pas, ajoute un vrai degré de liberté nouveau." % (f["famille"], f.get("rapport") or 0))
            else:
                lignes.append("- « %s » : %s" % (f["famille"], f.get("detail") or {"fausse": "a rendu un résultat différent", "lente": "n'était pas plus rapide", "vide": "n'a rien donné d'exploitable"}.get(f["issue"], "a échoué")))
        queue = 0
        for f in reversed(memoire):
            if f["issue"] in ("prouvee", "retenue"):
                break
            queue += 1
        if queue >= 6:
            lignes.append("Les %d dernières idées ont toutes échoué : toute nouvelle stratégie doit venir d'une famille ABSENTE de cette liste. Une variante, un réglage ou un mélange d'une famille ratée n'est pas une famille nouvelle." % queue)
        return "\n".join(lignes)

    @staticmethod
    def _juge_texte(contexte) -> str:
        """Ce que le juge de la maison récompense, dit au modèle fort (l'« analyse de l'évaluateur » de FrugalEvo, sans appel de modèle : les seuils sont connus)."""
        seuils = contexte.get("seuils") or {}
        if not seuils:
            return ""
        poids = {k: v for k, v in (seuils.get("objectifs") or {}).items() if isinstance(v, (int, float)) and v}
        txt = "Le juge n'acceptera une version que si elle rend EXACTEMENT les mêmes valeurs sur tout un corpus (dont des cas réservés que tu ne vois pas), gagne au moins %s %% de temps, plus de deux fois le bruit de mesure, et que ce gain tient hors des entrées visibles." % seuils.get("gain_min_pct", 5)
        if poids and set(poids) != {"latence"}:
            txt += " Il pèse : " + ", ".join("%s %s" % (k, v) for k, v in sorted(poids.items())) + "."
        return txt

    def _demande_strategies(self, contexte, chaud) -> str:
        lignes = ["Tu conseilles l'optimisation d'une fonction Python PURE : plus rapide, SANS changer son résultat.", "", "Fonction (nom : %s) :" % contexte["fonction"], "```python", contexte["source_reference"].rstrip(), "```", "",
                  "Profil mesuré : la ligne %d porte %s %% du travail : %s" % (chaud["ligne"], chaud["part_pct"], chaud["texte"]), ""]
        if contexte.get("tombes"):
            lignes += ["%d variante(s) ont DÉJÀ échoué sur ce point : ne propose pas une transformation triviale déjà tentée." % len(contexte["tombes"]), ""]
        if self._juge_texte(contexte):
            lignes += [self._juge_texte(contexte), ""]
        lignes += self._memoire_texte(contexte.get("memoire") or []).split("\n") if contexte.get("memoire") else []
        lignes += ["Propose %d stratégies VRAIMENT différentes (une autre structure de données, un autre algorithme, un autre découpage : pas un simple réglage). Ne rends AUCUN code : quelqu'un d'autre l'écrira." % self.strategies,
                   "Pour chaque stratégie, ce bloc exactement :", "<STRATEGIE>", "Famille : un mot ou deux qui nomment le mécanisme", "Portée : la ligne ou le bloc à remplacer",
                   "Gain : pourquoi ce serait plus rapide, à résultat identique", "Plan : les étapes, assez précises pour qu'on n'ait aucune décision à prendre", "</STRATEGIE>",
                   "Sois bref : 60 mots par stratégie au plus, aucune réflexion avant ni après les blocs.",
                   "Contraintes : bibliothèque standard pure seulement ; ni numpy, ni processus, ni fil, ni fichier, ni réseau."]
        return "\n".join(lignes)

    def _lire_strategies(self, reponse: str) -> list:
        blocs = [_CODE.sub("", b).strip() for b in _STRATEGIE.findall(reponse or "")]
        if not blocs and reponse and len(reponse.strip()) >= 40 and not _VIDE.match(reponse) and "```" not in reponse:
            blocs = [reponse.strip()[:1500]]                    # un modèle sans balises : son texte entier vaut une stratégie
        sortie, familles = [], set()
        for b in blocs:
            m = re.search(r"famille\s*:\s*(.+)", b, re.I)
            famille = (m.group(1).strip() if m else b[:40]).lower()[:60]
            if not b or famille in familles:
                continue
            familles.add(famille)
            sortie.append({"titre": famille, "plan": b[:1500], "texte": "", "raison": "", "etat": 0})
        ratees = {str(f.get("famille", "")).lower() for f in (self._memoire or []) if f.get("issue") in ("fausse", "lente", "vide", "refusee")}
        neuves = [s for s in sortie if s["titre"] not in ratees]                 # une famille déjà ratée ne coûte pas un appel de plus : le modèle fort l'a redite malgré la consigne
        self._toutes_ratees = bool(sortie) and not neuves
        if len(neuves) < len(sortie):
            self.etages.append("mémoire : %d stratégie(s) écartée(s), déjà ratées" % (len(sortie) - len(neuves)))
        return neuves[:self.strategies]

    # ── l'exécution : le modèle économe écrit, on vérifie ───────────────────
    def _ecrire(self, contexte, chaud, s):
        O = self.orfan
        prompt = O.construire_prompt(dict(contexte), [chaud], s["plan"])
        if s["texte"]:
            prompt += "\n\nTa version précédente :\n```python\n%s\n```\nProblème constaté : %s.\nCorrige-la sans abandonner l'idée de la stratégie ; rends le code complet de la fonction." % (s["texte"][:6000].rstrip(), s["raison"])
        elif s["raison"]:
            prompt += "\n\nTa réponse précédente a été refusée : %s." % s["raison"]
        prompt += "\n\nSois bref : une phrase d'hypothèse, puis le code ; aucune explication ensuite."
        reponse =self._appeler(prompt, "executant")
        if reponse is None:
            return None
        blocs = O.extraire_blocs(reponse)
        if not blocs:
            s["raison"] = "ta réponse ne contient aucun bloc de code python"
            self._noter(s, False, 0.0, s["raison"], vide=True)       # une idée qui n'a rien donné est inscrite au carnet : la prochaine fois on ne la repaie pas
            return False
        s["texte"] = blocs[0]["texte"]
        return True

    def _noter(self, s, ok, rapport, raison, vide=False):
        """Une fiche par famille : la dernière issue gagne (une idée raté au tour 0 puis réussie après affinage est une idée qui marche)."""
        if s["titre"] == "sans stratégie":
            return
        issue = "prouvee" if ok else ("lente" if rapport > 0 else ("vide" if vide else "fausse"))
        self.fiches = [f for f in self.fiches if f["famille"] != s["titre"]] + [{"famille": s["titre"], "issue": issue, "detail": ("gain ×%.2f sur le vu" % rapport) if ok else raison[:200], "rapport": round(rapport, 2)}]

    @staticmethod
    def _classer(trouves, budget):
        vus, sortie = set(), []
        for _, c in sorted(trouves, key=lambda x: -x[0]):
            if c["texte"] not in vus:
                vus.add(c["texte"])
                sortie.append(c)
        return sortie[:budget]

    def _dire_partiel(self, trouves, budget):
        """Dit au serveur ce qui est déjà prouvé : si le délai tombe pendant un appel de modèle plus lent que prévu, il ne perd pas ce travail."""
        emettre = getattr(self, "emettre", None)
        if callable(emettre):
            try:
                emettre(self._classer(trouves, budget))
            except Exception:
                pass

    def proposer(self, contexte: dict) -> list:
        O = self.orfan
        self._debut, self.appels, self.jetons, self._plein, self._plus_long = time.monotonic(), 0, 0, False, {}
        source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
        budget = max(1, int(contexte.get("budget", 3)))
        o = contexte.get("options") or {}                      # les réglages de l'admin, bornés ici quoi qu'on envoie
        for nom, cle, bas, haut in (("strategies", "strategies", 1, 5), ("tours", "tours", 0, 4), ("appels_max", "appels_max", 1, 6)):
            try:
                setattr(self, nom, min(haut, max(bas, int(o[cle]))))
            except (KeyError, TypeError, ValueError):
                pass
        self._memoire, self.fiches = [f for f in (contexte.get("memoire") or []) if isinstance(f, dict)], []
        trouves = []
        for c in O.optimisations(source):
            texte = c["texte"].rstrip("\n") + "\n"
            ok, rapport, _ = self._verifier(source, texte, fonction, entrees)
            if ok:
                trouves.append((rapport, {"texte": texte, "hypothese": "%s (×%.2f sur le vu)" % (c.get("hypothese") or "règle", rapport), "origine": "frugal"}))
        self.etages.append("règles : %d variante(s) prouvée(s)" % len(trouves))
        if trouves:
            trouves.sort(key=lambda x: -x[0])
            return [c for _, c in trouves][:budget]
        chaud = self._region_chaude(source, fonction, entrees) or O.point_chaud(source, fonction, entrees, self.seuil)
        if chaud is None:
            self.etages.append("aucun point chaud : aucune dépense")
            return []
        moyen = self._temps_moyen_us(source, fonction, entrees)
        if moyen is not None and moyen < self.plancher_us:
            self.etages.append("point chaud, mais l'appel dure %.1f µs (plancher %.0f µs) : rien à gagner qui vaille un jeton" % (moyen, self.plancher_us))
            return []
        if self.appeler_modele is None:
            self.etages.append("point chaud à la ligne %d, mais aucun modèle branché" % chaud["ligne"])
            return []
        reponse = self._appeler(self._demande_strategies(contexte, chaud), "strategie")
        strategies = self._lire_strategies(reponse) if reponse else []
        if not strategies and self._toutes_ratees:
            self.etages.append("toutes les idées du modèle fort ont déjà échoué ici : plus aucune dépense")
            return []
        if not strategies:
            self.etages.append("le modèle fort n'a rien proposé : une seule tentative, sans stratégie")
            strategies = [{"titre": "sans stratégie", "plan": "", "texte": "", "raison": "", "etat": 0}]
        else:
            self.etages.append("modèle fort : %d stratégie(s)" % len(strategies))
        for tour in range(self.tours + 1):                       # le tour 0 écrit chaque stratégie ; les suivants affinent, la plus proche du but d'abord
            file = strategies if tour == 0 else sorted([s for s in strategies if s["texte"] or s["raison"]], key=lambda s: -s["etat"])
            for s in file:
                if not self._reste():
                    break
                if self._ecrire(contexte, chaud, s) is None:
                    break
                if not s["texte"]:
                    continue
                texte = s["texte"].rstrip("\n") + "\n"
                ok, rapport, raison = self._verifier(source, texte, fonction, entrees)
                s["etat"], s["raison"] = (2 if ok else (1 if rapport > 0 else 0)), raison
                self._noter(s, ok, rapport, raison)
                if ok:
                    trouves.append((rapport, {"texte": texte, "hypothese": "stratégie « %s » (×%.2f sur le vu, tour %d)" % (s["titre"], rapport, tour), "origine": "frugal", "famille": s["titre"]}))
                    self._dire_partiel(trouves, budget)
                    if tour > 0:
                        break                                    # un affinage réussi suffit : on ne dépense plus
            if trouves or not self._reste():
                break
        self.etages.append("exécutant : %d variante(s) prouvée(s), %d appel(s), ~%d jeton(s)" % (len(trouves), self.appels, self.jetons))
        return self._classer(trouves, budget)
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un moteur ne s'évolue pas).
# CN : l'ordre règles → stratégies (fort) → code (économe) → vérification locale → affinage, et la règle de dépense : sans point chaud, ni règle qui marche, rien. Il ne juge jamais, il rend des textes déjà vérifiés sur le vu.
# LIEN : orfan/CN_orfan.py (règles, profil, point chaud, mesure locale), orfan/CN_moteur_hote.py, noyau/CN_moteurs.py, docs/CN_FRUGALEVO.md.
