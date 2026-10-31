# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les propositions des agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.4.0  #aa0035
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les propositions des agents : « À valider » (accepter exécute, refuser se mémorise, reporter), la carte de confiance et « Pourquoi ? ».
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=aa0035 ▼▼▼
"""Les propositions des agents.

Une proposition est ce qu'un agent veut faire et ne fait pas seul : un geste raconté (palier ou niveau), retenu pour accord (« demander »), ou retenu parce qu'il sort de la maison
juste après une lecture du dehors. L'utilisateur accepte (la capacité visée est EXÉCUTÉE par l'exécuteur, comme n'importe quel acte : droits du compte, palier, preuve, retour, journal),
refuse (le refus est gardé : l'agent ne repropose pas, et la mémoire le sait) ou reporte.

Règles tenues ici :
  - cloisonnement : une proposition d'Itare n'est lisible que de son compte, jamais de l'administrateur ; celles des agents d'instance, de l'administrateur seulement ;
  - un envoi (capacité « sortante ») ne part qu'avec un MANDAT du module des mandats : l'adresse ne vient jamais de la demande ; sans mandat valable, la proposition est bloquée ;
  - un argument secret est MASQUÉ dès l'enregistrement : une proposition qui en porte un n'est jamais exécutable (elle se fait à la main) ;
  - la carte de confiance PROPOSE « auto » après 8 validations de suite sans refus, jamais seule ; un outil neuf reste 7 jours à l'essai ; le recul de palier après deux échecs est la règle du noyau ;
  - « Pourquoi ? » ne copie rien : il garde des RÉFÉRENCES (événement du journal, conversation, souvenirs [M:id]) et les relit à la demande, pour le compte qui demande seulement.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from types import SimpleNamespace

from . import CN_equipe as eq

SEUIL_AUTO = 8                       # validations de suite, sans refus, avant de PROPOSER « auto »
ESSAI_JOURS = 7                      # un outil neuf reste raconté ce temps-là
VALIDITE_JOURS = 14                  # une proposition laissée sans réponse devient périmée
OUBLI_REFUS_JOURS = 30               # un refus n'empêche plus de reproposer après ce délai
HEURE_DEFAUT = 9
RISQUES_AUTO = ("faible", "moyen")
CLE_SECRETE = re.compile(r"(?:^|_)(?:mot_de_passe|passwd|password|passe|mdp|jeton|token|secret|cle_secrete|cle_privee|cle_api|api_key|apikey|credential)s?(?:$|_)|^key$", re.I)
CLE_ADRESSE = ("a", "to", "cc", "bcc", "destinataire", "destinataires", "adresse", "email", "mail")
REF_SOUVENIR = re.compile(r"\[M:(\d+)\]")


def masquer(args) -> tuple:
    """Une copie des arguments où les valeurs secrètes sont remplacées par « *** » ; rend (copie, il_y_avait_un_secret)."""
    secret, copie = False, {}
    for k, v in (args or {}).items():
        if CLE_SECRETE.search(str(k)):
            copie[k], secret = "***", True
        else:
            copie[k] = v
    return copie, secret


def empreinte_demande(agent: str, compte: str, capacite: str, args: dict) -> str:
    return hashlib.sha256(json.dumps([agent, compte, capacite, args], sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:24]


def serie_de_validations(decisions: list) -> tuple:
    """`decisions` : les états décidés, du plus récent au plus ancien ('acceptee' | 'refusee'). Rend (validations de suite sans refus, refus au total)."""
    suite = 0
    for etat in decisions:
        if etat != "acceptee":
            break
        suite += 1
    return suite, sum(1 for e in decisions if e == "refusee")


def en_essai(vu_le: float, maintenant: float) -> bool:
    return maintenant - float(vu_le) < ESSAI_JOURS * 86400


def propose_auto(validations: int, refus_recent: bool, essai: bool) -> bool:
    return validations >= SEUIL_AUTO and not essai and not refus_recent


def brancher_propositions(ctx, E, o, lecture, reglage):
    db = ctx.stockage
    def now():
        return eq.maintenant()

    def compte_agit():
        c = ctx.compte
        if not c or c in eq.SYSTEME:
            raise ValueError("les propositions sont celles d'un compte : aucun compte n'agit")
        return c

    def acteur_de(agent):
        return agent if agent in ("cassandra", "itare") else "agent"

    def portee_de(agent):
        d = E.definitions().get(agent)
        return d["portee"] if d else "instance"

    # ------------------------------------------------------------------ visibilité
    def visible(p, compte):
        if portee_de(p["agent"]) == "compte":
            return p["compte"] == compte                       # le bureau d'un compte : à lui seul, administrateur compris
        return E.admin(compte)                                 # un agent d'instance : à l'administrateur seulement

    def publique(p):
        d = E.definitions().get(p["agent"]) or {}
        return {"id": p["id"], "agent": p["agent"], "nom": d.get("nom", p["agent"]), "capacite": p["capacite"], "args": json.loads(p["args"] or "{}"), "titre": p["titre"], "resume": p["resume"],
                "risque": p["risque"], "pourquoi": p["pourquoi"], "impact": p["impact"], "origine": p["origine"], "etat": p["etat"], "cree": p["cree"], "decidee": p["decidee"], "par": p["par"],
                "reporte_jusqua": p["reporte_jusqua"], "conversation_id": p["conversation_id"], "mandat": json.loads(p["mandat"] or "{}"), "blocage": p["blocage"],
                "executable": not p["blocage"], "resultat": p["resultat"], "acte": p["acte"]}

    def perimer():
        limite = now() - VALIDITE_JOURS * 86400
        db.ecrire("UPDATE propositions SET etat='perimee' WHERE etat IN ('attend','reportee') AND cree<?", (limite,))

    def exiger(pid, compte):
        try:
            r = db.lire("SELECT * FROM propositions WHERE id=?", (int(pid),))
        except (TypeError, ValueError):
            r = []
        if not r or not visible(r[0], compte):
            raise ValueError("proposition introuvable")
        return r[0]

    # ------------------------------------------------------------------ le mandat des envois
    def mandat_de(args):
        """Le mandat désigné par la proposition : (id, fiche) ou (0, motif du blocage). L'adresse ne vient jamais de la demande : c'est le mandat qui désigne le destinataire."""
        adresses = [k for k, v in (args or {}).items() if str(k).lower() in CLE_ADRESSE and "@" in str(v)]
        if adresses:
            return 0, {}, "une adresse tirée de la demande (%s) : le destinataire vient du mandat, jamais de la demande" % ", ".join(adresses)
        try:
            mid = int((args or {}).get("mandat_id") or (args or {}).get("mandat") or 0)
        except (TypeError, ValueError):
            mid = 0
        if not mid:
            return 0, {}, "aucun mandat : un envoi ne part qu'avec un mandat qui le permet"
        lu = lecture("mandats.mandats")
        if lu is None:
            return 0, {}, "le module des mandats est absent : aucun envoi ne peut partir"
        m = next((x for x in lu.get("mandats", []) if x["id"] == mid), None)
        if m is None:
            return 0, {}, "le mandat %d n'existe pas" % mid
        if not m.get("actif") or m.get("suspendu"):
            return 0, {}, "le mandat « %s » est suspendu ou inactif" % m.get("nom", mid)
        fiche = {"id": m["id"], "nom": m["nom"], "a": (m.get("dst_source") or "") + ((" : " + m["dst_valeur"]) if m.get("dst_valeur") else ""), "objet": m.get("objet") or "",
                 "validite": "%s–%s, %s fois par jour au plus" % (m.get("heure_debut"), m.get("heure_fin"), m.get("quota_jour")), "controle": m.get("controle"),
                 "heure_debut": m.get("heure_debut"), "heure_fin": m.get("heure_fin")}
        return mid, fiche, ""

    def dans_la_plage(fiche):
        try:
            h = time.strftime("%H:%M", time.localtime(now()))
            return fiche.get("heure_debut", "00:00") <= h <= fiche.get("heure_fin", "23:59")
        except Exception:
            return True

    # ------------------------------------------------------------------ créer
    def proposer(agent, compte, outil, args, origine, resume="", pourquoi="", conversation_id=0, tour=0, attente=0):
        """Range ce qu'un agent veut faire et ne fait pas seul. Rend {id, etat, nouveau}. Une même demande déjà en attente, ou refusée récemment, n'est pas proposée deux fois."""
        cle = outil["cle"]
        propres, secret = masquer(args)
        emp = empreinte_demande(agent, compte, cle, propres)
        deja = db.lire("SELECT id, etat, decidee FROM propositions WHERE empreinte=? AND etat IN ('attend','reportee','refusee') ORDER BY id DESC LIMIT 1", (emp,))
        if deja and (deja[0]["etat"] != "refusee" or now() - deja[0]["decidee"] < OUBLI_REFUS_JOURS * 86400):
            return {"id": deja[0]["id"], "etat": deja[0]["etat"], "nouveau": False}
        blocage, mid, fiche = "", 0, {}
        if secret:
            blocage = "un argument est un secret : il n'est jamais gardé dans une proposition, le geste se fait à la main"
        elif outil.get("sortant"):
            mid, fiche, blocage = mandat_de(args)
        impact = "sort de la maison" if outil.get("sortant") else ("lit de l'extérieur" if outil.get("externe") else {"faible": "peu d'effet", "moyen": "effet réel, défaisable", "eleve": "engage fortement"}.get(outil.get("risque"), ""))
        pid = db.ecrire("INSERT INTO propositions(agent, compte, capacite, args, empreinte, titre, resume, risque, pourquoi, impact, origine, cree, conversation_id, tour, attente, mandat_id, mandat, blocage) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (agent, compte, cle, json.dumps(propres, ensure_ascii=False, default=str), emp, str(outil.get("description") or cle)[:200], str(resume or "")[:600], outil.get("risque") or "",
                         str(pourquoi or "")[:400], impact, origine, now(), int(conversation_id), int(tour), int(attente), mid, json.dumps(fiche, ensure_ascii=False), blocage))
        return {"id": pid, "etat": "attend", "nouveau": True}

    # ------------------------------------------------------------------ lire
    def propositions(c, etat="a_valider", agent="", limite=100):
        compte = compte_agit()
        perimer()
        limite = max(1, min(int(limite or 100), 500))
        sql, a = "SELECT * FROM propositions WHERE 1=1", []
        if etat == "a_valider":
            sql += " AND (etat='attend' OR (etat='reportee' AND reporte_jusqua<=?))"
            a.append(now())
        elif etat != "toutes":
            if etat not in ("attend", "acceptee", "refusee", "reportee", "perimee"):
                raise ValueError("etat : a_valider | toutes | attend | acceptee | refusee | reportee | perimee")
            sql += " AND etat=?"
            a.append(etat)
        if agent:
            sql += " AND agent=?"
            a.append(E.definition(agent)["id"])
        lignes = [publique(p) for p in db.lire(sql + " ORDER BY id DESC LIMIT ?", a + [limite * 3]) if visible(p, compte)][:limite]
        return {"propositions": lignes, "n": len(lignes), "compte": compte, "administrateur": E.admin(compte)}

    # ------------------------------------------------------------------ décider
    def prochaine_heure(jusqu_a):
        """Le moment du report : celui qu'on donne (AAAA-MM-JJ[ HH:MM], « demain »), sinon dans quatre heures — mais jamais avant l'heure du matin que la mémoire connaît (« pas avant 9 h »)."""
        t = now()
        if jusqu_a:
            j = str(jusqu_a).strip().lower()
            if j == "demain":
                lt = time.localtime(t + 86400)
                return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, HEURE_DEFAUT, 0, 0, 0, 0, -1))
            for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
                try:
                    cible = time.mktime(time.strptime(j, f))
                    if cible <= t:
                        raise ValueError("le report doit viser plus tard")
                    return cible
                except ValueError as e:
                    if "plus tard" in str(e):
                        raise
            raise ValueError("jusqu_a : « demain », AAAA-MM-JJ ou AAAA-MM-JJ HH:MM")
        cible = t + 4 * 3600
        lu = lecture("memoire.chercher", question="pas avant heure matin report proposition") or {}
        for s in lu.get("souvenirs", []):
            m = re.search(r"pas avant (\d{1,2}) ?h", str(s.get("valeur") or ""), re.I)
            if m and 0 <= int(m.group(1)) <= 23:
                h = int(m.group(1))
                lt = time.localtime(cible)
                jour = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 0, 0, 0, 0, -1))
                if lt.tm_hour < h:
                    cible = jour
                break
        return cible

    def retenir_le_refus(p, compte):
        """Le refus entre dans la mémoire de l'agent : il ne le reproposera pas de lui-même. Au mieux : un palier « raconter » de la mémoire n'empêche pas le refus d'être gardé ici."""
        try:
            ctx.agir("memoire.ecrire", {"categorie": "decision", "cle": "refus-" + p["capacite"], "valeur": "L'utilisateur a refusé « %s » (%s) : ne pas le reproposer sans qu'il le redemande." % (p["titre"][:120], p["capacite"]),
                                        "provenance": "dit", "nature": "constat"}, acteur=acteur_de(p["agent"]))
        except Exception:
            pass

    def executer_accord(p, compte):
        """Accepter = faire : la capacité visée passe par l'exécuteur au nom de CELUI qui accepte (ses droits), pour l'agent qui l'avait proposée."""
        acteur = acteur_de(p["agent"])
        outil = next((t for t in ctx.outils(acteur) if t["cle"] == p["capacite"]), None)
        if outil is None:
            raise ValueError("l'agent n'a plus cet outil, ou ce compte n'a plus le droit de l'utiliser")
        if outil.get("sortant"):
            mid, fiche, motif = mandat_de(dict(json.loads(p["args"] or "{}"), mandat_id=p["mandat_id"]))
            if not mid:
                raise ValueError(motif)
            if not dans_la_plage(fiche):
                raise ValueError("hors de la plage du mandat « %s » (%s)" % (fiche["nom"], fiche["validite"]))
        args = json.loads(p["args"] or "{}")
        args.pop("mandat", None)
        args.pop("mandat_id", None)
        r = ctx.agir(p["capacite"], args, acteur=acteur)
        s = r.get("statut")
        if s == "faite":
            return r
        if s == "racontee":
            raise ValueError("le palier de « %s » est « raconter » pour les agents : ton accord ne le contourne pas. Passe-le en « auto » (réglages de la capacité) ou fais le geste toi-même" % p["capacite"])
        if s in ("annulee", "annulation_impossible"):
            raise ValueError("le geste a été fait puis défait : la preuve n'y était pas (%s)" % r.get("motif", ""))
        raise ValueError(str(r.get("erreur") or r.get("raison") or "le geste a échoué"))

    def proposition_decider(c, id=0, decision="", jusqu_a=""):
        compte = compte_agit()
        decision = str(decision or "").strip().lower()
        if decision not in ("accepter", "refuser", "reporter"):
            raise ValueError("decision : accepter | refuser | reporter")
        p = exiger(id, compte)
        if p["etat"] not in ("attend", "reportee"):
            raise ValueError("cette proposition est déjà %s" % {"acceptee": "acceptée", "refusee": "refusée", "perimee": "périmée"}.get(p["etat"], p["etat"]))
        avant = {k: p[k] for k in ("etat", "decidee", "par", "reporte_jusqua", "resultat", "acte")}
        acte, resultat = 0, ""
        if decision == "accepter":
            if p["blocage"]:
                raise ValueError("proposition bloquée : %s" % p["blocage"])
            with db.transaction() as cx:                       # une seule acceptation à la fois : le second clic trouve la proposition déjà prise
                n = cx.execute("UPDATE propositions SET etat='acceptee', decidee=?, par=? WHERE id=? AND etat IN ('attend','reportee')", (now(), compte, p["id"])).rowcount
            if not n:
                raise ValueError("cette proposition vient d'être décidée")
            try:
                r = executer_accord(p, compte)
            except Exception:
                db.ecrire("UPDATE propositions SET etat=?, decidee=?, par=?, reporte_jusqua=? WHERE id=?", (avant["etat"], avant["decidee"], avant["par"], avant["reporte_jusqua"], p["id"]))
                raise
            acte = int(r.get("evenement") or 0)
            resultat = o.court(r.get("resultat") if r.get("resultat") is not None else "", 800)
            db.ecrire("UPDATE propositions SET acte=?, resultat=? WHERE id=?", (acte, resultat, p["id"]))
            if acte:
                tracer({"evenement": acte}, p["agent"], p["compte"], p["capacite"], {"cid": p["conversation_id"], "tour": p["tour"], "memoires": []}, "", "", 0, declencheur="proposition", proposition_id=p["id"])
        elif decision == "refuser":
            db.ecrire("UPDATE propositions SET etat='refusee', decidee=?, par=? WHERE id=?", (now(), compte, p["id"]))
            if p["attente"]:
                db.ecrire("UPDATE agent_attentes SET etat='refusee' WHERE id=?", (p["attente"],))
            retenir_le_refus(p, compte)
        else:
            db.ecrire("UPDATE propositions SET etat='reportee', reporte_jusqua=?, par=? WHERE id=?", (prochaine_heure(jusqu_a), compte, p["id"]))
        if decision == "accepter" and p["attente"]:
            db.ecrire("UPDATE agent_attentes SET etat='acceptee' WHERE id=?", (p["attente"],))
        apres = db.lire("SELECT * FROM propositions WHERE id=?", (p["id"],))[0]
        return {"id": p["id"], "decision": decision, "etat": apres["etat"], "acte": acte, "resultat": resultat, "reporte_jusqua": apres["reporte_jusqua"], "avant": avant, "agent": p["agent"], "capacite": p["capacite"]}

    def prouver_decision(c, res):
        r = db.lire("SELECT etat FROM propositions WHERE id=?", (res["id"],))
        return bool(r) and r[0]["etat"] == res["etat"]

    def defaire_decision(c, res):
        if res["acte"]:
            raise ValueError("le geste a été fait (acte n° %d) : il se défait par son propre retour, la proposition reste acceptée" % res["acte"])
        a = res["avant"]
        db.ecrire("UPDATE propositions SET etat=?, decidee=?, par=?, reporte_jusqua=?, resultat=?, acte=? WHERE id=?", (a["etat"], a["decidee"], a["par"], a["reporte_jusqua"], a["resultat"], a["acte"], res["id"]))

    # ------------------------------------------------------------------ la carte de confiance
    def observer_outils(agent, cle_compte, cles):
        """Le suivi de la période d'essai : un outil est « neuf » la première fois qu'on le voit pour cet agent. Un état, pas un second mécanisme."""
        if not cles:
            return
        vus = {r["outil"] for r in db.lire("SELECT outil FROM agent_outils_vus WHERE agent=? AND compte=?", (agent, cle_compte))}
        neufs = [k for k in cles if k not in vus]
        if neufs:
            with db.transaction() as cx:
                cx.executemany("INSERT OR IGNORE INTO agent_outils_vus(agent, compte, outil, vu_le) VALUES (?,?,?,?)", [(agent, cle_compte, k, now()) for k in neufs])

    def confiance(c, agent=""):
        compte = compte_agit()
        d, cle = E.cible(agent, compte)
        outils = E.outils_de(d)
        observer_outils(d["id"], cle, [t["cle"] for t in outils])
        sur = E.surcharges(d["id"], cle)
        vus = {r["outil"]: r["vu_le"] for r in db.lire("SELECT outil, vu_le FROM agent_outils_vus WHERE agent=? AND compte=?", (d["id"], cle))}
        decisions = {}
        sql, a = "SELECT capacite, etat FROM propositions WHERE agent=? AND etat IN ('acceptee','refusee')", [d["id"]]
        if d["portee"] == "compte":
            sql += " AND compte=?"
            a.append(compte)
        for r in db.lire(sql + " ORDER BY decidee DESC, id DESC", a):
            decisions.setdefault(r["capacite"], []).append(r["etat"])
        sortie, propose, en_essai_n = [], [], 0
        for t in outils:
            p = E.palier_outil(t, sur.get(t["cle"]))
            if p["palier"] != "raconter" or p["retire"] or t["risque"] not in RISQUES_AUTO:
                continue
            serie, refus = serie_de_validations(decisions.get(t["cle"], []))
            essai = en_essai(vus.get(t["cle"], now()), now())
            en_essai_n += 1 if essai else 0
            ok = propose_auto(serie, False, essai)
            if ok:
                propose.append(t["cle"])
            if serie or refus or ok:
                sortie.append({"cle": t["cle"], "risque": t["risque"], "palier": p["palier"], "validations": serie, "manque": max(0, SEUIL_AUTO - serie), "refus": refus,
                               "essai": essai, "essai_jusqua": (vus.get(t["cle"], now()) + ESSAI_JOURS * 86400) if essai else 0, "propose_auto": ok})
        sortie.sort(key=lambda x: (not x["propose_auto"], -x["validations"], x["cle"]))
        return {"agent": d["id"], "compte": compte, "seuil": SEUIL_AUTO, "essai_jours": ESSAI_JOURS, "outils": sortie, "propose_auto": propose, "en_essai": en_essai_n,
                "regle": "La carte propose « auto », jamais ne le pose : la promotion passe par palier_regler. Deux échecs de suite font reculer le palier d'une capacité : c'est la règle du noyau."}

    # ------------------------------------------------------------------ « Pourquoi ? »
    def tracer(r, agent, compte, cle, etat, palier, niveau, confirmer, declencheur="tour", proposition_id=0):
        """Garde les RÉFÉRENCES d'un acte (l'événement du journal, la conversation, les souvenirs cités) — rien du contenu."""
        ev = (r or {}).get("evenement")
        if not ev:
            return
        try:
            db.ecrire("INSERT OR REPLACE INTO agent_actes(evenement, compte, agent, capacite, conversation_id, tour, declencheur, memoires, palier, niveau, confirmer, proposition_id, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (int(ev), compte, agent, cle, int((etat or {}).get("cid") or 0), int((etat or {}).get("tour") or 0), declencheur, json.dumps((etat or {}).get("memoires") or []), palier or "", niveau or "", int(bool(confirmer)),
                       int(proposition_id), now()))
        except Exception:
            pass

    def pourquoi(c, acte=0, detail=False):
        compte = compte_agit()
        try:
            a = db.lire("SELECT * FROM agent_actes WHERE evenement=?", (int(acte),))
        except (TypeError, ValueError):
            a = []
        if not a or not (a[0]["compte"] == compte or (portee_de(a[0]["agent"]) != "compte" and E.admin(compte))):
            raise ValueError("acte introuvable")                 # l'acte d'un autre compte n'est jamais lisible, administrateur compris
        a = a[0]
        evs = {e["id"]: e for e in ctx.evenements("capacite.", 5000) if e.get("compte") in (a["compte"], "")}
        demande = evs.get(a["evenement"])
        directs = sorted((e for e in evs.values() if e.get("cause") == a["evenement"]), key=lambda e: e["id"])
        issue, preuve, retour, journal = "inconnue", None, None, []
        if demande:
            journal.append({"id": demande["id"], "type": demande["type"], "ts": demande["ts"]})
        for e in directs:
            journal.append({"id": e["id"], "type": e["type"], "ts": e["ts"]})
            issue = {"capacite.faite": "faite", "capacite.racontee": "racontee", "capacite.simulee": "simulee", "capacite.echouee": "echec"}.get(e["type"], issue)
            for s in (x for x in evs.values() if x.get("cause") == e["id"]):
                journal.append({"id": s["id"], "type": s["type"], "ts": s["ts"]})
                if s["type"] == "capacite.prouvee":
                    preuve = True
                elif s["type"] in ("capacite.annulee", "capacite.annulation_impossible"):
                    preuve, retour = False, "annulee" if s["type"] == "capacite.annulee" else "annulation_impossible"
        decl = {"type": a["declencheur"]}
        if a["declencheur"] == "proposition":
            pr = db.lire("SELECT id, titre, par, decidee FROM propositions WHERE id=?", (a["proposition_id"],))
            decl.update({"proposition": a["proposition_id"], "accepte_par": pr[0]["par"] if pr else "", "quand": pr[0]["decidee"] if pr else 0})
        else:
            m = db.lire("SELECT id, contenu FROM messages WHERE conversation_id=? AND tour=? AND role='user' ORDER BY id LIMIT 1", (a["conversation_id"], a["tour"])) if a["conversation_id"] else []
            decl.update({"conversation": a["conversation_id"], "tour": a["tour"], "message": m[0]["id"] if m else 0, "extrait": (m[0]["contenu"][:200] if m else "")})
        refs = json.loads(a["memoires"] or "[]")
        res = {"acte": a["evenement"], "agent": a["agent"], "capacite": a["capacite"], "quand": demande["ts"] if demande else a["ts"], "declencheur": decl,
               "memoire": [{"ref": "M:%d" % i} for i in refs], "outil": {"cle": a["capacite"]}, "palier": a["palier"], "niveau": a["niveau"], "confirmer": bool(a["confirmer"]),
               "issue": issue, "preuve": preuve, "retour": retour, "journal": journal, "arguments": (demande or {}).get("donnees", {}).get("args")}
        if detail:                                               # les souvenirs se lisent à la demande, par le module de la mémoire (qui garde son propre cloisonnement)
            for m in res["memoire"]:
                s = (lecture("memoire.lire", id=int(m["ref"][2:])) or {}).get("souvenir")
                if s:
                    m.update({"cle": s.get("cle"), "valeur": str(s.get("valeur") or "")[:300], "statut": s.get("statut")})
        return res

    c = ctx
    c.implementer("propositions", propositions)
    c.implementer("proposition_decider", proposition_decider, prouver_decision, defaire_decision,
                  simuler=lambda x, id="", decision="", **_: "%s la proposition %s" % ({"accepter": "accepterait (et ferait)", "refuser": "refuserait", "reporter": "reporterait"}.get(decision, "déciderait"), id))
    c.implementer("confiance", confiance)
    c.implementer("pourquoi", pourquoi)
    return SimpleNamespace(proposer=proposer, tracer=tracer, observer_outils=observer_outils, perimer=perimer)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : masquer, empreinte_demande, serie_de_validations, en_essai, propose_auto, brancher_propositions
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
