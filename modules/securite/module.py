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

from . import analyse

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
        return analyse.etat(cache["m"], time.strftime("%Y-%m-%d %H:%M:%S"), ailleurs=ailleurs, panneau=panneau)

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

    for cid, f in (("gestes", gestes), ("journal", journal), ("audits", audits), ("mesurer", mesurer), ("etat", etat)):
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
    ctx.implementer("noter", noter, prouver_noter, defaire_noter,
                    simuler=lambda x, geste="", **_: "inscrirait le geste « %s » au journal de sécurité" % geste)
    ctx.implementer("audit_poser", audit_poser, prouver_audit, defaire_audit,
                    simuler=lambda x, titre="", **_: "poserait l'audit « %s »" % titre)
