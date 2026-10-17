# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La GED
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : ged
# ZONE       : CN
# VERSION CN : 0.1.0  #f09c4f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La GED : les documents d'un compte, par sources, avec un index et des règles de classement.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f09c4f ▼▼▼
"""La GED : les documents d'un compte, par sources, avec un index et des règles de classement.

Porté de la V18 (`ged_*`), avec ses leçons :
  - le cloisonnement vit DANS `_racines` : la liste, la résolution, le balayage et la recherche y passent ;
    une racine sans `compte` est COMMUNE, une racine parente (celle qui porte les dossiers de comptes)
    n'est visible de personne, et un compte ne voit que les siennes ;
  - une source sans propriétaire est commune par intention, pas par défaut ;
  - la configuration (racines, formes, plafonds) vit dans la base, pas dans un fichier de secrets ;
  - remplacer un fichier n'écrase pas son passé (version) ; déposer ne vise que des dossiers locaux ;
  - un document ACTIF (html, svg, xml…) ou un exécutable ne se dépose pas ; l'affichage en ligne passe
    par une liste blanche stricte, jamais le type deviné ;
  - la corbeille est par racine, sous `.corbeille/AAAA-MM-JJ`, jamais une suppression ; la vider est le
    SEUL endroit qui efface vraiment ;
  - un nom de dossier ne doit pas pouvoir remonter l'arborescence (séparateurs retirés, `..` interdit).

Différé proprement (dépendances lourdes ou modules absents) : distants rclone/OAuth, montages/fstab,
OCR/vignettes (poppler/ffmpeg/pillow), extraction des pièces jointes (module courrier), recettes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

GED_PUBLIC_NOM = "_public"
GED_PJ_NOM_DEFAUT = "Pièces jointes"
_GED_TAILLE_HASH = 128 * 1024 * 1024
_GED_DEPOT_MAX = 64 * 1024 * 1024
_GED_LISTE_MAX = 500
_GED_ARBO = ("Contrats", "Factures", "Reçus", "Courriers")

_GED_FORMES = {
    "documents": {"n": "Documents", "ic": "📎", "exts": (), "saute": ()},
    "coffre": {"n": "Coffre de notes", "ic": "💎",
               "exts": (".md", ".markdown", ".canvas"),
               "saute": (".obsidian", ".trash", ".git", ".stfolder", ".stversions", "node_modules", "__pycache__")},
}
_GED_INLINE_OK = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
                  "text/plain", "application/pdf", "application/json"}
_GED_EDITABLE = {"txt", "md", "csv", "tsv", "json", "yaml", "yml", "log", "ini", "conf", "cfg", "toml", "sql"}
_GED_DEPOT_TYPES = {
    "pdf", "doc", "docx", "odt", "rtf", "txt", "md", "csv", "tsv", "xls", "xlsx", "ods", "ppt", "pptx",
    "odp", "pages", "numbers", "key", "epub",
    "png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "heic", "heif", "tif", "tiff", "psd",
    "mp3", "ogg", "oga", "wav", "flac", "aac", "m4a", "opus", "mp4", "m4v", "webm", "mov", "mkv", "avi",
    "zip", "7z", "tar", "gz", "tgz", "bz2", "xz", "rar",
    "json", "yaml", "yml", "ics", "vcf", "eml", "msg", "log", "sql", "gpx", "kml",
}
_GED_LIEN_KINDS = ("project", "contact", "task", "event", "note", "mail", "url", "domain", "server")
_GED_REGLES_DEFAUT = [
    {"ordre": 10, "libelle": "Factures", "si_kind": "", "si_sujet": "facture|invoice",
     "dest": "/Comptabilité/{année}/{mois}", "etiquette": "facture"},
    {"ordre": 999, "libelle": "À classer", "dest": "/À classer", "etiquette": ""},
]
_GED_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
             "octobre", "novembre", "décembre"]
_ACTIFS = ("xml", "html", "svg", "htm", "xhtml", "mhtml", "mht")


def _nt_dossier_compte(compte: str) -> str:
    """L'adresse nettoyée plus une empreinte : deux comptes proches ne se retrouvent jamais au même endroit."""
    c = re.sub(r"[^a-z0-9]", "-", str(compte or "").lower()).strip("-")[:40] or "compte"
    h = hashlib.sha1(str(compte or "").encode("utf-8")).hexdigest()[:8]
    return "%s-%s" % (c, h)


