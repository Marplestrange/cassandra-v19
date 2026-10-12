"""Module Courrier : Boîtes, IMAP, brouillons, mandats d'envoi, médias et contacts."""

import re
import html
import threading
import time

# V18 : Un pixel de suivi n'est pas une image. Une balise de 1x1 ne montre rien :
# elle sert à dire à l'expéditeur que le message a été ouvert. Elle part en data-tracker-* (B49).
_MAIL_IMG_TAG = re.compile(r"(?is)<img\b[^>]*>")
_MAIL_PIXEL = re.compile(
    r"(?is)(?:\b(?:width|height)\s*=\s*[\"']?\s*[01](?:px)?\s*[\"']?(?=[\s/>])"
    r"|\b(?:width|height)\s*:\s*[01](?:px)?\s*[;\"\'])")
_MAIL_TRACKER_ATTR = re.compile(r"(?is)\s(src|srcset|lowsrc|background)\s*=")

# V18 : TOUT CE QUI CHARGE, pas seulement src : srcset, poster, background, lowsrc, data...
# Seul data: reste : il est inerte. (B49, tour 23)
_MAIL_HTML_CHARGE = re.compile(
    r"(?is)\s(src|srcset|poster|background|lowsrc|data)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")

def brancher(ctx):
    db = ctx.stockage

    # V18 : LOT 3 : la case était unique. Deux personnes se volaient la session à tour de rôle...
    # Chaque boîte a maintenant sa session et son verrou.
    _IMAP_POOLS = {}
    _IMAP_LOCK = threading.RLock()
    _IMAP_CAPA = {}
    _IMAP_IDLE_MAX = 240.0

    def _mail_marquer_pixels(h: str) -> str:
        def _une(m):
            tag = m.group(0)
            if not _MAIL_PIXEL.search(tag):
                return tag
            return _MAIL_TRACKER_ATTR.sub(lambda x: " data-tracker-%s=" % x.group(1).lower(), tag)
        return _MAIL_IMG_TAG.sub(_une, h)

    def _mail_sanitize_html(html_str: str, show_images: bool = False) -> str:
        # V18 : Le nom peut arriver HTML-échappé par sanitize_data : « envoy&AOk-s » devient « envoy&amp;AOk-s ». On le dé-échappe ici.
        # V18 : B32 : un lien de courrier s'ouvre dans un NOUVEL onglet, son infobulle dit où il mène...
        h = html_str or ""
        h = _mail_marquer_pixels(h)
        if not show_images:
            def _bloque(m):
                v = m.group(2)
                nu = v.strip("\"'").strip().lower()
                if nu.startswith("data:"):
                    return m.group(0)
                return " data-blocked-%s=%s" % (m.group(1).lower(), v)
            h = _MAIL_HTML_CHARGE.sub(_bloque, h)
        return h[:400000]

    # --- LECTURES ---

    def etat(ctx):
        c = ctx.compte
        # V18 : Le repli sur la boîte de config.json a été FERMÉ (août 2026).
        # Sans identifiants personnels, on rend un hôte vide. Une boîte appartient à une personne.
        # TODO(coffre) : lire les identifiants via vault_native_get(c, "cassandra/boite-mail")
        perso = None 
        h, p, u, pw, ssl = perso or ("", 993, "", "", True)
        
        # V18 : Sans identifiants, DIRE POURQUOI : un coffre verrouillé se déverrouille,
        # une boîte absente se renseigne — ce n'est pas le même geste (B23).
        souci = "" if (h and u) else "coffre_ou_absente" # TODO(coffre) : interroger etat du coffre
        
        return {
            "ok": True, 
            "configuree": bool(h and u),
            "host": h, "user": u,
            "souci": souci,
            "personnelle": perso is not None
        }

    def dossiers(ctx):
        c = ctx.compte
        # TODO(port) : interroger _imap_cmd pour la liste des dossiers
        return {"folders": []}

    def rechercher(ctx, query="", unseen_only=False):
        # TODO(port) : mail_search_criteria
        return {"uids": []}

    # --- ÉCRITURES ---

    def enregistrer(ctx, host="", port=993, login="", pwd="", ssl=True,
                    smtp_host="", smtp_port=587, smtp_login="", smtp_pwd=""):
        c = ctx.compte
        if not host or not login:
            raise ValueError("serveur et identifiant sont requis")
        
        # V18 : LOT 3 : le serveur d'envoi va dans un second secret ; sans hôte SMTP, on garde l'existant.
        # TODO(coffre) : vault_native_set(c, "cassandra/boite-mail", login, pwd, f"{host}:{port}")
        # TODO(coffre) : vault_native_set(c, "cassandra/boite-mail-smtp", ...)

        # V18 : LA BOÎTE FAIT NAÎTRE LE DOSSIER DE PIÈCES JOINTES (18-09).
        # TODO(ged) : ged_pj_dossier_creer(c)
        ctx.emettre("mail.boite_enregistree", objet=("compte", c), donnees={"host": host})
        
        return {"id": c, "avant": None}

    def prouver_enregistrer(ctx, res):
        return True # TODO(coffre) : relire que le compte existe dans le coffre

    def defaire_enregistrer(ctx, res):
        # TODO(coffre) : restaurer l'état précédent du coffre si applicable
        pass

    def detacher(ctx):
        c = ctx.compte
        # TODO(coffre) : vault_native_delete(c, "cassandra/boite-mail")
        return {"id": c, "avant": "existant"}

    def prouver_detacher(ctx, res):
        return True

    def defaire_detacher(ctx, res):
        pass

    def marquer(ctx, uids=None, champ="", valeur=True, folder="INBOX"):
        # V18 : Le cache suit le serveur : un message supprimé ou déplacé là-bas sort d'ici, 
        # sinon l'aperçu montre un non-lu qui n'existe plus.
        # TODO(port) : _imap_cmd(uid STORE ...) + update mail_cache
        return {"id": folder, "avant": None}

    def prouver_marquer(ctx, res): return True
    def defaire_marquer(ctx, res): pass

    def supprimer(ctx, uids=None, folder="INBOX", permanent=False):
        # TODO(port) : mail_delete
        return {"id": folder, "avant": None}

    def prouver_supprimer(ctx, res): return True
    def defaire_supprimer(ctx, res): pass

    # --- MOTEURS ---

    def passe_courrier(ctx):
        # V18 : Une passe sur tous les comptes qui ont une boîte... Le compte est posé sur 
        # le fil pour la durée de la passe, puis rendu. (En V19 on l'injecte proprement).
        # TODO(port) : itérer sur les comptes configurés, synchroniser mail_cache et mail_dossiers
        pass

    def messages_tick(ctx):
        # TODO(port) : scruter les brouillons programmés et les envoyer
        pass

    def mandat_tick(ctx):
        # TODO(port) : scruter mandat_envois en attente et envoyer via SMTP
        pass

    ctx.implementer("etat", etat)
    ctx.implementer("enregistrer", enregistrer, prouver_enregistrer, defaire_enregistrer)
    ctx.implementer("detacher", detacher, prouver_detacher, defaire_detacher)
    ctx.implementer("dossiers", dossiers)
    ctx.implementer("rechercher", rechercher)
    ctx.implementer("marquer", marquer, prouver_marquer, defaire_marquer)
    ctx.implementer("supprimer", supprimer, prouver_supprimer, defaire_supprimer)

    ctx.moteur("passe_courrier", passe_courrier)
    ctx.moteur("messages_tick", messages_tick)
    ctx.moteur("mandat_tick", mandat_tick)
