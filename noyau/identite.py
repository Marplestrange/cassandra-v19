"""L'identité des comptes : qui est qui, et la preuve qu'on l'est. Portée de la V18 (load_users, set_user, verify_user, sessions,
jetons de mot de passe), à une différence près, voulue : le mot de passe n'est plus un SHA-256 nu mais un scrypt salé.

  - l'identifiant d'un compte EST une adresse e-mail (un compte Cassandra = un compte du coffre, même identifiant) ;
  - les règles du mot de passe sont celles de la V18, et la légende vient de la même table : elle ne peut pas promettre autre chose ;
  - le rôle « administrateur » n'est plus un champ du compte : il vit dans les droits (noyau/droits.py), une seule vérité ;
  - le compte au nom duquel on agit n'est pas un global : c'est `ctx.compte`, posé par l'exécuteur pour la durée d'une capacité.

Le jeton de session n'est jamais stocké : seule son empreinte l'est, et son identifiant d'écran est son empreinte courte
(les six derniers caractères du jeton, comme en V18, ne servent qu'à le DÉSIGNER à son propre compte).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import os
import secrets
import subprocess
import time

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MDP_MIN, MDP_MAX = 9, 20
MDP_REGLES = (
    ("longueur", "de %d à %d caractères" % (MDP_MIN, MDP_MAX), lambda p: MDP_MIN <= len(p) <= MDP_MAX),
    ("majuscule", "au moins une majuscule", lambda p: any(c.isupper() for c in p)),
    ("chiffre", "au moins un chiffre", lambda p: any(c.isdigit() for c in p)),
    ("special", "au moins un caractère spécial (!?#@…)", lambda p: any((not c.isalnum()) and not c.isspace() for c in p)),
)
# Les comptes SYSTÈME : ceux au nom desquels agissent le noyau, l'opérateur local (ligne de commande, root), Cassandra et Itare. Pas d'e-mail,
# pas de mot de passe, aucune session possible : ils existent pour que TOUT acte ait un compte, donc un auteur retraçable.
COMPTES_SYSTEME = {
    "noyau": ("Le noyau", True),              # (libellé, administrateur ?) : ses moteurs, ses détecteurs, la reprise après incident
    "operateur": ("L'opérateur local (root, ligne de commande)", True),
    "cassandra": ("Cassandra", True),         # la patronne : souveraine, donc administratrice par défaut (l'administrateur peut le changer)
    "itare": ("Itare", False),                # le sous-chef : les droits par défaut seulement, à étendre par choix
    # Les rôles d'agents, un compte chacun pour que chaque acte ait son auteur. Aucun n'est administrateur : l'administrateur leur donne ce qu'il veut.
    "itare_compte": ("Itare personnalisé par compte (la clé API et le modèle du compte, sinon le local)", False),
    "vision": ("Itare Vision : lit les images de tous les comptes", False),
    "second_avis": ("Second avis (Proactivité, règles) : relit les actes à risque élevé", False),
    "restauration": ("Restauration (Proactivité, règles) : remet en l'état ce qui doit l'être", False),
}
RE_AGENT = re.compile(r"^agent:[a-z][a-z0-9_-]{1,30}$")
CHAMPS_PROFIL = ("display_name", "role_label", "contact_email", "phone", "lang", "fp_account")
TENTATIVES_MAX, TENTATIVES_FENETRE = 10, 300       # comme la V18 : dix échecs en cinq minutes
TTL_SESSION_HEURES = 24
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


def norm_domain(d) -> str:
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def mdp_regles() -> list:
    return [{"cle": c, "dit": d} for c, d, _ in MDP_REGLES]


def mdp_valider(pwd) -> dict:
    """Rend ce qui MANQUE, pas seulement un verdict."""
    p = pwd or ""
    manque = [d for c, d, f in MDP_REGLES if not f(p)]
    return {"ok": not manque, "manque": manque, "error": ("Mot de passe : il manque " + ", ".join(manque)) if manque else ""}


def mdp_legende() -> str:
    return "Il faut " + ", ".join(d for _, d, _ in MDP_REGLES) + "."


def hacher(pwd: str) -> str:
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(pwd.encode("utf-8"), salt=sel, **_SCRYPT)
    return "scrypt$%s$%s" % (sel.hex(), h.hex())


def hash_ok(pwd: str, enregistre: str) -> bool:
    try:
        algo, sel, h = enregistre.split("$")
        if algo != "scrypt":
            return False
        calcul = hashlib.scrypt((pwd or "").encode("utf-8"), salt=bytes.fromhex(sel), **_SCRYPT)
        return hmac.compare_digest(calcul, bytes.fromhex(h))
    except (ValueError, TypeError):
        return False


def ip_nature(ip) -> str:
    """« serveur », « local », « internet » ou vide, sans jamais interroger personne (une géolocalisation dirait à un tiers qui se connecte d'où)."""
    ip = (ip or "").strip()
    if not ip:
        return ""
    if ip in ("127.0.0.1", "::1", "localhost"):
        return "serveur"
    p = ip.split(".")
    try:
        if p[0] == "10" or (p[0] == "192" and p[1] == "168"):
            return "local"
        if p[0] == "172" and 16 <= int(p[1]) <= 31:
            return "local"
    except (IndexError, ValueError):
        pass
    return "local" if ip.startswith(("fc", "fd", "fe80")) else "internet"


RE_UNIX = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def fastpanel_present() -> bool:
    """FastPanel est-il installé ? Il dépend de « fastuser » : tant qu'il l'est, le superadministrateur ne se touche pas."""
    import shutil
    return os.path.isdir("/usr/local/fastpanel2") or shutil.which("mogwai") is not None


def deposer_sudo(dossier, utilisateur: str) -> bool:
    """Demande au courtier (root) de mettre `utilisateur` dans le groupe sudo : le deuxième superadministrateur devient root par sudo, lui aussi."""
    if not dossier:
        return False
    os.makedirs(dossier, exist_ok=True)
    nom = "sudo-%d-%s" % (int(time.time()), secrets.token_hex(4))
    tmp = os.path.join(dossier, nom + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"action": "ajouter_sudo", "utilisateur": utilisateur}, f)
    os.replace(tmp, os.path.join(dossier, nom + ".json"))
    return True


