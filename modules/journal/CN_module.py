# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le journal
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : journal
# ZONE       : CN
# VERSION CN : 0.1.0  #2cecb5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le journal : le fil des agents et le lecteur unifié des journaux.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2cecb5 ▼▼▼
"""Le journal : le fil des agents et le lecteur unifié des journaux.

Porté de la V18 (`journal_*`), avec ses leçons :
  - le journal des agents inscrit une consultation avec SA question ET SA réponse — la question est
    toujours celle qu'on oublie de garder ; trois rôles (claude, itare, cassandra), chacun parle sous
    le sien, jamais sous un nom deviné (au pire « inconnu ») ;
  - un journal qui n'est pas déclaré dans le catalogue n'existe pas pour le lecteur ;
  - un journal absent ou vide est rendu quand même, marqué comme tel : le silence d'une source est une
    information, pas une raison de la cacher ;
  - on lit la FIN d'un fichier (un journal se consulte par le bas) ; la ligne brute reste la référence
    de preuve, l'enveloppe donne à chaque ligne les sept mêmes clés ;
  - une erreur jamais vue mérite d'être lue, une erreur connue qui revient est du bruit ;
  - un journal en table appartient à UN module : le lecteur le lit en lecture seule, jamais il n'écrit
    chez un autre.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

ROLES = ("claude", "itare", "cassandra")


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


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── le catalogue des sources ────────────────────────────────────────────────
# table : `module` (son stockage) + table + colonnes ; file : des chemins candidats (le même journal
# s'appelle `syslog` ici et `messages` là) ; cmd : déféré au courtier racine, pas de shell ici.
SOURCES = {
    "agents": {"label": "Journal des agents", "icon": "🎭", "module": "journal", "table": "journal_agents", "ts": "ts",
               "cols": ["ts", "qui", "modele", "etiquette", "reponse", "consigne", "dossier"],
               "search": ["reponse", "dossier", "etiquette", "qui"], "title": "etiquette", "badge": "qui",
               "desc": "Consultations avant écriture : la consigne, le dossier et la réponse, dans la même ligne."},
    "salon": {"label": "Salon — fils", "icon": "🗂", "module": "salon", "table": "journal", "ts": "ts",
              "cols": ["ts", "acteur", "geste", "fil", "titre", "messages", "details"],
              "search": ["geste", "titre", "details", "acteur"], "title": "titre", "badge": "acteur",
              "desc": "Suppressions et changements de statut des fils du salon."},
    # ── les journaux du SYSTÈME ──
    "syslog": {"label": "Syslog", "icon": "🗒", "group": "Système",
               "files": ["/var/log/syslog", "/var/log/messages"], "desc": "Messages généraux du système."},
    "auth": {"label": "Authentifications", "icon": "🔑", "group": "Système",
             "files": ["/var/log/auth.log", "/var/log/secure"], "desc": "Connexions SSH, sudo, tentatives d'intrusion."},
    "kern": {"label": "Noyau", "icon": "⚙️", "group": "Système",
             "files": ["/var/log/kern.log", "/var/log/dmesg"], "desc": "Matériel, mémoire, tueur de processus (OOM)."},
    "nginx_err": {"label": "nginx — erreurs", "icon": "🌐", "group": "Système",
                  "files": ["/var/log/nginx/error.log"], "desc": "Pourquoi un site rend 500 ou 502."},
    "nginx_acc": {"label": "nginx — accès", "icon": "🌐", "group": "Système",
                  "files": ["/var/log/nginx/access.log"], "desc": "Requêtes reçues par les sites."},
    "maillog": {"label": "Serveur de messagerie", "icon": "✉️", "group": "Système",
                "files": ["/var/log/mail.log", "/var/log/maillog"], "desc": "Remises, rejets, authentifications IMAP/SMTP."},
    "fail2ban": {"label": "fail2ban", "icon": "🚫", "group": "Système",
                 "files": ["/var/log/fail2ban.log"], "desc": "Adresses bannies et récidives."},
    "letsencrypt": {"label": "Let's Encrypt", "icon": "🔒", "group": "Système",
                    "files": ["/var/log/letsencrypt/letsencrypt.log"], "desc": "Pourquoi un certificat n'a pas été renouvelé."},
    "upgrades": {"label": "Mises à jour", "icon": "📦", "group": "Système",
                 "files": ["/var/log/unattended-upgrades/unattended-upgrades.log", "/var/log/apt/history.log"],
                 "desc": "Ce qui a été installé ou mis à jour, et quand."},
}


# ── l'enveloppe commune : sept clés, quelle que soit la source ─────────────
_TS_LIGNE = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)")
_ENV_ACTEURS = ("acteur", "username", "qui", "user", "auteur", "par", "compte", "session_id")
_ENV_NIVEAUX = (("critical", "critique"), ("crit", "critique"), ("fatal", "critique"), ("alert", "critique"),
                ("error", "erreur"), ("erreur", "erreur"), ("err", "erreur"), ("fail", "erreur"), ("traceback", "erreur"),
                ("warning", "avertissement"), ("warn", "avertissement"), ("avertissement", "avertissement"),
                ("avoir", "avertissement"), ("debug", "info"), ("notice", "info"), ("info", "info"), ("ok", "info"), ("success", "info"))
_ENV_MOIS = {"jan": "01", "feb": "02", "fév": "02", "fev": "02", "mar": "03", "apr": "04", "avr": "04", "may": "05", "mai": "05",
             "jun": "06", "juin": "06", "jul": "07", "juil": "07", "aug": "08", "aoû": "08", "aou": "08", "sep": "09",
             "oct": "10", "nov": "11", "dec": "12", "déc": "12"}
_ENV_TS_NGINX = re.compile(r"(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}:\d{2}:\d{2})")
_ENV_TS_APACHE = re.compile(r"[A-Za-z]{3} ([A-Za-z]{3}) (\d{2}) (\d{2}:\d{2}:\d{2})(?:\.\d+)? (\d{4})")
_ENV_TS_SYSLOG = re.compile(r"^([A-Za-z]{3}) +(\d{1,2}) (\d{2}:\d{2}:\d{2})")
_ERR_RE = re.compile(r"\b(error|erreur|fail(ed|s|ure)?|échec|echec|fatal|refused|denied|"
                     r"timeout|traceback|exception|critical|panic|abort(ed)?)\b", re.I)


def _ts_norm(v) -> str:
    """Horodatage comparable, quel que soit le format d'origine (epoch, ISO, nginx, apache, syslog)."""
    s = str(v if v is not None else "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{9,11}(?:\.\d+)?", s):
        try:
            return datetime.fromtimestamp(float(s), timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""
    m = _TS_LIGNE.search(s)
    if m:
        h = m.group(2)
        return "%s %s" % (m.group(1), h if len(h) == 8 else h + ":00")
    m = _ENV_TS_NGINX.search(s)
    if m:
        return "%s-%s-%s %s" % (m.group(3), _ENV_MOIS.get(m.group(2).lower(), "01"), m.group(1), m.group(4))
    m = _ENV_TS_APACHE.search(s)
    if m:
        return "%s-%s-%s %s" % (m.group(4), _ENV_MOIS.get(m.group(1).lower(), "01"), m.group(2), m.group(3))
    m = _ENV_TS_SYSLOG.search(s)
    if m:
        return "%s-%s-%02d %s" % (time.strftime("%Y", time.gmtime()), _ENV_MOIS.get(m.group(1).lower(), "01"), int(m.group(2)), m.group(3))
    return s[:19]


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


def _niveau(v, defaut="info") -> str:
    """_niveau. Le calcul est un POINT D'ÉVOLUTION : points/EC_niveau.py."""
    return _point("niveau", {"v": v, "defaut": defaut})["valeur"]


def _age_s(ts) -> int:
    s = _ts_norm(ts)
    if not s:
        return None
    try:
        d = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    return int((_utcnow() - d).total_seconds())


def _signature(texte: str) -> str:
    """Empreinte d'une erreur, débarrassée de ce qui change à chaque occurrence (ports, adresses, dates). Le calcul est un POINT D'ÉVOLUTION : points/EC_signature.py."""
    return _appeler_point("signature", {"texte": texte})["valeur"]


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def kind(spec):
        if spec.get("cmd"):
            return "cmd"
        if spec.get("file") or spec.get("files"):
            return "file"
        return "table"

    def base_de(spec):
        """La base d'une source en table : la sienne, ou celle d'un AUTRE module, en lecture seule."""
        return ctx.stockage_lecture(spec["module"])

    def fichier_de(spec):
        if spec.get("file"):
            return spec["file"] if os.path.isfile(spec["file"]) else ""
        for c in spec.get("files", []) or []:
            try:
                if os.path.isfile(c):
                    return c
            except Exception:
                continue
        return ""

    def cols_reels(spec):
        """Colonnes qui existent VRAIMENT : demander une colonne absente ferait échouer la requête entière."""
        try:
            presentes = {r["name"] for r in base_de(spec).lire("PRAGMA table_info(%s)" % spec["table"])}
        except Exception:
            return []
        if not presentes:
            return []
        return [c for c in spec["cols"] if c in presentes]

    def enveloppe(source, ligne_ou_row):
        """Les sept clés, pour une rangée de table (dict) ou une ligne de fichier (str)."""
        spec = SOURCES.get(source) or {}
        env = spec.get("env") or {}
        if not isinstance(ligne_ou_row, dict):
            s = str(ligne_ou_row or "")
            ts = _ts_norm(s)
            niveau, bas = "info", s.lower()
            for cle, niv in _ENV_NIVEAUX:
                if niv != "info" and cle in bas:
                    niveau = niv
                    break
            return {"ts": ts, "niveau": niveau, "source": source, "acteur": "", "action": s.strip()[:300], "sujet": "", "detail": {}}
        row = dict(ligne_ou_row)
        pris = set()

        def prendre(cle, candidats):
            c = env.get(cle)
            if c and str(c).startswith("="):
                return str(c)[1:]
            for k in ([c] if c else []) + list(candidats):
                if k and k in row and row[k] is not None and row[k] != "":
                    pris.add(k)
                    return row[k]
            return ""
        ts = _ts_norm(prendre("ts", [spec.get("ts", "ts"), "ts"]))
        brut = prendre("niveau", ["niveau", "level", "status", "statut", "verdict", "resultat", "mood", "is_risky"])
        niveau = _niveau(brut)
        if not env.get("niveau") and "rc" in row and str(row.get("rc")) not in ("", "0", "None"):
            niveau = "avertissement"
        acteur = str(prendre("acteur", _ENV_ACTEURS))
        if len(acteur) == 64:
            acteur = "session " + acteur[:8]
        action = str(prendre("action", [spec.get("title", "")]))[:300]
        sujet = str(prendre("sujet", [spec.get("badge", ""), "secret_name", "target_file", "category", "topic", "sujet", "titre", "fil"]))[:200]
        detail = {k: v for k, v in row.items() if k not in pris and v is not None and v != ""}
        return {"ts": ts, "niveau": niveau, "source": source, "acteur": acteur, "action": action, "sujet": sujet, "detail": detail}

    # ── lire une source ─────────────────────────────────────────────────────
    def lire(c, source="", limit=100, offset=0, query="", since=""):
        spec = SOURCES.get((source or "").strip())
        if not spec:
            raise ValueError("journal inconnu")
        limit = max(1, min(int(limit or 100), 500))
        offset = max(0, int(offset or 0))
        g = kind(spec)

        if g == "cmd":
            return {"source": source, "kind": "cmd", "lines": [], "total": 0, "reason": "commande déférée au courtier"}

        if g == "file":
            chemin = fichier_de(spec)
            if not chemin:
                return {"source": source, "kind": "file", "lines": [], "total": 0,
                        "reason": "fichier absent (cherché : %s)" % ", ".join(spec.get("files") or ([spec["file"]] if spec.get("file") else []))}
            try:
                with open(chemin, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    taille = f.tell()
                    bloc = min(taille, 400_000)
                    f.seek(taille - bloc)
                    brut = f.read().decode("utf-8", errors="replace")
                lignes = brut.splitlines()
                if bloc < taille and lignes:
                    lignes = lignes[1:]
                if query:
                    q = query.lower()
                    lignes = [l for l in lignes if q in l.lower()]
                total = len(lignes)
                fenetre = lignes[::-1][offset:offset + limit]
                return {"source": source, "kind": "file", "lines": fenetre,
                        "env": [enveloppe(source, l) for l in fenetre],
                        "total": total, "offset": offset, "truncated": bloc < taille,
                        "has_more": offset + len(fenetre) < total}
            except Exception as e:
                return {"source": source, "kind": "file", "lines": [], "total": 0, "reason": str(e)}

        cols = cols_reels(spec)
        if not cols:
            return {"source": source, "kind": "table", "rows": [], "total": 0, "columns": [],
                    "reason": "table absente ou vide (%s)" % spec["table"]}
        ts = spec["ts"] if spec["ts"] in cols else cols[0]
        conditions, params = [], []
        if query:
            champs = [c for c in spec.get("search", []) if c in cols] or cols
            conditions.append("(" + " OR ".join("lower(COALESCE(%s,'')) LIKE ?" % c for c in champs) + ")")
            params += ["%%%s%%" % query.lower()] * len(champs)
        if since:
            conditions.append("%s >= ?" % ts)
            params.append(since)
        ou = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        base = base_de(spec)
        try:
            total = base.lire("SELECT COUNT(*) AS n FROM %s%s" % (spec["table"], ou), params)[0]["n"]
            rows = base.lire("SELECT %s FROM %s%s ORDER BY %s DESC LIMIT ? OFFSET ?"
                             % (", ".join(cols), spec["table"], ou, ts), params + [limit, offset])
        except Exception as e:
            return {"source": source, "kind": "table", "rows": [], "total": 0, "reason": str(e)}
        return {"source": source, "kind": "table", "columns": cols, "ts_col": ts,
                "env": [enveloppe(source, r) for r in rows],
                "title_col": spec.get("title", ""), "label": spec["label"], "badge_col": spec.get("badge", ""),
                "rows": [dict(r) for r in rows], "total": total, "offset": offset,
                "has_more": offset + len(rows) < total}

    # ── les capacités de lecture ────────────────────────────────────────────
    def sources(c):
        out = []
        for cle, spec in SOURCES.items():
            g = kind(spec)
            item = {"key": cle, "label": spec["label"], "icon": spec.get("icon", ""),
                    "desc": spec.get("desc", ""), "kind": g, "group": spec.get("group", "Cassandra"),
                    "count": 0, "available": False, "last": "", "path": ""}
            if g == "file":
                chemin = fichier_de(spec)
                item["path"] = chemin
                item["available"] = bool(chemin)
                if chemin:
                    try:
                        item["count"] = os.path.getsize(chemin)
                        item["last"] = datetime.fromtimestamp(os.path.getmtime(chemin)).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass
            elif g == "table":
                cols = cols_reels(spec)
                if cols:
                    try:
                        base = base_de(spec)
                        item["count"] = base.lire("SELECT COUNT(*) AS n FROM %s" % spec["table"])[0]["n"]
                        ts = spec["ts"] if spec["ts"] in cols else cols[0]
                        r = base.lire("SELECT MAX(%s) AS m FROM %s" % (ts, spec["table"]))
                        item["last"] = str(r[0]["m"] or "")[:16] if r else ""
                        item["available"] = True
                    except Exception:
                        pass
            out.append(item)
        return {"sources": out}

    def chercher(c, question="", per_source=5):
        q = (question or "").strip()
        if not q:
            raise ValueError("terme de recherche requis")
        resultats = []
        for cle, spec in SOURCES.items():
            r = lire(c, source=cle, limit=per_source, query=q)
            n = r.get("total", 0)
            if not n:
                continue
            resultats.append({"key": cle, "label": spec["label"], "icon": spec.get("icon", ""),
                              "total": n, "kind": r.get("kind"),
                              "rows": r.get("rows", []), "lines": r.get("lines", []),
                              "ts_col": r.get("ts_col", ""), "title_col": r.get("title_col", "")})
        resultats.sort(key=lambda x: -x["total"])
        return {"query": q, "results": resultats, "total": sum(x["total"] for x in resultats)}

    def flux(c, sources=None, limit=200, niveau="", acteur="", query="", since="", equilibre=True, bruit=True):
        limit = max(1, min(int(limit or 200), 1000))
        voulues = [s for s in (sources or []) if s in SOURCES] or list(SOURCES.keys())
        par_source = max(5, min(300, limit // max(1, len(voulues)))) if equilibre else max(20, min(300, limit))
        niveau = (niveau or "").strip().lower()
        acteur = (acteur or "").strip().lower()
        q = (query or "").strip().lower()
        depuis = _ts_norm(since) if since else ""
        entrees, en_defaut = [], []
        filtre = bool(niveau or acteur or q or depuis)
        lecture = min(500, max(200, par_source * 20)) if filtre else par_source
        for cle in voulues:
            try:
                d = lire(c, source=cle, limit=lecture)
            except Exception as e:
                en_defaut.append("%s : %s" % (cle, e))
                continue
            spec = SOURCES.get(cle) or {}
            bruts = [dict(x) for x in (d.get("rows") or [])] or list(d.get("lines") or [])
            gardees = 0
            for i, e in enumerate(d.get("env") or []):
                if gardees >= par_source:
                    break
                if niveau and not (e.get("niveau") == niveau or (niveau == "erreur+" and e.get("niveau") in ("erreur", "critique"))):
                    continue
                if acteur and acteur not in str(e.get("acteur") or "").lower():
                    continue
                if depuis and e.get("ts") and e["ts"] < depuis:
                    continue
                if q and q not in (str(e.get("action") or "") + " " + str(e.get("sujet") or "") + " " + json.dumps(e.get("detail") or {}, ensure_ascii=False)).lower():
                    continue
                entrees.append(dict(e, label=spec.get("label", cle), icon=spec.get("icon", ""), rang=i,
                                    brut=(bruts[i] if i < len(bruts) else None)))
                gardees += 1
        entrees.sort(key=lambda e: (e.get("ts") or "", e.get("source") or ""), reverse=True)
        bruit_retire = 0
        if not bruit:
            sig = lambda e: (e.get("source") or "") + "|" + re.sub(r"\d+", "#", str(e.get("action") or "").lower())[:80]
            comptes = {}
            for e in entrees:
                comptes[sig(e)] = comptes.get(sig(e), 0) + 1
            gardees = [e for e in entrees if comptes[sig(e)] < 10]
            bruit_retire = len(entrees) - len(gardees)
            entrees = gardees
        return {"sources": voulues, "total": len(entrees), "entrees": entrees[:limit], "en_defaut": en_defaut,
                "equilibre": bool(equilibre), "par_source": par_source, "bruit_retire": bruit_retire}

    def flux_recent(c, n=8):
        """Les derniers événements notables, sans le bruit, pour la tuile du Journal : une liste lisible."""
        d = flux(c, sources=[], limit=300, bruit=False)
        lignes = []
        for e in d.get("entrees", [])[:int(n or 8)]:
            lignes.append({"libelle": "[%s] %s" % (e.get("niveau", "info"), str(e.get("action") or "")[:90])})
        return {"lignes": lignes}

    def resume(c, heures=24):
        heures = max(1, min(int(heures or 24), 24 * 30))
        since = (_utcnow() - timedelta(hours=heures)).strftime("%Y-%m-%d %H:%M:%S")
        d = flux(c, sources=[], limit=1000, since=since)
        entrees = d.get("entrees") or []
        compte = {"critique": 0, "erreur": 0, "avertissement": 0, "info": 0}
        for e in entrees:
            n = e.get("niveau") or "info"
            compte[n if n in compte else "info"] += 1
        sources_lues = len({e.get("source") for e in entrees})
        marquants = [{"ts": e.get("ts"), "source": e.get("source"), "label": e.get("label"), "niveau": e.get("niveau"),
                      "action": str(e.get("action") or "")[:160]}
                     for e in entrees if e.get("niveau") in ("critique", "erreur")][:4]
        sans_nouvelles = []
        for s in sources(c).get("sources", []):
            if s.get("kind") != "table" or not s.get("available") or not s.get("count") or not s.get("last"):
                continue
            age = _age_s(s["last"])
            if age is not None and age > 7 * 86400:
                sans_nouvelles.append({"key": s["key"], "label": s["label"], "last": s["last"]})
        duree = ("%d h" % heures) if heures < 48 else ("%d jours" % (heures // 24))
        pl = lambda n, mot: "%d %s%s" % (n, mot, "s" if n > 1 else "")
        if compte["critique"]:
            titre = "%s et %s sur %s." % (pl(compte["critique"], "critique"), pl(compte["erreur"], "erreur"), duree)
        elif compte["erreur"]:
            titre = "%s, %s sur %s." % (pl(compte["erreur"], "erreur"), pl(compte["avertissement"], "avertissement"), duree)
        elif compte["avertissement"]:
            titre = "Aucune erreur sur %s, %s." % (duree, pl(compte["avertissement"], "avertissement"))
        else:
            titre = "Aucune erreur ni avertissement sur %s." % duree
        plj = lambda n: "%d %s" % (n, "journal" if n < 2 else "journaux")
        sous = "%s lues dans %s" % (pl(len(entrees), "ligne"), plj(sources_lues))
        if (d.get("total") or 0) >= 1000:
            sous += " — le flux est plafonné, les comptes portent sur ce qui est lu"
        if sans_nouvelles:
            sous += " · %s sans nouvelles depuis plus d'une semaine" % plj(len(sans_nouvelles))
        niveau = "panne" if compte["critique"] else ("regarder" if compte["erreur"] else "stable")
        return {"heures": heures, "niveau": niveau, "etat": niveau, "titre": titre, "detail": titre, "sous_titre": sous, "compte": compte,
                "lignes_lues": len(entrees), "sources_lues": sources_lues, "marquants": marquants,
                "sans_nouvelles": sans_nouvelles, "en_defaut": d.get("en_defaut") or [],
                "lu_le": _utcnow().strftime("%Y-%m-%d %H:%M:%S")}

    def silences(c, minimum=10):
        out = []
        for cle, spec in SOURCES.items():
            if kind(spec) != "table":
                continue
            d = lire(c, source=cle, limit=30)
            ts = sorted({_ts_norm(e.get("ts")) for e in (d.get("env") or []) if e.get("ts")}, reverse=True)
            if len(ts) < minimum:
                continue
            try:
                dates = [datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S") for t in ts]
            except Exception:
                continue
            ecarts = sorted((dates[i] - dates[i + 1]).total_seconds() for i in range(len(dates) - 1))
            mediane = ecarts[len(ecarts) // 2]
            age = _age_s(ts[0])
            if age is None or mediane <= 0:
                continue
            if mediane > 3600 or age > 7 * 86400:
                continue
            if age > max(3600.0, 3 * mediane):
                out.append({"key": cle, "label": spec.get("label", cle), "last": ts[0], "age_s": int(age), "attendu_s": int(mediane)})
        out.sort(key=lambda x: -x["age_s"] / max(1, x["attendu_s"]))
        return {"silences": out[:20]}

    def timeline(c, at="", window_min=15, sources=None, limit=400):
        centre = _ts_norm(at) or _utcnow().strftime("%Y-%m-%d %H:%M:%S")
        try:
            pivot = datetime.strptime(centre[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            try:
                pivot = datetime.strptime(centre[:16], "%Y-%m-%d %H:%M")
            except Exception:
                raise ValueError("instant illisible (%s)" % at)
        marge = timedelta(minutes=max(1, min(int(window_min or 15), 1440)))
        debut = (pivot - marge).strftime("%Y-%m-%d %H:%M:%S")
        fin = (pivot + marge).strftime("%Y-%m-%d %H:%M:%S")
        voulues = set(sources or []) or set(SOURCES)
        evts = []
        for cle, spec in SOURCES.items():
            if cle not in voulues:
                continue
            if kind(spec) != "table":
                r = lire(c, source=cle, limit=800)
                for ligne in r.get("lines", []):
                    t = _ts_norm(ligne)
                    if debut <= t <= fin:
                        evts.append({"ts": t, "source": cle, "label": spec["label"], "icon": spec.get("icon", ""),
                                     "title": ligne.strip()[:300], "id": None, "detail": {}})
                continue
            cols = cols_reels(spec)
            if not cols:
                continue
            ts = spec["ts"] if spec["ts"] in cols else cols[0]
            titre = spec.get("title", "")
            sel = ", ".join(sorted(set(cols + (["id"] if "id" not in cols else []))))
            try:
                rows = base_de(spec).lire("SELECT %s FROM %s WHERE %s >= ? AND %s <= ? ORDER BY %s LIMIT ?"
                                          % (sel, spec["table"], ts, ts, ts), (debut, fin, limit))
            except Exception:
                continue
            for r in rows:
                d = dict(r)
                evts.append({"ts": _ts_norm(d.get(ts)), "source": cle, "label": spec["label"], "icon": spec.get("icon", ""),
                             "id": d.get("id"), "title": str(d.get(titre) or "")[:300] or "(sans intitulé)",
                             "detail": {k: str(v)[:600] for k, v in d.items() if k not in (ts, titre, "id") and v not in (None, "")}})
        evts.sort(key=lambda x: x["ts"])
        return {"at": centre, "from": debut, "to": fin, "window_min": int(window_min),
                "events": evts[:limit], "total": len(evts), "sources": sorted({e["source"] for e in evts})}

    def stats(c):
        out, total = [], 0
        for cle, spec in SOURCES.items():
            g = kind(spec)
            if g != "table":
                chemin = fichier_de(spec) if g == "file" else ""
                try:
                    o = os.path.getsize(chemin) if chemin else 0
                except Exception:
                    o = 0
                out.append({"key": cle, "label": spec["label"], "kind": g, "rows": 0, "bytes": o, "group": spec.get("group", "Cassandra")})
                total += o
                continue
            cols = cols_reels(spec)
            if not cols:
                continue
            try:
                base = base_de(spec)
                n = base.lire("SELECT COUNT(*) AS n FROM %s" % spec["table"])[0]["n"]
                o = base.lire("SELECT COALESCE(SUM(LENGTH(CAST(%s AS TEXT))),0) AS o FROM %s" % (cols[-1], spec["table"]))[0]["o"]
            except Exception:
                continue
            out.append({"key": cle, "label": spec["label"], "kind": "table", "rows": n, "bytes": int(o or 0)})
            total += int(o or 0)
        out.sort(key=lambda x: -x["bytes"])
        return {"journals": out, "bytes": total}

    # ── les veilles sur motif ───────────────────────────────────────────────
    def veilles(c):
        return {"veilles": db.lire("SELECT * FROM journal_watch ORDER BY id DESC")}

    def veille_poser(c, source="", pattern="", label="", enabled=True, wid=None):
        if source and source not in SOURCES:
            raise ValueError("journal inconnu")
        if not (pattern or "").strip():
            raise ValueError("motif requis")
        try:
            re.compile(pattern)
        except Exception as e:
            raise ValueError("motif invalide : %s" % e)
        if wid:
            avant = db.lire("SELECT * FROM journal_watch WHERE id=?", (int(wid),))
            if not avant:
                raise ValueError("veille inconnue")
            db.ecrire("UPDATE journal_watch SET source=?, pattern=?, label=?, enabled=? WHERE id=?",
                      (source, pattern, label or "", 1 if enabled else 0, int(wid)))
            return {"id": int(wid), "avant": avant[0]}
        _id = db.ecrire("INSERT INTO journal_watch (source, pattern, label, enabled) VALUES (?,?,?,?)",
                        (source, pattern, label or "", 1 if enabled else 0))
        return {"id": _id, "avant": None}

    def prouver_veille(c, res):
        return bool(db.lire("SELECT 1 FROM journal_watch WHERE id=?", (res["id"],)))

    def defaire_veille(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM journal_watch WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            db.ecrire("UPDATE journal_watch SET source=?, pattern=?, label=?, enabled=? WHERE id=?",
                      (a["source"], a["pattern"], a["label"], a["enabled"], a["id"]))

    def veille_retirer(c, wid=0):
        avant = db.lire("SELECT * FROM journal_watch WHERE id=?", (int(wid),))
        if not avant:
            raise ValueError("veille inconnue")
        db.ecrire("DELETE FROM journal_watch WHERE id=?", (int(wid),))
        return {"id": int(wid), "avant": avant[0]}

    def prouver_veille_retiree(c, res):
        return not db.lire("SELECT 1 FROM journal_watch WHERE id=?", (res["id"],))

    def defaire_veille_retiree(c, res):
        a = res["avant"]
        db.ecrire("INSERT INTO journal_watch(id, source, pattern, label, enabled, created_at) VALUES (?,?,?,?,?,?)",
                  (a["id"], a["source"], a["pattern"], a["label"], a["enabled"], a["created_at"]))

    # ── le journal des agents ───────────────────────────────────────────────
    def agents_ecrire(c, qui="", modele="", etiquette="", consigne="", dossier="", reponse=""):
        mid = db.ecrire("INSERT INTO journal_agents (qui, modele, etiquette, consigne, dossier, reponse) VALUES (?,?,?,?,?,?)",
                        (str(qui or "")[:40], str(modele or "")[:80], str(etiquette or "")[:200],
                         str(consigne or "")[:20000], str(dossier or "")[:60000], str(reponse or "")[:60000]))
        return {"id": mid}

    def prouver_agents_ecrire(c, res):
        return bool(db.lire("SELECT 1 FROM journal_agents WHERE id=?", (res["id"],)))

    def defaire_agents_ecrire(c, res):
        db.ecrire("DELETE FROM journal_agents WHERE id=?", (res["id"],))

    def agents_lire(c, n=8, qui="", cherche="", entier=False):
        q = "SELECT * FROM journal_agents WHERE 1=1"
        a = []
        if str(qui or "").strip():
            q += " AND qui=?"
            a.append(str(qui).strip().lower())
        if str(cherche or "").strip():
            q += " AND (reponse LIKE ? OR etiquette LIKE ? OR dossier LIKE ?)"
            a += ["%%%s%%" % cherche] * 3
        q += " ORDER BY id DESC LIMIT ?"
        a.append(max(1, min(40, int(n or 8))))
        out = []
        for x in db.lire(q, a):
            d = dict(x)
            if not entier:
                d["dossier"] = d["dossier"][:600]
                d["consigne"] = d["consigne"][:300]
                d["reponse"] = d["reponse"][:4000]
            out.append(d)
        return {"echanges": out, "n": len(out)}

    def fil(c, n=14, depuis=""):
        d = agents_lire(c, n=n)
        e = list(reversed(d["echanges"]))
        if str(depuis or "").strip():
            e = [x for x in e if x["ts"] >= str(depuis).strip()]
        return {"fil": e, "n": len(e)}

    def prompt(c, n=5):
        d = fil(c, n=n)
        if not d.get("fil"):
            return {"texte": ""}
        l = []
        for e in d["fil"]:
            t = " ".join((e["reponse"] or "").split())
            l.append("· [%s] %s — %s" % (e["qui"], e["etiquette"][:60], t[:260] + ("…" if len(t) > 260 else "")))
        return {"texte": "\n".join(l)}

    def agents_dire(c, etiquette="", message="", qui=""):
        m = str(message or "").strip()
        if not m:
            raise ValueError("un message vide n'apprend rien à personne")
        # UNE SIGNATURE NE SE DEVINE PAS : chacun parle sous le sien, jamais sous un nom passé au hasard.
        q = str(qui or "").strip().lower()
        if q not in ROLES:
            q = str(ctx.acteur or "").strip().lower()
            q = {"humain": "claude", "compte": "claude"}.get(q, q)   # le mainteneur est « claude » en V18
        if q not in ROLES:
            q = "inconnu"
        return agents_ecrire(c, qui=q, etiquette=str(etiquette or "note")[:200], reponse=m)

    def prouver_agents_dire(c, res):
        return bool(db.lire("SELECT 1 FROM journal_agents WHERE id=?", (res["id"],)))

    def defaire_agents_dire(c, res):
        db.ecrire("DELETE FROM journal_agents WHERE id=?", (res["id"],))

    # ── export ──────────────────────────────────────────────────────────────
    def exporter(c, source="", fmt="csv", query="", limit=5000):
        r = lire(c, source=source, limit=max(1, min(int(limit or 5000), 20000)), query=query)
        nom = "journal-%s-%s" % (source, _utcnow().strftime("%Y%m%d-%H%M"))
        if r.get("kind") in ("file", "cmd"):
            return {"mime": "text/plain", "nom": nom + ".txt", "contenu": "\n".join(r.get("lines", []))}
        lignes = r.get("rows", [])
        if (fmt or "csv").lower() == "json":
            return {"mime": "application/json", "nom": nom + ".json", "contenu": json.dumps(lignes, ensure_ascii=False, indent=1, default=str)}
        cols = r.get("columns", [])
        tampon = io.StringIO()
        w = csv.DictWriter(tampon, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for l in lignes:
            w.writerow({col: l.get(col) for col in cols})
        return {"mime": "text/csv", "nom": nom + ".csv", "contenu": "﻿" + tampon.getvalue()}

    # ── enregistrement ──────────────────────────────────────────────────────
    for cid, f in (("sources", sources), ("lire", lire), ("chercher", chercher), ("flux", flux),
                   ("flux_recent", flux_recent), ("resume", resume), ("silences", silences), ("timeline", timeline), ("stats", stats),
                   ("veilles", veilles), ("agents_lire", agents_lire),
                   ("fil", fil), ("prompt", prompt), ("exporter", exporter)):
        ctx.implementer(cid, f)
    ctx.implementer("agents_ecrire", agents_ecrire, prouver_agents_ecrire, defaire_agents_ecrire,
                    simuler=lambda x, etiquette="", **_: "inscrirait une consultation « %s » au journal des agents" % etiquette)
    ctx.implementer("agents_dire", agents_dire, prouver_agents_dire, defaire_agents_dire,
                    simuler=lambda x, message="", **_: "posterait au fil des agents : « %s »" % str(message)[:60])
    ctx.implementer("veille_poser", veille_poser, prouver_veille, defaire_veille,
                    simuler=lambda x, pattern="", **_: "poserait une veille sur « %s »" % pattern)
    ctx.implementer("veille_retirer", veille_retirer, prouver_veille_retiree, defaire_veille_retiree,
                    simuler=lambda x, wid=0, **_: "retirerait la veille %s" % wid)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _utcnow, _ts_norm, _niveau, _age_s, _signature, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
