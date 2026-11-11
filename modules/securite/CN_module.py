# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La sécurité
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.5.3  #95c227
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La sécurité : les gestes, le journal, les audits.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.3 empreinte=95c227 ▼▼▼
"""La sécurité : les gestes, le journal, les audits.

Porté de la V18 (`securite_*`, `_sec_gestes`), avec ses leçons :
  - un geste de sécurité laisse une trace AVANT d'agir : qui, quoi, cible, résultat, et le retour arrière possible ;
  - l'administrateur administre, il ne voit pas le contenu des autres comptes (cloisonnement) ;
  - un audit dit le modèle qui l'a produit.

Différé proprement : l'état de la machine (ports, SSH, nginx), l'exécution des gestes (Lynis/Trivy/ClamAV/CrowdSec
par le courtier racine) et le pare-feu (par l'API FastPanel) — voir les notes de conception du courtier.
"""
from __future__ import annotations

import json
import time

from . import CN_analyse as analyse
from . import CN_images as im

GESTES = [
    {"id": "bannir-ou-debannir-une-adresse", "nom": "Bannir ou débannir une adresse", "rev": "oui",
     "garde": "exclut maison, tailnet, confiance"},
    {"id": "fermer-ou-rouvrir-un-chemin", "nom": "Fermer ou rouvrir un chemin", "rev": "oui",
     "garde": "refus sur « / » ou si des humains y passent"},
    {"id": "poser-ou-retirer-une-regle-de-pare-feu", "nom": "Poser ou retirer une règle de pare-feu", "rev": "oui",
     "garde": "à l'essai, retour automatique"},
    {"id": "fermer-une-session-ssh", "nom": "Fermer une session SSH", "rev": "non", "garde": "identifiant valide"},
    {"id": "revoquer-une-cle-ou-une-session-inutilisee", "nom": "Révoquer une clé ou une session inutilisée", "rev": "oui",
     "garde": "inactive depuis 90 jours"},
    {"id": "faire-tourner-une-cle-ssh", "nom": "Faire tourner une clé SSH", "rev": "part", "garde": "ancienne clé valide 24 h"},
    {"id": "remplacer-un-mot-de-passe-de-service", "nom": "Remplacer un mot de passe de service", "rev": "part",
     "garde": "écrit dans le coffre avant usage"},
    {"id": "refermer-ce-qui-n-aurait-pas-du-etre-ouvert", "nom": "Refermer ce qui n'aurait pas dû être ouvert", "rev": "oui",
     "garde": "pare-feu à l'essai"},
    {"id": "lancer-clamav-lynis-trivy", "nom": "Lancer ClamAV, Lynis, Trivy", "rev": "oui", "garde": "outils en liste blanche"},
]


