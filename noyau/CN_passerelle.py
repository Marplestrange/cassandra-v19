# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La passerelle
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #52336b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La passerelle : l'API HTTP du noyau. UNE porte pour tous les modules, présents et à venir.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=52336b ▼▼▼
"""La passerelle : l'API HTTP du noyau. UNE porte pour tous les modules, présents et à venir.

Un module n'écrit aucune route. Il déclare des capacités, et la passerelle les rend toutes joignables par la même URL :

    POST /api/agir/<module>.<capacite>      {"args": {...}, "essai": false}
    GET  /api/agir/<module>.<capacite>?cle=valeur      (capacités de LECTURE seulement)

Qui est-ce ? Un jeton de session (cookie HttpOnly SameSite=Strict, ou en-tête « Authorization: Bearer ») ou le jeton d'un agent invité. Le compte vient
TOUJOURS du jeton, jamais du corps de la requête, et l'exécuteur (droits, paliers, preuve, journal) fait le reste : la passerelle n'a pas de règle à elle.

    POST /api/connexion {"compte", "mot_de_passe"}     GET /api/moi      POST /api/deconnexion      GET /api/menu      GET /api/modules      GET /api/sante

Sécurité de base : écoute locale par défaut, corps limité à 1 Mo, JSON seulement, un en-tête « X-Cassandra » exigé pour toute écriture au cookie
(un site tiers ne peut pas le poser sans accord préalable du navigateur : c'est le garde-fou CSRF), aucune ouverture CORS, pas de cache.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

log = logging.getLogger("noyau.CN_passerelle")

TAILLE_MAX = 1024 * 1024
TAILLE_TELEVERSE = 34 * 1024 * 1024      # une archive de module (32 Mo au plus) et son enveloppe ; seule une capacité qui DÉCLARE `corps_octets` reçoit un corps de cette taille
# L'interface (V18 extraite) pose des gestionnaires en ligne et charge ses bibliothèques sur deux CDN ; tout le reste est fermé.
CSP_PAGE = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; connect-src 'self'; frame-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
TYPES_STATIQUES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
                   ".json": "application/json; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon", ".webmanifest": "application/manifest+json", ".woff2": "font/woff2"}
RE_CAPACITE = re.compile(r"^[a-z][a-z0-9_]{1,40}\.[a-z][a-z0-9_]{1,40}$")
COOKIE = "cassandra_session"
HSTS = "max-age=31536000; includeSubDomains"
BOUCLES = ("127.0.0.1", "::1", "localhost")


def cookie_secure_effectif(demande, hote, proxy, env=None) -> bool:
    """Le cookie de session part-il avec `Secure` ? OUI par défaut dès que l'écoute n'est pas une boucle locale ou qu'un reverse proxy de confiance est devant
    (c'est lui qui porte le TLS : un cookie sans `Secure` y passerait en clair au premier oubli). On peut le FORCER ou le COUPER explicitement : par l'argument
    ou par CASSANDRA_COOKIE_SECURE, en texte ("1", "oui"… / "0", "non"…). Un booléen False et None veulent dire « pas de choix » : le défaut sûr s'applique."""
    for v in (os.environ.get("CASSANDRA_COOKIE_SECURE") if env is None else env, demande):
        if isinstance(v, str):
            t = v.strip().lower()
            if t in ("0", "non", "no", "false", "off", "faux"):
                return False
            if t in ("1", "oui", "yes", "true", "on", "vrai"):
                return True
        elif v is True:
            return True
    return bool(proxy) or (hote or "") not in BOUCLES
STATUTS_HTTP = {"faite": 200, "simulee": 200, "racontee": 202, "refuse": 403, "echec": 500, "annulee": 500, "annulation_impossible": 500}


def _valeur(v: str):
    try:
        return json.loads(v)
    except ValueError:
        return v


class Passerelle:
    def __init__(self, noyau, hote="127.0.0.1", port=9000, cookie_secure=None, proxy_de_confiance=False, interface=None):
        self.noyau = noyau
        self.interface = os.path.realpath(interface) if interface else None      # le dossier de l'interface servie à GET / (None : API seule)
        self.hote, self.port = hote, int(port)
        self.proxy = proxy_de_confiance          # croire X-Forwarded-For : seulement derrière notre propre reverse proxy
        self.cookie_secure = cookie_secure_effectif(cookie_secure, self.hote, self.proxy)
        self.serveur = None
        self.fil = None
        passerelle = self

        class Gestionnaire(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "Cassandra"
            sys_version = ""

            def log_message(self, fmt, *a):           # pas de bruit sur la sortie standard : le journal du noyau suffit
                log.debug("%s " + fmt, self.address_string(), *a)

            def do_GET(self):
                passerelle._traiter(self, "GET")

            def do_POST(self):
                passerelle._traiter(self, "POST")

            def do_OPTIONS(self):                      # aucune ouverture CORS : on le dit, on n'accorde rien
                passerelle._repondre(self, 405, {"erreur": "méthode non permise"})

        self._classe = Gestionnaire

    # ---- cycle de vie ----
    def demarrer(self) -> int:
        self.serveur = ThreadingHTTPServer((self.hote, self.port), self._classe)
        self.serveur.daemon_threads = True
        self.port = self.serveur.server_address[1]       # le port réel (0 : le système choisit)
        self.fil = threading.Thread(target=self.serveur.serve_forever, name="passerelle", daemon=True)
        self.fil.start()
        log.info("passerelle à l'écoute sur %s:%d", self.hote, self.port)
        return self.port

    def arreter(self) -> None:
        if self.serveur is not None:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.serveur = None

    # ---- une requête ----
    def _vider(self, h):
        """Le corps d'une requête qu'on n'a pas lu (une réponse d'erreur partie avant de le lire) reste dans la connexion : en HTTP/1.1 persistant, la requête
        suivante le trouverait devant elle (« Unsupported method ('{"args":{}}POST') ») et un refus passerait pour une autre erreur. On le lit pour le jeter ;
        s'il est trop grand, ou d'une forme qu'on ne sait pas lire (morcelé), on ferme la connexion plutôt que de la laisser désynchronisée."""
        if getattr(h, "_corps_lu", False):
            return
        h._corps_lu = True
        if "chunked" in (h.headers.get("Transfer-Encoding") or "").lower():
            h.close_connection = True
            return
        try:
            n = int(h.headers.get("Content-Length") or 0)
        except ValueError:
            h.close_connection = True
            return
        if n <= 0:
            return
        if n > TAILLE_MAX:
            h.close_connection = True
            return
        try:
            h.rfile.read(n)
        except Exception:
            h.close_connection = True

    def _repondre(self, h, code, corps, cookie=None):
        if h.command == "POST":
            self._vider(h)
        donnees = json.dumps(corps, ensure_ascii=False, default=str).encode("utf-8")
        h.send_response(code)
        if h.close_connection:
            h.send_header("Connection", "close")
        h.send_header("Content-Type", "application/json; charset=utf-8")
        h.send_header("Content-Length", str(len(donnees)))
        h.send_header("Cache-Control", "no-store")
        h.send_header("X-Content-Type-Options", "nosniff")
        h.send_header("Referrer-Policy", "no-referrer")
        h.send_header("Content-Security-Policy", "default-src 'none'")
        self._hsts(h)
        if cookie:
            h.send_header("Set-Cookie", cookie)
        h.end_headers()
        h.wfile.write(donnees)

    def _hsts(self, h) -> None:
        """Strict-Transport-Security : seulement quand le cookie est `Secure` ET que la requête est arrivée en HTTPS par notre proxy (X-Forwarded-Proto, cru
        seulement s'il est de confiance). Sur du HTTP direct l'en-tête n'a pas de sens (les navigateurs l'ignorent) : on ne le pose pas."""
        if self.cookie_secure and self.proxy and (h.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower() == "https":
            h.send_header("Strict-Transport-Security", HSTS)

    def _ip(self, h) -> str:
        if self.proxy:
            xff = h.headers.get("X-Forwarded-For", "")
            if xff:
                return xff.split(",")[0].strip()[:45]
        return h.client_address[0][:45]

    def _jeton(self, h):
        """(jeton, venait_du_cookie)."""
        a = h.headers.get("Authorization", "")
        if a.startswith("Bearer "):
            return a[7:].strip(), False
        for part in h.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE and v:
                return v, True
        return "", False

    def _qui(self, h):
        """(compte, acteur, admin) ou None. Une session donne un humain ; le jeton d'un agent invité donne un agent."""
        jeton, _ = self._jeton(h)
        if not jeton:
            return None
        idt = self.noyau.identite
        if len(jeton) == 64:
            v = idt.valider(jeton)
            if v.get("ok"):
                return v["compte"], "humain", v["admin"], jeton
        else:
            v = idt.valider_agent(jeton)
            if v.get("ok"):
                return v["compte"], "agent", False, jeton
        return None

    def _corps(self, h):
        n = int(h.headers.get("Content-Length") or 0)
        if n > TAILLE_MAX:
            raise ValueError("corps trop grand (1 Mo au plus)")        # _repondre fermera la connexion : ce corps-là n'est pas lu
        h._brut = b""
        if n == 0:
            h._corps_lu = True
            return {}
        if "json" not in (h.headers.get("Content-Type") or ""):
            raise ValueError("Content-Type : application/json attendu")     # idem : _repondre le lit pour le jeter
        brut = h.rfile.read(n)
        h._corps_lu = True
        h._brut = brut                                              # les octets exacts : un webhook SIGNÉ (Stripe) ne se vérifie que sur eux, jamais sur un JSON relu
        try:
            d = json.loads(brut.decode("utf-8"))
        except ValueError:
            raise ValueError("JSON illisible")
        if not isinstance(d, dict):
            raise ValueError("un objet JSON est attendu")
        return d

    def _traiter(self, h, methode):
        h._corps_lu = False                       # le gestionnaire vit autant que la connexion : l'état « corps lu » se remet à zéro à CHAQUE requête
        try:
            url = urlparse(h.path)
            chemin = unquote(url.path)
            if methode == "GET" and chemin == "/api/sante":
                return self._repondre(h, 200, {"ok": True, "version": self.noyau.etat()["version"]})
            if methode == "POST" and chemin == "/api/connexion":
                return self._connexion(h)
            if chemin.startswith("/api/public/"):
                return self._public(h, methode, chemin[len("/api/public/"):])
            if methode == "GET" and not chemin.startswith("/api/"):
                return self._statique(h, chemin)
            qui = self._qui(h)
            if qui is None:
                return self._repondre(h, 401, {"erreur": "authentification requise"})
            compte, acteur, admin, jeton = qui
            h._jeton_session = jeton
            venait_cookie = self._jeton(h)[1]
            if methode == "POST" and venait_cookie and h.headers.get("X-Cassandra") != "1":
                return self._repondre(h, 403, {"erreur": "en-tête X-Cassandra: 1 exigé (protection contre les requêtes d'un autre site)"})
            if methode == "GET" and chemin == "/api/moi":
                return self._repondre(h, 200, {"compte": compte, "acteur": acteur, "admin": admin})
            if methode == "POST" and chemin == "/api/deconnexion":
                r = self.noyau.executeur.executer("comptes.fermer_session", acteur, {"jeton": jeton}, compte=compte)
                return self._repondre(h, 200, {"ok": True}, cookie="%s=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict" % COOKIE)
            if methode == "POST" and chemin == "/api/reverifier":
                return self._reverifier(h, compte, acteur, jeton)
            if methode == "GET" and chemin == "/api/menu":
                r = self.noyau.executeur.executer("menus.lire_menu", acteur, {"role": "admin" if admin else "utilisateur", "compte": compte}, compte=compte)
                return self._repondre(h, STATUTS_HTTP.get(r["statut"], 200), r)
            if methode == "GET" and chemin == "/api/modules":
                branches = set(self.noyau._branches)               # ce qui est réellement branché (en exploitation : les modules actifs ; sans gestion des modules : tous)
                return self._repondre(h, 200, {"modules": [dict({k: m[k] for k in ("id", "nom", "famille", "etat", "version", "essentiel") if k in m}, actif=m["id"] in branches) for m in self.noyau.catalogue_modules()],
                                               "sections": self.noyau.sections_modules()["sections"]})
            if chemin.startswith("/api/agir/"):
                return self._agir(h, methode, chemin[len("/api/agir/"):], url.query, compte, acteur)
            if methode == "POST" and chemin.startswith("/api/televerser/"):
                return self._televerser(h, chemin[len("/api/televerser/"):], url.query, compte, acteur)
            return self._repondre(h, 404, {"erreur": "route inconnue"})
        except ValueError as ex:
            return self._repondre(h, 400, {"erreur": str(ex)})
        except Exception:
            log.exception("passerelle : erreur interne")
            return self._repondre(h, 500, {"erreur": "erreur interne"})

    def _statique(self, h, chemin):
        """Un fichier du dossier de l'interface, jamais autre chose : pas de remontée (..), pas de lien qui sorte du dossier, extensions connues."""
        if not self.interface:
            return self._repondre(h, 404, {"erreur": "route inconnue"})
        rel = "index.html" if chemin in ("/", "") else chemin.lstrip("/")
        if "\\" in rel or "\x00" in rel:
            return self._repondre(h, 404, {"erreur": "introuvable"})
        parts = rel.split("/")
        reel = os.path.realpath(os.path.join(self.interface, *parts))
        if not os.path.isfile(reel) and not parts[-1].startswith(("CN_", "EC_")):      # docs/CN_FORMAT.md §3 bis : le dépôt préfixe ses fichiers, les URL gardent leur nom
            reel = os.path.realpath(os.path.join(self.interface, *(parts[:-1] + ["CN_" + parts[-1]])))
        ext = os.path.splitext(reel)[1].lower()
        if os.path.commonpath([reel, self.interface]) != self.interface or ext not in TYPES_STATIQUES or not os.path.isfile(reel):
            return self._repondre(h, 404, {"erreur": "introuvable"})
        with open(reel, "rb") as f:
            donnees = f.read()
        h.send_response(200)
        h.send_header("Content-Type", TYPES_STATIQUES[ext])
        h.send_header("Content-Length", str(len(donnees)))
        h.send_header("Cache-Control", "no-cache")
        h.send_header("X-Content-Type-Options", "nosniff")
        h.send_header("Referrer-Policy", "no-referrer")
        if ext == ".html":
            h.send_header("Content-Security-Policy", CSP_PAGE)
        self._hsts(h)
        h.end_headers()
        h.wfile.write(donnees)

    def _connexion(self, h):
        corps = self._corps(h)
        compte, mdp = str(corps.get("compte") or ""), str(corps.get("mot_de_passe") or "")
        r = self.noyau.executeur.executer("comptes.ouvrir_session", "humain",
                                          {"compte": compte, "mot_de_passe": mdp, "ip": self._ip(h), "agent": h.headers.get("User-Agent", ""), "preuve": corps.get("preuve") if isinstance(corps.get("preuve"), dict) else None},
                                          compte="", interne=True)
        if r["statut"] != "faite":
            return self._repondre(h, 503, {"erreur": "la connexion est indisponible (module des comptes)"})
        res = r["resultat"]
        if res.get("second_facteur"):
            return self._repondre(h, 401, {"erreur": res["erreur"], "second_facteur": True, "methodes": res["methodes"], "invite": res["invite"]})
        if not res.get("ok"):
            return self._repondre(h, 429 if res.get("limite") else 401, {"erreur": res.get("erreur", "refusé"), "attente_s": res.get("attente_s", 0)})
        cookie = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict%s" % (COOKIE, res["jeton"], self.noyau.identite.ttl, "; Secure" if self.cookie_secure else "")
        corps = {"ok": True, "compte": res["compte"], "jeton": res["jeton"]}
        avert = self.noyau.identite.avertissement_connexion(res["compte"])         # un administrateur encore dans sa période de grâce est prévenu, avec la date
        if avert:
            corps["avertissement"] = avert
        return self._repondre(h, 200, corps, cookie=cookie)

    def _sensible(self, e, acteur) -> bool:
        """Un geste sensible : une capacité à risque « eleve », ou qui exige un droit que son module déclare sensible. Il ne concerne que la session d'un utilisateur."""
        if acteur != "humain":
            return False
        c = e.capacite
        d = getattr(self.noyau.droits, "connus", {}).get(c.droit) if c.droit else None
        return c.risque == "eleve" or bool(d and d[1].sensible)

    def _exiger_reverification(self, h, e, compte, acteur) -> bool:
        """Vrai si la requête a reçu sa réponse (401 + invitation du second facteur) : la session d'un administrateur est ancienne, il doit ressaisir son second facteur."""
        jeton = getattr(h, "_jeton_session", "")
        if not jeton or not self._sensible(e, acteur):
            return False
        demande = self.noyau.identite.reverif_requise(compte, jeton)
        if not demande:
            return False
        self._repondre(h, 401, {"erreur": "Geste sensible : ressaisissez votre second facteur", "second_facteur": True, "reverification": True,
                                "methodes": demande["methodes"], "invite": demande["invite"]})
        return True

    def _reverifier(self, h, compte, acteur, jeton):
        """POST /api/reverifier {"preuve": {...}} : la session ouverte prouve de nouveau son second facteur, puis le geste sensible se redemande."""
        corps = self._corps(h)
        if acteur != "humain":
            return self._repondre(h, 403, {"erreur": "réservé à la session d'un utilisateur"})
        r = self.noyau.identite.reverifier(jeton, compte, corps.get("preuve"), self._ip(h))
        if r.get("ok"):
            return self._repondre(h, 200, {"ok": True})
        return self._repondre(h, 429 if r.get("limite") else 401, {"erreur": r.get("error", "refusé"), "attente_s": r.get("attente_s", 0)})

    def _public(self, h, methode, cle):
        """Les capacités qui se DÉCLARENT publiques (qui = ["anonyme"]) : avant la connexion. Jamais les autres. L'origine est consignée."""
        if methode != "POST" or not RE_CAPACITE.match(cle):
            return self._repondre(h, 404, {"erreur": "route inconnue"})
        e = self.noyau.catalogue.get(cle)
        if e is None or "anonyme" not in e.capacite.qui:
            return self._repondre(h, 404, {"erreur": "capacité inconnue ou non publique"})
        corps = self._corps(h)
        noms = self._noms_args(e)
        if "corps_octets" in noms:                                 # un webhook signé : les octets reçus, tels quels (la capacité masque cet argument du journal)
            args = {"corps_octets": getattr(h, "_brut", b"")}
        elif "corps_brut" in noms:                                 # un service extérieur (le webhook de Telegram) poste son propre JSON, sans enveloppe « args »
            args = {"corps_brut": corps}
        else:
            args = corps.get("args") or {}
            if not isinstance(args, dict):
                raise ValueError("« args » doit être un objet")
        if "ip" in noms:
            args["ip"] = self._ip(h)
        if "en_tetes" in noms:                                     # les en-têtes (le secret d'un webhook), jamais le cookie ni l'autorisation
            args["en_tetes"] = {k.lower(): v for k, v in h.headers.items() if k.lower() not in ("cookie", "authorization")}
        r = self.noyau.executeur.executer(cle, "anonyme", args, compte="")
        res = r.get("resultat") if r.get("statut") == "faite" else None
        if isinstance(res, dict) and res.get("ouvre_session") and res.get("jeton"):        # une capacité publique qui PROUVE un compte (clé d'accès) ouvre la session
            cookie = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict%s" % (COOKIE, res["jeton"], self.noyau.identite.ttl, "; Secure" if self.cookie_secure else "")
            return self._repondre(h, 200, {"ok": True, "compte": res["compte"], "jeton": res["jeton"]}, cookie=cookie)
        if isinstance(res, dict) and res.get("ok") is False:                               # un refus rendu comme résultat (jamais une exception : voir webauthn)
            code = res.get("code") if res.get("code") in (401, 404, 410, 429) else (429 if res.get("limite") else 401)
            corps = {k: v for k, v in res.items() if k in ("erreur", "titre", "mdp", "attente_s")}
            return self._repondre(h, code, dict(corps, erreur=res.get("erreur", "refusé")))
        return self._repondre(h, STATUTS_HTTP.get(r["statut"], 200), r)

    @staticmethod
    def _noms_args(e):
        try:
            return e.faire.__code__.co_varnames[:e.faire.__code__.co_argcount]
        except AttributeError:
            return ()

    def _televerser(self, h, cle, requete, compte, acteur):
        """Des octets (une archive) pour une capacité qui les attend (`corps_octets`) : mêmes droits, même journal (l'argument est masqué par la capacité), mais une taille permise plus grande.
        Le corps est brut (application/octet-stream) ; les autres arguments viennent de l'adresse (?nom=...)."""
        if not RE_CAPACITE.match(cle):
            return self._repondre(h, 404, {"erreur": "capacité inconnue"})
        e = self.noyau.catalogue.get(cle)
        if e is None or "corps_octets" not in self._noms_args(e):
            return self._repondre(h, 404, {"erreur": "cette capacité ne reçoit pas de fichier"})
        if self._exiger_reverification(h, e, compte, acteur):
            return
        n = int(h.headers.get("Content-Length") or 0)
        if n <= 0:
            raise ValueError("fichier vide")
        if n > TAILLE_TELEVERSE:
            raise ValueError("fichier trop grand (%d Mo au plus)" % (TAILLE_TELEVERSE // 2 ** 20))
        h._brut = h.rfile.read(n)
        h._corps_lu = True
        args = {k: _valeur(v[-1]) for k, v in parse_qs(requete, keep_blank_values=True).items() if k in self._noms_args(e) and k != "corps_octets"}
        args["corps_octets"] = h._brut
        r = self.noyau.executeur.executer(cle, acteur, args, compte=compte)
        return self._repondre(h, STATUTS_HTTP.get(r["statut"], 200), r)

    def _agir(self, h, methode, cle, requete, compte, acteur):
        if not RE_CAPACITE.match(cle):
            return self._repondre(h, 404, {"erreur": "capacité inconnue"})
        e = self.noyau.catalogue.get(cle)
        if e is None:
            return self._repondre(h, 404, {"erreur": "capacité inconnue : %s" % cle})
        if self._exiger_reverification(h, e, compte, acteur):
            return
        if methode == "GET":
            if e.capacite.ecrit:
                return self._repondre(h, 405, {"erreur": "une écriture se demande par POST"})
            args, essai = {k: _valeur(v[-1]) for k, v in parse_qs(requete, keep_blank_values=True).items()}, False
        else:
            corps = self._corps(h)
            args, essai = corps.get("args") or {}, bool(corps.get("essai"))
            if not isinstance(args, dict):
                raise ValueError("« args » doit être un objet")
        # L'adresse de la SESSION vient de la connexion, jamais du corps : une capacité qui la déclare (`ip_session`) la reçoit d'ici, et celle qu'un client
        # enverrait est écrasée — une adresse fournie par le client permettrait de s'enfermer dehors en s'autorisant quelqu'un d'autre.
        if "ip_session" in self._noms_args(e):
            args["ip_session"] = self._ip(h)
        else:
            args.pop("ip_session", None)
        societe = (h.headers.get("X-Societe") or "").strip()[:41]       # la société choisie ; vide : celle du compte. L'exécuteur vérifie qu'elle est bien l'une des siennes.
        r = self.noyau.executeur.executer(cle, acteur, args, essai=essai, compte=compte, societe=societe)
        return self._repondre(h, STATUTS_HTTP.get(r["statut"], 200), r)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _valeur, Passerelle
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
