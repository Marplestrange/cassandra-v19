# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le coffre Vaultwarden
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : coffre
# ZONE       : CN
# VERSION CN : 0.1.0  #c473e4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le coffre Vaultwarden : le magasin de secrets de Cassandra.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c473e4 ▼▼▼
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

Différé proprement : la fiche complète d'un secret (chiffrement fin par le client), le provisionnement
des comptes (compte Cassandra = compte Vault natif), les clés d'API personnelles, le TOTP.
"""
from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8087"


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

    def _req(method, path, body=None):
        """Un appel au coffre. Ne lève jamais : l'échec est un dict, pas une panne."""
        cible = url() + path
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
            db.ecrire("INSERT INTO vault_audit (username, action, secret_name, espace) VALUES (?,?,?,?)",
                      ((ctx.compte or "").strip()[:80], action, str(secret or "")[:200], str(espace or "")[:80]))
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

    def _exiger_interne(esp):
        if esp.startswith("s:"):
            e = db.lire("SELECT mode FROM vault_espaces WHERE id=?", (esp,))
            if e and e[0]["mode"] == "externe":
                raise ValueError("ce coffre est hébergé hors de l'instance : son branchement n'est pas encore disponible ici")

    def _exiger_ouvert():
        s = status(None)
        if not (s.get("available") and s.get("status") == "unlocked"):
            raise ValueError("coffre indisponible ou verrouillé")

    # ── le serveur Vaultwarden : un nom physique par espace et par secret ────
    def _phys(esp, nom) -> str:
        return esp + "::" + nom

    def _find(phys):
        r = _req("GET", "/list/object/items?search=" + urllib.parse.quote(str(phys)))
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
            r = _req("PUT", "/object/item/%s" % it["id"], it)
        else:
            r = _req("POST", "/object/item", {"type": 2, "name": phys, "notes": valeur, "secureNote": {"type": 0}, "fields": []})
        if not r.get("success"):
            raise ValueError(r.get("error") or "échec écriture coffre")

    def _effacer_brut(esp, nom):
        it = _find(_phys(esp, nom))
        if it:
            _req("DELETE", "/object/item/%s" % it["id"])

    def _nom(name) -> str:
        n = str(name or "").strip()
        if not n:
            raise ValueError("nom requis")
        if len(n) > 200:
            raise ValueError("nom : 200 caractères au plus")
        return n

    # ── lectures ─────────────────────────────────────────────────────────────
    def status(c):
        r = _req("GET", "/status")
        t = (r.get("data") or {}).get("template") or {}
        return {"available": bool(r.get("success")), "status": t.get("status"),
                "email": t.get("userEmail"), "server": t.get("serverUrl"), "error": r.get("error")}

    def available(c):
        s = status(c)
        return {"disponible": bool(s.get("available")) and s.get("status") == "unlocked"}

    def lire(c, name="", espace=""):
        nom = _nom(name)
        esp = _espace(ctx.compte, espace)
        m = _acces(ctx.compte, esp)
        if m is None:
            raise ValueError(REFUS)
        _exiger_interne(esp)
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
        rows = db.lire("SELECT nom, auteur, collection FROM vault_secrets WHERE espace=? ORDER BY nom", (esp,))
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
        for m in db.lire("SELECT m.*, e.nom AS nom_espace, e.mode AS mode FROM vault_membres m JOIN vault_espaces e ON e.id=m.espace WHERE m.compte=? AND e.archive=0 ORDER BY e.nom", (compte,)):
            if m["expire"] and m["expire"] < _aujourdhui():
                continue
            rows = db.lire("SELECT nom, auteur, collection FROM vault_secrets WHERE espace=?", (m["espace"],))
            vus = sum(1 for r in rows if _peut(m, "lire", r, "", compte))
            admins = None
            if m["role"] == "admin":
                admins = db.lire("SELECT COUNT(*) AS n FROM vault_membres WHERE espace=? AND role='admin' AND (expire='' OR expire>=?)", (m["espace"], _aujourdhui()))[0]["n"]
            out.append({"id": m["espace"], "genre": "societe", "nom": m["nom_espace"] or m["espace"], "role": m["role"], "secrets": vus,
                        "collections": m["collections"], "expire": m["expire"], "mode": m["mode"], "admins": admins})
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
        _exiger_interne(esp)
        meta = _meta(esp, nom)
        col = str(collection or "").strip() or (meta["collection"] if meta else "")
        if not _peut(m, "ecrire", meta, col, ctx.compte):
            raise ValueError(REFUS)
        _exiger_ouvert()
        avant = _lire_brut(esp, nom)
        _poser_brut(esp, nom, valeur)
        db.ecrire("INSERT INTO vault_secrets (espace, nom, auteur, collection) VALUES (?,?,?,?) "
                  "ON CONFLICT(espace, nom) DO UPDATE SET collection=excluded.collection, maj=datetime('now')", (esp, nom, ctx.compte, col))
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
        _exiger_interne(esp)
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

    def regler(c, espace="", mode="interne", url=""):
        esp = _espace(ctx.compte, espace)
        _exiger_gerer(esp)
        if mode not in ("interne", "externe"):
            raise ValueError("mode : interne | externe")
        u = str(url or "").strip()
        if mode == "externe" and not (u.startswith("https://") or u.startswith("http://")):
            raise ValueError("un coffre externe a une adresse http(s)")
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

    def espaces_societes(ctx2, ev):
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
    ctx.implementer("espace_creer", espace_creer, prouver_creer, defaire_creer)
    ctx.implementer("espace_archiver", espace_archiver, prouver_archiver, defaire_archiver)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
