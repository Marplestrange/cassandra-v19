# ══════════════════════════════════════════════
# TITRE      : Les moteurs de recherche d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #688787
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Héberge un moteur de recherche dans un processus à part (protocole + relais de modèles plafonné) et tient le registre des moteurs et l'attribution des pièces.
# MÉTHODE    : le moteur parle par lignes JSON ; ses demandes de modèle passent par un relais qui compte appels et jetons et refuse au plafond ; le registre est un fichier JSON écrit par remplacement.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=688787 ▼▼▼
"""Lot 1 de la maquette d'Évolution : la frontière de processus, le relais de modèles, le registre des moteurs.

`MoteurProcessus` a le contrat de tout moteur (`proposer(contexte) -> liste de textes`) : le service d'évolution ne voit pas la différence entre Orfan en ligne, Orfan dans
un processus, ou un moteur externe derrière le même protocole. Dans le processus, ni clé, ni réseau (le bac), ni fichier écrit, mémoire plafonnée ; au délai, il est tué.

Le RELAIS : un moteur n'a jamais de jeton. Il demande « un modèle » ; le serveur choisit lequel (le rôle), compte les appels et les jetons, et refuse au plafond. Un refus est
une erreur que le moteur reçoit, jamais un silence.

Le REGISTRE : quels moteurs existent, lesquels sont actifs, ce que chacun a coûté, et quelle pièce vient de quel moteur (une pièce sans moteur connu se lit « inconnu »).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path

try:
    from .CN_points import DelaiEC, ErreurEC, _Travailleur, bac_os
except ImportError:                                                  # chargé par son chemin (un banc, un module)
    from noyau.CN_points import DelaiEC, ErreurEC, _Travailleur, bac_os          # type: ignore

CHOIX = ("deterministe", "modele", "les_deux", "evolutif", "frugal")
_ADAPTATEUR = re.compile(r"^adaptateur:[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
DELAI_MOTEUR_S = 120.0
MEMOIRE_MOTEUR_MO = 768
MAX_APPELS_MODELE = 6
MAX_JETONS = 40000
ETATS = ("actif", "installe", "prevu")
# Les étages d'une cascade : (moteur du registre, choix de recherche, libellé, coût). Un moteur externe installé ajoute son étage (son id, choix « adaptateur:<module> »).
ETAGES = {"orfan/deterministe": ("orfan", "deterministe", "Orfan · règles déterministes", "gratuit : zéro jeton"),
          "frugal": ("frugal", "frugal", "Frugal 2 · règles, puis idées du modèle fort, code du modèle économe", "peu de jetons : un modèle seulement sur un point chaud"),
          "orfan/modele": ("orfan", "modele", "Orfan · modèle guidé par le profil", "jetons : un modèle écrit les variantes"),
          "evolutif": ("evolutif", "evolutif", "Évolutif · populations et mutations", "jetons : plusieurs générations")}
CASCADE_DEFAUT = [("orfan/deterministe", True), ("frugal", True), ("orfan/modele", True), ("evolutif", False)]
OPTIONS_DEFAUT = {"arret_premiere": True, "modele_si_chaud": True, "course_si_deux": False}
BUDGET_DEFAUT = {"jetons_mois": 2000000, "alerte_pct": 80, "gratuits_d_abord": True, "couper_au_plafond": True}
NATIFS = {"orfan": "Orfan", "frugal": "Frugal", "evolutif": "Évolutif"}
POIDS_OBJECTIFS = {"latence": 1.0, "memoire": 0.0, "taille": 0.0}


def _jetons(texte: str) -> int:
    """Une estimation sans bibliothèque : un jeton pour quatre caractères. Le plafond est une garde, pas une facture."""
    return max(1, len(str(texte)) // 4)


class MoteurProcessus:
    """Un moteur de recherche dans son processus. `appeler_modele(prompt, role) -> texte` est fourni par Cassandra (son registre de modèles) ; le moteur n'y a accès que par le relais."""

    def __init__(self, choix: str = "deterministe", appeler_modele=None, orfan: str | Path | None = None, delai_s: float = DELAI_MOTEUR_S, memoire_mo: int = MEMOIRE_MOTEUR_MO,
                 max_appels: int = MAX_APPELS_MODELE, max_jetons: int = MAX_JETONS, bac: str = "auto", nom: str = "orfan-processus", python: str = "", on_relais=None, carnet=None, options=None):
        if choix not in CHOIX and not _ADAPTATEUR.match(str(choix)):
            raise ValueError("choix de moteur inconnu : %r (%s, ou adaptateur:<module>)" % (choix, ", ".join(CHOIX)))
        self.options = {k: v for k, v in dict(options or {}).items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)}      # les réglages du moteur (Frugal : idées, tours, appels) ; il les borne lui-même
        self._familles = {}                                             # empreinte d'une variante rendue -> sa famille d'idée, pour rapporter le verdict du juge
        self.carnet = carnet                                            # le carnet des idées essayées (Registre.fiches / noter_fiches) : sur le disque, jamais gardé en mémoire vive
        self.on_relais = on_relais                                      # appelé après chaque demande de modèle : {role, modele, jetons_haut, jetons_bas, resultat}
        self.python = str(python or "")                                 # l'interpréteur de l'environnement du moteur (un moteur externe a le sien)
        racine = Path(__file__).resolve().parent.parent / "orfan"
        self.choix, self.nom = choix, nom
        self.orfan = str(orfan or racine / "CN_orfan.py")
        self.hote = str(racine / "CN_moteur_hote.py")
        self.appeler_modele, self.delai_s, self.memoire_mo, self.bac = appeler_modele, float(delai_s), int(memoire_mo), bac
        self.max_appels, self.max_jetons = int(max_appels), int(max_jetons)
        self.stats = {"propositions": 0, "appels_modele": 0, "refus": 0, "jetons": 0, "duree_s": 0.0}

    def _lecture(self) -> tuple:
        """Ce que le bac doit rendre visible (lecture seule) pour un moteur externe : son environnement (…/venv) et, si son interpréteur n'est pas celui du système (un Python 3.13 posé par l'admin),
        le dossier d'installation de cet interpréteur, lu dans le `pyvenv.cfg` de l'environnement."""
        venv = Path(self.python).parent.parent
        visibles = [str(venv)]
        try:
            for ligne in (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
                cle, _, val = ligne.partition("=")
                if cle.strip() == "home" and val.strip():
                    home = Path(val.strip())
                    if not home.as_posix().startswith(("/usr", "/bin", "/lib")):
                        visibles.append(str(home.parent))
        except OSError:
            pass
        return tuple(visibles)

    def _retenir_familles(self, candidats: list) -> None:
        self._familles = {}
        try:
            from noyau.CN_evolution import empreinte_ast
        except Exception:
            return
        for c in candidats:
            if isinstance(c, dict) and c.get("famille"):
                try:
                    self._familles[empreinte_ast(str(c.get("texte", "")))] = str(c["famille"])
                except (SyntaxError, ValueError):
                    pass

    def verdicts(self, gid: str, essais: list) -> None:
        """Rappel du juge du noyau : ce qu'il a décidé de chaque variante rendue. Le carnet note « retenue » ou « refusée » (avec la raison) à la place de « prouvée sur le vu »."""
        if self.carnet is None or not self._familles:
            return
        fiches = []
        for e in essais:
            famille = self._familles.get(e.get("ast"))
            if not famille:
                continue
            if e.get("retenu"):
                fiches.append({"famille": famille, "issue": "retenue", "detail": "le juge l'a retenue", "rapport": e.get("gain_pct") or 0})
            else:
                raison = {"divergente": "le juge l'a refusée : sortie différente sur le corpus", "erreur": "le juge l'a refusée : erreur à l'exécution", "impure": "le juge l'a refusée : effet de bord",
                          "corpus_trop_etroit": "le juge n'a pas pu trancher (corpus trop étroit)", "deja_vue": "déjà vue et écartée"}.get(e.get("verdict"), "le juge l'a écartée : gain insuffisant, dans le bruit ou pas confirmé hors du vu (%s %%)" % e.get("gain_pct"))
                fiches.append({"famille": famille, "issue": "refusee", "detail": raison, "rapport": 0})
        if fiches:
            self.carnet.noter_fiches(gid, fiches)

    def _relais(self, role: str, modele: str, haut: int, bas: int, resultat: str) -> None:
        if self.on_relais is not None:
            try:
                self.on_relais({"moteur": self.nom, "role": role, "modele": modele, "jetons_haut": haut, "jetons_bas": bas, "resultat": resultat})
            except Exception:
                pass                                              # un journal qui échoue ne coupe jamais la recherche

    def proposer(self, contexte: dict) -> list:
        debut = time.monotonic()
        lecture = self._lecture() if self.python else ()
        t = _Travailleur(self.memoire_mo, self.bac, script=self.hote, arguments=(self.orfan, self.choix), executable=self.python, lecture=lecture)
        appels = jetons = 0
        gid = str(contexte.get("point") or "")
        envoi = {k: v for k, v in contexte.items() if not callable(v)}                      # une fonction ne traverse pas la frontière : le moteur reçoit du texte et des données
        if self.options:
            envoi["options"] = dict(self.options)
        if self.carnet is not None and gid:
            try:
                envoi["memoire"] = self.carnet.fiches(gid)                                  # ce que les recherches précédentes sur CE point ont appris (un moteur ne garde rien d'un appel à l'autre)
            except Exception:
                envoi["memoire"] = []                                                       # un carnet illisible ne coupe pas la recherche
        try:
            t.envoyer({"op": "proposer", "contexte": envoi})
            while True:
                reste = self.delai_s - (time.monotonic() - debut)
                if reste <= 0:
                    t.tuer()
                    raise DelaiEC("délai de %.0f s dépassé : le moteur est tué" % self.delai_s)
                msg = t.recevoir(reste)
                op = msg.get("op")
                if op == "resultat":
                    self.stats["propositions"] += 1
                    if self.carnet is not None and gid and msg.get("memoire"):
                        try:
                            self.carnet.noter_fiches(gid, msg.get("memoire"))
                        except Exception:
                            pass                                                          # le carnet est une aide : sa panne ne défait pas une recherche
                    candidats = list(msg.get("candidats") or [])
                    self._retenir_familles(candidats)
                    return candidats
                if op == "erreur":
                    raise ErreurEC("le moteur a échoué : %s" % msg.get("erreur"))
                if op != "modele":
                    raise ErreurEC("message inconnu du moteur : %r" % (op,))
                role = str(msg.get("role", "executant"))
                if self.appeler_modele is None:
                    self._relais(role, "", 0, 0, "refusé : aucun modèle")
                    t.envoyer({"ok": False, "erreur": "aucun modèle n'est branché sur ce moteur"})
                    continue
                if appels >= self.max_appels or jetons >= self.max_jetons:
                    self.stats["refus"] += 1
                    self._relais(role, "", 0, 0, "refusé : plafond")
                    t.envoyer({"ok": False, "erreur": "plafond du relais atteint (%d appels, %d jetons) : la recherche s'arrête là" % (appels, jetons)})
                    continue
                prompt = str(msg.get("prompt", ""))
                appels += 1
                self.stats["appels_modele"] += 1
                try:
                    texte = str(self.appeler_modele(prompt, role) or "")
                except Exception as e:                                # un modèle muet ou en panne se dit au moteur, il ne tue pas la recherche
                    self._relais(role, getattr(self.appeler_modele, "dernier_modele", ""), _jetons(prompt), 0, "erreur : %s" % str(e)[:80])
                    t.envoyer({"ok": False, "erreur": "le modèle n'a pas répondu : %s" % str(e)[:200]})
                    continue
                n = _jetons(prompt) + _jetons(texte)
                jetons += n
                self.stats["jetons"] += n
                self._relais(role, getattr(self.appeler_modele, "dernier_modele", ""), _jetons(prompt), _jetons(texte), "servi")
                t.envoyer({"ok": True, "texte": texte})
        finally:
            self.stats["duree_s"] = round(self.stats["duree_s"] + time.monotonic() - debut, 3)
            t.tuer()


class Registre:
    """Les moteurs connus et ce qu'ils ont coûté. Un fichier JSON écrit par remplacement (jamais à moitié) ; un fichier illisible se dit, il ne s'efface pas."""

    def __init__(self, chemin: str | Path, horloge=time.time):
        self.chemin = Path(chemin)
        self._horloge = horloge
        self._verrou = threading.RLock()

    def _lire(self) -> dict:
        try:
            d = json.loads(self.chemin.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"moteurs": {}, "attribution": {}}
        except ValueError as e:
            raise ValueError("le registre des moteurs est illisible (%s) : rien n'est écrasé, à réparer à la main" % e)
        d.setdefault("moteurs", {})
        d.setdefault("attribution", {})
        return d

    def _ecrire(self, d: dict) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".moteurs-", dir=str(self.chemin.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.chemin)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def declarer(self, ident: str, nom: str, genre: str = "natif", etat: str = "actif", **plus) -> dict:
        if not ident or not str(ident).replace("-", "").replace("_", "").isalnum():
            raise ValueError("identifiant de moteur invalide : %r" % (ident,))
        if etat not in ETATS:
            raise ValueError("état de moteur inconnu : %r (%s)" % (etat, ", ".join(ETATS)))
        with self._verrou:
            d = self._lire()
            vieux = d["moteurs"].get(ident, {})
            fiche = {"essais": 0, "pieces": 0, "appels_modele": 0, "jetons": 0, "refus": 0}
            fiche.update(vieux)
            fiche.update(plus)
            fiche.update(nom=nom, genre=genre, etat=etat)
            d["moteurs"][ident] = fiche
            self._ecrire(d)
            return d["moteurs"][ident]

    def etat(self, ident: str, etat: str) -> dict:
        if etat not in ETATS:
            raise ValueError("état de moteur inconnu : %r" % (etat,))
        with self._verrou:
            d = self._lire()
            if ident not in d["moteurs"]:
                raise ValueError("moteur inconnu : « %s »" % ident)
            d["moteurs"][ident]["etat"] = etat
            self._ecrire(d)
            return d["moteurs"][ident]

    FICHES_PAR_POINT = 24                                             # les plus récentes seulement : le carnet reste petit, sur le disque
    _ISSUES = ("prouvee", "fausse", "lente", "vide", "retenue", "refusee")

    def fiches(self, gid: str) -> list:
        """Les idées déjà essayées sur ce point (de la plus ancienne à la plus récente) : {famille, issue, detail, rapport}. Lu sur le disque à chaque demande, rien n'est gardé en mémoire vive."""
        with self._verrou:
            return list(self._lire().get("fiches", {}).get(str(gid), []))

    def noter_fiches(self, gid: str, fiches) -> int:
        """Inscrit ce qu'un moteur (dans la cage : sa parole est suspecte) dit avoir essayé. Tout est borné et nettoyé ici ; une même famille n'a qu'une fiche, la dernière."""
        propres = []
        for f in list(fiches or [])[:12]:
            if not isinstance(f, dict) or f.get("issue") not in self._ISSUES:
                continue
            famille = " ".join(str(f.get("famille", "")).split())[:80]
            if not famille:
                continue
            try:
                rapport = round(float(f.get("rapport") or 0.0), 2)
            except (TypeError, ValueError):
                rapport = 0.0
            propres.append({"famille": famille, "issue": f["issue"], "detail": " ".join(str(f.get("detail", "")).split())[:200], "rapport": rapport, "ts": self._horloge()})
        if not propres:
            return 0
        with self._verrou:
            d = self._lire()
            gardees = {x["famille"].lower(): x for x in d.setdefault("fiches", {}).get(str(gid), [])}
            for f in propres:
                gardees.pop(f["famille"].lower(), None)
                gardees[f["famille"].lower()] = f
            d["fiches"][str(gid)] = list(gardees.values())[-self.FICHES_PAR_POINT:]
            self._ecrire(d)
        return len(propres)

    def compter(self, ident: str, stats: dict, essais: int = 0) -> None:
        """Ajoute au moteur ce que sa recherche a coûté (les compteurs de `MoteurProcessus.stats`, par différence)."""
        with self._verrou:
            d = self._lire()
            m = d["moteurs"].get(ident)
            if m is None:
                return
            m["essais"] = m.get("essais", 0) + int(essais)
            for k in ("appels_modele", "jetons", "refus"):
                m[k] = m.get(k, 0) + int(stats.get(k, 0))
            jour = d.setdefault("depense", {}).setdefault(ident, {}).setdefault(self._jour(), {"jetons": 0, "essais": 0, "appels": 0})
            jour["jetons"] += int(stats.get("jetons", 0))
            jour["essais"] += int(essais)
            jour["appels"] += int(stats.get("appels_modele", 0))
            for ancien in sorted(d["depense"][ident])[:-62]:                       # deux mois d'historique, pas plus
                del d["depense"][ident][ancien]
            self._ecrire(d)

    def attribuer(self, gid: str, num: int, ident: str) -> None:
        with self._verrou:
            d = self._lire()
            d["attribution"]["%s#%d" % (gid, int(num))] = ident
            if ident in d["moteurs"]:
                d["moteurs"][ident]["pieces"] = d["moteurs"][ident].get("pieces", 0) + 1
            self._ecrire(d)

    def _jour(self, t: float | None = None) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(self._horloge() if t is None else t))

    # ── la cascade, les options, les affectations ─────────────────────────
    def etages(self) -> dict:
        """Les étages possibles : ceux du code, et un par moteur externe installé ou actif."""
        sortie = dict(ETAGES)
        for m in self.liste():
            if m.get("genre") == "externe" and m.get("adaptateur") and m.get("etat") in ("installe", "actif"):
                sortie[m["id"]] = (m["id"], "adaptateur:" + m["adaptateur"], m.get("nom", m["id"]), "moteur externe : %s" % m.get("version", ""))
        return sortie

    def cascade(self) -> list:
        """L'ordre des étages et lesquels sont actifs. Un étage dont le moteur n'est plus « actif » au registre est dit éteint sans perdre sa place."""
        d = self._lire()
        voulu = d.get("cascade") or [{"id": i, "on": on} for i, on in CASCADE_DEFAUT]
        connus = self.etages()
        etats = {m["id"]: m.get("etat") for m in self.liste()}
        sortie = []
        for e in voulu:
            if e["id"] in connus:
                moteur = connus[e["id"]][0]
                sortie.append({"id": e["id"], "on": bool(e["on"]), "actif": etats.get(moteur, "actif" if moteur in NATIFS else "prevu") == "actif",
                               "nom": connus[e["id"]][2], "cout": connus[e["id"]][3]})
        for i, (moteur, _c, nom, cout) in connus.items():                       # un étage nouveau (un moteur qu'on vient d'installer) arrive en fin, éteint
            if i not in {x["id"] for x in sortie}:
                sortie.append({"id": i, "on": False, "actif": etats.get(moteur, "actif" if moteur in NATIFS else "prevu") == "actif", "nom": nom, "cout": cout})
        return sortie

    def regler_cascade(self, ordre: list) -> list:
        connus = self.etages()
        ids = [str(x.get("id")) for x in ordre]
        if len(set(ids)) != len(ids) or any(i not in connus for i in ids):
            raise ValueError("cascade invalide : des étages inconnus ou en double (%s)" % ", ".join(sorted(connus)))
        with self._verrou:
            d = self._lire()
            d["cascade"] = [{"id": str(x["id"]), "on": bool(x.get("on"))} for x in ordre]
            self._ecrire(d)
        return self.cascade()

    def options(self) -> dict:
        return dict(OPTIONS_DEFAUT, **(self._lire().get("options") or {}))

    def regler_options(self, **opts) -> dict:
        inconnues = [k for k in opts if k not in OPTIONS_DEFAUT]
        if inconnues:
            raise ValueError("option inconnue : %s (%s)" % (", ".join(inconnues), ", ".join(OPTIONS_DEFAUT)))
        with self._verrou:
            d = self._lire()
            d["options"] = dict(OPTIONS_DEFAUT, **(d.get("options") or {}), **{k: bool(v) for k, v in opts.items()})
            self._ecrire(d)
            return d["options"]

    def affectation(self, gid: str) -> str:
        return (self._lire().get("affectations") or {}).get(gid, "auto")

    def affectations(self) -> dict:
        return dict(self._lire().get("affectations") or {})

    def affecter(self, gid: str, etage: str) -> str:
        """Force un étage sur un point (« auto » : la cascade). Un étage inconnu est refusé."""
        if etage != "auto" and etage not in self.etages():
            raise ValueError("étage inconnu : « %s » (auto, %s)" % (etage, ", ".join(sorted(self.etages()))))
        with self._verrou:
            d = self._lire()
            aff = d.setdefault("affectations", {})
            if etage == "auto":
                aff.pop(gid, None)
            else:
                aff[gid] = etage
            self._ecrire(d)
        return etage

    # ── les plafonds et la dépense ────────────────────────────────────────
    def plafond(self, ident: str) -> dict:
        return dict((self._lire().get("plafonds") or {}).get(ident, {}))

    def plafonner(self, ident: str, jetons_jour: int | None = None, essais_jour: int | None = None) -> dict:
        for nom, v in (("jetons_jour", jetons_jour), ("essais_jour", essais_jour)):
            if v is not None and (int(v) < 0 or int(v) > 10**9):
                raise ValueError("%s invalide : %r" % (nom, v))
        with self._verrou:
            d = self._lire()
            if ident not in d["moteurs"]:
                raise ValueError("moteur inconnu : « %s »" % ident)
            p = d.setdefault("plafonds", {}).setdefault(ident, {})
            if jetons_jour is not None:
                p["jetons_jour"] = int(jetons_jour)
            if essais_jour is not None:
                p["essais_jour"] = int(essais_jour)
            self._ecrire(d)
            return dict(p)

    def depense(self, ident: str, jour: str | None = None) -> dict:
        return dict((((self._lire().get("depense") or {}).get(ident) or {}).get(jour or self._jour())) or {"jetons": 0, "essais": 0, "appels": 0})

    def depense_mois(self, ident: str | None = None) -> int:
        """Les jetons dépensés sur les 30 derniers jours (un moteur, ou tous)."""
        d = self._lire().get("depense") or {}
        debut = self._jour(self._horloge() - 29 * 86400)
        return sum(v.get("jetons", 0) for i, jours in d.items() if ident in (None, i) for j, v in jours.items() if j >= debut)

    def depasse(self, ident: str) -> str:
        """Pourquoi un moteur ne doit pas chercher maintenant (« » s'il le peut) : son plafond du jour, ou le budget du mois."""
        p, jour, b = self.plafond(ident), self.depense(ident), self.budget()
        if p.get("jetons_jour") is not None and jour["jetons"] >= p["jetons_jour"]:
            return "plafond de %d jetons par jour atteint pour ce moteur" % p["jetons_jour"]
        if p.get("essais_jour") is not None and jour["essais"] >= p["essais_jour"]:
            return "plafond de %d essais par jour atteint pour ce moteur" % p["essais_jour"]
        if b["couper_au_plafond"] and self.depense_mois() >= b["jetons_mois"]:
            return "budget du mois atteint (%d jetons)" % b["jetons_mois"]
        return ""

    def budget(self) -> dict:
        return dict(BUDGET_DEFAUT, **(self._lire().get("budget") or {}))

    def regler_budget(self, **vals) -> dict:
        inconnus = [k for k in vals if k not in BUDGET_DEFAUT]
        if inconnus:
            raise ValueError("réglage de budget inconnu : %s (%s)" % (", ".join(inconnus), ", ".join(BUDGET_DEFAUT)))
        if "jetons_mois" in vals and not 0 <= int(vals["jetons_mois"]) <= 10**10:
            raise ValueError("jetons_mois invalide : %r" % (vals["jetons_mois"],))
        if "alerte_pct" in vals and not 1 <= int(vals["alerte_pct"]) <= 100:
            raise ValueError("alerte_pct invalide : %r (1 à 100)" % (vals["alerte_pct"],))
        with self._verrou:
            d = self._lire()
            b = dict(BUDGET_DEFAUT, **(d.get("budget") or {}))
            for k, v in vals.items():
                b[k] = bool(v) if isinstance(BUDGET_DEFAUT[k], bool) else int(v)
            d["budget"] = b
            self._ecrire(d)
            return b

    # ── le journal, le relais, les courses ────────────────────────────────
    def journaliser(self, genre: str, texte: str) -> None:
        with self._verrou:
            d = self._lire()
            d.setdefault("journal", []).append({"ts": self._horloge(), "genre": str(genre), "texte": str(texte)[:300]})
            d["journal"] = d["journal"][-200:]
            self._ecrire(d)

    def journal(self, n: int = 50) -> list:
        return (self._lire().get("journal") or [])[-int(n):][::-1]

    def noter_relais(self, entree: dict) -> None:
        with self._verrou:
            d = self._lire()
            d.setdefault("relais", []).append(dict(entree, ts=self._horloge()))
            d["relais"] = d["relais"][-200:]
            self._ecrire(d)

    def relais(self, n: int = 30) -> list:
        return (self._lire().get("relais") or [])[-int(n):][::-1]

    def noter_course(self, course: dict) -> int:
        with self._verrou:
            d = self._lire()
            cs = d.setdefault("courses", [])
            num = (cs[-1]["id"] + 1) if cs else 1
            cs.append(dict(course, id=num, ts=self._horloge(), gardee=False))
            d["courses"] = cs[-60:]
            self._ecrire(d)
            return num

    def courses(self, n: int = 20) -> list:
        return [dict(c, resultats=[{k: v for k, v in r.items() if k != "texte"} for r in c.get("resultats", [])]) for c in (self._lire().get("courses") or [])[-int(n):][::-1]]

    def course(self, num: int) -> dict | None:
        return next((c for c in (self._lire().get("courses") or []) if c["id"] == int(num)), None)

    def garder_course(self, num: int) -> bool:
        with self._verrou:
            d = self._lire()
            for c in d.get("courses") or []:
                if c["id"] == int(num):
                    c["gardee"] = True
                    self._ecrire(d)
                    return True
        return False

    def objectifs(self) -> dict:
        """Les poids du choix entre variantes prouvées, et la tolérance de régression (voir CN_objectifs)."""
        d = self._lire().get("objectifs") or {}
        return {"poids": dict(POIDS_OBJECTIFS, **(d.get("poids") or {})), "tolerance_pct": float(d.get("tolerance_pct", 25.0))}

    def regler_objectifs(self, poids: dict | None = None, tolerance_pct: float | None = None) -> dict:
        try:
            from . import CN_objectifs as O
        except ImportError:
            from noyau import CN_objectifs as O                          # type: ignore
        with self._verrou:
            d = self._lire()
            actuel = self.objectifs()
            nouveau = O.poids_valides(dict(actuel["poids"], **(poids or {})))
            tol = actuel["tolerance_pct"] if tolerance_pct is None else float(tolerance_pct)
            if not 0 <= tol <= 100:
                raise ValueError("tolérance invalide : %r (0 à 100)" % (tolerance_pct,))
            d["objectifs"] = {"poids": nouveau, "tolerance_pct": tol}
            self._ecrire(d)
            return d["objectifs"]

    def moteur_de(self, gid: str, num: int) -> str:
        return self._lire()["attribution"].get("%s#%d" % (gid, int(num)), "inconnu")

    def liste(self) -> list:
        d = self._lire()
        return [dict(m, id=i) for i, m in sorted(d["moteurs"].items())]

    def moteurs_actifs(self) -> list:
        return [m["id"] for m in self.liste() if m.get("etat") == "actif"]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (la frontière entre Cassandra et ses moteurs ne s'évolue pas : c'est elle qui garde).
# CN : l'hôte de processus, le relais de modèles et le registre ; tout ce qui décide d'une mise en service reste dans noyau/CN_evolution.py.
# LIEN : orfan/CN_moteur_hote.py (le côté moteur), noyau/CN_points.py (_Travailleur : processus, bac, délai), modules/evolution (la coquille).