def empreinte_sha512(mdp: str):
    """L'empreinte SHA-512 salée du mot de passe, au format de /etc/shadow ($6$...), calculée par openssl (mot de passe par l'entrée standard,
    jamais en argument). C'est tout ce qui part vers le courtier : le mot de passe, lui, ne quitte jamais cette fonction."""
    try:
        r = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input=mdp + "\n", capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    h = (r.stdout or "").strip()
    return h if r.returncode == 0 and h.startswith("$6$") else None


def deposer_demande(dossier, utilisateur: str, mdp: str) -> bool:
    """Dépose la demande « adosser_superadmin » pour le courtier (voir exploitation/courtier.py). Écrite entière puis renommée : le courtier
    ne voit jamais un fichier à moitié écrit."""
    h = empreinte_sha512(mdp)
    if not h or not dossier:
        return False
    os.makedirs(dossier, exist_ok=True)
    nom = "adosser-%d-%s" % (int(time.time()), secrets.token_hex(4))
    tmp = os.path.join(dossier, nom + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"action": "adosser_superadmin", "utilisateur": utilisateur, "empreinte": h}, f)
    os.replace(tmp, os.path.join(dossier, nom + ".json"))
    return True


def interpreteur_unix(nom: str):
    """L'interpréteur de commandes de l'utilisateur système `nom`, ou None s'il n'existe pas."""
    try:
        import pwd
        return pwd.getpwnam(nom).pw_shell
    except (ImportError, KeyError):
        return None


def shell_de_connexion(shell) -> bool:
    """Un vrai interpréteur (bash, sh, zsh...), pas nologin ni false : le superadmin doit pouvoir ouvrir une session système."""
    return bool(shell) and shell.rsplit("/", 1)[-1] in ("bash", "sh", "dash", "zsh", "ksh", "fish")


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


