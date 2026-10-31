# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le pont FastPanel
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : CN
# VERSION CN : 0.2.0  #3caba1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le pont FastPanel.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=3caba1 ▼▼▼
"""Le pont FastPanel.

Deux voies, chacune pour ce qu'elle fait de mieux :
  - la LECTURE se fait dans la base SQLite du panneau, ouverte en lecture seule (mode=ro) : c'est la base d'un autre logiciel, en service,
    on ne risque pas de l'altérer. Elle dit ce que l'API ne liste pas (propriétaires, liens base-site, copies de sauvegarde...) ;
  - l'ACTION passe par l'API du panneau (jamais par une écriture dans sa base : il en dérive des vhosts, des utilisateurs MySQL, des boîtes).

Leçons de la V18 gardées ici :
  - une adresse CHOISIE est la seule essayée (deviner à côté fait parler à un autre service : le port 5501 accepte une session mais pas les mêmes
    appels que le panneau, sur 8888) ; sans réglage, le panneau local, https puis http, 8888 ;
  - un certificat auto-signé n'est toléré QUE sur la boucle locale : la connexion ne quitte pas la machine ;
  - le jeton de session vit en mémoire, jamais sur disque ni dans un message d'erreur ;
  - le chemin d'API s'essaie avec et sans le préfixe « /api » (la façade nginx le retire parfois) ;
  - une source illisible LÈVE une erreur : un zéro par absence ne doit jamais ressembler à un zéro par conformité ;
  - un service arrêté en permanence est normal ; c'est la TRANSITION d'actif à arrêté, sans action de Cassandra, qui se signale ;
  - « sans certificat » et « certificat de date inconnue » sont deux états ;
  - les booléens d'un formulaire s'écrivent « true » / « false » (Go ne lit pas « True »).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import sqlite3
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from . import CN_parefeu as pf
except ImportError:                                     # chargé à plat (banc d'un module seul) : le frère se lit par son chemin
    import importlib.util as _iu
    _sp = _iu.spec_from_file_location("fastpanel_parefeu", str(Path(__file__).with_name("CN_parefeu.py")))
    pf = _iu.module_from_spec(_sp)
    _sp.loader.exec_module(pf)

# ------------------------------------------------------------------ constantes
BASES_PAR_DEFAUT = ("https://127.0.0.1:8888", "http://127.0.0.1:8888")
CHEMINS_LOGIN = ("/api/authorization", "/api/login", "/api/v1/login", "/api/auth", "/authorization", "/login", "/v1/login", "/auth")
CHEMINS_BASE = ("/usr/local/fastpanel2/app/db/fastpanel2.db", "/usr/local/fastpanel/app/db/fastpanel.db")
CHEMINS_CONFIG = ("/usr/local/fastpanel2/app/config/parameters.yml", "/usr/local/fastpanel2/app/config/parameters.yaml", "/usr/local/fastpanel2/config/database.yml")
TTL_SESSION = 1800
RE_BASE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
RE_UTILISATEUR_BASE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
RE_NOM = re.compile(r"^[\w .\-]{2,64}$")
RE_CHEMIN = re.compile(r"^/[\w./\-]{1,200}$")
RE_SERVICE = re.compile(r"^[A-Za-z0-9@._\-]{1,64}$")
RE_HOTE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$")
ACTIONS_RELANCER = ("start", "restart")
ACTIONS_ARRETER = ("stop",)
FIN_SUPPORT_PHP = {
    "5.6": "2018-12-31", "7.0": "2019-01-10", "7.1": "2019-12-01", "7.2": "2020-11-30", "7.3": "2021-12-06", "7.4": "2022-11-28",
    "8.0": "2023-11-26", "8.1": "2025-12-31", "8.2": "2026-12-31", "8.3": "2027-12-31", "8.4": "2028-12-31",
}
ATTENTE_SERVICE_S = 8          # combien de temps la preuve attend qu'un service change d'état
ATTENTE_SSL_S = 60             # combien de temps la preuve attend qu'un certificat soit réémis
PAS_ATTENTE_S = 0.5
SERVICE_DEMANDE_PERIME_S = 180


class PontErreur(Exception):
    """Une erreur du pont, au message sûr : jamais l'en-tête d'autorisation, donc jamais le jeton.
    genre : erreur | non_configure | acces_refuse | injoignable | source."""

    def __init__(self, message, code=None, genre="erreur"):
        super().__init__(message)
        self.code, self.genre = code, genre


# ------------------------------------------------------------------ réglages
_CTX = None
_point = None          # les points d'évolution du module (ctx.point), posés par brancher()
_SESSIONS = {}          # base -> {"jeton", "t"} : une session par adresse, en mémoire seulement
_TRACE_LOGIN = []       # ce que chaque tentative de connexion a réellement renvoyé (sans jamais citer un secret)


def _reglage(nom, defaut=""):
    if _CTX is None:
        return defaut
    try:
        v = _CTX.reglage(nom, "")
    except Exception:
        return defaut
    return defaut if v in (None, "") else v


def _delai():
    try:
        return max(3, min(120, int(_reglage("delai", 20) or 20)))
    except (TypeError, ValueError):
        return 20


def _adresses():
    choisie = str(_reglage("url", "") or "").strip().rstrip("/")
    if choisie:
        return [choisie]
    return list(BASES_PAR_DEFAUT)


def configure():
    """Vrai si de quoi se connecter est réglé : un jeton, ou un compte et son mot de passe."""
    return bool(str(_reglage("jeton", "") or "").strip() or (str(_reglage("utilisateur", "") or "").strip() and str(_reglage("mot_de_passe", "") or "")))


# ------------------------------------------------------------------ l'API
def _ouvrir(url, donnees, entetes, timeout, methode):
    """Requête HTTP. Un certificat auto-signé n'est toléré que sur la boucle locale : le panneau se sert un certificat pour son propre
    nom, toujours « invalide » vu de 127.0.0.1, et la connexion ne quitte jamais la machine. Ailleurs, la vérification reste entière."""
    req = urllib.request.Request(url, data=donnees, headers=entetes, method=methode)
    hote = urllib.parse.urlparse(url).hostname or ""
    if url.startswith("https://") and hote in ("127.0.0.1", "localhost", "::1"):
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return urllib.request.urlopen(req, timeout=timeout, context=c)
    return urllib.request.urlopen(req, timeout=timeout)


def _trouver_jeton(d):
    piles = [d]
    while piles:
        cur = piles.pop()
        if isinstance(cur, dict):
            for k in ("token", "access_token", "jwt", "accessToken"):
                v = cur.get(k)
                if isinstance(v, str) and len(v) > 20:
                    return v
            piles.extend(v for v in cur.values() if isinstance(v, (dict, list)))
        elif isinstance(cur, list):
            piles.extend(v for v in cur if isinstance(v, (dict, list)))
    return ""


def _login_sur(base, utilisateur, mdp, timeout):
    """Obtient un JWT. Rend (jeton, statuts_vus, erreurs_reseau). Chaque chemin, chaque nom de champ : deux nommages coexistent selon les versions."""
    statuts, reseau = set(), 0
    for chemin in CHEMINS_LOGIN:
        for champ, corps in (("username", {"username": utilisateur, "password": mdp}), ("login", {"login": utilisateur, "password": mdp})):
            try:
                with _ouvrir(base + chemin, json.dumps(corps).encode(), {"Content-Type": "application/json", "Accept": "application/json"}, timeout, "POST") as r:
                    d = json.loads(r.read(200000).decode("utf-8", "replace") or "{}")
            except urllib.error.HTTPError as ex:
                statuts.add(ex.code)
                _TRACE_LOGIN.append("%s%s [%s] -> %s" % (base, chemin, champ, ex.code))
                continue
            except (urllib.error.URLError, OSError, ValueError) as ex:
                reseau += 1
                _TRACE_LOGIN.append("%s%s [%s] -> %s" % (base, chemin, champ, type(ex).__name__))
                continue
            jeton = _trouver_jeton(d)
            if jeton:
                return jeton, statuts, reseau
            _TRACE_LOGIN.append("%s%s [%s] -> 200 sans jeton" % (base, chemin, champ))
    return "", statuts, reseau


def _session():
    """(base, jeton) valables. Lève PontErreur : non_configure, acces_refuse ou injoignable, jamais un message qui cite un secret."""
    jeton_fixe = str(_reglage("jeton", "") or "").strip()
    utilisateur, mdp = str(_reglage("utilisateur", "") or "").strip(), str(_reglage("mot_de_passe", "") or "")
    if not jeton_fixe and not (utilisateur and mdp):
        raise PontErreur("ni jeton ni compte du panneau dans les réglages", genre="non_configure")
    adresses = _adresses()
    if jeton_fixe:
        return adresses[0], jeton_fixe
    maintenant = time.time()
    for base in adresses:
        e = _SESSIONS.get(base)
        if e and maintenant - e["t"] < TTL_SESSION:
            return base, e["jeton"]
    del _TRACE_LOGIN[:]
    vus, reseau = set(), 0
    for base in adresses:
        jeton, statuts, r = _login_sur(base, utilisateur, mdp, _delai())
        if jeton:
            _SESSIONS[base] = {"jeton": jeton, "t": time.time()}
            return base, jeton
        vus |= statuts
        reseau += r
    if vus & {401, 403, 422}:
        raise PontErreur("le panneau refuse le compte de Cassandra (%s)" % ", ".join(str(s) for s in sorted(vus & {401, 403, 422})), genre="acces_refuse")
    if vus:
        raise PontErreur("aucun point de connexion reconnu sur %s (réponses : %s)" % (", ".join(adresses), ", ".join(str(s) for s in sorted(vus))), genre="erreur")
    raise PontErreur("le panneau ne répond pas sur %s" % ", ".join(adresses), genre="injoignable")


def _diag(brut):
    t = (brut or "").lstrip()[:400].lower()
    if not t or t.startswith(("{", "[")):
        return ""
    if "cloudflare" in t or "cf-ray" in t or "just a moment" in t:
        return "Cloudflare a répondu à la place du panneau : l'adresse des réglages passe par lui"
    if t.startswith("<!doctype") or t.startswith("<html") or "<title" in t:
        return "une page HTML a répondu, pas l'API : l'adresse des réglages ne mène probablement pas au panneau"
    return "réponse illisible (ni JSON ni HTML)"


def _formulaire(corps):
    plat = {}
    for k, v in (corps or {}).items():
        plat[k] = ("true" if v else "false") if isinstance(v, bool) else ("" if v is None else v)
    return urllib.parse.urlencode(plat).encode()


def appeler(methode, chemin, corps=None, encodage="json", timeout=None):
    """Un appel à l'API. Rend les données décodées ({} pour une réponse vide). Lève PontErreur.
    Le chemin s'essaie avec et sans « /api » ; une session refusée (401) est rouverte une fois."""
    timeout = timeout or _delai()
    chemin = "/" + chemin.lstrip("/")
    formes = [chemin, chemin[4:] if chemin.startswith("/api/") else "/api" + chemin]
    for tentative in range(2):
        base, jeton = _session()
        entetes = {"Authorization": "Bearer " + jeton, "Accept": "application/json"}
        donnees = None
        if corps is not None:
            if encodage == "form":
                donnees, entetes["Content-Type"] = _formulaire(corps), "application/x-www-form-urlencoded"
            else:
                donnees, entetes["Content-Type"] = json.dumps(corps).encode(), "application/json"
        dernier = (0, "")
        expire = False
        for k, forme in enumerate(formes):
            try:
                with _ouvrir(base + forme, donnees, entetes, timeout, methode.upper()) as r:
                    brut, code = r.read(2000000).decode("utf-8", "replace"), r.getcode()
            except urllib.error.HTTPError as ex:
                try:
                    brut = ex.read(20000).decode("utf-8", "replace")
                except Exception:
                    brut = ""
                dernier = (ex.code, brut)
                if ex.code == 404 and k + 1 < len(formes):
                    continue
                if ex.code == 401 and tentative == 0 and not str(_reglage("jeton", "") or "").strip():
                    _SESSIONS.pop(base, None)
                    expire = True
                    break
                motif = {401: "jeton refusé ou expiré", 403: "le compte du panneau n'a pas les droits requis", 404: "point d'entrée inconnu de cette version"}.get(ex.code, "erreur %s" % ex.code)
                d = _diag(brut)
                raise PontErreur("%s%s%s" % (motif, " — " + d if d else "", " : " + brut[:300] if brut and not d else ""), code=ex.code,
                                 genre="acces_refuse" if ex.code in (401, 403) else "erreur")
            except (urllib.error.URLError, OSError) as ex:
                raise PontErreur("le panneau ne répond pas : %s" % str(getattr(ex, "reason", ex))[:160], genre="injoignable")
            try:
                return json.loads(brut) if brut.strip() else {}
            except ValueError:
                return {"raw": brut[:2000]}
        if expire:
            continue
        raise PontErreur("point d'entrée inconnu sous les deux formes de chemin", code=dernier[0] or 404)
    raise PontErreur("session refusée par le panneau", code=401, genre="acces_refuse")


