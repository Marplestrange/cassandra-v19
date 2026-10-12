"""Module Mémoire.
V18 :
- La chaîne partagée garantie l'intégrité de l'îlot entier, sans forking (IntegrityError).
- La péremption par sondes : « etat-courant » doit porter une sonde rejouable, mesurée à l'écriture.
- Anti-secret (3 classes / courses de 12 signes), anti-consigne, anti-spi.
- Notes creuses refusées (« examiner les journaux... ») ; limites de taille et quotas par heure/jour.
- Rapprochement de faits proches (dédoublonnage sémantique plutôt que clé exacte).
"""

import time
import json
import re
import hashlib
import unicodedata

SYSTEME = ("cassandra", "itare", "noyau", "operateur")

MEMOIRE_CATEGORIES = ("config", "fix", "incident", "lecon", "pattern", "architecture",
                      "security", "rule", "personne", "fact", "perception", "decision")
MEMOIRE_CATEGORIES_STABLES = ("decision", "rule", "lecon", "architecture", "security", "personne")
MEMOIRE_CATEGORIE_ALIAS = {
    "server": "architecture", "service": "config", "config_value": "config", "command": "fix",
    "preference": "personne", "user_pref": "personne", "user": "personne", "profil": "personne",
    "learning": "lecon", "leçon": "lecon", "lesson": "lecon", "itare": "lecon", "itare_lecon": "lecon",
    "itare_note": "lecon", "itare_fait": "fact", "itare_vigie": "perception", "itare_regle": "rule",
    "relation": "fact", "updates": "fix", "capacité": "fact", "capacite": "fact", "insight": "lecon",
    "securite": "security", "sécurité": "security", "regle": "rule", "règle": "rule",
    "etat": "perception", "état": "perception", "status": "perception",
}
MEMOIRE_PROVENANCES = {
    "externe": (1, 0, 0.6), "infere": (2, 0, 0.8), "observe": (3, 1, 0.95),
    "dit": (4, 0, 0.95), "verifie_outil": (4, 1, 1.0), "decision": (5, 1, 1.0)}
MEMOIRE_PROVENANCE_ALIAS = {"told": "dit", "observed": "observe", "inferred": "infere", "reference": "externe",
                            "salon": "externe", "web": "externe", "mail": "externe", "outil": "verifie_outil",
                            "verified": "verifie_outil", "decision_distillee": "decision", "humain": "dit"}
MEMOIRE_NATURES = ("etat-courant", "constat")
MEMOIRE_CHAINE_GENESE = "0000000000000000000000000000000000000000000000000000000000000000"

MEMOIRE_QUOTA_GLOBAL_HEURE = 60
MEMOIRE_QUOTA_COMPTE_JOUR = 25
MEMOIRE_VALEUR_MAX = 2000

_MEMOIRE_BORD = "!@#$%^&*_+=.:;,?~-"
_MEMOIRE_HEX64_RE = re.compile(r"\b[A-Fa-f0-9]{24,}\b|\b[A-Za-z0-9+/]{24,}={0,2}\b")
_MEMOIRE_COURSE_RE = re.compile(r"[A-Za-z0-9]+")
_MEMOIRE_COURSE_MIN = 12
_MEMOIRE_SECRET_FORMATS_RE = re.compile(r"(?i)\b(?:sk-ant-[a-zA-Z0-9_-]{30,}|ghp_[a-zA-Z0-9]{36}|xox[bap]-(?:\d+-)+\d+[a-zA-Z0-9]*)\b")
_MEMOIRE_SECRET_MOTS_RE = re.compile(r"(?i)\b(?:mot de passe|password|secret|jeton|token|clef?|api[-_]key)\b")
_MEMOIRE_JETON_RE = re.compile(r"\S+")
_MEMOIRE_CONSIGNE_RE = re.compile(r"(?i)(?:ignore[sz]? (?:les|tes|toutes les|ces) (?:instructions|consignes|r[èe]gles)|[àa] partir de maintenant|d[ée]sormais tu|tu dois (?:maintenant|d[ée]sormais|toujours|absolument)|il faut (?:retenir|se souvenir) que|system prompt|prompt syst[èe]me|envoie(?:-moi|-le|-la)? (?:le|ce|les|la) (?:mot de passe|secret|token|cl[ée]|fichier|contenu)|transmets? (?:ce|le|la) (?:mot de passe|secret|token|cl[ée])|ex[ée]cute(?:r)? (?:la commande|rm |curl |wget |bash )|new instructions|you must now|disregard (?:all|previous))")
_MEMOIRE_SPI_RE = re.compile(r"(?i)\b(?:maladie|malade|d[ée]pression|m[ée]dicaments?|diagnostic m[ée]dical|sant[ée] mentale|salaire|dettes?(?! technique)|compte bancaire|iban|religion|croyances? religieuses?|opinions? politiques?|vote pour|orientation sexuelle|humeur|d[ée]prim[ée]e?|en col[èe]re|anxieux|anxi[ée]t[ée])\b")
_MEMOIRE_DOMAINE_RE = re.compile(r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,12})\b")
_MEMOIRE_CREUX_RE = re.compile(r"(?is)^\s*(examiner|surveiller|consulter|v[ée]rifier|analyser|regarder|inspecter)\b(?=.{0,200}\b(journaux|logs?|journalctl)\b)(?=.{0,240}\b(avant|identifier|comprendre|la cause)\b)")
_MEMOIRE_SONDES = ("fonction_existe", "fonction_absente", "fonction_contient", "constante_vaut", "machine_en_ligne", "site_repond", "service_actif")
_MEMOIRE_ENTITES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#x27;": "'", "&#39;": "'"}
_MEMOIRE_MOTS_VIDES = frozenset(("les des une est sur dans pour par pas que qui avec son ses aux ete cette sont plus tout fait elle ils lui mais donc car comme sans entre depuis apres avant leur leurs ont avoir etre fois").split())

