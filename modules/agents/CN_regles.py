# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les règles communes aux agents, la tuile « retenus / refusés » et les tâches récurrentes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.5.1  #2dd550
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les règles communes aux agents, la tuile « retenus / refusés » et les tâches récurrentes.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.1 empreinte=2dd550 ▼▼▼
"""Les règles communes aux agents, la tuile « retenus / refusés » et les tâches récurrentes.

  - RÈGLES COMMUNES (administrateur) : le plafond global de coût (le même que `plafond_regler` « global »), le palier par défaut d'un outil que l'agent n'a pas réglé (« raconter » : il raconte
    avant de faire ; « auto » : le palier du catalogue décide), « le dehors passe par Amizo » (vrai : aucun autre agent n'a un outil qui lit l'extérieur), l'ordre du journal (donnée pour l'écran).
    Une règle posée AGIT dans le tour de l'agent (CN_module) : elle ne reste pas une étiquette.
  - TUILE « retenus / refusés » : ce que le Relecteur a retenu, ce que l'utilisateur a refusé, ce que le noyau a refusé, sur une période.
  - TÂCHES RÉCURRENTES : on confie à un agent une consigne qui revient (horaire, quotidienne, hebdomadaire). La tâche est du compte qui la confie ; `tache_lancer` la joue maintenant, par un tour de l'agent,
    sous ce compte. À l'heure dite, le MOTEUR « taches » du module (le planificateur du noyau, pas un second ordonnanceur) la joue de même : sous le compte de la tâche, donc sous les droits, les paliers
    et les plafonds de l'agent, chaque lancement journalisé (`tache.lancee`).
  - MAUVAIS JOUR : un seul bouton. Tous les agents passent en « raconter » (ils racontent, ils ne font pas) pendant N heures (0 = jusqu'à levée). Le plus prudent gagne ; les réglages d'origine ne bougent pas ;
    le retour est automatique à l'échéance ; la levée dit exactement ce qui a été raconté au lieu d'être fait.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

from . import CN_equipe as eq

ORDRES = ("recent", "ancien")
PALIERS = ("auto", "raconter")
FREQUENCES = ("horaire", "quotidien", "hebdomadaire")
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
DEFAUTS = {"palier_defaut": "auto", "dehors_par_amizo": "1", "ordre_journal": "recent"}
TACHES_MAX = 20
PAR_PASSE = 3                    # tâches lancées par passe du moteur : un tour d'agent dure des secondes, le moteur est borné
DUREE_MAX_H = 720


def prochaine(frequence, heure, jour, depuis):
    """L'instant (secondes) de la prochaine exécution après `depuis` : horaire = l'heure ronde suivante ; quotidien = la prochaine HH:MM ; hebdomadaire = le prochain jour (0 = lundi) à HH:MM."""
    d = datetime.fromtimestamp(depuis)
    if frequence == "horaire":
        return (d.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).timestamp()
    h, m = (int(x) for x in heure.split(":"))
    c = d.replace(hour=h, minute=m, second=0, microsecond=0)
    if frequence == "hebdomadaire":
        c += timedelta(days=(int(jour) - c.weekday()) % 7)
    while c.timestamp() <= depuis:
        c += timedelta(days=7 if frequence == "hebdomadaire" else 1)
    return c.timestamp()


def brancher_regles(ctx, E, db, compte_agit, converser):
    def admin_seulement(compte):
        if not E.admin(compte):
            raise PermissionError("les règles communes se règlent depuis l'administration")

    def regle(cle):
        r = db.lire("SELECT valeur FROM agents_regles WHERE cle=?", (cle,))
        return r[0]["valeur"] if r else DEFAUTS[cle]

    def etat():
        p = db.lire("SELECT * FROM agent_plafonds WHERE portee='global'")
        return {"plafond_global_cts": p[0]["centimes"] if p else None, "plafond_action": p[0]["action"] if p else "", "palier_defaut": regle("palier_defaut"),
                "dehors_par_amizo": regle("dehors_par_amizo") == "1", "ordre_journal": regle("ordre_journal"),
                "vocabulaire": {"palier_agent": "Palier", "niveaux": {"observer": "Observer", "entretien": "Entretien", "reine": "Pleine autonomie"}, "paliers_outil": {"auto": "Automatique", "raconter": "À raconter", "retire": "Retiré"}}}

    # ------------------------------------------------------------------ le mauvais jour
    def mj_brut():
        r = db.lire("SELECT valeur FROM agents_regles WHERE cle='mauvais_jour'")
        try:
            return json.loads(r[0]["valeur"]) if r else {}
        except ValueError:
            return {}

    def mauvais_jour():
        """{actif, jusqua, depuis, raconte} : actif tant que le bouton est posé et que l'échéance n'est pas venue (0 = jusqu'à levée). `raconte` : ce que les agents ont raconté au lieu de faire depuis."""
        m = mj_brut()
        actif = bool(m.get("actif")) and (not m.get("jusqua") or time.time() < m["jusqua"])
        depuis = m.get("depuis") or 0
        sortie = {"actif": actif, "jusqua": m.get("jusqua") or 0, "depuis": depuis, "raconte": []}
        if depuis:
            comptes = {}
            for e in ctx.evenements("capacite.", 5000):                       # raconté = simulé (l'agent a dit ce qu'il ferait) ou raconté par l'exécuteur
                if e["type"] in ("capacite.simulee", "capacite.racontee") and e["ts"] >= depuis and e.get("acteur") in ("itare", "cassandra", "amizo"):
                    k = (e["acteur"], e.get("objet_id") or "")
                    comptes[k] = comptes.get(k, 0) + 1
            sortie["raconte"] = [{"agent": a, "capacite": cap, "fois": n} for (a, cap), n in sorted(comptes.items())]
        return sortie

    def mauvais_jour_actif():
        """Le seul « est-ce un mauvais jour ? » : sans relire le journal, il est demandé à chaque outil appelé."""
        m = mj_brut()
        return bool(m.get("actif")) and (not m.get("jusqua") or time.time() < m["jusqua"])

    def poser_mj(valeur):
        db.ecrire("INSERT OR REPLACE INTO agents_regles(cle, valeur, maj) VALUES ('mauvais_jour',?,?)", (json.dumps(valeur), time.time()))

    def mauvais_jour_poser(c, duree_h=0):
        compte = compte_agit()
        admin_seulement(compte)
        if isinstance(duree_h, bool) or not isinstance(duree_h, (int, float)) or duree_h < 0 or duree_h > DUREE_MAX_H:
            raise ValueError("duree_h : 0 (jusqu'à levée) ou un nombre d'heures, %d au plus" % DUREE_MAX_H)
        avant = mj_brut()
        maintenant = time.time()
        poser_mj({"actif": True, "depuis": maintenant, "jusqua": maintenant + duree_h * 3600 if duree_h else 0, "par": compte})
        return dict(mauvais_jour(), avant=avant)

    def prouver_mj(c, res):
        return mauvais_jour()["actif"]

    def defaire_mj(c, res):
        db.ecrire("DELETE FROM agents_regles WHERE cle='mauvais_jour'")
        if res["avant"]:
            poser_mj(res["avant"])

    def mauvais_jour_lever(c):
        compte = compte_agit()
        admin_seulement(compte)
        avant = mj_brut()
        bilan = mauvais_jour()
        if not avant.get("actif"):
            raise ValueError("ce n'est pas un mauvais jour")
        poser_mj(dict(avant, actif=False, leve=time.time()))
        return {"actif": False, "jusqua": 0, "depuis": bilan["depuis"], "raconte": bilan["raconte"], "avant": avant}

    def prouver_levee(c, res):
        return not mauvais_jour()["actif"]

    def defaire_levee(c, res):
        poser_mj(res["avant"])

    def regles(c):
        return dict(etat(), mauvais_jour=mauvais_jour())

    def regles_regler(c, plafond_euros=None, action="secours", palier_defaut=None, dehors_par_amizo=None, ordre_journal=None, sans_plafond=False):
        compte = compte_agit()
        admin_seulement(compte)
        avant = {"regles": {k: regle(k) for k in DEFAUTS}, "plafond": (db.lire("SELECT * FROM agent_plafonds WHERE portee='global'") or [None])[0]}
        if avant["plafond"]:
            avant["plafond"] = dict(avant["plafond"])
        if palier_defaut is not None and palier_defaut not in PALIERS:
            raise ValueError("palier_defaut : %s" % " | ".join(PALIERS))
        if ordre_journal is not None and ordre_journal not in ORDRES:
            raise ValueError("ordre_journal : %s" % " | ".join(ORDRES))
        if dehors_par_amizo is not None and not isinstance(dehors_par_amizo, bool):
            raise ValueError("dehors_par_amizo : vrai ou faux")
        if action not in ("secours", "arret", "accord"):
            raise ValueError("action : secours | arret | accord")
        if plafond_euros is not None and (isinstance(plafond_euros, bool) or not isinstance(plafond_euros, (int, float)) or plafond_euros <= 0 or plafond_euros > 1_000_000):
            raise ValueError("plafond_euros : un montant positif (le plafond d'un jour)")
        for cle, v in (("palier_defaut", palier_defaut), ("ordre_journal", ordre_journal), ("dehors_par_amizo", None if dehors_par_amizo is None else ("1" if dehors_par_amizo else "0"))):
            if v is not None:
                db.ecrire("INSERT OR REPLACE INTO agents_regles(cle, valeur, maj) VALUES (?,?,?)", (cle, v, time.time()))
        if sans_plafond:
            db.ecrire("DELETE FROM agent_plafonds WHERE portee='global'")
        elif plafond_euros is not None:
            db.ecrire("INSERT OR REPLACE INTO agent_plafonds(portee, centimes, action, accord_jour, maj) VALUES ('global',?,?,?,?)", (int(round(float(plafond_euros) * 100)), action, "", time.time()))
        return dict(etat(), avant=avant)

    def prouver_regles(c, res):
        return all(res[k] == v for k, v in etat().items() if k != "vocabulaire")

    def defaire_regles(c, res):
        a = res["avant"]
        for cle, v in a["regles"].items():
            db.ecrire("INSERT OR REPLACE INTO agents_regles(cle, valeur, maj) VALUES (?,?,?)", (cle, v, time.time()))
        db.ecrire("DELETE FROM agent_plafonds WHERE portee='global'")
        if a["plafond"]:
            p = a["plafond"]
            db.ecrire("INSERT OR REPLACE INTO agent_plafonds(portee, centimes, action, accord_jour, maj) VALUES ('global',?,?,?,?)", (p["centimes"], p["action"], p["accord_jour"], p["maj"]))

    def retenus_refuses(c, jours=7):
        compte = compte_agit()
        jours = eq.entier(jours, 7, 1, 90, "jours")
        debut = time.time() - jours * 86400
        admin = E.admin(compte)
        filtre = "" if admin else " AND compte=?"
        arg = [] if admin else [compte]
        rel = db.lire("SELECT agent, motifs, ts FROM relectures WHERE ts>=?" + filtre + " ORDER BY id DESC LIMIT 200", [debut] + arg)
        ref = db.lire("SELECT agent, titre, capacite, decidee FROM propositions WHERE etat='refusee' AND decidee>=?" + filtre + " ORDER BY decidee DESC LIMIT 200", [debut] + arg)
        noy = [e for e in ctx.evenements("capacite.refusee", 2000) if e["ts"] >= debut and (admin or e.get("compte") == compte)]
        return {"jours": jours, "retenus": len(rel), "refuses": len(ref) + len(noy), "par_le_relecteur": len(rel), "par_l_utilisateur": len(ref), "par_le_noyau": len(noy),
                "derniers": [{"qui": r["agent"], "quoi": "réponse retenue par le Relecteur", "ts": r["ts"]} for r in rel[:5]] + [{"qui": r["agent"], "quoi": "refusé : %s" % r["titre"], "ts": r["decidee"]} for r in ref[:5]]}

    # ------------------------------------------------------------------ les tâches récurrentes
    def tache(r):
        return {"id": r["id"], "agent": r["agent"], "consigne": r["consigne"], "frequence": r["frequence"], "heure": r["heure"], "jour": JOURS[r["jour"]] if r["frequence"] == "hebdomadaire" else "",
                "active": bool(r["active"]), "derniere": r["derniere"], "prochaine": prochaine(r["frequence"], r["heure"], r["jour"], time.time()) if r["active"] else None, "conversation_id": r["conversation_id"]}

    def taches(c):
        compte = compte_agit()
        return {"taches": [tache(r) for r in db.lire("SELECT * FROM taches_agents WHERE compte=? ORDER BY id", (compte,))], "declenchement_automatique": True}

    def tache_confier(c, agent="itare", consigne="", frequence="quotidien", heure="08:00", jour="lundi"):
        compte = compte_agit()
        d = E.definitions().get(str(agent or "").strip().lower())
        if not d or d["genre"] != "agent":
            raise ValueError("agent : un agent de l'équipe (pas un service)")
        if d["id"] == "amizo":
            raise ValueError("agent : Amizo répond quand on le sollicite, il n'a pas de tâche récurrente")
        if d["portee"] != "compte" and not E.admin(compte):
            raise PermissionError("cet agent est celui de l'instance : l'administrateur seulement")
        consigne = " ".join(str(consigne or "").split())
        if not 3 <= len(consigne) <= 600:
            raise ValueError("consigne : de 3 à 600 caractères")
        if frequence not in FREQUENCES:
            raise ValueError("frequence : %s" % " | ".join(FREQUENCES))
        try:
            h, m = (int(x) for x in str(heure).split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except (ValueError, AssertionError):
            raise ValueError("heure : HH:MM")
        if str(jour).lower() not in JOURS:
            raise ValueError("jour : %s" % " | ".join(JOURS))
        if db.lire("SELECT COUNT(*) AS n FROM taches_agents WHERE compte=? AND active=1", (compte,))[0]["n"] >= TACHES_MAX:
            raise ValueError("%d tâches récurrentes au plus par compte" % TACHES_MAX)
        tid = db.ecrire("INSERT INTO taches_agents(agent, compte, consigne, frequence, heure, jour, cree) VALUES (?,?,?,?,?,?,?)", (d["id"], compte, consigne, frequence, "%02d:%02d" % (h, m), JOURS.index(str(jour).lower()), time.time()))
        return {"tache": tid}

    def prouver_confiee(c, res):
        return bool(db.lire("SELECT 1 FROM taches_agents WHERE id=?", (res["tache"],)))

    def defaire_confiee(c, res):
        db.ecrire("DELETE FROM taches_agents WHERE id=?", (res["tache"],))

    def tache_retirer(c, id=0):
        compte = compte_agit()
        r = db.lire("SELECT * FROM taches_agents WHERE id=? AND compte=?", (eq.entier(id, 0, 0, 2**62, "id"), compte))
        if not r:
            raise ValueError("tâche introuvable")
        db.ecrire("DELETE FROM taches_agents WHERE id=?", (r[0]["id"],))
        return {"tache": r[0]["id"], "avant": dict(r[0])}

    def prouver_retiree(c, res):
        return not db.lire("SELECT 1 FROM taches_agents WHERE id=?", (res["tache"],))

    def defaire_retiree(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO taches_agents(id, agent, compte, consigne, frequence, heure, jour, active, cree, derniere, conversation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (a["id"], a["agent"], a["compte"], a["consigne"], a["frequence"], a["heure"], a["jour"], a["active"], a["cree"], a["derniere"], a["conversation_id"]))

    def tache_lancer(c, id=0):
        compte = compte_agit()
        r = db.lire("SELECT * FROM taches_agents WHERE id=? AND compte=?", (eq.entier(id, 0, 0, 2**62, "id"), compte))
        if not r:
            raise ValueError("tâche introuvable")
        t = r[0]
        res = converser(c, 0, t["consigne"], t["agent"])
        cid = int(res.get("conversation_id") or 0)
        db.ecrire("UPDATE taches_agents SET derniere=?, conversation_id=? WHERE id=?", (time.time(), cid, t["id"]))
        return {"tache": t["id"], "conversation_id": cid, "avant": {"derniere": t["derniere"], "conversation_id": t["conversation_id"]}}

    def prouver_lancee(c, res):
        return bool(db.lire("SELECT 1 FROM taches_agents WHERE id=? AND derniere IS NOT NULL", (res["tache"],)))

    def defaire_lancee(c, res):
        db.ecrire("UPDATE taches_agents SET derniere=?, conversation_id=? WHERE id=?", (res["avant"]["derniere"], res["avant"]["conversation_id"], res["tache"]))

    # ------------------------------------------------------------------ le moteur : les tâches échues
    def echue(t, maintenant):
        return prochaine(t["frequence"], t["heure"], t["jour"], t["derniere"] or t["cree"]) <= maintenant

    def lancer_tache(t):
        """Joue la tâche SOUS le compte qui l'a confiée : ses droits, les paliers et les plafonds de l'agent s'appliquent comme à un tour demandé par lui."""
        avant = (ctx._compte.valeur, ctx._societe.valeur)
        ctx._compte.valeur, ctx._societe.valeur = t["compte"], ctx.societe_de(t["compte"])
        try:
            db.ecrire("UPDATE taches_agents SET derniere=? WHERE id=?", (time.time(), t["id"]))        # d'abord : une tâche qui échoue ne se rejoue pas en boucle
            res = converser(ctx, 0, t["consigne"], t["agent"])
            cid = int(res.get("conversation_id") or 0)
            db.ecrire("UPDATE taches_agents SET conversation_id=? WHERE id=?", (cid, t["id"]))
            ctx.emettre("tache_agent.lancee", objet=("tache_agent", str(t["id"])), donnees={"tache": t["id"], "agent": t["agent"], "compte": t["compte"], "conversation_id": cid, "automatique": True}, compte=t["compte"])
            return cid
        finally:
            ctx._compte.valeur, ctx._societe.valeur = avant

    def moteur_taches(cx):
        maintenant = time.time()
        soc = cx.societe
        lancees = 0
        for t in db.lire("SELECT * FROM taches_agents WHERE active=1 ORDER BY id"):
            if lancees >= PAR_PASSE:
                break
            if (soc and ctx.societe_de(t["compte"]) != soc) or not echue(t, maintenant):
                continue
            try:
                lancer_tache(t)
            except Exception as ex:                                  # une tâche qui échoue ne ferme pas la passe des autres
                ctx.emettre("tache_agent.echouee", objet=("tache_agent", str(t["id"])), donnees={"tache": t["id"], "erreur": str(ex)[:200]}, compte=t["compte"])
            lancees += 1

    ctx.moteur("taches", moteur_taches)
    for cid, f in (("regles", regles), ("retenus_refuses", retenus_refuses), ("taches", taches)):
        ctx.implementer(cid, f)
    ctx.implementer("regles_regler", regles_regler, prouver_regles, defaire_regles, simuler=lambda x, **a: "réglerait les règles communes : %s" % ", ".join(sorted(k for k, v in a.items() if v is not None)))
    ctx.implementer("mauvais_jour", mauvais_jour_poser, prouver_mj, defaire_mj, simuler=lambda x, duree_h=0, **_: "ferait passer tous les agents en « raconter » %s" % ("jusqu'à levée" if not duree_h else "pendant %s h" % duree_h))
    ctx.implementer("mauvais_jour_lever", mauvais_jour_lever, prouver_levee, defaire_levee, simuler=lambda x, **_: "lèverait le mauvais jour")
    ctx.implementer("tache_confier", tache_confier, prouver_confiee, defaire_confiee, simuler=lambda x, agent="", consigne="", **_: "confierait à %s : %s" % (agent, str(consigne)[:80]))
    ctx.implementer("tache_retirer", tache_retirer, prouver_retiree, defaire_retiree, simuler=lambda x, id=0, **_: "retirerait la tâche %s" % id)
    ctx.implementer("tache_lancer", tache_lancer, prouver_lancee, defaire_lancee, simuler=lambda x, id=0, **_: "jouerait maintenant la tâche %s" % id)
    return SimpleNamespace(regle=regle, mauvais_jour=mauvais_jour, mauvais_jour_actif=mauvais_jour_actif)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : prochaine, brancher_regles
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
