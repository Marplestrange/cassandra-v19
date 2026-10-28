# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #8a44a5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le registre des mouvements (le « portefeuille » des revendeurs et des artistes) et les demandes de retrait.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8a44a5 ▼▼▼
"""Billetterie : le registre des mouvements (le « portefeuille » des revendeurs et des artistes) et les demandes de retrait.

Règles d'or :
  - le registre est en ÉCRITURE SEULE (les déclencheurs de la base le refusent) : une erreur se corrige par une ligne contraire, jamais par une retouche ;
  - Cassandra ne détient aucun fonds : le portefeuille est ce que l'organisateur DOIT au porteur, le versement se fait hors de Cassandra puis s'enregistre ;
  - un montant positif n'est retirable qu'à partir de sa date de disponibilité (le jour de l'événement + le délai du réglage) ; une ligne négative compte tout de suite ;
  - écrire deux fois le même fait n'écrit qu'une ligne (la clé d'idempotence), parce qu'un paiement qui revient deux fois ne doit pas payer deux fois.
L'argent est en centimes entiers.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import CN_identifiants as ids
from . import CN_regles as r

PORTEURS = ("revendeur", "artiste")
NATURES_DUES = ("commission", "fixe", "forfait")
NATURES_MANUELLES = NATURES_DUES + ("ajustement",)
ETATS_OUVERTS = ("demandee", "validee")


def disponible_apres(date_evenement: str, delai_jours: int) -> str:
    """La date à partir de laquelle une commission d'un événement est retirable : le jour de l'événement + le délai du réglage ('' si l'événement n'a pas de date : tout de suite)."""
    if not date_evenement:
        return ""
    return (date.fromisoformat(date_evenement) + timedelta(days=int(delai_jours))).isoformat()


def _porteur(tx, porteur, porteur_id):
    if porteur not in PORTEURS:
        raise ValueError("porteur : %s" % " ou ".join(PORTEURS))
    ligne = r.ligne(tx, "revendeurs" if porteur == "revendeur" else "artistes", porteur_id)
    if not ligne:
        raise ValueError("%s introuvable" % porteur)
    return ligne


def ecrire(tx, porteur, porteur_id, nature, montant, *, evenement_id=None, disponible_le="", origine="", cle=None, note="", par=""):
    """Écrit UNE ligne du registre et rend son identifiant. Si `cle` a déjà servi, rend la ligne déjà écrite sans en écrire une seconde."""
    if cle:
        deja = tx.execute("SELECT id FROM mouvements WHERE cle = ?", (cle,)).fetchone()
        if deja:
            return deja[0]
    _porteur(tx, porteur, porteur_id)
    montant = r.entier(montant, "montant", -10 ** 9)
    if montant == 0:
        raise ValueError("un mouvement de zéro n'a pas de sens")
    return tx.execute("INSERT INTO mouvements(ref, porteur, porteur_id, evenement_id, nature, montant, disponible_le, origine, cle, note, par) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (ids.nouvelle_ref(tx, "mouvement"), porteur, int(porteur_id), evenement_id, nature, montant, r.jour(disponible_le, "date de disponibilité"),
                       str(origine)[:80], cle, str(note)[:200], str(par)[:80])).lastrowid


def soldes(tx, porteur, porteur_id, au=""):
    """Ce qui est dû au porteur : retirable aujourd'hui, en attente de sa date, et ce qui est déjà parti en demande de retrait ou versé."""
    au = au or date.today().isoformat()
    eff = "(CASE WHEN COALESCE(e.dispo_min, '') > m.disponible_le THEN e.dispo_min ELSE m.disponible_le END)"       # un événement reporté repousse la disponibilité de ses lignes
    ligne = tx.execute("SELECT COALESCE(SUM(CASE WHEN %s <= ? THEN m.montant ELSE 0 END), 0) AS disponible, "
                       "COALESCE(SUM(CASE WHEN %s > ? THEN m.montant ELSE 0 END), 0) AS en_attente, COALESCE(SUM(m.montant), 0) AS du "
                       "FROM mouvements m LEFT JOIN evenements e ON e.id = m.evenement_id WHERE m.porteur = ? AND m.porteur_id = ?" % (eff, eff), (au, au, porteur, int(porteur_id))).fetchone()
    en_cours = tx.execute("SELECT COALESCE(SUM(montant),0) FROM retraits WHERE porteur = ? AND porteur_id = ? AND etat IN ('demandee','validee')", (porteur, int(porteur_id))).fetchone()[0]
    verse = tx.execute("SELECT COALESCE(SUM(montant),0) FROM retraits WHERE porteur = ? AND porteur_id = ? AND etat = 'payee'", (porteur, int(porteur_id))).fetchone()[0]
    return {"au": au, "disponible": ligne["disponible"], "en_attente": ligne["en_attente"], "du": ligne["du"], "retraits_en_cours": en_cours, "verse": verse}