def _media_kind(nom: str, mime: str = "") -> str:
    n = (nom or "").lower()
    if mime and mime.startswith(("image/", "video/", "audio/")):
        return mime.split("/")[0]
    ext = n.rsplit(".", 1)[-1] if "." in n else ""
    if ext in ("png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "heic", "heif", "tif", "tiff"):
        return "image"
    if ext in ("mp4", "m4v", "webm", "mov", "mkv", "avi"):
        return "video"
    if ext in ("mp3", "ogg", "oga", "wav", "flac", "aac", "m4a", "opus"):
        return "audio"
    if ext == "pdf":
        return "pdf"
    if ext in ("txt", "md", "csv", "tsv", "json", "yaml", "yml", "log"):
        return "texte"
    return "autre"


def _octets(n) -> str:
    n = float(n or 0)
    for u in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or u == "To":
            return ("%.0f %s" % (n, u)) if u == "o" else ("%.1f %s" % (n, u))
        n /= 1024.0
    return "%.0f o" % n


def _mime(nom: str) -> str:
    return mimetypes.guess_type(nom or "")[0] or "application/octet-stream"


def _depot_refuse(nom: str) -> str:
    """Le motif du refus, ou "" si le type se dépose."""
    ext = os.path.splitext(str(nom or ""))[1].lower().lstrip(".")
    if not ext:
        return "un fichier sans extension ne se dépose pas ici"
    if ext in _GED_DEPOT_TYPES:
        return ""
    if ext in _ACTIFS:
        return "un document actif (.%s) ne se dépose pas : il s'interpréterait" % ext
    return "type .%s refusé : seuls les documents, images, sons, vidéos, archives et données se déposent" % ext


def _inline_type(nom: str) -> str:
    """Type à annoncer pour un affichage en ligne, ou "" si le fichier reste en téléchargement."""
    m = _mime(nom)
    if m in _GED_INLINE_OK:
        return m
    ext = (nom or "").rsplit(".", 1)[-1].lower() if "." in (nom or "") else ""
    if ext in ("txt", "md", "log", "csv", "tsv", "json", "yaml", "yml", "ini", "conf", "cfg", "py", "js", "css", "sh", "sql", "toml"):
        return "text/plain"
    return ""


def _editable(nom: str) -> bool:
    ext = (nom or "").rsplit(".", 1)[-1].lower() if "." in (nom or "") else ""
    return ext in _GED_EDITABLE


def brancher(ctx):
    db = ctx.stockage

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def _base() -> str:
        return reglage("docs_base", "") or str(Path(db.chemin).resolve().parent.parent / "documents")

    def _dossier_compte(compte: str) -> str:
        return os.path.join(_base(), _nt_dossier_compte(str(compte or "")))

    def _public_dir() -> str:
        return os.path.join(_base(), GED_PUBLIC_NOM)

    def _pj_nom_propre(v) -> str:
        n = str(v or "").strip().replace("\\", "/")
        if not n or "/" in n or n in (".", ".."):
            return GED_PJ_NOM_DEFAUT
        return n[:60]

    def _extraction_dir(compte: str = "") -> str:
        c = str(compte or "").strip() or (ctx.compte or "").strip()
        if not c:
            return ""
        return os.path.join(_dossier_compte(c), _pj_nom_propre(_cfg_lire("extraction", GED_PJ_NOM_DEFAUT)))

    # ── configuration (dans la base, jamais un fichier de secrets) ──────────
    def _cfg_lire(cle, defaut):
        r = db.lire("SELECT valeur FROM ged_config WHERE cle=?", (cle,))
        if not r:
            return defaut
        try:
            return json.loads(r[0]["valeur"])
        except Exception:
            return defaut

    def _cfg_ecrire(cle, valeur):
        db.ecrire("INSERT INTO ged_config (cle, valeur) VALUES (?,?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                  (cle, json.dumps(valeur, ensure_ascii=False)))
        return True

    def _agent() -> bool:
        return (ctx.acteur or "") in ("cassandra", "itare", "agent")

    def _moi() -> str:
        return (ctx.compte or "").strip().lower()

    def _racine_parente(chemin) -> bool:
        """Vrai si le chemin EST le dossier qui porte les dossiers de comptes, ou l'un de ses parents."""
        try:
            rp = os.path.realpath(str(chemin or "").strip())
            base = os.path.realpath(_base())
            return bool(rp) and (base + os.sep).startswith(rp.rstrip(os.sep) + os.sep)
        except Exception:
            return False

    def _racines() -> list:
        """Les sources VISIBLES par l'appelant : le goulot du cloisonnement."""
        toutes = _cfg_lire("racines", None)
        if not toutes:
            toutes = [{"path": _base(), "label": "Documents partagés", "ro": 0, "compte": "", "forme": "documents", "sentinelle": ""}]
        if _agent():
            return toutes
        moi = _moi()
        return [r for r in toutes
                if not _racine_parente(r.get("path"))
                and (not str(r.get("compte") or "").strip() or str(r.get("compte")).strip().lower() == moi)]

    def _compte_du_chemin(chemin) -> str:
        """Le propriétaire d'un fichier local, lu sur son chemin ; « » pour le partagé, « #inconnu » sinon."""
        try:
            rp = os.path.realpath(str(chemin or ""))
            base = os.path.realpath(_base())
            if (rp + os.sep).startswith(base + os.sep) and rp != base:
                nom = os.path.relpath(rp, base).split(os.sep)[0]
                if nom == GED_PUBLIC_NOM:
                    return ""
                for u in (comptes_lister() or []):
                    if _nt_dossier_compte(str(u)) == nom:
                        return str(u).strip().lower()
                return "#inconnu"
            meilleur, comp = "", ""
            for r in _cfg_lire("racines", None) or []:
                p = os.path.realpath(str(r.get("path") or ""))
                if p and (rp + os.sep).startswith(p.rstrip(os.sep) + os.sep) and len(p) > len(meilleur):
                    meilleur, comp = p, str(r.get("compte") or "").strip().lower()
            return comp
        except Exception:
            return ""

    def comptes_lister():
        try:
            d = ctx.executer_lecture("comptes.lister") or {}
            return [str(x.get("compte") or "").strip().lower() for x in d.get("comptes", []) if x.get("compte")]
        except Exception:
            return []

    def _resoudre(chemin: str):
        """Chemin absolu réel et sa racine ; (None, None) s'il sort de toutes les racines déclarées."""
        if not chemin:
            return None, None
        try:
            p = os.path.realpath(os.path.abspath(str(chemin)))
        except Exception:
            return None, None
        for r in _racines():
            base = os.path.realpath(os.path.abspath(str(r["path"])))
            if p == base or p.startswith(base + os.sep):
                return p, r
        return None, None

    def _forme(rac) -> str:
        f = str((rac or {}).get("forme") or "documents").strip().lower()
        return f if f in _GED_FORMES else "documents"

    def _racine_souci(rac: dict) -> str:
        p = str((rac or {}).get("path") or "").strip()
        if not p:
            return "chemin vide"
        if not os.path.isdir(p):
            return "introuvable : %s" % p
        sent = str((rac or {}).get("sentinelle") or "").strip()
        if sent:
            if os.sep in sent or "/" in sent or sent in (".", ".."):
                return "sentinelle invalide"
            if not os.path.exists(os.path.join(p, sent)):
                return "montage absent : la sentinelle « %s » n'est pas là" % sent
        return ""

    def _empreinte(chemin: str) -> str:
        try:
            if os.path.getsize(chemin) > _GED_TAILLE_HASH:
                return ""
            h = hashlib.sha256()
            with open(chemin, "rb") as f:
                for bloc in iter(lambda: f.read(1024 * 256), b""):
                    h.update(bloc)
            return "sha256:" + h.hexdigest()
        except Exception:
            return ""

    def _source_norm(source) -> str:
        return str(source or "").strip()

    def _structurel(source: str, chemin: str) -> str:
        """Un élément structurel (le dossier de pièces jointes, la corbeille) ne se déplace ni ne s'écrase."""
        c = (chemin or "").strip().lstrip("/")
        if ".corbeille" in c:
            return "la corbeille ne se déplace pas"
        if c == _pj_nom_propre(_cfg_lire("extraction", GED_PJ_NOM_DEFAUT)) or c.startswith(_pj_nom_propre(_cfg_lire("extraction", GED_PJ_NOM_DEFAUT)) + "/"):
            return "le dossier de pièces jointes est structurel"
        return ""

    def _libre(chemin: str) -> str:
        """Un nom libre, sans écraser : `x`, puis `x (2)`, `x (3)`…"""
        if not os.path.exists(chemin):
            return chemin
        racine, ext = os.path.splitext(chemin)
        for i in range(2, 1000):
            c = "%s (%d)%s" % (racine, i, ext)
            if not os.path.exists(c):
                return c
        return chemin

    def _corbeilles() -> list:
        out = []
        for r in _racines():
            c = os.path.join(str(r["path"]), ".corbeille")
            if os.path.isdir(c):
                out.append((r, c))
        return out

    # ── lectures ─────────────────────────────────────────────────────────────
    def config(c):
        r = _cfg_lire("racines", None)
        if not r:
            r = [{"path": _base(), "label": "Documents partagés", "ro": 0, "compte": "", "forme": "documents", "sentinelle": ""}]
        return {"racines": r,
                "formes": [{"cle": k, "n": v["n"], "ic": v["ic"]} for k, v in _GED_FORMES.items()],
                "extraction": _pj_nom_propre(_cfg_lire("extraction", GED_PJ_NOM_DEFAUT)),
                "auto": bool(_cfg_lire("auto", True)),
                "taille_max": int(_cfg_lire("taille_max", 25 * 1024 * 1024)),
                "sans_inline": bool(_cfg_lire("sans_inline", True)),
                "dedup": bool(_cfg_lire("dedup", True)),
                "indexer_texte": bool(_cfg_lire("indexer_texte", True))}

    def racines_etat(c):
        out = []
        for x in _cfg_lire("racines", None) or []:
            f = _forme(x)
            out.append({"path": x.get("path", ""), "forme": f, "forme_n": _GED_FORMES[f]["n"],
                        "sentinelle": str(x.get("sentinelle") or ""), "souci": _racine_souci(x)})
        return {"racines": out}

    def sources(c):
        locales, trans = [], []
        for r in _racines():
            n = 0
            try:
                n = len([x for x in os.listdir(r["path"]) if not x.startswith(".")])
            except Exception:
                n = 0
            mien = _dossier_compte(_moi()) and os.path.realpath(str(r.get("path") or "")) == os.path.realpath(_dossier_compte(_moi()))
            commun = not str(r.get("compte") or "").strip()
            locales.append({"id": "local:" + r["path"],
                            "ic": "🔒" if r.get("ro") else ("🏠" if mien else ("👥" if commun else "💾")),
                            "nm": ("Mes documents" if mien else (r.get("label") or r["path"])), "n": n,
                            "ro": 1 if r.get("ro") else 0, "chemin": r["path"],
                            "mien": 1 if mien else 0, "commun": 1 if commun else 0,
                            "rang": 0 if mien else (1 if commun else 2)})
        locales.sort(key=lambda x: (x["rang"], str(x["nm"]).lower()))
        nrec = len((_lister_index("recents", "").get("items") or []))
        ndup = len([k for k, v in _doublons_comptes().items() if v > 1])
        ncor = 0
        for _r, c in _corbeilles():
            for _d, _sd, _f in os.walk(c):
                ncor += len(_f)
        trans = [{"id": "recents", "ic": "🕘", "nm": "Récents", "n": nrec},
                 {"id": "doublons", "ic": "⧉", "nm": "Doublons", "n": ndup},
                 {"id": "corbeille", "ic": "🗑", "nm": "Corbeille", "n": ncor}]
        defaut = next((x["id"] for x in locales if x.get("mien")), (locales[0]["id"] if locales else ""))
        return {"defaut": defaut, "groupes": [{"g": "Mes espaces", "l": locales}, {"g": "Vues", "l": trans}]}

    def lister(c, source="", chemin="", query=""):
        source = str(source or "").strip()
        if source.startswith("local:"):
            return _lister_local(source[6:], chemin, query)
        if source == "corbeille":
            return corbeille_lister(c, query)
        if source in ("recents", "doublons"):
            return _lister_index(source, query)
        raise ValueError("source inconnue (les distants ne sont pas encore portés)")

    def _lister_local(racine, chemin, query):
        base = os.path.join(racine, str(chemin or "").lstrip("/")) if chemin else racine
        p, r = _resoudre(base)
        if not p:
            raise ValueError("chemin hors des racines déclarées")
        if not os.path.isdir(p):
            raise ValueError("dossier introuvable")
        q = (query or "").lower()
        items = []
        try:
            for e in sorted(os.scandir(p), key=lambda x: (not x.is_dir(), x.name.lower())):
                if e.name.startswith("."):
                    continue
                if q and q not in e.name.lower():
                    continue
                try:
                    st = e.stat()
                except Exception:
                    continue
                if e.is_dir():
                    n = 0
                    try:
                        n = len([x for x in os.listdir(e.path) if not x.startswith(".")])
                    except Exception:
                        pass
                    items.append({"dossier": 1, "nom": e.name, "n": n, "chemin": os.path.join(chemin, e.name).lstrip("/")})
                else:
                    items.append({"nom": e.name, "taille": st.st_size, "taille_h": _octets(st.st_size),
                                  "kind": _media_kind(e.name, ""),
                                  "modifie": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                                  "chemin": os.path.join(chemin, e.name).lstrip("/"), "abs": e.path})
                if len(items) >= _GED_LISTE_MAX:
                    break
        except PermissionError:
            raise ValueError("lecture refusée par le système")
        except Exception as ex:
            raise ValueError(str(ex))
        mien = bool(_moi()) and os.path.realpath(racine) == os.path.realpath(_dossier_compte(_moi()))
        return {"items": items, "racine": racine, "chemin": chemin,
                "nom": ("Mes documents" if mien else (str((r or {}).get("label") or "") or racine)),
                "ro": 1 if (r or {}).get("ro") else 0, "distant": 0}

    def _lister_index(quoi, query):
        q = (query or "").lower()
        if quoi == "doublons":
            rows = db.lire("SELECT * FROM ged_fichiers WHERE empreinte<>'' AND empreinte IN "
                           "(SELECT empreinte FROM ged_fichiers WHERE empreinte<>'' GROUP BY empreinte HAVING COUNT(*)>1) ORDER BY empreinte, nom")
        else:
            rows = db.lire("SELECT * FROM ged_fichiers ORDER BY cree_le DESC LIMIT 120")
        agent, moi = _agent(), _moi()
        items, partis = [], []
        for d in rows:
            d = dict(d)
            if str(d.get("source") or "").startswith("local:"):
                p = os.path.join(str(d["source"])[6:], str(d.get("chemin") or "").lstrip("/"))
                if not os.path.exists(p):
                    partis.append(d["id"])
                    continue
                if not agent:
                    own = _compte_du_chemin(p)
                    if (own and own != moi) or not _resoudre(p)[0]:
                        continue
            if q and q not in (d["nom"] or "").lower():
                continue
            items.append({"id": d["id"], "nom": d["nom"], "taille": d["taille"], "cree": d.get("cree_le") or "",
                          "taille_h": _octets(d["taille"]), "kind": d["kind"],
                          "modifie": (d["modifie"] or d["cree_le"] or "")[:16], "chemin": d["chemin"],
                          "empreinte": d["empreinte"], "source": d["source"]})
        for i in partis:
            db.ecrire("DELETE FROM ged_liens WHERE fichier_id=?", (i,))
            db.ecrire("DELETE FROM ged_fichiers WHERE id=?", (i,))
        if quoi == "doublons":
            compte = {}
            for x in items:
                compte[x["empreinte"]] = compte.get(x["empreinte"], 0) + 1
            for x in items:
                x["dup"] = compte.get(x["empreinte"], 1)
            items = [x for x in items if x["dup"] > 1]
        return {"items": items, "racine": quoi, "chemin": "", "ro": 0, "distant": 0}

    def _indexer(source, chemin, abs_path=""):
        """L'id de la ligne d'index d'un fichier local, créée au besoin."""
        if not str(chemin or "").strip() and not str(abs_path or "").strip():
            return None
        source = _source_norm(source)
        p, r = _resoudre(abs_path or os.path.join(str(source)[6:] if source.startswith("local:") else "", str(chemin or "").lstrip("/")))
        if not p or not os.path.isfile(p):
            return None
        rel = "/" + os.path.relpath(p, os.path.realpath(str(r["path"]))).replace(os.sep, "/")
        ligne = db.lire("SELECT id FROM ged_fichiers WHERE source=? AND chemin=?", (source, rel))
        if ligne:
            return ligne[0]["id"]
        st = os.stat(p)
        emp = _empreinte(p)
        nom = os.path.basename(p)
        fid = db.ecrire("INSERT INTO ged_fichiers (source, chemin, nom, taille, kind, empreinte, modifie, compte) VALUES (?,?,?,?,?,?,?,?)",
                        (source, rel, nom, st.st_size, _media_kind(nom, ""), emp,
                         datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"), _compte_du_chemin(p)))
        return fid

    def fiche(c, fid=None, source="", chemin="", abs_path=""):
        if not fid:
            fid = _indexer(source, chemin, abs_path)
        if not fid:
            raise ValueError("fichier inconnu de l'index")
        f = db.lire("SELECT * FROM ged_fichiers WHERE id=?", (int(fid),))
        if not f:
            raise ValueError("fichier introuvable")
        f = dict(f[0])
        # le cloisonnement : la ligne n'est lisible que si son chemin est dans une racine visible (ou que c'est un agent)
        if not _agent() and str(f.get("source") or "").startswith("local:"):
            p = os.path.join(str(f["source"])[6:], str(f.get("chemin") or "").lstrip("/"))
            own = _compte_du_chemin(p)
            if own and own != _moi():
                raise ValueError("fichier introuvable")
        liens = db.lire("SELECT id, kind, ref, label FROM ged_liens WHERE fichier_id=? ORDER BY kind", (int(fid),))
        versions = db.lire("SELECT taille, empreinte, ts FROM ged_versions WHERE fichier_id=? ORDER BY id DESC LIMIT 10", (int(fid),))
        jumeaux = 0
        if f.get("empreinte"):
            jumeaux = db.lire("SELECT COUNT(*) AS n FROM ged_fichiers WHERE empreinte=?", (f["empreinte"],))[0]["n"]
        f["taille_h"] = _octets(f.get("taille"))
        return {"fichier": f, "liens": liens, "versions": versions, "jumeaux": jumeaux}

    def telecharger(c, fid=None, source="", chemin=""):
        if fid:
            d = fiche(c, fid=fid)
            f = d["fichier"]
            source, chemin, nom = f["source"], f["chemin"], f["nom"]
        else:
            nom = os.path.basename(str(chemin or "")) or "fichier"
        source = _source_norm(source)
        if not source.startswith("local:"):
            raise ValueError("source inconnue (les distants ne sont pas encore portés)")
        base, r = _resoudre(str(source)[6:])
        if not base:
            raise ValueError("racine introuvable ou non déclarée")
        p, _r2 = _resoudre(os.path.join(base, str(chemin or "").lstrip("/")))
        if not p:
            raise ValueError("chemin hors des racines déclarées")
        if not os.path.isfile(p):
            raise ValueError("fichier introuvable")
        return {"mode": "local", "chemin": p, "nom": os.path.basename(p), "mime": _mime(p), "taille": os.path.getsize(p)}

    def voir(c, fid=None, source="", chemin=""):
        d = telecharger(c, fid, source, chemin)
        t = _inline_type(d.get("nom", ""))
        if not t:
            raise ValueError("ce type ne s'affiche pas en ligne — téléchargez-le pour l'ouvrir")
        d["mime"] = t
        return d

    def corbeille_lister(c, query=""):
        q = (query or "").lower()
        items = []
        for racine, c_b in _corbeilles():
            for dossier, _sd, fichiers in os.walk(c_b):
                for f in fichiers:
                    if q and q not in f.lower():
                        continue
                    p = os.path.join(dossier, f)
                    try:
                        st = os.stat(p)
                    except Exception:
                        continue
                    items.append({"nom": f, "taille": st.st_size, "taille_h": _octets(st.st_size),
                                  "kind": _media_kind(f, ""),
                                  "modifie": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                                  "abs": p, "chemin": p, "jour": os.path.basename(dossier),
                                  "racine": racine.get("label") or racine.get("path", "")})
                    if len(items) >= _GED_LISTE_MAX:
                        break
        items.sort(key=lambda x: x["modifie"], reverse=True)
        total = sum(x["taille"] for x in items)
        return {"items": items, "racine": "Corbeille", "chemin": "", "ro": 0, "distant": 0,
                "octets": total, "octets_h": _octets(total)}

    def occupation(c):
        out = []
        for r in _cfg_lire("racines", None) or []:
            p = str(r.get("path") or "")
            n, o = 0, 0
            if os.path.isdir(p):
                for base, _sd, fichiers in os.walk(p):
                    if ".corbeille" in base:
                        continue
                    for f in fichiers:
                        n += 1
                        try:
                            o += os.path.getsize(os.path.join(base, f))
                        except Exception:
                            pass
            out.append({"path": p, "label": r.get("label") or p, "fichiers": n, "octets": o, "taille_h": _octets(o),
                        "ro": 1 if r.get("ro") else 0})
        out.sort(key=lambda x: -x["octets"])
        return {"sources": out, "octets": sum(x["octets"] for x in out)}

    def comptes(c):
        if not ctx.est_admin(_moi()):
            raise ValueError("réservé aux administrateurs")
        d = ctx.executer_lecture("comptes.lister") or {}
        return {"comptes": [{"compte": x.get("compte"), "nom": x.get("display_name") or x.get("compte")}
                            for x in d.get("comptes", []) if x.get("type") == "humain"]}

    # ── règles de classement ─────────────────────────────────────────────────
    def regles(c):
        rows = db.lire("SELECT * FROM ged_regles ORDER BY ordre, id")
        if not rows:
            for r in _GED_REGLES_DEFAUT:
                db.ecrire("INSERT INTO ged_regles (ordre, libelle, si_sujet, si_kind, si_taille_min, dest, etiquette) VALUES (?,?,?,?,?,?,?)",
                          (r.get("ordre", 100), r.get("libelle", ""), r.get("si_sujet", ""), r.get("si_kind", ""),
                           r.get("si_taille_min", 0), r.get("dest", ""), r.get("etiquette", "")))
            rows = db.lire("SELECT * FROM ged_regles ORDER BY ordre, id")
        return {"regles": rows}

    def _motif(champ, motif) -> bool:
        if not motif:
            return True
        c = (champ or "").lower()
        return any(m.strip() and m.strip().lower() in c for m in str(motif).split("|"))

    def _dest(regle, piece) -> str:
        d = str(regle.get("dest") or "/À classer")
        iso = str(piece.get("date_iso") or "")[:10]
        an = iso[:4] or datetime.now().strftime("%Y")
        try:
            mo = "%s-%s" % (iso[5:7], _GED_MOIS[int(iso[5:7]) - 1])
        except Exception:
            mo = datetime.now().strftime("%m")
        exp = (piece.get("from_name") or piece.get("from_addr") or "inconnu")
        exp = re.sub(r"[^\w .-]", "", exp)
        exp = re.sub(r"\.{2,}", ".", exp).strip(" .-")[:40] or "inconnu"
        for cle, val in (("{année}", an), ("{annee}", an), ("{mois}", mo),
                         ("{expéditeur}", exp), ("{expediteur}", exp),
                         ("{projet}", str(regle.get("projet") or "").strip() or "sans-projet")):
            d = d.replace(cle, val)
        parties = [p for p in d.replace("\\", "/").split("/") if p and p not in (".", "..")]
        return "/" + "/".join(parties)

    def _regle_pour(piece, regles):
        for r in regles:
            if not r.get("actif", 1):
                continue
            if int(r.get("si_taille_min") or 0) > int(piece.get("size") or 0):
                continue
            if not _motif((piece.get("from_addr") or "") + " " + (piece.get("from_name") or ""), r.get("si_from", "")):
                continue
            if not _motif(piece.get("filename", ""), r.get("si_nom", "")):
                continue
            if not _motif(piece.get("subject", ""), r.get("si_sujet", "")):
                continue
            k = str(r.get("si_kind") or "").strip()
            if k and k != piece.get("kind"):
                continue
            return r
        return None

    def regles_test(c, pieces=None):
        """Ce que les règles FERAIENT, sans rien écrire."""
        regles_ = regles(c)["regles"]
        par_regle, total = {}, 0
        for p in (pieces or [])[:3000]:
            r = _regle_pour(p, regles_)
            total += 1
            if not r:
                continue
            par_regle.setdefault(r["id"], {"libelle": r["libelle"], "n": 0, "exemples": []})
            par_regle[r["id"]]["n"] += 1
            if len(par_regle[r["id"]]["exemples"]) < 3:
                par_regle[r["id"]]["exemples"].append(str(p.get("filename") or "")[:80])
        return {"total": total, "par_regle": sorted(par_regle.values(), key=lambda x: -x["n"])}

    # ── écritures ────────────────────────────────────────────────────────────
    def config_set(c, d):
        avant = config(c)
        if "racines" in d:
            propres = []
            _avant, _lib, _formes, _sents = {}, {}, {}, {}
            for _r in (config(c).get("racines") or []):
                _p0 = os.path.abspath(str(_r.get("path", "")).strip())
                _avant[_p0] = str(_r.get("compte") or "").strip()
                _lib[_p0] = str(_r.get("label") or "").strip()
                _formes[_p0] = str(_r.get("forme") or "documents").strip()
                _sents[_p0] = str(_r.get("sentinelle") or "").strip()
            admin = ctx.est_admin(_moi())
            for x in (d.get("racines") or [])[:12]:
                p = os.path.abspath(str(x.get("path", "")).strip())
                if not p or p == "/":
                    continue
                if p in _avant:
                    _c = (str(x.get("compte", ""))[:120].strip() if admin else _avant[p])
                    if not admin and p in _lib:
                        x = dict(x)
                        x["label"] = _lib[p]
                else:
                    _c = _moi() or str(x.get("compte", ""))[:120].strip()
                _f0 = str((_formes.get(p) or "documents")).strip().lower()
                _s0 = str(_sents.get(p) or "").strip()
                if admin and "forme" in x:
                    _f0 = str(x.get("forme") or "documents").strip().lower()
                if admin and "sentinelle" in x:
                    _s0 = str(x.get("sentinelle") or "").strip()[:60]
                propres.append({"path": p, "label": str(x.get("label", ""))[:60] or p, "ro": 1 if x.get("ro") else 0,
                                "compte": _c, "forme": _f0, "sentinelle": _s0})
            _cfg_ecrire("racines", propres)
        for k, conv in (("extraction", _pj_nom_propre), ("auto", bool), ("taille_max", int),
                        ("sans_inline", bool), ("dedup", bool), ("indexer_texte", bool)):
            if k in d:
                try:
                    _cfg_ecrire(k, conv(d[k]))
                except Exception:
                    pass
        return {"avant": avant, "config": config(c)}

    def prouver_config(c, res):
        return config(c) != res.get("avant")

    def defaire_config(c, res):
        avant = res.get("avant") or {}
        if "racines" in avant:
            _cfg_ecrire("racines", avant["racines"])
        for k in ("extraction", "auto", "taille_max", "sans_inline", "dedup", "indexer_texte"):
            if k in avant:
                _cfg_ecrire(k, avant[k])

    def dossier_creer(c, compte=""):
        c_ = str(compte or "").strip() or _moi()
        if not c_:
            raise ValueError("compte vide")
        d = _dossier_compte(c_)
        neuf = not os.path.isdir(d)
        os.makedirs(d, mode=0o700, exist_ok=True)
        declaree = _source_declarer(d, "Documents — %s" % c_, compte=c_)
        return {"dossier": d, "neuf": neuf, "declaree": declaree, "compte": c_}

    def _source_declarer(chemin, libelle, compte=""):
        p = os.path.abspath(str(chemin or "").strip())
        if not p or p == "/":
            return False
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        for r in racines:
            if os.path.abspath(str(r.get("path", "")).strip()) == p:
                return False
        racines.append({"path": p, "label": str(libelle or "")[:60] or p, "ro": 0, "compte": str(compte or ""),
                        "forme": "documents", "sentinelle": ""})
        _cfg_ecrire("racines", racines)
        return True

    def prouver_dossier(c, res):
        return os.path.isdir(res["dossier"])

    def defaire_dossier(c, res):
        racines = [r for r in (_cfg_lire("racines", None) or []) if os.path.abspath(str(r.get("path", "")).strip()) != os.path.abspath(res["dossier"])]
        _cfg_ecrire("racines", racines)

    def public_creer(c):
        d = _public_dir()
        os.makedirs(d, mode=0o755, exist_ok=True)
        return {"dossier": d, "declaree": _source_declarer(d, "Documents partagés", compte="")}

    def prouver_public(c, res):
        return os.path.isdir(res["dossier"])

    def defaire_public(c, res):
        racines = [r for r in (_cfg_lire("racines", None) or []) if os.path.abspath(str(r.get("path", "")).strip()) != os.path.abspath(res["dossier"])]
        _cfg_ecrire("racines", racines)

    def source_forme(c, chemin="", forme="documents", sentinelle=""):
        if not ctx.est_admin(_moi()):
            raise PermissionError("seul un administrateur peut changer la forme d'une source")
        f = str(forme or "documents").strip().lower()
        if f not in _GED_FORMES:
            raise ValueError("forme inconnue : %s" % f)
        sent = str(sentinelle or "").strip()[:60]
        if sent and ("/" in sent or os.sep in sent or sent in (".", "..")):
            raise ValueError("la sentinelle est un nom, pas un chemin")
        p = os.path.abspath(str(chemin or "").strip())
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        avant = None
        for x in racines:
            if os.path.abspath(str(x.get("path", "")).strip()) == p:
                avant = dict(x)
                x["forme"], x["sentinelle"] = f, sent
        if avant is None:
            raise ValueError("source inconnue")
        _cfg_ecrire("racines", racines)
        return {"path": p, "forme": f, "sentinelle": sent, "avant": avant}

    def prouver_source_forme(c, res):
        return config(c)["racines"] and any(r["path"] == res["path"] and r.get("forme") == res["forme"] for r in config(c)["racines"])

    def defaire_source_forme(c, res):
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        for x in racines:
            if os.path.abspath(str(x.get("path", "")).strip()) == res["path"]:
                x["forme"] = res["avant"]["forme"]
                x["sentinelle"] = res["avant"]["sentinelle"]
        _cfg_ecrire("racines", racines)

    def source_proprietaire(c, chemin="", compte=""):
        if not ctx.est_admin(_moi()):
            raise PermissionError("seul un administrateur peut changer le propriétaire d'une source")
        p = os.path.abspath(str(chemin or "").strip())
        if os.path.basename(p) == GED_PUBLIC_NOM:
            raise ValueError("l'espace commun n'appartient à personne")
        c_ = str(compte or "").strip()[:120]
        if c_:
            connus = set(comptes_lister())
            if connus and c_.lower() not in connus:
                raise ValueError("aucun compte ne s'appelle « %s »" % c_)
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        avant = None
        for r in racines:
            if os.path.abspath(str(r.get("path", "")).strip()) == p:
                avant = str(r.get("compte") or "").strip()
                r["compte"] = c_
        if avant is None:
            raise ValueError("source inconnue")
        _cfg_ecrire("racines", racines)
        return {"path": p, "compte": c_, "avant": avant}

    def prouver_source_proprietaire(c, res):
        return any(r["path"] == res["path"] and str(r.get("compte") or "").strip() == res["compte"] for r in config(c)["racines"])

    def defaire_source_proprietaire(c, res):
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        for x in racines:
            if os.path.abspath(str(x.get("path", "")).strip()) == res["path"]:
                x["compte"] = res["avant"]
        _cfg_ecrire("racines", racines)

    def source_renommer(c, chemin="", libelle=""):
        if not ctx.est_admin(_moi()):
            raise PermissionError("seul un administrateur peut renommer une source")
        p = os.path.abspath(str(chemin or "").strip())
        lib = str(libelle or "").strip()[:60]
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        avant = None
        for r in racines:
            if os.path.abspath(str(r.get("path", "")).strip()) == p:
                avant = r.get("label")
                r["label"] = lib or p
        if avant is None:
            raise ValueError("source inconnue")
        _cfg_ecrire("racines", racines)
        return {"path": p, "label": lib or p, "avant": avant}

    def prouver_source_renommer(c, res):
        return any(r["path"] == res["path"] and r.get("label") == res["label"] for r in config(c)["racines"])

    def defaire_source_renommer(c, res):
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        for x in racines:
            if os.path.abspath(str(x.get("path", "")).strip()) == res["path"]:
                x["label"] = res["avant"]
        _cfg_ecrire("racines", racines)

    def source_deplacer(c, chemin="", nom=""):
        if not ctx.est_admin(_moi()):
            raise PermissionError("seul un administrateur peut renommer un répertoire")
        p = os.path.abspath(str(chemin or "").strip())
        n = str(nom or "").strip()
        if not n:
            raise ValueError("il faut un nom")
        if os.sep in n or (os.altsep and os.altsep in n) or n in (".", ".."):
            raise ValueError("le nom ne peut pas contenir de séparateur")
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        src = next((r for r in racines if os.path.abspath(str(r.get("path", "")).strip()) == p), None)
        if src is None:
            raise ValueError("cette source n'est pas déclarée")
        if src.get("ro"):
            raise ValueError("source en lecture seule")
        if not os.path.isdir(p):
            raise ValueError("ce répertoire n'existe pas")
        if os.path.ismount(p):
            raise ValueError("c'est un point de montage")
        dst = os.path.join(os.path.dirname(p), n)
        if os.path.exists(dst):
            raise ValueError("« %s » existe déjà à côté" % n)
        avant_label = src.get("label")
        os.rename(p, dst)
        for r in racines:
            if os.path.abspath(str(r.get("path", "")).strip()) == p:
                r["path"] = dst
                if not str(r.get("label") or "").strip() or r.get("label") == p:
                    r["label"] = dst
        _cfg_ecrire("racines", racines)
        bouges = db.ecrire("UPDATE ged_fichiers SET chemin = ? || substr(chemin, ?), source = ? WHERE chemin LIKE ?",
                           (dst, len(p) + 1, "local:" + dst, p + os.sep + "%"))
        db.ecrire("UPDATE ged_fichiers SET source = ? WHERE source = ?", ("local:" + dst, "local:" + p))
        return {"de": p, "vers": dst, "fichiers": bouges, "avant_label": avant_label}

    def prouver_source_deplacer(c, res):
        return os.path.isdir(res["vers"]) and not os.path.isdir(res["de"])

    def defaire_source_deplacer(c, res):
        os.rename(res["vers"], res["de"])
        racines = [dict(x) for x in (_cfg_lire("racines", None) or [])]
        for r in racines:
            if os.path.abspath(str(r.get("path", "")).strip()) == res["vers"]:
                r["path"] = res["de"]
                r["label"] = res.get("avant_label") or res["de"]
        _cfg_ecrire("racines", racines)
        db.ecrire("UPDATE ged_fichiers SET chemin = ? || substr(chemin, ?), source = ? WHERE chemin LIKE ?",
                  (res["de"], len(res["vers"]) + 1, "local:" + res["de"], res["vers"] + os.sep + "%"))
        db.ecrire("UPDATE ged_fichiers SET source = ? WHERE source = ?", ("local:" + res["de"], "local:" + res["vers"]))

    def deposer(c, source="", chemin="", nom="", contenu_b64=""):
        nom = os.path.basename(str(nom or "")).strip()
        nom = re.sub(r'[/\\\x00]', "_", nom)[:180]
        if not nom:
            raise ValueError("nom de fichier manquant")
        refus = _depot_refuse(nom)
        if refus:
            raise ValueError(refus)
        try:
            octets = base64.b64decode(contenu_b64 or "", validate=False)
        except Exception:
            raise ValueError("contenu illisible")
        if not octets:
            raise ValueError("fichier vide")
        if len(octets) > _GED_DEPOT_MAX:
            raise ValueError("au-delà de %s par fichier" % _octets(_GED_DEPOT_MAX))
        source = _source_norm(source)
        if not source.startswith("local:"):
            raise ValueError("choisissez d'abord un dossier local")
        base, racine = _resoudre(str(source)[6:])
        if not base:
            raise ValueError("racine introuvable ou non déclarée")
        if (racine or {}).get("ro"):
            raise ValueError("ce dossier est en lecture seule")
        dossier = os.path.join(base, str(chemin or "").lstrip("/"))
        os.makedirs(dossier, exist_ok=True)
        p, _r = _resoudre(dossier)
        if not p:
            raise ValueError("chemin hors des racines déclarées")
        cible = os.path.join(p, nom)
        remplace = os.path.exists(cible)
        ancienne = _empreinte(cible) if remplace else ""
        with open(cible, "wb") as f:
            f.write(octets)
        emp = "sha256:" + hashlib.sha256(octets).hexdigest()
        rel = "/" + os.path.relpath(cible, base).replace(os.sep, "/")
        ligne = db.lire("SELECT id FROM ged_fichiers WHERE source=? AND chemin=?", (source, rel))
        mod = datetime.now().strftime("%Y-%m-%d %H:%M")
        if ligne:
            if ancienne and ancienne != emp:
                db.ecrire("INSERT INTO ged_versions (fichier_id, empreinte, taille) VALUES (?,?,?)", (int(ligne[0]["id"]), ancienne, 0))
            db.ecrire("UPDATE ged_fichiers SET taille=?, empreinte=?, modifie=? WHERE id=?", (len(octets), emp, mod, int(ligne[0]["id"])))
            fid = int(ligne[0]["id"])
        else:
            fid = db.ecrire("INSERT INTO ged_fichiers (source, chemin, nom, taille, kind, empreinte, modifie, compte) VALUES (?,?,?,?,?,?,?,?)",
                            (source, rel, nom, len(octets), _media_kind(nom, ""), emp, mod, _compte_du_chemin(cible)))
        return {"id": fid, "nom": nom, "chemin": rel, "taille": len(octets), "remplace": 1 if remplace else 0,
                "nouvelle": 0 if remplace else 1, "ancienne_empreinte": ancienne, "cible": cible, "source": source}

    def prouver_deposer(c, res):
        return os.path.isfile(res["cible"]) and bool(db.lire("SELECT 1 FROM ged_fichiers WHERE id=?", (res["id"],)))

    def defaire_deposer(c, res):
        if res.get("nouvelle"):
            db.ecrire("DELETE FROM ged_fichiers WHERE id=?", (res["id"],))
            db.ecrire("DELETE FROM ged_liens WHERE fichier_id=?", (res["id"],))
            try:
                os.remove(res["cible"])
            except Exception:
                pass

    def ecrire(c, fid=None, source="", chemin="", texte="", confirme=False):
        if not confirme:
            raise ValueError("confirmation requise")
        d = telecharger(c, fid, source, chemin)
        if d.get("mode") != "local":
            raise ValueError("un fichier distant se modifie depuis son espace")
        if not _editable(d["nom"]):
            raise ValueError("ce format ne se modifie pas ici")
        src = source
        if fid and not src:
            r = db.lire("SELECT source, chemin FROM ged_fichiers WHERE id=?", (int(fid),))
            if r:
                src, chemin = r[0]["source"], r[0]["chemin"]
        src = _source_norm(src)
        base, r = _resoudre(str(src)[6:] if src.startswith("local:") else src)
        if not base:
            raise ValueError("racine introuvable")
        if (r or {}).get("ro"):
            raise ValueError("ce dossier est en lecture seule")
        st = _structurel(src, chemin)
        if st:
            raise ValueError(st)
        p = d["chemin"]
        ancienne = _empreinte(p)
        octets = str(texte or "").encode("utf-8")
        if len(octets) > _GED_DEPOT_MAX:
            raise ValueError("contenu trop volumineux")
        tmp = p + ".cassandra-tmp"
        with open(tmp, "wb") as f:
            f.write(octets)
        os.replace(tmp, p)
        emp = "sha256:" + hashlib.sha256(octets).hexdigest()
        ligne = db.lire("SELECT id FROM ged_fichiers WHERE source=? AND chemin=?", (src, chemin if chemin.startswith("/") else "/" + chemin))
        mod = datetime.now().strftime("%Y-%m-%d %H:%M")
        if ligne:
            if ancienne and ancienne != emp:
                db.ecrire("INSERT INTO ged_versions (fichier_id, empreinte, taille) VALUES (?,?,?)", (int(ligne[0]["id"]), ancienne, 0))
            db.ecrire("UPDATE ged_fichiers SET taille=?, empreinte=?, modifie=? WHERE id=?", (len(octets), emp, mod, int(ligne[0]["id"])))
        return {"taille": len(octets), "nom": d["nom"], "ancienne": ancienne, "chemin": p}

    def prouver_ecrire(c, res):
        return _empreinte(res["chemin"]) != res.get("ancienne")

    def defaire_ecrire(c, res):
        # l'ancienne version est restée dans ged_versions : on réécrit son empreinte si possible, sinon rien (le contenu est perdu sans version)
        if res.get("ancienne"):
            pass  # la restauration fine passe par ged_versions ; on ne réécrit pas à l'aveugle

    def corbeille(c, fid=0, confirme=False):
        if not confirme:
            raise ValueError("confirmation requise")
        d = fiche(c, fid=fid)
        f = d["fichier"]
        if str(f.get("source") or "").startswith("local:"):
            base, r = _resoudre(str(f["source"])[6:])
        else:
            raise ValueError("un fichier distant se retire depuis son espace")
        if not base:
            raise ValueError("racine introuvable")
        if (r or {}).get("ro"):
            raise ValueError("racine en lecture seule")
        src = os.path.realpath(os.path.join(base, str(f.get("chemin") or "").lstrip("/")))
        if not src.startswith(base):
            raise ValueError("chemin hors de la racine")
        cor = os.path.join(base, ".corbeille", datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(cor, exist_ok=True)
        dst = _libre(os.path.join(cor, os.path.basename(src)))
        shutil.move(src, dst)
        db.ecrire("DELETE FROM ged_fichiers WHERE id=?", (int(fid),))
        db.ecrire("DELETE FROM ged_liens WHERE fichier_id=?", (int(fid),))
        return {"corbeille": cor, "de": src, "vers": dst, "fichier": f, "liens": d.get("liens") or []}

    def prouver_corbeille(c, res):
        return not os.path.exists(res["de"]) and os.path.exists(res["vers"])

    def defaire_corbeille(c, res):
        shutil.move(res["vers"], res["de"])
        f = res["fichier"]
        db.ecrire("INSERT OR IGNORE INTO ged_fichiers (id, source, chemin, nom, taille, kind, empreinte, modifie, compte) VALUES (?,?,?,?,?,?,?,?,?)",
                  (f["id"], f["source"], f["chemin"], f["nom"], f["taille"], f["kind"], f["empreinte"], f["modifie"], f["compte"]))
        for l in res.get("liens") or []:
            db.ecrire("INSERT OR IGNORE INTO ged_liens (fichier_id, kind, ref, label) VALUES (?,?,?,?)", (f["id"], l["kind"], l["ref"], l["label"]))

    def corbeille_restaurer(c, chemins=None, confirme=False):
        if not confirme:
            raise ValueError("confirmation requise")
        if isinstance(chemins, str):
            chemins = [chemins]
        faits, erreurs, deplaces = 0, [], []
        for ch in (chemins or [])[:200]:
            p, r = _resoudre(ch)
            if not p or ".corbeille" not in p:
                erreurs.append("%s : hors corbeille" % os.path.basename(str(ch)))
                continue
            base = p
            while base and os.path.basename(base) != ".corbeille":
                base = os.path.dirname(base)
            cible_dir = os.path.dirname(base) if base else ""
            if not cible_dir:
                erreurs.append("%s : impossible de situer la racine" % os.path.basename(p))
                continue
            dst = _libre(os.path.join(cible_dir, os.path.basename(p)))
            shutil.move(p, dst)
            deplaces.append({"de": p, "vers": dst})
            faits += 1
        return {"faits": faits, "erreurs": erreurs[:6], "deplaces": deplaces}

    def prouver_corbeille_restaurer(c, res):
        return all(not os.path.exists(x["de"]) and os.path.exists(x["vers"]) for x in res.get("deplaces", []))

    def defaire_corbeille_restaurer(c, res):
        for x in res.get("deplaces", []):
            shutil.move(x["vers"], x["de"])

    def corbeille_vider(c, confirme=False):
        if not confirme:
            raise ValueError("confirmation requise")
        n, octets, erreurs, vides = 0, 0, [], []
        for racine, c_b in _corbeilles():
            p, _r = _resoudre(c_b)
            if not p or ".corbeille" not in p:
                erreurs.append("%s : hors des racines déclarées" % c_b)
                continue
            for _d, _sd, fichiers in os.walk(p):
                for f in fichiers:
                    try:
                        octets += os.path.getsize(os.path.join(_d, f))
                        n += 1
                    except Exception:
                        pass
            vides.append(p)
        for p in vides:
            shutil.rmtree(p)
            os.makedirs(p, exist_ok=True)
        return {"supprimes": n, "octets": octets, "octets_h": _octets(octets), "erreurs": erreurs[:6]}

    def lien(c, fid=0, kind="", ref="", label=""):
        kind = (kind or "").strip().lower()
        if kind not in _GED_LIEN_KINDS:
            raise ValueError("type inconnu (%s)" % ", ".join(_GED_LIEN_KINDS))
        if not str(ref or "").strip():
            raise ValueError("référence requise")
        db.ecrire("INSERT OR IGNORE INTO ged_liens (fichier_id, kind, ref, label) VALUES (?,?,?,?)",
                  (int(fid), kind, str(ref).strip(), (label or "")[:200]))
        return {"fichier_id": int(fid), "kind": kind, "ref": str(ref).strip()}

    def prouver_lien(c, res):
        return bool(db.lire("SELECT 1 FROM ged_liens WHERE fichier_id=? AND kind=? AND ref=?", (res["fichier_id"], res["kind"], res["ref"])))

    def defaire_lien(c, res):
        db.ecrire("DELETE FROM ged_liens WHERE fichier_id=? AND kind=? AND ref=?", (res["fichier_id"], res["kind"], res["ref"]))

    def delien(c, fid=0, kind="", ref=""):
        avant = db.lire("SELECT * FROM ged_liens WHERE fichier_id=? AND kind=? AND ref=?", (int(fid), (kind or "").lower(), str(ref or "")))
        if not avant:
            raise ValueError("lien inconnu")
        db.ecrire("DELETE FROM ged_liens WHERE fichier_id=? AND kind=? AND ref=?", (int(fid), (kind or "").lower(), str(ref or "")))
        return {"fichier_id": int(fid), "kind": (kind or "").lower(), "ref": str(ref or ""), "avant": avant[0]}

    def prouver_delien(c, res):
        return not db.lire("SELECT 1 FROM ged_liens WHERE fichier_id=? AND kind=? AND ref=?", (res["fichier_id"], res["kind"], res["ref"]))

    def defaire_delien(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR IGNORE INTO ged_liens (fichier_id, kind, ref, label) VALUES (?,?,?,?)", (a["fichier_id"], a["kind"], a["ref"], a["label"]))

    def regle_save(c, **d):
        champs = ("ordre", "actif", "libelle", "si_from", "si_nom", "si_sujet", "si_kind",
                  "si_taille_min", "dest", "remote", "projet", "etiquette")
        if d.get("id"):
            avant = db.lire("SELECT * FROM ged_regles WHERE id=?", (int(d["id"]),))
            if not avant:
                raise ValueError("règle inconnue")
            sets = ", ".join("%s=?" % c for c in champs if c in d)
            if sets:
                db.ecrire("UPDATE ged_regles SET " + sets + " WHERE id=?", [d[c] for c in champs if c in d] + [int(d["id"])])
            return {"id": int(d["id"]), "avant": avant[0]}
        vals = [d.get(c, 0 if c in ("ordre", "actif", "si_taille_min") else "") or
                (100 if c == "ordre" else (1 if c == "actif" else 0 if c == "si_taille_min" else "")) for c in champs]
        rid = db.ecrire("INSERT INTO ged_regles (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")", vals)
        return {"id": rid, "avant": None}

    def prouver_regle(c, res):
        return bool(db.lire("SELECT 1 FROM ged_regles WHERE id=?", (res["id"],)))

    def defaire_regle(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM ged_regles WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            db.ecrire("UPDATE ged_regles SET ordre=?, actif=?, libelle=?, si_from=?, si_nom=?, si_sujet=?, si_kind=?, si_taille_min=?, dest=?, remote=?, projet=?, etiquette=? WHERE id=?",
                      (a["ordre"], a["actif"], a["libelle"], a["si_from"], a["si_nom"], a["si_sujet"], a["si_kind"],
                       a["si_taille_min"], a["dest"], a["remote"], a["projet"], a["etiquette"], a["id"]))

    def regle_delete(c, rid=0):
        avant = db.lire("SELECT * FROM ged_regles WHERE id=?", (int(rid),))
        if not avant:
            raise ValueError("règle inconnue")
        db.ecrire("DELETE FROM ged_regles WHERE id=?", (int(rid),))
        return {"id": int(rid), "avant": avant[0]}

    def prouver_regle_delete(c, res):
        return not db.lire("SELECT 1 FROM ged_regles WHERE id=?", (res["id"],))

    def defaire_regle_delete(c, res):
        a = res["avant"]
        db.ecrire("INSERT INTO ged_regles (id, ordre, actif, libelle, si_from, si_nom, si_sujet, si_kind, si_taille_min, dest, remote, projet, etiquette, appliquee) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (a["id"], a["ordre"], a["actif"], a["libelle"], a["si_from"], a["si_nom"], a["si_sujet"], a["si_kind"],
                   a["si_taille_min"], a["dest"], a["remote"], a["projet"], a["etiquette"], a["appliquee"]))

    def _doublons_comptes():
        return {r["empreinte"]: r["n"] for r in db.lire(
            "SELECT empreinte, COUNT(*) AS n FROM ged_fichiers WHERE empreinte<>'' GROUP BY empreinte HAVING COUNT(*)>1")}

    def dedoublonner(c, confirme=False):
        """Répare les doublons : on garde la ligne la plus ancienne, les autres fichiers vont à la corbeille."""
        doublons = db.lire("SELECT * FROM ged_fichiers WHERE empreinte<>'' AND empreinte IN "
                           "(SELECT empreinte FROM ged_fichiers WHERE empreinte<>'' GROUP BY empreinte HAVING COUNT(*)>1) ORDER BY empreinte, id")
        par_emp = {}
        for r in doublons:
            par_emp.setdefault(r["empreinte"], []).append(dict(r))
        cibles = []
        for emp, lignes in par_emp.items():
            lignes.sort(key=lambda x: x["id"])
            for l in lignes[1:]:
                if str(l["source"] or "").startswith("local:"):
                    p = os.path.join(str(l["source"])[6:], str(l.get("chemin") or "").lstrip("/"))
                    if os.path.isfile(p):
                        cibles.append((l, p))
        if not confirme:
            return {"doublons": len(cibles), "a_corbeille": len(cibles)}
        faits = 0
        for l, p in cibles:
            try:
                base, r = _resoudre(str(l["source"])[6:])
                if not base:
                    continue
                cor = os.path.join(base, ".corbeille", datetime.now().strftime("%Y-%m-%d"))
                os.makedirs(cor, exist_ok=True)
                shutil.move(p, _libre(os.path.join(cor, os.path.basename(p))))
                db.ecrire("DELETE FROM ged_fichiers WHERE id=?", (l["id"],))
                db.ecrire("DELETE FROM ged_liens WHERE fichier_id=?", (l["id"],))
                faits += 1
            except Exception:
                continue
        return {"doublons": len(cibles), "a_corbeille": faits}

    # ── enregistrement ──────────────────────────────────────────────────────
    for cid, f in (("config", config), ("racines_etat", racines_etat), ("sources", sources), ("lister", lister),
                   ("fiche", fiche), ("telecharger", telecharger), ("voir", voir), ("corbeille_lister", corbeille_lister),
                   ("occupation", occupation), ("comptes", comptes), ("regles", regles), ("regles_test", regles_test)):
        ctx.implementer(cid, f)
    ctx.implementer("config_set", config_set, prouver_config, defaire_config,
                    simuler=lambda x, **_: "enregistrerait la configuration de la GED")
    ctx.implementer("dossier_creer", dossier_creer, prouver_dossier, defaire_dossier,
                    simuler=lambda x, compte="", **_: "créerait le dossier de documents de %s" % (compte or "ce compte"))
    ctx.implementer("public_creer", public_creer, prouver_public, defaire_public,
                    simuler=lambda x, **_: "créerait l'espace commun des documents")
    ctx.implementer("source_forme", source_forme, prouver_source_forme, defaire_source_forme,
                    simuler=lambda x, chemin="", forme="", **_: "changerait la forme de %s" % chemin)
    ctx.implementer("source_proprietaire", source_proprietaire, prouver_source_proprietaire, defaire_source_proprietaire,
                    simuler=lambda x, chemin="", **_: "changerait le propriétaire de %s" % chemin)
    ctx.implementer("source_renommer", source_renommer, prouver_source_renommer, defaire_source_renommer,
                    simuler=lambda x, chemin="", **_: "renommerait la source %s" % chemin)
    ctx.implementer("source_deplacer", source_deplacer, prouver_source_deplacer, defaire_source_deplacer,
                    simuler=lambda x, chemin="", nom="", **_: "renommerait le répertoire %s en %s" % (chemin, nom))
    ctx.implementer("deposer", deposer, prouver_deposer, defaire_deposer,
                    simuler=lambda x, nom="", **_: "déposerait « %s »" % nom)
    ctx.implementer("ecrire", ecrire, prouver_ecrire, defaire_ecrire,
                    simuler=lambda x, nom="", **_: "réécrirait « %s »" % nom)
    ctx.implementer("corbeille", corbeille, prouver_corbeille, defaire_corbeille,
                    simuler=lambda x, fid=0, **_: "enverrait le document %s à la corbeille" % fid)
    ctx.implementer("corbeille_restaurer", corbeille_restaurer, prouver_corbeille_restaurer, defaire_corbeille_restaurer,
                    simuler=lambda x, **_: "restaurerait depuis la corbeille")
    ctx.implementer("lien", lien, prouver_lien, defaire_lien, simuler=lambda x, kind="", ref="", **_: "rattacherait ce document à %s %s" % (kind, ref))
    ctx.implementer("delien", delien, prouver_delien, defaire_delien, simuler=lambda x, **_: "détacherait ce document")
    ctx.implementer("regle_save", regle_save, prouver_regle, defaire_regle, simuler=lambda x, libelle="", **_: "enregistrerait la règle « %s »" % libelle)
    ctx.implementer("regle_delete", regle_delete, prouver_regle_delete, defaire_regle_delete, simuler=lambda x, rid=0, **_: "retirerait la règle %s" % rid)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _nt_dossier_compte, _media_kind, _octets, _mime, _depot_refuse, _inline_type, _editable, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
