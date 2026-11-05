# ══════════════════════════════════════════════
# TITRE      : Les tâches de fond d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #d537d2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait tourner en fond ce qui dure des minutes (préparer, installer, mettre à jour un chercheur) et rend son avancement à l'écran qui le demande, au lieu de faire attendre une requête qui expirerait.
# MÉTHODE    : un fil par tâche, un état lisible à tout moment (étapes faites, étape en cours, fin) ; une seule tâche à la fois par chercheur ; la mémoire du processus, rien d'écrit : une tâche perdue au redémarrage se refait.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d537d2 ▼▼▼
"""Les installations durent plusieurs minutes (résoudre les paquets, les télécharger, écrire et éprouver un adaptateur) : la passerelle coupe une requête au bout d'une minute. La tâche tourne
donc dans un fil du serveur et l'écran la relit toutes les secondes (`evolution.moteur_tache`)."""
from __future__ import annotations

import threading
import time
import uuid


class Taches:
    CONSERVEES = 30

    def __init__(self, horloge=time.time):
        self._d: dict = {}
        self._ordre: list = []
        self._verrou = threading.Lock()
        self._horloge = horloge

    def actif(self, ident: str) -> bool:
        with self._verrou:
            return any(t["moteur"] == ident and not t["fini"] for t in self._d.values())

    def lancer(self, nature: str, ident: str, travail, plan=None) -> str:
        """`travail(progres) -> dict` ; `progres(etapes=None, en_cours=None)` met l'état à jour. Rend l'identifiant de la tâche."""
        num = uuid.uuid4().hex[:12]
        t = {"id": num, "nature": nature, "moteur": ident, "plan": list(plan or []), "etapes": [], "en_cours": "", "fini": False, "ok": False, "erreur": "", "debut": self._horloge(), "fin": None, "resultat": {}}
        with self._verrou:
            self._d[num] = t
            self._ordre.append(num)
            for vieux in self._ordre[:-self.CONSERVEES]:
                self._d.pop(vieux, None)
            self._ordre = self._ordre[-self.CONSERVEES:]

        def progres(etapes=None, en_cours=None):
            with self._verrou:
                if etapes is not None:
                    t["etapes"] = [dict(e) for e in etapes]
                if en_cours is not None:
                    t["en_cours"] = str(en_cours)

        def fil():
            try:
                res = travail(progres) or {}
                with self._verrou:
                    t["resultat"] = {k: v for k, v in res.items() if k != "etapes"}
                    if res.get("etapes") is not None:
                        t["etapes"] = [dict(e) for e in res["etapes"]]
                    t["ok"] = bool(res.get("ok"))
            except Exception as e:                                           # une tâche qui plante se dit : elle ne tue jamais le serveur
                with self._verrou:
                    t["erreur"] = "%s : %s" % (type(e).__name__, str(e)[:300])
            finally:
                with self._verrou:
                    t["fini"], t["en_cours"], t["fin"] = True, "", self._horloge()

        threading.Thread(target=fil, daemon=True, name="tache-" + num).start()
        return num

    def lire(self, num: str) -> dict:
        with self._verrou:
            t = self._d.get(str(num))
            if t is None:
                raise ValueError("tâche inconnue : « %s » (perdue au redémarrage du serveur ? refais le geste)" % num)
            return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in t.items()}


TACHES = Taches()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant.
# CN : le suivi des tâches longues d'Évolution ; il ne décide de rien, il relaie l'avancement.
# LIEN : modules/evolution (qui lance les tâches), interface/CN_evolution-ecran.js (qui les relit).