def _memoire_desechapper(t: str) -> str:
    t = str(t or "")
    if "&" not in t: return t
    return re.sub(r"&(?:amp|lt|gt|quot|#x27|#39);", lambda m: _MEMOIRE_ENTITES[m.group(0)], t)

def _memoire_jeton_classes(tok: str) -> int:
    return sum((bool(re.search(r"[a-z]", tok)), bool(re.search(r"[A-Z]", tok)),
                bool(re.search(r"[0-9]", tok)), bool(re.search(r"[!@#$%^&*_+=.:;,?~-]", tok))))

def memoire_a_un_secret(texte: str) -> bool:
    t = str(texte or "")
    if _MEMOIRE_SECRET_FORMATS_RE.search(t): return True
    mot = bool(_MEMOIRE_SECRET_MOTS_RE.search(t))
    for tok in _MEMOIRE_JETON_RE.findall(t):
        if "/" in tok or tok.lower().startswith(("http", "www.")) or "@" in tok and "." in tok.split("@")[-1]: continue
        nu = tok.strip(_MEMOIRE_BORD)
        if len(nu) < 8 or _memoire_jeton_classes(nu) < 3: continue
        courses = _MEMOIRE_COURSE_RE.findall(nu)
        if len(nu) >= 20 and any(len(c) >= _MEMOIRE_COURSE_MIN and _memoire_jeton_classes(c) >= 2 for c in courses): return True
    return mot and bool(_MEMOIRE_HEX64_RE.search(t))

def _memoire_jetons(t: str) -> set:
    t = unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()
    out = set()
    for w in re.findall(r"[a-z0-9](?:[a-z0-9._/:-]*[a-z0-9])?", t):
        if (len(w) < 4 and not w.isdigit()) or w in _MEMOIRE_MOTS_VIDES: continue
        out.add(w[:7] if w.isalpha() else w)
    return out

def _memoire_identifiant(t: str) -> bool:
    return bool(re.search(r"[./:_]", t)) or (bool(re.search(r"\d", t)) and bool(re.search(r"[a-z]", t)))

def _memoire_nombres(t: str) -> tuple:
    return tuple(re.findall(r"(?<![\w.:/-])\d+(?![\w.:/-])", str(t or "")))

