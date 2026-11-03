# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le dossier de fichiers d'un projet
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : projets
# ZONE       : CN
# VERSION CN : 0.2.0  #7ca4db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le dossier de fichiers d'un projet.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=7ca4db ▼▼▼
"""Le dossier de fichiers d'un projet (le « coffre » de l'Atelier V18), porté pour les dépôts de CE serveur.

Règles gardées de la V18, voulues par Drisse :
  - rien ne sort du dossier du projet (un chemin qui s'en échappe, par `..` ou par un lien, est refusé) ;
  - l'état trouvé est TOUJOURS rangé en version avant d'être remplacé, déplacé ou retiré : rien n'est perdu ;
  - une écriture porte l'empreinte de ce que l'auteur a lu : si le fichier a changé depuis (Obsidian, une autre personne), rien n'est écrasé, le conflit est rendu ;
  - renommer ou déplacer réécrit les [[liens]] du dossier comme Obsidian ; un dossier retiré part à la corbeille des dépôts, jamais effacé ;
  - ce qu'écrit Itare entre dans la file « à relire » du fil.
Un dépôt vit dans l'espace du PROPRIÉTAIRE du projet (<espace du compte>/projets/depots/<nom>) : l'équipe y accède par le projet, avec ses rôles, jamais directement.
Les machines distantes (SFTP) de la V18 ne sont pas portées : la flotte ne donne pas de canal de fichiers."""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import posixpath
import re
import shutil
import time
import urllib.parse
from pathlib import Path

TEXTE = (".md", ".txt", ".json", ".css", ".csv", ".yml", ".yaml", ".canvas", ".html", ".xml", ".js", ".toml", ".ini", ".log", ".tex", ".rst")
MEDIAS = ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "avif", "pdf", "mp3", "wav", "ogg", "m4a", "flac", "mp4", "webm", "mov", "m4v")
CACHES = (".obsidian", ".trash", ".git", "@eaDir", "#recycle", ".corbeille")
MAX_OCTETS = 8 * 1048576
HORS = "chemin hors du dossier du projet"
MACHINE = "local"
LIEN_WIKI = re.compile(r"(!?\[\[)([^\]\|#\n]+?)(#[^\]\|\n]*)?(\|[^\]\n]*)?(\]\])")
LIEN_MD = re.compile(r"(\]\()(<[^>\n]+>|[^)\s]+)(\))")


def empreinte(octets):
    return "sha256:" + hashlib.sha256(octets or b"").hexdigest()


def sans_md(x):
    return x[:-3] if x.lower().endswith(".md") else x


def sous(base, rel):
    """Le chemin réel de `rel` DANS `base`, ou ValueError s'il en sortirait (`..`, lien symbolique, octet nul)."""
    rel = str(rel or "").replace("\\", "/").strip()
    if "\x00" in rel or "\n" in rel:
        raise ValueError(HORS)
    b = Path(base).resolve()
    cible = (b / rel.lstrip("/")).resolve() if rel.strip("/") else b
    if cible != b and b not in cible.parents:
        raise ValueError(HORS)
    return cible


def rel_de(base, p):
    r = Path(p).resolve().relative_to(Path(base).resolve()).as_posix()
    return "" if r == "." else r


def ecrire_octets(chemin, octets):
    """Écrit à côté puis remplace : un fichier à moitié écrit ne remplace jamais l'original."""
    chemin = Path(chemin)
    tmp = chemin.with_name("." + chemin.name + ".cassandra-tmp")
    with open(tmp, "wb") as f:
        f.write(octets)
    os.replace(tmp, chemin)


