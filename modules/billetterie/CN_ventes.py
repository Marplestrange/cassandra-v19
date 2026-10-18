# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #6b45bc
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les ventes (places, panier, commandes, billets, commissions, remboursements, invitations).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6b45bc ▼▼▼
"""Billetterie : les ventes (places, panier, commandes, billets, commissions, remboursements, invitations).

Ce fichier DÉCIDE : qui peut acheter quoi, à quel prix, combien de places restent, quand une vente est acquise, ce qu'elle rapporte au revendeur et quand elle s'annule.
Le calcul de la commission est délégué au point d'évolution `commission` ; l'écriture se fait dans le registre (écriture seule), jamais par retouche.

Règles qui tiennent tout :
  - le prix vient TOUJOURS de la base, jamais de la demande ;
  - une commande en cours ne fait que RETENIR des places (le temps de payer, ou de recevoir un virement) ; un billet n'existe qu'une fois la commande payée (ou offerte, ou invitée) ;
  - une même référence de paiement ne se déclare qu'une fois (un paiement qui revient deux fois ne livre pas deux billets) ;
  - la commission d'un revendeur est la DIFFÉRENCE entre ce que rapporte la formule avant et après cette vente : la somme de ses lignes vaut toujours ce que rapporte la formule
    pour le nombre de billets réellement vendus, dans n'importe quel ordre de ventes et de remboursements ;
  - un remboursement retire les billets, rend les places et écrit la ligne contraire de la commission.
"""
from __future__ import annotations

import time
from datetime import date

from . import CN_billets as bil
from . import CN_identifiants as ids
from . import CN_regles as r
from . import CN_registre as reg

horloge = time.time                    # les bancs la remplacent pour simuler le temps

RETENANT = ("retenue", "en_attente")
MOYENS_PRESTATAIRE = ("stripe", "helloasso", "paypal")
MOYENS_IMMEDIATS = ("especes", "carte_terminal", "carte_declaree", "offert")
DUREE_VIREMENT_S = 3 * 24 * 3600


def aujourdhui() -> str:
    return date.fromtimestamp(horloge()).isoformat()


# ── le stock : ce qui reste à vendre ─────────────────────────────────────────
def retenus(tx, evenement_id, type_id=None) -> int:
    sql = ("SELECT COALESCE(SUM(l.quantite), 0) FROM lignes_commande l JOIN commandes c ON c.id = l.commande_id "
           "WHERE c.evenement_id = ? AND c.etat IN ('retenue','en_attente') AND c.expire_le > ?")
    p = [int(evenement_id), horloge()]
    if type_id:
        sql, p = sql + " AND l.type_billet_id = ?", p + [int(type_id)]
    return tx.execute(sql, p).fetchone()[0]


def vendus(tx, evenement_id, type_id=None) -> int:
    sql = "SELECT COUNT(*) FROM billets WHERE evenement_id = ? AND etat = 'valide' AND categorie_invite = ''"
    p = [int(evenement_id)]
    if type_id:
        sql, p = sql + " AND type_billet_id = ?", p + [int(type_id)]
    return tx.execute(sql, p).fetchone()[0]


def stock(tx, evt) -> dict:
    v, h = vendus(tx, evt["id"]), retenus(tx, evt["id"])
    types = []
    for t in tx.execute("SELECT * FROM types_billets WHERE evenement_id = ? ORDER BY rang, id", (evt["id"],)).fetchall():
        tv, th = vendus(tx, evt["id"], t["id"]), retenus(tx, evt["id"], t["id"])
        types.append({"id": t["id"], "nom": t["nom"], "quota": t["quota"], "vendus": tv, "retenus": th, "restant": (max(0, t["quota"] - tv - th) if t["quota"] else None)})
    return {"evenement_id": evt["id"], "quota": evt["quota"], "vendus": v, "retenus": h, "restant": max(0, evt["quota"] - v - h), "types": types}


# ── les règles d'achat ───────────────────────────────────────────────────────
def mode_achat(ctx, evt) -> str:
    """« obligatoire » : un compte est nécessaire ; « libre » : on peut acheter sans compte (avec des frais). La fiche de l'événement l'emporte sur le réglage général."""
    m = evt["achat"]
    if m == "general":
        m = ctx.reglage("compte_client")
    return "obligatoire" if m == "obligatoire" else "libre"


