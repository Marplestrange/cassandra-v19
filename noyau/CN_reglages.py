# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les réglages
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #160ca2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les réglages : ce que la V18 gardait dans UN fichier config.json réécrit en entier à chaque sauvegarde (d'où la leçon : « relire avant d'écrire », sans quoi un réglage disparaissait). Ici chaque réglage est une LIGNE, écrite seule, avec son
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=160ca2 ▼▼▼
"""Les réglages : ce que la V18 gardait dans UN fichier config.json réécrit en entier à chaque sauvegarde (d'où la leçon : « relire avant d'écrire »,
sans quoi un réglage disparaissait). Ici chaque réglage est une LIGNE, écrite seule, avec son historique.

  - un module DÉCLARE ses réglages dans son manifeste ([[reglages]]) ; ils s'appellent « module.reglage » ;
  - un réglage a un type (texte, entier, booleen, choix, secret), un défaut, et une portée : global, ou propre à chaque compte ;
  - une valeur qui ne passe pas son type est refusée ; une valeur absente rend le défaut ;
  - chaque changement garde l'avant et l'après (de quoi défaire, et savoir qui l'a fait) ; un secret n'est jamais rendu en clair par une lecture
    d'administration : seul le module qui l'a déclaré le lit, par `ctx.reglage()`.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets as _secrets
import threading
import time

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:                      # sans la bibliothèque, un secret ne s'écrit pas : on ne le garde jamais en clair
    AESGCM = None

log = logging.getLogger("noyau.CN_reglages")
PREFIXE = "enc1:"
NOM_CREDENTIAL = "cassandra-secrets-key"            # le nom sous lequel systemd (LoadCredential=) dépose la clé dans $CREDENTIALS_DIRECTORY
ENV_FICHIER_CLE = "CASSANDRA_SECRETS_KEY_FILE"      # ou un chemin de fichier, hors du dossier des données
AGE_MAX_JOURS = 90                                  # au-delà, un secret est signalé « à renouveler » (réglable : reglages.secret_age_max_jours)
GARDE_LECTURES_JOURS = 180                          # le journal des lectures est élagué au démarrage

# Les secrets-pièges : des noms plausibles qu'AUCUN module ne déclare. Personne n'a de raison de les lire ; toute lecture est donc une alarme.
# Ils n'ont aucune ligne en base : leur valeur (fausse) se dérive de la clé du serveur, elle ne ressemble à rien de réel et ne se stocke nulle part.
PIEGES = {
    "fastpanel.jeton_admin_ancien": "fp_",
    "dns.cle_zone_secours": "cfk_",
    "courrier.mot_de_passe_imap_secours": "",
    "billetterie.cle_live_ancienne": "sk_live_",
    "telegram.jeton_bot_ancien": "7",
    "agenda.mot_de_passe_caldav_ancien": "",
}

TYPES = ("texte", "entier", "booleen", "choix", "secret")
PORTEES = ("global", "compte")


def valider(r, valeur):
    """(valeur normalisée, erreur). `r` est un Reglage déclaré."""
    t = r.type
    if t in ("texte", "secret"):
        if not isinstance(valeur, str):
            return None, "un texte est attendu"
        if len(valeur) > 4000:
            return None, "texte trop long (4000 caractères au plus)"
        return valeur, ""
    if t == "entier":
        if isinstance(valeur, bool) or not isinstance(valeur, int):
            return None, "un entier est attendu"
        if r.minimum is not None and valeur < r.minimum:
            return None, "au moins %s" % r.minimum
        if r.maximum is not None and valeur > r.maximum:
            return None, "au plus %s" % r.maximum
        return valeur, ""
    if t == "booleen":
        if not isinstance(valeur, bool):
            return None, "vrai ou faux est attendu"
        return valeur, ""
    if t == "choix":
        if valeur not in r.choix:
            return None, "parmi : %s" % ", ".join(str(c) for c in r.choix)
        return valeur, ""
    return None, "type inconnu"


class SecretIllisible(RuntimeError):
    pass


class Reglages:
    """Les secrets sont CHIFFRÉS au repos (AES-256-GCM) avec une clé gardée à part, dans un fichier lisible de son seul propriétaire. Cela protège les
    sauvegardes et les copies de la base ; cela ne protège pas d'un accès au serveur lui-même (qui lit aussi la clé). Chaque valeur est liée à son
    réglage et à son compte (données associées) : recopier un secret chiffré d'une ligne à l'autre ne donne rien."""

    def __init__(self, base, fichier_cle=None, fichier_externe=None, bus=None):
        self.base = base
        self._fichier_cle = fichier_cle
        self._fichier_externe = fichier_externe      # la clé fournie hors des données (prioritaire sur l'environnement)
        self.bus = bus                               # pour l'alarme d'un secret-piège ; sans bus, l'alarme va au journal seul
        self._cle = None
        self._cle_ancienne = None                    # l'ancienne clé du fichier de repli, gardée en lecture le temps de tout rechiffrer
        self.origine_cle = ""                        # d'où vient la clé : « credential », « fichier externe », « fichier de repli », « processus »
        self.connus = {}                 # « module.reglage » -> (module, Reglage)
        self._verrou = threading.Lock()
        self._verrou_cle = threading.RLock()

    def declarer(self, manifeste) -> None:
        with self._verrou:
            for r in manifeste.reglages:
                self.connus["%s.%s" % (manifeste.id, r.id)] = (manifeste.id, r)

    def oublier(self, module: str) -> None:
        """Un module débranché n'offre plus ses réglages ; les valeurs posées sont gardées (il peut revenir)."""
        with self._verrou:
            for cle in [k for k, (m, _) in self.connus.items() if m == module]:
                del self.connus[cle]

    def _def(self, cle):
        c = self.connus.get(cle)
        if c is None:
            raise KeyError("réglage inconnu (aucun module actif ne le déclare) : %s" % cle)
        return c[1]

    # ---- le chiffrement des secrets ----
    @staticmethod
    def _decoder_cle(brut, origine):
        """32 octets bruts, ou 64 chiffres hexadécimaux, ou 32 octets en base64 (un credential est souvent un texte)."""
        if len(brut) == 32:
            return bytes(brut)
        texte = brut.strip()
        try:
            if len(texte) == 64:
                return bytes.fromhex(texte.decode("ascii"))
            cle = base64.b64decode(texte, validate=True)
            if len(cle) == 32:
                return cle
        except Exception:
            pass
        raise SecretIllisible("la clé des secrets fournie (%s) est invalide : 32 octets, 64 chiffres hexadécimaux ou 32 octets en base64 sont attendus" % origine)

    def _source_externe(self):
        """(chemin, origine) de la clé fournie hors des données, ou None. Priorité : le paramètre, le credential systemd, la variable d'environnement."""
        if self._fichier_externe:
            return str(self._fichier_externe), "fichier externe"
        rep = os.environ.get("CREDENTIALS_DIRECTORY", "")
        if rep and os.path.exists(os.path.join(rep, NOM_CREDENTIAL)):
            return os.path.join(rep, NOM_CREDENTIAL), "credential"
        chemin = os.environ.get(ENV_FICHIER_CLE, "")
        if chemin:
            return chemin, "fichier externe"
        return None

    def _cle_secrets(self):
        if AESGCM is None:
            raise SecretIllisible("la bibliothèque « cryptography » manque : un secret ne s'écrit pas en clair, il n'est donc pas écrit")
        if self._cle is not None:
            return self._cle
        with self._verrou_cle:
            if self._cle is not None:
                return self._cle
            ext = self._source_externe()
            if ext is not None:
                chemin, origine = ext
                try:
                    with open(chemin, "rb") as f:
                        brut = f.read()
                except OSError:
                    raise SecretIllisible("la clé des secrets fournie hors des données est introuvable ou illisible : %s" % chemin)
                cle = self._decoder_cle(brut, origine)
                # Une clé déjà rangée à côté de la base (installation d'avant) : elle sert encore à LIRE les anciens secrets, jusqu'à ce qu'on les rechiffre.
                if self._fichier_cle is not None and os.path.exists(str(self._fichier_cle)):
                    try:
                        with open(str(self._fichier_cle), "rb") as f:
                            ancienne = f.read()
                    except OSError:
                        ancienne = b""
                    if len(ancienne) == 32 and ancienne != cle:
                        self._cle_ancienne = ancienne
                        log.warning("réglages : l'ancienne clé est encore dans le dossier des données (%s) ; les secrets vont être rechiffrés sous la nouvelle, "
                                    "puis ce fichier pourra être supprimé", self._fichier_cle)
                    elif len(ancienne) == 32:
                        log.warning("réglages : la clé fournie hors des données est la même que celle du fichier de repli (%s) : supprimer ce fichier, "
                                    "sans quoi la séparation ne sert à rien", self._fichier_cle)
                if self._fichier_cle is not None and os.path.dirname(os.path.abspath(chemin)) == os.path.dirname(os.path.abspath(str(self._fichier_cle))):
                    log.warning("réglages : la clé fournie est dans le même dossier que les données (%s) : elle n'en est pas séparée", chemin)
                self._cle = cle
                self.origine_cle = origine
            elif self._fichier_cle is None:
                self._cle = _secrets.token_bytes(32)                      # sans fichier (essais) : une clé de la durée du processus
                self.origine_cle = "processus"
                log.warning("réglages : pas de fichier de clé, les secrets ne survivront pas au redémarrage")
            else:
                chemin = str(self._fichier_cle)
                if os.path.exists(chemin):
                    with open(chemin, "rb") as f:
                        cle = f.read()
                    if len(cle) != 32:
                        raise SecretIllisible("le fichier de clé des secrets est invalide : %s" % chemin)
                else:
                    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
                    cle = _secrets.token_bytes(32)
                    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)       # lisible de son seul propriétaire
                    with os.fdopen(fd, "wb") as f:
                        f.write(cle)
                self._cle = cle
                self.origine_cle = "fichier de repli"
                log.warning("réglages : la clé des secrets est dans le dossier des données (%s), à côté de la base : elle ne protège que les sauvegardes et les copies de la base, "
                            "pas un accès au serveur. À fournir hors des données : credential systemd « %s » ou variable %s (docs/CN_SECRETS.md)",
                            chemin, NOM_CREDENTIAL, ENV_FICHIER_CLE)
        return self._cle

    def demarrer(self) -> None:
        """Au démarrage du noyau : élague le journal des lectures ; si la clé est fournie hors des données, la charge tout de suite (une panne se voit au démarrage)
        et rechiffre sous elle les secrets d'avant. Ne crée jamais de clé de repli de lui-même."""
        try:
            self.base.ecrire("DELETE FROM reglages_lectures WHERE ts < ?", (time.time() - GARDE_LECTURES_JOURS * 86400,))
        except Exception as e:
            log.warning("réglages : le journal des lectures n'a pu être élagué (%s)", type(e).__name__)
        if self._source_externe() is None:
            return
        try:
            self._cle_secrets()
            if self._cle_ancienne is not None:
                r = self.rechiffrer_tout()
                log.warning("réglages : %d secret(s) rechiffré(s) sous la clé fournie hors des données, %d illisible(s)", r["rechiffres"], len(r["illisibles"]))
        except SecretIllisible as e:
            log.error("réglages : %s", e)

    def rechiffrer_tout(self) -> dict:
        """Remet tous les secrets sous la clé courante (la date de pose ne bouge pas). Rend {rechiffres, illisibles: [(cle, compte)]}."""
        self._cle_secrets()
        fait, mal = 0, []
        for r in self.base.lire("SELECT cle, compte, valeur FROM reglages"):
            v = json.loads(r["valeur"])
            if not (isinstance(v, str) and v.startswith(PREFIXE)):
                continue
            try:
                clair = self.dechiffrer(v, r["cle"], r["compte"])
                neuf = self.chiffrer(clair, r["cle"], r["compte"])
            except SecretIllisible:
                mal.append((r["cle"], r["compte"]))
                continue
            self.base.ecrire("UPDATE reglages SET valeur=? WHERE cle=? AND compte=?", (json.dumps(neuf), r["cle"], r["compte"]))
            fait += 1
        if not mal:
            self._cle_ancienne = None
        return {"rechiffres": fait, "illisibles": mal}

    def chiffrer(self, valeur, cle, compte):
        nonce = _secrets.token_bytes(12)
        ct = AESGCM(self._cle_secrets()).encrypt(nonce, str(valeur).encode("utf-8"), ("%s|%s" % (cle, compte)).encode("utf-8")) if AESGCM else None
        if ct is None:
            raise SecretIllisible("chiffrement indisponible")
        return PREFIXE + base64.b64encode(nonce + ct).decode("ascii")

    def dechiffrer(self, chiffre, cle, compte):
        aad = ("%s|%s" % (cle, compte)).encode("utf-8")
        try:
            brut = base64.b64decode(chiffre[len(PREFIXE):])
            principale = self._cle_secrets()
        except SecretIllisible:
            raise
        except Exception:
            raise SecretIllisible("le secret de « %s » est illisible (clé changée ou valeur altérée)" % cle)
        for k in (principale, self._cle_ancienne):
            if k is None:
                continue
            try:
                return AESGCM(k).decrypt(brut[:12], brut[12:], aad).decode("utf-8")
            except Exception:
                continue
        raise SecretIllisible("le secret de « %s » est illisible (clé changée ou valeur altérée)" % cle)

    def _brut(self, cle, compte):
        """(posé ?, valeur). Un secret est rendu EN CLAIR, déchiffré ; un secret resté en clair d'avant le chiffrement est chiffré au passage."""
        r = self.base.lire("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte))
        if not r:
            return False, None
        v = json.loads(r[0]["valeur"])
        c = self.connus.get(cle)
        if c is not None and c[1].type == "secret" and isinstance(v, str):
            if v.startswith(PREFIXE):
                return True, self.dechiffrer(v, cle, compte)
            if v:
                try:
                    self.base.ecrire("UPDATE reglages SET valeur=? WHERE cle=? AND compte=?", (json.dumps(self.chiffrer(v, cle, compte)), cle, compte))
                except SecretIllisible:
                    pass
        return True, v

    def brut_chiffre(self, cle, compte):
        """La valeur CHIFFRÉE telle qu'elle est rangée (pour un retour arrière : on la remet sans jamais la déchiffrer), ou None."""
        r = self.base.lire("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte))
        v = json.loads(r[0]["valeur"]) if r else None
        if isinstance(v, str) and v and not v.startswith(PREFIXE):
            v = self.chiffrer(v, cle, compte)
        return v

    def _pose_de(self, cle, compte):
        r = self.base.lire("SELECT pose FROM reglages_poses WHERE cle=? AND compte=?", (cle, compte))
        return r[0]["pose"] if r else None

    def poser_chiffre(self, cle, compte, chiffre, par="", pose=None):
        """Remet une valeur chiffrée d'avant (retour arrière). `pose` : la date de pose d'avant, pour qu'un retour arrière ne rajeunisse pas un vieux secret."""
        self._def(cle)
        now = time.time()
        with self.base.transaction() as c:
            c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES(?,?,?,?,?) ON CONFLICT(cle, compte) DO UPDATE SET valeur=excluded.valeur, maj=excluded.maj, par=excluded.par",
                      (cle, compte, json.dumps(chiffre), now, par))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,?,?,?)", (cle, compte, None, json.dumps("***"), now, par))
            if pose is not None:
                c.execute("INSERT INTO reglages_poses(cle, compte, pose) VALUES(?,?,?) ON CONFLICT(cle, compte) DO UPDATE SET pose=excluded.pose", (cle, compte, pose))

    def _effective(self, d, cle, compte, societe):
        """(posé ?, valeur, compte de la ligne lue). Rien n'est noté : c'est `valeur` qui note une lecture."""
        if d.portee == "compte" and compte:
            ok, v = self._brut(cle, compte)
            if ok:
                return True, v, compte
        if d.portee == "societe" and societe:
            ok, v = self._brut(cle, "@s:" + societe)
            if ok:
                return True, v, "@s:" + societe
        ok, v = self._brut(cle, "")
        return (True, v, "") if ok else (False, d.defaut, "")

    def valeur(self, cle: str, compte: str = "", societe: str = ""):
        """La valeur EFFECTIVE : celle du compte si le réglage est de portée compte et qu'il l'a posée, celle de la société s'il est de portée société et qu'elle l'a posée,
        sinon la globale, sinon le défaut. La lecture d'un SECRET est notée (module, compte, nom, moment : jamais la valeur) ; celle d'un secret-piège lève l'alarme."""
        if cle in PIEGES:
            return self._lire_piege(cle, compte)
        d = self._def(cle)
        ok, v, ligne = self._effective(d, cle, compte, societe)
        if ok and d.type == "secret":
            self._noter_lecture(cle, ligne)
        return v

    # ---- le journal des lectures, les pièges ----
    def _noter_lecture(self, cle, compte, piege=False) -> None:
        try:
            self.base.ecrire("INSERT INTO reglages_lectures(ts, module, cle, compte, piege) VALUES(?,?,?,?,?)",
                             (time.time(), cle.split(".", 1)[0], cle, compte or "", 1 if piege else 0))
        except Exception as e:                           # la lecture ne tombe jamais pour un journal qui ne s'écrit pas
            log.warning("réglages : une lecture de secret n'a pu être notée (%s)", type(e).__name__)

    def _valeur_piege(self, cle) -> str:
        """Une fausse valeur, stable, qui ressemble à son nom ; elle se dérive de la clé du serveur et n'est stockée nulle part."""
        try:
            graine = hmac.new(self._cle_secrets(), ("piege|" + cle).encode("utf-8"), hashlib.sha256).digest()
        except SecretIllisible:
            graine = hashlib.sha256(("piege|" + cle).encode("utf-8")).digest()
        corps = base64.b32encode(graine).decode("ascii").rstrip("=").lower()[:32]
        return PIEGES[cle] + corps

    def _lire_piege(self, cle, compte):
        self._noter_lecture(cle, compte, piege=True)
        module = cle.split(".", 1)[0]
        log.critical("réglages : ALARME, le secret-piège « %s » a été lu (module « %s », compte « %s »). Personne n'a de raison de le lire.", cle, module, compte or "-")
        if self.bus is not None:
            try:
                self.bus.emettre("noyau.piege_touche", source="noyau", acteur="noyau", objet=("reglage", cle), compte=compte or "",
                                 donnees={"cle": cle, "module": module, "compte": compte or ""})
                # Le constat critique devient une notification aux administrateurs (jamais au compte lecteur). Le noyau ne gèle rien seul : le gel est une règle de l'administrateur.
                self.bus.emettre("constat.ouvert", source="noyau", acteur="sonde", objet=("piege", cle),
                                 donnees={"detecteur": "piege_secret", "niveau": "critique", "titre": "Un secret-piège a été lu : %s" % cle,
                                          "detail": "Module « %s », compte « %s ». Aucun module légitime ne lit ce nom : un code a fouillé les secrets." % (module, compte or "-")})
            except Exception as e:
                log.error("réglages : l'alarme du piège n'a pu être émise (%s)", type(e).__name__)
        return self._valeur_piege(cle)

    def pieges(self) -> list:
        """Les noms des secrets-pièges (pour l'administrateur, qui sait ainsi lesquels sont faux)."""
        return sorted(PIEGES)

    def lectures(self, limite: int = 100, cle: str = "", module: str = "", depuis: float = 0.0) -> dict:
        """Qui a lu quel secret et quand (jamais la valeur) : les dernières lectures, et le compte par secret."""
        cond, args = "ts >= ?", [float(depuis or 0)]
        if cle:
            cond += " AND cle=?"
            args.append(cle)
        if module:
            cond += " AND module=?"
            args.append(module)
        rows = self.base.lire("SELECT ts, module, cle, compte, piege FROM reglages_lectures WHERE " + cond + " ORDER BY id DESC LIMIT ?",
                              tuple(args) + (max(1, min(int(limite), 1000)),))
        par = self.base.lire("SELECT cle, module, COUNT(*) n, MAX(ts) derniere, MAX(piege) piege FROM reglages_lectures WHERE " + cond + " GROUP BY cle ORDER BY derniere DESC", tuple(args))
        return {"lectures": [{"ts": r["ts"], "module": r["module"], "cle": r["cle"], "compte": r["compte"], "piege": bool(r["piege"])} for r in rows],
                "par_secret": [{"cle": r["cle"], "module": r["module"], "lectures": r["n"], "derniere": r["derniere"], "piege": bool(r["piege"])} for r in par]}

    def ages(self, seuil_jours=None) -> dict:
        """L'âge de chaque secret posé et ceux qui dépassent le seuil (par défaut `reglages.secret_age_max_jours`, 90 jours). Aucune valeur."""
        if seuil_jours is None:
            try:
                seuil_jours = int(self.valeur("reglages.secret_age_max_jours") or AGE_MAX_JOURS)
            except (KeyError, ValueError, TypeError):
                seuil_jours = AGE_MAX_JOURS
        seuil_jours = max(1, int(seuil_jours))
        poses = {(r["cle"], r["compte"]): r["pose"] for r in self.base.lire("SELECT cle, compte, pose FROM reglages_poses")}
        now = time.time()
        out = []
        with self._verrou:
            secrets_ = {k: m for k, (m, d) in self.connus.items() if d.type == "secret"}
        for r in self.base.lire("SELECT cle, compte, valeur, maj FROM reglages ORDER BY cle, compte"):
            if r["cle"] not in secrets_ or json.loads(r["valeur"]) in ("", None):
                continue
            pose = poses.get((r["cle"], r["compte"]))
            estimee = pose is None                       # posé avant la date de pose : on retient la dernière modification
            pose = r["maj"] if estimee else pose
            age = int((now - pose) // 86400)
            out.append({"cle": r["cle"], "module": secrets_[r["cle"]], "compte": r["compte"], "pose": pose, "age_jours": age, "estimee": estimee, "a_renouveler": age >= seuil_jours})
        return {"seuil_jours": seuil_jours, "secrets": out, "a_renouveler": [x for x in out if x["a_renouveler"]]}

    def poser(self, cle: str, valeur, compte: str = "", par: str = "") -> dict:
        """Écrit UN réglage (jamais un fichier entier). `compte` : la valeur propre à ce compte (portée compte) ; vide : la valeur globale."""
        d = self._def(cle)
        if compte.startswith("@s:"):
            if d.portee != "societe":
                raise ValueError("« %s » n'a pas de valeur par société" % cle)
        elif compte and d.portee != "compte":
            raise ValueError("« %s » est un réglage global : il n'a pas de valeur par compte" % cle)
        v, err = valider(d, valeur)
        if err:
            raise ValueError("%s : %s" % (cle, err))
        secret = d.type == "secret"
        ok, avant = self._brut(cle, compte)
        avant_chiffre = self.brut_chiffre(cle, compte) if (secret and ok) else None
        avant_pose = self._pose_de(cle, compte) if (secret and ok) else None
        stocke = self.chiffrer(v, cle, compte) if (secret and v != "") else v
        now = time.time()
        with self.base.transaction() as c:
            c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(cle, compte) DO UPDATE SET valeur=excluded.valeur, maj=excluded.maj, par=excluded.par",
                      (cle, compte, json.dumps(stocke), now, par))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,?,?,?)",
                      (cle, compte, (json.dumps("***") if (secret and ok) else (json.dumps(avant) if ok else None)), json.dumps("***" if secret else v), now, par))
            if secret:
                if v != "":
                    c.execute("INSERT INTO reglages_poses(cle, compte, pose) VALUES(?,?,?) ON CONFLICT(cle, compte) DO UPDATE SET pose=excluded.pose", (cle, compte, now))
                else:
                    c.execute("DELETE FROM reglages_poses WHERE cle=? AND compte=?", (cle, compte))
        if secret:
            return {"cle": cle, "compte": compte, "avant": "***" if ok else None, "avait": ok, "apres": "***", "avant_chiffre": avant_chiffre, "avant_pose": avant_pose}
        return {"cle": cle, "compte": compte, "avant": avant, "avait": ok, "apres": v}

    def retirer(self, cle: str, compte: str = "", par: str = "") -> dict:
        """Rend la valeur au défaut (ou au global) : la ligne disparaît."""
        self._def(cle)
        ok, avant = self._brut(cle, compte)
        if not ok:
            return {"cle": cle, "compte": compte, "avait": False}
        secret = self._def(cle).type == "secret"
        avant_chiffre = self.brut_chiffre(cle, compte) if secret else None
        avant_pose = self._pose_de(cle, compte) if secret else None
        now = time.time()
        with self.base.transaction() as c:
            c.execute("DELETE FROM reglages WHERE cle=? AND compte=?", (cle, compte))
            c.execute("DELETE FROM reglages_poses WHERE cle=? AND compte=?", (cle, compte))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,NULL,?,?)",
                      (cle, compte, json.dumps("***" if secret else avant), now, par))
        return {"cle": cle, "compte": compte, "avant": "***" if secret else avant, "avait": True, "avant_chiffre": avant_chiffre, "avant_pose": avant_pose}

    def historique(self, cle: str, compte: str = "", limite: int = 20) -> list:
        d = self._def(cle)
        sql = "SELECT ts, par, avant, apres, compte FROM reglages_historique WHERE cle=?" + ("" if compte == "*" else " AND compte=?")
        rows = self.base.lire(sql + " ORDER BY id DESC LIMIT ?", (cle,) + (() if compte == "*" else (compte,)) + (int(limite),))
        masque = d.type == "secret"
        return [{"ts": r["ts"], "par": r["par"], "compte": r["compte"],
                 "avant": ("***" if masque and r["avant"] is not None else (json.loads(r["avant"]) if r["avant"] is not None else None)),
                 "apres": ("***" if masque and r["apres"] is not None else (json.loads(r["apres"]) if r["apres"] is not None else None))} for r in rows]

    def liste(self, module: str = "", compte: str = "", global_visible: bool = True, societe: str = "") -> list:
        """Les réglages déclarés, leurs valeurs effectives, les secrets MASQUÉS (« *** » s'ils ont une valeur, vide sinon)."""
        out = []
        with self._verrou:
            items = sorted(self.connus.items())
        for cle, (mod, d) in items:
            if module and mod != module:
                continue
            if d.portee == "global" and not global_visible:
                continue
            v = self._effective(d, cle, compte, societe)[1]          # une liste d'administration ne compte pas comme une lecture : elle ne rend jamais la valeur d'un secret
            pose = self._brut(cle, ("@s:" + societe) if (d.portee == "societe" and societe) else (compte if d.portee == "compte" and compte else ""))[0]
            if d.type == "secret":
                v = "***" if (v not in (None, "")) else ""
            out.append({"cle": cle, "module": mod, "libelle": d.libelle, "type": d.type, "portee": d.portee, "valeur": v,
                        "defaut": ("***" if d.type == "secret" and d.defaut else d.defaut), "pose": pose, "choix": list(d.choix), "aide": d.aide})
        return out
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : valider, SecretIllisible, Reglages
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
