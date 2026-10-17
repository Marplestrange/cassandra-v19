# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les tâches planifiées
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.1  #99fc67
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les tâches planifiées : tout ce qui tourne tout seul sur la machine, et est-ce que ça va.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=99fc67 ▼▼▼
"""Les tâches planifiées : tout ce qui tourne tout seul sur la machine, et est-ce que ça va.

Porté de la V18 (`cron_*`, `_crontab_*`), avec ses leçons :
  - DEUX vues étanches existaient (celles que Cassandra a créées, avec leur intention ; celles du système, avec leur exécution réelle) : on les fusionne sur (utilisateur, commande) ;
  - le journal du système prouve qu'un cron a été LANCÉ, jamais qu'il a RÉUSSI : les commandes passent par un enrobage qui consigne le code de sortie, la durée, la sortie ;
  - « inconnu » est un état à part entière (sans donnée d'exécution on ne peut rien affirmer) ; une cible disparue passe AVANT le silence (le cron se déclenche, le journal enregistre,
    il paraît « ok » — et ne fait rien) ; un seul créneau manquant ne prouve rien, deux ne s'expliquent plus par le décalage ;
  - la base est écrite AVANT la crontab et défaite si la crontab refuse : dans l'autre sens, une ligne orpheline s'exécutait en root sans que rien ne la référence ;
  - une commande destructrice reste possible (c'est un outil d'administration) mais jamais par accident : un accord explicite, et seulement sur ce qui détruit vraiment ;
  - un essai n'écrit pas au journal : il ne doit pas changer l'état de la tâche, sinon essayer reviendrait à maquiller une panne en réussite ;
  - un mode maintenance a une DATE de fin, pas une intention ; deux tâches qui s'attendent l'une l'autre ne partiraient jamais et rien ne le dirait : la boucle est refusée.

Ce module est privilégié par nature (une tâche planifiée s'exécute en root) : il ne touche à rien lui-même. Il demande au courtier trois commandes que SON installation a posées en root
(lire les crontabs, réécrire celle d'un utilisateur permis, lancer une tâche déjà planifiée) ; ses réglages de prudence sont les paliers, choisis par l'administrateur.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import time
from datetime import datetime, timedelta, timezone

from . import CN_cron as k

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
ETIQUETTE = "# cassandra-id:"
ENROBAGE = "/usr/local/lib/cassandra/cron-wrap.sh"
CACHE_S = 45


def utc():
    return datetime.now(timezone.utc)


def maintenant():
    return utc().strftime("%Y-%m-%d %H:%M")


def guillemets(s):
    return "'" + (s or "").replace("'", "'\\''") + "'"


def brancher(ctx):
    db = ctx.stockage
    ctx.dossier_donnees = None
    cache = {"t": 0.0, "jobs": None, "erreur": ""}

    def donnees():
        return ctx.dossier_donnees or os.environ.get("CASSANDRA_DONNEES") or ""

    def reservee():
        c = ctx.compte
        if c and c not in SYSTEME and not ctx.est_admin(c):
            raise PermissionError("les tâches planifiées sont réservées à l'administrateur : elles s'exécutent en root")

    def acteur_qui():
        return ctx.compte or ctx.acteur or "système"

    def modif(ref, quoi):
        db.ecrire("INSERT INTO modifs(ref, ts, acteur, quoi) VALUES (?,?,?,?)", (str(ref or ""), time.time(), acteur_qui()[:60], str(quoi)[:300]))
        db.ecrire("DELETE FROM modifs WHERE ref=? AND id NOT IN (SELECT id FROM modifs WHERE ref=? ORDER BY id DESC LIMIT 40)", (str(ref or ""), str(ref or "")))

    # ------------------------------------------------------------------ le système, par le courtier
    def table(user):
        r = ctx.racine("lire_table", [user], None, 15)
        if not r["ok"]:
            raise ValueError("lecture de la crontab de %s impossible : %s" % (user, (r["erreur"] or "le courtier n'a pas répondu").strip()[:200]))
        return r["sortie"]

    def ecrire_table(user, texte):
        r = ctx.racine("ecrire_crontab", [user], texte if texte.endswith("\n") else texte + "\n", 20)
        if not r["ok"]:
            raise ValueError("crontab : %s" % ((r["erreur"] or "refus du courtier").strip()[:200]))

    def systeme(force=False):
        """Les tâches du système (crontabs, cron.d), gardées 45 s : le courtier est lent à réveiller, un écran ne l'attend pas à chaque affichage. -> (liste, erreur)"""
        if not force and cache["jobs"] is not None and time.time() - cache["t"] < CACHE_S:
            return cache["jobs"], cache["erreur"]
        r = ctx.racine("lire_crontabs", [], None, 15)
        if r["ok"]:
            try:
                cache.update(t=time.time(), jobs=json.loads(r["sortie"] or "[]"), erreur="")
            except ValueError:
                cache.update(t=time.time(), erreur="sortie illisible du courtier")
        else:
            cache["erreur"] = (r["erreur"] or "le courtier n'a pas répondu").strip()[:200]
            cache["t"] = time.time() - CACHE_S + 10          # on retente dans dix secondes, sans marteler
        return (cache["jobs"] or []), cache["erreur"]

    def oublier_cache():
        cache.update(t=0.0)

    # ------------------------------------------------------------------ les exécutions
    def ingerer():
        """Range les comptes rendus déposés par l'enrobage dans le journal, puis les supprime. Un compte rendu illisible est écarté et effacé : le laisser le ferait retenter indéfiniment."""
        spool = os.path.join(donnees(), "cron-runs")
        if not donnees() or not os.path.isdir(spool):
            return 0
        n = 0
        for nom in sorted(os.listdir(spool))[:500]:
            chemin = os.path.join(spool, nom)
            if nom.startswith("."):
                continue
            try:
                with open(chemin, encoding="utf-8", errors="replace") as f:
                    contenu = f.read(200000)
                tete, _, corps = contenu.partition("\n")
                p = tete.split("|")
                if len(p) != 4:
                    raise ValueError("en-tête illisible")
                db.ecrire("INSERT INTO executions(ref, debut, duree_ms, code, sortie, declencheur) VALUES (?,?,?,?,?,?)", (p[0][:80], p[1][:16], int(p[2]), int(p[3]), corps.strip()[:4000], "cron"))
                n += 1
            except (OSError, ValueError):
                pass
            try:
                os.remove(chemin)
            except OSError:
                pass
        return n

    def dernieres():
        return {r["ref"]: (r["debut"], r["code"], r["declencheur"]) for r in db.lire("SELECT ref, debut, code, declencheur FROM executions WHERE id IN (SELECT MAX(id) FROM executions GROUP BY ref)")}

    # ------------------------------------------------------------------ la vue unifiée
    def unifiee_interne(force=False):
        ingerer()
        now = maintenant()
        par = {}

        def mettre(ref, d):
            cur = par.get(ref)
            if cur is None:
                par[ref] = d
                return
            for cle, v in d.items():
                if v and not cur.get(cle):
                    cur[cle] = v
            cur["sources"] = sorted(set(cur.get("sources", []) + d.get("sources", [])))
        for r in db.lire("SELECT * FROM naturelles"):
            ref = k.reference(r["utilisateur"], r["commande"])
            mettre(ref, {"ref": ref, "utilisateur": r["utilisateur"], "horaire": r["horaire"], "commande": r["commande"], "description": r["description"], "actif": 1 if r["actif"] else 0,
                         "derniere": "", "dernier_statut": "", "creee": r["cree"], "id": r["id"], "enrobee": 1 if r["enrobee"] else 0, "sources": ["cassandra"]})
        sys_jobs, erreur = systeme(force)
        for c in sys_jobs:
            user, cmd = c.get("user") or "root", c.get("commande") or ""
            if not cmd:
                continue
            inner = cmd
            if cmd.split() and cmd.split()[0] == ENROBAGE:
                try:
                    p = shlex.split(cmd)
                    inner = " ".join(p[2:]) if len(p) >= 3 else cmd
                except ValueError:
                    pass
            ref = k.reference(user, inner)
            mettre(ref, {"ref": ref, "utilisateur": user, "horaire": c.get("horaire") or "", "commande": inner, "description": "", "actif": 1, "derniere": "", "dernier_statut": "", "creee": None,
                         "id": int(c["etiquette"]) if str(c.get("etiquette") or "").isdigit() else None, "enrobee": 1 if inner != cmd else 0, "sources": ["système"],
                         "cibles_manquantes": list(c.get("manquantes") or [])})
        manuel = dernieres()
        liens = {}
        for r in db.lire("SELECT ref, projet_id, libelle FROM liens"):
            liens.setdefault(r["ref"], []).append({"id": r["projet_id"], "nom": r["libelle"] or "?"})
        critiques = {r["ref"] for r in db.lire("SELECT ref FROM critiques")}
        out = []
        for ref, j in par.items():
            expr = j.get("horaire") or ""
            ts, code, decl = manuel.get(ref, ("", None, ""))
            if ts:
                j["derniere"], j["dernier_statut"], j["dernier_code"] = ts, "%s (code %s)" % (decl or "enregistré", code), code
            else:
                j["dernier_code"] = None
            j["a_historique"] = ref in manuel
            j["cibles_manquantes"] = j.get("cibles_manquantes") or []        # constatées par root, qui voit ce que le noyau ne voit pas (/root, les scripts privés)
            j["humain"] = k.decrire(expr)
            j["prochaine"] = k.suivante(expr, now) if j["actif"] else ""
            j["attendue_avant"] = k.precedente(expr, now) if j["actif"] else ""
            j["projets"] = liens.get(ref, [])
            j["critique"] = 1 if ref in critiques else 0
            j["etat"], j["etat_detail"] = k.etat(j, now)
            out.append(j)
        out.sort(key=lambda x: (k.ETAT_ORDRE.get(x["etat"], 6), x.get("utilisateur") or "", x.get("commande") or ""))
        return out, erreur

    def unifiee(c, forcer=False):
        reservee()
        jobs, erreur = unifiee_interne(bool(forcer))
        compteurs = {"total": len(jobs)}
        for j in jobs:
            compteurs[j["etat"]] = compteurs.get(j["etat"], 0) + 1
        try:
            projets = [{"id": p["id"], "nom": p["nom"]} for p in (ctx.executer_lecture("projets.lister") or {}).get("projets", [])]
        except Exception:
            projets = []
        return {"taches": jobs, "compteurs": compteurs, "projets": projets, "source_systeme": {"ok": not erreur, "erreur": erreur}}

    def trouver(ref):
        for j in unifiee_interne()[0]:
            if j["ref"] == ref:
                return j
        raise ValueError("tâche introuvable")

    def reglages_de(ref):
        r = db.lire("SELECT * FROM reglages_tache WHERE ref=?", (ref,))
        return dict(r[0]) if r else {"ref": ref, "fenetre_min": 0, "verrou": 0, "essais": 0, "motif_echec": "", "apres_ref": "", "apres_si_ok": 1, "nom": ""}

    def reglages(c, ref=""):
        reservee()
        if ref:
            return {"reglages": reglages_de(ref)}
        return {"reglages": {r["ref"]: dict(r) for r in db.lire("SELECT * FROM reglages_tache")}}

    def historique(c, ref="", limite=20):
        reservee()
        return {"executions": [dict(r) for r in db.lire("SELECT debut, duree_ms, code, sortie, declencheur FROM executions WHERE ref=? ORDER BY id DESC LIMIT ?", (ref, max(1, min(int(limite or 20), 100))))]}

    def serie(c, mesure="", depuis="", jusqu_a=""):
        """Les exécutions (ou les échecs) datées : un point par exécution, pour l'historique."""
        reservee()
        if mesure not in ("cron_runs", "cron_fail"):
            raise ValueError("mesure inconnue : « %s »" % mesure)
        a, b = str(depuis)[:19].replace("T", " "), str(jusqu_a)[:19].replace("T", " ")
        cond = " AND code IS NOT NULL AND code <> 0" if mesure == "cron_fail" else ""
        rows = db.lire("SELECT debut FROM executions WHERE replace(substr(debut,1,19),'T',' ') BETWEEN ? AND ?%s ORDER BY debut" % cond, (a, b))
        return {"series": [{"nom": "exécutions" if mesure == "cron_runs" else "échecs", "points": [[str(r["debut"])[:19].replace("T", " "), 1] for r in rows]}]}

    def duree_moyenne(ref):
        r = db.lire("SELECT AVG(duree_ms) AS m FROM executions WHERE ref=? AND duree_ms>0", (ref,))
        return int(r[0]["m"]) if r and r[0]["m"] else 0

    def fiche(c, ref=""):
        """Tout ce qu'une tâche peut dire d'elle-même, en un appel."""
        reservee()
        j = trouver(ref)
        runs = [dict(r) for r in db.lire("SELECT debut, duree_ms, code, sortie, declencheur FROM executions WHERE ref=? ORDER BY id DESC LIMIT 40", (ref,))][::-1]
        expr = j.get("horaire") or ""
        manque = set(j.get("cibles_manquantes") or [])
        inter = k.intervalle_min(expr, maintenant())
        moy = duree_moyenne(ref)
        durees = [r["duree_ms"] for r in db.lire("SELECT duree_ms FROM executions WHERE ref=? AND code=0 AND duree_ms>0 ORDER BY id", (ref,))]
        auj = utc()
        return {"tache": j, "executions": runs, "reglages": reglages_de(ref), "prochaines": k.apercu(expr, maintenant(), 5) if j["actif"] else [],
                "cibles": [{"chemin": t, "present": 0 if t in manque else 1} for t in k.cibles(j.get("commande") or "")], "derive": k.derive(durees),
                "modifs": [{"ts": datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S"), "acteur": r["acteur"], "quoi": r["quoi"]} for r in db.lire("SELECT ts, acteur, quoi FROM modifs WHERE ref=? ORDER BY id DESC LIMIT 12", (ref,))],
                "duree_moyenne_ms": moy, "intervalle_min": inter, "chevauche": bool(inter and moy and moy / 60000.0 > inter),
                "occurrences_touchees": len(k.occurrences(expr, auj.strftime("%Y-%m-%d"), (auj + timedelta(days=30)).strftime("%Y-%m-%d"), 24)) if j["actif"] else 0,
                "lourde": 1 if k.LOURDES.search(j.get("commande") or "") else 0, "destructive": k.destructeur(j.get("commande") or "")}

    def chevauchements_de(jobs):
        out = []
        for j in jobs:
            if not j["actif"]:
                continue
            moy = duree_moyenne(j["ref"])
            if moy <= 0:
                continue
            inter = k.intervalle_min(j.get("horaire") or "", maintenant())
            if inter and moy / 60000.0 > inter:
                out.append({"ref": j["ref"], "libelle": j.get("description") or j.get("commande") or j["ref"], "duree_min": round(moy / 60000.0, 1), "intervalle_min": inter,
                            "verrou": 1 if reglages_de(j["ref"])["verrou"] else 0})
        return out

    def chevauchements(c):
        reservee()
        return {"chevauchements": chevauchements_de(unifiee_interne()[0])}

    def manquantes_sauvegardes(jobs):
        """Les projets d'infrastructure sans aucune sauvegarde planifiée : l'absence de tâche ne déclenche rien, par définition, c'est le seul défaut que ni le journal, ni le silence, ni le code de sortie ne révéleront."""
        sauvegardes = [j for j in jobs if j["actif"] and k.SAUVEGARDE.search((j.get("commande") or "") + " " + (j.get("description") or ""))]
        liees = {p["id"] for j in sauvegardes for p in j.get("projets", [])}
        try:
            projets = (ctx.executer_lecture("projets.lister") or {}).get("projets", [])
        except Exception:
            return []
        out = []
        for p in projets:
            if p.get("genre") != "infra" or p.get("archive") or p["id"] in liees:
                continue
            dom = (p.get("domaine") or "").strip().lower()
            if dom and any(dom in (j.get("commande") or "").lower() for j in sauvegardes):      # un domaine cité dans une commande de sauvegarde vaut rattachement
                continue
            out.append({"id": p["id"], "nom": p.get("nom") or "?", "domaine": p.get("domaine") or ""})
        return out

    def audit(c):
        reservee()
        jobs = unifiee_interne()[0]
        return {"collisions": [dict(x, repartition=k.repartir(x)) for x in k.collisions(jobs)], "sauvegardes_manquantes": manquantes_sauvegardes(jobs)}

    def apercu(c, expression="", nombre=5):
        reservee()
        ok, e = k.valider(expression or "", "x")
        if not ok:
            raise ValueError(e)
        return {"expression": e, "humain": k.decrire(e), "prochaines": k.apercu(e, maintenant(), nombre)}

    def maintenance_etat(c):
        reservee()
        fin = db.lire("SELECT fin FROM maintenance WHERE id=1")[0]["fin"]
        actif = bool(fin) and fin > maintenant()
        return {"actif": actif, "fin": fin if actif else ""}

    def resume(c):
        reservee()
        jobs, erreur = unifiee_interne()
        mauvais = [j for j in jobs if j["etat"] in ("cassé", "échec", "muet")]
        return {"total": len(jobs), "ennuis": len(mauvais), "pire": ("%d en panne" % len(mauvais)) if mauvais else "tout à l'heure", "etat": "danger" if mauvais else "ok",
                "maintenance": maintenance_etat(c), "source_systeme": {"ok": not erreur, "erreur": erreur}}

    # ------------------------------------------------------------------ écrire la crontab, une ligne à la fois
    def appliquer(user, id_, expr, commande, actif, enrobee, ref):
        """Réécrit LA ligne de ce cron dans la crontab de l'utilisateur, sans toucher aux autres. Toute ligne portant la même étiquette est retirée d'abord : une modification remplace, elle n'empile pas.
        Un cron désactivé disparaît de la crontab mais reste en base : sinon « désactiver » perdrait la définition."""
        etiquette = "%s%d" % (ETIQUETTE, int(id_))
        gardees = [l for l in table(user).splitlines() if etiquette not in l]
        if actif:
            cmd = commande.strip()
            if enrobee:
                cmd = "%s %s %s" % (ENROBAGE, ref or k.reference(user, cmd), guillemets(cmd))
            gardees.append("%s %s %s" % (expr.strip(), cmd, etiquette))
        ecrire_table(user, "\n".join(l for l in gardees if l.strip() != "") + "\n")
        oublier_cache()

    def preuve_ligne(user, id_, doit_exister):
        etiquette = "%s%d" % (ETIQUETTE, int(id_))
        presente = any(etiquette in l for l in table(user).splitlines())
        return presente == doit_exister

    def sauver(c, description="", horaire="", commande="", id=None, actif=True, projet_id=None, confirmer_destructeur=False, enrobee=True, utilisateur="root"):
        """Crée ou modifie une tâche planifiée. La base d'abord, puis la crontab ; si la crontab refuse, la base revient comme avant."""
        reservee()
        ok, e = k.valider(horaire, commande)
        if not ok:
            raise ValueError(e)
        cmd = str(commande).strip()
        desc = str(description or "").strip()[:200] or cmd[:60]
        danger = k.destructeur(cmd)
        if danger and not confirmer_destructeur:
            raise ValueError("Commande destructrice (%s). Elle s'exécutera en root, automatiquement, à chaque déclenchement : confirmer_destructeur=true pour la poser." % danger)
        user = str(utilisateur or "root")
        avant = None
        if id:
            r = db.lire("SELECT * FROM naturelles WHERE id=?", (int(id),))
            if not r:
                raise ValueError("tâche introuvable")
            avant = dict(r[0])
            user = avant["utilisateur"]
            db.ecrire("UPDATE naturelles SET description=?, horaire=?, commande=?, actif=?, enrobee=? WHERE id=?", (desc, e, cmd, 1 if actif else 0, 1 if enrobee else 0, int(id)))
            nid = int(id)
        else:
            nid = db.ecrire("INSERT INTO naturelles(description, horaire, commande, utilisateur, actif, enrobee, cree) VALUES (?,?,?,?,?,?,?)", (desc, e, cmd, user, 1 if actif else 0, 1 if enrobee else 0, time.time()))
        ref = k.reference(user, cmd)
        try:
            appliquer(user, nid, e, cmd, bool(actif), bool(enrobee), ref)
        except Exception:
            if avant:
                db.ecrire("UPDATE naturelles SET description=?, horaire=?, commande=?, actif=?, enrobee=? WHERE id=?", (avant["description"], avant["horaire"], avant["commande"], avant["actif"], avant["enrobee"], nid))
            else:
                db.ecrire("DELETE FROM naturelles WHERE id=?", (nid,))
            raise
        if projet_id:
            db.ecrire("INSERT OR REPLACE INTO liens(ref, projet_id, libelle) VALUES (?,?,?)", (ref, int(projet_id), desc[:120]))
        modif(ref, "créée" if not avant else "modifiée : %s → %s" % (avant["horaire"], e))
        return {"id": nid, "ref": ref, "horaire": e, "commande": cmd, "actif": bool(actif), "enrobee": bool(enrobee), "utilisateur": user, "prochaines": k.apercu(e, maintenant(), 3), "avant": avant}

    def prouver_sauvee(c, res):
        r = db.lire("SELECT * FROM naturelles WHERE id=?", (res["id"],))
        return bool(r) and r[0]["horaire"] == res["horaire"] and preuve_ligne(res["utilisateur"], res["id"], bool(res["actif"]))

    def defaire_sauvee(c, res):
        a = res.get("avant")
        if a:
            db.ecrire("UPDATE naturelles SET description=?, horaire=?, commande=?, actif=?, enrobee=? WHERE id=?", (a["description"], a["horaire"], a["commande"], a["actif"], a["enrobee"], a["id"]))
            appliquer(a["utilisateur"], a["id"], a["horaire"], a["commande"], bool(a["actif"]), bool(a["enrobee"]), k.reference(a["utilisateur"], a["commande"]))
        else:
            appliquer(res["utilisateur"], res["id"], "", "", False, False, "")
            db.ecrire("DELETE FROM naturelles WHERE id=?", (res["id"],))

    def basculer(c, id=0, actif=True):
        reservee()
        r = db.lire("SELECT * FROM naturelles WHERE id=?", (int(id),))
        if not r:
            raise ValueError("tâche introuvable")
        a = dict(r[0])
        db.ecrire("UPDATE naturelles SET actif=? WHERE id=?", (1 if actif else 0, a["id"]))
        try:
            appliquer(a["utilisateur"], a["id"], a["horaire"], a["commande"], bool(actif), bool(a["enrobee"]), k.reference(a["utilisateur"], a["commande"]))
        except Exception:
            db.ecrire("UPDATE naturelles SET actif=? WHERE id=?", (a["actif"], a["id"]))
            raise
        modif(k.reference(a["utilisateur"], a["commande"]), "réactivée" if actif else "désactivée")
        return {"id": a["id"], "avant": a, "actif": 1 if actif else 0}

    def prouver_basculee(c, res):
        a = res["avant"]
        return db.lire("SELECT actif FROM naturelles WHERE id=?", (a["id"],))[0]["actif"] == res["actif"] and preuve_ligne(a["utilisateur"], a["id"], bool(res["actif"]))

    def defaire_basculee(c, res):
        a = res["avant"]
        db.ecrire("UPDATE naturelles SET actif=? WHERE id=?", (a["actif"], a["id"]))
        appliquer(a["utilisateur"], a["id"], a["horaire"], a["commande"], bool(a["actif"]), bool(a["enrobee"]), k.reference(a["utilisateur"], a["commande"]))

    def supprimer(c, id=0):
        """La crontab d'abord : si la base échouait après, il resterait une définition sans exécution (gênant, inoffensif). L'inverse laisserait une commande root qui tourne sans trace."""
        reservee()
        r = db.lire("SELECT * FROM naturelles WHERE id=?", (int(id),))
        if not r:
            raise ValueError("tâche introuvable")
        a = dict(r[0])
        ref = k.reference(a["utilisateur"], a["commande"])
        appliquer(a["utilisateur"], a["id"], "", "", False, False, "")
        liens = [dict(x) for x in db.lire("SELECT * FROM liens WHERE ref=?", (ref,))]
        db.ecrire("DELETE FROM naturelles WHERE id=?", (a["id"],))
        db.ecrire("DELETE FROM liens WHERE ref=?", (ref,))
        modif(ref, "supprimée")
        return {"id": a["id"], "avant": a, "liens": liens}

    def prouver_supprimee(c, res):
        return not db.lire("SELECT 1 FROM naturelles WHERE id=?", (res["id"],)) and preuve_ligne(res["avant"]["utilisateur"], res["id"], False)

    def defaire_supprimee(c, res):
        a = res["avant"]
        db.ecrire("INSERT INTO naturelles(id, description, horaire, commande, utilisateur, actif, enrobee, cree) VALUES (?,?,?,?,?,?,?,?)",
                  (a["id"], a["description"], a["horaire"], a["commande"], a["utilisateur"], a["actif"], a["enrobee"], a["cree"]))
        for l in res.get("liens", []):
            db.ecrire("INSERT OR REPLACE INTO liens(ref, projet_id, libelle) VALUES (?,?,?)", (l["ref"], l["projet_id"], l["libelle"]))
        appliquer(a["utilisateur"], a["id"], a["horaire"], a["commande"], bool(a["actif"]), bool(a["enrobee"]), k.reference(a["utilisateur"], a["commande"]))

    def critique(c, ref="", critique=True, libelle=""):
        reservee()
        ref = str(ref or "").strip()
        if not ref:
            raise ValueError("référence manquante")
        avant = db.lire("SELECT * FROM critiques WHERE ref=?", (ref,))
        if critique:
            db.ecrire("INSERT OR REPLACE INTO critiques(ref, libelle) VALUES (?,?)", (ref, str(libelle or "")[:200]))
        else:
            db.ecrire("DELETE FROM critiques WHERE ref=?", (ref,))
        modif(ref, "marquée critique" if critique else "n'est plus critique")
        return {"ref": ref, "critique": bool(critique), "avant": dict(avant[0]) if avant else None}

    def prouver_critique(c, res):
        return bool(db.lire("SELECT 1 FROM critiques WHERE ref=?", (res["ref"],))) == res["critique"]

    def defaire_critique(c, res):
        db.ecrire("DELETE FROM critiques WHERE ref=?", (res["ref"],))
        if res["avant"]:
            db.ecrire("INSERT INTO critiques(ref, libelle) VALUES (?,?)", (res["avant"]["ref"], res["avant"]["libelle"]))

    def lier(c, ref="", projet_id=0, libelle=""):
        reservee()
        if not ref or not int(projet_id):
            raise ValueError("référence et projet obligatoires")
        db.ecrire("INSERT OR REPLACE INTO liens(ref, projet_id, libelle) VALUES (?,?,?)", (str(ref), int(projet_id), str(libelle or "")[:200]))
        return {"ref": ref, "projet_id": int(projet_id)}

    def prouver_lie(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE ref=? AND projet_id=?", (res["ref"], res["projet_id"])))

    def defaire_lie(c, res):
        db.ecrire("DELETE FROM liens WHERE ref=? AND projet_id=?", (res["ref"], res["projet_id"]))

    def delier(c, ref="", projet_id=0):
        reservee()
        av = db.lire("SELECT * FROM liens WHERE ref=? AND projet_id=?", (str(ref), int(projet_id)))
        if not av:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE ref=? AND projet_id=?", (str(ref), int(projet_id)))
        return {"ref": ref, "projet_id": int(projet_id), "avant": dict(av[0])}

    def prouver_delie(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE ref=? AND projet_id=?", (res["ref"], res["projet_id"]))

    def defaire_delie(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO liens(ref, projet_id, libelle) VALUES (?,?,?)", (a["ref"], a["projet_id"], a["libelle"]))

    def ecrire_options(ref, vals):
        """Dépose le verrou et la fenêtre là où l'enrobage les lira (il lit ces fichiers au départ de chaque exécution, et n'en retient qu'un chiffre)."""
        if not donnees():
            return
        dossier = os.path.join(donnees(), "cron-opts")
        os.makedirs(dossier, exist_ok=True)
        sur = re.sub(r"[^A-Za-z0-9_.-]", "_", str(ref))[:120]
        with open(os.path.join(dossier, sur), "w", encoding="utf-8") as f:
            f.write("verrou=%d\nfenetre=%d\n" % (1 if vals.get("verrou") else 0, int(vals.get("fenetre_min") or 0) * 60))

    def reglages_poser(c, ref="", fenetre_min=0, verrou=False, essais=0, motif_echec="", apres_ref="", apres_si_ok=True, nom=""):
        reservee()
        ref = str(ref or "").strip()
        if not ref:
            raise ValueError("tâche non désignée")
        apres = str(apres_ref or "").strip()
        if apres == ref:
            raise ValueError("une tâche ne peut pas s'enchaîner à elle-même")
        suivants = {r["ref"]: r["apres_ref"] for r in db.lire("SELECT ref, apres_ref FROM reglages_tache WHERE apres_ref<>''")}
        if apres and k.boucle(ref, apres, suivants):
            raise ValueError("cet enchaînement forme une boucle — les deux tâches s'attendraient indéfiniment")
        vals = {"fenetre_min": max(0, min(1440, int(fenetre_min or 0))), "verrou": 1 if verrou else 0, "essais": max(0, min(5, int(essais or 0))), "motif_echec": str(motif_echec or "")[:120],
                "apres_ref": apres, "apres_si_ok": 1 if apres_si_ok else 0, "nom": str(nom or "")[:120]}
        try:
            re.compile(vals["motif_echec"] or "x")
        except re.error:
            raise ValueError("le motif d'échec n'est pas une expression valide")
        avant = reglages_de(ref)
        existait = bool(db.lire("SELECT 1 FROM reglages_tache WHERE ref=?", (ref,)))
        db.ecrire("INSERT OR REPLACE INTO reglages_tache(ref, fenetre_min, verrou, essais, motif_echec, apres_ref, apres_si_ok, nom) VALUES (?,?,?,?,?,?,?,?)", (ref,) + tuple(vals.values()))
        ecrire_options(ref, vals)
        changes = [x for x in vals if str(avant.get(x, "")) != str(vals[x])]
        if changes:
            modif(ref, "réglages modifiés : " + ", ".join(changes))
        return {"ref": ref, "reglages": dict(vals, ref=ref), "avant": avant, "existait": existait}

    def prouver_reglages(c, res):
        return reglages_de(res["ref"])["verrou"] == res["reglages"]["verrou"] and reglages_de(res["ref"])["fenetre_min"] == res["reglages"]["fenetre_min"]

    def defaire_reglages(c, res):
        if res["existait"]:
            a = res["avant"]
            db.ecrire("INSERT OR REPLACE INTO reglages_tache(ref, fenetre_min, verrou, essais, motif_echec, apres_ref, apres_si_ok, nom) VALUES (?,?,?,?,?,?,?,?)",
                      (a["ref"], a["fenetre_min"], a["verrou"], a["essais"], a["motif_echec"], a["apres_ref"], a["apres_si_ok"], a["nom"]))
            ecrire_options(a["ref"], a)
        else:
            db.ecrire("DELETE FROM reglages_tache WHERE ref=?", (res["ref"],))
            ecrire_options(res["ref"], {})

    def maintenance(c, actif=True, heures=4):
        """Suspend tout sauf le critique, avec RETOUR AUTOMATIQUE : la fin est une date, pas une intention. La sentinelle est lue par l'enrobage ; sans elle, « suspendre » ne serait qu'une intention affichée."""
        reservee()
        avant = db.lire("SELECT fin FROM maintenance WHERE id=1")[0]["fin"]
        fin = (utc() + timedelta(hours=max(1, min(24, int(heures or 4))))).strftime("%Y-%m-%d %H:%M") if actif else ""
        db.ecrire("UPDATE maintenance SET fin=? WHERE id=1", (fin,))
        if donnees():
            drapeau = os.path.join(donnees(), "cron-maintenance")
            if fin:
                exemptes = [r["ref"] for r in db.lire("SELECT ref FROM critiques")]
                with open(drapeau, "w", encoding="utf-8") as f:
                    f.write(fin + "\n" + "\n".join(exemptes) + "\n")
            elif os.path.exists(drapeau):
                os.remove(drapeau)
        modif("", ("mode maintenance jusqu'au %s" % fin) if fin else "mode maintenance levé")
        return {"actif": bool(fin), "fin": fin, "avant": avant, "portee": "les tâches journalisées, sauf celles marquées critiques"}

    def prouver_maintenance(c, res):
        return db.lire("SELECT fin FROM maintenance WHERE id=1")[0]["fin"] == res["fin"]

    def defaire_maintenance(c, res):
        db.ecrire("UPDATE maintenance SET fin=? WHERE id=1", (res["avant"],))
        if donnees():
            drapeau = os.path.join(donnees(), "cron-maintenance")
            if res["avant"] and res["avant"] > maintenant():
                with open(drapeau, "w", encoding="utf-8") as f:
                    f.write(res["avant"] + "\n" + "\n".join(r["ref"] for r in db.lire("SELECT ref FROM critiques")) + "\n")
            elif os.path.exists(drapeau):
                os.remove(drapeau)

    def lancer_tache(j, delai, essai, declencheur):
        reg = reglages_de(j["ref"])
        if reg["fenetre_min"]:
            delai = min(int(delai or 120), int(reg["fenetre_min"]) * 60)       # la fenêtre attendue devient le délai réel
        essais = 0 if essai else max(0, int(reg["essais"] or 0))
        debut = maintenant()
        t0 = time.time()
        code, sortie = -1, ""
        for tentative in range(essais + 1):
            r = ctx.racine("lancer", [str(max(5, min(int(delai or 120), 3600)))], j["commande"], max(5, min(int(delai or 120), 3600)) + 10)
            if r["ok"]:
                try:
                    d = json.loads(r["sortie"])
                    code, sortie = int(d.get("code", -1)), str(d.get("sortie") or "")
                except ValueError:
                    code, sortie = -1, "sortie illisible du courtier"
            else:                                           # le courtier a refusé ou n'a pas répondu : rien n'a tourné, ce n'est pas une exécution en échec
                raise ValueError("la tâche n'a pas pu être lancée : %s" % ((r["erreur"] or "le courtier n'a pas répondu").strip()[:200]))
            motif = str(reg.get("motif_echec") or "")
            if code == 0 and motif:
                try:
                    if re.search(motif, sortie or "", re.I):
                        code, sortie = 90, ("[Cassandra] la sortie contient « %s » — considéré comme un échec.\n" % motif) + (sortie or "")
                except re.error:
                    pass
            if code == 0 or tentative >= essais:
                break
            time.sleep(min(ctx.pause_essais, 5 * (tentative + 1)))
        ms = int((time.time() - t0) * 1000)
        sortie = sortie.strip()[:4000]
        if essais and code != 0:
            sortie = "[Cassandra] %d essai(s) supplémentaire(s), tous en échec.\n%s" % (essais, sortie)
        ident = None
        if not essai:                                          # un ESSAI ne s'inscrit pas au journal : il ne doit pas changer l'état de la tâche
            ident = db.ecrire("INSERT INTO executions(ref, debut, duree_ms, code, sortie, declencheur) VALUES (?,?,?,?,?,?)", (j["ref"], debut, ms, code, sortie, declencheur))
        return {"ref": j["ref"], "code": code, "duree_ms": ms, "sortie": sortie, "debut": debut, "commande": j["commande"], "essai": bool(essai), "execution": ident,
                "fenetre_depassee": bool(reg["fenetre_min"] and ms > int(reg["fenetre_min"]) * 60000)}
    ctx.pause_essais = 30

    def executer(c, ref="", id=None, essai=False, delai=120):
        """Exécute la commande UNE fois, tout de suite, et garde sa sortie : attendre le prochain créneau pour savoir si un cron fonctionne est le meilleur moyen de ne jamais le savoir.
        Le courtier ne lance que ce qui est déjà planifié. Ce que la commande a fait n'est pas défait par le retour : seule la ligne du journal l'est."""
        reservee()
        if id and not ref:
            r = db.lire("SELECT utilisateur, commande FROM naturelles WHERE id=?", (int(id),))
            if not r:
                raise ValueError("tâche introuvable")
            ref = k.reference(r[0]["utilisateur"], r[0]["commande"])
        j = trouver(ref)
        return lancer_tache(j, delai, essai, "manuel")

    def prouver_executee(c, res):
        return res["essai"] or bool(db.lire("SELECT 1 FROM executions WHERE id=?", (res["execution"],)))

    def defaire_executee(c, res):
        if res.get("execution"):
            db.ecrire("DELETE FROM executions WHERE id=?", (res["execution"],))

    # ------------------------------------------------------------------ les moteurs et le détecteur
    def suite(c):
        """Déclenche les tâches en attente de leur amont : cron ne sait pas faire ça (on met 03:00 et 03:30 en espérant que la première ait fini). Ici la seconde lit le code de sortie de la première."""
        chainees = {r["ref"]: dict(r) for r in db.lire("SELECT * FROM reglages_tache WHERE apres_ref<>''")}
        if not chainees:
            return {"lancees": []}
        derniers = dernieres()
        jobs = {j["ref"]: j for j in unifiee_interne()[0]}
        lancees = []
        for ref, r in chainees.items():
            ts_amont, code_amont, _ = derniers.get(r["apres_ref"], ("", None, ""))
            if not ts_amont:
                continue
            if r["apres_si_ok"] and code_amont not in (0, None):
                continue                                        # l'amont a échoué : la suite ne part pas
            ts_moi = (derniers.get(ref) or ("", None, ""))[0]
            if ts_moi and ts_moi >= ts_amont:
                continue                                        # déjà passée depuis l'amont
            if ref in jobs:
                res = lancer_tache(jobs[ref], 600, False, "suite")
                lancees.append({"ref": ref, "apres": r["apres_ref"], "code": res["code"]})
        return {"lancees": lancees}

    def passe(c):
        n = ingerer()
        s = suite(c) if db.lire("SELECT 1 FROM reglages_tache WHERE apres_ref<>'' LIMIT 1") else {"lancees": []}
        fin = db.lire("SELECT fin FROM maintenance WHERE id=1")[0]["fin"]
        if fin and fin <= maintenant():                         # une maintenance échue se lève toute seule
            db.ecrire("UPDATE maintenance SET fin='' WHERE id=1")
            if donnees() and os.path.exists(os.path.join(donnees(), "cron-maintenance")):
                os.remove(os.path.join(donnees(), "cron-maintenance"))
        return {"ingerees": n, "suite": len(s["lancees"])}

    def det_pannes(c):
        """Une tâche cassée, en échec ou muette ; une dérive de durée ; un chevauchement. Un constat par ligne, qui se referme seul quand l'état revient."""
        try:
            jobs, _ = unifiee_interne()
        except Exception:
            return []
        out = []
        for j in jobs:
            nom = j.get("description") or j.get("commande") or j["ref"]
            if j["etat"] in ("cassé", "échec", "muet"):
                out.append({"objet": ("tache_planifiee", j["ref"]), "titre": "Tâche planifiée %s : %s" % ({"cassé": "cassée", "échec": "en échec", "muet": "muette"}[j["etat"]], nom[:80]),
                            "detail": j["etat_detail"], "niveau": "critique" if j["critique"] else "attention"})
            d = k.derive([r["duree_ms"] for r in db.lire("SELECT duree_ms FROM executions WHERE ref=? AND code=0 AND duree_ms>0 ORDER BY id", (j["ref"],))])
            if d:
                out.append({"objet": ("tache_planifiee", j["ref"] + ":derive"), "titre": "Tâche planifiée plus lente : %s" % nom[:80],
                            "detail": "%d s en moyenne au début, %d s maintenant (×%s) : la fenêtre de nuit finira par ne plus suffire." % (d["avant_ms"] // 1000, d["apres_ms"] // 1000, d["facteur"]), "niveau": "attention"})
        for x in chevauchements_de(jobs):
            out.append({"objet": ("tache_planifiee", x["ref"] + ":chevauchement"), "titre": "Tâche planifiée qui se chevauche : %s" % x["libelle"][:80],
                        "detail": "Elle dure %s min en moyenne pour un intervalle de %d min.%s" % (x["duree_min"], x["intervalle_min"], "" if x["verrou"] else " Aucun verrou : deux copies peuvent tourner ensemble."), "niveau": "attention"})
        return out

    c = ctx
    c.moteur("passe", passe)
    c.detecteur("taches_en_panne", det_pannes)
    for cid, f in (("unifiee", unifiee), ("fiche", fiche), ("historique", historique), ("reglages", reglages), ("chevauchements", chevauchements), ("audit", audit), ("serie", serie), ("apercu", apercu),
                   ("maintenance_etat", maintenance_etat), ("resume", resume)):
        c.implementer(cid, f)
    c.implementer("sauver", sauver, prouver_sauvee, defaire_sauvee, simuler=lambda x, description="", horaire="", **_: "poserait la tâche « %s » (%s)" % (description, horaire))
    c.implementer("basculer", basculer, prouver_basculee, defaire_basculee, simuler=lambda x, id=0, actif=True, **_: "%s la tâche %s" % ("réactiverait" if actif else "désactiverait", id))
    c.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee, simuler=lambda x, id=0, **_: "retirerait la tâche %s de la crontab et de la base" % id)
    c.implementer("critique", critique, prouver_critique, defaire_critique, simuler=lambda x, ref="", **_: "changerait la criticité de %s" % ref)
    c.implementer("lier", lier, prouver_lie, defaire_lie, simuler=lambda x, ref="", **_: "rattacherait %s à un projet" % ref)
    c.implementer("delier", delier, prouver_delie, defaire_delie, simuler=lambda x, ref="", **_: "détacherait %s d'un projet" % ref)
    c.implementer("reglages_poser", reglages_poser, prouver_reglages, defaire_reglages, simuler=lambda x, ref="", **_: "réglerait verrou, fenêtre et enchaînement de %s" % ref)
    c.implementer("maintenance", maintenance, prouver_maintenance, defaire_maintenance, simuler=lambda x, actif=True, heures=4, **_: ("suspendrait les tâches %d h" % heures) if actif else "lèverait la maintenance")
    c.implementer("executer", executer, prouver_executee, defaire_executee, simuler=lambda x, ref="", **_: "lancerait une fois la tâche %s, tout de suite" % ref)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : utc, maintenant, guillemets, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