def brancher(ctx, db):
    def portefeuille(c, porteur="revendeur", porteur_id=0, au=""):
        with db.transaction() as tx:
            p = _porteur(tx, porteur, porteur_id)
            s = soldes(tx, porteur, porteur_id, au)
            lignes = [dict(x) for x in tx.execute("SELECT * FROM mouvements WHERE porteur = ? AND porteur_id = ? ORDER BY id DESC LIMIT 50", (porteur, int(porteur_id))).fetchall()]
        s.update({"porteur": porteur, "porteur_id": int(porteur_id), "nom": p.get("nom") or p.get("scene"), "ref": p["ref"], "mouvements": lignes})
        return s

    def mouvements(c, porteur="", porteur_id=0, evenement_id=0, limite=100):
        sql, p = "SELECT * FROM mouvements WHERE 1 = 1", []
        if porteur:
            sql, p = sql + " AND porteur = ?", p + [porteur]
        if porteur_id:
            sql, p = sql + " AND porteur_id = ?", p + [int(porteur_id)]
        if evenement_id:
            sql, p = sql + " AND evenement_id = ?", p + [int(evenement_id)]
        return {"mouvements": db.lire(sql + " ORDER BY id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 100), 1000)),))}

    def retraits(c, etat="", porteur="", porteur_id=0):
        sql, p = "SELECT * FROM retraits WHERE 1 = 1", []
        for col, v in (("etat", etat), ("porteur", porteur), ("porteur_id", int(porteur_id or 0))):
            if v:
                sql, p = sql + " AND %s = ?" % col, p + [v]
        return {"retraits": db.lire(sql + " ORDER BY id DESC LIMIT 500", tuple(p))}

    # ── une provision à la main (le titulaire fixe un montant dû) ─────────────
    def provision(c, porteur="revendeur", porteur_id=0, nature="commission", montant=0, evenement_id=0, disponible_le="", note=""):
        if nature not in NATURES_MANUELLES:
            raise ValueError("nature : %s" % ", ".join(NATURES_MANUELLES))
        montant = r.entier(montant, "montant", -10 ** 9)
        if montant < 0 and nature != "ajustement":
            raise ValueError("un montant négatif est un ajustement : écrivez-le comme tel")
        with db.transaction() as tx:
            if evenement_id and not r.ligne(tx, "evenements", evenement_id):
                raise ValueError("événement introuvable")
            mid = ecrire(tx, porteur, porteur_id, nature, montant, evenement_id=int(evenement_id) or None, disponible_le=disponible_le, origine="main", note=note, par=ctx.compte)
            ref = tx.execute("SELECT ref FROM mouvements WHERE id = ?", (mid,)).fetchone()[0]
        return {"mouvement_id": mid, "ref": ref, "porteur": porteur, "porteur_id": int(porteur_id), "montant": montant, "disponible_le": disponible_le}

    def prouver_provision(c, res):
        return bool(db.lire("SELECT 1 FROM mouvements WHERE id = ?", (res["mouvement_id"],)))

    def defaire_provision(c, res):
        with db.transaction() as tx:
            ecrire(tx, res["porteur"], res["porteur_id"], "ajustement", -res["montant"], disponible_le=res["disponible_le"], origine="défait:" + res["ref"],
                   cle="defait:" + res["ref"], note="annulation de " + res["ref"], par=ctx.compte)

    # ── les retraits ──────────────────────────────────────────────────────────
    def _retrait(tx, rid):
        x = r.ligne(tx, "retraits", rid)
        if not x:
            raise ValueError("demande de retrait introuvable")
        return x

    def demander(c, porteur="revendeur", porteur_id=0, montant=0, au=""):
        montant = r.entier(montant, "montant", 1)
        seuil = int(ctx.reglage("retrait_seuil"))
        with db.transaction() as tx:
            p = _porteur(tx, porteur, porteur_id)
            if porteur == "revendeur" and not p["actif"]:
                raise ValueError("ce revendeur est suspendu")
            if montant < seuil:
                raise ValueError("le retrait minimal est de %d centimes" % seuil)
            s = soldes(tx, porteur, porteur_id, au)
            if montant > s["disponible"]:
                raise ValueError("%d centimes seulement sont retirables aujourd'hui (le reste attend la date de disponibilité ou est déjà demandé)" % max(0, s["disponible"]))
            ref = ids.nouvelle_ref(tx, "retrait")
            rid = tx.execute("INSERT INTO retraits(ref, porteur, porteur_id, montant, par) VALUES (?,?,?,?,?)", (ref, porteur, int(porteur_id), montant, ctx.compte)).lastrowid
            ecrire(tx, porteur, porteur_id, "retrait", -montant, origine=ref, cle="retrait:" + ref, note="demande de retrait", par=ctx.compte)
        return {"id": rid, "ref": ref, "porteur": porteur, "porteur_id": int(porteur_id), "montant": montant}

    def prouver_demander(c, res):
        x = db.lire("SELECT etat FROM retraits WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "demandee"

    def _rendre(tx, x, nouvel_etat, motif, cle, note):
        """Le retrait ne se fera pas : la réserve revient au portefeuille par une ligne CONTRAIRE (le registre ne se retouche pas)."""
        tx.execute("UPDATE retraits SET etat = ?, motif = ?, traite_le = datetime('now'), par = ? WHERE id = ?", (nouvel_etat, motif, ctx.compte, x["id"]))
        ecrire(tx, x["porteur"], x["porteur_id"], "reprise", x["montant"], origine=x["ref"], cle=cle, note=note, par=ctx.compte)

    def defaire_demander(c, res):
        with db.transaction() as tx:
            x = _retrait(tx, res["id"])
            if x["etat"] in ("demandee", "validee"):
                _rendre(tx, x, "refusee", "demande annulée", "annule:" + x["ref"], "demande de retrait annulée")

    def valider(c, id=0):
        with db.transaction() as tx:
            x = _retrait(tx, id)
            if x["etat"] != "demandee":
                raise ValueError("seule une demande en attente se valide (état : %s)" % x["etat"])
            tx.execute("UPDATE retraits SET etat = 'validee', traite_le = datetime('now'), par = ? WHERE id = ?", (ctx.compte, x["id"]))
        return {"id": x["id"], "ref": x["ref"]}

    def prouver_valider(c, res):
        x = db.lire("SELECT etat FROM retraits WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "validee"

    def defaire_valider(c, res):
        db.ecrire("UPDATE retraits SET etat = 'demandee', traite_le = '' WHERE id = ? AND etat = 'validee'", (res["id"],))

    def payer(c, id=0, reference_virement=""):
        with db.transaction() as tx:
            x = _retrait(tx, id)
            if x["etat"] != "validee":
                raise ValueError("on n'enregistre un versement que pour une demande validée (état : %s)" % x["etat"])
            tx.execute("UPDATE retraits SET etat = 'payee', reference_virement = ?, traite_le = datetime('now'), par = ? WHERE id = ?", (str(reference_virement)[:80], ctx.compte, x["id"]))
        return {"id": x["id"], "ref": x["ref"]}

    def prouver_payer(c, res):
        x = db.lire("SELECT etat FROM retraits WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "payee"

    def defaire_payer(c, res):
        db.ecrire("UPDATE retraits SET etat = 'validee', reference_virement = '' WHERE id = ? AND etat = 'payee'", (res["id"],))

    def refuser(c, id=0, motif=""):
        with db.transaction() as tx:
            x = _retrait(tx, id)
            if x["etat"] not in ETATS_OUVERTS:
                raise ValueError("seule une demande ouverte se refuse (état : %s)" % x["etat"])
            _rendre(tx, x, "refusee", str(motif)[:200] or "refusée", "refus:" + x["ref"], "demande de retrait refusée")
        return {"id": x["id"], "ref": x["ref"], "etat_avant": x["etat"]}

    def prouver_refuser(c, res):
        x = db.lire("SELECT etat FROM retraits WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "refusee"

    def defaire_refuser(c, res):
        with db.transaction() as tx:
            x = _retrait(tx, res["id"])
            if x["etat"] != "refusee":
                return
            s = soldes(tx, x["porteur"], x["porteur_id"])
            if x["montant"] > s["disponible"]:
                raise ValueError("le portefeuille ne couvre plus ce retrait : on ne peut pas rouvrir la demande")
            tx.execute("UPDATE retraits SET etat = ?, motif = '' WHERE id = ?", (res["etat_avant"], x["id"]))
            ecrire(tx, x["porteur"], x["porteur_id"], "retrait", -x["montant"], origine=x["ref"], cle="rouvert:%s:%d" % (x["ref"], tx.execute("SELECT COUNT(*) FROM mouvements WHERE origine = ?", (x["ref"],)).fetchone()[0]),
                   note="demande de retrait rouverte", par=ctx.compte)

    ctx.implementer("portefeuille", portefeuille)
    ctx.implementer("mouvements", mouvements)
    ctx.implementer("retraits", retraits)
    ctx.implementer("provision", provision, prouver_provision, defaire_provision, simuler=lambda x, montant=0, **_: "inscrirait %s centimes au registre" % montant)
    ctx.implementer("retrait_demander", demander, prouver_demander, defaire_demander, simuler=lambda x, montant=0, **_: "demanderait un retrait de %s centimes" % montant)
    ctx.implementer("retrait_valider", valider, prouver_valider, defaire_valider, simuler=lambda x, id=0, **_: "validerait la demande de retrait %s" % id)
    ctx.implementer("retrait_payer", payer, prouver_payer, defaire_payer, simuler=lambda x, id=0, **_: "enregistrerait le versement de la demande %s" % id)
    ctx.implementer("retrait_refuser", refuser, prouver_refuser, defaire_refuser, simuler=lambda x, id=0, **_: "refuserait la demande de retrait %s" % id)
    return {"demander": demander, "prouver": prouver_demander, "defaire": defaire_demander}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : disponible_apres, _porteur, ecrire, soldes, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
