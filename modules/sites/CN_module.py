# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sites
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sites
# ZONE       : CN
# VERSION CN : 0.6.1  #011628
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module Sites.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.6.1 empreinte=011628 ▼▼▼
"""Le module Sites.

Ce qu'il tient de la V18 (sites, site_pass, site_fiche, site_history/availability, demandes, accords, liens) et les leçons qu'il garde :
  - la sonde CHRONOMÈTRE : un site qui répond 200 en huit secondes est en panne pour ses visiteurs ; le code seul ne suffit pas ;
  - le certificat se lit sur le port 443, pas dans la base : l'observation fait foi (au plus une fois par heure et par site) ;
  - un site n'est jugé qu'à sa TRANSITION (en ligne -> hors ligne), jamais à son état : la première observation est une découverte ;
  - une mesure ratée n'est pas une panne : il en faut plusieurs de suite (réglage « echecs_avant_panne ») avant d'alerter ;
  - un site qu'on ne mesure plus depuis deux jours n'entre plus dans les disponibilités (il n'a pas 100 % : il n'a pas de mesure) ;
  - chaque compte ne voit que ses sites ; l'administrateur voit l'état de tous, jamais le contenu (administrer n'est pas voir) ;
  - un site du panneau ne se déclare pas à la main : il appartient à son propriétaire du panneau, l'administrateur l'attribue ;
  - un site appartient à UN compte ; pour en changer, on transfère — et l'accord, les liens et la demande de l'ancien propriétaire ne suivent pas.

Les sites d'un compte sont : ceux qu'il a déclarés ici, ceux que l'administrateur lui a attribués, ceux inscrits dans sa fiche (module comptes, champ « sites »)
et ceux du panneau dont le propriétaire est le compte du panneau lié à sa fiche (« fp_account »). Les deux derniers se lisent, ils ne s'écrivent pas ici.

D'où le module tient les comptes et le panneau : un compte ordinaire n'a ni « comptes.gerer » ni « fastpanel.voir », ses lectures seraient refusées.
La sonde, qui tourne sans compte, lit donc les deux à chaque tour et en garde un MIROIR réduit (table miroir) ; un compte ordinaire lit ce miroir,
plus sa propre fiche (« comptes.moi ») pour ne pas attendre le tour suivant. L'administrateur, lui, lit en direct.
"""
from __future__ import annotations

import base64
import calendar
import html
import ipaddress
import json
import re
import secrets
import socket
import sqlite3
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timezone

RE_DOMAINE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
GENRES_LIEN = ("project", "contact", "machine", "note")
GESTES_ACCORD = ("restaurer", "supprimer", "transferer", "migrer")
SUIVI_J = 2                     # un site sans mesure depuis ce nombre de jours n'entre plus dans les disponibilités
CERT_REFRAICHI_S = 3600
BUDGET_SONDE_S = 240
DUREE_MAX_SONDE_S = 280         # celle du manifeste ([[moteurs]] duree_max_s) : la sonde s'arrête avant
MIROIR_S = 3600                 # au-delà, le miroir des comptes et du panneau n'est plus tenu pour frais
POINTS_MAX = 720                # un historique ne rend jamais plus de points : au-delà, ils sont regroupés
JOURNAL_GARDE_J = 365           # le journal des gestes se garde au moins un an, quelle que soit la garde des mesures
COTE_GARDE_J = 30               # liens mis de côté et accords échus : trente jours, le temps de défaire
INCIDENT_GARDE_J = 365          # un incident résolu se garde un an : sa cause sert la fois suivante
PREUVE_GARDE_J = 7              # une déclaration qui n'a pas été prouvée en sept jours tombe
RELEVE_MIN_S = 30               # une relève à la demande ne remesure pas un site mesuré il y a moins de trente secondes
OBJECTIF_DEFAUT = 99.9
COUPURE_COURTE_PCT = 98.0       # un jour à 98 % et plus (moins d'une demi-heure perdue) est une coupure courte ; en dessous, une coupure longue
CHEMIN_PREUVE = "/.well-known/cassandra-site.txt"
APERCU_S = 86400                # l'aperçu d'un site (titre, icône, image) se relit une fois par jour
APERCUS_PAR_TOUR = 4            # et pas plus de quatre sites par tour de sonde : les mesures passent d'abord
PAGE_MAX = 96 * 1024            # ce qu'on lit d'une page pour son en-tête
ICONE_MAX = 24 * 1024           # une icône plus lourde n'est pas gardée
IMAGE_MAX = 200 * 1024          # ni une image de présentation au-delà de 200 Ko
ICONE_EN_LISTE = 8 * 1024       # dans la liste des sites, une icône n'est jointe que si elle est petite (en caractères) : la liste doit rester légère
IMAGES_ADMISES = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/x-icon", "image/vnd.microsoft.icon", "image/svg+xml")
CMS_DECLARES = (("wordpress", "WordPress"), ("joomla", "Joomla"), ("drupal", "Drupal"), ("prestashop", "PrestaShop"), ("nextcloud", "Nextcloud"), ("typo3", "TYPO3"), ("spip", "SPIP"),
                ("dotclear", "Dotclear"), ("ghost", "Ghost"), ("hugo", "Hugo"), ("jekyll", "Jekyll"), ("gatsby", "Gatsby"), ("wix", "Wix"), ("shopify", "Shopify"),
                ("squarespace", "Squarespace"), ("webflow", "Webflow"), ("dolibarr", "Dolibarr"), ("matomo", "Matomo"), ("mediawiki", "MediaWiki"), ("discourse", "Discourse"))
VOISINS_S = 3600               # ce que les autres modules savent d'un site (CMS, bases, sauvegardes, échéance du nom…) se relit une fois par heure
NOM_COURT_J = 30                # un nom de domaine à moins de trente jours de son échéance se signale ; à moins de dix, c'est grave
# Des noms sous lesquels vivent les sites de beaucoup de gens : les déclarer donnerait, par les sous-domaines, la vue des sites des autres.
SUFFIXES_PARTAGES = frozenset((
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.nz", "co.jp", "com.br", "co.za", "com.cn", "co.in",
    "gouv.fr", "asso.fr", "com.fr", "nom.fr", "tm.fr",
    "github.io", "gitlab.io", "pages.dev", "workers.dev", "netlify.app", "vercel.app", "herokuapp.com", "web.app", "firebaseapp.com",
    "wordpress.com", "blogspot.com", "wixsite.com", "azurewebsites.net", "cloudfront.net", "amazonaws.com", "ovh.net", "free.fr",
))


def nom_hote(d):
    """Le nom d'hôte seul : sans protocole, chemin, requête, identifiants, port ni point final ; « www. » est le même site."""
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    for sep in "/?#":
        d = d.split(sep)[0]
    d = d.rsplit("@", 1)[-1]
    if d.count(":") == 1:
        d = d.split(":")[0]
    d = d.rstrip(".")
    return d[4:] if d.startswith("www.") else d


def _est_interne(hote):
    """Ce nom mène-t-il à une adresse qui n'est pas sur l'Internet public (boucle locale, réseau privé, lien local, métadonnées d'un hébergeur) ?
    Un nom qui ne se résout pas n'est pas « interne » : la requête dira elle-même qu'il est introuvable."""
    try:
        infos = socket.getaddrinfo(hote, 443, type=socket.SOCK_STREAM)
    except Exception:
        return False
    for i in infos:
        try:
            if not ipaddress.ip_address(str(i[4][0]).split("%")[0]).is_global:
                return True
        except ValueError:
            return True
    return False


class _MemeSite(urllib.request.HTTPRedirectHandler):
    """La sonde ne suit une redirection que vers le MÊME site, en HTTPS : ailleurs, le code 3xx est la réponse (le site répond, c'est ce qu'on mesure)."""

    def __init__(self, site, interne):
        self.site, self.interne = site, interne

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not str(newurl).lower().startswith("https://"):
            return None
        h = nom_hote(newurl)
        if h != self.site and not h.endswith("." + self.site):
            return None
        if not self.interne and _est_interne(h):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _une_requete(hote, site, delai, interne):
    """(code, ms, erreur, delai_depasse)."""
    t0 = time.time()
    ms = lambda: int((time.time() - t0) * 1000)          # noqa: E731
    try:
        if not interne and _est_interne(hote):
            return None, 0, "adresse interne : la sonde ne sort que vers l'Internet public (réglage « sonde_interne »)", False
        req = urllib.request.Request("https://%s/" % hote, method="GET", headers={"User-Agent": "Cassandra/site-check"})
        with urllib.request.build_opener(_MemeSite(site, interne)).open(req, timeout=delai) as r:
            r.read(2048)
            return r.getcode(), ms(), "", False
    except urllib.error.HTTPError as ex:
        return ex.code, ms(), "", False
    except Exception as ex:
        tard = isinstance(ex, (socket.timeout, TimeoutError)) or isinstance(getattr(ex, "reason", None), (socket.timeout, TimeoutError))
        return None, ms(), str(ex)[:200], tard


def _sonder_http(domaine, delai, interne=False):
    """(code, ms, erreur). Interroge le site et le chronomètre. Si le nom nu ne répond pas du tout (et pas par lenteur), « www. » est essayé :
    bien des sites ne servent que lui."""
    h = nom_hote(domaine)
    code, ms, erreur, tard = _une_requete(h, h, delai, interne)
    if code is None and not tard and not erreur.startswith("adresse interne"):
        c2, ms2, _, _ = _une_requete("www." + h, h, delai, interne)
        if c2 is not None:
            return c2, ms2, ""
    return code, ms, erreur


def _cert_jours_hote(hote, delai):
    try:
        with socket.create_connection((hote, 443), timeout=delai) as brut:
            try:
                with ssl.create_default_context().wrap_socket(brut, server_hostname=hote) as tls:
                    fin = tls.getpeercert().get("notAfter")
                return int((ssl.cert_time_to_seconds(fin) - time.time()) // 86400) if fin else None
            except ssl.SSLCertVerificationError:
                pass
        # Le certificat est refusé (échu, ou pour un autre nom) : c'est justement là qu'il faut savoir sa date. On le relit sans le juger.
        libre = ssl.create_default_context()
        libre.check_hostname = False
        libre.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hote, 443), timeout=delai) as brut:
            with libre.wrap_socket(brut, server_hostname=hote) as tls:
                der = tls.getpeercert(True)
        from cryptography import x509
        cert = x509.load_der_x509_certificate(der)
        fin = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
        return int((fin.timestamp() - time.time()) // 86400)
    except Exception:
        return None


def _cert_jours(domaine, delai):
    """Jours avant l'échéance du certificat SERVI (négatif s'il est échu), ou None si on ne sait pas le lire."""
    h = nom_hote(domaine)
    j = _cert_jours_hote(h, delai)
    return j if j is not None else _cert_jours_hote("www." + h, delai)


def _serveurs_dns():
    """Les serveurs de noms de la machine (/etc/resolv.conf). Aucun serveur d'un tiers n'est ajouté d'office : sans eux, la preuve par le DNS n'est pas lisible."""
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            return [x.split()[1] for x in f if x.startswith("nameserver") and len(x.split()) > 1][:3]
    except OSError:
        return []


def _txt_dns(nom, delai=4):
    """Les enregistrements TXT d'un nom, demandés aux serveurs de noms de la machine (une question DNS écrite à la main : la bibliothèque standard ne sait pas la poser).
    Rend la liste des textes, vide si le nom n'en a pas ou si personne ne répond."""
    try:
        question = b"".join(bytes([len(p)]) + p for p in nom.rstrip(".").encode("idna").split(b".")) + b"\x00\x00\x10\x00\x01"
    except Exception:
        return []
    for serveur in _serveurs_dns():
        try:
            famille = socket.AF_INET6 if ":" in serveur else socket.AF_INET
            with socket.socket(famille, socket.SOCK_DGRAM) as s:
                s.settimeout(delai)
                ident = int(time.time() * 1000) & 0xFFFF
                s.sendto(ident.to_bytes(2, "big") + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + question, (serveur, 53))
                rep = s.recv(4096)
            if len(rep) < 12 or rep[:2] != ident.to_bytes(2, "big"):
                continue
            n, i = int.from_bytes(rep[6:8], "big"), 12 + len(question)

            def sauter(i):
                while i < len(rep):
                    if rep[i] >= 192:
                        return i + 2
                    if rep[i] == 0:
                        return i + 1
                    i += 1 + rep[i]
                return i
            textes = []
            for _ in range(n):
                i = sauter(i)
                genre, taille = int.from_bytes(rep[i:i + 2], "big"), int.from_bytes(rep[i + 8:i + 10], "big")
                donnees, i = rep[i + 10:i + 10 + taille], i + 10 + taille
                if genre == 16:
                    morceaux, k = [], 0
                    while k < len(donnees):
                        morceaux.append(donnees[k + 1:k + 1 + donnees[k]])
                        k += 1 + donnees[k]
                    textes.append(b"".join(morceaux).decode("utf-8", "replace"))
            return textes
        except Exception:
            continue
    return []


def _fichier_preuve(domaine, delai, interne=False):
    """Le contenu du fichier de preuve servi par le site (256 octets au plus), ou "" s'il n'y est pas."""
    h = nom_hote(domaine)
    for hote in (h, "www." + h):
        try:
            if not interne and _est_interne(hote):
                return ""
            req = urllib.request.Request("https://%s%s" % (hote, CHEMIN_PREUVE), method="GET", headers={"User-Agent": "Cassandra/site-check"})
            with urllib.request.build_opener(_MemeSite(h, interne)).open(req, timeout=delai) as r:
                if r.getcode() == 200:
                    return r.read(256).decode("utf-8", "replace")
        except Exception:
            continue
    return ""


def _preuve_trouvee(domaine, jeton, delai, interne=False):
    """Par où la preuve est visible : « dns » (TXT _cassandra.<domaine> = cassandra-site=<jeton>), « fichier » (https://<domaine>/.well-known/cassandra-site.txt), ou ""."""
    h = nom_hote(domaine)
    attendu = "cassandra-site=" + jeton
    if any(attendu in t.replace(" ", "") for t in _txt_dns("_cassandra." + h, min(delai, 5))):
        return "dns"
    if jeton in _fichier_preuve(h, delai, interne).split():
        return "fichier"
    return ""


def _lire_page(domaine, delai, interne=False):
    """(texte, adresse finale) de la page d'accueil : ses 96 premiers Ko, là où vivent le titre, l'icône et les balises de présentation. ("", "") si elle ne se lit pas."""
    h = nom_hote(domaine)
    for hote in (h, "www." + h):
        try:
            if not interne and _est_interne(hote):
                return "", ""
            req = urllib.request.Request("https://%s/" % hote, method="GET", headers={"User-Agent": "Cassandra/site-check", "Accept": "text/html"})
            with urllib.request.build_opener(_MemeSite(h, interne)).open(req, timeout=delai) as r:
                if "html" not in (r.headers.get("Content-Type") or "").lower():
                    return "", ""
                brut = r.read(PAGE_MAX)
                try:
                    return brut.decode(r.headers.get_content_charset() or "utf-8", "replace"), r.geturl()
                except LookupError:
                    return brut.decode("utf-8", "replace"), r.geturl()
        except Exception:
            continue
    return "", ""


def _lire_image(adresse, site, delai, interne=False, maxi=ICONE_MAX):
    """Une image du site, rendue en « data: » (l'interface n'affiche aucune image venue d'ailleurs). Seulement en HTTPS, seulement sur le site lui-même
    (son nom ou un de ses sous-domaines), d'un type d'image connu, et bornée en taille ; "" sinon."""
    try:
        if not str(adresse).lower().startswith("https://"):
            return ""
        h = nom_hote(adresse)
        if h != site and not h.endswith("." + site):
            return ""
        if not interne and _est_interne(h):
            return ""
        req = urllib.request.Request(adresse, method="GET", headers={"User-Agent": "Cassandra/site-check"})
        with urllib.request.build_opener(_MemeSite(site, interne)).open(req, timeout=delai) as r:
            genre = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if genre not in IMAGES_ADMISES:
                return ""
            brut = r.read(maxi + 1)
            if not brut or len(brut) > maxi:
                return ""
            return "data:%s;base64,%s" % (genre, base64.b64encode(brut).decode("ascii"))
    except Exception:
        return ""


_RE_ATTRIBUT = re.compile(r"([A-Za-z_:][\w:.-]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+))")


def tete_html(texte, adresse=""):
    """Ce que l'en-tête d'une page dit d'elle : {titre, description, generateur, langue, icone, image}, les adresses rendues absolues.
    Pur : du texte en entrée, des données en sortie ; une page vide ou illisible rend des champs vides."""
    t = texte or ""

    def attributs(balise):
        return {m.group(1).lower(): html.unescape(next((g for g in m.groups()[1:] if g is not None), "")) for m in _RE_ATTRIBUT.finditer(balise)}
    m = re.search(r"<title[^>]*>(.*?)</title>", t, re.I | re.S)
    titre = " ".join(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).split()) if m else ""
    metas = {}
    for b in re.findall(r"<meta\b[^>]*>", t, re.I):
        a = attributs(b)
        cle = (a.get("property") or a.get("name") or "").lower()
        if cle and cle not in metas and a.get("content"):
            metas[cle] = " ".join(a["content"].split())
    icone, note = "", 0
    for b in re.findall(r"<link\b[^>]*>", t, re.I):
        a = attributs(b)
        rel = (a.get("rel") or "").lower().split()
        if "icon" in rel and a.get("href"):
            n = 3 if "32" in (a.get("sizes") or "") else 2
            if n > note:
                icone, note = a["href"], n
    m = re.search(r"<html\b[^>]*\blang\s*=\s*[\"']?([A-Za-z-]{2,10})", t, re.I)

    def absolue(u):
        return urllib.parse.urljoin(adresse or "", u) if u else ""
    return {"titre": (titre or metas.get("og:title", ""))[:150], "description": (metas.get("description") or metas.get("og:description") or "")[:300],
            "generateur": metas.get("generator", "")[:80], "langue": m.group(1).lower() if m else "",
            "icone": absolue(icone) or (absolue("/favicon.ico") if adresse and t else ""), "image": absolue(metas.get("og:image") or metas.get("twitter:image") or "")}


def cms_du_generateur(generateur):
    """Le CMS que la page déclare d'elle-même (<meta name="generator">), ou None : pour un site hors de la machine, c'est tout ce qu'on peut en savoir sans y entrer."""
    g = (generateur or "").strip()
    bas = g.lower()
    for cle, nom in CMS_DECLARES:
        if cle in bas:
            v = re.search(r"\d+(?:\.\d+)+", g)
            return {"type": nom, "version": v.group(0) if v else "", "theme": "", "extensions": None, "source": "page"}
    return None


