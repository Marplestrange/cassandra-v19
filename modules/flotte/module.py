import json
import time
import re
import socket
import os
from datetime import datetime, timedelta, timezone

# --- CONSTANTES V18 ---
_EMOJI_MAP = {'ssh': '🖥', 'synology': '🖧', 'proxmox': '🧱', 'ping': '📡', 'cassandra': '🤖'}
_FLOTTE_DEPOT = "/opt/cassandra/travail/flotte"
_FLOTTE_FICHIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,120}$")
_FLOTTE_MAX_OCTETS = 512 * 1024 * 1024
_FLOTTE_OUBLI_JOURS = 30
_FLOTTE_NIVEAUX = ("signal", "observation", "ssh", "agent")
_FLOTTE_STATUTS = ("attendue", "intermittente", "retiree")

SENSORIUM_NOTIF_APRES_S = 600
SENSORIUM_FERMER_APRES_S = 120
_SENSORIUM_IMMEDIAT = ("cle_ssh.", "box.redirection.", "box.upnp", "box.dmz", "box.acces_distant",
                       "tailnet.nouveau.", "tailnet.partage", "pare_feu.socle", "outil_secu.clamav")
_SENSORIUM_CRITIQUES = ("stockage.", "montage.", "web.", "controle.tls.", "systemd.failed_units")

_FLEET_ACTIONS = {
    "diagnostic": ("uptime; echo '---'; df -h; echo '---'; free -m; echo '---'; systemctl --failed --no-pager 2>/dev/null | head -20", False, "Charge, disques, mémoire et unités en échec."),
    "svc_restart": ("systemctl restart %(service)s && systemctl status %(service)s --no-pager | head -20", True, "Redémarre un service.")
}
_FLEET_SVC_VITAUX = {"ssh", "sshd", "network", "networking", "systemd-networkd", "NetworkManager", "systemd-journald"}
_FLEET_LINK_KINDS = ("project", "contact", "domain", "note")