def _liste(d):
    """Une réponse de liste : directe, ou enveloppée dans « data »."""
    if isinstance(d, dict) and isinstance(d.get("data"), list):
        d = d["data"]
    elif isinstance(d, dict):
        d = [d] if d else []
    return [x for x in (d or []) if isinstance(x, dict)]


def _objet(d):
    return d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), dict) else (d if isinstance(d, dict) else {})


# ------------------------------------------------------------------ la base du panneau (lecture seule)
def chemin_base():
    r = str(_reglage("base_panneau", "") or "").strip()
    if r:
        return r if os.path.isfile(r) else ""
    motif = re.compile(r"^\s*main\s*:\s*['\"]?(\S+\.db)['\"]?\s*$")
    for cfg in CHEMINS_CONFIG:
        try:
            for ligne in Path(cfg).read_text(errors="replace").splitlines():
                m = motif.match(ligne)
                if m and os.path.isfile(m.group(1)):
                    return m.group(1)
        except OSError:
            continue
    for p in CHEMINS_BASE:
        if os.path.isfile(p) and os.access(p, os.R_OK):
            return p
    return ""


def _requete(sql, params=()):
    """SELECT seulement. Lève PontErreur(genre='source') si la base est introuvable ou illisible : jamais une liste vide qui ferait
    passer une panne pour un parc vide."""
    if not sql.lstrip().upper().startswith(("SELECT", "PRAGMA TABLE_INFO")):
        raise PontErreur("la base du panneau ne se lit qu'avec SELECT", genre="source")
    chemin = chemin_base()
    if not chemin:
        raise PontErreur("la base du panneau est introuvable ou illisible (réglage « base_panneau », ou emplacements habituels de FastPanel)", genre="source")
    erreur = None
    # mode=ro d'abord (SQLite refuse alors toute écriture, même le journal) ; une base WAL refuse parfois le -shm : repli sur une connexion
    # ordinaire où seul un SELECT est émis, ce qui n'altère rien.
    for uri, ro in ((Path(chemin).resolve().as_uri() + "?mode=ro", True), (chemin, False)):
        try:
            con = sqlite3.connect(uri, uri=ro, timeout=5)
            try:
                return con.execute(sql, params).fetchall()
            finally:
                con.close()
        except sqlite3.Error as ex:
            m = str(ex).lower()
            erreur = ex
            if ro and any(k in m for k in ("unable to open", "readonly", "read-only", "attempt to write", "disk i/o")):
                continue
            break
    raise PontErreur("lecture de la base du panneau impossible : %s" % str(erreur)[:200], genre="source")