def diagnostic(code, erreur):
    """Ce que la dernière mesure dit de la panne, en une phrase : où chercher d'abord."""
    e = (erreur or "").lower()
    if code is not None:
        try:
            n = int(code)
        except (TypeError, ValueError):
            n = 0
        if n >= 500:
            return "Le serveur répond, mais par une erreur (HTTP %d) : ce qui sert le site derrière lui est en panne ou saturé." % n
        if n in (401, 403):
            return "Le serveur répond « accès refusé » (HTTP %d) : le site est protégé, ou ses droits de lecture ont changé." % n
        if n == 404:
            return "Le serveur répond, mais la page d'accueil est introuvable (HTTP 404) : site vidé, mal configuré, ou retiré du serveur."
        return "Le serveur répond par le code HTTP %d, qui n'est pas une page servie." % n
    if "adresse interne" in e:
        return "Le nom mène à une adresse interne : la sonde ne sort que vers l'Internet public."
    if "timed out" in e or "timeout" in e:
        return "Aucune réponse dans le délai : serveur surchargé, coupé du réseau, ou pare-feu."
    if any(x in e for x in ("name or service", "getaddrinfo", "nodename", "name resolution", "no address")):
        return "Le nom ne se résout plus : zone DNS, serveur de noms, ou nom de domaine échu."
    if any(x in e for x in ("certificate", "ssl", "tls")):
        return "La connexion chiffrée échoue : certificat échu, pour un autre nom, ou réglage TLS."
    if "refused" in e:
        return "Connexion refusée : le serveur web ne tourne pas, ou le port 443 est fermé."
    if "reset" in e:
        return "Connexion coupée par le serveur : il a accepté puis lâché la requête."
    return "Le site ne répond pas%s." % (" : " + str(erreur)[:120] if erreur else "")


