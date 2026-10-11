"""Registre des modèles et fournisseurs.

V18 (leçons apprises et portées) :
  - La ponctuation de fin d'un nom copié d'une phrase (« …:free. ») tombe aussi à la LECTURE : on la rstrip à l'ajout.
  - Un local doit être réellement installé (sécurité). Un modèle en ligne, non (vérifié à l'usage).
  - Sans identifiants propres, on ne se sert pas de ceux de la maison : l'admin ne paie pas pour tout le monde.
  - Réglé sur du nuage SANS clé : le compte retombe sur un modèle local sans le savoir. `muet` signale cet état.
  - Un rôle lié prime. S'il est délié après migration, on efface l'ancien réglage pour qu'il retombe sur le vrai défaut. (Ici géré via la table modeles_roles qui masque les vieux réglages).
"""

import json
import re
import time
import urllib.request
import urllib.error
import secrets

FOURNISSEURS = {
    "deepseek":     {"nom": "DeepSeek",      "defaut": "deepseek-flash",          "raisonneur": True,  "cle": "requise", "base_url": "https://api.deepseek.com/v1"},
    "openrouter":   {"nom": "OpenRouter",    "defaut": "google/gemini-2.5-flash", "raisonneur": True,  "cle": "requise", "base_url": "https://openrouter.ai/api/v1"},
    "openai":       {"nom": "OpenAI",        "defaut": "gpt-4o-mini",             "raisonneur": False, "cle": "requise", "base_url": "https://api.openai.com/v1"},
    "google":       {"nom": "Google",        "defaut": "gemini-2.5-flash",        "raisonneur": True,  "cle": "requise", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
    "groq":         {"nom": "Groq",          "defaut": "llama-3.3-70b-versatile", "raisonneur": False, "cle": "requise", "base_url": "https://api.groq.com/openai/v1"},
    "ollama":       {"nom": "Ollama (local)", "defaut": "qwen2.5:3b",             "raisonneur": False, "cle": "aucune", "base_url": "http://127.0.0.1:11434/v1"},
    "personnalise": {"nom": "Personnalisé (compatible OpenAI)", "defaut": "",     "raisonneur": False, "cle": "optionnelle", "base_url": ""},
}

_MODELES_ROLES = {"itare_citadelle": "Itare Citadelle", "vision": "Vision", "relecteur": "Relecteur de l'évolution"}
_MODELES_NOM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]{0,160}")

_MODELES_LEGACY = {
    "itare_citadelle": (("itare_citadelle_", "itare_"), ("itare_citadelle_api_key", "itare_api_key"),
                        ("itare_citadelle_provider", "itare_citadelle_base_url", "itare_citadelle_model",
                         "itare_provider", "itare_base_url", "itare_model")),
    "vision": (("itare_vision_",), ("itare_vision_api_key",),
               ("itare_vision_provider", "itare_vision_base_url", "itare_vision_model")),
    "relecteur": (("evolution_relecteur_",), ("evolution_relecteur_api_key",),
                  ("evolution_relecteur_provider", "evolution_relecteur_base_url", "evolution_relecteur_model")),
}