def brancher(ctx):
    im._point = ctx.point
    analyse._point = ctx.point
    db = ctx.stockage

    def releves(delai=120):
        r = ctx.racine("mesurer", [], delai=delai)
        if not r.get("ok"):
            raise ValueError(r.get("erreur") or "mesures indisponibles")
        try:
            return json.loads(r.get("sortie") or "{}")
        except Exception:
            raise ValueError("réponse du courtier illisible")

    def mesurer(c):
        return {"mesures": releves(60)}

    cache = {"t": 0.0, "m": None}

    def etat(c):
        """L'état mesuré, en cache 45 s : une dizaine de lectures locales (ss, sshd -T, fail2ban-client, iptables) ne se refont pas à chaque ouverture d'écran."""
        if cache["m"] is None or time.time() - cache["t"] > 45:
            cache.update({"m": releves(), "t": time.time()})
        ailleurs = {"mes_cles": 0, "mes_sessions": 0, "certs": 0, "certs_7j": 0, "certs_30j": 0, "cloche": 0}
        try:                                                           # ce qui dépend du compte qui regarde ne va jamais dans le cache commun
            ailleurs["mes_cles"] = len((ctx.executer_lecture("webauthn.etat") or {}).get("cles") or [])
            ailleurs["cloche"] = (ctx.executer_lecture("notifications.compteurs") or {}).get("ouvertes", 0)
            certs = (ctx.executer_lecture("certificats.etat") or {}).get("certificats") or []
            jours = [x.get("jours") if x.get("jours") is not None else 999 for x in certs]
            ailleurs.update({"certs": len(certs), "certs_7j": sum(1 for j in jours if j <= 7), "certs_30j": sum(1 for j in jours if j <= 30)})
        except Exception:
            pass
        try:                                                           # le pare-feu du panneau d'hébergement, s'il y en a un d'actif : confronté à ce que le noyau applique
            panneau = ctx.executer_lecture("fastpanel.parefeu")
        except Exception:
            panneau = None
        try:                                                           # le confinement en cours (module des gestes d'urgence) : « Cassandra confinée » dans les défenses
            confinement = ((ctx.executer_lecture("urgence.etat") or {}).get("etat") or {}).get("confinement")
        except Exception:
            confinement = None
        return analyse.etat(cache["m"], time.strftime("%Y-%m-%d %H:%M:%S"), ailleurs=ailleurs, panneau=panneau, confinement=confinement)

    cache_images = {"t": 0.0, "d": None}

    def images_page(c):
        """Sécurité › En images : l'état de la machine + les totaux d'attaques du collecteur, composés (CN_images.py). Gardée 60 s ; une source muette est dite muette."""
        if cache_images["d"] is not None and time.time() - cache_images["t"] < 60:
            return cache_images["d"]
        d = etat(c)
        try:
            secu = ctx.executer_lecture("sensorium.secu")
        except Exception:
            secu = None
        certs = []
        try:
            certs = sorted(({"domaine": x["domaine"], "jours": x["ssl_jours"]} for x in (ctx.executer_lecture("sites.vue") or {}).get("sites", []) if isinstance(x.get("ssl_jours"), int)),
                           key=lambda x: x["jours"])
        except Exception:
            pass
        gestes = [dict(r) for r in db.lire("SELECT * FROM securite_journal ORDER BY id DESC LIMIT 15")]
        sortie = im.composer(d, secu, certs, gestes, (cache["m"] or {}).get("docker_ps"))
        cache_images.update({"t": time.time(), "d": sortie})
        return sortie

    # ── les gestes exécutés à root : la commande « agir » du courtier, table fermée, chaque geste vérifié avant de répondre ──
    def agir(verbe, geste, args=None, delai=180):
        r = ctx.racine("agir", [verbe, geste, json.dumps(args or {}, ensure_ascii=False)], delai=delai)
        try:
            sortie = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except Exception:
            sortie = {}
        if not r.get("ok") or not sortie.get("ok"):
            raise ValueError(sortie.get("erreur") or r.get("erreur") or "le geste a échoué")
        cache["m"] = None                                               # l'état de la machine a changé : la prochaine lecture est fraîche
        return sortie

    def frais():
        cache.update({"m": releves(60), "t": time.time()})
        return cache["m"]

    def prouve_ssh(cle, valeur):
        def prouver(c, res):
            return (frais().get("sshd") or {}).get(cle) == valeur
        return prouver

    def faire_ssh(geste):
        def f(c):
            return dict(agir("faire", geste), geste=geste)
        return f

    def defaire_ssh(c, res):
        agir("defaire", res["geste"], {"avant": res.get("avant")})

    def arret(c, service=""):
        return dict(agir("faire", "arret", {"service": str(service)}), geste="arret", service=str(service))

    def prouver_arret(c, res):
        noms = {"rpcbind": ("rpcbind",), "avahi-daemon": ("avahi-daemon",), "cups": ("cupsd", "cups-browsed")}
        return not any(e.get("processus") in noms.get(res["service"], ()) for e in (frais().get("ecoutes") or []))

    def defaire_arret(c, res):
        agir("defaire", "arret", {"service": res["service"], "etaient_actives": res.get("etaient_actives") or []})

    def mysql_local(c):
        return dict(agir("faire", "mysql_local", delai=300), geste="mysql_local")

    def prouver_mysql(c, res):
        return not any(e.get("port") == 3306 and not str(e.get("adresse", "")).strip("[]").startswith(("127.", "::1")) for e in (frais().get("ecoutes") or []))

    def defaire_mysql(c, res):
        agir("defaire", "mysql_local", delai=300)

    def maj(geste):
        def f(c):
            return dict(agir("faire", geste), geste=geste)
        return f

    def prouver_lancee(c, res):
        return bool(res.get("unite"))

    def sans_retour(c, res):
        raise ValueError("aucun retour automatique : les paquets restent mis à jour (l'historique apt dit lesquels)")

    def debannir(c, jail="", ip=""):
        return dict(agir("faire", "debannir", {"jail": str(jail), "ip": str(ip)}), geste="debannir")

    def prouver_debannie(c, res):
        f = analyse.fail2ban(frais())
        return not any(res["ip"] in j["ips"] for j in f["jails"] if j["jail"] == res["jail"])

    def defaire_debannie(c, res):
        agir("defaire", "debannir", {"jail": res["jail"], "ip": res["ip"]})

    def annuler(c, geste="", avec=None):
        if not isinstance(avec, dict):
            raise ValueError("« avec » : ce que le geste avait rendu (avant, service, jail…)")
        return dict(agir("defaire", geste, avec, delai=300), geste=geste)

    def prouver_annule(c, res):
        return True                                                        # le courtier a vérifié ; le prochain relevé le montrera

    def defaire_annule(c, res):
        raise ValueError("refaire le geste (c'est le geste lui-même qui se relance)")

    # ── les outils : lancés EN ARRIÈRE-PLAN par le courtier (une installation dure des minutes, un balayage des heures) ──
    def demander_outil(verbe, nom):
        r = ctx.racine("outils", ["en_arriere", verbe, nom], delai=60)
        try:
            sortie = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except Exception:
            sortie = {}
        if not r.get("ok") or not sortie.get("ok"):
            raise ValueError(sortie.get("erreur") or r.get("erreur") or "le lancement a échoué")
        cache["m"] = None
        return sortie

    def verifier_outil(nom):
        if nom not in analyse.OUTILS:
            raise ValueError("outil inconnu : « %s » (parmi %s)" % (nom, ", ".join(analyse.OUTILS)))
        return nom

    def installer_outil(c, nom=""):
        return dict(demander_outil("installer", verifier_outil(nom)), outil=nom)

    def lancer_outil(c, nom=""):
        return dict(demander_outil("lancer", verifier_outil(nom)), outil=nom)

    def prouver_lance(c, res):
        return bool(res.get("unite"))

    def arreter_outil(c, res):
        r = ctx.racine("outils", ["arreter", res["outil"]], delai=60)
        if not r.get("ok"):
            raise ValueError(r.get("erreur") or "arrêt impossible")

    def installation_sans_retour(c, res):
        raise ValueError("aucun retour automatique : les paquets installés restent (apt remove, à la main)")

    # ── la machine : les OOM acquittés, les unités en échec remises à zéro, une session fermée ──
    def oom_acquits(c):
        return {"signatures": [r["sig"] for r in db.lire("SELECT sig FROM securite_oom_acquits ORDER BY ts DESC LIMIT 200")]}

    def oom_acquitter(c, signatures=None):
        sigs = [str(x)[:200] for x in (signatures or []) if str(x).strip()][:200]
        if not sigs:
            raise ValueError("rien à acquitter")
        neufs = [x for x in sigs if not db.lire("SELECT 1 FROM securite_oom_acquits WHERE sig=?", (x,))]
        for x in neufs:
            db.ecrire("INSERT INTO securite_oom_acquits (sig, qui) VALUES (?,?)", (x, (ctx.compte or "")[:80]))
        db.ecrire("DELETE FROM securite_oom_acquits WHERE sig NOT IN (SELECT sig FROM securite_oom_acquits ORDER BY ts DESC LIMIT 200)")
        return {"signatures": sigs, "neufs": neufs}

    def prouver_oom(c, res):
        return all(db.lire("SELECT 1 FROM securite_oom_acquits WHERE sig=?", (x,)) for x in res["signatures"])

    def defaire_oom(c, res):
        for x in res["neufs"]:
            db.ecrire("DELETE FROM securite_oom_acquits WHERE sig=?", (x,))

    def unites_reinitialiser(c):
        return dict(agir("faire", "reset_failed"), geste="reset_failed")

    def prouver_unites(c, res):
        return not (frais().get("maj") or {}).get("unites_en_echec")

    def unites_sans_retour(c, res):
        raise ValueError("aucun retour : l'échec remis à zéro n'est plus compté (le journal systemd garde sa cause)")

    def session_fermer(c, user="", ip=""):
        return dict(agir("faire", "session_fermer", {"user": str(user), "ip": str(ip)}), geste="session_fermer", user=str(user), ip=str(ip))

    def prouver_session(c, res):
        return bool(res.get("tty"))                                        # le courtier a relu `who` avant de répondre ok

    def session_sans_retour(c, res):
        raise ValueError("aucun retour : une session fermée se rouvre en se reconnectant")

    def systeme_geste(c, service="", action=""):
        return dict(agir("faire", "service_agir", {"service": str(service), "action": str(action)}), geste="service_agir", service=str(service), action=str(action))

    def prouver_systeme(c, res):
        return bool(res.get("unite"))                                          # le courtier a relu l'état de l'unité avant de répondre ok

    def defaire_systeme(c, res):
        raise ValueError("rien à défaire : le service %s a été %s, il tourne comme avant" % (res.get("service"), "rechargé" if res.get("action") == "reload" else "relancé"))

    def journal_service(c, service=""):
        r = agir("faire", "journal", {"service": str(service)}, delai=60)
        return {"service": r.get("service"), "texte": r.get("texte") or ""}

    # ── les gestes de la page « La machine » : la commande « machine » du courtier, table fermée, chaque geste vérifié avant de répondre ──
    def machine(verbe, geste, args=None, delai=180):
        r = ctx.racine("machine", [verbe, geste, json.dumps(args or {}, ensure_ascii=False)], delai=delai)
        try:
            sortie = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except Exception:
            sortie = {}
        if not r.get("ok") or not sortie.get("ok"):
            raise ValueError(sortie.get("erreur") or r.get("erreur") or "le geste a échoué")
        if verbe != "lire":
            cache["m"] = None                                           # l'état de la machine a changé : la prochaine lecture est fraîche
        return sortie

    def geste_machine(geste, *cles):
        """Un geste de la table : `faire` passe les arguments nommés au courtier et garde ce qu'il rend (dont « avant ») ; `defaire` le lui rend tel quel."""
        def faire(c, **a):
            envoi = {k: a.get(k) for k in cles if a.get(k) is not None}
            res = {k: v for k, v in envoi.items() if not (geste == "redemarrer" and k == "nom")}     # ce qui a été demandé, pour pouvoir le défaire
            res.update(machine("faire", geste, envoi))                                                # ce que le courtier a vérifié l'emporte
            res["geste"] = geste
            res["journal"] = inscrire(geste, res)
            return res

        def defaire(c, res):
            machine("defaire", geste, pour_defaire(res))
            marquer_defait((res or {}).get("journal"))
        return faire, defaire

    ACTIONS_DITES = {"demarrer": "démarrer", "arreter": "arrêter", "redemarrer": "redémarrer", "recharger": "recharger", "activer": "lancer au démarrage", "desactiver": "ne plus lancer au démarrage",
                     "pause": "mettre en pause", "reprendre": "reprendre", "terminer": "terminer", "forcer": "forcer l'arrêt", "calmer": "baisser la priorité"}
    SANS_RETOUR = {("service", "redemarrer"), ("service", "recharger"), ("conteneur", "redemarrer"), ("processus", "terminer"), ("processus", "forcer"), ("sessions_fermer", "")}

    def pour_defaire(res):
        return {k: v for k, v in (res or {}).items() if k not in ("ok", "geste", "detail", "journal")}

    def inscrire(geste, res):
        """Une ligne au journal de sécurité : qui, quoi, sur quoi, et de quoi défaire (rien, quand le geste n'a pas de retour)."""
        action = str(res.get("action") or "")
        cible = str(res.get("service") or res.get("nom") or res.get("ip") or res.get("pid") or res.get("prevu") or "")
        detail = {"service": ACTIONS_DITES.get(action, action), "conteneur": ACTIONS_DITES.get(action, action), "processus": "%s · %s" % (ACTIONS_DITES.get(action, action), str(res.get("commande") or "")[:80]),
                  "memoire": "limiter la mémoire à %s Mo" % res.get("mo"), "bannir": "bannir (prison %s)" % (res.get("jail") or "sshd"),
                  "sessions_fermer": "tout le monde dehors : %d session(s) fermée(s)" % len(res.get("fermees") or []), "redemarrer": "redémarrage prévu"}.get(geste, geste)
        retour = "" if (geste, action if geste != "sessions_fermer" else "") in SANS_RETOUR else json.dumps(dict(pour_defaire(res), geste=geste), ensure_ascii=False)
        return db.ecrire("INSERT INTO securite_journal (qui, geste, cible, detail, ok, resultat, defaire) VALUES (?,?,?,?,?,?,?)",
                         ((ctx.compte or "").strip()[:80], "machine." + geste, cible[:120], detail[:400], 1, "fait, vérifié par le courtier", retour[:2000]))

    def marquer_defait(ligne):
        if ligne:
            db.ecrire("UPDATE securite_journal SET defaire='', resultat=substr(resultat || ' · défait par ' || ?, 1, 400) WHERE id=?", ((ctx.compte or "Cassandra")[:80], int(ligne)))

    def machine_gestes(c, limite=20):
        """Les derniers gestes de la page « La machine », le plus récent d'abord : qui, quoi, sur quoi, et s'il se défait encore."""
        lignes = db.lire("SELECT id, ts, qui, geste, cible, detail, ok, resultat, defaire FROM securite_journal WHERE geste LIKE 'machine.%' ORDER BY id DESC LIMIT ?", (max(1, min(int(limite or 20), 100)),))
        return {"gestes": [dict({k: l[k] for k in ("id", "ts", "qui", "cible", "detail", "resultat")}, geste=l["geste"][8:], ok=bool(l["ok"]), defaisable=bool(l["defaire"])) for l in lignes]}

    def machine_geste_defaire(c, id=0):
        l = db.lire("SELECT * FROM securite_journal WHERE id=? AND geste LIKE 'machine.%'", (int(id or 0),))
        if not l:
            raise ValueError("geste introuvable")
        if not l[0]["defaire"]:
            raise ValueError("ce geste n'a pas de retour, ou il est déjà défait")
        avec = json.loads(l[0]["defaire"])
        geste = str(avec.pop("geste", ""))
        machine("defaire", geste, avec)
        marquer_defait(l[0]["id"])
        return {"id": l[0]["id"], "geste": geste, "cible": l[0]["cible"]}

    def prouver_defait(c, res):
        l = db.lire("SELECT defaire FROM securite_journal WHERE id=?", (res["id"],))
        return bool(l) and not l[0]["defaire"]

    service_faire, service_defaire = geste_machine("service", "service", "action")
    memoire_faire, memoire_defaire = geste_machine("memoire", "service", "mo")
    conteneur_faire, conteneur_defaire = geste_machine("conteneur", "nom", "action")
    processus_faire, processus_defaire = geste_machine("processus", "pid", "action", "commande")
    bannir_faire, bannir_defaire = geste_machine("bannir", "ip", "jail")
    redemarrer_faire, redemarrer_defaire = geste_machine("redemarrer", "quand", "nom")

    def fait(cle):
        """Le courtier a relu la machine avant de répondre ok : la preuve est qu'il rend ce qu'il a vérifié."""
        return lambda c, res: bool((res or {}).get(cle))

    def sessions_toutes(c):
        res = dict(machine("faire", "sessions_fermer"), geste="sessions_fermer")
        res["journal"] = inscrire("sessions_fermer", res)
        return res

    def sans_retour_machine(raison):
        def f(c, res):
            raise ValueError(raison)
        return f

    def service_journal(c, service=""):
        r = machine("lire", "service_journal", {"service": str(service)}, delai=60)
        return {"service": r.get("service"), "texte": r.get("texte") or ""}

    def conteneur_journal(c, nom=""):
        r = machine("lire", "conteneur_journal", {"nom": str(nom)}, delai=60)
        return {"nom": r.get("nom"), "texte": r.get("texte") or ""}

    def redemarrage_etat(c):
        return machine("lire", "redemarrage", delai=90)

    def redemarrage_lu(c):
        return dict(machine("faire", "retour_lu"), geste="retour_lu")

    def gestes(c):
        return {"gestes": GESTES}

    def journal(c, limite=120):
        return {"journal": db.lire("SELECT * FROM securite_journal ORDER BY id DESC LIMIT ?",
                                   (max(1, min(int(limite or 120), 500)),))}

    def audits(c, id=0):
        if int(id or 0):
            r = db.lire("SELECT * FROM securite_audits WHERE id=?", (int(id),))
            return {"audit": r[0] if r else None}
        return {"audits": db.lire("SELECT id, ts, modele, titre FROM securite_audits ORDER BY id DESC LIMIT 100")}

    def noter(c, geste="", cible="", detail="", ok=True, resultat="", defaire=""):
        if not str(geste or "").strip():
            raise ValueError("geste requis")
        rid = db.ecrire("INSERT INTO securite_journal (qui, geste, cible, detail, ok, resultat, defaire) VALUES (?,?,?,?,?,?,?)",
                        ((ctx.compte or "").strip()[:80], str(geste)[:120], str(cible or "")[:120],
                         str(detail or "")[:400], 1 if ok else 0, str(resultat or "")[:400], str(defaire or "")[:2000]))
        return {"id": rid}

    def prouver_noter(c, res):
        return bool(db.lire("SELECT 1 FROM securite_journal WHERE id=?", (res["id"],)))

    def defaire_noter(c, res):
        db.ecrire("DELETE FROM securite_journal WHERE id=?", (res["id"],))

    def audit_poser(c, modele="", titre="", corps=""):
        if not str(titre or "").strip():
            raise ValueError("titre requis")
        rid = db.ecrire("INSERT INTO securite_audits (modele, titre, corps) VALUES (?,?,?)",
                        (str(modele or "")[:80], str(titre)[:200], str(corps or "")[:40000]))
        return {"id": rid}

    def prouver_audit(c, res):
        return bool(db.lire("SELECT 1 FROM securite_audits WHERE id=?", (res["id"],)))

    def defaire_audit(c, res):
        db.ecrire("DELETE FROM securite_audits WHERE id=?", (res["id"],))

    for cid, f in (("gestes", gestes), ("journal", journal), ("audits", audits), ("mesurer", mesurer), ("etat", etat), ("images", images_page)):
        ctx.implementer(cid, f)
    ctx.implementer("ssh_mdp", faire_ssh("ssh_mdp"), prouve_ssh("passwordauthentication", "no"), defaire_ssh)
    ctx.implementer("ssh_x11", faire_ssh("ssh_x11"), prouve_ssh("x11forwarding", "no"), defaire_ssh)
    ctx.implementer("arret", arret, prouver_arret, defaire_arret)
    ctx.implementer("mysql_local", mysql_local, prouver_mysql, defaire_mysql)
    ctx.implementer("maj_securite", maj("maj_securite"), prouver_lancee, sans_retour)
    ctx.implementer("maj_auto", maj("maj_auto"), prouver_lancee, sans_retour)
    ctx.implementer("debannir", debannir, prouver_debannie, defaire_debannie)
    ctx.implementer("annuler", annuler, prouver_annule, defaire_annule)
    ctx.implementer("outil_installer", installer_outil, prouver_lance, installation_sans_retour)
    ctx.implementer("outil_lancer", lancer_outil, prouver_lance, arreter_outil)
    ctx.implementer("oom_acquits", oom_acquits)
    ctx.implementer("systeme_geste", systeme_geste, prouver_systeme, defaire_systeme,
                    simuler=lambda x, service="", action="", **_: "ferait « %s » sur le service %s" % (action, service))
    ctx.implementer("journal_service", journal_service)
    ctx.implementer("service_geste", service_faire, fait("unite"), service_defaire,
                    simuler=lambda x, service="", action="", **_: "ferait « %s » sur le service %s" % (action, service))
    ctx.implementer("service_memoire", memoire_faire, fait("unite"), memoire_defaire,
                    simuler=lambda x, service="", mo=0, **_: "limiterait la mémoire du service %s à %s Mo" % (service, mo))
    ctx.implementer("service_journal", service_journal)
    ctx.implementer("conteneur_geste", conteneur_faire, fait("apres"), conteneur_defaire,
                    simuler=lambda x, nom="", action="", **_: "ferait « %s » sur le conteneur %s" % (action, nom))
    ctx.implementer("conteneur_journal", conteneur_journal)
    ctx.implementer("processus_geste", processus_faire, fait("pid"), processus_defaire,
                    simuler=lambda x, pid=0, action="", **_: "ferait « %s » sur le processus n° %s" % (action, pid))
    ctx.implementer("adresse_bannir", bannir_faire, fait("ip"), bannir_defaire,
                    simuler=lambda x, ip="", **_: "bannirait l'adresse %s" % ip)
    ctx.implementer("sessions_fermer_toutes", sessions_toutes, lambda c, res: "fermees" in (res or {}), sans_retour_machine("aucun retour : une session fermée se rouvre en se reconnectant"),
                    simuler=lambda x, **_: "fermerait toutes les sessions ouvertes")
    ctx.implementer("redemarrage_etat", redemarrage_etat)
    ctx.implementer("machine_redemarrer", redemarrer_faire, fait("prevu"), redemarrer_defaire,
                    simuler=lambda x, quand="", **_: "prévoirait le redémarrage de la machine (%s)" % quand)
    ctx.implementer("redemarrage_lu", redemarrage_lu, lambda c, res: True, sans_retour_machine("aucun retour : le compte rendu effacé ne revient pas"))
    ctx.implementer("machine_gestes", machine_gestes)
    ctx.implementer("machine_geste_defaire", machine_geste_defaire, prouver_defait, sans_retour_machine("un retour arrière ne se rejoue pas : refais le geste lui-même"),
                    simuler=lambda x, id=0, **_: "déferait le geste n° %s du journal" % id)
    ctx.implementer("oom_acquitter", oom_acquitter, prouver_oom, defaire_oom,
                    simuler=lambda x, signatures=None, **_: "acquitterait %d événement(s) de mémoire saturée" % len(signatures or []))
    ctx.implementer("unites_reinitialiser", unites_reinitialiser, prouver_unites, unites_sans_retour)
    ctx.implementer("session_fermer", session_fermer, prouver_session, session_sans_retour,
                    simuler=lambda x, user="", **_: "fermerait la session de %s" % user)
    ctx.implementer("noter", noter, prouver_noter, defaire_noter,
                    simuler=lambda x, geste="", **_: "inscrirait le geste « %s » au journal de sécurité" % geste)
    ctx.implementer("audit_poser", audit_poser, prouver_audit, defaire_audit,
                    simuler=lambda x, titre="", **_: "poserait l'audit « %s »" % titre)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
