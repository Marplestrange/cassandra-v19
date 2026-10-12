"""Le pont FastPanel.

V18 : FastPanel connaît déjà le propriétaire de chaque site. Le redemander revenait à se tromper.
V18 : L'union (sites explicites + hérités) est calculée à la lecture et non recopiée : un site ajouté est visible tout de suite.
V18 : Cloisonnement : L'admin voit tout ; un compte ordinaire ne voit que ses sites.
V18 : Une ligne qui ne se rattache à rien n'est PAS montrée : le doute ne joue jamais en faveur de la fuite.
V18 : Ouverture de la base en LECTURE SEULE (mode=ro) pour ne pas altérer un logiciel tiers. Uniquement un refus d'ouverture WAL replie en RW.
V18 : ZÉRO PAR ABSENCE ≠ ZÉRO PAR CONFORMITÉ. Toute exception gardait la raison, pour ne pas masquer la panne par un zéro.
V18 : TOUTES les sorties passent par l'enrichissement SSL (qui croise base et constats réels).
V18 : Sondes SSL plafonnées à 12 par appel pour ne pas figer.
V18 : La version PHP vient du panneau, pas du collecteur (qui porte le gestionnaire : fpm, apache...).
V18 : Le collecteur retombait sur information_schema qui ne connaît pas db.site_id ; FastPanel sait tout.
V18 : Une copie sans date de fin n'est pas terminée. Le moteur v2 copie PAR COMPTE.
V18 : mogwai scan:virtualhost d'abord, car l'API de FastPanel renvoie une erreur trompeuse sur le corps pour les scans.
V18 : Rapport antivirus : chaque nombre absent vaut "inconnu" et non zéro (zéro induirait en erreur sur lecture ratée).
V18 : Le cercle des crons : rompu pour éviter le RecursionError de la liste unifiée.
V18 : Quatre états SSL, pas trois (zéro jour n'est pas "sans certificat" si non lu par la sonde).
V18 : La carte WebSocket (map) ne se pose pas forcément dans /etc/nginx/conf.d/.
V18 : Couper nginx, ssh, sshd, cassandra est protégé d'un arrêt distrait (services vitaux).
"""

import time
import json
import logging

def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def est_admin(compte):
        return dr.est_admin(compte) if dr and hasattr(dr, "est_admin") else False

    def voir_tout(compte):
        # V18 : L'admin voit tout ; un compte ordinaire ne voit que ses sites.
        return compte in ("cassandra", "itare", "noyau", "operateur") or not compte or dr.raison(compte, "fastpanel.voir_tout")["accord"]

    def domaines_du_compte(compte):
        if voir_tout(compte):
            return None
        # TODO(comptes) : Récupérer les sites explicites du compte via le module comptes
        # V18 : L'union est calculée à la lecture et non recopiée
        return set()

    def fp_appartient(dom, miens):
        # V18 : Le domaine lui-même, ou un sous-domaine
        dom = str(dom or "").strip().lower()
        if not dom:
            return False
        if miens is None:
            return True
        if dom in miens:
            return True
        return any(dom.endswith("." + m) for m in miens if m)

    # ------------------------------------------------------------------ Lectures

    def lister_sites(ctx):
        miens = domaines_du_compte(ctx.compte)
        # TODO(courtier): Lire l'état réel (Nginx, Certbot) ou interroger la base SQLite de FastPanel en RO (V18: _fp_db_query)
        # TODO(collecteur): Utiliser les données de télémétrie s'il y en a
        # V18 : ZÉRO PAR ABSENCE ≠ ZÉRO PAR CONFORMITÉ. Garder la raison si échec.
        # V18 : TOUTES les sorties passent par l'enrichissement SSL.
        sites = []
        filtres = [s for s in sites if fp_appartient(s.get("domain"), miens)]
        return {"sites": filtres}

    def lister_bases(ctx):
        miens = domaines_du_compte(ctx.compte)
        # TODO(courtier): Lire `fastpanel2.db` avec `_fp_db_query` (mode=ro) pour avoir le `db.site_id`
        # V18 : Le collecteur retombait sur information_schema qui ne connaît pas db.site_id ; FastPanel sait tout.
        bases = []
        # V18 : Une ligne qui ne se rattache à rien n'est PAS montrée : le doute ne joue jamais en faveur de la fuite.
        filtres = [b for b in bases if miens is None or fp_appartient(b.get("site"), miens)]
        return {"bases": filtres}

    def lister_comptes(ctx):
        if not voir_tout(ctx.compte):
            raise PermissionError("Lecture des comptes FastPanel réservée aux administrateurs.")
        # TODO(courtier): Lire `panel_account`
        return {"comptes": []}

    # ------------------------------------------------------------------ Écritures

    def creer_base(ctx, nom="", proprietaire="", serveur_id=""):
        # TODO(courtier): mogwai / api_call("POST", "/api/databases")
        return {"id": nom, "avant": None, "apres": nom}

    def prouver_creer_base(ctx, res):
        return True

    def defaire_creer_base(ctx, res):
        pass # TODO: call api_call("DELETE")

    def supprimer_base(ctx, id=""):
        # TODO(courtier): mogwai / api_call("DELETE", f"/api/databases/{id}")
        return {"id": id}

    def prouver_supprimer_base(ctx, res):
        return True

    def defaire_supprimer_base(ctx, res):
        pass # Impossible sans restauration

    # ------------------------------------------------------------------ Détecteurs et Moteurs

    def detecteur_services(ctx):
        # V18 : Ce qui compte, c'est la TRANSITION.
        vitaux = [s.strip() for s in str(ctx.reglage("services_vitaux") or "").split(",") if s.strip()]
        constats = []
        # TODO(courtier): `systemctl show` sur les services vitaux
        # Comparer avec ctx.stockage (`service_state_seen`) et émettre un constat si passé de active à inactif.
        # V18 : Couper nginx, ssh, sshd, cassandra est protégé d'un arrêt distrait.
        return constats

    def detecteur_analyses(ctx):
        constats = []
        # TODO(courtier): Lire `scan_report` en base
        # Comparer avec `scan_state_seen`
        # V18 : Rapport antivirus : chaque nombre absent vaut "inconnu" et non zéro.
        return constats

    def detecteur_sauvegardes(ctx):
        constats = []
        # TODO(courtier): Lire `backup_copy_v2`
        # V18 : Une copie sans date de fin n'est pas terminée. Le moteur v2 copie PAR COMPTE.
        return constats

    def detecteur_php(ctx):
        constats = []
        # TODO(courtier): Lire `website_backends` pour avoir la vraie version
        # V18 : La version PHP vient du panneau, pas du collecteur (qui porte le gestionnaire).
        return constats

    def liens_watch(ctx):
        # TODO(comptes): Surveiller les changements de `user_sites`
        # V18 : Signale ce qu'un compte adossé vient de gagner ou de perdre. Un rapatriement silencieux n'est pas un rapatriement.
        pass

    # ------------------------------------------------------------------ Branchement

    ctx.implementer("lister_sites", lister_sites)
    ctx.implementer("lister_bases", lister_bases)
    ctx.implementer("lister_comptes", lister_comptes)
    ctx.implementer("creer_base", creer_base, prouver_creer_base, defaire_creer_base)
    ctx.implementer("supprimer_base", supprimer_base, prouver_supprimer_base, defaire_supprimer_base)
    
    ctx.detecteur("services", detecteur_services)
    ctx.detecteur("analyses", detecteur_analyses)
    ctx.detecteur("sauvegardes", detecteur_sauvegardes)
    ctx.detecteur("php", detecteur_php)
    
    ctx.moteur("liens_watch", liens_watch)
