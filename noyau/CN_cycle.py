# ══════════════════════════════════════════════════════════════════
# TITRE      : Le cycle de vie d'un module installé : examiner, installer, mettre à jour, retour arrière, désinstaller
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #ec97f8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le cycle de vie d'un module venu d'une archive : examiner sans rien poser, installer avec consentement, mettre à jour, revenir en arrière, désinstaller (rien ne se perd : tout ce qui part va en sauvegarde).
# MÉTHODE    : l'archive attend en quarantaine ; l'examen la vérifie (empreintes, signature, manifeste) et compare au module en place ; l'installation re-vérifie, exige le consentement aux permissions, sauvegarde l'ancienne version puis dépose le dossier dans celui des extensions que le noyau surveille
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ec97f8 ▼▼▼
"""Le cycle de vie d'un module installé, à la manière d'un module store.

    examiner(octets)       l'archive va en quarantaine ; on la vérifie (SOMMES, signature, manifeste) et on dit ce qu'elle ferait : nouveau, mise à jour, retour à une version
                           plus ancienne ; ce qu'elle demande (permissions, élargies ou non), ce qui lui manque (dépendances, versions), ce qui la refuse (conflit, confiance, politique).
                           RIEN n'est posé.
    installer(jeton, ...)  re-vérifie, exige le consentement aux permissions TELLES QUE MONTRÉES, sauvegarde la version en place, dépose le dossier. Le noyau en marche le voit.
    retour_arriere(id)     remet la dernière sauvegarde (la version courante part elle-même en sauvegarde : on peut revenir sur son retour).
    desinstaller(id)       le dossier part en sauvegarde ; les données du module restent (elles ne se purgent que sur demande, et partent alors aussi en sauvegarde).

Ce qui est livré avec le noyau ne se désinstalle pas. Un module venu d'une archive tourne DANS le processus de Cassandra : ses permissions (réseau, écritures, privilèges) sont déclaratives,
jusqu'à la cage par processus. C'est pourquoi la politique par défaut n'accepte que des paquets signés par un éditeur dont l'administrateur a posé la clé (config/cles/<éditeur>.pub).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import CN_manifeste as mf
from . import CN_paquets as paquets
from . import CN_registre_officiel as officiel

TAILLE_MAX = 32 * 2 ** 20            # une archive de plus de 32 Mo n'est pas un module
POLITIQUES = ("signes", "tous")      # signes : seulement les paquets signés par une clé de confiance ; tous : un paquet non signé est permis (à ses risques, dit à l'écran)
CATEGORIES = ("espace_utilisateur", "reseau", "ecritures", "privileges", "introspection", "lectures", "droits", "identite", "reglages", "stockage", "stockage_lecture", "secrets", "racine", "agir")


class CycleErreur(ValueError):
    pass


TAILLE_INDEX = 2 * 2 ** 20           # l'index d'un registre : 2 Mo au plus
_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _ouvrir(url: str, delai: float, plafond: int) -> bytes:
    """Lit une adresse http(s), pas plus de `plafond` octets ; au-delà, c'est une erreur (jamais une lecture tronquée)."""
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise CycleErreur("seules les adresses http et https sont permises")
    req = urllib.request.Request(url, headers={"User-Agent": "Cassandra/19 (registre de modules)", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            donnees = r.read(plafond + 1)
    except (urllib.error.URLError, OSError, ValueError) as ex:
        raise CycleErreur("injoignable : %s" % str(getattr(ex, "reason", ex))[:120]) from ex
    if len(donnees) > plafond:
        raise CycleErreur("réponse démesurée (plus de %d Mo)" % (plafond // 2 ** 20))
    return donnees


def lire_index(octets: bytes, base_url: str) -> list:
    """L'index d'un registre : {"modules": [{id, nom, version, description, url, sha256, ...}]}. Une entrée mal formée est écartée ; une adresse d'archive d'un AUTRE hôte que le registre l'est aussi."""
    try:
        brut = json.loads(octets.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as ex:
        raise CycleErreur("l'index du registre n'est pas un JSON lisible") from ex
    liste = brut.get("modules") if isinstance(brut, dict) else None
    if not isinstance(liste, list):
        raise CycleErreur("l'index du registre doit contenir une liste « modules »")
    hote = urllib.parse.urlparse(base_url).netloc
    sortie = []
    for x in liste:
        if not isinstance(x, dict) or not _ID.match(str(x.get("id", ""))) or not str(x.get("version", "")).strip() or not _SHA.match(str(x.get("sha256", ""))):
            continue
        url = urllib.parse.urljoin(base_url, str(x.get("url", "")))
        if urllib.parse.urlparse(url).netloc != hote:
            continue                                                  # l'archive vit chez le registre : un index ne renvoie pas vers un tiers
        sortie.append({"id": x["id"], "nom": str(x.get("nom") or x["id"])[:80], "version": str(x["version"])[:30], "description": str(x.get("description", ""))[:500], "famille": str(x.get("famille", ""))[:40],
                       "editeur": str(x.get("editeur", ""))[:60], "licence": str(x.get("licence", ""))[:40], "importance": x.get("importance") if x.get("importance") in mf.IMPORTANCES else "",
                       "taille": int(x["taille"]) if isinstance(x.get("taille"), int) else 0, "url": url, "sha256": x["sha256"],
                       "noyau_min": str(x.get("noyau_min", ""))[:20], "requiert": [str(r)[:60] for r in (x.get("requiert") or []) if isinstance(r, str)][:20]})
    return sortie


def permissions_de(m) -> dict:
    """Ce que le manifeste DEMANDE, sous une forme stable : {catégorie : valeur} pour tout ce qui est demandé."""
    p = m.permissions
    sortie = {}
    for c in CATEGORIES:
        v = getattr(p, c, None)
        if isinstance(v, tuple):
            if v:
                sortie[c] = sorted(str(x) for x in v)
        elif v:
            sortie[c] = True
    return sortie


def empreinte_permissions(perms: dict) -> str:
    return hashlib.sha256(json.dumps(perms, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def elargies(avant: dict, apres: dict) -> list:
    """Ce que la nouvelle version demande EN PLUS de l'ancienne (une nouvelle catégorie, un nouvel hôte, un nouveau chemin)."""
    plus = []
    for c, v in apres.items():
        if c not in avant:
            plus.append("%s : %s" % (c, "oui" if v is True else ", ".join(v)))
        elif isinstance(v, list):
            neuf = [x for x in v if x not in avant[c]]
            if neuf:
                plus.append("%s : %s" % (c, ", ".join(neuf)))
    return plus


class Cycle:
    def __init__(self, extensions, donnees, cles, connus, actifs=None, cles_racine=None, url_officielle=None):
        """`connus` : appelable qui rend [(manifeste, est_extension)] des modules en place ; `actifs` : appelable qui rend l'ensemble des ids actifs."""
        self.extensions = Path(extensions) if extensions else None
        self.donnees = Path(donnees)
        self.cles = Path(cles) if cles else None
        self.connus = connus
        self.actifs = actifs or (lambda: set())
        self.quarantaine = self.donnees / "quarantaine"
        self.sauvegardes = self.donnees / "modules_sauvegardes"
        self.registre = self.donnees / "modules_installations.json"
        self.cles_racine = dict(officiel.CLES_RACINE if cles_racine is None else cles_racine)       # la racine de confiance : EMBARQUÉE, jamais lue du disque
        self.url_officielle = officiel.URL_OFFICIELLE if url_officielle is None else url_officielle
        self.cache_officiel = self.donnees / "registre_officiel.json"

    # ------------------------------------------------------------------ le journal des installations
    def journal(self) -> list:
        try:
            return json.loads(self.registre.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _ecrire_journal(self, l: list) -> None:
        self.donnees.mkdir(parents=True, exist_ok=True)
        self.registre.write_text(json.dumps(l[-500:], ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    def _noter(self, **fait) -> None:
        l = self.journal()
        l.append(dict(fait, ts=time.time()))
        self._ecrire_journal(l)

    def noter_acte(self, acte: str, mid: str, par: str = "", **plus) -> None:
        """Consigne un acte sur un module qui ne passe pas par l'archive (activé, désactivé) : le récit des modules n'a ainsi qu'un seul journal."""
        self._noter(acte=acte, id=mid, par=par, **plus)

    def annoter(self, mid: str, acte: str, pourquoi: str) -> None:
        """Ajoute le POURQUOI au dernier acte de ce genre sur ce module (qui l'a fait ne dit pas toujours pourquoi : la règle appliquée, la demande reçue)."""
        l = self.journal()
        for x in reversed(l):
            if x.get("id") == mid and x.get("acte") == acte and "pourquoi" not in x:
                x["pourquoi"] = str(pourquoi)[:300]
                self._ecrire_journal(l)
                return

    # ------------------------------------------------------------------ le verrou : un module auquel Cassandra ne touche pas
    def verrous(self) -> set:
        try:
            return set(json.loads((self.donnees / "modules_verrous.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return set()

    def verrouiller(self, mid: str, oui: bool = True, par: str = "") -> set:
        v = self.verrous()
        v.add(mid) if oui else v.discard(mid)
        self.donnees.mkdir(parents=True, exist_ok=True)
        (self.donnees / "modules_verrous.json").write_text(json.dumps(sorted(v), ensure_ascii=False), encoding="utf-8")
        self._noter(acte="verrou" if oui else "deverrouille", id=mid, par=par)
        return v

    def permissions_acceptees(self, mid: str) -> dict:
        """Les permissions de la dernière installation consentie de ce module ({} si jamais installé par archive)."""
        for x in reversed(self.journal()):
            if x.get("id") == mid and x.get("acte") in ("installe", "retour") and "permissions" in x:
                return x["permissions"]
        return {}

    # ------------------------------------------------------------------ les clés de confiance
    def _dossier_cles(self, editeurs=None):
        """Un dossier jetable de clés publiques : celles de l'administrateur (config/cles/*.pub), les racines (cassandra-*), les éditeurs vérifiés (ed_*). Le NOM d'une clé donne le niveau de confiance."""
        t = tempfile.TemporaryDirectory()
        base = Path(t.name)
        if self.cles and self.cles.is_dir():
            for f in sorted(self.cles.glob("*.pub")):
                if not f.stem.startswith(("cassandra-", "ed_")):                    # un nom réservé ne se prend pas : une clé posée à la main ne se fait pas passer pour l'officiel
                    shutil.copy(f, base / f.name)
        for nom, pem in self.cles_racine.items():
            (base / ("cassandra-%s.pub" % nom)).write_text(pem, encoding="utf-8")
        for eid, e in (editeurs if editeurs is not None else self._editeurs_en_cache()).items():
            (base / ("ed_%s.pub" % eid)).write_text(e["cle"], encoding="utf-8")
        return t

    def _lire_cache(self):
        try:
            c = json.loads(self.cache_officiel.read_text(encoding="utf-8"))
            return officiel.lire_index_signe(c["index"].encode("utf-8"), c["signature"].encode("ascii"), self.cles_racine)
        except (OSError, ValueError, KeyError, officiel.RegistreErreur):
            return None

    def _editeurs_en_cache(self) -> dict:
        i = self._lire_cache()
        return officiel.lire_editeurs(i["brut"]) if i else {}

    def revocations_en_cache(self) -> list:
        i = self._lire_cache()
        return officiel.lire_revocations(i["brut"]) if i else []

    # ------------------------------------------------------------------ le registre OFFICIEL : un index signé
    def registre_officiel(self, ouvrir=None, maintenant=None) -> dict:
        """Lit l'index officiel et sa signature, les vérifie contre la racine EMBARQUÉE, garde l'index vérifié en cache (ses éditeurs et ses révocations servent à l'examen des archives
        déposées à la main), et rend les modules proposés avec leur état ici, leur éditeur et leur niveau, les révocations, et les modules installés qui sont révoqués."""
        ouvrir = ouvrir or _ouvrir
        octets = ouvrir(self.url_officielle, 8, TAILLE_INDEX)
        signature = ouvrir(self.url_officielle + ".sig", 8, 4096)
        i = officiel.lire_index_signe(octets, signature, self.cles_racine, maintenant)
        brut = i["brut"]
        self.donnees.mkdir(parents=True, exist_ok=True)
        self.cache_officiel.write_text(json.dumps({"index": octets.decode("utf-8"), "signature": signature.decode("ascii", "replace").strip()}), encoding="utf-8")
        editeurs, revoc = officiel.lire_editeurs(brut), officiel.lire_revocations(brut)
        entrees = lire_index(octets, self.url_officielle)
        en_place = {x.id: x for x, _ in self.connus()}
        for e in entrees:
            m = en_place.get(e["id"])
            e["etat"] = "nouveau" if m is None else ("installe" if mf.version_de(e["version"]) <= mf.version_de(m.version) else "mise_a_jour")
            if m is not None:
                e["version_en_place"] = m.version
            sig = next((x for x in brut.get("modules", []) if isinstance(x, dict) and x.get("id") == e["id"]), {})
            e["editeur_id"] = str(sig.get("editeur", ""))[:40]
            e["niveau"] = "officiel" if e["editeur_id"] in ("", "cassandra") else ("verifie" if e["editeur_id"] in editeurs else "")
            e["revoque"] = officiel.revocation_de(e["id"], e["version"], revoc)
        installes_revoques = [{"id": x.id, "nom": x.nom, "version": x.version, "raison": r} for x, ext in self.connus() if ext
                              for r in [officiel.revocation_de(x.id, x.version, revoc)] if r]
        return {"url": self.url_officielle, "officiel": True, "emis": i["emis"], "expire": i["expire"], "signe_par": i["signe_par"],
                "modules": sorted(entrees, key=lambda e: (e["nom"].lower(), e["id"])),
                "editeurs": [{"id": k, "nom": v["nom"]} for k, v in sorted(editeurs.items())], "revocations": revoc, "installes_revoques": installes_revoques}

    def telecharger_officiel(self, mid: str, politique: str = "signes", ouvrir=None, maintenant=None) -> dict:
        """Télécharge une archive du registre officiel : l'index est vérifié, l'empreinte aussi, une version révoquée est refusée, puis l'archive est examinée avec les clés racine et les éditeurs vérifiés."""
        ouvrir = ouvrir or _ouvrir
        r = self.registre_officiel(ouvrir, maintenant)
        e = next((x for x in r["modules"] if x["id"] == mid), None)
        if e is None:
            raise CycleErreur("« %s » n'est pas dans le registre officiel" % mid)
        if e["revoque"]:
            raise CycleErreur("« %s » %s est révoqué par le registre : %s" % (mid, e["version"], e["revoque"]))
        octets = ouvrir(e["url"], 30, TAILLE_MAX)
        if hashlib.sha256(octets).hexdigest() != e["sha256"]:
            raise CycleErreur("l'archive téléchargée ne correspond pas à l'empreinte de l'index : refusée")
        return self.examiner(octets, politique)

    # ------------------------------------------------------------------ le registre (l'index d'un magasin NON officiel)
    def registre_lire(self, url: str, ouvrir=None) -> list:
        """Les modules que le registre propose, chacun avec son état ici : nouveau, mise_a_jour, installe, ou incompatible (le noyau est trop ancien)."""
        if not url:
            return []
        ouvrir = ouvrir or _ouvrir
        entrees = lire_index(ouvrir(url, 8, TAILLE_INDEX), url)
        en_place = {x.id: x for x, _ in self.connus()}
        for e in entrees:
            m = en_place.get(e["id"])
            if m is None:
                e["etat"] = "nouveau"
            else:
                a, b = mf.version_de(m.version), mf.version_de(e["version"])
                e["etat"] = "installe" if b <= a else "mise_a_jour"
                e["version_en_place"] = m.version
        return sorted(entrees, key=lambda e: (e["nom"].lower(), e["id"]))

    def telecharger(self, url_registre: str, mid: str, politique: str = "signes", ouvrir=None) -> dict:
        """Télécharge l'archive d'un module du registre, vérifie son empreinte contre l'index, puis l'EXAMINE comme n'importe quelle archive déposée : le registre n'a aucun passe-droit."""
        ouvrir = ouvrir or _ouvrir
        e = next((x for x in self.registre_lire(url_registre, ouvrir) if x["id"] == mid), None)
        if e is None:
            raise CycleErreur("« %s » n'est pas dans le registre" % mid)
        octets = ouvrir(e["url"], 30, TAILLE_MAX)
        if hashlib.sha256(octets).hexdigest() != e["sha256"]:
            raise CycleErreur("l'archive téléchargée ne correspond pas à l'empreinte de l'index : refusée")
        return self.examiner(octets, politique)

    # ------------------------------------------------------------------ examiner
    def examiner(self, octets: bytes, politique: str = "signes") -> dict:
        if not self.extensions:
            raise CycleErreur("pas de dossier d'extensions sur cette instance : rien ne peut s'installer")
        if politique not in POLITIQUES:
            politique = "signes"
        if not octets:
            raise CycleErreur("archive vide")
        if len(octets) > TAILLE_MAX:
            raise CycleErreur("archive trop grande (%d Mo au plus)" % (TAILLE_MAX // 2 ** 20))
        jeton = hashlib.sha256(octets).hexdigest()[:24]
        self.quarantaine.mkdir(parents=True, exist_ok=True)
        chemin = self.quarantaine / (jeton + ".cmod")
        chemin.write_bytes(octets)
        cles_tmp = self._dossier_cles()
        try:
            v = paquets.verifier(chemin, Path(cles_tmp.name))
        except (paquets.PaquetInvalide, mf.ManifesteInvalide) as ex:
            chemin.unlink(missing_ok=True)
            raise CycleErreur("paquet refusé : %s" % (" ; ".join(ex.erreurs) if isinstance(ex, mf.ManifesteInvalide) else ex)) from ex
        finally:
            cles_tmp.cleanup()
        m = v["manifeste"]
        connus = self.connus()
        manifestes = [x for x, _ in connus]
        en_place = next(((x, ext) for x, ext in connus if x.id == m.id), None)
        perms = permissions_de(m)
        raisons = []
        revoque = officiel.revocation_de(m.id, m.version, self.revocations_en_cache())
        if revoque:
            raisons.append("version révoquée par le registre officiel : %s" % revoque)
        if m.confiance == "interne":
            raisons.append("la confiance « interne » est réservée aux modules livrés avec le noyau")
        if politique == "signes" and not v["signe"]:
            raisons.append("paquet non signé par une clé de confiance : la politique de cette instance n'accepte que des paquets signés")
        if en_place and not en_place[1]:
            raisons.append("« %s » est livré avec le noyau : une archive ne le remplace pas (c'est un réglage de l'administrateur)" % m.id)
        statut, ancienne, plus = "nouveau", "", []
        if en_place:
            ancienne = en_place[0].version
            a, b = mf.version_de(ancienne), mf.version_de(m.version)
            statut = "identique" if a == b else ("mise_a_jour" if b > a else "retrograde")
            if en_place[1]:
                plus = elargies(self.permissions_acceptees(m.id) or permissions_de(en_place[0]), perms)
        # ce qui manque à la compagnie des autres modules
        par_id = {x.id: x for x in manifestes if x.id != m.id}
        four = mf.fournisseurs(list(par_id.values()) + [m])
        manque, versions = [], []
        for r in m.requiert:
            if r not in par_id and r not in four:
                manque.append(r)
        for r, c in m.contraintes:
            if r in par_id and not mf.satisfait(par_id[r].version, c):
                versions.append("%s %s (installé : %s)" % (r, c, par_id[r].version))
        actifs = set(self.actifs())
        conflits = sorted({c for c in m.conflits if c in actifs} | {x.id for x in par_id.values() if m.id in x.conflits and x.id in actifs})
        # les autres modules qui requièrent CE module avec une contrainte que la nouvelle version ne satisferait plus
        casse = []
        for x in par_id.values():
            for r, c in x.contraintes:
                if r == m.id and not mf.satisfait(m.version, c):
                    casse.append("%s requiert %s %s" % (x.id, m.id, c))
        fichiers = []
        try:
            with tarfile.open(chemin, "r:gz") as t:
                fichiers = [i.name for i in t.getmembers() if i.isfile()]
        except (OSError, tarfile.TarError):
            fichiers = []
        return {
            "jeton": jeton, "id": m.id, "nom": m.nom, "version": m.version, "description": m.description, "famille": m.famille or "autres", "icone_trace": m.icone_trace, "auteur": m.auteur, "licence": m.licence,
            "confiance": m.confiance, "importance": m.importance, "sans": m.sans, "signe": bool(v["signe"]), "editeur": v["editeur"], "niveau": officiel.niveau_de(v["editeur"]),
            "taille": len(octets), "nb_fichiers": len(fichiers), "fichiers": fichiers[:40], "script_installation": bool(m.installation.script),
            "permissions": perms, "empreinte_permissions": empreinte_permissions(perms), "permissions_elargies": plus,
            "statut": statut, "version_en_place": ancienne, "requiert": list(m.requiert), "requiert_manquants": manque, "versions_insuffisantes": versions,
            "conflits": conflits, "casserait": casse, "politique": politique,
            "autorise": not raisons, "raisons": raisons,
            "avertissements": (["ce module tourne dans le processus de Cassandra : n'installez que ce que vous avez de bonnes raisons de croire"] if not v["signe"] else []),
        }

    # ------------------------------------------------------------------ installer
    def installer(self, jeton: str, consentement: str, politique: str = "signes", par: str = "") -> dict:
        chemin = self._archive(jeton)
        e = self.examiner(chemin.read_bytes(), politique)             # on revérifie : la quarantaine a pu être touchée
        if e["jeton"] != jeton:
            raise CycleErreur("l'archive n'est plus celle qui a été examinée")
        if not e["autorise"]:
            raise CycleErreur("installation refusée : " + " ; ".join(e["raisons"]))
        if e["statut"] == "identique":
            raise CycleErreur("cette version est déjà installée")
        if e["requiert_manquants"] or e["versions_insuffisantes"]:
            raise CycleErreur("dépendances insatisfaites : " + " ; ".join(e["requiert_manquants"] + e["versions_insuffisantes"]))
        if e["conflits"]:
            raise CycleErreur("en conflit avec un module actif : " + ", ".join(e["conflits"]))
        if e["casserait"]:
            raise CycleErreur("casserait d'autres modules : " + " ; ".join(e["casserait"]))
        if consentement != e["empreinte_permissions"]:
            raise CycleErreur("le consentement ne correspond pas aux permissions montrées")
        mid = e["id"]
        cible = self.extensions / mid
        sauve = ""
        if cible.exists():
            sauve = self._sauvegarder(cible, mid, e["version_en_place"], "remplace")
        try:
            cles_tmp = self._dossier_cles()
            try:
                v = paquets.extraire(chemin, self.extensions, Path(cles_tmp.name), exiger_signature=(politique == "signes"))
            finally:
                cles_tmp.cleanup()
        except Exception:
            if sauve:                                                  # l'extraction a échoué en route : l'ancienne version revient
                shutil.rmtree(cible, ignore_errors=True)
                shutil.copytree(sauve, cible)
            raise
        self._noter(acte="installe", id=mid, version=v["version"], ancienne=e["version_en_place"], editeur=v["editeur"], signe=v["signe"], par=par, permissions=e["permissions"], sauvegarde=sauve)
        chemin.unlink(missing_ok=True)
        return {"id": mid, "version": v["version"], "ancienne": e["version_en_place"], "statut": e["statut"], "sauvegarde": str(sauve) if sauve else ""}

    def _archive(self, jeton: str) -> Path:
        if not jeton or not all(c in "0123456789abcdef" for c in jeton):
            raise CycleErreur("jeton d'archive invalide")
        chemin = self.quarantaine / (jeton + ".cmod")
        if not chemin.is_file():
            raise CycleErreur("archive introuvable en quarantaine : elle a expiré, déposez-la de nouveau")
        return chemin

    def abandonner(self, jeton: str) -> None:
        """L'archive quitte la quarantaine pour une corbeille (elle peut revenir : `restaurer`) ; la corbeille se vide avec le temps."""
        src = self._archive(jeton)
        corbeille = self.quarantaine / "corbeille"
        corbeille.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(corbeille / src.name))

    def restaurer(self, jeton: str) -> None:
        if not jeton or not all(c in "0123456789abcdef" for c in jeton):
            raise CycleErreur("jeton d'archive invalide")
        src = self.quarantaine / "corbeille" / (jeton + ".cmod")
        if not src.is_file():
            raise CycleErreur("archive introuvable dans la corbeille")
        shutil.move(str(src), str(self.quarantaine / src.name))

    def purger_quarantaine(self, age_s: int = 86400) -> int:
        """Les archives examinées mais jamais installées s'effacent après un jour."""
        n = 0
        if self.quarantaine.is_dir():
            for f in list(self.quarantaine.glob("*.cmod")) + list((self.quarantaine / "corbeille").glob("*.cmod")):
                if time.time() - f.stat().st_mtime > age_s:
                    f.unlink(missing_ok=True)
                    n += 1
        return n

    # ------------------------------------------------------------------ sauvegardes
    def _sauvegarder(self, dossier: Path, mid: str, version: str, raison: str) -> Path:
        dest = self.sauvegardes / mid / ("%d__%s__%s" % (int(time.time() * 1000), version or "inconnue", raison))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dossier, dest)
        return dest

    def versions(self, mid: str) -> dict:
        """Les versions qu'on peut remettre (les sauvegardes, la plus récente d'abord) et ce qui s'est passé pour ce module."""
        sauv = []
        base = self.sauvegardes / mid
        if base.is_dir():
            for d in sorted(base.iterdir(), reverse=True):
                parts = d.name.split("__")
                if len(parts) == 3 and d.is_dir():
                    sauv.append({"cle": d.name, "ts": int(parts[0]) / 1000.0, "version": parts[1], "raison": parts[2]})
        return {"id": mid, "sauvegardes": sauv, "journal": [x for x in self.journal() if x.get("id") == mid][-30:]}

    def _extension(self, mid: str):
        if not self.extensions:
            raise CycleErreur("pas de dossier d'extensions sur cette instance")
        connus = {x.id: ext for x, ext in self.connus()}
        if mid in connus and not connus[mid]:
            raise CycleErreur("« %s » est livré avec le noyau : il ne se désinstalle pas ni ne revient en arrière" % mid)
        return self.extensions / mid

    def retour_arriere(self, mid: str, cle: str = "", par: str = "") -> dict:
        cible = self._extension(mid)
        l = self.versions(mid)["sauvegardes"]
        if cle:
            l = [x for x in l if x["cle"] == cle]
        if not l:
            raise CycleErreur("aucune sauvegarde de « %s » à remettre" % mid)
        choix = l[0]
        src = self.sauvegardes / mid / choix["cle"]
        ancienne = ""
        if cible.exists():
            try:
                ancienne = mf.charger(cible / "CN_manifeste.toml").version
            except Exception:  # noqa: BLE001
                ancienne = "inconnue"
            self._sauvegarder(cible, mid, ancienne, "retour")
            shutil.rmtree(cible)
        shutil.copytree(src, cible)
        m = mf.charger(cible / "CN_manifeste.toml")
        self._noter(acte="retour", id=mid, version=m.version, ancienne=ancienne, par=par, permissions=permissions_de(m))
        return {"id": mid, "version": m.version, "ancienne": ancienne}

    def desinstaller(self, mid: str, par: str = "") -> dict:
        cible = self._extension(mid)
        if mid in self.actifs():
            raise CycleErreur("« %s » est actif : désactivez-le d'abord" % mid)
        if not cible.exists():
            raise CycleErreur("« %s » n'est pas installé par archive" % mid)
        try:
            version = mf.charger(cible / "CN_manifeste.toml").version
        except Exception:  # noqa: BLE001
            version = "inconnue"
        sauve = self._sauvegarder(cible, mid, version, "desinstalle")
        shutil.rmtree(cible)
        self._noter(acte="desinstalle", id=mid, version=version, par=par, sauvegarde=sauve)
        return {"id": mid, "version": version, "sauvegarde": str(sauve)}

    def purger_donnees(self, mid: str, par: str = "") -> dict:
        """Les données d'un module désinstallé (donnees/modules/<id>.db) partent à leur tour en sauvegarde. Refusé tant que le module est présent."""
        if any(x.id == mid for x, _ in self.connus()):
            raise CycleErreur("« %s » est encore présent : désinstallez-le d'abord" % mid)
        base = self.donnees / "modules" / (mid + ".db")
        if not base.exists():
            return {"id": mid, "purge": False}
        dest = self.sauvegardes / mid / ("%d__donnees__purge" % int(time.time() * 1000))
        dest.mkdir(parents=True, exist_ok=True)
        for suffixe in ("", "-wal", "-shm"):
            f = base.with_name(base.name + suffixe)
            if f.exists():
                shutil.move(str(f), str(dest / f.name))
        self._noter(acte="purge", id=mid, par=par, sauvegarde=dest)
        return {"id": mid, "purge": True, "sauvegarde": str(dest)}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Cycle (examiner, installer, retour_arriere, desinstaller, purger_donnees, versions), permissions_de, elargies.
# EC : néant.
# LIEN : noyau/CN_paquets.py (la vérification de l'archive), noyau/CN_manifeste.py (le manifeste), modules/modules/CN_module.py (les capacités), tests/CN_test_cycle.py.
