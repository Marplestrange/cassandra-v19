# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.9  #0019f3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module Sensorium : relie le noyau au collecteur (CN_sensorium.py), qui reste entier et tourne à part, en service root.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.9 empreinte=0019f3 ▼▼▼
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
        return json_de("GET_METRICS", 10)

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
    ctx.detecteur("collecteur_muet", collecteur_muet)
    ctx.detecteur("unites_en_echec", unites_en_echec)
    ctx.implementer("sante", sante_lue)
    ctx.implementer("metriques", metriques)
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
