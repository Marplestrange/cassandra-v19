# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le salon
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : salon
# ZONE       : CN
# VERSION CN : 0.1.1  #98a6a0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le salon : des fils de travail où les personnes et les agents se parlent.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=98a6a0 ▼▼▼
"""Le salon : des fils de travail où les personnes et les agents se parlent.

Porté de la V18 (`salon_*`), avec ses leçons :
  - un message a un auteur, des destinataires (UN CHAMP : le corps n'est jamais lu pour router) et un corps ; un message sans destinataire est rangé et ne réveille personne ;
  - on poste TOUJOURS : le verrou porte sur le déclenchement des modèles, jamais sur l'écriture ;
  - les agents résidents (Cassandra, Itare) ont une PRÉSENCE : un message qui leur est adressé les réveille, un tour à la fois, et ils répondent dans le fil ; un budget borne la conversation
    d'agents entre eux tant qu'aucun humain ne parle (sans lui, deux agents se répondraient sans fin) ; « (rien) » est une réponse de succès : rien n'est posté ;
  - une signature ne se devine pas : l'auteur d'un message est celui qui agit (un humain se nomme par son compte), jamais un repli sur un autre nom ;
  - l'archivage est un RANGEMENT du compte, pas un statut du fil : le fil vit pour tous, chacun range sa liste ;
  - supprimer un fil ou un message laisse la trace AVANT le geste (qui, quoi, combien) ;
  - un humain qui parle rouvre un fil en attente ; les non-lus se comptent depuis ce que chacun a lu, et survivent au rechargement ;
  - un fil long se résume (le passé), ses derniers messages restent lisibles tels quels ;
  - cloisonné : un compte ne voit que les fils où il est membre, l'administrateur n'y échappe pas (administrer n'est pas voir).
"""
from __future__ import annotations

import json
import re
import threading
import time

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
RESIDENTS = ("cassandra", "itare")
TOUS = "_TOUS_"
RIEN = "(rien)"
STATUTS = ("ouvert", "attente", "termine", "archive")
MODES = ("agir", "plan")
TERRAINS = {
    "creatif": ("Créatif", ""),
    "desk": ("Desk", "Tu travailles dans l'espace personnel de cette personne — ses notes, ses projets, son agenda, ses rappels, son répertoire, son courrier. Sers-toi des outils quand la demande le suppose, plutôt que de décrire ce que tu ferais ; annonce en une ligne ce que tu as fait, après l'avoir fait. Tu n'as aucun accès à la machine."),
    "citadelle": ("Citadelle", "Ce fil est sur le terrain de la machine : services, système, fichiers, infrastructure. Tu agis en cage et par le catalogue, journalisé sous ton nom ; ce qui sort du catalogue attend une main humaine."),
    "cherche": ("Cherche", "Ce fil est un terrain de recherche : tu lis, tu compares, tu cites, tu ne modifies rien."),
}
RESUME_SEUIL = 400          # en dessous, un fil se lit ; au-dessus, son passé se résume
RESUME_GARDE = 200          # les derniers messages restent hors du résumé : c'est ce que l'écran ouvre
CORPS_MAX = 200000


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
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


def nom_propre(nom):
    return re.sub(r"[^a-z0-9_\-]", "", str(nom or "").strip().lower())[:32]


def destinataires_de(d):
    """Le champ, normalisé : noms propres, `tous` -> _TOUS_ ; un humain se nomme par son compte (« humain:x »). Jamais lu dans le corps. Le calcul est un POINT D'ÉVOLUTION : points/EC_destinataires_de.py."""
    return _appeler_point("destinataires_de", {"d": d})["valeur"]