def _colonnes(table):
    if not re.match(r"^[a-z0-9_]+$", table):
        return set()
    try:
        return {r[1] for r in _requete("PRAGMA table_info(%s)" % table)}
    except PontErreur:
        return set()


def _exiger(table, *colonnes):
    """Le schéma attendu est-il là ? Sinon une erreur qui le DIT (une version du panneau qui change ne doit pas se lire « aucun »)."""
    _requete("SELECT 1")                                           # la base elle-même d'abord : introuvable n'est pas « table absente »
    cols = _colonnes(table)
    if not cols:
        raise PontErreur("la table « %s » n'existe pas dans la base du panneau (autre version de FastPanel ?)" % table, genre="source")
    manque = [c for c in colonnes if c not in cols]
    if manque:
        raise PontErreur("la table « %s » n'a pas la colonne %s (autre version de FastPanel ?)" % (table, ", ".join(manque)), genre="source")
    return cols


def _t(v):
    return "" if v is None else str(v)


def _mo(v):
    try:
        return round(float(v or 0) / 1048576.0, 2)
    except (TypeError, ValueError):
        return 0.0


def _vrai(v):
    return str(v).strip().lower() in ("1", "true", "t", "yes", "active", "enabled")


def nom_hote(d):
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def hote_valide(d):
    """Un nom d'hôte, rien d'autre : ni le « _ » de la page par défaut de nginx, ni un joker (deux sites fantômes ont reçu des alertes en V18)."""
    return bool(RE_HOTE.match(str(d or "").strip().rstrip(".").lower()))


# ------------------------------------------------------------------ lectures du parc
def _lecture(op, tables, **options):
    """Lire une famille de données du panneau. Le PLAN (quelles requêtes, selon les colonnes de CETTE version de FastPanel) et la FORME (ce que les lignes deviennent) sont un POINT D'ÉVOLUTION :
    points/EC_lecture.py. Les lectures se font ICI, en SELECT seulement : l'EC ne touche jamais la base."""
    schema = {t: sorted(_colonnes(t)) for t in tables}
    plan = _point("lecture", {"phase": "plan", "op": op, "schema": schema, "options": options})
    if plan.get("erreur"):
        raise PontErreur(plan["erreur"], genre="source")
    jeux = [_requete(q) if q else [] for q in plan["requetes"]]
    return _point("lecture", {"phase": "forme", "op": op, "schema": schema, "options": options, "jeux": jeux})["valeur"]


def lire_utilisateurs():
    _exiger("panel_account", "username")
    return _lecture("utilisateurs", ("panel_account",))


def lire_sites(seuil=30, maintenant=None):
    """Les sites du panneau, avec l'état de leur certificat. Quatre états : aucun (rien de rattaché), inconnu (rattaché sans date lisible), echu, proche (sous le seuil), actif.
    L'horloge se lit ICI : l'EC reçoit l'instant."""
    _exiger("site", "domain")
    auj = maintenant or datetime.now(timezone.utc).replace(tzinfo=None)
    return _lecture("sites", ("certificate", "website_backends", "site_stats"), seuil=seuil, maintenant=auj.strftime("%Y-%m-%d %H:%M:%S"))


def lire_bases():
    _exiger("db", "name")
    return _lecture("bases", ("db", "datbases_users", "database_user"))


def lire_ftp():
    _exiger("ftp_account", "name")
    return _lecture("ftp", ("ftp_account",))


def lire_mail():
    return _lecture("mail", ("mailboxes", "email_domain"))


def lire_dns():
    return _lecture("dns", ("record", "domain"))


def lire_services():
    """Un service par identifiant : le panneau décrit exim sous deux clés (name et service). La mise en forme est un POINT D'ÉVOLUTION (points/EC_lecture.py, opération « services »)."""
    return _point("lecture", {"phase": "forme", "op": "services", "schema": {}, "options": {}, "jeux": [appeler("GET", "/api/services")]})["valeur"]



def _proprietaires_sites():
    return {nom_hote(r[0]): _t(r[1]).strip().lower() for r in _requete("SELECT s.domain, COALESCE(p.username,'') FROM site s LEFT JOIN panel_account p ON s.owner_id = p.id") if r[0]}


