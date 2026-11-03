# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le coffre Vaultwarden
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : coffre
# ZONE       : CN
# VERSION CN : 0.2.0  #5fcc93
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le coffre Vaultwarden : le magasin de secrets de Cassandra.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=5fcc93 ▼▼▼
"""Le coffre Vaultwarden : le magasin de secrets de Cassandra.

Chaque compte ne voit QUE ses espaces : le sien (« u:<compte> »), puis ceux de société où on l'a fait entrer (« s:<société> »)
avec un rôle (admin | membre | contrib | lecture), des collections et une date de fin facultative. Aucun passe-droit : ni l'administrateur
de l'instance, ni Cassandra, ni l'administrateur d'une société ne lit un espace dont il n'est pas membre. Un secret garde son auteur
(le rôle « contrib » ne relit que les siens). Le serveur Vaultwarden n'a qu'une session : l'isolement est ici, dans ce module.

Porté de la V18 (`vault_*`, `_vault_req`), avec ses leçons :
  - `list` ne rend JAMAIS les valeurs, seulement les noms ;
  - `get` ne lève jamais (un secret absent rend rien, pas une panne) ;
  - `set` est idempotent et réversible : l'ancienne valeur revient, un secret neuf repart ;
  - le dernier échec est gardé un court instant et rendu tel quel (ne pas marteler un coffre verrouillé
    jusqu'au « Too many login requests »).

Les fiches typées (identifiant, note, carte) sont des documents JSON marqués rangés dans la note sécurisée : l'application Bitwarden ne les verra pas comme des identifiants.
Différé proprement : le provisionnement des comptes (compte Cassandra = compte Vault natif) et les clés d'API personnelles (une seule session sert tous les espaces).
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8088"      # bw serve (le service du coffre) ; Vaultwarden lui-même écoute sur 8087


ROLES = ("admin", "membre", "contrib", "lecture")


def brancher(ctx):
    db = ctx.stockage

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def url() -> str:
        u = reglage("vault_url", "")
        return (u or DEFAULT_URL).rstrip("/")

    def delai() -> int:
        try:
            return max(1, min(int(reglage("vault_timeout", 8)), 60))
        except Exception:
            return 8

    def base_de(esp):
        """Le serveur Vaultwarden d'un espace : celui de l'instance, ou — pour un espace de société déclaré « externe » — le sien (son adresse, fixée par l'administrateur de l'instance)."""
        if str(esp).startswith("s:"):
            e = db.lire("SELECT mode, url FROM vault_espaces WHERE id=?", (esp,))
            if e and e[0]["mode"] == "externe" and e[0]["url"]:
                return str(e[0]["url"]).rstrip("/")
        return url()

    def _req(method, path, body=None, base=None):
        """Un appel au coffre. Ne lève jamais : l'échec est un dict, pas une panne."""
        cible = (base or url()) + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(cible, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=delai()) as r:
                raw = r.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8", "replace"))
            except Exception:
                return {"success": False, "error": "HTTP %s" % e.code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _audit(action, secret, espace=""):
        try:
            db.ecrire("INSERT INTO vault_audit (username, action, secret_name, espace, acteur) VALUES (?,?,?,?,?)",
                      ((ctx.compte or "").strip()[:80], action, str(secret or "")[:200], str(espace or "")[:80], str(ctx.acteur or "")[:40]))
        except Exception:
            pass

    def _emettre(type, espace, donnees):
        try:
            ctx.emettre(type, objet=("espace", espace), donnees=donnees)
        except Exception:
            pass

    # ── à qui est ce coffre ──────────────────────────────────────────────────
    # Un compte ne voit que ses espaces : le sien, puis ceux où on l'a fait entrer. Aucun passe-droit : ni l'administrateur de l'instance,
    # ni Cassandra, ni un administrateur de société ne lit un espace dont il n'est pas membre. Un refus ne dit jamais si l'espace existe.
    REFUS = "accès refusé : cet espace n'est pas le vôtre, ou ce secret ne vous est pas ouvert"

    def _aujourdhui() -> str:
        return datetime.date.today().isoformat()

    def _perso(compte) -> str:
        return "u:" + compte

    def _espace(compte, espace) -> str:
        e = str(espace or "").strip()
        if not compte:
            raise ValueError("aucun compte n'agit : le coffre est toujours au nom de quelqu'un")
        return e or _perso(compte)

    def _acces(compte, esp):
        """La ligne d'accès de ce compte à cet espace (un dict avec « role »), ou None."""
        if not compte:
            return None
        if esp.startswith("u:"):
            return {"role": "proprio", "collections": "*", "expire": ""} if esp == _perso(compte) else None
        e = db.lire("SELECT archive FROM vault_espaces WHERE id=?", (esp,))
        if not e or e[0]["archive"]:
            return None
        m = db.lire("SELECT * FROM vault_membres WHERE espace=? AND compte=?", (esp, compte))
        if not m:
            return None
        if m[0]["expire"] and m[0]["expire"] < _aujourdhui():
            return None
        return m[0]

    def _collection_ouverte(m, collection) -> bool:
        cols = str(m.get("collections") or "")
        if cols == "*":
            return True
        return bool(collection) and collection in [x.strip() for x in cols.split(",") if x.strip()]

    def _peut(m, action, meta, collection, compte) -> bool:
        """Ce rôle peut-il lire / écrire / gérer ce secret ? (meta = ce qu'on sait du secret existant, ou None)."""
        role = m["role"]
        if role == "proprio":
            return True
        if action == "gerer":
            return role == "admin"
        col = meta["collection"] if meta else collection
        if role == "contrib":
            if action == "lire":
                return bool(meta) and meta["auteur"] == compte
            return _collection_ouverte(m, col) and (not meta or meta["auteur"] == compte)
        if role == "lecture":
            return action == "lire" and _collection_ouverte(m, col)
        if role in ("admin", "membre"):
            return _collection_ouverte(m, col)
        return False

    def _meta(esp, nom):
        r = db.lire("SELECT * FROM vault_secrets WHERE espace=? AND nom=?", (esp, nom))
        return r[0] if r else None

    def _exiger_ouvert(esp=""):
        s = _etat(base_de(esp) if esp else None)
        if not (s.get("available") and s.get("status") == "unlocked"):
            raise ValueError("coffre indisponible ou verrouillé")

    # ── le serveur Vaultwarden : un nom physique par espace et par secret ────
    def _phys(esp, nom) -> str:
        return esp + "::" + nom

    def _find(phys):
        r = _req("GET", "/list/object/items?search=" + urllib.parse.quote(str(phys)), base=base_de(str(phys).split("::", 1)[0]))
        items = ((r.get("data") or {}).get("data")) or []
        for it in items:
            if it.get("name") == phys:
                return it
        return None

    def _lire_brut(esp, nom):
        it = _find(_phys(esp, nom))
        return it.get("notes") if it else None

    def _poser_brut(esp, nom, valeur):
        phys = _phys(esp, nom)
        it = _find(phys)
        if it:
            it["notes"] = valeur
            r = _req("PUT", "/object/item/%s" % it["id"], it, base=base_de(esp))
        else:
            r = _req("POST", "/object/item", {"type": 2, "name": phys, "notes": valeur, "secureNote": {"type": 0}, "fields": []}, base=base_de(esp))
        if not r.get("success"):
            raise ValueError(r.get("error") or "échec écriture coffre")

    def _effacer_brut(esp, nom):
        it = _find(_phys(esp, nom))
        if it:
            _req("DELETE", "/object/item/%s" % it["id"], base=base_de(esp))

    def _nom(name) -> str:
        n = str(name or "").strip()
        if not n:
            raise ValueError("nom requis")
        if len(n) > 200:
            raise ValueError("nom : 200 caractères au plus")
        return n

    # ── lectures ─────────────────────────────────────────────────────────────
    def _etat(base=None):
        r = _req("GET", "/status", base=base)
        t = (r.get("data") or {}).get("template") or {}
        return {"available": bool(r.get("success")), "status": t.get("status"),
                "email": t.get("userEmail"), "server": t.get("serverUrl"), "error": r.get("error")}

    def status(c, espace=""):
        """L'état du serveur de coffre : celui de l'instance, ou celui de l'espace demandé (un coffre externe a le sien)."""
        if not espace:
            return _etat()
        esp = _espace(ctx.compte, espace)
        if _acces(ctx.compte, esp) is None:
            raise ValueError(REFUS)
        return dict(_etat(base_de(esp)), espace=esp, externe=base_de(esp) != url())

    def available(c):
        s = status(c)
        return {"disponible": bool(s.get("available")) and s.get("status") == "unlocked"}

    def lire(c, name="", espace=""):
        nom = _nom(name)
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        meta = _meta(esp, nom)
        if not meta or not _peut(m, "lire", meta, "", ctx.compte):
            return {"valeur": None, "espace": esp}          # un secret qu'on ne peut pas lire est, pour soi, un secret absent
        _audit("lire", nom, esp)
        return {"valeur": _lire_brut(esp, nom), "espace": esp}

    def lister(c, prefix="", espace=""):
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        rows = db.lire("SELECT nom, auteur, collection, fiche, cree, maj FROM vault_secrets WHERE espace=? ORDER BY nom", (esp,))
        vus = [r for r in rows if _peut(m, "lire", r, "", ctx.compte) and (not prefix or r["nom"].startswith(prefix))]
        return {"noms": [r["nom"] for r in vus], "secrets": vus, "espace": esp, "role": m["role"]}

    def journal(c, limite=50, espace=""):
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        n = max(1, min(int(limite or 50), 500))
        if m["role"] in ("proprio", "admin"):
            rows = db.lire("SELECT * FROM vault_audit WHERE espace=? ORDER BY id DESC LIMIT ?", (esp, n))
        else:                                              # un membre ordinaire ne lit que ses propres gestes
            rows = db.lire("SELECT * FROM vault_audit WHERE espace=? AND username=? ORDER BY id DESC LIMIT ?", (esp, ctx.compte, n))
        return {"journal": rows, "espace": esp}

    def espaces(c):
        compte = ctx.compte
        if not compte:
            raise ValueError("aucun compte n'agit : le coffre est toujours au nom de quelqu'un")
        out = []
        perso = _perso(compte)
        n = db.lire("SELECT COUNT(*) AS n FROM vault_secrets WHERE espace=?", (perso,))[0]["n"]
        out.append({"id": perso, "genre": "perso", "nom": "Mon coffre", "role": "proprio", "secrets": n, "collections": "*", "expire": "", "admins": None})
        for m in db.lire("SELECT m.*, e.nom AS nom_espace, e.mode AS mode, e.url AS url_espace FROM vault_membres m JOIN vault_espaces e ON e.id=m.espace WHERE m.compte=? AND e.archive=0 ORDER BY e.nom", (compte,)):
            if m["expire"] and m["expire"] < _aujourdhui():
                continue
            rows = db.lire("SELECT nom, auteur, collection FROM vault_secrets WHERE espace=?", (m["espace"],))
            vus = sum(1 for r in rows if _peut(m, "lire", r, "", compte))
            admins = None
            if m["role"] == "admin":
                admins = db.lire("SELECT COUNT(*) AS n FROM vault_membres WHERE espace=? AND role='admin' AND (expire='' OR expire>=?)", (m["espace"], _aujourdhui()))[0]["n"]
            out.append({"id": m["espace"], "genre": "societe", "nom": m["nom_espace"] or m["espace"], "role": m["role"], "secrets": vus,
                        "collections": m["collections"], "expire": m["expire"], "mode": m["mode"], "admins": admins,
                        "url": m["url_espace"] if (m["role"] == "admin" and m["mode"] == "externe") else ""})          # l'adresse interne d'un serveur : à ses administrateurs seulement
        return {"espaces": out}

    def membres(c, espace=""):
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None or not _peut(m, "gerer", None, "", ctx.compte):
            raise ValueError(REFUS)
        if esp.startswith("u:"):
            raise ValueError("un coffre personnel n'a pas de membres")
        rows = db.lire("SELECT compte, role, collections, expire, accorde_par, cree FROM vault_membres WHERE espace=? ORDER BY role, compte", (esp,))
        return {"espace": esp, "membres": rows, "admins": sum(1 for r in rows if r["role"] == "admin" and (not r["expire"] or r["expire"] >= _aujourdhui()))}

    # ── écritures réversibles ────────────────────────────────────────────────
    def poser(c, name="", valeur="", espace="", collection=""):
        nom = _nom(name)
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        meta = _meta(esp, nom)
        col = str(collection or "").strip() or (meta["collection"] if meta else "")
        if not _peut(m, "ecrire", meta, col, ctx.compte):
            raise ValueError(REFUS)
        _exiger_ouvert(esp)
        avant = _lire_brut(esp, nom)
        _poser_brut(esp, nom, valeur)
        db.ecrire("INSERT INTO vault_secrets (espace, nom, auteur, collection) VALUES (?,?,?,?) "
                  "ON CONFLICT(espace, nom) DO UPDATE SET collection=excluded.collection, maj=datetime('now'), fiche=''", (esp, nom, ctx.compte, col))
        _audit("ecrire", nom, esp)
        return {"name": nom, "espace": esp, "avant": avant, "apres": valeur, "meta_avant": meta, "collection": col}

    def prouver_set(c, res):
        return _lire_brut(res["espace"], res["name"]) == res["apres"]

    def _remettre_meta(esp, nom, meta):
        db.ecrire("DELETE FROM vault_secrets WHERE espace=? AND nom=?", (esp, nom))
        if meta:
            db.ecrire("INSERT INTO vault_secrets (espace, nom, auteur, collection, cree, maj) VALUES (?,?,?,?,?,?)",
                      (esp, nom, meta["auteur"], meta["collection"], meta["cree"], meta["maj"]))

    def defaire_set(c, res):
        # l'acte a déjà été autorisé : on remet l'état d'avant, sans redemander qui a le droit
        if res.get("avant") is None:
            _effacer_brut(res["espace"], res["name"])
        else:
            _poser_brut(res["espace"], res["name"], res["avant"])
        _remettre_meta(res["espace"], res["name"], res.get("meta_avant"))

    def delete(c, name="", espace=""):
        nom = _nom(name)
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        meta = _meta(esp, nom)
        if meta and not _peut(m, "ecrire", meta, meta["collection"], ctx.compte):
            raise ValueError(REFUS)
        avant = _lire_brut(esp, nom) if meta else None
        if meta:
            _effacer_brut(esp, nom)
            db.ecrire("DELETE FROM vault_secrets WHERE espace=? AND nom=?", (esp, nom))
        _audit("retirer", nom, esp)
        return {"name": nom, "espace": esp, "avant": avant, "meta_avant": meta}

    def prouver_delete(c, res):
        return _meta(res["espace"], res["name"]) is None and _lire_brut(res["espace"], res["name"]) is None

    def defaire_delete(c, res):
        if res.get("avant") is not None:
            _poser_brut(res["espace"], res["name"], res["avant"])
            _remettre_meta(res["espace"], res["name"], res.get("meta_avant"))

    # ── les espaces de société et leurs membres ──────────────────────────────
    def _admins_actifs(esp, sauf=""):
        return db.lire("SELECT COUNT(*) AS n FROM vault_membres WHERE espace=? AND role='admin' AND compte<>? AND (expire='' OR expire>=?)",
                       (esp, sauf, _aujourdhui()))[0]["n"]

    def _exiger_gerer(esp):
        m = _acces(ctx.compte, esp)
        if m is None or not _peut(m, "gerer", None, "", ctx.compte):
            raise ValueError(REFUS)
        if esp.startswith("u:"):
            raise ValueError("un coffre personnel n'a pas de membres")

    def _collections(role, collections):
        if collections is None:
            return "" if role == "admin" else "*"
        c = str(collections).strip()
        if c in ("", "*"):
            return c
        return ",".join(x.strip() for x in c.split(",") if x.strip())

    def accorder(c, espace="", utilisateur="", role="membre", collections=None, expire=""):
        esp = _espace(ctx.compte, espace)
        _exiger_gerer(esp)
        cible = str(utilisateur or "").strip().lower()
        if not cible:
            raise ValueError("utilisateur requis")
        if role not in ROLES:
            raise ValueError("rôle : %s" % " | ".join(ROLES))
        exp = str(expire or "").strip()
        if exp:
            try:
                datetime.date.fromisoformat(exp)
            except ValueError:
                raise ValueError("expire : une date AAAA-MM-JJ, ou rien")
        avant = db.lire("SELECT * FROM vault_membres WHERE espace=? AND compte=?", (esp, cible))
        avant = avant[0] if avant else None
        if avant and avant["role"] == "admin" and role != "admin" and _admins_actifs(esp, sauf=cible) < 1:
            raise ValueError("le dernier administrateur du coffre ne change pas de rôle : nommez-en un autre d'abord")
        cols = _collections(role, collections)
        db.ecrire("INSERT INTO vault_membres (espace, compte, role, collections, expire, accorde_par) VALUES (?,?,?,?,?,?) "
                  "ON CONFLICT(espace, compte) DO UPDATE SET role=excluded.role, collections=excluded.collections, expire=excluded.expire, accorde_par=excluded.accorde_par",
                  (esp, cible, role, cols, exp, ctx.compte))
        _audit("accorder:%s:%s" % (cible, role), "", esp)
        _emettre("espace.acces_accorde", esp, {"compte": cible, "role": role, "collections": cols, "expire": exp})
        return {"espace": esp, "compte": cible, "role": role, "collections": cols, "expire": exp, "avant": avant}

    def prouver_accorder(c, res):
        r = db.lire("SELECT role, collections, expire FROM vault_membres WHERE espace=? AND compte=?", (res["espace"], res["compte"]))
        return bool(r) and (r[0]["role"], r[0]["collections"], r[0]["expire"]) == (res["role"], res["collections"], res["expire"])

    def _remettre_membre(res):
        db.ecrire("DELETE FROM vault_membres WHERE espace=? AND compte=?", (res["espace"], res["compte"]))
        a = res.get("avant")
        if a:
            db.ecrire("INSERT INTO vault_membres (espace, compte, role, collections, expire, accorde_par, cree) VALUES (?,?,?,?,?,?,?)",
                      (a["espace"], a["compte"], a["role"], a["collections"], a["expire"], a["accorde_par"], a["cree"]))

    def defaire_accorder(c, res):
        _remettre_membre(res)

    def retirer(c, espace="", utilisateur=""):
        esp = _espace(ctx.compte, espace)
        _exiger_gerer(esp)
        cible = str(utilisateur or "").strip().lower()
        avant = db.lire("SELECT * FROM vault_membres WHERE espace=? AND compte=?", (esp, cible))
        if not avant:
            raise ValueError("ce compte n'a pas accès à cet espace")
        avant = avant[0]
        if avant["role"] == "admin" and _admins_actifs(esp, sauf=cible) < 1:
            raise ValueError("le dernier administrateur du coffre ne part pas : nommez-en un autre d'abord")
        db.ecrire("DELETE FROM vault_membres WHERE espace=? AND compte=?", (esp, cible))
        _audit("retirer_acces:%s" % cible, "", esp)
        _emettre("espace.acces_retire", esp, {"compte": cible})
        return {"espace": esp, "compte": cible, "avant": avant}

    def prouver_retirer(c, res):
        return not db.lire("SELECT 1 FROM vault_membres WHERE espace=? AND compte=?", (res["espace"], res["compte"]))

    def defaire_retirer(c, res):
        _remettre_membre(res)

    def adresse_externe(u):
        """Une adresse http(s) d'un serveur `bw serve`, sans identifiants ni fragment ; jamais l'adresse des métadonnées d'un hébergeur (169.254.x.x)."""
        p = urllib.parse.urlsplit(u)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("un coffre externe a une adresse http(s)")
        if p.username or p.password or p.fragment or p.query:
            raise ValueError("l'adresse d'un coffre externe ne porte ni identifiants, ni paramètres, ni ancre")
        if p.hostname.startswith("169.254."):
            raise ValueError("adresse refusée : celle d'un service de métadonnées")
        return "%s://%s%s" % (p.scheme, p.netloc, p.path.rstrip("/"))

    def regler(c, espace="", mode="interne", url=""):
        esp = _espace(ctx.compte, espace)
        _exiger_gerer(esp)
        if mode not in ("interne", "externe"):
            raise ValueError("mode : interne | externe")
        u = str(url or "").strip()
        if mode == "externe":
            if not ctx.est_admin(ctx.compte):
                raise ValueError("seul l'administrateur de l'instance branche un coffre externe : l'instance appelle cette adresse depuis son réseau")
            u = adresse_externe(u)
        avant = db.lire("SELECT mode, url FROM vault_espaces WHERE id=?", (esp,))[0]
        db.ecrire("UPDATE vault_espaces SET mode=?, url=? WHERE id=?", (mode, u if mode == "externe" else "", esp))
        _audit("regler:%s" % mode, "", esp)
        return {"espace": esp, "mode": mode, "url": u, "avant": avant}

    def prouver_regler(c, res):
        r = db.lire("SELECT mode FROM vault_espaces WHERE id=?", (res["espace"],))
        return bool(r) and r[0]["mode"] == res["mode"]

    def defaire_regler(c, res):
        db.ecrire("UPDATE vault_espaces SET mode=?, url=? WHERE id=?", (res["avant"]["mode"], res["avant"]["url"], res["espace"]))

    def espace_creer(c, societe="", nom="", admin=""):
        sid = str(societe or "").strip()
        if not sid:
            raise ValueError("société requise")
        esp = "s:" + sid
        premier = str(admin or ctx.compte or "").strip().lower()
        if not premier:
            raise ValueError("un premier administrateur est requis")
        deja = db.lire("SELECT * FROM vault_espaces WHERE id=?", (esp,))
        if deja:
            db.ecrire("UPDATE vault_espaces SET archive=0, nom=CASE WHEN ?<>'' THEN ? ELSE nom END WHERE id=?", (nom, nom, esp))
        else:
            db.ecrire("INSERT INTO vault_espaces (id, genre, nom) VALUES (?,?,?)", (esp, "societe", str(nom or "").strip()[:120]))
        if not db.lire("SELECT 1 FROM vault_membres WHERE espace=? AND compte=?", (esp, premier)):
            db.ecrire("INSERT INTO vault_membres (espace, compte, role, collections, accorde_par) VALUES (?,?,?,?,?)", (esp, premier, "admin", "", ctx.compte))
        _audit("espace_creer", "", esp)
        _emettre("espace.cree", esp, {"societe": sid, "admin": premier})
        return {"espace": esp, "cree": not deja, "avant": deja[0] if deja else None, "admin": premier}

    def prouver_creer(c, res):
        r = db.lire("SELECT archive FROM vault_espaces WHERE id=?", (res["espace"],))
        return bool(r) and r[0]["archive"] == 0

    def defaire_creer(c, res):
        if res.get("cree"):
            db.ecrire("DELETE FROM vault_membres WHERE espace=?", (res["espace"],))
            db.ecrire("DELETE FROM vault_espaces WHERE id=?", (res["espace"],))
        elif res.get("avant"):
            db.ecrire("UPDATE vault_espaces SET archive=?, nom=? WHERE id=?", (res["avant"]["archive"], res["avant"]["nom"], res["espace"]))

    def espace_archiver(c, espace=""):
        esp = str(espace or "").strip()
        r = db.lire("SELECT archive FROM vault_espaces WHERE id=?", (esp,))
        if not r:
            raise ValueError("espace inconnu")
        db.ecrire("UPDATE vault_espaces SET archive=1 WHERE id=?", (esp,))
        _audit("espace_archiver", "", esp)
        _emettre("espace.archive", esp, {})
        return {"espace": esp, "avant": r[0]["archive"]}

    def prouver_archiver(c, res):
        r = db.lire("SELECT archive FROM vault_espaces WHERE id=?", (res["espace"],))
        return bool(r) and r[0]["archive"] == 1

    def defaire_archiver(c, res):
        db.ecrire("UPDATE vault_espaces SET archive=? WHERE id=?", (res["avant"], res["espace"]))

    def depart(compte):
        """Un compte désactivé ou supprimé ne garde aucun accès aux espaces de société. Son coffre personnel reste intact. Le dernier administrateur d'un espace ne part pas
        (l'espace resterait sans maître) : on le dit au journal du coffre, et un autre administrateur doit être nommé."""
        compte = str(compte or "").strip().lower()
        if not compte:
            return
        for m in db.lire("SELECT espace, role FROM vault_membres WHERE compte=? AND espace LIKE 's:%'", (compte,)):
            if m["role"] == "admin" and _admins_actifs(m["espace"], sauf=compte) < 1:
                _audit("depart_bloque:%s" % compte, "", m["espace"])
                continue
            db.ecrire("DELETE FROM vault_membres WHERE espace=? AND compte=?", (m["espace"], compte))
            _audit("depart:%s" % compte, "", m["espace"])
            _emettre("espace.acces_retire", m["espace"], {"compte": compte, "motif": "départ"})

    def espaces_societes(ctx2, ev):
        if ev.get("type") in ("compte.desactive", "compte.supprime"):
            depart(ev.get("objet_id") or (ev.get("donnees") or {}).get("compte"))
            return
        d = ev.get("donnees") or {}
        soc = str(d.get("societe") or "").strip()
        if not soc:
            return
        if ev.get("type") == "societe.creee":
            if d.get("administrateur"):
                espace_creer(None, societe=soc, nom=d.get("nom", ""), admin=d["administrateur"])
        elif ev.get("type") == "societe.archivee":
            if db.lire("SELECT 1 FROM vault_espaces WHERE id=?", ("s:" + soc,)):
                espace_archiver(None, espace="s:" + soc)

    # ── les fiches typées (identifiant, note, carte) : le même secret, sa valeur est alors un document JSON marqué ; ce qu'on peut AFFICHER sans l'ouvrir va dans `fiche` ─────
    GENRES = ("login", "note", "card")
    MARQUE = "cn_fiche"
    CHAMPS_FICHE = ("username", "password", "uri", "totp", "notes", "value", "contexte", "card_name", "card_number", "card_exp", "card_cvv", "card_brand")

    def decoder(valeur):
        """Le document d'une fiche typée, ou None si la valeur est un texte simple (une note)."""
        try:
            d = json.loads(valeur) if isinstance(valeur, str) and valeur.startswith("{") else None
        except ValueError:
            return None
        return d if isinstance(d, dict) and d.get(MARQUE) == 1 else None

    def vue_fiche(nom, valeur, meta=None):
        """Ce qu'une fiche montre : le document ouvert, ou une note simple."""
        d = decoder(valeur)
        if d is None:
            return {"name": nom, "kind": "note", "value": valeur or "", "notes": "", "fields": [], "contexte": "", "favorite": False, "agent": False, "totp": ""}
        sortie = {k: v for k, v in d.items() if k != MARQUE}
        sortie["name"] = nom
        sortie.setdefault("kind", "login")
        sortie.setdefault("fields", [])
        return sortie

    def meta_fiche(d):
        return json.dumps({"kind": d.get("kind", "login"), "username": str(d.get("username") or "")[:200], "uri": str(d.get("uri") or "")[:300], "favorite": bool(d.get("favorite")),
                           "totp": bool(d.get("totp")), "champs": len(d.get("fields") or []), "agent": bool(d.get("agent")), "mdp_maj": d.get("mdp_maj", "")}, ensure_ascii=False)

    def cible(name, espace, action):
        nom = _nom(name)
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        meta = _meta(esp, nom)
        if action == "lire":
            if not meta or not _peut(m, "lire", meta, "", ctx.compte):
                return nom, esp, m, None
        elif not _peut(m, "ecrire", meta, meta["collection"] if meta else "", ctx.compte):
            raise ValueError(REFUS)
        return nom, esp, m, meta

    def fiche(c, name="", espace="", motif="fiche"):
        """La fiche d'un secret, valeurs comprises, pour la personne qui l'ouvre : l'ouverture s'inscrit au journal. Les anciens mots de passe ne sortent pas d'ici (voir `historique`)."""
        nom, esp, m, meta = cible(name, espace, "lire")
        if meta is None:
            return {"detail": None, "espace": esp}
        _exiger_ouvert(esp)
        valeur = _lire_brut(esp, nom)
        if valeur is None:
            return {"detail": None, "espace": esp}
        _audit("fiche" if motif == "fiche" else "reveal", nom, esp)
        d = vue_fiche(nom, valeur, meta)
        d["historique_n"] = db.lire("SELECT COUNT(*) AS n FROM vault_historique WHERE espace=? AND nom=?", (esp, nom))[0]["n"]
        d["doublons"] = []
        if d["kind"] == "login" and d.get("password"):
            for r in db.lire("SELECT nom, fiche FROM vault_secrets WHERE espace=? AND nom<>? AND fiche LIKE '%\"login\"%' LIMIT 60", (esp, nom)):
                autre = decoder(_lire_brut(esp, r["nom"]) or "")
                if autre and autre.get("password") == d["password"]:
                    d["doublons"].append(r["nom"])
        return {"detail": d, "espace": esp}

    def valider_valeurs(kind, v):
        v = dict(v or {})
        champs = []
        for f in (v.get("fields") or []):
            if isinstance(f, dict) and str(f.get("name") or "").strip():
                champs.append({"name": str(f["name"]).strip()[:100], "value": str(f.get("value") or "")[:2000], "type": int(f.get("type") or 0) if str(f.get("type") or 0).isdigit() else 0})
        doc = {MARQUE: 1, "kind": kind, "fields": champs[:40], "favorite": bool(v.get("favorite")), "agent": bool(v.get("agent"))}
        for k in CHAMPS_FICHE:
            if k in v:
                doc[k] = str(v.get(k) or "")[:20000]
        return doc

    def historiser(esp, nom, ancien):
        """Un mot de passe remplacé n'est pas perdu : il est gardé chiffré, daté, relisible à la demande (et inscrit au journal)."""
        return db.ecrire("INSERT INTO vault_historique(espace, nom, ts, valeur_chiffree) VALUES(?,?,datetime('now'),?)", (esp, nom, ctx.chiffrer(ancien, "historique:%s:%s" % (esp, nom))))

    def fiche_ecrire(c, name="", kind="login", valeurs=None, patch=None, creer=False, espace=""):
        """Créer une fiche (identifiant, note ou carte), ou la modifier sans rien perdre : `patch` ne porte que ce qui change, y compris le nom."""
        nom, esp, m, meta = cible(name, espace, "ecrire")
        _exiger_ouvert(esp)
        avant = _lire_brut(esp, nom) if meta else None
        if creer:
            if meta:
                raise ValueError("un secret porte déjà ce nom")
            kind = str(kind or "login").strip().lower()
            if kind not in GENRES:
                raise ValueError("genre : %s" % " | ".join(GENRES))
            v = dict(valeurs or {})
            if str(v.get("contexte") or "").strip() and kind == "note":
                pass
            doc = valider_valeurs(kind, v)
            if kind == "login" and doc.get("password"):
                doc["mdp_maj"] = _aujourdhui()
            nouveau_nom = nom
        else:
            if not meta or avant is None:
                raise ValueError("secret introuvable")
            p = dict(patch or {})
            if not p:
                raise ValueError("rien à modifier")
            actuel = vue_fiche(nom, avant)
            nouveau_nom = str(p.pop("name", nom) or "").strip()
            if not nouveau_nom:
                raise ValueError("le nom ne peut pas être vide")
            if nouveau_nom != nom and _meta(esp, nouveau_nom):
                raise ValueError("un secret porte déjà ce nom")
            actuel.pop("name", None)
            actuel.update({k: v for k, v in p.items() if k in CHAMPS_FICHE or k in ("fields", "favorite", "agent")})
            kind = actuel.get("kind", "note")
            if kind == "note" and decoder(avant) is None:
                # une note simple modifiée reste un texte simple tant qu'elle n'a ni champ ni drapeau
                simple = actuel.get("value", "") if "value" in p or not p.get("notes") else p.get("notes")
                if not actuel.get("fields") and not actuel.get("favorite") and not actuel.get("agent") and not str(actuel.get("contexte") or ""):
                    doc = None
                else:
                    doc = valider_valeurs("note", dict(actuel, value=simple))
            else:
                doc = valider_valeurs(kind, actuel)
            if doc is not None and kind == "login":
                ancien = vue_fiche(nom, avant)
                if "password" in p and str(p.get("password") or "") != str(ancien.get("password") or ""):
                    if ancien.get("password"):
                        historiser(esp, nouveau_nom, ancien["password"])
                    doc["mdp_maj"] = _aujourdhui()
                else:
                    doc["mdp_maj"] = ancien.get("mdp_maj", "")
        apres = json.dumps(doc, ensure_ascii=False) if doc is not None else str(actuel.get("value", "") if not creer else "")
        _poser_brut(esp, nouveau_nom, apres)
        if nouveau_nom != nom:
            _effacer_brut(esp, nom)
            db.ecrire("DELETE FROM vault_secrets WHERE espace=? AND nom=?", (esp, nom))
            db.ecrire("UPDATE vault_historique SET nom=? WHERE espace=? AND nom=?", (nouveau_nom, esp, nom))
        col = meta["collection"] if meta else ""
        db.ecrire("INSERT INTO vault_secrets (espace, nom, auteur, collection, fiche) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(espace, nom) DO UPDATE SET maj=datetime('now'), fiche=excluded.fiche", (esp, nouveau_nom, meta["auteur"] if meta else ctx.compte, col, meta_fiche(doc) if doc is not None else ""))
        _audit("creer" if creer else "update", nom + ((" → " + nouveau_nom) if nouveau_nom != nom else ""), esp)
        return {"name": nouveau_nom, "ancien_nom": nom, "espace": esp, "avant": avant, "apres": apres, "meta_avant": meta, "cree": bool(creer)}

    def prouver_fiche(c, res):
        return _lire_brut(res["espace"], res["name"]) == res["apres"]

    def defaire_fiche(c, res):
        esp = res["espace"]
        if res["cree"]:
            _effacer_brut(esp, res["name"])
            db.ecrire("DELETE FROM vault_secrets WHERE espace=? AND nom=?", (esp, res["name"]))
            return
        if res["name"] != res["ancien_nom"]:
            _effacer_brut(esp, res["name"])
            db.ecrire("DELETE FROM vault_secrets WHERE espace=? AND nom=?", (esp, res["name"]))
            db.ecrire("UPDATE vault_historique SET nom=? WHERE espace=? AND nom=?", (res["ancien_nom"], esp, res["name"]))
        _poser_brut(esp, res["ancien_nom"], res["avant"])
        _remettre_meta(esp, res["ancien_nom"], res.get("meta_avant"))

    def code_totp(graine, quand=None):
        """Le code à usage unique courant (RFC 6238) : (code, secondes restantes, période). La clé est un `otpauth://totp/…` ou la seule graine base32 ; None si elle ne se lit pas."""
        x = str(graine or "").strip()
        if not x:
            return None
        graine, chiffres, periode, algo = x, 6, 30, "sha1"
        if x.lower().startswith("otpauth://"):
            try:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(x).query)
                graine = (q.get("secret") or [""])[0]
                chiffres = max(4, min(int((q.get("digits") or ["6"])[0] or 6), 10))
                periode = max(1, int((q.get("period") or ["30"])[0] or 30))
                algo = ((q.get("algorithm") or ["SHA1"])[0] or "SHA1").lower().replace("-", "")
            except ValueError:
                return None
        graine = re.sub(r"[\s\-]", "", graine).upper()
        try:
            cle = base64.b32decode(graine + "=" * (-len(graine) % 8), casefold=True)
        except (ValueError, TypeError):
            return None
        if not cle:
            return None
        t = int(quand if quand is not None else time.time())
        h = hmac.new(cle, struct.pack(">Q", t // periode), getattr(hashlib, algo if algo in ("sha1", "sha256", "sha512") else "sha1")).digest()
        o = h[-1] & 0x0F
        code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** chiffres)
        return str(code).zfill(chiffres), periode - (t % periode), periode

    def totp(c, name="", espace=""):
        nom, esp, m, meta = cible(name, espace, "lire")
        if meta is None:
            raise ValueError("secret introuvable")
        _exiger_ouvert(esp)
        d = vue_fiche(nom, _lire_brut(esp, nom))
        if not d.get("totp"):
            raise ValueError("pas de clé TOTP sur ce secret")
        r = code_totp(d["totp"])
        if not r:
            raise ValueError("clé TOTP illisible")
        _audit("totp", nom, esp)
        return {"code": r[0], "reste": r[1], "periode": r[2]}

    def historique(c, name="", espace=""):
        nom, esp, m, meta = cible(name, espace, "lire")
        if meta is None:
            raise ValueError("secret introuvable")
        _audit("historique", nom, esp)
        return {"historique": [{"password": ctx.dechiffrer(r["valeur_chiffree"], "historique:%s:%s" % (esp, nom)), "ts": r["ts"]}
                               for r in db.lire("SELECT ts, valeur_chiffree FROM vault_historique WHERE espace=? AND nom=? ORDER BY id DESC LIMIT 20", (esp, nom))]}

    def trace(c, name="", action="", espace=""):
        """Ce que l'écran fait d'une valeur déjà dans la page — la révéler, la copier — s'inscrit au journal ; jamais la valeur."""
        nom, esp, m, meta = cible(name, espace, "lire")
        if action not in ("reveal", "copie"):
            raise ValueError("action inconnue")
        if meta is not None:
            _audit(action, nom, esp)
        return {"name": nom, "action": action}

    ctx.moteur("espaces_societes", espaces_societes)
    for cid, f in (("status", status), ("available", available), ("get", lire), ("list", lister), ("journal", journal),
                   ("espaces", espaces), ("membres", membres)):
        ctx.implementer(cid, f)
    ctx.implementer("set", poser, prouver_set, defaire_set,
                    simuler=lambda x, name="", valeur="", **_: "poserait le secret « %s »" % name)
    ctx.implementer("delete", delete, prouver_delete, defaire_delete,
                    simuler=lambda x, name="", **_: "retirerait le secret « %s »" % name)
    ctx.implementer("accorder", accorder, prouver_accorder, defaire_accorder,
                    simuler=lambda x, utilisateur="", role="membre", **_: "donnerait à %s le rôle %s" % (utilisateur, role))
    ctx.implementer("retirer", retirer, prouver_retirer, defaire_retirer,
                    simuler=lambda x, utilisateur="", **_: "retirerait l'accès de %s" % utilisateur)
    ctx.implementer("regler", regler, prouver_regler, defaire_regler)
    ctx.implementer("fiche", fiche)
    ctx.implementer("totp", totp)
    ctx.implementer("historique", historique)
    ctx.implementer("trace", trace)
    ctx.implementer("fiche_ecrire", fiche_ecrire, prouver_fiche, defaire_fiche, simuler=lambda x, name="", **_: "écrirait la fiche « %s »" % name)
    ctx.implementer("espace_creer", espace_creer, prouver_creer, defaire_creer)
    ctx.implementer("espace_archiver", espace_archiver, prouver_archiver, defaire_archiver)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
