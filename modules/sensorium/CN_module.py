# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.2.6  #4ddd01
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module Sensorium : relie le noyau au collecteur (CN_sensorium.py), qui reste entier et tourne à part, en service root.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.6 empreinte=4ddd01 ▼▼▼
"""Le module Sensorium : relie le noyau au collecteur (CN_sensorium.py), qui reste entier et tourne à part, en service root.

Le collecteur mesure la machine et son monde. Ce module ne mesure rien : il le questionne par son socket (une requête texte, une réponse
JSON), en fait des objets, des constats et des tuiles, et le tient à l'oeil. Un collecteur muet se voit : c'est un constat, jamais un silence.
"""
import hashlib
import html
import json
import os
import re
import socket
import time
from datetime import datetime, timedelta, timezone

try:
    from . import CN_lecture as lec
    from . import CN_capteurs as capt
except ImportError:                        # chargé hors de son paquet (les bancs, l'outil de scellé) : le dossier est sur le chemin
    import CN_lecture as lec
    import CN_capteurs as capt

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


def _maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


_PORTEE = re.compile(r"^(\*|famille:[a-z0-9_]{1,30}|domaine:[a-z]{1,20}|machine:[A-Za-z0-9._-]{1,60})$")
_INSTANT = re.compile(r"^\d{4}-\d\d-\d\d[ T]\d\d:\d\d(:\d\d)?$")