def verifier_promo(tx, code, evt, quantite_totale, sous_total):
    """Rend (remise, promo) ou lève ValueError dit en français. Le code se compare sans tenir compte de la casse."""
    code = str(code or "").strip().upper()
    if not code:
        return 0, None
    p = tx.execute("SELECT * FROM promos WHERE code = ?", (code,)).fetchone()
    if not p:
        raise ValueError("code promo inconnu")
    p = dict(p)
    if not p["actif"]:
        raise ValueError("ce code promo n'est plus actif")
    if p["evenement_id"] and p["evenement_id"] != evt["id"]:
        raise ValueError("ce code promo ne s'applique pas à cet événement")
    if p["fin"] and p["fin"] < aujourdhui():
        raise ValueError("ce code promo a expiré")
    if p["max_usages"]:
        en_cours = tx.execute("SELECT COUNT(*) FROM commandes WHERE promo_code = ? AND etat IN ('retenue','en_attente') AND expire_le > ?", (code, horloge())).fetchone()[0]
        if p["usages"] + en_cours >= p["max_usages"]:
            raise ValueError("ce code promo a atteint son nombre d'utilisations")
    remise = round(sous_total * p["valeur"] / 100) if p["type"] == "pct" else min(sous_total, p["valeur"] * quantite_totale)
    return max(0, int(remise)), p


def devis(ctx, tx, evt, lignes, *, canal, code_promo="", don=0, sans_compte=False) -> dict:
    """Chiffre un panier et vérifie qu'il peut se vendre. Rien n'est écrit. Les prix viennent de la base."""
    if evt["statut"] != "en vente":
        raise ValueError("cet événement n'est pas en vente (état : %s)" % evt["statut"])
    voulu = {}
    for x in lignes or []:
        tid, q = int((x or {}).get("type_billet_id", 0) or 0), r.entier((x or {}).get("quantite", 0), "quantité", 0, 200)
        if q:
            voulu[tid] = voulu.get(tid, 0) + q
    if not voulu:
        raise ValueError("le panier est vide")
    s = stock(tx, evt)
    total_places = sum(voulu.values())
    if total_places > s["restant"]:
        raise ValueError("il ne reste que %d place(s)" % s["restant"])
    out, sous_total = [], 0
    for tid, q in voulu.items():
        t = r.ligne(tx, "types_billets", tid)
        if not t or t["evenement_id"] != evt["id"]:
            raise ValueError("ce billet n'existe pas pour cet événement")
        if canal != "titulaire":
            if canal not in t["canaux"].split(","):
                raise ValueError("« %s » ne se vend pas par ce canal" % t["nom"])
            if not t["visible"] and canal == "boutique":
                raise ValueError("« %s » n'est pas proposé" % t["nom"])
            if t["ouverture"] and aujourdhui() < t["ouverture"]:
                raise ValueError("« %s » n'est pas encore en vente" % t["nom"])
            if t["fermeture"] and aujourdhui() > t["fermeture"]:
                raise ValueError("la vente de « %s » est terminée" % t["nom"])
        st = [x for x in s["types"] if x["id"] == tid][0]
        if st["restant"] is not None and q > st["restant"]:
            raise ValueError("« %s » : il ne reste que %d place(s)" % (t["nom"], st["restant"]))
        sous_total += t["prix"] * q
        out.append({"type_billet_id": tid, "nom": t["nom"], "prix": t["prix"], "quantite": q, "entrees": t["entrees"]})
    remise, promo = verifier_promo(tx, code_promo, evt, total_places, sous_total)
    don = r.entier(don or 0, "don")
    if don and ctx.reglage("titulaire_statut") != "association":
        raise ValueError("l'organisateur n'est pas une association : pas de don possible")
    frais = 0
    if sans_compte and canal == "boutique":
        if mode_achat(ctx, evt) == "obligatoire":
            raise ValueError("un compte est nécessaire pour acheter cet événement")
        frais = evt["frais_sans_compte"] if evt["frais_sans_compte"] is not None else int(ctx.reglage("frais_sans_compte"))
    return {"lignes": out, "places": total_places, "sous_total": sous_total, "remise": remise, "promo": promo["code"] if promo else "", "don": don, "frais": frais,
            "total": sous_total - remise + don + frais}


# ── l'attribution à un revendeur ─────────────────────────────────────────────
def trouver_revendeur(tx, code):
    c = str(code or "").strip().upper()
    x = tx.execute("SELECT * FROM revendeurs WHERE code = ?", (c,)).fetchone() if c else None
    return dict(x) if x else None