def lire_octets(chemin):
    chemin = Path(chemin)
    if not chemin.exists():
        return None
    if chemin.is_dir():
        raise ValueError("c'est un dossier, pas un fichier")
    if chemin.stat().st_size > MAX_OCTETS:
        raise ValueError("fichier trop gros (%d Mo au plus)" % (MAX_OCTETS // 1048576))
    return chemin.read_bytes()


def quand(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts or 0))


def liens_reecrire(texte, fichier, de, vers, dossier=False, base_unique=True, forme=""):
    """Réécrit dans `texte` (la note `fichier`) les liens qui visaient `de` pour qu'ils visent `vers` : [[x]], [[x#titre]], [[x|alias]], ![[x]] et [t](chemin%20encodé.md).
    Rend (texte, nombre de liens réécrits)."""
    n = [0]
    if dossier:
        dp, vp = de.rstrip("/") + "/", vers.rstrip("/") + "/"
    else:
        md = de.lower().endswith(".md")
        anc_base = (sans_md(posixpath.basename(de)) if md else posixpath.basename(de)).lower()
        anc_chem = (sans_md(de) if md else de).lower()

    def wiki(m):
        t = m.group(2).strip()
        tl = t.lower()
        if dossier:
            if tl.startswith(dp.lower()):
                n[0] += 1
                return m.group(1) + vp + t[len(dp):] + (m.group(3) or "") + (m.group(4) or "") + m.group(5)
            return m.group(0)
        tl2 = sans_md(tl) if md else tl
        if tl2 == anc_chem or tl == de.lower() or (base_unique and tl2 == anc_base):
            n[0] += 1
            return m.group(1) + forme + (m.group(3) or "") + (m.group(4) or "") + m.group(5)
        return m.group(0)

    def mdl(m):
        brut = m.group(2)
        ang = brut.startswith("<")
        u = brut[1:-1] if ang else brut
        if re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I) or u.startswith("#"):
            return m.group(0)
        chemin, _s, ancre = u.partition("#")
        dec = urllib.parse.unquote(chemin)
        formes = ([("racine/", dec.lstrip("/"))] if dec.startswith("/") else
                  [("relatif", posixpath.normpath(posixpath.join(posixpath.dirname(fichier), dec))), ("racine", dec)])
        for genre, res in formes:
            if dossier and res.lower().startswith(dp.lower()):
                nouv = vp + res[len(dp):]
                break
            if not dossier and res.lower() == de.lower():
                nouv = vers
                break
        else:
            return m.group(0)
        rel = {"racine/": "/" + nouv, "racine": nouv}.get(genre) or posixpath.relpath(nouv, posixpath.dirname(fichier) or ".")
        n[0] += 1
        return m.group(1) + ("<" + rel + ">" if ang else urllib.parse.quote(rel, safe="/()")) + ("#" + ancre if ancre else "") + m.group(3)

    texte = LIEN_WIKI.sub(wiki, texte)
    texte = LIEN_MD.sub(mdl, texte)
    return texte, n[0]


def liens_propres(texte, ancien, nouveau):
    """La note déplacée elle-même : ses liens Markdown RELATIFS visaient depuis l'ancien dossier."""
    if posixpath.dirname(ancien) == posixpath.dirname(nouveau):
        return texte, 0
    n = [0]

    def mdl(m):
        brut = m.group(2)
        ang = brut.startswith("<")
        u = brut[1:-1] if ang else brut
        if re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I) or u.startswith(("#", "/")):
            return m.group(0)
        chemin, _s, ancre = u.partition("#")
        cible = posixpath.normpath(posixpath.join(posixpath.dirname(ancien), urllib.parse.unquote(chemin)))
        rel = posixpath.relpath(cible, posixpath.dirname(nouveau) or ".")
        n[0] += 1
        return m.group(1) + ("<" + rel + ">" if ang else urllib.parse.quote(rel, safe="/()")) + ("#" + ancre if ancre else "") + m.group(3)

    return LIEN_MD.sub(mdl, texte), n[0]


