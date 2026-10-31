# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.3.0  #d266db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les agents : Cassandra (la machine) et Itare (le bureau) en conversation.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=d266db ▼▼▼
"""Les agents : Cassandra (la machine) et Itare (le bureau) en conversation.

Porté de la V18 (`call_deepseek_stream`, `_tool_loop`, `_handle_tool`, `build_system_prompt`, le fil solo), avec ses leçons :
  - L'ORDRE EST IMPOSÉ PAR L'API : le message assistant porteur des appels précède les réponses des outils, et CHAQUE appel reçoit sa réponse — même un outil inconnu, des arguments illisibles
    ou un échec (sinon « tool_calls must have responses » et le travail du tour est perdu) ; un fil relu est remis en cohérence avant l'envoi ;
  - un modèle qui raisonne dépense son budget en réflexion et rend un contenu vide sans erreur : un seul rejeu, budget triplé, consigne de réponse directe (le module des modèles le fait) ;
  - après des outils, l'agent conclut TOUJOURS en clair ; si le modèle ne rend que des appels puis rien, on lui demande de résumer ;
  - une PANNE n'est pas une parole de l'agent : elle se range sous un rôle à part et ne revient jamais dans le contexte ;
  - ARRÊTER : une demande lue entre deux étapes ; une action déjà lancée finit (son journal et son retour sont pris avant qu'elle parte) ;
  - la TEINTE : après une lecture venue de l'extérieur (un message reçu, une page), du texte étranger est dans le tour ; ce qui SORT de la maison, ou engage fortement, ne part plus tout seul ;
  - le compte atteint la porte : l'agent agit AU NOM du compte qui parle, avec SES droits — jamais plus (administrer n'est pas voir) ;
  - les outils ne sont plus écrits à la main : ils dérivent du catalogue. Un outil « raconté » n'a rien fait, et l'agent le dit ;
  - un tour à la fois par conversation ; les erreurs d'un outil se disent au modèle, elles ne font pas tomber le tour.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from . import CN_outils as o
from .CN_atelier import brancher_equipe
from .CN_garde import brancher_garde
from .CN_propositions import REF_SOUVENIR, brancher_propositions

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
AGENTS = ("cassandra", "itare")
ECRITURES_RISQUEES = ("moyen", "eleve")


def brancher(ctx):
    o._point = ctx.point
    db = ctx.stockage

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("une conversation est celle d'un compte : aucun compte n'agit")
        return c

    def lecture(cap, **a):
        try:
            return ctx.executer_lecture(cap, **a)
        except Exception:
            return None

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
        except Exception:
            return defaut
        return defaut if v in (None, "") else v

    E = brancher_equipe(ctx, reglage)                                  # l'équipe : réglages par agent, paliers par outil, coûts et plafonds
    P = brancher_propositions(ctx, E, o, lecture, reglage)             # « À valider », la carte de confiance, « Pourquoi ? »
    G = brancher_garde(ctx, E, o, lecture, reglage)                    # la sentinelle anti-fuite, le Relecteur, les épreuves de sûreté

    def cle_cfg(agent, compte):
        """Itare se règle compte par compte ; les autres agents pour toute l'instance."""
        return compte if agent == "itare" else ""

    # ------------------------------------------------------------------ conversations
    def conv_brute(cid, compte):
        try:
            r = db.lire("SELECT * FROM conversations WHERE id=? AND compte=? AND supprime_at IS NULL", (int(cid), compte))
        except (TypeError, ValueError):
            return None
        return r[0] if r else None

    def exiger(cid, compte):
        c = conv_brute(cid, compte)
        if c is None:
            raise ValueError("conversation introuvable")
        return c

    def conversations(c):
        compte = compte_agit()
        return {"conversations": db.lire("SELECT c.id, c.agent, c.titre, c.cree, c.maj, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id AND m.role IN ('user','assistant')) AS n "
                                         "FROM conversations c WHERE c.compte=? AND c.supprime_at IS NULL ORDER BY c.maj DESC LIMIT 200", (compte,))}

    def messages_de(cid, limite=None):
        sql = "SELECT * FROM messages WHERE conversation_id=? ORDER BY id"
        rows = db.lire(sql, (cid,))
        return rows[-int(limite):] if limite else rows

    def conversation(c, id=0, limite=200):
        compte = compte_agit()
        cv = exiger(id, compte)
        msgs = messages_de(cv["id"], max(1, min(int(limite or 200), 1000)))
        return {"conversation": {k: cv[k] for k in ("id", "agent", "titre", "cree", "maj")},
                "messages": [{"id": m["id"], "role": m["role"], "contenu": m["contenu"], "appels": json.loads(m["appels"]) if m["appels"] else None, "nom": m["nom"], "statut": m["statut"], "tour": m["tour"], "ts": m["ts"]}
                             for m in msgs], "en_cours": bool(cv["en_cours"] and time.time() - cv["en_cours"] < 600)}

    def conversation_creer(c, agent="cassandra", titre=""):
        compte = compte_agit()
        agent = str(agent or "cassandra").strip().lower()
        if agent not in AGENTS:
            raise ValueError("agent : %s" % " | ".join(AGENTS))
        now = time.time()
        cid = db.ecrire("INSERT INTO conversations(compte, agent, titre, cree, maj) VALUES (?,?,?,?,?)", (compte, agent, str(titre or "").strip()[:120], now, now))
        return {"id": cid, "compte": compte, "agent": agent}

    def prouver_creee(c, res):
        return conv_brute(res["id"], res["compte"]) is not None

    def defaire_creee(c, res):
        db.ecrire("DELETE FROM messages WHERE conversation_id=?", (res["id"],))
        db.ecrire("DELETE FROM conversations WHERE id=?", (res["id"],))

    def conversation_renommer(c, id=0, titre=""):
        compte = compte_agit()
        cv = exiger(id, compte)
        t = str(titre or "").strip()[:120]
        if not t:
            raise ValueError("un titre est requis")
        db.ecrire("UPDATE conversations SET titre=? WHERE id=?", (t, cv["id"]))
        return {"id": cv["id"], "compte": compte, "titre": t, "avant": cv["titre"]}

    def prouver_renomme(c, res):
        return conv_brute(res["id"], res["compte"])["titre"] == res["titre"]

    def defaire_renomme(c, res):
        db.ecrire("UPDATE conversations SET titre=? WHERE id=?", (res["avant"], res["id"]))

    def conversation_supprimer(c, id=0):
        compte = compte_agit()
        cv = exiger(id, compte)
        copie = {"conversation": dict(cv), "messages": messages_de(cv["id"])}
        db.ecrire("DELETE FROM messages WHERE conversation_id=?", (cv["id"],))
        db.ecrire("DELETE FROM conversations WHERE id=?", (cv["id"],))
        db.ecrire("DELETE FROM arrets WHERE conversation_id=?", (cv["id"],))
        return {"id": cv["id"], "compte": compte, "copie": copie}

    def prouver_supprimee(c, res):
        return not db.lire("SELECT 1 FROM conversations WHERE id=?", (res["id"],))

    def defaire_supprimee(c, res):
        with db.transaction() as cx:
            for t, lignes in (("conversations", [res["copie"]["conversation"]]), ("messages", res["copie"]["messages"])):
                for ligne in lignes:
                    ks = list(ligne)
                    cx.execute("INSERT OR REPLACE INTO %s(%s) VALUES (%s)" % (t, ",".join(ks), ",".join("?" * len(ks))), [ligne[k] for k in ks])

    def arreter(c, id=0):
        compte = compte_agit()
        cv = exiger(id, compte)
        deja = bool(db.lire("SELECT 1 FROM arrets WHERE conversation_id=?", (cv["id"],)))
        db.ecrire("INSERT OR REPLACE INTO arrets(conversation_id, ts) VALUES (?,?)", (cv["id"], time.time()))
        return {"id": cv["id"], "compte": compte, "deja": deja}

    def prouver_arret(c, res):
        return bool(db.lire("SELECT 1 FROM arrets WHERE conversation_id=?", (res["id"],)))

    def defaire_arret(c, res):
        if not res["deja"]:
            db.ecrire("DELETE FROM arrets WHERE conversation_id=?", (res["id"],))

    def outils(c):
        compte = compte_agit()
        return {"outils": [{k: v for k, v in t.items() if k != "parametres"} | {"arguments": list(t["parametres"]["properties"])} for t in ctx.outils("itare")], "compte": compte}

    # ------------------------------------------------------------------ le tour
    def stocker(cid, role, contenu="", appels=None, tool_call_id="", nom="", statut="", tour=0):
        return db.ecrire("INSERT INTO messages(conversation_id, role, contenu, appels, tool_call_id, nom, statut, tour, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                         (cid, role, str(contenu or "")[:o.CONTENU_MAX], json.dumps(appels, ensure_ascii=False) if appels else "", tool_call_id, nom, statut, tour, time.time()))

    def fil_pour_modele(cid, taille):
        """Le fil relu : seules les paroles comptent (une panne n'y revient jamais), remis en cohérence avant l'envoi."""
        rows = [m for m in db.lire("SELECT * FROM messages WHERE conversation_id=? AND role<>'panne' ORDER BY id DESC LIMIT ?", (cid, int(taille)))][::-1]
        while rows and rows[0]["role"] == "tool":
            rows.pop(0)
        msgs = []
        for m in rows:
            if m["role"] == "assistant":
                msg = {"role": "assistant", "content": m["contenu"] or None}
                if m["appels"]:
                    msg["tool_calls"] = json.loads(m["appels"])
                msgs.append(msg)
            elif m["role"] == "tool":
                msgs.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["contenu"]})
            else:
                msgs.append({"role": "user", "content": m["contenu"]})
        return o.coherents(msgs)

    def modele_pour(agent, cfg, secours=False):
        """Les rôles essayés, dans l'ordre. Cassandra parle par le rôle de la maison ; Itare par le modèle que le compte a choisi, à défaut par le rôle d'Itare ;
        le réglage de l'agent (modèle principal) l'emporte, et son modèle de secours ferme la liste. Au plafond « secours », le secours seul."""
        if secours and (cfg["secours"] or agent != "cassandra"):          # Cassandra n'est jamais coupée : sans secours, elle garde son modèle
            roles = [cfg["secours"]] if cfg["secours"] else []
        else:
            if cfg["modele"]:
                roles = [cfg["modele"]]
            elif agent == "itare":
                roles = ["", str(reglage("role_itare", "itare_citadelle"))]
            else:
                roles = [str(reglage("role_cassandra", "principal"))]
            roles = roles + ([cfg["secours"]] if cfg["secours"] and cfg["secours"] not in roles else [])
        if reglage("epreuves_exigees", False) in (True, 1, "1", "true"):  # un modèle qui a échoué à ses épreuves de sûreté ne sert pas un agent (un modèle jamais éprouvé n'est pas écarté)
            roles = [r for r in roles if not r or not G.deconseille(r)]
        return roles

    def appeler_modele(agent, compte, cfg, msgs, systeme, tools, max_jetons, secours=False):
        derniere = {"ok": False, "erreur": "aucun modèle"}
        for role in modele_pour(agent, cfg, secours):
            r = lecture("modeles.completer", messages=msgs, systeme=systeme, max_tokens=max_jetons, role=role, outils=tools, allow_reasoning=True, timeout=120.0, temperature=0.4)
            if isinstance(r, dict):
                try:
                    if r.get("usage"):
                        E.compter(agent, compte, r["usage"])            # le coût du jour, par agent
                except Exception:
                    pass
            if isinstance(r, dict) and r.get("ok"):
                return r
            derniere = r if isinstance(r, dict) else derniere
        return derniere

    def executer_appel(a, index, par_cle, tous, etat, agent, compte=""):
        """Un appel d'outil : TOUJOURS une réponse pour le modèle, jamais une exception."""
        nom, args = a["nom"], a["arguments"]
        if "_brut" in args:
            return "Arguments illisibles (JSON invalide) : %s — recommence avec un objet JSON valide." % args["_brut"][:200], None
        if nom == o.META_CHERCHE:
            ms = o.mots(args.get("requete", ""))
            trouves = sorted(((o.score(t, ms), t) for t in tous), key=lambda x: (-x[0], x[1]["cle"]))
            return o.court([{"cle": t["cle"], "role": t["description"], "risque": t["risque"], "palier": t["palier"], "arguments": t["parametres"]["properties"] and list(t["parametres"]["properties"]),
                             "externe": t["externe"], "sortant": t["sortant"]} for s, t in trouves if s > 0][:15]) or "Aucun outil ne correspond.", None
        if nom == o.META_APPELER:
            t = par_cle.get(str(args.get("cle") or ""))
            args = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
        else:
            t = index.get(nom)
        if t is None:
            cible = str(a["arguments"].get("cle") or nom) if nom == o.META_APPELER else nom
            return "Outil inconnu ou non disponible pour toi : %s. Utilise `%s` pour trouver le bon." % (cible, o.META_CHERCHE), None
        def proposer(origine, resume="", attente=0):
            """Ce que l'agent ne fait pas seul entre dans « À valider » ; une proposition ratée ne fait jamais tomber le tour."""
            try:
                return P.proposer(agent, compte, t, args, origine, resume=resume, pourquoi="Demande : « %s »" % (etat.get("message") or "")[:160], conversation_id=etat.get("cid", 0), tour=etat.get("tour", 0), attente=attente)
            except Exception:
                return None

        def refusee(prop):
            return ("Non exécuté : l'utilisateur a déjà refusé cette même action (proposition n° %d) : ne la repropose pas, sauf s'il te le redemande." % prop["id"], {"cle": t["cle"], "statut": "refusee", "risque": t["risque"]})

        sur = E.surcharges(agent, cle_cfg(agent, compte)).get(t["cle"]) or {}
        if (t["sortant"] or t["risque"] in ECRITURES_RISQUEES) and etat["teinte"]:
            prop = proposer("retenue")
            if prop and prop["etat"] == "refusee":
                return refusee(prop)
            return ("Non exécuté : ce tour a lu du contenu venu de l'extérieur (%s). Une action qui sort de la maison, ou qui engage fortement, ne part pas seule après une lecture étrangère : "
                    "dis à la personne ce que tu ferais et demande-lui de confirmer dans un nouveau message." % ", ".join(sorted(set(etat["teinte"])))), {"cle": t["cle"], "statut": "retenue"}
        if t["risque"] != "lecture" and (sur.get("confirmer") or etat["niveau"] == "observer" or sur.get("palier") == "raconter"):
            if sur.get("confirmer"):                                   # « demander » : un accord posé sur « auto », retenu jusqu'à ce qu'on décide
                attente = E.retenir(agent, compte, "confirmer", t["cle"], args)
                prop = proposer("confirmer", attente=attente)
                if prop and prop["etat"] == "refusee":
                    return refusee(prop)
                return "Non exécuté : cette action demande l'accord de l'utilisateur (elle est retenue dans « À valider », rien n'a été fait). Dis-le tel quel.", {"cle": t["cle"], "statut": "a_confirmer", "risque": t["risque"]}
            sim = ctx.agir(t["cle"], args, acteur=agent, essai=True)   # observer, ou palier « raconter » posé pour cet agent : il raconte, il ne fait pas
            P.tracer(sim, agent, compte, t["cle"], etat, "raconter", etat["niveau"], False)
            prop = proposer("racontee", resume=sim.get("simulation") if sim.get("statut") == "simulee" else "")
            if prop and prop["etat"] == "refusee":
                return refusee(prop)
            return o.resume_resultat(dict(sim, statut="racontee", simulation=sim.get("simulation") if sim.get("statut") == "simulee" else ""), ctx.point), {"cle": t["cle"], "statut": "racontee", "risque": t["risque"]}
        r = ctx.agir(t["cle"], args, acteur=agent)
        P.tracer(r, agent, compte, t["cle"], etat, sur.get("palier") or t["palier"], etat["niveau"], sur.get("confirmer"))
        if r.get("statut") == "racontee":
            sim = ctx.agir(t["cle"], args, acteur=agent, essai=True)
            r = dict(r, simulation=sim.get("simulation") if sim.get("statut") == "simulee" else "")
            if t["risque"] != "lecture":
                prop = proposer("racontee", resume=r["simulation"])
                if prop and prop["etat"] == "refusee":
                    return refusee(prop)
        if t["externe"] and r.get("statut") == "faite":
            etat["teinte"].append(t["cle"])                    # du texte étranger est maintenant dans le tour
        if t["risque"] != "lecture" and r.get("statut") == "faite":
            etat["ecritures"] += 1
        return o.resume_resultat(r, ctx.point), {"cle": t["cle"], "statut": r.get("statut"), "risque": t["risque"], "evenement": r.get("evenement")}

    def converser(c, conversation_id=0, message="", agent="cassandra"):
        compte = compte_agit()
        message = str(message or "").strip()
        if not message:
            raise ValueError("un message est requis")
        if len(message) > 20000:
            raise ValueError("message trop long (20 000 caractères au plus)")
        if conversation_id:
            cv = exiger(conversation_id, compte)
        else:
            cv = db.lire("SELECT * FROM conversations WHERE id=?", (conversation_creer(c, agent)["id"],))[0]
        agent = cv["agent"]
        if cv["en_cours"] and time.time() - cv["en_cours"] < 600:
            raise ValueError("un tour est déjà en cours dans cette conversation")
        cid = cv["id"]
        db.ecrire("UPDATE conversations SET en_cours=? WHERE id=?", (time.time(), cid))
        db.ecrire("DELETE FROM arrets WHERE conversation_id=?", (cid,))
        crees, actions = [], []
        tour = (db.lire("SELECT COALESCE(MAX(tour),0) AS t FROM messages WHERE conversation_id=?", (cid,))[0]["t"]) + 1
        try:
            crees.append(stocker(cid, "user", message, tour=tour))
            if not cv["titre"]:
                db.ecrire("UPDATE conversations SET titre=? WHERE id=?", (" ".join(message.split())[:60], cid))
            try:
                ctx.agir("memoire.tour_commencer", {"question": message}, acteur=agent)
                memo = lecture("memoire.rappeler", question=message) or {}
            except Exception:
                memo = {}
            try:
                ctx.agir("memoire.doutes_depuis_reponse", {"texte": message}, acteur=agent)
            except Exception:
                pass
            cfg = E.effectif(agent, cle_cfg(agent, compte))
            retires = {k for k, v in E.surcharges(agent, cle_cfg(agent, compte)).items() if v["palier"] == "retire"}
            tous = [t for t in ctx.outils(agent) if t["cle"] not in retires and (agent == "cassandra" or not t["nom"].startswith("coffre__"))]     # Cassandra seule tient le coffre : jamais un outil de secret pour les autres
            par_cle = {t["cle"]: t for t in tous}
            pres = o.choisir_outils(tous, message, int(reglage("max_outils", 60)))
            index = {t["nom"]: t for t in tous}                    # tout ce qui est permis s'appelle par son nom, présenté ou non : le modèle peut s'en souvenir d'un tour précédent
            schemas = [o.schema_outil(t) for t in pres] + o.meta_outils()
            ton = ""
            persona = cfg["ton"] or str(reglage("persona_" + agent, ""))
            soc = lecture("societes.carte") or {}
            if soc.get("nom"):                                          # chaque société a ses agents : ils savent pour qui ils travaillent, et ne mélangent jamais deux sociétés
                persona = (persona + "\n\n" if persona else "") + "Tu travailles pour la société « %s »%s. Ses données et celles de ses utilisateurs lui appartiennent : n'en mélange jamais avec celles d'une autre société." % (
                    soc["nom"], (" (" + ", ".join(x for x in (soc.get("forme"), soc.get("ville")) if x) + ")") if (soc.get("forme") or soc.get("ville")) else "")
            try:
                ton = str((lecture("modeles.lister") or {}).get("ton") or "")
            except Exception:
                ton = ""
            systeme = o.prompt_systeme(agent, compte, datetime.now().strftime("%A %d %B %Y, %H:%M"), memo.get("bloc") or "", persona, ton, len(pres))
            etat = {"teinte": [], "ecritures": 0, "niveau": cfg["niveau"], "cid": cid, "tour": tour, "message": message, "memoires": sorted({int(i) for i in REF_SOUVENIR.findall(memo.get("bloc") or "")})}
            try:
                P.observer_outils(agent, cle_cfg(agent, compte), [t["cle"] for t in tous])      # la période d'essai d'un outil neuf commence à sa première apparition
            except Exception:
                pass
            texte, vide_rejoue, secours = "", False, False
            max_tours = E.limite(cfg, "max_tours", int(reglage("max_tours", 12)))
            for etape in range(max_tours):
                if db.lire("SELECT 1 FROM arrets WHERE conversation_id=?", (cid,)):
                    crees.append(stocker(cid, "panne", "Tour arrêté à ta demande.", tour=tour))
                    texte = ""
                    actions.append({"statut": "arrete"})
                    break
                v = E.verdict(agent)                                        # le plafond de coût le plus bas que la dépense du jour atteint
                if v and v["action"] == "accord":
                    E.retenir(agent, compte, "plafond")
                    crees.append(stocker(cid, "panne", "⚠️ Plafond de coût atteint (%s) : l'accord de l'administrateur est requis pour continuer aujourd'hui." % v["portee"], tour=tour))
                    actions.append({"statut": "plafond", "portee": v["portee"], "action": "accord"})
                    break
                if v and v["action"] == "arret" and agent != "cassandra":
                    crees.append(stocker(cid, "panne", "⚠️ Plafond de coût atteint (%s) : %s est arrêté jusqu'à demain." % (v["portee"], cfg["nom_affiche"]), tour=tour))
                    actions.append({"statut": "plafond", "portee": v["portee"], "action": "arret"})
                    break
                secours = bool(v and v["action"] in ("secours", "arret"))   # Cassandra n'est jamais arrêtée : au plafond elle passe sur son secours
                msgs = fil_pour_modele(cid, E.limite(cfg, "taille_fil", int(reglage("taille_fil", 40))))
                r = appeler_modele(agent, compte, cfg, msgs, systeme, schemas, E.limite(cfg, "max_jetons", int(reglage("max_jetons", 12000))), secours)
                if not r.get("ok") and etape > 0 and not vide_rejoue and "VIDE" in str(r.get("erreur", "")):
                    vide_rejoue = True                                      # des outils, puis un contenu vide : on demande de conclure, une fois
                    crees.append(stocker(cid, "user", "(Conclus maintenant en clair : ce qui a été fait, l'état final, ce qui reste.)", tour=tour))
                    continue
                if not r.get("ok"):
                    crees.append(stocker(cid, "panne", "⚠️ Panne de %s — %s" % (o.PERSONAS[agent][0].capitalize(), r.get("erreur", "le modèle n'a pas répondu")), tour=tour))
                    actions.append({"statut": "panne", "erreur": r.get("erreur", "")})
                    break
                appels = r.get("appels") or []
                if not appels:
                    texte = (r.get("texte") or "").strip()
                    if not texte and etape > 0 and not vide_rejoue:       # des outils, puis rien : on demande de conclure
                        vide_rejoue = True
                        crees.append(stocker(cid, "user", "(Conclus maintenant en clair : ce qui a été fait, l'état final, ce qui reste.)", tour=tour))
                        continue
                    if texte:
                        v = G.relire(texte, agent, compte, cid, tour)           # le Relecteur relit AVANT que la réponse parte
                        if v["verdict"] == "retenue":
                            crees.append(stocker(cid, "panne", "⚠️ Réponse retenue par le Relecteur (%s) : elle n'est pas partie." % ", ".join(v["motifs"]), tour=tour))
                            actions.append({"statut": "retenue", "relecteur": v["motifs"]})
                            texte = ""
                        else:
                            crees.append(stocker(cid, "assistant", texte, tour=tour))
                    break
                brut = r.get("message") or {"role": "assistant", "content": r.get("texte") or None, "tool_calls": [
                    {"id": a["id"], "type": "function", "function": {"name": a["nom"], "arguments": json.dumps(a["arguments"], ensure_ascii=False)}} for a in appels]}
                crees.append(stocker(cid, "assistant", r.get("texte") or "", appels=brut.get("tool_calls"), tour=tour))      # l'assistant d'abord : l'API l'impose
                for a in appels:
                    try:
                        contenu, action = executer_appel(a, index, par_cle, tous, etat, agent, compte)
                    except Exception as e:                                  # une erreur d'outil se dit au modèle, elle ne fait pas tomber le tour
                        contenu, action = "Erreur de l'outil : %s" % str(e)[:300], {"cle": a["nom"], "statut": "erreur"}
                    crees.append(stocker(cid, "tool", contenu, tool_call_id=a["id"], nom=a["nom"], statut=(action or {}).get("statut", ""), tour=tour))
                    if action:
                        actions.append(action)
            else:
                crees.append(stocker(cid, "panne", "⚠️ Trop d'étapes d'outils dans ce tour : arrêté (%s au plus)." % max_tours, tour=tour))
            if texte:
                try:
                    ctx.agir("memoire.apres_echange", {"session_id": "conv-%d" % cid, "question": message, "reponse": texte, "actes": etat["ecritures"],
                                                       "commandes": "; ".join(a["cle"] for a in actions if a.get("cle") and a.get("risque") != "lecture")}, acteur=agent)
                except Exception:
                    pass
            ctx.emettre("conversation.tour", objet=("conversation", str(cid)), donnees={"id": cid, "agent": agent, "actions": len(actions)})
        finally:
            db.ecrire("UPDATE conversations SET en_cours=NULL, maj=? WHERE id=?", (time.time(), cid))
        return {"conversation_id": cid, "compte": compte, "agent": agent, "texte": texte, "actions": actions, "messages": crees, "teinte": etat["teinte"]}

    def prouver_tour(c, res):
        return bool(db.lire("SELECT 1 FROM conversations WHERE id=?", (res["conversation_id"],)))

    def defaire_tour(c, res):
        """Retire les messages que ce tour a gardés. Les actions de l'agent ont chacune leur retour (leur journal le dit) : elles ne sont pas défaites ici."""
        for m in res["messages"]:
            db.ecrire("DELETE FROM messages WHERE id=?", (m,))

    # ------------------------------------------------------------------ inscription
    c = ctx
    for cid, f in (("conversations", conversations), ("conversation", conversation), ("outils", outils)):
        c.implementer(cid, f)
    c.implementer("conversation_creer", conversation_creer, prouver_creee, defaire_creee, simuler=lambda x, agent="cassandra", **_: "ouvrirait une conversation avec %s" % agent)
    c.implementer("conversation_renommer", conversation_renommer, prouver_renomme, defaire_renomme, simuler=lambda x, id="", titre="", **_: "renommerait la conversation %s en « %s »" % (id, titre))
    c.implementer("conversation_supprimer", conversation_supprimer, prouver_supprimee, defaire_supprimee, simuler=lambda x, id="", **_: "supprimerait la conversation %s et ses messages" % id)
    c.implementer("arreter", arreter, prouver_arret, defaire_arret, simuler=lambda x, id="", **_: "demanderait l'arrêt du tour de la conversation %s" % id)
    c.implementer("converser", converser, prouver_tour, defaire_tour, simuler=lambda x, **_: "ferait répondre l'agent")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
