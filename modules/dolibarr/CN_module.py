# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le pont Dolibarr
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dolibarr
# ZONE       : CN
# VERSION CN : 0.4.0  #6b7ee9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le pont Dolibarr : Cassandra pilote une instance Dolibarr par son API REST.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=6b7ee9 ▼▼▼
"""Le pont Dolibarr : Cassandra pilote une instance Dolibarr par son API REST.

Dolibarr garde son PHP et sa base ; il fait son métier. Ce module lit (GET, par `appeler`) et écrit (POST / PUT / DELETE, par `ecrire`, la seule porte
d'écriture). Toute écriture est une capacité déclarée avec son périmètre, sa PREUVE (relire ce qui a été écrit) et son RETOUR ARRIÈRE (restaurer l'état
d'avant, ou supprimer ce que l'acte vient de créer, et seulement cela). Trois classes :
  - réversible : créer / modifier un tiers, un contact, un produit, un projet, créer un brouillon de facture, de devis ou de commande ;
  - supprimer : l'objet est d'abord copié EN ENTIER dans la corbeille ; on peut le recréer (`restaurer`), seul l'identifiant change. Dolibarr refuse de
    supprimer ce qui est référencé ailleurs (un tiers qui a des factures) : cette garde est la sienne ;
  - légal : valider une facture (elle consomme un numéro).
Le plafond d'autonomie de chaque capacité est un CHOIX DE L'ADMINISTRATEUR (`python CN_main.py palier`) : par défaut Cassandra raconte ce qu'elle ferait ;
un humain agit en voie parallèle, ou monte le palier.
Il en tire un objet du registre (l'instance : version, comptes, impayés), des constats (injoignable, accès refusé) et des lectures bornées.

Réglage : config/dolibarr.conf, des lignes « cle = valeur » :
    url          = http://100.64.0.20:8081/api/index.php     l'adresse de l'API (en production : l'adresse privée de la machine Dolibarr)
    hote         = www.cassandra.center                          (facultatif) l'en-tête Host, quand l'adresse est une IP
    fichier_cle  = dolibarr.key                                   (facultatif) où est la clé, relativement à config/
    delai        = 15                                             (facultatif) secondes
La clé elle-même n'est JAMAIS dans la configuration, ne se logue pas, ne figure dans aucun événement ni aucun objet.
"""
import calendar
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Les types d'objets lisibles, et les champs qu'on peut demander. Aucune coordonnée personnelle (e-mail, téléphone, adresse) dans cette version.
OBJETS = {"tiers": "/thirdparties", "factures": "/invoices", "devis": "/proposals", "commandes": "/orders",
          "projets": "/projects", "produits": "/products", "contacts": "/contacts"}
CHAMPS_OK = {"id", "ref", "name", "nom", "firstname", "label", "statut", "status", "total_ht", "total_ttc", "paye", "date", "date_creation",
             "date_lim_reglement", "date_validation", "fk_soc", "socid", "client", "fournisseur", "type", "price", "price_ttc", "datec", "tms"}
CHAMPS_DEFAUT = {"tiers": "id,name,client,fournisseur", "factures": "id,ref,socid,total_ttc,paye,date,date_lim_reglement",
                 "devis": "id,ref,socid,total_ttc,statut,date", "commandes": "id,ref,socid,total_ttc,statut,date",
                 "projets": "id,ref,statut,date_creation", "produits": "id,ref,label,price", "contacts": "id,socid,firstname,name"}
LIMITE_MAX = 100
PAGE = 1000
_ID = re.compile(r"^[0-9]{1,12}$")
_CHAMP = re.compile(r"^[a-z_]{1,40}$")


# Ce qu'on peut ÉCRIRE : par objet, la route, les champs permis (rien d'autre n'est transmis), et comment on le défait.
ECRIVABLES = {
    "tiers": {"chemin": "/thirdparties", "champs": {"name", "name_alias", "client", "fournisseur", "email", "phone", "address", "zip", "town",
                                                       "country_id", "url", "note_private", "note_public", "tva_intra", "status"}},
    "contacts": {"chemin": "/contacts", "champs": {"socid", "firstname", "lastname", "email", "phone_pro", "phone_mobile", "poste", "address", "zip",
                                                      "town", "note_private"}},
    "produits": {"chemin": "/products", "champs": {"ref", "label", "description", "price", "price_base_type", "tva_tx", "type", "status",
                                                      "status_buy"}},
    "projets": {"chemin": "/projects", "champs": {"title", "description", "socid", "date_start", "date_end", "public"}},
}
DOCUMENTS = {"factures": "/invoices", "devis": "/proposals", "commandes": "/orders"}     # créés en brouillon, jamais validés ici
CHAMPS_DOC = {"socid", "date", "note_private", "note_public", "lines"}
CHAMPS_LIGNE = {"desc", "qty", "subprice", "tva_tx", "fk_product", "product_type", "remise_percent"}
MAX_CORPS = 16384
AGENT = "Cassandra-Dolibarr/0.4"      # une identité franche : un pare-feu applicatif (Cloudflare) refuse l'agent par défaut de Python
MODES_PAIEMENT = ("VIR", "CHQ", "LIQ", "CB", "PRE")      # les codes du dictionnaire « modes de règlement » de Dolibarr
# Les domaines de l'API REST de Dolibarr (noyau) : la requête libre ne sort pas de cette liste, une faute de frappe est refusée avant d'être envoyée.
DOMAINES = ("accountancy", "agendaevents", "bankaccounts", "categories", "contacts", "contracts", "documents", "donations", "emailtemplates",
            "eventattendees", "expensereports", "holidays", "interventions", "invoices", "knowledgemanagement", "mailings", "members", "memberstypes",
            "objectlinks", "orders", "paiements", "partnerships", "productlots", "products", "projects", "proposals", "recruitments", "salaries",
            "setup", "shipments", "status", "stockmovements", "subscriptions", "supplierinvoices", "supplierorders", "supplierproposals", "tasks",
            "thirdparties", "tickets", "users", "warehouses")
_CHEMIN_LIBRE = re.compile(r"^/[a-z]{3,30}(/[A-Za-z0-9_.@-]{1,60}){0,4}$")
_REQUETE = re.compile(r"^[A-Za-z0-9_.,=&%+:*()\[\]-]{0,400}$")
_SECRET = re.compile(r"(pass|api_key|apikey|token|secret|signature|private_key|cle_)", re.I)
# Les pièces dont on lit ou produit le PDF : objet -> (chemin de l'objet, « modulepart » de Dolibarr). Le PDF est celui que Dolibarr a produit : Cassandra le lit, elle ne le recompose pas.
PIECES = {"devis": ("/proposals", "propal"), "factures": ("/invoices", "facture"), "dons": ("/donations", "donation")}
MAX_PDF = 8 * 1024 * 1024
MAX_LIBRE = 100             # lignes rendues par une lecture libre
MAX_LIGNES = 50


class PontErreur(Exception):
    """Une erreur du pont, au message sûr : jamais l'en-tête de la requête, donc jamais la clé."""

    def __init__(self, message, code=None, genre="erreur"):
        super().__init__(message)
        self.code, self.genre = code, genre


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


# ------------------------------------------------------------------ configuration
def _dossier_config():
    return os.environ.get("CASSANDRA_CONFIG") or ""


_CTX = None          # le contexte du module, posé au branchement : les réglages l'emportent sur le fichier


def _reglages():
    """Les réglages posés (non vides), ou {} : le module des réglages est peut-être absent."""
    if _CTX is None:
        return {}
    try:
        r = {"url": str(_CTX.reglage("url", "") or ""), "hote": str(_CTX.reglage("hote", "") or "")}
        d = int(_CTX.reglage("delai", "") or 0)
        if d:
            r["delai"] = str(d)
        return {k: v for k, v in r.items() if v}
    except Exception:
        return {}


