# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #638c9e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : « Mon espace » du revendeur et de l'artiste.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=638c9e ▼▼▼
"""Billetterie : « Mon espace » du revendeur et de l'artiste.

Un revendeur ou un artiste a un COMPTE (le champ « compte » de sa fiche, posé par le titulaire). Avec lui il voit ses propres chiffres et rien d'autre :
  - le revendeur : son code, les événements où il est affecté (formule, quota, ce qu'il a vendu), ses ventes, son portefeuille, ses retraits, et il demande un retrait ;
  - l'artiste : son programme (événements, ordre et heure de passage, durée), sa formule, son portefeuille et ses retraits ; s'il vend lui-même, ses ventes aussi.
Le compte vient TOUJOURS de l'acte (jamais d'un paramètre) : on ne peut pas demander la fiche d'un autre, ni forger une date de retrait.
Le nom de l'acheteur est montré à celui qui a vendu ; son courriel ne l'est pas.
"""
from __future__ import annotations

from . import CN_boutique as boutique
from . import CN_regles as r


def brancher(ctx, db, retrait):
    def moi(tx, table):
        if not ctx.compte:
            raise ValueError("aucun compte : connectez-vous")
        x = tx.execute("SELECT * FROM %s WHERE compte = ? AND compte <> ''" % table, (ctx.compte,)).fetchone()
        if not x:
            raise ValueError("aucune fiche %s n'est liée à votre compte : demandez au titulaire de la relier" % ("de revendeur" if table == "revendeurs" else "d'artiste"))
        return dict(x)

    def portefeuille(tx, porteur, pid):
        from . import CN_registre as reg
        s = reg.soldes(tx, porteur, pid)
        return {"disponible": s["disponible"], "en_attente": s["en_attente"], "du": s["du"], "retraits_en_cours": s["retraits_en_cours"], "verse": s["verse"],
                "mouvements": [dict(x) for x in tx.execute("SELECT ref, nature, montant, disponible_le, note, cree_le FROM mouvements WHERE porteur = ? AND porteur_id = ? ORDER BY id DESC LIMIT 50", (porteur, pid)).fetchall()],
                "retraits": [dict(x) for x in tx.execute("SELECT ref, montant, etat, motif, demande_le, traite_le FROM retraits WHERE porteur = ? AND porteur_id = ? ORDER BY id DESC LIMIT 50", (porteur, pid)).fetchall()]}

    def ventes_de(tx, rid, limite=200):
        out = []
        for cmd in tx.execute("SELECT c.*, e.ref AS eref, e.nom AS enom FROM commandes c JOIN evenements e ON e.id = c.evenement_id WHERE c.revendeur_id = ? ORDER BY c.id DESC LIMIT ?", (rid, limite)).fetchall():
            billets = tx.execute("SELECT COUNT(*) FROM billets WHERE commande_id = ? AND etat = 'valide'", (cmd["id"],)).fetchone()[0]
            com = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE origine = ? AND porteur = 'revendeur' AND porteur_id = ?", (cmd["ref"], rid)).fetchone()[0]
            out.append({"commande": cmd["ref"], "evenement": cmd["enom"], "evenement_ref": cmd["eref"], "etat": cmd["etat"], "billets": billets, "total": cmd["total"],
                        "acheteur": cmd["nom"], "commission": com, "date": cmd["payee_le"] or ""})
        return out

    # ── le profil : ce que le titulaire doit avoir pour payer et facturer ───────
    def iban_propre(texte):
        """Un IBAN : espaces retirés, majuscules, longueur et clé de contrôle (modulo 97) vérifiées. Rend l'IBAN normalisé ou lève ValueError."""
        t = "".join(str(texte).split()).upper()
        if not t:
            return ""
        if not t.isalnum() or not 15 <= len(t) <= 34 or not t[:2].isalpha() or not t[2:4].isdigit():
            raise ValueError("cet IBAN n'a pas la forme d'un IBAN")
        if int("".join(str(int(c, 36)) for c in t[4:] + t[:4])) % 97 != 1:
            raise ValueError("la clé de contrôle de cet IBAN est fausse : vérifiez-le")
        return t

    def masque(iban):
        return ("%s •••• %s" % (iban[:4], iban[-4:])) if iban else ""

    def profil_de(tx, genre, f):
        """Le profil d'une fiche, avec ce qui manque. L'IBAN se rend en clair à la personne (`clair=True` plus bas), jamais ailleurs."""
        iban = ctx.dechiffrer(f["iban_chiffre"], "iban") if f["iban_chiffre"] else ""
        manque = []
        nom = f["nom"] if genre == "revendeur" else f["scene"]
        if not nom:
            manque.append("nom")
        if not f["mail"]:
            manque.append("courriel")
        if not iban:
            manque.append("IBAN (sans lui, pas de retrait)")
        if genre == "revendeur" and f["mode_facturation"] == "mandat" and not (f["adresse"] and f["code_postal"] and f["ville"]):
            manque.append("adresse complète (nécessaire à l'auto-facture établie en votre nom)")
        if f["statut"] != "Particulier" and not f["siret"]:
            manque.append("SIRET (structure professionnelle)")
        sortie = {"ref": f["ref"], "nom": nom, "statut": f["statut"], "mail": f["mail"], "tel": f["tel"], "siret": f["siret"], "tva": f["tva"], "adresse": f["adresse"], "code_postal": f["code_postal"], "ville": f["ville"],
                  "pays": f["pays"], "iban": iban, "iban_masque": masque(iban), "manque": manque, "complet": not manque}
        if genre == "revendeur":
            sortie["mode_facturation"] = f["mode_facturation"]
        return sortie

    CHAMPS_PROFIL = ("mail", "tel", "siret", "tva", "adresse", "code_postal", "ville", "pays")

    def enregistrer_profil(genre, table, c, champs):
        with db.transaction() as tx:
            f = moi(tx, table)
            avant = {k: f[k] for k in CHAMPS_PROFIL + ("iban_chiffre",) + (("mode_facturation",) if genre == "revendeur" else ())}
            maj = {}
            for k in CHAMPS_PROFIL:
                if k in champs and champs[k] is not None:
                    maj[k] = r.mail_valide(champs[k]) if k == "mail" else r.texte(champs[k], 200)
            if "pays" in maj:
                maj["pays"] = (maj["pays"] or "FR").upper()[:2] or "FR"
            if "iban" in champs and champs["iban"] is not None:
                n = iban_propre(champs["iban"])
                maj["iban_chiffre"] = ctx.chiffrer(n, "iban") if n else ""
            if genre == "revendeur" and champs.get("mode_facturation") is not None:
                if champs["mode_facturation"] not in ("mandat", "propre"):
                    raise ValueError("facturation : « mandat » (le titulaire établit l'auto-facture en votre nom) ou « propre » (vous facturez vous-même)")
                maj["mode_facturation"] = champs["mode_facturation"]
            if not maj:
                raise ValueError("rien à changer")
            tx.execute("UPDATE %s SET %s WHERE id = ?" % (table, ", ".join("%s = ?" % k for k in maj)), tuple(maj.values()) + (f["id"],))
            apres = dict(tx.execute("SELECT * FROM %s WHERE id = ?" % table, (f["id"],)).fetchone())
            nouveau = profil_de(tx, genre, apres)
            nouveau.pop("iban", None)                                             # le résultat d'une écriture va au journal : jamais l'IBAN en clair
            return {"id": f["id"], "table": table, "avant": avant, "profil": nouveau}

    def defaire_profil(c, res):
        a = res["avant"]
        db.ecrire("UPDATE %s SET %s WHERE id = ?" % (res["table"], ", ".join("%s = ?" % k for k in a)), tuple(a.values()) + (res["id"],))

    def mon_profil_revendeur(c):
        with db.transaction() as tx:
            return profil_de(tx, "revendeur", moi(tx, "revendeurs"))

    def mon_profil_revendeur_save(c, mail=None, tel=None, siret=None, tva=None, adresse=None, code_postal=None, ville=None, pays=None, iban=None, mode_facturation=None):
        return enregistrer_profil("revendeur", "revendeurs", c, dict(mail=mail, tel=tel, siret=siret, tva=tva, adresse=adresse, code_postal=code_postal, ville=ville, pays=pays, iban=iban, mode_facturation=mode_facturation))

    def mon_profil_artiste(c):
        with db.transaction() as tx:
            return profil_de(tx, "artiste", moi(tx, "artistes"))

    def mon_profil_artiste_save(c, mail=None, tel=None, siret=None, tva=None, adresse=None, code_postal=None, ville=None, pays=None, iban=None):
        return enregistrer_profil("artiste", "artistes", c, dict(mail=mail, tel=tel, siret=siret, tva=tva, adresse=adresse, code_postal=code_postal, ville=ville, pays=pays, iban=iban))

    def prouver_profil(c, res):
        return bool(db.lire("SELECT 1 FROM %s WHERE id = ?" % res["table"], (res["id"],)))

    def profil_vu_par_le_titulaire(c, porteur="revendeur", id=0):
        """Le résumé d'un profil pour le titulaire : complet ou « manque : … », l'IBAN seulement par sa fin."""
        with db.transaction() as tx:
            f = r.ligne(tx, "revendeurs" if porteur == "revendeur" else "artistes", id)
            if not f:
                raise ValueError("fiche introuvable")
            p = profil_de(tx, porteur, f)
        p.pop("iban", None)
        return p

    def exiger_iban(tx, table):
        f = moi(tx, table)
        if not f["iban_chiffre"]:
            raise ValueError("renseignez votre IBAN dans « Mon profil » avant de demander un retrait : c'est là que le versement est fait")

    # ── le revendeur ─────────────────────────────────────────────────────────
    def mon_revendeur(c):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
            aff = []
            for a in tx.execute("SELECT f.*, e.ref AS eref, e.nom AS enom, e.date_iso, e.statut AS estatut, fo.nom AS formule FROM affectations f JOIN evenements e ON e.id = f.evenement_id "
                                "JOIN formules fo ON fo.id = f.formule_id WHERE f.revendeur_id = ? ORDER BY e.date_iso, f.id", (rv["id"],)).fetchall():
                vendus = tx.execute("SELECT COUNT(*) FROM billets WHERE revendeur_id = ? AND evenement_id = ? AND etat = 'valide'", (rv["id"], a["evenement_id"])).fetchone()[0]
                gagne = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE porteur = 'revendeur' AND porteur_id = ? AND evenement_id = ? AND nature IN ('commission','fixe')", (rv["id"], a["evenement_id"])).fetchone()[0]
                aff.append({"evenement": a["enom"], "evenement_ref": a["eref"], "date": a["date_iso"], "etat": a["estatut"], "formule": a["formule"], "quota": a["quota"],
                            "vendus": vendus, "restant": max(0, a["quota"] - vendus) if a["quota"] else None, "commission": gagne})
            out = {"ref": rv["ref"], "nom": rv["nom"], "code": rv["code"], "actif": bool(rv["actif"]), "motif_suspension": rv["suspendu_motif"], "type": rv["type"], "affectations": aff,
                   "portefeuille": portefeuille(tx, "revendeur", rv["id"]), "ventes": ventes_de(tx, rv["id"], 50)}
            out["lien_de_vente"] = "?r=" + rv["code"]
        return out

    def mes_ventes(c, limite=200):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
            return {"ventes": ventes_de(tx, rv["id"], max(1, min(int(limite or 200), 500)))}

    def retrait_revendeur(c, montant=0):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
            exiger_iban(tx, "revendeurs")
        return retrait["demander"](c, "revendeur", rv["id"], montant)

    # ── l'artiste ────────────────────────────────────────────────────────────
    def mon_artiste(c):
        with db.transaction() as tx:
            a = moi(tx, "artistes")
            f = r.ligne(tx, "formules", a["formule_id"]) if a["formule_id"] else None
            programme = []
            for e in tx.execute("SELECT DISTINCT e.* FROM passages p JOIN evenements e ON e.id = p.evenement_id WHERE p.artiste_id = ? ORDER BY e.date_iso, e.id", (a["id"],)).fetchall():
                tous = [dict(x) for x in tx.execute("SELECT id, artiste_id, ordre, duree FROM passages WHERE evenement_id = ? ORDER BY ordre", (e["id"],)).fetchall()]
                heures = boutique.horaires(e["debut"], tous, e["pause"])
                for p, h in zip(tous, heures):
                    if p["artiste_id"] == a["id"]:
                        programme.append({"evenement": e["nom"], "evenement_ref": e["ref"], "date": e["date_iso"], "etat": e["statut"], "ordre": p["ordre"], "sur": len(tous),
                                          "heure": h, "duree": p["duree"], "portes": e["portes"]})
            out = {"ref": a["ref"], "scene": a["scene"], "genre": a["genre"], "rider": a["rider"],
                   "formule": ({"nom": f["nom"], "forfait": f["forfait"], "commission": f["com"], "fixe": f["fixe"]} if f else None),
                   "programme": programme, "portefeuille": portefeuille(tx, "artiste", a["id"]), "vend": bool(a["vend"])}
            if a["vend"] and a["revendeur_id"]:
                rv = r.ligne(tx, "revendeurs", a["revendeur_id"])
                out["vente"] = {"code": rv["code"], "lien_de_vente": "?r=" + rv["code"], "ventes": ventes_de(tx, rv["id"], 50), "portefeuille": portefeuille(tx, "revendeur", rv["id"])}
        return out

    def retrait_artiste(c, montant=0):
        with db.transaction() as tx:
            a = moi(tx, "artistes")
            exiger_iban(tx, "artistes")
        return retrait["demander"](c, "artiste", a["id"], montant)

    ctx.implementer("mon_profil_revendeur", mon_profil_revendeur)
    ctx.implementer("mon_profil_revendeur_save", mon_profil_revendeur_save, prouver_profil, defaire_profil, simuler=lambda x, **_: "modifierait mon profil de revendeur")
    ctx.implementer("mon_profil_artiste", mon_profil_artiste)
    ctx.implementer("mon_profil_artiste_save", mon_profil_artiste_save, prouver_profil, defaire_profil, simuler=lambda x, **_: "modifierait mon profil d'artiste")
    ctx.implementer("profil_vu", profil_vu_par_le_titulaire)
    ctx.implementer("mon_revendeur", mon_revendeur)
    ctx.implementer("mes_ventes", mes_ventes)
    ctx.implementer("mon_retrait_revendeur", retrait_revendeur, retrait["prouver"], retrait["defaire"], simuler=lambda x, montant=0, **_: "demanderait un retrait de %s centimes" % montant)
    ctx.implementer("mon_artiste", mon_artiste)
    ctx.implementer("mon_retrait_artiste", retrait_artiste, retrait["prouver"], retrait["defaire"], simuler=lambda x, montant=0, **_: "demanderait un retrait de %s centimes" % montant)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