def lire_copies(limite=60):
    """Les copies de sauvegarde faites (version 2 du panneau). L'état se déduit : fin renseignée = réussie ; début sans fin = en cours ;
    action « error »/« failed » = échec."""
    _exiger("backup_copy_v2", "start_at")
    cols = _colonnes("backup_copy_v2")
    def c(nom, defaut="''"):
        return "COALESCE(c.%s,%s)" % (nom, defaut) if nom in cols else defaut
    lignes = _requete(
        "SELECT COALESCE(pl.name,''), %s, %s, %s, %s, %s, %s, %s, COALESCE(a.name,''), COALESCE(a.type,''), COALESCE(p.username,''), %s, %s "
        "FROM backup_copy_v2 c LEFT JOIN backup_plan_v2 pl ON c.plan_id = pl.id LEFT JOIN backup_account a ON pl.account_id = a.id "
        "LEFT JOIN panel_account p ON pl.owner_id = p.id ORDER BY c.start_at DESC LIMIT %d"
        % (c("action"), c("total_uploaded", "0"), c("total_source", "0"), c("start_at"), c("end_at"), c("total_file_count", "0"), c("partial", "0"), c("copied_user"), c("dbs"), max(1, min(int(limite), 500))))
    sortie = []
    for r in lignes:
        duree = None
        try:
            if r[4] and r[5]:
                duree = int((datetime.strptime(_t(r[5])[:19], "%Y-%m-%d %H:%M:%S") - datetime.strptime(_t(r[4])[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() // 60)
        except ValueError:
            duree = None
        etat = "reussie" if r[5] else ("en_cours" if r[4] else "echec")
        if str(r[1]).lower() in ("error", "failed"):
            etat = "echec"
        try:
            bases = [str(x.get("name") or "") for x in json.loads(r[12] or "[]") if isinstance(x, dict)]
        except ValueError:
            bases = []
        compte = _t(r[11])
        sortie.append({"plan": r[0], "etat": etat, "partielle": _vrai(r[7]), "envoye_mo": _mo(r[2]), "source_mo": _mo(r[3]), "debut": _t(r[4])[:19], "fin": _t(r[5])[:19],
                       "duree_min": duree, "fichiers": r[6], "compte": compte or r[10], "proprietaire": r[10], "bases": [b for b in bases if b],
                       "destination": ("%s (%s)" % (r[8], r[9])) if r[8] else "", "erreur": (r[1] or "échec") if etat == "echec" else ""})
    return sortie


def _proxys():
    """Les sites qui ne servent qu'un proxy : rien à sauvegarder chez eux."""
    cols = _colonnes("website_backends")
    if not {"frontend_id", "main", "type"} <= cols:
        return set()
    return {nom_hote(r[0]) for r in _requete("SELECT s.domain FROM site s JOIN website_backends b ON b.frontend_id = s.id WHERE b.main = 1 AND b.type = 'reverse_proxy'") if r[0]}


# ------------------------------------------------------------------ les audits (fonctions pures sur des listes)
def audit_certificats(sites):
    """Les certificats des sites rangés par état. Le calcul est un POINT D'ÉVOLUTION : points/EC_audit.py (opération « certificats »)."""
    return _point("audit", {"op": "certificats", "sites": sites})["valeur"]


def audit_sauvegardes(sites, copies, proxys, seuil_j, maintenant=None):
    """Une sauvegarde périmée est plus dangereuse qu'une absente : elle donne l'illusion d'être couvert. On regarde donc la DATE de la dernière
    copie réussie du compte propriétaire, pas son existence."""
    limite = ((maintenant or datetime.now(timezone.utc).replace(tzinfo=None)) - timedelta(days=seuil_j)).strftime("%Y-%m-%d")
    derniere = {}
    for c in copies:
        if c["etat"] != "reussie":
            continue
        for cle in {c["compte"].strip().lower(), c["proprietaire"].strip().lower()} - {""}:
            if c["debut"][:10] > derniere.get(cle, ""):
                derniere[cle] = c["debut"][:10]
    sans, perimees = [], []
    for s in sites:
        if nom_hote(s["domaine"]) in proxys:
            continue
        d = derniere.get(s["proprietaire"].strip().lower(), "")
        if not d:
            sans.append(s["domaine"])
        elif d < limite:
            perimees.append({"domaine": s["domaine"], "derniere": d})
    return {"seuil_j": seuil_j, "sans": sans, "perimees": perimees, "total": len(sites)}


def audit_php(sites, maintenant=None):
    """Les versions de PHP en fin de support ou bientôt. Le calcul est un POINT D'ÉVOLUTION : points/EC_audit.py (opération « php »). L'horloge se lit ICI."""
    auj = maintenant or datetime.now(timezone.utc).replace(tzinfo=None)
    return _point("audit", {"op": "php", "sites": sites, "maintenant": auj.strftime("%Y-%m-%d %H:%M:%S")})["valeur"]


# ------------------------------------------------------------------ services (par l'API)
def _trouver_service(services, nom):
    court = str(nom or "").strip().lower().replace(".service", "")
    for s in services:
        if s["nom"].lower().replace(".service", "") == court or court in s["alias"]:
            return s
    raise ValueError("service « %s » inconnu du panneau" % nom)


# ------------------------------------------------------------------ le branchement
def brancher(ctx):
    global _CTX, _point
    _CTX = ctx
    _point = ctx.point
    PANNEAU = ("fastpanel", "principal")
    memoire = {"audit_t": 0.0}

    def instance(c):
        return c.lire(*PANNEAU, portee=c.TOUT)

    def seuil_ssl():
        """Le seuil d'alerte d'un certificat : celui du module `certificats` (son propriétaire). L'ancien réglage `ssl_alerte_j` n'est repris que si le
        propriétaire est resté à son défaut (migration : rien d'une installation existante ne change en silence) ; sans le propriétaire, son défaut."""
        try:
            ancien = int(_reglage("ssl_alerte_j", 0) or 0)
        except (TypeError, ValueError):
            ancien = 0
        try:
            r = _CTX.executer_lecture("certificats.seuil") or {}
            jours, defaut = int(r["jours"]), int(r.get("defaut", 21))
        except Exception:
            jours, defaut = 21, 21
        return ancien if (ancien > 0 and jours == defaut) else jours

    def seuil_sauvegarde():
        try:
            return int(_reglage("sauvegarde_age_max_j", 7) or 7)
        except (TypeError, ValueError):
            return 7

    def calculer_audit():
        """Les audits du parc, d'après la base du panneau. Chaque audit dit sa propre panne plutôt que de se taire."""
        sortie, sites = {}, None
        try:
            sites = lire_sites(seuil_ssl())
            sortie["certificats"] = audit_certificats(sites)
            sortie["php"] = audit_php(sites)
        except PontErreur as ex:
            sortie["erreur"] = str(ex)
            return sortie
        try:
            sortie["sauvegardes"] = audit_sauvegardes(sites, lire_copies(500), _proxys(), seuil_sauvegarde())
        except PontErreur as ex:
            sortie["sauvegardes"] = {"erreur": str(ex)}
        return sortie

    # ---- la relève
    def releve_services(c):
        services = lire_services()
        maintenant = time.time()
        for s in services:
            anc = c.lire("fastpanel_service", s["nom"], portee=c.TOUT)
            avant = anc["etat"] if anc else ""
            donnees = {"id": s["id"], "etat_panneau": s["etat"]}
            if avant == "demande" and maintenant - float(anc["donnees"].get("demande_t", 0)) < SERVICE_DEMANDE_PERIME_S:
                continue                                           # Cassandra vient d'agir dessus : la preuve de l'acte tranchera
            if s["actif"]:
                nouvel = "actif"
                if avant == "tombe":
                    c.emettre("fastpanel.service_revenu", objet=("fastpanel_service", s["nom"]), donnees={"service": s["nom"]})
            elif avant in ("actif", "tombe"):
                nouvel = "tombe"
                if avant == "actif":
                    c.emettre("fastpanel.service_tombe", objet=("fastpanel_service", s["nom"]), donnees={"service": s["nom"], "etat": s["etat"]})
            else:
                nouvel = "arrete"                                   # arrêté depuis toujours (ou à la demande) : c'est normal
            if not anc or anc["etat"] != nouvel or anc["donnees"].get("etat_panneau") != s["etat"]:
                c.poser("fastpanel_service", s["nom"], s["nom"], etat=nouvel, donnees=donnees)
        return services

    def releve(c):
        precedent = instance(c)
        donnees = dict(precedent["donnees"] if precedent else {})
        nouvel, erreur = "ok", ""
        if not configure():
            nouvel, erreur = "non_configure", "ni jeton ni compte du panneau dans les réglages"
        else:
            try:
                donnees["services"] = {"total": len(releve_services(c)), "tombes": sum(1 for o in c.lister(portee=c.TOUT, type="fastpanel_service") if o["etat"] == "tombe")}
            except PontErreur as ex:
                nouvel = {"acces_refuse": "refuse", "injoignable": "injoignable"}.get(ex.genre, "erreur")
                erreur = str(ex)
        if time.time() - memoire["audit_t"] >= 900 or "audit" not in donnees:
            donnees["audit"] = calculer_audit()
            memoire["audit_t"] = time.time()
        donnees["erreur"] = erreur
        if precedent and precedent["etat"] in ("injoignable", "refuse") and nouvel == "ok":
            c.emettre("fastpanel.reprise", objet=PANNEAU, donnees={})
        elif nouvel in ("injoignable", "refuse") and (not precedent or precedent["etat"] != nouvel):
            c.emettre("fastpanel.injoignable" if nouvel == "injoignable" else "fastpanel.acces_refuse", objet=PANNEAU, donnees={"erreur": erreur})
        c.poser(*PANNEAU, "FastPanel", etat=nouvel, donnees=donnees)

    def audit_de(c, cle):
        i = instance(c)
        return ((i or {}).get("donnees") or {}).get("audit", {}).get(cle) or {}

    def constat_etat(c, voulu, titre):
        i = instance(c)
        return [{"objet": PANNEAU, "titre": titre, "detail": i["donnees"].get("erreur", "")}] if i and i["etat"] == voulu else []

    def det_services(c):
        return [{"objet": ("fastpanel_service", o["id"]), "titre": "Service arrêté sans action de Cassandra : %s" % o["id"], "detail": "passé de actif à %s" % o["donnees"].get("etat_panneau", "arrêté")}
                for o in c.lister(portee=c.TOUT, type="fastpanel_service") if o["etat"] == "tombe"]

    def det_certificats(c):
        a = audit_de(c, "certificats")
        sortie = [{"objet": ("fastpanel", d), "titre": "Certificat échu : %s" % d, "detail": "le certificat est échu"} for d in a.get("echus", [])]
        sortie += [{"objet": ("fastpanel", x["domaine"]), "titre": "Certificat de %s : %s jour(s)" % (x["domaine"], x["jours"]), "detail": "échéance le %s" % x["echeance"]} for x in a.get("proches", [])]
        return sortie

    def det_sauvegardes(c):
        a = audit_de(c, "sauvegardes")
        sortie = [{"objet": ("fastpanel", d), "titre": "Aucune sauvegarde réussie pour %s" % d, "detail": "aucune copie réussie ne couvre le compte de ce site"} for d in a.get("sans", [])]
        sortie += [{"objet": ("fastpanel", x["domaine"]), "titre": "Sauvegarde périmée : %s" % x["domaine"], "detail": "dernière copie le %s (seuil : %s jours)" % (x["derniere"], a.get("seuil_j"))} for x in a.get("perimees", [])]
        return sortie

    def det_php(c):
        a = audit_de(c, "php")
        return [{"objet": ("fastpanel", x["domaine"]), "titre": "PHP %s sans correctifs de sécurité : %s" % (x["php"], x["domaine"]), "detail": "support terminé le %s" % x["fin"]} for x in a.get("fin_de_support", [])]

    # ---- lectures
    def resume(c):
        i = instance(c)
        return None if not i else dict(i["donnees"], etat=i["etat"])

    def sante(c):
        sortie = {"api": {"ok": False}, "base_panneau": {"ok": False}}
        _SESSIONS.clear()                                          # une épreuve force une vraie connexion
        try:
            for chemin in ("/api/account", "/api/databases", "/api/users", "/api/services"):
                try:
                    d = appeler("GET", chemin, timeout=8)
                except PontErreur as ex:
                    if ex.code in (401, 403) or ex.genre in ("non_configure", "injoignable", "acces_refuse"):
                        raise
                    continue
                sortie["api"] = {"ok": True, "chemin": chemin, "elements": len(_liste(d))}
                break
            else:
                sortie["api"] = {"ok": False, "erreur": "l'API répond mais aucun point d'entrée connu n'a abouti — autre version ?"}
        except PontErreur as ex:
            sortie["api"] = {"ok": False, "erreur": str(ex), "genre": ex.genre, "essais": [t for t in _TRACE_LOGIN if "-> 404" not in t][:8]}
        try:
            chemin = chemin_base()
            _requete("SELECT 1")
            sortie["base_panneau"] = {"ok": True, "chemin": chemin}
        except PontErreur as ex:
            sortie["base_panneau"] = {"ok": False, "erreur": str(ex)}
        return sortie

    def en_valeur(fonction, *a):
        try:
            return fonction(*a)
        except PontErreur as ex:
            raise ValueError(str(ex))

    def utilisateurs(c):
        return en_valeur(lire_utilisateurs)

    def sites(c):
        return en_valeur(lire_sites, seuil_ssl())

    def bases(c):
        return en_valeur(lire_bases)

    def ftp(c):
        return en_valeur(lire_ftp)

    def mail(c):
        return en_valeur(lire_mail)

    def dns(c):
        return en_valeur(lire_dns)

    def sauvegardes(c, limite=60):
        return en_valeur(lire_copies, limite)

    def plans(c):
        for chemin in ("/api/v2/backup/plans", "/api/backup/plans"):
            try:
                return _liste(appeler("GET", chemin))
            except PontErreur as ex:
                derniere = ex
        raise ValueError(str(derniere))

    def stockages(c):
        return en_valeur(lambda: _liste(appeler("GET", "/api/backups/accounts")))

    def services(c):
        return en_valeur(lire_services)

    def certificats(c):
        return en_valeur(lambda: audit_certificats(lire_sites(seuil_ssl())))

    def ssl_sonder(c, domaine):
        d = nom_hote(domaine)
        if not hote_valide(d):
            raise ValueError("nom de domaine invalide")
        try:
            ctxssl = ssl.create_default_context()
            with socket.create_connection((d, 443), timeout=8) as brut:
                with ctxssl.wrap_socket(brut, server_hostname=d) as tls:
                    cert = tls.getpeercert()
        except (OSError, ssl.SSLError) as ex:
            return {"domaine": d, "ok": False, "erreur": str(ex)[:200]}          # un échec est une information : pas de HTTPS, mauvais nom, port fermé
        fin = cert.get("notAfter", "")
        reste = (datetime.strptime(fin, "%b %d %H:%M:%S %Y %Z") - datetime.now(timezone.utc).replace(tzinfo=None)).days if fin else None
        emetteur = next((v for champ in (cert.get("issuer") or ()) for k, v in champ if k == "organizationName"), "")
        return {"domaine": d, "ok": True, "echeance": fin, "jours": reste, "emetteur": emetteur, "noms": [v for k, v in (cert.get("subjectAltName") or ()) if k == "DNS"]}

    def php(c):
        return en_valeur(lambda: audit_php(lire_sites(seuil_ssl())))

    def audit(c):
        return calculer_audit()

    # ---- services : relancer / arrêter
    def _agir_service(c, service, action):
        if not RE_SERVICE.match(str(service or "")):
            raise ValueError("nom de service invalide")
        fiche = _trouver_service(lire_services(), service)
        c.poser("fastpanel_service", fiche["nom"], fiche["nom"], etat="demande", donnees={"id": fiche["id"], "demande_t": time.time(), "action": action})
        try:
            appeler("PUT", "/api/services/%s/%s" % (fiche["id"], action), {})
        except PontErreur:
            c.poser("fastpanel_service", fiche["nom"], fiche["nom"], etat="actif" if fiche["actif"] else "arrete", donnees={"id": fiche["id"], "etat_panneau": fiche["etat"]})
            raise
        return {"service": fiche["nom"], "id": fiche["id"], "action": action, "etait_actif": fiche["actif"]}

    def relancer(c, service, action="restart"):
        if action not in ACTIONS_RELANCER:
            raise ValueError("action : %s" % " | ".join(ACTIONS_RELANCER))
        return _agir_service(c, service, action)

    def arreter(c, service, action="stop"):
        if action not in ACTIONS_ARRETER:
            raise ValueError("action : %s" % " | ".join(ACTIONS_ARRETER))
        return _agir_service(c, service, action)

    def _etat_attendu(res):
        return res["action"] != "stop"

    def _marquer(c, res, actif, etat_panneau=""):
        c.poser("fastpanel_service", res["service"], res["service"], etat="actif" if actif else "arrete", donnees={"id": res["id"], "etat_panneau": etat_panneau})

    def prouver_service(c, res):
        voulu = _etat_attendu(res)
        fin = time.time() + ATTENTE_SERVICE_S
        while True:
            fiche = _trouver_service(lire_services(), res["service"])
            if fiche["actif"] == voulu:
                _marquer(c, res, voulu, fiche["etat"])
                return True
            if time.time() >= fin:
                _marquer(c, res, fiche["actif"], fiche["etat"])
                return False
            time.sleep(PAS_ATTENTE_S)

    def defaire_service(c, res):
        fiche = _trouver_service(lire_services(), res["service"])
        if fiche["actif"] == res["etait_actif"]:
            _marquer(c, res, fiche["actif"], fiche["etat"])
            return
        c.poser("fastpanel_service", res["service"], res["service"], etat="demande", donnees={"id": res["id"], "demande_t": time.time(), "action": "retour"})
        appeler("PUT", "/api/services/%s/%s" % (res["id"], "start" if res["etait_actif"] else "stop"), {})
        fin = time.time() + ATTENTE_SERVICE_S
        while True:
            fiche = _trouver_service(lire_services(), res["service"])
            if fiche["actif"] == res["etait_actif"] or time.time() >= fin:
                _marquer(c, res, fiche["actif"], fiche["etat"])
                return
            time.sleep(PAS_ATTENTE_S)

    # ---- certificats
    def _certificats_panneau():
        return _liste(appeler("GET", "/api/certificates"))

    def _certificat_de(domaine):
        d = nom_hote(domaine)
        for x in _certificats_panneau():
            alt = str(x.get("alternative_name") or "").lower().replace(",", " ").split()
            if nom_hote(str(x.get("common_name") or "")) == d or d in [nom_hote(a) for a in alt]:
                return x
        raise ValueError("aucun certificat du panneau pour %s" % d)

    def ssl_renouveler(c, domaine):
        d = nom_hote(domaine)
        if not hote_valide(d):
            raise ValueError("nom de domaine invalide")
        cert = _certificat_de(d)
        appeler("PUT", "/api/certificates/%s/renew/external" % int(cert["id"]), {}, timeout=90)
        return {"domaine": d, "certificat": int(cert["id"]), "emission_avant": str(cert.get("issued_at") or "")}

    def prouver_ssl(c, res):
        fin = time.time() + ATTENTE_SSL_S
        while True:
            x = next((y for y in _certificats_panneau() if y.get("id") == res["certificat"]), {})
            if str(x.get("issued_at") or "") != res["emission_avant"]:
                c.emettre("fastpanel.certificat_renouvele", objet=("fastpanel", res["domaine"]), donnees={"domaine": res["domaine"], "certificat": res["certificat"]})
                return True
            if time.time() >= fin:
                return False
            time.sleep(PAS_ATTENTE_S)

    def defaire_ssl(c, res):
        return None                                                 # un certificat réémis ne se défait pas : l'ancien reste valable jusqu'à son terme

    # ---- bases
    def _serveurs():
        return _liste(appeler("GET", "/api/databases/servers"))

    def _bases_panneau():
        return _liste(appeler("GET", "/api/databases"))

    def base_creer(c, nom, serveur_id="", utilisateur_id="", nouvel_utilisateur="", proprietaire_id=""):
        n = str(nom or "").strip()
        if not RE_BASE.match(n):
            raise ValueError("nom de base invalide (lettres, chiffres, souligné ; 64 caractères au plus)")
        uid, nu = str(utilisateur_id or "").strip(), str(nouvel_utilisateur or "").strip()
        if not uid.isdigit() and not nu:
            nu = n[:32]
        if nu and not RE_UTILISATEUR_BASE.match(nu):
            raise ValueError("identifiant d'utilisateur invalide (lettres, chiffres, souligné ; 32 au plus)")
        if any(b.get("name") == n for b in _bases_panneau()):
            raise ValueError("la base « %s » existe déjà" % n)
        serveurs = _serveurs()
        sid = str(serveur_id or "").strip()
        if not sid.isdigit():
            sid = str((next((x for x in serveurs if x.get("use_as_default")), serveurs[0] if serveurs else {})).get("id") or "")
        if not sid.isdigit():
            raise ValueError("aucun serveur de bases déclaré dans le panneau")
        pid = str(proprietaire_id or "").strip()
        if not pid.isdigit():
            try:
                comptes = _requete("SELECT id FROM panel_account ORDER BY id")
            except PontErreur:
                comptes = []
            if not comptes:
                raise ValueError("propriétaire inconnu : donnez « proprietaire_id » (la base du panneau n'a pas pu être lue)")
            pid = str(comptes[0][0])
        corps = {"name": n, "server_id": int(sid), "charset": "utf8mb4", "owner_id": int(pid)}
        mdp = ""
        if uid.isdigit():
            existants = _liste(appeler("GET", "/api/databases/servers/%s/users" % sid))
            u = next((x for x in existants if str(x.get("id")) == uid), None)
            if not u:
                raise ValueError("utilisateur de bases inconnu du panneau")
            corps["user_id"], nu = int(uid), u.get("login") or ""
        else:
            existants = _liste(appeler("GET", "/api/databases/servers/%s/users" % sid))
            if any(x.get("login") == nu for x in existants):
                raise ValueError("l'utilisateur « %s » existe déjà : indiquez-le avec « utilisateur_id »" % nu)
            mdp = secrets.token_urlsafe(18)
            corps["user"] = {"login": nu, "password": mdp, "allow_remote_connection": False}
        reponse = appeler("POST", "/api/databases", corps)
        identifiant = _objet(reponse).get("id")
        if identifiant is None:                                    # la création est asynchrone : on retrouve la base par son nom
            identifiant = next((b.get("id") for b in _bases_panneau() if b.get("name") == n), None)
        res = {"id": identifiant, "nom": n, "utilisateur": nu, "serveur": int(sid)}
        if mdp:
            res["mot_de_passe"] = mdp                                # rendu une seule fois, jamais au journal (masque)
        return res

    def prouver_base(c, res):
        for _ in range(int(ATTENTE_SERVICE_S / PAS_ATTENTE_S)):
            if any(b.get("name") == res["nom"] for b in _bases_panneau()):
                return True
            time.sleep(PAS_ATTENTE_S)
        return False

    def defaire_base(c, res):
        identifiant = res.get("id")
        if identifiant is None:
            identifiant = next((b.get("id") for b in _bases_panneau() if b.get("name") == res["nom"]), None)
        if identifiant is None:
            return
        appeler("DELETE", "/api/databases/%s" % int(identifiant))      # cette base-là, que cet acte a créée : son utilisateur part avec elle

    # ---- le pare-feu du panneau : règles, politique, et l'ESSAI (un réglage qui peut fermer se défait seul, sauf si on le garde)
    def regles_parefeu():
        regles = _liste(appeler("GET", "/api/firewall/ports"))
        politique = ""
        try:
            p = appeler("GET", "/api/firewall/policy")
            if isinstance(p, dict):
                politique = str((p.get("data") if isinstance(p.get("data"), dict) else p).get("policy") or "")
        except PontErreur:
            pass
        return regles, politique

    def contexte_ssh(c):
        """Le port SSH (lu par la sécurité, 22 à défaut) et la présence de Tailscale : ce qui décide si refuser SSH laisserait dehors."""
        port = 22
        try:
            e = c.executer_lecture("securite.etat")
            port = int(((e or {}).get("ssh") or {}).get("port") or 22)
        except Exception:
            pass
        return port, os.path.exists("/sys/class/net/tailscale0")

    def essais(c):
        sortie = []
        for o in c.lister(portee=c.TOUT, type="fastpanel_essai"):
            d = o.get("donnees") or {}
            sortie.append({"jeton": o["id"], "quoi": d.get("quoi", ""), "fin": d.get("fin", 0), "reste": max(0, int(d.get("fin", 0) - time.time()))})
        return sortie

    def poser_essai(c, quoi, defaire):
        """Le filet : les appels qui remettent tout comme avant, rejoués à la fin du délai sauf si on garde le réglage."""
        jeton = secrets.token_hex(6)
        fin = time.time() + pf.DELAI_ESSAI_S
        c.poser("fastpanel_essai", jeton, quoi, etat="en_cours", donnees={"quoi": quoi, "fin": fin, "defaire": defaire})
        return {"jeton": jeton, "fin": fin}

    def jouer_defaire(defaire):
        erreurs = []
        for methode, chemin, corps in defaire:
            try:
                appeler(methode, chemin, corps)
            except PontErreur as ex:
                erreurs.append(str(ex))
        return erreurs

    def filet(c):
        """Toutes les dix secondes : un essai échu qu'on n'a pas gardé se défait. Survit à un redémarrage (les essais sont des objets du registre)."""
        for o in c.lister(portee=c.TOUT, type="fastpanel_essai"):
            d = o.get("donnees") or {}
            if o["etat"] == "en_cours" and d.get("fin", 0) <= time.time():
                erreurs = jouer_defaire(d.get("defaire") or [])
                c.retirer("fastpanel_essai", o["id"])
                c.emettre("fastpanel.essai_defait", objet=("fastpanel_essai", o["id"]), donnees={"quoi": d.get("quoi", ""), "erreurs": erreurs})

    def parefeu(c):
        try:
            regles, politique = regles_parefeu()
        except PontErreur as ex:
            return {"ok": False, "erreur": str(ex), "regles": [], "politique": "", "essais": essais(c)}
        return {"ok": True, "erreur": "", "regles": [pf.vers_panneau(r) for r in regles], "politique": politique, "essais": essais(c)}

    def avec_filet(c, quoi, defaire, ferme):
        """Si le réglage peut fermer, le filet est posé (ou le réglage est défait aussitôt) : ce qui peut fermer ne reste jamais sans retour."""
        if not ferme:
            return {}
        try:
            return {"essai": poser_essai(c, quoi, defaire)}
        except Exception as ex:
            jouer_defaire(defaire)
            raise ValueError("filet de deux minutes impossible (%s) : le réglage a été défait aussitôt" % ex)

    def regle_poser(c, nom="", ports="", proto="TCP", sens="INPUT", politique="", sources="", id=0):
        corps, err = pf.valider({"nom": nom, "ports": ports, "proto": proto, "sens": sens, "politique": politique, "sources": sources})
        if err:
            raise ValueError(err)
        regles, pol_globale = regles_parefeu()
        rid = int(id or 0)
        avant = next((x for x in regles if int(x.get("id") or 0) == rid), None) if rid else None
        if rid and not avant:
            raise ValueError("règle introuvable (déjà retirée ?)")
        ssh, tailscale = contexte_ssh(c)
        refus, ferme = pf.risque(corps, regles, pol_globale, ssh, tailscale)
        if refus:
            raise ValueError(refus)
        if rid:
            r = appeler("PUT", "/api/firewall/ports/%d" % rid, {"port": dict(corps, id=rid)})
        else:
            r = appeler("PUT", "/api/firewall/ports", {"port": corps})
        corps_rendu = r.get("data") if isinstance(r, dict) and isinstance(r.get("data"), dict) else (r if isinstance(r, dict) else {})
        nid = int(corps_rendu.get("id") or rid or 0)
        defaire = [["PUT", "/api/firewall/ports/%d" % rid, {"port": dict(pf.corps_de(avant), id=rid)}]] if avant else [["DELETE", "/api/firewall/ports/%d" % nid, None]]
        sortie = {"id": nid, "nom": corps["name"], "defaire": defaire, "avait": bool(avant)}
        sortie.update(avec_filet(c, "%s : %s" % ("règle modifiée" if rid else "règle posée", corps["name"]), defaire, ferme or bool(avant and avant.get("policy") != "ACCEPT")))
        return sortie

    def prouver_regle(c, res):
        return any(int(x.get("id") or 0) == int(res["id"]) and x.get("name") == res["nom"] for x in regles_parefeu()[0])

    def defaire_regle(c, res):
        jouer_defaire(res["defaire"])
        if res.get("essai"):
            c.retirer("fastpanel_essai", res["essai"]["jeton"])

    def regle_retirer(c, id=0):
        rid = int(id or 0)
        regles, pol_globale = regles_parefeu()
        avant = next((x for x in regles if int(x.get("id") or 0) == rid), None)
        if not avant:
            raise ValueError("règle introuvable")
        _, ferme = pf.risque(None, regles, pol_globale, retire=rid)
        appeler("DELETE", "/api/firewall/ports/%d" % rid)
        defaire = [["PUT", "/api/firewall/ports", {"port": pf.corps_de(avant)}]]
        sortie = {"id": rid, "nom": avant.get("name"), "defaire": defaire}
        sortie.update(avec_filet(c, "règle retirée : %s" % avant.get("name"), defaire, ferme))
        return sortie

    def prouver_retiree(c, res):
        return not any(int(x.get("id") or 0) == int(res["id"]) for x in regles_parefeu()[0])

    def parefeu_politique(c, politique=""):
        pol = str(politique or "").upper()
        regles, avant = regles_parefeu()
        ssh, tailscale = contexte_ssh(c)
        refus = pf.politique_refus(pol, regles, ssh, tailscale)
        if refus:
            raise ValueError(refus)
        appeler("PUT", "/api/firewall/policy", {"policy": pol})
        defaire = [["PUT", "/api/firewall/policy", {"policy": avant or "ACCEPT"}]]
        sortie = {"politique": pol, "avant": avant, "defaire": defaire}
        sortie.update(avec_filet(c, "politique : refuser par défaut", defaire, pol == "DROP" and avant != "DROP"))
        return sortie

    def prouver_politique(c, res):
        return regles_parefeu()[1] == res["politique"]

    def trancher(c, jeton="", garder=True):
        o = c.lire("fastpanel_essai", str(jeton), portee=c.TOUT)
        if not o:
            raise ValueError("cet essai est déjà tranché (ou s'est défait tout seul)")
        erreurs = [] if garder else jouer_defaire((o.get("donnees") or {}).get("defaire") or [])
        c.retirer("fastpanel_essai", str(jeton))
        return {"jeton": str(jeton), "garde": bool(garder), "erreurs": erreurs}

    def prouver_tranche(c, res):
        return c.lire("fastpanel_essai", res["jeton"], portee=c.TOUT) is None

    def defaire_tranche(c, res):
        raise ValueError("garder ou défaire un essai ne se rejoue pas : refaire le réglage")

    # ---- sauvegardes
    def stockage_local_creer(c, nom, chemin):
        n, ch = str(nom or "").strip() or "local", str(chemin or "").strip()
        if not RE_NOM.match(n):
            raise ValueError("nom de stockage invalide (2 à 64 caractères)")
        if not RE_CHEMIN.match(ch) or ".." in ch:
            raise ValueError("chemin invalide : un dossier absolu du serveur, sans « .. »")
        reponse = appeler("POST", "/api/backups/accounts", {"name": n, "type": "local", "path": ch})
        identifiant = _objet(reponse).get("id")
        if identifiant is None:
            identifiant = next((x.get("id") for x in _liste(appeler("GET", "/api/backups/accounts")) if x.get("name") == n), None)
        return {"id": identifiant, "nom": n, "chemin": ch}

    def prouver_stockage(c, res):
        return any(x.get("name") == res["nom"] and (x.get("path") in (None, res["chemin"])) for x in _liste(appeler("GET", "/api/backups/accounts")))

    def defaire_stockage(c, res):
        if res.get("id") is not None:
            appeler("DELETE", "/api/backups/accounts/%s" % int(res["id"]))

    def plan_creer(c, nom, stockage="", garder=7, heure="4", jours="*"):
        n = str(nom or "").strip()
        if not RE_NOM.match(n):
            raise ValueError("nom de plan invalide (2 à 64 caractères)")
        try:
            garder = max(1, min(60, int(garder or 7)))
        except (TypeError, ValueError):
            garder = 7
        comptes = _liste(appeler("GET", "/api/backups/accounts"))
        if not comptes:
            raise ValueError("aucun stockage de sauvegarde n'est déclaré dans le panneau : un plan a besoin d'un endroit où écrire (stockage_local_creer)")
        compte = next((x for x in comptes if str(x.get("id")) == str(stockage)), None) if stockage else comptes[0]
        if compte is None:
            raise ValueError("stockage %s inconnu" % stockage)
        corps = {"name": n, "account": compte.get("id"), "compressor_name": "gzip", "compressor_lvl": "best_speed", "full_copy_limit": garder, "partial_copy_limit": garder,
                 "minute": "0", "hour": str(heure), "day_of_month": "*", "month": "*", "day_of_week": str(jours),
                 "exclude_email": False, "exclude_logs": False, "excluded_users": [], "excluded_databases": []}
        try:
            reponse = appeler("POST", "/api/v2/backup/plans/full", corps)
        except PontErreur:
            corps["user_id"] = compte.get("owner_id") or (compte.get("owner") or {}).get("id") or 1
            reponse = appeler("POST", "/api/v2/backup/plans", corps)
        identifiant = _objet(reponse).get("id")
        if identifiant is None:
            identifiant = next((x.get("id") for x in plans(c) if x.get("name") == n), None)
        return {"id": identifiant, "nom": n, "stockage": compte.get("name") or compte.get("id"), "garder": garder}

    def prouver_plan(c, res):
        return any(x.get("name") == res["nom"] for x in plans(c))

    def defaire_plan(c, res):
        if res.get("id") is not None:
            appeler("DELETE", "/api/v2/backup/plans/%s" % int(res["id"]))

    # ---- inscription
    c = ctx
    c.moteur("releve", releve)
    c.moteur("filet", filet)
    c.detecteur("injoignable", lambda x: constat_etat(x, "injoignable", "Le panneau FastPanel ne répond plus"))
    c.detecteur("acces_refuse", lambda x: constat_etat(x, "refuse", "Le panneau FastPanel refuse les identifiants de Cassandra"))
    c.detecteur("service_tombe", det_services)
    c.detecteur("certificat_proche", det_certificats)
    c.detecteur("sauvegarde_manquante", det_sauvegardes)
    c.detecteur("php_fin_support", det_php)
    for cid, f in (("sante", sante), ("resume", resume), ("utilisateurs", utilisateurs), ("sites", sites), ("bases", bases), ("ftp", ftp), ("mail", mail), ("dns", dns),
                   ("sauvegardes", sauvegardes), ("plans", plans), ("stockages", stockages), ("services", services), ("certificats", certificats),
                   ("ssl_sonder", ssl_sonder), ("php", php), ("audit", audit), ("parefeu", parefeu)):
        c.implementer(cid, f)
    c.implementer("service_relancer", relancer, prouver_service, defaire_service, simuler=lambda x, service="", action="restart", **_: "ferait « %s » sur le service %s" % (action, service))
    c.implementer("service_arreter", arreter, prouver_service, defaire_service, simuler=lambda x, service="", **_: "arrêterait le service %s (il serait relancé au retour arrière)" % service)
    c.implementer("ssl_renouveler", ssl_renouveler, prouver_ssl, defaire_ssl, simuler=lambda x, domaine="", **_: "demanderait un nouveau certificat pour %s à l'autorité (quota limité)" % domaine)
    c.implementer("parefeu_regle_poser", regle_poser, prouver_regle, defaire_regle, simuler=lambda x, nom="", ports="", **_: "poserait la règle « %s » (ports %s) au pare-feu du panneau" % (nom, ports))
    c.implementer("parefeu_regle_retirer", regle_retirer, prouver_retiree, defaire_regle, simuler=lambda x, id=0, **_: "retirerait la règle %s du pare-feu du panneau" % id)
    c.implementer("parefeu_politique", parefeu_politique, prouver_politique, defaire_regle, simuler=lambda x, politique="", **_: "passerait la politique du pare-feu à %s" % politique)
    c.implementer("parefeu_trancher", trancher, prouver_tranche, defaire_tranche)
    c.implementer("base_creer", base_creer, prouver_base, defaire_base, simuler=lambda x, nom="", **_: "créerait la base %s avec son utilisateur" % nom)
    c.implementer("stockage_local_creer", stockage_local_creer, prouver_stockage, defaire_stockage, simuler=lambda x, nom="", chemin="", **_: "déclarerait le dossier %s comme stockage « %s »" % (chemin, nom))
    c.implementer("plan_creer", plan_creer, prouver_plan, defaire_plan, simuler=lambda x, nom="", **_: "créerait le plan de sauvegarde « %s »" % nom)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : PontErreur, _reglage, _delai, _adresses, configure, _ouvrir, _trouver_jeton, _login_sur …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
