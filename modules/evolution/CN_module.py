# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Évolution : le pilotage de l'évolution de Cassandra
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.5.0  #514bc7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : expose l'évolution du noyau comme capacités de Cassandra : cibles, état, proposer, retour, visiter, et un moteur qui fait avancer les paliers.
# MÉTHODE    : une coquille mince : tout ce qui décide vit dans noyau/CN_evolution.py ; le moteur de recherche est chargé par son chemin d'import (le contrat d'adaptateur).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=514bc7 ▼▼▼
"""Le module « Évolution » : la coquille entre Cassandra (droits, paliers, preuves, retours, réglages) et le service d'évolution du noyau.

Il ne propose rien lui-même et ne juge rien : le moteur de recherche (Orfan) rend du texte, l'évaluateur du noyau le juge, le routage du noyau le met en service.
Ce module ne fait que donner à ces gestes leurs droits, leur preuve et leur retour, comme à tout geste de Cassandra qui écrit.
"""
from __future__ import annotations

import importlib
import importlib.util
import re

_MOTEUR_PERMIS = re.compile(r"^orfan(\.[A-Za-z_][A-Za-z0-9_]*)+$")      # un moteur se trouve DANS le paquet orfan : un réglage n'importe pas n'importe quel module du serveur


def brancher(ctx):
    evo = ctx.evolution()

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
        except Exception:
            v = None
        return defaut if v in (None, "") else v

    def registre():
        """Le registre des moteurs, à côté de la base d'évolution ; Orfan y est toujours déclaré (natif, actif)."""
        mot = importlib.import_module("noyau.CN_moteurs")
        r = mot.Registre(evo.rejeu.chemin.parent / "moteurs.json")
        if not any(m["id"] == "orfan" for m in r.liste()):
            r.declarer("orfan", "Orfan", genre="natif", etat="actif")
        return r

    def appeler_modele(prompt):
        """Le modèle du rôle choisi, par le module Modèles (une lecture). Un modèle muet ou absent est une erreur DITE, jamais une réponse inventée."""
        r = ctx.executer_lecture("modeles.completer", messages=[{"role": "user", "content": prompt}], role=str(reglage("modele_role", "evolution")),
                                 max_tokens=3000, temperature=0.2)
        if not r or not r.get("ok"):
            raise RuntimeError((r or {}).get("erreur") or "le modèle n'a pas répondu (module Modèles absent, ou rôle « %s » sans modèle)" % reglage("modele_role", "evolution"))
        return r.get("texte") or ""

    def moteur_de_recherche(choix):
        nom = str(reglage("moteur_orfan", "orfan.CN_orfan"))
        if not _MOTEUR_PERMIS.match(nom):
            raise ValueError("moteur de recherche refusé : « %s » (un moteur vit dans le paquet orfan, par ex. orfan.CN_orfan)" % nom)
        orfan = importlib.import_module(nom)
        if str(reglage("moteurs_isoles", "non")) == "oui":                   # le moteur dans son processus : sans clé, plafonné, tué au délai ; les modèles passent par le relais
            mot = importlib.import_module("noyau.CN_moteurs")
            return mot.MoteurProcessus(choix, appeler_modele=lambda prompt, role="executant": appeler_modele(prompt), orfan=importlib.util.find_spec(nom).origin)
        if choix == "modele":
            return orfan.MoteurModele(appeler_modele)
        if choix == "les_deux":
            return orfan.MoteurComposite(orfan.MoteurDeterministe(), orfan.MoteurModele(appeler_modele))
        return orfan.MoteurDeterministe()

    def decouper(point):
        gid = str(point or "").strip()
        if gid not in evo.points.points():
            raise ValueError("point d'évolution inconnu : « %s » (voir evolution.cibles)" % gid)
        return gid.split(".", 1)

    # ── les lectures ─────────────────────────────────────────────────────
    def absorber_externes():
        """Les appels que le démon du Sensorium garde dans son propre fichier (un autre processus) rejoignent le corpus de rejeu : seuls les deltas sont pris."""
        try:
            evo.rejeu.absorber(evo.rejeu.chemin.parent / "sensorium" / "rejeu_sensorium.db")
        except Exception:
            pass                                                   # un fichier du démon illisible ne doit jamais gêner l'écran

    def cibles(c):
        absorber_externes()
        return {"cibles": evo.cibles()}

    def etat(c):
        absorber_externes()
        points = []
        for gid in evo.points.points():
            m, p = gid.split(".", 1)
            points.append(dict(evo.points.etat(m, p), corpus=evo.rejeu.stats(gid)))
        return {"cibles": evo.cibles(), "pieces": evo.pieces(), "points": points, "chaine": evo.verifier_chaine(), "journal": evo.chaine(None, 40), "seuils": {k: (list(v) if isinstance(v, tuple) else v) for k, v in evo.seuils.items()},
                "tombes": {gid: len(evo.tombes(gid)) for gid in evo.points.points()}}

    # ── les gestes ───────────────────────────────────────────────────────
    def proposer(c, point="", moteur="", budget=0):
        m, p = decouper(point)
        evo.seuils["propositions_par_jour"] = max(1, int(reglage("propositions_par_jour", evo.seuils.get("propositions_par_jour", 20))))      # le réglage de l'admin l'emporte sur la valeur du fichier
        choix = str(moteur or reglage("moteur_defaut", "deterministe"))
        if choix not in ("deterministe", "modele", "les_deux"):
            raise ValueError("moteur inconnu : « %s » (deterministe, modele, les_deux)" % choix)
        moteur = moteur_de_recherche(choix)
        r = evo.proposer(m, p, moteur, max(1, min(10, int(budget) or int(reglage("budget_essais", 3)))))
        r["moteur"] = choix
        try:
            reg = registre()
            reg.compter("orfan", getattr(moteur, "stats", {}), essais=len(r.get("essais") or []))
            if r.get("piece"):
                reg.attribuer(r["piece"]["gid"], r["piece"]["num"], "orfan")
                r["piece"]["moteur"] = "orfan"
        except Exception as e:                                    # le registre est un livre de comptes : son panne ne défait pas une pièce prouvée, elle se dit
            r["registre"] = "non tenu : %s" % e
        return r

    def prouver_proposition(c, res):
        if not res.get("piece"):
            return True                                        # rien n'a été écrit : rien à prouver, et rien à défaire
        piece = res["piece"]
        vivante = [x for x in evo.pieces(piece["gid"]) if x["num"] == piece["num"] and x["etat"] == "ombre"]
        return bool(vivante) and evo.verifier_chaine()["ok"]

    def defaire_proposition(c, res):
        if res.get("piece"):
            evo.retour(res["piece"]["gid"], "retour arrière de la proposition")

    def retour(c, point="", raison="retour demandé"):
        decouper(point)
        return {"point": point, "retraits": evo.retour(point, str(raison or "retour demandé"))}

    def prouver_retour(c, res):
        m, p = res["point"].split(".", 1)
        e = evo.points.etat(m, p)
        return (e["routage"] or {}).get("mode") in (None, "arret") and not any(x["etat"] in ("ombre", "palier_10", "palier_50", "en_service") for x in evo.pieces(res["point"]))

    def sans_retour(c, res):
        raise ValueError("aucun retour automatique : une pièce retirée se propose de nouveau (evolution.proposer)")

    def moteurs(c):
        return {"moteurs": registre().liste(), "isoles": str(reglage("moteurs_isoles", "non")) == "oui"}

    def installateur():
        """L'installateur : catalogue et environnements à côté de la base d'évolution, scellé par la clé de l'instance (sans clé, rien ne se scelle : rien ne s'installe)."""
        cle = evo.points._cle()
        if not cle:
            raise ValueError("pas de clé d'instance (exiger_sceau est désactivé) : un catalogue ne peut être cru, aucun moteur ne s'installe")
        ins = importlib.import_module("noyau.CN_installateur")
        base = evo.rejeu.chemin.parent
        return ins.Installateur(base / "moteurs", base / "moteurs-catalogue.json", cle, registre=registre())

    def moteur_installer(c, moteur=""):
        r = installateur().installer(str(moteur or "").strip())
        r["moteur"] = str(moteur or "").strip()
        return r

    def prouver_installation(c, res):
        if not res.get("ok"):
            return True                                        # rien n'a été installé : rien à prouver, et l'échec a déjà tout défait
        return any(m["id"] == res["moteur"] and m["etat"] == "installe" for m in registre().liste())

    def defaire_installation(c, res):
        if res.get("ok"):
            installateur().desinstaller(res["moteur"])

    def moteur_etat(c, moteur="", etat=""):
        reg = registre()
        avant = next((m["etat"] for m in reg.liste() if m["id"] == moteur), None)
        if avant is None:
            raise ValueError("moteur inconnu : « %s » (voir evolution.moteurs)" % moteur)
        reg.etat(str(moteur), str(etat))
        return {"moteur": str(moteur), "avant": avant, "etat": str(etat)}

    def prouver_etat(c, res):
        return any(m["id"] == res["moteur"] and m["etat"] == res["etat"] for m in registre().liste())

    def defaire_etat(c, res):
        registre().etat(res["moteur"], res["avant"])

    def visiter(c):
        return {"visites": evo.visiter()}

    def prouver_visite(c, res):
        return all(v.get("verdict") for v in res["visites"])

    def purger_compte(c, compte=""):
        compte = str(compte or "").strip()
        if not compte:
            raise ValueError("quel compte ? (purger_compte compte=…)")
        r = evo.rejeu.purger_compte(compte)
        r["compte"] = compte
        return r

    def prouver_purge(c, res):
        return evo.rejeu.comptes().get(res["compte"], 0) == 0

    # ── le moteur périodique : les paliers avancent seulement si les preuves le permettent ──
    def tick(c):
        absorber_externes()
        avances = evo.tick()
        visites = evo.visiter(maximum=1)                       # une visite est une évaluation entière : une seule par passage
        return {"avances": avances, "visites": visites}

    ctx.implementer("cibles", cibles)
    ctx.implementer("etat", etat)
    ctx.implementer("moteurs", moteurs)
    ctx.implementer("moteur_installer", moteur_installer, prouver_installation, defaire_installation)
    ctx.implementer("moteur_etat", moteur_etat, prouver_etat, defaire_etat)
    ctx.implementer("proposer", proposer, prouver_proposition, defaire_proposition)
    ctx.implementer("retour", retour, prouver_retour, sans_retour)
    ctx.implementer("visiter", visiter, prouver_visite, sans_retour)
    ctx.implementer("purger_compte", purger_compte, prouver_purge, sans_retour)
    ctx.moteur("tick", tick)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la coquille du module Évolution (capacités, preuves, retours, moteur périodique). Aucune logique d'évolution ici.
# EC : néant. Le module qui pilote l'évolution ne s'évolue pas (docs/CN_NEXUS.md §4).
# LIEN : noyau/CN_evolution.py (le service), noyau/CN_evaluateur.py (le juge), orfan/CN_orfan.py (le moteur de recherche), modules/modeles (les modèles par rôle).
