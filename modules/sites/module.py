import time
import json
import re
import urllib.request
from datetime import datetime

_SITE_LENT_MS = 3000
_SITE_DOMAINE_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
_LE_MAX_PAR_SEMAINE = 50

# V18 : Répertoires qui SONT une racine web d'application : quand la racine déclarée
# porte un de ces noms, l'application vit un cran AU-DESSUS.
_RACINES_WEB = ("public", "public_html", "html", "web", "httpdocs", "www", "htdocs")

# V18 : Applications sans racine sur le disque. Vaultwarden, Gitea, Grafana n'ont
# pas de racine. Ces applications se nomment elles-mêmes sur HTTP.
_SONDES_HTTP = (
    {"nom": "Vaultwarden", "chemin": "/api/config", "signe": ("vaultwarden",)},
    {"nom": "Bitwarden", "chemin": "/api/config", "signe": ("bitwarden",)},
    {"nom": "Nextcloud", "chemin": "/status.php", "signe": ("nextcloud",)},
    {"nom": "Gitea", "chemin": "/api/v1/version", "signe": ()},
)


def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def gere(compte):
        return dr.raison(compte, "sites.gerer")["accord"]

    def _norm_domain(domain):
        return str(domain).strip().lower()

    def _site_up(code):
        # V18 : N'exiger que 200 était faux : un site qui force HTTPS répond 301.
        # Une redirection est une réponse, pas une panne.
        if code in (301, 302, 307, 308):
            return True
        return 200 <= code < 400 if code else False

    def _cert_days(cert):
        # V18 : LE PIÈGE : `expires` n'est PAS une date, c'est la DURÉE DE VALIDITÉ en jours (90 pour Let's Encrypt).
        # La vraie date est `expired_at`.
        # V18 : ARRONDI, pas troncature pour éviter l'affichage de deux chiffres différents (55.99 j -> 56).
        # TODO(certificats) : logic to parse mogwai/fastpanel certs
        pass

    def _site_probe(domain, timeout=8.0):
        # V18 : Le code seul ne suffit pas : un site qui répond 200 en 8 secondes est en panne
        # pour ses visiteurs. C'est la mesure de durée qui manquait.
        url = "https://%s/" % _norm_domain(domain)
        t0 = time.time()
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Cassandra/site-check"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.getcode(), int((time.time() - t0) * 1000), None
        except urllib.error.HTTPError as e:
            return e.code, int((time.time() - t0) * 1000), str(e)
        except Exception as e:
            return None, int((time.time() - t0) * 1000), str(e)

    def sonde(ctx):
        if not ctx.reglage("site_watch_enabled"):
            return
        
        # TODO(panneau) : récupérer les domaines du panneau via le courtier FastPanel
        domaines_panneau = []
        
        declares = db.lire("SELECT domain FROM sites_declares")
        domaines = set(domaines_panneau + [d["domain"] for d in declares])
        
        now = time.time()
        for dn in domaines:
            code, ms, err = _site_probe(dn)
            up = 1 if _site_up(code) else 0
            
            db.ecrire("INSERT INTO site_status(ts, domain, http_code, response_ms, up, error) VALUES(?,?,?,?,?,?)",
                      (now, dn, code, ms, up, err))
            
            avant = db.lire("SELECT up, since FROM site_state_seen WHERE domain=?", (dn,))
            if not avant:
                db.ecrire("INSERT INTO site_state_seen(domain, up, since, ts) VALUES(?,?,?,?)", (dn, up, now, now))
                db.ecrire("INSERT INTO site_events(ts, domain, kind, detail) VALUES(?,?,?,?)",
                          (now, dn, "decouverte", "Première observation (HTTP %s, %s ms)" % (code, ms)))
            elif avant[0]["up"] != up:
                duree = int((now - avant[0]["since"]) / 60.0)
                db.ecrire("INSERT OR REPLACE INTO site_state_seen(domain, up, since, ts) VALUES(?,?,?,?)", (dn, up, now, now))
                db.ecrire("INSERT INTO site_events(ts, domain, kind, detail, duration_min) VALUES(?,?,?,?,?)",
                          (now, dn, "retour" if up else "panne", "Transition HTTP %s" % code, duree))

        jours = max(7, int(ctx.reglage("site_retention_days") or 90))
        limite = now - (jours * 86400)
        db.ecrire("DELETE FROM site_status WHERE ts < ?", (limite,))

    def detecteur_panne(ctx):
        constats = []
        lignes = db.lire("SELECT domain, since FROM site_state_seen WHERE up=0")
        for r in lignes:
            duree = int((time.time() - r["since"]) / 60)
            constats.append({
                "objet": ("site", r["domain"]),
                "titre": "%s ne répond pas" % r["domain"],
                "detail": "En panne depuis %d minutes" % duree,
                "niveau": "panne",
                "capacite": "fiche",
                "args": {"domain": r["domain"]}
            })
        return constats

    def vue(ctx):
        # V18 : L'accueil et l'onglet appelaient mogwai sites list (40s) : le cache évite
        # la double attente. Le collecteur qui hoquète garde le cache pour ne pas croire
        # à une disparition des sites.
        # TODO(panneau) : récupérer les données depuis le cache ou FastPanel
        return {"sites": db.lire("SELECT * FROM sites_declares")}

    def declarer(ctx, domain="", par=""):
        dn = _norm_domain(domain)
        compte = ctx.compte
        if not dn or not _SITE_DOMAINE_RE.match(dn):
            raise ValueError("domaine invalide")
        
        # TODO(panneau) : verify it's not in the panel
        
        existant = db.lire("SELECT compte FROM sites_declares WHERE domain=?", (dn,))
        if existant and existant[0]["compte"] != compte:
            raise ValueError("ce site appartient déjà à un autre compte")
        
        if not existant:
            db.ecrire("INSERT INTO sites_declares(domain, compte, ts, par) VALUES(?,?,?,?)",
                      (dn, compte, time.time(), par or compte))
            ctx.emettre("site.declare", objet=("site", dn), donnees={"compte": compte})
            return {"domain": dn, "nouveau": True, "avant": None}
        return {"domain": dn, "nouveau": False, "avant": existant[0]}

    def prouver_declarer(ctx, res):
        return bool(db.lire("SELECT compte FROM sites_declares WHERE domain=?", (res["domain"],)))

    def defaire_declarer(ctx, res):
        if res["nouveau"]:
            db.ecrire("DELETE FROM sites_declares WHERE domain=?", (res["domain"],))

    def retirer(ctx, domain="", par=""):
        dn = _norm_domain(domain)
        compte = ctx.compte
        existant = db.lire("SELECT compte, ts, par FROM sites_declares WHERE domain=?", (dn,))
        if not existant:
            raise ValueError("site absent de sites_declares")
        
        if not gere(compte) and existant[0]["compte"] != compte:
            raise PermissionError("non autorisé à retirer le site d'un autre compte")
            
        db.ecrire("DELETE FROM sites_declares WHERE domain=?", (dn,))
        ctx.emettre("site.retire", objet=("site", dn), donnees={"compte": existant[0]["compte"]})
        return {"domain": dn, "avant": existant[0]}

    def prouver_retirer(ctx, res):
        return not db.lire("SELECT compte FROM sites_declares WHERE domain=?", (res["domain"],))

    def defaire_retirer(ctx, res):
        a = res["avant"]
        db.ecrire("INSERT INTO sites_declares(domain, compte, ts, par) VALUES(?,?,?,?)",
                  (res["domain"], a["compte"], a["ts"], a["par"]))

    def attribuer(ctx, domain="", compte=""):
        dn = _norm_domain(domain)
        cible = str(compte or "").strip().lower()
        if not gere(ctx.compte):
            raise PermissionError("seul un administrateur peut attribuer un site")
        
        # TODO(comptes): check user exists in modules/comptes
        avant = db.lire("SELECT compte, ts, par FROM sites_declares WHERE domain=?", (dn,))
        if avant and avant[0]["compte"] == cible:
            return {"domain": dn, "nouveau": False, "avant": avant[0]}
        
        db.ecrire("INSERT OR REPLACE INTO sites_declares(domain, compte, ts, par) VALUES(?,?,?,?)",
                  (dn, cible, time.time(), ctx.compte))
        ctx.emettre("site.attribue", objet=("site", dn), donnees={"a": cible, "par": ctx.compte})
        return {"domain": dn, "nouveau": True, "avant": avant[0] if avant else None, "compte": cible}

    def prouver_attribuer(ctx, res):
        r = db.lire("SELECT compte FROM sites_declares WHERE domain=?", (res["domain"],))
        return bool(r and r[0]["compte"] == res["compte"])

    def defaire_attribuer(ctx, res):
        if not res["nouveau"]: return
        if res["avant"]:
            a = res["avant"]
            db.ecrire("INSERT OR REPLACE INTO sites_declares(domain, compte, ts, par) VALUES(?,?,?,?)",
                      (res["domain"], a["compte"], a["ts"], a["par"]))
        else:
            db.ecrire("DELETE FROM sites_declares WHERE domain=?", (res["domain"],))

    def demander(ctx, domain="", message=""):
        dn = _norm_domain(domain)
        compte = ctx.compte
        
        avant = db.lire("SELECT * FROM site_demandes WHERE domain=? AND compte=? AND statut='ouverte'", (dn, compte))
        if avant:
            raise ValueError("demande déjà en attente pour ce site")
        
        row_id = db.ecrire("INSERT INTO site_demandes(ts, domain, compte, message) VALUES(?,?,?,?)",
                           (time.time(), dn, compte, str(message)[:500]))
        ctx.emettre("site.demande", objet=("site", dn), donnees={"compte": compte})
        return {"id": row_id, "domain": dn}

    def prouver_demander(ctx, res):
        return bool(db.lire("SELECT id FROM site_demandes WHERE id=?", (res["id"],)))

    def defaire_demander(ctx, res):
        db.ecrire("DELETE FROM site_demandes WHERE id=?", (res["id"],))

    def fiche(ctx, domain=""):
        return {"domain": _norm_domain(domain), "info": "TODO(donnees): agrégation V18 fiche"}

    def databases(ctx, domain=""):
        # V18 : Le rattachement vient de db.site_id, pas d'une ressemblance de noms :
        # deviner « exemple_com_wp appartient à exemple.com » marcherait neuf fois sur dix,
        # et la dixième montrerait la base d'un autre. SANS RATTACHEMENT, ON NE MONTRE RIEN.
        # TODO(fastpanel) : implémenter avec certitude l'appartenance
        return {"bases": []}

    ctx.moteur("sonde", sonde)
    ctx.detecteur("panne", detecteur_panne)
    ctx.implementer("vue", vue)
    ctx.implementer("fiche", fiche)
    ctx.implementer("databases", databases)
    ctx.implementer("declarer", declarer, prouver_declarer, defaire_declarer)
    ctx.implementer("retirer", retirer, prouver_retirer, defaire_retirer)
    ctx.implementer("attribuer", attribuer, prouver_attribuer, defaire_attribuer)
    ctx.implementer("demander", demander, prouver_demander, defaire_demander)
