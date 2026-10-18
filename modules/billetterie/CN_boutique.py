# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #3877b6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la boutique PUBLIQUE (calendrier, page d'un événement, panier, commande, suivi, webhook du prestataire).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3877b6 ▼▼▼
"""Billetterie : la boutique PUBLIQUE (calendrier, page d'un événement, panier, commande, suivi, webhook du prestataire).

Ces capacités se déclarent publiques (`qui = ["anonyme"]`) : elles s'exécutent avant toute connexion. Donc :
  - elles n'exposent QUE ce qu'un visiteur peut voir : des événements publiés, des références publiques (EVT-…, TYP-…), jamais un identifiant interne ni une donnée d'acheteur ;
  - une commande se suit avec un JETON non devinable donné à l'acheteur, jamais avec sa seule référence ;
  - elles se protègent de l'abus : une origine ne retient pas toutes les places (limites par adresse, par courriel, et places retenues en même temps) ;
  - le prix, le stock et les règles sont ceux de la base (CN_ventes.py) : une vente en ligne et une vente à la main obéissent aux mêmes contrôles.
"""
from __future__ import annotations

import hmac
import json

from . import CN_ventes as v
from . import CN_regles as r
from . import CN_stripe as stripe

MOYENS_PRESTATAIRE_PRETS = ("stripe",)               # helloasso et paypal : réglages prévus, adaptateurs à venir
LIMITE_COMMANDES_IP = (10, 3600)                      # 10 commandes par heure et par adresse
LIMITE_COMMANDES_MAIL = (6, 3600)
LIMITE_RETENUES_IP = 3                                # places retenues en même temps : 3 commandes en cours par adresse
HTTP = {}                                             # les bancs y posent un faux transport vers un prestataire : HTTP["stripe"] = fonction


def limiter(tx, cle, maximum, fenetre_s):
    """Compte cette demande ; refuse si l'origine a déjà fait `maximum` demandes dans la fenêtre."""
    now = v.horloge()
    tx.execute("DELETE FROM limites WHERE ts < ?", (now - 86400,))
    n = tx.execute("SELECT COUNT(*) FROM limites WHERE cle = ? AND ts > ?", (cle, now - fenetre_s)).fetchone()[0]
    if n >= maximum:
        raise ValueError("trop de demandes depuis cette origine : réessayez plus tard")
    tx.execute("INSERT INTO limites(cle, ts) VALUES (?,?)", (cle, now))


def etat_public(tx, evt, s):
    if evt["statut"] in ("annulé", "reporté"):
        return evt["statut"]
    if evt["statut"] == "terminé" or (evt["date_iso"] and evt["date_iso"] < v.aujourdhui()):
        return "terminé"
    if evt["statut"] != "en vente":
        return "bientôt"
    if s["restant"] <= 0:
        return "complet"
    return "dernières places" if s["restant"] <= max(10, evt["quota"] * 0.1) else "ouvert"


