# ══════════════════════════════════════════════
# TITRE      : L'installateur des moteurs de recherche
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #ab1bf8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Installe un moteur externe d'Évolution depuis un catalogue scellé : environnement à part, paquets épinglés par empreinte, banc d'import, retour arrière complet au moindre échec.
# MÉTHODE    : catalogue JSON scellé par HMAC (la clé de l'instance) ; un venv par moteur ; `pip --require-hashes` ; chaque étape est journalisée ; un échec défait tout ce qui précède.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ab1bf8 ▼▼▼
"""Lot 2 de la maquette d'Évolution : installer un moteur autre qu'Orfan sans lui faire confiance.

Rien ne s'installe qui ne soit dans le CATALOGUE, et le catalogue n'est cru que scellé (HMAC de la clé de l'instance) : un catalogue modifié ou sans sceau est refusé.
Chaque paquet est épinglé par version ET par empreinte (`pip --require-hashes`) : un paquet changé en route ne s'installe pas. Un moteur a son environnement à lui (jamais celui de
Cassandra). Le banc d'import prouve que l'adaptateur se charge dans CET environnement. À la moindre étape en échec, l'environnement est supprimé et le registre n'est pas touché.

Un moteur installé n'est pas ACTIF : l'activer est un geste à part (Registre.etat). L'installation n'exécute rien du moteur au-delà de son import.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

_IDENT = re.compile(r"^[a-z][a-z0-9_-]{1,40}$")
_REQ = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(==[A-Za-z0-9._+!-]+| @ https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)$")       # « nom==version » ou « nom @ https://archive » (toujours avec ses empreintes)
_ADAPTATEUR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_EMPREINTE = re.compile(r"^sha256:[0-9a-f]{64}$")


class InstallationRefusee(Exception):
    """Une raison dite : le catalogue, le moteur, un paquet, une étape."""


def sceller_catalogue(catalogue: dict, cle: bytes) -> str:
    """Le sceau d'un catalogue : HMAC-SHA256 de son texte canonique. Écrit à côté du catalogue (`catalogue.sceau`)."""
    texte = json.dumps(catalogue, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(cle, texte, hashlib.sha256).hexdigest()


def lire_catalogue(chemin: str | Path, cle: bytes) -> dict:
    """Le catalogue, ou une InstallationRefusee. Sans sceau, ou sceau faux : rien."""
    chemin = Path(chemin)
    try:
        catalogue = json.loads(chemin.read_text(encoding="utf-8"))
        sceau = chemin.with_suffix(".sceau").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise InstallationRefusee("catalogue des moteurs absent ou sans sceau : %s" % chemin)
    except ValueError as e:
        raise InstallationRefusee("catalogue des moteurs illisible : %s" % e)
    if not hmac.compare_digest(sceau, sceller_catalogue(catalogue, cle)):
        raise InstallationRefusee("le sceau du catalogue ne correspond pas : il a été modifié depuis qu'il a été scellé")
    return catalogue


def verifier_entree(e: dict) -> dict:
    """La forme d'une entrée : {id, nom, version, paquets:[{requis:"nom==1.2", empreintes:["sha256:…"]}], adaptateur:"paquet.module", python_min?}."""
    if not isinstance(e, dict) or not _IDENT.match(str(e.get("id", ""))):
        raise InstallationRefusee("identifiant de moteur invalide dans le catalogue")
    if not _ADAPTATEUR.match(str(e.get("adaptateur", ""))):
        raise InstallationRefusee("adaptateur invalide : %r" % (e.get("adaptateur"),))
    if e.get("interpreteur") is not None and (not isinstance(e["interpreteur"], str) or not os.path.isabs(e["interpreteur"]) or re.search(r"[\s;&|`$<>]", e["interpreteur"])):
        raise InstallationRefusee("interpréteur invalide : un chemin absolu, sans espace ni caractère de commande (%r)" % (e.get("interpreteur"),))
    for p in e.get("paquets", []):
        if not _REQ.match(str(p.get("requis", ""))):
            raise InstallationRefusee("paquet non épinglé (« nom==version » ou « nom @ https://… » exigé) : %r" % (p.get("requis"),))
        emps = p.get("empreintes") or []
        if not emps or not all(_EMPREINTE.match(str(h)) for h in emps):
            raise InstallationRefusee("paquet sans empreinte (sha256 exigée) : %s" % p["requis"])
    return e


_PT_NOTE, _PT_GNU_STACK = 4, 0x6474E551


def pile_non_executable(chemin) -> str:
    """Donne à un binaire ELF 64 bits le marqueur « pile NON exécutable » (PT_GNU_STACK, lecture et écriture seules). Rend « deja », « corrige », « impossible » ou « pas_elf ».

    Pourquoi : un binaire qui n'a PAS ce marqueur est lu par glibc comme demandant une pile exécutable, et glibc rend alors exécutable la pile de chaque fil qu'il crée.
    Sous `MemoryDenyWriteExecute` (le durcissement du service) cela est refusé : le moteur ne peut plus démarrer un seul fil. Le Python téléchargé par uv (python-build-standalone)
    est dans ce cas. Ce n'est pas un assouplissement du service : au contraire, on retire une exécutabilité inutile au binaire. Le marqueur prend la place de l'en-tête PT_NOTE
    (une note de construction que l'exécution n'utilise pas)."""
    try:
        with open(chemin, "r+b") as f:
            tete = f.read(64)
            if len(tete) < 64 or tete[:4] != b"ELF" or tete[4] != 2 or tete[5] != 1:
                return "pas_elf"
            phoff = struct.unpack_from("<Q", tete, 32)[0]
            phentsize, phnum = struct.unpack_from("<HH", tete, 54)
            if phentsize < 56 or not 0 < phnum <= 64:
                return "impossible"
            f.seek(phoff)
            table = f.read(phentsize * phnum)
            if len(table) < phentsize * phnum:
                return "impossible"
            note = None
            for i in range(phnum):
                o = i * phentsize
                t, fl = struct.unpack_from("<II", table, o)
                if t == _PT_GNU_STACK:
                    if fl & 1:
                        f.seek(phoff + o + 4)
                        f.write(struct.pack("<I", fl & ~1))
                        return "corrige"
                    return "deja"
                if t == _PT_NOTE and note is None:
                    note = i
            if note is None:
                return "impossible"
            f.seek(phoff + note * phentsize)
            f.write(struct.pack("<IIQQQQQQ", _PT_GNU_STACK, 6, 0, 0, 0, 0, 0, 16))
            return "corrige"
    except OSError:
        return "impossible"


def durcir_python_pose(racine) -> dict:
    """Passe `pile_non_executable` sur chaque binaire ELF (programmes et bibliothèques) d'un Python posé. Rend {corriges, impossibles}."""
    corriges, impossibles = 0, []
    for dossier, _sous, fichiers in os.walk(str(racine)):
        for nom in fichiers:
            chemin = os.path.join(dossier, nom)
            if os.path.islink(chemin) or not (nom.endswith(".so") or ".so." in nom or os.access(chemin, os.X_OK)):
                continue
            etat = pile_non_executable(chemin)
            if etat == "corrige":
                corriges += 1
            elif etat == "impossible":
                impossibles.append(chemin)
    return {"corriges": corriges, "impossibles": impossibles}


def _executer(commande: list, delai_s: float, cwd=None) -> tuple:
    """Lance une commande, sans interpréteur de commandes, avec un délai. Rend (code, texte de sortie bref)."""
    try:
        r = subprocess.run(commande, capture_output=True, timeout=delai_s, cwd=cwd, text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, "délai de %.0f s dépassé" % delai_s
    except OSError as e:
        return 127, str(e)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-600:]


class Installateur:
    """Installe, dans `dossier`/<id>/, le moteur du catalogue. `executer(commande, delai_s, cwd) -> (code, sortie)` est injectable (les bancs)."""

    def __init__(self, dossier: str | Path, catalogue: str | Path, cle: bytes, registre=None, executer=None, horloge=time.time, delai_s: float = 600.0, adaptateurs: str | Path | None = None, generateur=None):
        self.generateur = generateur                                                         # (entree, python, racine, etape) -> {empreinte, code} ; sans lui, un adaptateur à générer est refusé
        self.dossier, self.catalogue, self._cle = Path(dossier), Path(catalogue), cle
        self.adaptateurs = Path(adaptateurs) if adaptateurs else Path(__file__).resolve().parent.parent / "orfan" / "adaptateurs"       # les adaptateurs livrés avec Cassandra
        self.registre, self._exec, self._horloge, self.delai_s = registre, executer or _executer, horloge, float(delai_s)

    def disponibles(self) -> list:
        """Les moteurs que le catalogue propose, avec leur état d'installation."""
        cat = lire_catalogue(self.catalogue, self._cle)
        return [{"id": e["id"], "nom": e.get("nom", e["id"]), "version": e.get("version", ""), "installe": (self.dossier / e["id"] / "venv").is_dir()} for e in cat.get("moteurs", [])]

    # ── Python posé à la demande (un moteur peut exiger une version que le serveur n'a pas) ──
    @staticmethod
    def _version_de(chemin: str) -> str:
        try:
            r = subprocess.run([chemin, "--version"], capture_output=True, text=True, timeout=20)
            return ((r.stdout or "") + (r.stderr or "")).strip().split()[-1]
        except Exception:
            return ""

    def _uv(self, etape=None) -> str:
        """Le programme `uv` (qui pose les interpréteurs Python) : celui du serveur, sinon un à part, installé dans son propre environnement."""
        trouve = shutil.which("uv")
        if trouve:
            return trouve
        racine = self.dossier.parent / "outils" / "uv"
        uv = racine / "bin" / "uv"
        if uv.exists():
            return str(uv)
        code, sortie = self._exec([sys.executable, "-m", "venv", str(racine)], self.delai_s, None)
        if code == 0:
            code, sortie = self._exec([str(racine / "bin" / "python"), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "uv"], self.delai_s, None)
        if code != 0 or not uv.exists():
            shutil.rmtree(racine, ignore_errors=True)
            raise InstallationRefusee("l'outil qui pose Python (uv) n'a pas pu être installé : %s" % sortie[-200:])
        return str(uv)

    def poser_python(self, version: str, etape=None) -> str:
        """Le chemin d'un Python de cette version EXACTE, posé à côté de celui du serveur (`<données>/pythons`) ; déjà là, il est repris."""
        if not re.match(r"^\d+\.\d+(\.\d+)?$", str(version)):
            raise InstallationRefusee("version de Python invalide : %r" % (version,))
        for nom in ("python" + ".".join(str(version).split(".")[:2]), "python3"):
            c = shutil.which(nom)
            if c and self._version_de(c) == str(version):
                return c
        pythons = self.dossier.parent / "pythons"
        env = ["env", "UV_PYTHON_INSTALL_DIR=" + str(pythons), "UV_CACHE_DIR=" + str(self.dossier.parent / "outils" / "uv-cache"), "UV_PYTHON_PREFERENCE=only-managed"]
        uv = self._uv(etape)
        code, sortie = self._exec(env + [uv, "python", "install", str(version)], self.delai_s, None)
        if code != 0:
            raise InstallationRefusee("Python %s n'a pas pu être posé : %s" % (version, sortie[-200:]))
        code, sortie = self._exec(env + [uv, "python", "find", str(version)], 120.0, None)
        chemin = (sortie.strip().splitlines() or [""])[-1].strip()
        if code != 0 or not os.path.isfile(chemin):
            raise InstallationRefusee("Python %s posé mais introuvable : %s" % (version, sortie[-200:]))
        if os.path.realpath(chemin).startswith(os.path.realpath(str(pythons)) + os.sep):          # seulement un Python que NOUS avons posé, jamais celui du système
            durcir_python_pose(Path(os.path.realpath(chemin)).parent.parent)             # sa pile redevient non exécutable : le durcissement du service le laisse alors démarrer des fils
        code, sortie = self._exec([chemin, "-I", "-c", "import threading; t = threading.Thread(target=lambda: None); t.start(); t.join()"], 60.0, None)
        if code != 0:                                                                  # un Python téléchargé peut ne pas démarrer de fil sous le durcissement du service (MemoryDenyWriteExecute) : pip planterait plus loin, sans explication
            raise InstallationRefusee("Python %s est posé mais ne peut pas démarrer de fil d'exécution sous la protection du service (MemoryDenyWriteExecute) : ce chercheur ne peut pas s'installer sur ce serveur sans assouplir ce durcissement. %s" % (version, sortie[-160:]))
        return chemin

    def installer(self, ident: str, progres=None, racine_nom: str = "", declarer: bool = True) -> dict:
        """Les étapes, dans l'ordre : catalogue scellé → entrée valide → venv (avec Python posé si besoin) → paquets épinglés par empreinte → adaptateur (généré si aucun n'est écrit) → banc d'import → registre (installé, jamais actif).
        Rend {ok, etapes:[{nom, ok, detail}]} ; au premier échec, l'environnement est supprimé. `progres(etapes)` est appelé après chaque étape ; `racine_nom` et `declarer` servent la mise à jour (installer À CÔTÉ)."""
        etapes: list = []

        def etape(nom, ok, detail=""):
            texte = str(detail)
            if len(texte) > (300 if ok else 800):
                texte = texte[:300] if ok else "…" + texte[-799:]                              # l'erreur d'un échec est en BAS de la sortie : on garde la fin
            etapes.append({"nom": nom, "ok": bool(ok), "detail": texte})
            if progres is not None:
                try:
                    progres([dict(e) for e in etapes])
                except Exception:
                    pass                                                                      # un rapport d'avancement qui échoue ne coupe jamais une installation
            return ok

        racine = self.dossier / str(racine_nom or ident)
        try:
            cat = lire_catalogue(self.catalogue, self._cle)
            etape("catalogue scellé", True)
            entree = next((e for e in cat.get("moteurs", []) if e.get("id") == ident), None)
            if entree is None:
                raise InstallationRefusee("moteur absent du catalogue : « %s »" % ident)
            verifier_entree(entree)
            etape("entrée du catalogue", True, "%s %s" % (entree.get("nom", ident), entree.get("version", "")))
        except InstallationRefusee as e:
            etape("refusée", False, e)
            return {"ok": False, "etapes": etapes}
        if racine.exists():
            etape("déjà installé", False, "supprimer d'abord (desinstaller) : une installation n'en écrase pas une autre")
            return {"ok": False, "etapes": etapes}
        try:
            racine.mkdir(parents=True)
            interpreteur = entree.get("interpreteur") or sys.executable                  # un moteur peut exiger un autre Python (CodeEvolve : 3.13.5) que Cassandra pose
            if entree.get("interpreteur") and not os.path.isfile(interpreteur):
                if entree.get("python"):
                    interpreteur = self.poser_python(entree["python"])
                    etape("Python posé", True, "%s : %s" % (entree["python"], interpreteur))
                else:
                    raise InstallationRefusee("l'interpréteur du moteur est absent : %s (le poser d'abord, par exemple `uv python install`)" % interpreteur)
            code, sortie = self._exec([interpreteur, "-m", "venv", str(racine / "venv")], self.delai_s, None)
            if not etape("environnement à part", code == 0, sortie if code else str(racine / "venv")):
                raise InstallationRefusee("environnement non créé")
            python = racine / "venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python")
            paquets = entree.get("paquets", [])
            if paquets:
                exigences = racine / "exigences.txt"
                exigences.write_text("".join("%s %s\n" % (p["requis"], " ".join("--hash=" + h for h in p["empreintes"])) for p in paquets), encoding="utf-8", newline="\n")
                code, sortie = self._exec([str(python), "-m", "pip", "install", "--require-hashes", "--no-input", "--disable-pip-version-check", "-r", str(exigences)], self.delai_s, str(racine))
                if not etape("paquets épinglés par empreinte", code == 0, sortie if code else "%d paquet(s)" % len(paquets)):
                    raise InstallationRefusee("paquets non installés")
            else:
                etape("paquets épinglés par empreinte", True, "aucun paquet à ajouter")
            genere = None
            if entree.get("adaptateur_genere"):                                           # aucun adaptateur écrit à la main : le repli
                if self.generateur is None:
                    etape("adaptateur généré", False, "aucun générateur d'adaptateur n'est branché")
                    raise InstallationRefusee("adaptateur non généré")
                try:
                    genere = self.generateur(entree, python, racine, etape)
                except InstallationRefusee:
                    raise
                except Exception as e:
                    etape("adaptateur généré", False, "%s : %s" % (type(e).__name__, e))
                    raise InstallationRefusee("adaptateur non généré")
            module = str(entree["adaptateur"])
            banc = ("import importlib,sys; sys.path.insert(0, sys.argv[2]); m = importlib.import_module(sys.argv[1]); "
                    "[importlib.import_module(x) for x in getattr(m, 'IMPORTER', [])]")           # l'adaptateur se charge, et le paquet du moteur qu'il annonce aussi
            code, sortie = self._exec([str(python), "-I", "-c", banc, module, str(self.adaptateurs)], 120.0, str(racine))
            if not etape("banc d'import de l'adaptateur", code == 0, sortie if code else module):
                raise InstallationRefusee("l'adaptateur ne se charge pas")
        except Exception as e:
            if etapes[-1]["ok"] or not isinstance(e, InstallationRefusee):
                etape("échec", False, "%s : %s" % (type(e).__name__, e))
            shutil.rmtree(racine, ignore_errors=True)
            etape("retour arrière", not racine.exists(), "environnement supprimé")
            return {"ok": False, "etapes": etapes}
        if self.registre is not None and declarer:
            plus = {}
            if genere:
                plus["adaptateur_genere"] = {"empreinte": genere.get("empreinte", ""), "relu": False, "ts": self._horloge()}
            self.registre.declarer(ident, entree.get("nom", ident), genre="externe", etat="installe", version=entree.get("version", ""), adaptateur=entree["adaptateur"],
                                   python=str(python), installe_le=self._horloge(), **plus)
            etape("registre des moteurs", True, "installé, pas actif : l'activer est un geste à part")
        return {"ok": True, "etapes": etapes, "python": str(python), "racine": str(racine), "empreinte": (genere or {}).get("empreinte", "")}

    def mettre_a_jour(self, ident: str, progres=None) -> dict:
        """Installe la version NOUVELLE du catalogue à côté de l'ancienne ; si tout passe, on bascule, sinon l'ancienne n'a jamais bougé. Rend {ok, etapes}."""
        ancienne = self.dossier / ident
        nouvelle_nom = ident + ".nouveau"
        if not ancienne.exists():
            return {"ok": False, "etapes": [{"nom": "refusée", "ok": False, "detail": "ce moteur n'est pas installé : il n'y a rien à mettre à jour"}]}
        shutil.rmtree(self.dossier / nouvelle_nom, ignore_errors=True)
        r = self.installer(ident, progres=progres, racine_nom=nouvelle_nom, declarer=False)
        if not r["ok"]:
            r["etapes"].append({"nom": "ancienne version", "ok": True, "detail": "elle est restée en place : rien n'a changé"})
            return r
        archive = self.dossier / (ident + ".ancien")
        shutil.rmtree(archive, ignore_errors=True)
        os.replace(ancienne, archive)
        try:
            os.replace(self.dossier / nouvelle_nom, ancienne)
            python = ancienne / "venv" / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python")
            cat = lire_catalogue(self.catalogue, self._cle)
            entree = next(e for e in cat["moteurs"] if e["id"] == ident)
            code, sortie = self._exec([str(python), "-I", "-c", "import importlib,sys; sys.path.insert(0, sys.argv[2]); m = importlib.import_module(sys.argv[1]); [importlib.import_module(x) for x in getattr(m, 'IMPORTER', [])]", str(entree["adaptateur"]), str(self.adaptateurs)], 120.0, str(ancienne))
            if code != 0:
                raise InstallationRefusee("la nouvelle version ne se charge pas à sa place définitive : %s" % sortie[-160:])
        except Exception as e:
            shutil.rmtree(ancienne, ignore_errors=True)
            os.replace(archive, ancienne)
            r["etapes"].append({"nom": "bascule", "ok": False, "detail": str(e)[:200]})
            r["etapes"].append({"nom": "retour arrière", "ok": True, "detail": "l'ancienne version a été remise : rien n'a changé"})
            return {"ok": False, "etapes": r["etapes"]}
        shutil.rmtree(archive, ignore_errors=True)
        if self.registre is not None:
            old = next((m for m in self.registre.liste() if m["id"] == ident), {})
            plus = {"adaptateur_genere": {"empreinte": (r.get("empreinte") or ""), "relu": False, "ts": self._horloge()}} if entree.get("adaptateur_genere") else {}
            self.registre.declarer(ident, entree.get("nom", ident), genre="externe", etat=old.get("etat", "installe"), version=entree.get("version", ""), adaptateur=entree["adaptateur"],
                                   python=str(python), installe_le=self._horloge(), **plus)
            if not plus:
                self.registre.retirer_champ(ident, "adaptateur_genere")
        r["etapes"].append({"nom": "bascule", "ok": True, "detail": "la nouvelle version est en place, l'ancienne est retirée"})
        return r

    def desinstaller(self, ident: str) -> dict:
        """Supprime l'environnement du moteur et le remet « prévu » au registre. Les pièces qu'il a fournies restent : elles vivent par leur preuve, pas par lui."""
        if not _IDENT.match(str(ident)):
            raise InstallationRefusee("identifiant invalide")
        racine = self.dossier / ident
        existait = racine.exists()
        shutil.rmtree(racine, ignore_errors=True)
        for reste in (ident + ".nouveau", ident + ".ancien"):
            shutil.rmtree(self.dossier / reste, ignore_errors=True)
        if self.registre is not None and existait:
            try:
                self.registre.etat(ident, "prevu")
            except ValueError:
                pass
        return {"ok": not racine.exists(), "supprime": existait}
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (l'installation ne s'évolue pas : elle est la garde).
# CN : le catalogue scellé, l'environnement à part, les empreintes exigées et le retour arrière ; aucune exécution du moteur au-delà de son import.
# LIEN : noyau/CN_moteurs.py (le registre), modules/evolution (la coquille), docs/CN_maquette-evolution-moteurs.html (la vue Installation).
