# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les notes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : CN
# VERSION CN : 0.1.0  #aeaa0b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les notes.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=aeaa0b ▼▼▼
"""Les notes.

Porté de la V18 (`note_*`, `notes_*`, `ca_*`, `_nt_*`), avec ses leçons :
  - le NUMÉRO (N-0007) est l'identité : il ne change jamais et n'est jamais réattribué (corbeille et purge comprises, compteur à part) ; le titre et le dossier
    se changent sans casser un renvoi ; une note absorbée par une fusion redirige vers la fusion, un vieux renvoi tombe donc toujours juste ;
  - rien ne se supprime : corbeille, et chaque écriture laisse la version d'AVANT (jamais d'après : après, l'ancien contenu n'existe déjà plus) ; revenir à une
    version est lui-même versionné ;
  - les notes sont à la personne : l'administrateur ne les voit pas, un numéro forgé dans une requête ne rend rien d'un autre compte ;
  - un dossier dit OÙ c'est rangé (un seul, deux niveaux au plus), une étiquette dit DE QUOI ça parle (autant qu'on veut) ; supprimer un dossier ne supprime
    aucune note, elles remontent d'un cran ; un projet fait ranger la note dans le dossier de son nom, sans toucher à un dossier que la personne a choisi ;
  - les cases à cocher sont lues avec leur NUMÉRO DE LIGNE (deux cases peuvent porter le même texte) ; liées à une tâche, elles ne sont jamais recopiées ;
  - un lien de partage porte un jeton tiré au sort, jamais un chemin ; il expire, se retire immédiatement, ne compte que les vraies ouvertures et refuse les
    mots de passe devinés à la chaîne ; son mot de passe n'est jamais gardé en clair ;
  - une proposition (mention non liée, ménage, doublon) est proposée, jamais écrite : une note effacée par une règle serait perdue sans témoin ;
  - un signal de santé qui n'a rien à dire SE TAIT, et un signal qui lève le dit au lieu de disparaître.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import re
import secrets
import time
import zipfile
from datetime import datetime

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
ETATS = {"brouillon": "Brouillon", "cours": "En cours", "stable": "Stabilisée", "archive": "Archivée"}
TRIS = ("recent", "ancien", "titre", "poids", "usage", "jamais")
FILTRES = ("toutes", "epinglees", "projet", "orphelines", "menage", "arelire", "ouvertes")
FORMATS = ("html", "md", "txt")
NATURES = ("note", "projet", "tache", "contact", "site", "domain", "serveur", "certificat", "constat", "evenement", "mail", "document", "rappel")
PROFONDEUR = 2
MAX_VERSIONS = 20
MAX_PARTAGES = 200
JOURS_PARTAGE = 30
ZIP_NOTES = 400
ZIP_OCTETS = 60 * 1024 * 1024
ASSEZ = 400                         # en deçà, un brouillon n'a pas à se faire reprocher son isolement
MENTION_MIN = 4
ESSAIS_MDP, FENETRE_MDP = 8, 600
RE_LIEN = re.compile(r"!?\[\[([^\]|]{1,160})(?:\|[^\]]*)?\]\]")
RE_CASE = re.compile(r"^(\s*[-*]\s+)\[([ xX])\]\s?(.*)$")
RE_ANCRE = re.compile(r"\s\^([\w-]{2,40})\s*$")
RE_NUM = re.compile(r"^N-?0*(\d+)$", re.I)
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INDESIRABLE = re.compile(r"(?i)\b(spam|ind[ée]sirable|viagra|lottery|prize|winner|casino|crypto\s+bonus)\b")


def num_dit(n):
    return "N-%04d" % int(n)


def segment_ok(s):
    s = str(s or "").strip()
    return bool(s) and len(s) <= 64 and s not in (".", "..") and not s.startswith(".") and not any(x in s for x in ("/", "\\", "\x00"))


def dossier_ok(ch):
    ch = str(ch or "").strip().replace("\\", "/")
    if not ch:
        return True
    if ch.startswith("/") or (len(ch) > 1 and ch[1] == ":"):
        return False
    parts = ch.strip("/").split("/")
    return len(parts) <= PROFONDEUR and all(segment_ok(x) for x in parts)


def dossier_propre(ch):
    brut_ = str(ch or "").strip().replace("\\", "/")
    if not dossier_ok(brut_):                      # un chemin absolu se refuse, il ne se rabote pas : on rendrait un autre dossier que celui demandé
        raise ValueError("dossier refusé — %d niveaux au plus, ni « .. » ni nom commençant par un point" % PROFONDEUR)
    return brut_.strip("/")


def dossier_projet(projet):
    s = re.sub(r"[/\\\x00]+", "-", str(projet or "")).strip().strip(".").strip()[:60].strip()
    return s if segment_ok(s) else ""


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


def liens_de(corps):
    """`[[N-0011]]` vers une note, `[[projet:12]]` vers un projet ; `![[…]]` inclut au lieu de renvoyer ; `[[N-0012#^ancre]]` vise un paragraphe. Le calcul est un POINT D'ÉVOLUTION : points/EC_liens_de.py."""
    return _point("liens_de", {"corps": corps})["valeur"]


def cases_de(corps):
    out = []
    for i, ligne in enumerate(str(corps or "").split("\n")):
        m = RE_CASE.match(ligne)
        if m:
            out.append({"ligne": i, "faite": m.group(2).lower() == "x", "texte": m.group(3).strip()})
    return out


def ancres_de(corps):
    out = []
    for i, ligne in enumerate(str(corps or "").split("\n")):
        m = RE_ANCRE.search(ligne)
        if m:
            out.append({"ligne": i, "ancre": m.group(1), "texte": RE_ANCRE.sub("", ligne).strip()[:120]})
    return out


def stats(corps):
    mots = len([x for x in re.split(r"\s+", str(corps or "")) if x])
    return {"mots": mots, "lecture_min": max(1, int(round(mots / 200.0))) if mots else 0}


def jours_depuis(d):
    """Jours depuis une date AAAA-MM-JJ ; -1 si illisible (une date de travers ne doit pas faire taire un signal)."""
    try:
        return int((time.time() - time.mktime(time.strptime(str(d)[:10], "%Y-%m-%d"))) / 86400)
    except (ValueError, OverflowError):
        return -1


def etat_de(n, cases):
    e = str(n.get("etat") or "").strip()
    if e in ETATS:
        return e
    return "cours" if cases and not all(c["faite"] for c in cases) else "brouillon"


def titre_de(corps, repli="note"):
    for ligne in str(corps or "").split("\n"):
        t = ligne.strip().lstrip("#").strip()
        if t:
            return t[:140]
    return repli


def date_iso(v):
    v = str(v or "").strip()[:10]
    if v and not RE_DATE.match(v):
        raise ValueError("date attendue au format AAAA-MM-JJ")
    if v:
        datetime.strptime(v, "%Y-%m-%d")
    return v


def norm_domaine(ref):
    r = str(ref or "").strip().lower()
    r = re.sub(r"^[a-z]+://", "", r).split("/")[0]
    return r[4:] if r.startswith("www.") else r


