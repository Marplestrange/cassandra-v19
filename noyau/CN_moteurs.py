# ══════════════════════════════════════════════
# TITRE      : Les moteurs de recherche d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #e5e857
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Héberge un moteur de recherche dans un processus à part (protocole + relais de modèles plafonné) et tient le registre des moteurs et l'attribution des pièces.
# MÉTHODE    : le moteur parle par lignes JSON ; ses demandes de modèle passent par un relais qui compte appels et jetons et refuse au plafond ; le registre est un fichier JSON écrit par remplacement.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e5e857 ▼▼▼
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
import tempfile
import threading
import time
from pathlib import Path

try:
    from .CN_points import DelaiEC, ErreurEC, _Travailleur, bac_os
except ImportError:                                                  # chargé par son chemin (un banc, un module)
    from noyau.CN_points import DelaiEC, ErreurEC, _Travailleur, bac_os          # type: ignore

CHOIX = ("deterministe", "modele", "les_deux")
DELAI_MOTEUR_S = 120.0
MEMOIRE_MOTEUR_MO = 768
MAX_APPELS_MODELE = 6
MAX_JETONS = 40000
ETATS = ("actif", "installe", "prevu")


def _jetons(texte: str) -> int:
    """Une estimation sans bibliothèque : un jeton pour quatre caractères. Le plafond est une garde, pas une facture."""
    return max(1, len(str(texte)) // 4)


class MoteurProcessus:
    """Un moteur de recherche dans son processus. `appeler_modele(prompt, role) -> texte` est fourni par Cassandra (son registre de modèles) ; le moteur n'y a accès que par le relais."""

    def __init__(self, choix: str = "deterministe", appeler_modele=None, orfan: str | Path | None = None, delai_s: float = DELAI_MOTEUR_S, memoire_mo: int = MEMOIRE_MOTEUR_MO,
                 max_appels: int = MAX_APPELS_MODELE, max_jetons: int = MAX_JETONS, bac: str = "auto", nom: str = "orfan-processus"):
        if choix not in CHOIX:
            raise ValueError("choix de moteur inconnu : %r (%s)" % (choix, ", ".join(CHOIX)))
        racine = Path(__file__).resolve().parent.parent / "orfan"
        self.choix, self.nom = choix, nom
        self.orfan = str(orfan or racine / "CN_orfan.py")
        self.hote = str(racine / "CN_moteur_hote.py")
        self.appeler_modele, self.delai_s, self.memoire_mo, self.bac = appeler_modele, float(delai_s), int(memoire_mo), bac
        self.max_appels, self.max_jetons = int(max_appels), int(max_jetons)
        self.stats = {"propositions": 0, "appels_modele": 0, "refus": 0, "jetons": 0, "duree_s": 0.0}

    def proposer(self, contexte: dict) -> list:
        debut = time.monotonic()
        t = _Travailleur(self.memoire_mo, self.bac, script=self.hote, arguments=(self.orfan, self.choix))
        appels = jetons = 0
        try:
            t.envoyer({"op": "proposer", "contexte": {k: v for k, v in contexte.items() if not callable(v)}})          # une fonction ne traverse pas la frontière : le moteur reçoit du texte et des données
            while True:
                reste = self.delai_s - (time.monotonic() - debut)
                if reste <= 0:
                    t.tuer()
                    raise DelaiEC("délai de %.0f s dépassé : le moteur est tué" % self.delai_s)
                msg = t.recevoir(reste)
                op = msg.get("op")
                if op == "resultat":
                    self.stats["propositions"] += 1
                    return list(msg.get("candidats") or [])
                if op == "erreur":
                    raise ErreurEC("le moteur a échoué : %s" % msg.get("erreur"))
                if op != "modele":
                    raise ErreurEC("message inconnu du moteur : %r" % (op,))
                if self.appeler_modele is None:
                    t.envoyer({"ok": False, "erreur": "aucun modèle n'est branché sur ce moteur"})
                    continue
                if appels >= self.max_appels or jetons >= self.max_jetons:
                    self.stats["refus"] += 1
                    t.envoyer({"ok": False, "erreur": "plafond du relais atteint (%d appels, %d jetons) : la recherche s'arrête là" % (appels, jetons)})
                    continue
                prompt = str(msg.get("prompt", ""))
                appels += 1
                self.stats["appels_modele"] += 1
                try:
                    texte = str(self.appeler_modele(prompt, str(msg.get("role", "executant"))) or "")
                except Exception as e:                                # un modèle muet ou en panne se dit au moteur, il ne tue pas la recherche
                    t.envoyer({"ok": False, "erreur": "le modèle n'a pas répondu : %s" % str(e)[:200]})
                    continue
                n = _jetons(prompt) + _jetons(texte)
                jetons += n
                self.stats["jetons"] += n
                t.envoyer({"ok": True, "texte": texte})
        finally:
            self.stats["duree_s"] = round(self.stats["duree_s"] + time.monotonic() - debut, 3)
            t.tuer()


class Registre:
    """Les moteurs connus et ce qu'ils ont coûté. Un fichier JSON écrit par remplacement (jamais à moitié) ; un fichier illisible se dit, il ne s'efface pas."""

    def __init__(self, chemin: str | Path):
        self.chemin = Path(chemin)
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
            self._ecrire(d)

    def attribuer(self, gid: str, num: int, ident: str) -> None:
        with self._verrou:
            d = self._lire()
            d["attribution"]["%s#%d" % (gid, int(num))] = ident
            if ident in d["moteurs"]:
                d["moteurs"][ident]["pieces"] = d["moteurs"][ident].get("pieces", 0) + 1
            self._ecrire(d)

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
