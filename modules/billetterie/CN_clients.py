# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #b4d629
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les comptes clients de la boutique.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b4d629 ▼▼▼
"""Billetterie : les comptes clients de la boutique.

Pas de mot de passe : un client demande un LIEN de connexion à son courriel (la réponse est la même que le compte existe ou non : on ne révèle pas qui est client), ouvre le lien,
et reçoit une session. Le lien (15 minutes, un seul usage) et la session (30 jours) ne sont jamais gardés en clair, seulement leur empreinte.
Avec son compte, le client retrouve ses commandes et ses billets, achète sans les frais d'achat sans compte, modifie son nom, exporte ses données et demande leur suppression.

La suppression est différée (réglage) et se défait tant qu'elle n'a pas eu lieu ; à l'exécution les données personnelles sont effacées (client, commandes, billets, listes d'attente,
courriels), les montants et les reçus fiscaux restent : ce sont des pièces comptables.
"""
from __future__ import annotations

import secrets

from . import CN_identifiants as ids
from . import CN_regles as r
from . import CN_ventes as v
from .CN_boutique import limiter

VALIDITE_LIEN_S = 15 * 60
VALIDITE_SESSION_S = 30 * 24 * 3600
LIMITE_LIENS_IP = (8, 3600)
LIMITE_LIENS_MAIL = (4, 3600)


def _exiger(tx, session):
    c = v.client_de_session(tx, session)
    if not c:
        raise ValueError("votre session a expiré : reconnectez-vous")
    return c


def anonymiser(tx, client):
    """Efface les données personnelles d'un client. Les montants et les reçus fiscaux restent."""
    cid, ancien = client["id"], client["mail"]
    tx.execute("UPDATE clients SET nom = '', mail = ?, tel = '', adresse = '', code_postal = '', ville = '', organisation = '', siret = '', ape = '', tva = '', consentement = 0, compte = 0, efface = 1, suppression_le = 0 WHERE id = ?",
               ("efface-%d@invalide.local" % cid, cid))
    cmds = [x[0] for x in tx.execute("SELECT id FROM commandes WHERE client_id = ?", (cid,)).fetchall()]
    for k in cmds:
        tx.execute("UPDATE commandes SET nom = '', mail = '', ip = '' WHERE id = ?", (k,))
        tx.execute("UPDATE billets SET nom = '', mail = '' WHERE commande_id = ?", (k,))
    tx.execute("UPDATE attente SET nom = '', mail = 'efface', etat = CASE WHEN etat IN ('attente','offerte') THEN 'retiree' ELSE etat END, ip = '' WHERE lower(mail) = lower(?)", (ancien,))
    tx.execute("DELETE FROM courriels WHERE lower(a) = lower(?)", (ancien,))
    tx.execute("DELETE FROM liens_connexion WHERE client_id = ?", (cid,))
    tx.execute("DELETE FROM sessions_client WHERE client_id = ?", (cid,))
    return len(cmds)


def dossier(tx, c):
    """Tout ce que la billetterie sait d'un client (droit d'accès : export complet)."""
    cid = c["id"]
    q = lambda sql, p=(): [dict(x) for x in tx.execute(sql, p).fetchall()]
    cmds = q("SELECT c.ref, c.etat, c.moyen, c.sous_total, c.remise, c.don, c.frais, c.total, c.promo_code, c.nom, c.mail, c.cree_le, c.payee_le, e.nom AS evenement, e.date_iso FROM commandes c JOIN evenements e ON e.id = c.evenement_id WHERE c.client_id = ? ORDER BY c.id", (cid,))
    return {"client": {k: c[k] for k in ("ref", "nom", "mail", "tel", "adresse", "code_postal", "ville", "pays", "consentement", "compte", "cree_le")},
            "commandes": cmds,
            "billets": q("SELECT b.numero, b.nom, b.mail, b.etat, b.entrees, b.entrees_faites, b.cree_le, e.nom AS evenement FROM billets b JOIN commandes c ON c.id = b.commande_id JOIN evenements e ON e.id = b.evenement_id WHERE c.client_id = ? ORDER BY b.id", (cid,)),
            "recus_fiscaux": q("SELECT rf.numero, rf.montant, rf.nom, rf.adresse, rf.date_don, rf.mode, rf.etat FROM recus_fiscaux rf JOIN commandes c ON c.id = rf.commande_id WHERE c.client_id = ? ORDER BY rf.id", (cid,)),
            "liste_attente": q("SELECT a.ref, a.quantite, a.etat, a.cree_le, e.nom AS evenement FROM attente a JOIN evenements e ON e.id = a.evenement_id WHERE lower(a.mail) = lower(?) ORDER BY a.id", (c["mail"],)),
            "courriels": q("SELECT objet, etat, cree_le FROM courriels WHERE lower(a) = lower(?) ORDER BY id", (c["mail"],))}


