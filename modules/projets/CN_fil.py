# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le fil du projet
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : projets
# ZONE       : CN
# VERSION CN : 0.2.0  #f849e9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le fil du projet.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=f849e9 ▼▼▼
"""Ce qui se dit et se fait dans un projet : le fil, les commentaires en marge, la présence, le courrier rangé au projet, le cadrage, les suites proposées, le navigateur-clipper.

Règles gardées de la V18 :
  - un seul fil daté pour ce qui se dit (messages avec @mentions), se décide (on se prononce, quelqu'un tranche), s'écrit au journal et se fait dans le dossier ; la file « à relire » reçoit ce qu'Itare écrit ;
  - un commentaire s'accroche à un PASSAGE par sa citation, pas par une position : il survit à ce qu'on écrit autour ;
  - chacun voit SA boîte : le courrier d'un projet, c'est ce que la boîte du compte échange avec les personnes du projet, ce dont l'objet nomme le projet et ce qu'on y a rangé à la main, moins ce qu'on en a écarté. Rien ne lit la boîte d'un autre membre, et la lecture est celle du CACHE : jamais d'IMAP sur le chemin d'un écran ;
  - le cadrage rend un DIFF (ce qui serait écrit, et ce qui n'a pas été compris) : rien n'est enregistré avant l'accord ; une date fausse dans un plan est pire qu'une date absente ;
  - la présence ne s'écrit jamais : en mémoire, une minute de vie.
Deux choses de la V18 ne sont pas reprises telles quelles : la réponse d'Itare à une @mention (le module des agents n'écoute pas encore le fil : l'événement `projet.itare` est émis, aucune réponse n'est inventée), et le Chromium piloté par tube (le navigateur partagé lit les pages par le module web, en texte : ni image, ni clic)."""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime

MOIS = {"janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12}
CADRAGE_Q = (("objectif", "Sur quoi porte ce projet, en une phrase ?"), ("perimetre_out", "Qu'est-ce qui est clairement HORS périmètre ?"),
             ("reussite", "À quoi saurez-vous qu'il est réussi ?"), ("jalon", "Quelle est la première date qui ne peut pas bouger ?"))
HORS_COURRIER = ("trash", "corbeille", "spam", "junk", "indésirable", "indesirable", "deleted", "supprim")
GENRES_FIL = ("message", "decision", "journal")
PRESENCE_VIE = 60
_presence = {}
_presence_verrou = threading.Lock()
_nav = {}
_nav_verrou = threading.Lock()
NAV_INACTIF = 900


def date_iso(txt):
    """Rend une date ISO, ou ''. Jamais une approximation."""
    t = str(txt or "").strip().lower()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", t)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    m = re.search(r"\b(\d{1,2})\s+([a-zéèûôà]+)\s*(\d{4})?\b", t)
    if m and m.group(2) in MOIS:
        an = int(m.group(3)) if m.group(3) else datetime.now().year
        try:
            d = datetime(an, MOIS[m.group(2)], int(m.group(1)))
        except ValueError:
            return ""
        if not m.group(3) and d < datetime.now():
            d = d.replace(year=an + 1)
        return d.strftime("%Y-%m-%d")
    return ""


def lignes(txt):
    return [re.sub(r"^\s*[-*•]\s*", "", l).strip() for l in str(txt or "").splitlines() if l.strip()]


def horodatage(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts or 0))