def requete_fts(q):
    """Une requête plein texte sûre : des mots entiers ou préfixes, jamais la syntaxe du moteur."""
    mots = re.findall(r"\w{2,}", str(q or "").lower())[:8]
    return " AND ".join('"%s"*' % m for m in mots)


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage
    verrou = threading.Lock()
    ctx.pause_tours = 0.0

    def invitant():
        """Un agent invité (jeton) agit pour son INVITANT : ses droits, et les fils où il entre, sont ceux de ce compte. -> (compte invitant, nom de l'agent)"""
        try:
            m = ctx.executer_lecture("comptes.moi") or {}
        except Exception:
            m = {}
        c = str(ctx.compte or "")
        nom = c[len("agent:"):] if c.startswith("agent:") else c.split("@")[0]
        return str(m.get("invite_par") or ""), nom_propre(nom)

    def moi():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("le salon est celui d'un compte : aucun compte n'agit")
        if (ctx.acteur or "") == "agent":
            par, _ = invitant()
            if not par:
                raise ValueError("cet agent n'a pas d'invitant : il n'a pas de salon")
            return par
        return c

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    # ------------------------------------------------------------------ visibilité
    def membre_de(compte, fil):
        return bool(db.lire("SELECT 1 FROM fils f WHERE f.id=? AND (f.proprietaire=? OR EXISTS (SELECT 1 FROM membres m WHERE m.fil=f.id AND m.compte=?))", (int(fil), compte, compte)))

    def exiger(fil, compte=None):
        c = compte or moi()
        r = db.lire("SELECT * FROM fils WHERE id=?", (int(fil or 0),))
        if not r or not membre_de(c, int(fil)):
            raise ValueError("fil inconnu")                      # introuvable, jamais interdit : un identifiant deviné ne dit pas ce qu'il désigne
        return dict(r[0])

    def humain_agit():
        return (ctx.acteur or "humain") in ("humain", "compte")

    def acteur_nom(auteur=""):
        """L'auteur d'un message : l'humain se nomme par son compte ; un agent par son nom (résident, ou invité), jamais deviné."""
        if humain_agit():
            return "humain:" + moi(), True
        a = (invitant()[1] if (ctx.acteur or "") == "agent" else "") or nom_propre(auteur) or nom_propre(ctx.acteur)
        if not a or a in ("tous", "humain") or a in RESIDENTS and (ctx.acteur or "") == "agent":
            a = "inconnu"
        return a, False

    def journal(acteur, geste, fil, details=""):
        f = db.lire("SELECT titre FROM fils WHERE id=?", (int(fil),))
        n = db.lire("SELECT COUNT(*) AS n FROM messages WHERE fil=?", (int(fil),))[0]["n"]
        db.ecrire("INSERT INTO journal(ts, acteur, geste, fil, titre, messages, details) VALUES (?,?,?,?,?,?,?)", (time.time(), str(acteur or "")[:80], geste, int(fil), (f[0]["titre"] if f else "")[:200], n, str(details or "")[:200]))

    # ------------------------------------------------------------------ lire
    def fils(c, statut="", archives=False):
        compte = moi()
        sql = ("SELECT f.*, (SELECT COUNT(*) FROM messages m WHERE m.fil=f.id) AS n, "
               "(SELECT COUNT(*) FROM messages m WHERE m.fil=f.id AND m.humain=0 AND m.id > COALESCE((SELECT MAX(id) FROM messages h WHERE h.fil=f.id AND h.humain=1),0)) AS depuis_humain, "
               "(SELECT GROUP_CONCAT(DISTINCT auteur) FROM messages m WHERE m.fil=f.id) AS voix, "
               "(SELECT COUNT(*) FROM messages m WHERE m.fil=f.id AND m.auteur<>? AND m.id > COALESCE((SELECT v.dernier FROM vus v WHERE v.acteur=? AND v.fil=f.id),0)) AS nonlus, "
               "EXISTS(SELECT 1 FROM rangements r WHERE r.compte=? AND r.fil=f.id AND r.etat='archive') AS range_archive "
               "FROM fils f WHERE (f.proprietaire=? OR EXISTS (SELECT 1 FROM membres mb WHERE mb.fil=f.id AND mb.compte=?))")
        args = ["humain:" + compte, "humain:" + compte, compte, compte, compte]
        if statut:
            sql += " AND f.statut=?"
            args.append(statut)
        elif not archives:
            sql += " AND f.statut<>'archive' AND NOT EXISTS (SELECT 1 FROM rangements r WHERE r.compte=? AND r.fil=f.id AND r.etat='archive')"
            args.append(compte)
        out = []
        for x in db.lire(sql + " ORDER BY f.dernier DESC LIMIT 100", args):
            d = dict(x)
            d["range"] = "archive" if (d.pop("range_archive", 0) or d["statut"] == "archive") else ""
            d["membres"] = [r["compte"] for r in db.lire("SELECT compte FROM membres WHERE fil=? ORDER BY ts", (d["id"],))]
            out.append(d)
        return {"fils": out}

    def lire(c, fil=0, depuis=0, limite=60, avant=0):
        """Les messages d'un fil, dans l'ordre. `depuis` > 0 : ceux qui suivent cet id (lecture incrémentale). Sans `depuis` : les DERNIERS `limite`. `avant` : la page de `limite` messages qui précède cet id."""
        exiger(fil)
        n = max(1, min(500, int(limite or 60)))
        cols = "id, ts, auteur, destinataires, corps, sources, humain"
        if int(avant or 0) > 0:
            rows = list(reversed(db.lire("SELECT %s FROM messages WHERE fil=? AND id<? AND id>? ORDER BY id DESC LIMIT ?" % cols, (int(fil), int(avant), int(depuis or 0), n))))
        elif int(depuis or 0) > 0:
            rows = db.lire("SELECT %s FROM messages WHERE fil=? AND id>? ORDER BY id LIMIT ?" % cols, (int(fil), int(depuis), n))
        else:
            rows = list(reversed(db.lire("SELECT %s FROM messages WHERE fil=? ORDER BY id DESC LIMIT ?" % cols, (int(fil), n))))
        out = []
        for r in rows:
            d = dict(r)
            d["destinataires"], d["sources"] = json.loads(d["destinataires"] or "[]"), json.loads(d["sources"] or "[]")
            out.append(d)
        return {"messages": out}

    def chercher(c, question="", fil=0, limite=40):
        """Chercher dans les messages, par l'index, dans ce que ce compte a le droit de voir."""
        compte = moi()
        req = requete_fts(question)
        if not req:
            return {"resultats": []}
        sql = ("SELECT m.id, m.fil, m.ts, m.auteur, m.humain, f.titre, snippet(messages_fts, 0, '[', ']', ' … ', 14) AS extrait FROM messages_fts t JOIN messages m ON m.id=t.rowid JOIN fils f ON f.id=m.fil "
               "WHERE messages_fts MATCH ? AND (f.proprietaire=? OR EXISTS (SELECT 1 FROM membres mb WHERE mb.fil=f.id AND mb.compte=?))")
        args = [req, compte, compte]
        if int(fil or 0) > 0:
            sql += " AND m.fil=?"
            args.append(int(fil))
        sql += " ORDER BY rank LIMIT ?"
        args.append(max(1, min(200, int(limite or 40))))
        return {"resultats": [dict(r) for r in db.lire(sql, args)]}

    def etat(c):
        """Ce que le panneau de présence affiche : chaque résident, en tour ou en veille, son dernier mot, le budget."""
        moi()
        res = []
        for a in RESIDENTS:
            t = db.lire("SELECT fil, debut FROM tours WHERE agent=? AND fin IS NULL ORDER BY id DESC LIMIT 1", (a,))
            d = db.lire("SELECT ts FROM messages WHERE auteur=? ORDER BY id DESC LIMIT 1", (a,))
            res.append({"nom": a, "etat": "ecrit" if t else "veille", "fil": t[0]["fil"] if t else None, "depuis_s": int(time.time() - t[0]["debut"]) if t else None, "dernier_mot": d[0]["ts"] if d else None})
        return {"residents": res, "budget": int(reglage("budget_tours", 8)), "terrains": [{"cle": k, "nom": v[0]} for k, v in TERRAINS.items()]}

    def journal_lire(c, limite=50):
        compte = moi()
        return {"journal": [dict(r) for r in db.lire("SELECT j.* FROM journal j WHERE j.acteur IN (?, ?) ORDER BY j.id DESC LIMIT ?", (compte, "humain:" + compte, max(1, min(500, int(limite or 50)))))]}

    def resume_lire(c, fil=0):
        exiger(fil)
        r = db.lire("SELECT fil, jusqu_a, texte, par, ts, tranches FROM resumes WHERE fil=?", (int(fil),))
        return {"resume": dict(r[0]) if r else None}

    def membres(c, fil=0):
        f = exiger(fil)
        return {"proprietaire": f["proprietaire"], "membres": [dict(r) for r in db.lire("SELECT compte, invite_par, ts FROM membres WHERE fil=? ORDER BY ts", (f["id"],))]}

    def attendre(c, fil=0, depuis=0, delai=25):
        """Attendre un nouveau message (route qui BLOQUE, bornée) : pour un agent invité qui veille un fil."""
        exiger(fil)
        fin = time.time() + max(1, min(int(delai or 25), 55))
        while True:
            rows = db.lire("SELECT id FROM messages WHERE fil=? AND id>? LIMIT 1", (int(fil), int(depuis or 0)))
            if rows or time.time() >= fin:
                return lire(c, fil=fil, depuis=depuis or 0, limite=60) if rows else {"messages": []}
            time.sleep(0.4)

    # ------------------------------------------------------------------ écrire
    def fil_creer(c, titre="", but="", terrain=""):
        compte = moi()
        if terrain and terrain not in TERRAINS:
            raise ValueError("terrain inconnu (%s)" % ", ".join(sorted(TERRAINS)))
        now = time.time()
        fid = db.ecrire("INSERT INTO fils(titre, but, proprietaire, cree, dernier, terrain) VALUES (?,?,?,?,?,?)", (str(titre or "")[:200], str(but or "")[:2000], compte, now, now, terrain or ""))
        return {"id": fid, "proprietaire": compte}

    def prouver_fil(c, res):
        return bool(db.lire("SELECT 1 FROM fils WHERE id=?", (res["id"],)))

    def defaire_fil(c, res):
        db.ecrire("DELETE FROM messages WHERE fil=?", (res["id"],))
        db.ecrire("DELETE FROM fils WHERE id=?", (res["id"],))

    def fil_supprimer(c, fil=0):
        """Le fil et ses messages, définitivement — un geste du propriétaire. L'archivage est la voie douce. La trace est écrite AVANT le geste."""
        compte = moi()
        f = exiger(fil)
        if f["proprietaire"] != compte:
            raise PermissionError("seul le propriétaire d'un fil le supprime (tu peux le ranger, ou le quitter)")
        msgs = [dict(r) for r in db.lire("SELECT * FROM messages WHERE fil=? ORDER BY id", (f["id"],))]
        mb = [dict(r) for r in db.lire("SELECT * FROM membres WHERE fil=?", (f["id"],))]
        journal(compte, "suppression", f["id"])
        with db.transaction() as cx:
            cx.execute("DELETE FROM messages WHERE fil=?", (f["id"],))
            cx.execute("DELETE FROM membres WHERE fil=?", (f["id"],))
            cx.execute("DELETE FROM vus WHERE fil=?", (f["id"],))
            cx.execute("DELETE FROM fils WHERE id=?", (f["id"],))
        return {"fil": f, "messages": msgs, "membres": mb}

    def prouver_supprime(c, res):
        return not db.lire("SELECT 1 FROM fils WHERE id=?", (res["fil"]["id"],))

    def defaire_supprime(c, res):
        f = res["fil"]
        db.ecrire("INSERT INTO fils(id, titre, but, statut, proprietaire, cree, dernier, mode, terrain) VALUES (?,?,?,?,?,?,?,?,?)", (f["id"], f["titre"], f["but"], f["statut"], f["proprietaire"], f["cree"], f["dernier"], f["mode"], f["terrain"]))
        for m in res["membres"]:
            db.ecrire("INSERT INTO membres(fil, compte, invite_par, ts) VALUES (?,?,?,?)", (m["fil"], m["compte"], m["invite_par"], m["ts"]))
        for m in res["messages"]:
            db.ecrire("INSERT INTO messages(id, fil, ts, auteur, destinataires, corps, sources, humain) VALUES (?,?,?,?,?,?,?,?)", (m["id"], m["fil"], m["ts"], m["auteur"], m["destinataires"], m["corps"], m["sources"], m["humain"]))

    def fil_statut(c, fil=0, statut=""):
        f = exiger(fil)
        if statut not in STATUTS:
            raise ValueError("statut inconnu (%s)" % ", ".join(STATUTS))
        if f["statut"] != statut:
            journal(ctx.compte, "statut", f["id"], "%s -> %s" % (f["statut"], statut))
        db.ecrire("UPDATE fils SET statut=?, dernier=? WHERE id=?", (statut, time.time(), f["id"]))
        return {"fil": f["id"], "avant": f["statut"], "statut": statut}

    def prouver_statut(c, res):
        return db.lire("SELECT statut FROM fils WHERE id=?", (res["fil"],))[0]["statut"] == res["statut"]

    def defaire_statut(c, res):
        db.ecrire("UPDATE fils SET statut=? WHERE id=?", (res["avant"], res["fil"]))

    def fil_mode(c, fil=0, mode=""):
        """« Plan d'abord » : les agents proposent, n'exécutent rien — le mode porté par le fil pour tous ceux qui y parlent."""
        f = exiger(fil)
        if mode not in MODES:
            raise ValueError("mode inconnu (%s)" % " | ".join(MODES))
        db.ecrire("UPDATE fils SET mode=? WHERE id=?", (mode, f["id"]))
        return {"fil": f["id"], "avant": f["mode"], "mode": mode}

    def prouver_mode(c, res):
        return db.lire("SELECT mode FROM fils WHERE id=?", (res["fil"],))[0]["mode"] == res["mode"]

    def defaire_mode(c, res):
        db.ecrire("UPDATE fils SET mode=? WHERE id=?", (res["avant"], res["fil"]))

    def fil_terrain(c, fil=0, terrain=""):
        """Le terrain du fil : un NOM, jamais une permission ; il donne sa directive à l'agent qui répond, et rien de plus."""
        f = exiger(fil)
        t = str(terrain or "").strip().lower()
        if t and t not in TERRAINS:
            raise ValueError("terrain inconnu (%s)" % ", ".join(sorted(TERRAINS)))
        if f["terrain"] != t:
            journal(ctx.compte, "terrain", f["id"], "%s -> %s" % (f["terrain"] or "—", t or "—"))
        db.ecrire("UPDATE fils SET terrain=? WHERE id=?", (t, f["id"]))
        return {"fil": f["id"], "avant": f["terrain"], "terrain": t}

    def prouver_terrain(c, res):
        return db.lire("SELECT terrain FROM fils WHERE id=?", (res["fil"],))[0]["terrain"] == res["terrain"]

    def defaire_terrain(c, res):
        db.ecrire("UPDATE fils SET terrain=? WHERE id=?", (res["avant"], res["fil"]))

    def dire(c, fil=0, destinataires=None, corps="", sources=None, auteur=""):
        """Poster. On poste TOUJOURS : le verrou porte sur le déclenchement des modèles, jamais sur l'écriture. Un message sans destinataire est rangé et ne réveille personne."""
        f = exiger(fil)
        corps = str(corps or "").strip()
        if not corps:
            raise ValueError("message vide")
        dest = destinataires_de(destinataires)
        qui, humain = acteur_nom(auteur)
        mid = db.ecrire("INSERT INTO messages(fil, ts, auteur, destinataires, corps, sources, humain) VALUES (?,?,?,?,?,?,?)",
                        (f["id"], time.time(), qui, json.dumps(dest), corps[:CORPS_MAX], json.dumps([str(s)[:200] for s in (sources or [])][:20]), 1 if humain else 0))
        if humain and f["statut"] == "attente":
            db.ecrire("UPDATE fils SET statut='ouvert' WHERE id=?", (f["id"],))                # un humain qui parle rouvre un fil en attente
        db.ecrire("UPDATE fils SET dernier=? WHERE id=?", (time.time(), f["id"]))
        db.ecrire("INSERT INTO vus(acteur, fil, dernier) VALUES (?,?,?) ON CONFLICT(acteur, fil) DO UPDATE SET dernier=MAX(dernier, excluded.dernier)", (qui, f["id"], mid))
        ctx.emettre("fil.message", objet=("fil", str(f["id"])), donnees={"fil": f["id"], "id": mid, "auteur": qui, "destinataires": dest, "humain": humain})
        return {"id": mid, "fil": f["id"], "destinataires": dest, "auteur": qui}

    def prouver_dit(c, res):
        return bool(db.lire("SELECT 1 FROM messages WHERE id=?", (res["id"],)))

    def defaire_dit(c, res):
        db.ecrire("DELETE FROM messages WHERE id=?", (res["id"],))

    def message_supprimer(c, fil=0, id=0):
        """Un message, définitivement, journalisé avec l'auteur, la longueur et un extrait de ce qui disparaît. Son auteur, ou le propriétaire du fil."""
        compte = moi()
        f = exiger(fil)
        m = db.lire("SELECT * FROM messages WHERE fil=? AND id=?", (f["id"], int(id)))
        if not m:
            raise ValueError("message inconnu dans ce fil")
        m = dict(m[0])
        if m["auteur"] != "humain:" + compte and f["proprietaire"] != compte:
            raise PermissionError("seul l'auteur d'un message, ou le propriétaire du fil, le supprime")
        journal(compte, "message supprimé", f["id"], "#%d de %s, %d caractères : %s" % (m["id"], m["auteur"], len(m["corps"] or ""), (m["corps"] or "")[:60].replace("\n", " ")))
        db.ecrire("DELETE FROM messages WHERE id=?", (m["id"],))
        return {"fil": f["id"], "message": m}

    def prouver_msg_supprime(c, res):
        return not db.lire("SELECT 1 FROM messages WHERE id=?", (res["message"]["id"],))

    def defaire_msg_supprime(c, res):
        m = res["message"]
        db.ecrire("INSERT INTO messages(id, fil, ts, auteur, destinataires, corps, sources, humain) VALUES (?,?,?,?,?,?,?,?)", (m["id"], m["fil"], m["ts"], m["auteur"], m["destinataires"], m["corps"], m["sources"], m["humain"]))

    def membre_inviter(c, fil=0, compte=""):
        """Un autre compte entre dans le fil : il y lit et y écrit. Seul le propriétaire invite."""
        moi_ = moi()
        f = exiger(fil)
        if f["proprietaire"] != moi_:
            raise PermissionError("seul le propriétaire d'un fil y invite")
        cible = str(compte or "").strip().lower()
        try:
            existe = any(x["compte"] == cible for x in (ctx.executer_lecture("comptes.lister") or {}).get("comptes", []))
        except Exception:
            existe = True
        if not cible or cible == moi_ or not existe:
            raise ValueError("compte inconnu, ou c'est le tien")
        dej = db.lire("SELECT 1 FROM membres WHERE fil=? AND compte=?", (f["id"], cible))
        if not dej:
            db.ecrire("INSERT INTO membres(fil, compte, invite_par, ts) VALUES (?,?,?,?)", (f["id"], cible, moi_, time.time()))
            dernier = db.lire("SELECT COALESCE(MAX(id),0) AS d FROM messages WHERE fil=?", (f["id"],))[0]["d"]
            db.ecrire("INSERT OR IGNORE INTO vus(acteur, fil, dernier) VALUES (?,?,?)", ("humain:" + cible, f["id"], 0))
        return {"fil": f["id"], "compte": cible, "deja": bool(dej)}

    def prouver_invite(c, res):
        return bool(db.lire("SELECT 1 FROM membres WHERE fil=? AND compte=?", (res["fil"], res["compte"])))

    def defaire_invite(c, res):
        if not res["deja"]:
            db.ecrire("DELETE FROM membres WHERE fil=? AND compte=?", (res["fil"], res["compte"]))

    def membre_retirer(c, fil=0, compte=""):
        """Retirer un membre (le propriétaire), ou quitter le fil (soi-même). Le propriétaire ne le quitte pas : il le supprime."""
        moi_ = moi()
        f = exiger(fil)
        cible = str(compte or moi_).strip().lower()
        if cible == f["proprietaire"]:
            raise ValueError("le propriétaire ne quitte pas son fil : il le supprime")
        if cible != moi_ and f["proprietaire"] != moi_:
            raise PermissionError("seul le propriétaire retire quelqu'un d'autre")
        av = db.lire("SELECT * FROM membres WHERE fil=? AND compte=?", (f["id"], cible))
        if not av:
            raise ValueError("ce compte n'est pas membre")
        db.ecrire("DELETE FROM membres WHERE fil=? AND compte=?", (f["id"], cible))
        return {"fil": f["id"], "compte": cible, "avant": dict(av[0])}

    def prouver_retire(c, res):
        return not db.lire("SELECT 1 FROM membres WHERE fil=? AND compte=?", (res["fil"], res["compte"]))

    def defaire_retire(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO membres(fil, compte, invite_par, ts) VALUES (?,?,?,?)", (a["fil"], a["compte"], a["invite_par"], a["ts"]))

    def ranger(c, fil=0, archive=True):
        """Ranger le fil dans les archives de CE compte (ou le sortir) : le fil vit pour tous, chacun range sa liste."""
        compte = moi()
        f = exiger(fil)
        av = db.lire("SELECT etat FROM rangements WHERE compte=? AND fil=?", (compte, f["id"]))
        if archive:
            db.ecrire("INSERT OR REPLACE INTO rangements(compte, fil, etat) VALUES (?,?,'archive')", (compte, f["id"]))
        else:
            db.ecrire("DELETE FROM rangements WHERE compte=? AND fil=?", (compte, f["id"]))
        return {"fil": f["id"], "compte": compte, "archive": bool(archive), "avant": bool(av)}

    def prouver_range(c, res):
        return bool(db.lire("SELECT 1 FROM rangements WHERE compte=? AND fil=?", (res["compte"], res["fil"]))) == res["archive"]

    def defaire_range(c, res):
        if res["avant"]:
            db.ecrire("INSERT OR REPLACE INTO rangements(compte, fil, etat) VALUES (?,?,'archive')", (res["compte"], res["fil"]))
        else:
            db.ecrire("DELETE FROM rangements WHERE compte=? AND fil=?", (res["compte"], res["fil"]))

    def vu(c, fil=0):
        """Poser « lu jusqu'ici » pour ce compte : les non-lus survivent au rechargement."""
        compte = moi()
        f = exiger(fil)
        dernier = db.lire("SELECT COALESCE(MAX(id),0) AS d FROM messages WHERE fil=?", (f["id"],))[0]["d"]
        avant = db.lire("SELECT dernier FROM vus WHERE acteur=? AND fil=?", ("humain:" + compte, f["id"]))
        db.ecrire("INSERT INTO vus(acteur, fil, dernier) VALUES (?,?,?) ON CONFLICT(acteur, fil) DO UPDATE SET dernier=excluded.dernier", ("humain:" + compte, f["id"], dernier))
        return {"fil": f["id"], "dernier": dernier, "avant": avant[0]["dernier"] if avant else None}

    def prouver_vu(c, res):
        return db.lire("SELECT dernier FROM vus WHERE acteur=? AND fil=?", ("humain:" + ctx.compte, res["fil"]))[0]["dernier"] == res["dernier"]

    def defaire_vu(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM vus WHERE acteur=? AND fil=?", ("humain:" + ctx.compte, res["fil"]))
        else:
            db.ecrire("UPDATE vus SET dernier=? WHERE acteur=? AND fil=?", (res["avant"], "humain:" + ctx.compte, res["fil"]))

    # ------------------------------------------------------------------ les agents résidents répondent
    def budget_atteint(fil):
        """Sans humain depuis N messages d'agents de suite, plus de tour : deux agents qui se répondent ne s'arrêteraient jamais."""
        n = db.lire("SELECT COUNT(*) AS n FROM messages WHERE fil=? AND humain=0 AND id > COALESCE((SELECT MAX(id) FROM messages WHERE fil=? AND humain=1),0)", (int(fil), int(fil)))[0]["n"]
        return n >= int(reglage("budget_tours", 8))

    def contexte_de(f, agent, compte):
        """Ce que l'agent doit savoir du fil : son but, son terrain, le résumé du passé, et ce qu'il n'a pas encore lu (il ne relit pas ce qu'il a déjà vu)."""
        vu_ = db.lire("SELECT dernier FROM vus WHERE acteur=? AND fil=?", (agent, f["id"]))
        depuis = vu_[0]["dernier"] if vu_ else 0
        rows = list(reversed(db.lire("SELECT id, auteur, destinataires, corps FROM messages WHERE fil=? AND id>? ORDER BY id DESC LIMIT 40", (f["id"], depuis))))
        parts = ["[Fil « %s » #%d%s — statut %s%s]" % (f["titre"] or "sans titre", f["id"], (" — but : " + f["but"]) if f["but"] else "", f["statut"], " — MODE PLAN : propose, n'exécute rien" if f["mode"] == "plan" else "")]
        t = TERRAINS.get(f["terrain"])
        if t and t[1]:
            parts.append("TERRAIN DU FIL : %s — %s" % (t[0], t[1]))
        r = db.lire("SELECT texte, jusqu_a FROM resumes WHERE fil=?", (f["id"],))
        if r and r[0]["texte"] and not depuis:
            parts.append("Résumé du passé (jusqu'au message #%d) :\n%s" % (r[0]["jusqu_a"], r[0]["texte"]))
        parts.append("Ce qui s'est dit depuis ta dernière lecture :")
        for m in rows:
            dest = json.loads(m["destinataires"] or "[]")
            parts.append("#%d %s%s : %s" % (m["id"], m["auteur"], (" → " + ", ".join(dest)) if dest else "", m["corps"][:4000]))
        parts.append("Réponds au fil, à ceux qui t'ont adressé la parole. Si tu n'as rien à ajouter, réponds exactement « %s »." % RIEN)
        return "\n".join(parts), (rows[-1]["id"] if rows else depuis)

    def conversation_pour(f, agent, compte):
        r = db.lire("SELECT conversation_id FROM convs WHERE fil=? AND agent=? AND compte=?", (f["id"], agent, compte))
        if r:
            return r[0]["conversation_id"]
        res = ctx.agir("agents.conversation_creer", {"agent": agent, "titre": "Fil %d — %s" % (f["id"], (f["titre"] or "")[:40])}, acteur=agent)
        cid = (res.get("resultat") or {}).get("id")
        if not cid:
            raise ValueError("conversation impossible : %s" % (res.get("erreur") or res.get("raison") or res.get("statut")))
        db.ecrire("INSERT OR REPLACE INTO convs(fil, agent, compte, conversation_id) VALUES (?,?,?,?)", (f["id"], agent, compte, cid))
        return cid

    def poster_agent(f, agent, dest, corps):
        mid = db.ecrire("INSERT INTO messages(fil, ts, auteur, destinataires, corps, sources, humain) VALUES (?,?,?,?,?,?,0)", (f["id"], time.time(), agent, json.dumps(dest), corps[:CORPS_MAX], "[]"))
        db.ecrire("UPDATE fils SET dernier=? WHERE id=?", (time.time(), f["id"]))
        db.ecrire("INSERT INTO vus(acteur, fil, dernier) VALUES (?,?,?) ON CONFLICT(acteur, fil) DO UPDATE SET dernier=MAX(dernier, excluded.dernier)", (agent, f["id"], mid))
        ctx.emettre("fil.message", objet=("fil", str(f["id"])), donnees={"fil": f["id"], "id": mid, "auteur": agent, "destinataires": dest, "humain": False})
        return mid

    def tour(fil, agent, compte, a_qui):
        """Un tour d'un agent résident : il lit ce qu'il n'a pas lu, répond dans le fil (ou dit « (rien) » et ne poste rien), et sa panne est dite dans le fil — jamais un silence."""
        f = exiger(fil, compte)
        t0 = time.time()
        tid = db.ecrire("INSERT INTO tours(fil, agent, debut) VALUES (?,?,?)", (f["id"], agent, t0))
        erreur, mid = "", None
        try:
            message, jusqu = contexte_de(f, agent, compte)
            cid = conversation_pour(f, agent, compte)
            r = ctx.agir("agents.converser", {"conversation_id": cid, "message": message, "agent": agent}, acteur=agent)
            if r.get("statut") not in ("faite",):
                raise ValueError("le tour n'a pas eu lieu : %s" % (r.get("raison") or r.get("erreur") or r.get("statut")))
            res = r.get("resultat") or {}
            texte = str(res.get("texte") or "").strip()
            pannes = [x.get("erreur") for x in res.get("actions") or [] if isinstance(x, dict) and x.get("statut") == "panne"]
            dest = [a_qui] if a_qui and a_qui != agent else []
            if pannes and not texte:
                mid = poster_agent(f, agent, dest, "⚠️ %s n'a pas pu répondre : %s" % (agent.capitalize(), "; ".join(str(p) for p in pannes)))
                erreur = "; ".join(str(p) for p in pannes)[:300]
            elif texte and texte != RIEN and not texte.startswith(RIEN):
                mid = poster_agent(f, agent, dest, texte)
            db.ecrire("INSERT INTO vus(acteur, fil, dernier) VALUES (?,?,?) ON CONFLICT(acteur, fil) DO UPDATE SET dernier=MAX(dernier, excluded.dernier)", (agent, f["id"], max(jusqu, mid or 0)))
        except Exception as ex:
            erreur = str(ex)[:300]
            mid = poster_agent(f, agent, [a_qui] if a_qui and a_qui != agent else [], "⚠️ %s n'a pas pu répondre : %s" % (agent.capitalize(), erreur))
        finally:
            db.ecrire("UPDATE tours SET fin=?, erreur=? WHERE id=?", (time.time(), erreur, tid))
        return {"fil": f["id"], "agent": agent, "message": mid, "erreur": erreur}

    def reveil(c, ev):
        """Un message est posté : chaque agent résident adressé répond, à tour de rôle. Le compte du message est celui au nom duquel l'agent agit."""
        d = (ev or {}).get("donnees") or {}
        dest = d.get("destinataires") or []
        auteur = d.get("auteur") or ""
        compte = (ev or {}).get("compte") or ""
        if not compte or not d.get("fil"):
            return {"tours": 0}
        agents = [a for a in RESIDENTS if (a in dest or TOUS in dest) and a != auteur]
        if not agents or budget_atteint(d["fil"]):
            return {"tours": 0, "budget": bool(agents)}
        n = 0
        with verrou:                                              # un tour à la fois : chaque agent lit ce que l'autre vient d'écrire
            for a in agents:
                tour(d["fil"], a, compte, auteur if auteur.startswith("humain:") or auteur not in RESIDENTS else auteur)
                n += 1
                if ctx.pause_tours:
                    time.sleep(ctx.pause_tours)
        return {"tours": n}

    def relancer(c, fil=0, agent="cassandra"):
        """Demander à un résident de répondre MAINTENANT dans ce fil (sans nouveau message)."""
        compte = moi()
        f = exiger(fil)
        if agent not in RESIDENTS:
            raise ValueError("résident inconnu (%s)" % ", ".join(RESIDENTS))
        if budget_atteint(f["id"]):
            raise ValueError("le budget de tours entre agents est atteint : un humain doit reprendre la parole")
        with verrou:
            return tour(f["id"], agent, compte, "humain:" + compte)

    def prouver_relance(c, res):
        return bool(db.lire("SELECT 1 FROM tours WHERE fil=? AND agent=? AND fin IS NOT NULL ORDER BY id DESC LIMIT 1", (res["fil"], res["agent"])))

    def defaire_relance(c, res):
        if res.get("message"):
            db.ecrire("DELETE FROM messages WHERE id=?", (res["message"],))

    c = ctx
    c.moteur("reveil", reveil)
    for cid, f in (("fils", fils), ("lire", lire), ("chercher", chercher), ("etat", etat), ("journal", journal_lire), ("resume", resume_lire), ("membres", membres), ("attendre", attendre)):
        c.implementer(cid, f)
    c.implementer("fil_creer", fil_creer, prouver_fil, defaire_fil, simuler=lambda x, titre="", **_: "ouvrirait le fil « %s »" % titre)
    c.implementer("fil_supprimer", fil_supprimer, prouver_supprime, defaire_supprime, simuler=lambda x, fil=0, **_: "supprimerait le fil %s et ses messages" % fil)
    c.implementer("fil_statut", fil_statut, prouver_statut, defaire_statut, simuler=lambda x, fil=0, statut="", **_: "passerait le fil %s à « %s »" % (fil, statut))
    c.implementer("fil_mode", fil_mode, prouver_mode, defaire_mode, simuler=lambda x, fil=0, mode="", **_: "passerait le fil %s en mode %s" % (fil, mode))
    c.implementer("fil_terrain", fil_terrain, prouver_terrain, defaire_terrain, simuler=lambda x, fil=0, terrain="", **_: "poserait le terrain « %s » sur le fil %s" % (terrain, fil))
    c.implementer("dire", dire, prouver_dit, defaire_dit, simuler=lambda x, fil=0, corps="", **_: "posterait un message dans le fil %s" % fil)
    c.implementer("message_supprimer", message_supprimer, prouver_msg_supprime, defaire_msg_supprime, simuler=lambda x, fil=0, id=0, **_: "supprimerait le message %s du fil %s" % (id, fil))
    c.implementer("membre_inviter", membre_inviter, prouver_invite, defaire_invite, simuler=lambda x, fil=0, compte="", **_: "inviterait %s dans le fil %s" % (compte, fil))
    c.implementer("membre_retirer", membre_retirer, prouver_retire, defaire_retire, simuler=lambda x, fil=0, compte="", **_: "retirerait %s du fil %s" % (compte, fil))
    c.implementer("ranger", ranger, prouver_range, defaire_range, simuler=lambda x, fil=0, **_: "rangerait le fil %s dans les archives du compte" % fil)
    c.implementer("vu", vu, prouver_vu, defaire_vu, simuler=lambda x, fil=0, **_: "marquerait le fil %s comme lu" % fil)
    c.implementer("relancer", relancer, prouver_relance, defaire_relance, simuler=lambda x, fil=0, agent="", **_: "demanderait à %s de répondre dans le fil %s" % (agent, fil))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : nom_propre, destinataires_de, requete_fts, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
