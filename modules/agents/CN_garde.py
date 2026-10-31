# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La garde des agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.3.0  #1a501c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La garde des agents : la sentinelle anti-fuite (empreintes des secrets), le Relecteur qui retient une réponse, et les épreuves de sûreté d'un modèle.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=1a501c ▼▼▼
"""La garde des agents.

  - Sentinelle : le module ne garde des secrets connus que leur EMPREINTE (HMAC sous une clé propre à l'instance) et leur longueur — jamais la valeur. On l'apprend d'un secret
    (`sentinelle_apprendre`, la valeur est masquée au journal et ne ressort nulle part) ; on peut l'oublier. Aucun agent n'a ces capacités.
  - Relecteur : avant qu'une réponse parte, il la compare aux empreintes et cherche un ordre caché ; il retient la réponse et n'en garde que les MOTIFS.
  - Épreuves : huit situations piégées jouées contre un modèle en MODE ESSAI ; un modèle qui échoue est déconseillé (et écarté si le réglage `epreuves_exigees` est posé).
"""
from __future__ import annotations

import json
import re
import secrets
from types import SimpleNamespace

from . import CN_epreuves as ep
from . import CN_equipe as eq
from . import CN_relecteur as rl

ETIQUETTE_OK = re.compile(r"^[a-z0-9_.:\-]{1,60}$")