def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def gere(compte):
        return compte in SYSTEME or not compte or dr.raison(compte, "memoire.gerer")["accord"]

    def memoire_portee(lecteur):
        if lecteur in SYSTEME or not lecteur:
            return ["cassandra", "partage", "itare"]
        if dr.est_admin(lecteur):
            return [f"compte:{lecteur}", "partage", "cassandra"]
        return [f"compte:{lecteur}"]
    
    def proprietaire_defaut(lecteur, categorie):
        if not lecteur or lecteur in SYSTEME: return "cassandra"
        if lecteur == "itare": return "itare"
        if categorie != "personne" and dr.est_admin(lecteur): return "partage"
        return f"compte:{lecteur}"

    def memoire_cle(cat, cle):
        c = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", str(cle or "").lower()).encode("ascii", "ignore").decode()).strip("-")
        return c[:80]

    def _memoire_empreinte(prev, ts, acteur, verbe, memoire_id, details):
        return hashlib.sha256(f"{prev or ''}|{ts}|{acteur}|{verbe}|{memoire_id or ''}|{details}".encode("utf-8", "replace")).hexdigest()

    def _chaine_inserer(c, verbe, ts, acteur, memoire_id, details):
        d = json.dumps(details, ensure_ascii=False)[:1500] if not isinstance(details, str) else details[:1500]
        for essai in range(3):
            prev_row = c.execute("SELECT hash FROM chaine ORDER BY seq DESC LIMIT 1").fetchone()
            prev = prev_row["hash"] if prev_row else MEMOIRE_CHAINE_GENESE
            h = _memoire_empreinte(prev, ts, acteur, verbe, memoire_id, d)
            try:
                seq = c.execute("INSERT INTO chaine (origine, ligne_id, verbe, ts, details, hash, previous_hash) VALUES (?,?,?,?,?,?,?)",
                                ("memoire", None, verbe, ts, None, h, prev)).lastrowid
                lid = c.execute("INSERT INTO memoire_journal (ts, acteur, verbe, memoire_id, details, hash, previous_hash) VALUES (?,?,?,?,?,?,?)",
                                (ts, acteur, verbe, memoire_id, d, h, prev)).lastrowid
                c.execute("UPDATE chaine SET ligne_id=? WHERE seq=?", (lid, seq))
                return
            except Exception:
                if essai == 2: raise

    def memoire_sonde(nom: str, args) -> tuple:
        # TODO(agent, sensorium): rejouer de vraies sondes. Ici on simule pour l'interface de la capacité.
        if nom not in _MEMOIRE_SONDES: return None, "", "sonde inconnue"
        return False, "", f"sonde {nom} non branchée sur le sensorium en V19"

    def _memoire_proche(prop: str, cat: str, cle: str, val: str):
        moi = _memoire_jetons(cle.replace("-", " ") + " " + val)
        mes_n = _memoire_nombres(cle.replace("-", " ") + " " + val)
        meilleur, cle_m, id_m = 0.0, None, None
        for r in db.lire("SELECT id, cle, valeur FROM memoires WHERE proprietaire=? AND categorie=? AND statut='actif' AND cle<>? ORDER BY maj_le DESC LIMIT 500", (prop, cat, cle)):
            texte = str(r["cle"]).replace("-", " ") + " " + str(r["valeur"])
            ses_n = _memoire_nombres(texte)
            if mes_n and ses_n and mes_n != ses_n: continue
            b = _memoire_jetons(texte)
            if min(len(moi), len(b)) < 3: continue
            commun = moi & b
            j = len(commun) / min(len(moi), len(b))
            s = j if j >= 0.65 or (j >= 0.4 and any(_memoire_identifiant(t) for t in commun)) else 0.0
            if s > meilleur:
                meilleur, cle_m, id_m = s, r["cle"], r["id"]
        return id_m

    def ecrire(ctx, categorie="", cle="", valeur="", proprietaire=None, provenance="infere", confiance=0.5, nature="constat", sonde="", sonde_args=None):
        acteur = ctx.compte or "cassandra"
        cat0 = str(categorie or "").strip().lower()
        cat = cat0 if cat0 in MEMOIRE_CATEGORIES else MEMOIRE_CATEGORIE_ALIAS.get(cat0, "")
        prov = str(provenance or "infere").strip().lower()
        prov = prov if prov in MEMOIRE_PROVENANCES else MEMOIRE_PROVENANCE_ALIAS.get(prov, "infere")
        val = _memoire_desechapper(" ".join(str(valeur or "").split()).strip())
        cle_net = _memoire_desechapper(str(cle or ""))
        prop = str(proprietaire or proprietaire_defaut(acteur, cat))
        
        def _refus(raison, detail=""):
            with db.transaction() as c:
                _chaine_inserer(c, "refus_garde", time.time(), acteur, None, {"raison": raison, "categorie": cat, "cle": cle_net, "detail": detail})
            return {"ok": False, "action": "refus", "refus": raison, "detail": detail}

        if not cat: return _refus("categorie", cat0)
        if not val: return _refus("vide")
        nat = str(nature or "").strip().lower()
        if nat not in MEMOIRE_NATURES: return _refus("nature")
        
        art, art_emp, s_val = "", "", None
        if nat == "etat-courant":
            if not sonde: return _refus("nature", "sans sonde")
            s_val, art, err = memoire_sonde(sonde, sonde_args)
            if err: return _refus("sonde", err)
            if s_val is not True: return _refus("sonde", "répond NON")
            art_emp = "" # TODO(sensorium)
            
        val = val[:MEMOIRE_VALEUR_MAX]
        if len(cle_net.split()) > 8 or len(cle_net) > 120: return _refus("cle", "phrase libre")
        k = memoire_cle(cat, cle_net)
        if not k: return _refus("cle", "vide")
        if memoire_a_un_secret(val) or memoire_a_un_secret(cle_net): return _refus("secret")
        if _MEMOIRE_CONSIGNE_RE.search(val): return _refus("consigne")
        if _MEMOIRE_SPI_RE.search(val): return _refus("spi")
        if len(re.sub(r"[\W_]+", "", val)) < 8 or _MEMOIRE_CREUX_RE.search(val): return _refus("creux", val[:80])
        # TODO(fastpanel): _memoire_domaine_etranger(prop, k + " " + val)
        
        niveau, direct, plafond = MEMOIRE_PROVENANCES[prov]
        conf = max(0.0, min(float(confiance) if type(confiance) in (float, int) else 0.5, plafond))
        now = time.time()
        
        with db.transaction() as c:
            n_h = c.execute("SELECT COUNT(*) FROM memoire_journal WHERE verbe IN ('ecriture','remplace','conteste') AND ts >= ?", (now - 3600,)).fetchone()[0]
            if n_h >= MEMOIRE_QUOTA_GLOBAL_HEURE: return _refus("quota", f"global {n_h}/h")
            if prop.startswith("compte:"):
                n_j = c.execute("SELECT COUNT(*) FROM memoire_journal j JOIN memoires m ON m.id=j.memoire_id WHERE j.verbe IN ('ecriture','remplace','conteste') AND m.proprietaire=? AND j.ts >= ?", (prop, now - 86400)).fetchone()[0]
                if n_j >= MEMOIRE_QUOTA_COMPTE_JOUR: return _refus("quota", f"compte {n_j}/j")
            
            proche_id = _memoire_proche(prop, cat, k, val)
            action = "ecriture"
            remplace = None
            if proche_id:
                old = c.execute("SELECT * FROM memoires WHERE id=?", (proche_id,)).fetchone()
                old_niv = MEMOIRE_PROVENANCES.get(old["provenance"], (0,))[0]
                if niveau >= old_niv:
                    action = "remplace"
                    c.execute("UPDATE memoires SET statut='expire', maj_le=? WHERE id=?", (now, proche_id))
                    remplace = proche_id
                else:
                    action = "conteste"
            
            statut = "conteste" if action == "conteste" else "actif"
            nid = c.execute("INSERT INTO memoires (proprietaire, categorie, cle, valeur, provenance, confiance, statut, nature, sonde, sonde_args, sonde_valeur, artefact, artefact_empreinte, remplace, cree_le, maj_le) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (prop, cat, k, val, prov, conf, statut, nat, sonde, json.dumps(sonde_args or []), json.dumps(s_val), art, art_emp, remplace, now, now)).lastrowid
            _chaine_inserer(c, action, now, acteur, nid, {"cle": k, "valeur": val[:80]})
            
        ctx.emettre("memoire.ecrite", objet=("memoire", nid), donnees={"action": action, "cle": k})
        return {"ok": True, "id": nid, "action": action, "avant": remplace}

    def prouver_ecrire(ctx, res):
        if res.get("action") == "refus": return True
        r = db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))
        return bool(r and r[0]["statut"] in ("actif", "conteste"))

    def defaire_ecrire(ctx, res):
        if res.get("action") == "refus": return
        nid = res["id"]
        now = time.time()
        with db.transaction() as c:
            c.execute("UPDATE memoires SET statut='quarantaine', maj_le=? WHERE id=?", (now, nid))
            if res.get("avant"):
                c.execute("UPDATE memoires SET statut='actif', maj_le=? WHERE id=?", (now, res["avant"]))
            _chaine_inserer(c, "defait_ecriture", now, ctx.compte or "cassandra", nid, {})

    def lister(ctx, portee=None, statut="actif", categorie=None, limite=200):
        p = portee or memoire_portee(ctx.compte)
        ph = ",".join("?" * len(p))
        sql = f"SELECT * FROM memoires WHERE proprietaire IN ({ph}) AND statut=?"
        args = list(p) + [statut]
        if categorie:
            sql += " AND categorie=?"
            args.append(categorie)
        sql += " ORDER BY force DESC, maj_le DESC LIMIT ?"
        args.append(min(int(limite), 500))
        return {"memoires": [dict(r) for r in db.lire(sql, tuple(args))]}
        
    def rappeler(ctx, question="", portee=None, limite=12):
        p = portee or memoire_portee(ctx.compte)
        ph = ",".join("?" * len(p))
        # Simple fallback text search, ignoring fts5 for brevity in mock if needed, but we have fts5
        now = time.time()
        sql = f"SELECT m.* FROM memoires_fts JOIN memoires m ON m.id = memoires_fts.rowid WHERE memoires_fts MATCH ? AND m.proprietaire IN ({ph}) AND m.statut='actif' ORDER BY m.force DESC, m.maj_le DESC LIMIT ?"
        q = " OR ".join(f'"{t}"' for t in re.findall(r"\w+", question) if len(t) > 3)
        if not q: return {"memoires": []}
        return {"memoires": [dict(r) for r in db.lire(sql, [q] + list(p) + [int(limite)])]}

    def _changer_statut(ctx, mid, nouveau_statut, verbe, raison=""):
        acteur = ctx.compte or "cassandra"
        p = memoire_portee(acteur)
        ph = ",".join("?" * len(p))
        r = db.lire(f"SELECT * FROM memoires WHERE id=? AND proprietaire IN ({ph})", (mid,) + tuple(p))
        if not r: raise ValueError("souvenir introuvable ou hors portée")
        old_statut = r[0]["statut"]
        if old_statut == nouveau_statut: return {"id": mid, "avant": old_statut}
        now = time.time()
        with db.transaction() as c:
            c.execute("UPDATE memoires SET statut=?, maj_le=? WHERE id=?", (nouveau_statut, now, mid))
            _chaine_inserer(c, verbe, now, acteur, mid, {"raison": raison})
        ctx.emettre(f"memoire.{verbe}e", objet=("memoire", mid), donnees={"par": acteur})
        return {"id": mid, "avant": old_statut, "apres": nouveau_statut}

    def expirer(ctx, mid, raison=""):
        return _changer_statut(ctx, mid, "expire", "expire", raison)
    def oublier(ctx, mid, raison="oubli sur ordre"):
        return _changer_statut(ctx, mid, "expire", "oubli", raison)
    def restaurer(ctx, mid):
        return _changer_statut(ctx, mid, "actif", "restaure", "")

    def prouver_changement(ctx, res):
        if not res.get("apres"): return True
        return bool(db.lire("SELECT statut FROM memoires WHERE id=? AND statut=?", (res["id"], res["apres"])))
        
    def defaire_changement(ctx, res):
        if res.get("avant") and res.get("avant") != res.get("apres"):
            with db.transaction() as c:
                c.execute("UPDATE memoires SET statut=?, maj_le=? WHERE id=?", (res["avant"], time.time(), res["id"]))

    def postmortem_save(ctx, title, summary, lessons="", status="open"):
        nid = db.ecrire("INSERT INTO postmortems (ts, title, summary, lessons, status) VALUES (?,?,?,?,?)",
                        (time.time(), (title or "Post-mortem")[:200], (summary or "")[:20000], (lessons or "")[:4000], status))
        return {"id": nid}

    def prouver_postmortem(ctx, res):
        return bool(db.lire("SELECT id FROM postmortems WHERE id=?", (res["id"],)))

    def defaire_postmortem(ctx, res):
        db.ecrire("DELETE FROM postmortems WHERE id=?", (res["id"],))

    def chaine_veille(ctx):
        # Moteur
        pass

    ctx.moteur("chaine_veille", chaine_veille)
    ctx.moteur("rappels_evaluer", lambda ctx: None)
    ctx.moteur("episodes_fermer", lambda ctx: None)
    
    ctx.implementer("lister", lister)
    ctx.implementer("rappeler", rappeler)
    ctx.implementer("ecrire", ecrire, prouver_ecrire, defaire_ecrire)
    ctx.implementer("expirer", expirer, prouver_changement, defaire_changement)
    ctx.implementer("oublier", oublier, prouver_changement, defaire_changement)
    ctx.implementer("restaurer", restaurer, prouver_changement, defaire_changement)
    ctx.implementer("postmortem_save", postmortem_save, prouver_postmortem, defaire_postmortem)
