# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les messages en cours et programmés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : messages
# ZONE       : CN
# VERSION CN : 0.1.0  #11e12a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les messages en cours et programmés : rédiger, enregistrer, envoyer à la main, programmer un départ.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=11e12a ▼▼▼
"""Les messages en cours et programmés.

Porté de la V18 (`message_*`, `itare_drafts`), avec ses leçons :
  - un message rédigé à partir d'un contenu extérieur (sa « teinte ») ne part JAMAIS seul : ni programmation, ni minuterie, seulement la main ;
  - la programmation fait partir le message sans que la page soit ouverte, mais ce qui part est ce que la personne a enregistré : le courrier ne reçoit qu'un numéro ;
  - un envoi en échec retire la programmation et laisse le message intact, en le disant dans la cloche.

L'envoi à la main passe par `courrier.envoyer` (réservé à un humain), appelé par l'écran avec l'adresse ENREGISTRÉE dans le message ; l'issue est déclarée ensuite (`sortie`).
Le départ programmé passe par `courrier.envoyer_programme`, qui ne reçoit qu'un numéro de message et relit ici (`envoi_a_poster`) ce qui doit partir.
"""
import json
import re
import time
from datetime import datetime

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ETATS = ("brouillon", "programme", "envoi", "envoye", "echec")
MAX_ADRESSES = 20


def _adresses(texte):
    return [a.strip() for a in re.split(r"[,;]", str(texte or "")) if a.strip()]