def formule_de_vente(tx, evt, rev, quantite):
    """Quelle formule rémunère CE revendeur pour CET événement ? Rend (formule_id, motif_si_aucune). Un indépendant : sa première affectation qui a encore de la place ;
    un artiste vendeur : la formule de son passage."""
    if rev["type"] == "artiste":
        p = tx.execute("SELECT p.formule_id FROM passages p JOIN formules f ON f.id = p.formule_id WHERE p.evenement_id = ? AND p.artiste_id = ? AND f.role = 'artiste' ORDER BY p.ordre", (evt["id"], rev["artiste_id"])).fetchone()
        return (p[0], "") if p else (None, "cet artiste ne joue pas à cet événement avec une formule qui vend")
    deja = tx.execute("SELECT COUNT(*) FROM billets WHERE revendeur_id = ? AND evenement_id = ? AND etat = 'valide'", (rev["id"], evt["id"])).fetchone()[0]
    deja += tx.execute("SELECT COALESCE(SUM(l.quantite),0) FROM lignes_commande l JOIN commandes c ON c.id = l.commande_id WHERE c.revendeur_id = ? AND c.evenement_id = ? AND c.etat IN ('retenue','en_attente') AND c.expire_le > ?",
                       (rev["id"], evt["id"], horloge())).fetchone()[0]
    affs = tx.execute("SELECT * FROM affectations WHERE evenement_id = ? AND revendeur_id = ? ORDER BY id", (evt["id"], rev["id"])).fetchall()
    if not affs:
        return None, "ce revendeur n'est pas affecté à cet événement"
    for a in affs:
        if not a["quota"] or deja + quantite <= a["quota"]:
            return a["formule_id"], ""
    return None, "le quota de ce revendeur est atteint"


def formule_pour(tx, evenement_id, formule_id):
    """La formule telle qu'elle vaut pour cet événement : figée si l'événement a déjà des ventes et que la formule a changé depuis."""
    f = tx.execute("SELECT contenu FROM formules_figees WHERE evenement_id = ? AND formule_id = ?", (evenement_id, formule_id)).fetchone()
    if f:
        import json
        return json.loads(f[0])
    x = r.ligne(tx, "formules", formule_id)
    return x


def figer_formule(tx, formule_id):
    """Avant de modifier une formule : pour chaque événement qui a des ventes et s'en sert, on garde ses conditions d'origine."""
    import json
    f = r.ligne(tx, "formules", formule_id)
    if not f:
        return []
    evts = [x[0] for x in tx.execute("SELECT DISTINCT evenement_id FROM (SELECT evenement_id FROM affectations WHERE formule_id = ? UNION SELECT evenement_id FROM passages WHERE formule_id = ?) "
                                     "WHERE evenement_id IN (SELECT DISTINCT evenement_id FROM billets WHERE etat = 'valide')", (formule_id, formule_id)).fetchall()]
    figes = []
    for e in evts:
        if not tx.execute("SELECT 1 FROM formules_figees WHERE evenement_id = ? AND formule_id = ?", (e, formule_id)).fetchone():
            tx.execute("INSERT INTO formules_figees(evenement_id, formule_id, contenu) VALUES (?,?,?)", (e, formule_id, json.dumps(f, ensure_ascii=False)))
            figes.append(e)
    return figes


# ── la commission d'une vente ────────────────────────────────────────────────
def porteur_de(rev):
    return ("artiste", rev["artiste_id"]) if rev["type"] == "artiste" else ("revendeur", rev["id"])


def _valeur(ctx, formule, n):
    f = {k: formule[k] for k in ("role", "forfait", "com", "fixe", "palier", "palier_n", "palier_com")}
    f["palier"] = bool(f["palier"])
    return ctx.point("commission", {"formule": f, "places": int(n)})["valeur"]