def lire_conf():
    """La configuration, relue à chaque passe (un changement s'applique sans redémarrer). None si le pont n'est pas configuré.
    Les réglages (module « réglages ») l'emportent sur config/dolibarr.conf, qui reste le repli. Elle porte aussi le compte courant et ses clés (jamais loguées)."""
    f = os.path.join(_dossier_config(), "dolibarr.conf")
    conf = {"delai": "15"}
    if os.path.isfile(f):
        with open(f, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.split("#", 1)[0].strip()
                if "=" in ligne:
                    k, v = ligne.split("=", 1)
                    conf[k.strip()] = v.strip()
    conf.update(_reglages())
    if not conf.get("url", "").startswith(("http://", "https://")):
        return None
    conf["fichier_cle"] = os.path.join(_dossier_config(), conf.get("fichier_cle", "dolibarr.key"))
    conf["compte"] = _compte_courant()
    conf["cle_perso"] = _reglage_texte("cle_api") if conf["compte"] else ""
    conf["cle_mandat"] = _reglage_texte("cle_mandat")
    conf["mandat_pour_tous"] = _reglage_texte("mandat_pour_tous").lower() in ("1", "true", "vrai", "oui")
    conf["societe_attendue"] = _reglage_texte("societe_attendue")
    return conf


def _compte_courant():
    """Le compte au nom duquel la capacité en cours s'exécute ('' : un moteur, le système). PAR FIL : jamais un global."""
    try:
        return str(_CTX.compte or "") if _CTX is not None else ""
    except Exception:
        return ""


def _reglage_texte(nom):
    if _CTX is None:
        return ""
    try:
        return str(_CTX.reglage(nom) or "").strip()
    except Exception:
        return ""


def _cle(conf, ecriture=False):
    """LA clé d'API de ce geste. Trois sources, dans cet ordre :
      1. la clé PROPRE du compte (réglage « cle_api », secret de portée compte) : Dolibarr agit alors sous le nom de son utilisateur, avec ses droits ;
      2. la clé de MANDAT (réglage « cle_mandat ») ou le fichier de clé : le système, pour les moteurs et les lectures d'un compte sans clé ;
    Un compte SANS clé propre ne peut pas écrire (sauf le réglage « mandat_pour_tous ») : il ne tombe jamais, par accident, sur la clé d'un autre."""
    if conf.get("compte"):
        if conf.get("cle_perso"):
            return conf["cle_perso"]
        if ecriture and not conf.get("mandat_pour_tous"):
            raise PontErreur("la clé Dolibarr de ce compte n'est pas renseignée (Réglages › Dolibarr › Ma clé) : sans elle, rien ne s'écrit dans Dolibarr sous son nom",
                             genre="pas_de_cle")
    if conf.get("cle_mandat"):
        return conf["cle_mandat"]
    try:
        with open(conf["fichier_cle"], encoding="utf-8") as fh:
            cle = fh.read().strip()
    except OSError:
        raise PontErreur("le fichier de clé est illisible", genre="non_configure")
    if not cle:
        raise PontErreur("le fichier de clé est vide", genre="non_configure")
    return cle


_SOCIETES = {}          # (adresse, empreinte de clé) -> (horodatage, nom de la société lue) : la société ne change pas à chaque geste


def _garde_societe(conf):
    """Avant d'ÉCRIRE : la société que la clé voit est-elle celle qu'on attend (réglage « societe_attendue ») ? Une instance qui garde plusieurs entités peut
    donner une clé qui écrit dans la mauvaise comptabilité : on le refuse avant, pas après."""
    voulu = (conf.get("societe_attendue") or "").strip().lower()
    if not voulu:
        return
    import hashlib
    cle = _cle(conf, ecriture=True)
    k = (conf["url"], hashlib.sha256(cle.encode()).hexdigest()[:12])
    t, nom = _SOCIETES.get(k, (0, ""))
    if time.time() - t > 300:
        en_tetes = {"DOLAPIKEY": cle, "Accept": "application/json", "User-Agent": AGENT}
        if conf.get("hote"):
            en_tetes["Host"] = conf["hote"]
        req = urllib.request.Request(conf["url"].rstrip("/") + "/setup/company", headers=en_tetes, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=float(conf.get("delai", 15))) as r:
                brut = r.read()
            if brut[:2] == b"\x1f\x8b":
                brut = gzip.decompress(brut)
            nom = str((json.loads(brut.decode("utf-8", "replace")) or {}).get("name") or "")
        except Exception:
            raise PontErreur("impossible de lire la société de Dolibarr : rien n'est écrit tant qu'on ne sait pas dans quelle comptabilité", genre="injoignable")
        _SOCIETES[k] = (time.time(), nom)
    if nom.strip().lower() != voulu:
        raise PontErreur("la clé voit la société « %s », pas « %s » : rien n'est écrit" % (nom, conf["societe_attendue"]), genre="mauvaise_societe")


# ------------------------------------------------------------------ le client : un GET, rien d'autre
def appeler(conf, chemin, parametres=None):
    """GET sur l'API. Rend le JSON décodé. Aucune autre méthode n'existe dans ce module."""
    url = conf["url"].rstrip("/") + chemin
    if parametres:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(parametres)
    en_tetes = {"DOLAPIKEY": _cle(conf), "Accept": "application/json", "User-Agent": AGENT}
    if conf.get("hote"):
        en_tetes["Host"] = conf["hote"]
    req = urllib.request.Request(url, headers=en_tetes, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=float(conf.get("delai", 15))) as r:
            brut = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PontErreur("Dolibarr refuse l'accès (HTTP %d)" % e.code, e.code, "acces_refuse")
        raise PontErreur("Dolibarr répond HTTP %d" % e.code, e.code)
    except (urllib.error.URLError, OSError) as e:
        raise PontErreur("Dolibarr est injoignable (%s)" % type(getattr(e, "reason", e)).__name__, genre="injoignable")
    if brut[:2] == b"\x1f\x8b":                       # certains serveurs compressent sans qu'on l'ait demandé
        brut = gzip.decompress(brut)
    try:
        return json.loads(brut.decode("utf-8", "replace"))
    except ValueError:
        raise PontErreur("Dolibarr a répondu autre chose que du JSON")


def ecrire(conf, methode, chemin, corps=None):
    """LA porte d'écriture : POST, PUT ou DELETE, jamais autre chose. Rend le JSON décodé (ou None). Utilisée seulement par les capacités déclarées à
    risque moyen ou élevé, qui ont toutes leur preuve et leur retour arrière."""
    if methode not in ("POST", "PUT", "DELETE"):
        raise PontErreur("méthode refusée : %s" % methode)
    donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8") if corps is not None else None
    if donnees is not None and len(donnees) > MAX_CORPS:
        raise ValueError("le corps de la requête dépasse %d octets" % MAX_CORPS)
    _garde_societe(conf)
    en_tetes = {"DOLAPIKEY": _cle(conf, ecriture=True), "Accept": "application/json", "Content-Type": "application/json", "User-Agent": AGENT}
    if conf.get("hote"):
        en_tetes["Host"] = conf["hote"]
    req = urllib.request.Request(conf["url"].rstrip("/") + chemin, data=donnees, headers=en_tetes, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=float(conf.get("delai", 15))) as r:
            brut = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PontErreur("Dolibarr refuse l'accès (HTTP %d)" % e.code, e.code, "acces_refuse")
        raise PontErreur("Dolibarr répond HTTP %d" % e.code, e.code)
    except (urllib.error.URLError, OSError) as e:
        raise PontErreur("Dolibarr est injoignable (%s)" % type(getattr(e, "reason", e)).__name__, genre="injoignable")
    if brut[:2] == b"\x1f\x8b":
        brut = gzip.decompress(brut)
    texte = brut.decode("utf-8", "replace").strip()
    if not texte:
        return None
    try:
        return json.loads(texte)
    except ValueError:
        return texte


def _liste_complete(conf, objet, parametres=None):
    """Toutes les lignes (champ id seulement), page par page : l'API ne donne pas de total."""
    sortie, page = [], 0
    while True:
        p = {"limit": PAGE, "page": page, "properties": "id", "sortfield": "t.rowid"}
        p.update(parametres or {})
        try:
            lot = appeler(conf, OBJETS[objet], p)
        except PontErreur as ex:
            if ex.code == 404:                          # « aucun enregistrement » : Dolibarr répond 404
                break
            raise
        if not isinstance(lot, list):
            break
        sortie += lot
        if len(lot) < PAGE:
            break
        page += 1
        if page > 200:
            break
    return sortie


def _compter(conf, objet):
    return len(_liste_complete(conf, objet))


def _date(v):
    """Dolibarr rend ses dates en horodatage Unix (« 1656712800 ») ; on les montre en jour (AAAA-MM-JJ). Une date déjà lisible reste telle quelle."""
    t = str(v)
    if t.isdigit():
        # Dolibarr range « minuit dans son fuseau » : en UTC cela tombe la veille au soir. +12 h donne le bon jour, quel que soit le fuseau.
        return time.strftime("%Y-%m-%d", time.gmtime(int(t) + 43200))
    return t


def _impayees(conf):
    try:
        lot = appeler(conf, OBJETS["factures"], {"limit": PAGE, "status": "unpaid", "properties": "id,total_ttc,date_lim_reglement"})
    except PontErreur as ex:
        if ex.code == 404:
            return {"n": 0, "total_ttc": 0.0, "plus_ancienne": ""}
        raise
    lot = lot if isinstance(lot, list) else []
    echeances = sorted(_date(x.get("date_lim_reglement")) for x in lot if x.get("date_lim_reglement"))
    return {"n": len(lot), "total_ttc": round(sum(float(x.get("total_ttc") or 0) for x in lot), 2), "plus_ancienne": echeances[0] if echeances else ""}


def _egaux(a, b):
    """Dolibarr rend souvent des nombres en texte (« 1 » pour 1) : on compare ce qui compte. Le calcul est un POINT D'ÉVOLUTION : points/EC_egaux.py."""
    return _appeler_point("egaux", {"a": a, "b": b})["valeur"]


def _completer(objet, corps):
    """Ce que Dolibarr 24 exige à la CRÉATION et que l'appelant n'a pas à connaître : le code client ou fournisseur d'un tiers et la référence d'un projet (« auto » : Dolibarr numérote). Vu sur le vrai Dolibarr : sans cela, HTTP 500 (ErrorCustomerCodeRequired) ou 400 (ref field missing). Le calcul est un POINT D'ÉVOLUTION : points/EC_completer.py."""
    return _appeler_point("completer", {"objet": objet, "corps": corps})["valeur"]


def _verifier_champs(champs, permis, ce_quon_fait):
    if not isinstance(champs, dict) or not champs:
        raise ValueError("champs : un dictionnaire non vide")
    for k, v in champs.items():
        if k not in permis:
            raise ValueError("champ %r refusé pour %s (permis : %s)" % (k, ce_quon_fait, ", ".join(sorted(permis))))
        if not isinstance(v, (str, int, float, type(None))) or isinstance(v, bool):
            raise ValueError("champ %r : un texte ou un nombre" % k)
        if isinstance(v, str) and len(v) > 4000:
            raise ValueError("champ %r : 4000 caractères au plus" % k)


def _champs(objet, champs):
    if not champs:
        return CHAMPS_DEFAUT[objet]
    liste = [c.strip() for c in str(champs).split(",") if c.strip()]
    if not liste or any(not _CHAMP.match(c) or c not in CHAMPS_OK for c in liste):
        raise ValueError("champs permis : " + ", ".join(sorted(CHAMPS_OK)))
    return ",".join(liste)


# ------------------------------------------------------------------ le module
def brancher(ctx):
    global _point
    _point = ctx.point
    global _CTX
    _CTX = ctx
    etat = {"comptes_t": 0.0}
    INSTANCE = ("dolibarr", "principal")

    def instance(ctx):
        return ctx.lire(*INSTANCE, portee=ctx.TOUT)

    def releve(ctx):
        conf = lire_conf()
        precedent = instance(ctx)
        if conf is None:
            ctx.poser(*INSTANCE, "Dolibarr", etat="non_configure", donnees={"erreur": "config/dolibarr.conf absent ou sans url"})
            return
        try:
            statut = appeler(conf, "/status")
            donnees = dict(precedent["donnees"] if precedent and precedent["etat"] == "ok" else {})
            donnees["version"] = (statut.get("success") or statut).get("dolibarr_version", "?") if isinstance(statut, dict) else "?"
            donnees["verrouille"] = str((statut.get("success") or statut).get("access_locked", "0")) != "0" if isinstance(statut, dict) else False
            if time.time() - etat["comptes_t"] >= 900 or "comptes" not in donnees:
                donnees["comptes"] = {o: _compter(conf, o) for o in ("tiers", "factures", "devis", "projets", "produits")}
                donnees["impayees"] = _impayees(conf)
                donnees["modules"] = len(appeler(conf, "/setup/modules") or [])
                etat["comptes_t"] = time.time()
            donnees["erreur"] = ""
            if precedent and precedent["etat"] in ("injoignable", "refuse"):
                ctx.emettre("dolibarr.reprise", objet=INSTANCE, donnees={"version": donnees["version"]})
            ctx.poser(*INSTANCE, "Dolibarr", etat="ok", donnees=donnees)
        except PontErreur as ex:
            nouvel = "refuse" if ex.genre == "acces_refuse" else ("non_configure" if ex.genre == "non_configure" else "injoignable")
            if not precedent or precedent["etat"] != nouvel:
                if nouvel == "refuse":
                    ctx.emettre("dolibarr.acces_refuse", objet=INSTANCE, donnees={"erreur": str(ex)})
                elif nouvel == "injoignable":
                    ctx.emettre("dolibarr.injoignable", objet=INSTANCE, donnees={"erreur": str(ex)})
            ctx.poser(*INSTANCE, "Dolibarr", etat=nouvel, donnees=dict(precedent["donnees"] if precedent else {}, erreur=str(ex)))

    def constat_si(ctx, etat_voulu, titre):
        i = instance(ctx)
        if i and i["etat"] == etat_voulu:
            return [{"objet": INSTANCE, "titre": titre, "detail": i["donnees"].get("erreur", "")}]
        return []

    # ------------------------------------------------------------------ lectures
    def resume(ctx):
        i = instance(ctx)
        return None if not i else dict(i["donnees"], etat=i["etat"])

    def statut(ctx):
        conf = lire_conf()
        if conf is None:
            raise ValueError("le pont n'est pas configuré (config/dolibarr.conf)")
        t0 = time.time()
        s = appeler(conf, "/status")
        s = s.get("success", s) if isinstance(s, dict) else {}
        return {"version": s.get("dolibarr_version", "?"), "latence_ms": int((time.time() - t0) * 1000), "verrouille": str(s.get("access_locked", "0")) != "0"}

    def modules(ctx):
        conf = lire_conf()
        if conf is None:
            raise ValueError("le pont n'est pas configuré (config/dolibarr.conf)")
        return sorted(appeler(conf, "/setup/modules") or [])

    def _conf_et_objet(objet):
        if objet not in OBJETS:
            raise ValueError("objet inconnu : %r (permis : %s)" % (objet, ", ".join(sorted(OBJETS))))
        conf = lire_conf()
        if conf is None:
            raise ValueError("le pont n'est pas configuré (config/dolibarr.conf)")
        return conf

    def compter(ctx, objet):
        conf = _conf_et_objet(objet)
        return {"objet": objet, "nombre": _compter(conf, objet)}

    def lister(ctx, objet, limite=20, page=0, champs="", etat=""):
        conf = _conf_et_objet(objet)
        if not isinstance(limite, int) or isinstance(limite, bool) or not 1 <= limite <= LIMITE_MAX:
            raise ValueError("limite : un entier de 1 à %d" % LIMITE_MAX)
        if not isinstance(page, int) or isinstance(page, bool) or not 0 <= page <= 10000:
            raise ValueError("page : un entier de 0 à 10000")
        p = {"limit": limite, "page": page, "properties": _champs(objet, champs), "sortfield": "t.rowid", "sortorder": "DESC"}
        if etat:
            if objet != "factures" or etat != "impayees":
                raise ValueError("etat : seulement « impayees », pour les factures")
            p["status"] = "unpaid"
        try:
            return {"objet": objet, "lignes": appeler(conf, OBJETS[objet], p)}
        except PontErreur as ex:
            if ex.code == 404:
                return {"objet": objet, "lignes": []}
            raise

    def lire(ctx, objet, id, champs=""):
        conf = _conf_et_objet(objet)
        if not _ID.match(str(id)):
            raise ValueError("id : un nombre")
        r = appeler(conf, "%s/%s" % (OBJETS[objet], id), {"properties": _champs(objet, champs)})
        return {"objet": objet, "ligne": r}

    def impayees(ctx):
        conf = lire_conf()
        if conf is None:
            raise ValueError("le pont n'est pas configuré (config/dolibarr.conf)")
        return _impayees(conf)

    # ------------------------------------------------------------------ écritures : preuve et retour arrière, toujours
    def _conf():
        conf = lire_conf()
        if conf is None:
            raise ValueError("le pont n'est pas configuré (config/dolibarr.conf)")
        return conf

    def _lire_un(conf, chemin, id):
        return appeler(conf, "%s/%s" % (chemin, id))

    def creer(ctx, objet, champs):
        if objet not in ECRIVABLES:
            raise ValueError("objet inconnu : %r (permis : %s)" % (objet, ", ".join(sorted(ECRIVABLES))))
        _verifier_champs(champs, ECRIVABLES[objet]["champs"], objet)
        conf = _conf()
        nouvel = ecrire(conf, "POST", ECRIVABLES[objet]["chemin"], _completer(objet, champs))
        if not isinstance(nouvel, int) and not (isinstance(nouvel, str) and _ID.match(nouvel)):
            raise PontErreur("Dolibarr n'a pas rendu l'identifiant de l'objet créé")
        return {"objet": objet, "id": int(nouvel), "champs": champs, "cree": True}

    def modifier(ctx, objet, id, champs):
        if objet not in ECRIVABLES:
            raise ValueError("objet inconnu : %r (permis : %s)" % (objet, ", ".join(sorted(ECRIVABLES))))
        if not _ID.match(str(id)):
            raise ValueError("id : un nombre")
        _verifier_champs(champs, ECRIVABLES[objet]["champs"], objet)
        conf = _conf()
        courant = _lire_un(conf, ECRIVABLES[objet]["chemin"], id)
        if not isinstance(courant, dict):
            raise PontErreur("l'objet %s %s est introuvable" % (objet, id))
        avant = {k: courant.get(k) for k in champs}
        ecrire(conf, "PUT", "%s/%s" % (ECRIVABLES[objet]["chemin"], id), champs)
        return {"objet": objet, "id": int(id), "avant": avant, "apres": champs, "cree": False}

    def prouver_objet(ctx, res):
        conf = _conf()
        o = _lire_un(conf, ECRIVABLES[res["objet"]]["chemin"], res["id"])
        attendu = res["champs"] if res["cree"] else res["apres"]
        return isinstance(o, dict) and all(_egaux(o.get(k), v) for k, v in attendu.items())

    def defaire_objet(ctx, res):
        conf = _conf()
        chemin = "%s/%s" % (ECRIVABLES[res["objet"]]["chemin"], res["id"])
        if res["cree"]:
            ecrire(conf, "DELETE", chemin)          # ce que CET acte vient de créer, et rien d'autre
        else:
            ecrire(conf, "PUT", chemin, res["avant"])

    def _lignes(lignes):
        if not isinstance(lignes, list) or not lignes or len(lignes) > MAX_LIGNES:
            raise ValueError("lignes : une liste de 1 à %d lignes" % MAX_LIGNES)
        propres = []
        for l in lignes:
            _verifier_champs(l, CHAMPS_LIGNE, "une ligne")
            propres.append(l)
        return propres

    def creer_brouillon(ctx, objet, socid, lignes, date=None, note=""):
        if objet not in DOCUMENTS:
            raise ValueError("document inconnu : %r (permis : %s)" % (objet, ", ".join(sorted(DOCUMENTS))))
        if not _ID.match(str(socid)):
            raise ValueError("socid : un nombre (l'identifiant du tiers)")
        corps = {"socid": int(socid), "lines": _lignes(lignes), "date": date if date is not None else _jour_ts("")}      # Dolibarr 24 exige la date d'un devis
        if note:
            corps["note_private"] = str(note)[:4000]
        conf = _conf()
        nouvel = ecrire(conf, "POST", DOCUMENTS[objet], corps)
        if not isinstance(nouvel, int) and not (isinstance(nouvel, str) and _ID.match(nouvel)):
            raise PontErreur("Dolibarr n'a pas rendu l'identifiant du brouillon")
        return {"document": objet, "id": int(nouvel), "socid": int(socid), "lignes": len(corps["lines"])}

    def prouver_brouillon(ctx, res):
        d = _lire_un(_conf(), DOCUMENTS[res["document"]], res["id"])
        return (isinstance(d, dict) and str(d.get("statut", d.get("status", ""))) == "0" and len(d.get("lines") or []) == res["lignes"]
                and str(d.get("socid", d.get("fk_soc", ""))) == str(res["socid"]))

    def defaire_brouillon(ctx, res):
        conf = _conf()
        d = _lire_un(conf, DOCUMENTS[res["document"]], res["id"])
        if isinstance(d, dict) and str(d.get("statut", d.get("status", ""))) != "0":
            raise PontErreur("le document n'est plus un brouillon : il ne se supprime pas")      # jamais supprimer autre chose qu'un brouillon à nous
        ecrire(conf, "DELETE", "%s/%s" % (DOCUMENTS[res["document"]], res["id"]))

    def _chemin_de(objet):
        if objet in ECRIVABLES:
            return ECRIVABLES[objet]["chemin"]
        if objet in DOCUMENTS:
            return DOCUMENTS[objet]
        raise ValueError("objet inconnu : %r (permis : %s)" % (objet, ", ".join(sorted(list(ECRIVABLES) + list(DOCUMENTS)))))

    def _corps_depuis(objet, snap):
        """Ce qu'il faut renvoyer à Dolibarr pour recréer un objet copié : les champs permis, sans les vides."""
        if objet in ECRIVABLES:
            corps = {k: snap[k] for k in ECRIVABLES[objet]["champs"] if k in snap and snap[k] not in (None, "")}
            return corps
        lignes = [{k: l[k] for k in CHAMPS_LIGNE if k in l and l[k] not in (None, "")} for l in (snap.get("lines") or [])]
        corps = {"socid": int(snap.get("socid") or snap.get("fk_soc")), "lines": lignes}
        if snap.get("date"):
            corps["date"] = snap["date"]
        if snap.get("note_private"):
            corps["note_private"] = snap["note_private"]
        return corps

    def supprimer(ctx, objet, id):
        chemin = _chemin_de(objet)
        if not _ID.match(str(id)):
            raise ValueError("id : un nombre")
        conf = _conf()
        courant = _lire_un(conf, chemin, id)
        if not isinstance(courant, dict):
            raise PontErreur("l'objet %s %s est introuvable" % (objet, id))
        cid = "%s-%s-%d" % (objet, id, int(time.time()))
        # la copie d'abord : si le processus meurt entre la suppression et sa preuve, rien n'est perdu
        ctx.poser("dolibarr_corbeille", cid, "%s %s" % (objet, id), etat="en_cours", donnees={"objet": objet, "id": int(id), "copie": courant})
        try:
            ecrire(conf, "DELETE", "%s/%s" % (chemin, id))
        except Exception:
            ctx.retirer("dolibarr_corbeille", cid)               # rien n'a été supprimé : la copie ne sert à rien
            raise
        ctx.poser("dolibarr_corbeille", cid, "%s %s" % (objet, id), etat="supprime", donnees={"objet": objet, "id": int(id), "copie": courant})
        return {"objet": objet, "id": int(id), "corbeille": cid}

    def prouver_suppression(ctx, res):
        try:
            _lire_un(_conf(), _chemin_de(res["objet"]), res["id"])
        except PontErreur as ex:
            return ex.code == 404
        return False

    def _recreer(ctx, cid):
        conf = _conf()
        c = ctx.lire("dolibarr_corbeille", cid, portee=ctx.TOUT)
        if not c:
            raise PontErreur("la corbeille ne contient pas %s" % cid)
        objet, copie = c["donnees"]["objet"], c["donnees"]["copie"]
        chemin = _chemin_de(objet)
        nouvel = ecrire(conf, "POST", chemin, _completer(objet, _corps_depuis(objet, copie)))
        if not isinstance(nouvel, int) and not (isinstance(nouvel, str) and _ID.match(nouvel)):
            raise PontErreur("Dolibarr n'a pas rendu l'identifiant de l'objet recréé")
        ctx.poser("dolibarr_corbeille", cid, c["libelle"], etat="restaure", donnees=dict(c["donnees"], restaure_id=int(nouvel)))
        return {"objet": objet, "id": int(nouvel), "corbeille": cid, "ancien_id": c["donnees"]["id"]}

    def defaire_suppression(ctx, res):
        conf = _conf()
        try:
            _lire_un(conf, _chemin_de(res["objet"]), res["id"])        # l'objet est encore là : rien à recréer
            c = ctx.lire("dolibarr_corbeille", res["corbeille"], portee=ctx.TOUT)
            if c:
                ctx.retirer("dolibarr_corbeille", res["corbeille"])
            return
        except PontErreur as ex:
            if ex.code != 404:
                raise
        _recreer(ctx, res["corbeille"])

    def restaurer(ctx, corbeille):
        c = ctx.lire("dolibarr_corbeille", str(corbeille), portee=ctx.TOUT)
        if not c or c["etat"] != "supprime":
            raise ValueError("rien à restaurer dans la corbeille sous « %s »" % corbeille)
        return _recreer(ctx, str(corbeille))

    def prouver_restauration(ctx, res):
        o = _lire_un(_conf(), _chemin_de(res["objet"]), res["id"])
        return isinstance(o, dict)

    def defaire_restauration(ctx, res):
        ecrire(_conf(), "DELETE", "%s/%s" % (_chemin_de(res["objet"]), res["id"]))
        c = ctx.lire("dolibarr_corbeille", res["corbeille"], portee=ctx.TOUT)
        if c:
            donnees = {k: v for k, v in c["donnees"].items() if k != "restaure_id"}
            ctx.poser("dolibarr_corbeille", res["corbeille"], c["libelle"], etat="supprime", donnees=donnees)

    def corbeille_lue(ctx, etat=""):
        sortie = []
        for o in ctx.lister(portee=ctx.TOUT, type="dolibarr_corbeille"):
            if etat and o["etat"] != etat:
                continue
            d = o["donnees"]
            sortie.append({"corbeille": o["id"], "objet": d["objet"], "id": d["id"], "etat": o["etat"], "restaure_id": d.get("restaure_id")})
        return sortie

    def valider_facture(ctx, id):
        if not _ID.match(str(id)):
            raise ValueError("id : un nombre")
        conf = _conf()
        f = _lire_un(conf, DOCUMENTS["factures"], id)
        if not isinstance(f, dict):
            raise PontErreur("la facture %s est introuvable" % id)
        if str(f.get("statut", f.get("status", ""))) != "0":
            raise ValueError("la facture %s n'est pas un brouillon (statut %s)" % (id, f.get("statut", f.get("status"))))
        ecrire(conf, "POST", "%s/%s/validate" % (DOCUMENTS["factures"], id), {"idwarehouse": 0, "notrigger": 0})
        return {"id": int(id)}

    def prouver_validation(ctx, res):
        f = _lire_un(_conf(), DOCUMENTS["factures"], res["id"])
        return isinstance(f, dict) and str(f.get("statut", f.get("status", ""))) == "1"

    def defaire_validation(ctx, res):
        ecrire(_conf(), "POST", "%s/%s/settodraft" % (DOCUMENTS["factures"], res["id"]), {"idwarehouse": 0})


    # ------------------------------------------------------------------ la gestion complète : règlements, avoirs, relances, devis, dons, cotisations, virements, projets
    def _int_id(nouvel, quoi):
        if isinstance(nouvel, bool) or not (isinstance(nouvel, int) or (isinstance(nouvel, str) and _ID.match(nouvel))):
            raise PontErreur("Dolibarr n'a pas rendu l'identifiant de %s" % quoi)
        return int(nouvel)

    def _liste(conf, chemin, params=None):
        try:
            r = appeler(conf, chemin, params)
        except PontErreur as ex:
            if ex.code == 404:                                   # « rien trouvé » : Dolibarr répond 404
                return []
            raise
        return r if isinstance(r, list) else []

    def _montant(v, nom="montant"):
        try:
            m = round(float(str(v).replace(",", ".")), 2)
        except ValueError:
            raise ValueError("%s : un nombre" % nom)
        if not 0 < m <= 10000000:
            raise ValueError("%s : entre 0,01 et 10 000 000" % nom)
        return m

    def _jour_ts(v):
        v = v or time.strftime("%Y-%m-%d")
        if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", str(v)):
            raise ValueError("date : AAAA-MM-JJ")
        return calendar.timegm(time.strptime(str(v), "%Y-%m-%d")) + 43200

    def _statut(d):
        return str(d.get("statut", d.get("status", "")))

    def _doc(conf, chemin, id, quoi):
        if not _ID.match(str(id)):
            raise ValueError("id : un nombre")
        d = _lire_un(conf, chemin, id)
        if not isinstance(d, dict) or d.get("id") in (None, ""):          # Dolibarr 24 rend 200 et un objet VIDE pour un don qui n'existe plus
            raise PontErreur("%s %s est introuvable" % (quoi, id))
        return d

    def _reste(conf, f):
        if f.get("remaintopay") not in (None, ""):
            return round(float(f["remaintopay"]), 2)
        paye = sum(float(p.get("amount") or 0) for p in _liste(conf, "/invoices/%s/payments" % f["id"]))
        return round(float(f.get("total_ttc") or 0) - paye, 2)

    def _mode_id(conf, code):
        if code not in MODES_PAIEMENT:
            raise ValueError("mode : %s" % ", ".join(MODES_PAIEMENT))
        for m in _liste(conf, "/setup/dictionary/payment_types", {"limit": 200}):
            if str(m.get("code", "")).upper() == code:
                return int(m["id"])
        raise PontErreur("Dolibarr n'a pas de mode de règlement de code « %s » (Configuration › Dictionnaires)" % code)


    # --- le PDF d'une pièce : le lire (pour l'afficher), le produire s'il n'existe pas encore
    def _piece(objet, id):
        if objet not in PIECES:
            raise ValueError("objet : %s" % ", ".join(sorted(PIECES)))
        conf = _conf()
        chemin, part = PIECES[objet]
        d = _doc(conf, chemin, id, "la pièce")
        return conf, chemin, part, d, str(d.get("ref") or id)

    def _pdfs(conf, part, id):
        return [x for x in _liste(conf, "/documents", {"modulepart": part, "id": id}) if isinstance(x, dict) and str(x.get("name", "")).lower().endswith(".pdf")]

    def piece_pdf(ctx, objet, id):
        conf, chemin, part, d, ref = _piece(objet, id)
        pdfs = _pdfs(conf, part, id)
        if not pdfs:
            raise ValueError("%s %s n'a pas de PDF : on peut le produire (produire_pdf)" % (objet, ref))
        nom = sorted(str(x["name"]) for x in pdfs)[0]
        rep = appeler(conf, "/documents/download", {"modulepart": part, "original_file": "%s/%s" % (ref, nom)})
        if not isinstance(rep, dict) or not rep.get("content"):
            raise PontErreur("Dolibarr n'a pas rendu le contenu du PDF")
        if str(rep.get("content-type", "application/pdf")).split(";")[0] != "application/pdf":
            raise PontErreur("le fichier n'est pas un PDF (%s)" % rep.get("content-type"))
        if int(rep.get("filesize") or 0) > MAX_PDF:
            raise ValueError("le PDF dépasse %d Mo : ouvrez-le dans Dolibarr" % (MAX_PDF // 2 ** 20))
        return {"objet": objet, "id": int(id), "ref": ref, "nom": nom, "type": "application/pdf", "taille": int(rep.get("filesize") or 0), "donnees_b64": str(rep["content"])}

    def produire_pdf(ctx, objet, id):
        conf, chemin, part, d, ref = _piece(objet, id)
        if _pdfs(conf, part, id):
            raise ValueError("%s %s a déjà son PDF" % (objet, ref))
        fichier = "%s/%s.pdf" % (ref, ref)
        ecrire(conf, "PUT", "/documents/builddoc", {"modulepart": part, "original_file": fichier, "langcode": "fr_FR"})
        return {"objet": objet, "id": int(id), "ref": ref, "fichier": fichier}

    def prouver_produire(ctx, res):
        conf = _conf()
        return bool(_pdfs(conf, PIECES[res["objet"]][1], res["id"]))

    def defaire_produire(ctx, res):
        ecrire(_conf(), "DELETE", "/documents?" + urllib.parse.urlencode({"modulepart": PIECES[res["objet"]][1], "original_file": res["fichier"]}))

    def mon_acces(ctx):
        conf = _conf()
        info = appeler(conf, "/users/info")
        info = info if isinstance(info, dict) else {}
        try:
            societe = str((appeler(conf, "/setup/company") or {}).get("name") or "")
        except PontErreur:
            societe = ""
        propre = bool(conf["compte"] and conf["cle_perso"])
        return {"cle": "compte" if propre else ("mandat" if conf["cle_mandat"] else "fichier"), "peut_ecrire": propre or not conf["compte"] or conf["mandat_pour_tous"],
                "utilisateur": str(info.get("login") or ""), "administrateur": str(info.get("admin")) == "1", "entite": str(info.get("entity") or ""), "societe": societe}

    # --- encaisser un règlement
    def encaisser(ctx, id, montant, banque, mode="VIR", date="", numero="", note=""):
        montant = _montant(montant)
        if not _ID.match(str(banque)):
            raise ValueError("banque : l'identifiant du compte bancaire Dolibarr")
        conf = _conf()
        f = _doc(conf, DOCUMENTS["factures"], id, "la facture")
        if _statut(f) != "1" or str(f.get("paye")) == "1":
            raise ValueError("la facture %s n'est pas validée et ouverte (statut %s)" % (id, _statut(f)))
        reste = _reste(conf, f)
        if montant > reste + 0.005:
            raise ValueError("%.2f dépasse le reste dû (%.2f)" % (montant, reste))
        avant = len(_liste(conf, "/invoices/%s/payments" % id))
        # « paymentsdistributed » : le seul point qui accepte un MONTANT (le point /payments d'une facture règle toujours tout le reste dû)
        corps = {"arrayofamounts": {str(int(id)): {"amount": montant, "multicurrency_amount": montant}}, "datepaye": _jour_ts(date), "paymentid": _mode_id(conf, str(mode).upper()),
                 "closepaidinvoices": "yes" if montant >= reste - 0.005 else "no", "accountid": int(banque), "num_payment": str(numero)[:60], "comment": str(note)[:500]}
        rep = ecrire(conf, "POST", "/invoices/paymentsdistributed", corps)
        pid = int(rep) if isinstance(rep, int) and not isinstance(rep, bool) or (isinstance(rep, str) and _ID.match(rep)) else None
        return {"id": int(id), "montant": montant, "reste_avant": reste, "paiements_avant": avant, "paiement": pid}

    def prouver_encaisser(ctx, res):
        conf = _conf()
        f = _lire_un(conf, DOCUMENTS["factures"], res["id"])
        return (isinstance(f, dict) and abs(_reste(conf, f) - (res["reste_avant"] - res["montant"])) < 0.01
                and len(_liste(conf, "/invoices/%s/payments" % res["id"])) == res["paiements_avant"] + 1)

    def defaire_encaisser(ctx, res):
        if not res.get("paiement"):
            raise PontErreur("Dolibarr n'a pas rendu l'identifiant du règlement : à supprimer dans Dolibarr (Facture › Règlements)")
        ecrire(_conf(), "DELETE", "/paiements/%d" % res["paiement"])          # Dolibarr refuse un règlement déjà rapproché en banque : cette garde est la sienne

    # --- un avoir en brouillon
    def creer_avoir(ctx, id):
        conf = _conf()
        f = _doc(conf, DOCUMENTS["factures"], id, "la facture")
        if _statut(f) not in ("1", "2") or str(f.get("type")) not in ("0", "None", ""):
            raise ValueError("un avoir se fait sur une facture validée ordinaire (statut %s, type %s)" % (_statut(f), f.get("type")))
        lignes = []
        for l in (f.get("lines") or []):
            n = {k: l[k] for k in CHAMPS_LIGNE if k in l and l[k] not in (None, "")}
            if "subprice" in n:
                n["subprice"] = -abs(float(n["subprice"]))               # un avoir porte les montants de la facture, en négatif
            lignes.append(n)
        if not lignes:
            raise ValueError("la facture %s n'a pas de lignes" % id)
        socid = int(f.get("socid") or f.get("fk_soc"))
        nouvel = _int_id(ecrire(conf, "POST", DOCUMENTS["factures"], {"socid": socid, "type": 2, "fk_facture_source": int(id), "date": _jour_ts(""), "lines": lignes[:MAX_LIGNES],
                                                                      "note_private": "Avoir préparé par Cassandra pour la facture %s" % (f.get("ref") or id)}), "l'avoir")
        return {"document": "factures", "id": nouvel, "socid": socid, "lignes": len(lignes[:MAX_LIGNES]), "source": int(id)}

    # --- une relance, gardée dans l'agenda du tiers (l'envoi du courriel reste au module Mandats, qui seul résout l'adresse)
    def relancer(ctx, id, message):
        message = str(message or "").strip()
        if not message or len(message) > 4000:
            raise ValueError("message : de 1 à 4000 caractères")
        conf = _conf()
        f = _doc(conf, DOCUMENTS["factures"], id, "la facture")
        if _statut(f) != "1" or str(f.get("paye")) == "1":
            raise ValueError("la facture %s n'est pas ouverte : rien à relancer" % id)
        maintenant = int(time.time())
        moi = appeler(conf, "/users/info")
        proprietaire = int((moi or {}).get("id") or 0) if isinstance(moi, dict) else 0
        if not proprietaire:
            raise PontErreur("Dolibarr n'a pas dit qui est l'utilisateur de la clé : un évènement d'agenda doit avoir un propriétaire")
        nouvel = _int_id(ecrire(conf, "POST", "/agendaevents", {"userownerid": proprietaire, "type_code": "AC_OTH", "label": "Relance de la facture %s" % (f.get("ref") or id), "note": message, "datep": maintenant,
                                                                "datef": maintenant, "percentage": 100, "socid": int(f.get("socid") or f.get("fk_soc"))}),
                       "l'évènement de relance")          # Dolibarr 24 refuse elementtype et fk_element dans la requête : le lien à la facture est dans le libellé
        return {"evenement": nouvel, "id": int(id)}

    def prouver_relance(ctx, res):
        e = _lire_un(_conf(), "/agendaevents", res["evenement"])
        return isinstance(e, dict) and str(e.get("label", "")).startswith("Relance de la facture")

    def defaire_relance(ctx, res):
        ecrire(_conf(), "DELETE", "/agendaevents/%d" % res["evenement"])

    # --- le devis : valider, marquer signé ou refusé ; puis le facturer
    ETATS_DEVIS = {"valider": ("0", "1"), "signer": ("1", "2"), "refuser": ("1", "3")}

    def devis(ctx, id, action):
        if action not in ETATS_DEVIS:
            raise ValueError("action : %s" % ", ".join(sorted(ETATS_DEVIS)))
        conf = _conf()
        d = _doc(conf, DOCUMENTS["devis"], id, "le devis")
        de, vers = ETATS_DEVIS[action]
        if _statut(d) != de:
            raise ValueError("le devis %s est au statut %s : « %s » demande le statut %s" % (id, _statut(d), action, de))
        if action == "valider":
            ecrire(conf, "POST", "%s/%s/validate" % (DOCUMENTS["devis"], id), {"notrigger": 0})
        else:
            ecrire(conf, "POST", "%s/%s/close" % (DOCUMENTS["devis"], id), {"status": int(vers), "note_private": "Marqué par Cassandra (%s)" % action})
        return {"id": int(id), "action": action, "avant": de, "apres": vers}

    def prouver_devis(ctx, res):
        d = _lire_un(_conf(), DOCUMENTS["devis"], res["id"])
        return isinstance(d, dict) and _statut(d) == res["apres"]

    def defaire_devis(ctx, res):
        ecrire(_conf(), "POST", "%s/%s/settodraft" % (DOCUMENTS["devis"], res["id"]), {"idwarehouse": 0})

    def facturer_devis(ctx, id):
        conf = _conf()
        d = _doc(conf, DOCUMENTS["devis"], id, "le devis")
        if _statut(d) != "2":
            raise ValueError("seul un devis signé se facture (statut %s)" % _statut(d))
        lignes = [{k: l[k] for k in CHAMPS_LIGNE if k in l and l[k] not in (None, "")} for l in (d.get("lines") or [])][:MAX_LIGNES]
        if not lignes:
            raise ValueError("le devis %s n'a pas de lignes" % id)
        socid = int(d.get("socid") or d.get("fk_soc"))
        nouvel = _int_id(ecrire(conf, "POST", DOCUMENTS["factures"], {"socid": socid, "date": _jour_ts(""), "lines": lignes,
                                                                      "note_private": "Issue du devis %s, préparée par Cassandra" % (d.get("ref") or id)}), "la facture")
        return {"document": "factures", "id": nouvel, "socid": socid, "lignes": len(lignes), "devis": int(id)}

    # --- les dons : saisir, valider, éditer le reçu fiscal
    def don_creer(ctx, montant, date="", nom="", prenom="", societe=""):
        montant = _montant(montant)
        conf = _conf()
        champs = {"amount": montant, "date": _jour_ts(date)}
        for k, v in (("lastname", nom), ("firstname", prenom), ("societe", societe)):
            if v:
                champs[k] = str(v)[:120]
        nouvel = _int_id(ecrire(conf, "POST", "/donations", champs), "le don")
        return {"id": nouvel, "montant": montant}

    def prouver_don(ctx, res):
        d = _lire_un(_conf(), "/donations", res["id"])
        return isinstance(d, dict) and abs(float(d.get("amount") or 0) - res["montant"]) < 0.01

    def defaire_don(ctx, res):
        d = _lire_un(_conf(), "/donations", res["id"])
        if isinstance(d, dict) and _statut(d) not in ("0", "-1"):
            raise PontErreur("le don n'est plus une promesse : il ne se supprime pas")
        ecrire(_conf(), "DELETE", "/donations/%d" % res["id"])

    def don_valider(ctx, id):
        conf = _conf()
        d = _doc(conf, "/donations", id, "le don")
        if _statut(d) != "0":
            raise ValueError("le don %s n'est pas une promesse à valider (statut %s)" % (id, _statut(d)))
        ecrire(conf, "POST", "/donations/%s/validate" % id, {"notrigger": 0})
        return {"id": int(id)}

    def prouver_don_valide(ctx, res):
        d = _lire_un(_conf(), "/donations", res["id"])
        return isinstance(d, dict) and _statut(d) == "1"

    def defaire_don_valide(ctx, res):
        raise PontErreur("Dolibarr ne repasse pas un don validé en promesse par l'API : à défaire dans Dolibarr")

    def don_recu(ctx, id):
        conf = _conf()
        d = _doc(conf, "/donations", id, "le don")
        if _statut(d) not in ("1", "2"):
            raise ValueError("le reçu fiscal se prépare pour un don validé (statut %s)" % _statut(d))
        ref = str(d.get("ref") or id)
        fichier = "%s/%s.pdf" % (ref, ref)
        rep = ecrire(conf, "PUT", "/documents/builddoc", {"modulepart": "donation", "original_file": fichier, "doctemplate": "html_cerfaDonation", "langcode": "fr_FR"})
        return {"id": int(id), "fichier": fichier, "reponse": (rep if isinstance(rep, (dict, str)) else {})}

    def prouver_recu(ctx, res):
        conf = _conf()
        rep = appeler(conf, "/documents", {"modulepart": "donation", "id": res["id"]})
        return isinstance(rep, list) and any(str(x.get("name", "")).endswith(".pdf") for x in rep if isinstance(x, dict))

    def defaire_recu(ctx, res):
        ecrire(_conf(), "DELETE", "/documents?" + urllib.parse.urlencode({"modulepart": "donation", "original_file": res["fichier"]}))

    # --- une cotisation d'adhérent
    def cotisation(ctx, membre, montant, debut="", fin="", libelle=""):
        montant = _montant(montant)
        conf = _conf()
        m = _doc(conf, "/members", membre, "l'adhérent")
        avant = len(_liste(conf, "/members/%s/subscriptions" % membre))
        nouvel = _int_id(ecrire(conf, "POST", "/members/%s/subscriptions" % membre, {"start_date": _jour_ts(debut), "end_date": _jour_ts(fin) if fin else _jour_ts(debut) + 365 * 86400, "amount": montant,
                                                                                   "label": str(libelle or "Cotisation")[:120]}), "la cotisation")
        return {"membre": int(membre), "cotisation": nouvel, "montant": montant, "avant": avant, "fin_avant": m.get("datefin")}

    def prouver_cotisation(ctx, res):
        return len(_liste(_conf(), "/members/%s/subscriptions" % res["membre"])) == res["avant"] + 1

    def defaire_cotisation(ctx, res):
        ecrire(_conf(), "DELETE", "/subscriptions/%d" % res["cotisation"])

    # --- un virement entre deux comptes bancaires (le retour est le virement inverse)
    def _solde(conf, bid):
        r = appeler(conf, "/bankaccounts/%s/balance" % bid)
        try:
            return round(float(r if not isinstance(r, dict) else r.get("balance", 0)), 2)
        except (TypeError, ValueError):
            raise PontErreur("Dolibarr n'a pas rendu le solde du compte %s" % bid)

    def virement_interne(ctx, de, vers, montant, date="", libelle=""):
        montant = _montant(montant)
        if not _ID.match(str(de)) or not _ID.match(str(vers)) or str(de) == str(vers):
            raise ValueError("de et vers : deux comptes bancaires différents (identifiants)")
        conf = _conf()
        sd, sv = _solde(conf, de), _solde(conf, vers)
        ecrire(conf, "POST", "/bankaccounts/transfer", {"bankaccount_from_id": int(de), "bankaccount_to_id": int(vers), "amount": montant, "date": _jour_ts(date),
                                                         "description": str(libelle or "Virement interne")[:120]})
        return {"de": int(de), "vers": int(vers), "montant": montant, "solde_de": sd, "solde_vers": sv}

    def prouver_virement(ctx, res):
        conf = _conf()
        return (abs(_solde(conf, res["de"]) - (res["solde_de"] - res["montant"])) < 0.01 and abs(_solde(conf, res["vers"]) - (res["solde_vers"] + res["montant"])) < 0.01)

    def defaire_virement(ctx, res):
        ecrire(_conf(), "POST", "/bankaccounts/transfer", {"bankaccount_from_id": res["vers"], "bankaccount_to_id": res["de"], "amount": res["montant"], "date": _jour_ts(""),
                                                           "description": "Annulation du virement interne"})

    # --- un projet : l'ouvrir, le clore
    ETATS_PROJET = {"valider": ("0", "1"), "clore": ("1", "2")}

    def projet(ctx, id, action):
        if action not in ETATS_PROJET:
            raise ValueError("action : %s" % ", ".join(sorted(ETATS_PROJET)))
        conf = _conf()
        p = _doc(conf, "/projects", id, "le projet")
        de, vers = ETATS_PROJET[action]
        if _statut(p) != de:
            raise ValueError("le projet %s est au statut %s : « %s » demande le statut %s" % (id, _statut(p), action, de))
        if action == "valider":
            ecrire(conf, "POST", "/projects/%s/validate" % id, {"notrigger": 0})
        else:
            ecrire(conf, "PUT", "/projects/%s" % id, {"status": int(vers)})          # « statut » est ignoré par Dolibarr 24 : seul « status » (ou fk_statut) agit
        return {"id": int(id), "action": action, "avant": de, "apres": vers}

    def prouver_projet(ctx, res):
        p = _lire_un(_conf(), "/projects", res["id"])
        return isinstance(p, dict) and _statut(p) == res["apres"]

    def defaire_projet(ctx, res):
        ecrire(_conf(), "PUT", "/projects/%d" % res["id"], {"status": int(res["avant"])})

    # --- tout le reste de l'API : une lecture libre (jamais un secret) et une écriture libre (preuve et retour quand l'acte le permet)
    def _nettoyer(x):
        if isinstance(x, dict):
            return {k: ("***" if _SECRET.search(str(k)) and v not in (None, "", 0, "0") else _nettoyer(v)) for k, v in x.items()}
        if isinstance(x, list):
            return [_nettoyer(v) for v in x]
        return x

    def _chemin_libre(chemin):
        if not isinstance(chemin, str) or not _CHEMIN_LIBRE.match(chemin) or ".." in chemin:
            raise ValueError("chemin : de la forme /domaine/…, par exemple /thirdparties/12")
        if chemin.split("/")[1] not in DOMAINES:
            raise ValueError("domaine inconnu : %r (permis : %s)" % (chemin.split("/")[1], ", ".join(DOMAINES)))
        return chemin

    def lire_libre(ctx, chemin, parametres=""):
        chemin = _chemin_libre(chemin)
        if not _REQUETE.match(str(parametres or "")):
            raise ValueError("parametres : une chaîne de requête simple (limit=5&page=0)")
        conf = _conf()
        p = dict(urllib.parse.parse_qsl(str(parametres or ""))) if parametres else {}
        if chemin.count("/") == 1:                                  # une collection : une page de MAX_LIBRE lignes au plus (page=1, page=2… pour la suite)
            try:
                p["limit"] = str(max(1, min(int(p.get("limit", MAX_LIBRE)), MAX_LIBRE)))
            except ValueError:
                raise ValueError("limit : un entier")
        try:
            rep = appeler(conf, chemin, p)
        except PontErreur as ex:
            if ex.code == 404:
                return {"chemin": chemin, "reponse": [], "tronque": False}
            raise
        tronque = isinstance(rep, list) and chemin.count("/") == 1 and len(rep) >= int(p["limit"])        # il en reste peut-être : la page suivante
        return {"chemin": chemin, "reponse": _nettoyer(rep), "tronque": tronque}

    def ecrire_libre(ctx, methode, chemin, corps=None):
        methode = str(methode).upper()
        if methode not in ("POST", "PUT"):
            raise ValueError("methode : POST ou PUT (une suppression passe par « supprimer », avec sa corbeille)")
        chemin = _chemin_libre(chemin)
        if corps is not None and not isinstance(corps, dict):
            raise ValueError("corps : un objet JSON")
        conf = _conf()
        parties = chemin.strip("/").split("/")
        avant = None
        if methode == "PUT" and len(parties) == 2 and isinstance(corps, dict):
            courant = _lire_un(conf, "/" + parties[0], parties[1])
            if not isinstance(courant, dict):
                raise PontErreur("%s est introuvable" % chemin)
            avant = {k: courant.get(k) for k in corps}
        rep = ecrire(conf, methode, chemin, corps)
        nouvel = None
        if methode == "POST" and len(parties) == 1 and isinstance(rep, (int, str)) and not isinstance(rep, bool) and _ID.match(str(rep)):
            nouvel = int(rep)
        return {"methode": methode, "chemin": chemin, "corps": corps, "avant": avant, "cree": nouvel, "reponse": _nettoyer(rep) if isinstance(rep, (dict, list)) else None}

    def prouver_libre(ctx, res):
        conf = _conf()
        parties = res["chemin"].strip("/").split("/")
        if res["avant"] is not None:
            o = _lire_un(conf, "/" + parties[0], parties[1])
            return isinstance(o, dict) and all(_egaux(o.get(k), v) for k, v in res["corps"].items())
        if res["cree"]:
            return isinstance(_lire_un(conf, res["chemin"], res["cree"]), dict)
        return True            # une action (valider, clore…) : Dolibarr a répondu sans erreur, la preuve est sa réponse

    def defaire_libre(ctx, res):
        conf = _conf()
        parties = res["chemin"].strip("/").split("/")
        if res["avant"] is not None:
            ecrire(conf, "PUT", res["chemin"], res["avant"])
        elif res["cree"]:
            ecrire(conf, "DELETE", "%s/%d" % (res["chemin"], res["cree"]))
        else:
            raise PontErreur("cette action n'a pas de retour générique : à défaire dans Dolibarr")

    ctx.implementer("creer", creer, prouver_objet, defaire_objet, simuler=lambda ctx, objet="", **_: "créerait un(e) %s" % objet)
    ctx.implementer("modifier", modifier, prouver_objet, defaire_objet, simuler=lambda ctx, objet="", id="", **_: "modifierait %s %s" % (objet, id))
    ctx.implementer("creer_brouillon", creer_brouillon, prouver_brouillon, defaire_brouillon,
                    simuler=lambda ctx, objet="", **_: "créerait un brouillon de %s" % objet)
    ctx.implementer("supprimer", supprimer, prouver_suppression, defaire_suppression,
                    simuler=lambda ctx, objet="", id="", **_: "supprimerait %s %s (copie gardée dans la corbeille)" % (objet, id))
    ctx.implementer("restaurer", restaurer, prouver_restauration, defaire_restauration,
                    simuler=lambda ctx, corbeille="", **_: "recréerait l'objet de la corbeille %s" % corbeille)
    ctx.implementer("corbeille", corbeille_lue)
    ctx.implementer("valider_facture", valider_facture, prouver_validation, defaire_validation,
                    simuler=lambda ctx, id="", **_: "validerait la facture %s (elle prendrait un numéro)" % id)

    ctx.implementer("mon_acces", mon_acces)
    ctx.implementer("piece_pdf", piece_pdf)
    ctx.implementer("produire_pdf", produire_pdf, prouver_produire, defaire_produire, simuler=lambda ctx, objet="", id="", **_: "produirait le PDF de %s %s" % (objet, id))
    ctx.implementer("encaisser", encaisser, prouver_encaisser, defaire_encaisser,
                    simuler=lambda ctx, id="", montant="", **_: "encaisserait %s € sur la facture %s" % (montant, id))
    ctx.implementer("creer_avoir", creer_avoir, prouver_brouillon, defaire_brouillon, simuler=lambda ctx, id="", **_: "préparerait un avoir en brouillon pour la facture %s" % id)
    ctx.implementer("relancer", relancer, prouver_relance, defaire_relance, simuler=lambda ctx, id="", **_: "noterait une relance de la facture %s dans l'agenda du tiers" % id)
    ctx.implementer("devis", devis, prouver_devis, defaire_devis, simuler=lambda ctx, id="", action="", **_: "ferait « %s » sur le devis %s" % (action, id))
    ctx.implementer("facturer_devis", facturer_devis, prouver_brouillon, defaire_brouillon, simuler=lambda ctx, id="", **_: "préparerait une facture en brouillon depuis le devis %s" % id)
    ctx.implementer("don_creer", don_creer, prouver_don, defaire_don, simuler=lambda ctx, montant="", **_: "saisirait un don de %s €" % montant)
    ctx.implementer("don_valider", don_valider, prouver_don_valide, defaire_don_valide, simuler=lambda ctx, id="", **_: "validerait le don %s" % id)
    ctx.implementer("don_recu", don_recu, prouver_recu, defaire_recu, simuler=lambda ctx, id="", **_: "éditerait le reçu fiscal du don %s" % id)
    ctx.implementer("cotisation", cotisation, prouver_cotisation, defaire_cotisation, simuler=lambda ctx, membre="", montant="", **_: "enregistrerait une cotisation de %s € pour l'adhérent %s" % (montant, membre))
    ctx.implementer("virement_interne", virement_interne, prouver_virement, defaire_virement,
                    simuler=lambda ctx, de="", vers="", montant="", **_: "virerait %s € du compte %s au compte %s" % (montant, de, vers))
    ctx.implementer("projet", projet, prouver_projet, defaire_projet, simuler=lambda ctx, id="", action="", **_: "ferait « %s » sur le projet %s" % (action, id))
    ctx.implementer("lire_libre", lire_libre)
    ctx.implementer("ecrire_libre", ecrire_libre, prouver_libre, defaire_libre, simuler=lambda ctx, methode="", chemin="", **_: "ferait %s %s" % (methode, chemin))

    ctx.moteur("releve", releve)
    ctx.detecteur("injoignable", lambda ctx: constat_si(ctx, "injoignable", "Dolibarr ne répond plus"))
    ctx.detecteur("acces_refuse", lambda ctx: constat_si(ctx, "refuse", "Dolibarr refuse la clé d'API"))
    ctx.implementer("resume", resume)
    ctx.implementer("statut", statut)
    ctx.implementer("modules", modules)
    ctx.implementer("compter", compter)
    ctx.implementer("lister", lister)
    ctx.implementer("lire", lire)
    ctx.implementer("impayees", impayees)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : PontErreur, _dossier_config, _reglages, lire_conf, _cle, appeler, ecrire, _liste_complete …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