def brancher(ctx):
    db = ctx.stockage

    def compte_agit():
        c = (ctx.compte or "").strip().lower()
        if not c or c in ("noyau", "cassandra", "itare", "operateur"):
            raise ValueError("un message est celui d'une personne : aucun compte n'agit")
        return c

    def brut(mid, compte):
        r = db.lire("SELECT * FROM messages WHERE id=? AND compte=?", (int(mid or 0), compte))
        if not r:
            raise ValueError("message introuvable")
        return dict(r[0])

    def manque(d):
        out = []
        if not _adresses(d["a"]):
            out.append("un destinataire")
        elif not all(EMAIL.match(a) for a in _adresses(d["a"] + "," + d["cc"])):
            out.append("une adresse valide")
        if not str(d["objet"]).strip():
            out.append("un objet")
        if not str(d["corps"]).strip():
            out.append("un texte")
        return out

    def public(d):
        d = dict(d)
        d["pieces"] = json.loads(d["pieces"] or "[]")
        d["liens"] = json.loads(d["liens"] or "[]")
        d["manque"] = manque(d)
        d["extrait"] = str(d["corps"]).strip()[:180]
        d["to_addr"], d["subject"], d["body"] = d["a"], d["objet"], d["corps"]
        d["part_a"] = datetime.fromtimestamp(d["quand"]).strftime("%Y-%m-%d %H:%M:%S") if d.get("quand") else ""
        d["updated_at"] = datetime.fromtimestamp(d["maj"]).strftime("%Y-%m-%d %H:%M:%S")
        return d

    # ------------------------------------------------------------------ lectures
    def liste(c, limite=60):
        compte = compte_agit()
        prets, finir = [], []
        for r in db.lire("SELECT * FROM messages WHERE compte=? AND etat IN ('brouillon','programme','envoi','echec') ORDER BY maj DESC LIMIT ?", (compte, max(1, min(int(limite or 60), 200)))):
            d = public(r)
            (finir if d["manque"] else prets).append(d)
        return {"prets": prets, "a_finir": finir, "total": len(prets) + len(finir)}

    def voir(c, id=0):
        return public(brut(id, compte_agit()))

    def destinataires(c, q="", limite=8):
        """Les correspondants qu'on peut proposer à la personne qui écrit : son carnet, ses propres adresses (c'est elle qui les voit, jamais un modèle)."""
        ref = str(q or "").strip()
        if not ref:
            return {"contacts": []}
        r = ctx.executer_lecture("contacts.adresses_pour_mandat", reference=ref) or {}          # la lecture que le carnet réserve à la résolution d'un destinataire : un modèle, lui, ne reçoit jamais les adresses
        out = []
        for f in (r.get("fiches") or []):
            adrs = [a for a in (f.get("emails") or []) if EMAIL.match(str(a or ""))]
            if adrs:
                out.append({"nom": f.get("display_name") or adrs[0], "addr": adrs[0], "societe": f.get("company") or "", "id": f.get("id"), "dernier": ""})
            if len(out) >= int(limite or 8):
                break
        return {"contacts": out}

    def envoi_a_poster(c, message=0):
        """Pour le courrier seulement : le message tel qu'il doit partir (rien d'autre n'est posté)."""
        r = db.lire("SELECT * FROM messages WHERE id=? AND etat='envoi'", (int(message or 0),))
        if not r:
            return None
        d = r[0]
        return {"a": d["a"], "cc": d["cc"], "objet": d["objet"], "corps": d["corps"], "repond_a_message": d["reponse_a"], "references": d["references_fil"], "pieces": json.loads(d["pieces"] or "[]")}

    # ------------------------------------------------------------------ écritures réversibles
    def save(c, id=None, to="", cc="", cci="", subject="", body="", pieces=None, liens=None, suivi_jours=0, in_reply_to="", reply_refs="", teinte="", **_):
        compte = compte_agit()
        avant = brut(id, compte) if id else None
        if avant and avant["etat"] not in ("brouillon", "programme", "echec"):
            raise ValueError("ce message est parti ou en train de partir")
        champs = {"a": str(to or "")[:400], "cc": str(cc or "")[:400], "cci": str(cci or "")[:400], "objet": str(subject or "")[:400], "corps": str(body or "")[:60000],
                  "pieces": json.dumps([p for p in (pieces or [])[:6] if isinstance(p, dict)], ensure_ascii=False), "liens": json.dumps((liens or [])[:12], ensure_ascii=False),
                  "suivi_jours": max(0, min(90, int(suivi_jours or 0)))}
        if len(_adresses(champs["a"] + "," + champs["cc"])) > MAX_ADRESSES:
            raise ValueError("%d destinataires au plus" % MAX_ADRESSES)
        now = time.time()
        if avant:
            # modifier un message programmé retire sa programmation : ce qui part est ce qu'on a relu
            sets = dict(champs, maj=now, etat="brouillon", quand=None, erreur="")
            db.ecrire("UPDATE messages SET %s WHERE id=?" % ",".join("%s=?" % k for k in sets), list(sets.values()) + [avant["id"]])
            mid = avant["id"]
        else:
            mid = db.ecrire("INSERT INTO messages(compte, a, cc, cci, objet, corps, pieces, liens, suivi_jours, reponse_a, references_fil, teinte, cree, maj) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (compte, champs["a"], champs["cc"], champs["cci"], champs["objet"], champs["corps"], champs["pieces"], champs["liens"], champs["suivi_jours"],
                             str(in_reply_to or "")[:300], str(reply_refs or "")[:300], str(teinte or "")[:80], now, now))
        return {"id": mid, "compte": compte, "avant": avant, "manque": manque(dict(champs))}

    def prouver_save(c, res):
        r = db.lire("SELECT compte FROM messages WHERE id=?", (res["id"],))
        return bool(r) and r[0]["compte"] == res["compte"]

    def defaire_save(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM messages WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            cols = [k for k in a if k != "id"]
            db.ecrire("UPDATE messages SET %s WHERE id=?" % ",".join("%s=?" % k for k in cols), [a[k] for k in cols] + [a["id"]])

    def supprimer(c, id=0):
        compte = compte_agit()
        d = brut(id, compte)
        if d["etat"] == "envoi":
            raise ValueError("ce message est en train de partir")
        db.ecrire("DELETE FROM messages WHERE id=?", (d["id"],))
        return {"id": d["id"], "compte": compte, "avant": d}

    def prouver_supprime(c, res):
        return not db.lire("SELECT 1 FROM messages WHERE id=?", (res["id"],))

    def defaire_supprime(c, res):
        a = res["avant"]
        cols = list(a)
        db.ecrire("INSERT INTO messages(%s) VALUES(%s)" % (",".join(cols), ",".join("?" * len(cols))), [a[k] for k in cols])

    def programmer(c, id=0, quand=""):
        """Un départ différé : le message part seul à l'heure dite, sans que la page soit ouverte. Une heure vide retire la programmation."""
        compte = compte_agit()
        d = brut(id, compte)
        if d["etat"] not in ("brouillon", "programme", "echec"):
            raise ValueError("ce message est parti ou en train de partir")
        if not str(quand or "").strip():
            ts, etat = None, "brouillon"
        else:
            if not re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", str(quand)):
                raise ValueError("date attendue : AAAA-MM-JJ HH:MM")
            try:
                ts = time.mktime(time.strptime(str(quand).replace("T", " ")[:16], "%Y-%m-%d %H:%M"))
            except ValueError:
                raise ValueError("date illisible")
            if d["teinte"]:
                raise ValueError("ce message a été rédigé à partir d'un courrier reçu (%s) : il ne part pas seul, envoyez-le à la main" % d["teinte"][:40])
            m = manque(d)
            if m:
                raise ValueError("il manque %s" % " et ".join(m))
            etat = "programme"
        db.ecrire("UPDATE messages SET etat=?, quand=?, maj=?, erreur='' WHERE id=?", (etat, ts, time.time(), d["id"]))
        return {"id": d["id"], "compte": compte, "avant": {"etat": d["etat"], "quand": d["quand"], "erreur": d["erreur"]}, "etat": etat, "quand": ts}

    def prouver_programme(c, res):
        r = db.lire("SELECT etat, quand FROM messages WHERE id=?", (res["id"],))
        return bool(r) and r[0]["etat"] == res["etat"] and r[0]["quand"] == res["quand"]

    def defaire_programme(c, res):
        a = res["avant"]
        db.ecrire("UPDATE messages SET etat=?, quand=?, erreur=? WHERE id=?", (a["etat"], a["quand"], a["erreur"], res["id"]))

    def preparer_envoi(c, id=0):
        """Mettre un message en partance (la personne a relu et confirmé) : le courrier le postera sur son numéro."""
        compte = compte_agit()
        d = brut(id, compte)
        if d["etat"] not in ("brouillon", "programme", "echec"):
            raise ValueError("ce message est parti ou en train de partir")
        m = manque(d)
        if m:
            raise ValueError("il manque %s" % " et ".join(m))
        db.ecrire("UPDATE messages SET etat='envoi', maj=? WHERE id=?", (time.time(), d["id"]))
        return {"id": d["id"], "compte": compte, "avant": {"etat": d["etat"], "quand": d["quand"], "erreur": d["erreur"], "message_id": d["message_id"], "envoye_le": d["envoye_le"]}, "etat": "envoi"}

    def sortie(c, id=0, message_id="", erreur=""):
        """Déclarer l'issue d'un envoi fait à la main : parti (avec son Message-ID) ou échoué (avec la raison)."""
        compte = compte_agit()
        d = brut(id, compte)
        if erreur:
            db.ecrire("UPDATE messages SET etat='echec', erreur=?, maj=? WHERE id=?", (str(erreur)[:300], time.time(), d["id"]))
        else:
            db.ecrire("UPDATE messages SET etat='envoye', message_id=?, envoye_le=?, maj=?, quand=NULL, erreur='' WHERE id=?", (str(message_id or "")[:300], time.time(), time.time(), d["id"]))
        return {"id": d["id"], "compte": compte, "avant": {"etat": d["etat"], "quand": d["quand"], "erreur": d["erreur"], "message_id": d["message_id"], "envoye_le": d["envoye_le"]},
                "etat": "echec" if erreur else "envoye"}

    def prouver_sortie(c, res):
        r = db.lire("SELECT etat FROM messages WHERE id=?", (res["id"],))
        return bool(r) and r[0]["etat"] == res["etat"]

    def defaire_sortie(c, res):
        a = res["avant"]
        db.ecrire("UPDATE messages SET etat=?, quand=?, erreur=?, message_id=?, envoye_le=? WHERE id=?", (a["etat"], a["quand"], a["erreur"], a["message_id"], a["envoye_le"], res["id"]))

    # ------------------------------------------------------------------ la minuterie
    def minuterie(cx):
        """Fait partir les messages programmés dont l'heure est venue. Un échec retire la programmation et laisse le message intact."""
        db.ecrire("UPDATE messages SET etat='echec', erreur='envoi interrompu avant son issue', quand=NULL WHERE etat='envoi' AND maj < ?", (time.time() - 600,))
        for d in db.lire("SELECT * FROM messages WHERE etat='programme' AND quand IS NOT NULL AND quand<=? ORDER BY quand LIMIT 10", (time.time(),)):
            db.ecrire("UPDATE messages SET etat='envoi', maj=? WHERE id=? AND etat='programme'", (time.time(), d["id"]))
            if not db.lire("SELECT 1 FROM messages WHERE id=? AND etat='envoi'", (d["id"],)):
                continue
            # la personne qui a écrit : son serveur d'envoi, ses droits (même procédé que les mandats)
            avant = (ctx._compte.valeur, ctx._societe.valeur)
            ctx._compte.valeur, ctx._societe.valeur = d["compte"], ctx.societe_de(d["compte"])
            try:
                r = ctx.agir("courrier.envoyer_programme", {"message": d["id"]}, acteur="cassandra") or {}
                st = r.get("statut")
                if st in ("racontee", "simulee"):
                    raise ValueError("le courrier ne part pas seul (palier de courrier.envoyer_programme) : envoyez ce message à la main")
                if st != "faite":
                    raise ValueError(str(r.get("erreur") or r.get("raison") or r.get("motif") or st or "envoi impossible"))
                mid = (r.get("resultat") or {}).get("message_id", "")
                db.ecrire("UPDATE messages SET etat='envoye', message_id=?, envoye_le=?, maj=?, quand=NULL, erreur='' WHERE id=?", (str(mid)[:300], time.time(), time.time(), d["id"]))
            except Exception as ex:
                db.ecrire("UPDATE messages SET etat='echec', quand=NULL, erreur=?, maj=? WHERE id=?", (str(ex)[:300], time.time(), d["id"]))
                try:
                    ctx.agir("notifications.emettre", {"titre": "Envoi programmé en échec", "corps": "%s — la programmation est retirée, le message reste intact." % str(ex)[:200], "source": "courrier",
                                                       "niveau": "avoir", "sujet": "message:%s" % d["id"], "cle": "courrier:programme:%s" % d["id"], "dest": [d["compte"]]}, acteur="cassandra")
                except Exception:
                    pass
            finally:
                ctx._compte.valeur, ctx._societe.valeur = avant

    ctx.moteur("minuterie", minuterie)
    for cid, f in (("liste", liste), ("voir", voir), ("destinataires", destinataires), ("envoi_a_poster", envoi_a_poster)):
        ctx.implementer(cid, f)
    ctx.implementer("save", save, prouver_save, defaire_save, simuler=lambda x, subject="", **_: "enregistrerait le message « %s »" % subject)
    ctx.implementer("supprimer", supprimer, prouver_supprime, defaire_supprime, simuler=lambda x, id="", **_: "supprimerait le message %s" % id)
    ctx.implementer("programmer", programmer, prouver_programme, defaire_programme, simuler=lambda x, id="", quand="", **_: "programmerait le message %s pour %s" % (id, quand))
    ctx.implementer("preparer_envoi", preparer_envoi, prouver_sortie, defaire_sortie, simuler=lambda x, id="", **_: "mettrait le message %s en partance" % id)
    ctx.implementer("sortie", sortie, prouver_sortie, defaire_sortie)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
