# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #7182f9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les textes légaux de la boutique (conditions générales de vente, mentions légales, politique de confidentialité).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7182f9 ▼▼▼
"""Billetterie : les textes légaux de la boutique (conditions générales de vente, mentions légales, politique de confidentialité).

Le titulaire écrit ses textes ; la billetterie les publie, les versionne, et exige l'acceptation des conditions de vente avant toute commande dès qu'elles existent.
Le « modèle » n'est qu'un SQUELETTE à compléter avec les données du titulaire : il ne prétend rien de juridique à la place de l'organisateur, et le dit en tête (à faire relire).
"""
from __future__ import annotations

from . import CN_regles as r

TITRES = {"cgv": "Conditions générales de vente", "mentions": "Mentions légales", "confidentialite": "Politique de confidentialité"}


def brancher(ctx, db):
    def lire_texte(cle):
        x = db.lire("SELECT * FROM pages_legales WHERE cle = ?", (cle,))
        return x[0] if x else {"cle": cle, "titre": TITRES[cle], "texte": "", "version": 0, "maj_le": ""}

    def pages(c):
        return {"pages": [dict(lire_texte(k), publiee=bool(lire_texte(k)["texte"].strip())) for k in TITRES]}

    def enregistrer(c, cle="", texte=""):
        if cle not in TITRES:
            raise ValueError("page : %s" % ", ".join(TITRES))
        texte = str(texte or "").strip()
        if len(texte) > 60000:
            raise ValueError("le texte dépasse 60 000 caractères")
        avant = lire_texte(cle)
        if texte == avant["texte"]:
            raise ValueError("le texte n'a pas changé")
        with db.transaction() as tx:
            tx.execute("INSERT INTO pages_legales(cle, titre, texte, version) VALUES (?,?,?,1) ON CONFLICT(cle) DO UPDATE SET texte = excluded.texte, version = pages_legales.version + 1, maj_le = datetime('now')", (cle, TITRES[cle], texte))
        return {"cle": cle, "avant": avant, "version": avant["version"] + 1}

    def prouver(c, res):
        return lire_texte(res["cle"])["version"] == res["version"]

    def defaire(c, res):
        a = res["avant"]
        with db.transaction() as tx:
            if a["version"] == 0:
                tx.execute("DELETE FROM pages_legales WHERE cle = ?", (res["cle"],))
            else:
                tx.execute("UPDATE pages_legales SET texte = ?, version = ?, maj_le = ? WHERE cle = ?", (a["texte"], a["version"], a["maj_le"], res["cle"]))

    def modele(c, cle=""):
        if cle not in TITRES:
            raise ValueError("page : %s" % ", ".join(TITRES))
        nom, adr, mail, siret = (ctx.reglage(k) or "[à compléter]" for k in ("titulaire_nom", "titulaire_adresse", "titulaire_mail", "titulaire_siret"))
        tete = "[SQUELETTE À COMPLÉTER ET À FAIRE RELIRE : ce texte ne tient lieu d'aucun avis juridique. Supprimez cette ligne une fois relu.]\n\n"
        corps = {
            "cgv": "1. Vendeur\n%s, %s. SIRET : %s. Contact : %s.\n\n2. Objet\nLes présentes conditions régissent la vente de billets pour les événements organisés par le vendeur.\n\n3. Prix et paiement\nLes prix sont en euros. [Précisez la TVA : non applicable, ou taux.] Le paiement se fait en ligne ou par virement ; les places sont retenues pendant [durée] le temps du paiement.\n\n"
                   "4. Billets\nChaque billet porte un QR code personnel, à présenter à l'entrée. [Précisez : nominatif ou non, revente, transfert.]\n\n5. Annulation, report, remboursement\n[Précisez les cas : annulation de l'événement par l'organisateur (remboursement), report (billets valables, remboursement sur demande), absence de l'acheteur.]\n\n"
                   "6. Droit de rétractation\n[Précisez : les billets de spectacle à date déterminée en sont en principe exclus ; à vérifier.]\n\n7. Données personnelles\nVoir la politique de confidentialité.\n\n8. Réclamations et droit applicable\n[À compléter.]" % (nom, adr, siret, mail),
            "mentions": "Éditeur du site : %s, %s. SIRET : %s. Contact : %s.\n\nDirecteur de la publication : [à compléter].\n\nHébergeur : [nom et adresse de l'hébergeur].\n\nPropriété intellectuelle : [à compléter]." % (nom, adr, siret, mail),
            "confidentialite": "Responsable du traitement : %s, %s. Contact : %s.\n\nDonnées collectées : nom, courriel, adresse (pour un reçu fiscal), historique des commandes.\nFinalités : vous envoyer vos billets, gérer votre commande et votre compte, tenir la comptabilité, [vous informer si vous l'avez accepté].\nDurées de conservation : [à compléter ; les pièces comptables se conservent la durée légale].\n"
                               "Vos droits : accès, rectification, effacement, portabilité : depuis « Mon espace » (export et suppression en ligne) ou par courriel à %s.\nDestinataires : [prestataires de paiement, hébergeur, comptabilité]. Aucun paiement par carte ne passe par nos serveurs." % (nom, adr, mail, mail)}[cle]
        return {"cle": cle, "texte": tete + corps}

    def public(c, cle=""):
        if cle not in TITRES:
            raise ValueError("page introuvable")
        x = lire_texte(cle)
        if not x["texte"].strip():
            raise ValueError("cette page n'est pas publiée")
        return {"cle": cle, "titre": x["titre"], "texte": x["texte"], "version": x["version"], "maj_le": x["maj_le"]}

    ctx.implementer("legal_pages", pages)
    ctx.implementer("legal_page_save", enregistrer, prouver, defaire, simuler=lambda x, cle="", **_: "enregistrerait le texte « %s » de la boutique" % cle)
    ctx.implementer("legal_modele", modele)
    ctx.implementer("public_legal", public)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
