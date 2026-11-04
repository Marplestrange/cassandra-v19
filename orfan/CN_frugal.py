# ══════════════════════════════════════════════
# TITRE      : Frugal 2, le moteur économe d'Orfan
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #140d6f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le moins de jetons possible : les règles gratuites d'abord ; sinon un modèle fort propose 2-3 stratégies en texte, un modèle économe les écrit en code, chaque version est vérifiée ici et affinée sur sa raison d'échec.
# MÉTHODE    : règles, puis stratégies (rôle strategie) → code (rôle executant) → vérification locale → affinage borné ; s'arrête dès qu'une variante prouvée existe ; sans point chaud, aucune dépense.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=140d6f ▼▼▼
"""Frugal 2 : notre version de l'idée de FrugalEvo (docs/CN_FRUGALEVO.md).

  étage 1 · règles déterministes : zéro jeton ; si l'une est prouvée plus rapide, on la rend et on s'arrête ;
  étage 2 · seulement si le profil montre un point chaud (>= 40 % du travail sur une ligne) : le modèle FORT (rôle « strategie ») propose 2-3 stratégies en texte, sans code ;
  étage 3 · le modèle ÉCONOME (rôle « executant ») écrit chaque stratégie en code ; chaque version est vérifiée ICI (même sortie que la référence sur les entrées visibles ET plus rapide) ;
  étage 4 · une version fausse ou pas plus rapide est renvoyée au modèle économe AVEC sa raison, pour qu'il l'affine, tant que le budget le permet (tours, appels, jetons, durée).

Il ne rend que des versions vérifiées et ne juge jamais : le contrôleur du noyau décide, ensuite, sur tout le corpus et le jeu réservé. Il tourne dans la cage (orfan/CN_moteur_hote.py).
"""
import ast
import re
import time

_STRATEGIE = re.compile(r"<STRATEGIE>\s*(.*?)\s*</STRATEGIE>", re.S | re.I)
_CODE = re.compile(r"```.*?```", re.S)


class MoteurFrugal:
    nom = "frugal"

    def __init__(self, orfan, appeler_modele=None, seuil_chaud_pct: float = 40.0, strategies: int = 3, tours: int = 2, appels_max: int = 6, jetons_max: int = 30000, duree_max_s: float = 90.0):
        self.orfan, self.appeler_modele, self.seuil = orfan, appeler_modele, float(seuil_chaud_pct)
        self.strategies, self.tours = max(1, int(strategies)), max(0, int(tours))
        self.appels_max, self.jetons_max, self.duree_max_s = max(1, int(appels_max)), int(jetons_max), float(duree_max_s)
        self.etages = []                                        # ce que chaque étage a fait, dit au journal
        self.fiches = []                                        # ce que CET appel a appris, rendu au serveur qui le garde sur le disque (le moteur ne garde rien d'un appel à l'autre)
        self.appels = self.jetons = 0
        self._debut = 0.0
        self._plein = False
        self._memoire = []
        self._toutes_ratees = False

    # ── le budget : tours (self.tours), appels, jetons, durée ───────────────
    def _reste(self) -> bool:
        return (not self._plein and self.appels < self.appels_max and self.jetons < self.jetons_max and time.monotonic() - self._debut < self.duree_max_s)

    def _appeler(self, prompt: str, role: str):
        if not self._reste():
            return None
        self.appels += 1
        self.jetons += (len(prompt) + 3) // 4
        try:
            texte = str(self.appeler_modele(prompt, role) or "")
        except Exception as e:
            self._plein = self._plein or "plafond" in str(e)
            self.etages.append("modèle %s indisponible : %s" % (role, str(e)[:80]))
            return None
        self.jetons += (len(texte) + 3) // 4
        return texte

    # ── la vérification : seul juge du moteur, jamais rendu comme verdict ────
    def _verifier(self, source, texte, fonction, entrees):
        """(valide, rapport, raison) : la raison dit au modèle économe ce qui ne va pas."""
        try:
            compile(texte, "<candidat>", "exec")
        except SyntaxError as e:
            return False, 0.0, "erreur de syntaxe ligne %s : %s" % (e.lineno, str(e.msg)[:80])
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
                   "Gain : pourquoi ce serait plus rapide, à résultat identique", "Plan : les étapes, assez précises pour qu'on n'ait aucune décision à prendre", "</STRATEGIE>"]
        return "\n".join(lignes)

    def _lire_strategies(self, reponse: str) -> list:
        blocs = [_CODE.sub("", b).strip() for b in _STRATEGIE.findall(reponse or "")]
        if not blocs and reponse and reponse.strip() and "```" not in reponse:
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
        reponse = self._appeler(prompt, "executant")
        if reponse is None:
            return None
        blocs = O.extraire_blocs(reponse)
        if not blocs:
            s["raison"] = "ta réponse ne contient aucun bloc de code python"
            return False
        s["texte"] = blocs[0]["texte"]
        return True

    def _noter(self, s, ok, rapport, raison):
        """Une fiche par famille : la dernière issue gagne (une idée raté au tour 0 puis réussie après affinage est une idée qui marche)."""
        if s["titre"] == "sans stratégie":
            return
        issue = "prouvee" if ok else ("lente" if rapport > 0 else "fausse")
        self.fiches = [f for f in self.fiches if f["famille"] != s["titre"]] + [{"famille": s["titre"], "issue": issue, "detail": raison[:200], "rapport": round(rapport, 2)}]

    def proposer(self, contexte: dict) -> list:
        O = self.orfan
        self._debut, self.appels, self.jetons, self._plein = time.monotonic(), 0, 0, False
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
        chaud = O.point_chaud(source, fonction, entrees, self.seuil)
        if chaud is None:
            self.etages.append("aucun point chaud : aucune dépense")
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
                    if tour > 0:
                        break                                    # un affinage réussi suffit : on ne dépense plus
            if trouves or not self._reste():
                break
        self.etages.append("exécutant : %d variante(s) prouvée(s), %d appel(s), ~%d jeton(s)" % (len(trouves), self.appels, self.jetons))
        vus, sortie = set(), []
        for _, c in sorted(trouves, key=lambda x: -x[0]):
            if c["texte"] not in vus:
                vus.add(c["texte"])
                sortie.append(c)
        return sortie[:budget]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un moteur ne s'évolue pas).
# CN : l'ordre règles → stratégies (fort) → code (économe) → vérification locale → affinage, et la règle de dépense : sans point chaud, ni règle qui marche, rien. Il ne juge jamais, il rend des textes déjà vérifiés sur le vu.
# LIEN : orfan/CN_orfan.py (règles, profil, point chaud, mesure locale), orfan/CN_moteur_hote.py, noyau/CN_moteurs.py, docs/CN_FRUGALEVO.md.
