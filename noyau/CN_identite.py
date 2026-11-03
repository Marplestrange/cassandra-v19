# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'identité des comptes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #3d8585
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'identité des comptes : qui est qui, et la preuve qu'on l'est. Portée de la V18 (load_users, set_user, verify_user, sessions, jetons de mot de passe), à une différence près, voulue : le mot de passe n'est plus un SHA-256 nu mais un scrypt 
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3d8585 ▼▼▼
"""L'identité des comptes : qui est qui, et la preuve qu'on l'est. Portée de la V18 (load_users, set_user, verify_user, sessions,
jetons de mot de passe), à une différence près, voulue : le mot de passe n'est plus un SHA-256 nu mais un scrypt salé.

  - l'identifiant d'un compte EST une adresse e-mail (un compte Cassandra = un compte du coffre, même identifiant) ;
  - les règles du mot de passe sont celles de la V18, et la légende vient de la même table : elle ne peut pas promettre autre chose ;
  - le rôle « administrateur » n'est plus un champ du compte : il vit dans les droits (noyau/CN_droits.py), une seule vérité ;
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

from noyau import CN_fiche as _fiche

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
    "itare": ("Itare Citadelle (itare_citadelle) : celui qui parle à Cassandra et touche à la machine", False),   # le sous-chef : droits par défaut, à étendre par choix
    # Les rôles d'agents, un compte chacun pour que chaque acte ait son auteur. Aucun n'est administrateur : l'administrateur leur donne ce qu'il veut.
    "itare_user": ("Itare du compte (itare_user, « Votre Itare » du Desk) : la clé et le modèle du compte, sinon le modèle local", False),
    "vision": ("Itare Vision : lit les images de tous les comptes", False),
    # Le second avis est un MODÈLE qui relit un geste avant qu'il parte (V18 : aut_second_avis, réglé dans Proactivité › règles). Le point de
    # restauration, lui, est un mécanisme (un instantané avant un geste en plusieurs étapes), pas un agent : il agit sous le compte « noyau ».
    "second_avis": ("Second avis (Proactivité, règles) : un modèle relit les gestes qui ne sont pas pleinement réversibles", False),
}
RE_AGENT = re.compile(r"^agent:[a-z][a-z0-9_-]{1,30}$")
CHAMPS_PROFIL = ("display_name", "role_label", "contact_email", "phone", "lang", "fp_account")      # les anciens champs de profil (colonnes de comptes) : la fiche les dérive
PORTRAIT_MAX = 300 * 1024      # l'image propre d'un compte : 300 Ko au plus (l'écran la recadre en carré de 256 px avant de l'envoyer)
PORTRAIT_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg", b"RIFF": "image/webp"}
SOURCES_PORTRAIT = ("", "propre", "dolibarr", "fastpanel", "telegram", "initiales")
TENTATIVES_MAX, TENTATIVES_FENETRE = 10, 300       # comme la V18 : dix échecs en cinq minutes
TTL_SESSION_HEURES = 24
APPAREIL_CONFIANCE_JOURS = 30                  # « se souvenir de cet appareil »
APPAREIL_OUBLI_JOURS = 30                      # un appareil non revu depuis autant de jours, et dont on ne s'est pas souvenu, redevient « nouveau »
# Le coût du mot de passe : scrypt n=2**17, r=8, p=1 (la recommandation d'OWASP), soit 128 Mo de mémoire et ~0,5 s par hachage. hashlib plafonne la mémoire à
# 32 Mo si on ne la lève pas (ValueError) : MAXMEM la lève, avec de la marge. Les paramètres VIVENT DANS L'EMPREINTE (« scrypt$n=..,r=..,p=..$sel$hash ») : une
# empreinte plus ancienne reste vérifiable avec les siens, et se réécrit au paramètre courant à la connexion suivante.
_SCRYPT = dict(n=2 ** 17, r=8, p=1, dklen=32)
_SCRYPT_ANCIEN = dict(n=2 ** 14, r=8, p=1, dklen=32)      # l'ancien format « scrypt$sel$hash », sans paramètres : c'étaient eux
_SCRYPT_SECRET = dict(n=2 ** 14, r=8, p=1, dklen=32)      # un secret tiré au hasard (code de secours) : assez d'entropie, huit vérifications par essai
MAXMEM = 2 ** 29
# Sessions : délai d'INACTIVITÉ (en plus de la durée maximale), plus court pour un administrateur ; âge au-delà duquel une session d'administrateur doit
# ressaisir son second facteur pour un geste sensible. 0 : sans délai. Valeurs de départ ; réglables (voir Identite.parametre).
INACTIVITE_HEURES, INACTIVITE_ADMIN_HEURES = 8, 2
REVERIF_ADMIN_MINUTES = 60
GRACE_SECOND_FACTEUR_JOURS = 7
CONFIRMATION_MINUTES = 10  # un geste sensible demande le mot de passe s'il n'a pas été confirmé depuis ce délai (réglage « confirmation_minutes », 0 : jamais demandé)
SESSIONS_MAX = 10          # par compte : la onzième ouverte ferme la plus ancienne


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


def hacher(pwd: str, params=None) -> str:
    """« scrypt$n=131072,r=8,p=1$sel$hash » : les paramètres sont DANS l'empreinte."""
    p = dict(params or _SCRYPT)
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(pwd.encode("utf-8"), salt=sel, maxmem=MAXMEM, **p)
    return "scrypt$n=%d,r=%d,p=%d$%s$%s" % (p["n"], p["r"], p["p"], sel.hex(), h.hex())


def _lire_empreinte(enregistre: str):
    """(paramètres, sel, hash) d'une empreinte, ancien format compris ; ValueError si elle n'est pas lisible."""
    morceaux = enregistre.split("$")
    if morceaux[0] != "scrypt":
        raise ValueError("algorithme inconnu")
    if len(morceaux) == 3:                                     # l'ancien format : « scrypt$sel$hash », avec les paramètres d'alors
        return dict(_SCRYPT_ANCIEN), morceaux[1], morceaux[2]
    if len(morceaux) != 4:
        raise ValueError("empreinte illisible")
    kv = dict(x.split("=", 1) for x in morceaux[1].split(","))
    p = {"n": int(kv["n"]), "r": int(kv["r"]), "p": int(kv["p"]), "dklen": 32}
    if not (2 ** 10 <= p["n"] <= 2 ** 20 and p["n"] & (p["n"] - 1) == 0 and 1 <= p["r"] <= 16 and 1 <= p["p"] <= 8):      # une base altérée ne choisit pas notre mémoire
        raise ValueError("paramètres hors bornes")
    return p, morceaux[2], morceaux[3]


def hash_ok(pwd: str, enregistre: str) -> bool:
    try:
        p, sel, h = _lire_empreinte(enregistre)
        calcul = hashlib.scrypt((pwd or "").encode("utf-8"), salt=bytes.fromhex(sel), maxmem=MAXMEM, **p)
        return hmac.compare_digest(calcul, bytes.fromhex(h))
    except (ValueError, TypeError, KeyError):
        return False


