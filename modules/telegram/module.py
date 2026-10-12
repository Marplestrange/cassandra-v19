"""Le robot Telegram d'un compte.

Porté de la V18 (`tg_*`), avec ses leçons :
  - le robot ne sert qu'à PRÉVENIR : il porte les notifications du compte vers son téléphone, et ne lit rien de ce qu'on lui écrit (rien n'est exécuté ni lu
    par un modèle). Itare, elle, a son propre compte Telegram : c'est là qu'on lui parle ;
  - le webhook est public par NÉCESSITÉ (c'est Telegram qui appelle) : il ne se protège que par le secret renvoyé en en-tête, qui SEUL désigne le compte.
    Le contenu de l'appel ne choisit jamais un destinataire : sinon n'importe qui écrirait chez n'importe qui. Un secret inconnu reçoit un 200 muet
    (un refus dirait que le chemin existe) ;
  - le destinataire est une DÉCISION, pas une déduction : celui que la personne a déclaré (et qu'on a essayé pour de bon auprès de Telegram) l'emporte
    sur celui appris du premier message ; un @pseudo est refusé, un robot ne sait pas en faire une conversation ;
  - un identifiant « accepté » sans essai est le pire cas : l'écran dit « enregistré » et les alertes tombent dans le vide pendant des semaines ;
  - le mot du rôle n'est dit qu'une fois par heure et par compte (répéter à chaque message ferait boucler deux automates) ;
  - un échec d'envoi est un RÉSULTAT ({ok: false}), jamais une exception : l'apprentissage des paliers compte les échecs d'une capacité, et le refus d'un seul
    robot ne doit pas faire redescendre l'envoi de tous les comptes ;
  - le jeton ne sort jamais (ni de l'état, ni du journal, ni d'un message d'erreur).
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import urllib.error
import urllib.request

RE_JETON = re.compile(r"^\d{3,}:[A-Za-z0-9_\-]{20,}$")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
DIT_TTL_S = 3600
DITS = {}                       # compte -> quand on lui a dit à quoi sert le robot (en mémoire : au redémarrage, on peut le redire une fois)
TAILLE_MAX = 4000


def empreinte(secret):
    return hashlib.sha256(str(secret or "").encode()).hexdigest()


def requete(api, jeton, methode, corps, timeout=10):
    """Un appel à l'API Telegram. Ne lève jamais : rend un dict. Le jeton n'apparaît dans aucun message."""
    if not jeton:
        return {"ok": False, "error": "aucun robot configuré"}
    url = "%s/bot%s/%s" % (api.rstrip("/"), jeton, methode)
    req = urllib.request.Request(url, data=json.dumps(corps or {}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as ex:
        try:
            return json.loads(ex.read().decode("utf-8", "replace"))
        except Exception:
            return {"ok": False, "error": "HTTP %s" % ex.code}
    except Exception as ex:
        return {"ok": False, "error": str(ex).replace(jeton, "***")[:160]}


def raison(r):
    return str(r.get("description") or r.get("error") or "")[:140]


def brancher(ctx):
    db = ctx.stockage

    def api():
        return str(ctx.reglage("api", "") or "https://api.telegram.org")

    def appel(jeton, methode, corps=None, timeout=10):
        return requete(api(), jeton, methode, corps, timeout)

    def compte_qui_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("un robot est celui d'un compte : aucun compte n'agit")
        return c

    def lien(compte):
        r = db.lire("SELECT * FROM liens WHERE compte=?", (compte,))
        return r[0] if r else None

    def webhook_url():
        base = str(ctx.reglage("url_publique", "") or "").strip().rstrip("/")
        if not base.startswith("https://"):
            raise ValueError("Telegram exige une adresse publique en https (réglage telegram.url_publique)")
        return base + "/api/public/telegram.recevoir"

    def poser_lien(compte, jeton, conserver=None):
        """Vérifie le jeton, tire un secret, pose le webhook, écrit le lien. Rend le nom du robot."""
        if not RE_JETON.match(jeton):
            raise ValueError("jeton de robot invalide (format 123456:ABC…)")
        url = webhook_url()
        me = appel(jeton, "getMe")
        if not me.get("ok"):
            raise ValueError("Telegram refuse ce jeton : %s" % raison(me))
        nom = str((me.get("result") or {}).get("username") or "").strip()
        secret = secrets.token_urlsafe(32)
        r = appel(jeton, "setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"], "drop_pending_updates": True})
        if not r.get("ok"):
            raise ValueError("webhook refusé : %s" % raison(r))
        conserver = conserver or {}
        db.ecrire("INSERT INTO liens(compte, jeton, nom_robot, secret_empreinte, chat_id, cible, actif, cree) VALUES (?,?,?,?,?,?,1,?) "
                  "ON CONFLICT(compte) DO UPDATE SET jeton=excluded.jeton, nom_robot=excluded.nom_robot, secret_empreinte=excluded.secret_empreinte, actif=1",
                  (compte, jeton, nom, empreinte(secret), conserver.get("chat_id", ""), conserver.get("cible", ""), conserver.get("cree") or time.time()))
        return nom

    def destinataire(l):
        return (l["cible"] or l["chat_id"]) if l else ""

    # ------------------------------------------------------------------ lectures
    def etat(c):
        compte = compte_qui_agit()
        l = lien(compte)
        n = db.lire("SELECT COUNT(*) n FROM messages WHERE compte=?", (compte,))[0]["n"]
        return {"robot": bool(l), "nom_robot": l["nom_robot"] if l else "", "actif": bool(l and l["actif"]), "chat_id": l["chat_id"] if l else "", "cible": l["cible"] if l else "",
                "destinataire": destinataire(l), "origine": "declare" if l and l["cible"] else ("appris" if l and l["chat_id"] else ""),
                "depuis": l["cree"] if l else None, "dernier": l["dernier"] if l else None, "messages": n,
                "webhook": str(ctx.reglage("url_publique", "") or "").rstrip("/") + "/api/public/telegram.recevoir" if ctx.reglage("url_publique", "") else ""}

    def fil(c, limite=100):
        compte = compte_qui_agit()
        lim = max(1, min(int(limite or 100), 500))
        rows = db.lire("SELECT id, ts, sens, corps, expediteur FROM messages WHERE compte=? ORDER BY id DESC LIMIT ?", (compte, lim))
        return {"messages": list(reversed(rows))}

    # ------------------------------------------------------------------ brancher / débrancher
    def brancher_robot(c, jeton=""):
        compte = compte_qui_agit()
        jeton = str(jeton or "").strip()
        avant = lien(compte)
        nom = poser_lien(compte, jeton, conserver=avant)
        c.poser("telegram", compte, "Robot Telegram de %s" % compte, etat="branche", donnees={"robot": nom})
        c.emettre("telegram.branche", objet=("telegram", compte), donnees={"compte": compte, "robot": nom})
        return {"compte": compte, "robot": nom, "existait": bool(avant), "jeton_avant": avant["jeton"] if avant else "", "robot_avant": avant["nom_robot"] if avant else "",
                "chat_id_avant": avant["chat_id"] if avant else "", "cible_avant": avant["cible"] if avant else "", "cree_avant": avant["cree"] if avant else None}

    def prouver_brancher(c, res):
        l = lien(res["compte"])
        if not l:
            return False
        info = appel(l["jeton"], "getWebhookInfo")
        return bool(info.get("ok")) and str((info.get("result") or {}).get("url") or "") == webhook_url()

    def defaire_brancher(c, res):
        l = lien(res["compte"])
        if l:
            appel(l["jeton"], "deleteWebhook", {"drop_pending_updates": True})
        if res.get("existait") and res.get("jeton_avant"):
            poser_lien(res["compte"], res["jeton_avant"], conserver={"chat_id": res["chat_id_avant"], "cible": res["cible_avant"], "cree": res["cree_avant"]})
        else:
            db.ecrire("DELETE FROM liens WHERE compte=?", (res["compte"],))
        c.retirer("telegram", res["compte"])

    def detacher(c):
        compte = compte_qui_agit()
        l = lien(compte)
        if not l:
            raise ValueError("aucun robot lié à ce compte")
        appel(l["jeton"], "deleteWebhook", {"drop_pending_updates": True})
        db.ecrire("DELETE FROM liens WHERE compte=?", (compte,))
        c.retirer("telegram", compte)
        c.emettre("telegram.detache", objet=("telegram", compte), donnees={"compte": compte})
        return {"compte": compte, "jeton": l["jeton"], "chat_id": l["chat_id"], "cible": l["cible"], "cree": l["cree"]}

    def prouver_detache(c, res):
        return lien(res["compte"]) is None

    def defaire_detache(c, res):
        poser_lien(res["compte"], res["jeton"], conserver={"chat_id": res["chat_id"], "cible": res["cible"], "cree": res["cree"]})

    # ------------------------------------------------------------------ le destinataire
    def cible_poser(c, valeur=""):
        compte = compte_qui_agit()
        v = str(valeur or "").strip()
        if v.startswith("@") or (v and not v.lstrip("-").isdigit()):
            raise ValueError("Un robot Telegram ne sait pas retrouver quelqu'un par son pseudo : il lui faut l'identifiant numérique "
                             "(demandez-le à @userinfobot sur Telegram).")
        l = lien(compte)
        if not l:
            raise ValueError("Aucun robot branché sur ce compte : branchez-le d'abord, sinon rien ne peut être essayé.")
        if v:
            r = appel(l["jeton"], "getChat", {"chat_id": v})
            if not r.get("ok"):
                raise ValueError("Telegram refuse cette destination (%s). Un robot ne peut pas ouvrir une conversation : écrivez-lui « /start » une fois "
                                 "depuis ce compte Telegram, puis réessayez." % raison(r)[:90])
        db.ecrire("UPDATE liens SET cible=? WHERE compte=?", (v, compte))
        return {"compte": compte, "cible": v, "avant": l["cible"]}

    def prouver_cible(c, res):
        l = lien(res["compte"])
        return bool(l) and l["cible"] == res["cible"]

    def defaire_cible(c, res):
        db.ecrire("UPDATE liens SET cible=? WHERE compte=?", (res["avant"], res["compte"]))

    # ------------------------------------------------------------------ envoyer
    def envoyer(c, texte="", compte=""):
        agit = ctx.compte
        cible_compte = str(compte or agit or "").strip().lower()
        if not cible_compte:
            raise ValueError("à quel compte ? (« compte »)")
        if agit and agit not in SYSTEME and cible_compte != agit:
            raise ValueError("un compte n'écrit que par son propre robot")
        t = str(texte or "").strip()
        if not t:
            raise ValueError("message vide")
        l = lien(cible_compte)
        if not l or not l["actif"]:
            return {"ok": False, "cause": "sans-robot", "erreur": "Telegram n'est pas configuré pour ce compte : il faut créer un robot et brancher son jeton.", "compte": cible_compte}
        dest = destinataire(l)
        if not dest:
            return {"ok": False, "cause": "sans-destinataire", "compte": cible_compte,
                    "erreur": "Le robot est branché, mais aucun destinataire : déclarez votre identifiant Telegram, ou écrivez « /start » au robot depuis Telegram."}
        r = appel(l["jeton"], "sendMessage", {"chat_id": dest, "text": t[:TAILLE_MAX]})
        if not r.get("ok"):
            c.emettre("telegram.echec_envoi", objet=("telegram", cible_compte), donnees={"raison": raison(r)})
            return {"ok": False, "cause": "refus", "erreur": raison(r), "compte": cible_compte}
        mid = str(((r.get("result") or {}).get("message_id")) or "")
        db.ecrire("INSERT INTO messages(compte, chat_id, sens, corps, expediteur, message_id, ts) VALUES (?,?,'envoye',?,?,?,?)", (cible_compte, dest, t[:TAILLE_MAX], cible_compte, mid, time.time()))
        c.emettre("telegram.envoye", objet=("telegram", cible_compte), donnees={"compte": cible_compte, "message_id": mid})
        return {"ok": True, "compte": cible_compte, "chat_id": dest, "message_id": mid}

    def prouver_envoye(c, res):
        return (not res.get("ok")) or bool(res.get("message_id"))

    def defaire_envoye(c, res):
        if not res.get("ok"):
            return
        l = lien(res["compte"])
        if l and res.get("message_id"):
            appel(l["jeton"], "deleteMessage", {"chat_id": res["chat_id"], "message_id": int(res["message_id"]) if str(res["message_id"]).isdigit() else res["message_id"]})
        db.ecrire("DELETE FROM messages WHERE compte=? AND message_id=? AND sens='envoye'", (res["compte"], res["message_id"]))

    # ------------------------------------------------------------------ recevoir (public)
    def dit_deja(compte):
        t = time.time()
        for k in [k for k, v in list(DITS.items()) if t - v > DIT_TTL_S]:
            DITS.pop(k, None)
        if t - DITS.get(compte, 0.0) < DIT_TTL_S:
            return True
        DITS[compte] = t
        return False

    def recevoir(c, corps_brut=None, en_tetes=None):
        """Toujours {ok: true} : un secret inconnu reçoit le même 200 muet qu'un message rangé, et Telegram ne retente jamais pour rien."""
        secret = str((en_tetes or {}).get("x-telegram-bot-api-secret-token") or "").strip()
        if len(secret) < 20:
            return {"ok": True}
        r = db.lire("SELECT compte FROM liens WHERE secret_empreinte=? AND actif=1", (empreinte(secret),))
        if not r:
            return {"ok": True}
        compte = r[0]["compte"]
        def objet(x):
            return x if isinstance(x, dict) else {}
        m = objet(objet(corps_brut).get("message"))
        chat_id = objet(m.get("chat")).get("id")
        if not isinstance(chat_id, (int, str)) or isinstance(chat_id, bool) or not str(chat_id).lstrip("-").isdigit():
            return {"ok": True, "ignore": "sans conversation"}        # un appel mal formé n'est jamais une exception : il ferait redescendre le palier
        chat = str(chat_id)
        texte = str(m.get("text") or "")[:TAILLE_MAX]
        de = objet(m.get("from"))
        qui = str(de.get("username") or de.get("first_name") or "?")[:80]
        mid = db.ecrire("INSERT INTO messages(compte, chat_id, sens, corps, expediteur, ts) VALUES (?,?,'recu',?,?,?)", (compte, chat, texte, qui, time.time()))
        db.ecrire("UPDATE liens SET chat_id = CASE WHEN chat_id = '' THEN ? ELSE chat_id END, dernier=? WHERE compte=?", (chat, time.time(), compte))
        c.emettre("telegram.message_recu", objet=("telegram", compte), donnees={"compte": compte, "de": qui, "texte": texte[:400]}, compte=compte)
        if texte and not dit_deja(compte):
            l = lien(compte)
            appel(l["jeton"], "sendMessage", {"chat_id": chat, "text": str(ctx.reglage("mot_du_role", "") or "")[:TAILLE_MAX]}, timeout=5)
        return {"ok": True, "compte": compte, "message": mid}

    def prouver_recu(c, res):
        return (not res.get("message")) or bool(db.lire("SELECT 1 FROM messages WHERE id=?", (res["message"],)))

    def defaire_recu(c, res):
        if res.get("message"):
            db.ecrire("DELETE FROM messages WHERE id=?", (res["message"],))

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.implementer("etat", etat)
    c.implementer("fil", fil)
    c.implementer("brancher", brancher_robot, prouver_brancher, defaire_brancher, simuler=lambda x, **_: "brancherait le robot Telegram de ce compte (webhook posé chez Telegram)")
    c.implementer("detacher", detacher, prouver_detache, defaire_detache, simuler=lambda x, **_: "débrancherait le robot (webhook retiré, jeton oublié)")
    c.implementer("cible_poser", cible_poser, prouver_cible, defaire_cible, simuler=lambda x, valeur="", **_: "déclarerait %s comme destinataire (après essai auprès de Telegram)" % (valeur or "aucun"))
    c.implementer("envoyer", envoyer, prouver_envoye, defaire_envoye, simuler=lambda x, compte="", **_: "enverrait un message Telegram à %s" % (compte or "ce compte"))
    c.implementer("recevoir", recevoir, prouver_recu, defaire_recu, simuler=lambda x, **_: "rangerait un message reçu")