def ecrire_commission(ctx, tx, cmd, evt, quantite, sens):
    """Écrit au registre ce que la vente (sens +1) ou son remboursement (sens -1) change à la commission du revendeur : la différence entre « avant » et « après »."""
    if not cmd["revendeur_id"] or not cmd["formule_id"]:
        return
    rev = r.ligne(tx, "revendeurs", cmd["revendeur_id"])
    f = formule_pour(tx, evt["id"], cmd["formule_id"])
    autres = tx.execute("SELECT COUNT(*) FROM billets WHERE revendeur_id = ? AND evenement_id = ? AND etat = 'valide' AND (commande_id IS NULL OR commande_id <> ?)", (rev["id"], evt["id"], cmd["id"])).fetchone()[0]
    avant, apres = (autres, autres + quantite) if sens > 0 else (autres + quantite, autres)
    p0, p1 = _valeur(ctx, f, avant), _valeur(ctx, f, apres)
    porteur, pid = porteur_de(rev)
    dispo = reg.disponible_apres(evt["date_iso"], int(ctx.reglage("retrait_delai_jours")))
    pre = "vente" if sens > 0 else "remb"
    rang = tx.execute("SELECT COUNT(*) FROM mouvements WHERE origine = ?", (cmd["ref"],)).fetchone()[0]       # une vente rejouée après un retour arrière écrit de NOUVELLES lignes
    for nature, cle_ in (("commission", "commission"), ("fixe", "fixe")):
        delta = p1[cle_] - p0[cle_]
        if delta:
            reg.ecrire(tx, porteur, pid, nature, delta, evenement_id=evt["id"], disponible_le=dispo, origine=cmd["ref"], cle="%s:%s:%s#%d" % (pre, cmd["ref"], nature, rang),
                       note="%s %s" % ("vente" if sens > 0 else "remboursement", cmd["ref"]), par=ctx.compte)


# ── clients, commandes, billets ──────────────────────────────────────────────
def client_pour(tx, nom, mail, sans_compte=True):
    mail = r.mail_valide(mail)
    if not mail:
        return None
    x = tx.execute("SELECT id FROM clients WHERE mail = ?", (mail,)).fetchone()
    if x:
        return x[0]
    return tx.execute("INSERT INTO clients(ref, nom, mail, compte) VALUES (?,?,?,?)", (ids.nouvelle_ref(tx, "client"), r.texte(nom, 120), mail, 0 if sans_compte else 1)).lastrowid


def creer_commande(ctx, tx, evt, lignes, *, canal, nom="", mail="", revendeur_code="", code_promo="", don=0, sans_compte=False, moyen="", par=""):
    d = devis(ctx, tx, evt, lignes, canal=canal, code_promo=code_promo, don=don, sans_compte=sans_compte)
    rev, formule_id, attribution = None, None, ""
    if revendeur_code:
        rev = trouver_revendeur(tx, revendeur_code)
        if not rev or not rev["actif"]:
            rev, attribution = None, "code inconnu ou revendeur suspendu : vente directe"
        else:
            formule_id, motif = formule_de_vente(tx, evt, rev, d["places"])
            if formule_id is None:
                rev, attribution = None, motif + " : vente directe"
            else:
                attribution = "attribuée à %s (%s)" % (rev["nom"], rev["code"])
    client = client_pour(tx, nom, mail, sans_compte) if mail else None
    minutes = int(ctx.reglage("reservation_minutes"))
    expire = horloge() + (DUREE_VIREMENT_S if moyen == "virement" else minutes * 60)
    ref = ids.nouvelle_ref(tx, "commande")
    cid = tx.execute("INSERT INTO commandes(ref, evenement_id, client_id, revendeur_id, canal, moyen, etat, sous_total, remise, don, frais, total, promo_code, nom, mail, attribution, formule_id, expire_le, par) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (ref, evt["id"], client, rev["id"] if rev else None, canal, moyen, "en_attente" if moyen == "virement" else "retenue", d["sous_total"], d["remise"], d["don"], d["frais"], d["total"],
                      d["promo"], r.texte(nom, 120), r.texte(mail, 160), attribution, formule_id, expire, par)).lastrowid
    for l in d["lignes"]:
        tx.execute("INSERT INTO lignes_commande(commande_id, type_billet_id, nom, prix, quantite, entrees) VALUES (?,?,?,?,?,?)", (cid, l["type_billet_id"], l["nom"], l["prix"], l["quantite"], l["entrees"]))
    return cid, d


