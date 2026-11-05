# ══════════════════════════════════════════════
# TITRE      : La course, la cascade et les affectations des moteurs
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #92c7e7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Décide quel moteur cherche pour quel point : la cascade (le gratuit d'abord), l'affectation forcée, la course entre moteurs, les plafonds par moteur ; rien n'est mis en service par une course.
# MÉTHODE    : un moteur à la fois dans son processus, jugé par le même juge sur le même corpus ; chaque étage compte ses jetons ; un plafond atteint saute l'étage et le dit.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=92c7e7 ▼▼▼
"""Lots 3 de la maquette d'Évolution : course, cascade, affectations, budget par moteur.

La CASCADE : les étages actifs, dans l'ordre (le gratuit d'abord). `arret_premiere` : on s'arrête à la première variante prouvée. `modele_si_chaud` : un étage qui dépense un modèle
n'est essayé que si le profil montre un point chaud (une ligne qui porte >= 40 % du travail). `course_si_deux` : après un premier succès, l'étage suivant est essayé et la meilleure des
deux variantes (rendement) prend la place.

L'AFFECTATION : un étage forcé sur un point ignore la cascade.

La COURSE : plusieurs étages sur le même point, le même corpus, le même budget par moteur ; un tableau (variantes, équivalentes, gain, tient hors du vu, jetons, rendement, mémoire,
durée), un classement selon le critère (rendement = points de gain par millier de jetons, gain brut, durée). RIEN n'est écrit dans le stock : adopter est un geste à part qui REJUGE
la variante gardée, puis la met en ombre comme toute pièce.

Le rendement d'un étage gratuit : ses jetons comptent pour au moins 1 000 (sinon un étage à zéro jeton aurait un rendement infini et gagnerait toujours).
"""
from __future__ import annotations

import importlib
import time

try:
    from .CN_moteurs import ETAGES, MoteurProcessus
except ImportError:                                                  # chargé par son chemin
    from noyau.CN_moteurs import ETAGES, MoteurProcessus             # type: ignore

CRITERES = ("rendement", "brut", "duree")
BUDGETS = ("jetons", "essais", "temps")
ETAGES_A_MODELE = {"orfan/modele", "evolutif"}                      # les étages qui dépensent un modèle d'office (Frugal décide seul, d'après son profil) ; un moteur externe aussi
PLANCHER_JETONS = 1000


def rendement(gain, jetons) -> float:
    """Points de gain pour mille jetons dépensés (au moins mille comptés)."""
    return round((gain or 0.0) / (max(int(jetons or 0), PLANCHER_JETONS) / 1000.0), 2)


