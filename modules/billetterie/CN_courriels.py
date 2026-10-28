# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #841c7d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : l'envoi réel des courriels (billets, annulations, offres de la liste d'attente, liens de connexion).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=841c7d ▼▼▼
"""Billetterie : l'envoi réel des courriels (billets, annulations, offres de la liste d'attente, liens de connexion).

La billetterie PRÉPARE ses courriels dans une boîte d'envoi (jamais d'envoi au milieu d'une vente : un serveur de courrier en panne ne doit pas faire perdre une commande).
Ce fichier les expédie, par le serveur SMTP réglé dans la billetterie :
  - rien ne part tant que l'envoi n'est pas activé (réglage) et le serveur réglé ;
  - un envoi qui échoue est retenté plus tard (5 essais, délais de plus en plus longs), puis marqué en échec avec sa raison ; le mot de passe n'apparaît jamais dans une raison ;
  - le frein « envois » du noyau arrête tout, comme pour n'importe quelle capacité sortante ;
  - l'adresse vient toujours de la commande ou du compte de la personne : jamais d'un texte lu ailleurs.
Le transport (`ENVOI`) se remplace dans les bancs : on ne parle pas à un vrai serveur depuis un banc.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import CN_billets as bil
from . import CN_pdf as pdf
from . import CN_ventes as v

ESSAIS_MAX = 5
BASE_DELAI_S = 300
ENVOI = {}                      # les bancs y posent « smtp » : une fonction (hote, port, securite, identifiant, mot_de_passe, expediteur, a, objet, corps)


BOUCLE_LOCALE = ("localhost", "127.0.0.1", "::1")


def envoyer_smtp(hote, port, securite, identifiant, mot_de_passe, expediteur, a, objet, corps, delai=20, pieces=None):
    if identifiant and securite not in ("starttls", "ssl") and hote not in BOUCLE_LOCALE:
        raise ValueError("jamais de mot de passe sans chiffrement : choisissez starttls ou ssl")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = expediteur, a, objet
    msg["Date"], msg["Message-ID"] = formatdate(localtime=False), make_msgid()
    msg.set_content(corps)
    for nom, type_, octets in pieces or []:
        msg.add_attachment(octets, maintype=type_.split("/")[0], subtype=type_.split("/")[1], filename=nom)
    if securite == "ssl":
        srv = smtplib.SMTP_SSL(hote, int(port), timeout=delai, context=ssl.create_default_context())
    else:
        srv = smtplib.SMTP(hote, int(port), timeout=delai)
    with srv as s:
        if securite == "starttls":
            s.starttls(context=ssl.create_default_context())
        if identifiant:
            s.login(identifiant, mot_de_passe)
        s.send_message(msg)


def frein_envois(ctx) -> bool:
    """Le frein « envois » du noyau, s'il l'expose au module (`ctx.frein_actif`). Sinon on ne peut pas le lire d'ici : le dit le retour de `etat`."""
    f = getattr(ctx, "frein_actif", None)
    return bool(f("envois")) if callable(f) else False


def reglages(ctx):
    return {"actif": bool(ctx.reglage("courriels_actifs")), "hote": str(ctx.reglage("smtp_hote") or "").strip(), "port": int(ctx.reglage("smtp_port") or 587),
            "securite": str(ctx.reglage("smtp_securite") or "starttls"), "identifiant": str(ctx.reglage("smtp_identifiant") or "").strip(),
            "mdp": str(ctx.reglage("smtp_mot_de_passe") or ""), "de": str(ctx.reglage("smtp_expediteur") or ctx.reglage("titulaire_mail") or "").strip()}


def pieces_jointes(ctx, db, m):
    """Les pièces d'un courriel : les billets de la commande en PDF, refaits maintenant depuis la base (seules les places encore valides)."""
    if m.get("joindre") != "billets" or not m.get("commande_ref"):
        return []
    cle = bil.cle(ctx, db)
    with db.transaction() as tx:
        cmd = tx.execute("SELECT * FROM commandes WHERE ref = ?", (m["commande_ref"],)).fetchone()
        billets = v.donnees_pdf(ctx, tx, cle, dict(cmd)) if cmd and cmd["etat"] == "payee" else []
    return [("billets-%s.pdf" % m["commande_ref"], "application/pdf", pdf.billets_pdf(billets))] if billets else []