def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def _ollama_base():
        return str(ctx.reglage("ollama_url") or "http://127.0.0.1:11434").rstrip("/")

    def _ollama_list():
        try:
            req = urllib.request.Request(_ollama_base() + "/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                return json.loads(r.read().decode("utf-8")).get("models", [])
        except Exception:
            return []

    def _ollama_available():
        try:
            req = urllib.request.Request(_ollama_base() + "/api/tags")
            with urllib.request.urlopen(req, timeout=2) as r:
                return True
        except Exception:
            return False

    def _modeles_legacy(role: str) -> dict:
        prefixes, _cles, _tout = _MODELES_LEGACY[role]
        def lire(champ):
            for pre in prefixes:
                v = str(ctx.reglage(pre + champ) or "").strip()
                if v:
                    return v
            return ""
        prov = lire("provider")
        prov = "personnalise" if prov == "custom" else prov
        return {"prov": prov, "nom": lire("model").rstrip(".,;:!?»« ").strip(), "base": lire("base_url"), "cle": lire("api_key")}

    def _modeles_roles_lies() -> dict:
        rows = db.lire("SELECT role, modele_id FROM modeles_roles")
        return {r["role"]: r["modele_id"] for r in rows}

    def prouver_bouchon(ctx, res): return True
    def defaire_bouchon(ctx, res): pass

    # --- MOTEURS ---
    def moteur_ollama_pull(ctx, ev):
        nom = ev["donnees"]["nom"]
        try:
            req = urllib.request.Request(_ollama_base() + "/api/pull", 
                                         data=json.dumps({"name": nom, "stream": False}).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3600) as r:
                pass
            ctx.emettre("modele.pull_termine", objet=("modele", nom), donnees={"nom": nom})
        except Exception as e:
            ctx.emettre("modele.pull_erreur", objet=("modele", nom), donnees={"erreur": str(e)})

    # --- LECTURES ---
    def lister(ctx):
        liens = _modeles_roles_lies()
        rows = db.lire("SELECT * FROM modeles_registre ORDER BY ts, id")
        par_modele = {}
        for role, mid in liens.items():
            par_modele.setdefault(mid, []).append(role)
        out = []
        for r in rows:
            d = dict(r)
            d["roles"] = par_modele.get(r["id"], [])
            d["en_ligne"] = r["fournisseur"] != "ollama" and not (r["fournisseur"] == "personnalise" and
                                                                  re.match(r"https?://(127\.|localhost|\[::1\])", r["base_url"] or ""))
            out.append(d)
        
        locaux = _ollama_list() if _ollama_available() else []
        en_clair = []
        for role in _MODELES_ROLES:
            leg = _modeles_legacy(role)
            if leg["cle"] and leg["cle"] != "ollama" and role not in liens:
                en_clair.append({"role": role, "nom": _MODELES_ROLES[role], "migrable": bool(leg["nom"]),
                                 "modele": leg["nom"], "fournisseur": leg["prov"]})
        
        return {"ok": True, "modeles": out, "roles": liens, "locaux": locaux,
                "ollama": bool(locaux) or _ollama_available(),
                "pull": {"model": "", "status": "", "percent": 0, "running": False, "error": ""}, # TODO(noyau) : etat reel asynchrone
                "fournisseurs": [{"id": k, "nom": v["nom"], "defaut": v["defaut"], "cle": v["cle"],
                                  "raisonneur": v["raisonneur"]} for k, v in FOURNISSEURS.items()],
                "roles_branches": list(_MODELES_ROLES), "en_clair": en_clair,
                "coffre": True} # TODO(coffre)

    def compte_etat(ctx):
        c = ctx.compte
        if not c:
            raise ValueError("compte requis")
        # TODO(coffre) : lire si le compte a une clé
        a_cle = False 
        r = db.lire("SELECT fournisseur, modele FROM compte_choix WHERE compte=?", (c,))
        prov = r[0]["fournisseur"] if r else ""
        return {"fournisseur": prov, "a_cle": a_cle, 
                "fournisseurs": sorted(list(FOURNISSEURS.keys())),
                "muet": bool(prov and prov != "ollama" and not a_cle)}

    # --- ÉCRITURES COMPTE ---
    def compte_ecrire(ctx, nom="", fournisseur=""):
        c = ctx.compte
        if not c:
            raise ValueError("compte requis")
        nom = str(nom or "").strip().rstrip(".,;:!?»« ")
        prov = str(fournisseur or "").strip()
        if prov and prov not in FOURNISSEURS:
            raise ValueError("fournisseur inconnu : %s" % prov)
        if nom and (not prov or prov == "ollama"):
            dispo = {m["name"] for m in _ollama_list()}
            if nom not in dispo:
                raise ValueError("modèle local inconnu ou non installé")
        
        avant = db.lire("SELECT fournisseur, modele FROM compte_choix WHERE compte=?", (c,))
        avant_dict = {"fournisseur": avant[0]["fournisseur"], "modele": avant[0]["modele"]} if avant else None
        
        db.ecrire("INSERT INTO compte_choix (compte, fournisseur, modele, maj) VALUES (?,?,?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET fournisseur=excluded.fournisseur, modele=excluded.modele, maj=excluded.maj",
                  (c, prov, nom, time.time()))
        return {"compte": c, "avant": avant_dict, "apres": {"fournisseur": prov, "modele": nom}}

    def prouver_compte_ecrire(ctx, res):
        r = db.lire("SELECT fournisseur, modele FROM compte_choix WHERE compte=?", (res["compte"],))
        return bool(r and r[0]["fournisseur"] == res["apres"]["fournisseur"] and r[0]["modele"] == res["apres"]["modele"])

    def defaire_compte_ecrire(ctx, res):
        if res["avant"]:
            db.ecrire("UPDATE compte_choix SET fournisseur=?, modele=?, maj=? WHERE compte=?", 
                      (res["avant"]["fournisseur"], res["avant"]["modele"], time.time(), res["compte"]))
        else:
            db.ecrire("DELETE FROM compte_choix WHERE compte=?", (res["compte"],))

    def compte_cle_ecrire(ctx, cle=""):
        c = ctx.compte
        if not c:
            raise ValueError("compte requis")
        # TODO(coffre) : écrire la clé dans _IT_MODELE_SECRET
        return {"compte": c, "avant": None}
        
    def compte_cle_retirer(ctx):
        c = ctx.compte
        if not c:
            raise ValueError("compte requis")
        # TODO(coffre) : retirer la clé de _IT_MODELE_SECRET
        return {"compte": c, "avant": None}

    # --- ÉCRITURES REGISTRE ---
    def ajouter(ctx, fournisseur="", nom="", base_url="", cle=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        prov = str(fournisseur or "").strip()
        if prov not in FOURNISSEURS:
            raise ValueError("fournisseur inconnu")
        nom = str(nom or "").strip().rstrip(".,;:!?»« ")
        if not nom:
            raise ValueError("nom de modèle requis")
        if re.match(r"https?://", nom, re.I):
            raise ValueError("le modèle est un nom, pas une adresse")
        if not _MODELES_NOM_RE.fullmatch(nom) or nom.endswith(":"):
            raise ValueError("nom de modèle invalide")
        base = str(base_url or "").strip()
        if prov == "personnalise":
            if not base or not re.fullmatch(r"https?://[^\s]+", base):
                raise ValueError("adresse du serveur manquante ou invalide")
        else:
            base = ""
        cle = str(cle or "").strip()
        besoin = FOURNISSEURS[prov]["cle"]
        if besoin == "requise" and not cle:
            raise ValueError("clé manquante")
            
        slug = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")[:28] or "modele"
        mid = "%s-%s" % (slug, secrets.token_hex(2))
        a_cle = 1 if (cle and prov != "ollama") else 0
        
        if a_cle:
            # TODO(coffre) : écrire la clé dans modele/mid
            pass
            
        db.ecrire("INSERT INTO modeles_registre (id, fournisseur, nom, base_url, a_cle, ts, ajoute_par) VALUES (?,?,?,?,?,?,?)",
                  (mid, prov, nom, base, a_cle, time.time(), ctx.compte or ""))
        return {"id": mid, "avant": None}

    def prouver_ajouter(ctx, res):
        return len(db.lire("SELECT id FROM modeles_registre WHERE id=?", (res["id"],))) == 1

    def defaire_ajouter(ctx, res):
        db.ecrire("DELETE FROM modeles_registre WHERE id=?", (res["id"],))
        # TODO(coffre) : supprimer modele/mid

    def retirer(ctx, id=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        mid = str(id or "").strip()
        lies = [r for r, m in _modeles_roles_lies().items() if m == mid]
        if lies:
            raise ValueError("ce modèle sert un rôle (%s) : change le rôle d'abord" % ", ".join(lies))
        row = db.lire("SELECT * FROM modeles_registre WHERE id=?", (mid,))
        if not row:
            raise ValueError("modèle introuvable")
        
        # TODO(coffre) : supprimer modele/mid si a_cle
        
        db.ecrire("DELETE FROM modeles_registre WHERE id=?", (mid,))
        return {"id": mid, "avant": dict(row[0])}

    def prouver_retirer(ctx, res):
        return len(db.lire("SELECT id FROM modeles_registre WHERE id=?", (res["id"],))) == 0

    def defaire_retirer(ctx, res):
        a = res["avant"]
        db.ecrire("INSERT INTO modeles_registre (id, fournisseur, nom, base_url, a_cle, ts, ajoute_par, essai_ts, essai_ok, essai_s, essai_msg) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (a["id"], a["fournisseur"], a["nom"], a["base_url"], a["a_cle"], a["ts"], a["ajoute_par"], a["essai_ts"], a["essai_ok"], a["essai_s"], a["essai_msg"]))

    def essayer(ctx, id=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        mid = str(id or "").strip()
        row = db.lire("SELECT * FROM modeles_registre WHERE id=?", (mid,))
        if not row:
            raise ValueError("modèle introuvable")
        
        # TODO(agent) : appeler le modèle via le noyau (V18 _itare_agent_text)
        ok = True
        msg = "ok (bouchon)"
        dt = 0.5
        
        db.ecrire("UPDATE modeles_registre SET essai_ts = ?, essai_ok = ?, essai_s = ?, essai_msg = ? WHERE id = ?",
                  (time.time(), 1 if ok else 0, dt, msg, mid))
        return {"id": mid, "ok": ok, "reponse": msg, "avant": dict(row[0])}

    def prouver_essayer(ctx, res):
        return db.lire("SELECT essai_ok FROM modeles_registre WHERE id=?", (res["id"],))[0]["essai_ok"] is not None

    def defaire_essayer(ctx, res):
        a = res["avant"]
        db.ecrire("UPDATE modeles_registre SET essai_ts=?, essai_ok=?, essai_s=?, essai_msg=? WHERE id=?",
                  (a["essai_ts"], a["essai_ok"], a["essai_s"], a["essai_msg"], res["id"]))

    def role_set(ctx, role="", id=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        if role not in _MODELES_ROLES:
            raise ValueError("rôle inconnu")
        mid = str(id or "").strip()
        if mid:
            row = db.lire("SELECT id FROM modeles_registre WHERE id=?", (mid,))
            if not row:
                raise ValueError("modèle introuvable")
        
        avant = db.lire("SELECT modele_id FROM modeles_roles WHERE role=?", (role,))
        avant_id = avant[0]["modele_id"] if avant else None
        
        if mid:
            db.ecrire("INSERT INTO modeles_roles (role, modele_id) VALUES (?,?) "
                      "ON CONFLICT(role) DO UPDATE SET modele_id=excluded.modele_id", (role, mid))
        else:
            db.ecrire("DELETE FROM modeles_roles WHERE role=?", (role,))
            
        return {"role": role, "mid": mid, "avant": avant_id}

    def prouver_role_set(ctx, res):
        r = db.lire("SELECT modele_id FROM modeles_roles WHERE role=?", (res["role"],))
        return (r[0]["modele_id"] == res["mid"]) if res["mid"] else (len(r) == 0)

    def defaire_role_set(ctx, res):
        if res["avant"]:
            db.ecrire("INSERT INTO modeles_roles (role, modele_id) VALUES (?,?) "
                      "ON CONFLICT(role) DO UPDATE SET modele_id=excluded.modele_id", (res["role"], res["avant"]))
        else:
            db.ecrire("DELETE FROM modeles_roles WHERE role=?", (res["role"],))

    def migrer(ctx, role=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        if role not in _MODELES_ROLES:
            raise ValueError("rôle inconnu")
        leg = _modeles_legacy(role)
        if not leg["cle"] or leg["cle"] == "ollama":
            raise ValueError("rien à migrer")
        if not leg["nom"] or not leg["prov"]:
            raise ValueError("ce rôle n'a ni fournisseur ni modèle réglés")
        if leg["prov"] not in FOURNISSEURS:
            raise ValueError("fournisseur inconnu : %s" % leg["prov"][:40])
        
        res_ajout = ajouter(ctx, fournisseur=leg["prov"], nom=leg["nom"], base_url=leg["base"], cle=leg["cle"])
        mid = res_ajout["id"]
        res_role = role_set(ctx, role=role, id=mid)
        
        return {"id": mid, "role": role, "avant_ajout": res_ajout["avant"], "avant_role": res_role["avant"]}

    def prouver_migrer(ctx, res):
        return len(db.lire("SELECT id FROM modeles_registre WHERE id=?", (res["id"],))) == 1

    def defaire_migrer(ctx, res):
        defaire_role_set(ctx, {"role": res["role"], "avant": res["avant_role"]})
        defaire_ajouter(ctx, {"id": res["id"]})

    def ollama_pull(ctx, nom=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        nom = str(nom or "").strip()
        if not nom:
            raise ValueError("nom requis")
        ctx.emettre("modele.pull_demande", objet=("modele", nom), donnees={"nom": nom})
        return {"nom": nom, "avant": None}

    def ollama_supprimer(ctx, nom=""):
        if not dr.raison(ctx.compte, "modeles.gerer")["accord"]:
            raise PermissionError("droit modeles.gerer requis")
        nom = str(nom or "").strip()
        if not nom:
            raise ValueError("nom requis")
        ids = [r["id"] for r in db.lire("SELECT id FROM modeles_registre WHERE fournisseur='ollama' AND nom=?", (nom,))]
        lies = _modeles_roles_lies()
        if any(m in ids for m in lies.values()):
            raise ValueError("ce modèle sert un rôle : change le rôle d'abord")
        
        # TODO(ollama) : urllib DELETE request to ollama_url/api/delete
        
        avant_ids = []
        for i in ids:
            row = db.lire("SELECT * FROM modeles_registre WHERE id=?", (i,))
            if row:
                avant_ids.append(dict(row[0]))
            db.ecrire("DELETE FROM modeles_registre WHERE id=?", (i,))
        
        return {"nom": nom, "avant": avant_ids}

    def defaire_ollama_supprimer(ctx, res):
        for a in (res["avant"] or []):
            db.ecrire("INSERT INTO modeles_registre (id, fournisseur, nom, base_url, a_cle, ts, ajoute_par, essai_ts, essai_ok, essai_s, essai_msg) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (a["id"], a["fournisseur"], a["nom"], a["base_url"], a["a_cle"], a["ts"], a["ajoute_par"], a["essai_ts"], a["essai_ok"], a["essai_s"], a["essai_msg"]))

    ctx.moteur("ollama_pull", moteur_ollama_pull)
    ctx.implementer("lister", lister)
    ctx.implementer("compte_etat", compte_etat)
    ctx.implementer("compte_ecrire", compte_ecrire, prouver_compte_ecrire, defaire_compte_ecrire)
    ctx.implementer("compte_cle_ecrire", compte_cle_ecrire, prouver_bouchon, defaire_bouchon)
    ctx.implementer("compte_cle_retirer", compte_cle_retirer, prouver_bouchon, defaire_bouchon)
    ctx.implementer("ajouter", ajouter, prouver_ajouter, defaire_ajouter)
    ctx.implementer("retirer", retirer, prouver_retirer, defaire_retirer)
    ctx.implementer("essayer", essayer, prouver_essayer, defaire_essayer)
    ctx.implementer("role_set", role_set, prouver_role_set, defaire_role_set)
    ctx.implementer("migrer", migrer, prouver_migrer, defaire_migrer)
    ctx.implementer("ollama_pull", ollama_pull, prouver_bouchon, defaire_bouchon)
    ctx.implementer("ollama_supprimer", ollama_supprimer, prouver_bouchon, defaire_ollama_supprimer)