def brancher(ctx):
    db = ctx.stockage

    def _utcnow():
        return datetime.now(timezone.utc)

    def _flotte_nom(nom):
        return str(nom or "").strip().lower()

    def _fleet_etats():
        try:
            return json.loads(ctx.reglage("fleet_etats") or "{}")
        except:
            return {}

    def _flotte_niveaux():
        try:
            return json.loads(ctx.reglage("fleet_niveaux") or "{}")
        except:
            return {}

    def _load_machines():
        return [dict(m) for m in db.lire("SELECT * FROM machines")]

    def _flotte_serveur(nom):
        for m in _load_machines():
            if _flotte_nom(m.get("nom")) == _flotte_nom(nom):
                return m
        return {}

    def _fleet_duree(minutes: int) -> str:
        m = max(0, int(minutes or 0))
        if m < 60: return "%d min" % m
        if m < 1440: return "%d h %02d" % (m // 60, m % 60)
        return "%d j %d h" % (m // 1440, (m % 1440) // 60)

    def _fleet_minutes(depuis: str, jusqua: str) -> int:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                a = datetime.strptime((depuis or "")[:19], fmt)
                b = datetime.strptime((jusqua or "")[:19], fmt)
                return max(0, int((b - a).total_seconds() // 60))
            except Exception:
                continue
        return 0

    def _ms_ssh_exec(machine, cmd, timeout=30):
        # TODO(ssh) : exécuter la commande via paramiko ou proxy.
        # En V18, passait par SSH directement. V19 doit utiliser le système ou l'API.
        return "", "", 0

    # ── MOTEURS ──
    def moteur_presence(ctx):
        if not ctx.reglage("fleet_watch_enabled"):
            return
        # TODO(tailscale): _flotte_tailscale_live()
        live = {} 
        etats = _fleet_etats()
        registre = {_flotte_nom(m["nom"]) for m in _load_machines()}
        maintenant = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        connus = {r["name"]: (r["online"], r["since"], r["ts"]) 
                  for r in db.lire("SELECT name, online, since, ts FROM fleet_state_seen")}
        
        for nom, p in live.items():
            if nom.startswith("_") or p.get("self") or nom in registre or etats.get(nom) == "retiree":
                continue
            en_ligne = 1 if p.get("online") else 0
            db.ecrire("INSERT INTO fleet_status (ts,name,type,online,error) VALUES (?,?,?,?,?)",
                      (maintenant, nom, "signal", en_ligne, ""))
            avant = connus.get(nom)
            if avant is None:
                db.ecrire("INSERT OR REPLACE INTO fleet_state_seen (name,online,since,ts) VALUES (?,?,?,?)",
                          (nom, en_ligne, maintenant, maintenant))
                db.ecrire("INSERT INTO fleet_events (ts,name,kind,detail) VALUES (?,?,?,?)",
                          (maintenant, nom, "decouverte", "Première observation"))
                continue
            if avant[0] == en_ligne:
                db.ecrire("UPDATE fleet_state_seen SET ts=? WHERE name=?", (maintenant, nom))
                continue
            duree = _fleet_minutes(avant[1], maintenant)
            db.ecrire("INSERT OR REPLACE INTO fleet_state_seen (name,online,since,ts) VALUES (?,?,?,?)",
                      (nom, en_ligne, maintenant, maintenant))
            db.ecrire("INSERT INTO fleet_events (ts,name,kind,detail,duration_min) VALUES (?,?,?,?,?)",
                      (maintenant, nom, "retour" if en_ligne else "perte", "Transition", duree))
            
            # V18 : alerter via notification au lieu du fil proactif
            if en_ligne:
                ctx.emettre("parc_machine.revenue", objet=("parc_machine", nom), donnees={"duree_min": duree})
            else:
                ctx.emettre("parc_machine.perdue", objet=("parc_machine", nom), donnees={})

    def moteur_sensorium(ctx):
        # TODO(ssh): boucle de relevés SSH sur les machines ("flotte_sensorium_passe")
        # Enregistre dans world_model
        pass

    ctx.moteur("presence", moteur_presence)
    ctx.moteur("sensorium_sondes", moteur_sensorium)

    # ── DÉTECTEUR ──
    # V18: "Le Sensorium qui prévient sans polluer. Une alerte n'est notifiée que si elle DURE (10 min)..."
    def detecteur_alertes(ctx):
        rows = db.lire("SELECT * FROM world_model")
        # V18: filtre des absences volontaires
        etats = _fleet_etats()
        filtrés = []
        for r in rows:
            wk = r["wkey"]
            if wk.startswith("fleet.") or wk.startswith("machine."):
                nom = wk[6:] if wk.startswith("fleet.") else wk.split(".")[1]
                st = etats.get(_flotte_nom(nom), "attendue")
                if st == "retiree": continue
                if st == "intermittente" and r["severity"] == "warning":
                    r = dict(r)
                    r["severity"] = "info"
            filtrés.append(r)
            
        acquits = {a["wkey"]: a for a in db.lire("SELECT * FROM sensorium_acquits WHERE jusqua = '' OR jusqua > ?", 
                                                 (_utcnow().strftime("%Y-%m-%d %H:%M:%S"),))}
        actives = {r["wkey"]: r for r in filtrés if r["severity"] == "warning" and r["wkey"] not in acquits}
        now = _utcnow()
        fmt = "%Y-%m-%d %H:%M:%S"
        
        etat_alertes = {r["wkey"]: r for r in db.lire("SELECT * FROM sensorium_alertes")}
        
        # V18: transaction courte, on décide puis on renvoie à la cloche
        constats = []
        with db.transaction() as c:
            for wk, r in actives.items():
                val = str(r["value"])
                e = etat_alertes.get(wk)
                if not e:
                    c.execute("INSERT INTO sensorium_alertes (wkey, depuis, valeur) VALUES (?,?,?)",
                              (wk, now.strftime(fmt), val))
                    if wk.startswith(_SENSORIUM_IMMEDIAT):
                        e = {"depuis": now.strftime(fmt), "valeur": None}
                    else:
                        continue # wait next tick
                if e.get("ok_depuis"):
                    c.execute("UPDATE sensorium_alertes SET ok_depuis = NULL WHERE wkey = ?", (wk,))
                age = (now - datetime.strptime(e["depuis"], fmt)).total_seconds()
                delai = 0 if wk.startswith(_SENSORIUM_IMMEDIAT) else SENSORIUM_NOTIF_APRES_S
                
                if age >= delai:
                    niveau = "critique" if wk.startswith(_SENSORIUM_CRITIQUES) else ("avoir" if wk.startswith(_SENSORIUM_IMMEDIAT) else "info")
                    constats.append({"objet": ("entite", wk), "titre": wk, "detail": val, "niveau": niveau})
            
            for wk, e in etat_alertes.items():
                if wk in actives: continue
                if not e.get("ok_depuis"):
                    c.execute("UPDATE sensorium_alertes SET ok_depuis = ? WHERE wkey = ?", (now.strftime(fmt), wk))
                    # V18: un collecteur muet ne ferme rien, on garde le constat ouvert par précaution le temps qu'il se résolve.
                    constats.append({"objet": ("entite", wk), "titre": wk, "detail": e["valeur"], "niveau": "info"})
                    continue
                age_ok = (now - datetime.strptime(e["ok_depuis"], fmt)).total_seconds()
                if age_ok < SENSORIUM_FERMER_APRES_S and wk not in acquits:
                    constats.append({"objet": ("entite", wk), "titre": wk, "detail": e["valeur"], "niveau": "info"})
                else:
                    c.execute("DELETE FROM sensorium_alertes WHERE wkey=?", (wk,))
                    
        return constats

    ctx.detecteur("alertes", detecteur_alertes)

    # ── CAPACITÉS ──
    def parc(ctx):
        M = _load_machines()
        return {"machines": M}

    def verdict(ctx):
        # V18 : Ce que le parc dit à l'ouverture. Une machine attendue en panne est prioritaire.
        return {"verdict": "Tout le parc répond."}

    def ping(ctx, nom=""):
        # TODO(tailscale): exécuter `tailscale ping`
        return {"ok": False, "reason": "non branché à tailscale CLI"}

    def historique(ctx, nom="", hours=24):
        h = max(1, min(int(hours or 24), 24 * 90))
        depuis = (_utcnow() - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")
        lignes = db.lire("SELECT * FROM fleet_status WHERE name=? AND ts >= ? ORDER BY ts", (nom, depuis))
        return {"machine": nom, "samples": len(lignes), "history": lignes}

    def engagement(ctx, nom="", statut="", niveau=""):
        nom = _flotte_nom(nom)
        if statut and statut not in _FLOTTE_STATUTS: raise ValueError("statut inconnu")
        if niveau and niveau not in _FLOTTE_NIVEAUX: raise ValueError("niveau inconnu")
        
        cfg_etats = _fleet_etats()
        cfg_niv = _flotte_niveaux()
        
        avant = {"statut": cfg_etats.get(nom, "attendue"), "niveau": cfg_niv.get(nom, "")}
        
        if statut:
            cfg_etats[nom] = statut
            ctx.executer_ecriture("reglages", "modifier", {"id": "fleet_etats", "valeur": json.dumps(cfg_etats)})
        if niveau:
            cfg_niv[nom] = niveau
            ctx.executer_ecriture("reglages", "modifier", {"id": "fleet_niveaux", "valeur": json.dumps(cfg_niv)})
            
        return {"avant": avant, "apres": {"statut": statut, "niveau": niveau}, "nom": nom}

    def prouver_engagement(ctx, res):
        nom = res["nom"]
        st = _fleet_etats().get(nom, "attendue")
        ni = _flotte_niveaux().get(nom, "")
        return st == res["apres"]["statut"] if res["apres"]["statut"] else True

    def defaire_engagement(ctx, res):
        nom = res["nom"]
        cfg_etats = _fleet_etats()
        cfg_niv = _flotte_niveaux()
        cfg_etats[nom] = res["avant"]["statut"]
        cfg_niv[nom] = res["avant"]["niveau"]
        ctx.executer_ecriture("reglages", "modifier", {"id": "fleet_etats", "valeur": json.dumps(cfg_etats)})
        ctx.executer_ecriture("reglages", "modifier", {"id": "fleet_niveaux", "valeur": json.dumps(cfg_niv)})

    def oublier(ctx, nom=""):
        # V18 : Efface TOUTES les traces d'un nom : présence, sonde, entité Sensorium
        nom = _flotte_nom(nom)
        if _flotte_serveur(nom): raise ValueError("%s est au registre Serveurs : efface-la d'abord." % nom)
        
        fait = []
        with db.transaction() as c:
            for t in ("fleet_state_seen", "fleet_ssh_sonde"):
                c.execute(f"DELETE FROM {t} WHERE name=?", (nom,))
            c.execute("INSERT INTO fleet_events (ts,name,kind,detail) VALUES (?,?,?,?)",
                      (_utcnow().strftime("%Y-%m-%d %H:%M:%S"), nom, "oubli", "Traces effacées"))
            c.execute("DELETE FROM world_model WHERE wkey=?", ("fleet.%s" % nom,))
            fait.append("effacé")
            
        return {"nom": nom, "traces": fait}

    def prouver_oublier(ctx, res):
        return len(db.lire("SELECT name FROM fleet_state_seen WHERE name=?", (res["nom"],))) == 0

    def action_run(ctx, machine="", action="", service=""):
        spec = _FLEET_ACTIONS.get(action)
        if not spec: raise ValueError("Action inconnue")
        gabarit, modifie, _ = spec
        m = _flotte_serveur(machine)
        if not m: raise ValueError("Machine introuvable")
        
        cmd = gabarit % {"service": service} if service else gabarit
        # TODO(ssh): _ms_ssh_exec(m, cmd)
        return {"machine": machine, "action": action, "output": "TODO"}

    def sensorium_accepter(ctx, wkey="", raison="", jours=30):
        wkey = str(wkey or "").strip()
        j = max(0, min(365, int(jours or 0)))
        jusqua = (_utcnow() + timedelta(days=j)).strftime("%Y-%m-%d %H:%M:%S") if j else ""
        
        avant = db.lire("SELECT * FROM sensorium_acquits WHERE wkey=?", (wkey,))
        db.ecrire("INSERT INTO sensorium_acquits (wkey, raison, jusqua, valeur, par) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(wkey) DO UPDATE SET raison=excluded.raison, jusqua=excluded.jusqua",
                  (wkey, raison, jusqua, "", ctx.compte))
        return {"wkey": wkey, "avant": dict(avant[0]) if avant else None}

    def defaire_acquit(ctx, res):
        wkey = res["wkey"]
        if res["avant"]:
            db.ecrire("UPDATE sensorium_acquits SET raison=?, jusqua=? WHERE wkey=?", 
                      (res["avant"]["raison"], res["avant"]["jusqua"], wkey))
        else:
            db.ecrire("DELETE FROM sensorium_acquits WHERE wkey=?", (wkey,))

    def sensorium_retirer_acquit(ctx, wkey=""):
        avant = db.lire("SELECT * FROM sensorium_acquits WHERE wkey=?", (wkey,))
        if not avant: raise ValueError("Acquit introuvable")
        db.ecrire("DELETE FROM sensorium_acquits WHERE wkey=?", (wkey,))
        return {"wkey": wkey, "avant": dict(avant[0])}

    ctx.implementer("parc", parc)
    ctx.implementer("verdict", verdict)
    ctx.implementer("ping", ping)
    ctx.implementer("historique", historique)
    ctx.implementer("engagement", engagement, prouver_engagement, defaire_engagement)
    ctx.implementer("oublier", oublier, prouver_oublier, lambda ctx, res: None)
    ctx.implementer("action_run", action_run, lambda ctx, res: True, lambda ctx, res: None)
    ctx.implementer("sensorium_accepter", sensorium_accepter, lambda ctx, res: True, defaire_acquit)
    ctx.implementer("sensorium_retirer_acquit", sensorium_retirer_acquit, lambda ctx, res: True, 
                    lambda ctx, res: sensorium_accepter(ctx, res["wkey"], res["avant"]["raison"], 30))
