# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.12  #5aabe3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module Sensorium : relie le noyau au collecteur (CN_sensorium.py), qui reste entier et tourne à part, en service root.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.12 empreinte=5aabe3 ▼▼▼
"""Le module Sensorium : relie le noyau au collecteur (CN_sensorium.py), qui reste entier et tourne à part, en service root.

Le collecteur mesure la machine et son monde. Ce module ne mesure rien : il le questionne par son socket (une requête texte, une réponse
JSON), en fait des objets, des constats et des tuiles, et le tient à l'oeil. Un collecteur muet se voit : c'est un constat, jamais un silence.
"""
import json
import os
import re
import socket
import time

SOCKET = os.environ.get("SENSORIUM_SOCKET") or "/run/sensorium/knowledge.sock"
DELAI = 5.0
_CLE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,200}$")
_ENTITE = re.compile(r"^[a-z_]{1,64}$")
MACHINE = ("machine", "hote")


def demander(requete, delai=DELAI):
    """Une requête, une réponse : le protocole du collecteur. Rend le texte reçu."""
    if not hasattr(socket, "AF_UNIX"):
        raise OSError("pas de socket Unix sur ce système : le collecteur n'est joignable que sous Linux")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(delai)
    try:
        s.connect(SOCKET)
        s.sendall(requete.encode("utf-8"))
        morceaux = []
        while True:
            d = s.recv(65536)
            if not d:
                break
            morceaux.append(d)
        return b"".join(morceaux).decode("utf-8", "replace")
    finally:
        s.close()


def json_de(requete, delai=DELAI):
    brut = demander(requete, delai).strip()
    if brut == "ERROR":
        raise RuntimeError("le collecteur a refusé la requête « %s »" % requete.split(":")[0])
    return json.loads(brut)


def _arrondi(d, cle):
    v = d.get(cle)
    return round(v, 1) if isinstance(v, (int, float)) else v