def duree_texte(minutes):
    m = int(minutes or 0)
    if m < 1:
        return "moins d'une minute"
    if m < 120:
        return "%d min" % m
    return "%d h %02d" % (m // 60, m % 60) if m < 2880 else "%d jours" % (m // 1440)


def nombre(v, defaut, mini, maxi, nom):
    """Un entier borné, ou un refus qui se lit (jamais « invalid literal for int() »)."""
    if v is None or v == "":
        v = defaut
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError("« %s » doit être un nombre entier" % nom) from None
    return max(mini, min(n, maxi))


def brancher(ctx):
    db = ctx.stockage

    # ------------------------------------------------------------------ réglages
    def entier(nom, defaut):
        try:
            return int(ctx.reglage(nom, "") or defaut)
        except (TypeError, ValueError):
            return defaut

    def vrai(nom):
        try:
            v = ctx.reglage(nom, "")
        except Exception:
            return False
        return v is True or str(v).strip().lower() in ("1", "true", "vrai", "oui")

    # ------------------------------------------------------------------ qui est qui
    def systeme(compte):
        return not compte or compte in SYSTEME

    def admin(compte):
        return systeme(compte) or ctx.est_admin(compte)

    # ------------------------------------------------------------------ les comptes et le panneau
    def lecture(cap, **args):
        """(valeur, état) : « ok », « muet » (la capacité existe mais ne répond pas, ou la refuse à ce compte) ou « absent » (son module n'est pas là)."""
        try:
            r = ctx.executer_lecture(cap, **args)
        except PermissionError:
            return None, "absent"
        return (r, "ok") if r is not None else (None, "muet")

    def lire_comptes():
        r, e = lecture("comptes.lister")
        if e != "ok":
            return ([] if e == "absent" else None), e
        return [{"compte": c.get("compte"), "sites": [nom_hote(x) for x in (c.get("sites") or [])], "fp_account": str(c.get("fp_account") or "").strip().lower()}
                for c in (r.get("comptes") or []) if c.get("compte")], e

    def lire_panneau():
        r, e = lecture("fastpanel.sites")
        if e != "ok":
            return ([] if e == "absent" else None), e
        if isinstance(r, dict):
            r = r.get("sites") or []
        return [dict({"domaine": nom_hote(s.get("domaine")), "proprietaire": str(s.get("proprietaire") or ""), "ssl": s.get("ssl") or {}, "php": s.get("php", "")},
                     **{k: s[k] for k in ("statut", "erreurs", "code_http", "fichiers_mo", "bases_mo") if s.get(k) not in (None, "")})
                for s in (r or []) if isinstance(s, dict) and s.get("domaine")], e

    def miroir(cle, perime=False):
        r = db.lire("SELECT ts, contenu FROM miroir WHERE cle=?", (cle,))
        if not r or (not perime and time.time() - r[0]["ts"] > MIROIR_S):
            return None
        try:
            return json.loads(r[0]["contenu"])
        except ValueError:
            return None

    def quand_miroir(cle):
        """L'instant où ce miroir a été posé (secondes depuis 1970), ou None s'il n'existe pas ou s'il est périmé."""
        r = db.lire("SELECT ts FROM miroir WHERE cle=?", (cle,))
        return r[0]["ts"] if r and time.time() - r[0]["ts"] <= MIROIR_S else None

    def heure_locale(ts):
        """« AAAA-MM-JJ HH:MM:SS » à l'heure de la machine : le format et l'heure que la vue d'ensemble écrit déjà pour son propre relevé."""
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

    def poser_miroir(cle, valeur):
        db.ecrire("INSERT OR REPLACE INTO miroir(cle, ts, contenu) VALUES (?,?,?)", (cle, time.time(), json.dumps(valeur, ensure_ascii=False)))

    # ------------------------------------------------------------------ les sociétés
    def societes_connues():
        try:
            return [str(s) for s in ctx.societes()] or ["1"]
        except Exception:
            return ["1"]

    def superadmin(compte):
        if systeme(compte):
            return True
        try:
            return bool(ctx.est_superadmin(compte))
        except Exception:
            return False

    def noms_societes():
        """{id: nom} des sociétés que ce compte peut nommer (le module Sociétés les donne ; sans lui, l'identifiant sert de nom)."""
        r, _ = lecture("societes.lister")
        noms = {str(s.get("id")): str(s.get("nom") or s.get("id")) for s in (r.get("societes") or []) if isinstance(s, dict)} if isinstance(r, dict) else {}
        return noms

    class Regard:
        """Ce qu'on sait des comptes, du panneau et de la portée, pour UN appel : lu une fois, pas à chaque question.

        Trois étendues : un compte voit SES sites ; l'administrateur d'une société, ceux de sa société ; le superadministrateur, ceux de toutes
        (« large »). Une instance à une seule société n'a rien à cloisonner : son administrateur est « large » lui aussi."""

        def __init__(self, compte):
            self.compte = compte
            self.tout = admin(compte)
            self.super = superadmin(compte)
            self.multi = len(societes_connues()) > 1
            self.large = self.tout and (self.super or not self.multi)
            self.soc = "" if systeme(compte) else str(ctx.societe or ctx.societe_de(compte) or "1")
            self._soc_comptes, self._posees = {}, None
            if self.tout:
                self.cs, e1 = lire_comptes()
                self.pan, e2 = lire_panneau()
                self.comptes_surs, self.panneau_lu, self.comptes_absents = e1 != "muet", e2 == "ok", e1 == "absent"
            else:
                self.comptes_absents = False
                cs, mp = miroir("comptes"), miroir("panneau")
                pan, frais = (mp.get("sites"), bool(mp.get("lu"))) if isinstance(mp, dict) else (None, False)
                if cs is None:
                    cs, _ = lire_comptes()
                    if cs is None:
                        cs = miroir("comptes", perime=True)
                if pan is None:
                    pan, e2 = lire_panneau()
                    frais = e2 == "ok"
                    if pan is None:
                        mp = miroir("panneau", perime=True)
                        pan = mp.get("sites") if isinstance(mp, dict) else None
                self.comptes_surs = cs is not None                   # sait-on à qui sont les sites des AUTRES ? (sinon on ne laisse rien déclarer)
                moi, _ = lecture("comptes.moi")                      # sa propre fiche, tout de suite : pas besoin d'attendre le tour de sonde
                if isinstance(moi, dict):
                    cs = [x for x in (cs or []) if x.get("compte") != compte]
                    cs.append({"compte": compte, "sites": [nom_hote(x) for x in (moi.get("sites") or [])], "fp_account": str(moi.get("fp_account") or "").strip().lower()})
                self.cs, self.pan, self.panneau_lu = cs, pan, frais
            self.par_fp = {}
            for c in self.cs or []:
                if c.get("fp_account"):
                    self.par_fp.setdefault(c["fp_account"], []).append(c["compte"])
            self._carte = None

        def du_panneau(self, d):
            return next((s for s in (self.pan or []) if s["domaine"] == d), None)

        def proprietaires(self, d):
            """Les comptes qui ont ce site : déclaré, attribué, inscrit dans leur fiche, ou propriétaires du panneau par leur compte lié."""
            pris = {r["compte"] for r in db.lire("SELECT compte FROM sites WHERE domaine=?", (d,))}
            for c in self.cs or []:
                if d in c["sites"]:
                    pris.add(c["compte"])
            s = self.du_panneau(d)
            if s:
                pris |= set(self.par_fp.get(s["proprietaire"].lower(), []))
            return pris

        def en_ont_declare(self, d):
            """Déclaré, attribué ou inscrit dans une fiche — sans le panneau (un site du panneau ne se déclare pas, il s'attribue)."""
            pris = {r["compte"] for r in db.lire("SELECT compte FROM sites WHERE domaine=?", (d,))}
            for c in self.cs or []:
                if d in c["sites"]:
                    pris.add(c["compte"])
            return pris

        @property
        def carte(self):
            """{domaine: {origine, comptes, panneau}} des sites que CE compte voit. L'administrateur voit l'état de tous."""
            if self._carte is not None:
                return self._carte
            compte, tout, carte = self.compte, self.tout, {}

            def ajouter(d, origine, qui, pan=None):
                d = nom_hote(d)
                if not d:
                    return
                e = carte.setdefault(d, {"origine": origine, "comptes": [], "panneau": None})
                if qui and qui not in e["comptes"]:
                    e["comptes"].append(qui)
                if pan is not None:
                    e["panneau"] = pan
                    e["origine"] = "panneau"
            for r in db.lire("SELECT domaine, compte, origine FROM sites"):
                if tout or r["compte"] == compte:
                    ajouter(r["domaine"], r["origine"], r["compte"])
            for c in self.cs or []:
                if tout or c["compte"] == compte:
                    for d in c["sites"]:
                        ajouter(d, "compte", c["compte"])
            for s in self.pan or []:
                proprietaires = self.par_fp.get(s["proprietaire"].lower(), [])
                if tout or compte in proprietaires:
                    ajouter(s["domaine"], "panneau", None, s)
                    for o in proprietaires:
                        ajouter(s["domaine"], "panneau", o)
            for d, e in carte.items():
                e["societe"], e["societe_source"] = self.societe_selon(d, e["comptes"] if tout else self.proprietaires(d))
            if tout and not self.large:
                # L'administrateur d'une société : les sites de SA société (attribués, ou par leur compte), et les siens propres.
                carte = {d: e for d, e in carte.items() if e["societe"] == self.soc or compte in e["comptes"]}
            self._carte = carte
            return carte

        def societe_du_compte(self, x):
            if x not in self._soc_comptes:
                try:
                    self._soc_comptes[x] = str(ctx.societe_de(x) or "1")
                except Exception:
                    self._soc_comptes[x] = "1"
            return self._soc_comptes[x]

        def societe_selon(self, d, proprietaires):
            """(société, source) d'un site : celle qu'on lui a attribuée (« attribuee ») ; à défaut celle de son compte (« compte ») ; à défaut aucune."""
            if self._posees is None:
                self._posees = {r["domaine"]: r["societe"] for r in db.lire("SELECT domaine, societe FROM societes_site")}
            if d in self._posees:
                return self._posees[d], "attribuee"
            socs = {self.societe_du_compte(x) for x in proprietaires or ()}
            return (socs.pop(), "compte") if len(socs) == 1 else ("", "")

        def societe_de_site(self, d):
            return self.societe_selon(d, self.proprietaires(d))

        def dans(self, d):
            """Le domaine est-il dans la portée du compte : lui-même, ou un sous-domaine d'un de ses sites qui n'est pas suivi à part pour quelqu'un d'autre."""
            if self.large or d in self.carte:
                return True
            if not any(d.endswith("." + s) for s in self.carte):
                return False
            pr = self.proprietaires(d)
            if self.tout:
                # Un sous-domaine suivi à part (il a un compte, une société ou une ligne au panneau) n'entre que s'il est de la société de cet administrateur.
                soc = self.societe_selon(d, pr)[0]
                return soc == self.soc if (soc or pr or self.du_panneau(d)) else True
            if pr:
                return self.compte in pr
            return self.du_panneau(d) is None

        def exiger(self, domaine):
            d = nom_hote(domaine)
            if not d or not RE_DOMAINE.match(d):
                raise ValueError("nom de domaine invalide")
            if not self.dans(d):
                raise ValueError("site hors de ta portée")
            return d

        def domaines_connus(self):
            d = {nom_hote(r["domaine"]) for r in db.lire("SELECT domaine FROM sites")}
            for c in self.cs or []:
                d |= set(c["sites"])
            d |= {s["domaine"] for s in (self.pan or [])}
            return d

    def noter(acteur, verbe, domaine, detail=""):
        db.ecrire("INSERT INTO journal(ts, acteur, verbe, domaine, detail) VALUES (?,?,?,?,?)", (time.time(), acteur or "?", verbe, nom_hote(domaine), str(detail)[:300]))

    # ------------------------------------------------------------------ les voisins : ce que les autres modules savent déjà d'un site
    # Sites ne remesure rien de tout cela : il lit. Le Sensorium tient les fenêtres de maintenance, les alertes acceptées, le CMS et le trafic ; le panneau, le disque,
    # les bases, le courrier, les sauvegardes, les analyses et la fin de support de PHP ; le DNS, l'échéance du nom. Ces lectures demandent des droits qu'un compte
    # ordinaire n'a pas : la sonde, qui tourne sans compte, les recopie dans le miroir, et chacun n'y lit que ce qui touche SES sites.
    def instant_utc(texte):
        """« AAAA-MM-JJ HH:MM:SS » (UTC, le format du Sensorium) en secondes depuis 1970, ou None."""
        try:
            return float(calendar.timegm(time.strptime(str(texte)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")))
        except (TypeError, ValueError):
            return None

    def relever_sensorium():
        """À chaque tour : les fenêtres de maintenance et les alertes de site acceptées. Une fenêtre posée ou une alerte acceptée dans le Sensorium vaut aussi ici."""
        e, st = lecture("sensorium.etat")
        if st == "absent":
            return poser_miroir("sensorium", {"lu": False, "fenetres": [], "acceptees": {}})
        if st != "ok" or not isinstance(e, dict) or e.get("muet"):
            return None                                                   # il se tait : on garde ce qu'on savait
        acceptees, suivis = {}, {}
        for r in e.get("rows") or []:
            wk = str(r.get("wkey") or "") if isinstance(r, dict) else ""
            if not wk.startswith("web.") or len(wk) < 5:
                continue
            d = nom_hote(wk[4:])
            # Ce que le Sensorium voit de ce site DEPUIS la machine : sa mesure, s'il en fait une alerte, et les gestes de réparation qu'il propose alors.
            suivis[d] = {"cle": wk, "valeur": str(r.get("value") or "")[:160], "alerte": r.get("severity") == "warning",
                         "gestes": [{"id": str(g.get("id") or ""), "libelle": str(g.get("libelle") or "")} for g in (r.get("gestes") or []) if isinstance(g, dict) and g.get("id")][:6]}
            if isinstance(r.get("acquit"), dict):
                acceptees[d] = {"raison": str(r["acquit"].get("raison") or "")[:200], "jusqu_a": instant_utc(r["acquit"].get("jusqua")), "par": str(r["acquit"].get("par") or "")}
        f, _ = lecture("sensorium.fenetres")
        fen = []
        for x in ((f.get("vivantes") or []) + (f.get("finies") or [])) if isinstance(f, dict) else (e.get("fenetres") or []):
            if isinstance(x, dict) and not x.get("annulee"):
                a, b = instant_utc(x.get("debut")), instant_utc(x.get("fin"))
                if a is not None and b is not None:
                    fen.append({"id": x.get("id"), "portee": str(x.get("portee") or "*"), "debut": a, "fin": b, "motif": str(x.get("motif") or "")[:200], "par": str(x.get("par") or "")})
        poser_miroir("sensorium", {"lu": True, "fenetres": fen, "acceptees": acceptees, "suivis": suivis})

    def relever_voisins(echeance=None):
        """Une fois par heure : le CMS et le trafic (Sensorium), les bases, le courrier, les sauvegardes, les analyses et la fin de support de PHP (panneau), l'échéance des noms (DNS).
        Chaque source absente ou muette laisse sa rubrique vide (et le dit : « lu » faux) ; rien n'est inventé."""
        v = {"ts": time.time(), "cms": {}, "trafic": {}, "bases": {}, "courrier": {}, "sauvegardes": None, "php": {}, "analyses": {}, "noms": {}, "sources": {}}
        ancien = miroir("voisins", perime=True)
        ancien = ancien if isinstance(ancien, dict) else {}

        def source(rubrique, cap, **args):
            if echeance is not None and time.time() > echeance:
                r, st = None, "muet"                                    # plus le temps dans ce tour de sonde : cette rubrique attendra le suivant
                v["ts"] = ancien.get("ts") or 0
            else:
                r, st = lecture(cap, **args)
            v["sources"][rubrique] = st
            if st == "muet" and rubrique in ancien:
                v[rubrique] = ancien[rubrique]                          # elle se tait : on garde ce qu'on savait, on ne vide pas la rubrique
            return r if st == "ok" else None
        r = source("cms", "sensorium.entite", nom="cms_sites")
        for x in r if isinstance(r, list) else []:
            if isinstance(x, dict) and x.get("domain") and x.get("cms_type"):
                v["cms"][nom_hote(x["domain"])] = {"type": str(x["cms_type"]), "version": str(x.get("version") or ""), "theme": str(x.get("theme") or ""), "extensions": x.get("plugins_count")}
        r = source("trafic", "sensorium.secu")
        if isinstance(r, dict):
            robots = r.get("robots") if isinstance(r.get("robots"), dict) else {}
            for x in r.get("sites") or []:
                if isinstance(x, dict) and x.get("site"):
                    v["trafic"][nom_hote(x["site"])] = {"requetes": x.get("n"), "robots": x.get("b"), "jours": 9, "premiers_robots": [str(y.get("robot")) for y in (robots.get(x["site"]) or [])[:3] if isinstance(y, dict)]}
        r = source("bases", "fastpanel.bases")
        for x in r if isinstance(r, list) else []:
            if isinstance(x, dict) and x.get("site"):
                v["bases"].setdefault(nom_hote(x["site"]), []).append({"nom": str(x.get("nom") or ""), "moteur": str(x.get("moteur") or ""), "taille_mo": x.get("taille_mo"), "derniere_copie": x.get("derniere_copie")})
        r = source("courrier", "fastpanel.mail")
        for x in r if isinstance(r, list) else []:
            if isinstance(x, dict) and x.get("domaine"):
                c = v["courrier"].setdefault(nom_hote(x["domaine"]), {"boites": 0, "utilise_mo": 0, "quota_mo": 0})
                c["boites"] += 1
                for k in ("utilise_mo", "quota_mo"):
                    if isinstance(x.get(k), (int, float)):
                        c[k] += x[k]
        r = source("sauvegardes", "fastpanel.audit")
        s = r.get("sauvegardes") if isinstance(r, dict) else None
        if isinstance(s, dict):
            v["sauvegardes"] = {"seuil_j": s.get("seuil_j"), "sans": [nom_hote(d) for d in s.get("sans") or []],
                                "perimees": {nom_hote(x["domaine"]): x.get("derniere") for x in s.get("perimees") or [] if isinstance(x, dict) and x.get("domaine")}}
        r = source("php", "fastpanel.php")
        if isinstance(r, dict):
            for etat_, cle in (("depassee", "fin_de_support"), ("bientot", "bientot")):
                for x in r.get(cle) or []:
                    if isinstance(x, dict) and x.get("domaine"):
                        v["php"].setdefault(nom_hote(x["domaine"]), {"etat": etat_, "version": str(x.get("php") or ""), "fin": str(x.get("fin") or "")})
        r = source("analyses", "fastpanel.scans_cibles")
        for x in (r.get("sites") or []) if isinstance(r, dict) else []:
            if isinstance(x, dict) and x.get("domaine"):
                v["analyses"][nom_hote(x["domaine"])] = {"actif": bool(x.get("actif")), "planning": str(x.get("planning") or ""), "dernier": x.get("dernier"), "rapports": x.get("rapports")}
        r = source("noms", "dns.etat")
        for x in (r.get("zones") or []) if isinstance(r, dict) else []:
            if isinstance(x, dict) and x.get("domaine") and x.get("expiration"):
                v["noms"][nom_hote(x["domaine"])] = str(x["expiration"])[:10]
        poser_miroir("voisins", v)

    class Voisins:
        """Ce que le miroir sait des voisins, pour UN appel (ou un passage de détecteur) : lu une fois."""

        def __init__(self):
            ms = miroir("sensorium", perime=True)
            self.sens = ms if isinstance(ms, dict) else {}
            mv = miroir("voisins", perime=True)
            self.v = mv if isinstance(mv, dict) else {}
            self.maintenant = time.time()

        def maintenance(self, d):
            """La fenêtre de maintenance du Sensorium qui couvre ce site en ce moment (tout, tous les sites, les services, ou ce site-là), ou None."""
            for f in self.sens.get("fenetres") or []:
                if f["debut"] <= self.maintenant < f["fin"] and f["portee"] in ("*", "famille:web", "domaine:services", "site:" + d, "site:www." + d):
                    return {"id": f["id"], "fin": f["fin"], "motif": f["motif"], "par": f.get("par", ""), "ce_site": f["portee"].startswith("site:")}
            return None

        def fenetres_de(self, d, a, b):
            """Les fenêtres (passées ou en cours) qui ont couvert ce site entre deux instants : pour son calendrier."""
            return [f for f in self.sens.get("fenetres") or [] if f["debut"] < b and f["fin"] >= a and f["portee"] in ("*", "famille:web", "domaine:services", "site:" + d, "site:www." + d)]

        def vu_de_la_machine(self, d):
            """Ce que le Sensorium voit de ce site depuis la machine ({cle, valeur, alerte, gestes}), ou None s'il ne le suit pas (un site hébergé ailleurs, ou pas de Sensorium)."""
            return (self.sens.get("suivis") or {}).get(d) or (self.sens.get("suivis") or {}).get("www." + d)

        def acceptee(self, d):
            a = (self.sens.get("acceptees") or {}).get(d)
            return a if a and (a.get("jusqu_a") is None or a["jusqu_a"] > self.maintenant) else None

        def nom(self, d):
            """L'échéance du nom de domaine qui porte ce site : {zone, expiration, jours}, ou None si le DNS ne la connaît pas."""
            for zone, exp in sorted((self.v.get("noms") or {}).items(), key=lambda x: -len(x[0])):
                if d == zone or d.endswith("." + zone):
                    t = instant_utc(exp + " 00:00:00")
                    return {"zone": zone, "expiration": exp, "jours": int((t - self.maintenant) // 86400) if t is not None else None}
            return None

        def sauvegarde(self, d):
            """{etat: « ok » | « sans » | « perimee », derniere, seuil_j}, ou None si le panneau n'a pas dit ce qu'il sauvegarde."""
            s = self.v.get("sauvegardes")
            if not isinstance(s, dict):
                return None
            if d in (s.get("sans") or []):
                return {"etat": "sans", "derniere": None, "seuil_j": s.get("seuil_j")}
            if d in (s.get("perimees") or {}):
                return {"etat": "perimee", "derniere": s["perimees"][d], "seuil_j": s.get("seuil_j")}
            return {"etat": "ok", "derniere": None, "seuil_j": s.get("seuil_j")}

        def resume(self, d, panneau, ligne_panneau=None):
            """Ce qui entre dans la ligne d'un site : court, pour la liste, les chiffres de la vue d'ensemble et les alertes."""
            p = ligne_panneau or {}
            poids = [p.get(k) for k in ("fichiers_mo", "bases_mo") if isinstance(p.get(k), (int, float))]
            return {"maintenance": self.maintenance(d), "acceptee": self.acceptee(d), "cms": (self.v.get("cms") or {}).get(d), "nom": self.nom(d),
                    "sauvegarde": self.sauvegarde(d) if panneau else None, "php_fin": (self.v.get("php") or {}).get(d) if panneau else None,
                    "disque_mo": round(sum(poids), 2) if poids else None,
                    "analyse": ((self.v.get("analyses") or {}).get(d) or ({"actif": False, "dernier": None} if (self.v.get("sources") or {}).get("analyses") == "ok" else None)) if panneau else None}

        def detail(self, d, panneau, ligne_panneau):
            """Ce qui entre dans la fiche d'un site : tout ce que les voisins en savent, et de quand date la lecture."""
            p = ligne_panneau or {}
            return dict(self.resume(d, panneau), lu=self.v.get("ts"), sources=self.v.get("sources") or {}, sensorium_lu=bool(self.sens.get("lu")),
                        trafic=(self.v.get("trafic") or {}).get(d),
                        hebergement={"statut": p.get("statut"), "disque_mo": p.get("fichiers_mo"), "bases_mo": p.get("bases_mo"), "erreurs": p.get("erreurs"), "code_http": p.get("code_http"),
                                     "bases": (self.v.get("bases") or {}).get(d) or [], "courrier": (self.v.get("courrier") or {}).get(d),
                                     "analyse": (self.v.get("analyses") or {}).get(d)} if panneau else None)

    # ------------------------------------------------------------------ les incidents : une panne est un objet
    def fait_incident(iid, acteur, genre, texte="", ts=None):
        return db.ecrire("INSERT INTO incident_faits(incident, ts, acteur, genre, texte) VALUES (?,?,?,?,?)", (iid, ts or time.time(), acteur or "?", genre, str(texte)[:500]))

    def incident_ouvert(d):
        r = db.lire("SELECT id, etat FROM incidents WHERE domaine=? AND etat IN ('ouvert','depannage')", (d,))
        return r[0] if r else None

    def ouvrir_incident(d, debut, code, erreur):
        if incident_ouvert(d):
            return None
        iid = db.ecrire("INSERT INTO incidents(domaine, debut, etat, diagnostic, code, erreur) VALUES (?,?,?,?,?,?)", (d, debut, "ouvert", diagnostic(code, erreur), code, erreur or ""))
        fait_incident(iid, "sonde", "ouvert", "Panne confirmée — %s" % (erreur or "HTTP %s" % code), debut)
        return iid

    def retablir_incident(d, quand, texte):
        """Le site répond de nouveau. Si personne n'a touché à l'incident, il se clôt seul ; sinon il attend que celui qui s'en occupait en note la cause."""
        i = incident_ouvert(d)
        if not i:
            return
        suivi = db.lire("SELECT 1 FROM incidents WHERE id=? AND pris_par != ''", (i["id"],)) or db.lire("SELECT 1 FROM incident_faits WHERE incident=? AND acteur != 'sonde' LIMIT 1", (i["id"],))
        fait_incident(i["id"], "sonde", "retour", texte, quand)
        if suivi:
            db.ecrire("UPDATE incidents SET etat='retabli', fin=?, connu_jusqu=NULL WHERE id=?", (quand, i["id"]))
        else:
            db.ecrire("UPDATE incidents SET etat='resolu', fin=?, clos_par='sonde', connu_jusqu=NULL WHERE id=?", (quand, i["id"]))
            fait_incident(i["id"], "sonde", "clos", "Revenu seul : incident clos, cause non notée.", quand)

    # ------------------------------------------------------------------ la sonde
    def dernieres_mesures():
        return {r["domaine"]: r for r in db.lire("SELECT m.domaine, m.ts, m.code, m.ms, m.up, m.ssl_jours, m.erreur FROM mesures m "
                                                 "JOIN (SELECT domaine, MAX(id) i FROM mesures GROUP BY domaine) x ON x.i = m.id")}

    def tour():
        """Ce qu'une mesure a besoin de savoir, lu une fois par tour : les réglages, et les certificats.
        Les certificats sont l'affaire du module Certificats (Sécurité) : il les lit, les alerte, tient le seuil et le quota. Quand il est là, Sites ne refait
        rien de tout cela : il recopie les jours restants pour sa vue et sa courbe. Sans lui, Sites garde sa propre lecture, pour ne pas devenir aveugle."""
        etat_c, ec = lecture("certificats.etat")
        par_cert = {nom_hote(x.get("hote")): x for x in (etat_c.get("certificats") or []) if isinstance(x, dict)} if isinstance(etat_c, dict) else None
        return {"delai": entier("delai_sonde_s", 8), "seuil": max(1, min(entier("echecs_avant_panne", 2), 5)), "interne": vrai("sonde_interne"),
                "proteges": vrai("proteges_en_ligne"), "tenu": ec != "absent", "par_cert": par_cert}

    def mesurer(c, d, t, avant, connu):
        """Une mesure d'un site : la requête chronométrée, le certificat, la ligne en base, la panne ou le retour s'il y a lieu (et leur incident), l'objet du registre.
        `avant` est sa dernière mesure, `connu` son état vu (up, depuis) ; la sonde et la relève à la demande passent toutes deux par ici."""
        delai, seuil = t["delai"], t["seuil"]
        code, ms, erreur = _sonder_http(d, delai, True) if t["interne"] else _sonder_http(d, delai)
        bon = code is not None and (200 <= int(code) < 400 or (t["proteges"] and int(code) in (401, 403)))
        up = 1 if bon else 0
        if t["tenu"]:
            x = (t["par_cert"] or {}).get(d)
            if t["par_cert"] is None:
                jours = avant["ssl_jours"] if avant else None      # Certificats est là mais se tait : on garde ce qu'on savait, on ne le double pas
            else:
                jours = x.get("jours") if x and isinstance(x.get("jours"), int) else None
        elif avant and avant["ssl_jours"] is not None and int(time.time() // CERT_REFRAICHI_S) == int(avant["ts"] // CERT_REFRAICHI_S):
            # Une lecture par heure d'horloge. Comparer à l'âge de la dernière MESURE (cinq minutes, toujours) ne relisait jamais le certificat :
            # le nombre de jours restait figé à sa première lecture.
            jours = avant["ssl_jours"]
        elif code is None and (erreur or "").startswith("adresse interne"):
            jours = None
        else:
            jours = _cert_jours(d, delai)
            if jours is None and avant and code is None:
                jours = avant["ssl_jours"]                          # le site ne répond plus du tout : sa dernière date connue reste la meilleure
        maintenant = time.time()
        db.ecrire("INSERT INTO mesures(ts, domaine, code, ms, up, ssl_jours, erreur) VALUES (?,?,?,?,?,?,?)", (maintenant, d, code, ms, up, jours, erreur))
        douteux = False
        if connu is None:
            db.ecrire("INSERT OR REPLACE INTO etat_vu(domaine, up, depuis, ts) VALUES (?,?,?,?)", (d, up, maintenant, maintenant))
            db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail) VALUES (?,?,?,?)",
                      (maintenant, d, "decouverte", "Première observation — %s (%s, %d ms)" % ("en ligne" if up else "hors ligne", ("HTTP %s" % code) if code is not None else "sans réponse", ms)))
        elif connu[0] != up:
            tombe = maintenant
            if not up and seuil > 1:
                # Une mesure ratée n'est pas une panne (un paquet perdu, une seconde de trop) : il en faut `seuil` de suite, celle-ci comprise.
                der = db.lire("SELECT ts, up FROM mesures WHERE domaine=? ORDER BY id DESC LIMIT ?", (d, seuil))
                if len(der) < seuil or any(x["up"] for x in der):
                    douteux = True
                else:
                    tombe = der[-1]["ts"]                            # la panne a commencé au premier échec, pas à sa confirmation
            if not douteux:
                minutes = max(0, int((tombe - connu[1]) // 60))
                db.ecrire("INSERT OR REPLACE INTO etat_vu(domaine, up, depuis, ts) VALUES (?,?,?,?)", (d, up, tombe, maintenant))
                if up:
                    texte = "De nouveau en ligne après %s (HTTP %s, %d ms)." % (duree_texte(minutes), code, ms)
                    db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail, duree_min) VALUES (?,?,?,?,?)", (maintenant, d, "retour", texte, minutes))
                    retablir_incident(d, maintenant, texte)
                    c.emettre("site.retour", objet=("site", d), donnees={"domaine": d, "duree_min": minutes, "ms": ms}, compte="")
                else:
                    db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail, duree_min) VALUES (?,?,?,?,?)",
                              (tombe, d, "panne", "Injoignable — %s" % (erreur or "HTTP %s" % code), minutes))
                    iid = ouvrir_incident(d, tombe, code, erreur)
                    c.emettre("site.panne", objet=("site", d), donnees={"domaine": d, "code": code, "erreur": erreur, "incident": iid}, compte="")
        # Tant que la panne n'est pas confirmée, l'objet reste « en ligne » (marqué douteux) : aucun constat ne s'ouvre sur une seule mesure.
        c.poser("site", d, d, etat="en_ligne" if (up or douteux) else "hors_ligne",
                donnees={"code": code, "ms": ms, "ssl_jours": jours, "erreur": erreur, "mesure": maintenant, "douteux": douteux}, compte="")
        return {"domaine": d, "ts": maintenant, "code": code, "ms": ms, "up": bool(up), "erreur": erreur, "ssl_jours": jours, "douteux": douteux}

    def relever_apercus(doms, t, echeance, sources_sures):
        """L'aperçu des sites qui répondent : quelques-uns par tour, les plus anciens d'abord, une fois par jour chacun. La page est lue une fois, puis son icône
        et — si elle en déclare une sur son propre nom — son image de présentation. Une page illisible garde l'aperçu d'avant, et le dit."""
        maintenant = time.time()
        connus = {r["domaine"]: r["ts"] for r in db.lire("SELECT domaine, ts FROM apercus")}
        en_ligne = {r["domaine"] for r in db.lire("SELECT domaine FROM etat_vu WHERE up=1")}
        a_lire = sorted((d for d in doms if d in en_ligne and connus.get(d, 0) < maintenant - APERCU_S), key=lambda d: connus.get(d, 0))
        for d in a_lire[:APERCUS_PAR_TOUR]:
            if time.time() > echeance:
                break
            texte, adresse = _lire_page(d, t["delai"], True) if t["interne"] else _lire_page(d, t["delai"])
            if not texte:
                if d in connus:
                    db.ecrire("UPDATE apercus SET ts=?, erreur=? WHERE domaine=?", (maintenant, "page illisible au dernier passage", d))
                else:
                    db.ecrire("INSERT INTO apercus(domaine, ts, erreur) VALUES (?,?,?)", (d, maintenant, "page illisible"))
                continue
            p = tete_html(texte, adresse)
            icone = _lire_image(p["icone"], d, t["delai"], t["interne"], ICONE_MAX) if p["icone"] else ""
            image = _lire_image(p["image"], d, t["delai"], t["interne"], IMAGE_MAX) if p["image"] and time.time() < echeance else ""
            db.ecrire("INSERT OR REPLACE INTO apercus(domaine, ts, titre, description, generateur, langue, icone, image, erreur) VALUES (?,?,?,?,?,?,?,?,'')",
                      (d, maintenant, p["titre"], p["description"], p["generateur"], p["langue"], icone, image))
        if sources_sures:
            suivis = set(doms)
            for d in connus:
                if d not in suivis:
                    db.ecrire("DELETE FROM apercus WHERE domaine=?", (d,))

    def apercus_legers():
        """{domaine: {titre, generateur, icone}} pour la liste : l'icône n'y entre que si elle est petite."""
        return {r["domaine"]: {"titre": r["titre"], "generateur": r["generateur"], "icone": r["icone"] if len(r["icone"]) <= ICONE_EN_LISTE else ""}
                for r in db.lire("SELECT domaine, titre, generateur, icone FROM apercus")}

    def sonde(c):
        t = tour()
        delai = t["delai"]
        debut = time.time()
        # Un site coûte au pire deux requêtes puis deux lectures de certificat : on s'arrête tant qu'il reste de quoi finir le suivant dans la durée du moteur.
        limite = max(delai, min(BUDGET_SONDE_S, DUREE_MAX_SONDE_S - 10 - 4 * delai))
        cs, e1 = lire_comptes()
        pan, e2 = lire_panneau()
        if e1 != "muet":
            poser_miroir("comptes", cs)                                  # le miroir des comptes ordinaires (absent : une liste vide, et c'est vrai)
        if e2 != "muet":
            poser_miroir("panneau", {"lu": e2 == "ok", "sites": pan})      # « lu » : le panneau a répondu (absent, il n'y a rien à lire, et on le dit)
        if t["tenu"]:
            s_c, _ = lecture("certificats.seuil")
            ancien = miroir("certificats", perime=True) or {}
            poser_miroir("certificats", {"tenu": True, "seuil": int(s_c["jours"]) if isinstance(s_c, dict) and isinstance(s_c.get("jours"), int) else ancien.get("seuil", 21)})
        else:
            poser_miroir("certificats", {"tenu": False})
        connus = {nom_hote(r["domaine"]) for r in db.lire("SELECT domaine FROM sites")}
        for x in cs or []:
            connus |= set(x["sites"])
        connus |= {s["domaine"] for s in (pan or [])}
        doms = sorted(x for x in connus if RE_DOMAINE.match(x))
        avant_tous = dernieres_mesures()
        doms.sort(key=lambda x: (avant_tous.get(x) or {}).get("ts", 0))        # les moins récemment mesurés d'abord : un budget épuisé tourne
        vus = {r["domaine"]: (r["up"], r["depuis"]) for r in db.lire("SELECT domaine, up, depuis FROM etat_vu")}
        for d in doms:
            if time.time() - debut > limite:
                break
            mesurer(c, d, t, avant_tous.get(d), vus.get(d))
        maintenant = time.time()
        # Ce qu'on ne suit plus (retiré, sorti d'une fiche ou du panneau) quitte le registre : sinon son dernier état resterait un constat pour toujours.
        # Seulement si les deux sources ont répondu : un panneau muet n'a pas « perdu » ses sites.
        if e1 != "muet" and e2 != "muet":
            suivis = set(doms)
            for o in c.lister(portee=c.TOUT, type="site"):
                if o["id"] not in suivis:
                    c.retirer("site", o["id"])
            for r in db.lire("SELECT domaine FROM etat_vu"):
                if r["domaine"] not in suivis:
                    db.ecrire("DELETE FROM etat_vu WHERE domaine=?", (r["domaine"],))
            for i in db.lire("SELECT id, domaine FROM incidents WHERE etat IN ('ouvert','depannage')"):
                if i["domaine"] not in suivis:
                    db.ecrire("UPDATE incidents SET etat='resolu', fin=?, clos_par='sonde', cause=CASE WHEN cause='' THEN 'Le site n''est plus suivi.' ELSE cause END, connu_jusqu=NULL WHERE id=?", (maintenant, i["id"]))
                    fait_incident(i["id"], "sonde", "clos", "Le site n'est plus suivi : incident clos.", maintenant)
        # Un site déjà en panne quand les incidents sont arrivés (ou dont l'incident s'est perdu) en reçoit un, daté du début de sa panne.
        for r in db.lire("SELECT e.domaine, e.depuis FROM etat_vu e WHERE e.up=0 AND NOT EXISTS (SELECT 1 FROM incidents i WHERE i.domaine=e.domaine AND i.etat IN ('ouvert','depannage'))"):
            m = db.lire("SELECT code, erreur FROM mesures WHERE domaine=? ORDER BY id DESC LIMIT 1", (r["domaine"],))
            ouvrir_incident(r["domaine"], r["depuis"], m[0]["code"] if m else None, m[0]["erreur"] if m else "")
        garde = entier("retention_j", 90)
        db.ecrire("DELETE FROM mesures WHERE ts < ?", (maintenant - garde * 86400,))
        db.ecrire("DELETE FROM evenements_site WHERE ts < ?", (maintenant - garde * 86400,))
        db.ecrire("DELETE FROM journal WHERE ts < ?", (maintenant - max(garde, JOURNAL_GARDE_J) * 86400,))
        db.ecrire("DELETE FROM accords WHERE jusqu_a < ?", (maintenant - COTE_GARDE_J * 86400,))
        db.ecrire("DELETE FROM liens_retires WHERE lot < ?", (maintenant - COTE_GARDE_J * 86400,))
        # Les voisins, en dernier : les mesures d'abord. Le Sensorium à chaque tour (une fenêtre posée doit valoir vite), le reste une fois par heure, s'il reste du temps.
        relever_sensorium()
        mv = miroir("voisins", perime=True)
        if (not isinstance(mv, dict) or maintenant - (mv.get("ts") or 0) > VOISINS_S) and time.time() - debut < DUREE_MAX_SONDE_S - 90:
            relever_voisins(debut + DUREE_MAX_SONDE_S - 40)              # le panneau peut être lent : ce qui ne tient pas dans ce tour se lira au suivant
        relever_apercus(doms, t, debut + DUREE_MAX_SONDE_S - 60, e1 != "muet" and e2 != "muet")
        vieux =maintenant - max(garde, INCIDENT_GARDE_J) * 86400
        db.ecrire("DELETE FROM incident_faits WHERE incident IN (SELECT id FROM incidents WHERE etat='resolu' AND fin < ?)", (vieux,))
        db.ecrire("DELETE FROM incidents WHERE etat='resolu' AND fin < ?", (vieux,))
        db.ecrire("DELETE FROM preuves WHERE cree < ?", (maintenant - PREUVE_GARDE_J * 86400,))
        db.ecrire("DELETE FROM alertes_acceptees WHERE jusqu_a < ?", (maintenant,))

    def objets_site(c, etat=None):
        return c.lister(portee=c.TOUT, type="site", etat=etat or "")

    def det_panne(c):
        # Une panne dite « connue » (quelqu'un s'en occupe et l'a dit) se tait jusqu'à l'échéance : l'incident reste ouvert, le constat ne sonne plus.
        connues = {r["domaine"] for r in db.lire("SELECT domaine FROM incidents WHERE etat IN ('ouvert','depannage') AND connu_jusqu > ?", (time.time(),))}
        vo, sortie = Voisins(), []
        for o in objets_site(c, "hors_ligne"):
            d = o["id"]
            if d in connues or tu(vo, d):
                continue
            vu = vo.vu_de_la_machine(d)
            if vu and vu["alerte"]:
                continue                 # le Sensorium le voit tomber lui aussi et en fait déjà son alerte : une seule suffit (l'incident, lui, est ouvert ici)
            detail = o["donnees"].get("erreur") or ("code %s" % o["donnees"].get("code"))
            if vu:
                # Lui le voit répondre, d'ici il ne répond pas : la panne est sur le chemin, pas dans le site. Seul Sites le sait, donc Sites le dit.
                detail += " — depuis la machine, le Sensorium le voit répondre (%s) : cherche entre l'Internet et la machine (DNS, réseau, pare-feu, certificat)" % vu["valeur"]
            sortie.append({"objet": ("site", d), "titre": "Site hors ligne : %s" % d, "detail": detail, "niveau": "critique"})      # une panne : le niveau qui passe les canaux les plus pressants
        return sortie

    def tu(vo, d):
        """Le Sensorium a-t-il fait taire ce site : une fenêtre de maintenance le couvre, ou son alerte y a été acceptée ? Ce qui se tait là-bas se tait ici."""
        return bool(vo.maintenance(d) or vo.acceptee(d))

    def proprietaires_miroir():
        """{domaine: {comptes}} d'après la table sites et les miroirs de la sonde : ce qu'un détecteur, qui tourne sans compte, sait des propriétaires sans rien relire."""
        cs = miroir("comptes", perime=True) or []
        mp = miroir("panneau", perime=True) or {}
        par_fp, pr = {}, {}
        for x in cs:
            if x.get("fp_account"):
                par_fp.setdefault(x["fp_account"], []).append(x["compte"])
            for d in x.get("sites") or []:
                pr.setdefault(d, set()).add(x["compte"])
        for r in db.lire("SELECT domaine, compte FROM sites"):
            pr.setdefault(nom_hote(r["domaine"]), set()).add(r["compte"])
        for s in (mp.get("sites") or []) if isinstance(mp, dict) else []:
            for o in par_fp.get(str(s.get("proprietaire") or "").lower(), []):
                pr.setdefault(s["domaine"], set()).add(o)
        return pr

    def det_panne_proprietaire(c):
        """La panne d'un site, dite à SON propriétaire (un constat adressé à son compte) : le constat « panne » ne va qu'aux administrateurs.
        Un propriétaire qui est administrateur a déjà le sien ; une panne dite connue se tait pour lui aussi."""
        ouverts = {r["domaine"]: r for r in db.lire("SELECT id, domaine, diagnostic, connu_jusqu FROM incidents WHERE etat IN ('ouvert','depannage')")}
        pr, maintenant, sortie, vo = proprietaires_miroir(), time.time(), [], Voisins()
        for o in objets_site(c, "hors_ligne"):
            d = o["id"]
            i = ouverts.get(d)
            if (i and (i["connu_jusqu"] or 0) > maintenant) or tu(vo, d):
                continue
            for k, compte in enumerate(sorted(x for x in pr.get(d, ()) if x and not admin(x))):
                # La clé d'un constat est son objet : un site à plusieurs comptes en ouvre un par compte, sous un identifiant qui les distingue.
                sortie.append({"objet": ("site", d if k == 0 else "%s#%s" % (d, compte)), "compte": compte, "titre": "Ton site %s ne répond pas" % d, "niveau": "critique",
                               "detail": (i["diagnostic"] if i else "") or o["donnees"].get("erreur") or ("code %s" % o["donnees"].get("code"))})
        return sortie

    def det_lenteur(c):
        seuil = entier("lent_ms", 3000)
        vo = Voisins()
        return [{"objet": ("site", o["id"]), "titre": "Site lent : %s (%d ms)" % (o["id"], o["donnees"]["ms"]),
                 "detail": "le code HTTP est bon, mais pour un visiteur c'est déjà lent (au-delà de %d ms)" % seuil}
                for o in objets_site(c, "en_ligne") if not o["donnees"].get("douteux") and (o["donnees"].get("ms") or 0) >= seuil and not vo.maintenance(o["id"])]

    def certificats_tenus():
        """(tenu, seuil) : le module Certificats est-il là, et quel seuil fait foi — le sien s'il est là, le réglage de Sites sinon."""
        m = miroir("certificats", perime=True)
        if isinstance(m, dict) and m.get("tenu"):
            return True, int(m.get("seuil") or 21)
        return False, entier("ssl_court_j", 21)

    def det_certificat(c):
        if lecture("certificats.seuil")[1] != "absent":
            return []                                                   # le module Certificats ouvre déjà ce constat (expiration_proche) : un seul suffit
        seuil = entier("ssl_court_j", 21)
        sortie = []
        for o in objets_site(c):
            j = o["donnees"].get("ssl_jours")
            if isinstance(j, int) and j < seuil:
                if j < 0:
                    titre, detail = "Certificat de %s : échu depuis %d jour(s)" % (o["id"], -j), "les navigateurs refusent le site"
                else:
                    titre, detail = "Certificat de %s : %d jour(s)" % (o["id"], j), "renouvellement urgent" if j < 7 else "à renouveler avant l'échéance"
                sortie.append({"objet": ("site", o["id"]), "titre": titre, "detail": detail})
        return sortie

    def det_demandes(c):
        return [{"objet": ("site", r["domaine"]), "titre": "Adossement demandé : %s" % r["domaine"], "detail": "%s demande que ce site passe au panneau. %s" % (r["compte"], r["message"])}
                for r in db.lire("SELECT domaine, compte, message FROM demandes WHERE statut='ouverte'")]

    # ------------------------------------------------------------------ lectures
    def disponibilites(jours, domaines=None):
        maintenant = time.time()
        depuis = maintenant - jours * 86400
        suivi = maintenant - SUIVI_J * 86400
        lignes = db.lire("SELECT domaine, COUNT(*) n, SUM(up) u, AVG(CASE WHEN up=1 THEN ms END) moy, MAX(CASE WHEN up=1 THEN ms END) mx, MAX(ts) dernier "
                         "FROM mesures WHERE ts >= ? GROUP BY domaine ORDER BY domaine", (depuis,))
        ev = {}
        for r in db.lire("SELECT domaine, genre, COUNT(*) n, COALESCE(SUM(duree_min),0) m FROM evenements_site WHERE genre IN ('panne','retour') AND ts >= ? GROUP BY domaine, genre", (depuis,)):
            ev.setdefault(r["domaine"], {})[r["genre"]] = (r["n"], r["m"])
        # Une panne qui dure encore n'a pas de « retour » : elle compte quand même, et son temps court jusqu'à maintenant.
        en_cours = {r["domaine"]: r["depuis"] for r in db.lire("SELECT domaine, depuis FROM etat_vu WHERE up=0")}
        sortie, plus_suivis = [], []
        for r in lignes:
            d = r["domaine"]
            if domaines is not None and d not in domaines:
                continue
            if r["dernier"] < suivi:
                plus_suivis.append(d)
                continue
            n_panne = ev.get(d, {}).get("panne", (0, 0))[0]
            n_retour, m = ev.get(d, {}).get("retour", (0, 0))
            dure = 1 if d in en_cours else 0
            if dure:
                m += int((maintenant - max(en_cours[d], depuis)) // 60)
            sortie.append({"domaine": d, "mesures": r["n"], "disponibilite": round(100.0 * (r["u"] or 0) / r["n"], 2), "reponse_moy_ms": int(r["moy"]) if r["moy"] is not None else None,
                           "reponse_max_ms": int(r["mx"]) if r["mx"] is not None else None, "pannes": max(n_panne, n_retour + dure), "en_panne": bool(dure),
                           "indisponible_min": m, "indisponible": duree_texte(m)})
        return sortie, plus_suivis

    def objectif_defaut():
        try:
            return max(90.0, min(100.0, float(str(ctx.reglage("objectif_pct", "") or OBJECTIF_DEFAUT).replace(",", "."))))
        except (TypeError, ValueError):
            return OBJECTIF_DEFAUT

    def preuve_exigee():
        try:
            v = ctx.reglage("preuve_exigee", "")
        except Exception:
            return True
        return not (v is False or str(v).strip().lower() in ("0", "false", "faux", "non"))

    def ligne_incident(i, maintenant=None):
        maintenant = maintenant or time.time()
        minutes = max(0, int(((i["fin"] or maintenant) - i["debut"]) // 60))
        return {"id": i["id"], "domaine": i["domaine"], "etat": i["etat"], "debut": i["debut"], "fin": i["fin"], "duree_min": minutes, "duree": duree_texte(minutes),
                "diagnostic": i["diagnostic"], "code": i["code"], "erreur": i["erreur"], "pris_par": i["pris_par"],
                "connu_jusqu": i["connu_jusqu"] if (i["connu_jusqu"] or 0) > maintenant else None, "cause": i["cause"], "clos_par": i["clos_par"]}

    def vigilances(lignes, r, demandes):
        tout = r.tout
        vig, noms_dits = [], set()
        court = certificats_tenus()[1]
        for d in demandes:
            if tout:
                vig.append({"niveau": "regarder", "site": d["domaine"], "titre": "%s : adossement demandé par %s" % (d["domaine"], d["compte"]), "detail": d["message"] or "sans message", "geste": "repondre_demande", "demande": d["id"]})
            else:
                vig.append({"niveau": "info", "site": d["domaine"], "titre": "%s : demande d'adossement en attente" % d["domaine"], "detail": "", "geste": None})
        for x in lignes:
            d = x["domaine"]
            if x.get("preuve"):
                vig.append({"niveau": "info", "site": d, "titre": "%s : preuve de propriété en attente" % d,
                            "detail": "déclaré par %s : tant que la preuve manque, le site n'est à personne et n'est pas mesuré" % x["preuve"]["compte"], "geste": "prouver"})
                continue
            inc = x.get("incident")
            if inc and inc["etat"] == "retabli":
                vig.append({"niveau": "regarder", "site": d, "titre": "%s répond de nouveau : incident à clore" % d, "detail": "note la cause, pour ne pas la rechercher deux fois", "geste": "depanner", "incident": inc["id"]})
            mnt, acc = x.get("maintenance"), x.get("acceptee")
            if mnt:
                vig.append({"niveau": "info", "site": d, "titre": "%s est en maintenance" % d, "detail": (mnt["motif"] or "fenêtre posée dans le Sensorium") + " : ses alertes se taisent, les mesures continuent",
                            "geste": "maintenance", "jusqu_a": mnt["fin"]})
            if x["up"] is False:
                # En maintenance, ou son alerte acceptée dans le Sensorium : la panne reste dite, mais elle ne compte plus comme une alerte.
                vig.append({"niveau": "info" if (mnt or acc) else "panne", "site": d, "titre": "%s ne répond pas" % d,
                            "detail": ("alerte acceptée dans le Sensorium : %s" % (acc["raison"] or "sans raison notée")) if acc and not mnt else ("code %s" % x["code"]) if x["code"] else (x.get("erreur") or "aucune réponse"),
                            "geste": "depanner" if inc else None, "incident": inc["id"] if inc else None})
            sv, pf, nm = x.get("sauvegarde"), x.get("php_fin"), x.get("nom")
            if sv and sv["etat"] == "sans":
                vig.append({"niveau": "regarder", "site": d, "titre": "%s : aucune sauvegarde connue" % d, "detail": "aucun plan du panneau ne couvre ce site", "geste": "hebergement", "cle": "sauvegarde:" + d})
            elif sv and sv["etat"] == "perimee":
                vig.append({"niveau": "regarder", "site": d, "titre": "%s : sauvegarde trop ancienne" % d, "detail": "la dernière date du %s" % str(sv["derniere"] or "?")[:10], "geste": "hebergement", "cle": "sauvegarde:" + d})
            if pf:
                vig.append({"niveau": "regarder" if pf["etat"] == "depassee" else "info", "site": d,
                            "titre": "%s : PHP %s %s" % (d, pf["version"], "n'est plus maintenu" if pf["etat"] == "depassee" else "arrive en fin de support"),
                            "detail": ("plus de correctifs de sécurité depuis le %s" if pf["etat"] == "depassee" else "fin des correctifs de sécurité le %s") % pf["fin"], "geste": "hebergement", "cle": "php:" + d})
            if nm and isinstance(nm.get("jours"), int) and nm["jours"] < NOM_COURT_J and nm["zone"] not in noms_dits:
                noms_dits.add(nm["zone"])                                   # une alerte par nom, pas une par site qu'il porte
                vig.append({"niveau": "panne" if nm["jours"] < 10 else "regarder", "site": d,
                            "titre": ("le nom %s est échu" % nm["zone"]) if nm["jours"] < 0 else "le nom %s expire dans %d jour(s)" % (nm["zone"], nm["jours"]),
                            "detail": "s'il n'est pas renouvelé, le site et son courrier disparaissent", "geste": None, "cle": "nom:" + nm["zone"], "valeur": nm["jours"]})
            if r.super and r.multi and x.get("societe_source") != "attribuee":
                vig.append({"niveau": "info", "site": d, "titre": "%s n'est attribué à aucune société" % d,
                            "detail": ("il suit celle de son compte (%s), mais le site lui-même n'est pas attribué" % ", ".join(x["comptes"] or [])) if x.get("societe")
                            else "ni compte ni société : seuls les superadministrateurs le voient", "geste": "attribuer_societe"})
            j = x["ssl_jours"]
            if isinstance(j, int):
                if j < 0:
                    vig.append({"niveau": "panne", "site": d, "titre": "certificat de %s : échu depuis %d jour(s)" % (d, -j), "detail": "les navigateurs refusent le site", "geste": "certificats", "cle": "certificat:" + d, "valeur": j})
                elif j < 7:
                    vig.append({"niveau": "panne", "site": d, "titre": "certificat de %s : %d jour(s)" % (d, j), "detail": "renouvellement urgent", "geste": "certificats", "cle": "certificat:" + d, "valeur": j})
                elif j < court:
                    vig.append({"niveau": "regarder", "site": d, "titre": "certificat de %s : %d jours" % (d, j), "detail": "à renouveler avant l'échéance", "geste": "certificats", "cle": "certificat:" + d, "valeur": j})
            if x["source"] != "panneau" and not x["demande"]:
                # L'administrateur n'attribue que ce qui n'est à personne ; un compte ne demande l'adossement que de ce qui est à lui.
                geste = ("attribuer" if not x["comptes"] else None) if tout else "demander"
                vig.append({"niveau": "info", "site": d, "titre": "%s : hors panneau" % d, "detail": "suivi à la main : sonde, historique et journal seulement", "geste": geste})
        ordre = {"panne": 0, "regarder": 1, "info": 2}
        vig.sort(key=lambda v: (ordre.get(v["niveau"], 9), v["site"]))
        # « Je sais, c'est normal » : une alerte acceptée sort de la liste jusqu'à son échéance — sauf si son chiffre a empiré depuis (un certificat accepté à
        # douze jours revient à onze). Elle reste lisible à part, pour qu'on puisse la reprendre.
        maintenant = time.time()
        acc = {a["cle"]: a for a in db.lire("SELECT cle, jusqu_a, valeur, par, ts FROM alertes_acceptees WHERE jusqu_a > ?", (maintenant,))}
        gardees, tues = [], []
        for v in vig:
            a = acc.get(v.get("cle") or "")
            if a and not (isinstance(v.get("valeur"), (int, float)) and a["valeur"] is not None and v["valeur"] < a["valeur"]):
                tues.append(dict(v, acceptee={"jusqu_a": a["jusqu_a"], "par": a["par"]}))
            else:
                gardees.append(v)
        return gardees, tues

    def _vue(r):
        compte, tout, carte = r.compte, r.tout, r.carte
        dispo, _ = disponibilites(30, set(carte))
        dispo = {x["domaine"]: x for x in dispo}
        demandes = db.lire("SELECT id, domaine, compte, message, ts FROM demandes WHERE statut='ouverte'" + ("" if tout else " AND compte=?"), () if tout else (compte,))
        if tout and not r.large:
            demandes = [x for x in demandes if x["domaine"] in carte]              # l'administrateur d'une société : les demandes de sa société
        parsite = {x["domaine"]: x for x in demandes}
        mesures = dernieres_mesures()
        maintenant = time.time()
        objectifs, defaut = {x["domaine"]: x["pct"] for x in db.lire("SELECT domaine, pct FROM objectifs")}, objectif_defaut()
        incidents_ = {}
        for i in db.lire("SELECT * FROM incidents WHERE etat != 'resolu' ORDER BY id"):
            incidents_[i["domaine"]] = ligne_incident(i, maintenant)                 # le plus récent l'emporte (un « rétabli » cède devant un nouvel « ouvert »)
        lignes, vo, ap = [], Voisins(), apercus_legers()
        # Les déclarations qui attendent leur preuve : le site n'est encore à personne, il n'est ni dans la carte ni mesuré. Son déclarant le voit, et l'administrateur de sa société.
        for p in db.lire("SELECT domaine, compte, jeton, cree FROM preuves WHERE cree >= ? ORDER BY domaine", (maintenant - PREUVE_GARDE_J * 86400,)):
            if p["domaine"] in carte or not (p["compte"] == compte or r.large or (tout and r.societe_du_compte(p["compte"]) == r.soc)):
                continue
            lignes.append({"domaine": p["domaine"], "source": "declare", "origine": "declare", "up": None, "code": None, "ms": None, "erreur": "", "ssl_jours": None, "ssl_etat": None, "ssl_source": "",
                           "php": "", "proprietaire_panneau": "", "mesure": None, "dispo30": None, "comptes": [p["compte"]] if tout else None, "demande": None,
                           "societe": r.societe_du_compte(p["compte"]), "societe_source": "compte", "objectif": defaut, "objectif_propre": False, "incident": None,
                           "maintenance": None, "acceptee": None, "cms": None, "nom": None, "sauvegarde": None, "php_fin": None, "disque_mo": None, "analyse": None, "titre": "", "icone": "",
                           "preuve": {"compte": p["compte"], "expire": p["cree"] + PREUVE_GARDE_J * 86400, "jeton": p["jeton"] if p["compte"] == compte else None}})
        for d in sorted(carte):
            e = carte[d]
            m = mesures.get(d)
            p = e["panneau"] or {}
            res, a = vo.resume(d, bool(e["panneau"]), e["panneau"]), ap.get(d) or {}
            if not res["cms"] and a.get("generateur"):
                res["cms"] = cms_du_generateur(a["generateur"])                # hors de la machine, le Sensorium n'y entre pas : reste ce que la page déclare d'elle-même
            lignes.append({**res, "titre": a.get("titre", ""), "icone": a.get("icone", ""),
                           "domaine": d, "source": e["origine"] if e["origine"] == "panneau" else "declare", "origine": e["origine"],
                           "societe": e.get("societe", ""), "societe_source": e.get("societe_source", ""), "objectif": objectifs.get(d, defaut), "objectif_propre": d in objectifs,
                           "incident": incidents_.get(d), "preuve": None,
                           "up": bool(m["up"]) if m else None, "code": m["code"] if m else None, "ms": m["ms"] if m else None, "erreur": m["erreur"] if m else "",
                           "ssl_jours": m["ssl_jours"] if m and m["ssl_jours"] is not None else (p.get("ssl") or {}).get("jours"), "ssl_etat": (p.get("ssl") or {}).get("etat"),
                           "ssl_source": ("certificats" if certificats_tenus()[0] else "sonde") if m and m["ssl_jours"] is not None else ("panneau" if (p.get("ssl") or {}).get("jours") is not None else ""),
                           "php": p.get("php", ""), "proprietaire_panneau": p.get("proprietaire", ""), "mesure": m["ts"] if m else None,
                           "dispo30": dispo.get(d), "comptes": e["comptes"] if tout else None, "demande": parsite.get(d)})
        lignes.sort(key=lambda x: x["domaine"])
        noms = noms_societes() if r.multi else {}
        vig, tues = vigilances(lignes, r, demandes)
        # L'âge de ce qu'on montre, pour qui compose une vue d'ensemble : la dernière mesure parmi ces sites, et la dernière lecture réussie du panneau
        # (l'administrateur vient de le lire ; les autres lisent le miroir du dernier tour). Rien, plutôt qu'une heure inventée.
        mesurees = [x["mesure"] for x in lignes if x["mesure"]]
        lu_a = (maintenant if tout else quand_miroir("panneau")) if r.panneau_lu else None
        return {"sites": lignes, "vigilances": vig, "acceptees": tues,
                "portee": {"admin": tout, "compte": compte, "sites": len(lignes), "panneau": sum(1 for x in lignes if x["source"] == "panneau"),
                           "declares": sum(1 for x in lignes if x["source"] != "panneau"), "panneau_lu": r.panneau_lu,
                           "sonde": heure_locale(max(mesurees)) if mesurees else None, "panneau_releve": heure_locale(lu_a) if lu_a else None,
                           "super": bool(r.super and tout), "multi": r.multi, "societe": r.soc,
                           "societes": [{"id": s, "nom": noms.get(s, s)} for s in (societes_connues() if r.large else [r.soc])] if r.multi else [],
                           "preuve_exigee": preuve_exigee(), "objectif": defaut,
                           "incidents_ouverts": sum(1 for x in lignes if x["incident"] and x["incident"]["etat"] in ("ouvert", "depannage"))}}

    def vue(c):
        return _vue(Regard(c.compte))

    def _historique(d, depuis, jusqu, max_ev=100):
        s = db.lire("SELECT COUNT(*) n, COALESCE(SUM(up),0) u, AVG(CASE WHEN up=1 THEN ms END) moy, MAX(CASE WHEN up=1 THEN ms END) mx "
                    "FROM mesures WHERE domaine=? AND ts >= ? AND ts <= ?", (d, depuis, jusqu))[0]
        pts = db.lire("SELECT ts, code, ms, up, ssl_jours, erreur FROM mesures WHERE domaine=? AND ts >= ? AND ts <= ? ORDER BY ts", (d, depuis, jusqu))
        pas = max(1, -(-len(pts) // POINTS_MAX))
        if pas > 1:
            # Trop de points pour une courbe : on les regroupe par paquets, en gardant le PIRE de chacun (une coupure ne doit pas disparaître dans une moyenne).
            groupes = []
            for i in range(0, len(pts), pas):
                g = pts[i:i + pas]
                bas = [p for p in g if not p["up"]]
                ms = [p["ms"] for p in g if p["ms"] is not None]
                ssl_j = [p["ssl_jours"] for p in g if p["ssl_jours"] is not None]
                groupes.append({"ts": g[0]["ts"], "code": (bas[0] if bas else g[-1])["code"], "ms": max(ms) if ms else None, "up": 0 if bas else 1,
                                "ssl_jours": min(ssl_j) if ssl_j else None, "erreur": next((p["erreur"] for p in bas if p["erreur"]), "")})
            pts = groupes
        ev = db.lire("SELECT ts, genre, detail, duree_min FROM evenements_site WHERE domaine=? AND ts >= ? AND ts <= ? ORDER BY ts DESC LIMIT ?", (d, depuis, jusqu, max_ev))
        return {"domaine": d, "mesures": s["n"], "disponibilite": round(100.0 * s["u"] / s["n"], 2) if s["n"] else None,
                "reponse_moy_ms": int(s["moy"]) if s["moy"] is not None else None, "reponse_max_ms": int(s["mx"]) if s["mx"] is not None else None,
                "regroupes_par": pas, "points": [dict(p, up=bool(p["up"])) for p in pts], "evenements": ev}

    def historique(c, domaine, heures=24, debut=None, fin=None):
        """Sur les `heures` dernières heures, ou entre `debut` et `fin` (secondes depuis 1970) pour une période passée — un mois de rapport, par exemple."""
        d = Regard(c.compte).exiger(domaine)
        maintenant = time.time()
        if debut not in (None, ""):
            try:
                a, b = float(debut), float(fin) if fin not in (None, "") else maintenant
            except (TypeError, ValueError):
                raise ValueError("« debut » et « fin » sont des secondes depuis 1970")
            if b < a:
                a, b = b, a
            a = max(a, b - 366 * 86400)
            h = max(1, int((b - a) // 3600))
            return dict(_historique(d, a, b, 500), heures=h)
        h = nombre(heures, 24, 1, 24 * 90, "heures")
        return dict(_historique(d, maintenant - h * 3600, maintenant), heures=h)

    def disponibilite(c, jours=30):
        r = Regard(c.compte)
        j = nombre(jours, 30, 1, 365, "jours")
        sites, plus = disponibilites(j, set(r.carte))
        return {"jours": j, "sites": sites, "plus_suivis": plus,
                "raison": "" if sites else "Aucune mesure enregistrée — la sonde n'a pas encore tourné."}

    def tendances(c, jours=30):
        """Pour chaque site de la portée, de quoi dessiner sa ligne : une bande (un état par jour sur `jours` jours — ok, courte, longue, maintenance, sans),
        la durée de réponse moyenne de chaque jour (la courbe), et sa disponibilité sur la période et sur celle d'avant (l'écart). Les jours sont des tranches
        de 24 heures qui finissent maintenant : la dernière case est « les dernières 24 heures »."""
        carte = Regard(c.compte).carte
        n = nombre(jours, 30, 7, 90, "jours")
        maintenant = time.time()
        a0 = maintenant - 2 * n * 86400
        par = {}
        for x in db.lire("SELECT domaine, CAST((ts - ?) / 86400 AS INTEGER) k, COUNT(*) n, COALESCE(SUM(up),0) u, AVG(CASE WHEN up=1 THEN ms END) m FROM mesures WHERE ts >= ? GROUP BY domaine, k", (a0, a0)):
            if x["domaine"] in carte:
                par.setdefault(x["domaine"], {})[min(int(x["k"]), 2 * n - 1)] = x
        vo, sortie = Voisins(), {}
        for d in carte:
            lignes = par.get(d) or {}
            etats, durees, tot, bons = [], [], 0, 0
            for k in range(n, 2 * n):
                x = lignes.get(k)
                if not x:
                    etats.append("sans")
                    durees.append(None)
                    continue
                tot, bons = tot + x["n"], bons + x["u"]
                pct = 100.0 * x["u"] / x["n"]
                e = "ok" if x["u"] == x["n"] else ("courte" if pct >= COUPURE_COURTE_PCT else "longue")
                if vo.fenetres_de(d, a0 + k * 86400, a0 + (k + 1) * 86400):
                    e = "maintenance"                                    # une fenêtre a couvert ce jour : ses coupures étaient voulues
                etats.append(e)
                durees.append(int(x["m"]) if x["m"] is not None else None)
            avant = [lignes[k] for k in range(0, n) if k in lignes]
            ta, ba = sum(x["n"] for x in avant), sum(x["u"] for x in avant)
            sortie[d] = {"jours": etats, "ms": durees, "disponibilite": round(100.0 * bons / tot, 2) if tot else None, "avant": round(100.0 * ba / ta, 2) if ta else None}
        return {"jours": n, "sites": sortie, "lent_ms": entier("lent_ms", 3000)}

    def serie(c, mesure="", depuis="", jusqu_a=""):
        """Les points de la sonde pour l'historique : une courbe PAR SITE de la portée du compte (l'administrateur voit l'état de tous, jamais leur contenu).
        Sur une longue période les points sont regroupés par tranches de temps (400 au plus par site) : une moyenne, ou le minimum pour le certificat."""
        import datetime as _dt

        def epoque(t, defaut):
            try:
                return _dt.datetime.strptime(str(t)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp()
            except ValueError:
                return defaut
        a, b = epoque(depuis, time.time() - 86400), epoque(jusqu_a, time.time())
        if b < a:
            a, b = b, a
        a = max(a, b - 366 * 86400)
        doms = set(Regard(c.compte).carte)

        def heure(ts):
            return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if mesure == "site_down":
            ev = [r for r in db.lire("SELECT ts, domaine FROM evenements_site WHERE genre='panne' AND ts BETWEEN ? AND ? ORDER BY ts", (a, b)) if r["domaine"] in doms]
            return {"series": [{"nom": "pannes", "points": [[heure(r["ts"]), 1] for r in ev]}]}
        colonne = {"site_up": "ROUND(AVG(up) * 100.0, 2)", "site_ms": "CAST(AVG(ms) AS INTEGER)", "site_ssl": "MIN(ssl_jours)"}.get(mesure)
        if not colonne:
            raise ValueError("mesure inconnue : « %s »" % mesure)
        cond = " AND up = 1" if mesure == "site_ms" else (" AND ssl_jours IS NOT NULL" if mesure == "site_ssl" else "")
        pas = max(300.0, (b - a) / 400.0)
        par = {}
        for r in db.lire("SELECT domaine, CAST((ts - ?) / ? AS INTEGER) k, MIN(ts) t, %s AS v FROM mesures WHERE ts BETWEEN ? AND ?%s GROUP BY domaine, k ORDER BY domaine, k" % (colonne, cond), (a, pas, a, b)):
            if r["domaine"] in doms and r["v"] is not None:
                par.setdefault(r["domaine"], []).append([heure(r["t"]), r["v"]])
        return {"series": [{"nom": d, "points": p} for d, p in sorted(par.items())]}

    def _journal(r, d, lim):
        if d:
            lignes = db.lire("SELECT ts, acteur, verbe, domaine, detail FROM journal WHERE domaine=? OR domaine LIKE ? ORDER BY id DESC LIMIT ?", (d, "%." + d, lim))
            ev = db.lire("SELECT ts, genre verbe, domaine, detail FROM evenements_site WHERE domaine=? ORDER BY id DESC LIMIT ?", (d, lim))
        elif r.large:
            lignes = db.lire("SELECT ts, acteur, verbe, domaine, detail FROM journal ORDER BY id DESC LIMIT ?", (lim,))
            ev = db.lire("SELECT ts, genre verbe, domaine, detail FROM evenements_site ORDER BY id DESC LIMIT ?", (lim,))
        else:
            # Le filtre se fait dans la base : filtrer après coup les dernières lignes de TOUS rendait une liste vide à qui a peu de sites.
            doms = sorted(r.carte)[:900]
            if not doms:
                return []
            marques = ",".join("?" * len(doms))
            lignes = db.lire("SELECT ts, acteur, verbe, domaine, detail FROM journal WHERE domaine IN (%s) ORDER BY id DESC LIMIT ?" % marques, (*doms, lim))
            ev = db.lire("SELECT ts, genre verbe, domaine, detail FROM evenements_site WHERE domaine IN (%s) ORDER BY id DESC LIMIT ?" % marques, (*doms, lim))
        toutes = [dict(x, source="geste") for x in lignes] + [dict(x, acteur="sonde", source="veille") for x in ev]
        toutes.sort(key=lambda x: x["ts"], reverse=True)
        return toutes[:lim]

    def journal(c, domaine="", limite=60):
        r = Regard(c.compte)
        lim = nombre(limite, 60, 10, 600, "limite")
        d = r.exiger(domaine) if domaine else ""
        return {"domaine": d, "lignes": _journal(r, d, lim)}

    def _liens(d):
        return db.lire("SELECT genre, ref, note, ts FROM liens WHERE domaine=? ORDER BY genre, ts", (d,))

    def liens(c, domaine):
        d = Regard(c.compte).exiger(domaine)
        return {"domaine": d, "liens": _liens(d)}

    def demandes(c, statut="ouverte"):
        tout = admin(c.compte)
        cond, args = [], []
        if statut:
            cond.append("statut=?")
            args.append(str(statut))
        if not tout:
            cond.append("compte=?")
            args.append(c.compte)
        lignes = db.lire("SELECT id, ts, domaine, compte, message, statut, reponse, traite_par, traite_ts FROM demandes"
                         + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY id DESC LIMIT 200", tuple(args))
        r = Regard(c.compte)
        if tout and not r.large:
            lignes = [x for x in lignes if x["domaine"] in r.carte or r.societe_du_compte(x["compte"]) == r.soc]      # l'administrateur d'une société : celles de sa société
        # Les preuves de propriété en attente, et les accords en cours : ce que la page « Demandes et preuves » montre à côté des demandes d'adossement.
        maintenant = time.time()
        preuves = [{"domaine": p["domaine"], "compte": p["compte"], "cree": p["cree"], "expire": p["cree"] + PREUVE_GARDE_J * 86400, "essais": p["essais"], "dernier": p["dernier"]}
                   for p in db.lire("SELECT domaine, compte, cree, essais, dernier FROM preuves WHERE cree >= ? ORDER BY cree DESC", (maintenant - PREUVE_GARDE_J * 86400,))
                   if p["compte"] == c.compte or r.large or (tout and r.societe_du_compte(p["compte"]) == r.soc)]
        accords = [dict(a) for a in db.lire("SELECT id, domaine, compte, geste, ts, jusqu_a FROM accords WHERE jusqu_a > ? ORDER BY jusqu_a", (maintenant,))
                   if a["domaine"] in r.carte and a["compte"] in r.proprietaires(a["domaine"])]
        return {"demandes": lignes, "preuves": preuves, "accords": accords}

    def rattaches(d):
        """Ce que les autres modules ont rattaché à ce site, lu CHEZ EUX au nom du compte qui regarde : les contacts (Contacts), les notes (Notes), les documents (GED).
        Chaque module porte ses liens ; Sites les montre, il ne les recopie pas. Une source absente ou muette rend une liste vide, et le dit."""
        out = {"contacts": [], "notes": [], "documents": [], "sources": {}}
        r, out["sources"]["contacts"] = lecture("contacts.pour_cible", kind="domain", ref=d)
        for x in ((r.get("contacts") or []) if isinstance(r, dict) else [])[:30]:
            if isinstance(x, dict):
                out["contacts"].append({"id": x.get("id"), "nom": str(x.get("display_name") or ""), "societe": str(x.get("company") or ""), "role": str(x.get("role") or "")})
        r, out["sources"]["notes"] = lecture("notes.de", kind="site", ref=d)
        for x in ((r.get("notes") or []) if isinstance(r, dict) else [])[:30]:
            if isinstance(x, dict):
                out["notes"].append({"id": x.get("id"), "titre": str(x.get("titre") or "")})
        r, out["sources"]["documents"] = lecture("ged.documents_de", kind="domain", ref=d)
        for x in ((r.get("documents") or []) if isinstance(r, dict) else [])[:30]:
            if isinstance(x, dict):
                out["documents"].append({"id": x.get("id"), "nom": str(x.get("nom") or ""), "libelle": str(x.get("label") or "")})
        return out

    def accord_valide(r, d, geste):
        """Le dernier accord encore valable, donné par un compte qui a TOUJOURS ce site : l'accord d'un ancien propriétaire n'engage pas le nouveau."""
        pr = r.proprietaires(d)
        for a in db.lire("SELECT compte, jusqu_a FROM accords WHERE domaine=? AND geste=? AND jusqu_a > ? ORDER BY id DESC", (d, geste, time.time())):
            if a["compte"] in pr:
                return {"par": a["compte"], "jusqu_a": a["jusqu_a"]}
        return None

    def geste_accord(geste):
        g = str(geste or "restaurer").strip().lower()
        if g not in GESTES_ACCORD:
            raise ValueError("geste inconnu (%s)" % ", ".join(GESTES_ACCORD))
        return g

    def accord(c, domaine, geste="restaurer"):
        r = Regard(c.compte)
        d = r.exiger(domaine)
        g = geste_accord(geste)
        return {"domaine": d, "geste": g, "accord": accord_valide(r, d, g)}

    def fiche(c, domaine):
        r = Regard(c.compte)
        compte, tout = r.compte, r.tout
        vue_ = _vue(r)
        attente = next((x for x in vue_["sites"] if x["preuve"] and x["domaine"] == nom_hote(domaine)), None)
        if attente:
            # Une déclaration qui attend sa preuve : pas de mesure, pas d'histoire ; ce qu'il faut poser pour prouver, et qui peut le faire.
            d, mien = attente["domaine"], attente["preuve"]["compte"] == compte
            jeton = attente["preuve"]["jeton"]
            return {"domaine": d, "site": attente, "mien": mien, "admin_autrui": bool(tout and not mien), "hors_panneau": True,
                    "histoire": {"disponibilite": None, "reponse_moy_ms": None, "reponse_max_ms": None, "mesures": 0, "evenements": []},
                    "liens": [], "journal": db.lire("SELECT ts, acteur, verbe, domaine, detail, 'geste' source FROM journal WHERE domaine=? ORDER BY id DESC LIMIT 12", (d,)),
                    "demande": None, "accord": None, "accords": {}, "incidents": [], "voisins": None, "apercu": None, "rattaches": {"contacts": [], "notes": [], "documents": [], "sources": {}},
                    "preuve": {"compte": attente["preuve"]["compte"], "expire": attente["preuve"]["expire"], "jeton": jeton,
                               "dns": {"nom": "_cassandra." + d, "valeur": "cassandra-site=" + jeton} if jeton else None,
                               "fichier": {"adresse": "https://%s%s" % (d, CHEMIN_PREUVE), "contenu": jeton} if jeton else None},
                    "gestes": {"prouver": mien, "retirer": bool(mien or tout), "attribuer": tout, "transferer": False, "demander": False, "accorder": False,
                               "objectif": False, "attribuer_societe": False, "relever": False}}
        d = r.exiger(domaine)
        ligne = next((x for x in vue_["sites"] if x["domaine"] == d), None)
        if ligne is None:
            raise ValueError("site hors de ta portée")
        mien = compte in (r.carte.get(d, {}).get("comptes") or [])
        hors = ligne["source"] != "panneau"
        rows = db.lire("SELECT compte, origine FROM sites WHERE domaine=?", (d,))
        maintenant = time.time()
        h = _historique(d, maintenant - 86400, maintenant)
        accords = {g: accord_valide(r, d, g) for g in GESTES_ACCORD}
        voisins_d = Voisins().detail(d, not hors, r.du_panneau(d))
        ap = db.lire("SELECT ts, titre, description, generateur, langue, icone, image, erreur FROM apercus WHERE domaine=?", (d,))
        apercu = dict(ap[0]) if ap else None
        if not voisins_d["cms"] and apercu and apercu["generateur"]:
            voisins_d["cms"] = cms_du_generateur(apercu["generateur"])
        return {"domaine": d, "site": ligne, "mien": mien, "admin_autrui": bool(tout and not mien), "hors_panneau": hors,
                "histoire": {k: h[k] for k in ("disponibilite", "reponse_moy_ms", "reponse_max_ms", "mesures")} | {"evenements": h["evenements"][:8]},
                "liens": _liens(d), "journal": _journal(r, d, 12), "demande": ligne["demande"],
                "accord": accords["restaurer"], "accords": accords, "preuve": None,
                "voisins": voisins_d, "apercu": apercu, "rattaches": rattaches(d),
                "incidents": [ligne_incident(i, maintenant) for i in db.lire("SELECT * FROM incidents WHERE domaine=? ORDER BY id DESC LIMIT 6", (d,))],
                "gestes": {"retirer": bool(rows and (tout or (mien and rows[0]["origine"] != "attribue"))), "attribuer": tout,
                           "transferer": bool(tout and rows),
                           "demander": bool(mien and not tout and hors and not ligne["demande"]), "accorder": bool(mien and not tout and not hors),
                           "objectif": bool(mien or tout), "attribuer_societe": bool(r.super and tout and r.multi), "relever": True, "prouver": False}}

    # ------------------------------------------------------------------ gestes
    def valider_compte_cible(r, cible):
        cible = str(cible or "").strip().lower()
        if not cible or len(cible) > 120:
            raise ValueError("compte invalide")
        # Sans module de comptes, ou s'il se tait, rien n'est vérifiable : on ne refuse alors personne.
        if r.cs is not None and not r.comptes_absents and cible not in {x["compte"] for x in r.cs}:
            raise ValueError("compte inconnu")
        return cible

    def mettre_de_cote(d, lot):
        """Ce qui était à l'ancien propriétaire ne passe pas au suivant : ses liens sont mis de côté, ses accords tombent, sa demande ouverte se ferme."""
        db.ecrire("INSERT INTO liens_retires(lot, domaine, genre, ref, note, ts) SELECT ?, domaine, genre, ref, note, ts FROM liens WHERE domaine=?", (lot, d))
        db.ecrire("DELETE FROM liens WHERE domaine=?", (d,))
        db.ecrire("DELETE FROM accords WHERE domaine=?", (d,))
        dem = db.lire("SELECT id FROM demandes WHERE domaine=? AND statut='ouverte'", (d,))
        if dem:
            db.ecrire("UPDATE demandes SET statut='caduque', traite_ts=? WHERE id=?", (time.time(), dem[0]["id"]))
        return dem[0]["id"] if dem else None

    def remettre(d, lot, demande):
        if lot:
            db.ecrire("INSERT OR IGNORE INTO liens(domaine, genre, ref, note, ts) SELECT domaine, genre, ref, note, ts FROM liens_retires WHERE domaine=? AND lot=?", (d, lot))
            db.ecrire("DELETE FROM liens_retires WHERE domaine=? AND lot=?", (d, lot))
        if demande and not db.lire("SELECT 1 FROM demandes WHERE domaine=? AND statut='ouverte'", (d,)):
            db.ecrire("UPDATE demandes SET statut='ouverte', traite_ts=NULL WHERE id=? AND statut='caduque'", (demande,))

    def declarer(c, domaine):
        compte = c.compte
        if systeme(compte):
            raise ValueError("un site se déclare au nom d'un compte")
        d = nom_hote(domaine)
        if not RE_DOMAINE.match(d):
            raise ValueError("nom de domaine invalide")
        if d in SUFFIXES_PARTAGES:
            raise ValueError("ce nom est partagé par les sites de beaucoup de gens : déclare ton site, pas le nom qui les porte tous")
        r = Regard(compte)
        if not r.comptes_surs:
            raise ValueError("les comptes ne sont pas lisibles pour l'instant : impossible de vérifier que ce site n'est à personne, réessaie dans quelques minutes")
        if r.du_panneau(d):
            raise ValueError("ce site est géré par le panneau : c'est à l'administrateur de te l'attribuer")
        pris = r.en_ont_declare(d)
        if compte in pris:
            raise ValueError("déjà dans la liste de ce compte")
        if pris:
            raise ValueError("ce site appartient déjà à un autre compte")
        # Déclarer un nom donne la vue de ses sous-domaines : pas si l'un d'eux est déjà le site de quelqu'un d'autre.
        for x in r.domaines_connus():
            if x.endswith("." + d) and compte not in r.proprietaires(x):
                raise ValueError("des sites d'autres comptes dépendent de ce nom (%s) : c'est à l'administrateur de te l'attribuer" % x)
        if preuve_exigee() and not r.tout:
            # Le panneau dit à qui est un site ; hors de lui, rien ne le dit : le compte doit le prouver (un enregistrement DNS ou un fichier portant son jeton).
            # D'ici là le site n'est à personne : il n'entre pas dans la table sites, n'est pas mesuré, et un autre peut encore le réclamer en apportant la preuve.
            deja = db.lire("SELECT jeton FROM preuves WHERE domaine=? AND compte=?", (d, compte))
            jeton = deja[0]["jeton"] if deja else secrets.token_hex(8)
            db.ecrire("INSERT OR REPLACE INTO preuves(domaine, compte, jeton, cree, essais, dernier) VALUES (?,?,?,?,0,NULL)", (d, compte, jeton, time.time()))
            noter(compte, "declare_a_prouver", d)
            return {"domaine": d, "compte": compte, "preuve": "attente", "jeton": jeton, "reprise": bool(deja),
                    "dns": {"nom": "_cassandra." + d, "valeur": "cassandra-site=" + jeton}, "fichier": {"adresse": "https://%s%s" % (d, CHEMIN_PREUVE), "contenu": jeton}}
        try:
            db.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (d, compte, "declare", time.time(), compte))
        except sqlite3.IntegrityError:
            raise ValueError("ce site vient d'être pris par un autre compte")
        noter(compte, "declare", d)
        c.emettre("site.declare", objet=("site", d), donnees={"domaine": d, "compte": compte})
        return {"domaine": d, "compte": compte}

    def prouver_ligne(compte_voulu):
        def f(c, res):
            if res.get("preuve") == "attente":
                return bool(db.lire("SELECT 1 FROM preuves WHERE domaine=? AND compte=?", (res["domaine"], res["compte"])))
            r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
            return bool(r) and r[0]["compte"] == res.get(compte_voulu or "compte")
        return f

    def defaire_declarer(c, res):
        if res.get("preuve") == "attente":
            if not res.get("reprise"):
                db.ecrire("DELETE FROM preuves WHERE domaine=? AND compte=?", (res["domaine"], res["compte"]))
        else:
            db.ecrire("DELETE FROM sites WHERE domaine=? AND compte=?", (res["domaine"], res["compte"]))
        noter(res["compte"], "declare_annule", res["domaine"])

    def prouver(c, domaine):
        """Vérifie la preuve de propriété d'un site déclaré : le jeton du compte, dans le DNS ou dans un fichier servi par le site. Trouvée, le site est à lui."""
        compte = c.compte
        d = nom_hote(domaine)
        maintenant = time.time()
        p = db.lire("SELECT jeton, cree FROM preuves WHERE domaine=? AND compte=? AND cree >= ?", (d, compte, maintenant - PREUVE_GARDE_J * 86400))
        if not p:
            raise ValueError("aucune déclaration en attente de preuve pour ce site à ton nom")
        r = Regard(compte)
        if r.du_panneau(d):
            raise ValueError("ce site est géré par le panneau : c'est à l'administrateur de te l'attribuer")
        if r.en_ont_declare(d) - {compte}:
            raise ValueError("ce site appartient déjà à un autre compte, qui l'a prouvé")
        par = _preuve_trouvee(d, p[0]["jeton"], entier("delai_sonde_s", 8), vrai("sonde_interne"))
        db.ecrire("UPDATE preuves SET essais=essais+1, dernier=? WHERE domaine=? AND compte=?", (maintenant, d, compte))
        if not par:
            raise ValueError("preuve introuvable : ni l'enregistrement TXT « _cassandra.%s » ni le fichier « https://%s%s » ne portent ton jeton "
                             "(un enregistrement DNS met parfois quelques minutes à paraître)" % (d, d, CHEMIN_PREUVE))
        autres = [dict(x) for x in db.lire("SELECT domaine, compte, jeton, cree, essais, dernier FROM preuves WHERE domaine=?", (d,))]
        try:
            db.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (d, compte, "declare", maintenant, compte))
        except sqlite3.IntegrityError:
            raise ValueError("ce site vient d'être pris par un autre compte")
        db.ecrire("DELETE FROM preuves WHERE domaine=?", (d,))           # la preuve tranche : les autres déclarations de ce nom tombent
        noter(compte, "prouve", d, "par le DNS" if par == "dns" else "par un fichier")
        c.emettre("site.declare", objet=("site", d), donnees={"domaine": d, "compte": compte, "preuve": par})
        return {"domaine": d, "compte": compte, "par": par, "preuves": autres}

    def remettre_preuves(lignes):
        for x in lignes or []:
            db.ecrire("INSERT OR IGNORE INTO preuves(domaine, compte, jeton, cree, essais, dernier) VALUES (?,?,?,?,?,?)",
                      (x["domaine"], x["compte"], x["jeton"], x["cree"], x.get("essais") or 0, x.get("dernier")))

    def defaire_prouve(c, res):
        db.ecrire("DELETE FROM sites WHERE domaine=? AND compte=? AND origine='declare'", (res["domaine"], res["compte"]))
        remettre_preuves(res.get("preuves"))

    def retirer(c, domaine):
        compte = c.compte
        d = nom_hote(domaine)
        r = db.lire("SELECT compte, origine, cree, par FROM sites WHERE domaine=?", (d,))
        if not r:
            # Une déclaration qui attend sa preuve se retire aussi : la sienne, ou — pour l'administrateur — celles de ce nom qu'il voit.
            rg = Regard(compte)
            att = [dict(x) for x in db.lire("SELECT domaine, compte, jeton, cree, essais, dernier FROM preuves WHERE domaine=?", (d,))
                   if x["compte"] == compte or rg.large or (rg.tout and rg.societe_du_compte(x["compte"]) == rg.soc)]
            if att:
                for x in att:
                    db.ecrire("DELETE FROM preuves WHERE domaine=? AND compte=?", (d, x["compte"]))
                noter(compte, "declare_annule", d, ", ".join(x["compte"] for x in att))
                return {"domaine": d, "compte": att[0]["compte"], "preuves": att}
            if any(d in x["sites"] for x in (rg.cs or [])):
                raise ValueError("ce site est inscrit dans la fiche d'un compte : il s'enlève là-bas")
            raise ValueError("site absent de la liste")
        if r[0]["compte"] != compte and not admin(compte):
            raise ValueError("ce site n'est pas à toi")
        if r[0]["compte"] != compte:
            rg = Regard(compte)
            if not rg.large and d not in rg.carte:
                raise ValueError("ce site n'est pas de ta société")
        if r[0]["origine"] == "attribue" and not admin(compte):
            raise ValueError("ce site t'a été attribué : seul l'administrateur le reprend")
        db.ecrire("DELETE FROM sites WHERE domaine=?", (d,))
        lot = time.time()
        demande = mettre_de_cote(d, lot)
        noter(compte, "retire", d, r[0]["compte"])
        c.emettre("site.retire", objet=("site", d), donnees={"domaine": d, "compte": r[0]["compte"]})
        return {"domaine": d, "compte": r[0]["compte"], "origine": r[0]["origine"], "cree": r[0]["cree"], "par": r[0]["par"], "lot": lot, "demande": demande}

    def prouver_retire(c, res):
        if res.get("preuves"):
            return not any(db.lire("SELECT 1 FROM preuves WHERE domaine=? AND compte=?", (res["domaine"], x["compte"])) for x in res["preuves"])
        return not db.lire("SELECT 1 FROM sites WHERE domaine=?", (res["domaine"],))

    def defaire_retire(c, res):
        if res.get("preuves"):
            return remettre_preuves(res["preuves"])
        db.ecrire("INSERT OR IGNORE INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (res["domaine"], res["compte"], res["origine"], res["cree"], res["par"]))
        if db.lire("SELECT 1 FROM sites WHERE domaine=? AND compte=?", (res["domaine"], res["compte"])):
            remettre(res["domaine"], res.get("lot"), res.get("demande"))        # seulement si le site est bien revenu à son compte

    def attribuer(c, domaine, compte):
        d = nom_hote(domaine)
        if not RE_DOMAINE.match(d):
            raise ValueError("nom de domaine invalide")
        r = Regard(c.compte)
        cible = valider_compte_cible(r, compte)
        pris = r.proprietaires(d)
        if pris and cible not in pris:
            raise ValueError("ce site est déjà à un autre compte : il se transfère, il ne s'attribue pas")
        if cible in pris:
            raise ValueError("ce site est déjà à ce compte")
        if not r.large and d in r.domaines_connus() and r.societe_selon(d, pris)[0] != r.soc:
            # L'administrateur d'une société n'attribue qu'un site de sa société, ou un nom que personne ne suit encore.
            raise ValueError("ce site n'est pas de ta société : c'est au superadministrateur de l'attribuer")
        try:
            db.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (d, cible, "attribue", time.time(), c.compte))
        except sqlite3.IntegrityError:
            raise ValueError("ce site vient d'être pris par un autre compte")
        # L'administrateur atteste : les déclarations de ce nom qui attendaient une preuve n'ont plus lieu d'être.
        att = [dict(x) for x in db.lire("SELECT domaine, compte, jeton, cree, essais, dernier FROM preuves WHERE domaine=?", (d,))]
        db.ecrire("DELETE FROM preuves WHERE domaine=?", (d,))
        noter(c.compte, "attribue", d, cible)
        c.emettre("site.attribue", objet=("site", d), donnees={"domaine": d, "compte": cible, "par": c.compte})
        return {"domaine": d, "compte": cible, "preuves": att}

    def transferer(c, domaine, vers):
        d = nom_hote(domaine)
        rg = Regard(c.compte)
        cible = valider_compte_cible(rg, vers)
        r = db.lire("SELECT compte, origine, cree, par FROM sites WHERE domaine=?", (d,))
        if not r:
            raise ValueError("ce site n'est ni déclaré ni attribué ici : il s'attribue, il ne se transfère pas")
        if not rg.large and d not in rg.carte:
            raise ValueError("ce site n'est pas de ta société")
        if r[0]["compte"] == cible:
            raise ValueError("ce site est déjà à ce compte")
        db.ecrire("UPDATE sites SET compte=?, origine='attribue', par=? WHERE domaine=?", (cible, c.compte, d))
        lot = time.time()
        demande = mettre_de_cote(d, lot)
        noter(c.compte, "transfere", d, "%s -> %s" % (r[0]["compte"], cible))
        c.emettre("site.transfere", objet=("site", d), donnees={"domaine": d, "de": r[0]["compte"], "vers": cible})
        return {"domaine": d, "vers": cible, "de": r[0]["compte"], "origine_avant": r[0]["origine"], "par_avant": r[0]["par"], "compte": cible, "lot": lot, "demande": demande}

    def defaire_transfert(c, res):
        db.ecrire("UPDATE sites SET compte=?, origine=?, par=? WHERE domaine=? AND compte=?", (res["de"], res["origine_avant"], res["par_avant"], res["domaine"], res["vers"]))
        if db.lire("SELECT 1 FROM sites WHERE domaine=? AND compte=?", (res["domaine"], res["de"])):
            remettre(res["domaine"], res.get("lot"), res.get("demande"))

    def demander(c, domaine, message=""):
        compte = c.compte
        d = nom_hote(domaine)
        if systeme(compte):
            raise ValueError("une demande se fait au nom d'un compte")
        r = Regard(compte)
        if compte not in r.en_ont_declare(d):
            raise ValueError("ce site n'est pas déclaré par ton compte")
        if r.du_panneau(d):
            raise ValueError("ce site est déjà géré par le panneau")
        msg = str(message or "").strip()[:500]
        ouverte = db.lire("SELECT id, message, ts, compte FROM demandes WHERE domaine=? AND statut='ouverte'", (d,))
        if ouverte:
            db.ecrire("UPDATE demandes SET message=?, ts=?, compte=? WHERE id=?", (msg, time.time(), compte, ouverte[0]["id"]))
            did = ouverte[0]["id"]
        else:
            did = db.ecrire("INSERT INTO demandes(ts, domaine, compte, message) VALUES (?,?,?,?)", (time.time(), d, compte, msg))
        noter(compte, "demande", d)
        c.emettre("site.demande", objet=("site", d), donnees={"domaine": d, "compte": compte, "demande": did})
        return {"id": did, "domaine": d, "reprise": bool(ouverte), "avant": {k: ouverte[0][k] for k in ("message", "ts", "compte")} if ouverte else None}

    def prouver_demande(c, res):
        return bool(db.lire("SELECT 1 FROM demandes WHERE id=? AND statut='ouverte'", (res["id"],)))

    def defaire_demande(c, res):
        if not res.get("reprise"):
            db.ecrire("DELETE FROM demandes WHERE id=? AND statut='ouverte'", (res["id"],))
        elif res.get("avant"):
            a = res["avant"]
            db.ecrire("UPDATE demandes SET message=?, ts=?, compte=? WHERE id=? AND statut='ouverte'", (a["message"], a["ts"], a["compte"], res["id"]))

    def repondre_demande(c, id, decision, reponse=""):
        # Une décision se dit en toutes lettres : deviner (« tout ce qui ne commence pas par f est un refus ») refusait sans le dire un « oui » ou un « ok ».
        mot = str(decision or "").strip().lower()
        if mot in ("fait", "faite", "f"):
            decision = "fait"
        elif mot in ("refusee", "refusée", "refuse", "refusé", "refus"):
            decision = "refusee"
        else:
            raise ValueError("décision inconnue : « fait » ou « refusee »")
        r = db.lire("SELECT id, domaine, compte FROM demandes WHERE id=? AND statut='ouverte'", (nombre(id, 0, 0, 2 ** 62, "id"),))
        if not r:
            raise ValueError("demande introuvable ou déjà traitée")
        rg = Regard(c.compte)
        if not rg.large and r[0]["domaine"] not in rg.carte and rg.societe_du_compte(r[0]["compte"]) != rg.soc:
            raise ValueError("demande introuvable ou déjà traitée")              # celle d'une autre société : elle n'existe pas pour cet administrateur
        db.ecrire("UPDATE demandes SET statut=?, reponse=?, traite_par=?, traite_ts=? WHERE id=?", (decision, str(reponse or "")[:500], c.compte, time.time(), r[0]["id"]))
        noter(c.compte, "adossement_" + ("fait" if decision == "fait" else "refuse"), r[0]["domaine"], r[0]["compte"])
        c.emettre("site.adossement", objet=("site", r[0]["domaine"]), donnees={"domaine": r[0]["domaine"], "compte": r[0]["compte"], "decision": decision})
        return {"id": r[0]["id"], "domaine": r[0]["domaine"], "compte": r[0]["compte"], "statut": decision}

    def prouver_reponse(c, res):
        return bool(db.lire("SELECT 1 FROM demandes WHERE id=? AND statut=?", (res["id"], res["statut"])))

    def defaire_reponse(c, res):
        if not db.lire("SELECT 1 FROM demandes WHERE domaine=? AND statut='ouverte'", (res["domaine"],)):
            db.ecrire("UPDATE demandes SET statut='ouverte', reponse='', traite_par='', traite_ts=NULL WHERE id=?", (res["id"],))

    def accorder(c, domaine, geste="restaurer", heures=24):
        compte = c.compte
        d = nom_hote(domaine)
        r = Regard(compte)
        if systeme(compte) or compte not in r.proprietaires(d):
            raise ValueError("ce site n'est pas à toi")
        geste = geste_accord(geste)
        h = nombre(heures, 24, 1, 168, "heures")
        fin = time.time() + h * 3600
        aid = db.ecrire("INSERT INTO accords(ts, domaine, compte, geste, jusqu_a) VALUES (?,?,?,?,?)", (time.time(), d, compte, geste, fin))
        noter(compte, "accord", d, "%s %d h" % (geste, h))
        c.emettre("site.accord", objet=("site", d), donnees={"domaine": d, "geste": geste, "compte": compte, "jusqu_a": fin})
        return {"id": aid, "domaine": d, "geste": geste, "jusqu_a": fin}

    def prouver_accord(c, res):
        return bool(db.lire("SELECT 1 FROM accords WHERE id=? AND jusqu_a > ?", (res["id"], time.time())))

    def defaire_accord(c, res):
        db.ecrire("DELETE FROM accords WHERE id=?", (res["id"],))

    def lier(c, domaine, genre, ref, note=""):
        d = Regard(c.compte).exiger(domaine)
        if genre not in GENRES_LIEN:
            raise ValueError("type de lien inconnu (%s)" % ", ".join(GENRES_LIEN))
        r = str(ref or "").strip()[:200]
        if not r:
            raise ValueError("référence obligatoire")
        avant = db.lire("SELECT note, ts FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, r))
        db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (d, genre, r, str(note or "")[:300], time.time()))
        noter(c.compte, "lien", d, "%s %s" % (genre, r))
        return {"domaine": d, "genre": genre, "ref": r, "note": str(note or "")[:300], "avant": avant[0] if avant else None}

    def prouver_lien(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"])))

    def defaire_lien(c, res):
        if res.get("avant"):
            db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (res["domaine"], res["genre"], res["ref"], res["avant"]["note"], res["avant"]["ts"]))
        else:
            db.ecrire("DELETE FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"]))

    def delier(c, domaine, genre, ref):
        d = Regard(c.compte).exiger(domaine)
        ref = str(ref or "").strip()
        r = db.lire("SELECT note, ts FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, ref))
        if not r:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, ref))
        noter(c.compte, "delie", d, "%s %s" % (genre, ref))
        return {"domaine": d, "genre": genre, "ref": ref, "note": r[0]["note"], "ts": r[0]["ts"]}

    def prouver_delie(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"]))

    def defaire_delie(c, res):
        db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (res["domaine"], res["genre"], res["ref"], res["note"], res["ts"]))

    def prouver_attribue(c, res):
        r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
        return bool(r) and r[0]["compte"] == res["compte"]

    def defaire_attribue(c, res):
        db.ecrire("DELETE FROM sites WHERE domaine=? AND compte=? AND origine='attribue'", (res["domaine"], res["compte"]))
        remettre_preuves(res.get("preuves"))

    def prouver_transfert(c, res):
        r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
        return bool(r) and r[0]["compte"] == res["vers"]

    # ------------------------------------------------------------------ les incidents : lire, dépanner, clore
    def qui_agit(c):
        """Qui signe un fait de la chronologie : le compte, ou l'agent qui agit en son nom."""
        acteur = str(getattr(c, "acteur", "") or "")
        return c.compte if acteur in ("", "humain", "compte") else "%s, pour %s" % (acteur, c.compte or "le système")

    def incident_a_portee(c, id, etats=None, refus=""):
        rows = db.lire("SELECT * FROM incidents WHERE id=?", (nombre(id, 0, 0, 2 ** 62, "id"),))
        if not rows or not Regard(c.compte).dans(rows[0]["domaine"]):
            raise ValueError("incident introuvable")                      # celui d'un autre n'existe pas pour ce compte
        if etats and rows[0]["etat"] not in etats:
            raise ValueError(refus or "cet incident n'est plus dans cet état")
        return rows[0]

    def incidents(c, etat="", domaine="", jours=30, limite=100):
        """Les incidents de la portée du compte. `etat` : « ouverts » (tout ce qui n'est pas résolu), « resolus », ou vide pour tous ; les résolus sur `jours` jours."""
        r = Regard(c.compte)
        j, lim = nombre(jours, 30, 1, 366, "jours"), nombre(limite, 100, 1, 500, "limite")
        d = r.exiger(domaine) if domaine else ""
        maintenant = time.time()
        lignes = db.lire("SELECT * FROM incidents WHERE (etat != 'resolu' OR debut >= ?)" + (" AND domaine=?" if d else "") + " ORDER BY id DESC LIMIT 2000",
                         (maintenant - j * 86400,) + ((d,) if d else ()))
        if not r.large and not d:
            lignes = [i for i in lignes if i["domaine"] in r.carte]
        mot = str(etat or "").strip().lower()
        if mot in ("ouverts", "ouvert"):
            lignes = [i for i in lignes if i["etat"] != "resolu"]
        elif mot in ("resolus", "résolus", "resolu"):
            lignes = [i for i in lignes if i["etat"] == "resolu"]
        elif mot:
            raise ValueError("état inconnu : « ouverts », « resolus », ou rien pour tous")
        return {"jours": j, "incidents": [ligne_incident(i, maintenant) for i in lignes[:lim]]}

    def incident(c, id):
        """Un incident : son diagnostic, ce que les mesures en disent, sa chronologie, et ce que ce compte peut faire dessus."""
        i = incident_a_portee(c, id)
        r = Regard(c.compte)
        d, maintenant = i["domaine"], time.time()
        vu = db.lire("SELECT up, depuis FROM etat_vu WHERE domaine=?", (d,))
        tombes = [x["domaine"] for x in db.lire("SELECT domaine FROM etat_vu WHERE up=0 AND domaine != ? ORDER BY domaine", (d,)) if r.large or x["domaine"] in r.carte]
        ouvert = i["etat"] in ("ouvert", "depannage")
        vo = Voisins()
        return dict(ligne_incident(i, maintenant), maintenance=vo.maintenance(d), acceptee=vo.acceptee(d), vu_de_la_machine=vo.vu_de_la_machine(d),
                    en_ligne=bool(vu and vu[0]["up"]), suivi=bool(vu),
                    mesures=[dict(m, up=bool(m["up"])) for m in db.lire("SELECT ts, code, ms, up, erreur FROM mesures WHERE domaine=? ORDER BY id DESC LIMIT 8", (d,))],
                    tombes_aussi=tombes[:20],                              # d'autres sites en panne au même moment : une cause commune, probablement
                    faits=db.lire("SELECT id, ts, acteur, genre, texte FROM incident_faits WHERE incident=? ORDER BY ts, id", (i["id"],)),
                    liens=_liens(d), contacts=rattaches(d)["contacts"],          # qui prévenir : les contacts que le module Contacts a rattachés à ce site
                    gestes={"prendre": ouvert and i["pris_par"] != c.compte, "noter": True, "connu": ouvert, "relever": ouvert,
                            "clore": i["etat"] == "retabli", "cause": i["etat"] == "resolu"})

    def incident_prendre(c, id):
        i = incident_a_portee(c, id, ("ouvert", "depannage"), "cet incident est déjà clos ou rétabli")
        if systeme(c.compte):
            raise ValueError("un incident se prend au nom d'un compte")
        if i["pris_par"] == c.compte:
            raise ValueError("tu t'en occupes déjà")
        db.ecrire("UPDATE incidents SET etat='depannage', pris_par=? WHERE id=?", (c.compte, i["id"]))
        f = fait_incident(i["id"], qui_agit(c), "pris", "S'en occupe%s." % (" (à la suite de %s)" % i["pris_par"] if i["pris_par"] else ""))
        noter(c.compte, "incident_pris", i["domaine"], "n° %d" % i["id"])
        return {"id": i["id"], "domaine": i["domaine"], "par": c.compte, "avant": {"etat": i["etat"], "pris_par": i["pris_par"]}, "fait": f}

    def prouver_pris(c, res):
        return bool(db.lire("SELECT 1 FROM incidents WHERE id=? AND pris_par=?", (res["id"], res["par"])))

    def defaire_pris(c, res):
        db.ecrire("UPDATE incidents SET etat=?, pris_par=? WHERE id=? AND etat='depannage' AND pris_par=?", (res["avant"]["etat"], res["avant"]["pris_par"], res["id"], res["par"]))
        db.ecrire("DELETE FROM incident_faits WHERE id=?", (res["fait"],))

    def incident_noter(c, id, texte=""):
        i = incident_a_portee(c, id)
        t = str(texte or "").strip()
        if not t:
            raise ValueError("une note ne peut pas être vide")
        return {"id": i["id"], "domaine": i["domaine"], "fait": fait_incident(i["id"], qui_agit(c), "note", t)}

    def prouver_fait(c, res):
        return bool(db.lire("SELECT 1 FROM incident_faits WHERE id=? AND incident=?", (res["fait"], res["id"])))

    def defaire_fait(c, res):
        db.ecrire("DELETE FROM incident_faits WHERE id=? AND incident=?", (res["fait"], res["id"]))

    def incident_connu(c, id, heures=24):
        """La panne est connue, quelqu'un s'en occupe : son constat se tait pendant `heures` heures (0 : il reparle). L'incident reste ouvert."""
        i = incident_a_portee(c, id, ("ouvert", "depannage"), "cet incident est déjà clos ou rétabli")
        h = nombre(heures, 24, 0, 168, "heures")
        jusqu = time.time() + h * 3600 if h else None
        db.ecrire("UPDATE incidents SET connu_jusqu=? WHERE id=?", (jusqu, i["id"]))
        f = fait_incident(i["id"], qui_agit(c), "connu", ("Panne connue : son alerte se tait %d h." % h) if h else "L'alerte de cette panne reparle.")
        return {"id": i["id"], "domaine": i["domaine"], "jusqu_a": jusqu, "avant": i["connu_jusqu"], "fait": f}

    def prouver_connu(c, res):
        r = db.lire("SELECT connu_jusqu FROM incidents WHERE id=?", (res["id"],))
        return bool(r) and r[0]["connu_jusqu"] == res["jusqu_a"]

    def defaire_connu(c, res):
        db.ecrire("UPDATE incidents SET connu_jusqu=? WHERE id=?", (res["avant"], res["id"]))
        db.ecrire("DELETE FROM incident_faits WHERE id=?", (res["fait"],))

    def incident_clore(c, id, cause=""):
        """Clôt un incident dont le site répond de nouveau, avec sa cause ; sur un incident déjà résolu, note ou corrige la cause."""
        i = incident_a_portee(c, id)
        t = str(cause or "").strip()[:500]
        if i["etat"] in ("ouvert", "depannage"):
            raise ValueError("le site ne répond pas encore : un incident se clôt quand il répond de nouveau")
        if i["etat"] == "resolu" and not t:
            raise ValueError("cet incident est déjà clos : écris sa cause pour la noter")
        avant = {k: i[k] for k in ("etat", "cause", "clos_par")}
        if i["etat"] == "retabli":
            db.ecrire("UPDATE incidents SET etat='resolu', cause=?, clos_par=? WHERE id=?", (t, c.compte or "?", i["id"]))
            f = fait_incident(i["id"], qui_agit(c), "clos", "Incident clos%s" % (" — cause : " + t if t else ", cause non notée."))
        else:
            db.ecrire("UPDATE incidents SET cause=? WHERE id=?", (t, i["id"]))
            f = fait_incident(i["id"], qui_agit(c), "cause", "Cause notée : " + t)
        noter(c.compte, "incident_clos", i["domaine"], ("n° %d — %s" % (i["id"], t))[:300])
        return {"id": i["id"], "domaine": i["domaine"], "cause": t, "avant": avant, "fait": f}

    def prouver_clos(c, res):
        r = db.lire("SELECT etat, cause FROM incidents WHERE id=?", (res["id"],))
        return bool(r) and r[0]["etat"] == "resolu" and r[0]["cause"] == res["cause"]

    def defaire_clos(c, res):
        a = res["avant"]
        db.ecrire("UPDATE incidents SET etat=?, cause=?, clos_par=? WHERE id=?", (a["etat"], a["cause"], a["clos_par"], res["id"]))
        db.ecrire("DELETE FROM incident_faits WHERE id=?", (res["fait"],))

    def relever(c, domaine):
        """Mesure un site tout de suite, sans attendre le tour de la sonde : la même mesure qu'elle, écrite au même endroit."""
        r = Regard(c.compte)
        d = r.exiger(domaine)
        if d not in r.domaines_connus():
            raise ValueError("ce nom n'est pas un site suivi : il se déclare d'abord")
        avant = db.lire("SELECT ts, code, ms, up, ssl_jours, erreur FROM mesures WHERE domaine=? ORDER BY id DESC LIMIT 1", (d,))
        avant = avant[0] if avant else None
        if avant and time.time() - avant["ts"] < RELEVE_MIN_S:
            return {"domaine": d, "ts": avant["ts"], "code": avant["code"], "ms": avant["ms"], "up": bool(avant["up"]), "erreur": avant["erreur"], "ssl_jours": avant["ssl_jours"],
                    "douteux": False, "recente": True}
        vu = db.lire("SELECT up, depuis FROM etat_vu WHERE domaine=?", (d,))
        i = incident_ouvert(d)
        m = mesurer(c, d, tour(), avant, (vu[0]["up"], vu[0]["depuis"]) if vu else None)
        if i:
            fait_incident(i["id"], qui_agit(c), "releve", "Relève à la demande : %s." % (("HTTP %s en %s ms" % (m["code"], m["ms"])) if m["code"] is not None else ("sans réponse — " + (m["erreur"] or "?"))))
        return dict(m, recente=False)

    def prouver_releve(c, res):
        return bool(db.lire("SELECT 1 FROM mesures WHERE domaine=? AND ts >= ?", (res["domaine"], res["ts"] - 1)))

    def defaire_releve(c, res):
        """Rien à défaire : une mesure est un fait observé, elle ne se retire pas de l'historique (le manifeste le dit : retour « aucun »)."""

    # ------------------------------------------------------------------ le calendrier d'un site
    def calendrier(c, domaine, mois="", jours=None):
        """Tout ce qui est arrivé à un site, jour par jour, sur un mois : l'état de chaque jour, ses coupures, ses incidents, les gestes faits dessus.
        `mois` « AAAA-MM » se lit à l'heure du serveur ; l'écran passe plutôt `jours` : les débuts de journée (secondes depuis 1970) tels qu'il les voit, puis la fin du dernier."""
        d = Regard(c.compte).exiger(domaine)
        maintenant = time.time()
        if jours:
            try:
                bornes = sorted({float(x) for x in jours})[:33]
            except (TypeError, ValueError):
                raise ValueError("« jours » : des secondes depuis 1970") from None
            if len(bornes) < 2 or bornes[-1] - bornes[0] > 33 * 86400:
                raise ValueError("« jours » : les débuts de journée d'un mois au plus, puis la fin du dernier")
        else:
            m = re.match(r"^(\d{4})-(\d{2})$", str(mois or "").strip()) if mois else None
            if mois and (not m or not 1 <= int(m.group(2)) <= 12):
                raise ValueError("« mois » s'écrit AAAA-MM")
            an, mo = (int(m.group(1)), int(m.group(2))) if m else time.localtime(maintenant)[:2]
            n = 28
            while time.localtime(time.mktime((an, mo, n + 1, 12, 0, 0, 0, 0, -1)))[1] == mo:
                n += 1
            bornes = [time.mktime((an, mo, k, 0, 0, 0, 0, 0, -1)) for k in range(1, n + 2)]
        a, b = bornes[0], bornes[-1]

        def rang(ts):
            k = 0
            while k + 1 < len(bornes) - 1 and ts >= bornes[k + 1]:
                k += 1
            return k
        cases = [{"debut": bornes[k], "mesures": 0, "rates": 0, "ms_max": None, "evenements": []} for k in range(len(bornes) - 1)]
        for x in db.lire("SELECT ts, up, ms FROM mesures WHERE domaine=? AND ts >= ? AND ts < ? ORDER BY ts", (d, a, b)):
            j = cases[rang(x["ts"])]
            j["mesures"] += 1
            if not x["up"]:
                j["rates"] += 1
            elif x["ms"] is not None and (j["ms_max"] is None or x["ms"] > j["ms_max"]):
                j["ms_max"] = x["ms"]
        inc = db.lire("SELECT * FROM incidents WHERE domaine=? AND debut < ? AND (fin IS NULL OR fin >= ?) ORDER BY debut", (d, b, a))
        debuts = [i["debut"] for i in inc]
        for i in inc:
            li = ligne_incident(i, maintenant)
            if a <= i["debut"] < b:
                cases[rang(i["debut"])]["evenements"].append({"ts": i["debut"], "genre": "incident", "texte": "Incident ouvert — %s" % (i["erreur"] or ("HTTP %s" % i["code"])), "incident": i["id"]})
            if i["fin"] and a <= i["fin"] < b:
                cases[rang(i["fin"])]["evenements"].append({"ts": i["fin"], "genre": "retour", "texte": "De nouveau en ligne après %s%s" % (li["duree"], (" — " + i["cause"]) if i["cause"] else ""), "incident": i["id"]})
        for f in Voisins().fenetres_de(d, a, b):
            if a <= f["debut"] < b:
                cases[rang(f["debut"])]["evenements"].append({"ts": f["debut"], "genre": "maintenance", "texte": "Maintenance" + (" — " + f["motif"] if f["motif"] else ""), "fin": f["fin"], "incident": None})
        for e in db.lire("SELECT ts, genre, detail FROM evenements_site WHERE domaine=? AND ts >= ? AND ts < ? ORDER BY ts", (d, a, b)):
            if e["genre"] == "panne" and any(abs(e["ts"] - x) < 2 for x in debuts):
                continue                                                # déjà dit par son incident
            if e["genre"] == "retour" and any(i["fin"] and abs(e["ts"] - i["fin"]) < 2 for i in inc):
                continue
            cases[rang(e["ts"])]["evenements"].append({"ts": e["ts"], "genre": e["genre"], "texte": e["detail"], "incident": None})
        for g in db.lire("SELECT ts, acteur, verbe, detail FROM journal WHERE domaine=? AND ts >= ? AND ts < ? ORDER BY ts", (d, a, b)):
            cases[rang(g["ts"])]["evenements"].append({"ts": g["ts"], "genre": "geste", "texte": g["verbe"], "acteur": g["acteur"], "detail": g["detail"], "incident": None})
        tot = rates = jours_mesures = jours_coupure = 0
        for j in cases:
            j["evenements"].sort(key=lambda e: e["ts"])
            if j["debut"] > maintenant:
                j["etat"] = "futur"
            elif not j["mesures"]:
                j["etat"] = "sans"
            else:
                pct = 100.0 * (j["mesures"] - j["rates"]) / j["mesures"]
                j["etat"] = "ok" if not j["rates"] else ("courte" if pct >= COUPURE_COURTE_PCT else "longue")
                j["disponibilite"] = round(pct, 2)
                tot, rates, jours_mesures = tot + j["mesures"], rates + j["rates"], jours_mesures + 1
                jours_coupure += 1 if j["rates"] else 0
        av = db.lire("SELECT COUNT(*) n, COALESCE(SUM(up),0) u FROM mesures WHERE domaine=? AND ts >= ? AND ts < ?", (d, a - (b - a), a))[0]
        cible = db.lire("SELECT pct FROM objectifs WHERE domaine=?", (d,))
        cible = cible[0]["pct"] if cible else objectif_defaut()
        dispo = round(100.0 * (tot - rates) / tot, 2) if tot else None
        return {"domaine": d, "debut": a, "fin": b, "jours": cases, "garde_j": entier("retention_j", 90),
                "mois": {"disponibilite": dispo, "avant": round(100.0 * av["u"] / av["n"], 2) if av["n"] else None, "jours_mesures": jours_mesures, "jours_coupure": jours_coupure,
                         "incidents": sum(1 for x in debuts if a <= x < b), "objectif": cible, "tenu": (dispo >= cible) if dispo is not None else None}}

    # ------------------------------------------------------------------ l'objectif, la société, qui est concerné
    def objectif(c, domaine, pct=None):
        """L'objectif de disponibilité d'un site (de 90 à 100 %) ; sans valeur, il reprend celui du réglage."""
        r = Regard(c.compte)
        d = r.exiger(domaine)
        if d not in r.domaines_connus():
            raise ValueError("un objectif se pose sur un site suivi")
        avant = db.lire("SELECT pct, par, ts FROM objectifs WHERE domaine=?", (d,))
        if pct in (None, ""):
            db.ecrire("DELETE FROM objectifs WHERE domaine=?", (d,))
            v = None
        else:
            try:
                v = round(float(str(pct).replace(",", ".").replace("%", "").strip()), 3)
            except (TypeError, ValueError):
                raise ValueError("un objectif est un pourcentage, de 90 à 100") from None
            if not 90 <= v <= 100:
                raise ValueError("un objectif est un pourcentage, de 90 à 100")
            db.ecrire("INSERT OR REPLACE INTO objectifs(domaine, pct, par, ts) VALUES (?,?,?,?)", (d, v, c.compte or "", time.time()))
        noter(c.compte, "objectif", d, ("%s %%" % v) if v is not None else "celui du réglage")
        return {"domaine": d, "pct": v, "avant": dict(avant[0]) if avant else None}

    def prouver_objectif(c, res):
        r = db.lire("SELECT pct FROM objectifs WHERE domaine=?", (res["domaine"],))
        return (not r) if res["pct"] is None else (bool(r) and r[0]["pct"] == res["pct"])

    def defaire_objectif(c, res):
        a = res.get("avant")
        if a:
            db.ecrire("INSERT OR REPLACE INTO objectifs(domaine, pct, par, ts) VALUES (?,?,?,?)", (res["domaine"], a["pct"], a["par"], a["ts"]))
        else:
            db.ecrire("DELETE FROM objectifs WHERE domaine=?", (res["domaine"],))

    def attribuer_societe(c, domaine, societe=""):
        """Attribue un site à une société (ou, sans société, lui rend celle de son compte). Les administrateurs de cette société le voient alors, quel que soit son compte."""
        r = Regard(c.compte)
        if not (r.super and r.tout):
            raise ValueError("seul le superadministrateur attribue un site à une société")
        d = nom_hote(domaine)
        if d not in r.domaines_connus():
            raise ValueError("ce nom n'est pas un site suivi")
        soc = str(societe or "").strip()
        if soc and soc not in societes_connues():
            raise ValueError("société inconnue")
        avant = db.lire("SELECT societe, par, ts FROM societes_site WHERE domaine=?", (d,))
        if soc and avant and avant[0]["societe"] == soc:
            raise ValueError("ce site est déjà attribué à cette société")
        if soc:
            db.ecrire("INSERT OR REPLACE INTO societes_site(domaine, societe, par, ts) VALUES (?,?,?,?)", (d, soc, c.compte or "", time.time()))
        else:
            db.ecrire("DELETE FROM societes_site WHERE domaine=?", (d,))
        noter(c.compte, "societe", d, soc or "aucune : celle de son compte")
        c.emettre("site.societe", objet=("site", d), donnees={"domaine": d, "societe": soc, "par": c.compte})
        return {"domaine": d, "societe": soc, "avant": dict(avant[0]) if avant else None}

    def prouver_societe(c, res):
        r = db.lire("SELECT societe FROM societes_site WHERE domaine=?", (res["domaine"],))
        return (bool(r) and r[0]["societe"] == res["societe"]) if res["societe"] else not r

    def defaire_societe(c, res):
        a = res.get("avant")
        if a:
            db.ecrire("INSERT OR REPLACE INTO societes_site(domaine, societe, par, ts) VALUES (?,?,?,?)", (res["domaine"], a["societe"], a["par"], a["ts"]))
        else:
            db.ecrire("DELETE FROM societes_site WHERE domaine=?", (res["domaine"],))

    def concerne(c):
        """Ce compte est-il concerné par les sites ? Il a un site, une déclaration à prouver, ou il administre. Le menu ne lui montre « Sites » que si oui."""
        r = Regard(c.compte)
        n = len(r.carte)
        attente = db.lire("SELECT COUNT(*) n FROM preuves WHERE compte=? AND cree >= ?", (c.compte or "", time.time() - PREUVE_GARDE_J * 86400))[0]["n"]
        return {"concerne": bool(r.tout or n or attente), "sites": n, "a_prouver": attente, "admin": r.tout}

    def alerte_accepter(c, cle="", jours=7):
        """« Je sais, c'est normal » : une alerte que Sites signale (certificat court, nom qui expire, sauvegarde, PHP) se tait `jours` jours.
        Elle revient d'elle-même à l'échéance, ou avant si son chiffre empire."""
        r = Regard(c.compte)
        cle = str(cle or "").strip()
        vue_ = _vue(r)
        v = next((x for x in vue_["vigilances"] + vue_["acceptees"] if x.get("cle") == cle), None)
        if not cle or v is None:
            raise ValueError("cette alerte n'existe pas, ou plus, dans ta portée")
        if v["niveau"] == "info":
            raise ValueError("une information ne s'accepte pas : elle ne demande rien")
        j = nombre(jours, 7, 1, 90, "jours")
        avant = db.lire("SELECT cle, domaine, titre, jusqu_a, valeur, par, ts FROM alertes_acceptees WHERE cle=?", (cle,))
        jusqu = time.time() + j * 86400
        db.ecrire("INSERT OR REPLACE INTO alertes_acceptees(cle, domaine, titre, jusqu_a, valeur, par, ts) VALUES (?,?,?,?,?,?,?)",
                  (cle, v["site"], v["titre"][:200], jusqu, v.get("valeur") if isinstance(v.get("valeur"), (int, float)) else None, c.compte or "", time.time()))
        noter(c.compte, "alerte_acceptee", v["site"], ("%s — %d j" % (v["titre"], j))[:300])
        return {"cle": cle, "domaine": v["site"], "jusqu_a": jusqu, "avant": dict(avant[0]) if avant else None}

    def prouver_acceptee(c, res):
        r = db.lire("SELECT jusqu_a FROM alertes_acceptees WHERE cle=?", (res["cle"],))
        return bool(r) and r[0]["jusqu_a"] == res["jusqu_a"]

    def remettre_acceptation(a):
        db.ecrire("INSERT OR REPLACE INTO alertes_acceptees(cle, domaine, titre, jusqu_a, valeur, par, ts) VALUES (?,?,?,?,?,?,?)",
                  (a["cle"], a["domaine"], a["titre"], a["jusqu_a"], a["valeur"], a["par"], a["ts"]))

    def defaire_acceptee(c, res):
        if res.get("avant"):
            remettre_acceptation(res["avant"])
        else:
            db.ecrire("DELETE FROM alertes_acceptees WHERE cle=?", (res["cle"],))

    def alerte_reprendre(c, cle=""):
        """Ne plus accepter une alerte : elle redevient une alerte."""
        cle = str(cle or "").strip()
        a = db.lire("SELECT cle, domaine, titre, jusqu_a, valeur, par, ts FROM alertes_acceptees WHERE cle=?", (cle,))
        if not a or not Regard(c.compte).dans(a[0]["domaine"]):
            raise ValueError("cette alerte n'est pas acceptée")
        db.ecrire("DELETE FROM alertes_acceptees WHERE cle=?", (cle,))
        noter(c.compte, "alerte_reprise", a[0]["domaine"], a[0]["titre"])
        return {"cle": cle, "domaine": a[0]["domaine"], "avant": dict(a[0])}

    def prouver_reprise(c, res):
        return not db.lire("SELECT 1 FROM alertes_acceptees WHERE cle=?", (res["cle"],))

    def defaire_reprise(c, res):
        remettre_acceptation(res["avant"])

    def voisins(c):
        """Relit tout de suite, auprès du Sensorium, les fenêtres de maintenance et les alertes acceptées — pour un compte qui a le droit de les lire ; sinon rien ne change.
        L'écran l'appelle après avoir posé ou annulé une fenêtre, pour que le site se taise sans attendre le tour de la sonde."""
        relever_sensorium()
        ms = miroir("sensorium", perime=True)
        ms = ms if isinstance(ms, dict) else {}
        maintenant = time.time()
        return {"lu": bool(ms.get("lu")), "fenetres_en_cours": sum(1 for f in ms.get("fenetres") or [] if f["debut"] <= maintenant < f["fin"]), "acceptees": len(ms.get("acceptees") or {})}

    def gestes(c):
        """Ce que chacun peut faire sur les sites : pour chaque geste, qui peut le faire (humain, compte, agents), à quel palier un agent le fait, et le droit exigé."""
        return {"gestes": [{"id": x.id, "libelle": x.libelle, "risque": x.risque, "qui": list(x.qui), "paliers": list(x.paliers), "droit": x.droit or ""}
                           for x in ctx.manifeste.capacites if x.risque != "lecture"]}

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("sonde", sonde)
    c.detecteur("panne", det_panne)
    c.detecteur("panne_proprietaire", det_panne_proprietaire)
    c.detecteur("lenteur", det_lenteur)
    c.detecteur("certificat_court", det_certificat)
    c.detecteur("adossement_demande", det_demandes)
    for cid, f in (("vue", vue), ("fiche", fiche), ("historique", historique), ("disponibilite", disponibilite), ("serie", serie), ("journal", journal), ("liens", liens), ("demandes", demandes), ("accord", accord),
                   ("incidents", incidents), ("incident", incident), ("calendrier", calendrier), ("concerne", concerne), ("gestes", gestes), ("voisins", voisins), ("tendances", tendances)):
        c.implementer(cid, f)
    c.implementer("prouver", prouver, prouver_ligne("compte"), defaire_prouve, simuler=lambda x, domaine="", **_: "vérifierait la preuve de propriété de %s" % domaine)
    c.implementer("relever", relever, prouver_releve, defaire_releve, simuler=lambda x, domaine="", **_: "mesurerait %s tout de suite" % domaine)
    c.implementer("objectif", objectif, prouver_objectif, defaire_objectif, simuler=lambda x, domaine="", pct=None, **_: "poserait l'objectif de %s à %s" % (domaine, ("%s %%" % pct) if pct not in (None, "") else "celui du réglage"))
    c.implementer("attribuer_societe", attribuer_societe, prouver_societe, defaire_societe, simuler=lambda x, domaine="", societe="", **_: "attribuerait %s à la société %s" % (domaine, societe or "de son compte"))
    c.implementer("alerte_accepter", alerte_accepter, prouver_acceptee, defaire_acceptee, simuler=lambda x, cle="", jours=7, **_: "accepterait l'alerte « %s » pour %s jours" % (cle, jours))
    c.implementer("alerte_reprendre", alerte_reprendre, prouver_reprise, defaire_reprise, simuler=lambda x, cle="", **_: "cesserait d'accepter l'alerte « %s »" % cle)
    c.implementer("incident_prendre", incident_prendre, prouver_pris, defaire_pris, simuler=lambda x, id="", **_: "prendrait en charge l'incident %s" % id)
    c.implementer("incident_noter", incident_noter, prouver_fait, defaire_fait, simuler=lambda x, id="", **_: "ajouterait une note à l'incident %s" % id)
    c.implementer("incident_connu", incident_connu, prouver_connu, defaire_connu, simuler=lambda x, id="", heures=24, **_: "ferait taire %s h l'alerte de l'incident %s" % (heures, id))
    c.implementer("incident_clore", incident_clore, prouver_clos, defaire_clos, simuler=lambda x, id="", **_: "clorait l'incident %s" % id)
    c.implementer("declarer", declarer, prouver_ligne("compte"), defaire_declarer, simuler=lambda x, domaine="", **_: "déclarerait %s au compte" % domaine)
    c.implementer("retirer", retirer, prouver_retire, defaire_retire, simuler=lambda x, domaine="", **_: "retirerait %s de la liste" % domaine)
    c.implementer("attribuer", attribuer, prouver_attribue, defaire_attribue, simuler=lambda x, domaine="", compte="", **_: "attribuerait %s à %s" % (domaine, compte))
    c.implementer("transferer", transferer, prouver_transfert, defaire_transfert, simuler=lambda x, domaine="", vers="", **_: "transférerait %s à %s" % (domaine, vers))
    c.implementer("demander", demander, prouver_demande, defaire_demande, simuler=lambda x, domaine="", **_: "demanderait l'adossement de %s au panneau" % domaine)
    c.implementer("repondre_demande", repondre_demande, prouver_reponse, defaire_reponse, simuler=lambda x, id="", decision="", **_: "fermerait la demande %s (%s)" % (id, decision))
    c.implementer("accorder", accorder, prouver_accord, defaire_accord, simuler=lambda x, domaine="", geste="restaurer", **_: "accorderait « %s » sur %s" % (geste, domaine))
    c.implementer("lier", lier, prouver_lien, defaire_lien, simuler=lambda x, domaine="", genre="", ref="", **_: "lierait %s %s à %s" % (genre, ref, domaine))
    c.implementer("delier", delier, prouver_delie, defaire_delie, simuler=lambda x, domaine="", genre="", ref="", **_: "délierait %s %s de %s" % (genre, ref, domaine))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : nom_hote, _sonder_http, _cert_jours, duree_texte, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