def hash_a_jour(enregistre: str) -> bool:
    """L'empreinte est-elle au paramètre courant ? Sinon on la réécrit à la prochaine connexion réussie (le mot de passe n'est connu qu'à ce moment-là)."""
    try:
        p, _, _ = _lire_empreinte(enregistre)
    except (ValueError, TypeError, KeyError):
        return True                                            # illisible : on ne réécrit pas ce qu'on ne comprend pas
    return p["n"] >= _SCRYPT["n"] and p["r"] >= _SCRYPT["r"] and p["p"] >= _SCRYPT["p"]


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
RE_FP = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


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
    """Dépose la demande « adosser_superadmin » pour le courtier (voir exploitation/CN_courtier.py). Écrite entière puis renommée : le courtier
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
    def __init__(self, base, droits, ttl_heures=TTL_SESSION_HEURES, unix_superadmin="fastuser", unix=None, courtier=None, reglages=None):
        self.base = base
        self.droits = droits
        self.unix_superadmin = unix_superadmin       # l'utilisateur système du premier compte, comme « fastuser » chez FastPanel
        self.unix = unix or interpreteur_unix        # nom -> son interpréteur de commandes (None : l'utilisateur n'existe pas)
        self.courtier = courtier                     # le dossier où l'on dépose les demandes au courtier (root) ; None : pas de courtier
        self.adosser = lambda utilisateur, mdp: deposer_demande(self.courtier, utilisateur, mdp)
        self.sudo = lambda utilisateur: deposer_sudo(self.courtier, utilisateur)
        self.fastpanel = fastpanel_present            # appelable : FastPanel est-il là ? (verrou du superadministrateur)
        droits.verrou = self.verrou_superadmin
        droits.delegant = self.invite_par
        self._ttl_depart = int(ttl_heures) * 3600
        self.reglages = reglages                      # le service des réglages : la durée des sessions y est réglable (comptes.session_heures)
        self.seconds_facteurs = {}                    # module -> objet (exige, invite, verifier) : un second facteur branché par un module
        self._faux_h = None                           # le leurre : un compte inconnu coûte le même temps qu'un mauvais mot de passe (calculé au premier besoin : 0,5 s)
        self.securite = {}                            # valeurs de départ des réglages de sécurité (clé courte -> valeur) quand le service des réglages ne les porte pas
        self._tables_securite()
        self.migrer_fiches()
        self.amorcer_systeme()

    @property
    def _faux(self) -> str:
        if self._faux_h is None:
            self._faux_h = hacher("sel-de-leurre")
        return self._faux_h

    def _tables_securite(self) -> None:
        """Deux petites tables à elles : la dernière preuve du second facteur d'une session, et quelques dates (l'activation de l'obligation)."""
        with self.base.transaction() as c:
            c.execute("CREATE TABLE IF NOT EXISTS sessions_verif(id TEXT PRIMARY KEY, ts REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS identite_etat(cle TEXT PRIMARY KEY, valeur REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS sessions_mdp(id TEXT PRIMARY KEY, ts REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS appareils(compte TEXT NOT NULL, empreinte TEXT NOT NULL, premiere REAL NOT NULL, derniere REAL NOT NULL, PRIMARY KEY(compte, empreinte))")
            for col, defn in (("confiance", "REAL NOT NULL DEFAULT 0"), ("statut", "TEXT NOT NULL DEFAULT 'approuve'"), ("agent", "TEXT NOT NULL DEFAULT ''"), ("reseau", "TEXT NOT NULL DEFAULT ''")):
                if col not in [r[1] for r in c.execute("PRAGMA table_info(appareils)")]:
                    c.execute("ALTER TABLE appareils ADD COLUMN %s %s" % (col, defn))
            c.execute("CREATE TABLE IF NOT EXISTS comptes_prefs(compte TEXT NOT NULL, cle TEXT NOT NULL, valeur TEXT NOT NULL, maj REAL NOT NULL, PRIMARY KEY(compte, cle))")

    def parametre(self, cle: str, defaut):
        """Un réglage de sécurité : `self.securite[cle]` s'il est posé (une valeur imposée par le code qui construit l'identité : les bancs d'essai), sinon `comptes.<cle>`
        dans les réglages (sa valeur posée, ou son défaut déclaré au manifeste), sinon la valeur de départ."""
        if cle in self.securite:
            return self.securite[cle]
        try:
            v = self.reglages.valeur("comptes." + cle)
            if v is not None:
                return v
        except Exception:
            pass
        return defaut

    def verrou_superadmin(self, compte: str) -> str:
        """Pourquoi on ne retire pas l'administration à ce compte ("" : on peut). Conditionnel : seul le superadmin ET seulement si FastPanel est là."""
        r = self.base.lire("SELECT superadmin FROM comptes WHERE compte=?", (compte,))
        if r and r[0]["superadmin"] and self.fastpanel():
            return "Verrouillé : « %s » est le superadministrateur et FastPanel est installé, qui dépend de son utilisateur système" % compte
        return ""

    @property
    def ttl(self) -> int:
        """La durée d'une session, en secondes : le réglage `comptes.session_heures` s'il existe (module actif), sinon la valeur de départ."""
        try:
            return int(self.reglages.valeur("comptes.session_heures")) * 3600
        except Exception:
            return self._ttl_depart

    def amorcer_systeme(self) -> None:
        """Les comptes système existent toujours. Leurs droits ne sont posés qu'UNE fois : ce que l'administrateur règle ensuite lui appartient."""
        now = time.time()
        for r in self.base.lire("SELECT compte FROM comptes WHERE type='systeme'"):       # un compte système qui n'existe plus au catalogue est retiré
            if r["compte"] not in COMPTES_SYSTEME:
                self.base.ecrire("DELETE FROM comptes WHERE compte=?", (r["compte"],))
                self.droits.regler_admin(r["compte"], False)
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

    # ---- la société d'un compte : obligatoire ----
    def societe_valide(self, societe: str = ""):
        """L'identifiant d'une société où l'on peut ranger un compte (vide : la principale), ou None si elle n'existe pas ou est archivée."""
        s = str(societe or "").strip() or "1"
        r = self.base.lire("SELECT 1 FROM societes WHERE id=? AND archivee=0", (s,))
        return s if r else None

    def societe_de(self, compte: str) -> str:
        """La société de rattachement d'un compte (la principale pour un compte système ou inconnu)."""
        r = self.base.lire("SELECT societe FROM comptes WHERE compte=?", (compte,))
        return r[0]["societe"] if r and r[0]["societe"] else "1"

    # ---- les sociétés : seul le superadministrateur les administre toutes ----
    def societes(self, tout: bool = False) -> list:
        sql = "SELECT id, nom, principale, archivee, cree FROM societes" + ("" if tout else " WHERE archivee=0") + " ORDER BY principale DESC, nom, id"
        return self.base.lire(sql)

    def societe(self, societe: str):
        r = self.base.lire("SELECT id, nom, principale, archivee, cree FROM societes WHERE id=?", (societe,))
        return r[0] if r else None

    def comptes_de_societe(self, societe: str) -> list:
        return [r["compte"] for r in self.base.lire("SELECT compte FROM comptes WHERE societe=? AND desactive=0 ORDER BY compte", (societe,))]

    def est_utilisateur(self, compte: str) -> bool:
        """Ce compte est-il une personne (ni un agent ni un compte système) ?"""
        return bool(self.base.lire("SELECT 1 FROM comptes WHERE compte=? AND type='humain'", (compte,)))

    def nombre_utilisateurs(self, societe: str) -> int:
        """Les personnes actives d'une société (ni agents ni comptes système)."""
        return self.base.lire("SELECT COUNT(*) AS n FROM comptes WHERE societe=? AND desactive=0 AND type='humain'", (societe,))[0]["n"]

    def societe_creer(self, nom: str, identifiant: str = "") -> dict:
        nom = (nom or "").strip()
        if not nom or len(nom) > 120:
            return {"ok": False, "error": "Le nom d'une société : de 1 à 120 caractères"}
        ident = re.sub(r"[^a-z0-9]+", "-", (identifiant or nom).lower().encode("ascii", "ignore").decode()).strip("-")[:40] or "societe"
        if ident == "1" or self.societe(ident):
            base_id, n = ident, 2
            while self.societe(ident) or ident == "1":
                ident = "%s-%d" % (base_id[:36], n)
                n += 1
        self.base.ecrire("INSERT INTO societes(id, nom, principale, archivee, cree) VALUES(?,?,0,0,?)", (ident, nom, time.time()))
        return {"ok": True, "societe": ident, "nom": nom}

    def societe_renommer(self, societe: str, nom: str) -> dict:
        nom = (nom or "").strip()
        if not nom or len(nom) > 120:
            return {"ok": False, "error": "Le nom d'une société : de 1 à 120 caractères"}
        if not self.societe(societe):
            return {"ok": False, "error": "Société inconnue"}
        self.base.ecrire("UPDATE societes SET nom=? WHERE id=?", (nom, societe))
        return {"ok": True, "societe": societe, "nom": nom}

    def societe_archiver(self, societe: str, archiver: bool = True) -> dict:
        s = self.societe(societe)
        if not s:
            return {"ok": False, "error": "Société inconnue"}
        if archiver and s["principale"]:
            return {"ok": False, "error": "La société principale ne s'archive pas"}
        if archiver and self.comptes_de_societe(societe):
            return {"ok": False, "error": "Des comptes appartiennent encore à cette société : transférez-les d'abord"}
        self.base.ecrire("UPDATE societes SET archivee=? WHERE id=?", (1 if archiver else 0, societe))
        return {"ok": True, "societe": societe, "archivee": bool(archiver)}

    def societe_retirer(self, societe: str) -> None:
        """Retrait sec d'une société tout juste créée (retour arrière d'une création) : jamais la principale, jamais avec des comptes."""
        if societe != "1" and not self.comptes_de_societe(societe):
            self.base.ecrire("DELETE FROM societes WHERE id=? AND principale=0", (societe,))

    # ---- les modules de chaque société ----
    def module_ouvert(self, societe: str, module: str, importance: str = "", essentiel: bool = False, instance: bool = False) -> bool:
        """Ce module est-il ouvert dans cette société ? Un module vital ou essentiel l'est partout ; sinon il l'est là où on l'a ouvert, et par défaut dans la société principale."""
        if not societe:
            return True
        if instance:                      # un module d'instance n'est ouvert que dans la société principale, quoi qu'on ait choisi
            return societe == "1"
        if importance == "vital" or essentiel:
            return True
        r = self.base.lire("SELECT actif FROM societe_modules WHERE societe=? AND module=?", (societe, module))
        if r:
            return bool(r[0]["actif"])
        return societe == "1"

    # ── les partages entre sociétés ──────────────────────────────────────────
    TYPES_PARTAGE = ("utilisateurs", "contacts", "modeles")

    def partage_regler(self, source: str, destinataire: str, type: str, mode: str, elements, actif: bool, par: str = "") -> dict:
        """Crée ou remplace le partage `type` de `source` vers `destinataire` ; `elements` ne compte qu'en mode « choisis »."""
        if type not in self.TYPES_PARTAGE:
            raise ValueError("type de partage inconnu : %s" % type)
        if mode not in ("tous", "choisis"):
            raise ValueError("mode de partage : tous ou choisis")
        if source == destinataire:
            raise ValueError("une société ne se partage pas avec elle-même")
        for s in (source, destinataire):
            x = self.societe(s)
            if not x or x["archivee"]:
                raise ValueError("société inconnue ou archivée")
        if type in ("contacts", "modeles"):
            mode, elements = "tous", []                    # le carnet de société et les modèles se partagent en entier
        els = sorted({str(e).strip().lower() for e in (elements or []) if str(e).strip()}) if mode == "choisis" else []
        for e in els:
            if type == "utilisateurs" and self.societe_de(e) != source:
                raise ValueError("%s n'est pas un utilisateur de la société qui partage" % e)
        self.base.ecrire("INSERT INTO societe_partages(source, destinataire, type, mode, actif, cree, par) VALUES(?,?,?,?,?,?,?) "
                         "ON CONFLICT(source, destinataire, type) DO UPDATE SET mode=excluded.mode, actif=excluded.actif, par=excluded.par",
                         (source, destinataire, type, mode, 1 if actif else 0, time.time(), par))
        self.base.ecrire("DELETE FROM societe_partage_elements WHERE source=? AND destinataire=? AND type=?", (source, destinataire, type))
        for e in els:
            self.base.ecrire("INSERT INTO societe_partage_elements(source, destinataire, type, element) VALUES(?,?,?,?)", (source, destinataire, type, e))
        return {"source": source, "destinataire": destinataire, "type": type, "mode": mode, "elements": els, "actif": bool(actif)}

    def partage_retirer(self, source: str, destinataire: str, type: str) -> bool:
        a = bool(self.base.lire("SELECT 1 FROM societe_partages WHERE source=? AND destinataire=? AND type=?", (source, destinataire, type)))
        self.base.ecrire("DELETE FROM societe_partage_elements WHERE source=? AND destinataire=? AND type=?", (source, destinataire, type))
        self.base.ecrire("DELETE FROM societe_partages WHERE source=? AND destinataire=? AND type=?", (source, destinataire, type))
        return a

    def partages(self, societe: str) -> dict:
        """Ce que cette société partage (sortants) et ce qu'on partage avec elle (entrants)."""
        def ligne(r):
            els = [x["element"] for x in self.base.lire("SELECT element FROM societe_partage_elements WHERE source=? AND destinataire=? AND type=? ORDER BY element", (r["source"], r["destinataire"], r["type"]))]
            return {"source": r["source"], "destinataire": r["destinataire"], "type": r["type"], "mode": r["mode"], "actif": bool(r["actif"]), "elements": els}
        return {"sortants": [ligne(r) for r in self.base.lire("SELECT * FROM societe_partages WHERE source=? ORDER BY destinataire, type", (societe,))],
                "entrants": [ligne(r) for r in self.base.lire("SELECT * FROM societe_partages WHERE destinataire=? AND actif=1 ORDER BY source, type", (societe,))]}

    def partage_actif(self, source: str, destinataire: str, type: str) -> bool:
        """`source` partage-t-elle ce type d'objet avec `destinataire` (partage actif) ?"""
        return bool(self.base.lire("SELECT 1 FROM societe_partages WHERE source=? AND destinataire=? AND type=? AND actif=1", (source, destinataire, type)))

    def utilisateur_partage(self, compte: str, destinataire: str) -> bool:
        """Ce compte, d'une autre société, est-il mis à la disposition de `destinataire` par un partage actif ?"""
        src = self.societe_de(compte)
        if not src or src == destinataire or not self.base.lire("SELECT 1 FROM comptes WHERE compte=? AND type='humain'", (compte,)):
            return False
        r = self.base.lire("SELECT mode FROM societe_partages WHERE source=? AND destinataire=? AND type='utilisateurs' AND actif=1", (src, destinataire))
        if not r:
            return False
        if r[0]["mode"] == "tous":
            return True
        return bool(self.base.lire("SELECT 1 FROM societe_partage_elements WHERE source=? AND destinataire=? AND type='utilisateurs' AND element=?", (src, destinataire, compte)))

    def utilisateurs_partages(self, destinataire: str) -> list:
        """Les comptes d'autres sociétés mis à la disposition de `destinataire`."""
        out = []
        for r in self.base.lire("SELECT source, mode FROM societe_partages WHERE destinataire=? AND type='utilisateurs' AND actif=1 ORDER BY source", (destinataire,)):
            if r["mode"] == "tous":
                cs = [x["compte"] for x in self.base.lire("SELECT compte FROM comptes WHERE societe=? AND type='humain' ORDER BY compte", (r["source"],))]
            else:
                cs = [x["element"] for x in self.base.lire("SELECT element FROM societe_partage_elements WHERE source=? AND destinataire=? AND type='utilisateurs' ORDER BY element", (r["source"], destinataire))]
            out.extend({"compte": c, "societe": r["source"]} for c in cs)
        return out

    def modules_de_societe(self, societe: str) -> dict:
        """Les choix faits pour cette société : {module: vrai | faux} (ce qui n'y figure pas suit la règle par défaut)."""
        return {r["module"]: bool(r["actif"]) for r in self.base.lire("SELECT module, actif FROM societe_modules WHERE societe=?", (societe,))}

    def module_regler(self, societe: str, module: str, actif) -> None:
        """actif : vrai, faux, ou None (retire le choix : la règle par défaut s'applique de nouveau)."""
        if actif is None:
            self.base.ecrire("DELETE FROM societe_modules WHERE societe=? AND module=?", (societe, module))
        else:
            self.base.ecrire("INSERT INTO societe_modules(societe, module, actif) VALUES(?,?,?) ON CONFLICT(societe, module) DO UPDATE SET actif=excluded.actif",
                             (societe, module, 1 if actif else 0))

    def est_superadmin(self, compte: str) -> bool:
        r = self.base.lire("SELECT superadmin FROM comptes WHERE compte=?", (compte,))
        return bool(r and r[0]["superadmin"])

    def peut_agir_dans(self, compte: str, societe: str) -> bool:
        """Un compte agit dans sa société, dans celles où il a une fonction ; le superadministrateur, dans toutes."""
        return bool(compte) and societe in self.droits.societes_de(compte)

    def existe(self, compte: str) -> bool:
        return bool(self.base.lire("SELECT 1 FROM comptes WHERE compte=?", (compte,)))

    def invite_par(self, compte: str) -> str:
        r = self.base.lire("SELECT invite_par FROM comptes WHERE compte=? AND type='agent'", (compte,))
        return r[0]["invite_par"] if r else ""

    def inviter_agent(self, nom: str, par: str, libelle: str = "") -> dict:
        """Invite un agent : son COMPTE (« agent:<nom> ») ET son jeton, qui s'ajoutent l'un à l'autre. Le jeton n'est rendu qu'une fois, seule son
        empreinte reste. Une nouvelle invitation du même nom désactive les jetons précédents. Ses droits sont ceux de l'invitant (voir noyau/CN_droits.py)."""
        n = (nom or "").strip().lower()
        cid = "agent:" + n
        if not RE_AGENT.match(cid) or n in ("tous",) or n in COMPTES_SYSTEME:
            return {"ok": False, "error": "Nom d'agent invalide ou réservé (minuscules, chiffres, - et _, 2 à 31 caractères)"}
        if not par or not self.existe(par):
            return {"ok": False, "error": "Un agent est invité par un compte"}
        existant = self.base.lire("SELECT invite_par FROM comptes WHERE compte=?", (cid,))
        if existant and existant[0]["invite_par"] != par and not self.droits.est_admin(par):
            return {"ok": False, "error": "Cet agent a été invité par un autre compte"}
        now = time.time()
        jeton = secrets.token_urlsafe(32)
        with self.base.transaction() as c:
            if not existant:
                c.execute("INSERT INTO comptes(compte, hash, display_name, cree, maj, type, invite_par, societe) VALUES(?,?,?,?,?,'agent',?,?)",
                          (cid, "", (libelle or n).strip(), now, now, par, self.societe_de(par)))      # un agent est de la société de celui qui l'invite
            c.execute("UPDATE agents_jetons SET actif=0 WHERE compte=?", (cid,))
            c.execute("INSERT INTO agents_jetons(id, compte, cree, actif) VALUES(?,?,?,1)", (_empreinte(jeton), cid, now))
        return {"ok": True, "compte": cid, "jeton": jeton, "nouveau": not existant}

    def revoquer_agent(self, nom: str, par: str) -> dict:
        """Désactive le jeton d'un agent invité. Un compte ordinaire ne révoque que les siens ; l'administrateur, tous."""
        cid = "agent:" + (nom or "").strip().lower()
        r = self.base.lire("SELECT invite_par FROM comptes WHERE compte=? AND type='agent'", (cid,))
        if not r:
            return {"ok": False, "error": "Agent inconnu"}
        if r[0]["invite_par"] != par and not self.droits.est_admin(par):
            return {"ok": False, "error": "Cet agent n'est pas le vôtre"}
        n = self.base.lire("SELECT COUNT(*) AS n FROM agents_jetons WHERE compte=? AND actif=1", (cid,))[0]["n"]
        self.base.ecrire("UPDATE agents_jetons SET actif=0 WHERE compte=?", (cid,))
        return {"ok": True, "compte": cid, "revoques": n}

    def valider_agent(self, jeton: str) -> dict:
        """Le compte lié à ce jeton, ou rien : l'invité ne se déclare pas, on le reconnaît."""
        if not jeton or len(jeton) < 20:
            return {"ok": False}
        e = _empreinte(jeton)
        r = self.base.lire("SELECT compte FROM agents_jetons WHERE id=? AND actif=1", (e,))
        if not r:
            return {"ok": False}
        self.base.ecrire("UPDATE agents_jetons SET dernier_vu=? WHERE id=?", (time.time(), e))
        return {"ok": True, "compte": r[0]["compte"], "invite_par": self.invite_par(r[0]["compte"])}

    def agents(self, par: str = "", tous: bool = False) -> list:
        """Les agents invités : ceux d'un compte, ou tous (administrateur)."""
        sql = "SELECT compte, display_name, invite_par, cree FROM comptes WHERE type='agent'" + ("" if tous else " AND invite_par=?")
        out = []
        for r in self.base.lire(sql + " ORDER BY compte", () if tous else (par,)):
            j = self.base.lire("SELECT MAX(dernier_vu) AS vu, MAX(actif) AS actif FROM agents_jetons WHERE compte=?", (r["compte"],))[0]
            out.append(dict(r, actif=bool(j["actif"]), dernier_vu=j["vu"]))
        return out

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

    # ---- la fiche : l'état civil et les coordonnées d'un compte humain (noyau/CN_fiche.py) ----
    def fiche(self, compte: str):
        """La fiche d'un compte humain, avec la source de son portrait ; None pour un agent, un compte système ou un compte inconnu.
        Un compte d'avant la fiche et pas encore migré se lit comme sa migration le donnerait (rien n'est écrit en lisant)."""
        compte = (compte or "").strip().lower()
        c = self.base.lire("SELECT * FROM comptes WHERE compte=?", (compte,))
        if not c or c[0]["type"] != "humain":
            return None
        r = self.base.lire("SELECT * FROM comptes_fiche WHERE compte=?", (compte,))
        if r:
            f = {k: r[0][k] for k in _fiche.ORDRE}
            f["photo_source"] = r[0]["photo_source"]
            return f
        f = dict(_fiche.DEFAUTS)
        f.update(_fiche.depuis_ancien(c[0]["display_name"], c[0]["role_label"], c[0]["contact_email"], c[0]["phone"], c[0]["lang"]))
        f["photo_source"] = ""
        return f

    def nom_affiche(self, compte: str) -> str:
        """LE nom affiché d'un compte : prénom nom pour un humain, sinon son nom d'affichage ancien, sinon l'identifiant. Une seule règle pour tous les écrans."""
        compte = (compte or "").strip().lower()
        f = self.fiche(compte)
        n = _fiche.nom_affiche(f) if f else ""
        if n:
            return n
        r = self.base.lire("SELECT display_name FROM comptes WHERE compte=?", (compte,))
        return (r[0]["display_name"] if r and r[0]["display_name"] else "") or compte

    @staticmethod
    def _vers_fiche(profil: dict) -> dict:
        """Les champs de fiche contenus dans une saisie : les noms de la fiche passent tels quels, les anciens (display_name, role_label, contact_email, phone, lang) se convertissent."""
        out = {k: v for k, v in profil.items() if k in _fiche.CHAMPS and v is not None}
        if profil.get("display_name") is not None:
            out["firstname"], out["lastname"] = _fiche.couper_nom(str(profil["display_name"]))
        for ancien, nouveau in (("role_label", "job"), ("contact_email", "email"), ("phone", "office_phone"), ("lang", "lang")):
            if profil.get(ancien) is not None and nouveau not in out:
                out[nouveau] = profil[ancien]
        return out

    def _sync_ancien(self, compte: str) -> None:
        """Les colonnes d'avant la fiche (display_name, role_label, contact_email, phone, lang) restent écrites, DÉRIVÉES de la fiche : ce qui les lit encore n'est pas cassé."""
        r = self.base.lire("SELECT * FROM comptes_fiche WHERE compte=?", (compte,))
        if r:
            f = r[0]
            self.base.ecrire("UPDATE comptes SET display_name=?, role_label=?, contact_email=?, phone=?, lang=?, maj=? WHERE compte=?",
                             (_fiche.nom_affiche(f), f["job"], f["email"], f["office_phone"], _fiche.langue_courte(f["lang"]), time.time(), compte))

    def _poser_fiche(self, compte: str) -> None:
        """Écrit la ligne de la fiche d'un compte qui n'en a pas encore (pour la lire telle que la migration la donne), sans rien changer à ce qu'elle dit."""
        if self.base.lire("SELECT 1 FROM comptes_fiche WHERE compte=?", (compte,)):
            return
        f = self.fiche(compte)
        cols = list(_fiche.ORDRE)
        self.base.ecrire("INSERT OR IGNORE INTO comptes_fiche(compte, %s, photo_source, maj) VALUES(?, %s, ?, ?)" % (", ".join(cols), ", ".join("?" * len(cols))),
                         (compte,) + tuple(f[k] for k in cols) + (f["photo_source"], time.time()))

    def fiche_ecrire(self, compte: str, champs: dict) -> dict:
        """Écrit des champs de la fiche (les autres ne bougent pas). Une valeur trop longue ou mal formée est REFUSÉE, jamais coupée. Rend ce qui a changé, avant et après."""
        compte = (compte or "").strip().lower()
        if self.fiche(compte) is None:
            return {"ok": False, "error": "Cette fiche n'existe pas : un agent ou un compte système n'en a pas"}
        propres, erreurs = _fiche.valider(champs)
        if erreurs:
            return {"ok": False, "error": " ; ".join(erreurs), "erreurs": erreurs}
        avant = self.fiche(compte)
        changes = {k: v for k, v in propres.items() if avant.get(k) != v}
        self._poser_fiche(compte)
        if changes:
            cols = list(changes)
            self.base.ecrire("UPDATE comptes_fiche SET " + ", ".join("%s=?" % k for k in cols) + ", maj=? WHERE compte=?", tuple(changes[k] for k in cols) + (time.time(), compte))
        self._sync_ancien(compte)
        return {"ok": True, "avant": {k: avant[k] for k in changes}, "apres": changes}

    def portrait_source_poser(self, compte: str, source: str) -> dict:
        """Le choix de la source du portrait (propre, dolibarr, fastpanel, telegram, initiales ; vide : le défaut). Ne touche à aucune image."""
        compte = (compte or "").strip().lower()
        source = (source or "").strip().lower()
        if self.fiche(compte) is None:
            return {"ok": False, "error": "Cette fiche n'existe pas"}
        if source not in SOURCES_PORTRAIT:
            return {"ok": False, "error": "Source de portrait inconnue : %s" % source}
        avant = self.fiche(compte)["photo_source"]
        self._poser_fiche(compte)
        self.base.ecrire("UPDATE comptes_fiche SET photo_source=?, maj=? WHERE compte=?", (source, time.time(), compte))
        return {"ok": True, "avant": avant, "apres": source}

    def portrait_poser(self, compte: str, donnees: bytes) -> dict:
        """Garde l'image propre d'un compte humain. Le type se lit dans les octets (PNG, JPEG, WebP), jamais dans ce que dit l'appelant ; au-delà de PORTRAIT_MAX, refusée."""
        compte = (compte or "").strip().lower()
        if self.fiche(compte) is None:
            return {"ok": False, "error": "Cette fiche n'existe pas"}
        if not donnees or len(donnees) > PORTRAIT_MAX:
            return {"ok": False, "error": "Image vide ou trop lourde (%d Ko au plus)" % (PORTRAIT_MAX // 1024)}
        type_ = next((t for sig, t in PORTRAIT_TYPES.items() if donnees.startswith(sig)), "")
        if type_ == "image/webp" and donnees[8:12] != b"WEBP":
            type_ = ""
        if not type_:
            return {"ok": False, "error": "Image PNG, JPEG ou WebP attendue"}
        avant = self.base.lire("SELECT type, donnees FROM comptes_portrait WHERE compte=?", (compte,))
        self.base.ecrire("INSERT OR REPLACE INTO comptes_portrait(compte, type, donnees, maj) VALUES(?,?,?,?)", (compte, type_, donnees, time.time()))
        return {"ok": True, "type": type_, "octets": len(donnees), "avant": (bytes(avant[0]["donnees"]) if avant else None)}

    def portrait_lire(self, compte: str):
        """(type, octets) de l'image propre du compte, ou None."""
        r = self.base.lire("SELECT type, donnees FROM comptes_portrait WHERE compte=?", ((compte or "").strip().lower(),))
        return (r[0]["type"], bytes(r[0]["donnees"])) if r else None

    def portrait_retirer(self, compte: str) -> dict:
        compte = (compte or "").strip().lower()
        avant = self.portrait_lire(compte)
        self.base.ecrire("DELETE FROM comptes_portrait WHERE compte=?", (compte,))
        return {"ok": True, "avant": avant[1] if avant else None}

    def migrer_fiches(self) -> dict:
        """Crée la fiche des comptes humains qui n'en ont pas, à partir des anciens champs (règles de CN_fiche.depuis_ancien). Idempotent : un compte qui a sa fiche n'est pas retouché.
        Rend (et garde dans etat_noyau « fiches_migration ») le rapport : comptes lus, fiches créées, valeurs trop longues pour la fiche (gardées en entier dans le rapport),
        noms de plus de deux mots (le découpage prénom / nom est à relire)."""
        rapport = {"lus": 0, "creees": 0, "tronques": [], "noms_a_relire": []}
        for c in self.base.lire("SELECT * FROM comptes WHERE type='humain' AND compte NOT IN (SELECT compte FROM comptes_fiche)"):
            rapport["lus"] += 1
            brut = _fiche.depuis_ancien(c["display_name"], c["role_label"], c["contact_email"], c["phone"], c["lang"])
            vals = dict(_fiche.DEFAUTS)
            for k, v in brut.items():
                maxi = _fiche.CHAMPS[k][1]
                if len(v) > maxi:
                    rapport["tronques"].append({"compte": c["compte"], "champ": k, "original": v})
                    v = v[:maxi]
                vals[k] = v
            if len((c["display_name"] or "").split()) > 2:
                rapport["noms_a_relire"].append({"compte": c["compte"], "nom": c["display_name"], "prenom": brut["firstname"], "nom_famille": brut["lastname"]})
            cols = list(vals)
            self.base.ecrire("INSERT OR IGNORE INTO comptes_fiche(compte, %s, maj) VALUES(?, %s, ?)" % (", ".join(cols), ", ".join("?" * len(cols))),
                             (c["compte"],) + tuple(vals[k] for k in cols) + (time.time(),))
            rapport["creees"] += 1
        if rapport["creees"]:
            try:
                self.base.ecrire("INSERT OR REPLACE INTO etat_noyau(cle, valeur) VALUES('fiches_migration', ?)", (json.dumps(rapport, ensure_ascii=False),))
            except Exception:
                pass
        return rapport

    def creer(self, compte: str, mdp: str, sites=None, superadmin: bool = False, unix_user: str = "", societe: str = "", **profil) -> dict:
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
        soc = self.societe_valide(societe)
        if soc is None:
            return {"ok": False, "error": "Société inconnue ou archivée : tout compte appartient à une société"}
        premier = not self.base.lire("SELECT 1 FROM comptes WHERE type='humain' LIMIT 1")
        # Comme FastPanel : le premier compte est le SUPERADMINISTRATEUR, adossé à l'utilisateur système « fastuser » avec bash. Il s'inscrit
        # tout de même par e-mail (c'est elle qui crée son coffre). Ce n'est pas un interdit : CN_install.sh et CN_deploy.sh créent fastuser et son bash ;
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
        fiche_saisie, erreurs = _fiche.valider(self._vers_fiche(profil))
        if erreurs:
            return {"ok": False, "error": " ; ".join(erreurs), "erreurs": erreurs}
        champs = {k: str(profil.get(k) or "").strip() for k in CHAMPS_PROFIL}
        champs["lang"] = (champs["lang"].lower()[:5] or "fr")
        self.base.ecrire("INSERT INTO comptes(compte, hash, display_name, role_label, contact_email, phone, lang, fp_account, sites, cree, maj, unix_user, superadmin, societe) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (compte, hacher(mdp), champs["display_name"], champs["role_label"], champs["contact_email"], champs["phone"],
                          champs["lang"], champs["fp_account"] or unix, json.dumps(sorted({norm_domain(s) for s in (sites or []) if s})), now, now,
                          unix, 1 if (premier or superadmin) else 0, soc))
        self._poser_fiche(compte)                                    # la fiche naît avec le compte, des anciens champs saisis ; le reste se complète ensuite
        if fiche_saisie:
            self.fiche_ecrire(compte, fiche_saisie)
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
        fiche_saisie = {}
        if self.fiche(avant["compte"]) is not None:             # un humain : nom, fonction, courriel, téléphone, langue vivent dans sa fiche ; les colonnes anciennes en sont dérivées
            fiche_saisie = self._vers_fiche({k: v for k, v in profil.items() if v is not None})
            propres, erreurs = _fiche.valider(fiche_saisie)
            if erreurs:
                return {"ok": False, "error": " ; ".join(erreurs), "erreurs": erreurs}
            for k in ("display_name", "role_label", "contact_email", "phone", "lang"):
                champs.pop(k, None)
        nouveaux = {k: avant[k] for k in CHAMPS_PROFIL}
        nouveaux.update(champs)
        s = avant["sites"] if sites is None else sorted({norm_domain(x) for x in sites if x})
        self.base.ecrire("UPDATE comptes SET display_name=?, role_label=?, contact_email=?, phone=?, lang=?, fp_account=?, sites=?, maj=? WHERE compte=?",
                         (nouveaux["display_name"], nouveaux["role_label"], nouveaux["contact_email"], nouveaux["phone"], nouveaux["lang"],
                          nouveaux["fp_account"], json.dumps(s), time.time(), avant["compte"]))
        fiche_avant = {}
        if fiche_saisie:
            r = self.fiche_ecrire(avant["compte"], fiche_saisie)
            fiche_avant = r.get("avant", {})
            nouveaux = {k: self.lire(avant["compte"])[k] for k in CHAMPS_PROFIL}
        return {"ok": True, "avant": {k: avant[k] for k in CHAMPS_PROFIL} | {"sites": avant["sites"]}, "apres": nouveaux | {"sites": s},
                "fiche_avant": fiche_avant, "fiche_apres": {k: v for k, v in (self.fiche(avant["compte"]) or {}).items() if k in fiche_avant}}

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
        if self.droits.dernier_admin_humain(compte):
            return {"ok": False, "error": "« %s » est le dernier administrateur : nommez-en un autre d'abord" % compte}
        instantane = dict(r[0]) | {"admin": self.droits.est_admin(compte), "groupes": self.droits.groupes_de(compte)}
        f = self.base.lire("SELECT * FROM comptes_fiche WHERE compte=?", (compte,))
        if f:
            instantane["fiche"] = dict(f[0])                          # sans elle, une restauration perdrait l'état civil
        with self.base.transaction() as c:
            cur = c.execute("INSERT INTO comptes_corbeille(compte, instantane, ts) VALUES(?,?,?)", (compte, json.dumps(instantane), time.time()))
            c.execute("DELETE FROM comptes_fiche WHERE compte=?", (compte,))
            c.execute("DELETE FROM comptes_portrait WHERE compte=?", (compte,))
            c.execute("DELETE FROM comptes_prefs WHERE compte=?", (compte,))
            c.execute("DELETE FROM appareils WHERE compte=?", (compte,))
            c.execute("DELETE FROM comptes WHERE compte=?", (compte,))
            c.execute("DELETE FROM sessions WHERE compte=?", (compte,))
            c.execute("DELETE FROM jetons_mdp WHERE compte=?", (compte,))
        self.droits.regler_admin(compte, False)
        return {"ok": True, "corbeille": cur.lastrowid}

    def desactive(self, compte: str) -> bool:
        r = self.base.lire("SELECT desactive FROM comptes WHERE compte=?", ((compte or "").strip().lower(),))
        return bool(r and r[0]["desactive"])

    def desactiver(self, compte: str, vers: str = "", agents: str = "revoquer") -> dict:
        """Coupe l'accès SANS rien supprimer : sessions et jetons fermés, mot de passe gardé (la réactivation rend le compte tel quel).
        `vers` : le compte qui reçoit ses sites ; `agents` : « revoquer » (leurs jetons cessent d'ouvrir) ou « reattribuer » (à `vers`).
        Rend de quoi se défaire : les sites d'avant, les agents touchés."""
        compte = (compte or "").strip().lower()
        r = self.base.lire("SELECT * FROM comptes WHERE compte=?", (compte,))
        if not r:
            return {"ok": False, "error": "Compte inconnu"}
        if r[0]["type"] == "systeme":
            return {"ok": False, "error": "Compte système : il fait partie du noyau, on ne le désactive pas"}
        if r[0]["desactive"]:
            return {"ok": False, "error": "Ce compte est déjà désactivé"}
        raison = self.verrou_superadmin(compte)
        if raison:
            return {"ok": False, "error": raison}
        if self.droits.dernier_admin_humain(compte):
            return {"ok": False, "error": "« %s » est le dernier administrateur : nommez-en un autre d'abord" % compte}
        vers = (vers or "").strip().lower()
        if vers and (vers == compte or not self.existe(vers) or self.desactive(vers)):
            return {"ok": False, "error": "Le compte destinataire doit exister, être actif et différer du compte qui part"}
        if agents not in ("revoquer", "reattribuer"):
            return {"ok": False, "error": "agents : revoquer | reattribuer"}
        if agents == "reattribuer" and not vers:
            return {"ok": False, "error": "Réattribuer les agents demande un compte destinataire"}
        mes_agents = [a["compte"] for a in self.base.lire("SELECT compte FROM comptes WHERE type='agent' AND invite_par=?", (compte,))]
        sites_avant = json.loads(r[0]["sites"] or "[]")
        dest_avant = json.loads(self.base.lire("SELECT sites FROM comptes WHERE compte=?", (vers,))[0]["sites"] or "[]") if vers else None
        with self.base.transaction() as c:
            c.execute("UPDATE comptes SET desactive=1, maj=? WHERE compte=?", (time.time(), compte))
            c.execute("DELETE FROM sessions WHERE compte=?", (compte,))
            c.execute("DELETE FROM jetons_mdp WHERE compte=?", (compte,))
            if vers and sites_avant:
                c.execute("UPDATE comptes SET sites=?, maj=? WHERE compte=?", (json.dumps(sorted(set(dest_avant) | set(sites_avant))), time.time(), vers))
                c.execute("UPDATE comptes SET sites='[]', maj=? WHERE compte=?", (time.time(), compte))
            for a in mes_agents:
                if agents == "reattribuer":
                    c.execute("UPDATE comptes SET invite_par=?, maj=? WHERE compte=?", (vers, time.time(), a))
                else:
                    c.execute("UPDATE agents_jetons SET actif=0 WHERE compte=?", (a,))
        return {"ok": True, "vers": vers, "agents": agents, "agents_touches": mes_agents, "sites_avant": sites_avant, "sites_dest_avant": dest_avant}

    def reactiver(self, compte: str) -> dict:
        compte = (compte or "").strip().lower()
        if not self.existe(compte):
            return {"ok": False, "error": "Compte inconnu"}
        self.base.ecrire("UPDATE comptes SET desactive=0, maj=? WHERE compte=?", (time.time(), compte))
        return {"ok": True}

    def restituer_depart(self, compte: str, res: dict) -> None:
        """Défait `desactiver` : le compte revient, ses sites aussi (et ceux du destinataire d'avant), ses agents retrouvent leur invitant. Les jetons révoqués restent révoqués : on réinvite."""
        with self.base.transaction() as c:
            c.execute("UPDATE comptes SET desactive=0, maj=? WHERE compte=?", (time.time(), compte))
            if res.get("vers") and res.get("sites_dest_avant") is not None:
                c.execute("UPDATE comptes SET sites=?, maj=? WHERE compte=?", (json.dumps(res["sites_dest_avant"]), time.time(), res["vers"]))
                c.execute("UPDATE comptes SET sites=?, maj=? WHERE compte=?", (json.dumps(res["sites_avant"]), time.time(), compte))
            if res.get("agents") == "reattribuer":
                for a in res.get("agents_touches", []):
                    c.execute("UPDATE comptes SET invite_par=?, maj=? WHERE compte=?", (compte, time.time(), a))

    def corbeille(self, societe: str = "") -> list:
        """Les comptes supprimés qu'on peut restaurer ; `societe` : ceux de cette société seulement (l'instantané garde la société du compte)."""
        sortie = []
        for r in self.base.lire("SELECT id, compte, ts, instantane FROM comptes_corbeille ORDER BY id DESC"):
            try:
                soc = json.loads(r["instantane"]).get("societe") or "1"
            except Exception:
                soc = "1"
            if not societe or soc == societe:
                sortie.append({"id": r["id"], "compte": r["compte"], "ts": r["ts"], "societe": soc})
        return sortie

    def restaurer(self, corbeille: int) -> dict:
        r = self.base.lire("SELECT instantane FROM comptes_corbeille WHERE id=?", (corbeille,))
        if not r:
            return {"ok": False, "error": "Rien de tel dans la corbeille"}
        s = json.loads(r[0]["instantane"])
        if self.existe(s["compte"]):
            return {"ok": False, "error": "Un compte porte déjà cet identifiant"}
        with self.base.transaction() as c:
            c.execute("INSERT INTO comptes(compte, hash, display_name, role_label, contact_email, phone, lang, fp_account, sites, cree, maj, unix_user, superadmin, societe) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (s["compte"], s["hash"], s["display_name"], s["role_label"], s["contact_email"], s["phone"],
                                                            s["lang"], s["fp_account"], s["sites"], s["cree"], time.time(), s.get("unix_user", ""), s.get("superadmin", 0),
                                                            self.societe_valide(s.get("societe", "")) or "1"))
            if s.get("type", "humain") != "humain":
                c.execute("UPDATE comptes SET type=? WHERE compte=?", (s["type"], s["compte"]))
            c.execute("DELETE FROM comptes_corbeille WHERE id=?", (corbeille,))
            fs = s.get("fiche")
            if fs:
                cols = [k for k in fs if k != "compte"]
                c.execute("INSERT OR REPLACE INTO comptes_fiche(compte, %s) VALUES(?, %s)" % (", ".join(cols), ", ".join("?" * len(cols))), (s["compte"],) + tuple(fs[k] for k in cols))
        if not s.get("fiche"):
            self.migrer_fiches()                                       # une corbeille d'avant la fiche : elle se déduit des anciens champs
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
    def enregistrer_facteur(self, module: str, facteur) -> None:
        """Un module branche un second facteur : `exige(compte)`, `invite(compte)` (ce que le navigateur doit signer), `verifier(compte, preuve, ip)`."""
        self.seconds_facteurs[module] = facteur

    def oublier_facteur(self, module: str) -> None:
        self.seconds_facteurs.pop(module, None)

    def hacher(self, secret: str) -> str:
        """Pour un SECRET tiré au hasard (code de secours), pas pour un mot de passe choisi : coût léger, parce que huit empreintes se vérifient à chaque essai."""
        return hacher(secret, _SCRYPT_SECRET)

    def secret_ok(self, secret: str, enregistre: str) -> bool:
        return hash_ok(secret, enregistre)

    def _session(self, compte: str, ip: str, agent: str) -> dict:
        jeton = secrets.token_hex(32)
        now = time.time()
        self.base.ecrire("INSERT INTO sessions(id, compte, court, cree, derniere, ip, agent) VALUES(?,?,?,?,?,?,?)",
                         (_empreinte(jeton), compte, jeton[-6:], now, now, (ip or "")[:45], (agent or "")[:60]))
        self.base.ecrire("DELETE FROM sessions WHERE cree<?", (now - self.ttl,))
        with self.base.transaction() as c:                    # au plus SESSIONS_MAX par compte : la plus ancienne (la moins récemment servie) cède la place
            c.execute("DELETE FROM sessions WHERE compte=? AND id NOT IN (SELECT id FROM sessions WHERE compte=? ORDER BY derniere DESC, cree DESC LIMIT ?)", (compte, compte, SESSIONS_MAX))
        return {"ok": True, "jeton": jeton, "id": jeton[-6:], "compte": compte}

    @staticmethod
    def _appareil(ip: str, agent: str):
        ip = (ip or "").strip()
        reseau = ".".join(ip.split(".")[:3]) if "." in ip else ":".join(ip.split(":")[:4])
        emp = hashlib.sha256(("%s|%s" % ((agent or "")[:60], reseau)).encode("utf-8")).hexdigest()[:16]
        return emp, reseau

    def appareil_vu(self, compte: str, ip: str, agent: str, bloquer: bool = False) -> str:
        """Note l'appareil (agent + réseau, sans les derniers chiffres de l'adresse) d'une connexion réussie. Rend « premier » pour la toute première
        connexion du compte, « nouveau » si cet appareil n'a jamais servi à ce compte (ou s'il n'est pas revenu depuis APPAREIL_OUBLI_JOURS sans qu'on s'en soit souvenu),
        « attente » s'il attend l'approbation d'une session déjà ouverte (`bloquer`, pour un administrateur), « connu » sinon. Le premier n'alerte personne."""
        compte = (compte or "").strip().lower()
        emp, reseau = self._appareil(ip, agent)
        now = time.time()
        deja = self.base.lire("SELECT COUNT(*) AS n FROM appareils WHERE compte=?", (compte,))[0]["n"]
        vu = self.base.lire("SELECT statut, confiance, derniere FROM appareils WHERE compte=? AND empreinte=?", (compte, emp))
        if vu:
            v = vu[0]
            if v["statut"] == "attente":
                return "attente"
            self.base.ecrire("UPDATE appareils SET derniere=?, agent=?, reseau=? WHERE compte=? AND empreinte=?", (now, (agent or "")[:60], reseau, compte, emp))
            if v["confiance"] <= now and now - v["derniere"] > APPAREIL_OUBLI_JOURS * 86400:
                return "nouveau"                       # un appareil qu'on n'a plus vu depuis longtemps et dont on ne s'est pas souvenu : on le traite comme neuf
            return "connu"
        statut = "attente" if (deja and bloquer) else "approuve"
        self.base.ecrire("INSERT OR IGNORE INTO appareils(compte, empreinte, premiere, derniere, statut, agent, reseau) VALUES(?,?,?,?,?,?,?)", (compte, emp, now, now, statut, (agent or "")[:60], reseau))
        return "attente" if statut == "attente" else ("nouveau" if deja else "premier")

    def appareils(self, compte: str, court: str = "") -> list:
        """Les appareils connus du compte : approuvés, de confiance (jusqu'à quand), en attente. `courant` : celui de la session dont on donne l'identifiant court."""
        compte = (compte or "").strip().lower()
        courant = ""
        if court:
            s = self.base.lire("SELECT ip, agent FROM sessions WHERE court=? AND compte=?", (court, compte))
            if s:
                courant = self._appareil(s[0]["ip"], s[0]["agent"])[0]
        now = time.time()
        return [{"id": r["empreinte"], "agent": r["agent"], "reseau": r["reseau"], "premiere": r["premiere"], "derniere": r["derniere"], "statut": r["statut"],
                 "confiance_jusqua": r["confiance"] if r["confiance"] > now else 0, "courant": r["empreinte"] == courant}
                for r in self.base.lire("SELECT * FROM appareils WHERE compte=? ORDER BY derniere DESC", (compte,))]

    def appareil_confiance(self, compte: str, appareil: str, oui: bool) -> dict:
        """« Se souvenir de cet appareil » : APPAREIL_CONFIANCE_JOURS jours sans le traiter comme nouveau. Le mot de passe et le second facteur restent demandés à chaque connexion."""
        compte = (compte or "").strip().lower()
        r = self.base.lire("SELECT statut, confiance FROM appareils WHERE compte=? AND empreinte=?", (compte, appareil))
        if not r or r[0]["statut"] != "approuve":
            return {"ok": False, "error": "Cet appareil n'est pas connu du compte"}
        jusqua = time.time() + APPAREIL_CONFIANCE_JOURS * 86400 if oui else 0
        self.base.ecrire("UPDATE appareils SET confiance=? WHERE compte=? AND empreinte=?", (jusqua, compte, appareil))
        return {"ok": True, "avant": r[0]["confiance"], "apres": jusqua}

    def appareil_decider(self, compte: str, appareil: str, approuver: bool) -> dict:
        """Approuve ou refuse (retire) un appareil en attente."""
        compte = (compte or "").strip().lower()
        r = self.base.lire("SELECT statut FROM appareils WHERE compte=? AND empreinte=?", (compte, appareil))
        if not r:
            return {"ok": False, "error": "Cet appareil n'existe pas"}
        if approuver:
            self.base.ecrire("UPDATE appareils SET statut='approuve' WHERE compte=? AND empreinte=?", (compte, appareil))
        else:
            self.base.ecrire("DELETE FROM appareils WHERE compte=? AND empreinte=?", (compte, appareil))
        return {"ok": True, "avant": r[0]["statut"]}

    # ---- les préférences d'un compte (qui voit ma fiche, qui l'emporte avec Dolibarr) : un petit dictionnaire JSON par clé ----
    def pref(self, compte: str, cle: str, defaut=None):
        r = self.base.lire("SELECT valeur FROM comptes_prefs WHERE compte=? AND cle=?", ((compte or "").strip().lower(), cle))
        if not r:
            return defaut
        try:
            return json.loads(r[0]["valeur"])
        except ValueError:
            return defaut

    def pref_poser(self, compte: str, cle: str, valeur) -> None:
        self.base.ecrire("INSERT OR REPLACE INTO comptes_prefs(compte, cle, valeur, maj) VALUES(?,?,?,?)", ((compte or "").strip().lower(), cle, json.dumps(valeur), time.time()))

    # ---- les identités liées : le pseudo FastPanel, l'utilisateur système (bash) ----
    def lier_fastpanel(self, compte: str, fp_account: str) -> dict:
        compte = (compte or "").strip().lower()
        fp = (fp_account or "").strip()
        if fp and not RE_FP.match(fp):
            return {"ok": False, "error": "Pseudo FastPanel : lettres, chiffres, point, tiret et soulignement (64 au plus)"}
        r = self.base.lire("SELECT fp_account, type FROM comptes WHERE compte=?", (compte,))
        if not r:
            return {"ok": False, "error": "Ce compte n'existe pas"}
        self.base.ecrire("UPDATE comptes SET fp_account=?, maj=? WHERE compte=?", (fp, time.time(), compte))
        return {"ok": True, "avant": r[0]["fp_account"], "apres": fp}

    def lier_unix(self, compte: str, unix_user: str) -> dict:
        """Adosse un compte ADMINISTRATEUR (non superadministrateur) à un utilisateur système qui a un bash. Le bash est réservé aux administrateurs ; le superadministrateur
        garde le sien, posé à sa création. Vider le lien retire l'adossement (pas l'utilisateur système)."""
        compte = (compte or "").strip().lower()
        unix = (unix_user or "").strip().lower()
        r = self.base.lire("SELECT unix_user, superadmin, type FROM comptes WHERE compte=?", (compte,))
        if not r:
            return {"ok": False, "error": "Ce compte n'existe pas"}
        if r[0]["superadmin"]:
            return {"ok": False, "error": "L'utilisateur système du superadministrateur se pose à sa création et ne se change pas ici"}
        if unix:
            if not self.droits.est_admin(compte):
                return {"ok": False, "error": "Le bash est réservé aux administrateurs : ce compte n'en est pas un"}
            if not RE_UNIX.match(unix) or unix == "root":
                return {"ok": False, "error": "Identifiant système : minuscules, chiffres, - et _ (pas root)"}
            shell = self.unix(unix)
            if shell is None or not shell_de_connexion(shell):
                return {"ok": False, "error": "L'utilisateur système « %s » n'existe pas ou n'a pas d'interpréteur de commandes (bash)" % unix}
            if self.base.lire("SELECT 1 FROM comptes WHERE unix_user=? AND compte<>?", (unix, compte)):
                return {"ok": False, "error": "L'utilisateur système « %s » est déjà adossé à un autre compte" % unix}
        self.base.ecrire("UPDATE comptes SET unix_user=?, maj=? WHERE compte=?", (unix, time.time(), compte))
        return {"ok": True, "avant": r[0]["unix_user"], "apres": unix}

    def ouvrir(self, compte: str, mdp: str, ip: str = "", agent: str = "", preuve=None) -> dict:
        """Mot de passe, puis second facteur si un module en exige un POUR CE COMPTE. Sans preuve, on rend l'invitation (ce qu'il faut signer),
        pas de session. Un second facteur qui plante REFUSE l'entrée (fermé, pas ouvert) : l'administrateur le retire en débranchant le module."""
        compte = (compte or "").strip().lower()
        attente = self.bloque(compte, ip)
        if attente:
            return {"ok": False, "limite": True, "attente_s": attente, "error": "Trop d'essais : réessayez dans %d s" % attente}
        h = self.hash_de(compte)
        bon = hash_ok(mdp, h if h else self._faux) and h is not None
        if not bon:
            self._echec(compte, ip)
            return {"ok": False, "error": "Identifiant ou mot de passe incorrect"}
        if self.desactive(compte):
            return {"ok": False, "desactive": True, "error": "Ce compte est désactivé : demandez à un administrateur de le réactiver"}
        refus = self._obligation_second_facteur(compte)
        if refus:
            return {"ok": False, "error": refus}
        for module, f in list(self.seconds_facteurs.items()):
            try:
                if not f.exige(compte):
                    continue
                if not preuve:
                    return {"ok": False, "second_facteur": True, "methodes": [module], "invite": f.invite(compte), "error": "Second facteur requis"}
                v = f.verifier(compte, preuve, ip)
            except Exception:
                return {"ok": False, "error": "Le second facteur (%s) est indisponible : l'entrée est refusée" % module}
            if not v.get("ok"):
                self._echec(compte, ip)
                return {"ok": False, "error": v.get("error") or "Second facteur refusé"}
        if h and not hash_a_jour(h):                   # une empreinte de l'ancien coût : on la réécrit maintenant, le mot de passe est sous la main
            try:
                self.poser_hash(compte, hacher(mdp))
            except Exception:
                pass                                   # jamais refuser une entrée valide pour une réécriture qui échoue : ce sera pour la prochaine
        return self._session(compte, ip, agent)

    def ouvrir_sans_mdp(self, compte: str, ip: str = "", agent: str = "") -> dict:
        """Ouvre une session pour un compte DÉJÀ PROUVÉ par un module de confiance (une clé d'accès). Le compte doit exister."""
        compte = (compte or "").strip().lower()
        if self.hash_de(compte) is None:
            return {"ok": False, "error": "compte inconnu"}
        if self.desactive(compte):
            return {"ok": False, "desactive": True, "error": "Ce compte est désactivé"}
        return self._session(compte, ip, agent)

    def valider(self, jeton: str) -> dict:
        """L'expiration se vérifie à CHAQUE requête ; last_used n'est réécrit qu'au plus une fois par minute (leçon de la V18 : 502 en rafale)."""
        if not jeton or len(jeton) != 64:
            return {"ok": False}
        now = time.time()
        r = self.base.lire("SELECT s.compte AS compte, s.derniere AS derniere FROM sessions s LEFT JOIN comptes c ON c.compte=s.compte "
                           "WHERE s.id=? AND s.cree>? AND COALESCE(c.desactive,0)=0", (_empreinte(jeton), now - self.ttl))
        if not r:
            return {"ok": False}
        admin = self.droits.est_admin(r[0]["compte"])
        delai = self.inactivite(admin)
        if delai and now - r[0]["derniere"] > delai:      # restée sans servir trop longtemps : fermée, il faut se reconnecter
            self.fermer(jeton)
            return {"ok": False, "inactive": True}
        if now - r[0]["derniere"] >= 60:
            try:
                self.base.ecrire("UPDATE sessions SET derniere=? WHERE id=?", (now, _empreinte(jeton)))
            except Exception:
                pass                                   # une donnée de télémétrie n'invalide jamais une session par ailleurs valide
        return {"ok": True, "compte": r[0]["compte"], "admin": admin, "id": jeton[-6:]}

    # ---- la sécurité des sessions et du second facteur ----
    def inactivite(self, admin: bool) -> int:
        """Secondes sans servir au-delà desquelles une session se ferme (0 : pas de délai). Plus court pour un administrateur."""
        defaut = INACTIVITE_ADMIN_HEURES if admin else INACTIVITE_HEURES
        try:
            h = float(self.parametre("inactivite_admin_heures" if admin else "inactivite_heures", defaut))
        except (TypeError, ValueError):
            h = defaut
        return max(0, int(h * 3600))

    def _a_un_second_facteur(self, compte: str) -> bool:
        for f in list(self.seconds_facteurs.values()):
            try:
                if f.exige(compte):
                    return True
            except Exception:
                return True                                    # dans le doute on le tient pour posé : fermé, pas ouvert
        return False

    def reverif_requise(self, compte: str, jeton: str):
        """Pour un geste SENSIBLE : None si l'on peut y aller, sinon la demande à rendre au navigateur (l'invitation du second facteur). Ne concerne qu'une session
        d'administrateur dont le compte a un second facteur et dont la dernière preuve (la connexion, ou une ressaisie) date de plus de `admin_reverif_minutes`."""
        if not self.droits.est_admin(compte) or not self._a_un_second_facteur(compte):
            return None
        try:
            minutes = float(self.parametre("admin_reverif_minutes", REVERIF_ADMIN_MINUTES))
        except (TypeError, ValueError):
            minutes = REVERIF_ADMIN_MINUTES
        if minutes <= 0:
            return None
        s = self.base.lire("SELECT s.cree AS cree, v.ts AS ts FROM sessions s LEFT JOIN sessions_verif v ON v.id=s.id WHERE s.id=?", (_empreinte(jeton),))
        if not s or time.time() - max(s[0]["cree"], s[0]["ts"] or 0) <= minutes * 60:
            return None
        for module, f in list(self.seconds_facteurs.items()):
            try:
                if f.exige(compte):
                    return {"methodes": [module], "invite": f.invite(compte)}
            except Exception:
                return {"methodes": [module], "invite": {}}
        return None

    def confirmation_requise(self, compte: str, jeton: str) -> bool:
        """Vrai si cette session n'a pas confirmé son mot de passe depuis `confirmation_minutes` (la connexion compte comme une confirmation)."""
        try:
            minutes = float(self.parametre("confirmation_minutes", CONFIRMATION_MINUTES))
        except (TypeError, ValueError):
            minutes = CONFIRMATION_MINUTES
        if minutes <= 0:
            return False
        s = self.base.lire("SELECT s.cree AS cree, v.ts AS ts FROM sessions s LEFT JOIN sessions_mdp v ON v.id=s.id WHERE s.id=? AND s.compte=?", (_empreinte(jeton), compte))
        return bool(s) and time.time() - max(s[0]["cree"], s[0]["ts"] or 0) > minutes * 60

    def confirmer_mdp(self, jeton: str, compte: str, mdp: str, ip: str = "") -> dict:
        """Ressaisie du mot de passe sur une session ouverte : remet à zéro l'âge de la dernière confirmation. Les essais comptent comme à la connexion."""
        attente = self.bloque(compte, ip)
        if attente:
            return {"ok": False, "limite": True, "attente_s": attente, "error": "Trop d'essais : réessayez dans %d s" % attente}
        if not self.base.lire("SELECT 1 FROM sessions WHERE id=? AND compte=?", (_empreinte(jeton), compte)) or not hash_ok(mdp or "", self.hash_de(compte) or ""):
            self._echec(compte, ip)
            return {"ok": False, "error": "Mot de passe incorrect"}
        self.base.ecrire("INSERT OR REPLACE INTO sessions_mdp(id, ts) VALUES(?,?)", (_empreinte(jeton), time.time()))
        return {"ok": True}

    def reverifier(self, jeton: str, compte: str, preuve, ip: str = "") -> dict:
        """Ressaisie du second facteur sur une session ouverte : remet à zéro l'âge de la dernière preuve. Les essais comptent comme à la connexion."""
        attente = self.bloque(compte, ip)
        if attente:
            return {"ok": False, "limite": True, "attente_s": attente, "error": "Trop d'essais : réessayez dans %d s" % attente}
        if not isinstance(preuve, dict) or not preuve:
            return {"ok": False, "error": "Preuve du second facteur attendue"}
        for module, f in list(self.seconds_facteurs.items()):
            try:
                if not f.exige(compte):
                    continue
                v = f.verifier(compte, preuve, ip)
            except Exception:
                return {"ok": False, "error": "Le second facteur (%s) est indisponible" % module}
            if not v.get("ok"):
                self._echec(compte, ip)
                return {"ok": False, "error": v.get("error") or "Second facteur refusé"}
        self.base.ecrire("INSERT OR REPLACE INTO sessions_verif(id, ts) VALUES(?,?)", (_empreinte(jeton), time.time()))
        return {"ok": True}

    def _obligation_depuis(self) -> float:
        """Depuis quand l'obligation est active (0 : elle ne l'est pas). Observée à la première lecture : c'est de là que court la période de grâce."""
        actif = bool(self.parametre("admin_second_facteur_obligatoire", True))
        r = self.base.lire("SELECT valeur FROM identite_etat WHERE cle='mfa_admin_depuis'")
        if not actif:
            if r:
                self.base.ecrire("DELETE FROM identite_etat WHERE cle='mfa_admin_depuis'")
            return 0.0
        if r:
            return float(r[0]["valeur"])
        now = time.time()
        self.base.ecrire("INSERT OR IGNORE INTO identite_etat(cle, valeur) VALUES('mfa_admin_depuis', ?)", (now,))
        return now

    def _grace_second_facteur(self, compte: str):
        """None si rien à dire ; sinon (fin_de_grace, encore_en_grace) pour un administrateur SANS second facteur quand l'instance l'exige."""
        if not self.seconds_facteurs or not self.droits.est_admin(compte):
            return None                                        # aucun module de second facteur branché : on ne peut rien exiger, donc on n'enferme personne
        depuis = self._obligation_depuis()
        if not depuis or self._a_un_second_facteur(compte):
            return None
        try:
            jours = float(self.parametre("admin_second_facteur_grace_jours", GRACE_SECOND_FACTEUR_JOURS))
        except (TypeError, ValueError):
            jours = GRACE_SECOND_FACTEUR_JOURS
        fin = depuis + max(0.0, jours) * 86400
        return fin, time.time() < fin

    def _obligation_second_facteur(self, compte: str) -> str:
        """Le refus (en clair) d'un administrateur sans second facteur, une fois la grâce écoulée ; "" sinon."""
        g = self._grace_second_facteur(compte)
        if g is None or g[1]:
            return ""
        return ("Cette instance exige un second facteur (clé de sécurité) pour les administrateurs, et la période de grâce est terminée. Un autre administrateur "
                "peut en poser un pour vous, ou désactiver l'obligation (réglage « comptes.admin_second_facteur_obligatoire »), y compris depuis le serveur.")

    def avertissement_connexion(self, compte: str) -> dict:
        """À rendre avec une connexion réussie : un administrateur encore dans sa période de grâce est prévenu, avec la date. {} sinon."""
        g = self._grace_second_facteur((compte or "").strip().lower())
        if g is None or not g[1]:
            return {}
        jour = time.strftime("%d/%m/%Y", time.localtime(g[0]))
        return {"code": "second_facteur_requis_bientot", "jusqu_au": time.strftime("%Y-%m-%d", time.localtime(g[0])),
                "message": "Cette instance exige un second facteur pour les administrateurs : posez une clé de sécurité avant le %s, sinon vous ne pourrez plus vous connecter." % jour}

    def fermer(self, jeton: str) -> int:
        self.base.ecrire("DELETE FROM sessions WHERE id=?", (_empreinte(jeton or ""),))
        return 1

    def sessions(self, compte: str, courant: str = "") -> list:
        """Les sessions VIVANTES du compte : ni expirées (durée de vie), ni restées sans servir au-delà du délai d'inactivité.
        Celles qui sont mortes sont purgées à la lecture, pour que la liste ne montre jamais une session qui ne s'ouvrirait plus."""
        now = time.time()
        delai = self.inactivite(self.droits.est_admin(compte))
        vivantes, mortes = [], []
        for r in self.base.lire("SELECT * FROM sessions WHERE compte=? ORDER BY derniere DESC", (compte,)):
            if r["cree"] <= now - self.ttl or (delai and now - r["derniere"] > delai):
                mortes.append(r["id"])
            else:
                vivantes.append({"id": r["court"], "created": r["cree"], "last_used": r["derniere"], "ip": r["ip"], "agent": r["agent"],
                                 "nature": ip_nature(r["ip"]), "current": bool(courant) and r["id"] == _empreinte(courant)})
        if mortes:
            with self.base.transaction() as c:
                c.executemany("DELETE FROM sessions WHERE id=?", [(i,) for i in mortes])
        return vivantes

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

    def revoquer_toutes_autres(self, courant: str) -> int:
        """Ferme les sessions de TOUS les comptes sauf la courante (le geste d'urgence : chacun devra se reconnecter, y compris les agents invités)."""
        with self.base.transaction() as c:
            return c.execute("DELETE FROM sessions WHERE id!=?", (_empreinte(courant or ""),)).rowcount

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
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : norm_domain, mdp_regles, mdp_valider, mdp_legende, hacher, hash_ok, ip_nature, fastpanel_present …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