def brancher(ctx):
    etat = {"t": 0.0, "donnees": {}, "etat": None}

    def machine(ctx):
        return ctx.lire(*MACHINE, portee=ctx.TOUT)

    def releve(ctx):
        """Une relève : santé (tableau de bord) et ressources. On ne réécrit pas à chaque passe : un changement net, ou toutes les cinq minutes."""
        libelle = socket.gethostname()
        try:
            tableau = json_de("GET_DASHBOARD")
            mesures = json_de("GET_METRICS")
        except (OSError, ValueError, RuntimeError) as ex:
            precedent = machine(ctx)
            if not precedent or precedent["etat"] != "muet":
                ctx.emettre("machine.muette", objet=MACHINE, donnees={"erreur": str(ex)[:200]})
            ctx.poser(*MACHINE, libelle, etat="muet", donnees=dict(precedent["donnees"] if precedent else {}, erreur=str(ex)[:200]))
            etat["etat"] = "muet"
            return
        sante = tableau.get("health_status", "inconnue")
        donnees = {"score": tableau.get("health_score", 0), "statut": sante, "unites_en_echec": tableau.get("failed_units", 0),
                   "oom_24h": tableau.get("oom_events_24h", 0), "cpu": _arrondi(mesures, "cpu"), "ram": _arrondi(mesures, "ram"),
                   "disque": _arrondi(mesures, "disk"), "swap": _arrondi(mesures, "swap"), "charge_1m": _arrondi(mesures, "load_1m"),
                   "ram_go": [_arrondi(mesures, "ram_used_gb"), _arrondi(mesures, "ram_total_gb")],
                   "disque_go": [_arrondi(mesures, "disk_used_gb"), _arrondi(mesures, "disk_total_gb")],
                   "processus": [{"nom": p.get("name", p.get("command", "?")), "cpu": p.get("cpu")} for p in (mesures.get("top_processes") or [])[:5]
                                 if isinstance(p, dict)], "erreur": ""}
        precedent = machine(ctx)
        a_change = (not precedent or precedent["etat"] in ("muet", "") or precedent["donnees"].get("statut") != sante
                    or precedent["donnees"].get("unites_en_echec") != donnees["unites_en_echec"])
        derives = [k for k in ("cpu", "ram", "disque", "swap") if precedent and isinstance(donnees[k], (int, float))
                   and isinstance(precedent["donnees"].get(k), (int, float)) and abs(donnees[k] - precedent["donnees"][k]) >= 5]
        if a_change or derives or time.time() - etat["t"] >= 300:
            if precedent and precedent["etat"] == "muet":
                ctx.emettre("machine.reprise", objet=MACHINE, donnees={"statut": sante})
            elif precedent and precedent["donnees"].get("statut") not in (None, sante):
                ctx.emettre("machine.sante_change", objet=MACHINE, donnees={"de": precedent["donnees"].get("statut"), "a": sante})
            ctx.poser(*MACHINE, libelle, etat=sante, donnees=donnees)
            etat["t"] = time.time()
        etat["etat"] = sante

    # ------------------------------------------------------------------ la santé des modules du noyau
    suivi = {"modules": None, "erreur": "", "t": 0.0, "verdicts": {}, "admins": None}

    def releve_modules(ctx):
        """Relève ce que le noyau mesure déjà de CHAQUE module (moteurs, détecteurs suspendus, refus, constats) : un verdict par module. Un module qui tombe en échec se dit une fois ; son retour aussi.
        Ce que le démon ne peut pas voir de dedans, c'est ici qu'on le sait ; ce que le noyau ne peut pas dire de lui-même, c'est le démon qui le dit (voir CN_sensorium.collect_cassandra_v19)."""
        try:
            r = ctx.executer_lecture("modules.sante")
        except (PermissionError, ValueError, KeyError) as ex:
            suivi.update(modules=None, erreur="la santé des modules n'est pas lisible : %s" % str(ex)[:150], t=time.time())
            return
        mods = r.get("modules") if isinstance(r, dict) else None
        if not isinstance(mods, dict):
            suivi.update(modules=None, erreur="le noyau n'a rien rendu de la santé des modules", t=time.time())
            return
        avant, apres = suivi["verdicts"], {}
        for mid in sorted(mods):
            s = mods[mid] if isinstance(mods[mid], dict) else {}
            v = str(s.get("verdict") or "inconnu")
            apres[mid] = v
            if v == "en_echec" and avant.get(mid) != "en_echec":
                ctx.emettre("module_noyau.en_echec", objet=("module_noyau", mid), donnees={"en_echec": [str(x) for x in (s.get("en_echec") or [])[:6]]})
            elif v != "en_echec" and avant.get(mid) == "en_echec":
                ctx.emettre("module_noyau.retabli", objet=("module_noyau", mid), donnees={"verdict": v})
        suivi.update(modules=mods, erreur="", t=time.time(), verdicts=apres)
        try:                                                              # le dernier administrateur : sans lui, plus rien ne s'administre
            d = ctx.executer_lecture("droits.etat")
            suivi["admins"] = [str(a) for a in d.get("admins", [])] if isinstance(d, dict) else None
        except (PermissionError, ValueError, KeyError):
            suivi["admins"] = None

    def modules_en_echec(ctx):
        if suivi["modules"] is None:
            return [{"objet": MACHINE, "titre": "La santé des modules ne se lit plus", "detail": suivi["erreur"]}] if suivi["erreur"] else []
        res = []
        for mid, s in sorted(suivi["modules"].items()):
            if isinstance(s, dict) and s.get("verdict") == "en_echec":
                res.append({"objet": ("module_noyau", mid), "titre": "Le module « %s » est en échec" % mid,
                            "detail": ", ".join(str(x) for x in (s.get("en_echec") or [])) or "un moteur ou un détecteur est suspendu"})
        return res

    def sans_administrateur(ctx):
        if suivi["admins"] is not None and not suivi["admins"]:
            return [{"objet": ("module_noyau", "droits"), "titre": "Aucun administrateur", "detail": "Personne ne peut plus administrer Cassandra : ni comptes, ni modules, ni réglages."}]
        return []

    def collecteur_muet(ctx):
        m = machine(ctx)
        if m and m["etat"] == "muet":
            return [{"objet": MACHINE, "titre": "Le Sensorium ne répond plus", "detail": m["donnees"].get("erreur", "")}]
        return []

    def unites_en_echec(ctx):
        m = machine(ctx)
        n = m["donnees"].get("unites_en_echec", 0) if m and m["etat"] != "muet" else 0
        if n:
            return [{"objet": MACHINE, "titre": "%d unité%s systemd en échec" % (n, "s" if n > 1 else ""), "detail": "systemctl --failed"}]
        return []

    # ------------------------------------------------------------------ lectures
    def sante_lue(ctx):
        m = machine(ctx)
        return None if not m else dict(m["donnees"], etat=m["etat"], machine=m["libelle"])

    def metriques(ctx):
        """Les ressources de la machine, ou {muet: True, erreur} quand le collecteur ne répond pas (pas de socket Unix, collecteur arrêté) :
        une source muette ne dit rien, elle ne pose pas des zéros, et l'appel ne fait pas une erreur 500 à chaque chargement."""
        try:
            return json_de("GET_METRICS", 10)
        except (OSError, ValueError, RuntimeError) as ex:
            return {"muet": True, "erreur": str(ex)[:200]}

    def modules_lus(ctx):
        """La santé de chaque module telle que le noyau la mesure : verdict, moteurs, détecteurs coupés, ce que ses capacités ont fait en 24 h ; et les administrateurs."""
        if suivi["modules"] is None:
            return {"muet": True, "erreur": suivi["erreur"] or "pas encore relevée"}
        return {"muet": False, "lu_a": suivi["t"], "modules": suivi["modules"], "administrateurs": suivi["admins"]}

    def monde(ctx, prefixe=""):
        if prefixe and not _CLE.match(prefixe):
            raise ValueError("préfixe illisible")
        return json_de("GET_WORLD" + (":" + prefixe if prefixe else ""), 10)

    def entite(ctx, nom):
        if not isinstance(nom, str) or not _ENTITE.match(nom):
            raise ValueError("nom d'entité illisible")
        return json_de("GET_ENTITY:" + nom, 10)

    def historique(ctx, cle):
        if not isinstance(cle, str) or not _CLE.match(cle):
            raise ValueError("clé illisible")
        return json_de("GET_HISTORY:" + cle, 10)

    def secu(ctx):
        """Les totaux d'attaques du collecteur (journaux nginx : jours, heures, chemins, adresses, sites, robots), les mesures diverses (courriel, box, tailnet), la sauvegarde hors machine."""
        return json_de("GET_SECU", 20)

    def serie(ctx, mesure="", depuis="", jusqu_a=""):
        """Les points d'une mesure, lus dans l'historique du collecteur (la liste des courbes est fermée côté collecteur)."""
        if not isinstance(mesure, str) or not _CLE.match(mesure):
            raise ValueError("mesure illisible")
        from datetime import datetime as _dt
        try:
            jours = max(1, min(40, int((_dt.utcnow() - _dt.strptime(str(depuis)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")).total_seconds() // 86400) + 1))
        except ValueError:
            jours = 1
        return json_de("GET_SERIES:%s:%d" % (mesure, jours), 20)

    def changements(ctx, depuis=""):
        if depuis and not re.match(r"^[0-9T:\-. ]{1,40}$", str(depuis)):
            raise ValueError("date illisible")
        return json_de("GET_CHANGES" + (":" + str(depuis) if depuis else ""), 10)

    ctx.moteur("releve", releve)
    ctx.moteur("sante_modules", releve_modules)
    ctx.detecteur("modules_en_echec", modules_en_echec)
    ctx.detecteur("sans_administrateur", sans_administrateur)
    ctx.detecteur("collecteur_muet", collecteur_muet)
    ctx.detecteur("unites_en_echec", unites_en_echec)
    ctx.implementer("sante", sante_lue)
    ctx.implementer("metriques", metriques)
    ctx.implementer("modules", modules_lus)
    ctx.implementer("monde", monde)
    ctx.implementer("entite", entite)
    ctx.implementer("historique", historique)
    ctx.implementer("changements", changements)
    ctx.implementer("serie", serie)
    ctx.implementer("secu", secu)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : demander, json_de, _arrondi, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
