# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La Proactivité
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : proactif
# ZONE       : CN
# VERSION CN : 0.1.0  #ca0bbb
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La Proactivité : l'autonomie qui se gagne, le savoir-faire mesuré, l'ombre et les incidents.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ca0bbb ▼▼▼
"""La Proactivité : l'autonomie qui se gagne, le savoir-faire mesuré, l'ombre et les incidents.

Porté de la V18 (`pf_*`), avec ses leçons :
  - l'autonomie est un PALIER et un budget, pas un interrupteur ; un geste devient éprouvé à dix réussites
    et retombe à deux échecs d'affilée (une autonomie qui ne se retire jamais toute seule est un pari) ;
  - l'ombre est ce qu'elle AURAIT fait : rien n'est exécuté, c'est la façon honnête d'accorder de l'autonomie ;
  - un refus n'est jamais un silence : il devient une ligne dans l'ombre ;
  - un incident a un début, une cause, une chaîne et une fin PROUVÉE (toutes ses conséquences retombées),
    pas l'absence de nouvelle alerte.

Différé proprement : la porte de décision par domaine/geste (catalogue ~100 gestes), les projections/le
tableau (métriques), et le moteur d'évolution (auto-modification) — voir le module « evolution ».
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

PALIERS = ("observer", "proposer", "maitrise", "raconter")
PALIER_NOM = {
    "observer": "Observer — elle remarque et prévient, elle n'agit jamais",
    "proposer": "Proposer — elle prépare le geste et attend un appui",
    "maitrise": "Agir sur ce qu'elle maîtrise — savoir-faire éprouvés seulement",
    "raconter": "Agir puis raconter — tout ce qui est réversible",
}
SEUIL_PROMO = 10
SEUIL_RETRO = 2

# ── Le catalogue des gestes autonomes (domaine › gestes), 10-10 ─────────────
# Chaque geste : (id, libellé, statut, réversibilité, garde). statut : ok | brancher | ecrire | dur.
# « dur » et « ecrire » ne dépassent pas le palier « proposer » : ils ne SAVENT pas encore agir seuls.
AUT_CATALOGUE = [
    ("machine", "Machine", "Services, paquets, correctifs, disque, redémarrages.", [
        ("relancer-un-service", "Relancer un service", "ok", "oui", "santé vérifiée après coup"),
        ("relancer-le-collecteur", "Relancer le collecteur", "ok", "oui", "même garde que les services"),
        ("purger-journaux-et-caches", "Purger journaux et caches", "ok", "part", "liste de caches inoffensifs"),
        ("appliquer-les-correctifs-de-securite", "Appliquer les correctifs de sécurité", "brancher", "part", "aucune"),
        ("redemarrer-la-machine", "Redémarrer la machine", "brancher", "non", "après mise à jour du noyau, hors heures ouvrées"),
    ]),
    ("reseau-et-acces", "Réseau et accès", "Adresses, robots, chemins, pare-feu, interfaces.", [
        ("bannir-ou-debannir-une-adresse-ou-un-pays", "Bannir ou débannir une adresse ou un pays", "ok", "oui", "exclut maison, tailnet, confiance"),
        ("poser-ou-retirer-une-regle-de-pare-feu", "Poser ou retirer une règle de pare-feu", "brancher", "oui", "à l'essai, retour automatique"),
    ]),
    ("hebergement", "Hébergement", "Sites, bases, sauvegardes, certificats, domaines (FastPanel).", [
        ("relancer-un-site", "Relancer un site", "ok", "oui", "réponse HTTP vérifiée"),
        ("relancer-une-sauvegarde-en-echec", "Relancer une sauvegarde en échec", "ok", "oui", "une relance par échec, en arrière-plan"),
        ("renouveler-un-certificat", "Renouveler un certificat", "ok", "oui", "seuil de 30 jours"),
        ("creer-ou-modifier-un-plan-de-sauvegarde", "Créer ou modifier un plan de sauvegarde", "ok", "oui", "cloisonnement par compte"),
        ("supprimer-une-base-ou-un-site", "Supprimer une base ou un site", "dur", "non", "confirmation humaine"),
    ]),
    ("conteneurs", "Conteneurs", "Docker et Compose.", [
        ("relancer-un-conteneur", "Relancer un conteneur", "ok", "oui", "dossiers connus"),
    ]),
    ("comptes", "Comptes", "Utilisateurs, droits, clés de sécurité.", [
        ("creer-un-compte", "Créer un compte", "ecrire", "oui", "cloisonnement : l'admin ne voit pas les autres"),
        ("modifier-les-droits-d-un-compte", "Modifier les droits d'un compte", "ecrire", "oui", "journal « qui a fait quoi »"),
        ("revoquer-une-cle-ou-une-session-inutilisee", "Révoquer une clé ou une session inutilisée", "ecrire", "oui", "inactive depuis 90 jours"),
    ]),
    ("courrier-et-messages", "Courrier et messages", "Rangement, mandats d'envoi, Telegram.", [
        ("ranger-classer-archiver-le-courrier", "Ranger, classer, archiver le courrier", "ok", "oui", "corbeille"),
        ("envoyer-un-message-sous-mandat", "Envoyer un message sous mandat", "ok", "non", "mandat + contexte non teinté"),
    ]),
    ("flotte", "Flotte", "Machines du parc, agents, transferts.", [
        ("relancer-l-agent-d-une-machine", "Relancer l'agent d'une machine", "brancher", "oui", "SSH, clé dédiée"),
        ("ajouter-ou-retirer-une-machine", "Ajouter ou retirer une machine", "ecrire", "oui", "clé neuve à chaque ajout"),
    ]),
    ("coffre", "Coffre", "Secrets et clés.", [
        ("se-servir-d-un-secret-pour-une-tache", "Se servir d'un secret pour une tâche", "ok", "oui", "jamais affiché, remplacé à l'exécution"),
        ("creer-ou-versionner-un-secret", "Créer ou versionner un secret", "ok", "oui", "ancienne version gardée"),
        ("supprimer-un-secret", "Supprimer un secret", "dur", "non", "confirmation humaine"),
    ]),
    ("travail-d-itare", "Travail d'Itare", "Notes, projets, agenda, GED, pièces jointes.", [
        ("creer-et-modifier-notes-taches-rappels-agenda", "Créer et modifier notes, tâches, rappels, agenda", "ok", "oui", "dans l'espace du compte"),
        ("classer-dans-la-ged-et-indexer-les-pieces-jointe", "Classer dans la GED et indexer les pièces jointes", "ok", "oui", "corbeille"),
        ("supprimer-un-projet-ou-une-tache", "Supprimer un projet ou une tâche", "dur", "non", "suppression définitive"),
    ]),
    ("son-propre-code", "Son propre code", "Évolution quotidienne, catalogue.", [
        ("evoluer-chaque-nuit", "Évoluer chaque nuit", "ok", "oui", "copie avant, retour arrière, raison au journal"),
        ("etendre-son-catalogue-de-gestes", "Étendre son catalogue de gestes", "ok", "oui", "tour sans lecture extérieure"),
    ]),
    ("domaines-et-dns", "Domaines et DNS", "Enregistrements, SPF, DKIM, DMARC, tunnels, expirations.", [
        ("corriger-un-enregistrement-derive-de-la-referenc", "Corriger un enregistrement dérivé de la référence (A, MX)", "ok", "oui", "référence versionnée"),
        ("modifier-les-serveurs-de-noms", "Modifier les serveurs de noms", "dur", "non", "peut couper un site entier"),
        ("renouveler-ou-acheter-un-domaine", "Renouveler ou acheter un domaine", "dur", "non", "dépense : accord humain"),
    ]),
    ("crise", "Crise", "Procédure préparée à l'avance, déclenchée d'un geste.", [
        ("couper-l-acces-public-garder-le-tailnet", "Couper l'accès public, garder le tailnet", "ecrire", "oui", "retour en un geste"),
        ("passer-en-lecture-seule", "Passer en lecture seule", "ok", "oui", "retour en un geste"),
    ]),
    ("sauvegardes-preuve-et-hors-site", "Sauvegardes : preuve et hors site", "Restaurer, envoyer ailleurs, purger.", [
        ("tester-une-restauration-en-bac-a-sable", "Tester une restauration en bac à sable", "ok", "oui", "bac isolé, rien en production"),
        ("envoyer-une-sauvegarde-hors-site", "Envoyer une sauvegarde hors site", "ok", "oui", "destination à décider"),
        ("purger-les-sauvegardes-hors-retention", "Purger les sauvegardes hors rétention", "dur", "non", "suppression irréversible"),
    ]),
    ("rotation-des-secrets", "Rotation des secrets", "Clés SSH, jetons, mots de passe de service.", [
        ("signaler-un-secret-trop-ancien", "Signaler un secret trop ancien", "ok", "oui", "lecture seule"),
        ("faire-tourner-une-cle-ssh", "Faire tourner une clé SSH", "ok", "part", "ancienne clé valide 24 h"),
        ("remplacer-un-mot-de-passe-de-service", "Remplacer un mot de passe de service", "ok", "part", "écrit dans le coffre avant usage"),
    ]),
    ("defense-vue-de-l-exterieur", "Défense vue de l'extérieur", "Ce qui est exposé, comparé à ce qui devrait l'être.", [
        ("scanner-sa-surface-depuis-l-exterieur", "Scanner sa surface depuis l'extérieur", "ok", "oui", "ses propres adresses seulement"),
        ("lancer-clamav-lynis-trivy", "Lancer ClamAV, Lynis, Trivy", "brancher", "oui", "outils en liste blanche"),
    ]),
    ("modeles-et-quotas", "Modèles et quotas", "Fournisseurs, bascules, coûts.", [
        ("basculer-sur-un-autre-fournisseur-quand-un-quota", "Basculer sur un autre fournisseur quand un quota tombe", "brancher", "oui", "secours déclarés seulement"),
        ("depasser-un-plafond-de-depense", "Dépasser un plafond de dépense", "dur", "non", "dépense : accord humain"),
    ]),
    ("automatismes", "Automatismes", "Ses propres tâches planifiées.", [
        ("creer-ou-modifier-une-tache-planifiee", "Créer ou modifier une tâche planifiée", "ok", "oui", "journal « qui a fait quoi »"),
        ("suspendre-une-tache-qui-boucle", "Suspendre une tâche qui boucle", "ecrire", "oui", "reprise en un geste"),
        ("corriger-un-cron-silencieux", "Corriger un cron silencieux", "ecrire", "oui", "ancienne ligne gardée"),
    ]),
    ("coordination-des-agents", "Coordination des agents", "Salon, journal des agents, délégation.", [
        ("ouvrir-un-fil-et-inviter-des-agents", "Ouvrir un fil et inviter des agents", "ok", "oui", "dans le salon"),
        ("ecrire-au-journal-des-agents", "Écrire au journal des agents", "ok", "oui", "aucune"),
        ("deleguer-une-lecture-lourde-a-l-agent-d-orion", "Déléguer une lecture lourde à l'agent d'Orion", "brancher", "oui", "lecture seule, sans données personnelles"),
    ]),
    ("sites-wordpress", "Sites WordPress", "Cœur, plugins, cache, restauration.", [
        ("vider-le-cache", "Vider le cache", "ok", "oui", "aucune"),
        ("desactiver-un-plugin-fautif", "Désactiver un plugin fautif", "ok", "oui", "réactivable"),
        ("mettre-a-jour-le-cur-et-les-plugins", "Mettre à jour le cœur et les plugins", "ok", "part", "point de restauration obligatoire"),
        ("restaurer-le-site-depuis-une-sauvegarde", "Restaurer le site depuis une sauvegarde", "ok", "part", "état actuel gardé avant écrasement"),
    ]),
]
AUT_STATUTS = {"ok": "en service", "brancher": "à brancher", "ecrire": "à écrire", "dur": "garde dure"}
AUT_DEFAUT = {"lv": None, "ombre": False, "decl": "Sur alerte", "per": "Hérite du domaine", "persel": "", "excl": "",
              "fen": "Toujours", "fd": "02:00", "ff": "06:00", "ech": 2, "boucle": 3, "boucleh": "1 h",
              "avis": None, "aviq": "Hérite de la gouvernance", "snap": None,
              "ou": "Hérite (selon le geste)", "nuit": "Hérite de la gouvernance"}
AUT_CHOIX = {"decl": ("Sur alerte", "Planifié", "Sur demande seulement", "Sur alerte et planifié"),
             "per": ("Hérite du domaine", "Orion seulement", "Les sites de la maison seulement", "Une sélection à choisir"),
             "fen": ("Toujours", "Plage horaire", "Hors heures ouvrées"),
             "boucleh": ("1 h", "6 h", "24 h"),
             "aviq": ("Hérite de la gouvernance",),
             "ou": ("Hérite (selon le geste)", "Info : la cloche", "À voir : cloche et e-mail à l'administrateur", "Critique : cloche, e-mail et Telegram"),
             "nuit": ("Hérite de la gouvernance", "Oui, pour ce geste", "Non, jamais pour ce geste")}
AUT_GOV_DEFAUT = {"avis_defaut": "", "avis_secours": "Elle propose seulement",
                  "snap_mode": "Fichiers et base, avant chaque geste en plusieurs étapes",
                  "intouchables": ["ragnar", "iphone-sandrine"]}


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def brancher(ctx):
    db = ctx.stockage

    def _lire(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def _ecrire(nom, valeur):
        try:
            ctx.service_reglages().poser("proactif." + nom, valeur, par=ctx.compte or "")
            return True
        except Exception:
            return False

    # ── l'autonomie ─────────────────────────────────────────────────────────
    def autonomie(c):
        p = str(_lire("palier", "proposer"))
        if p not in PALIERS:
            p = "proposer"
        return {"palier": p, "palier_nom": PALIER_NOM[p],
                "budget_jour": int(_lire("budget_jour", 9) or 9),
                "pause_debut": str(_lire("pause_debut", "09:00")),
                "pause_fin": str(_lire("pause_fin", "18:00")),
                "pause": bool(_lire("pause", True)),
                "reversible": bool(_lire("reversible", True)),
                "retrograde": bool(_lire("retrograde", True)),
                "paliers": list(PALIERS), "noms": PALIER_NOM}

    def autonomie_set(c, **d):
        avant = autonomie(c)
        if "palier" in d and d["palier"] not in PALIERS:
            raise ValueError("palier inconnu (%s)" % " | ".join(PALIERS))
        if "palier" in d:
            _ecrire("palier", str(d["palier"]))
        for k in ("pause_debut", "pause_fin"):
            if k in d:
                _ecrire(k, str(d[k])[:5])
        for k in ("pause", "reversible", "retrograde"):
            if k in d:
                _ecrire(k, bool(d[k]))
        if "budget_jour" in d:
            _ecrire("budget_jour", max(0, min(100, int(d["budget_jour"] or 0))))
        return {"avant": avant, "autonomie": autonomie(c)}

    def prouver_autonomie(c, res):
        return autonomie(c) != res.get("avant")

    def defaire_autonomie(c, res):
        for k, v in (res.get("avant") or {}).items():
            if k in ("palier", "pause_debut", "pause_fin", "pause", "reversible", "retrograde", "budget_jour"):
                _ecrire(k, v)

    # ── le savoir-faire ─────────────────────────────────────────────────────
    def _savoir(signature):
        r = db.lire("SELECT * FROM proactive_playbooks WHERE signature=?", (signature,))
        return dict(r[0]) if r else None

    def savoirs(c):
        out = []
        for r in db.lire("SELECT * FROM proactive_playbooks ORDER BY successes DESC"):
            d = dict(r)
            t = (d.get("successes") or 0) + (d.get("failures") or 0)
            d["total"] = t
            d["taux"] = round(100.0 * (d.get("successes") or 0) / t) if t else 0
            d["etat"] = d.get("etat") or "proposition"
            d["promouvable"] = bool((d.get("successes") or 0) >= SEUIL_PROMO and not (d.get("echecs_suite") or 0) and d["etat"] != "auto")
            out.append(d)
        props = db.lire("SELECT * FROM pf_savoir_props WHERE etat='propose' AND vu >= 3 ORDER BY vu DESC LIMIT 6")
        return {"savoirs": out, "propositions": props, "seuil_promo": SEUIL_PROMO, "seuil_retro": SEUIL_RETRO}

    def savoir_etat(c, signature="", etat=""):
        if etat not in ("auto", "proposition", "manuel"):
            raise ValueError("état inconnu")
        sav = _savoir(signature)
        if not sav:
            raise ValueError("savoir-faire inconnu")
        if etat == "auto" and (sav.get("successes") or 0) < SEUIL_PROMO:
            raise ValueError("il faut %d réussites pour confier ce geste (actuellement %d)" % (SEUIL_PROMO, sav.get("successes") or 0))
        db.ecrire("UPDATE proactive_playbooks SET etat=?, promu_le=?, echecs_suite=0 WHERE signature=?",
                  (etat, _utcnow().strftime("%Y-%m-%d %H:%M") if etat == "auto" else "", signature))
        return {"signature": signature, "avant": sav["etat"], "etat": etat}

    def prouver_savoir_etat(c, res):
        return (_savoir(res["signature"]) or {}).get("etat") == res["etat"]

    def defaire_savoir_etat(c, res):
        db.ecrire("UPDATE proactive_playbooks SET etat=?, promu_le='', echecs_suite=0 WHERE signature=?",
                  (res["avant"], res["signature"]))

    def savoir_resultat(c, signature="", reussi=False):
        r = db.lire("SELECT etat, echecs_suite FROM proactive_playbooks WHERE signature=?", (signature,))
        suite = 0 if reussi else ((r[0]["echecs_suite"] if r else 0) or 0) + 1
        db.ecrire("UPDATE proactive_playbooks SET echecs_suite=?, successes=successes+?, failures=failures+? WHERE signature=?",
                  (suite, 1 if reussi else 0, 0 if reussi else 1, signature))
        retro = bool(r and r[0]["etat"] == "auto" and suite >= SEUIL_RETRO and bool(_lire("retrograde", True)))
        if retro:
            db.ecrire("UPDATE proactive_playbooks SET etat='proposition', promu_le='' WHERE signature=?", (signature,))
        return {"signature": signature, "reussi": bool(reussi), "retrograde": retro}

    def savoir_observe(c, signature="", action_kind="", action=""):
        if not signature or not action:
            raise ValueError("signature et action requises")
        if _savoir(signature):
            return {"deja_connu": True}
        cur = db.ecrire("UPDATE pf_savoir_props SET vu = vu + 1, dernier=datetime('now'), action=? WHERE signature=? AND etat='propose'",
                        (str(action)[:400], signature))
        if not cur:
            db.ecrire("INSERT OR IGNORE INTO pf_savoir_props (signature, action_kind, action) VALUES (?,?,?)",
                      (signature, str(action_kind or "")[:40], str(action)[:400]))
        vu = db.lire("SELECT vu FROM pf_savoir_props WHERE signature=?", (signature,))
        return {"signature": signature, "vu": vu[0]["vu"] if vu else 0, "propose": bool(vu and vu[0]["vu"] >= 3)}

    def savoir_accepter(c, signature=""):
        p = db.lire("SELECT * FROM pf_savoir_props WHERE signature=?", (signature,))
        if not p:
            raise ValueError("proposition inconnue")
        db.ecrire("INSERT OR IGNORE INTO proactive_playbooks (signature, action_kind, action, successes, failures, etat) VALUES (?,?,?,0,0,'proposition')",
                  (signature, p[0]["action_kind"], p[0]["action"]))
        db.ecrire("UPDATE pf_savoir_props SET etat='accepte' WHERE signature=?", (signature,))
        return {"signature": signature, "avant": p[0]["etat"]}

    def prouver_savoir_accepter(c, res):
        return bool(_savoir(res["signature"]))

    def defaire_savoir_accepter(c, res):
        db.ecrire("DELETE FROM proactive_playbooks WHERE signature=?", (res["signature"],))
        db.ecrire("UPDATE pf_savoir_props SET etat='propose' WHERE signature=?", (res["signature"],))

    def savoir_ecarter(c, signature=""):
        p = db.lire("SELECT etat FROM pf_savoir_props WHERE signature=?", (signature,))
        if not p:
            raise ValueError("proposition inconnue")
        db.ecrire("UPDATE pf_savoir_props SET etat='ecarte' WHERE signature=?", (signature,))
        return {"signature": signature, "avant": p[0]["etat"]}

    def prouver_savoir_ecarter(c, res):
        return db.lire("SELECT etat FROM pf_savoir_props WHERE signature=?", (res["signature"],))[0]["etat"] == "ecarte"

    def defaire_savoir_ecarter(c, res):
        db.ecrire("UPDATE pf_savoir_props SET etat=? WHERE signature=?", (res["avant"], res["signature"]))

    # ── l'ombre ─────────────────────────────────────────────────────────────
    def ombre_ajouter(c, fkey="", signature="", action_kind="", action="", titre="", motif=""):
        db.ecrire("INSERT INTO pf_ombre (fkey, signature, action_kind, action, titre, motif) VALUES (?,?,?,?,?,?)",
                  (str(fkey or ""), str(signature or ""), str(action_kind or ""), str(action or "")[:400],
                   str(titre or "")[:200], str(motif or "")[:250]))
        db.ecrire("DELETE FROM pf_ombre WHERE id NOT IN (SELECT id FROM pf_ombre ORDER BY id DESC LIMIT 200)")
        return {"ajoutee": True}

    def ombre(c, limit=40):
        rows = db.lire("SELECT * FROM pf_ombre ORDER BY id DESC LIMIT ?", (max(1, min(int(limit or 40), 200)),))
        return {"ombre": rows, "justes": len([r for r in rows if r.get("avis") == "juste"]),
                "discutables": len([r for r in rows if r.get("avis") == "discutable"])}

    def ombre_avis(c, oid=0, avis=""):
        if avis not in ("juste", "discutable", ""):
            raise ValueError("avis inconnu")
        avant = db.lire("SELECT avis FROM pf_ombre WHERE id=?", (int(oid),))
        if not avant:
            raise ValueError("geste de l'ombre inconnu")
        db.ecrire("UPDATE pf_ombre SET avis=? WHERE id=?", (avis, int(oid)))
        return {"oid": int(oid), "avant": avant[0]["avis"], "avis": avis}

    def prouver_ombre_avis(c, res):
        return db.lire("SELECT avis FROM pf_ombre WHERE id=?", (res["oid"],))[0]["avis"] == res["avis"]

    def defaire_ombre_avis(c, res):
        db.ecrire("UPDATE pf_ombre SET avis=? WHERE id=?", (res["avant"], res["oid"]))

    # ── les incidents ───────────────────────────────────────────────────────
    def incidents_batir(c):
        """Regroupe les découvertes ouvertes en incidents. Les découvertes viennent du noyau (constats) ;
        ici on ne fait que regrouper ce qu'on a déjà corrélé (les liens sont posés par le noyau ou l'humain)."""
        ouverts, fermes = [], []
        for inc in db.lire("SELECT * FROM pf_incidents WHERE statut='ouvert'"):
            liens = db.lire("SELECT fkey FROM pf_incident_liens WHERE incident_id=?", (inc["id"],))
            ouverts.append(inc["cle"])
        return {"ok": True, "ouverts": ouverts, "fermes": fermes}

    def incidents(c, limit=20, tout=False):
        q = "SELECT * FROM pf_incidents %s ORDER BY id DESC LIMIT ?" % ("" if tout else "WHERE statut='ouvert'")
        out = []
        for r in db.lire(q, (max(1, min(int(limit or 20), 100)),)):
            d = dict(r)
            d["chaine"] = db.lire("SELECT fkey, role, ts FROM pf_incident_liens WHERE incident_id=? ORDER BY ts", (d["id"],))
            out.append(d)
        return {"incidents": out}

    # ── le fil ──────────────────────────────────────────────────────────────
    def fil(c, heures=24, limit=80):
        depuis = (_utcnow() - timedelta(hours=max(1, min(168, int(heures or 24))))).strftime("%Y-%m-%d %H:%M:%S")
        out = []

        def _add(ts, src, couleur, titre, detail, par_elle=0, gros=0):
            if ts:
                out.append({"ts": str(ts)[:19], "source": src, "couleur": couleur, "titre": str(titre)[:180],
                            "detail": str(detail or "")[:260], "par_elle": par_elle, "gros": gros})

        for r in db.lire("SELECT * FROM pf_ombre WHERE ts >= ?", (depuis,)):
            _add(r["ts"], "OMBRE", "warn", (r["titre"] or r["signature"] or "geste retenu"), r["motif"])
        for r in db.lire("SELECT * FROM pf_incidents WHERE ouvert_le >= ? OR ferme_le >= ?", (depuis, depuis)):
            _add(r["ouvert_le"], "INCIDENT", "danger", "Incident : " + str(r["cause"]), str(r["titre"]), 0, 1)
            if r["ferme_le"]:
                _add(r["ferme_le"], "INCIDENT", "ok", "Incident clos : " + str(r["cause"]), str(r["preuve"] or ""), 0, 1)
        for r in db.lire("SELECT * FROM proactive_playbooks WHERE promu_le >= ?", (depuis,)):
            _add(r["promu_le"], "SAVOIR", "ok", "Savoir-faire confié : " + str(r["signature"]), "éprouvé à %d réussites" % (r["successes"] or 0), 1, 1)
        out.sort(key=lambda x: x["ts"], reverse=True)
        return {"fil": out[:int(limit)], "par_elle": len([x for x in out if x["par_elle"]])}

    # ── l'autonomie par domaine et par geste (l'« automatisme ») ────────────
    def _aut_index():
        out = {}
        for did, dnom, ddesc, gestes in AUT_CATALOGUE:
            out["d:" + did] = {"domaine": did, "nom": dnom, "desc": ddesc}
            for gid, gnom, st, rev, garde in gestes:
                out["g:%s/%s" % (did, gid)] = {"domaine": did, "geste": gid, "nom": gnom,
                                               "st": st, "rev": rev, "garde": garde, "dnom": dnom}
        return out

    def _aut_libelle(cle):
        e = _aut_index().get("g:" + str(cle or ""))
        return ("%s › %s" % (e["dnom"], e["nom"])) if e else str(cle or "")

    def _aut_norm(cle):
        c = str(cle or "").strip()
        return c if c.startswith(("d:", "g:")) else "g:" + c

    def catalogue(c):
        familles = []
        for did, dnom, ddesc, gestes in AUT_CATALOGUE:
            familles.append({"id": did, "nom": dnom, "desc": ddesc,
                             "gestes": [{"id": gid, "nom": gnom, "st": st, "statut": AUT_STATUTS.get(st, st),
                                         "rev": rev, "garde": garde, "cle": "%s/%s" % (did, gid)}
                                        for gid, gnom, st, rev, garde in gestes]})
        return {"familles": familles, "statuts": AUT_STATUTS, "choix": AUT_CHOIX, "defauts": AUT_DEFAUT}

    def aut_reglages_lire():
        out = {}
        for r in db.lire("SELECT cle, reglages FROM autonomie_reglages"):
            try:
                out[r["cle"]] = json.loads(r["reglages"] or "{}")
            except Exception:
                out[r["cle"]] = {}
        return out

    def reglages(c):
        return {"reglages": aut_reglages_lire(), "defauts": AUT_DEFAUT, "choix": AUT_CHOIX}

    def regler(c, cle="", reglages=None):
        cle = _aut_norm(cle)
        ent = _aut_index().get(cle)
        if not ent:
            raise ValueError("domaine ou geste inconnu")
        est_geste = "geste" in ent
        propres = {}
        for k, v in (reglages or {}).items():
            if k not in AUT_DEFAUT:
                raise ValueError("réglage inconnu : %s" % str(k)[:40])
            if not est_geste and k not in ("lv", "per", "persel"):
                raise ValueError("un domaine ne porte que le palier et le périmètre")
            if k == "lv":
                if v in (None, ""):
                    propres[k] = None
                elif v not in PALIERS:
                    raise ValueError("palier inconnu")
                elif est_geste and ent["st"] in ("dur", "ecrire") and PALIERS.index(v) > PALIERS.index("proposer"):
                    raise ValueError("ce geste %s : il ne peut pas dépasser « proposer »" % ("est en garde dure" if ent["st"] == "dur" else "n'existe pas encore"))
                else:
                    propres[k] = v
            elif k in ("ombre", "avis", "snap"):
                propres[k] = None if v is None else bool(v)
            elif k in ("ech", "boucle"):
                try:
                    n = int(v)
                except Exception:
                    raise ValueError("%s : un nombre est attendu" % k)
                borne = (1, 5) if k == "ech" else (1, 10)
                if not borne[0] <= n <= borne[1]:
                    raise ValueError("%s : entre %d et %d" % (k, borne[0], borne[1]))
                propres[k] = n
            elif k in ("fd", "ff"):
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v or "")):
                    raise ValueError("%s : une heure HH:MM est attendue" % k)
                propres[k] = str(v)
            elif k in ("excl", "persel"):
                propres[k] = str(v or "")[:300]
            elif k == "aviq":
                propres[k] = str(v or AUT_DEFAUT["aviq"])[:120]
            else:
                if str(v) not in AUT_CHOIX[k]:
                    raise ValueError("%s : valeur inconnue" % k)
                propres[k] = str(v)
        avant = aut_reglages_lire().get(cle)
        actuel = dict(avant or {})
        actuel.update(propres)
        db.ecrire("INSERT INTO autonomie_reglages (cle, reglages, par) VALUES (?,?,?) "
                  "ON CONFLICT(cle) DO UPDATE SET reglages=excluded.reglages, par=excluded.par, ts=datetime('now','localtime')",
                  (cle, json.dumps(actuel, ensure_ascii=False), ctx.compte or ""))
        return {"cle": cle, "avant": avant, "apres": propres}

    def prouver_regler(c, res):
        return aut_reglages_lire().get(res["cle"]) == (dict(res.get("avant") or {}) | res.get("apres", {}))

    def defaire_regler(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM autonomie_reglages WHERE cle=?", (res["cle"],))
        else:
            db.ecrire("INSERT INTO autonomie_reglages (cle, reglages, par) VALUES (?,?,?) "
                      "ON CONFLICT(cle) DO UPDATE SET reglages=excluded.reglages, ts=datetime('now','localtime')",
                      (res["cle"], json.dumps(res["avant"], ensure_ascii=False), ctx.compte or ""))

    def remettre(c, cle=""):
        cle = _aut_norm(cle)
        if cle not in _aut_index():
            raise ValueError("domaine ou geste inconnu")
        avant = aut_reglages_lire().get(cle)
        db.ecrire("DELETE FROM autonomie_reglages WHERE cle=?", (cle,))
        return {"cle": cle, "avant": avant}

    def prouver_remettre(c, res):
        return res["cle"] not in aut_reglages_lire()

    def defaire_remettre(c, res):
        if res.get("avant") is not None:
            db.ecrire("INSERT INTO autonomie_reglages (cle, reglages) VALUES (?,?)", (res["cle"], json.dumps(res["avant"], ensure_ascii=False)))

    def disjoncteurs(c):
        return {"disjoncteurs": db.lire("SELECT * FROM autonomie_disj WHERE etat='declenche' ORDER BY depuis DESC")}

    def debloquer(c, cle=""):
        cle = _aut_norm(cle)
        if cle not in _aut_index():
            raise ValueError("geste inconnu")
        avant = db.lire("SELECT * FROM autonomie_disj WHERE cle=?", (cle,))
        db.ecrire("UPDATE autonomie_disj SET etat='arme', raison='', echecs_suite=0 WHERE cle=?", (cle,))
        db.ecrire("DELETE FROM autonomie_actions WHERE cle=?", (cle,))
        return {"cle": cle, "avant": avant[0] if avant else None}

    def prouver_debloquer(c, res):
        r = db.lire("SELECT etat FROM autonomie_disj WHERE cle=?", (res["cle"],))
        return (not r) or r[0]["etat"] == "arme"

    def defaire_debloquer(c, res):
        if res.get("avant"):
            a = res["avant"]
            db.ecrire("INSERT INTO autonomie_disj (cle, etat, raison, depuis, echecs_suite) VALUES (?,?,?,?,?) "
                      "ON CONFLICT(cle) DO UPDATE SET etat=excluded.etat, raison=excluded.raison, echecs_suite=excluded.echecs_suite",
                      (a["cle"], a["etat"], a["raison"], a["depuis"], a["echecs_suite"]))

    def gouvernance(c):
        g = dict(AUT_GOV_DEFAUT)
        g["intouchables"] = list(AUT_GOV_DEFAUT["intouchables"])
        g.update({k: v for k, v in (aut_reglages_lire().get("gov") or {}).items() if k in AUT_GOV_DEFAUT})
        return g

    def gouverner(c, **champs):
        avant = aut_reglages_lire().get("gov") or {}
        propres = {}
        for k, v in (champs or {}).items():
            if k not in AUT_GOV_DEFAUT:
                raise ValueError("réglage inconnu : %s" % str(k)[:40])
            if k in ("avis_secours", "snap_mode", "avis_defaut"):
                propres[k] = str(v or "")[:160]
            elif k == "intouchables":
                if not isinstance(v, list):
                    raise ValueError("une liste est attendue")
                propres[k] = [str(x).strip()[:120] for x in v if str(x).strip()][:200]
        actuel = dict(avant)
        actuel.update(propres)
        db.ecrire("INSERT INTO autonomie_reglages (cle, reglages, par) VALUES ('gov', ?, ?) "
                  "ON CONFLICT(cle) DO UPDATE SET reglages=excluded.reglages, ts=datetime('now','localtime')",
                  (json.dumps(actuel, ensure_ascii=False), ctx.compte or ""))
        return {"avant": avant, "apres": propres}

    def prouver_gouverner(c, res):
        return aut_reglages_lire().get("gov") == (dict(res.get("avant") or {}) | res.get("apres", {}))

    def defaire_gouverner(c, res):
        db.ecrire("INSERT INTO autonomie_reglages (cle, reglages) VALUES ('gov', ?) "
                  "ON CONFLICT(cle) DO UPDATE SET reglages=excluded.reglages, ts=datetime('now','localtime')",
                  (json.dumps(res.get("avant") or {}, ensure_ascii=False),))

    # ── enregistrement ──────────────────────────────────────────────────────
    for cid, f in (("autonomie", autonomie), ("savoirs", savoirs), ("ombre", ombre),
                   ("incidents", incidents), ("fil", fil), ("catalogue", catalogue),
                   ("reglages", reglages), ("disjoncteurs", disjoncteurs), ("gouvernance", gouvernance)):
        ctx.implementer(cid, f)
    ctx.implementer("autonomie_set", autonomie_set, prouver_autonomie, defaire_autonomie,
                    simuler=lambda x, **_: "réglerait l'autonomie")
    ctx.implementer("savoir_etat", savoir_etat, prouver_savoir_etat, defaire_savoir_etat,
                    simuler=lambda x, signature="", etat="", **_: "passerait « %s » à %s" % (signature, etat))
    ctx.implementer("savoir_accepter", savoir_accepter, prouver_savoir_accepter, defaire_savoir_accepter,
                    simuler=lambda x, signature="", **_: "accepterait le savoir-faire « %s »" % signature)
    ctx.implementer("savoir_ecarter", savoir_ecarter, prouver_savoir_ecarter, defaire_savoir_ecarter,
                    simuler=lambda x, signature="", **_: "écarterait la proposition « %s »" % signature)
    ctx.implementer("ombre_avis", ombre_avis, prouver_ombre_avis, defaire_ombre_avis,
                    simuler=lambda x, oid=0, avis="", **_: "jugerait le geste %s : %s" % (oid, avis))
    ctx.implementer("regler", regler, prouver_regler, defaire_regler,
                    simuler=lambda x, cle="", **_: "réglerait le geste « %s »" % cle)
    ctx.implementer("remettre", remettre, prouver_remettre, defaire_remettre,
                    simuler=lambda x, cle="", **_: "remettrait « %s » aux valeurs par défaut" % cle)
    ctx.implementer("debloquer", debloquer, prouver_debloquer, defaire_debloquer,
                    simuler=lambda x, cle="", **_: "débloquerait le geste « %s »" % cle)
    ctx.implementer("gouverner", gouverner, prouver_gouverner, defaire_gouverner,
                    simuler=lambda x, **_: "réglerait la gouvernance")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _utcnow, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
