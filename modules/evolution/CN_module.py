# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Évolution : le pilotage de l'évolution de Cassandra
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.5.0  #3fe2d7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : expose l'évolution du noyau comme capacités de Cassandra : cibles, état, proposer, retour, visiter, et un moteur qui fait avancer les paliers.
# MÉTHODE    : une coquille mince : tout ce qui décide vit dans noyau/CN_evolution.py ; le moteur de recherche est chargé par son chemin d'import (le contrat d'adaptateur).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=3fe2d7 ▼▼▼
"""Le module « Évolution » : la coquille entre Cassandra (droits, paliers, preuves, retours, réglages) et le service d'évolution du noyau.

Il ne propose rien lui-même et ne juge rien : le moteur de recherche (Orfan) rend du texte, l'évaluateur du noyau le juge, le routage du noyau le met en service.
Ce module ne fait que donner à ces gestes leurs droits, leur preuve et leur retour, comme à tout geste de Cassandra qui écrit.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

_MOTEUR_PERMIS = re.compile(r"^orfan(\.[A-Za-z_][A-Za-z0-9_]*)+$")      # un moteur se trouve DANS le paquet orfan : un réglage n'importe pas n'importe quel module du serveur


SEPARATEUR_CACHE = "<!--orfan:variable-->"      # le même que orfan.CN_orfan.SEPARATEUR_CACHE (le module n'importe pas Orfan pour si peu)


def contenu_du_prompt(prompt, avec_cache: bool = False):
    """Le séparateur d'Orfan ne part JAMAIS chez le modèle. Sans cache (par défaut) : le même texte qu'avant, séparateur retiré. Avec cache : la partie stable (la fonction, le profil, le contrat,
    les règles) devient un bloc marqué `cache_control`, la partie qui change (tombes, stratégie) un second bloc. Un endpoint qui refuse le marqueur est rejoué en texte simple par le module Modèles."""
    stable, sep, variable = str(prompt).partition(SEPARATEUR_CACHE)
    if not sep:
        return str(prompt)
    retour = chr(10)
    stable, variable = stable.rstrip(retour), variable.lstrip(retour)
    if not avec_cache:
        return stable + retour + variable
    return [{"type": "text", "text": stable + retour, "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": retour + variable}]


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
        try:
            plafond = ctx.executer_lecture("agents.service_plafond", service="evolution")    # le plafond de coût de la maison (Agents IA) : atteint, Évolution n'appelle plus de modèle aujourd'hui
        except Exception as e:
            if "n'est pas une capacité de lecture" not in str(e):
                raise RuntimeError("le plafond de dépense n'a pas pu être lu (%s) : par prudence, Évolution n'appelle pas de modèle" % str(e)[:120])
            plafond = None                                        # Agents IA est absent : aucun plafond n'est posé nulle part, il n'y a rien à respecter
        if isinstance(plafond, dict) and plafond.get("retient"):
            raise RuntimeError("le plafond de dépense de la maison est atteint aujourd'hui (%s € sur %s €, action « %s ») : Évolution n'appelle plus de modèle jusqu'à demain, ou jusqu'à ce que tu le relèves dans Agents IA"
                               % (plafond.get("depense_euros"), plafond.get("plafond_euros"), plafond.get("action")))
        messages = [{"role": "user", "content": contenu_du_prompt(prompt, str(reglage("cache_prompt", "non")) == "oui")}]
        essais = [nom_role]
        if role == "strategie" and not str(reglage("modele_role_strategie", "") or ""):
            essais = ["evolution_strategie", nom_role]                  # un modèle lié au rôle « evolution_strategie » sert le stratège sans qu'on touche au réglage ; sinon, le rôle des autres appels
        r = None
        for nom_role in essais:
            r = ctx.executer_lecture("modeles.completer", messages=messages, role=nom_role, max_tokens=3000, temperature=0.2)
            if r and r.get("ok"):
                break
        if not r or not r.get("ok"):
            raise RuntimeError((r or {}).get("erreur") or "le modèle n'a pas répondu (module Modèles absent, ou rôle « %s » sans modèle)" % nom_role)
        appeler_modele.dernier_modele = str(r.get("modele") or nom_role)
        u = r.get("usage") or {}
        appeler_modele.dernier_cache = {"lu": int(u.get("cache_lu") or 0), "ecrit": int(u.get("cache_ecrit") or 0)}          # ce que le fournisseur a servi du cache : zéro tant qu'il n'en dit rien
        return r.get("texte") or ""

    appeler_modele.dernier_modele = ""
    appeler_modele.dernier_cache = {"lu": 0, "ecrit": 0}

    def isoles():
        return str(reglage("moteurs_isoles", "oui")) == "oui"

    def orchestre():
        cou = importlib.import_module("noyau.CN_course")
        return cou.Orchestrateur(evo, registre(), appeler_modele=appeler_modele, isoles=isoles, en_ligne=moteur_en_ligne, options_moteur=options_frugal)

    def options_frugal(choix=""):
        """Les réglages de Frugal (idées, tours d'affinage, appels) : lus ici, bornés par le moteur lui-même."""
        if choix and choix != "frugal":
            return {}
        return {"strategies": reglage("frugal_strategies", 3), "tours": reglage("frugal_tours", 2), "appels_max": reglage("frugal_appels", 6)}

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
            return mot.MoteurProcessus(choix, appeler_modele=lambda prompt, role="executant": appeler_modele(prompt, role), orfan=importlib.util.find_spec(nom).origin, carnet=registre(), options=options_frugal(choix))
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
                "depense_mois": reg.depense_mois(), "propositions_jour": {"fait": evo.tentatives_depuis(), "plafond": max(1, int(reglage("propositions_par_jour", evo.seuils.get("propositions_par_jour", 20))))},
                "relais": reg.relais(30), "courses": reg.courses(20), "journal": reg.journal(60), "objectifs": reg.objectifs(),
                "etages": {k: {"moteur": v[0], "nom": v[2], "cout": v[3]} for k, v in reg.etages().items()}, "catalogue": catalogue, "catalogue_erreur": erreur_catalogue,
                "points": sorted(evo.points.points()), "repertoire": repertoire_vue(), "serveur": serveur_info()}

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

    def proposer_prompt(c, reference="", consigne="", contrat=None, valeurs=None, poison="", combien=2):
        """Un moteur de genome texte : le modèle (rôle stratège) réécrit un prompt, le juge des prompts décide de chaque réécriture. Rien n'est écrit : des propositions jugées."""
        gn = importlib.import_module("noyau.CN_genomes")
        return gn.proposer_prompt(str(reference), str(consigne), lambda p: appeler_modele(p, "strategie"), contrat_sortie=contrat, valeurs=dict(valeurs or {}), poison=str(poison or "") or None,
                                  combien=int(combien))

    def prouver_proposition_texte(c, res):
        return isinstance(res.get("propositions"), list) and isinstance(res.get("refusees"), list)

    def proposer_politique(c, reference=None, intervalles=None, planchers=None, historique=None):
        """Une recherche locale sur un seuil, d'après ce que l'utilisateur a acquitté sans agir. Aucun modèle, aucune écriture."""
        gn = importlib.import_module("noyau.CN_genomes")
        return gn.proposer_politique(dict(reference or {}), dict(intervalles or {}) or None, dict(planchers or {}) or None, [dict(h) for h in (historique or [])])

    def prouver_politique(c, res):
        return isinstance(res.get("politique"), dict) and res.get("jugement", {}).get("verdict") in ("accepte", "refuse")

    # ── un compte supprimé emporte ses entrées du corpus de rejeu (le corpus ne garde pas ce qu'un utilisateur parti a fait) ──
    def purge_sur_suppression(c2, ev):
        compte = str(ev.get("objet_id") or (ev.get("donnees") or {}).get("compte") or "").strip().lower()
        if compte:
            r = evo.rejeu.purger_compte(compte)
            registre().journaliser("purge", "compte supprimé « %s » : %s entrée(s) retirée(s) du corpus" % (compte, r.get("entrees", 0)))

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

    def verifier_programme(ident):
        """Le code d'un moteur est là et intact : un moteur natif, son fichier lisible et compilable ; un moteur externe, son environnement installé et le catalogue scellé qui le décrit."""
        reg = registre()
        fiche = next((m for m in reg.liste() if m["id"] == ident), None)
        if fiche is None:
            return False, "moteur inconnu : « %s »" % ident
        if fiche.get("genre") == "externe":
            try:
                catalogue = installateur().disponibles()
            except Exception as e:
                return False, str(e)[:200]
            entree = next((x for x in catalogue if x["id"] == ident), None)
            if entree is None:
                return False, "il n'est plus dans le catalogue scellé"
            if not entree.get("installe"):
                return False, "son environnement n'est plus installé"
            return True, "son environnement est installé et le catalogue scellé le décrit"
        nom = str(reglage("moteur_orfan", "orfan.CN_orfan"))
        if not _MOTEUR_PERMIS.match(nom):
            return False, "moteur de recherche refusé : « %s »" % nom
        spec = importlib.util.find_spec(nom)
        if spec is None or not spec.origin:
            return False, "le fichier du moteur est introuvable"
        fichier = {"orfan": spec.origin, "frugal": os.path.join(os.path.dirname(spec.origin), "CN_frugal.py"), "evolutif": os.path.join(os.path.dirname(spec.origin), "CN_evolutif.py")}.get(ident, spec.origin)
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                ast.parse(f.read())
        except (OSError, SyntaxError, ValueError) as e:
            return False, "son fichier est illisible ou invalide : %s" % str(e)[:120]
        return True, "livré avec Cassandra, lisible et valide"

    def moteur_controler(c, moteur=""):
        """Le contrôle d'intégrité d'un moteur : programme, isolation, réponse à un ping dans son processus, modèle, plafond. Dit la défaillance trouvée et ce qu'on peut faire."""
        ident = str(moteur or "").strip()
        reg = registre()
        if not any(m["id"] == ident for m in reg.liste()):
            raise ValueError("moteur inconnu : « %s » (voir evolution.moteurs)" % ident)
        mot = importlib.import_module("noyau.CN_moteurs")
        etages = [(e, v) for e, v in reg.etages().items() if v[0] == ident]
        a_modele = any(not str(v[3]).startswith("gratuit") for _e, v in etages)
        creer = None
        if etages and isoles():
            orch = orchestre()
            creer = lambda: orch._moteur(etages[0][0])
        return mot.controler(ident, reg, creer_moteur=creer, appeler_modele=appeler_modele, isoles=isoles(), programme=lambda: verifier_programme(ident), a_modele=a_modele)

    def prouver_controle(c, res):
        m = next((x for x in registre().liste() if x["id"] == res.get("moteur")), None)
        return bool(m) and "controle" in m

    # ── le répertoire des chercheurs, les tâches de fond, l'adaptateur à relire ──
    def depot():
        return importlib.import_module("noyau.CN_repertoire")

    def taches():
        return importlib.import_module("noyau.CN_taches").TACHES

    def catalogue_lu():
        """Le catalogue scellé s'il existe et si son sceau tient ; sinon rien (l'écran dit qu'aucun chercheur n'est encore préparé)."""
        try:
            ins = importlib.import_module("noyau.CN_installateur")
            base = evo.rejeu.chemin.parent
            return {e["id"]: e for e in ins.lire_catalogue(base / "moteurs-catalogue.json", evo.points._cle()).get("moteurs", [])}
        except Exception:
            return {}

    def serveur_info():
        import shutil
        base = evo.rejeu.chemin.parent
        return {"python": "%d.%d.%d" % sys.version_info[:3], "venv": importlib.util.find_spec("ensurepip") is not None, "bac": evo.points._nom_bac(),
                "disque_libre_go": round(shutil.disk_usage(base).free / 1e9, 1), "uv": bool(shutil.which("uv")) or (base / "outils" / "uv" / "bin" / "uv").exists(), "cle": bool(evo.points._cle())}

    def repertoire_vue():
        R = depot()
        fiches = {m["id"]: m for m in registre().liste()}
        cat = catalogue_lu()
        sortie = [dict(e, statut="livre") for e in R.LIVRES]
        for e in R.REPERTOIRE:
            f, c = fiches.get(e["id"]) or {}, cat.get(e["id"])
            installe = f.get("etat") in ("installe", "actif")
            g = f.get("adaptateur_genere") or {}
            sortie.append({"id": e["id"], "nom": e["nom"], "qui": e["qui"], "cible": e["cible"], "cout": e["cout"], "desc": e["desc"], "force": e["force"], "lien": e.get("lien", ""), "python": e.get("python", ""),
                           "statut": "installe" if installe else "disponible", "prepare": c is not None, "version": (f.get("version") if installe else (c or {}).get("version", "")) or "",
                           "paquets": len((c or {}).get("paquets", [])), "ecrit": e.get("adaptateur") is not None, "avec_paquet": bool(e.get("paquet") or e.get("github")),
                           "adaptateur_genere": installe and bool(g), "relu": (not g) or bool(g.get("relu")), "empreinte_adaptateur": g.get("empreinte", ""), "actif": f.get("etat") == "actif"})
        return sortie

    def generateur_pour(rep, inst):
        gen = importlib.import_module("noyau.CN_adaptateur_gen")
        return lambda entree, python, racine, etape: gen.generer(entree, rep, python, racine, etape, appeler_modele, inst._exec, inst.adaptateurs, bac="requis")

    def plan_de(rep, prepare, genere, python_pose):
        return ([] if prepare else ["préparation des paquets"]) + ["catalogue scellé", "entrée du catalogue"] + (["Python posé"] if python_pose else []) + ["environnement à part", "paquets épinglés par empreinte"] + (["adaptateur généré"] if genere else []) + ["banc d'import de l'adaptateur", "registre des moteurs"]

    def preparer(rep, progres, inst):
        """Du répertoire au catalogue scellé : Python posé s'il le faut, paquets résolus et empreintés, entrée écrite et scellée. Rend (entrée, étapes faites)."""
        ep = importlib.import_module("noyau.CN_epinglage")
        faites = []
        interp = ""
        if rep.get("python") and inst._version_de(sys.executable) != rep["python"]:
            progres(faites, "Python %s : recherche ou pose…" % rep["python"])
            interp = inst.poser_python(rep["python"])
            faites.append({"nom": "Python posé", "ok": True, "detail": "%s : %s" % (rep["python"], interp)})
        progres(faites, "préparation des paquets…")
        entree = ep.epingler(rep, interpreteur=interp, progres=lambda t: progres(faites, t), executer=inst._exec)
        if rep.get("python"):
            entree["python"] = rep["python"]
        ep.inscrire(inst.catalogue, entree, evo.points._cle())
        faites.append({"nom": "préparation des paquets", "ok": True, "detail": "%d paquet(s) épinglé(s) par empreinte, catalogue scellé" % len(entree["paquets"])})
        progres(faites, "")
        return entree, faites

    def travail_installer(rep, progres):
        inst = installateur()
        inst.generateur = generateur_pour(rep, inst)
        prepare = rep["id"] in catalogue_lu()
        faites = []
        if not prepare:
            _entree, faites = preparer(rep, progres, inst)
        res = inst.installer(rep["id"], progres=lambda etapes: progres(faites + etapes, ""))
        res["etapes"] = faites + res["etapes"]
        registre().journaliser("installation", "%s : %s" % (rep["id"], "installé" if res.get("ok") else "échec"))
        return res

    def travail_maj(rep, progres):
        inst = installateur()
        inst.generateur = generateur_pour(rep, inst)
        ancien = catalogue_lu().get(rep["id"])
        if ancien is None:
            raise ValueError("ce chercheur n'est pas dans le catalogue : rien à mettre à jour")
        ep = importlib.import_module("noyau.CN_epinglage")
        faites = []
        progres(faites, "recherche de la version la plus récente…")
        nouvelle = ep.epingler(rep, interpreteur=ancien.get("interpreteur", ""), progres=lambda t: progres(faites, t), executer=inst._exec)
        if rep.get("python"):
            nouvelle["python"] = rep["python"]
        if str(nouvelle.get("version")) == str(ancien.get("version")):
            return {"ok": True, "deja_a_jour": True, "etapes": [{"nom": "version", "ok": True, "detail": "déjà la plus récente : %s" % ancien.get("version")}]}
        faites.append({"nom": "nouvelle version", "ok": True, "detail": "%s → %s" % (ancien.get("version"), nouvelle.get("version"))})
        ep.inscrire(inst.catalogue, nouvelle, evo.points._cle())
        res = inst.mettre_a_jour(rep["id"], progres=lambda etapes: progres(faites + etapes, ""))
        if not res.get("ok"):
            ep.inscrire(inst.catalogue, ancien, evo.points._cle())                 # l'ancienne entrée est remise : le catalogue dit toujours ce qui tourne
        res["etapes"] = faites + res["etapes"]
        registre().journaliser("mise à jour", "%s : %s" % (rep["id"], "à jour" if res.get("ok") else "échec, ancienne version gardée"))
        return res

    def moteur_installer_tache(c, moteur=""):
        """Lance EN FOND la préparation (si besoin) puis l'installation d'un chercheur du répertoire ; rend l'identifiant de la tâche à relire (`moteur_tache`)."""
        ident = str(moteur or "").strip()
        rep = depot().trouver(ident)
        if rep is None:
            raise ValueError("chercheur inconnu : « %s » (il n'est pas dans le répertoire)" % ident)
        if any(m["id"] == ident and m.get("etat") in ("installe", "actif") for m in registre().liste()):
            raise ValueError("« %s » est déjà installé" % rep["nom"])
        if taches().actif(ident):
            raise ValueError("une tâche est déjà en cours pour « %s »" % rep["nom"])
        srv = serveur_info()
        if not srv["cle"]:
            raise ValueError("pas de clé d'instance : un catalogue ne peut être cru, rien ne s'installe")
        if not srv["venv"]:
            raise ValueError("Python n'a pas son module d'environnements (paquet python3-venv) : l'installer sur le serveur")
        genere = rep.get("adaptateur") is None
        if genere and str(srv["bac"]) in ("aucun", "indisponible", "à éprouver"):
            raise ValueError("un adaptateur généré ne s'éprouve que dans la cage, et ce serveur n'en a pas (paquet bubblewrap) : l'installer sur le serveur")
        plan = plan_de(rep, ident in catalogue_lu(), genere, bool(rep.get("python")) and rep["python"] != srv["python"])
        return {"tache": taches().lancer("installer", ident, lambda progres: travail_installer(rep, progres), plan), "moteur": ident, "plan": plan}

    def moteur_maj_tache(c, moteur=""):
        """Lance EN FOND la mise à jour d'un chercheur installé : la version nouvelle s'installe à côté, on bascule seulement si tout passe, sinon l'ancienne n'a pas bougé."""
        ident = str(moteur or "").strip()
        rep = depot().trouver(ident)
        if rep is None or not any(m["id"] == ident and m.get("genre") == "externe" and m.get("etat") in ("installe", "actif") for m in registre().liste()):
            raise ValueError("« %s » n'est pas un chercheur externe installé" % ident)
        if taches().actif(ident):
            raise ValueError("une tâche est déjà en cours pour « %s »" % rep["nom"])
        plan = ["nouvelle version", "catalogue scellé", "entrée du catalogue", "environnement à part", "paquets épinglés par empreinte"] + (["adaptateur généré"] if rep.get("adaptateur") is None else []) + ["banc d'import de l'adaptateur", "bascule"]
        return {"tache": taches().lancer("maj", ident, lambda progres: travail_maj(rep, progres), plan), "moteur": ident, "plan": plan}

    def moteur_tache(c, tache=""):
        return taches().lire(str(tache))

    def moteur_maj_dispo(c):
        """Pour chaque chercheur externe installé : la version installée et la plus récente disponible (PyPI, ou le dernier commit du dépôt). Une lecture réseau, un chercheur à la fois, délai court."""
        import urllib.request
        ep = importlib.import_module("noyau.CN_epinglage")
        sortie = []
        for m in registre().liste():
            if m.get("genre") != "externe" or m.get("etat") not in ("installe", "actif"):
                continue
            rep = depot().trouver(m["id"]) or {}
            ligne = {"moteur": m["id"], "installee": m.get("version", ""), "disponible": "", "maj": False, "erreur": ""}
            try:
                if rep.get("github"):
                    ligne["disponible"] = ep.resoudre_commit(rep["github"], rep.get("ref", "HEAD"))[:12]
                elif rep.get("paquet"):
                    with urllib.request.urlopen("https://pypi.org/pypi/%s/json" % rep["paquet"], timeout=15) as r:
                        ligne["disponible"] = str(json.loads(r.read().decode("utf-8"))["info"]["version"])
                ligne["maj"] = bool(ligne["disponible"]) and ligne["disponible"] != ligne["installee"]
            except Exception as e:
                ligne["erreur"] = str(e)[:120]
            sortie.append(ligne)
        return {"verifie_le": time.time(), "chercheurs": sortie}

    def fichier_adaptateur(ident):
        fiche = next((m for m in registre().liste() if m["id"] == ident), None)
        if fiche is None or not fiche.get("adaptateur_genere"):
            raise ValueError("« %s » n'a pas d'adaptateur généré" % ident)
        racine = Path(str(fiche.get("python", ""))).parent.parent
        trouves = sorted(racine.glob("lib/python*/site-packages/%s.py" % fiche.get("adaptateur", "")))
        if not trouves:
            raise ValueError("le fichier de l'adaptateur est introuvable dans l'environnement du chercheur")
        return fiche, trouves[0]

    def moteur_adaptateur_lire(c, moteur=""):
        """Le code de l'adaptateur généré, son empreinte, ce que Cassandra en a déjà contrôlé : de quoi le relire."""
        gen = importlib.import_module("noyau.CN_adaptateur_gen")
        fiche, fichier = fichier_adaptateur(str(moteur or "").strip())
        code = fichier.read_text(encoding="utf-8")
        emp = hashlib.sha256(code.encode("utf-8")).hexdigest()
        return {"moteur": fiche["id"], "code": code, "empreinte": emp, "enregistree": fiche["adaptateur_genere"].get("empreinte", ""), "intact": emp == fiche["adaptateur_genere"].get("empreinte"), "relu": bool(fiche["adaptateur_genere"].get("relu")), "verification": gen.verifier_code(code) or "ok"}

    def moteur_adaptateur_approuver(c, moteur="", empreinte=""):
        """L'admin a relu l'adaptateur : le chercheur peut être activé. L'empreinte donnée doit être celle du fichier tel qu'il est maintenant."""
        info = moteur_adaptateur_lire(c, moteur)
        if info["empreinte"] != str(empreinte) or not info["intact"]:
            raise ValueError("le fichier a changé depuis qu'on te l'a montré (ou ne correspond plus à son empreinte) : relis-le de nouveau")
        registre().approuver_adaptateur(info["moteur"], info["empreinte"])
        registre().journaliser("adaptateur", "%s : adaptateur généré relu et approuvé (%s…)" % (info["moteur"], info["empreinte"][:12]))
        return {"moteur": info["moteur"], "empreinte": info["empreinte"], "relu": True}

    def prouver_adaptateur(c, res):
        m = next((x for x in registre().liste() if x["id"] == res.get("moteur")), {})
        return bool((m.get("adaptateur_genere") or {}).get("relu"))

    def prouver_tache(c, res):
        return bool(res.get("tache"))

    def moteur_etat(c, moteur="", etat=""):
        reg = registre()
        avant = next((m["etat"] for m in reg.liste() if m["id"] == moteur), None)
        if avant is None:
            raise ValueError("moteur inconnu : « %s » (voir evolution.moteurs)" % moteur)
        fiche = next((m for m in reg.liste() if m["id"] == moteur), {})
        g = fiche.get("adaptateur_genere")
        if str(etat) == "actif" and g and not g.get("relu"):
            raise ValueError("l'adaptateur de « %s » a été généré et n'a pas été relu : relis-le (Installer un chercheur), puis active-le" % fiche.get("nom", moteur))
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

    # ── ce qu'Évolution dit aux autres modules : des constats (Notifications), un signal (Aujourd'hui), des mesures (Mesures) ──
    # Rien n'est recalculé ni inventé ici : tout vient de la chaîne scellée, de la cage et du registre des moteurs. Un module ne parle jamais à la place d'un autre : il déclare, les autres lisent.
    def retraits_seuls(heures=24):
        """Les pièces retirées SANS que l'admin le demande, ces dernières heures : par le disjoncteur ou par la visite (le gain n'a pas tenu). Un retour demandé n'est pas une alerte."""
        depuis = time.time() - heures * 3600
        out = []
        for e in evo.chaine(None, 200):
            raison = str((e["details"] or {}).get("raison", ""))
            if e["verbe"] == "retiree" and float(e["ts"]) >= depuis and (raison.startswith("suspendue par le disjoncteur") or raison.startswith("visite :")):
                out.append({"gid": e["gid"], "ec": (e["details"] or {}).get("ec", ""), "raison": raison, "ts": float(e["ts"])})
        return out

    def isolation_faible():
        """Sur un hôte POSIX, le bac du système devrait envelopper les processus des chercheurs. Ailleurs (Windows) il n'existe pas : ce n'est pas une alerte."""
        return os.name == "posix" and evo.points.isolation == "processus" and evo.points._nom_bac() in ("aucun", "indisponible")

    def constats(c):
        """Un constat par cause ; il se referme seul quand la cause disparaît (le détecteur ne le rend plus)."""
        out = []
        chaine = evo.verifier_chaine()
        if not chaine.get("ok"):
            out.append({"objet": ("evolution_chaine", "chaine"), "titre": "La chaîne scellée d'Évolution est rompue",
                        "detail": "Une ligne a été modifiée ou retirée après coup (maillon %s%s). Ce qu'Évolution a fait ne peut plus être garanti." % (chaine.get("rupture_a", "?"), ", " + chaine["raison"] if chaine.get("raison") else ""), "niveau": "critique"})
        for p in retraits_seuls():
            out.append({"objet": ("evolution_piece", "%s:%s" % (p["gid"], p["ec"])), "titre": "Une amélioration a été retirée toute seule : %s" % p["gid"],
                        "detail": p["raison"][:200], "niveau": "attention"})
        if isolation_faible():
            out.append({"objet": ("evolution_bac", "bac"), "titre": "Les chercheurs d'Évolution ne sont pas enveloppés par le bac du système",
                        "detail": "Chaque chercheur tourne bien dans un processus à part, sans clé ni réseau, mais le bac du système (bubblewrap) n'est pas disponible sur cet hôte.", "niveau": "attention"})
        return out

    def item_jour(bande, quoi, titre, detail="", ref="", poids=0, geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": "evolution", "ref": str(ref or ""), "poids": int(poids), "ou": "evolution",
                "geste": list(geste) if geste else None}

    def signal_evolution(c):
        """Pour le bureau du jour : ce qui brûle ou se dégrade côté Évolution. Rien quand tout va bien."""
        items = []
        chaine = evo.verifier_chaine()
        if not chaine.get("ok"):
            items.append(item_jour("brule", "evolution", "La chaîne scellée d'Évolution est rompue", "Ce qu'elle a fait ne peut plus être garanti.", "chaine", 100, ("Vérifier", "ouvrir")))
        for p in retraits_seuls():
            items.append(item_jour("regarder", "evolution", "Amélioration retirée toute seule : %s" % p["gid"], p["raison"], "%s:%s" % (p["gid"], p["ec"]), 60, ("Voir", "ouvrir")))
        return {"items": items}

    def serie(c, mesure="", depuis="", jusqu_a=""):
        """Les séries d'Évolution, un point par jour (jetons et essais des moteurs) ou par événement (retraits) : ce que Mesures trace."""
        if mesure not in ("evolution_jetons", "evolution_essais", "evolution_retraits"):
            raise ValueError("mesure inconnue : « %s »" % mesure)
        a, b = str(depuis)[:10], str(jusqu_a)[:10]
        if mesure == "evolution_retraits":
            pts = [[time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(e["ts"]))), 1] for e in reversed(evo.chaine(None, 500)) if e["verbe"] == "retiree"]
            return {"series": [{"nom": "retraits", "points": [p for p in pts if (not a or p[0][:10] >= a) and (not b or p[0][:10] <= b)]}]}
        cle = "jetons" if mesure == "evolution_jetons" else "essais"
        jours = {}
        depense = registre()._lire().get("depense") or {}
        for ident in depense:
            for j, v in (depense.get(ident) or {}).items():
                jours[j] = jours.get(j, 0) + int(v.get(cle, 0))
        pts = [[j + " 12:00:00", n] for j, n in sorted(jours.items()) if (not a or j >= a) and (not b or j <= b)]
        return {"series": [{"nom": "jetons" if cle == "jetons" else "essais", "points": pts}]}

    ctx.detecteur("evolution_alertes", constats)
    ctx.implementer("signal_evolution", signal_evolution)
    ctx.implementer("serie", serie)
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
    ctx.implementer("proposer_prompt", proposer_prompt, prouver_proposition_texte, sans_retour)
    ctx.implementer("proposer_politique", proposer_politique, prouver_politique, sans_retour)
    ctx.moteur("purge_comptes", purge_sur_suppression)
    ctx.implementer("cage", cage)
    ctx.implementer("bac_eprouver", bac_eprouver, prouver_bac, sans_retour)
    ctx.implementer("moteur_desinstaller", moteur_desinstaller, prouver_desinstallation, sans_retour)
    ctx.implementer("moteur_installer", moteur_installer, prouver_installation, defaire_installation)
    ctx.implementer("moteur_etat", moteur_etat, prouver_etat, defaire_etat)
    ctx.implementer("moteur_controler", moteur_controler, prouver_controle, sans_retour)
    ctx.implementer("moteur_installer_tache", moteur_installer_tache, prouver_tache, sans_retour)
    ctx.implementer("moteur_maj_tache", moteur_maj_tache, prouver_tache, sans_retour)
    ctx.implementer("moteur_tache", moteur_tache)
    ctx.implementer("moteur_maj_dispo", moteur_maj_dispo)
    ctx.implementer("moteur_adaptateur_lire", moteur_adaptateur_lire)
    ctx.implementer("moteur_adaptateur_approuver", moteur_adaptateur_approuver, prouver_adaptateur, sans_retour)
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
