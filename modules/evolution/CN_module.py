# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Évolution : le pilotage de l'évolution de Cassandra
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.5.0  #82b789
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : expose l'évolution du noyau comme capacités de Cassandra : cibles, état, proposer, retour, visiter, et un moteur qui fait avancer les paliers.
# MÉTHODE    : une coquille mince : tout ce qui décide vit dans noyau/CN_evolution.py ; le moteur de recherche est chargé par son chemin d'import (le contrat d'adaptateur).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=82b789 ▼▼▼
"""Le module « Évolution » : la coquille entre Cassandra (droits, paliers, preuves, retours, réglages) et le service d'évolution du noyau.

Il ne propose rien lui-même et ne juge rien : le moteur de recherche (Orfan) rend du texte, l'évaluateur du noyau le juge, le routage du noyau le met en service.
Ce module ne fait que donner à ces gestes leurs droits, leur preuve et leur retour, comme à tout geste de Cassandra qui écrit.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import sys

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
        connus = {m["id"] for m in r.liste()}
        for ident, nom in mot.NATIFS.items():
            if ident not in connus:
                r.declarer(ident, nom, genre="natif", etat="actif")
        evo.seuils["objectifs"] = r.objectifs()["poids"]                       # le choix entre variantes suit les poids de l'admin
        evo.seuils["tolerance_objectif_pct"] = r.objectifs()["tolerance_pct"]
        return r

    def appeler_modele(prompt, role="executant"):
        """Le modèle du rôle choisi, par le module Modèles (une lecture). « strategie » prend le rôle fort s'il est réglé, sinon le même. Un modèle muet ou absent est une erreur DITE,
        jamais une réponse inventée."""
        nom_role = str(reglage("modele_role_strategie", "") if role == "strategie" else "") or str(reglage("modele_role", "evolution"))
        r = ctx.executer_lecture("modeles.completer", messages=[{"role": "user", "content": prompt}], role=nom_role, max_tokens=3000, temperature=0.2)
        if not r or not r.get("ok"):
            raise RuntimeError((r or {}).get("erreur") or "le modèle n'a pas répondu (module Modèles absent, ou rôle « %s » sans modèle)" % nom_role)
        appeler_modele.dernier_modele = str(r.get("modele") or nom_role)
        return r.get("texte") or ""

    appeler_modele.dernier_modele = ""

    def isoles():
        return str(reglage("moteurs_isoles", "oui")) == "oui"

    def orchestre():
        cou = importlib.import_module("noyau.CN_course")
        return cou.Orchestrateur(evo, registre(), appeler_modele=appeler_modele, isoles=isoles, en_ligne=moteur_en_ligne)

    def moteur_en_ligne(choix):
        """L'Orfan du serveur : il n'écrit que du texte, il n'exécute aucun candidat."""
        nom = str(reglage("moteur_orfan", "orfan.CN_orfan"))
        if not _MOTEUR_PERMIS.match(nom):
            raise ValueError("moteur de recherche refusé : « %s » (un moteur vit dans le paquet orfan, par ex. orfan.CN_orfan)" % nom)
        orfan = importlib.import_module(nom)
        if choix == "modele":
            return orfan.MoteurModele(appeler_modele)
        if choix == "les_deux":
            return orfan.MoteurComposite(orfan.MoteurDeterministe(), orfan.MoteurModele(appeler_modele))
        return orfan.MoteurDeterministe()

    def moteur_de_recherche(choix):
        nom = str(reglage("moteur_orfan", "orfan.CN_orfan"))
        if not _MOTEUR_PERMIS.match(nom):
            raise ValueError("moteur de recherche refusé : « %s » (un moteur vit dans le paquet orfan, par ex. orfan.CN_orfan)" % nom)
        orfan = importlib.import_module(nom)
        if isoles():                   # le moteur dans son processus : sans clé, plafonné, tué au délai ; les modèles passent par le relais
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
        reg = registre()
        pieces = [dict(p, moteur=reg.moteur_de(p["gid"], p["num"])) for p in evo.pieces()]
        return {"cibles": evo.cibles(), "pieces": pieces, "points": points, "chaine": evo.verifier_chaine(), "journal": evo.chaine(None, 40), "seuils": {k: (list(v) if isinstance(v, tuple) else v) for k, v in evo.seuils.items()},
                "tombes": {gid: len(evo.tombes(gid)) for gid in evo.points.points()}}

    # ── les gestes ───────────────────────────────────────────────────────
    def proposer(c, point="", moteur="", budget=0):
        m, p = decouper(point)
        evo.seuils["propositions_par_jour"] = max(1, int(reglage("propositions_par_jour", evo.seuils.get("propositions_par_jour", 20))))      # le réglage de l'admin l'emporte sur la valeur du fichier
        choix = str(moteur or reglage("moteur_defaut", "cascade"))
        reg0 = registre()
        etages = reg0.etages()
        if choix == "cascade" or choix in etages:                       # la cascade (ou un étage forcé) : l'orchestrateur compte, plafonne et attribue
            r = orchestre().proposer(m, p, max(1, min(10, int(budget) or int(reglage("budget_essais", 3)))), etage="" if choix == "cascade" else choix)
            r["moteur_choisi"] = choix
            return r
        if choix not in ("deterministe", "modele", "les_deux"):
            raise ValueError("moteur inconnu : « %s » (cascade, deterministe, modele, les_deux, %s)" % (choix, ", ".join(sorted(etages))))
        moteur = moteur_de_recherche(choix)
        r = evo.proposer(m, p, moteur, max(1, min(10, int(budget) or int(reglage("budget_essais", 3)))))
        r["moteur"] = choix
        try:
            reg = registre()
            reg.compter("orfan", getattr(moteur, "stats", {}), essais=len(r.get("essais") or []))
            reg.journaliser("proposition", "%s : moteur %s" % (point, choix))
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
        reg = registre()
        liste = [dict(m, plafond=reg.plafond(m["id"]), aujourdhui=reg.depense(m["id"]), mois=reg.depense_mois(m["id"])) for m in reg.liste()]
        try:
            catalogue = installateur().disponibles()
            erreur_catalogue = ""
        except Exception as e:
            catalogue, erreur_catalogue = [], str(e)
        return {"moteurs": liste, "isoles": isoles(), "cascade": reg.cascade(), "options": reg.options(), "affectations": reg.affectations(), "budget": reg.budget(),
                "depense_mois": reg.depense_mois(), "propositions_jour": {"fait": evo.tentatives_depuis(), "plafond": int(evo.seuils["propositions_par_jour"])},
                "relais": reg.relais(30), "courses": reg.courses(20), "journal": reg.journal(60), "objectifs": reg.objectifs(),
                "etages": {k: {"moteur": v[0], "nom": v[2], "cout": v[3]} for k, v in reg.etages().items()}, "catalogue": catalogue, "catalogue_erreur": erreur_catalogue,
                "points": sorted(evo.points.points())}

    # ── la cascade, les affectations, le budget, les objectifs ──
    def cascade_regler(c, ordre=None, options=None):
        reg = registre()
        avant = {"ordre": [{"id": e["id"], "on": e["on"]} for e in reg.cascade()], "options": reg.options()}
        if ordre is not None:
            reg.regler_cascade([dict(x) for x in ordre])
        if options:
            reg.regler_options(**dict(options))
        reg.journaliser("cascade", "ordre %s" % ", ".join(("" if e["on"] else "(") + e["id"] + ("" if e["on"] else ")") for e in reg.cascade()))
        return {"avant": avant, "ordre": [{"id": e["id"], "on": e["on"]} for e in reg.cascade()], "options": reg.options()}

    def prouver_cascade(c, res):
        reg = registre()
        return [{"id": e["id"], "on": e["on"]} for e in reg.cascade()] == res["ordre"] and reg.options() == res["options"]

    def defaire_cascade(c, res):
        reg = registre()
        reg.regler_cascade(res["avant"]["ordre"])
        reg.regler_options(**res["avant"]["options"])

    def affecter(c, point="", etage="auto"):
        decouper(point)
        reg = registre()
        avant = reg.affectation(point)
        reg.affecter(point, str(etage))
        reg.journaliser("affectation", "%s : %s" % (point, etage))
        return {"point": point, "avant": avant, "etage": str(etage)}

    def prouver_affectation(c, res):
        return registre().affectation(res["point"]) == res["etage"]

    def defaire_affectation(c, res):
        registre().affecter(res["point"], res["avant"])

    def budget_regler(c, jetons_mois=None, alerte_pct=None, gratuits_d_abord=None, couper_au_plafond=None):
        reg = registre()
        avant = reg.budget()
        vals = {k: v for k, v in (("jetons_mois", jetons_mois), ("alerte_pct", alerte_pct), ("gratuits_d_abord", gratuits_d_abord), ("couper_au_plafond", couper_au_plafond)) if v is not None}
        reg.regler_budget(**vals)
        reg.journaliser("budget", ", ".join("%s=%s" % kv for kv in sorted(vals.items())) or "inchangé")
        return {"avant": avant, "budget": reg.budget()}

    def prouver_budget(c, res):
        return registre().budget() == res["budget"]

    def defaire_budget(c, res):
        registre().regler_budget(**res["avant"])

    def moteur_plafonner(c, moteur="", jetons_jour=None, essais_jour=None):
        reg = registre()
        avant = reg.plafond(str(moteur))
        reg.plafonner(str(moteur), jetons_jour=jetons_jour, essais_jour=essais_jour)
        reg.journaliser("plafond", "%s : %s jetons/jour, %s essais/jour" % (moteur, jetons_jour, essais_jour))
        return {"moteur": str(moteur), "avant": avant, "plafond": reg.plafond(str(moteur))}

    def prouver_plafond(c, res):
        return registre().plafond(res["moteur"]) == res["plafond"]

    def defaire_plafond(c, res):
        reg = registre()
        for cle in ("jetons_jour", "essais_jour"):
            if cle in res["plafond"] or cle in res["avant"]:
                reg.plafonner(res["moteur"], **{cle: res["avant"].get(cle, 0)})

    def objectifs_regler(c, poids=None, tolerance_pct=None):
        reg = registre()
        avant = reg.objectifs()
        reg.regler_objectifs(poids=dict(poids) if poids else None, tolerance_pct=tolerance_pct)
        reg.journaliser("objectifs", "poids %s" % json.dumps(reg.objectifs()["poids"]))
        return {"avant": avant, "objectifs": reg.objectifs()}

    def prouver_objectifs(c, res):
        return registre().objectifs() == res["objectifs"]

    def defaire_objectifs(c, res):
        registre().regler_objectifs(poids=res["avant"]["poids"], tolerance_pct=res["avant"]["tolerance_pct"])

    # ── la course ──
    def course(c, point="", etages=None, budget="jetons", limite=20000, critere="rendement"):
        m, p = decouper(point)
        registre()
        return orchestre().course(m, p, list(etages or []), str(budget), int(limite), str(critere))

    def prouver_course(c, res):
        return registre().course(res["id"]) is not None

    def course_adopter(c, course=0, etage=""):
        registre()
        r = orchestre().adopter(int(course), str(etage))
        r["course"], r["etage"] = int(course), str(etage)
        return r

    def course_garder(c, course=0):
        if not registre().garder_course(int(course)):
            raise ValueError("course inconnue : %r" % (course,))
        return {"course": int(course)}

    def prouver_gardee(c, res):
        return bool((registre().course(res["course"]) or {}).get("gardee"))

    # ── les juges (lot 4) ──
    def juger_prompt(c, reference="", candidat="", contrat=None, valeurs=None, poison=""):
        jp = importlib.import_module("noyau.CN_juge_prompt")
        return jp.juger_prompt(str(reference), str(candidat), appeler_modele=appeler_modele if reglage("modele_role", "evolution") else None, contrat_sortie=contrat,
                               valeurs=dict(valeurs or {}), poison=str(poison or "") or None)

    def juger_politique(c, candidate=None, reference=None, intervalles=None, planchers=None, tolerance_pct=10):
        jp = importlib.import_module("noyau.CN_juge_prompt")
        return jp.juger_politique(dict(candidate or {}), dict(reference or {}), intervalles=dict(intervalles or {}) or None, planchers=dict(planchers or {}) or None,
                                  tolerance_pct=float(tolerance_pct))

    def prouver_jugement(c, res):
        return res.get("verdict") in ("accepte", "refuse", "indetermine")

    # ── la cage ──
    def cage(c):
        P = importlib.import_module("noyau.CN_points")
        bac = evo.points._nom_bac()
        chaine = evo.verifier_chaine()
        garanties = [
            ["Chaque EC tourne dans un processus à part, environnement vidé", evo.points.isolation == "processus"],
            ["Le moteur de recherche tourne dans son processus (sans clé, sans fichier écrit)", isoles()],
            ["Le bac du système (sans réseau, sans fichier du serveur) enveloppe ces processus", bac not in ("aucun", "indisponible", "à éprouver")],
            ["Mémoire plafonnée par processus (POSIX)", os.name == "posix"],
            ["Un processus qui dépasse son délai est tué", True],
            ["Une EC ne sert que sous un sceau valide et un routage signé", bool(getattr(evo.points, "exiger_sceau", False))],
            ["La chaîne des événements est scellée et intacte", bool(chaine.get("ok"))]]
        return {"os": sys.platform, "isolation": evo.points.isolation, "bac_mode": evo.points.bac_os, "bac": bac, "memoire_mo": P.MEMOIRE_EC_MO, "garanties": [{"texte": t, "ok": ok} for t, ok in garanties],
                "chaine": chaine, "epreuves": [j for j in registre().journal(60) if j["genre"] == "bac"][:5]}

    def bac_eprouver(c):
        """L'épreuve se fait ICI, à la demande (jamais sur le chemin d'un écran) : elle fait tourner le vrai travailleur dans le bac."""
        P = importlib.import_module("noyau.CN_points")
        try:
            prefixe, nom = P.bac_os(evo.points.bac_os)
            dit = "bac « %s » éprouvé : le travailleur répond dedans" % nom if nom != "aucun" else "aucun bac sur cet hôte (%s) : processus à part, délai et plafonds seulement" % sys.platform
            ok = True
        except P.BacIndisponible as e:
            nom, dit, ok = "indisponible", str(e), False
        registre().journaliser("bac", dit)
        return {"bac": nom, "ok": ok, "detail": dit}

    def prouver_bac(c, res):
        return "bac" in res

    def moteur_desinstaller(c, moteur=""):
        return dict(installateur().desinstaller(str(moteur)), moteur=str(moteur))

    def prouver_desinstallation(c, res):
        return res.get("ok") is True

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
    ctx.implementer("cascade_regler", cascade_regler, prouver_cascade, defaire_cascade)
    ctx.implementer("affecter", affecter, prouver_affectation, defaire_affectation)
    ctx.implementer("budget_regler", budget_regler, prouver_budget, defaire_budget)
    ctx.implementer("moteur_plafonner", moteur_plafonner, prouver_plafond, defaire_plafond)
    ctx.implementer("objectifs_regler", objectifs_regler, prouver_objectifs, defaire_objectifs)
    ctx.implementer("course", course, prouver_course, sans_retour)
    ctx.implementer("course_adopter", course_adopter, prouver_proposition, defaire_proposition)
    ctx.implementer("course_garder", course_garder, prouver_gardee, sans_retour)
    ctx.implementer("juger_prompt", juger_prompt, prouver_jugement, sans_retour)
    ctx.implementer("juger_politique", juger_politique, prouver_jugement, sans_retour)
    ctx.implementer("cage", cage)
    ctx.implementer("bac_eprouver", bac_eprouver, prouver_bac, sans_retour)
    ctx.implementer("moteur_desinstaller", moteur_desinstaller, prouver_desinstallation, sans_retour)
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