def brancher(ctx, h, coffre):
    db = h.db

    def lire_projet(id):
        return h.exiger(id, "lire", h.compte_agit())

    def archive_refuse(id):
        p = h.entete(id)
        if p is not None and p["archive"]:
            raise ValueError("projet archivé : rouvrez-le pour y écrire")

    def membres_comptes(p):
        e = h.equipe_de(p)
        return [x for x in [str(e["proprietaire"]).lower()] + [str(m["compte"]).lower() for m in e["membres"] if m.get("etat") == "actif"] if x]

    def mentions(p, texte):
        """(comptes mentionnés, Itare mentionnée ?). « @Sandrine », « @sandrine.x », « @adresse@complète », « @Itare »."""
        noms = h.noms()
        comptes, itare = [], False
        for m in re.finditer(r"@([\wÀ-ÿ][\wÀ-ÿ.\-]*(?:@[\w.\-]+)?)", str(texte or "")):
            t = m.group(1).rstrip(".").lower()
            if t == "itare":
                itare = True
                continue
            for k in membres_comptes(p):
                nom = (noms.get(k) or "").lower()
                if t in (k, k.split("@")[0], nom, nom.split(" ")[0] if nom else "") and k not in comptes:
                    comptes.append(k)
        return comptes, itare

    def prevenir(c, p, type, titre, corps, comptes):
        moi = (c.compte or "").lower()
        for k in comptes:
            if k and k != moi:
                c.emettre(type, objet=("projet", str(p["id"])), donnees={"id": p["id"], "projet": p["nom"], "titre": titre, "corps": corps[:400], "par": moi}, compte=k)

    def meta_de(r):
        try:
            return json.loads(r["meta"] or "{}")
        except Exception:
            return {}

    def ligne_fil(pid, fid):
        r = db.lire("SELECT * FROM pj_fil WHERE id=? AND projet_id=?", (int(fid or 0), pid))
        return dict(r[0]) if r else None

    # ------------------------------------------------------------------ le courrier du projet
    def boite_ouverte(compte):
        try:
            return ctx.stockage_lecture("courrier")
        except Exception:
            return None

    def adresses_du_projet(p, moi):
        adrs = set()
        try:
            for ct in (ctx.executer_lecture("contacts.pour_cible", kind="project", ref=str(p["id"])) or {}).get("contacts", []):
                adrs.update(str(e).lower() for e in ct.get("emails") or [] if e)
        except Exception:
            pass
        adrs.update(k for k in membres_comptes(p) if "@" in k)
        adrs.discard(moi)
        return sorted(a for a in adrs if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", a))[:60]

    def courrier_fils(p, compte, q="", limite=80, boite=False):
        stock = boite_ouverte(compte)
        if stock is None:
            return {"boite": False, "fils": [], "attend": 0}
        moi = {compte.lower()}
        modes = {r["cle"]: r["mode"] for r in db.lire("SELECT cle, mode FROM pj_courriers WHERE projet_id=? AND compte=?", (p["id"], compte))}
        cols = "dossier, uid, fil, de_addr, de_nom, a_addr, objet, date_iso, lu, repondu, pj, texte"
        q = str(q or "").strip()[:80]
        try:
            if q:
                like = "%" + q.replace("%", "").replace("_", "") + "%"
                rows = stock.lire("SELECT %s FROM messages WHERE compte=? AND (objet LIKE ? OR de_addr LIKE ? OR de_nom LIKE ? OR a_addr LIKE ? OR texte LIKE ?) ORDER BY date_iso DESC LIMIT ?" % cols,
                                  (compte, like, like, like, like, like, 400 if boite else 60))
            elif boite:
                rows = stock.lire("SELECT %s FROM messages WHERE compte=? ORDER BY date_iso DESC LIMIT 600" % cols, (compte,))
            else:
                cond, args = [], [compte]
                adrs = adresses_du_projet(p, compte.lower())
                if adrs:
                    cond.append("lower(de_addr) IN (%s)" % ",".join("?" * len(adrs)))
                    args += adrs
                    for a in adrs:
                        cond.append("lower(a_addr) LIKE ?")
                        args.append("%" + a + "%")
                nom = str(p["nom"] or "").strip()
                if len(nom) >= 5:
                    cond.append("objet LIKE ?")
                    args.append("%" + nom.replace("%", "").replace("_", "") + "%")
                lies = [k for k, m in modes.items() if m == "lie"]
                if lies:
                    cond.append("fil IN (%s)" % ",".join("?" * len(lies)))
                    args += lies
                rows = stock.lire("SELECT %s FROM messages WHERE compte=? AND (%s) ORDER BY date_iso DESC LIMIT 600" % (cols, " OR ".join(cond)), args) if cond else []
        except Exception:
            return {"boite": False, "fils": [], "attend": 0}        # le module du courrier n'est pas là, ou sa base est illisible
        recent = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))
        fils, ordre = {}, []
        for r in rows:
            if any(x in str(r["dossier"] or "").lower() for x in HORS_COURRIER):
                continue
            k = str(r["fil"] or "") or "uid:%s:%s" % (r["dossier"], r["uid"])
            if modes.get(k) == "ecarte" and not q and not boite:
                continue
            f = fils.get(k)
            if f is None:
                de = str(r["de_addr"] or "").lower()
                qd = str(r["date_iso"] or "")[:16].replace("T", " ")
                f = fils[k] = {"cle": k, "folder": r["dossier"], "uid": str(r["uid"]), "sujet": r["objet"] or "(sans objet)", "de": de, "de_nom": r["de_nom"] or "", "quand": qd,
                               "apercu": str(r["texte"] or "")[:200], "n": 0, "non_lus": 0, "pj": False, "moi": de in moi,
                               "attend": (de not in moi) and not r["repondu"] and qd[:10] >= recent, "mode": modes.get(k) or "", "msgs": []}
                ordre.append(k)
            f["msgs"].append("%s/%s" % (r["uid"], r["dossier"]))
            f["n"] += 1
            f["non_lus"] += 0 if r["lu"] else 1
            f["pj"] = f["pj"] or bool(r["pj"])
        out = [fils[k] for k in ordre]
        return {"boite": True, "fils": out[:int(limite)], "attend": sum(1 for f in out if f["attend"])}

    def courrier(c, id=0, q="", limite=80, boite=False):
        p = lire_projet(id)
        return courrier_fils(p, c.compte, q, limite, bool(boite))

    def courrier_ranger(c, id=0, folder="", uid="", mode="lie"):
        p = lire_projet(id)
        mode = mode if mode in ("lie", "ecarte") else ""
        stock = boite_ouverte(c.compte)
        r = stock.lire("SELECT dossier, uid, fil FROM messages WHERE compte=? AND dossier=? AND uid=?", (c.compte, str(folder or ""), str(uid or ""))) if stock is not None else []
        if not r:
            raise ValueError("courriel introuvable dans la boîte")
        k = str(r[0]["fil"] or "") or "uid:%s:%s" % (r[0]["dossier"], r[0]["uid"])
        avant = db.lire("SELECT mode, ts FROM pj_courriers WHERE projet_id=? AND compte=? AND cle=?", (p["id"], c.compte, k))
        if mode:
            db.ecrire("INSERT OR REPLACE INTO pj_courriers(projet_id, compte, cle, mode, ts) VALUES (?,?,?,?,?)", (p["id"], c.compte, k, mode, time.time()))
        else:
            db.ecrire("DELETE FROM pj_courriers WHERE projet_id=? AND compte=? AND cle=?", (p["id"], c.compte, k))
        return {"pid": p["id"], "compte": c.compte, "cle": k, "mode": mode, "avant": dict(avant[0]) if avant else None}

    def prouver_range(c, res):
        r = db.lire("SELECT mode FROM pj_courriers WHERE projet_id=? AND compte=? AND cle=?", (res["pid"], res["compte"], res["cle"]))
        return (r[0]["mode"] == res["mode"]) if res["mode"] else not r

    def defaire_range(c, res):
        db.ecrire("DELETE FROM pj_courriers WHERE projet_id=? AND compte=? AND cle=?", (res["pid"], res["compte"], res["cle"]))
        if res["avant"]:
            db.ecrire("INSERT INTO pj_courriers(projet_id, compte, cle, mode, ts) VALUES (?,?,?,?,?)", (res["pid"], res["compte"], res["cle"], res["avant"]["mode"], res["avant"]["ts"]))

    def atelier_sources(c, id=0):
        """Ce que l'Atelier réunit à côté du dossier : les notes du Carnet rangées dans le projet, les documents de MA GED qui lui sont liés, le courrier de MA boîte."""
        p = lire_projet(id)
        notes, docs = [], []
        try:
            r = ctx.executer_lecture("notes.lister", groupe="pj:" + str(p["nom"]), limite=300)
            notes = [{"id": n.get("id"), "titre": n.get("titre") or n.get("id"), "modifie": n.get("modifiee") or ""} for n in (r or {}).get("notes", [])]
        except Exception:
            pass
        try:
            ged = ctx.stockage_lecture("ged")
            docs = [dict(x) for x in ged.lire("SELECT id, nom, kind, taille, modifie FROM ged_fichiers WHERE compte=? AND (project_id=? OR id IN "
                                              "(SELECT fichier_id FROM ged_liens WHERE kind IN ('projet','project') AND ref=?)) ORDER BY nom LIMIT 300", (c.compte, p["id"], str(p["id"])))]
        except Exception:
            pass
        cour = {}
        try:
            cour = courrier_fils(p, c.compte, limite=60)
        except Exception:
            pass
        return {"notes": notes, "documents": docs, "courrier": cour.get("fils") or [], "boite": bool(cour.get("boite"))}

    # ------------------------------------------------------------------ le fil
    def attente(p, cour=None):
        d = db.lire("SELECT COUNT(*) n FROM pj_fil WHERE projet_id=? AND genre='decision' AND etat='ouverte'", (p["id"],))[0]["n"]
        r = db.lire("SELECT COUNT(*) n FROM pj_fil WHERE projet_id=? AND genre='relire' AND etat='attente'", (p["id"],))[0]["n"]
        return {"decisions": d, "relire": r, "courrier": int((cour or {}).get("attend") or 0)}

    def fil(c, id=0, limite=200):
        p = lire_projet(id)
        limite = max(1, min(int(limite or 200), 1000))
        out = []
        for r in db.lire("SELECT * FROM pj_fil WHERE projet_id=? ORDER BY ts DESC LIMIT ?", (p["id"], limite)):
            d = dict(r)
            d["meta"] = meta_de(r)
            out.append(d)
        deja = {(horodatage(r["ts"]), r["texte"].strip()) for r in out if r["genre"] == "journal"}
        for j in journal_de(p["notes"]):
            if not j["quand"] or (j["quand"], j["texte"]) in deja:
                continue
            try:
                ts = datetime.strptime(j["quand"] if len(j["quand"]) > 10 else j["quand"] + " 00:00", "%Y-%m-%d %H:%M").timestamp()
            except ValueError:
                continue
            out.append({"id": 0, "ts": ts, "auteur": "", "genre": "journal", "texte": j["texte"], "ref": "", "parent": 0, "etat": "", "meta": {}})
        groupe = None
        for a in db.lire("SELECT ts, chemin, geste, auteur, de FROM pj_activite WHERE projet_id=? ORDER BY ts DESC LIMIT 400", (p["id"],)):
            if groupe and groupe["auteur"] == a["auteur"] and groupe["ref"] == a["chemin"] and groupe["ts_bas"] - a["ts"] < 1800:
                groupe["ts_bas"] = a["ts"]
                groupe["meta"]["n"] += 1
                continue
            groupe = {"id": 0, "ts": a["ts"], "ts_bas": a["ts"], "auteur": a["auteur"], "genre": "activite", "texte": a["geste"], "ref": a["chemin"], "parent": 0, "etat": "", "meta": {"n": 1, "de": a["de"] or ""}}
            out.append(groupe)
        cour = None
        try:
            cour = courrier_fils(p, c.compte, limite=40)
            lim = time.time() - 45 * 86400
            for f in cour["fils"] if cour.get("boite") else []:
                try:
                    ts = datetime.strptime(f["quand"], "%Y-%m-%d %H:%M").timestamp()
                except ValueError:
                    continue
                if ts >= lim:
                    out.append({"id": 0, "ts": ts, "auteur": f["de"], "genre": "courrier", "texte": f["sujet"], "ref": "::mail/%s/%s" % (f["uid"], f["folder"]), "parent": 0,
                                "etat": "attend" if f["attend"] else "", "meta": {"de": f["de_nom"], "n": f["n"], "moi": f["moi"]}})
        except Exception:
            cour = None
        out.sort(key=lambda r: -r["ts"])
        out = out[:limite]
        for r in out:
            r.pop("ts_bas", None)
            r["quand"] = horodatage(r["ts"])
        return {"fil": out, "noms": h.noms(), "role": h.role_de(p["id"], c.compte), "moi": c.compte, "attente": attente(p, cour)}

    def journal_de(notes):
        sortie = []
        for l in [x.strip() for x in str(notes or "").replace("\r", "").split("\n") if x.strip()]:
            m = re.match(r"^\[(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?)\]\s*(.*)$", l)
            sortie.append({"quand": m.group(1) if m else "", "texte": (m.group(2) if m else l).strip()})
        return sortie

    def fil_publier(c, id=0, genre="message", texte="", parent=0):
        compte = h.compte_agit()
        archive_refuse(id)
        texte = str(texte or "").strip()
        if not texte:
            raise ValueError("message vide")
        genre = genre if genre in GENRES_FIL else "message"
        p = h.exiger(id, "lire" if genre == "message" else "ecrire", compte)
        res = {"pid": p["id"], "genre": genre, "notes_avant": None}
        if genre == "journal":
            res["notes_avant"] = p["notes"]
            db.ecrire("UPDATE projets SET notes=?, maj=? WHERE id=?", (h.ajouter_ligne(p["notes"], texte), time.time(), p["id"]))
            res["fid"] = db.ecrire("INSERT INTO pj_fil(projet_id, ts, auteur, genre, texte) VALUES (?,?,?,?,?)", (p["id"], time.time(), compte, "journal", texte[:20000]))
            res.update(mentions=[], itare=False)
            return res
        res["fid"] = db.ecrire("INSERT INTO pj_fil(projet_id, ts, auteur, genre, texte, parent, etat, meta) VALUES (?,?,?,?,?,?,?,?)",
                               (p["id"], time.time(), compte, genre, texte[:20000], int(parent or 0), "ouverte" if genre == "decision" else "", json.dumps({"avis": {}} if genre == "decision" else {})))
        comptes, itare = mentions(p, texte)
        nom = h.noms().get(compte.lower()) or compte
        if genre == "decision":
            prevenir(c, p, "projet.decision", "Décision à prendre — « %s »" % p["nom"], "%s : %s" % (nom, texte[:300]), membres_comptes(p))
        elif comptes:
            prevenir(c, p, "projet.mention", "%s te mentionne — « %s »" % (nom, p["nom"]), texte[:400], comptes)
        if itare:
            c.emettre("projet.itare", objet=("projet", str(p["id"])), donnees={"id": p["id"], "projet": p["nom"], "fil": res["fid"], "question": texte[:2000], "par": compte})
        res.update(mentions=comptes, itare=itare)
        return res

    def prouver_publie(c, res):
        return bool(db.lire("SELECT 1 FROM pj_fil WHERE id=?", (res["fid"],)))

    def defaire_publie(c, res):
        db.ecrire("DELETE FROM pj_fil WHERE id=?", (res["fid"],))
        if res["notes_avant"] is not None:
            db.ecrire("UPDATE projets SET notes=? WHERE id=?", (res["notes_avant"], res["pid"]))

    def modifier_ligne(pid, fid, etat=None, meta=None):
        d = ligne_fil(pid, fid)
        m = meta_de(d)
        if meta:
            m.update(meta)
        db.ecrire("UPDATE pj_fil SET etat=?, meta=? WHERE id=?", (d["etat"] if etat is None else etat, json.dumps(m, ensure_ascii=False), int(fid)))

    def fil_avis(c, id=0, fid=0, avis=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        d = ligne_fil(p["id"], fid)
        if not d or d["genre"] != "decision" or d["etat"] != "ouverte":
            raise ValueError("aucune décision ouverte à ce numéro")
        if avis not in ("pour", "contre", "neutre"):
            raise ValueError("avis : pour, contre ou neutre")
        m = meta_de(d)
        m.setdefault("avis", {})[c.compte.lower()] = avis
        modifier_ligne(p["id"], fid, meta={"avis": m["avis"]})
        return {"pid": p["id"], "fid": int(fid), "avant": d["meta"], "etat_avant": d["etat"], "avis": avis, "compte": c.compte.lower()}

    def prouver_avis(c, res):
        d = ligne_fil(res["pid"], res["fid"])
        return d is not None and meta_de(d).get("avis", {}).get(res["compte"]) == res["avis"]

    def defaire_ligne(c, res):
        db.ecrire("UPDATE pj_fil SET meta=?, etat=? WHERE id=?", (res["avant"], res["etat_avant"], res["fid"]))

    def fil_trancher(c, id=0, fid=0, issue="", raison="", seuil=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        d = ligne_fil(p["id"], fid)
        if not d or d["genre"] != "decision" or d["etat"] != "ouverte":
            raise ValueError("aucune décision ouverte à ce numéro")
        issue = str(issue or "").strip()
        if not issue:
            raise ValueError("dis ce qui est décidé")
        modifier_ligne(p["id"], fid, "decidee", {"issue": issue[:2000], "raison": str(raison or "")[:2000], "seuil": str(seuil or "")[:500], "par": c.compte, "le": time.strftime("%Y-%m-%d %H:%M")})
        prevenir(c, p, "projet.decision", "Décidé — « %s »" % p["nom"], "%s\n→ %s" % (d["texte"][:200], issue[:300]), membres_comptes(p))
        return {"pid": p["id"], "fid": int(fid), "avant": d["meta"], "etat_avant": d["etat"]}

    def prouver_tranche(c, res):
        d = ligne_fil(res["pid"], res["fid"])
        return d is not None and d["etat"] == "decidee"

    def fil_relire(c, id=0, fid=0, action=""):
        p = h.exiger(id, "ecrire", h.compte_agit())
        d = ligne_fil(p["id"], fid)
        if not d or d["genre"] != "relire" or d["etat"] != "attente":
            raise ValueError("rien à relire à ce numéro")
        m = meta_de(d)
        quand_ = {"par": c.compte, "le": time.strftime("%Y-%m-%d %H:%M")}
        res = {"pid": p["id"], "fid": int(fid), "avant": d["meta"], "etat_avant": d["etat"], "action": action, "restaure": None}
        if action == "valider":
            modifier_ligne(p["id"], fid, "valide", quand_)
            return res
        if action == "annuler":
            if m.get("geste") != "ecrire" or not m.get("version"):
                raise ValueError("seule une modification de texte se défait d'un clic ; pour le reste, « Versions »")
            racine = coffre["racine_de"](p)
            from . import CN_coffre as cf
            a = cf.sous(racine, d["ref"])
            actuel = cf.lire_octets(a)
            avant_n = coffre["poser_version"](p["id"], d["ref"], actuel, "avant", "état remplacé par la v%d (annulation)" % int(m["version"]))["n"] if actuel is not None else 0
            coffre["restaurer_octets"](p["id"], d["ref"], int(m["version"]))
            res["restaure"] = {"chemin": d["ref"], "avant_n": avant_n}
            modifier_ligne(p["id"], fid, "annule", quand_)
            return res
        raise ValueError("action : valider ou annuler")

    def prouver_relu(c, res):
        d = ligne_fil(res["pid"], res["fid"])
        return d is not None and d["etat"] in ("valide", "annule")

    def defaire_relu(c, res):
        if res.get("restaure") and res["restaure"]["avant_n"]:
            coffre["restaurer_octets"](res["pid"], res["restaure"]["chemin"], res["restaure"]["avant_n"])
        defaire_ligne(c, res)

    # ------------------------------------------------------------------ commentaires et présence
    def commentaires(c, id=0, chemin=""):
        p = lire_projet(id)
        rows = [dict(r) for r in db.lire("SELECT * FROM pj_commentaires WHERE projet_id=? AND chemin=? ORDER BY ts", (p["id"], str(chemin or "")))]
        for r in rows:
            r["quand"] = horodatage(r["ts"])
        return {"commentaires": rows, "noms": h.noms(), "role": h.role_de(p["id"], c.compte), "moi": c.compte}

    def commenter(c, id=0, chemin="", citation="", texte="", parent=0):
        compte = h.compte_agit()
        archive_refuse(id)
        p = h.exiger(id, "lire", compte)
        texte = str(texte or "").strip()
        if not texte:
            raise ValueError("commentaire vide")
        cid = db.ecrire("INSERT INTO pj_commentaires(projet_id, chemin, citation, auteur, texte, ts, parent) VALUES (?,?,?,?,?,?,?)",
                        (p["id"], str(chemin)[:500], str(citation or "")[:2000], compte, texte[:8000], time.time(), int(parent or 0)))
        comptes, itare = mentions(p, texte)
        nom = h.noms().get(compte.lower()) or compte
        if comptes:
            prevenir(c, p, "projet.mention", "%s te mentionne dans « %s »" % (nom, str(chemin).split("/")[-1]), "« %s »\n%s" % (str(citation or "")[:160], texte[:300]), comptes)
        if itare:
            c.emettre("projet.itare", objet=("projet", str(p["id"])), donnees={"id": p["id"], "projet": p["nom"], "commentaire": cid, "chemin": chemin, "question": texte[:2000], "par": compte})
        return {"pid": p["id"], "cid": cid, "mentions": comptes, "itare": itare}

    def prouver_commente(c, res):
        return bool(db.lire("SELECT 1 FROM pj_commentaires WHERE id=?", (res["cid"],)))

    def defaire_commente(c, res):
        db.ecrire("DELETE FROM pj_commentaires WHERE id=?", (res["cid"],))

    def commentaire_resoudre(c, id=0, cid=0, resolu=True):
        p = h.exiger(id, "ecrire", h.compte_agit())
        r = db.lire("SELECT resolu FROM pj_commentaires WHERE id=? AND projet_id=?", (int(cid or 0), p["id"]))
        if not r:
            raise ValueError("commentaire introuvable")
        v = ("%s · %s" % (c.compte, time.strftime("%Y-%m-%d %H:%M"))) if resolu else ""
        db.ecrire("UPDATE pj_commentaires SET resolu=? WHERE id=?", (v, int(cid)))
        return {"pid": p["id"], "cid": int(cid), "avant": r[0]["resolu"], "resolu": v}

    def prouver_resolu(c, res):
        return db.lire("SELECT resolu FROM pj_commentaires WHERE id=?", (res["cid"],))[0]["resolu"] == res["resolu"]

    def defaire_resolu(c, res):
        db.ecrire("UPDATE pj_commentaires SET resolu=? WHERE id=?", (res["avant"], res["cid"]))

    def presence(c, id=0, chemin=""):
        p = lire_projet(id)
        moi = str(c.compte or "").lower()
        t = time.time()
        with _presence_verrou:
            d = _presence.setdefault(p["id"], {})
            if moi:
                d[moi] = (str(chemin or "")[:500], t)
            for k in [k for k, v in d.items() if t - v[1] > PRESENCE_VIE]:
                d.pop(k, None)
            autres = [{"compte": k, "chemin": v[0]} for k, v in d.items() if k != moi]
        return {"presents": autres, "noms": h.noms()}

    # ------------------------------------------------------------------ cadrage et suites proposées
    def cadrage_proposer(c, id=0, reponses=None):
        p = lire_projet(id)
        reponses = reponses if isinstance(reponses, dict) else {}
        R = {k: str(reponses.get(k, "") or "").strip() for k, _ in CADRAGE_Q}
        props, flou = [], []
        if R["objectif"]:
            props.append({"genre": "entete", "quoi": "Objectif", "apercu": R["objectif"][:160], "valeurs": {"objectif": R["objectif"]}})
        if R["perimetre_out"]:
            ls = lignes(R["perimetre_out"].replace(",", "\n"))
            props.append({"genre": "entete", "quoi": "Hors périmètre — %d point(s)" % len(ls), "apercu": " · ".join(ls)[:160], "valeurs": {"perimetre_out": "\n".join(ls)}})
        if R["reussite"]:
            ls = lignes(R["reussite"].replace(";", "\n"))
            props.append({"genre": "entete", "quoi": "Critères de réussite — %d" % len(ls), "apercu": " · ".join(ls)[:160], "valeurs": {"reussite": "\n".join(ls)}})
        if R["jalon"]:
            d = date_iso(R["jalon"])
            if d:
                nom = re.sub(r"\b(le|pour|avant|d'ici|au)\b", " ", R["jalon"], flags=re.I)
                nom = re.sub(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+\w+\s*\d{0,4}", " ", nom)
                nom = re.sub(r"\s+", " ", nom).strip(" :,-") or "Première échéance"
                props.append({"genre": "jalon", "quoi": "Étape — %s" % d, "apercu": nom, "valeurs": {"date": d, "nom": nom, "etat": "prevu"}})
            else:
                flou.append("Aucune date lisible dans « %s » — l'étape n'est pas posée." % R["jalon"][:70])
        for cle, question in CADRAGE_Q:
            if not R[cle]:
                flou.append("Sans réponse : %s" % question)
        return {"pid": p["id"], "propositions": props, "flou": flou}

    def suites_de(p, c):
        """Trois suites au plus, tirées des faits du projet : rien d'inventé."""
        auj = time.strftime("%Y-%m-%d")
        items = []
        for j in db.lire("SELECT nom, date FROM jalons WHERE projet_id=? AND etat='prevu' AND date<>'' AND date<? ORDER BY date LIMIT 2", (p["id"], auj)):
            items.append("Le jalon « %s » (prévu le %s) est dépassé : le tenir, le reporter ou le déclarer manqué." % (j["nom"], j["date"]))
        for d in db.lire("SELECT question FROM decisions WHERE projet_id=? AND etat='ouverte' ORDER BY id LIMIT 2", (p["id"],)):
            items.append("Trancher : %s" % d["question"][:160])
        n = db.lire("SELECT COUNT(*) n FROM pj_fil WHERE projet_id=? AND genre='relire' AND etat='attente'", (p["id"],))[0]["n"]
        if n:
            items.append("Relire les %d écriture(s) d'Itare en attente dans le fil." % n)
        if not p["objectif"]:
            items.append("Écrire l'objectif du projet (le cadrage le propose en quatre questions).")
        if not p["dossier"]:
            items.append("Créer le dossier du projet pour ouvrir l'Atelier.")
        try:
            tk = (ctx.executer_lecture("taches.lister", projet_id=p["id"], limite=400) or {}).get("taches", [])
            tard = [t for t in tk if t.get("statut") not in ("fait", "abandonnee") and t.get("echeance") and str(t["echeance"])[:10] < auj]
            if tard:
                items.append("Reprendre les %d tâche(s) en retard (la plus ancienne : %s)." % (len(tard), min(str(t["echeance"])[:10] for t in tard)))
        except Exception:
            pass
        return items[:3]

    def proposer(c, id=0):
        p = h.exiger(id, "ecrire", h.compte_agit())
        avant = db.lire("SELECT * FROM pj_propositions WHERE projet_id=?", (p["id"],))
        items = suites_de(p, c)
        db.ecrire("INSERT OR REPLACE INTO pj_propositions(projet_id, jour, quand, items) VALUES (?,?,?,?)", (p["id"], time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d %H:%M"), json.dumps(items, ensure_ascii=False)))
        return {"pid": p["id"], "items": items, "avant": dict(avant[0]) if avant else None}

    def prouver_propose(c, res):
        r = db.lire("SELECT items FROM pj_propositions WHERE projet_id=?", (res["pid"],))
        return bool(r) and json.loads(r[0]["items"]) == res["items"]

    def defaire_propose(c, res):
        db.ecrire("DELETE FROM pj_propositions WHERE projet_id=?", (res["pid"],))
        if res["avant"]:
            a = res["avant"]
            db.ecrire("INSERT INTO pj_propositions(projet_id, jour, quand, items) VALUES (?,?,?,?)", (a["projet_id"], a["jour"], a["quand"], a["items"]))

    # ------------------------------------------------------------------ le navigateur partagé (texte seul, par le module web)
    def nav_de(compte, creer=True):
        with _nav_verrou:
            for k in [k for k, n in _nav.items() if time.time() - n["vu"] > NAV_INACTIF]:
                _nav.pop(k, None)
            n = _nav.get(compte)
            if n is None and creer:
                n = _nav[compte] = {"pile": [], "vu": time.time()}
            if n is not None:
                n["vu"] = time.time()
            return n

    def nav_vue(n):
        cur = n["pile"][-1] if n and n["pile"] else None
        return {"url": cur["url"] if cur else "", "titre": cur["titre"] if cur else "", "pages": len(n["pile"]) if n else 0, "texte": cur["texte"][:12000] if cur else ""}

    def charger(url):
        r = ctx.executer_lecture("web.lire", url=url)
        if not r:
            raise ValueError("lecture impossible : la page est refusée (adresse non publique, port ou type de contenu) ou le module web n'est pas actif")
        return {"url": r["url"], "titre": r.get("titre") or r["url"], "texte": r.get("texte") or ""}

    def nav_aller(c, url=""):
        compte = h.compte_agit()
        url = str(url or "").strip()
        if url and not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
            url = "https://" + url
        if not url:
            raise ValueError("adresse manquante")
        page = charger(url)
        n = nav_de(compte)
        n["pile"].append(page)
        del n["pile"][:-30]
        return nav_vue(n)

    def nav_retour(c):
        n = nav_de(h.compte_agit(), creer=False)
        if not n or len(n["pile"]) < 2:
            raise ValueError("rien avant cette page")
        n["pile"].pop()
        return nav_vue(n)

    def nav_fermer(c):
        compte = h.compte_agit()
        with _nav_verrou:
            _nav.pop(compte, None)
        return {"ferme": True}

    def nav_clipper(c, id=0, dossier="Clips"):
        p = h.exiger(id, "ecrire", h.compte_agit())
        n = nav_de(c.compte, creer=False)
        if not n or not n["pile"]:
            raise ValueError("aucune page ouverte à ranger")
        pg = n["pile"][-1]
        titre = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]+', " ", pg["titre"] or "Page")).strip()[:90] or "Page"
        d = str(dossier or "Clips").strip().strip("/") or "Clips"
        corps = ("---\nsource: %s\ntitre: \"%s\"\nclip: %s\n---\n\n# %s\n\n> Source : <%s>\n\n%s\n" % (pg["url"], titre.replace('"', "'"), time.strftime("%Y-%m-%d %H:%M"), titre, pg["url"], pg["texte"]))
        racine = coffre["racine_de"](p)
        from . import CN_coffre as cf
        (cf.sous(racine, d)).mkdir(parents=True, exist_ok=True)
        for k in range(1, 9):
            ch = "%s/%s%s.md" % (d, titre, "" if k == 1 else " (%d)" % k)
            try:
                w = coffre["ecrire_interne"](c, p, ch, corps, "", True)
            except ValueError as e:
                if "existe déjà" in str(e):
                    continue
                raise
            coffre["tracer"](c, p, w["chemin"], "ecrire", None)
            return dict(w, titre=titre, url=pg["url"], octets=len(corps))
        raise ValueError("trop de clips du même nom dans %s" % d)

    def prouver_clip(c, res):
        return (coffre["racine_de"](h.entete(res["pid"])) / res["chemin"]).is_file()

    def defaire_clip(c, res):
        a = coffre["racine_de"](h.entete(res["pid"])) / res["chemin"]
        if a.is_file():
            a.unlink()

    # ------------------------------------------------------------------ inscription
    for cid, f in (("courrier", courrier), ("atelier_sources", atelier_sources), ("fil", fil), ("commentaires", commentaires), ("presence", presence), ("cadrage_proposer", cadrage_proposer)):
        ctx.implementer(cid, f)
    ctx.implementer("courrier_ranger", courrier_ranger, prouver_range, defaire_range, simuler=lambda x, id="", **_: "rangerait un fil de courrier dans le projet %s" % id)
    ctx.implementer("fil_publier", fil_publier, prouver_publie, defaire_publie, simuler=lambda x, id="", **_: "publierait dans le fil du projet %s" % id)
    ctx.implementer("fil_avis", fil_avis, prouver_avis, defaire_ligne, simuler=lambda x, id="", **_: "donnerait un avis sur une décision du projet %s" % id)
    ctx.implementer("fil_trancher", fil_trancher, prouver_tranche, defaire_ligne, simuler=lambda x, id="", **_: "trancherait une décision du projet %s" % id)
    ctx.implementer("fil_relire", fil_relire, prouver_relu, defaire_relu, simuler=lambda x, id="", **_: "validerait ou annulerait une écriture à relire du projet %s" % id)
    ctx.implementer("commenter", commenter, prouver_commente, defaire_commente, simuler=lambda x, id="", **_: "commenterait un passage du projet %s" % id)
    ctx.implementer("commentaire_resoudre", commentaire_resoudre, prouver_resolu, defaire_resolu, simuler=lambda x, id="", **_: "résoudrait un commentaire du projet %s" % id)
    ctx.implementer("proposer", proposer, prouver_propose, defaire_propose, simuler=lambda x, id="", **_: "calculerait les suites proposées du projet %s" % id)
    ctx.implementer("nav_aller", nav_aller, lambda c, res: bool(res.get("url")), lambda c, res: nav_retour(c) if res.get("pages", 0) > 1 else nav_fermer(c), simuler=lambda x, url="", **_: "ouvrirait %s" % url)
    ctx.implementer("nav_retour", nav_retour, lambda c, res: True, lambda c, res: None, simuler=lambda x, **_: "reviendrait à la page d'avant")
    ctx.implementer("nav_fermer", nav_fermer, lambda c, res: True, lambda c, res: None, simuler=lambda x, **_: "fermerait le navigateur")
    ctx.implementer("nav_clipper", nav_clipper, prouver_clip, defaire_clip, simuler=lambda x, id="", **_: "rangerait la page ouverte dans le dossier du projet %s" % id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