def brancher(ctx, h):
    """Inscrit les capacités du dossier de fichiers. `h` : les aides du module (db, compte_agit, exiger, entete, ajouter_ligne…)."""
    db = h.db
    c0 = ctx

    # ------------------------------------------------------------------ les dépôts du propriétaire
    def depots(compte):
        d = ctx.espace_compte(compte, creer=True) / "depots"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def racine_de(p):
        d = str(p["dossier"] or "")
        if not d.startswith("local:") or not d[6:].strip("/"):
            raise ValueError("ce projet n'a pas de dossier : créez-en un dans l'Atelier, ou rattachez-en un (Modifier › Dossier du projet)")
        r = sous(depots(p["compte"]), d[6:])
        if not r.is_dir():
            raise ValueError("le dossier du projet a disparu du disque : %s" % d)
        return r

    def garde(c, id=0, geste="lire"):
        """La porte de tout geste de l'Atelier qui passe par plusieurs capacités : refuse en mots clairs, rend de quoi agir."""
        compte = h.compte_agit()
        g = str(geste or "lire")
        if g not in ("lire", "ecrire", "fiche", "equipe", "supprimer"):
            raise ValueError("geste inconnu")
        p = h.exiger(id, g, compte)
        return {"id": p["id"], "nom": p["nom"], "proprietaire": p["compte"], "role": h.role_de(p["id"], compte), "dossier": p["dossier"], "archive": bool(p["archive"]), "moi": compte}

    # ------------------------------------------------------------------ versions et trace
    def poser_version(pid, chemin, octets, auteur, note=""):
        emp = empreinte(octets)
        r = db.lire("SELECT n FROM pj_versions WHERE projet_id=? AND chemin=? AND empreinte=? ORDER BY n DESC LIMIT 1", (pid, chemin, emp))
        if r:
            return {"n": r[0]["n"], "deja": True}
        n = (db.lire("SELECT COALESCE(MAX(n),0) m FROM pj_versions WHERE projet_id=? AND chemin=?", (pid, chemin))[0]["m"] or 0) + 1
        db.ecrire("INSERT INTO pj_versions(projet_id, chemin, n, auteur, empreinte, taille, note, ts, contenu) VALUES (?,?,?,?,?,?,?,?,?)",
                  (pid, chemin, n, auteur or "", emp, len(octets), note[:200], time.time(), octets))
        return {"n": n, "deja": False}

    def version_octets(pid, chemin, n):
        r = db.lire("SELECT contenu FROM pj_versions WHERE projet_id=? AND chemin=? AND n=?", (pid, chemin, int(n)))
        return bytes(r[0]["contenu"]) if r else None

    def auteur_de(c):
        return "itare" if c.acteur == "itare" else (c.compte or "?")

    def tracer(c, p, chemin, geste, version=None, de=""):
        db.ecrire("INSERT INTO pj_activite(projet_id, ts, chemin, geste, auteur, de) VALUES (?,?,?,?,?,?)", (p["id"], time.time(), str(chemin)[:500], geste, auteur_de(c)[:120], str(de)[:500]))
        if c.acteur == "itare" and geste in ("ecrire", "deplacer", "retirer", "remettre"):
            r = db.lire("SELECT id, meta FROM pj_fil WHERE projet_id=? AND genre='relire' AND etat='attente' AND ref=? AND ts>? ORDER BY ts DESC LIMIT 1", (p["id"], chemin, time.time() - 1800))
            if r:
                m = json.loads(r[0]["meta"] or "{}")
                m["n"] = int(m.get("n") or 1) + 1
                db.ecrire("UPDATE pj_fil SET meta=? WHERE id=?", (json.dumps(m, ensure_ascii=False), r[0]["id"]))
                return
            db.ecrire("INSERT INTO pj_fil(projet_id, ts, auteur, genre, texte, ref, etat, meta) VALUES (?,?,?,?,?,?,?,?)",
                      (p["id"], time.time(), "Itare", "relire", geste, chemin, "attente", json.dumps({"version": version, "n": 1, "geste": geste}, ensure_ascii=False)))
            c.emettre("projet.arelire", objet=("projet", str(p["id"])), donnees={"id": p["id"], "projet": p["nom"], "chemin": chemin, "geste": geste}, compte=p["compte"])

    # ------------------------------------------------------------------ l'écriture (interne : sans porte, la capacité garde)
    def ecrire_interne(c, p, rel, texte, empreinte_lue="", creer=False):
        racine = racine_de(p)
        absolu = sous(racine, rel)
        if absolu == racine:
            raise ValueError(HORS)
        if not absolu.name.lower().endswith(TEXTE):
            raise ValueError("seuls les fichiers texte s'écrivent ici (.md, .txt…)")
        chemin = rel_de(racine, absolu)
        neuf = (texte or "").encode("utf-8")
        actuel = lire_octets(absolu)
        auteur = auteur_de(c)
        if creer and actuel is not None:
            raise ValueError("%s existe déjà" % chemin)
        if not creer and actuel is None and empreinte_lue:
            raise ValueError("%s a disparu depuis que tu l'as ouvert" % chemin)
        avant_n = 0
        if actuel is not None:
            emp = empreinte(actuel)
            v = poser_version(p["id"], chemin, actuel, "avant", "état trouvé avant écriture")
            avant_n = v["n"]
            if empreinte_lue and empreinte_lue != emp:
                return {"pid": p["id"], "conflit": True, "chemin": chemin, "empreinte": emp, "texte": actuel.decode("utf-8", "replace"), "version_gardee": v["n"],
                        "reason": "%s a changé depuis que tu l'as ouvert (ailleurs : Obsidian, une autre personne). Rien n'est écrasé : le texte trouvé est gardé en version %d." % (chemin, v["n"])}
            if emp == empreinte(neuf):
                return {"pid": p["id"], "chemin": chemin, "empreinte": emp, "inchange": True}
        elif not absolu.parent.is_dir():
            raise ValueError("le dossier %s n'existe pas" % posixpath.dirname(chemin))
        ecrire_octets(absolu, neuf)
        v = poser_version(p["id"], chemin, neuf, auteur)
        return {"pid": p["id"], "chemin": chemin, "empreinte": empreinte(neuf), "version": v["n"], "cree": actuel is None, "avant_n": avant_n}

    def restaurer_octets(pid, chemin, n):
        p = h.entete(pid)
        absolu = sous(racine_de(p), chemin)
        octets = version_octets(pid, chemin, n)
        if octets is None:
            raise ValueError("version %s introuvable" % n)
        ecrire_octets(absolu, octets)

    def coffre_ecrire(c, id=0, chemin="", texte="", empreinte="", creer=False):
        p = h.exiger(id, "ecrire", h.compte_agit())
        res = ecrire_interne(c, p, chemin, texte, str(empreinte or ""), bool(creer))
        if not res.get("conflit") and not res.get("inchange"):
            tracer(c, p, res["chemin"], "ecrire", res.get("avant_n") or None)          # « à relire » garde l'état d'AVANT : c'est lui que « Annuler » remet
        return res

    def prouver_ecrit(c, res):
        if res.get("conflit") or res.get("inchange"):
            return True
        p = h.entete(res["pid"])
        o = lire_octets(sous(racine_de(p), res["chemin"]))
        return o is not None and empreinte(o) == res["empreinte"]

    def defaire_ecrit(c, res):
        if res.get("conflit") or res.get("inchange"):
            return
        p = h.entete(res["pid"])
        absolu = sous(racine_de(p), res["chemin"])
        if res.get("cree"):
            if absolu.is_file():
                absolu.unlink()
        else:
            restaurer_octets(res["pid"], res["chemin"], res["avant_n"])

    # ------------------------------------------------------------------ les liens suivent un déplacement
    def md_du_dossier(racine):
        sortie = []
        for dp, dn, fn in os.walk(racine):
            dn[:] = [d for d in dn if d not in CACHES]
            for f in fn:
                if f.lower().endswith((".md", ".canvas")) and not f.endswith(".cassandra-tmp"):
                    sortie.append(rel_de(racine, Path(dp) / f))
            if len(sortie) > 5000:
                break
        return sortie

    def tous_fichiers(racine, exts):
        sortie = []
        for dp, dn, fn in os.walk(racine):
            dn[:] = [d for d in dn if d not in CACHES and not d.startswith("@")]
            for f in fn:
                if f.lower().rsplit(".", 1)[-1] in exts and not f.endswith(".cassandra-tmp"):
                    sortie.append(rel_de(racine, Path(dp) / f))
        return sorted(sortie, key=str.lower)

    def liens_suivre(c, p, de, vers, dossier):
        racine = racine_de(p)
        tous = tous_fichiers(racine, ("md",) + MEDIAS)
        base_unique, forme = True, ""
        if dossier:
            aiguille = de.rstrip("/") + "/"
        else:
            md = de.lower().endswith(".md")
            nom = lambda q: (sans_md(posixpath.basename(q)) if md else posixpath.basename(q)).lower()
            anc, nv = nom(de), nom(vers)
            base_unique = not any(nom(q) == anc for q in tous)
            forme = (sans_md(posixpath.basename(vers)) if md else posixpath.basename(vers)) if sum(1 for q in tous if nom(q) == nv) <= 1 else (sans_md(vers) if md else vers)
            aiguille = sans_md(posixpath.basename(de)) if md else posixpath.basename(de)
        variantes = {aiguille.lower(), urllib.parse.quote(aiguille, safe="/").lower()}
        total, notes = 0, []
        for f in md_du_dossier(racine):
            try:
                brut = lire_octets(racine / f)
            except ValueError:
                continue
            if brut is None:
                continue
            t = brut.decode("utf-8", "replace")
            if not any(v in t.lower() for v in variantes):
                continue
            t2, k = liens_reecrire(t, f, de, vers, dossier, base_unique, forme)
            if k:
                r = ecrire_interne(c, p, f, t2, empreinte(brut))
                if not r.get("conflit"):
                    total += k
                    notes.append(f)
        if not dossier and vers.lower().endswith(".md"):
            brut = lire_octets(racine / vers)
            if brut is not None:
                t2, k = liens_propres(brut.decode("utf-8", "replace"), de, vers)
                if k:
                    r = ecrire_interne(c, p, vers, t2, empreinte(brut))
                    if not r.get("conflit"):
                        total += k
                        notes.append(vers)
        return {"liens": total, "notes": notes}

    # ------------------------------------------------------------------ déplacer, créer un dossier, retirer, remettre
    def coffre_deplacer(c, id=0, chemin="", vers=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        racine = racine_de(p)
        a, b = sous(racine, chemin), sous(racine, vers)
        if racine in (a, b):
            raise ValueError(HORS)
        if b.exists():
            raise ValueError("%s existe déjà" % rel_de(racine, b))
        if not a.exists():
            raise ValueError("introuvable : %s" % chemin)
        est_dossier = a.is_dir()
        ra, rb = rel_de(racine, a), rel_de(racine, b)
        if est_dossier and (b == a or a in b.parents):
            raise ValueError("un dossier ne peut pas entrer dans lui-même")
        if not est_dossier and a.stat().st_size <= MAX_OCTETS:
            poser_version(p["id"], ra, a.read_bytes(), auteur_de(c), "avant déplacement vers %s" % rb)
        b.parent.mkdir(parents=True, exist_ok=True)
        os.replace(a, b)
        res = {"pid": p["id"], "de": ra, "vers": rb, "dossier": est_dossier}
        try:
            res.update(liens_suivre(c, p, ra, rb, est_dossier))
        except Exception as e:
            res["liens_erreur"] = str(e)[:160]
        tracer(c, p, rb, "deplacer", None, ra)
        return res

    def prouver_deplace(c, res):
        racine = racine_de(h.entete(res["pid"]))
        return (racine / res["vers"]).exists() and not (racine / res["de"]).exists()

    def defaire_deplace(c, res):
        p = h.entete(res["pid"])
        racine = racine_de(p)
        os.replace(racine / res["vers"], racine / res["de"])
        liens_suivre(c, p, res["vers"], res["de"], res["dossier"])

    def coffre_dossier(c, id=0, chemin=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        racine = racine_de(p)
        a = sous(racine, chemin)
        if a == racine:
            raise ValueError(HORS)
        if a.exists():
            raise ValueError("%s existe déjà" % rel_de(racine, a))
        a.mkdir(parents=True)
        tracer(c, p, rel_de(racine, a), "dossier")
        return {"pid": p["id"], "chemin": rel_de(racine, a)}

    def prouver_dossier(c, res):
        return (racine_de(h.entete(res["pid"])) / res["chemin"]).is_dir()

    def defaire_dossier(c, res):
        d = racine_de(h.entete(res["pid"])) / res["chemin"]
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    def corbeille_de(compte):
        d = depots(compte) / ".corbeille"
        d.mkdir(exist_ok=True)
        return d

    def vers_corbeille(compte, absolu):
        nom = "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), absolu.name)
        cible = corbeille_de(compte) / nom
        shutil.move(str(absolu), str(cible))
        return cible

    def coffre_retirer(c, id=0, chemin=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        racine = racine_de(p)
        a = sous(racine, chemin)
        if a == racine:
            raise ValueError(HORS)
        if not a.exists():
            raise ValueError("introuvable : %s" % chemin)
        ra = rel_de(racine, a)
        if a.is_dir():
            cible = vers_corbeille(p["compte"], a)
            tracer(c, p, ra, "retirer")
            return {"pid": p["id"], "chemin": ra, "dossier": True, "corbeille": cible.name}
        octets = lire_octets(a)
        v = poser_version(p["id"], ra, octets, auteur_de(c), "retiré du dossier")
        a.unlink()
        tracer(c, p, ra, "retirer", v["n"])
        return {"pid": p["id"], "chemin": ra, "dossier": False, "version": v["n"]}

    def prouver_retire(c, res):
        return not (racine_de(h.entete(res["pid"])) / res["chemin"]).exists()

    def defaire_retire(c, res):
        p = h.entete(res["pid"])
        racine = racine_de(p)
        if res["dossier"]:
            src = corbeille_de(p["compte"]) / res["corbeille"]
            if src.exists():
                (racine / res["chemin"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(racine / res["chemin"]))
        else:
            (racine / res["chemin"]).parent.mkdir(parents=True, exist_ok=True)
            restaurer_octets(res["pid"], res["chemin"], res["version"])

    def coffre_remettre(c, id=0, chemin="", n=0):
        p = h.exiger(id, "ecrire", h.compte_agit())
        racine = racine_de(p)
        a = sous(racine, chemin)
        ch = rel_de(racine, a)
        octets = version_octets(p["id"], ch, n)
        if octets is None:
            raise ValueError("version %s introuvable" % n)
        actuel = lire_octets(a)
        avant_n = 0
        if actuel is not None:
            avant_n = poser_version(p["id"], ch, actuel, "avant", "état remplacé par la v%d" % int(n))["n"]
        ecrire_octets(a, octets)
        nv = poser_version(p["id"], ch, octets, auteur_de(c), "v%d remise à la place de la source" % int(n))
        tracer(c, p, ch, "remettre", nv["n"])
        return {"pid": p["id"], "chemin": ch, "remise": int(n), "version": nv["n"], "empreinte": empreinte(octets), "avant_n": avant_n}

    def prouver_remis(c, res):
        o = lire_octets(sous(racine_de(h.entete(res["pid"])), res["chemin"]))
        return o is not None and empreinte(o) == res["empreinte"]

    def defaire_remis(c, res):
        if res["avant_n"]:
            restaurer_octets(res["pid"], res["chemin"], res["avant_n"])
        else:
            a = sous(racine_de(h.entete(res["pid"])), res["chemin"])
            if a.is_file():
                a.unlink()

    # ------------------------------------------------------------------ lectures du dossier
    def projet_lu(id):
        return h.exiger(id, "lire", h.compte_agit())

    def coffre_lister(c, id=0, chemin=""):
        p = projet_lu(id)
        racine = racine_de(p)
        absolu = sous(racine, chemin)
        if not absolu.is_dir():
            raise ValueError("dossier illisible : %s" % chemin)
        items = []
        for e in os.scandir(absolu):
            if e.name in CACHES or e.name.endswith(".cassandra-tmp"):
                continue
            st = e.stat()
            items.append({"nom": e.name, "dossier": e.is_dir(), "taille": 0 if e.is_dir() else st.st_size, "modifie": quand(st.st_mtime), "chemin": rel_de(racine, Path(e.path))})
        items.sort(key=lambda x: (not x["dossier"], x["nom"].lower()))
        return {"dossier": rel_de(racine, absolu), "items": items}

    def coffre_lire(c, id=0, chemin=""):
        p = projet_lu(id)
        racine = racine_de(p)
        absolu = sous(racine, chemin)
        if absolu == racine:
            raise ValueError(HORS)
        octets = lire_octets(absolu)
        if octets is None:
            raise ValueError("fichier introuvable : %s" % chemin)
        st = absolu.stat()
        d = {"chemin": rel_de(racine, absolu), "empreinte": empreinte(octets), "taille": len(octets), "modifie": quand(st.st_mtime), "mt": st.st_mtime}
        if absolu.name.lower().endswith(TEXTE):
            d["texte"] = octets.decode("utf-8", "replace")
        else:
            d["binaire"] = True
        return d

    def coffre_etat(c, id=0, chemin=""):
        p = projet_lu(id)
        racine = racine_de(p)
        a = sous(racine, chemin)
        if a == racine:
            raise ValueError(HORS)
        if not a.exists():
            raise ValueError("disparu")
        st = a.stat()
        return {"mt": st.st_mtime, "taille": st.st_size}

    def coffre_fichier(c, id=0, chemin="", apercu=True):
        p = projet_lu(id)
        racine = racine_de(p)
        if not str(chemin or "").strip():
            raise ValueError("chemin manquant : donne le chemin du fichier dans le dossier du projet (ex. « Pièces Jointes/photo.jpg »)")
        a = sous(racine, chemin)
        if a == racine:
            raise ValueError(HORS)
        ext = a.suffix.lower().lstrip(".")
        if ext not in MEDIAS:
            raise ValueError("type non affichable ici : .%s" % (ext or "?"))
        octets = lire_octets(a)
        if octets is None:
            raise ValueError("fichier introuvable : %s" % chemin)
        mime = "image/svg+xml" if ext == "svg" else (mimetypes.guess_type(a.name)[0] or "application/octet-stream")
        taille, reduit = len(octets), False
        if apercu and mime.startswith("image/") and ext not in ("svg", "gif") and taille > 1200000:
            try:
                import io
                from PIL import Image, ImageOps
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(octets)))
                im.thumbnail((2000, 2000))
                b = io.BytesIO()
                if im.mode in ("RGBA", "LA", "P"):
                    im.save(b, "PNG", optimize=True)
                    mime = "image/png"
                else:
                    im.convert("RGB").save(b, "JPEG", quality=85)
                    mime = "image/jpeg"
                octets, reduit = b.getvalue(), True
            except Exception:
                pass
        return {"chemin": rel_de(racine, a), "mime": mime, "taille": taille, "reduit": reduit, "b64": base64.b64encode(octets).decode("ascii")}

    def coffre_index(c, id=0):
        p = projet_lu(id)
        tous = tous_fichiers(racine_de(p), ("md",) + MEDIAS)
        return {"notes": [q for q in tous if q.lower().endswith(".md")], "medias": [q for q in tous if not q.lower().endswith(".md")]}

    def coffre_versions(c, id=0, chemin=""):
        p = projet_lu(id)
        racine = racine_de(p)
        ch = rel_de(racine, sous(racine, chemin))
        rows = db.lire("SELECT n, auteur, ts, empreinte, taille, note FROM pj_versions WHERE projet_id=? AND chemin=? ORDER BY n DESC LIMIT 200", (p["id"], ch))
        return {"chemin": ch, "versions": [dict(r) for r in rows]}

    def coffre_version(c, id=0, chemin="", n=0):
        p = projet_lu(id)
        racine = racine_de(p)
        ch = rel_de(racine, sous(racine, chemin))
        r = db.lire("SELECT auteur, ts, contenu FROM pj_versions WHERE projet_id=? AND chemin=? AND n=?", (p["id"], ch, int(n)))
        if not r:
            raise ValueError("version %s introuvable" % n)
        return {"n": int(n), "auteur": r[0]["auteur"], "ts": r[0]["ts"], "texte": bytes(r[0]["contenu"]).decode("utf-8", "replace")}

    # ------------------------------------------------------------------ choisir un dossier (les dépôts de ce serveur)
    def dossier_parcourir(c, machine="", chemin=""):
        compte = h.compte_agit()
        base = depots(compte)
        machines = [{"nom": MACHINE, "libelle": "Ce serveur (mes dépôts)", "windows": False, "racine": "/"}]
        if not machine:
            ex = db.lire("SELECT dossier FROM projets WHERE compte=? AND dossier LIKE 'local:%' AND supprime_at IS NULL ORDER BY maj DESC LIMIT 1", (compte,))
            depart = {"machine": MACHINE, "chemin": "/" + posixpath.dirname(ex[0]["dossier"][6:].strip("/"))} if ex and "/" in ex[0]["dossier"][6:].strip("/") else None
            return {"machines": machines, "depart": depart}
        if machine != MACHINE:
            raise ValueError("machine inconnue : %s (seuls les dépôts de ce serveur sont portés)" % machine)
        try:
            absolu = sous(base, chemin if str(chemin or "").strip("/") else "")
        except ValueError:
            absolu = base.resolve()
        if not absolu.is_dir():
            absolu = base.resolve()
        ds = sorted((e.name for e in os.scandir(absolu) if e.is_dir(follow_symlinks=False) and not e.name.startswith((".", "#", "@"))), key=str.lower)[:500]
        rel = rel_de(base, absolu)
        reel = "/" + rel if rel else "/"
        return {"machines": machines, "machine": MACHINE, "chemin": reel, "parent": ("/" + posixpath.dirname(rel)).rstrip("/") or "/" if rel else "", "dossiers": ds}

    def nom_sain(x):
        n = re.sub(r'[/\\\x00-\x1f:*?"<>|]', "_", str(x or "").strip()).strip(" .")
        if not n or n.startswith("."):
            raise ValueError("nom de dossier invalide")
        return n[:100]

    def dossier_creer(c, machine="", chemin="/", nom=""):
        compte = h.compte_agit()
        if machine != MACHINE:
            raise ValueError("machine inconnue : %s" % machine)
        base = depots(compte)
        parent = sous(base, chemin)
        cible = parent / nom_sain(nom)
        if cible.exists():
            raise ValueError("%s existe déjà" % cible.name)
        cible.mkdir()
        return {"compte": compte, "chemin": "/" + rel_de(base, cible)}

    def prouver_dossier_cree(c, res):
        return (depots(res["compte"]) / res["chemin"].strip("/")).is_dir()

    def defaire_dossier_cree(c, res):
        d = depots(res["compte"]) / res["chemin"].strip("/")
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    def dossier_corbeille(c, machine="", chemin="/"):
        compte = h.compte_agit()
        if machine != MACHINE:
            raise ValueError("machine inconnue : %s" % machine)
        base = depots(compte)
        a = sous(base, chemin)
        if a == base.resolve() or not a.is_dir():
            raise ValueError("la racine des dépôts ne se met pas à la corbeille")
        pris = h.db.lire("SELECT nom FROM projets WHERE compte=? AND supprime_at IS NULL AND (dossier=? OR dossier LIKE ?)", (compte, "local:/" + rel_de(base, a), "local:/" + rel_de(base, a) + "/%"))
        if pris:
            raise ValueError("ce dossier est celui du projet « %s » : détachez-le d'abord" % pris[0]["nom"])
        ra = rel_de(base, a)
        cible = vers_corbeille(compte, a)
        return {"compte": compte, "chemin": ra, "corbeille": "%s (corbeille des dépôts)" % cible.name, "rangee": cible.name}

    def prouver_dossier_corbeille(c, res):
        return not (depots(res["compte"]) / res["chemin"]).exists()

    def defaire_dossier_corbeille(c, res):
        src = corbeille_de(res["compte"]) / res["rangee"]
        if src.exists():
            cible = depots(res["compte"]) / res["chemin"]
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(cible))

    def lier_dossier(pid, valeur):
        db.ecrire("UPDATE projets SET dossier=?, maj=? WHERE id=?", (valeur, time.time(), pid))

    def dossier_local(c, id=0):
        compte = h.compte_agit()
        p = h.exiger(id, "fiche", compte)
        if str(p["dossier"] or ""):
            raise ValueError("ce projet a déjà un dossier : %s" % p["dossier"])
        base = depots(p["compte"])
        nom = nom_sain(p["nom"] or "Projet")
        cible, k = base / nom, 1
        while cible.exists():
            k += 1
            cible = base / ("%s (%d)" % (nom, k))
        cible.mkdir()
        valeur = "local:/" + rel_de(base, cible)
        lier_dossier(p["id"], valeur)
        db.ecrire("INSERT INTO pj_fil(projet_id, ts, auteur, genre, texte) VALUES (?,?,?,?,?)", (p["id"], time.time(), compte, "journal", "Dépôt créé sur ce serveur : %s" % valeur))
        return {"pid": p["id"], "dossier": valeur, "avant": "", "cree": True}

    def prouver_dossier_local(c, res):
        p = h.entete(res["pid"])
        return p["dossier"] == res["dossier"] and racine_de(p).is_dir()

    def defaire_dossier_local(c, res):
        p = h.entete(res["pid"])
        if res.get("cree"):
            try:
                d = racine_de(p)
                if not any(d.iterdir()):
                    d.rmdir()
            except ValueError:
                pass
        lier_dossier(res["pid"], res["avant"])

    def dossier_lier(c, id=0, dossier=""):
        compte = h.compte_agit()
        p = h.exiger(id, "fiche", compte)
        v = str(dossier or "").strip()
        if v and not v.startswith("local:"):
            raise ValueError("seuls les dépôts de ce serveur se rattachent (« local:/nom ») : les machines distantes ne sont pas portées")
        if v:
            if not sous(depots(p["compte"]), v[6:]).is_dir() or not v[6:].strip("/"):
                raise ValueError("dossier introuvable dans les dépôts : %s" % v)
            v = "local:/" + v[6:].strip("/")
        lier_dossier(p["id"], v)
        return {"pid": p["id"], "dossier": v, "avant": p["dossier"], "cree": False}

    def prouver_dossier_lie(c, res):
        return h.entete(res["pid"])["dossier"] == res["dossier"]

    def defaire_dossier_lie(c, res):
        lier_dossier(res["pid"], res["avant"])

    # ------------------------------------------------------------------ la fiche d'un document
    def atelier_fiche(c, id=0, chemin=""):
        p = projet_lu(id)
        ch = str(chemin or "").strip().lstrip("/")[:500]
        if not ch or ch.startswith("::"):
            raise ValueError("la fiche vaut pour un fichier du coffre")
        nom = sans_md(posixpath.basename(ch))
        out = {"chemin": ch, "cite_par": [], "auteurs": [], "versions": 0, "taches": [], "commentaires": 0}
        try:
            racine = racine_de(p)
            b = posixpath.basename(ch)
            aig = ("[[%s]]" % nom, "[[%s|" % nom, "[[%s#" % nom, "(%s)" % urllib.parse.quote(b), "(%s)" % b, "/%s)" % urllib.parse.quote(b))
            for f in md_du_dossier(racine):
                if f == ch:
                    continue
                try:
                    brut = lire_octets(racine / f)
                except ValueError:
                    continue
                if brut and any(a in brut.decode("utf-8", "replace") for a in aig):
                    out["cite_par"].append(f)
                if len(out["cite_par"]) >= 50:
                    break
        except ValueError:
            pass
        for r in db.lire("SELECT auteur, COUNT(*) n, MAX(ts) dernier FROM pj_activite WHERE projet_id=? AND chemin=? GROUP BY auteur ORDER BY MAX(ts) DESC", (p["id"], ch)):
            out["auteurs"].append({"auteur": r["auteur"], "n": r["n"], "dernier": quand(r["dernier"])})
        out["versions"] = db.lire("SELECT COUNT(*) n FROM pj_versions WHERE projet_id=? AND chemin=?", (p["id"], ch))[0]["n"]
        out["commentaires"] = db.lire("SELECT COUNT(*) n FROM pj_commentaires WHERE projet_id=? AND chemin=? AND parent=0 AND resolu=''", (p["id"], ch))[0]["n"]
        if len(nom) >= 3:
            try:
                etapes = {j["id"]: j["nom"] for j in db.lire("SELECT id, nom FROM jalons WHERE projet_id=?", (p["id"],))}
                tk = (ctx.executer_lecture("taches.lister", projet_id=p["id"], limite=400) or {}).get("taches", [])
                out["taches"] = [{"id": t["id"], "texte": t.get("texte"), "statut": t.get("statut"), "etape": etapes.get(t.get("etape_id")) or ""}
                                 for t in tk if t.get("statut") not in ("fait", "abandonnee") and nom.lower() in (str(t.get("texte") or "") + " " + str(t.get("notes") or "")).lower()][:20]
            except Exception:
                pass
        out["noms"] = h.noms()
        return out

    # ------------------------------------------------------------------ inscription
    for cid, f in (("garde", garde), ("coffre_lister", coffre_lister), ("coffre_lire", coffre_lire), ("coffre_etat", coffre_etat), ("coffre_fichier", coffre_fichier),
                   ("coffre_index", coffre_index), ("coffre_versions", coffre_versions), ("coffre_version", coffre_version),
                   ("dossier_parcourir", dossier_parcourir), ("atelier_fiche", atelier_fiche)):
        ctx.implementer(cid, f)
    sim = lambda t: (lambda x, id="", chemin="", **_: "%s (projet %s, %s)" % (t, id, chemin))
    ctx.implementer("coffre_ecrire", coffre_ecrire, prouver_ecrit, defaire_ecrit, simuler=sim("écrirait le fichier"))
    ctx.implementer("coffre_deplacer", coffre_deplacer, prouver_deplace, defaire_deplace, simuler=sim("déplacerait"))
    ctx.implementer("coffre_dossier", coffre_dossier, prouver_dossier, defaire_dossier, simuler=sim("créerait le dossier"))
    ctx.implementer("coffre_retirer", coffre_retirer, prouver_retire, defaire_retire, simuler=sim("retirerait"))
    ctx.implementer("coffre_remettre", coffre_remettre, prouver_remis, defaire_remis, simuler=sim("remettrait une version de"))
    ctx.implementer("dossier_creer", dossier_creer, prouver_dossier_cree, defaire_dossier_cree, simuler=lambda x, nom="", **_: "créerait le dépôt « %s »" % nom)
    ctx.implementer("dossier_corbeille", dossier_corbeille, prouver_dossier_corbeille, defaire_dossier_corbeille, simuler=lambda x, chemin="", **_: "mettrait %s à la corbeille" % chemin)
    ctx.implementer("dossier_local", dossier_local, prouver_dossier_local, defaire_dossier_local, simuler=lambda x, id="", **_: "créerait le dépôt du projet %s" % id)
    ctx.implementer("dossier_lier", dossier_lier, prouver_dossier_lie, defaire_dossier_lie, simuler=lambda x, id="", **_: "rattacherait un dépôt au projet %s" % id)
    return {"racine_de": racine_de, "ecrire_interne": ecrire_interne, "restaurer_octets": restaurer_octets, "tracer": tracer, "poser_version": poser_version, "version_octets": version_octets}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