def horaires(debut, passages, pause):
    """L'heure de début de chaque passage : l'ouverture du spectacle, puis la durée de chacun et la pause entre eux."""
    try:
        h, m = (int(x) for x in str(debut).split(":"))
    except ValueError:
        return [None] * len(passages)
    t, out = h * 60 + m, []
    for p in passages:
        out.append("%02d:%02d" % (t // 60 % 24, t % 60))
        t += int(p["duree"]) + int(pause)
    return out


def brancher(ctx, db):
    def en_ligne():
        if not ctx.reglage("boutique_en_ligne"):
            raise ValueError("la billetterie est fermée pour le moment")

    def evt_pub(tx, ref):
        e = tx.execute("SELECT * FROM evenements WHERE ref = ? AND publie = 1", (str(ref).strip().upper(),)).fetchone()
        if not e:
            raise ValueError("événement introuvable")
        return dict(e)

    def moyens():
        m = []
        if ctx.reglage("stripe_actif") and ctx.reglage("stripe_cle_secrete"):
            m.append({"id": "stripe", "libelle": "Carte bancaire"})
        if ctx.reglage("virement_actif") and ctx.reglage("iban"):
            m.append({"id": "virement", "libelle": "Virement bancaire", "detail": "Places retenues 3 jours, billets émis à réception du virement"})
        return m

    # ── le calendrier et la page d'un événement ──────────────────────────────
    def calendrier(c):
        en_ligne()
        with db.transaction() as tx:
            out = []
            for e in tx.execute("SELECT * FROM evenements WHERE publie = 1 ORDER BY date_iso, id").fetchall():
                e = dict(e)
                s = v.stock(tx, e)
                salle = r.ligne(tx, "salles", e["salle_id"])
                prix = tx.execute("SELECT MIN(prix) FROM types_billets WHERE evenement_id = ? AND visible = 1", (e["id"],)).fetchone()[0]
                out.append({"ref": e["ref"], "nom": e["nom"], "date": e["date_iso"], "accroche": e["accroche"], "lieu": salle["nom"] if salle else "", "a_partir_de": prix,
                            "etat": etat_public(tx, e, s)})
        return {"organisateur": ctx.reglage("titulaire_nom"), "evenements": out}

    def evenement(c, ref=""):
        en_ligne()
        with db.transaction() as tx:
            e = evt_pub(tx, ref)
            s = v.stock(tx, e)
            salle = r.ligne(tx, "salles", e["salle_id"])
            prog = [dict(x) for x in tx.execute("SELECT p.ordre, p.duree, a.scene, a.genre, a.bio FROM passages p JOIN artistes a ON a.id = p.artiste_id WHERE p.evenement_id = ? ORDER BY p.ordre", (e["id"],)).fetchall()]
            for p, h in zip(prog, horaires(e["debut"], prog, e["pause"])):
                p["heure"] = h
            types = []
            for t in tx.execute("SELECT * FROM types_billets WHERE evenement_id = ? AND visible = 1 ORDER BY rang, id", (e["id"],)).fetchall():
                st = [x for x in s["types"] if x["id"] == t["id"]][0]
                etat = "ok"
                if t["ouverture"] and v.aujourdhui() < t["ouverture"]:
                    etat = "bientôt"
                elif t["fermeture"] and v.aujourdhui() > t["fermeture"]:
                    etat = "clos"
                elif st["restant"] is not None and st["restant"] <= 0:
                    etat = "épuisé"
                types.append({"ref": t["ref"], "nom": t["nom"], "description": t["description"], "prix": t["prix"], "entrees": t["entrees"], "etat": etat,
                              "plus_que": st["restant"] if (st["restant"] is not None and 0 < st["restant"] <= 10) else None})
            attente = bool(ctx.reglage("liste_attente")) and e["statut"] in ("en vente", "complet")
            mode = v.mode_achat(ctx, e)
            return {"evenement": {"ref": e["ref"], "nom": e["nom"], "date": e["date_iso"], "description": e["description"], "accroche": e["accroche"], "tags": e["tags"],
                                  "portes": e["portes"], "debut": e["debut"], "fin": e["fin"], "age": e["age"], "configuration": e["conf"], "etat": etat_public(tx, e, s)},
                    "salle": {"nom": salle["nom"], "adresse": salle["adresse"], "pmr": bool(salle["pmr"]), "equipements": salle["equipements"]} if salle else None,
                    "programme": prog, "billets": types, "places_restantes": s["restant"],
                    "achat": {"compte_obligatoire": mode == "obligatoire", "frais_sans_compte": (e["frais_sans_compte"] if e["frais_sans_compte"] is not None else int(ctx.reglage("frais_sans_compte"))),
                              "don_possible": ctx.reglage("titulaire_statut") == "association"},
                    "paiements": moyens(), "liste_attente": attente, "organisateur": {"nom": ctx.reglage("titulaire_nom"), "mail": ctx.reglage("titulaire_mail")}}

    def _lignes(tx, e, lignes):
        out = []
        for x in lignes or []:
            t = tx.execute("SELECT id FROM types_billets WHERE ref = ? AND evenement_id = ?", (str((x or {}).get("type", "")).strip().upper(), e["id"])).fetchone()
            if not t:
                raise ValueError("ce billet n'existe pas pour cet événement")
            out.append({"type_billet_id": t[0], "quantite": (x or {}).get("quantite", 0)})
        return out

    def panier(c, evenement="", lignes=None, code_promo="", don=0, sans_compte=False):
        en_ligne()
        with db.transaction() as tx:
            e = evt_pub(tx, evenement)
            d = v.devis(ctx, tx, e, _lignes(tx, e, lignes), canal="boutique", code_promo=code_promo, don=don, sans_compte=bool(sans_compte))
        return {"lignes": d["lignes"], "places": d["places"], "sous_total": d["sous_total"], "remise": d["remise"], "promo": d["promo"], "don": d["don"], "frais": d["frais"], "total": d["total"]}

    # ── préparer le paiement d'une commande qui retient déjà ses places ──────
    def payer(cmd, e, moyen, abandonner_si_echec=False):
        """Rend de quoi payer : les instructions de virement, ou l'adresse de la page de paiement chez le prestataire. Sert à la commande directe ET à l'offre faite à la liste d'attente."""
        if moyen == "virement":
            with db.transaction() as tx:
                tx.execute("UPDATE commandes SET moyen = 'virement', etat = 'en_attente', expire_le = MAX(expire_le, ?) WHERE id = ?", (v.horloge() + v.DUREE_VIREMENT_S, cmd["id"]))
            return {"type": "virement", "iban": ctx.reglage("iban"), "beneficiaire": ctx.reglage("virement_beneficiaire") or ctx.reglage("titulaire_nom"), "reference": cmd["ref"], "montant": cmd["total"], "delai_jours": 3}
        try:
            page = stripe.creer_page_de_paiement(ctx.reglage("stripe_cle_secrete"), cmd, e, v.url(ctx, "/c/%s?s=%s" % (cmd["ref"], cmd["suivi"])), v.url(ctx, "/e/%s" % e["ref"]), http=HTTP.get("stripe"))
        except RuntimeError as ex:
            if abandonner_si_echec:
                with db.transaction() as tx:
                    tx.execute("UPDATE commandes SET etat = 'annulee', note = ? WHERE id = ?", (str(ex)[:200], cmd["id"]))
            raise ValueError("le paiement n'a pas pu être préparé : %s" % ex)
        with db.transaction() as tx:
            tx.execute("UPDATE commandes SET session_prestataire = ?, moyen = 'stripe' WHERE id = ?", (page["id"], cmd["id"]))
        return {"type": "stripe", "url": page["url"]}

    # ── commander ────────────────────────────────────────────────────────────
    def commander(c, evenement="", lignes=None, nom="", mail="", moyen="", code_promo="", don=0, sans_compte=False, code_revendeur="", ip="", consentement=False):
        en_ligne()
        dispo = {m["id"] for m in moyens()}
        if moyen not in dispo:
            raise ValueError("ce moyen de paiement n'est pas proposé (%s)" % (", ".join(sorted(dispo)) or "aucun n'est configuré"))
        nom = r.requis(nom, "votre nom")
        mail = r.mail_valide(mail)
        if not mail:
            raise ValueError("votre courriel est obligatoire : vos billets vous y sont envoyés")
        ip = str(ip or "")[:64]
        with db.transaction() as tx:
            e = evt_pub(tx, evenement)
            if ip:
                limiter(tx, "cmd:ip:" + ip, *LIMITE_COMMANDES_IP)
                if tx.execute("SELECT COUNT(*) FROM commandes WHERE ip = ? AND etat IN ('retenue','en_attente') AND expire_le > ?", (ip, v.horloge())).fetchone()[0] >= LIMITE_RETENUES_IP:
                    raise ValueError("vous avez déjà des réservations en cours : payez-les ou attendez qu'elles expirent")
            limiter(tx, "cmd:mail:" + mail.lower(), *LIMITE_COMMANDES_MAIL)
            cid, d = v.creer_commande(ctx, tx, e, _lignes(tx, e, lignes), canal="boutique", nom=nom, mail=mail, revendeur_code=code_revendeur, code_promo=code_promo, don=don,
                                      sans_compte=bool(sans_compte), moyen="virement" if moyen == "virement" else "", par="boutique")
            tx.execute("UPDATE commandes SET moyen = ?, ip = ? WHERE id = ?", (moyen, ip, cid))
            if consentement:
                tx.execute("UPDATE clients SET consentement = 1 WHERE mail = ?", (mail,))
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (cid,)).fetchone())
        sortie = {"commande": cmd["ref"], "suivi": cmd["suivi"], "total": d["total"], "places": d["places"], "expire_le": cmd["expire_le"], "attribution": cmd["attribution"]}
        sortie["paiement"] = payer(cmd, e, moyen, abandonner_si_echec=True)
        return sortie

    def prouver_commander(c, res):
        return bool(db.lire("SELECT 1 FROM commandes WHERE ref = ?", (res["commande"],)))

    def defaire_commander(c, res):
        with db.transaction() as tx:
            tx.execute("UPDATE commandes SET etat = 'annulee' WHERE ref = ? AND etat IN ('retenue','en_attente')", (res["commande"],))

    # ── suivre sa commande ───────────────────────────────────────────────────
    def suivre(c, commande="", suivi=""):
        from . import CN_billets as bil
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM commandes WHERE ref = ?", (str(commande).strip().upper(),)).fetchone()
            if not x or not x["suivi"] or not hmac.compare_digest(str(x["suivi"]), str(suivi)):
                raise ValueError("commande introuvable")            # la même phrase dans les deux cas : on ne dit pas si la référence existe
            x = dict(x)
            e = r.ligne(tx, "evenements", x["evenement_id"])
        out = {"commande": x["ref"], "etat": x["etat"], "total": x["total"], "evenement": {"ref": e["ref"], "nom": e["nom"], "date": e["date_iso"]}, "billets": []}
        if x["etat"] == "payee":
            k = bil.cle(ctx, db)
            out["billets"] = [{"numero": b["numero"], "nom": b["nom"], "etat": b["etat"], "qr": bil.contenu_qr(k, b["numero"], b["version"]), "code_controle": bil.code_controle(k, b["numero"], b["version"])}
                              for b in db.lire("SELECT * FROM billets WHERE commande_id = ? ORDER BY id", (x["id"],))]
        elif x["etat"] in ("retenue", "en_attente"):
            out["expire_le"] = x["expire_le"]
            if x["moyen"] == "virement":
                out["paiement"] = {"type": "virement", "iban": ctx.reglage("iban"), "reference": x["ref"], "montant": x["total"]}
        return out

    # ── le webhook de Stripe ─────────────────────────────────────────────────
    def webhook_stripe(c, corps_octets=None, en_tetes=None):
        """Stripe y poste ses événements. Les OCTETS bruts du corps sont ce que Stripe a signé : on ne les reconstruit jamais à partir d'un JSON relu."""
        brut = bytes(corps_octets or b"")
        entete = (en_tetes or {}).get("stripe-signature", "")
        if not stripe.verifier_signature(bytes(brut), entete, ctx.reglage("stripe_webhook_secret"), v.horloge()):
            return {"ok": False, "code": 401, "erreur": "signature invalide"}
        try:
            ev = json.loads(bytes(brut).decode("utf-8"))
        except ValueError:
            return {"ok": False, "code": 401, "erreur": "corps illisible"}
        ident, typ = str(ev.get("id", ""))[:80], str(ev.get("type", ""))[:80]
        obj = (ev.get("data") or {}).get("object") or {}
        with db.transaction() as tx:
            if tx.execute("SELECT 1 FROM evenements_paiement WHERE fournisseur = 'stripe' AND ident = ?", (ident,)).fetchone():
                return {"ok": True, "deja": True}
            ref = str(obj.get("client_reference_id", ""))[:40]
            issue, detail = "ignore", ""
            if typ == "checkout.session.completed" and ref:
                cmd = tx.execute("SELECT * FROM commandes WHERE ref = ?", (ref,)).fetchone()
                if not cmd:
                    issue, detail = "inconnue", "commande inconnue"
                elif obj.get("payment_status") != "paid":
                    issue, detail = "attente", "pas encore payé"
                elif int(obj.get("amount_total", -1)) != int(cmd["total"]):
                    issue, detail = "ecart", "montant payé %s ≠ total de la commande %s : rien n'est livré" % (obj.get("amount_total"), cmd["total"])
                    tx.execute("UPDATE commandes SET note = ? WHERE id = ?", ("paiement Stripe d'un montant différent : " + str(obj.get("amount_total")), cmd["id"]))
                else:
                    try:
                        v.encaisser(ctx, tx, dict(cmd), "stripe", str(obj.get("payment_intent") or obj.get("id") or ""), "stripe")
                        issue = "paye"
                    except ValueError as ex:
                        issue, detail = "a_rembourser", str(ex)[:200]
                        if cmd["etat"] == "payee":                    # un SECOND paiement pour une commande déjà livrée : on ne touche pas à la commande, on dit qu'il faut le rendre
                            tx.execute("UPDATE commandes SET note = ? WHERE id = ?", ("second paiement Stripe reçu (%s) : à rembourser chez Stripe" % str(obj.get("payment_intent") or ""), cmd["id"]))
                        else:
                            tx.execute("UPDATE commandes SET etat = CASE WHEN etat IN ('retenue','en_attente','expiree') THEN 'annulee' ELSE etat END, note = ? WHERE id = ?",
                                       ("paiement reçu mais commande non livrée (%s) : à rembourser chez Stripe" % detail, cmd["id"]))
            tx.execute("INSERT INTO evenements_paiement(fournisseur, ident, type, commande_ref, issue, detail) VALUES ('stripe',?,?,?,?,?)", (ident, typ, ref, issue, detail))
        return {"ok": True, "issue": issue, "commande": ref}

    def prouver_webhook(c, res):
        return True

    def defaire_webhook(c, res):
        """Un paiement livré par erreur se défait comme une encaissement : la commande est remboursée (le remboursement chez Stripe reste à faire)."""
        if res.get("issue") != "paye":
            return
        with db.transaction() as tx:
            cmd = tx.execute("SELECT * FROM commandes WHERE ref = ?", (res["commande"],)).fetchone()
            if cmd and cmd["etat"] == "payee":
                v.rembourser(ctx, tx, dict(cmd), "événement annulé")
    ctx.implementer("public_calendrier", calendrier)
    ctx.implementer("public_evenement", evenement)
    ctx.implementer("public_panier", panier)
    ctx.implementer("public_commander", commander, prouver_commander, defaire_commander, simuler=lambda x, evenement="", **_: "passerait une commande pour %s" % evenement)
    ctx.implementer("public_suivre", suivre)

    def courriels(c, etat="", limite=100):
        sql, p = "SELECT * FROM courriels WHERE 1 = 1", []
        if etat:
            sql, p = sql + " AND etat = ?", [etat]
        return {"courriels": db.lire(sql + " ORDER BY id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 100), 500)),))}
    ctx.implementer("courriels", courriels)
    ctx.implementer("public_webhook_stripe", webhook_stripe, prouver_webhook, defaire_webhook, simuler=lambda x, **_: "recevrait un événement de Stripe")

    def payer_commande(c, commande="", suivi="", moyen=""):
        """Payer une commande qui retient déjà ses places (l'offre faite à la liste d'attente, ou une commande reprise) : même jeton de suivi que pour la consulter."""
        en_ligne()
        if moyen not in {m["id"] for m in moyens()}:
            raise ValueError("ce moyen de paiement n'est pas proposé")
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM commandes WHERE ref = ?", (str(commande).strip().upper(),)).fetchone()
            if not x or not x["suivi"] or not hmac.compare_digest(str(x["suivi"]), str(suivi)):
                raise ValueError("commande introuvable")
            x = dict(x)
            if x["etat"] not in ("retenue", "en_attente") or x["expire_le"] <= v.horloge():
                raise ValueError("cette réservation n'est plus valable")
            e = r.ligne(tx, "evenements", x["evenement_id"])
        return {"commande": x["ref"], "total": x["total"], "paiement": payer(x, e, moyen), "moyen": moyen,
                "avant": {"id": x["id"], "etat": x["etat"], "moyen": x["moyen"], "expire_le": x["expire_le"], "session_prestataire": x["session_prestataire"]}}

    def prouver_payer(c, res):
        x = db.lire("SELECT moyen FROM commandes WHERE ref = ?", (res["commande"],))
        return bool(x) and x[0]["moyen"] == res["moyen"]

    def defaire_payer(c, res):
        a = res["avant"]
        with db.transaction() as tx:
            tx.execute("UPDATE commandes SET etat = ?, moyen = ?, expire_le = ?, session_prestataire = ? WHERE id = ? AND etat IN ('retenue','en_attente')",
                       (a["etat"], a["moyen"], a["expire_le"], a["session_prestataire"], a["id"]))

    ctx.implementer("public_payer", payer_commande, prouver_payer, defaire_payer, simuler=lambda x, commande="", **_: "préparerait le paiement de la commande %s" % commande)
    return {"payer": payer, "en_ligne": en_ligne, "evt_pub": evt_pub, "moyens": moyens}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : limiter, etat_public, horaires, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