class Identite:
    def __init__(self, base, droits, ttl_heures=TTL_SESSION_HEURES, unix_superadmin="fastuser", unix=None, courtier=None):
        self.base = base
        self.droits = droits
        self.unix_superadmin = unix_superadmin       # l'utilisateur système du premier compte, comme « fastuser » chez FastPanel
        self.unix = unix or interpreteur_unix        # nom -> son interpréteur de commandes (None : l'utilisateur n'existe pas)
        self.courtier = courtier                     # le dossier où l'on dépose les demandes au courtier (root) ; None : pas de courtier
        self.adosser = lambda utilisateur, mdp: deposer_demande(self.courtier, utilisateur, mdp)
        self.sudo = lambda utilisateur: deposer_sudo(self.courtier, utilisateur)
        self.fastpanel = fastpanel_present            # appelable : FastPanel est-il là ? (verrou du superadministrateur)
        droits.verrou = self.verrou_superadmin
        self.ttl = int(ttl_heures) * 3600
        self._faux = hacher("sel-de-leurre")      # un compte inconnu coûte le même temps qu'un mauvais mot de passe
        self.amorcer_systeme()

    def verrou_superadmin(self, compte: str) -> str:
        """Pourquoi on ne retire pas l'administration à ce compte ("" : on peut). Conditionnel : seul le superadmin ET seulement si FastPanel est là."""
        r = self.base.lire("SELECT superadmin FROM comptes WHERE compte=?", (compte,))
        if r and r[0]["superadmin"] and self.fastpanel():
            return "Verrouillé : « %s » est le superadministrateur et FastPanel est installé, qui dépend de son utilisateur système" % compte
        return ""

    def amorcer_systeme(self) -> None:
        """Les comptes système existent toujours. Leurs droits ne sont posés qu'UNE fois : ce que l'administrateur règle ensuite lui appartient."""
        now = time.time()
        for cid, (libelle, admin) in COMPTES_SYSTEME.items():
            self.base.ecrire("INSERT OR IGNORE INTO comptes(compte, hash, display_name, cree, maj, type) VALUES(?,?,?,?,?,'systeme')", (cid, "", libelle, now, now))
        if not self.base.lire("SELECT 1 FROM etat_noyau WHERE cle='comptes_systeme_amorces'"):
            for cid, (libelle, admin) in COMPTES_SYSTEME.items():
                if admin:
                    self.droits.regler_admin(cid, True)
            self.base.ecrire("INSERT OR REPLACE INTO etat_noyau(cle, valeur) VALUES('comptes_systeme_amorces', '1')")

    # ---- les comptes ----
    @staticmethod
    def _ligne(r: dict) -> dict:
        r = dict(r)
        r.pop("hash", None)
        r["sites"] = json.loads(r.get("sites") or "[]")
        return r

    def existe(self, compte: str) -> bool:
        return bool(self.base.lire("SELECT 1 FROM comptes WHERE compte=?", (compte,)))

    def creer_agent(self, nom: str, libelle: str = "") -> dict:
        """Un agent INVITÉ (le compte s'ajoute à son jeton, il ne le remplace pas) : « agent:<nom> », sans mot de passe, sans droit tant qu'on ne lui en donne pas."""
        cid = "agent:" + (nom or "").strip().lower()
        if not RE_AGENT.match(cid):
            return {"ok": False, "error": "Nom d'agent : minuscules, chiffres, - et _ (2 à 31 caractères)"}
        if self.existe(cid):
            return {"ok": False, "error": "Cet agent existe déjà"}
        now = time.time()
        self.base.ecrire("INSERT INTO comptes(compte, hash, display_name, cree, maj, type) VALUES(?,?,?,?,?,'agent')", (cid, "", (libelle or nom).strip(), now, now))
        return {"ok": True, "compte": cid}

    def lire(self, compte: str):
        r = self.base.lire("SELECT * FROM comptes WHERE compte=?", ((compte or "").strip().lower(),))
        if not r:
            return None
        d = self._ligne(r[0])
        d["admin"] = self.droits.est_admin(d["compte"])
        d["superadmin"] = bool(d["superadmin"])
        d["unix_etat"] = self.unix_etat(d["unix_user"])
        return d

    def unix_etat(self, unix_user: str) -> str:
        """'' (aucun adossement) | 'ok' | 'absent' (l'utilisateur système n'existe pas) | 'sans_shell' (nologin, false : pas de bash)."""
        if not unix_user:
            return ""
        shell = self.unix(unix_user)
        return "absent" if shell is None else ("ok" if shell_de_connexion(shell) else "sans_shell")

    def lister(self) -> list:
        admins = set(self.droits.etat()["admins"])
        return [dict(self._ligne(r), admin=r["compte"] in admins, superadmin=bool(r["superadmin"]), unix_etat=self.unix_etat(r["unix_user"]))
                for r in self.base.lire("SELECT * FROM comptes ORDER BY compte")]

    def creer(self, compte: str, mdp: str, sites=None, superadmin: bool = False, unix_user: str = "", **profil) -> dict:
        compte = (compte or "").strip().lower()
        if not EMAIL.match(compte):
            return {"ok": False, "error": "Adresse e-mail invalide (ex : prenom@exemple.com)"}
        if len(compte) > 120:
            return {"ok": False, "error": "Adresse e-mail trop longue"}
        v = mdp_valider(mdp)
        if not v["ok"]:
            return {"ok": False, "error": v["error"], "manque": v["manque"]}
        if self.existe(compte):
            return {"ok": False, "error": "Ce compte existe déjà"}
        premier = not self.base.lire("SELECT 1 FROM comptes WHERE type='humain' LIMIT 1")
        # Comme FastPanel : le premier compte est le SUPERADMINISTRATEUR, adossé à l'utilisateur système « fastuser » avec bash. Il s'inscrit
        # tout de même par e-mail (c'est elle qui crée son coffre). Ce n'est pas un interdit : install.sh et deploy.sh créent fastuser et son bash ;
        # si le système ne l'a pas (encore), le compte se crée quand même et `unix_etat` le DIT, de quoi lever un constat.
        unix = self.unix_superadmin if premier else ""
        if superadmin and not premier:
            # Un superadministrateur de plus : il apporte l'identifiant de SON utilisateur système (bash), qui rejoint sudo tout seul.
            unix = (unix_user or "").strip().lower()
            if not RE_UNIX.match(unix) or unix == "root":
                return {"ok": False, "error": "Identifiant système du superadministrateur : minuscules, chiffres, - et _ (pas root)"}
            shell = self.unix(unix)
            if shell is None or not shell_de_connexion(shell):
                return {"ok": False, "error": "L'utilisateur système « %s » n'existe pas ou n'a pas d'interpréteur de commandes (bash)" % unix}
            if self.base.lire("SELECT 1 FROM comptes WHERE unix_user=?", (unix,)):
                return {"ok": False, "error": "L'utilisateur système « %s » est déjà adossé à un autre compte" % unix}
        else:
            superadmin = False
        now = time.time()
        champs = {k: str(profil.get(k) or "").strip() for k in CHAMPS_PROFIL}
        champs["lang"] = (champs["lang"].lower()[:5] or "fr")
        self.base.ecrire("INSERT INTO comptes(compte, hash, display_name, role_label, contact_email, phone, lang, fp_account, sites, cree, maj, unix_user, superadmin) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (compte, hacher(mdp), champs["display_name"], champs["role_label"], champs["contact_email"], champs["phone"],
                          champs["lang"], champs["fp_account"] or unix, json.dumps(sorted({norm_domain(s) for s in (sites or []) if s})), now, now,
                          unix, 1 if (premier or superadmin) else 0))
        demande = False
        if superadmin and not premier:
            self.droits.regler_admin(compte, True)
            try:
                demande = bool(self.sudo(unix))
            except Exception:
                demande = False
            return {"ok": True, "compte": compte, "admin": True, "superadmin": True, "unix_user": unix, "unix_demande": demande}
        if premier:                                    # le superadministrateur est administrateur : il détient tous les droits
            self.droits.regler_admin(compte, True)
            try:                                       # et « fastuser » reçoit le mot de passe choisi : par le courtier, car le noyau n'a aucun privilège
                demande = bool(self.adosser(unix, mdp))
            except Exception:
                demande = False                        # le compte existe quand même : l'adossement se rattrape, il ne bloque rien
        return {"ok": True, "compte": compte, "admin": premier, "superadmin": premier, "unix_user": unix, "unix_demande": demande}

    def modifier(self, compte: str, sites=None, **profil) -> dict:
        avant = self.lire(compte)
        if avant is None:
            return {"ok": False, "error": "Compte inconnu"}
        champs = {k: str(profil[k]).strip() for k in CHAMPS_PROFIL if k in profil and profil[k] is not None}
        if "lang" in champs:
            champs["lang"] = champs["lang"].lower()[:5] or "fr"
        nouveaux = {k: avant[k] for k in CHAMPS_PROFIL}
        nouveaux.update(champs)
        s = avant["sites"] if sites is None else sorted({norm_domain(x) for x in sites if x})
        self.base.ecrire("UPDATE comptes SET display_name=?, role_label=?, contact_email=?, phone=?, lang=?, fp_account=?, sites=?, maj=? WHERE compte=?",
                         (nouveaux["display_name"], nouveaux["role_label"], nouveaux["contact_email"], nouveaux["phone"], nouveaux["lang"],
                          nouveaux["fp_account"], json.dumps(s), time.time(), avant["compte"]))
        return {"ok": True, "avant": {k: avant[k] for k in CHAMPS_PROFIL} | {"sites": avant["sites"]}, "apres": nouveaux | {"sites": s}}

    def hash_de(self, compte: str):
        r = self.base.lire("SELECT hash FROM comptes WHERE compte=?", (compte,))
        return r[0]["hash"] if r else None

    def poser_hash(self, compte: str, h: str) -> None:
        self.base.ecrire("UPDATE comptes SET hash=?, maj=? WHERE compte=?", (h, time.time(), compte))

    def changer_mdp(self, compte: str, mdp: str) -> dict:
        compte = (compte or "").strip().lower()
        if not self.existe(compte):
            return {"ok": False, "error": "Compte inconnu"}
        v = mdp_valider(mdp)
        if not v["ok"]:
            return {"ok": False, "error": v["error"], "manque": v["manque"]}
        ancien = self.hash_de(compte)
        self.poser_hash(compte, hacher(mdp))
        return {"ok": True, "ancien_hash": ancien}

    def supprimer(self, compte: str) -> dict:
        """La suppression garde une copie entière (la corbeille) : `restaurer` rend le compte, son mot de passe, ses sessions NON (elles sont fermées)."""
        compte = (compte or "").strip().lower()
        r = self.base.lire("SELECT * FROM comptes WHERE compte=?", (compte,))
        if not r:
            return {"ok": False, "error": "Compte inconnu"}
        if r[0]["type"] == "systeme":
            return {"ok": False, "error": "Compte système : il fait partie du noyau (il se recrée à chaque démarrage), on ne le supprime pas"}
        raison = self.verrou_superadmin(compte)
        if raison:
            return {"ok": False, "error": raison}
        instantane = dict(r[0]) | {"admin": self.droits.est_admin(compte), "groupes": self.droits.groupes_de(compte)}
        with self.base.transaction() as c:
            cur = c.execute("INSERT INTO comptes_corbeille(compte, instantane, ts) VALUES(?,?,?)", (compte, json.dumps(instantane), time.time()))
            c.execute("DELETE FROM comptes WHERE compte=?", (compte,))
            c.execute("DELETE FROM sessions WHERE compte=?", (compte,))
            c.execute("DELETE FROM jetons_mdp WHERE compte=?", (compte,))
        self.droits.regler_admin(compte, False)
        return {"ok": True, "corbeille": cur.lastrowid}

    def corbeille(self) -> list:
        return [{"id": r["id"], "compte": r["compte"], "ts": r["ts"]} for r in self.base.lire("SELECT id, compte, ts FROM comptes_corbeille ORDER BY id DESC")]

    def restaurer(self, corbeille: int) -> dict:
        r = self.base.lire("SELECT instantane FROM comptes_corbeille WHERE id=?", (corbeille,))
        if not r:
            return {"ok": False, "error": "Rien de tel dans la corbeille"}
        s = json.loads(r[0]["instantane"])
        if self.existe(s["compte"]):
            return {"ok": False, "error": "Un compte porte déjà cet identifiant"}
        with self.base.transaction() as c:
            c.execute("INSERT INTO comptes(compte, hash, display_name, role_label, contact_email, phone, lang, fp_account, sites, cree, maj, unix_user, superadmin) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (s["compte"], s["hash"], s["display_name"], s["role_label"], s["contact_email"], s["phone"],
                                                            s["lang"], s["fp_account"], s["sites"], s["cree"], time.time(), s.get("unix_user", ""), s.get("superadmin", 0)))
            if s.get("type", "humain") != "humain":
                c.execute("UPDATE comptes SET type=? WHERE compte=?", (s["type"], s["compte"]))
            c.execute("DELETE FROM comptes_corbeille WHERE id=?", (corbeille,))
        if s.get("admin"):
            self.droits.regler_admin(s["compte"], True)
        for g in s.get("groupes", []):
            if self.droits.groupe(g):
                self.droits.regler_membre(s["compte"], g, True)
        return {"ok": True, "compte": s["compte"]}

    # ---- les tentatives : dix échecs en cinq minutes, par compte et par origine ----
    def _clefs(self, compte, ip):
        return ["compte:" + (compte or "").strip().lower()] + (["ip:" + ip] if ip else [])

    def bloque(self, compte: str, ip: str = "") -> int:
        """Secondes à attendre (0 : on peut essayer)."""
        now = time.time()
        attente = 0
        for k in self._clefs(compte, ip):
            ts = [r["ts"] for r in self.base.lire("SELECT ts FROM tentatives WHERE cle=? AND ts>? ORDER BY ts", (k, now - TENTATIVES_FENETRE))]
            if len(ts) >= TENTATIVES_MAX:
                attente = max(attente, int(TENTATIVES_FENETRE - (now - ts[0])) + 1)
        return attente

    def _echec(self, compte, ip):
        now = time.time()
        with self.base.transaction() as c:
            c.execute("DELETE FROM tentatives WHERE ts<?", (now - 3600,))
            for k in self._clefs(compte, ip):
                c.execute("INSERT INTO tentatives(cle, ts) VALUES(?,?)", (k, now))

    # ---- les sessions ----
    def ouvrir(self, compte: str, mdp: str, ip: str = "", agent: str = "") -> dict:
        compte = (compte or "").strip().lower()
        attente = self.bloque(compte, ip)
        if attente:
            return {"ok": False, "limite": True, "attente_s": attente, "error": "Trop d'essais : réessayez dans %d s" % attente}
        h = self.hash_de(compte)
        bon = hash_ok(mdp, h if h else self._faux) and h is not None
        if not bon:
            self._echec(compte, ip)
            return {"ok": False, "error": "Identifiant ou mot de passe incorrect"}
        jeton = secrets.token_hex(32)
        now = time.time()
        self.base.ecrire("INSERT INTO sessions(id, compte, court, cree, derniere, ip, agent) VALUES(?,?,?,?,?,?,?)",
                         (_empreinte(jeton), compte, jeton[-6:], now, now, (ip or "")[:45], (agent or "")[:60]))
        self.base.ecrire("DELETE FROM sessions WHERE cree<?", (now - self.ttl,))
        return {"ok": True, "jeton": jeton, "id": jeton[-6:], "compte": compte}

    def valider(self, jeton: str) -> dict:
        """L'expiration se vérifie à CHAQUE requête ; last_used n'est réécrit qu'au plus une fois par minute (leçon de la V18 : 502 en rafale)."""
        if not jeton or len(jeton) != 64:
            return {"ok": False}
        now = time.time()
        r = self.base.lire("SELECT compte, derniere FROM sessions WHERE id=? AND cree>?", (_empreinte(jeton), now - self.ttl))
        if not r:
            return {"ok": False}
        if now - r[0]["derniere"] >= 60:
            try:
                self.base.ecrire("UPDATE sessions SET derniere=? WHERE id=?", (now, _empreinte(jeton)))
            except Exception:
                pass                                   # une donnée de télémétrie n'invalide jamais une session par ailleurs valide
        return {"ok": True, "compte": r[0]["compte"], "admin": self.droits.est_admin(r[0]["compte"]), "id": jeton[-6:]}

    def fermer(self, jeton: str) -> int:
        self.base.ecrire("DELETE FROM sessions WHERE id=?", (_empreinte(jeton or ""),))
        return 1

    def sessions(self, compte: str, courant: str = "") -> list:
        return [{"id": r["court"], "created": r["cree"], "last_used": r["derniere"], "ip": r["ip"], "agent": r["agent"],
                 "nature": ip_nature(r["ip"]), "current": bool(courant) and r["id"] == _empreinte(courant)}
                for r in self.base.lire("SELECT * FROM sessions WHERE compte=? ORDER BY derniere DESC", (compte,))]

    def revoquer(self, compte: str, court: str) -> dict:
        """Ferme UNE session de ce compte, désignée par six caractères. Le compte est celui de l'appelant, jamais un paramètre libre."""
        court = (court or "").strip()
        if not compte or len(court) != 6:
            return {"ok": False, "error": "session inconnue"}
        with self.base.transaction() as c:
            n = c.execute("DELETE FROM sessions WHERE compte=? AND court=?", (compte, court)).rowcount
        return {"ok": True, "ferme": n}

    def revoquer_autres(self, compte: str, courant: str) -> int:
        with self.base.transaction() as c:
            return c.execute("DELETE FROM sessions WHERE compte=? AND id!=?", (compte, _empreinte(courant or ""))).rowcount

    # ---- les jetons de mise en place et de réinitialisation du mot de passe ----
    def jeton_creer(self, compte: str, heures: int = 72) -> dict:
        compte = (compte or "").strip().lower()
        if not self.existe(compte):
            return {"ok": False, "error": "Compte inconnu"}
        jeton = secrets.token_urlsafe(32)
        now = time.time()
        self.base.ecrire("DELETE FROM jetons_mdp WHERE expire<?", (now,))
        self.base.ecrire("INSERT INTO jetons_mdp(id, compte, expire, utilise) VALUES(?,?,?,0)", (_empreinte(jeton), compte, now + heures * 3600))
        return {"ok": True, "jeton": jeton, "compte": compte}

    def jeton_compte(self, jeton: str) -> str:
        """Lecture seule : le compte si le jeton est valable et non utilisé (ne le consomme pas)."""
        r = self.base.lire("SELECT compte, expire, utilise FROM jetons_mdp WHERE id=?", (_empreinte((jeton or "").strip()),))
        return "" if (not r or r[0]["utilise"] or r[0]["expire"] < time.time()) else r[0]["compte"]

    def reinitialiser(self, jeton: str, mdp: str) -> dict:
        """Usage unique : le jeton n'est consommé que si le nouveau mot de passe est accepté."""
        compte = self.jeton_compte(jeton)
        if not compte:
            return {"ok": False, "error": "Lien invalide ou expiré"}
        r = self.changer_mdp(compte, mdp)
        if not r["ok"]:
            return r
        self.base.ecrire("UPDATE jetons_mdp SET utilise=1 WHERE id=?", (_empreinte(jeton.strip()),))
        self.base.ecrire("DELETE FROM sessions WHERE compte=?", (compte,))        # un mot de passe changé ferme les sessions ouvertes
        return {"ok": True, "compte": compte, "ancien_hash": r["ancien_hash"]}
