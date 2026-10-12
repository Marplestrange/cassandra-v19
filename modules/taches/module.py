"""Les tâches.

Porté de la V18 (`itare_task_*`, `itare_task_from_source`), avec ses leçons :
  - une tâche est à la PERSONNE, pas au projet : supprimer un projet ne l'emporte pas (effacer ce qu'elle a encore à faire serait pire que le désordre) ;
  - abandonner exige une RAISON, gardée au journal : « dis pourquoi on l'abandonne » ;
  - une tâche récurrente cochée recrée l'occurrence suivante en repartant de l'échéance PRÉCÉDENTE, pas d'aujourd'hui : la cocher un vendredi quand elle
    était due le lundi ne doit pas décaler tout le rythme ;
  - le nombre de REPORTS compte : une échéance qu'on repousse sans cesse dit quelque chose ;
  - avancer une tâche « à faire » la passe « en cours » ; la terminer la met à 100 % ;
  - chaque mouvement laisse une ligne au journal de la tâche (ouverte, passée en..., reportée du... au..., confiée à...) ;
  - le responsable est « moi », « Itare » ou un MEMBRE du projet : on ne confie rien à un étranger ;
  - une tâche née d'une détection garde sa provenance, et une détection ne crée plus de tâche d'elle-même (LOT 4 de la V18) : elle sonne, la tâche naît du geste
    « en faire une tâche » — et ne naît qu'une fois pour la même origine ;
  - l'avancement d'un projet est pondéré par la CHARGE des tâches (trois broutilles faites ne valent pas la moitié d'un projet dont le gros n'a pas commencé).
Confier une tâche à Itare ne lance plus un fil en arrière-plan : l'événement `tache.confiee` le dit, c'est Itare (son module) qui s'en saisit.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

STATUTS = ("todo", "en cours", "en attente", "fait", "abandonnee")
FERMES = ("fait", "abandonnee")
PRIORITES = ("basse", "normale", "haute", "urgente")
LIENS = ("note", "mail", "url", "project", "contact", "event", "domain", "server", "certificate", "finding")
RECURRENCES = {"weekly": 7, "biweekly": 14, "monthly": 30, "quarterly": 91, "yearly": 365}
DIT_STATUT = {"todo": "à faire", "en cours": "en cours", "en attente": "en attente", "fait": "faite", "abandonnee": "abandonnée"}
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
PROVENANCES = {
    "auto-ssl": ("🔒", "Détectée par Cassandra — certificat proche de l'échéance"),
    "auto-cron": ("⚙️", "Détectée par Cassandra — tâche planifiée muette"),
    "auto-relance": ("👤", "Détectée par Cassandra — contact sans réponse"),
    "constat": ("🔔", "Née d'un constat"),
    "mail": ("📧", "Née d'un message"),
    "événement": ("📅", "Préparation d'un événement"),
}


def lire_echeance(s):
    """'+30m' '+2h' '+3d' ; 'AAAA-MM-JJ HH:MM' ; 'AAAA-MM-JJTHH:MM' ; 'AAAA-MM-JJ' (à 9 h). -> 'AAAA-MM-JJ HH:MM' ou '' ; lève si illisible."""
    s = str(s or "").strip()
    if not s:
        return ""
    m = re.match(r"^\+(\d+)\s*(min|m|h|d|j)$", s, re.I)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        return (datetime.now() + timedelta(minutes={"m": n, "min": n, "h": n * 60, "d": n * 1440, "j": n * 1440}[u])).strftime("%Y-%m-%d %H:%M")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return (d.replace(hour=9, minute=0) if fmt == "%Y-%m-%d" else d).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    raise ValueError("échéance illisible « %s » (AAAA-MM-JJ, AAAA-MM-JJ HH:MM, +3d, +2h, +30m)" % s)


def provenance(t):
    src, ref = (t.get("source") or "manuel").strip(), (t.get("origine") or "").strip()
    quand = datetime.fromtimestamp(t["cree"]).strftime("%Y-%m-%d %H:%M") if t.get("cree") else ""
    if src in ("", "manuel"):
        return {"kind": "manuel", "texte": "Saisie à la main", "quand": quand}
    ic, txt = PROVENANCES.get(src, ("✨", "Créée par « %s »" % src))
    return {"kind": src, "icone": ic, "texte": txt, "ref": ref, "quand": quand}


def brancher(ctx):
    db = ctx.stockage

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("une tâche est celle d'un compte : aucun compte n'agit")
        return c

    # ------------------------------------------------------------------ le projet, lu pour le compte qui agit
    def equipe(pid):
        """{mon_role, proprietaire, membres} du projet, ou None s'il n'est pas visible de ce compte (ou si le module des projets est absent)."""
        try:
            return ctx.executer_lecture("projets.equipe", id=int(pid))
        except Exception:
            return None

    def peut_ecrire(pid):
        e = equipe(pid)
        return bool(e) and e.get("mon_role") in ("proprietaire", "coproprietaire", "auteur")

    def peut_lire(pid):
        e = equipe(pid)
        return bool(e) and e.get("mon_role") in ("proprietaire", "coproprietaire", "auteur", "lecteur")

    def responsable_ok(pid, responsable, compte):
        """« itare », soi-même, ou (dans un projet) le propriétaire ou un membre actif."""
        r = str(responsable or "").strip().lower()
        if r in ("", "itare", compte):
            return True
        if not pid:
            return False
        e = equipe(pid) or {}
        return r == e.get("proprietaire") or any(m["compte"] == r and m["etat"] == "actif" for m in e.get("membres", []))

    # ------------------------------------------------------------------ accès
    def tache_brute(tid):
        try:
            r = db.lire("SELECT * FROM taches WHERE id=?", (int(tid),))
        except (TypeError, ValueError):
            return None
        return r[0] if r else None

    def accessible(t, compte, ecriture=False):
        if t is None:
            return False
        if t["compte"] == compte:
            return True
        return bool(t["projet_id"]) and (peut_ecrire(t["projet_id"]) if ecriture else peut_lire(t["projet_id"]))

    def exiger(tid, compte, ecriture=False):
        t = tache_brute(tid)
        if not accessible(t, compte, ecriture):
            raise ValueError("tâche introuvable")
        return t

    def noter(tid, texte, acteur=""):
        db.ecrire("INSERT INTO journal(tache_id, texte, acteur, ts) VALUES (?,?,?,?)", (int(tid), str(texte or "")[:300], str(acteur or "")[:80], time.time()))

    def instantane(tid):
        t = tache_brute(tid)
        sous = [r["id"] for r in db.lire("SELECT id FROM taches WHERE parent_id=?", (t["id"],))]
        return {"tache": dict(t), "liens": [dict(r) for r in db.lire("SELECT * FROM liens WHERE tache_id=?", (t["id"],))],
                "journal": [dict(r) for r in db.lire("SELECT * FROM journal WHERE tache_id=?", (t["id"],))], "sous": [instantane(s) for s in sous]}

    def reposer(snap):
        t = snap["tache"]
        with db.transaction() as cx:
            cols = list(t)
            cx.execute("INSERT OR REPLACE INTO taches(%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))), [t[k] for k in cols])
            for l in snap["liens"]:
                ks = list(l)
                cx.execute("INSERT OR REPLACE INTO liens(%s) VALUES (%s)" % (",".join(ks), ",".join("?" * len(ks))), [l[k] for k in ks])
            for j in snap["journal"]:
                ks = list(j)
                cx.execute("INSERT OR REPLACE INTO journal(%s) VALUES (%s)" % (",".join(ks), ",".join("?" * len(ks))), [j[k] for k in ks])
        for s in snap["sous"]:
            reposer(s)

    def effacer(tid):
        for r in db.lire("SELECT id FROM taches WHERE parent_id=?", (int(tid),)):
            effacer(r["id"])
        with db.transaction() as cx:
            for t in ("liens", "journal"):
                cx.execute("DELETE FROM %s WHERE tache_id=?" % t, (int(tid),))
            cx.execute("DELETE FROM taches WHERE id=?", (int(tid),))

    # ------------------------------------------------------------------ lectures
    def lister(c, projet_id=None, inclure_faites=False, limite=200, racines_seules=False):
        compte = compte_agit()
        sql = ("SELECT t.*, (SELECT COUNT(*) FROM taches s WHERE s.parent_id=t.id) AS nb_sous, (SELECT COUNT(*) FROM taches s WHERE s.parent_id=t.id AND s.statut='fait') AS nb_sous_faites "
               "FROM taches t WHERE ")
        args = []
        if projet_id is not None:
            if not peut_lire(projet_id) and not db.lire("SELECT 1 FROM taches WHERE projet_id=? AND compte=? LIMIT 1", (int(projet_id), compte)):
                raise ValueError("projet introuvable")
            sql += "t.projet_id=? AND (t.compte=? OR ?)"
            args += [int(projet_id), compte, 1 if peut_lire(projet_id) else 0]
        else:
            sql += "t.compte=?"
            args.append(compte)
        if not inclure_faites:
            sql += " AND t.statut NOT IN ('fait','abandonnee')"
        if racines_seules:
            sql += " AND t.parent_id IS NULL"
        sql += " ORDER BY (t.echeance=''), t.echeance, t.id DESC LIMIT ?"
        args.append(max(1, min(int(limite or 200), 1000)))
        try:
            noms = {p["id"]: p["nom"] for p in (ctx.executer_lecture("projets.lister") or {}).get("projets", [])}
        except Exception:
            noms = {}
        return {"taches": [dict(r, projet=noms.get(r["projet_id"], "")) for r in db.lire(sql, args)]}

    def fiche(c, id=0):
        compte = compte_agit()
        t = exiger(id, compte)
        return {"tache": dict(t), "sous": [dict(r) for r in db.lire("SELECT id, texte, statut, echeance FROM taches WHERE parent_id=? ORDER BY (statut='fait'), id", (t["id"],))],
                "liens": [dict(r) for r in db.lire("SELECT kind, ref, label FROM liens WHERE tache_id=? ORDER BY kind", (t["id"],))],
                "journal": [dict(r) for r in db.lire("SELECT texte, acteur, ts FROM journal WHERE tache_id=? ORDER BY id DESC LIMIT 12", (t["id"],))], "provenance": provenance(dict(t))}

    def avancement(c, projet_id=0):
        compte = compte_agit()
        if not peut_lire(projet_id):
            raise ValueError("projet introuvable")
        rows = db.lire("SELECT statut, charge FROM taches WHERE projet_id=? AND statut<>'abandonnee'", (int(projet_id),))
        poids = lambda x: max(int(x["charge"] or 0), 1)
        total = sum(poids(r) for r in rows)
        fait = sum(poids(r) for r in rows if r["statut"] == "fait")
        return {"global": int(round(fait * 100.0 / total)) if total else 0, "fait": fait, "total": total, "mesure": "taches" if total else "",
                "detail": ("%d sur %d (tâches, pondérées par leur charge)" % (fait, total)) if total else ""}

    def det_retard(c):
        maintenant = time.strftime("%Y-%m-%d %H:%M")
        return [{"objet": ("tache", str(r["id"])), "compte": r["compte"], "titre": "Tâche en retard : %s" % r["texte"][:80],
                 "detail": "échue le %s%s" % (r["echeance"][:16], (" — repoussée %d fois" % r["reports"]) if r["reports"] >= 2 else "")}
                for r in db.lire("SELECT id, compte, texte, echeance, reports FROM taches WHERE statut NOT IN ('fait','abandonnee') AND echeance<>'' AND echeance<?", (maintenant,))]

    # ------------------------------------------------------------------ créer
    def valeur_priorite(p):
        if p is None:
            return 1
        if isinstance(p, str) and p.strip().lower() in PRIORITES:
            return PRIORITES.index(p.strip().lower())
        try:
            n = int(p)
        except (TypeError, ValueError):
            raise ValueError("priorité : %s" % " | ".join(PRIORITES))
        if not 0 <= n < len(PRIORITES):
            raise ValueError("priorité : %s" % " | ".join(PRIORITES))
        return n

    def creer(c, texte="", projet_id=None, echeance=None, priorite=None, notes="", parent_id=None, recurrence="", charge=0, alarme="", responsable="", source="manuel", origine="", etape_id=None,
              avancement=0):
        compte = compte_agit()
        texte = str(texte or "").strip()[:500]
        if not texte:
            raise ValueError("texte requis")
        if projet_id and not peut_ecrire(projet_id):
            raise ValueError("projet introuvable, ou ton rôle ne permet pas d'y écrire")
        resp = str(responsable or "").strip().lower()
        if resp and not responsable_ok(projet_id, resp, compte):
            raise ValueError("« %s » n'est pas membre de ce projet" % resp)
        rec = str(recurrence or "").strip().lower()
        if rec and rec not in RECURRENCES:
            raise ValueError("récurrence : %s" % " | ".join(RECURRENCES))
        if parent_id and not db.lire("SELECT 1 FROM taches WHERE id=? AND compte=?", (int(parent_id), compte)):
            raise ValueError("tâche parente introuvable")
        source, origine = str(source or "manuel")[:40], str(origine or "")[:200]
        if origine and source != "manuel" and db.lire("SELECT id FROM taches WHERE compte=? AND source=? AND origine=?", (compte, source, origine)):
            raise ValueError("cette détection est déjà devenue une tâche")
        ech = lire_echeance(echeance)
        tid = db.ecrire("INSERT INTO taches(compte, projet_id, texte, echeance, cree, source, origine, notes, priorite, parent_id, recurrence, charge, alarme, avancement, responsable, etape_id) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (compte, int(projet_id) if projet_id else None, texte, ech, time.time(), source, origine, str(notes or "")[:4000], valeur_priorite(priorite),
                         int(parent_id) if parent_id else None, rec, max(0, int(charge or 0)), str(alarme or "")[:60], max(0, min(100, int(avancement or 0))), resp, etape_id))
        noter(tid, "Ouverte" + (" — confiée à %s" % ("Itare" if resp == "itare" else resp) if resp else ""), compte)
        c.emettre("tache.creee", objet=("tache", str(tid)), donnees={"id": tid, "projet": projet_id})
        if resp == "itare":
            c.emettre("tache.confiee", objet=("tache", str(tid)), donnees={"id": tid, "a": "itare", "par": compte})
        return {"id": tid, "compte": compte, "texte": texte}

    def prouver_creee(c, res):
        t = tache_brute(res["id"])
        return t is not None and t["texte"] == res["texte"] and t["compte"] == res["compte"]

    def defaire_creee(c, res):
        effacer(res["id"])

    # ------------------------------------------------------------------ modifier
    def modifier(c, id=0, texte=None, statut=None, echeance=None, projet_id=None, priorite=None, notes=None, parent_id=None, recurrence=None, charge=None, alarme=None, avancement=None,
                 raison=None, responsable=None, etape_id=None):
        compte = compte_agit()
        t = exiger(id, compte, ecriture=True)
        avant = dict(t)
        statut = None if statut is None else str(statut).strip().lower()
        if statut is not None and statut not in STATUTS:
            raise ValueError("statut : %s" % " | ".join(STATUTS))
        nouveau_statut = statut or t["statut"]
        if not statut and avancement is not None and t["statut"] == "todo" and int(avancement or 0) > 0:
            nouveau_statut = "en cours"                    # on a avancé : elle est en cours
        raison_v = t["raison"] if raison is None else str(raison).strip()[:500]
        if nouveau_statut == "abandonnee" and not raison_v:
            raise ValueError("dis pourquoi on l'abandonne (gardé dans l'historique)")
        ech = t["echeance"] if echeance is None else lire_echeance(echeance)
        reports = t["reports"] + (1 if (echeance is not None and ech and t["echeance"] and ech[:10] > t["echeance"][:10]) else 0)
        resp = t["responsable"] if responsable is None else str(responsable).strip().lower()
        pid = t["projet_id"] if projet_id is None else (int(projet_id) or None)
        if projet_id is not None and pid and pid != t["projet_id"] and not peut_ecrire(pid):
            raise ValueError("projet introuvable, ou ton rôle ne permet pas d'y écrire")
        if responsable is not None and resp and not responsable_ok(pid, resp, compte):
            raise ValueError("« %s » n'est pas membre de ce projet" % resp)
        rec = t["recurrence"] if recurrence is None else str(recurrence).strip().lower()
        if rec and rec not in RECURRENCES:
            raise ValueError("récurrence : %s" % " | ".join(RECURRENCES))
        av = 100 if nouveau_statut == "fait" else max(0, min(100, int(t["avancement"] if avancement is None else avancement or 0)))
        fait_le = t["fait_le"] if nouveau_statut == "fait" and t["fait_le"] else (time.time() if nouveau_statut == "fait" else None)
        maj = {"texte": (str(texte).strip()[:500] or t["texte"]) if texte is not None else t["texte"], "statut": nouveau_statut, "echeance": ech, "projet_id": pid, "priorite": t["priorite"] if priorite is None else valeur_priorite(priorite),
               "notes": t["notes"] if notes is None else str(notes)[:4000], "parent_id": t["parent_id"] if parent_id is None else (int(parent_id) or None), "recurrence": rec,
               "charge": t["charge"] if charge is None else max(0, int(charge or 0)), "alarme": t["alarme"] if alarme is None else str(alarme)[:60], "avancement": av, "raison": raison_v,
               "responsable": resp, "etape_id": t["etape_id"] if etape_id is None else etape_id, "reports": reports, "fait_le": fait_le}
        db.ecrire("UPDATE taches SET %s WHERE id=?" % ",".join("%s=?" % k for k in maj), list(maj.values()) + [t["id"]])
        if nouveau_statut != t["statut"]:
            if nouveau_statut == "abandonnee":
                noter(t["id"], "Abandonnée : « %s »" % raison_v, compte)
            elif t["statut"] in FERMES and nouveau_statut not in FERMES:
                noter(t["id"], "Rouverte", compte)
            else:
                noter(t["id"], "Passée « %s »" % DIT_STATUT.get(nouveau_statut, nouveau_statut), compte)
        if echeance is not None and ech != t["echeance"]:
            noter(t["id"], ("Reportée du %s au %s" % (t["echeance"][:10], ech[:10])) if (ech and t["echeance"]) else ("Échéance : %s" % ech[:10]) if ech else "Échéance retirée", compte)
        if avancement is not None and av != t["avancement"] and nouveau_statut != "fait":
            noter(t["id"], "Avancement %d %%" % av, compte)
        if responsable is not None and resp != t["responsable"]:
            noter(t["id"], ("Confiée à %s" % ("Itare" if resp == "itare" else resp)) if resp else "Plus de responsable", compte)
            if resp == "itare" and nouveau_statut not in FERMES:
                c.emettre("tache.confiee", objet=("tache", str(t["id"])), donnees={"id": t["id"], "a": "itare", "par": compte})
        suivante = None
        if nouveau_statut == "fait" and t["statut"] != "fait":
            c.emettre("tache.terminee", objet=("tache", str(t["id"])), donnees={"id": t["id"]})
            suivante = occurrence_suivante(t, compte)
        return {"id": t["id"], "compte": compte, "avant": avant, "maj": maj, "suivante": suivante}

    def occurrence_suivante(t, compte):
        """L'échéance repart de la PRÉCÉDENTE, pas d'aujourd'hui."""
        jours = RECURRENCES.get((t["recurrence"] or "").strip().lower())
        if not jours:
            return None
        base = (t["echeance"] or "")[:10] or datetime.now().strftime("%Y-%m-%d")
        try:
            d = datetime.strptime(base, "%Y-%m-%d") + timedelta(days=jours)
        except ValueError:
            d = datetime.now() + timedelta(days=jours)
        heure = (t["echeance"] or "")[11:16] or "09:00"
        nid = db.ecrire("INSERT INTO taches(compte, projet_id, texte, echeance, cree, source, origine, notes, priorite, recurrence, charge, alarme, responsable) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (t["compte"], t["projet_id"], t["texte"], d.strftime("%Y-%m-%d") + " " + heure, time.time(), t["source"], "", t["notes"], t["priorite"], t["recurrence"], t["charge"], t["alarme"], t["responsable"]))
        noter(nid, "Occurrence suivante de « %s »" % t["texte"][:60], compte)
        noter(t["id"], "Terminée — prochaine occurrence le %s" % d.strftime("%Y-%m-%d"), compte)
        return {"id": nid, "echeance": d.strftime("%Y-%m-%d") + " " + heure}

    def prouver_modifiee(c, res):
        t = tache_brute(res["id"])
        return t is not None and all(t[k] == v for k, v in res["maj"].items() if k != "fait_le")

    def defaire_modifiee(c, res):
        if res.get("suivante"):
            effacer(res["suivante"]["id"])
        a = res["avant"]
        db.ecrire("UPDATE taches SET %s WHERE id=?" % ",".join("%s=?" % k for k in a if k != "id"), [a[k] for k in a if k != "id"] + [a["id"]])
        noter(a["id"], "Retour arrière", "")

    # ------------------------------------------------------------------ supprimer
    def supprimer(c, id=0):
        compte = compte_agit()
        t = exiger(id, compte, ecriture=True)
        snap = instantane(t["id"])
        effacer(t["id"])
        return {"id": t["id"], "compte": compte, "copie": snap}

    def prouver_supprimee(c, res):
        return tache_brute(res["id"]) is None

    def defaire_supprimee(c, res):
        reposer(res["copie"])

    # ------------------------------------------------------------------ liens
    def lier(c, id=0, kind="", ref="", label=""):
        compte = compte_agit()
        t = exiger(id, compte, ecriture=True)
        kind, ref = str(kind or "").strip().lower(), str(ref or "").strip()
        if kind not in LIENS:
            raise ValueError("type inconnu (%s)" % ", ".join(LIENS))
        if not ref:
            raise ValueError("référence requise")
        if kind == "domain":
            ref = re.sub(r"^[a-z]+://", "", ref.lower()).split("/")[0]
            ref = ref[4:] if ref.startswith("www.") else ref
        existait = bool(db.lire("SELECT 1 FROM liens WHERE tache_id=? AND kind=? AND ref=?", (t["id"], kind, ref)))
        if not existait:
            db.ecrire("INSERT INTO liens(tache_id, kind, ref, label, cree) VALUES (?,?,?,?,?)", (t["id"], kind, ref, str(label or "")[:200], time.time()))
            noter(t["id"], "Rattachée — %s « %s »" % (kind, (label or ref)[:70]), compte)
        return {"id": t["id"], "kind": kind, "ref": ref, "existait": existait}

    def prouver_lie(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE tache_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"])))

    def defaire_lie(c, res):
        if not res["existait"]:
            db.ecrire("DELETE FROM liens WHERE tache_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))

    def delier(c, id=0, kind="", ref=""):
        compte = compte_agit()
        t = exiger(id, compte, ecriture=True)
        kind, ref = str(kind or "").strip().lower(), str(ref or "").strip()
        avant = db.lire("SELECT * FROM liens WHERE tache_id=? AND kind=? AND ref=?", (t["id"], kind, ref))
        if not avant:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE tache_id=? AND kind=? AND ref=?", (t["id"], kind, ref))
        return {"id": t["id"], "kind": kind, "ref": ref, "avant": dict(avant[0])}

    def prouver_delie(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE tache_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))

    def defaire_delie(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO liens(id, tache_id, kind, ref, label, cree) VALUES (?,?,?,?,?,?)", (a["id"], a["tache_id"], a["kind"], a["ref"], a["label"], a["cree"]))

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.detecteur("en_retard", det_retard)
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
        """Les tâches ouvertes qui brûlent (échéance dépassée) ou tombent aujourd'hui."""
        out = []
        for t in lister(c, limite=400)["taches"]:
            j = jours_de(t.get("echeance"))
            if j is None:
                continue
            pj = t.get("projet") or ""
            if j < 0:
                out.append(item_jour("brule", "tache", t["texte"], "En retard de %d jour(s).%s" % (-j, (" — " + pj) if pj else ""), "tache", t["id"], 90 - j, "proj"))
            elif j == 0:
                out.append(item_jour("jour", "tache", t["texte"], pj or "échéance du jour", "tache", t["id"], 35, "proj"))
        return {"items": out}

    for cid, f in (("lister", lister), ("fiche", fiche), ("avancement", avancement), ("signal_jour", signal_jour)):
        c.implementer(cid, f)
    c.implementer("creer", creer, prouver_creee, defaire_creee, simuler=lambda x, texte="", **_: "créerait la tâche « %s »" % texte)
    c.implementer("modifier", modifier, prouver_modifiee, defaire_modifiee, simuler=lambda x, id="", **_: "modifierait la tâche %s" % id)
    c.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee, simuler=lambda x, id="", **_: "supprimerait la tâche %s avec ses sous-tâches" % id)
    c.implementer("lier", lier, prouver_lie, defaire_lie, simuler=lambda x, id="", kind="", ref="", **_: "rattacherait la tâche %s à %s %s" % (id, kind, ref))
    c.implementer("delier", delier, prouver_delie, defaire_delie, simuler=lambda x, id="", kind="", ref="", **_: "détacherait la tâche %s de %s %s" % (id, kind, ref))