def expedier_lot(ctx, db, maximum=20):
    """Envoie les courriels dus. Rend {envoyes, echecs, reportes, raison}."""
    g = reglages(ctx)
    if not g["actif"]:
        return {"envoyes": 0, "echecs": 0, "reportes": 0, "raison": "l'envoi des courriels n'est pas activé"}
    if not g["hote"] or not g["de"]:
        return {"envoyes": 0, "echecs": 0, "reportes": 0, "raison": "le serveur d'envoi ou l'adresse d'expédition n'est pas réglé"}
    if frein_envois(ctx):
        return {"envoyes": 0, "echecs": 0, "reportes": 0, "raison": "le frein « envois » est posé : rien ne sort"}
    envoi = ENVOI.get("smtp") or envoyer_smtp
    dus = db.lire("SELECT * FROM courriels WHERE etat = 'a_envoyer' AND prochain_essai <= ? ORDER BY id LIMIT ?", (v.horloge(), max(1, min(int(maximum), 100))))
    ok = ko = rep = 0
    for m in dus:
        try:
            envoi(g["hote"], g["port"], g["securite"], g["identifiant"], g["mdp"], g["de"], m["a"], m["objet"], m["corps"], pieces=pieces_jointes(ctx, db, m))
        except Exception as ex:                                            # un serveur qui refuse, une coupure, un délai : on retient la raison, sans le mot de passe
            raison = str(ex)
            for secret in (g["mdp"], g["identifiant"]):
                if secret:
                    raison = raison.replace(secret, "***")
            essais = m["essais"] + 1
            with db.transaction() as tx:
                if essais >= ESSAIS_MAX:
                    tx.execute("UPDATE courriels SET etat = 'echec', essais = ?, erreur = ? WHERE id = ?", (essais, raison[:300], m["id"]))
                    ko += 1
                else:
                    tx.execute("UPDATE courriels SET essais = ?, erreur = ?, prochain_essai = ? WHERE id = ?", (essais, raison[:300], v.horloge() + BASE_DELAI_S * 2 ** (essais - 1), m["id"]))
                    rep += 1
            continue
        with db.transaction() as tx:
            tx.execute("UPDATE courriels SET etat = 'envoye', envoye_le = datetime('now'), essais = essais + 1, erreur = '' WHERE id = ?", (m["id"],))
        ok += 1
    return {"envoyes": ok, "echecs": ko, "reportes": rep, "raison": ""}


def brancher(ctx, db):
    def envoyer(c, maximum=20):
        return expedier_lot(ctx, db, maximum)

    def prouver_envoyer(c, res):
        return True

    def defaire_envoyer(c, res):
        return None                                             # un courriel parti ne se rappelle pas : le retour de la capacité le dit

    def relancer(c, id=0):
        with db.transaction() as tx:
            m = tx.execute("SELECT * FROM courriels WHERE id = ?", (int(id),)).fetchone()
            if not m:
                raise ValueError("courriel introuvable")
            if m["etat"] != "echec":
                raise ValueError("seul un courriel en échec se relance")
            tx.execute("UPDATE courriels SET etat = 'a_envoyer', essais = 0, prochain_essai = 0 WHERE id = ?", (m["id"],))
        return {"id": int(id)}

    def prouver_relancer(c, res):
        x = db.lire("SELECT etat FROM courriels WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "a_envoyer"

    def defaire_relancer(c, res):
        db.ecrire("UPDATE courriels SET etat = 'echec' WHERE id = ? AND etat = 'a_envoyer'", (res["id"],))

    def etat(c):
        g = reglages(ctx)
        cnt = {x["etat"]: x["n"] for x in db.lire("SELECT etat, COUNT(*) AS n FROM courriels GROUP BY etat")}
        return {"actif": g["actif"], "serveur_regle": bool(g["hote"] and g["de"]), "a_envoyer": cnt.get("a_envoyer", 0), "envoyes": cnt.get("envoye", 0), "echecs": cnt.get("echec", 0),
                "frein_lisible": callable(getattr(ctx, "frein_actif", None)), "frein_envois": frein_envois(ctx)}

    def moteur(c):
        return expedier_lot(ctx, db)

    ctx.implementer("courriels_envoyer", envoyer, prouver_envoyer, defaire_envoyer, simuler=lambda x, **_: "enverrait les courriels de la boîte d'envoi par le serveur réglé")
    ctx.implementer("courriel_relancer", relancer, prouver_relancer, defaire_relancer, simuler=lambda x, id=0, **_: "remettrait le courriel %s dans la boîte d'envoi" % id)
    ctx.implementer("courriels_etat", etat)
    ctx.moteur("courriels", moteur)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : envoyer_smtp, frein_envois, reglages, expedier_lot, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