class Orchestrateur:
    """`appeler_modele(prompt, role) -> texte` : le registre de modèles de Cassandra. `isoles()` : les étages d'Orfan tournent-ils dans leur processus ? `en_ligne(choix)` : l'Orfan en ligne (le serveur)."""

    def __init__(self, evo, registre, appeler_modele=None, isoles=lambda: True, en_ligne=None, horloge=time.time, delai_s: float = 120.0, options_moteur=None):
        self.options_moteur = options_moteur
        self.evo, self.reg, self.appeler_modele, self._isoles, self._en_ligne = evo, registre, appeler_modele, isoles, en_ligne
        self._horloge, self.delai_s = horloge, float(delai_s)

    # ── les moteurs ──────────────────────────────────────────────────────
    def _moteur(self, etage: str, budget_type: str = "jetons", limite: int | None = None):
        etages = self.reg.etages()
        if etage not in etages:
            raise ValueError("étage inconnu : « %s » (%s)" % (etage, ", ".join(sorted(etages))))
        ident, choix, _nom, _cout = etages[etage]
        reste = None
        p = self.reg.plafond(ident)
        if p.get("jetons_jour"):                                   # 0 = aucun plafond
            reste = max(0, p["jetons_jour"] - self.reg.depense(ident)["jetons"])
        if choix in ("deterministe", "modele") and not self._isoles() and self._en_ligne is not None:
            return self._en_ligne(choix)                                # l'Orfan du serveur : jamais un candidat exécuté ici, il ne fait qu'écrire du texte
        kw = {"appeler_modele": self.appeler_modele, "nom": etage, "delai_s": self.delai_s, "on_relais": lambda e: self.reg.noter_relais(dict(e, moteur=etage))}
        max_jetons = limite if budget_type == "jetons" and limite else None
        if reste is not None:
            max_jetons = reste if max_jetons is None else min(max_jetons, reste)
        if max_jetons is not None:
            kw["max_jetons"] = int(max_jetons)
        if budget_type == "essais" and limite:
            kw["max_appels"] = int(limite)
        if budget_type == "temps" and limite:
            kw["delai_s"] = float(limite)
        if choix.startswith("adaptateur:"):
            m = next((x for x in self.reg.liste() if x["id"] == ident), {})
            kw["python"] = m.get("python", "")
        kw["carnet"] = self.reg
        if callable(self.options_moteur):
            kw["options"] = self.options_moteur(choix)
        return MoteurProcessus(choix, **kw)

    def _chaud(self, module: str, point: str) -> bool:
        """Le profil de la référence sur les entrées visibles montre-t-il une ligne qui porte >= 40 % du travail ? (La référence est le code de Cassandra : on peut la profiler ici.)"""
        try:
            orfan = importlib.import_module("orfan.CN_orfan")
            ref = self.evo.points.reference(module, point)
            visibles = [c["entree"] for c in self.evo.rejeu.corpus(ref["gid"], "visible")[:20]]
            return orfan.point_chaud(ref["fichier"].read_text(encoding="utf-8"), ref["fonction"], visibles, 40.0) is not None
        except Exception:
            return True                                                 # un profil qui échoue ne ferme pas la porte : on laisse l'étage essayer

    def _lancer(self, etage: str, module: str, point: str, budget: int, ecrire: bool, budget_type: str = "jetons", limite: int | None = None) -> dict:
        """Un étage : ses garde-fous, sa recherche, ce qu'elle a coûté. Rend {etage, moteur, saute, raison, r, stats, duree_s}."""
        ident = self.reg.etages()[etage][0]
        sortie = {"etage": etage, "moteur": ident, "saute": False, "raison": "", "r": None, "stats": {}, "duree_s": 0.0}
        etat = next((m.get("etat") for m in self.reg.liste() if m["id"] == ident), "actif" if ident in ("orfan", "frugal", "evolutif") else "prevu")
        if etat != "actif":
            sortie.update(saute=True, raison="moteur « %s » non actif (%s)" % (ident, etat))
            return sortie
        raison = self.reg.depasse(ident)
        if raison:
            sortie.update(saute=True, raison=raison)
            return sortie
        moteur = self._moteur(etage, budget_type, limite)
        debut = time.monotonic()
        try:
            if ecrire:
                r = self.evo.proposer(module, point, moteur, budget)
            else:
                r = self.evo.essayer(module, point, moteur, budget)
        except Exception as e:
            r = {"ok": False, "erreur": "%s : %s" % (type(e).__name__, e), "essais": [], "retenus": [], "meilleur": None, "raison": "%s : %s" % (type(e).__name__, e), "piece": None}
        sortie["duree_s"] = round(time.monotonic() - debut, 2)
        sortie["stats"] = dict(getattr(moteur, "stats", {}) or {})
        sortie["r"] = r
        essais = r.get("essais") or []
        self.reg.compter(ident, sortie["stats"], essais=max(1, len(essais)))
        try:
            if r.get("erreur"):                                         # le moteur a échoué lui-même (exception, délai) : on le retient pour l'écran
                self.reg.defaillance(ident, str(r.get("erreur")))
            else:
                self.reg.retablir(ident)
        except Exception:
            pass                                                        # le registre est un livre de comptes : sa panne ne défait pas une recherche
        return sortie

    # ── la cascade ───────────────────────────────────────────────────────
    def proposer(self, module: str, point: str, budget: int = 3, etage: str = "") -> dict:
        """La proposition par la cascade (ou l'étage forcé sur ce point). Rend le résultat d'un `proposer` du noyau, plus {etages:[{id, saute, raison, ok}], moteur}."""
        gid = "%s.%s" % (module, point)
        forcé = etage or self.reg.affectation(gid)
        opts = self.reg.options()
        etages = [forcé] if forcé != "auto" else [e["id"] for e in self.reg.cascade() if e["on"] and e["actif"]]
        chaud = None
        rapport, gagnant = [], None
        for etage in etages:
            if forcé == "auto" and opts["modele_si_chaud"] and (etage in ETAGES_A_MODELE or etage not in ETAGES):
                if chaud is None:
                    chaud = self._chaud(module, point)
                if not chaud:
                    rapport.append({"id": etage, "saute": True, "raison": "pas de point chaud : un modèle ne se dépense pas sur un profil étalé", "ok": False})
                    continue
            if gagnant is not None and not opts["course_si_deux"]:
                break
            ecrire = gagnant is None
            lance = self._lancer(etage, module, point, budget, ecrire=ecrire)
            r = lance["r"] or {}
            ok = bool(r.get("ok")) if ecrire else bool(r.get("meilleur"))
            rapport.append({"id": etage, "saute": lance["saute"], "raison": lance["raison"] or ("" if ok else r.get("raison") or r.get("erreur") or "rien de prouvé"), "ok": ok,
                            "jetons": lance["stats"].get("jetons", 0)})
            if lance["saute"] or not ok:
                continue
            if gagnant is None:
                gagnant = {"etage": etage, "lance": lance, "r": r, "gain": (r["piece"] or {}).get("gain_annonce_pct")}
                if not opts["arret_premiere"] and not opts["course_si_deux"]:
                    pass
                continue
            # course entre deux étages : la meilleure des deux (rendement) prend la place
            m = r["meilleur"]
            nouveau = rendement(m["eval"]["gain_pct"], lance["stats"].get("jetons", 0))
            ancien = rendement(gagnant["gain"], gagnant["lance"]["stats"].get("jetons", 0))
            if nouveau > ancien:
                adoption = self.evo.adopter(module, point, m["texte"], m.get("hypothese", ""), lance["moteur"])
                if adoption.get("ok"):
                    gagnant = {"etage": etage, "lance": lance, "r": adoption, "gain": adoption["piece"]["gain_annonce_pct"]}
            break
        if gagnant is None:
            derniere = next((x for x in reversed(rapport) if not x["saute"]), None)
            return {"ok": False, "raison": (derniere or {}).get("raison") or "aucun étage n'a pu chercher (%s)" % "; ".join("%s : %s" % (x["id"], x["raison"]) for x in rapport) if rapport else "aucun étage actif",
                    "essais": [], "piece": None, "etages": rapport, "moteur": ""}
        res = dict(gagnant["r"])
        piece = res.get("piece")
        if piece:
            ident = gagnant["lance"]["moteur"]
            piece["moteur"] = ident
            self.reg.attribuer(piece["gid"], piece["num"], ident)
            self.reg.journaliser("proposition", "%s : EC%d par « %s » (−%s %%)" % (piece["gid"], piece["num"], gagnant["etage"], piece.get("gain_annonce_pct")))
        res["etages"], res["moteur"] = rapport, gagnant["lance"]["moteur"]
        return res

    # ── la course ────────────────────────────────────────────────────────
    def course(self, module: str, point: str, etages: list, budget_type: str = "jetons", limite: int = 20000, critere: str = "rendement") -> dict:
        if critere not in CRITERES:
            raise ValueError("critère inconnu : « %s » (%s)" % (critere, ", ".join(CRITERES)))
        if budget_type not in BUDGETS:
            raise ValueError("budget inconnu : « %s » (%s)" % (budget_type, ", ".join(BUDGETS)))
        etages = [str(e) for e in etages]
        if len(etages) < 2:
            raise ValueError("une course oppose au moins deux étages")
        connus = self.reg.etages()
        if any(e not in connus for e in etages) or len(set(etages)) != len(etages):
            raise ValueError("étages inconnus ou en double (%s)" % ", ".join(sorted(connus)))
        limite = int(limite)
        if limite <= 0:
            raise ValueError("limite invalide : %r" % (limite,))
        budget = min(limite, 10) if budget_type == "essais" else 3
        lignes = []
        for etage in etages:
            lance = self._lancer(etage, module, point, budget, ecrire=False, budget_type=budget_type, limite=limite)
            r = lance["r"] or {}
            meilleur = r.get("meilleur")
            essais = r.get("essais") or []
            equiv = [e for e in essais if e.get("verdict") in ("equivalente", "corpus_trop_etroit")]
            gains = [e["gain_pct"] for e in equiv if e.get("gain_pct") is not None]
            jetons = lance["stats"].get("jetons", 0)
            gain = meilleur["eval"]["gain_pct"] if meilleur else (max(gains) if gains else 0.0)
            lignes.append({"etage": etage, "nom": connus[etage][2], "moteur": lance["moteur"], "saute": lance["saute"], "raison": lance["raison"] or r.get("raison", "") or r.get("erreur", ""),
                           "variantes": len(essais), "equivalentes": len(equiv), "gain": round(max(gain, 0.0), 1), "tient": bool(meilleur and meilleur["eval"].get("gain_tient")),
                           "jetons": jetons, "rendement": rendement(gain if meilleur else 0.0, jetons), "memoire": (meilleur or {}).get("objectifs", {}).get("memoire"),
                           "duree_s": lance["duree_s"], "texte": (meilleur or {}).get("texte", ""), "hypothese": (meilleur or {}).get("hypothese", "")})
        cle = {"rendement": lambda x: x["rendement"], "brut": lambda x: x["gain"], "duree": lambda x: -x["duree_s"]}[critere]
        lignes.sort(key=lambda x: (bool(x["texte"]), cle(x)), reverse=True)
        num = self.reg.noter_course({"point": "%s.%s" % (module, point), "critere": critere, "budget": budget_type, "limite": limite, "resultats": lignes,
                                     "vainqueur": lignes[0]["etage"] if lignes and lignes[0]["texte"] else ""})
        self.reg.journaliser("course", "%s.%s : %s (%s)" % (module, point, ", ".join(etages), critere))
        return {"id": num, "point": "%s.%s" % (module, point), "critere": critere, "resultats": [{k: v for k, v in x.items() if k != "texte"} for x in lignes],
                "vainqueur": lignes[0]["etage"] if lignes and lignes[0]["texte"] else ""}

    def adopter(self, num: int, etage: str) -> dict:
        """Met en place la variante qu'une course a gardée pour cet étage : rejugée, puis écrite en ombre. Un étage sans variante prouvée ne s'adopte pas."""
        c = self.reg.course(num)
        if c is None:
            raise ValueError("course inconnue : %r" % (num,))
        ligne = next((x for x in c["resultats"] if x["etage"] == etage), None)
        if ligne is None or not ligne.get("texte"):
            raise ValueError("l'étage « %s » n'a rien de prouvé dans cette course" % etage)
        module, point = c["point"].split(".", 1)
        res = self.evo.adopter(module, point, ligne["texte"], ligne.get("hypothese", ""), ligne["moteur"])
        piece = res.get("piece")
        if piece:
            piece["moteur"] = ligne["moteur"]
            self.reg.attribuer(piece["gid"], piece["num"], ligne["moteur"])
            self.reg.journaliser("adoption", "%s : EC%d adoptée depuis la course %d (%s)" % (piece["gid"], piece["num"], c["id"], etage))
        return res
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (qui cherche, avec quel budget, est une décision du noyau).
# CN : la cascade, les affectations, la course, les plafonds par moteur ; la mise en service reste à noyau/CN_evolution.py.
# LIEN : noyau/CN_moteurs.py (le registre et les processus), noyau/CN_evolution.py (le juge), modules/evolution (la coquille).
