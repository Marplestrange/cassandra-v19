"""Le pont Dolibarr : Cassandra pilote une instance Dolibarr par son API REST.

Dolibarr garde son PHP et sa base ; il fait son métier. Ce module lit (GET, par `appeler`) et écrit (POST / PUT / DELETE, par `ecrire`, la seule porte
d'écriture). Toute écriture est une capacité déclarée avec son périmètre, sa PREUVE (relire ce qui a été écrit) et son RETOUR ARRIÈRE (restaurer l'état
d'avant, ou supprimer ce que l'acte vient de créer, et seulement cela). Trois classes :
  - réversible : créer / modifier un tiers, un contact, un produit, un projet, créer un brouillon de facture, de devis ou de commande ;
  - supprimer : l'objet est d'abord copié EN ENTIER dans la corbeille ; on peut le recréer (`restaurer`), seul l'identifiant change. Dolibarr refuse de
    supprimer ce qui est référencé ailleurs (un tiers qui a des factures) : cette garde est la sienne ;
  - légal : valider une facture (elle consomme un numéro).
Le plafond d'autonomie de chaque capacité est un CHOIX DE L'ADMINISTRATEUR (`python main.py palier`) : par défaut Cassandra raconte ce qu'elle ferait ;
un humain agit en voie parallèle, ou monte le palier.
Il en tire un objet du registre (l'instance : version, comptes, impayés), des constats (injoignable, accès refusé) et des lectures bornées.

Réglage : config/dolibarr.conf, des lignes « cle = valeur » :
    url          = http://100.64.0.9:8081/api/index.php     l'adresse de l'API (en production : Athena, par le réseau privé)
    hote         = www.cassandra.center                          (facultatif) l'en-tête Host, quand l'adresse est une IP
    fichier_cle  = dolibarr.key                                   (facultatif) où est la clé, relativement à config/
    delai        = 15                                             (facultatif) secondes
La clé elle-même n'est JAMAIS dans la configuration, ne se logue pas, ne figure dans aucun événement ni aucun objet.
"""
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
MAX_LIGNES = 50


class PontErreur(Exception):
    """Une erreur du pont, au message sûr : jamais l'en-tête de la requête, donc jamais la clé."""

    def __init__(self, message, code=None, genre="erreur"):
        super().__init__(message)
        self.code, self.genre = code, genre


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
    Les réglages (module « réglages ») l'emportent sur config/dolibarr.conf, qui reste le repli."""
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
    return conf


def _cle(conf):
    try:
        with open(conf["fichier_cle"], encoding="utf-8") as fh:
            cle = fh.read().strip()
    except OSError:
        raise PontErreur("le fichier de clé est illisible", genre="non_configure")
    if not cle:
        raise PontErreur("le fichier de clé est vide", genre="non_configure")
    return cle


# ------------------------------------------------------------------ le client : un GET, rien d'autre
def appeler(conf, chemin, parametres=None):
    """GET sur l'API. Rend le JSON décodé. Aucune autre méthode n'existe dans ce module."""
    url = conf["url"].rstrip("/") + chemin
    if parametres:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(parametres)
    en_tetes = {"DOLAPIKEY": _cle(conf), "Accept": "application/json"}
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
    en_tetes = {"DOLAPIKEY": _cle(conf), "Accept": "application/json", "Content-Type": "application/json"}
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
    """Dolibarr rend souvent des nombres en texte (« 1 » pour 1) : on compare ce qui compte."""
    if a is None or b is None:
        return a is b or str(a or "") == str(b or "")
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a) == str(b)


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
        nouvel = ecrire(conf, "POST", ECRIVABLES[objet]["chemin"], champs)
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
        corps = {"socid": int(socid), "lines": _lignes(lignes)}
        if date is not None:
            corps["date"] = date
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
        nouvel = ecrire(conf, "POST", chemin, _corps_depuis(objet, copie))
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