def _instant(t, nom) -> str:
    t = str(t or "").strip().replace("T", " ")[:19]
    if not _INSTANT.match(t):
        raise ValueError("%s : un instant « AAAA-MM-JJ HH:MM » (heure UTC) est attendu" % nom)
    return t if len(t) == 19 else t + ":00"


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

    # ------------------------------------------------------------------ le monde : ce que le collecteur sait, accepté et en maintenance déduits
    monde_c = {"t": 0.0, "rows": None, "erreur": "", "vus": {}}
    def reglage_entier(ctx, nom):
        """Un seuil réglé (entier dans ses bornes), ou son défaut : un réglage illisible n'arrête rien."""
        d = lec.SEUILS[nom]
        try:
            v = ctx.reglage(nom)
        except Exception:
            return d[0]
        return v if isinstance(v, int) and not isinstance(v, bool) and d[1] <= v <= d[2] else d[0]

    def gravite_permise(ctx, g):
        try:
            return ctx.reglage("constat_" + g) is not False
        except Exception:
            return True

    def releve_monde(ctx):
        """Une lecture du modèle du monde, gardée : l'écran, les constats et la recherche la partagent au lieu de la redemander chacun."""
        try:
            rows = lec.lignes_du_monde(json_de("GET_WORLD", 20))
        except (OSError, ValueError, RuntimeError) as ex:
            monde_c.update(rows=None, erreur=str(ex)[:200], t=time.time())
            return
        vus = monde_c["vus"]
        monde_c.update(rows=rows, erreur="", t=time.time(), vus={r["wkey"]: vus.get(r["wkey"], 0) + 1 for r in rows if r.get("severity") == "warning"})
        try:                                     # les mesures du monde que l'on suit ou publie deviennent des lectures ; une panne ici ne touche jamais la relève
            capt.ingerer_monde(ctx, rows)
        except Exception as ex:
            ctx.log.warning("ingestion des mesures du monde : %s", ex)
        try:                                     # le moteur de recherche du module Web, s'il est installé et configuré : une lecture, jamais une écriture chez lui
            capt.ingerer_sante_web(ctx, ctx.executer_lecture("web.sante_moteur"))
        except PermissionError as ex:            # module Web absent ou inactif : normal, rien à dire toutes les minutes
            ctx.log.debug("mesure web.moteur indisponible : %s", ex)
        except Exception as ex:
            ctx.log.warning("mesure web.moteur : %s", ex)

    def monde_frais(ctx):
        if monde_c["rows"] is None or time.time() - monde_c["t"] > 45:
            releve_monde(ctx)
        return monde_c["rows"]

    def acceptations(ctx):
        """Les alertes acceptées encore valables (une échéance passée les efface)."""
        db = ctx.stockage
        db.ecrire("DELETE FROM sensorium_acceptations WHERE jusqua <> '' AND jusqua < ?", (_maintenant(),))
        return {r["wkey"]: dict(r, raison=html.unescape(str(r["raison"] or ""))) for r in db.lire("SELECT * FROM sensorium_acceptations")}

    def fenetres_en_cours(ctx, tout=False):
        n = _maintenant()
        sql = "SELECT * FROM sensorium_fenetres WHERE annulee = ''" + ("" if tout else " AND fin > ?") + " ORDER BY debut"
        return [dict(r) for r in ctx.stockage.lire(sql, () if tout else (n,))]

    def hote_de(rows):
        return next((str(r.get("value") or "") for r in rows or [] if r.get("wkey") == "system.hostname"), "")

    def alertes_du_monde(ctx):
        rows = monde_c["rows"]
        if rows is None:
            return []                            # le collecteur muet a son propre constat : on n'invente pas de pannes à partir de rien
        hote, n = hote_de(rows), _maintenant()
        acq, fen = acceptations(ctx), fenetres_en_cours(ctx)
        attente = reglage_entier(ctx, "releves_avant_constat")
        permises = {g[0]: gravite_permise(ctx, g[0]) for g in lec.GRAVITES}
        res = []
        for r in lec.appliquer_acquits(rows, acq):
            wk = r["wkey"]
            if r.get("severity") != "warning" or wk.startswith("health.") or lec.dans_fenetre(wk, fen, n, hote):
                continue
            if not permises[lec.gravite(wk)] or monde_c["vus"].get(wk, 0) < (1 if lec.immediat(wk) else attente):
                continue
            try:
                causes = (json.loads(r.get("detail") or "{}") or {}).get("causes_probables") or []
            except (ValueError, AttributeError):
                causes = []
            res.append({"objet": ("mesure", wk), "titre": "%s : %s" % (lec.libelle(wk), str(r.get("value") or "")[:140]), "detail": str(causes[0]) if causes else "", "niveau": lec.gravite(wk)})
        if len(res) > 60:                        # une panne générale ne fait pas soixante constats : un seul, qui dit combien
            res = res[:59] + [{"objet": ("mesure", "(autres)"), "titre": "%d autres mesures en alerte" % (len(res) - 59), "detail": "Voir le Sensorium."}]
        return res

    def etat_lu(ctx):
        """Tout ce que l'écran lit en une fois : les lignes du monde (nom en français, famille, objet, alerte acceptée, maintenance), les changements, les corrélations, les fenêtres."""
        rows = monde_frais(ctx)
        n = _maintenant()
        if rows is None:
            return {"ok": True, "muet": True, "erreur": monde_c["erreur"], "rows": [], "changes": [], "correlations": [], "fenetres": fenetres_en_cours(ctx), "maintenant": n,
                    "familles": [[i, l] for i, l, _ in lec.FAMILLES], "domaines": [[i, l, list(fs)] for i, l, fs in lec.DOMAINES], "genres": list(lec.GENRES)}
        hote, fen = hote_de(rows), fenetres_en_cours(ctx)
        sortie = []
        for r in lec.appliquer_acquits(rows, acceptations(ctx)):
            r = dict(r, libelle=lec.libelle(r["wkey"]), famille=lec.famille_de(r["wkey"]), gravite=lec.gravite(r["wkey"]))
            g = [{"id": x["id"], "libelle": x["libelle"]} for x in lec.gestes(r)]
            if g:
                r["gestes"] = g
            o = lec.objet_de(r["wkey"], hote)
            if o:
                r["objet"] = {"genre": o[0], "nom": o[1]}
            f = lec.dans_fenetre(r["wkey"], fen, n, hote)
            if f:
                r["maintenance"] = {"id": f["id"], "fin": f["fin"], "motif": f["motif"]}
            sortie.append(r)
        try:
            changes = json_de("GET_CHANGES", 10)
        except (OSError, ValueError, RuntimeError):
            changes = []
        try:
            corr = json_de("GET_CORRELATIONS", 10)
        except (OSError, ValueError, RuntimeError):
            corr = []                            # un démon d'avant cette lecture répond « ERROR » : pas de corrélations, pas d'erreur
        return {"ok": True, "muet": False, "source": "collecteur", "rows": sortie, "changes": changes if isinstance(changes, list) else [],
                "correlations": corr if isinstance(corr, list) else [], "hote": hote, "fenetres": fen, "maintenant": n, "lu_a": monde_c["t"],
                "familles": [[i, l] for i, l, _ in lec.FAMILLES], "domaines": [[i, l, list(fs)] for i, l, fs in lec.DOMAINES], "genres": list(lec.GENRES),
                "seuils": seuils_lus(ctx), "gravites": [{"id": g[0], "libelle": g[1], "dit": g[2], "ouvre": gravite_permise(ctx, g[0])} for g in lec.GRAVITES]}

    def seuils_lus(ctx):
        """Chaque seuil : son nom, son libellé, sa valeur, son défaut, ses bornes, et qui l'applique ; et où en est la pose chez le démon."""
        liste = [{"id": n, "libelle": d[3], "valeur": reglage_entier(ctx, n), "defaut": d[0], "min": d[1], "max": d[2], "qui": d[4]} for n, d in lec.SEUILS.items()]
        return {"liste": liste, "pose": monde_c.get("seuils") or {"poses": None, "erreur": "pas encore posés", "t": 0}}

    def pousser_seuils(ctx):
        """Les seuils du démon, réglés ici, sont posés dans son fichier par la commande root « seuils » : une fois au départ, puis à chaque changement ; un échec se redit toutes les cinq minutes."""
        voulus = {n: reglage_entier(ctx, n) for n, d in lec.SEUILS.items() if d[4] == "demon"}
        etat = monde_c.get("seuils")
        if etat and etat.get("poses") == voulus:
            return
        if etat and etat.get("erreur") and etat.get("voulus") == voulus and time.time() - etat.get("t", 0) < 300:
            return                                               # le même essai a échoué il y a moins de cinq minutes ; un seuil changé, lui, est tenté tout de suite
        try:
            r = ctx.racine("seuils", [], stdin=json.dumps(voulus), delai=15)
            sortie = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except Exception as ex:                                  # la commande n'est pas posée (banc, installation en cours) : on le dit, on réessaiera
            monde_c["seuils"] = {"poses": None, "erreur": str(ex)[:160] or "la commande « seuils » ne répond pas", "t": time.time(), "voulus": voulus}
            return
        if r.get("ok") and sortie.get("ok"):
            monde_c["seuils"] = {"poses": voulus, "erreur": "", "t": time.time()}
        else:
            monde_c["seuils"] = {"poses": None, "erreur": str(sortie.get("erreur") or r.get("erreur") or "refusés")[:160], "t": time.time(), "voulus": voulus}

    def releve_seuils(ctx):
        pousser_seuils(ctx)

    def seuils_pousser(ctx):
        """Les seuils réglés sont posés chez le démon TOUT DE SUITE (l'écran le demande après avoir enregistré). Dit où en est la pose."""
        monde_c["seuils"] = None
        pousser_seuils(ctx)
        e = monde_c.get("seuils") or {}
        return {"pose": bool(e.get("poses")), "erreur": e.get("erreur", "")}

    def accepter(ctx, wkey="", raison="", jours=30):
        wkey = str(wkey or "").strip()[:200]
        r = next((x for x in (monde_frais(ctx) or []) if x["wkey"] == wkey), None)
        if r is None:
            raise ValueError("mesure inconnue : « %s »" % wkey)
        try:
            j = max(0, min(365, int(jours or 0)))
        except (TypeError, ValueError):
            j = 30
        jusqua = (datetime.now(timezone.utc) + timedelta(days=j)).strftime("%Y-%m-%d %H:%M:%S") if j else ""
        db = ctx.stockage
        avant = db.lire("SELECT * FROM sensorium_acceptations WHERE wkey=?", (wkey,))
        db.ecrire("INSERT INTO sensorium_acceptations(wkey, raison, jusqua, valeur, par) VALUES (?,?,?,?,?) ON CONFLICT(wkey) DO UPDATE SET raison=excluded.raison, "
                  "jusqua=excluded.jusqua, valeur=excluded.valeur, par=excluded.par, ts=datetime('now')",
                  (wkey, html.unescape(str(raison or ""))[:300], jusqua, str(r.get("value") or "")[:300], ctx.compte or ctx.acteur or ""))
        return {"wkey": wkey, "jusqua": jusqua, "avant": dict(avant[0]) if avant else None}

    def accepte_prouve(ctx, res):
        return bool(ctx.stockage.lire("SELECT 1 FROM sensorium_acceptations WHERE wkey=?", (res["wkey"],)))

    def accepte_defait(ctx, res):
        a = res.get("avant")
        if a:
            ctx.stockage.ecrire("INSERT OR REPLACE INTO sensorium_acceptations(wkey, raison, jusqua, valeur, par, ts) VALUES (?,?,?,?,?,?)",
                                (a["wkey"], a["raison"], a["jusqua"], a["valeur"], a["par"], a["ts"]))
        else:
            ctx.stockage.ecrire("DELETE FROM sensorium_acceptations WHERE wkey=?", (res["wkey"],))

    def retirer_acceptation(ctx, wkey=""):
        wkey = str(wkey or "").strip()[:200]
        avant = ctx.stockage.lire("SELECT * FROM sensorium_acceptations WHERE wkey=?", (wkey,))
        ctx.stockage.ecrire("DELETE FROM sensorium_acceptations WHERE wkey=?", (wkey,))
        return {"wkey": wkey, "retire": bool(avant), "avant": dict(avant[0]) if avant else None}

    def retire_prouve(ctx, res):
        return not ctx.stockage.lire("SELECT 1 FROM sensorium_acceptations WHERE wkey=?", (res["wkey"],))

    def retire_defait(ctx, res):
        a = res.get("avant")
        if a:
            ctx.stockage.ecrire("INSERT OR REPLACE INTO sensorium_acceptations(wkey, raison, jusqua, valeur, par, ts) VALUES (?,?,?,?,?,?)",
                                (a["wkey"], a["raison"], a["jusqua"], a["valeur"], a["par"], a["ts"]))

    def fenetre_poser(ctx, portee="*", debut="", fin="", motif="", redemarrer=False):
        portee = str(portee or "*").strip()
        if not _PORTEE.match(portee):
            raise ValueError("portée illisible : « * », « famille:<id> », « domaine:<id> » ou « machine:<nom> »")
        d, f = _instant(debut, "début"), _instant(fin, "fin")
        if f <= d:
            raise ValueError("la fenêtre finit avant de commencer")
        if datetime.strptime(f, "%Y-%m-%d %H:%M:%S") - datetime.strptime(d, "%Y-%m-%d %H:%M:%S") > timedelta(days=14):
            raise ValueError("une fenêtre de maintenance ne dépasse pas quatorze jours")
        db = ctx.stockage
        db.ecrire("INSERT INTO sensorium_fenetres(portee, debut, fin, motif, redemarrer, par) VALUES (?,?,?,?,?,?)",
                  (portee, d, f, html.unescape(str(motif or ""))[:200], 1 if redemarrer else 0, ctx.compte or ctx.acteur or ""))
        return {"id": db.lire("SELECT MAX(id) AS i FROM sensorium_fenetres")[0]["i"], "portee": portee, "debut": d, "fin": f}

    def fenetre_prouvee(ctx, res):
        return bool(ctx.stockage.lire("SELECT 1 FROM sensorium_fenetres WHERE id=? AND annulee=''", (res["id"],)))

    def fenetre_defaite(ctx, res):
        ctx.stockage.ecrire("UPDATE sensorium_fenetres SET annulee=? WHERE id=?", (_maintenant(), res["id"]))

    def fenetre_annuler(ctx, id=0):
        try:
            i = int(id)
        except (TypeError, ValueError):
            raise ValueError("fenêtre illisible")
        if not ctx.stockage.lire("SELECT 1 FROM sensorium_fenetres WHERE id=?", (i,)):
            raise ValueError("fenêtre inconnue")
        ctx.stockage.ecrire("UPDATE sensorium_fenetres SET annulee=? WHERE id=? AND annulee=''", (_maintenant(), i))
        return {"id": i}

    def annulee_prouvee(ctx, res):
        return bool(ctx.stockage.lire("SELECT 1 FROM sensorium_fenetres WHERE id=? AND annulee<>''", (res["id"],)))

    def annulee_defaite(ctx, res):
        ctx.stockage.ecrire("UPDATE sensorium_fenetres SET annulee='' WHERE id=?", (res["id"],))

    def fenetres_lues(ctx):
        """Les fenêtres en cours, à venir, et les dix dernières finies ou annulées."""
        n = _maintenant()
        tout = [dict(r) for r in ctx.stockage.lire("SELECT * FROM sensorium_fenetres ORDER BY id DESC LIMIT 60")]
        vivantes = sorted((f for f in tout if not f["annulee"] and f["fin"] > n), key=lambda f: f["debut"])
        finies = [f for f in tout if f["annulee"] or f["fin"] <= n][:10]
        return {"maintenant": n, "vivantes": vivantes, "finies": finies}

    # ------------------------------------------------------------------ réparer en un clic : la table fermée est celle de la commande root
    DELAIS_GESTE = {"service": 150, "nginx": 120, "compose": 360, "journal": 150, "maj": 1000}

    def reparer(ctx, wkey="", geste=""):
        r = next((x for x in (monde_frais(ctx) or []) if x["wkey"] == str(wkey or "")), None)
        if r is None:
            raise ValueError("mesure inconnue : « %s »" % str(wkey)[:80])
        g = next((x for x in lec.gestes(lec.appliquer_acquits([r], acceptations(ctx))[0]) if x["id"] == str(geste or "")), None)
        if g is None:
            raise ValueError("ce geste ne s'applique pas (ou plus) à cette mesure")
        qui = ctx.compte or ctx.acteur or ""
        try:
            rep_ = ctx.racine("reparer", [g["op"]] + ([g["arg"]] if g["arg"] else []), delai=DELAIS_GESTE[g["op"]])
            sortie = json.loads((rep_.get("sortie") or "").strip().splitlines()[-1])
        except (ValueError, IndexError, KeyError, OSError, PermissionError) as ex:
            rep_, sortie = {"ok": False, "erreur": str(ex)}, {}
        ok = bool(rep_.get("ok") and sortie.get("ok"))
        texte = (sortie.get("sortie") if ok else (sortie.get("erreur") or rep_.get("erreur") or "le geste a échoué")) or ""
        ctx.stockage.ecrire("INSERT INTO sensorium_gestes(qui, wkey, geste, op, ok, sortie) VALUES (?,?,?,?,?,?)", (qui, r["wkey"], g["libelle"], g["op"], 1 if ok else 0, str(texte)[:600]))
        if not ok:
            raise ValueError(str(texte)[:300])
        return {"geste": g["libelle"], "op": g["op"], "verifie": bool(sortie.get("verifie")), "sortie": str(texte)[:600]}

    def gestes_journal(ctx):
        return {"gestes": [dict(x) for x in ctx.stockage.lire("SELECT ts, qui, wkey, geste, ok, sortie FROM sensorium_gestes ORDER BY id DESC LIMIT 20")]}

    def temoin(ctx):
        """Ce qu'il faut poser sur une AUTRE machine : le script, sa configuration (jeton et destinataire à remplir LÀ-BAS : Cassandra ne les connaît pas), et les pas. Rien n'est lancé d'ici."""
        def lu(nom):
            try:
                return str(ctx.reglage(nom) or "").strip()
            except Exception:
                return ""
        urls = [u for u in (lu("temoin_url_publique"), lu("temoin_url_lan")) if u]
        hote = hote_de(monde_c["rows"]) or socket.gethostname()
        sortie = {"urls": urls, "manque": [] if urls else ["temoin_url_publique"], "nom": hote}
        if urls:
            sortie.update(script=lec.TEMOIN_SCRIPT, config=lec.temoin_config(urls, hote), dossier="~/.cassandra-temoin",
                          unite="[Unit]\nDescription=Témoin de Cassandra\n\n[Service]\nExecStart=%h/.cassandra-temoin/temoin.sh\nRestart=always\n\n[Install]\nWantedBy=default.target\n")
        return sortie

    # ------------------------------------------------------------------ le démon : son état, son redémarrage
    def demon_lu(ctx):
        """L'état que le démon dit de lui-même (GET_DAEMON), et l'histoire de ses redémarrages. Un démon d'avant cette lecture répond « refusée » : on le dit, on ne le dit pas muet."""
        histoire = [dict(r) for r in ctx.stockage.lire("SELECT ts, qui, motif, silence_s, resultat FROM sensorium_redemarrages ORDER BY id DESC LIMIT 12")]
        try:
            d = json_de("GET_DAEMON", 8)
        except RuntimeError:
            return {"muet": False, "ancien": True, "redemarrages": histoire, "socket": SOCKET}
        except (OSError, ValueError) as ex:
            return {"muet": True, "erreur": str(ex)[:200], "redemarrages": histoire, "socket": SOCKET}
        return dict(d if isinstance(d, dict) else {}, muet=False, redemarrages=histoire, socket=SOCKET)

    def redemarrer(ctx, quand="apres_passe", motif=""):
        quand = str(quand or "apres_passe")
        if quand not in ("maintenant", "apres_passe"):
            raise ValueError("« maintenant » ou « apres_passe »")
        qui = ctx.compte or ctx.acteur or ""
        motif = html.unescape(str(motif or ""))[:200]
        r = ctx.racine("redemarrer", [quand], delai=240)
        try:
            sortie = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            sortie = {}
        if not r.get("ok") or not sortie.get("ok"):
            raison = str(sortie.get("erreur") or r.get("erreur") or "le redémarrage a échoué")[:200]
            ctx.stockage.ecrire("INSERT INTO sensorium_redemarrages(qui, motif, silence_s, resultat) VALUES (?,?,?,?)", (qui, motif, sortie.get("silence_s"), "échec : " + raison))
            raise ValueError(raison)
        ctx.stockage.ecrire("INSERT INTO sensorium_redemarrages(qui, motif, silence_s, resultat) VALUES (?,?,?,?)", (qui, motif, sortie.get("silence_s"), "revenu"))
        return {"silence_s": sortie.get("silence_s"), "attendu_s": sortie.get("attendu_s"), "avant": sortie.get("avant"), "apres": sortie.get("apres")}

    def redemarre_prouve(ctx, res):
        try:
            return json_de("GET_DAEMON", 8).get("pid") == (res.get("apres") or {}).get("pid")
        except (OSError, ValueError, RuntimeError, AttributeError):
            return False

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

    def erreurs_navigateur(ctx):
        """Des erreurs JavaScript qui se répètent dans les écrans : trois erreurs distinctes dans l'heure, ou dix occurrences. Une seule n'est pas un constat."""
        try:
            l = ctx.stockage.lire("SELECT COUNT(*) AS d, COALESCE(SUM(n), 0) AS t FROM sensorium_erreurs_js WHERE derniere > datetime('now', '-1 hour')")[0]
        except Exception:
            return []
        if l["d"] >= 3 or l["t"] >= 10:
            return [{"objet": ("module_noyau", "navigateur"), "titre": "%d erreur%s JavaScript dans les écrans (%d fois) depuis une heure" % (l["d"], "s" if l["d"] > 1 else "", l["t"]),
                     "detail": "Voir Sensorium › Les capteurs.", "niveau": "avoir"}]
        return []

    def erreur_navigateur(ctx, message="", source="", ligne=0, page=""):
        """Un écran signale une erreur JavaScript. Dédoublonnée (même message, même fichier, même ligne : un compteur), plafonnée (300 lignes, 14 jours)."""
        message = html.unescape(str(message or ""))[:300].strip()
        if not message:
            raise ValueError("une erreur sans message n'est pas retenue")
        source = str(source or "")[:200]
        try:
            ligne = max(0, min(10 ** 7, int(ligne or 0)))
        except (TypeError, ValueError):
            ligne = 0
        empreinte = hashlib.sha1(("%s|%s|%d" % (message, source, ligne)).encode("utf-8")).hexdigest()[:20]
        db = ctx.stockage
        db.ecrire("INSERT INTO sensorium_erreurs_js(empreinte, message, source, ligne, page, qui) VALUES (?,?,?,?,?,?) ON CONFLICT(empreinte) DO UPDATE SET n = n + 1, derniere = datetime('now'), page = excluded.page",
                  (empreinte, message, source, ligne, str(page or "")[:120], ctx.compte or ctx.acteur or ""))
        db.ecrire("DELETE FROM sensorium_erreurs_js WHERE derniere < datetime('now', '-14 days') OR id NOT IN (SELECT id FROM sensorium_erreurs_js ORDER BY derniere DESC LIMIT 300)")
        return {"empreinte": empreinte}

    def erreur_prouvee(ctx, res):
        return bool(ctx.stockage.lire("SELECT 1 FROM sensorium_erreurs_js WHERE empreinte=?", (res["empreinte"],)))

    def erreurs_lues(ctx):
        return {"erreurs": [dict(x) for x in ctx.stockage.lire("SELECT message, source, ligne, page, qui, n, premiere, derniere FROM sensorium_erreurs_js ORDER BY derniere DESC LIMIT 30")]}

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
    ctx.moteur("monde", releve_monde)
    ctx.moteur("seuils", releve_seuils)
    ctx.detecteur("alertes_du_monde", alertes_du_monde)
    ctx.moteur("sante_modules", releve_modules)
    ctx.detecteur("modules_en_echec", modules_en_echec)
    ctx.detecteur("sans_administrateur", sans_administrateur)
    ctx.detecteur("collecteur_muet", collecteur_muet)
    ctx.detecteur("unites_en_echec", unites_en_echec)
    ctx.detecteur("erreurs_navigateur", erreurs_navigateur)
    ctx.implementer("sante", sante_lue)
    ctx.implementer("metriques", metriques)
    ctx.implementer("modules", modules_lus)
    ctx.implementer("etat", etat_lu)
    ctx.implementer("demon", demon_lu)
    ctx.implementer("reparer", reparer, lambda c, res: bool(res.get("verifie")), lambda c, res: None)
    ctx.implementer("gestes_journal", gestes_journal)
    ctx.implementer("seuils_pousser", seuils_pousser, lambda c, res: bool(res.get("pose")), lambda c, res: None)
    ctx.implementer("temoin", temoin)
    ctx.implementer("redemarrer", redemarrer, redemarre_prouve, lambda c, res: None)
    ctx.implementer("fenetres", fenetres_lues)
    ctx.implementer("accepter", accepter, accepte_prouve, accepte_defait)
    ctx.implementer("retirer_acceptation", retirer_acceptation, retire_prouve, retire_defait)
    ctx.implementer("fenetre_poser", fenetre_poser, fenetre_prouvee, fenetre_defaite)
    ctx.implementer("fenetre_annuler", fenetre_annuler, annulee_prouvee, annulee_defaite)
    ctx.implementer("erreur_navigateur", erreur_navigateur, erreur_prouvee, lambda ctx, res: None)
    ctx.implementer("erreurs_navigateur", erreurs_lues)
    ctx.implementer("monde", monde)
    ctx.implementer("entite", entite)
    ctx.implementer("historique", historique)
    ctx.implementer("changements", changements)
    ctx.implementer("serie", serie)
    ctx.implementer("secu", secu)

    # ------------------------------------------------------------------ les mesures de première classe (CN_capteurs.py, docs/CN_SENSORIUM_EVOLUTION.md)
    ctx.moteur("suivi_mesures", capt.tour_suivi)
    ctx.detecteur("capteurs_suivis_muets", capt.suivies_muettes)
    ctx.implementer("capteur_declarer", capt.capteur_declarer, capt.declare_prouve, capt.declare_defait)
    ctx.implementer("capteur_retirer", capt.capteur_retirer, capt.retire_prouve, capt.retire_defait)
    ctx.implementer("capteur_alimenter", capt.capteur_alimenter, capt.alimente_prouve, lambda c, res: None)
    ctx.implementer("mesure_suivre", capt.mesure_suivre, capt.suivre_prouve, capt.suivre_defait)
    ctx.implementer("mesure_ne_plus_suivre", capt.mesure_ne_plus_suivre, capt.ne_suit_prouve, capt.ne_suit_defait)
    ctx.implementer("mesure_publier", capt.mesure_publier, capt.publier_prouve, capt.publier_defait)
    ctx.implementer("lien_poser", capt.lien_poser, capt.lien_prouve, capt.lien_defait)
    ctx.implementer("lien_retirer", capt.lien_retirer, capt.delie_prouve, capt.delie_defait)
    for nom in ("mesure_etat", "vue_minimale", "mesure_detail", "mesures_suivies", "prevision_mesure", "autoobservation", "liens", "impact"):
        ctx.implementer(nom, getattr(capt, nom))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : demander, json_de, _arrondi, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