def echapper(t):
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def inline(t):
    t = echapper(t)
    t = RE_LIEN.sub(lambda m: "<b>%s</b>" % m.group(1), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def md_vers_html(md, appeler):
    """Rendu suffisant pour lire et imprimer : titres, listes, citations, gras, code. Un moteur Markdown complet serait un second moteur à maintenir. Le calcul est un POINT D'ÉVOLUTION : points/EC_md_vers_html.py."""
    return appeler("md_vers_html", {"md": md})["html"]


def lire_entete(texte, appeler):
    """Un fichier sans en-tête reste une note valide : on ne refuse pas une note écrite à la main dans un éditeur. Le calcul est un POINT D'ÉVOLUTION : points/EC_lire_entete.py."""
    return appeler("lire_entete", {"texte": texte})["valeur"]


def hacher_mdp(mdp):
    sel = secrets.token_hex(8)
    return "%s$%s" % (sel, hashlib.scrypt(str(mdp).encode("utf-8"), salt=sel.encode(), n=2 ** 14, r=8, p=1, dklen=32).hex())


def mdp_ok(range_, donne):
    """Comparaison en TEMPS CONSTANT : une comparaison ordinaire fuit sa réponse par sa durée."""
    if not range_:
        return True
    try:
        sel, h = str(range_).split("$", 1)
        calc = hashlib.scrypt(str(donne or "").encode("utf-8"), salt=sel.encode(), n=2 ** 14, r=8, p=1, dklen=32).hex()
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(calc, h)


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage
    essais = {}                      # jeton -> horodatages des mots de passe faux (en mémoire : un redémarrage vide le compteur, pas le lien)

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("une note est celle d'un compte : aucun compte n'agit")
        return c

    def qui_agit(compte):
        """Le compte pour une personne, le nom de l'agent sinon : c'est ce que raconte l'activité."""
        a = ctx.acteur or ""
        return compte if a in ("", "humain", "compte") else a

    # ------------------------------------------------------------------ accès
    def champs(r):
        d = dict(r)
        d["etiquettes"] = json.loads(d.get("etiquettes") or "[]")
        d["rattache"] = json.loads(d.get("rattache") or "[]")
        d["ref"] = num_dit(d["num"])
        return d

    def toutes(compte, ou="vivante"):
        cond = {"vivante": " AND corbeille_at IS NULL", "corbeille": " AND corbeille_at IS NOT NULL", "toutes": ""}[ou]
        return [champs(r) for r in db.lire("SELECT * FROM notes WHERE compte=?" + cond + " ORDER BY id", (compte,))]

    def resoudre(ref, compte, ou="vivante"):
        """Numéro (avec redirection d'une note absorbée), puis titre. Le numéro d'abord : c'est la seule référence qui survit à un renommage."""
        ref = str(ref or "").strip().split("#")[0].strip()
        if not ref:
            return None
        m = RE_NUM.match(ref)
        if m:
            n = int(m.group(1))
            for _ in range(6):
                r = db.lire("SELECT * FROM notes WHERE compte=? AND num=?", (compte, n))
                if not r:
                    return None
                r = r[0]
                if r["corbeille_at"] is None:
                    return champs(r) if ou in ("vivante", "toutes") else None
                if ou == "vivante" and r["redirige"]:
                    n = r["redirige"]
                    continue
                return champs(r) if ou in ("corbeille", "toutes") else None
            return None
        bas = ref.casefold()
        for r in db.lire("SELECT * FROM notes WHERE compte=? ORDER BY id", (compte,)):
            if r["titre"].casefold() == bas and ((r["corbeille_at"] is None) == (ou != "corbeille") or ou == "toutes"):
                return champs(r)
        return None

    def exiger(ref, compte, ou="vivante"):
        n = resoudre(ref, compte, ou)
        if n is None:
            raise ValueError("note introuvable" if ou != "corbeille" else "note introuvable dans la corbeille")
        return n

    def numero(compte):
        with db.transaction() as cx:
            cx.execute("INSERT OR IGNORE INTO compteurs(compte, dernier) VALUES (?, 0)", (compte,))
            cx.execute("UPDATE compteurs SET dernier = MAX(dernier, COALESCE((SELECT MAX(num) FROM notes WHERE compte=?), 0)) + 1 WHERE compte=?", (compte, compte))
            return cx.execute("SELECT dernier FROM compteurs WHERE compte=?", (compte,)).fetchone()[0]

    def noter(note_id, quoi, det="", qui=""):
        return db.ecrire("INSERT INTO activite(note_id, ts, quoi, det, qui) VALUES (?,?,?,?,?)", (note_id, time.time(), quoi[:80], str(det)[:180], str(qui)[:80]))

    def versionner(n, auteur, motif):
        vid = db.ecrire("INSERT INTO versions(note_id, ts, auteur, motif, titre, corps) VALUES (?,?,?,?,?,?)", (n["id"], time.time(), str(auteur)[:60], str(motif or "modification")[:80], n["titre"], n["corps"]))
        for r in db.lire("SELECT id FROM versions WHERE note_id=? ORDER BY id DESC LIMIT -1 OFFSET ?", (n["id"], MAX_VERSIONS)):
            db.ecrire("DELETE FROM versions WHERE id=?", (r["id"],))
        return vid

    def dossier_existe(compte, ch):
        return not ch or bool(db.lire("SELECT 1 FROM dossiers WHERE compte=? AND chemin=?", (compte, ch)))

    def creer_dossier(compte, ch):
        """Crée le dossier et ses parents. Rend les chemins réellement créés (pour le retour)."""
        faits = []
        parts = ch.split("/")
        for i in range(1, len(parts) + 1):
            p = "/".join(parts[:i])
            if not dossier_existe(compte, p):
                db.ecrire("INSERT INTO dossiers(compte, chemin) VALUES (?,?)", (compte, p))
                faits.append(p)
        return faits

    def propres_etiquettes(v):
        out = []
        for x in (v or []):
            e = str(x).strip()[:40]
            if e and e not in out:
                out.append(e)
        return out[:12]

    def propres_rattaches(v):
        out = []
        for x in (v or []):
            t = str(x or "").strip()
            nature, _, cible = t.partition(":")
            if nature not in NATURES or not cible.strip():
                raise ValueError("rattachement « %s » : nature:référence attendue (%s)" % (t[:40], ", ".join(NATURES)))
            t = "%s:%s" % (nature, cible.strip()[:120])
            if t not in out:
                out.append(t)
        return out[:40]

    # ------------------------------------------------------------------ les cibles des renvois
    def existe_ailleurs(kind, ref, memo):
        """Une cible hors des notes : on la lit auprès de son module, pour CE compte. None = non vérifiable ici (ce n'est pas « morte »)."""
        cle = (kind, ref)
        if cle in memo:
            return memo[cle]
        r = None
        try:
            if kind == "projet":
                e = ctx.executer_lecture("projets.equipe", id=int(ref))
                r = {"existe": bool(e), "titre": (e or {}).get("projet") or ref}
            elif kind == "tache":
                f = ctx.executer_lecture("taches.fiche", id=int(ref))
                r = {"existe": bool(f), "titre": ((f or {}).get("tache") or {}).get("texte") or ref}
        except Exception:
            r = {"existe": False, "titre": ref} if kind in ("projet", "tache") else None
        memo[cle] = r
        return r

    def liens_resolus(corps, vivantes, memo=None):
        memo = {} if memo is None else memo
        par_num = {n["num"]: n for n in vivantes}
        par_titre = {n["titre"].casefold(): n for n in vivantes}
        out = []
        for l in liens_de(corps):
            d = dict(l, titre=l["ref"], existe=None)
            if l["kind"] == "note":
                ref = l["ref"].split("#")[0].strip()
                m = RE_NUM.match(ref)
                cible = par_num.get(int(m.group(1))) if m else par_titre.get(ref.casefold())
                d["existe"] = cible is not None
                if cible:
                    d["id"], d["titre"] = cible["ref"], cible["titre"]
            else:
                ref = l["ref"]
                r = existe_ailleurs(l["kind"], ref, memo)
                if r is not None:
                    d["existe"], d["titre"] = r["existe"], r["titre"]
            out.append(d)
        return out

    def graphe(vivantes):
        """Qui cite qui, en un seul balayage. Le calcul est un POINT D'ÉVOLUTION : points/EC_graphe.py (les numéros de note, clés d'un objet JSON, redeviennent des entiers ici)."""
        r = ctx.point("graphe", {"vivantes": vivantes})
        return ({int(k): v for k, v in r["sortants"].items()}, {int(k): v for k, v in r["entrants"].items()}, {int(k): v for k, v in r["titres"].items()})

    # ------------------------------------------------------------------ santé
    def sg_liens(f):
        morts = [l for l in f["liens"] if l.get("existe") is False]
        if morts:
            return ("avoir", "%d renvoi(s) sans cible : %s" % (len(morts), ", ".join(str(l["ref"]) for l in morts[:3])), 30)
        verifies = [l for l in f["liens"] if l.get("existe")]
        return ("info", "Les %d cibles existent." % len(verifies), 0) if verifies and len(verifies) == len(f["liens"]) else None

    def sg_orpheline(f):
        if f["octets"] < ASSEZ:
            return None
        if not f["liens"] and not f["entrants"] and not f["etiquettes"] and not f["projet"]:
            return ("avoir", "Rien ne mène à cette note et elle ne mène nulle part : elle sera introuvable dans six mois.", 20)

    def sg_jamais_relue(f):
        if f["octets"] < ASSEZ:
            return None
        j = jours_depuis(f["creee"])
        if not f["vues"] and j > 14:
            return ("info", "Écrite il y a %d jours, jamais rouverte." % j, 5)

    def sg_taches(f):
        ouvertes = [t for t in f["taches"] if not t["faite"]]
        if not ouvertes:
            return None
        j = jours_depuis(f["modifiee"][:10])
        if j > 7:
            return ("avoir", "%d tâche(s) ouverte(s), et rien n'a bougé depuis %d jours." % (len(ouvertes), j), 25)
        return ("info", "%d tâche(s) ouverte(s)." % len(ouvertes), 0)

    def sg_relire(f):
        d = f["relire"]
        if not d:
            return None
        return ("avoir", "La relecture était prévue le %s." % d, 35) if jours_depuis(d) >= 0 else ("info", "Relecture prévue le %s." % d, 0)

    def sg_titres(f):
        if f["octets"] > 2500 and "\n##" not in "\n" + f["corps"]:
            return ("info", "Longue et sans intertitres : elle ne se parcourt pas.", 10)

    SANTE = {"liens": ("Renvois", sg_liens), "orphelin": ("Isolement", sg_orpheline), "relue": ("Relecture", sg_jamais_relue), "taches": ("Tâches", sg_taches),
             "relire": ("Échéance de relecture", sg_relire), "titres": ("Structure", sg_titres)}

    def sante(f):
        out = []
        for cle, (nom, fn) in SANTE.items():
            try:
                r = fn(f)
            except Exception as e:
                out.append({"cle": cle, "n": nom, "niveau": "avoir", "poids": 1, "detail": "signal en panne : %s" % str(e)[:90]})
                continue
            if r:
                out.append({"cle": cle, "n": nom, "niveau": r[0], "detail": r[1], "poids": r[2]})
        return sorted(out, key=lambda x: -x["poids"])

    # ------------------------------------------------------------------ lectures
    def date_dit(ts):
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""

    def resume(n, sortants, entrants):
        cs = cases_de(n["corps"])
        return {"id": n["ref"], "num": n["num"], "titre": n["titre"], "dossier": n["dossier"],
                "apercu": " ".join(x.strip() for x in n["corps"].split("\n") if x.strip() and not x.strip().startswith("#"))[:200],
                "etiquettes": n["etiquettes"], "projet": n["projet"], "source": n["source"], "octets": len(n["corps"].encode("utf-8")), "mots": stats(n["corps"])["mots"],
                "mtime": n["modifie"], "modifiee": date_dit(n["modifie"]), "vu": date_dit(n["vu_at"]), "vues": n["vues"], "epinglee": bool(n["epinglee"]),
                "relire": n["relire"], "etat": etat_de(n, cs), "ouvertes": len([c for c in cs if not c["faite"]]),
                "entrants": len(entrants.get(n["num"], [])), "sortants": len(sortants.get(n["num"], [])),
                "indesirable": bool(INDESIRABLE.search(n["titre"]))}

    def lister(c, q="", tri="recent", filtre="toutes", etiquette="", projet="", dossier=None, groupe="*", limite=500):
        compte = compte_agit()
        q = str(q or "").strip().lower()
        tri = tri if tri in TRIS else "recent"
        filtre = filtre if filtre in FILTRES else "toutes"
        vivantes = toutes(compte)
        sortants, entrants, _ = graphe(vivantes)
        op_etq = op_pj = op_lie = ""
        if q.startswith("#"):
            op_etq, q = q[1:].strip(), ""
        elif q.startswith("projet:") or q.startswith("chantier:"):
            op_pj, q = q.split(":", 1)[1].strip(), ""
        elif q.startswith("lié:") or q.startswith("lie:"):
            op_lie, q = q.split(":", 1)[1].strip().upper(), ""
        g = str(groupe or "*")
        etqs, pjs, sans, out = {}, {}, 0, []
        for n in vivantes:
            for e in n["etiquettes"]:
                etqs[e] = etqs.get(e, 0) + 1
            if n["projet"]:
                pjs[n["projet"]] = pjs.get(n["projet"], 0) + 1
            if not n["etiquettes"] and not n["projet"]:
                sans += 1
        for n in vivantes:
            r = resume(n, sortants, entrants)
            if q and q not in (n["titre"] + " " + n["corps"] + " " + " ".join(n["etiquettes"])).lower():
                continue
            if op_etq and not any(op_etq.lower() in e.lower() for e in n["etiquettes"]):
                continue
            if op_pj and op_pj.lower() not in n["projet"].lower():
                continue
            if op_lie and not any(x["id"] == op_lie for x in sortants.get(n["num"], [])):
                continue
            if etiquette and etiquette not in n["etiquettes"]:
                continue
            if projet and n["projet"] != projet:
                continue
            if dossier is not None and n["dossier"] != str(dossier).strip("/") and not (str(dossier).strip("/") and n["dossier"].startswith(str(dossier).strip("/") + "/")):
                continue
            if g == "sans" and (n["etiquettes"] or n["projet"]):
                continue
            if g.startswith("pj:") and n["projet"] != g[3:]:
                continue
            if g.startswith("et:") and g[3:] not in n["etiquettes"]:
                continue
            if filtre == "epinglees" and not r["epinglee"]:
                continue
            if filtre == "arelire" and not (r["relire"] and jours_depuis(r["relire"]) >= -7):
                continue
            if filtre == "ouvertes" and not r["ouvertes"]:
                continue
            if filtre == "projet" and not n["projet"]:
                continue
            if filtre == "orphelines" and (n["etiquettes"] or n["projet"]):
                continue
            if filtre == "menage" and not (r["indesirable"] or (not r["vues"] and not r["entrants"])):
                continue
            out.append(r)
        cle = {"recent": lambda x: -x["mtime"], "ancien": lambda x: x["mtime"], "titre": lambda x: x["titre"].lower(), "poids": lambda x: -x["octets"],
               "usage": lambda x: (-x["vues"], -x["mtime"]), "jamais": lambda x: (x["vues"], -x["mtime"])}[tri]
        out.sort(key=lambda x: (not x["epinglee"], cle(x)) if tri == "recent" else cle(x))
        tri_n = lambda d: [{"nom": k, "n": v} for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))]
        return {"notes": out[:max(1, min(int(limite or 500), 2000))], "total": len(vivantes), "filtrees": len(out), "etiquettes": [[k, v] for k, v in sorted(etqs.items(), key=lambda kv: (-kv[1], kv[0]))],
                "projets": [[k, v] for k, v in sorted(pjs.items(), key=lambda kv: (-kv[1], kv[0]))], "groupes": {"projets": tri_n(pjs), "etiquettes": tri_n(etqs), "sans": sans},
                "tris": list(TRIS), "filtres": list(FILTRES)}

    def liste_versions(n):
        return [{"id": r["id"], "auteur": r["auteur"], "motif": r["motif"], "quand": date_dit(r["ts"]), "octets": len(r["corps"].encode("utf-8"))}
                for r in db.lire("SELECT id, ts, auteur, motif, corps FROM versions WHERE note_id=? ORDER BY id DESC", (n["id"],))]

    def activite_de(n, versions):
        out = [{"q": v["quand"], "quoi": v["motif"] or "modifiée", "det": "version %s" % v["id"], "qui": v["auteur"]} for v in versions]
        out += [{"q": date_dit(r["ts"]), "quoi": r["quoi"], "det": r["det"], "qui": r["qui"]} for r in db.lire("SELECT * FROM activite WHERE note_id=? ORDER BY id DESC LIMIT 40", (n["id"],))]
        return sorted(out, key=lambda x: x["q"], reverse=True)[:40]

    def rattachements(liste, memo):
        out = []
        for t in liste[:40]:
            nature, _, cible = t.partition(":")
            e = {"brut": t, "nature": nature, "ref": cible, "titre": cible, "vivant": None}
            if nature == "note":
                n = resoudre(cible, ctx.compte)
                e["vivant"], e["titre"] = n is not None, (n or {}).get("titre", cible)
            else:
                r = existe_ailleurs(nature, cible, memo)
                if r is not None:
                    e["vivant"], e["titre"] = r["existe"], r["titre"]
            out.append(e)
        return out

    def fiche(c, ref="", marquer=True):
        compte = compte_agit()
        n = exiger(ref, compte)
        if marquer:
            db.ecrire("UPDATE notes SET vues=vues+1, vu_at=? WHERE id=?", (time.time(), n["id"]))
        vivantes = toutes(compte)
        sortants, entrants, titres = graphe(vivantes)
        memo = {}
        cs = cases_de(n["corps"])
        liees = {r["ligne"]: r["tache_id"] for r in db.lire("SELECT ligne, tache_id FROM cases WHERE note_id=?", (n["id"],))}
        for k in cs:
            k["tache_id"] = liees.get(k["ligne"])
        st = stats(n["corps"])
        versions = liste_versions(n)
        f = {"id": n["ref"], "num": n["num"], "titre": n["titre"], "dossier": n["dossier"], "corps": n["corps"], "brut": brut(n), "etiquettes": n["etiquettes"], "projet": n["projet"],
             "source": n["source"], "epinglee": bool(n["epinglee"]), "creee": datetime.fromtimestamp(n["cree"]).strftime("%Y-%m-%d"), "modifiee": date_dit(n["modifie"]),
             "octets": len(n["corps"].encode("utf-8")), "mots": st["mots"], "lecture_min": st["lecture_min"], "vu": date_dit(n["vu_at"]), "vues": n["vues"] + (1 if marquer else 0),
             "relire": n["relire"], "taches": cs, "ancres": ancres_de(n["corps"]), "etat": etat_de(n, cs), "etats": [{"cle": k, "n": v} for k, v in ETATS.items()],
             "liens": liens_resolus(n["corps"], vivantes, memo), "entrants": [{"id": num_dit(x), "titre": titres.get(x, num_dit(x))} for x in entrants.get(n["num"], [])],
             "sommaire": [{"niveau": len(h[0]), "texte": h[1].strip()} for h in re.findall(r"(?m)^(#{1,4})\s+(.+)$", n["corps"])],
             "rattache": rattachements(n["rattache"], memo), "versions": versions, "indesirable": bool(INDESIRABLE.search(n["titre"]))}
        f["etat_n"] = ETATS.get(f["etat"], f["etat"])
        f["sante"] = sante(f)
        f["activite"] = activite_de(n, versions)
        return f

    def versions(c, ref=""):
        return {"versions": liste_versions(exiger(ref, compte_agit()))}

    def version_lire(c, ref="", version=0):
        n = exiger(ref, compte_agit())
        r = db.lire("SELECT * FROM versions WHERE id=? AND note_id=?", (int(version or 0), n["id"]))
        if not r:
            raise ValueError("version introuvable")
        return {"id": r[0]["id"], "titre": r[0]["titre"], "contenu": r[0]["corps"], "quand": date_dit(r[0]["ts"]), "auteur": r[0]["auteur"], "motif": r[0]["motif"]}

    def corbeille(c):
        return {"notes": [{"id": n["ref"], "titre": n["titre"], "quand": date_dit(n["corbeille_at"])[:10], "octets": len(n["corps"].encode("utf-8")), "redirige": num_dit(n["redirige"]) if n["redirige"] else ""}
                          for n in sorted(toutes(compte_agit(), "corbeille"), key=lambda x: -x["corbeille_at"])]}

    def dossiers(c):
        compte = compte_agit()
        vivantes = toutes(compte)
        chemins = {r["chemin"] for r in db.lire("SELECT chemin FROM dossiers WHERE compte=?", (compte,))}
        for n in vivantes:                                           # un dossier porté par une note existe, même sans ligne
            if n["dossier"]:
                parts = n["dossier"].split("/")
                for i in range(1, len(parts) + 1):
                    chemins.add("/".join(parts[:i]))
        out = []
        for ch in sorted(chemins):
            pre = ch + "/"
            out.append({"chemin": ch, "nom": ch.rsplit("/", 1)[-1], "profondeur": ch.count("/"), "n": len([x for x in vivantes if x["dossier"] == ch or x["dossier"].startswith(pre)])})
        return {"dossiers": out, "racine": len([x for x in vivantes if not x["dossier"]]), "total": len(vivantes), "profondeur_max": PROFONDEUR}

    def liens(c):
        compte = compte_agit()
        vivantes = toutes(compte)
        memo, out = {}, []
        for n in vivantes:
            vus = set()
            for l in liens_resolus(n["corps"], vivantes, memo):
                cle = (l["kind"], l["ref"])
                if cle in vus:
                    continue
                vus.add(cle)
                out.append({"src": n["ref"], "src_titre": n["titre"], "kind": l["kind"], "ref": l["ref"], "titre": l["titre"], "existe": l["existe"], "inclus": l["inclus"]})
        return {"liens": out, "total": len(out), "morts": len([x for x in out if x["existe"] is False])}

    def de(c, kind="", ref=""):
        compte = compte_agit()
        kind, ref = str(kind or "").strip().lower(), str(ref or "").strip()
        if not kind or not ref:
            raise ValueError("il faut une nature et une référence")
        norm = (lambda r: norm_domaine(r)) if kind in ("domain", "site") else (lambda r: r.strip().lower())
        vise = norm(ref)
        out = []
        for n in toutes(compte):
            for l in liens_de(n["corps"]):
                lk = "domain" if l["kind"] in ("domain", "site") else l["kind"]
                vk = "domain" if kind in ("domain", "site") else kind
                r = l["ref"].split("#")[0] if l["kind"] == "note" else l["ref"]
                if lk == vk and norm(r) == vise:
                    out.append({"id": n["ref"], "titre": n["titre"], "inclus": l["inclus"]})
                    break
        return {"notes": out, "cible": "%s:%s" % (kind, vise)}

    def mentions(c, ref=""):
        compte = compte_agit()
        vivantes = toutes(compte)
        index = {}
        for n in vivantes:
            t = n["titre"].strip()
            if len(t) >= MENTION_MIN:
                index.setdefault(t.lower(), n)
        visees = [exiger(ref, compte)] if ref else vivantes
        out = []
        for n in visees:
            deja = {str(l["ref"]).strip().lower() for l in liens_de(n["corps"])}
            nu = RE_LIEN.sub(" ", n["corps"]).lower()                     # « [[N-0003]] » ne compte pas comme une mention du titre
            for nom, cible in index.items():
                if cible["num"] == n["num"] or nom in deja or cible["ref"].lower() in deja or nom not in nu:
                    continue
                out.append({"note": n["ref"], "note_titre": n["titre"], "mot": cible["titre"], "kind": "note", "ref": cible["ref"], "ecriture": "[[%s]]" % cible["ref"]})
        return {"mentions": out[:200]}

    def cases(c, ouvertes_seules=False):
        compte = compte_agit()
        out = []
        for n in toutes(compte):
            liees = {r["ligne"]: r["tache_id"] for r in db.lire("SELECT ligne, tache_id FROM cases WHERE note_id=?", (n["id"],))}
            for k in cases_de(n["corps"]):
                if ouvertes_seules and k["faite"]:
                    continue
                out.append({"note": n["ref"], "note_titre": n["titre"], "ligne": k["ligne"], "faite": k["faite"], "texte": k["texte"], "tache_id": liees.get(k["ligne"])})
        return {"taches": out, "ouvertes": len([x for x in out if not x["faite"]])}

    def etat_tache(tid):
        try:
            f = ctx.executer_lecture("taches.fiche", id=int(tid))
        except Exception:
            return None
        return (f or {}).get("tache")

    def cases_etat(c, ref=""):
        """Ce que la note et les tâches savent chacune, mis face à face. On apparie sur le TEXTE : un numéro de ligne se déplace dès qu'on écrit au-dessus."""
        compte = compte_agit()
        n = exiger(ref, compte)
        liees = {r["ligne"]: r for r in db.lire("SELECT ligne, tache_id, texte FROM cases WHERE note_id=?", (n["id"],))}
        cs = cases_de(n["corps"])
        par_texte = {}
        for r in liees.values():
            par_texte.setdefault(r["texte"].strip().lower(), r)
        out, vus = [], set()
        for k in cs:
            r = liees.get(k["ligne"])
            if r is not None and r["texte"].strip().lower() != k["texte"].strip().lower():
                r = None                                                    # la ligne a changé de texte : ce n'est plus la même case
            if r is None:
                r = par_texte.get(k["texte"].strip().lower())
            t = etat_tache(r["tache_id"]) if r else None
            if r:
                vus.add(r["tache_id"])
            tache_faite = None if t is None else t["statut"] == "fait"
            out.append({"ligne": k["ligne"], "texte": k["texte"], "faite": k["faite"], "tache": r["tache_id"] if r else None, "tache_faite": tache_faite,
                        "desaccord": tache_faite is not None and tache_faite != k["faite"]})
        orphelines = [{"tache": r["tache_id"], "texte": r["texte"]} for r in liees.values() if r["tache_id"] not in vus]
        return {"id": n["ref"], "projet": n["projet"], "cases": out, "orphelines": orphelines}

    def menage(c):
        compte = compte_agit()
        vivantes = toutes(compte)
        sortants, entrants, _ = graphe(vivantes)
        res = [resume(n, sortants, entrants) for n in vivantes]
        a_ranger = [r for r in res if r["indesirable"] or (not r["vues"] and not r["entrants"])]
        fiches = [(r, set(re.findall(r"\w{5,}", (r["titre"] + " " + r["apercu"]).lower()))) for r in res[-400:]]
        doublons = []
        for i, (a, sa) in enumerate(fiches):
            for b, sb in fiches[i + 1:]:
                if sa and sb:
                    j = len(sa & sb) / float(len(sa | sb))
                    if j >= 0.45:
                        doublons.append({"a": a["id"], "b": b["id"], "titre_a": a["titre"], "titre_b": b["titre"], "proche": int(j * 100)})
        return {"a_ranger": a_ranger, "doublons": doublons[:12], "corbeille": corbeille(c)["notes"]}

    def jour(c, jour=""):
        compte = compte_agit()
        j = str(jour or "").strip() or time.strftime("%Y-%m-%d")
        for n in toutes(compte):
            if n["titre"] == j and "journal" in n["etiquettes"]:
                return {"existe": True, "id": n["ref"], "jour": j}
        return {"existe": False, "jour": j}

    # ------------------------------------------------------------------ export
    def brut(n):
        """La note avec son en-tête : ce qu'on emporte, et ce que l'import relit."""
        lignes = ["id: %s" % n["ref"], "titre: %s" % n["titre"]]
        if n["etiquettes"]:
            lignes.append("etiquettes: [%s]" % ", ".join(n["etiquettes"]))
        for cle in ("projet", "source", "etat", "relire"):
            if n[cle]:
                lignes.append("%s: %s" % (cle, n[cle]))
        lignes.append("creee: %s" % datetime.fromtimestamp(n["cree"]).strftime("%Y-%m-%d"))
        if n["epinglee"]:
            lignes.append("epinglee: true")
        if n["rattache"]:
            lignes.append("rattache: [%s]" % ", ".join(n["rattache"]))
        return "---\n" + "\n".join(lignes) + "\n---\n\n" + n["corps"].lstrip("\n")

    def slug(titre):
        base = re.sub(r"[^\w\s\-.]", "", str(titre or ""), flags=re.UNICODE).strip()
        return (re.sub(r"\s+", "-", base)[:80].strip("-. ") or "note")

    def rendre(n, format):
        format = format if format in FORMATS else "md"
        if format == "md":
            return {"nom": slug(n["titre"]) + ".md", "mime": "text/markdown", "contenu": brut(n)}
        if format == "txt":
            t = re.sub(r"(?m)^(#{1,6})\s+(.+)$", lambda m: m.group(2).upper(), n["corps"])
            t = RE_LIEN.sub(lambda m: m.group(1), t)
            t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
            t = re.sub(r"(?m)^>\s?", "  ", t)
            return {"nom": slug(n["titre"]) + ".txt", "mime": "text/plain", "contenu": "%s\n%s\n\n%s" % (n["titre"], "=" * len(n["titre"]), t)}
        st = stats(n["corps"])
        html = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>'
                '<style>body{font:15px/1.7 Georgia,serif;max-width:40em;margin:3em auto;padding:0 1.5em;color:#241f18;background:#fff}h1,h2,h3{font-family:system-ui,sans-serif;line-height:1.25}'
                'code{background:#f2eee5;padding:1px 5px;border-radius:4px}blockquote{border-left:2px solid #0a6f66;margin:1em 0;padding-left:1em;color:#575045}'
                '.meta{font:12px/1.6 system-ui,sans-serif;color:#7e7667;border-bottom:1px solid #e3ddd0;padding-bottom:1em;margin-bottom:2em}@media print{body{margin:0;max-width:none}}</style>'
                '<h1>%s</h1><div class="meta">%s &middot; %s &middot; %d mots</div>%s'
                % (echapper(n["titre"]), echapper(n["titre"]), echapper(n["ref"]), echapper(date_dit(n["modifie"])), st["mots"], md_vers_html(n["corps"], ctx.point)))
        return {"nom": slug(n["titre"]) + ".html", "mime": "text/html", "contenu": html}

    def exporter(c, ref="", format="md"):
        n = exiger(ref, compte_agit())
        return dict(rendre(n, str(format or "md").lower()), id=n["ref"])

    def archive(c, portee="tout", dossier="", refs=None):
        """Le corpus qu'on emporte, avec son rangement. Bornée, et la borne SE DIT : une archive amputée en silence se lit comme une sauvegarde complète."""
        compte = compte_agit()
        portee = str(portee or "tout").strip().lower()
        notes = toutes(compte)
        if portee == "dossier":
            ch = dossier_propre(dossier)
            notes = [n for n in notes if (n["dossier"].startswith(ch + "/") or n["dossier"] == ch)] if ch else [n for n in notes if not n["dossier"]]
        elif portee == "selection":
            choix, vus = [], set()
            for r in (refs or []):
                n = resoudre(str(r), compte)
                if n and n["num"] not in vus:
                    vus.add(n["num"])
                    choix.append(n)
            notes = choix
        if not notes:
            raise ValueError("rien à mettre dans l'archive")
        if len(notes) > ZIP_NOTES:
            raise ValueError("%d notes — au-delà de %d, l'archive se prépare mal dans une requête. Réduisez la portée (un dossier, une sélection)." % (len(notes), ZIP_NOTES))
        tampon, octets, pris = io.BytesIO(), 0, set()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
            for n in notes:
                nom = (n["dossier"] + "/" if n["dossier"] else "") + slug(n["titre"]) + ".md"
                if nom in pris:
                    nom = (n["dossier"] + "/" if n["dossier"] else "") + "%s-%s.md" % (slug(n["titre"]), n["ref"])
                pris.add(nom)
                t = brut(n)
                octets += len(t.encode("utf-8"))
                if octets > ZIP_OCTETS:
                    raise ValueError("archive trop lourde — réduisez la portée")
                z.writestr(nom, t)
        nom = {"dossier": (dossier or "racine").replace("/", "-"), "selection": "selection"}.get(portee, "corpus")
        return {"nom": "notes-%s-%s.zip" % (nom, time.strftime("%Y%m%d")), "mime": "application/zip", "octets": tampon.tell(), "notes": len(notes), "contenu_b64": base64.b64encode(tampon.getvalue()).decode("ascii")}

    def partages(c):
        compte = compte_agit()
        maintenant = time.time()
        return {"liens": [{"jeton": r["jeton"], "note": num_dit(r["num"]), "titre": r["titre"], "format": r["format"], "expire_le": date_dit(r["expire_le"]), "expire": bool(r["expire_le"] and r["expire_le"] < maintenant),
                           "n_vues": r["n_vues"], "dernier": date_dit(r["dernier"]), "cree": date_dit(r["cree"]), "protege": bool(r["mdp"]), "chemin": "/api/public/notes.partage_servir"}
                          for r in db.lire("SELECT p.*, n.num FROM partages p JOIN notes n ON n.id=p.note_id WHERE p.compte=? ORDER BY p.cree DESC", (compte,))]}

    # ------------------------------------------------------------------ créer
    def creer_note(compte, titre, corps="", etiquettes=None, projet="", dossier=None, source="", epinglee=False, etat="", relire="", rattache=None, auteur=""):
        titre = str(titre or "").strip()[:200]
        if not titre:
            raise ValueError("une note a besoin d'un titre")
        corps = str(corps or "")
        if len(corps) > 200000:
            raise ValueError("note trop longue (200 000 caractères au plus)")
        projet = str(projet or "").strip()[:80]
        if etat and etat not in ETATS:
            raise ValueError("état : %s" % " | ".join(ETATS))
        ch = dossier_propre(dossier) if dossier else (dossier_projet(projet) if projet else "")
        if ch:
            if dossier and not dossier_existe(compte, ch):
                raise ValueError("ce dossier n'existe pas — crée-le d'abord")
            creer_dossier(compte, ch)
        num = numero(compte)
        maintenant = time.time()
        nid = db.ecrire("INSERT INTO notes(compte, num, titre, corps, etiquettes, projet, dossier, source, epinglee, etat, relire, rattache, cree, modifie) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (compte, num, titre, corps, json.dumps(propres_etiquettes(etiquettes), ensure_ascii=False), projet, ch, str(source or auteur or "vous")[:60], 1 if epinglee else 0,
                         etat or "", date_iso(relire), json.dumps(propres_rattaches(rattache), ensure_ascii=False), maintenant, maintenant))
        noter(nid, "Créée", "", auteur or compte)
        ctx.emettre("note.creee", objet=("note", str(nid)), donnees={"id": num_dit(num), "titre": titre[:80]})
        return {"id": nid, "num": num, "ref": num_dit(num), "compte": compte, "titre": titre}

    def creer(c, titre="", corps="", etiquettes=None, projet="", dossier=None, source="", epinglee=False, etat="", relire="", rattache=None):
        return creer_note(compte_agit(), titre, corps, etiquettes, projet, dossier, source, epinglee, etat, relire, rattache, auteur=qui_agit(compte_agit()))

    def prouver_creee(c, res):
        r = db.lire("SELECT titre, compte FROM notes WHERE id=?", (res["id"],))
        return bool(r) and r[0]["titre"] == res["titre"] and r[0]["compte"] == res["compte"]

    def effacer_note(nid):
        for t in ("versions", "activite", "cases"):
            db.ecrire("DELETE FROM %s WHERE note_id=?" % t, (nid,))
        db.ecrire("DELETE FROM partages WHERE note_id=?", (nid,))
        db.ecrire("DELETE FROM notes WHERE id=?", (nid,))

    def defaire_creee(c, res):
        effacer_note(res["id"])                                  # le compteur ne recule pas : le numéro reste réservé

    # ------------------------------------------------------------------ écrire
    COLONNES = ("titre", "corps", "etiquettes", "projet", "dossier", "epinglee", "etat", "relire", "rattache", "modifie")

    def ecrire(c, ref="", corps=None, titre=None, etiquettes=None, projet=None, dossier=None, epinglee=None, etat=None, relire=None, rattache=None, motif=""):
        compte = compte_agit()
        n = exiger(ref, compte)
        ligne = db.lire("SELECT * FROM notes WHERE id=?", (n["id"],))[0]
        avant = {k: ligne[k] for k in COLONNES}
        maj, dits = {}, []
        if titre is not None:
            t = str(titre).strip()[:200]
            if not t:
                raise ValueError("une note a besoin d'un titre")
            maj["titre"] = t
        if corps is not None:
            if len(str(corps)) > 200000:
                raise ValueError("note trop longue (200 000 caractères au plus)")
            maj["corps"] = str(corps)
        if etiquettes is not None:
            maj["etiquettes"] = json.dumps(propres_etiquettes(etiquettes), ensure_ascii=False)
            dits.append("étiquettes : %s" % (", ".join(propres_etiquettes(etiquettes)) or "aucune"))
        if projet is not None:
            maj["projet"] = str(projet).strip()[:80]
            dits.append("projet : %s" % (maj["projet"] or "aucun"))
            if dossier is None:                                  # le dossier suit le projet — sans toucher à un dossier que la personne a choisi
                voulu = dossier_projet(maj["projet"]) if maj["projet"] else ""
                if voulu:
                    if n["dossier"] != voulu:
                        creer_dossier(compte, voulu)
                        maj["dossier"] = voulu
                elif n["dossier"] and n["dossier"] == dossier_projet(n["projet"]):
                    maj["dossier"] = ""
        if dossier is not None:
            ch = dossier_propre(dossier)
            if not dossier_existe(compte, ch):
                raise ValueError("ce dossier n'existe pas — crée-le d'abord")
            maj["dossier"] = ch
        if epinglee is not None:
            maj["epinglee"] = 1 if epinglee else 0
        if etat is not None:
            e = str(etat).strip()
            if e and e not in ETATS:
                raise ValueError("état : %s" % " | ".join(ETATS))
            maj["etat"] = e
        if relire is not None:
            maj["relire"] = date_iso(relire)
        if rattache is not None:
            maj["rattache"] = json.dumps(propres_rattaches(rattache), ensure_ascii=False)
        if not maj:
            raise ValueError("rien à écrire")
        vid = None
        if "corps" in maj or "titre" in maj:
            vid = versionner(n, qui_agit(compte), motif or "modification")
        maj["modifie"] = time.time()
        db.ecrire("UPDATE notes SET %s WHERE id=?" % ",".join("%s=?" % k for k in maj), list(maj.values()) + [n["id"]])
        qui = qui_agit(compte)
        if dits:
            noter(n["id"], "Rangée", " ; ".join(dits), qui)
        if "dossier" in maj and maj["dossier"] != n["dossier"]:
            noter(n["id"], "Déplacée", maj["dossier"] or "(racine)", qui)
        if "rattache" in maj:
            ancien, neuf = set(n["rattache"]), set(json.loads(maj["rattache"]))
            for x in sorted(neuf - ancien):
                noter(n["id"], "Rattachée", x, qui)
            for x in sorted(ancien - neuf):
                noter(n["id"], "Détachée", x, qui)
        if "etat" in maj and maj["etat"] != n["etat"]:
            noter(n["id"], "État", ETATS.get(maj["etat"], "déduit"), qui)
        if "relire" in maj and maj["relire"] != n["relire"]:
            noter(n["id"], "Relecture prévue" if maj["relire"] else "Relecture retirée", maj["relire"], qui)
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "avant": avant, "maj": maj, "vid": vid}

    def prouver_ecrite(c, res):
        r = db.lire("SELECT * FROM notes WHERE id=?", (res["id"],))
        return bool(r) and all(r[0][k] == v for k, v in res["maj"].items() if k != "modifie")

    def defaire_ecrite(c, res):
        a = res["avant"]
        db.ecrire("UPDATE notes SET %s WHERE id=?" % ",".join("%s=?" % k for k in a), list(a.values()) + [res["id"]])
        if res.get("vid"):
            db.ecrire("DELETE FROM versions WHERE id=?", (res["vid"],))
        noter(res["id"], "Écriture annulée", "", res["compte"])

    def revenir(c, ref="", version=0):
        """Revenir ne détruit rien : l'état actuel devient à son tour une version."""
        compte = compte_agit()
        n = exiger(ref, compte)
        v = db.lire("SELECT * FROM versions WHERE id=? AND note_id=?", (int(version or 0), n["id"]))
        if not v:
            raise ValueError("version introuvable")
        avant = {"titre": n["titre"], "corps": n["corps"], "modifie": n["modifie"]}
        vid = versionner(n, qui_agit(compte), "retour à une version")
        db.ecrire("UPDATE notes SET titre=?, corps=?, modifie=? WHERE id=?", (v[0]["titre"], v[0]["corps"], time.time(), n["id"]))
        noter(n["id"], "Retour à une version", "version %s" % v[0]["id"], qui_agit(compte))
        return {"id": n["id"], "compte": compte, "avant": avant, "titre": v[0]["titre"], "corps": v[0]["corps"], "vid": vid}

    def prouver_revenue(c, res):
        r = db.lire("SELECT corps FROM notes WHERE id=?", (res["id"],))
        return bool(r) and r[0]["corps"] == res["corps"]

    def defaire_revenue(c, res):
        a = res["avant"]
        db.ecrire("UPDATE notes SET titre=?, corps=?, modifie=? WHERE id=?", (a["titre"], a["corps"], a["modifie"], res["id"]))
        db.ecrire("DELETE FROM versions WHERE id=?", (res["vid"],))

    # ------------------------------------------------------------------ corbeille
    def supprimer(c, ref=""):
        compte = compte_agit()
        n = exiger(ref, compte)
        db.ecrire("UPDATE notes SET corbeille_at=? WHERE id=?", (time.time(), n["id"]))
        noter(n["id"], "Mise à la corbeille", "", qui_agit(compte))
        return {"id": n["id"], "ref": n["ref"], "compte": compte}

    def prouver_supprimee(c, res):
        r = db.lire("SELECT corbeille_at FROM notes WHERE id=?", (res["id"],))
        return bool(r) and r[0]["corbeille_at"] is not None

    def defaire_supprimee(c, res):
        db.ecrire("UPDATE notes SET corbeille_at=NULL WHERE id=?", (res["id"],))

    def restaurer(c, ref=""):
        compte = compte_agit()
        n = exiger(ref, compte, "corbeille")
        avant = {"corbeille_at": n["corbeille_at"], "redirige": n["redirige"]}
        db.ecrire("UPDATE notes SET corbeille_at=NULL, redirige=NULL WHERE id=?", (n["id"],))
        noter(n["id"], "Sortie de la corbeille", "", qui_agit(compte))
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "avant": avant}

    def prouver_restauree(c, res):
        r = db.lire("SELECT corbeille_at FROM notes WHERE id=?", (res["id"],))
        return bool(r) and r[0]["corbeille_at"] is None

    def defaire_restauree(c, res):
        db.ecrire("UPDATE notes SET corbeille_at=?, redirige=? WHERE id=?", (res["avant"]["corbeille_at"], res["avant"]["redirige"], res["id"]))

    def instantane(nid):
        return {t: [dict(r) for r in db.lire("SELECT * FROM %s WHERE %s=?" % (t, "id" if t == "notes" else "note_id"), (nid,))] for t in ("notes", "versions", "activite", "cases", "partages")}

    def reposer(snap):
        with db.transaction() as cx:
            for t in ("notes", "versions", "activite", "cases", "partages"):
                for ligne in snap.get(t, []):
                    ks = list(ligne)
                    cx.execute("INSERT OR REPLACE INTO %s(%s) VALUES (%s)" % (t, ",".join(ks), ",".join("?" * len(ks))), [ligne[k] for k in ks])

    def vider_corbeille(c):
        compte = compte_agit()
        vises = toutes(compte, "corbeille")
        copies = [instantane(n["id"]) for n in vises]
        for n in vises:
            effacer_note(n["id"])                                # les numéros restent réservés : le compteur ne recule pas
        return {"compte": compte, "videes": len(vises), "ids": [n["id"] for n in vises], "copies": copies}

    def prouver_videe(c, res):
        return not db.lire("SELECT 1 FROM notes WHERE compte=? AND corbeille_at IS NOT NULL", (res["compte"],))

    def defaire_videe(c, res):
        for s in res["copies"]:
            reposer(s)

    # ------------------------------------------------------------------ fusion
    def fusionner(c, refs=None, titre=""):
        """Les textes sont conservés sous leur titre, les renvois sont réécrits, les absorbées vont à la corbeille : leur numéro redirige vers la fusion."""
        compte = compte_agit()
        vus, absorbees = set(), []
        for r in (refs or []):
            n = exiger(r, compte)
            if n["num"] not in vus:
                vus.add(n["num"])
                absorbees.append(n)
        if len(absorbees) < 2:
            raise ValueError("il faut au moins deux notes")
        if not str(titre or "").strip():
            raise ValueError("la fusion a besoin d'un titre")
        corps = "\n\n".join("# %s\n\n%s" % (n["titre"], n["corps"].strip()) for n in absorbees)
        etq = []
        for n in absorbees:
            for e in n["etiquettes"]:
                if e not in etq:
                    etq.append(e)
        pj = next((n["projet"] for n in absorbees if n["projet"]), "")
        neuve = creer_note(compte, titre, corps, etq, pj, None, "fusion", auteur=qui_agit(compte))
        nums = {n["num"] for n in absorbees}

        def neuf_renvoi(m):
            return m.group(1) + num_dit(neuve["num"]) if int(m.group(2)) in nums else m.group(0)

        motif = re.compile(r"(!?\[\[\s*)N-?0*(\d+)(?=[#|\]\s])", re.I)
        reecrits = []
        for n in toutes(compte):
            if n["num"] in nums or n["num"] == neuve["num"]:
                continue
            nc = motif.sub(neuf_renvoi, n["corps"])
            if nc != n["corps"]:
                vid = versionner(n, qui_agit(compte), "renvoi vers la fusion %s" % neuve["ref"])
                db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", (nc, time.time(), n["id"]))
                reecrits.append({"id": n["id"], "corps": n["corps"], "modifie": n["modifie"], "vid": vid})
        maintenant = time.time()
        for n in absorbees:
            db.ecrire("UPDATE notes SET corbeille_at=?, redirige=? WHERE id=?", (maintenant, neuve["num"], n["id"]))
            noter(n["id"], "Absorbée par une fusion", neuve["ref"], qui_agit(compte))
        return {"id": neuve["id"], "ref": neuve["ref"], "compte": compte, "titre": neuve["titre"], "absorbees": [n["id"] for n in absorbees], "absorbees_refs": [n["ref"] for n in absorbees], "reecrits": reecrits}

    def prouver_fusion(c, res):
        if not db.lire("SELECT 1 FROM notes WHERE id=? AND corbeille_at IS NULL", (res["id"],)):
            return False
        return all(db.lire("SELECT corbeille_at FROM notes WHERE id=?", (a,))[0]["corbeille_at"] is not None for a in res["absorbees"])

    def defaire_fusion(c, res):
        for r in res["reecrits"]:
            db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", (r["corps"], r["modifie"], r["id"]))
            if r.get("vid"):
                db.ecrire("DELETE FROM versions WHERE id=?", (r["vid"],))
        for a in res["absorbees"]:
            db.ecrire("UPDATE notes SET corbeille_at=NULL, redirige=NULL WHERE id=?", (a,))
        effacer_note(res["id"])

    # ------------------------------------------------------------------ import
    def importer(c, fichiers=None):
        compte = compte_agit()
        fichiers = list(fichiers or [])
        if not fichiers:
            raise ValueError("aucun fichier")
        if len(fichiers) > ZIP_NOTES:
            raise ValueError("%d fichiers — %d au plus par import" % (len(fichiers), ZIP_NOTES))
        faits, refus = [], []
        for f in fichiers:
            try:
                nom = str((f or {}).get("chemin") or (f or {}).get("nom") or "").replace("\\", "/").strip("/")
                texte = str((f or {}).get("contenu") or "")
                meta, corps = lire_entete(texte, ctx.point)
                dos = nom.rsplit("/", 1)[0] if "/" in nom else ""
                dos = "/".join(dos.split("/")[:PROFONDEUR]) if dossier_ok("/".join(dos.split("/")[:PROFONDEUR])) else ""
                base = nom.rsplit("/", 1)[-1]
                base = base[:-3] if base.lower().endswith(".md") else base
                t = str(meta.get("titre") or "").strip() or titre_de(corps, base)
                etq = meta.get("etiquettes") or []
                etq = etq if isinstance(etq, list) else [etq]
                att = meta.get("rattache") or []
                att = att if isinstance(att, list) else [att]
                att = [x for x in att if x.partition(":")[0] in NATURES and x.partition(":")[2].strip()]
                etat = str(meta.get("etat") or "")
                try:
                    relire = date_iso(meta.get("relire") or "")
                except ValueError:
                    relire = ""
                if dos:
                    creer_dossier(compte, dos)
                r = creer_note(compte, t, corps, etq, str(meta.get("projet") or meta.get("chantier") or ""), dos or None, "import", bool(meta.get("epinglee")), etat if etat in ETATS else "", relire, att,
                               auteur=qui_agit(compte))
                faits.append(r)
            except ValueError as e:
                refus.append({"fichier": str((f or {}).get("nom") or "?")[:80], "raison": str(e)})
        return {"compte": compte, "creees": faits, "ids": [r["id"] for r in faits], "refus": refus}

    def prouver_importe(c, res):
        return all(db.lire("SELECT 1 FROM notes WHERE id=?", (i,)) for i in res["ids"])

    def defaire_importe(c, res):
        for i in res["ids"]:
            effacer_note(i)

    # ------------------------------------------------------------------ note du jour
    def jour_ouvrir(c, jour=""):
        compte = compte_agit()
        j = str(jour or "").strip() or time.strftime("%Y-%m-%d")
        date_iso(j)
        ex = jour_existante(compte, j)
        if ex:
            return {"id": ex["id"], "ref": ex["ref"], "compte": compte, "cree": False, "jour": j}
        r = creer_note(compte, j, "", ["journal"], "", None, "note du jour", auteur=qui_agit(compte))
        return {"id": r["id"], "ref": r["ref"], "compte": compte, "cree": True, "jour": j}

    def jour_existante(compte, j):
        return next((n for n in toutes(compte) if n["titre"] == j and "journal" in n["etiquettes"]), None)

    def prouver_jour(c, res):
        return bool(db.lire("SELECT 1 FROM notes WHERE id=?", (res["id"],)))

    def defaire_jour(c, res):
        if res["cree"]:
            effacer_note(res["id"])

    # ------------------------------------------------------------------ dossiers
    def dossier_creer(c, chemin=""):
        compte = compte_agit()
        ch = dossier_propre(chemin)
        if not ch:
            raise ValueError("il faut un nom")
        if dossier_existe(compte, ch) or any(n["dossier"] == ch for n in toutes(compte)):
            raise ValueError("ce dossier existe déjà")
        return {"compte": compte, "chemin": ch, "faits": creer_dossier(compte, ch)}

    def prouver_dossier_cree(c, res):
        return dossier_existe(res["compte"], res["chemin"])

    def defaire_dossier_cree(c, res):
        for p in reversed(res["faits"]):
            if not db.lire("SELECT 1 FROM notes WHERE compte=? AND (dossier=? OR dossier LIKE ?)", (res["compte"], p, p + "/%")):
                db.ecrire("DELETE FROM dossiers WHERE compte=? AND chemin=?", (res["compte"], p))

    def dossier_existant(compte, ch):
        return dossier_existe(compte, ch) or any(n["dossier"] == ch or n["dossier"].startswith(ch + "/") for n in toutes(compte, "toutes"))

    def renommer_chemins(compte, de_, vers):
        """Change le préfixe d'un dossier dans la table et dans les notes (corbeille comprise : une note restaurée retrouve son dossier)."""
        for r in db.lire("SELECT chemin FROM dossiers WHERE compte=? AND (chemin=? OR chemin LIKE ?)", (compte, de_, de_ + "/%")):
            db.ecrire("DELETE FROM dossiers WHERE compte=? AND chemin=?", (compte, r["chemin"]))
            db.ecrire("INSERT OR IGNORE INTO dossiers(compte, chemin) VALUES (?,?)", (compte, vers + r["chemin"][len(de_):]))
        for r in db.lire("SELECT id, dossier FROM notes WHERE compte=? AND (dossier=? OR dossier LIKE ?)", (compte, de_, de_ + "/%")):
            db.ecrire("UPDATE notes SET dossier=? WHERE id=?", (vers + r["dossier"][len(de_):], r["id"]))

    def dossier_renommer(c, chemin="", nom=""):
        compte = compte_agit()
        ch = dossier_propre(chemin)
        nom = str(nom or "").strip()
        if not ch or not dossier_existant(compte, ch):
            raise ValueError("dossier inconnu")
        if not segment_ok(nom):
            raise ValueError("nom refusé — ni « / », ni « .. », ni nom commençant par un point")
        parent = ch.rsplit("/", 1)[0] if "/" in ch else ""
        neuf = (parent + "/" + nom) if parent else nom
        if neuf == ch:
            raise ValueError("ce dossier porte déjà ce nom")
        if dossier_existant(compte, neuf):
            raise ValueError("un dossier de ce nom existe déjà ici")
        renommer_chemins(compte, ch, neuf)
        return {"compte": compte, "chemin": neuf, "avant": ch}

    def prouver_dossier_renomme(c, res):
        return dossier_existant(res["compte"], res["chemin"]) and not dossier_existe(res["compte"], res["avant"])

    def defaire_dossier_renomme(c, res):
        renommer_chemins(res["compte"], res["chemin"], res["avant"])

    def dossier_supprimer(c, chemin=""):
        """Un dossier n'est qu'un rangement : ce qu'il contient remonte d'un cran, sous-dossiers compris. Rien ne disparaît."""
        compte = compte_agit()
        ch = dossier_propre(chemin)
        if not ch or not dossier_existant(compte, ch):
            raise ValueError("dossier inconnu")
        parent = ch.rsplit("/", 1)[0] if "/" in ch else ""
        lignes = [r["chemin"] for r in db.lire("SELECT chemin FROM dossiers WHERE compte=? AND (chemin=? OR chemin LIKE ?)", (compte, ch, ch + "/%"))]
        deplacees = [{"id": r["id"], "dossier": r["dossier"]} for r in db.lire("SELECT id, dossier FROM notes WHERE compte=? AND (dossier=? OR dossier LIKE ?)", (compte, ch, ch + "/%"))]
        for r in deplacees:
            reste = r["dossier"][len(ch):].strip("/")
            neuf = "/".join(x for x in (parent, reste) if x)
            db.ecrire("UPDATE notes SET dossier=? WHERE id=?", (neuf, r["id"]))
        db.ecrire("DELETE FROM dossiers WHERE compte=? AND (chemin=? OR chemin LIKE ?)", (compte, ch, ch + "/%"))
        crees = []
        for p in lignes:
            reste = p[len(ch):].strip("/")
            if reste:
                crees += creer_dossier(compte, "/".join(x for x in (parent, reste) if x))
        return {"compte": compte, "chemin": ch, "vers": parent or "(racine)", "remontees": len(deplacees), "lignes": lignes, "deplacees": deplacees, "crees": crees}

    def prouver_dossier_supprime(c, res):
        return not dossier_existe(res["compte"], res["chemin"]) and not any(n["dossier"] == res["chemin"] for n in toutes(res["compte"], "toutes"))

    def defaire_dossier_supprime(c, res):
        for p in res["crees"]:
            db.ecrire("DELETE FROM dossiers WHERE compte=? AND chemin=?", (res["compte"], p))
        for p in res["lignes"]:
            db.ecrire("INSERT OR IGNORE INTO dossiers(compte, chemin) VALUES (?,?)", (res["compte"], p))
        for r in res["deplacees"]:
            db.ecrire("UPDATE notes SET dossier=? WHERE id=?", (r["dossier"], r["id"]))

    # ------------------------------------------------------------------ cases
    def case_basculer(c, ref="", ligne=-1):
        """Coche ou décoche UNE ligne. On repart du texte actuel, pas d'un index mémorisé : entre l'affichage et le clic, la note a pu changer."""
        compte = compte_agit()
        n = exiger(ref, compte)
        lignes = n["corps"].split("\n")
        try:
            i = int(ligne)
        except (TypeError, ValueError):
            raise ValueError("ligne invalide")
        if i < 0 or i >= len(lignes):
            raise ValueError("cette ligne n'existe plus")
        m = RE_CASE.match(lignes[i])
        if not m:
            raise ValueError("cette ligne n'est pas une case à cocher")
        fait = m.group(2).lower() != "x"
        lignes[i] = "%s[%s] %s" % (m.group(1), "x" if fait else " ", m.group(3))
        vid = versionner(n, qui_agit(compte), "%s « %s »" % ("coché" if fait else "décoché", m.group(3).strip()[:40]))
        db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", ("\n".join(lignes), time.time(), n["id"]))
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "ligne": i, "faite": fait, "vid": vid, "avant": {"corps": n["corps"], "modifie": n["modifie"]}}

    def prouver_basculee(c, res):
        r = db.lire("SELECT corps FROM notes WHERE id=?", (res["id"],))
        if not r:
            return False
        m = RE_CASE.match(r[0]["corps"].split("\n")[res["ligne"]])
        return bool(m) and (m.group(2).lower() == "x") == res["faite"]

    def defaire_basculee(c, res):
        db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", (res["avant"]["corps"], res["avant"]["modifie"], res["id"]))
        db.ecrire("DELETE FROM versions WHERE id=?", (res["vid"],))

    def case_lier(c, ref="", ligne=-1, tache_id=0):
        compte = compte_agit()
        n = exiger(ref, compte)
        try:
            i, tid = int(ligne), int(tache_id)
        except (TypeError, ValueError):
            raise ValueError("ligne ou tâche invalide")
        k = [x for x in cases_de(n["corps"]) if x["ligne"] == i]
        if not k:
            raise ValueError("cette ligne n'est pas une case à cocher")
        if etat_tache(tid) is None:
            raise ValueError("tâche introuvable")
        avant = db.lire("SELECT * FROM cases WHERE note_id=? AND ligne=?", (n["id"], i))
        db.ecrire("INSERT OR REPLACE INTO cases(note_id, ligne, tache_id, texte) VALUES (?,?,?,?)", (n["id"], i, tid, k[0]["texte"][:200]))
        noter(n["id"], "Case liée à une tâche", "tâche %s" % tid, qui_agit(compte))
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "ligne": i, "tache_id": tid, "avant": dict(avant[0]) if avant else None}

    def prouver_case_liee(c, res):
        r = db.lire("SELECT tache_id FROM cases WHERE note_id=? AND ligne=?", (res["id"], res["ligne"]))
        return bool(r) and r[0]["tache_id"] == res["tache_id"]

    def defaire_case_liee(c, res):
        if res["avant"]:
            a = res["avant"]
            db.ecrire("INSERT OR REPLACE INTO cases(note_id, ligne, tache_id, texte) VALUES (?,?,?,?)", (a["note_id"], a["ligne"], a["tache_id"], a["texte"]))
        else:
            db.ecrire("DELETE FROM cases WHERE note_id=? AND ligne=?", (res["id"], res["ligne"]))

    def case_delier(c, ref="", ligne=-1):
        compte = compte_agit()
        n = exiger(ref, compte)
        try:
            i = int(ligne)
        except (TypeError, ValueError):
            raise ValueError("ligne invalide")
        avant = db.lire("SELECT * FROM cases WHERE note_id=? AND ligne=?", (n["id"], i))
        if not avant:
            raise ValueError("cette case n'est liée à aucune tâche")
        db.ecrire("DELETE FROM cases WHERE note_id=? AND ligne=?", (n["id"], i))
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "ligne": i, "avant": dict(avant[0])}

    def prouver_case_deliee(c, res):
        return not db.lire("SELECT 1 FROM cases WHERE note_id=? AND ligne=?", (res["id"], res["ligne"]))

    def defaire_case_deliee(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO cases(note_id, ligne, tache_id, texte) VALUES (?,?,?,?)", (a["note_id"], a["ligne"], a["tache_id"], a["texte"]))

    def cases_reprendre(c, ref=""):
        """Le sens retour : on ferme une tâche, la case se coche dans la note. Une seule réécriture, pas une version par case."""
        compte = compte_agit()
        n = exiger(ref, compte)
        etat = cases_etat(c, ref)
        lignes = n["corps"].split("\n")
        change = []
        for k in etat["cases"]:
            if k["tache"] is None or k["tache_faite"] is None or k["tache_faite"] == k["faite"]:
                continue
            m = RE_CASE.match(lignes[k["ligne"]]) if k["ligne"] < len(lignes) else None
            if not m:
                continue
            lignes[k["ligne"]] = "%s[%s] %s" % (m.group(1), "x" if k["tache_faite"] else " ", m.group(3))
            change.append(k["texte"])
        if not change:
            return {"id": n["id"], "ref": n["ref"], "compte": compte, "reprises": [], "vid": None, "avant": None, "note": "Les deux côtés disent déjà la même chose."}
        vid = versionner(n, qui_agit(compte), "%d case(s) reprise(s) des tâches" % len(change))
        db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", ("\n".join(lignes), time.time(), n["id"]))
        noter(n["id"], "Cases reprises des tâches", "%d" % len(change), qui_agit(compte))
        return {"id": n["id"], "ref": n["ref"], "compte": compte, "reprises": change, "vid": vid, "avant": {"corps": n["corps"], "modifie": n["modifie"]}}

    def prouver_reprise(c, res):
        return True if not res["reprises"] else db.lire("SELECT corps FROM notes WHERE id=?", (res["id"],))[0]["corps"] != res["avant"]["corps"]

    def defaire_reprise(c, res):
        if res["avant"]:
            db.ecrire("UPDATE notes SET corps=?, modifie=? WHERE id=?", (res["avant"]["corps"], res["avant"]["modifie"], res["id"]))
            db.ecrire("DELETE FROM versions WHERE id=?", (res["vid"],))

    # ------------------------------------------------------------------ partage
    def partage_creer(c, ref="", format="html", jours=None, mdp=""):
        compte = compte_agit()
        n = exiger(ref, compte)
        fmt = str(format or "html").lower()
        if fmt not in FORMATS:
            raise ValueError("format inconnu (%s)" % ", ".join(FORMATS))
        try:
            j = JOURS_PARTAGE if jours is None else int(jours)
        except (TypeError, ValueError):
            j = JOURS_PARTAGE
        nb = db.lire("SELECT COUNT(*) AS n FROM partages WHERE compte=?", (compte,))[0]["n"]
        if nb >= MAX_PARTAGES:
            raise ValueError("trop de liens ouverts (%d) — retire-en avant d'en créer" % nb)
        jeton = secrets.token_urlsafe(16)
        exp = time.time() + j * 86400 if j > 0 else None
        db.ecrire("INSERT INTO partages(jeton, compte, note_id, titre, format, mdp, expire_le, cree) VALUES (?,?,?,?,?,?,?,?)", (jeton, compte, n["id"], n["titre"], fmt, hacher_mdp(mdp) if mdp else "", exp, time.time()))
        noter(n["id"], "Lien de partage ouvert", "%s, %s" % (fmt, ("%d jours" % j) if j > 0 else "sans échéance"), qui_agit(compte))
        ctx.emettre("note.partagee", objet=("note", str(n["id"])), donnees={"id": n["ref"], "format": fmt, "protege": bool(mdp)})
        return {"jeton": jeton, "compte": compte, "note": n["ref"], "titre": n["titre"], "format": fmt, "expire_le": date_dit(exp), "protege": bool(mdp), "chemin": "/api/public/notes.partage_servir"}

    def prouver_partage(c, res):
        return bool(db.lire("SELECT 1 FROM partages WHERE jeton=?", (res["jeton"],)))

    def defaire_partage(c, res):
        db.ecrire("DELETE FROM partages WHERE jeton=?", (res["jeton"],))

    def partage_retirer(c, jeton=""):
        """Retire un lien IMMÉDIATEMENT. Le compte est dans la condition : un jeton deviné ne retire pas le lien de quelqu'un d'autre."""
        compte = compte_agit()
        avant = db.lire("SELECT * FROM partages WHERE jeton=? AND compte=?", (str(jeton or "").strip(), compte))
        if not avant:
            raise ValueError("lien inconnu")
        db.ecrire("DELETE FROM partages WHERE jeton=? AND compte=?", (avant[0]["jeton"], compte))
        return {"jeton": avant[0]["jeton"], "compte": compte, "avant": dict(avant[0])}

    def prouver_partage_retire(c, res):
        return not db.lire("SELECT 1 FROM partages WHERE jeton=?", (res["jeton"],))

    def defaire_partage_retire(c, res):
        a = res["avant"]
        ks = list(a)
        db.ecrire("INSERT OR REPLACE INTO partages(%s) VALUES (%s)" % (",".join(ks), ",".join("?" * len(ks))), [a[k] for k in ks])

    def partage_servir(c, jeton="", mdp="", compter=True):
        """Ce que sert la route publique. AUCUNE session n'est consultée. Chaque refus est distinct (inconnu, expiré, mot de passe) et rendu comme RÉSULTAT, jamais comme
        exception : un refus public qui lève ferait baisser le palier de la capacité pour tout le monde."""
        j = str(jeton or "").strip()
        if not j or len(j) > 64 or not re.match(r"^[A-Za-z0-9_-]+$", j):               # le jeton n'est pas un chemin : on n'accepte que l'alphabet qu'on produit
            return {"ok": False, "code": 404, "erreur": "lien inconnu"}
        r = db.lire("SELECT * FROM partages WHERE jeton=?", (j,))
        if not r:
            return {"ok": False, "code": 404, "erreur": "lien inconnu"}
        p = r[0]
        if p["expire_le"] and p["expire_le"] < time.time():
            return {"ok": False, "code": 410, "erreur": "ce lien a expiré", "titre": p["titre"]}
        if p["mdp"]:
            maintenant = time.time()
            recents = [t for t in essais.get(j, []) if maintenant - t < FENETRE_MDP]
            essais[j] = recents
            if len(recents) >= ESSAIS_MDP:
                return {"ok": False, "code": 429, "limite": True, "erreur": "trop d'essais — réessaie plus tard", "attente_s": int(FENETRE_MDP - (maintenant - recents[0]))}
            if not mdp_ok(p["mdp"], mdp):
                if mdp:
                    essais[j].append(maintenant)
                return {"ok": False, "code": 401, "mdp": True, "titre": p["titre"], "erreur": "mot de passe incorrect" if mdp else "mot de passe demandé"}
        n = db.lire("SELECT * FROM notes WHERE id=? AND corbeille_at IS NULL", (p["note_id"],))
        if not n:
            return {"ok": False, "code": 404, "erreur": "la note n'existe plus"}
        e = rendre(champs(n[0]), p["format"])
        if compter:                                            # seulement les vraies ouvertures : un messager visite le lien pour en fabriquer l'aperçu
            db.ecrire("UPDATE partages SET n_vues=n_vues+1, dernier=? WHERE jeton=?", (time.time(), j))
        return {"ok": True, "code": 200, "nom": e["nom"], "mime": e["mime"], "contenu": e["contenu"], "titre": p["titre"], "format": p["format"]}

    def resoudre_textes(c, texte="", textes=None):
        """Les renvois [[…]] d'un texte nu (une tâche, un rappel, un message n'ont pas de fiche) : leurs cibles, sans rien garder du texte."""
        compte = compte_agit()
        vivantes = toutes(compte)
        memo = {}
        if isinstance(textes, list):
            return {"lots": [liens_resolus(str(x or "")[:20000], vivantes, memo) for x in textes[:400]]}
        return {"liens": liens_resolus(str(texte or "")[:20000], vivantes, memo)}

    def cibles(c, q="", limite=300):
        """Tout ce vers quoi un renvoi peut pointer : mes notes, puis ce que les autres modules listent pour moi. Une nature qui échoue ne vide pas les autres."""
        compte = compte_agit()
        q = str(q or "").strip().lower()
        out, soucis = [], []

        def ajouter(kind, ref, titre, detail=""):
            ref, titre = str(ref or ""), str(titre or ref)
            if not ref or (q and q not in titre.lower() and q not in ref.lower() and q not in kind):
                return
            out.append({"kind": kind, "ref": ref, "titre": titre, "detail": str(detail or ""), "n": kind, "ecriture": "[[%s:%s]]" % (kind, ref)})
        for n in toutes(compte):
            ajouter("note", n["ref"], n["titre"], n["dossier"])
        for kind, cap, cle, champ in (("projet", "projets.lister", "projets", "nom"), ("tache", "taches.lister", "taches", "texte")):
            try:
                for x in (ctx.executer_lecture(cap) or {}).get(cle) or []:
                    ajouter(kind, x.get("id"), x.get(champ) or x.get("titre") or x.get("nom") or x.get("texte"), x.get("statut") or x.get("etat") or "")
            except Exception as ex:
                soucis.append("%s : %s" % (kind, str(ex)[:70]))
        out.sort(key=lambda x: (0 if x["kind"] == "note" else 1, x["titre"].lower()))
        return {"cibles": out[:int(limite)], "total": len(out), "soucis": soucis}

    def jours_de(quand):
        """Le nombre de jours entre aujourd'hui et une date « AAAA-MM-JJ… » (négatif : dépassée) ; None si elle est illisible."""
        s = str(quand or "")[:10]
        try:
            t = time.mktime(time.strptime(s, "%Y-%m-%d"))
        except Exception:
            return None
        return int(round((t - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) / 86400))

    def item_jour(bande, quoi, titre, detail="", nat="", ref="", poids=0, ou="", geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": nat, "ref": str(ref or ""), "poids": int(poids), "ou": ou,
                "geste": list(geste) if geste else None}

    def signal_jour(c):
        """Les notes dont la relecture est due : `relire` est une DATE posée par la personne, la laisser passer sans rien dire vide le champ de son sens."""
        out = []
        for n in lister(c, groupe="*").get("notes", []):
            j = jours_de(n.get("relire"))
            if j is None or j > 0:
                continue
            out.append(item_jour("brule" if j < -7 else "jour", "note", n.get("titre") or n.get("id") or "(sans titre)",
                                 ("Relecture prévue le %s." % str(n.get("relire"))[:10]) if j < 0 else "À relire aujourd'hui.", "note", n.get("id"), 60 - j, "notes", geste=("Lire", "ouvrir")))
        return {"items": out}

    # ------------------------------------------------------------------ détecteur
    def det_relecture(c):
        auj = time.strftime("%Y-%m-%d")
        return [{"objet": ("note", str(r["id"])), "compte": r["compte"], "titre": "Relecture due : %s" % r["titre"][:80], "detail": "prévue le %s" % r["relire"]}
                for r in db.lire("SELECT id, compte, titre, relire FROM notes WHERE corbeille_at IS NULL AND relire<>'' AND relire<=? AND etat<>'archive'", (auj,))]

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.detecteur("relecture_due", det_relecture)
    for cid, f in (("lister", lister), ("fiche", fiche), ("versions", versions), ("version_lire", version_lire), ("corbeille", corbeille), ("dossiers", dossiers), ("liens", liens), ("de", de),
                   ("mentions", mentions), ("cases", cases), ("cases_etat", cases_etat), ("menage", menage), ("jour", jour), ("exporter", exporter), ("archive", archive), ("partages", partages), ("resoudre", resoudre_textes), ("cibles", cibles), ("signal_jour", signal_jour)):
        c.implementer(cid, f)
    c.implementer("creer", creer, prouver_creee, defaire_creee, simuler=lambda x, titre="", **_: "créerait la note « %s »" % titre)
    c.implementer("ecrire", ecrire, prouver_ecrite, defaire_ecrite, simuler=lambda x, ref="", **_: "modifierait la note %s" % ref)
    c.implementer("revenir", revenir, prouver_revenue, defaire_revenue, simuler=lambda x, ref="", version="", **_: "ramènerait la note %s à la version %s" % (ref, version))
    c.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee, simuler=lambda x, ref="", **_: "mettrait la note %s à la corbeille" % ref)
    c.implementer("restaurer", restaurer, prouver_restauree, defaire_restauree, simuler=lambda x, ref="", **_: "sortirait la note %s de la corbeille" % ref)
    c.implementer("vider_corbeille", vider_corbeille, prouver_videe, defaire_videe, simuler=lambda x, **_: "effacerait pour de bon toutes les notes de la corbeille, avec leurs versions")
    c.implementer("fusionner", fusionner, prouver_fusion, defaire_fusion, simuler=lambda x, refs=None, titre="", **_: "fusionnerait %d notes en « %s »" % (len(refs or []), titre))
    c.implementer("importer", importer, prouver_importe, defaire_importe, simuler=lambda x, fichiers=None, **_: "importerait %d fichier(s) comme notes neuves" % len(fichiers or []))
    c.implementer("jour_ouvrir", jour_ouvrir, prouver_jour, defaire_jour, simuler=lambda x, **_: "ouvrirait la note du jour")
    c.implementer("dossier_creer", dossier_creer, prouver_dossier_cree, defaire_dossier_cree, simuler=lambda x, chemin="", **_: "créerait le dossier « %s »" % chemin)
    c.implementer("dossier_renommer", dossier_renommer, prouver_dossier_renomme, defaire_dossier_renomme, simuler=lambda x, chemin="", nom="", **_: "renommerait « %s » en « %s »" % (chemin, nom))
    c.implementer("dossier_supprimer", dossier_supprimer, prouver_dossier_supprime, defaire_dossier_supprime, simuler=lambda x, chemin="", **_: "retirerait le dossier « %s » (ses notes remontent)" % chemin)
    c.implementer("case_basculer", case_basculer, prouver_basculee, defaire_basculee, simuler=lambda x, ref="", ligne="", **_: "basculerait la case %s de la note %s" % (ligne, ref))
    c.implementer("case_lier", case_lier, prouver_case_liee, defaire_case_liee, simuler=lambda x, ref="", ligne="", tache_id="", **_: "lierait la case %s de %s à la tâche %s" % (ligne, ref, tache_id))
    c.implementer("case_delier", case_delier, prouver_case_deliee, defaire_case_deliee, simuler=lambda x, ref="", ligne="", **_: "délierait la case %s de %s" % (ligne, ref))
    c.implementer("cases_reprendre", cases_reprendre, prouver_reprise, defaire_reprise, simuler=lambda x, ref="", **_: "reporterait l'état des tâches liées dans les cases de %s" % ref)
    c.implementer("partage_creer", partage_creer, prouver_partage, defaire_partage, simuler=lambda x, ref="", **_: "ouvrirait un lien public vers la note %s" % ref)
    c.implementer("partage_retirer", partage_retirer, prouver_partage_retire, defaire_partage_retire, simuler=lambda x, jeton="", **_: "retirerait le lien de partage")
    c.implementer("partage_servir", partage_servir)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : num_dit, segment_ok, dossier_ok, dossier_propre, dossier_projet, liens_de, cases_de, ancres_de …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