def effacer_echus(tx) -> int:
    """Le travail du moteur : purge des liens et sessions périmés, effacement des comptes dont le délai est écoulé."""
    faits = 0
    tx.execute("DELETE FROM liens_connexion WHERE expire_le < ?", (v.horloge() - 86400,))
    tx.execute("DELETE FROM sessions_client WHERE expire_le < ?", (v.horloge(),))
    for cli in [dict(x) for x in tx.execute("SELECT * FROM clients WHERE suppression_le > 0 AND suppression_le <= ? AND efface = 0", (v.horloge(),)).fetchall()]:
        anonymiser(tx, cli)
        faits += 1
    return faits


def brancher(ctx, db):
    delai = lambda: max(0, int(ctx.reglage("suppression_delai_jours"))) * 86400

    # ── un lien de connexion par courriel ────────────────────────────────────
    def lien(c, mail="", ip=""):
        mail = r.mail_valide(mail)
        if not mail:
            raise ValueError("indiquez votre courriel")
        ip = str(ip or "")[:64]
        with db.transaction() as tx:
            if ip:
                limiter(tx, "lien:ip:" + ip, *LIMITE_LIENS_IP)
            limiter(tx, "lien:mail:" + mail.lower(), *LIMITE_LIENS_MAIL)
            cli = tx.execute("SELECT * FROM clients WHERE mail = ?", (mail,)).fetchone()
            if not cli:
                cid = tx.execute("INSERT INTO clients(ref, nom, mail, compte) VALUES (?,?,?,0)", (ids.nouvelle_ref(tx, "client"), "", mail)).lastrowid
            else:
                cid = cli["id"]
            jeton = secrets.token_urlsafe(32)
            lid = tx.execute("INSERT INTO liens_connexion(client_id, empreinte, expire_le) VALUES (?,?,?)", (cid, v.empreinte(jeton), v.horloge() + VALIDITE_LIEN_S)).lastrowid
            corps = ("Bonjour,\n\nVoici votre lien de connexion à votre espace billetterie (il ne sert qu'une fois et expire dans 15 minutes) :\n%s\n\n"
                     "Si vous n'avez rien demandé, ignorez ce message : personne ne peut se connecter sans ce lien.\n\n%s" % (v.url(ctx, "/boutique.html#/compte?t=" + jeton), ctx.reglage("titulaire_nom")))
            mid = tx.execute("INSERT INTO courriels(a, objet, corps) VALUES (?,?,?)", (mail, "Votre lien de connexion", corps)).lastrowid
        return {"ok": True, "lien_id": lid, "courriel_id": mid}          # même réponse que le compte existe ou non

    def prouver_lien(c, res):
        return bool(db.lire("SELECT 1 FROM liens_connexion WHERE id = ?", (res["lien_id"],)))

    def defaire_lien(c, res):
        with db.transaction() as tx:
            tx.execute("DELETE FROM liens_connexion WHERE id = ?", (res["lien_id"],))
            tx.execute("DELETE FROM courriels WHERE id = ? AND etat = 'a_envoyer'", (res["courriel_id"],))

    def ouvrir(c, jeton=""):
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM liens_connexion WHERE empreinte = ?", (v.empreinte(jeton),)).fetchone()
            if not x or x["utilise"] or x["expire_le"] <= v.horloge():
                raise ValueError("ce lien n'est plus valable : demandez-en un nouveau")
            tx.execute("UPDATE liens_connexion SET utilise = 1 WHERE id = ?", (x["id"],))
            cli = dict(tx.execute("SELECT * FROM clients WHERE id = ?", (x["client_id"],)).fetchone())
            if cli["efface"]:
                raise ValueError("ce compte a été supprimé")
            tx.execute("UPDATE clients SET compte = 1 WHERE id = ?", (cli["id"],))
            session = secrets.token_urlsafe(32)
            sid = tx.execute("INSERT INTO sessions_client(client_id, empreinte, expire_le) VALUES (?,?,?)", (cli["id"], v.empreinte(session), v.horloge() + VALIDITE_SESSION_S)).lastrowid
        return {"session": session, "session_id": sid, "lien_id": x["id"], "nom": cli["nom"], "mail": cli["mail"], "suppression_le": cli["suppression_le"]}

    def prouver_ouvrir(c, res):
        return bool(db.lire("SELECT 1 FROM sessions_client WHERE id = ?", (res["session_id"],)))

    def defaire_ouvrir(c, res):
        with db.transaction() as tx:
            tx.execute("DELETE FROM sessions_client WHERE id = ?", (res["session_id"],))
            tx.execute("UPDATE liens_connexion SET utilise = 0 WHERE id = ? AND expire_le > ?", (res["lien_id"], v.horloge()))

    def fermer(c, session=""):
        with db.transaction() as tx:
            n = tx.execute("DELETE FROM sessions_client WHERE empreinte = ?", (v.empreinte(session),)).rowcount
        return {"fermees": n}

    # ── mon espace ───────────────────────────────────────────────────────────
    def moi(c, session=""):
        with db.transaction() as tx:
            cli = _exiger(tx, session)
            cmds = []
            for x in tx.execute("SELECT c.ref, c.suivi, c.etat, c.total, c.don, c.cree_le, e.nom AS evenement, e.date_iso FROM commandes c JOIN evenements e ON e.id = c.evenement_id WHERE c.client_id = ? ORDER BY c.id DESC LIMIT 100", (cli["id"],)).fetchall():
                cmds.append({"commande": x["ref"], "suivi": x["suivi"], "etat": x["etat"], "total": x["total"], "don": x["don"], "evenement": x["evenement"], "date": x["date_iso"], "cree_le": x["cree_le"]})
            att = [dict(x) for x in tx.execute("SELECT a.jeton AS suivi, a.etat, a.quantite, e.nom AS evenement FROM attente a JOIN evenements e ON e.id = a.evenement_id WHERE lower(a.mail) = lower(?) AND a.etat IN ('attente','offerte') ORDER BY a.id", (cli["mail"],)).fetchall()]
        return {"nom": cli["nom"], "mail": cli["mail"], "tel": cli["tel"], "consentement": bool(cli["consentement"]), "suppression_le": cli["suppression_le"], "commandes": cmds, "attente": att}

    def modifier(c, session="", nom="", tel="", consentement=False):
        with db.transaction() as tx:
            cli = _exiger(tx, session)
            tx.execute("UPDATE clients SET nom = ?, tel = ?, consentement = ? WHERE id = ?", (r.texte(nom, 120), r.texte(tel, 40), 1 if consentement else 0, cli["id"]))
        return {"id": cli["id"], "avant": {"nom": cli["nom"], "tel": cli["tel"], "consentement": cli["consentement"]}, "nom": r.texte(nom, 120)}

    def prouver_modifier(c, res):
        x = db.lire("SELECT nom FROM clients WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["nom"] == res["nom"]

    def defaire_modifier(c, res):
        a = res["avant"]
        db.ecrire("UPDATE clients SET nom = ?, tel = ?, consentement = ? WHERE id = ?", (a["nom"], a["tel"], a["consentement"], res["id"]))

    def exporter(c, session=""):
        with db.transaction() as tx:
            return dossier(tx, _exiger(tx, session))

    def supprimer(c, session=""):
        with db.transaction() as tx:
            cli = _exiger(tx, session)
            quand = v.horloge() + delai()
            tx.execute("UPDATE clients SET suppression_le = ? WHERE id = ?", (quand, cli["id"]))
            tx.execute("DELETE FROM courriels WHERE lower(a) = lower(?) AND etat = 'a_envoyer' AND commande_ref = ''", (cli["mail"],))
            tx.execute("UPDATE attente SET etat = 'retiree' WHERE lower(mail) = lower(?) AND etat IN ('attente','offerte')", (cli["mail"],))
        return {"id": cli["id"], "effacement_le": quand, "avant": cli["suppression_le"]}

    def prouver_supprimer(c, res):
        x = db.lire("SELECT suppression_le FROM clients WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["suppression_le"] == res["effacement_le"]

    def defaire_supprimer(c, res):
        db.ecrire("UPDATE clients SET suppression_le = ? WHERE id = ? AND efface = 0", (res["avant"], res["id"]))

    def annuler_suppression(c, session=""):
        with db.transaction() as tx:
            cli = _exiger(tx, session)
            if not cli["suppression_le"]:
                raise ValueError("aucune suppression n'est programmée")
            tx.execute("UPDATE clients SET suppression_le = 0 WHERE id = ?", (cli["id"],))
        return {"id": cli["id"], "avant": cli["suppression_le"]}

    def prouver_annuler(c, res):
        x = db.lire("SELECT suppression_le FROM clients WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["suppression_le"] == 0

    def defaire_annuler(c, res):
        db.ecrire("UPDATE clients SET suppression_le = ? WHERE id = ? AND efface = 0", (res["avant"], res["id"]))

    # ── côté titulaire ───────────────────────────────────────────────────────
    def clients(c, q="", limite=100):
        sql, p = "SELECT c.id, c.ref, c.nom, c.mail, c.compte, c.consentement, c.suppression_le, c.efface, c.cree_le, (SELECT COUNT(*) FROM commandes WHERE client_id = c.id) AS commandes FROM clients c WHERE 1 = 1", []
        if q:
            sql, p = sql + " AND (c.nom LIKE ? OR c.mail LIKE ? OR c.ref LIKE ?)", p + ["%" + str(q) + "%"] * 3
        return {"clients": db.lire(sql + " ORDER BY c.id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 100), 500)),))}

    def client_dossier(c, id=0):
        with db.transaction() as tx:
            cli = r.ligne(tx, "clients", id)
            if not cli:
                raise ValueError("client introuvable")
            if cli["efface"]:
                raise ValueError("ce client a été effacé : il ne reste que les montants et les reçus")
            return dossier(tx, cli)

    def effacement(c, id=0, annuler=False):
        with db.transaction() as tx:
            cli = r.ligne(tx, "clients", id)
            if not cli or cli["efface"]:
                raise ValueError("client introuvable ou déjà effacé")
            quand = 0 if annuler else v.horloge() + delai()
            tx.execute("UPDATE clients SET suppression_le = ? WHERE id = ?", (quand, cli["id"]))
            if not annuler:
                tx.execute("DELETE FROM sessions_client WHERE client_id = ?", (cli["id"],))
        return {"id": cli["id"], "effacement_le": quand, "avant": cli["suppression_le"]}

    def prouver_effacement(c, res):
        x = db.lire("SELECT suppression_le FROM clients WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["suppression_le"] == res["effacement_le"]

    def defaire_effacement(c, res):
        db.ecrire("UPDATE clients SET suppression_le = ? WHERE id = ? AND efface = 0", (res["avant"], res["id"]))

    def moteur(c):
        with db.transaction() as tx:
            return {"effaces": effacer_echus(tx)}

    ctx.implementer("public_compte_lien", lien, prouver_lien, defaire_lien, simuler=lambda x, mail="", **_: "enverrait un lien de connexion")
    ctx.implementer("public_compte_ouvrir", ouvrir, prouver_ouvrir, defaire_ouvrir, simuler=lambda x, **_: "ouvrirait une session avec un lien de connexion")
    ctx.implementer("public_compte_fermer", fermer)
    ctx.implementer("public_compte_moi", moi)
    ctx.implementer("public_compte_modifier", modifier, prouver_modifier, defaire_modifier, simuler=lambda x, **_: "modifierait le nom du compte")
    ctx.implementer("public_compte_exporter", exporter)
    ctx.implementer("public_compte_supprimer", supprimer, prouver_supprimer, defaire_supprimer, simuler=lambda x, **_: "programmerait la suppression du compte")
    ctx.implementer("public_compte_annuler_suppression", annuler_suppression, prouver_annuler, defaire_annuler, simuler=lambda x, **_: "annulerait la suppression programmée")
    ctx.implementer("clients", clients)
    ctx.implementer("client_dossier", client_dossier)
    ctx.implementer("client_effacement", effacement, prouver_effacement, defaire_effacement, simuler=lambda x, id=0, **_: "programmerait l'effacement des données du client %s" % id)
    ctx.moteur("clients", moteur)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _exiger, anonymiser, dossier, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