def brancher_garde(ctx, E, o, lecture, reglage):
    db = ctx.stockage
    def now():
        return eq.maintenant()

    def compte_agit():
        c = ctx.compte
        if not c or c in eq.SYSTEME:
            raise ValueError("la garde est celle d'un compte : aucun compte n'agit")
        return c

    def exiger_admin():
        compte = compte_agit()
        if not E.admin(compte):
            raise PermissionError("la garde des agents se règle depuis l'administration")
        return compte

    # ------------------------------------------------------------------ sentinelle
    def cle_hmac():
        r = db.lire("SELECT cle FROM sentinelle_cle WHERE id=1")
        if r:
            return r[0]["cle"]
        cle = secrets.token_hex(32)
        db.ecrire("INSERT OR IGNORE INTO sentinelle_cle(id, cle) VALUES (1, ?)", (cle,))
        return db.lire("SELECT cle FROM sentinelle_cle WHERE id=1")[0]["cle"]

    def connus():
        return rl.index(db.lire("SELECT etiquette, empreinte, longueur FROM sentinelle"))

    def sentinelle_apprendre(c, etiquette="", valeur=""):
        exiger_admin()
        etiquette = str(etiquette or "").strip().lower()
        valeur = str(valeur or "")
        if not ETIQUETTE_OK.match(etiquette):
            raise ValueError("etiquette : 1 à 60 signes parmi a-z 0-9 _ . : -")
        if len(valeur) < rl.LONGUEUR_MIN:
            raise ValueError("un secret de moins de %d signes ne se reconnaît pas par une empreinte" % rl.LONGUEUR_MIN)
        avant = db.lire("SELECT * FROM sentinelle WHERE etiquette=?", (etiquette,))
        db.ecrire("INSERT OR REPLACE INTO sentinelle(etiquette, empreinte, longueur, ajoutee) VALUES (?,?,?,?)", (etiquette, rl.empreinte(cle_hmac(), valeur), len(valeur), now()))
        return {"etiquette": etiquette, "longueur": len(valeur), "avant": avant[0] if avant else None}

    def prouver_apprise(c, res):
        r = db.lire("SELECT longueur FROM sentinelle WHERE etiquette=?", (res["etiquette"],))
        return bool(r) and r[0]["longueur"] == res["longueur"]

    def defaire_apprise(c, res):
        a = res["avant"]
        if a is None:
            db.ecrire("DELETE FROM sentinelle WHERE etiquette=?", (res["etiquette"],))
        else:
            db.ecrire("INSERT OR REPLACE INTO sentinelle(etiquette, empreinte, longueur, ajoutee) VALUES (?,?,?,?)", (a["etiquette"], a["empreinte"], a["longueur"], a["ajoutee"]))

    def sentinelle_oublier(c, etiquette=""):
        exiger_admin()
        etiquette = str(etiquette or "").strip().lower()
        avant = db.lire("SELECT * FROM sentinelle WHERE etiquette=?", (etiquette,))
        if not avant:
            raise ValueError("secret inconnu de la sentinelle : %s" % etiquette)
        db.ecrire("DELETE FROM sentinelle WHERE etiquette=?", (etiquette,))
        return {"etiquette": etiquette, "avant": avant[0]}

    def prouver_oubliee(c, res):
        return not db.lire("SELECT 1 FROM sentinelle WHERE etiquette=?", (res["etiquette"],))

    def defaire_oubliee(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO sentinelle(etiquette, empreinte, longueur, ajoutee) VALUES (?,?,?,?)", (a["etiquette"], a["empreinte"], a["longueur"], a["ajoutee"]))

    def sentinelle_etat(c):
        exiger_admin()
        return {"secrets": [{"etiquette": r["etiquette"], "longueur": r["longueur"], "ajoutee": r["ajoutee"]} for r in db.lire("SELECT etiquette, longueur, ajoutee FROM sentinelle ORDER BY etiquette")],
                "relectures_retenues": db.lire("SELECT COUNT(*) AS n FROM relectures WHERE verdict='retenue'")[0]["n"]}

    # ------------------------------------------------------------------ le Relecteur
    def relire_reponse(texte, agent, compte, conversation_id=0, tour=0):
        """Le verdict du Relecteur sur une réponse AVANT qu'elle parte : {verdict, motifs, remarques}. Retenue : on ne garde que les motifs."""
        regles = eq.DONNEES.get("services", {}).get("relecteur", {})
        try:
            v = rl.relire(texte, cle_hmac(), connus(), regles)
        except Exception:                                   # un relecteur en panne ne fait pas parler une réponse suspecte : sans verdict, elle est retenue
            v = {"verdict": "retenue", "motifs": ["relecture_impossible"], "remarques": []}
        if v["verdict"] == "retenue":
            try:
                db.ecrire("INSERT INTO relectures(agent, compte, conversation_id, tour, verdict, motifs, ts) VALUES (?,?,?,?,?,?,?)", (agent, compte, int(conversation_id), int(tour), "retenue", json.dumps(v["motifs"]), now()))
            except Exception:
                pass
        return v

    # ------------------------------------------------------------------ les épreuves
    def dernier_run(modele):
        r = db.lire("SELECT * FROM epreuves_runs WHERE modele=? ORDER BY id DESC LIMIT 1", (modele,))
        return r[0] if r else None

    def cas_du_run(run):
        titres = {c["id"]: c["titre"] for c in ep.CORPUS["cas"]}
        return [{"id": r["cas"], "titre": titres.get(r["cas"], r["cas"]), "reussi": bool(r["reussi"]), "detail": r["detail"]} for r in db.lire("SELECT * FROM epreuves_cas WHERE run_id=? ORDER BY rowid", (run["id"],))]

    def forme(run):
        return {"modele": run["modele"], "run": run["id"], "quand": run["ts"], "ok": bool(run["ok"]), "reussies": run["reussies"], "total": run["total"], "sert": bool(run["ok"]), "deconseille": not run["ok"], "cas": cas_du_run(run)}

    def epreuves_lancer(c, modele=""):
        compte = exiger_admin()
        modele = str(modele or "").strip()
        if not modele or not eq.MODELE_OK.match(modele):
            raise ValueError("modele : le nom d'un rôle ou d'un modèle (lettres, chiffres, _ . : / -)")

        def appeler(role, messages, systeme, outils):
            return lecture("modeles.completer", messages=messages, systeme=systeme, max_tokens=900, role=role, outils=outils, allow_reasoning=True, timeout=90.0, temperature=0.2) or {"ok": False, "erreur": "aucune réponse"}

        def agir_essai(cle, args):
            return ctx.agir(cle, args, acteur="itare", essai=True)           # MODE ESSAI : l'exécuteur simule, il ne fait rien

        resultats = [ep.derouler(cas, appeler, modele, o.coherents, agir_essai) for cas in ep.CORPUS["cas"]]
        ok = all(r["reussi"] for r in resultats)
        rid = db.ecrire("INSERT INTO epreuves_runs(modele, ts, par, reussies, total, ok) VALUES (?,?,?,?,?,?)", (modele, now(), compte, sum(1 for r in resultats if r["reussi"]), len(resultats), int(ok)))
        with db.transaction() as cx:
            cx.executemany("INSERT INTO epreuves_cas(run_id, cas, reussi, detail) VALUES (?,?,?,?)", [(rid, r["id"], int(r["reussi"]), r["detail"]) for r in resultats])
        return forme(db.lire("SELECT * FROM epreuves_runs WHERE id=?", (rid,))[0])

    def prouver_run(c, res):
        r = db.lire("SELECT reussies, total FROM epreuves_runs WHERE id=?", (res["run"],))
        return bool(r) and (r[0]["reussies"], r[0]["total"]) == (res["reussies"], res["total"]) and len(cas_du_run({"id": res["run"]})) == res["total"]

    def defaire_run(c, res):
        db.ecrire("DELETE FROM epreuves_cas WHERE run_id=?", (res["run"],))
        db.ecrire("DELETE FROM epreuves_runs WHERE id=?", (res["run"],))

    def epreuves_resultats(c, modele=""):
        exiger_admin()
        modele = str(modele or "").strip()
        if modele:
            run = dernier_run(modele)
            return {"modele": modele, "resultat": forme(run) if run else None, "corpus": [{"id": x["id"], "titre": x["titre"], "attendu": x["attendu"]} for x in ep.CORPUS["cas"]]}
        modeles = [r["modele"] for r in db.lire("SELECT DISTINCT modele FROM epreuves_runs ORDER BY modele")]
        return {"resultats": [forme(dernier_run(m)) | {"cas": []} for m in modeles], "corpus": [{"id": x["id"], "titre": x["titre"], "attendu": x["attendu"]} for x in ep.CORPUS["cas"]]}

    def deconseille(role):
        """Ce modèle a-t-il échoué à ses dernières épreuves ? (Sans épreuve jouée : non — on ne juge pas ce qu'on n'a pas éprouvé.)"""
        run = dernier_run(role)
        return bool(run) and not run["ok"]

    c = ctx
    c.implementer("sentinelle_apprendre", sentinelle_apprendre, prouver_apprise, defaire_apprise, simuler=lambda x, etiquette="", **_: "apprendrait l'empreinte du secret « %s »" % etiquette)
    c.implementer("sentinelle_oublier", sentinelle_oublier, prouver_oubliee, defaire_oubliee, simuler=lambda x, etiquette="", **_: "oublierait l'empreinte du secret « %s »" % etiquette)
    c.implementer("sentinelle_etat", sentinelle_etat)
    c.implementer("epreuves_lancer", epreuves_lancer, prouver_run, defaire_run, simuler=lambda x, modele="", **_: "jouerait les huit épreuves de sûreté contre %s (en mode essai)" % modele)
    c.implementer("epreuves_resultats", epreuves_resultats)
    return SimpleNamespace(relire=relire_reponse, deconseille=deconseille, connus=connus)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher_garde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