def creer_billet(ctx, tx, evt, *, commande=None, ligne=None, type_billet=None, categorie="", nom="", mail="", revendeur_id=None, entrees=1):
    n = ids.suivant(tx, "billet:%d" % evt["id"])
    numero = "%s-%04d" % (bil.lettre_evenement(evt["id"]), n)
    tx.execute("INSERT INTO billets(ref, numero, commande_id, ligne_id, evenement_id, type_billet_id, categorie_invite, nom, mail, revendeur_id, entrees) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (ids.nouvelle_ref(tx, "billet"), numero, commande, ligne, evt["id"], type_billet, categorie, r.texte(nom, 120), r.texte(mail, 160), revendeur_id, entrees))
    return numero


def encaisser(ctx, tx, cmd, moyen, reference="", par=""):
    """La commande est PAYÉE : les billets naissent, la commission s'écrit, le code promo compte. Idempotent sur la référence du prestataire."""
    if reference:
        autre = tx.execute("SELECT id, ref FROM commandes WHERE reference_externe = ?", (reference,)).fetchone()
        if autre:
            if autre["id"] == cmd["id"]:
                return {"deja": True, "numeros": [b[0] for b in tx.execute("SELECT numero FROM billets WHERE commande_id = ? ORDER BY id", (cmd["id"],)).fetchall()]}
            raise ValueError("ce paiement (%s) est déjà rattaché à la commande %s" % (reference, autre["ref"]))
    if cmd["etat"] not in RETENANT:
        raise ValueError("cette commande n'est plus à payer (état : %s)" % cmd["etat"])
    evt = r.ligne(tx, "evenements", cmd["evenement_id"])
    qte = tx.execute("SELECT COALESCE(SUM(quantite),0) FROM lignes_commande WHERE commande_id = ?", (cmd["id"],)).fetchone()[0]
    if cmd["expire_le"] <= horloge():                                 # la réservation a expiré : les places ont pu repartir
        s = stock(tx, evt)
        if qte > s["restant"]:
            raise ValueError("la réservation a expiré et les places sont reparties")
    numeros = []
    for l in tx.execute("SELECT * FROM lignes_commande WHERE commande_id = ? ORDER BY id", (cmd["id"],)).fetchall():
        for _ in range(l["quantite"]):
            numeros.append(creer_billet(ctx, tx, evt, commande=cmd["id"], ligne=l["id"], type_billet=l["type_billet_id"], nom=cmd["nom"], mail=cmd["mail"], revendeur_id=cmd["revendeur_id"], entrees=l["entrees"]))
    ecrire_commission(ctx, tx, cmd, evt, qte, +1)
    if cmd["promo_code"]:
        tx.execute("UPDATE promos SET usages = usages + 1 WHERE code = ?", (cmd["promo_code"],))
    tx.execute("UPDATE commandes SET etat = 'payee', moyen = ?, payee_le = datetime('now'), reference_externe = ?, par = ? WHERE id = ?", (moyen or cmd["moyen"], reference or None, par, cmd["id"]))
    return {"deja": False, "numeros": numeros}


def rembourser(ctx, tx, cmd, motif=""):
    """Le remboursement : les billets s'annulent (donc les places reviennent), la commission s'annule par une ligne contraire. Le remboursement CHEZ le prestataire reste à faire (dit dans le retour)."""
    if cmd["etat"] != "payee":
        raise ValueError("seule une commande payée se rembourse (état : %s)" % cmd["etat"])
    evt = r.ligne(tx, "evenements", cmd["evenement_id"])
    qte = tx.execute("SELECT COUNT(*) FROM billets WHERE commande_id = ? AND etat = 'valide'", (cmd["id"],)).fetchone()[0]
    ecrire_commission(ctx, tx, cmd, evt, qte, -1)
    tx.execute("UPDATE billets SET etat = 'annule' WHERE commande_id = ?", (cmd["id"],))
    tx.execute("UPDATE commandes SET etat = 'remboursee', note = ? WHERE id = ?", (r.texte(motif, 200), cmd["id"]))
    return {"montant": cmd["total"], "chez_le_prestataire": cmd["moyen"] in MOYENS_PRESTATAIRE, "moyen": cmd["moyen"]}


def rejouer(ctx, tx, cmd):
    """Défait un remboursement : la commande redevient payée, ses billets valides, sa commission revient par de nouvelles lignes."""
    evt = r.ligne(tx, "evenements", cmd["evenement_id"])
    tx.execute("UPDATE billets SET etat = 'valide' WHERE commande_id = ?", (cmd["id"],))
    qte = tx.execute("SELECT COUNT(*) FROM billets WHERE commande_id = ? AND etat = 'valide'", (cmd["id"],)).fetchone()[0]
    ecrire_commission(ctx, tx, cmd, evt, qte, +1)
    tx.execute("UPDATE commandes SET etat = 'payee', note = '' WHERE id = ?", (cmd["id"],))


def expirer(tx) -> int:
    """Les commandes dont la réservation est écoulée libèrent leurs places (elles n'ont jamais fait de billets)."""
    return tx.execute("UPDATE commandes SET etat = 'expiree' WHERE etat IN ('retenue','en_attente') AND expire_le <= ?", (horloge(),)).rowcount
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : aujourdhui, retenus, vendus, stock, mode_achat, verifier_promo, devis, trouver_revendeur …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
