"""Les modèles.

Porté de la V18 (registre `modele_*`, `FOURNISSEURS`, `_itare_agent_text`, `_itare_ollama_texte`, `it_modele_*`, `ollama_*`), avec ses leçons :
  - un modèle se déclare UNE fois ; les rôles et les comptes y puisent. Quatre rôles saisissaient chacun leur modèle, leur clé et leur serveur, et une clé dormait en clair
    dans la configuration : ici la clé est chiffrée, liée à son modèle, et ne sort JAMAIS du module (ni liste, ni journal, ni réponse) ;
  - un compte n'utilise que SES modèles, avec SA clé : sans clé propre on ne se sert pas de celle de la maison, sinon l'administrateur paierait pour tout le monde ;
    les rôles (modèles de l'instance) ne servent que les acteurs de la maison ;
  - un modèle RAISONNEUR dépense son budget en réflexion et rend un contenu vide sans erreur : un seul rejeu, budget triplé, consigne de réponse directe ; une réponse
    coupée par la limite est DITE, pas laissée passer pour du code invalide ;
  - le repli sur la réflexion est refusable (`allow_reasoning`) : pour du code, la prose de réflexion ferait un faux diagnostic de code tronqué ;
  - un Ollama local se parle par son API NATIVE (seule à accepter `think` et `num_ctx`) ; un modèle qui ne sait pas réfléchir refuse `think` (400) : on rejoue sans ;
  - le nom d'un modèle copié d'une phrase perd sa ponctuation de fin ; un nom n'est pas une adresse ;
  - une panne dit ce qui s'est passé et ce qu'on peut y faire (un local qui n'a pas répondu à temps) ; basculer seul vers un modèle en ligne enverrait la conversation
    hors de la machine, donc le choix reste à la personne ;
  - retirer un modèle qui sert un rôle ou un choix est refusé : un rôle sans modèle ne se verrait qu'à la première panne.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.error
import urllib.request
from datetime import datetime

FOURNISSEURS = {
    "deepseek": {"nom": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "defaut": "deepseek-flash", "raisonneur": True, "cle": "requise"},
    "openrouter": {"nom": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "defaut": "google/gemini-2.5-flash", "raisonneur": True, "cle": "requise"},
    "openai": {"nom": "OpenAI", "base_url": "https://api.openai.com/v1", "defaut": "gpt-4o-mini", "raisonneur": False, "cle": "requise"},
    "google": {"nom": "Google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "defaut": "gemini-2.5-flash", "raisonneur": True, "cle": "requise"},
    "groq": {"nom": "Groq", "base_url": "https://api.groq.com/openai/v1", "defaut": "llama-3.3-70b-versatile", "raisonneur": False, "cle": "requise"},
    "ollama": {"nom": "Ollama (local)", "base_url": "http://127.0.0.1:11434/v1", "defaut": "qwen2.5:3b", "raisonneur": False, "cle": "aucune"},
    "personnalise": {"nom": "Personnalisé (compatible OpenAI)", "base_url": "", "defaut": "", "raisonneur": False, "cle": "optionnelle"},
}
ROLES_CONNUS = {"itare_citadelle": "Itare Citadelle", "vision": "Vision", "relecteur": "Relecteur de l'évolution", "principal": "Modèle principal", "second_avis": "Second avis"}
RE_NOM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]{0,160}")
RE_ROLE = re.compile(r"[a-z][a-z0-9_]{1,39}")
RE_BASE = re.compile(r"https?://[^\s]+")
ACTEURS_MAISON = ("cassandra", "itare", "agent", "noyau")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
PONCTUATION = ".,;:!?»« "
PREMIERS_MOTS = "Réponds par le seul mot : prêt."


def lire_json(url, corps=None, entetes=None, timeout=30.0, methode=None, limite=8 * 1024 * 1024):
    req = urllib.request.Request(url, data=None if corps is None else json.dumps(corps).encode("utf-8"), method=methode or ("POST" if corps is not None else "GET"))
    req.add_header("Content-Type", "application/json")
    for k, v in (entetes or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=float(timeout)) as r:
        return json.loads(r.read(limite).decode("utf-8", "replace") or "{}")


def panne_texte(nom, base, e):
    """Ce qui s'est passé, et ce qu'on peut y faire. « Request timed out » ne disait ni l'un ni l'autre."""
    txt = str(e or "")
    if any(h in str(base or "") for h in ("127.0.0.1", "localhost", ":11434")) and ("timed out" in txt.lower() or "timeout" in txt.lower()):
        return ("le modèle local « %s » n'a pas répondu à temps. Un modèle qui réfléchit avant de répondre, sur le processeur de la machine et face à un long contexte, dépasse ce délai. "
                "Un modèle en ligne se choisit dans Mon compte." % (nom or "?"))
    if isinstance(e, urllib.error.HTTPError):
        try:
            corps = e.read(500).decode("utf-8", "replace")
        except Exception:
            corps = ""
        return "HTTP %s%s" % (e.code, (" — " + corps[:200]) if corps else "")
    return txt[:300] or type(e).__name__


def brancher(ctx):
    db = ctx.stockage

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("un modèle personnel est celui d'un compte : aucun compte n'agit")
        return c

    def maison():
        return (ctx.acteur or "") in ACTEURS_MAISON

    def hote_ollama():
        return str(ctx.reglage("ollama_hote") or "http://127.0.0.1:11434").rstrip("/")

    # ------------------------------------------------------------------ registre
    def brut(mid):
        r = db.lire("SELECT * FROM modeles WHERE id=?", (str(mid or "").strip(),))
        return dict(r[0]) if r else None

    def visible(m, compte):
        return m is not None and (m["portee"] == "instance" or m["compte"] == compte)

    def exiger(mid, compte, instance=False):
        m = brut(mid)
        if m is None or (instance and m["portee"] != "instance") or (not instance and m["portee"] == "instance") or (not instance and m["compte"] != compte):
            raise ValueError("modèle introuvable")
        return m

    def publique(m, roles=None, choisi=""):
        return {"id": m["id"], "fournisseur": m["fournisseur"], "nom": m["nom"], "base_url": m["base_url"], "a_cle": bool(m["cle"]), "portee": m["portee"],
                "ajoute_par": m["ajoute_par"], "cree": datetime.fromtimestamp(m["cree"]).strftime("%Y-%m-%d %H:%M"),
                "essai": None if m["essai_ts"] is None else {"quand": datetime.fromtimestamp(m["essai_ts"]).strftime("%Y-%m-%d %H:%M"), "ok": bool(m["essai_ok"]), "secondes": m["essai_s"], "message": m["essai_msg"]},
                "roles": (roles or {}).get(m["id"], []), "choisi": m["id"] == choisi,
                "en_ligne": m["fournisseur"] != "ollama" and not (m["fournisseur"] == "personnalise" and re.match(r"https?://(127\.|localhost|\[::1\])", m["base_url"] or ""))}

    def creds(m):
        """(clé, modèle, base, fournisseur). Sans clé : « ollama » pour le local, « none » ailleurs (le client exige une valeur non vide)."""
        prov = m["fournisseur"]
        if m["cle"]:
            cle = ctx.dechiffrer(m["cle"], "modele:" + m["id"])
        else:
            cle = "ollama" if prov == "ollama" else "none"
        base = (m["base_url"] or "").strip() or (hote_ollama() + "/v1" if prov == "ollama" else FOURNISSEURS.get(prov, {}).get("base_url", ""))
        return cle, m["nom"], base, prov

    def fournisseurs(c):
        return {"fournisseurs": [{"id": k, "nom": v["nom"], "defaut": v["defaut"], "cle": v["cle"], "raisonneur": v["raisonneur"]} for k, v in FOURNISSEURS.items()], "roles": ROLES_CONNUS}

    def lister(c):
        compte = compte_agit()
        roles = {}
        for r in db.lire("SELECT role, modele_id FROM roles"):
            roles.setdefault(r["modele_id"], []).append(r["role"])
        ch = db.lire("SELECT modele_id FROM choix WHERE compte=?", (compte,))
        choisi = ch[0]["modele_id"] if ch else ""
        rows = [dict(r) for r in db.lire("SELECT * FROM modeles WHERE portee='instance' OR compte=? ORDER BY cree, id", (compte,))]
        out = {"modeles": [publique(m, roles if m["portee"] == "instance" else None, choisi) for m in rows], "choix": choisi, "ton": str(ctx.reglage("ton", compte) or "")[:4000]}
        out["roles"] = {r["role"]: r["modele_id"] for r in db.lire("SELECT * FROM roles")} if maison() else {}
        try:
            out["locaux"] = [m["name"] for m in lister_locaux()]
        except Exception:
            out["locaux"] = []
        return out

    def lister_locaux():
        j = lire_json(hote_ollama() + "/api/tags", timeout=3)
        return [{"name": m.get("name", ""), "taille": m.get("size", 0)} for m in (j.get("models") or []) if m.get("name")]

    def locaux(c):
        try:
            modeles, repond, raison = lister_locaux(), True, ""
        except Exception as e:
            modeles, repond, raison = [], False, str(e)[:120]
        pulls = [dict(r) for r in db.lire("SELECT id, nom, etat, detail, pourcent, ts FROM pulls ORDER BY id DESC LIMIT 20")]
        return {"repond": repond, "raison": raison, "modeles": modeles, "telechargements": pulls}

    # ------------------------------------------------------------------ déclarer
    def valider(prov, nom, base, cle):
        prov = str(prov or "").strip()
        if prov not in FOURNISSEURS:
            raise ValueError("fournisseur inconnu")
        nom = str(nom or "").strip().rstrip(PONCTUATION).strip()
        if not nom:
            raise ValueError("nom de modèle requis")
        if re.match(r"https?://", nom, re.I):
            raise ValueError("le modèle est un nom, pas une adresse")
        if not RE_NOM.fullmatch(nom) or nom.endswith(":"):
            raise ValueError("nom de modèle invalide : « %s »" % nom[:80])
        base = str(base or "").strip()
        if prov == "personnalise":
            if not base:
                raise ValueError("adresse du serveur manquante")
            if not RE_BASE.fullmatch(base):
                raise ValueError("adresse du serveur invalide")
        elif prov == "ollama" and base:
            if not RE_BASE.fullmatch(base):
                raise ValueError("adresse du serveur invalide")
        else:
            base = ""                                   # l'adresse vient de la table des fournisseurs, une seule fois
        cle = str(cle or "").strip()
        if FOURNISSEURS[prov]["cle"] == "requise" and not cle:
            raise ValueError("clé manquante")
        return prov, nom, base, (cle if prov != "ollama" else "")

    def declarer(portee, compte, prov, nom, base, cle):
        prov, nom, base, cle = valider(prov, nom, base, cle)
        mid = "%s-%s" % (re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")[:28] or "modele", secrets.token_hex(2))
        chiffre = ctx.chiffrer(cle, "modele:" + mid) if cle else ""
        db.ecrire("INSERT INTO modeles(id, fournisseur, nom, base_url, cle, portee, compte, ajoute_par, cree) VALUES (?,?,?,?,?,?,?,?,?)",
                  (mid, prov, nom, base, chiffre, portee, compte if portee == "compte" else "", ctx.compte or "", time.time()))
        ctx.emettre("modele.ajoute", objet=("modele", mid), donnees={"id": mid, "fournisseur": prov, "nom": nom, "portee": portee})
        return {"id": mid, "portee": portee, "compte": compte, "fournisseur": prov, "nom": nom, "a_cle": bool(cle)}

    def ajouter(c, fournisseur="", nom="", cle="", base_url=""):
        return declarer("compte", compte_agit(), fournisseur, nom, base_url, cle)

    def instance_ajouter(c, fournisseur="", nom="", cle="", base_url=""):
        return declarer("instance", "", fournisseur, nom, base_url, cle)

    def prouver_ajoute(c, res):
        m = brut(res["id"])
        return m is not None and m["nom"] == res["nom"] and bool(m["cle"]) == res["a_cle"]

    def defaire_ajoute(c, res):
        db.ecrire("DELETE FROM modeles WHERE id=?", (res["id"],))

    # ------------------------------------------------------------------ appeler
    def ajouter_usage(role, mid, ok, secondes, usage):
        e, s = int((usage or {}).get("prompt_tokens") or 0), int((usage or {}).get("completion_tokens") or 0)
        db.ecrire("INSERT INTO usage(jour, role, modele_id, appels, echecs, entrees, sorties, secondes) VALUES (?,?,?,1,?,?,?,?) "
                  "ON CONFLICT(jour, role, modele_id) DO UPDATE SET appels=appels+1, echecs=echecs+excluded.echecs, entrees=entrees+excluded.entrees, sorties=sorties+excluded.sorties, secondes=secondes+excluded.secondes",
                  (time.strftime("%Y-%m-%d"), role or "", mid, 0 if ok else 1, e, s, secondes))

    def appel_ollama(cle_, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion):
        """L'API NATIVE : la seule qui accepte `think` (couper la réflexion) et `num_ctx` (la fenêtre)."""
        base = str(base or "").rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        opts = {"num_predict": int(max_tokens), "num_ctx": int(ctx.reglage("ollama_num_ctx") or 8192)}
        if temperature is not None:
            opts["temperature"] = float(temperature)
        corps = {"model": modele, "messages": msgs, "stream": False, "options": opts, "keep_alive": "10m", "think": bool(reflexion)}
        try:
            j = lire_json(base + "/api/chat", corps, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code != 400:                            # un modèle qui ne sait pas réfléchir refuse `think` : on rejoue sans lui
                raise
            corps.pop("think", None)
            j = lire_json(base + "/api/chat", corps, timeout=timeout)
        m = j.get("message") or {}
        txt = (m.get("content") or "").strip()
        fin = str(j.get("done_reason") or "")
        avert = ""
        if fin == "length":
            avert = "réponse TRONQUÉE par num_predict=%s (done_reason=length) — augmenter le budget" % max_tokens
        if not txt:
            rc = (m.get("thinking") or "").strip()
            if rc and allow_reasoning:
                txt = rc
            else:
                avert = "contenu VIDE renvoyé par %s en local (done_reason=%s, réflexion %s)" % (modele, fin, "demandée" if reflexion else "coupée")
        return txt, avert, {"prompt_tokens": j.get("prompt_eval_count"), "completion_tokens": j.get("eval_count")}

    def appel_openai(cle, modele, base, msgs, max_tokens, temperature, allow_reasoning, timeout):
        entetes = {} if cle in ("none", "ollama", "") else {"Authorization": "Bearer " + cle}
        url = str(base).rstrip("/") + "/chat/completions"
        kw = {"model": modele, "messages": msgs, "max_tokens": int(max_tokens)}
        if temperature is not None:
            kw["temperature"] = float(temperature)
        rejoue, usage = False, {}
        while True:
            try:
                j = lire_json(url, kw, entetes, timeout)
            except urllib.error.HTTPError as e:
                if e.code == 400 and "temperature" in kw:          # un endpoint qui n'accepte pas le paramètre : repli sans lui
                    kw = {k: v for k, v in kw.items() if k != "temperature"}
                    continue
                raise
            ch = (j.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            txt = (msg.get("content") or "").strip()
            fin = str(ch.get("finish_reason") or "")
            rc = str(msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
            for k, v in (j.get("usage") or {}).items():
                usage[k] = usage.get(k, 0) + (v if isinstance(v, int) else 0)
            if not txt and rc and not rejoue:
                # MODÈLE RAISONNEUR : la réflexion a mangé le budget — un SEUL rejeu, budget élargi, consigne de réponse directe.
                rejoue = True
                kw = dict(kw, max_tokens=max(int(max_tokens) * 3, 3000), messages=list(kw["messages"]) + [{"role": "user", "content":
                          "(Ta réponse est arrivée vide : ta réflexion a consommé tout le budget. Réponds maintenant directement, sans réfléchir longuement.)"}])
                continue
            avert = ""
            if fin == "length":
                avert = "réponse TRONQUÉE par max_tokens=%s (finish_reason=length) — augmenter le budget" % max_tokens
            if not txt:
                if rc and allow_reasoning:
                    txt = rc
                else:
                    avert = "contenu VIDE renvoyé par %s (finish_reason=%s) — modèle raisonneur qui a tout dépensé en réflexion ?" % (modele, fin)
            return txt, avert, usage

    def appeler(m, messages, systeme, max_tokens, temperature, allow_reasoning, timeout, reflexion, role=""):
        """Rend toujours un dict, jamais une exception : {ok, texte, avertissement, erreur, secondes, modele}."""
        t0 = time.time()
        try:
            cle, nom, base, prov = creds(m)
        except Exception as e:                               # une clé altérée ou recopiée ailleurs ne se lit plus : c'est une panne, pas une exception
            ajouter_usage(role, m["id"], False, 0.0, None)
            return {"ok": False, "texte": "", "erreur": "clé illisible (%s)" % str(e)[:120], "secondes": 0.0, "modele": m["id"]}
        msgs = ([{"role": "system", "content": str(systeme)}] if systeme else []) + [{"role": str(x.get("role") or "user"), "content": x.get("content")} for x in messages if isinstance(x, dict)]
        usage = {}
        try:
            if prov == "ollama" and all(isinstance(x.get("content"), str) for x in msgs):
                txt, avert, usage = appel_ollama(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout, reflexion)
            else:
                txt, avert, usage = appel_openai(cle, nom, base, msgs, max_tokens, temperature, allow_reasoning, timeout)
        except Exception as e:
            dt = round(time.time() - t0, 1)
            ajouter_usage(role, m["id"], False, dt, None)
            return {"ok": False, "texte": "", "erreur": panne_texte(nom, base, e).replace(cle, "***") if cle not in ("none", "ollama", "") else panne_texte(nom, base, e), "secondes": dt, "modele": m["id"]}
        dt = round(time.time() - t0, 1)
        ajouter_usage(role, m["id"], bool(txt), dt, usage)
        return {"ok": bool(txt), "texte": txt, "avertissement": avert, "erreur": "" if txt else (avert or "aucune réponse"), "secondes": dt, "modele": m["id"], "usage": {k: v for k, v in usage.items() if isinstance(v, int)}}

    def completer(c, messages=None, systeme="", max_tokens=1400, temperature=None, role="", modele_id="", reflexion=False, timeout=75.0, allow_reasoning=True):
        compte = ctx.compte or ""
        if not isinstance(messages, list) or not messages:
            return {"ok": False, "erreur": "aucun message"}
        m, role = None, str(role or "").strip()
        if role:
            if not maison():
                return {"ok": False, "erreur": "un rôle de la maison ne sert pas un compte : utilise ton propre modèle"}
            r = db.lire("SELECT modele_id FROM roles WHERE role=?", (role,))
            m = brut(r[0]["modele_id"]) if r else None
            if m is None:
                return {"ok": False, "erreur": "le rôle « %s » n'est lié à aucun modèle" % role}
        elif modele_id:
            m = brut(modele_id)
            if m is None or (m["portee"] == "instance" and not maison()) or (m["portee"] == "compte" and m["compte"] != compte):
                return {"ok": False, "erreur": "modèle introuvable"}
        else:
            ch = db.lire("SELECT modele_id FROM choix WHERE compte=?", (compte,)) if compte and compte not in SYSTEME else []
            m = brut(ch[0]["modele_id"]) if ch else None
            if m is None:
                return {"ok": False, "erreur": "aucun modèle : choisis l'un des tiens (jamais la clé du serveur)"}
        try:
            mx = max(16, min(int(max_tokens or 1400), 64000))
            tp = None if temperature is None else float(temperature)
            to = max(5.0, min(float(timeout or 75.0), 600.0))
        except (TypeError, ValueError):
            return {"ok": False, "erreur": "paramètres invalides"}
        return appeler(m, messages, systeme, mx, tp, bool(allow_reasoning), to, bool(reflexion), role)

    # ------------------------------------------------------------------ essayer
    def essai(mid, compte, instance):
        m = exiger(mid, compte, instance)
        avant = {k: m[k] for k in ("essai_ts", "essai_ok", "essai_s", "essai_msg")}
        r = appeler(m, [{"role": "user", "content": PREMIERS_MOTS}], "", 300, None, True, 60.0, False)
        msg = (r["texte"][:120] if r["ok"] else (r["erreur"] or "aucune réponse")[:200])
        maj = {"essai_ts": time.time(), "essai_ok": 1 if r["ok"] else 0, "essai_s": r["secondes"], "essai_msg": msg}
        db.ecrire("UPDATE modeles SET essai_ts=?, essai_ok=?, essai_s=?, essai_msg=? WHERE id=?", (maj["essai_ts"], maj["essai_ok"], maj["essai_s"], maj["essai_msg"], m["id"]))
        return {"id": m["id"], "ok": r["ok"], "secondes": r["secondes"], "reponse": msg if r["ok"] else "", "erreur": "" if r["ok"] else msg, "avant": avant, "maj": maj}

    def essayer(c, id=""):
        return essai(id, compte_agit(), False)

    def instance_essayer(c, id=""):
        return essai(id, ctx.compte or "", True)

    def prouver_essai(c, res):
        m = brut(res["id"])
        return m is not None and m["essai_ts"] == res["maj"]["essai_ts"]

    def defaire_essai(c, res):
        a = res["avant"]
        db.ecrire("UPDATE modeles SET essai_ts=?, essai_ok=?, essai_s=?, essai_msg=? WHERE id=?", (a["essai_ts"], a["essai_ok"], a["essai_s"], a["essai_msg"], res["id"]))

    # ------------------------------------------------------------------ retirer
    def retrait(mid, compte, instance):
        m = exiger(mid, compte, instance)
        roles = [r["role"] for r in db.lire("SELECT role FROM roles WHERE modele_id=?", (m["id"],))]
        if roles:
            raise ValueError("ce modèle sert un rôle (%s) : change le rôle d'abord" % ", ".join(ROLES_CONNUS.get(r, r) for r in roles))
        if db.lire("SELECT 1 FROM choix WHERE modele_id=?", (m["id"],)):
            raise ValueError("ce modèle est le choix d'un compte : il doit en choisir un autre d'abord")
        db.ecrire("DELETE FROM modeles WHERE id=?", (m["id"],))
        ctx.emettre("modele.retire", objet=("modele", m["id"]), donnees={"id": m["id"], "nom": m["nom"]})
        return {"id": m["id"], "copie": m}

    def retirer(c, id=""):
        return retrait(id, compte_agit(), False)

    def instance_retirer(c, id=""):
        return retrait(id, ctx.compte or "", True)

    def prouver_retire(c, res):
        return brut(res["id"]) is None

    def defaire_retire(c, res):
        m = res["copie"]
        ks = list(m)
        db.ecrire("INSERT OR REPLACE INTO modeles(%s) VALUES (%s)" % (",".join(ks), ",".join("?" * len(ks))), [m[k] for k in ks])

    # ------------------------------------------------------------------ rôles et choix
    def role_lier(c, role="", modele_id=""):
        role = str(role or "").strip()
        if not RE_ROLE.fullmatch(role):
            raise ValueError("un rôle : 2 à 40 minuscules, chiffres ou _")
        avant = db.lire("SELECT modele_id FROM roles WHERE role=?", (role,))
        mid = str(modele_id or "").strip()
        if mid:
            m = brut(mid)
            if m is None or m["portee"] != "instance":
                raise ValueError("un rôle ne se lie qu'à un modèle de l'instance")
            db.ecrire("INSERT OR REPLACE INTO roles(role, modele_id) VALUES (?,?)", (role, mid))
        else:
            db.ecrire("DELETE FROM roles WHERE role=?", (role,))
        return {"role": role, "modele_id": mid, "avant": avant[0]["modele_id"] if avant else ""}

    def prouver_role(c, res):
        r = db.lire("SELECT modele_id FROM roles WHERE role=?", (res["role"],))
        return (r[0]["modele_id"] if r else "") == res["modele_id"]

    def defaire_role(c, res):
        if res["avant"]:
            db.ecrire("INSERT OR REPLACE INTO roles(role, modele_id) VALUES (?,?)", (res["role"], res["avant"]))
        else:
            db.ecrire("DELETE FROM roles WHERE role=?", (res["role"],))

    def choisir(c, modele_id=""):
        compte = compte_agit()
        avant = db.lire("SELECT modele_id FROM choix WHERE compte=?", (compte,))
        mid = str(modele_id or "").strip()
        if mid:
            exiger(mid, compte, False)
            db.ecrire("INSERT OR REPLACE INTO choix(compte, modele_id) VALUES (?,?)", (compte, mid))
        else:
            db.ecrire("DELETE FROM choix WHERE compte=?", (compte,))
        return {"compte": compte, "modele_id": mid, "avant": avant[0]["modele_id"] if avant else ""}

    def prouver_choix(c, res):
        r = db.lire("SELECT modele_id FROM choix WHERE compte=?", (res["compte"],))
        return (r[0]["modele_id"] if r else "") == res["modele_id"]

    def defaire_choix(c, res):
        if res["avant"]:
            db.ecrire("INSERT OR REPLACE INTO choix(compte, modele_id) VALUES (?,?)", (res["compte"], res["avant"]))
        else:
            db.ecrire("DELETE FROM choix WHERE compte=?", (res["compte"],))

    # ------------------------------------------------------------------ usage
    def usage(c, jours=30):
        depuis = datetime.fromtimestamp(time.time() - max(1, min(int(jours or 30), 365)) * 86400).strftime("%Y-%m-%d")
        lignes = [dict(r) for r in db.lire("SELECT * FROM usage WHERE jour>=? ORDER BY jour DESC, role, modele_id", (depuis,))]
        tot = {"appels": sum(x["appels"] for x in lignes), "echecs": sum(x["echecs"] for x in lignes), "entrees": sum(x["entrees"] for x in lignes), "sorties": sum(x["sorties"] for x in lignes)}
        return {"lignes": lignes, "total": tot}

    # ------------------------------------------------------------------ Ollama
    def nom_local_ok(nom):
        return bool(RE_NOM.fullmatch(nom)) and not nom.endswith(":")

    def ollama_telecharger(c, nom=""):
        nom = str(nom or "").strip()
        if not nom_local_ok(nom):
            raise ValueError("nom de modèle invalide")
        if db.lire("SELECT 1 FROM pulls WHERE nom=? AND etat IN ('attente','en cours')", (nom,)):
            raise ValueError("ce modèle est déjà en cours de téléchargement")
        pid = db.ecrire("INSERT INTO pulls(nom, demande_par, ts) VALUES (?,?,?)", (nom, ctx.compte or "", time.time()))
        return {"id": pid, "nom": nom}

    def prouver_pull(c, res):
        return bool(db.lire("SELECT 1 FROM pulls WHERE id=?", (res["id"],)))

    def defaire_pull(c, res):
        db.ecrire("DELETE FROM pulls WHERE id=? AND etat='attente'", (res["id"],))

    def moteur_pulls(c):
        """Tire un modèle à la fois ; la progression est écrite au fil du flux. Un échec se dit, il ne bloque pas la file."""
        r = db.lire("SELECT * FROM pulls WHERE etat='attente' ORDER BY id LIMIT 1")
        if not r:
            return {"tires": 0}
        p = r[0]
        db.ecrire("UPDATE pulls SET etat='en cours' WHERE id=?", (p["id"],))
        try:
            req = urllib.request.Request(hote_ollama() + "/api/pull", data=json.dumps({"model": p["nom"], "stream": True}).encode("utf-8"), method="POST")
            req.add_header("Content-Type", "application/json")
            dernier = ""
            with urllib.request.urlopen(req, timeout=900) as flux:
                for ligne in flux:
                    try:
                        j = json.loads(ligne.decode("utf-8", "replace"))
                    except ValueError:
                        continue
                    if j.get("error"):
                        raise RuntimeError(str(j["error"])[:200])
                    dernier = str(j.get("status") or dernier)
                    pc = int(100 * j["completed"] / j["total"]) if j.get("total") and j.get("completed") is not None else None
                    db.ecrire("UPDATE pulls SET detail=?, pourcent=COALESCE(?, pourcent) WHERE id=?", (dernier[:120], pc, p["id"]))
            db.ecrire("UPDATE pulls SET etat='fait', pourcent=100, detail=? WHERE id=?", (dernier[:120], p["id"]))
        except Exception as e:
            db.ecrire("UPDATE pulls SET etat='echec', detail=? WHERE id=?", (str(e)[:200], p["id"]))
        return {"tires": 1}

    def ollama_supprimer(c, nom=""):
        nom = str(nom or "").strip()
        if not nom_local_ok(nom):
            raise ValueError("nom de modèle invalide")
        ids = [r["id"] for r in db.lire("SELECT id FROM modeles WHERE fournisseur='ollama' AND nom=?", (nom,))]
        for i in ids:
            if db.lire("SELECT 1 FROM roles WHERE modele_id=?", (i,)) or db.lire("SELECT 1 FROM choix WHERE modele_id=?", (i,)):
                raise ValueError("ce modèle sert un rôle ou un choix : change-le d'abord")
        lire_json(hote_ollama() + "/api/delete", {"model": nom}, methode="DELETE", timeout=30)
        for i in ids:
            db.ecrire("DELETE FROM modeles WHERE id=?", (i,))
        return {"nom": nom, "retires": ids}

    def prouver_local_supprime(c, res):
        try:
            return res["nom"] not in [m["name"] for m in lister_locaux()]
        except Exception:
            return False

    def defaire_local_supprime(c, res):
        """Un modèle supprimé ne se restaure pas : il se retélécharge. Le retour remet donc le téléchargement en file."""
        if not db.lire("SELECT 1 FROM pulls WHERE nom=? AND etat IN ('attente','en cours')", (res["nom"],)):
            db.ecrire("INSERT INTO pulls(nom, demande_par, ts) VALUES (?,?,?)", (res["nom"], ctx.compte or "", time.time()))

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("pulls", moteur_pulls)
    for cid, f in (("fournisseurs", fournisseurs), ("lister", lister), ("locaux", locaux), ("usage", usage), ("completer", completer)):
        c.implementer(cid, f)
    c.implementer("ajouter", ajouter, prouver_ajoute, defaire_ajoute, simuler=lambda x, nom="", **_: "déclarerait le modèle « %s »" % nom)
    c.implementer("instance_ajouter", instance_ajouter, prouver_ajoute, defaire_ajoute, simuler=lambda x, nom="", **_: "déclarerait le modèle d'instance « %s »" % nom)
    c.implementer("essayer", essayer, prouver_essai, defaire_essai, simuler=lambda x, id="", **_: "ferait répondre le modèle %s" % id)
    c.implementer("instance_essayer", instance_essayer, prouver_essai, defaire_essai, simuler=lambda x, id="", **_: "ferait répondre le modèle d'instance %s" % id)
    c.implementer("retirer", retirer, prouver_retire, defaire_retire, simuler=lambda x, id="", **_: "retirerait le modèle %s" % id)
    c.implementer("instance_retirer", instance_retirer, prouver_retire, defaire_retire, simuler=lambda x, id="", **_: "retirerait le modèle d'instance %s" % id)
    c.implementer("role_lier", role_lier, prouver_role, defaire_role, simuler=lambda x, role="", modele_id="", **_: "lierait le rôle %s au modèle %s" % (role, modele_id))
    c.implementer("choisir", choisir, prouver_choix, defaire_choix, simuler=lambda x, modele_id="", **_: "choisirait le modèle %s" % modele_id)
    c.implementer("ollama_telecharger", ollama_telecharger, prouver_pull, defaire_pull, simuler=lambda x, nom="", **_: "téléchargerait le modèle local %s" % nom)
    c.implementer("ollama_supprimer", ollama_supprimer, prouver_local_supprime, defaire_local_supprime, simuler=lambda x, nom="", **_: "supprimerait le modèle local %s" % nom)
