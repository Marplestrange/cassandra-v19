# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'atelier de l'équipe
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.2.0  #faee09
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'atelier de l'équipe : les capacités de lecture (equipe, agent, couts, paliers) et de réglage (agent_regler, palier_regler, niveau_regler, plafond_regler) du module agents, et les services que le tour de conversation emploie (réglage effec
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=faee09 ▼▼▼
"""L'atelier de l'équipe : les capacités de lecture (equipe, agent, couts, paliers) et de réglage (agent_regler, palier_regler, niveau_regler, plafond_regler) du module agents,
et les services que le tour de conversation emploie (réglage effectif, palier par outil, coût du jour, plafond).

Le cloisonnement vit dans `cible()` : un agent « de compte » (Itare) se règle et se lit pour LE COMPTE QUI AGIT, jamais pour un autre, administrateur compris ;
un agent « d'instance » (Cassandra, Amizo, les services) n'est à la portée que de l'administrateur.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

from . import CN_equipe as eq

D = eq.DONNEES
COLONNES = ("nom_affiche", "ton", "modele", "secours", "niveau")
CHAMPS_REGLABLES = {"nom_affiche": 40, "ton": 2000, "modele": 80, "secours": 80, "limites": 0}


def brancher_equipe(ctx, reglage):
    db = ctx.stockage

    # ------------------------------------------------------------------ les définitions (des données, semées une fois)
    for a in D["agents"]:
        db.ecrire("INSERT OR IGNORE INTO agents_def(id, genre, nom, role, portee, acteur_outils, niveau_defaut, modele_defaut, ordre) VALUES (?,?,?,?,?,?,?,?,?)",
                  (a["id"], a["genre"], a["nom"], a["role"], a["portee"], a["acteur_outils"], a["niveau_defaut"], a["modele_defaut"], a["ordre"]))

    def definitions():
        return {r["id"]: dict(r) for r in db.lire("SELECT * FROM agents_def ORDER BY ordre, id")}

    def definition(agent):
        d = definitions().get(str(agent or "").strip().lower())
        if d is None:
            raise ValueError("agent inconnu : %s" % " | ".join(definitions()))
        return d

    def compte_agit():
        c = ctx.compte
        if not c or c in eq.SYSTEME:
            raise ValueError("l'équipe se règle pour un compte : aucun compte n'agit")
        return c

    def admin(compte):
        return ctx.est_admin(compte)

    def cible(agent, compte):
        """La clé de compte sous laquelle on lit et règle cet agent. Itare : celle du compte qui agit (jamais un autre). Les autres : '' — pour l'administrateur seulement."""
        d = definition(agent)
        if d["portee"] == "compte":
            return d, compte
        if not admin(compte):
            raise PermissionError("%s se règle depuis l'administration : ce compte n'agit que sur son propre Itare" % d["nom"])
        return d, ""

    def visibles(compte):
        ds = definitions().values()
        return [d for d in ds if admin(compte) or d["portee"] == "compte"]

    # ------------------------------------------------------------------ la configuration effective
    def ligne(agent, compte):
        r = db.lire("SELECT * FROM agent_config WHERE agent=? AND compte=?", (agent, compte))
        return dict(r[0]) if r else None

    def effectif(agent, compte=""):
        d = definition(agent)
        cfg = {"agent": d["id"], "nom_affiche": d["nom"], "ton": "", "modele": d["modele_defaut"], "secours": "", "niveau": d["niveau_defaut"], "limites": {}}
        for cle in (("",) if not compte else ("", compte)):
            r = ligne(d["id"], cle)
            if not r:
                continue
            for k in COLONNES:
                if r[k] is not None:
                    cfg[k] = r[k]
            cfg["limites"].update(json.loads(r["limites"] or "{}"))
        return cfg

    def limite(cfg, nom, defaut):
        v = cfg["limites"].get(nom)
        return int(v) if isinstance(v, int) and not isinstance(v, bool) else defaut

    def tarifs(cfg):
        return limite(cfg, "tarif_entree_cts", D["tarif_defaut_cts"]["entree"]), limite(cfg, "tarif_sortie_cts", D["tarif_defaut_cts"]["sortie"])

    # ------------------------------------------------------------------ les paliers par outil
    def surcharges(agent, compte):
        return {r["outil"]: {"palier": r["palier"], "confirmer": bool(r["confirmer"])} for r in db.lire("SELECT * FROM agent_paliers WHERE agent=? AND compte=?", (agent, compte))}

    def outils_de(d):
        if not d["acteur_outils"]:
            return []
        return [t for t in ctx.outils(d["acteur_outils"]) if d["acteur_outils"] == "cassandra" or not t["nom"].startswith(tuple(D["interdit_hors_cassandra"]))]

    def palier_outil(t, surcharge):
        """Le palier effectif d'un outil pour cet agent : le sien s'il a été posé, sinon celui du catalogue ; une lecture n'a pas de palier."""
        if t["risque"] == "lecture":
            return {"palier": "lecture", "confirmer": False, "retire": bool(surcharge and surcharge["palier"] == "retire"), "defaut": ""}
        s = surcharge or {}
        p = s.get("palier") or t["palier"] or "raconter"
        return {"palier": p, "confirmer": bool(s.get("confirmer")), "retire": p == "retire", "defaut": t["palier"]}

    # ------------------------------------------------------------------ les coûts
    def depense(agent="", compte=None):
        sql, a = "SELECT COALESCE(SUM(centimes),0) AS c, COALESCE(SUM(appels),0) AS n, COALESCE(SUM(entrees),0) AS e, COALESCE(SUM(sorties),0) AS s FROM agent_couts WHERE jour=?", [eq.jour()]
        if agent:
            sql += " AND agent=?"
            a.append(agent)
        if compte is not None:
            sql += " AND compte=?"
            a.append(compte)
        return dict(db.lire(sql, a)[0])

    def compter(agent, compte, usage):
        """Le coût d'un échange avec le modèle, ajouté au jour : par agent, et par compte pour Itare."""
        d = definition(agent)
        e, s = int((usage or {}).get("prompt_tokens") or 0), int((usage or {}).get("completion_tokens") or 0)
        te, ts = tarifs(effectif(agent, compte if d["portee"] == "compte" else ""))
        cle = compte if d["portee"] == "compte" else ""
        db.ecrire("INSERT INTO agent_couts(jour, agent, compte, appels, entrees, sorties, centimes) VALUES (?,?,?,1,?,?,?) ON CONFLICT(jour, agent, compte) DO UPDATE SET "
                  "appels=appels+1, entrees=entrees+excluded.entrees, sorties=sorties+excluded.sorties, centimes=centimes+excluded.centimes",
                  (eq.jour(), d["id"], cle, e, s, eq.cout_centimes(e, s, te, ts)))

    def plafonds():
        return {r["portee"]: dict(r) for r in db.lire("SELECT * FROM agent_plafonds")}

    def verdict(agent):
        """Rien ne retient (None) ou le plafond qui retient, avec son action. La dépense de l'agent est celle de toute l'instance pour lui (tous comptes) : le plafond de Itare est partagé."""
        pl = plafonds()
        if not pl:
            return None
        dep = {"global": depense()["c"], agent: depense(agent)["c"]}
        return eq.verdict_plafond(pl, dep, agent, eq.jour())

    def retenir(agent, compte, genre, outil="", args=None):
        deja = db.lire("SELECT id FROM agent_attentes WHERE agent=? AND compte=? AND genre=? AND outil=? AND etat='attente' AND args=?", (agent, compte, genre, outil, json.dumps(args or {}, sort_keys=True, ensure_ascii=False)))
        if deja:
            return deja[0]["id"]
        return db.ecrire("INSERT INTO agent_attentes(agent, compte, genre, outil, args, ts) VALUES (?,?,?,?,?,?)", (agent, compte, genre, outil, json.dumps(args or {}, sort_keys=True, ensure_ascii=False), time.time()))

    # ------------------------------------------------------------------ lectures
    def decompte(d, compte):
        sur = surcharges(d["id"], compte if d["portee"] == "compte" else "")
        n = {"lecture": 0, "auto": 0, "raconter": 0, "maitre": 0, "retire": 0}
        for t in outils_de(d):
            p = palier_outil(t, sur.get(t["cle"]))
            n["retire" if p["retire"] else p["palier"]] += 1
        return n

    def cout_visible(d, compte):
        dep = depense(d["id"], compte if d["portee"] == "compte" and not admin(compte) else None)
        return {"euros": eq.euros(dep["c"]), "appels": dep["n"]}

    def equipe(c):
        compte = compte_agit()
        sortie = []
        for d in visibles(compte):
            cfg = effectif(d["id"], compte if d["portee"] == "compte" else "")
            n = decompte(d, compte)
            v = verdict(d["id"])
            sortie.append({"id": d["id"], "genre": d["genre"], "nom": cfg["nom_affiche"], "role": d["role"], "niveau": cfg["niveau"], "modele": cfg["modele"], "secours": cfg["secours"],
                           "outils": n, "nb_outils": sum(n.values()), "cout_jour": cout_visible(d, compte), "plafond_atteint": bool(v), "portee": d["portee"]})
        return {"equipe": sortie, "compte": compte, "administrateur": admin(compte)}

    def agent(c, id=""):
        compte = compte_agit()
        d, cle = cible(id, compte)
        cfg = effectif(d["id"], cle)
        sur = surcharges(d["id"], cle)
        out = []
        for t in outils_de(d):
            p = palier_outil(t, sur.get(t["cle"]))
            out.append({"cle": t["cle"], "risque": t["risque"], "palier": p["palier"], "confirmer": p["confirmer"], "retire": p["retire"]})
        res = {"agent": {"id": d["id"], "genre": d["genre"], "nom": cfg["nom_affiche"], "nom_origine": d["nom"], "role": d["role"], "portee": d["portee"], "ton": cfg["ton"], "modele": cfg["modele"],
                         "secours": cfg["secours"], "niveau": cfg["niveau"], "limites": cfg["limites"], "tarifs_cts": list(tarifs(cfg))},
               "outils": out, "decompte": decompte(d, compte), "cout_jour": cout_visible(d, compte), "compte": compte}
        if admin(compte):
            res["plafond"] = {"agent": plafonds().get(d["id"]), "global": plafonds().get("global")}
        v = verdict(d["id"])
        res["plafond_atteint"] = ({"portee": v["portee"], "action": v["action"]} if v else None)
        return res

    def paliers(c, id=""):
        compte = compte_agit()
        d, cle = cible(id, compte)
        sur = surcharges(d["id"], cle)
        out = []
        for t in outils_de(d):
            p = palier_outil(t, sur.get(t["cle"]))
            out.append({"cle": t["cle"], "description": t["description"], "risque": t["risque"], "palier": p["palier"], "confirmer": p["confirmer"], "retire": p["retire"], "defaut": p["defaut"], "pose": t["cle"] in sur})
        return {"agent": d["id"], "paliers": out, "compte": compte}

    def couts(c, id="", jours=7):
        compte = compte_agit()
        jours = max(1, min(int(jours or 7), 90))
        voit_tout = admin(compte)
        if id:
            d = definition(id)
            if d["portee"] != "compte" and not voit_tout:
                raise PermissionError("les coûts de %s ne se lisent que depuis l'administration" % d["nom"])
        depuis = time.strftime("%Y-%m-%d", time.localtime(eq.maintenant() - (jours - 1) * 86400))
        sql, a = "SELECT jour, agent, SUM(appels) AS appels, SUM(entrees) AS entrees, SUM(sorties) AS sorties, SUM(centimes) AS c FROM agent_couts WHERE jour>=?", [depuis]
        if id:
            sql += " AND agent=?"
            a.append(definition(id)["id"])
        if not voit_tout:
            sql += " AND agent='itare' AND compte=?"          # un compte ne lit que son propre Itare
            a.append(compte)
        lignes = [{"jour": r["jour"], "agent": r["agent"], "appels": r["appels"], "entrees": r["entrees"], "sorties": r["sorties"], "euros": eq.euros(r["c"])}
                  for r in db.lire(sql + " GROUP BY jour, agent ORDER BY jour DESC, agent", a)]
        auj = depense(definition(id)["id"] if id else "")["c"] if voit_tout else depense("itare", compte)["c"]
        res = {"jours": lignes, "total_euros": round(sum(x["euros"] for x in lignes), 6), "aujourdhui_euros": eq.euros(auj)}
        if voit_tout:
            res["plafonds"] = {k: {"euros": eq.euros(v["centimes"]), "action": v["action"], "accord_jour": v["accord_jour"]} for k, v in plafonds().items()}
        return res

    # ------------------------------------------------------------------ réglages : chacun prouve et se défait
    def agent_regler(c, id="", champs=None):
        compte = compte_agit()
        d, cle = cible(id, compte)
        champs = champs if isinstance(champs, dict) else {}
        inconnus = [k for k in champs if k not in CHAMPS_REGLABLES]
        if inconnus or not champs:
            raise ValueError("champs réglables : %s" % ", ".join(CHAMPS_REGLABLES))
        avant = ligne(d["id"], cle)
        neuf = dict(avant) if avant else {"agent": d["id"], "compte": cle, "nom_affiche": None, "ton": None, "modele": None, "secours": None, "niveau": None, "limites": "{}"}
        for k, v in champs.items():
            if k == "limites":
                lim = json.loads(neuf["limites"] or "{}")
                if not isinstance(v, dict):
                    raise ValueError("limites : un objet {nom: valeur}")
                for nom, val in v.items():
                    if nom not in D["limites"]:
                        raise ValueError("limite inconnue : %s (%s)" % (nom, ", ".join(D["limites"])))
                    if val is None:
                        lim.pop(nom, None)
                        continue
                    lo, hi = D["limites"][nom]
                    if isinstance(val, bool) or not isinstance(val, int) or not lo <= val <= hi:
                        raise ValueError("%s : un entier entre %d et %d" % (nom, lo, hi))
                    lim[nom] = val
                neuf["limites"] = json.dumps(lim, sort_keys=True)
                continue
            texte = str(v).strip() if v is not None else None
            if texte is not None and len(texte) > CHAMPS_REGLABLES[k]:
                raise ValueError("%s : %d caractères au plus" % (k, CHAMPS_REGLABLES[k]))
            if k in ("modele", "secours") and texte is not None and not eq.MODELE_OK.match(texte):
                raise ValueError("%s : le nom d'un rôle ou d'un modèle (lettres, chiffres, _ . : / -)" % k)
            if k == "nom_affiche" and texte == "":
                raise ValueError("nom_affiche : un nom est requis")
            neuf[k] = texte if k == "nom_affiche" else (texte or None)       # vide : on retombe sur l'héritage
        neuf["maj"] = time.time()
        poser_ligne(neuf)
        return {"agent": d["id"], "compte": cle, "avant": avant, "apres": ligne(d["id"], cle)}

    def poser_ligne(r):
        db.ecrire("INSERT OR REPLACE INTO agent_config(agent, compte, nom_affiche, ton, modele, secours, niveau, limites, maj) VALUES (?,?,?,?,?,?,?,?,?)",
                  (r["agent"], r["compte"], r["nom_affiche"], r["ton"], r["modele"], r["secours"], r["niveau"], r["limites"], r["maj"]))

    def prouver_config(c, res):
        a = ligne(res["agent"], res["compte"])
        return a is not None and all(a[k] == res["apres"][k] for k in COLONNES + ("limites",))

    def defaire_config(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM agent_config WHERE agent=? AND compte=?", (res["agent"], res["compte"]))
        else:
            poser_ligne(res["avant"])

    def niveau_regler(c, agent="", niveau=""):
        compte = compte_agit()
        d, cle = cible(agent, compte)
        if niveau not in D["niveaux"]:
            raise ValueError("niveau : %s" % " | ".join(D["niveaux"]))
        avant = ligne(d["id"], cle)
        base = dict(avant) if avant else {"agent": d["id"], "compte": cle, "nom_affiche": None, "ton": None, "modele": None, "secours": None, "niveau": None, "limites": "{}"}
        base["niveau"], base["maj"] = niveau, time.time()
        poser_ligne(base)
        return {"agent": d["id"], "compte": cle, "avant": avant, "apres": ligne(d["id"], cle)}

    def palier_regler(c, agent="", outil="", palier="", confirmer=None):
        compte = compte_agit()
        d, cle = cible(agent, compte)
        if palier not in D["paliers"] + ["defaut", ""]:
            raise ValueError("palier : %s | defaut" % " | ".join(D["paliers"]))
        if palier == "" and confirmer is None:
            raise ValueError("rien à régler : un palier ou `confirmer`")
        if not d["acteur_outils"]:
            raise ValueError("%s n'a pas d'outils à régler" % d["nom"])
        t = next((x for x in outils_de(d) if x["cle"] == outil), None)
        if t is None:
            raise ValueError("outil inconnu pour %s : %s" % (d["nom"], outil))
        avant = db.lire("SELECT * FROM agent_paliers WHERE agent=? AND compte=? AND outil=?", (d["id"], cle, outil))
        avant = dict(avant[0]) if avant else None
        p = palier or (avant["palier"] if avant else "auto")
        conf = int(bool(confirmer)) if confirmer is not None else (avant["confirmer"] if avant else 0)
        if t["risque"] == "lecture" and (p == "raconter" or conf):
            raise ValueError("une lecture n'a ni palier « raconter » ni confirmation : seulement « retire »")
        if p == "retire" and conf:
            raise ValueError("un outil retiré ne se confirme pas")
        if p == "defaut":
            db.ecrire("DELETE FROM agent_paliers WHERE agent=? AND compte=? AND outil=?", (d["id"], cle, outil))
        else:
            db.ecrire("INSERT OR REPLACE INTO agent_paliers(agent, compte, outil, palier, confirmer, maj) VALUES (?,?,?,?,?,?)", (d["id"], cle, outil, p, conf, time.time()))
        apres = db.lire("SELECT * FROM agent_paliers WHERE agent=? AND compte=? AND outil=?", (d["id"], cle, outil))
        return {"agent": d["id"], "compte": cle, "outil": outil, "avant": avant, "apres": dict(apres[0]) if apres else None}

    def prouver_palier(c, res):
        r = db.lire("SELECT * FROM agent_paliers WHERE agent=? AND compte=? AND outil=?", (res["agent"], res["compte"], res["outil"]))
        return (dict(r[0]) if r else None) == res["apres"]

    def defaire_palier(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM agent_paliers WHERE agent=? AND compte=? AND outil=?", (res["agent"], res["compte"], res["outil"]))
        else:
            a = res["avant"]
            db.ecrire("INSERT OR REPLACE INTO agent_paliers(agent, compte, outil, palier, confirmer, maj) VALUES (?,?,?,?,?,?)", (a["agent"], a["compte"], a["outil"], a["palier"], a["confirmer"], a["maj"]))

    def plafond_regler(c, portee="", euros=None, action="secours", accorder=False):
        compte = compte_agit()
        if not admin(compte):
            raise PermissionError("les plafonds de coût se règlent depuis l'administration")
        portee = str(portee or "").strip().lower()
        if portee != "global":
            portee = definition(portee)["id"]
        if action not in D["actions_plafond"]:
            raise ValueError("action : %s" % " | ".join(D["actions_plafond"]))
        avant = db.lire("SELECT * FROM agent_plafonds WHERE portee=?", (portee,))
        avant = dict(avant[0]) if avant else None
        if accorder:
            if avant is None:
                raise ValueError("aucun plafond à lever pour %s" % portee)
            db.ecrire("UPDATE agent_plafonds SET accord_jour=?, maj=? WHERE portee=?", (eq.jour(), time.time(), portee))
        elif euros is None:
            db.ecrire("DELETE FROM agent_plafonds WHERE portee=?", (portee,))
        else:
            if isinstance(euros, bool) or not isinstance(euros, (int, float)) or euros <= 0 or euros > 1_000_000:
                raise ValueError("euros : un montant positif (le plafond d'un jour)")
            db.ecrire("INSERT OR REPLACE INTO agent_plafonds(portee, centimes, action, accord_jour, maj) VALUES (?,?,?,?,?)", (portee, int(round(float(euros) * 100)), action, "", time.time()))
        apres = db.lire("SELECT * FROM agent_plafonds WHERE portee=?", (portee,))
        return {"portee": portee, "avant": avant, "apres": dict(apres[0]) if apres else None}

    def prouver_plafond(c, res):
        r = db.lire("SELECT * FROM agent_plafonds WHERE portee=?", (res["portee"],))
        return (dict(r[0]) if r else None) == res["apres"]

    def defaire_plafond(c, res):
        a = res["avant"]
        if a is None:
            db.ecrire("DELETE FROM agent_plafonds WHERE portee=?", (res["portee"],))
        else:
            db.ecrire("INSERT OR REPLACE INTO agent_plafonds(portee, centimes, action, accord_jour, maj) VALUES (?,?,?,?,?)", (a["portee"], a["centimes"], a["action"], a["accord_jour"], a["maj"]))

    # ------------------------------------------------------------------ inscription
    for cid, f in (("equipe", equipe), ("agent", agent), ("couts", couts), ("paliers", paliers)):
        ctx.implementer(cid, f)
    ctx.implementer("agent_regler", agent_regler, prouver_config, defaire_config, simuler=lambda x, id="", champs=None, **_: "réglerait %s : %s" % (id, ", ".join(sorted(champs or {}))))
    ctx.implementer("niveau_regler", niveau_regler, prouver_config, defaire_config, simuler=lambda x, agent="", niveau="", **_: "mettrait %s au niveau %s" % (agent, niveau))
    ctx.implementer("palier_regler", palier_regler, prouver_palier, defaire_palier, simuler=lambda x, agent="", outil="", palier="", **_: "poserait le palier « %s » à %s pour %s" % (palier or "inchangé", outil, agent))
    ctx.implementer("plafond_regler", plafond_regler, prouver_plafond, defaire_plafond, simuler=lambda x, portee="", euros=None, **_: "poserait un plafond de %s € par jour sur %s" % (euros, portee))

    # ce que le tour de conversation emploie
    return SimpleNamespace(effectif=effectif, limite=limite, surcharges=surcharges, outils_de=outils_de, compter=compter, verdict=verdict, retenir=retenir, definitions=definitions, palier_outil=palier_outil)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher_equipe
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
