# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le coffre Vaultwarden
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : coffre
# ZONE       : CN
# VERSION CN : 0.1.0  #58b7c7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le coffre Vaultwarden : le magasin de secrets de Cassandra.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=58b7c7 ▼▼▼
"""Le coffre Vaultwarden : le magasin de secrets de Cassandra.

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

import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8087"


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

    def _audit(action, secret):
        try:
            db.ecrire("INSERT INTO vault_audit (username, action, secret_name) VALUES (?,?,?)",
                      ((ctx.compte or "").strip()[:80], action, str(secret or "")[:200]))
        except Exception:
            pass

    # ── lectures ─────────────────────────────────────────────────────────────
    def status(c):
        r = _req("GET", "/status")
        t = (r.get("data") or {}).get("template") or {}
        return {"available": bool(r.get("success")), "status": t.get("status"),
                "email": t.get("userEmail"), "server": t.get("serverUrl"), "error": r.get("error")}

    def available(c):
        s = status(c)
        return {"disponible": bool(s.get("available")) and s.get("status") == "unlocked"}

    def _find(name):
        r = _req("GET", "/list/object/items?search=" + urllib.parse.quote(str(name)))
        items = ((r.get("data") or {}).get("data")) or []
        for it in items:
            if it.get("name") == name:
                return it
        return None

    def lire(c, name=""):
        if not str(name or "").strip():
            raise ValueError("nom requis")
        it = _find(name)
        if it:
            _audit("lire", name)
        return {"valeur": it.get("notes") if it else None}

    def lister(c, prefix=""):
        r = _req("GET", "/list/object/items")
        items = ((r.get("data") or {}).get("data")) or []
        names = [it.get("name") for it in items if it.get("name")]
        if prefix:
            names = [n for n in names if n.startswith(prefix)]
        return {"noms": sorted(set(names))}

    def journal(c, limite=50):
        return {"journal": db.lire("SELECT * FROM vault_audit ORDER BY id DESC LIMIT ?",
                                   (max(1, min(int(limite or 50), 500)),))}

    # ── écritures réversibles ────────────────────────────────────────────────
    def poser(c, name="", valeur=""):
        name = str(name or "").strip()
        if not name:
            raise ValueError("nom requis")
        s = status(c)
        if not (s.get("available") and s.get("status") == "unlocked"):
            raise ValueError("coffre indisponible ou verrouillé")
        avant = lire(c, name=name)["valeur"]
        it = _find(name)
        if it:
            it["notes"] = valeur
            r = _req("PUT", "/object/item/%s" % it["id"], it)
        else:
            body = {"type": 2, "name": name, "notes": valeur, "secureNote": {"type": 0}, "fields": []}
            r = _req("POST", "/object/item", body)
        if not r.get("success"):
            raise ValueError(r.get("error") or "échec écriture coffre")
        _audit("ecrire", name)
        return {"name": name, "avant": avant, "apres": valeur}

    def prouver_set(c, res):
        return lire(c, name=res["name"])["valeur"] == res["apres"]

    def defaire_set(c, res):
        if res.get("avant") is None:
            delete(c, name=res["name"])
        else:
            poser(c, name=res["name"], valeur=res["avant"])

    def delete(c, name=""):
        name = str(name or "").strip()
        if not name:
            raise ValueError("nom requis")
        avant = lire(c, name=name)["valeur"]
        it = _find(name)
        if it:
            _req("DELETE", "/object/item/%s" % it["id"])
        _audit("retirer", name)
        return {"name": name, "avant": avant}

    def prouver_delete(c, res):
        return lire(c, name=res["name"])["valeur"] is None

    def defaire_delete(c, res):
        if res.get("avant") is not None:
            poser(c, name=res["name"], valeur=res["avant"])

    for cid, f in (("status", status), ("available", available), ("get", lire), ("list", lister), ("journal", journal)):
        ctx.implementer(cid, f)
    ctx.implementer("set", poser, prouver_set, defaire_set,
                    simuler=lambda x, name="", valeur="", **_: "poserait le secret « %s »" % name)
    ctx.implementer("delete", delete, prouver_delete, defaire_delete,
                    simuler=lambda x, name="", **_: "retirerait le secret « %s »" % name)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
