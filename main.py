#!/usr/bin/env python3
"""Cassandra V19 : le moteur central.

Ce fichier ASSEMBLE, il ne fait pas de métier. Le métier vit dans modules/<id>/ ; les pièces communes
vivent dans noyau/ (bus, registre, catalogue, exécuteur, chargeur). Ici on les relie et on fait battre
le cycle : percevoir (les détecteurs), décider (le palier de la capacité), agir, prouver, apprendre.

    python main.py verifier          lit les manifestes, vérifie l'isolation, donne l'ordre d'installation
    python main.py ordre [id ...]    ordre d'installation des modules demandés et de leurs dépendances (un id par ligne)
    python main.py versions          « id version » de chaque module (pour deploy.sh)
    python main.py etat              résume le noyau sans rien écrire (modules, objets, constats, paliers)
    python main.py agir CAPACITE ...  lance une capacité à la main (voie humaine) et imprime le résultat
    python main.py palier [CLE PALIER]  le plafond d'autonomie de chaque capacité qui écrit : un choix d'administrateur
    python main.py paquet <cmd>      construire / vérifier / extraire un paquet de module (.cmod, signé)
    python main.py module <cmd>      l'état des modules : liste | activer ID | desactiver ID | installe ID | oublier ID | actif ID
    python main.py moteurs           les moteurs déclarés par les modules actifs, avec leur état
    python main.py tick              une passe de détection et des moteurs échus
    python main.py demarrer          le cycle en continu (sous systemd : type notify, chien de garde)

Modules actifs : `$CASSANDRA_CONFIG/modules.actifs` (un id par ligne). Sans ce fichier, tous les modules du
dossier modules/ sont chargés (développement).

Principe de souveraineté : rien ici n'attend un humain. Un humain agit par `agir_humain`, en parallèle,
et Cassandra le sait (événement `capacite.*` avec acteur « humain »).
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

from noyau import chargeur, manifeste, paquets, systemd
from noyau.base import Base
from noyau.bus import TOUT, Bus
from noyau.catalogue import Catalogue
from noyau.contexte import Contexte
from noyau.droits import Droits
from noyau.executeur import Executeur
from noyau.identite import Identite
from noyau.modules import Modules
from noyau.registre import Registre

RACINE = Path(__file__).resolve().parent
log = logging.getLogger("noyau")
SEUIL_PANNES = 5   # pannes de suite d'un détecteur avant qu'il soit suspendu (disjoncteur)


class Noyau:
    def __init__(self, donnees, modules=None, config=None, actifs=None, extensions=None, lire_actifs=None,
                 gerer_modules=False, amorce=None):
        self.modules = Path(modules or RACINE / "modules")
        self.extensions = Path(extensions) if extensions else None   # dossier des modules greffés après coup
        self.actifs = actifs         # None : tous les modules du dossier ; sinon la liste des modules actifs
        self.lire_actifs = lire_actifs   # appelable : relit la liste des modules actifs (greffe à chaud)
        self.gerer = bool(gerer_modules)  # vrai en exploitation : l'état des modules (installé, actif) vit dans la base
        self._amorce = amorce            # appelable : l'ancienne liste de modules actifs, pour amorcer un état vide
        self.battement = lambda: None   # appelé entre deux détecteurs : le chien de garde de systemd
        self.config = dict(config or {})
        self.base = Base(Path(donnees) / "noyau.db")
        self.bus = Bus(self.base)
        self.registre = Registre(self.base, self.bus)
        self.etat_modules = Modules(self.base)
        self.catalogue = Catalogue(self.base)
        self.droits = Droits(self.base)
        self.identite = Identite(self.base, self.droits, (self.config.get("comptes") or {}).get("session_heures", 24),
                                 str((self.config.get("comptes") or {}).get("superadmin_unix", "fastuser")))
        self.executeur = Executeur(self.catalogue, self.bus, self.en_crise, self.droits)
        self.detecteurs = []       # (module, Detecteur, fonction)
        self._derniere = {}        # (module, detecteur) -> dernier passage
        self._pannes = {}          # (module, detecteur) -> pannes de suite
        self._suspendus = set()    # détecteurs coupés par leur disjoncteur
        self.moteurs = []          # (module, Moteur, fonction)
        self._branches = set()     # modules déjà branchés (la greffe à chaud n'ajoute que les autres)
        self._sources = {}         # module -> manifeste.toml qui l'a branché : s'il change (remplacement, retrait), on rebranche
        self._cables = set()       # moteurs sur événement déjà reliés au bus
        self._fils_moteurs = {}    # (module, moteur) -> dernier thread lancé
        self._figes = set()        # moteurs tenus pour figés
        self._moteurs_derniere = {}
        self._moteurs_suspendus = set()
        self._signature = None
        self._refus_dits = set()
        self.rapport = {}

    # ---------- démarrage ----------
    def _racines(self) -> list:
        r = [(self.modules, False)]
        if self.extensions:
            r.append((self.extensions, True))
        return r

    def _fabriquer(self, m):
        self.droits.declarer(m)
        ctx = Contexte(m, self.bus, self.registre, self.catalogue, self.detecteurs, self.config.get(m.id), self.moteurs,
                       {"manifestes": self._manifestes_actifs, "compteurs": self._compteurs, "lecture": self._lecture, "droits": self.droits, "identite": self.identite})
        self.executeur.contextes[m.id] = ctx
        return ctx

    def brancher(self, annoncer: bool = True) -> dict:
        """Branche les modules. `annoncer=False` pour une lecture (état, vérification) : rien n'est écrit au bus."""
        self._amorcer()
        if annoncer and self.droits.amorcer(str((self.config.get("droits") or {}).get("admin_initial", "fastuser"))):
            self.bus.emettre("noyau.admin_amorce", source="noyau", donnees={"compte": (self.config.get("droits") or {}).get("admin_initial", "fastuser")})
        self.actifs = self._actifs_courants()
        self.rapport = chargeur.brancher(self._racines(), self._fabriquer, self.catalogue, self.registre, self.actifs, tolerant=self.gerer,
                                         surcharges=self._surcharges())
        self._branches |= set(self.rapport["branches"])
        self._cabler_moteurs()
        self._noter_sources()
        self._signature = self._signer()
        if annoncer:
            self._dire_refus(self.rapport["refuses"])
            for mid, v in self.rapport.get("remplaces", {}).items():
                self.bus.emettre("noyau.module_remplace", source="noyau", objet=("module", mid),
                                 donnees={"module": mid, "livre": v["livre"], "extension": v["extension"]})
            for mid in self.rapport["introuvables"]:
                self.bus.emettre("noyau.module_introuvable", source="noyau", objet=("module", mid), donnees={"module": mid})
            self.bus.emettre("noyau.demarre", source="noyau", donnees={"modules": self.rapport["ordre"], "a_porter": len(self.rapport["a_porter"])})
            self.rapport["reprises"] = self.reprendre()
        return self.rapport

    # ---------- l'état des modules ----------
    def _actifs_courants(self):
        if self.gerer:
            return self.etat_modules.actifs()
        return self.lire_actifs() if self.lire_actifs else self.actifs

    def _amorcer(self) -> None:
        """Premier démarrage en gestion par état : la liste d'avant (fichier modules.actifs) devient l'état."""
        if self.gerer and self._amorce and not self.etat_modules.tous():
            for mid in self._amorce() or []:
                self.etat_modules.poser(mid, installe=True, actif=True, par="amorce")

    def _manifestes_actifs(self) -> list:
        connus, _ = self._connus()
        return [connus[i][0] for i in sorted(self._branches) if i in connus]

    def _lecture(self, cle: str, args: dict):
        """Une lecture pour le compte d'un module : jamais une écriture, et un échec rend None au lieu de casser l'appelant."""
        e = self.catalogue.get(cle)
        if e is None or e.capacite.ecrit:
            raise PermissionError("« %s » n'est pas une capacité de lecture" % cle)
        r = self.executeur.executer(cle, "cassandra", args)
        return r.get("resultat") if r["statut"] == "faite" else None

    def _compteurs(self, mid: str) -> dict:
        n = self.base.lire("SELECT COUNT(*) AS n FROM constats WHERE module=? AND etat='ouvert'", (mid,))[0]["n"]
        return {"constats": n, "moteurs": sum(1 for m in self.etat_moteurs() if m["cle"].startswith(mid + ".") and m["etat"] != "actif")}

    def _connus(self):
        self._remplaces = {}
        ms, refus = chargeur.decouvrir_tout(self._racines(), self._surcharges(), self._remplaces)
        return {m.id: (m, ext) for m, ext in ms}, refus

    def _surcharges(self):
        """Les modules ESSENTIELS qu'une extension peut remplacer : le choix de l'administrateur ([surcharge] essentiels)."""
        return tuple((self.config.get("surcharge") or {}).get("essentiels", ()))

    def _plan_activation(self, mid: str, avec_dependances: bool = True) -> dict:
        connus, refus = self._connus()
        if mid not in connus:
            raisons = next((r["raisons"] for r in refus if r["module"] == mid), None)
            return {"ok": False, "raison": ("module écarté : " + " ; ".join(raisons)) if raisons else "module inconnu : %s" % mid}
        etats = self.etat_modules.tous()
        chaine = manifeste.avec_dependances([m for m, _ in connus.values()], [mid])
        if not avec_dependances:
            manquants = [x for x in chaine if x != mid and not etats.get(x, {}).get("actif")]
            if manquants:
                return {"ok": False, "raison": "dépend de : " + ", ".join(manquants), "dependances": manquants}
        a_activer = [x for x in chaine if not etats.get(x, {}).get("actif")]
        for x in a_activer:
            if connus[x][0].installation.script and not etats.get(x, {}).get("installe"):
                return {"ok": False, "a_installer": x,
                        "raison": "« %s » s'installe d'abord par l'administrateur système : install.sh --module %s" % (x, x)}
        return {"ok": True, "modules": a_activer}

    def _dependants(self, mid: str, connus: dict, actifs: set) -> list:
        """Les modules ACTIFS qui requièrent `mid`, directement ou non, ceux qui dépendent le plus d'abord."""
        voulus, front = set(), [mid]
        while front:
            cur = front.pop()
            for i in actifs:
                if i in connus and cur in connus[i][0].requiert and i not in voulus:
                    voulus.add(i)
                    front.append(i)
        if not voulus:
            return []
        ordre = manifeste.ordre_installation([connus[i][0] for i in voulus | {mid} if i in connus])
        return [i for i in reversed(ordre) if i in voulus]

    def _plan_desactivation(self, mid: str, cascade: bool = False, forcer: bool = False) -> dict:
        connus, _ = self._connus()
        etats = self.etat_modules.tous()
        if mid not in connus and mid not in etats:
            return {"ok": False, "raison": "module inconnu : %s" % mid}
        if not etats.get(mid, {}).get("actif"):
            return {"ok": True, "modules": []}
        if mid in connus and connus[mid][0].essentiel and not forcer:
            return {"ok": False, "raison": "« %s » est un module essentiel : il ne se désactive pas" % mid, "essentiel": True}
        actifs = {i for i, e in etats.items() if e["actif"]}
        deps = self._dependants(mid, connus, actifs)
        if deps and not cascade:
            return {"ok": False, "raison": "requis par : " + ", ".join(deps), "dependants": deps}
        for d in deps:
            if connus[d][0].essentiel and not forcer:
                return {"ok": False, "raison": "« %s » est essentiel et dépend de « %s »" % (d, mid), "essentiel": True}
        return {"ok": True, "modules": deps + [mid]}

    def activer(self, mid: str, acteur: str = "humain", avec_dependances: bool = True, appliquer: bool = True) -> dict:
        """Active un module (et ses dépendances). Voie humaine ou agent : chaque activation est un événement avec son auteur.
        `appliquer=False` écrit l'état seul ; le noyau en marche le voit et branche à chaud."""
        plan = self._plan_activation(mid, avec_dependances)
        if not plan["ok"]:
            return plan
        connus, _ = self._connus()
        for x in plan["modules"]:
            self.etat_modules.poser(x, installe=True, actif=True, par=acteur)
            self.bus.emettre("module.active", source="noyau", acteur=acteur, objet=("module", x), donnees={"module": x, "demande": mid})
        if appliquer and plan["modules"]:
            self.recharger()
        return {"ok": True, "actives": plan["modules"]}

    def desactiver(self, mid: str, acteur: str = "humain", cascade: bool = False, forcer: bool = False, appliquer: bool = True) -> dict:
        """Désactive un module à chaud : ses moteurs, détecteurs et capacités s'arrêtent, ses données restent."""
        plan = self._plan_desactivation(mid, cascade, forcer)
        if not plan["ok"]:
            return plan
        for x in plan["modules"]:
            self.etat_modules.poser(x, actif=False, par=acteur)
            self.bus.emettre("module.desactive", source="noyau", acteur=acteur, objet=("module", x), donnees={"module": x, "demande": mid})
        if appliquer and plan["modules"]:
            self.recharger()
        return {"ok": True, "desactives": plan["modules"]}

    def _debrancher(self, mid: str) -> dict:
        """Retire un module du noyau en marche. Ses données (objets, événements, savoir-faire) ne sont pas touchées."""
        abonnements = self.bus.desabonner(mid)
        self.droits.oublier(mid)
        self.moteurs[:] = [x for x in self.moteurs if x[0] != mid]
        self.detecteurs[:] = [x for x in self.detecteurs if x[0] != mid]
        self._cables = {k for k in self._cables if k[0] != mid}
        self._suspendus = {k for k in self._suspendus if k[0] != mid}
        self._moteurs_suspendus = {k for k in self._moteurs_suspendus if k[0] != mid}
        self._figes = {k for k in self._figes if k[0] != mid}
        n = self.catalogue.desactiver_module(mid)
        self.executeur.contextes.pop(mid, None)
        self.base.ecrire("UPDATE constats SET etat='suspendu' WHERE module=? AND etat='ouvert'", (mid,))
        self._branches.discard(mid)
        self.bus.emettre("noyau.module_debranche", source="noyau", objet=("module", mid),
                         donnees={"module": mid, "abonnements": abonnements, "capacites": n})
        return {"module": mid, "abonnements": abonnements, "capacites": n}

    def catalogue_modules(self) -> list:
        """Ce que montre le menu des modules : un module par ligne, son état, ses liens, ce qu'on peut en faire."""
        connus, refus = self._connus()
        etats = self.etat_modules.tous()
        requis_par = {}
        for m, _ in connus.values():
            for r in m.requiert:
                requis_par.setdefault(r, []).append(m.id)
        entrees = self.catalogue.lister()
        sortie = []
        for mid, (m, ext) in connus.items():
            e = etats.get(mid, {})
            if e.get("actif"):
                etat = "actif"
            elif m.installation.script and not e.get("installe"):
                etat = "a_installer"
            else:
                etat = "inactif"
            pa = self._plan_activation(mid) if etat != "actif" else {"ok": False, "raison": "déjà actif"}
            pd = self._plan_desactivation(mid) if etat == "actif" else {"ok": False, "raison": "n'est pas actif"}
            mine = [x for x in entrees if x.module == mid]
            sortie.append({
                "id": mid, "nom": m.nom, "description": m.description, "version": m.version, "famille": m.famille or "autres",
                "auteur": m.auteur, "licence": m.licence, "api": m.api,
                "permissions": {"espace_utilisateur": m.permissions.espace_utilisateur, "reseau": list(m.permissions.reseau),
                                "ecritures": list(m.permissions.ecritures), "privileges": list(m.permissions.privileges)},
                "confiance": m.confiance, "essentiel": m.essentiel, "extension": ext, "etat": etat,
                "remplace": (getattr(self, "_remplaces", {}).get(mid).version if getattr(self, "_remplaces", {}).get(mid) else ""),
                "requiert": list(m.requiert), "requis_par": sorted(requis_par.get(mid, [])),
                "objets": len(m.objets), "capacites": len(m.capacites), "implementees": sum(1 for x in mine if x.implementee) if etat == "actif" else None,
                "moteurs": len(m.moteurs), "detecteurs": len(m.detecteurs), "ecrans": len(m.ecrans),
                "peut_activer": pa, "peut_desactiver": pd, "depuis": e.get("maj"), "par": e.get("par", ""),
            })
        for r in refus:
            sortie.append({"id": r["module"], "nom": r["module"], "description": "; ".join(r["raisons"][:2]), "version": "", "famille": "refusés",
                           "confiance": "", "essentiel": False, "extension": True, "etat": "refuse", "requiert": [], "requis_par": [],
                           "objets": 0, "capacites": 0, "implementees": None, "moteurs": 0, "detecteurs": 0, "ecrans": 0,
                           "peut_activer": {"ok": False, "raison": "extension écartée"}, "peut_desactiver": {"ok": False, "raison": ""}, "depuis": None, "par": ""})
        return sorted(sortie, key=lambda x: (x["famille"], x["nom"].lower()))

    # ---------- greffe à chaud ----------
    def _signer(self):
        """Empreinte de ce qui peut changer sans redémarrage : la liste des modules actifs et les extensions déposées."""
        ext = []
        if self.extensions and self.extensions.is_dir():
            for d in sorted(self.extensions.iterdir()):
                f = d / "manifeste.toml"
                if f.exists():
                    ext.append((d.name, f.stat().st_mtime_ns))
        if self.gerer:
            return (self.etat_modules.signature(), tuple(ext))
        actifs = tuple(self.lire_actifs() or ()) if self.lire_actifs else (tuple(self.actifs) if self.actifs is not None else None)
        return (actifs, tuple(ext))

    def _dire_refus(self, refus) -> None:
        """Une extension écartée se dit UNE fois au bus, avec ses raisons ; elle n'empêche rien de ce qui tourne."""
        for r in refus:
            cle = (r["module"], "|".join(r["raisons"]))
            if cle not in self._refus_dits:
                self._refus_dits.add(cle)
                self.bus.emettre("noyau.greffe_refusee", source="noyau", objet=("module", r["module"]),
                                 donnees={"module": r["module"], "raisons": r["raisons"][:6]})

    def recharger(self) -> dict:
        """Greffe à chaud : branche les modules devenus actifs ou déposés depuis le démarrage, sans toucher à ceux qui
        tournent. Un dépôt refusé (manifeste invalide, extension « interne », import d'un autre module) est dit une
        fois au bus, et n'empêche rien de ce qui tourne déjà."""
        self.actifs = self._actifs_courants()
        self._signature = self._signer()
        retires = [self._debrancher(m) for m in sorted(self._branches) if self.actifs is not None and m not in self.actifs]
        # un module dont le manifeste qui le sert a changé (une extension le remplace, ou on la retire) est rebranché à chaud
        connus, _ = self._connus()
        changes = [m for m in sorted(self._branches) if m in connus and str(connus[m][0].source) != self._sources.get(m, str(connus[m][0].source))]
        retires += [self._debrancher(m) for m in changes]
        try:
            r = chargeur.brancher(self._racines(), self._fabriquer, self.catalogue, self.registre, self.actifs, deja=self._branches, tolerant=self.gerer,
                                  surcharges=self._surcharges())
        except manifeste.ManifesteInvalide as ex:
            self.bus.emettre("noyau.greffe_refusee", source="noyau", donnees={"erreurs": ex.erreurs[:10]})
            return {"refuse": ex.erreurs}
        self._dire_refus(r["refuses"])
        self._branches |= set(r["branches"])
        self._cabler_moteurs()
        self._noter_sources()
        for mid in r["branches"]:
            self.bus.emettre("noyau.greffe", source="noyau", objet=("module", mid), donnees={"module": mid})
            if mid in r.get("remplaces", {}):
                self.bus.emettre("noyau.module_remplace", source="noyau", objet=("module", mid),
                                 donnees={"module": mid, "livre": r["remplaces"][mid]["livre"], "extension": r["remplaces"][mid]["extension"]})
        self.rapport = dict(self.rapport, ordre=r["ordre"], a_porter=r["a_porter"])
        return {"branches": r["branches"], "refuses": r["refuses"], "debranches": [x["module"] for x in retires]}

    def _noter_sources(self) -> None:
        connus, _ = self._connus()
        for mid in self._branches:
            if mid in connus:
                self._sources[mid] = str(connus[mid][0].source)

    def _surveiller(self) -> None:
        if (self.gerer or self.lire_actifs or self.extensions) and self._signer() != self._signature:
            self.recharger()

    # ---------- les moteurs : le noyau les ordonnance ----------
    def _cabler_moteurs(self) -> None:
        for module, mo, fn in list(self.moteurs):
            if (module, mo.id) in self._cables or mo.mode != "evenement":
                continue
            self._cables.add((module, mo.id))
            for type_evenement in mo.sur:
                self.bus.ecouter(type_evenement, lambda ev, m=module, mo=mo, fn=fn: self._lancer_moteur(m, mo, fn, ev), module)

    def _lancer_moteur(self, module: str, mo, fn, ev=None) -> dict:
        """Exécute un moteur dans un fil surveillé : durée mesurée, jamais deux fois en même temps, figé s'il dépasse
        sa durée maximale, suspendu après SEUIL_PANNES échecs de suite. Un échec se dit toujours au bus."""
        k = (module, mo.id)
        if k in self._moteurs_suspendus:
            return {"statut": "suspendu"}
        t = self._fils_moteurs.get(k)
        if t is not None and t.is_alive():
            return {"statut": "fige"}
        self._figes.discard(k)
        ctx = self.executeur.contextes[module]
        sortie = {}

        def cible():
            ctx._cause.valeur = ev["id"] if ev else None
            ctx._compte.valeur = ev["compte"] if ev else ""
            d0 = time.time()
            try:
                fn(ctx, ev) if ev is not None else fn(ctx)
            except Exception as ex:
                log.exception("moteur en échec : %s.%s", module, mo.id)
                sortie["erreur"] = str(ex)[:300]
            sortie["duree"] = time.time() - d0

        t = threading.Thread(target=cible, daemon=True, name="moteur-%s.%s" % k)
        self._fils_moteurs[k] = t
        t.start()
        t.join(mo.duree_max_s)
        if t.is_alive():
            self._figes.add(k)
            self._noter_moteur(k, mo.duree_max_s, "", fige=True)
            self.bus.emettre("moteur.fige", source=module, objet=("moteur", "%s.%s" % k), cause=ev["id"] if ev else None,
                             donnees={"moteur": mo.id, "depuis_s": mo.duree_max_s})
            return {"statut": "fige"}
        erreur = sortie.get("erreur", "")
        de_suite = self._noter_moteur(k, sortie.get("duree", 0.0), erreur)
        if erreur:
            self.bus.emettre("moteur.echoue", source=module, objet=("moteur", "%s.%s" % k), cause=ev["id"] if ev else None,
                             donnees={"moteur": mo.id, "erreur": erreur, "de_suite": de_suite})
            if de_suite >= SEUIL_PANNES:
                self._moteurs_suspendus.add(k)
                self.bus.emettre("moteur.suspendu", source=module, objet=("moteur", "%s.%s" % k), donnees={"moteur": mo.id, "apres": de_suite})
            return {"statut": "echec", "erreur": erreur}
        return {"statut": "fait", "duree": sortie.get("duree", 0.0)}

    def _noter_moteur(self, k, duree: float, erreur: str, fige: bool = False) -> int:
        cle = "%s.%s" % k
        echec = 1 if (erreur or fige) else 0
        self.base.ecrire(
            "INSERT INTO moteurs_etat(cle, derniere, duree, executions, echecs, echecs_de_suite, erreur, figes) VALUES (?,?,?,1,?,?,?,?) "
            "ON CONFLICT(cle) DO UPDATE SET derniere=excluded.derniere, duree=excluded.duree, executions=executions+1, echecs=echecs+excluded.echecs, "
            "echecs_de_suite=CASE WHEN excluded.echecs>0 THEN echecs_de_suite+1 ELSE 0 END, erreur=excluded.erreur, figes=figes+excluded.figes",
            (cle, time.time(), duree, echec, echec, erreur, 1 if fige else 0))
        return self.base.lire("SELECT echecs_de_suite FROM moteurs_etat WHERE cle=?", (cle,))[0]["echecs_de_suite"]

    def lancer(self, cle: str, acteur: str = "humain") -> dict:
        """Lance un moteur à la main (humain, agent). Voie parallèle : le moteur n'attend pas qu'on le lui demande,
        mais on peut le lui demander. Un moteur sur événement ne se lance pas sans événement."""
        for module, mo, fn in self.moteurs:
            if "%s.%s" % (module, mo.id) == cle:
                if mo.mode == "evenement":
                    return {"statut": "refuse", "raison": "ce moteur se réveille sur « %s »" % " », « ".join(mo.sur)}
                self.bus.emettre("moteur.demande", source=module, acteur=acteur, objet=("moteur", cle), donnees={"moteur": mo.id})
                self._moteurs_suspendus.discard((module, mo.id))
                return self._lancer_moteur(module, mo, fn)
        return {"statut": "refuse", "raison": "moteur inconnu : %s" % cle}

    def etat_moteurs(self) -> list:
        etat = {r["cle"]: r for r in self.base.lire("SELECT * FROM moteurs_etat")}
        sortie = []
        for module, mo, _ in self.moteurs:
            cle = "%s.%s" % (module, mo.id)
            e = etat.get(cle, {})
            sortie.append({"cle": cle, "mode": mo.mode, "toutes_les_s": mo.toutes_les_s, "sur": ", ".join(mo.sur), "executions": e.get("executions", 0),
                           "echecs": e.get("echecs", 0), "derniere": e.get("derniere"), "duree": e.get("duree"), "erreur": e.get("erreur", ""),
                           "etat": "suspendu" if (module, mo.id) in self._moteurs_suspendus else ("fige" if (module, mo.id) in self._figes else "actif")})
        return sortie

    # ---------- résilience ----------
    def reprendre(self) -> list:
        """Reprise après incident. Une écriture dont le résultat est consigné (`capacite.faite`) mais qui n'a ni
        preuve ni annulation est une écriture interrompue : on la prouve, sinon on la défait. Seul."""
        fin = "('capacite.prouvee','capacite.annulee','capacite.annulation_impossible')"
        orphelines = self.base.lire(
            "SELECT f.* FROM evenements f WHERE f.type='capacite.faite' AND json_extract(f.donnees,'$.resultat') IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM evenements s WHERE s.cause=f.id AND s.type IN " + fin + ") ORDER BY f.id")
        sortie = []
        for f in orphelines:
            ev = self.bus._lire(f["id"])
            e = self.catalogue.get(ev["objet_id"])
            ctx = self.executeur.contextes.get(e.module) if e else None
            if e is None or not e.implementee:
                self.bus.emettre("capacite.reprise_impossible", source="noyau", cause=f["id"], compte=f["compte"],
                                 donnees={"raison": "capacité absente ou non portée"})
                sortie.append((ev["objet_id"], "impossible"))
                continue
            res = ev["donnees"]["resultat"]
            prouve, motif = self.executeur.prouver(e, ctx, res)
            if prouve:
                self.bus.emettre("capacite.prouvee", source=e.module, acteur="noyau", objet=("capacite", e.cle), cause=f["id"],
                                 compte=f["compte"], donnees={"reprise": True})
                sortie.append((e.cle, "prouvee"))
            else:
                annule, detail = self.executeur.defaire(e, ctx, res)
                self.bus.emettre("capacite.annulee" if annule else "capacite.annulation_impossible", source=e.module, acteur="noyau",
                                 objet=("capacite", e.cle), cause=f["id"], compte=f["compte"],
                                 donnees={"reprise": True, "motif": motif, "detail": detail})
                sortie.append((e.cle, "annulee" if annule else "annulation_impossible"))
        return sortie

    def rearmer_detecteur(self, module: str, detecteur: str) -> None:
        self._suspendus.discard((module, detecteur))
        self._pannes.pop((module, detecteur), None)

    # ---------- évolution : ce qui revient ----------
    def recurrences(self, jours: int = 14, seuil: int = 3) -> list:
        """Les constats qui REVIENNENT (même module, détecteur et objet) : la matière du moteur d'évolution.
        Un constat qui revient trois fois en quinze jours demande qu'on corrige la cause, pas qu'on répare encore."""
        return self.base.lire(
            "SELECT source AS module, json_extract(donnees,'$.detecteur') AS detecteur, objet_type, objet_id, compte, COUNT(*) AS n "
            "FROM evenements WHERE type='constat.ouvert' AND ts>=? GROUP BY 1,2,3,4,5 HAVING n>=? ORDER BY n DESC",
            (time.time() - jours * 86400, int(seuil)))

    # ---------- crise ----------
    def en_crise(self) -> bool:
        r = self.base.lire("SELECT valeur FROM etat_noyau WHERE cle='crise'")
        return bool(r) and r[0]["valeur"] == "1"

    def crise(self, active: bool, raison: str = "", acteur: str = "cassandra") -> None:
        self.base.ecrire("INSERT INTO etat_noyau(cle, valeur) VALUES ('crise', ?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", ("1" if active else "0",))
        self.bus.emettre("noyau.crise" if active else "noyau.crise_levee", source="noyau", acteur=acteur, donnees={"raison": raison})

    # ---------- le plafond d'autonomie : un choix d'administrateur ----------
    def regler_palier(self, cle: str, palier: str, acteur: str = "humain") -> dict:
        """L'administrateur règle jusqu'où Cassandra agit seule sur une capacité. Le manifeste fixe le maximum permis ; ici on choisit,
        dans ce maximum. Jamais une validation que Cassandra attendrait : un réglage, journalisé, qu'elle connaît."""
        e = self.catalogue.get(cle)
        if e is None:
            return {"ok": False, "raison": "capacité inconnue : %s" % cle}
        avant = self.catalogue.savoir(cle)["palier"]
        try:
            self.catalogue.regler_palier(cle, palier)
        except ValueError as ex:
            return {"ok": False, "raison": str(ex)}
        self.bus.emettre("savoir.regle", source="noyau", acteur=acteur, objet=("capacite", cle), donnees={"de": avant, "a": palier})
        return {"ok": True, "de": avant, "a": palier}

    # ---------- voie humaine, parallèle ----------
    def agir_humain(self, cle: str, args=None, essai: bool = False, compte: str = "") -> dict:
        """Un humain lance une capacité. Aucun palier ne l'arrête ; Cassandra l'apprend par le bus."""
        return self.executeur.executer(cle, "humain", args, essai=essai, compte=compte)

    def signaler_geste_humain(self, description: str, objet=None, donnees=None, compte: str = "") -> int:
        """Pour un geste fait HORS du noyau (SSH, panneau, fichier) : il entre quand même au cycle."""
        return self.bus.emettre("humain.geste", source="noyau", acteur="humain", objet=objet, compte=compte,
                                donnees=dict(donnees or {}, description=description))

    # ---------- le cycle ----------
    def tick(self, maintenant=None) -> dict:
        """Une passe : chaque détecteur échu perçoit, chaque nouveau constat décide et agit selon le palier."""
        maintenant = time.time() if maintenant is None else maintenant
        rapport = {"detecteurs": 0, "moteurs": 0, "ouverts": 0, "resolus": 0, "pannes": 0, "actions": []}
        for module, d, fonction in list(self.detecteurs):
            self.battement()
            k = (module, d.id)
            if k in self._suspendus or maintenant - self._derniere.get(k, 0) < d.frequence_s:
                continue
            self._derniere[k] = maintenant
            rapport["detecteurs"] += 1
            try:
                constats = fonction(self.executeur.contextes[module]) or []
                for c in constats:
                    if len(c.get("objet", ())) != 2 or not c.get("titre"):
                        raise ValueError("un constat doit porter « objet » (type, id) et « titre »")
                self._pannes.pop(k, None)
            except Exception as ex:   # un détecteur qui plante ne doit JAMAIS ressembler à « rien à signaler »
                log.exception("détecteur en panne : %s.%s", module, d.id)
                self._pannes[k] = self._pannes.get(k, 0) + 1
                self.bus.emettre("noyau.detecteur_en_panne", source=module, donnees={"detecteur": d.id, "erreur": str(ex)[:300], "de_suite": self._pannes[k]})
                rapport["pannes"] += 1
                if self._pannes[k] >= SEUIL_PANNES:      # disjoncteur : on cesse de marteler, et on le dit une fois
                    self._suspendus.add(k)
                    self.bus.emettre("noyau.detecteur_suspendu", source=module, donnees={"detecteur": d.id, "apres": self._pannes[k]})
                continue
            vus = set()
            for c in constats:
                cle = "%s.%s:%s:%s" % (module, d.id, c["objet"][0], c["objet"][1])
                vus.add(cle)
                if self.base.lire("SELECT 1 FROM constats WHERE cle=? AND etat='ouvert'", (cle,)):
                    continue
                compte = c.get("compte", "")
                ev = self.bus.emettre("constat.ouvert", source=module, acteur="sonde", objet=tuple(c["objet"]), compte=compte,
                                      donnees={"detecteur": d.id, "titre": c["titre"], "detail": c.get("detail", "")})
                self.base.ecrire(
                    "INSERT INTO constats(cle,module,detecteur,objet_type,objet_id,titre,etat,ouvert,ferme,evenement) VALUES (?,?,?,?,?,?,'ouvert',?,NULL,?) "
                    "ON CONFLICT(cle) DO UPDATE SET etat='ouvert', titre=excluded.titre, ouvert=excluded.ouvert, ferme=NULL, evenement=excluded.evenement",
                    (cle, module, d.id, c["objet"][0], str(c["objet"][1]), c["titre"], maintenant, ev))
                rapport["ouverts"] += 1
                cap = c.get("capacite") or d.capacite
                if cap:
                    r = self.executeur.executer("%s.%s" % (module, cap), "cassandra", c.get("args"), cause=ev, compte=compte)
                    rapport["actions"].append({"constat": cle, "capacite": cap, "statut": r["statut"]})
            for o in self.base.lire("SELECT cle, evenement FROM constats WHERE module=? AND detecteur=? AND etat='ouvert'", (module, d.id)):
                if o["cle"] not in vus:
                    self.base.ecrire("UPDATE constats SET etat='resolu', ferme=? WHERE cle=?", (maintenant, o["cle"]))
                    origine = self.bus._lire(o["evenement"]) or {}
                    self.bus.emettre("constat.resolu", source=module, acteur="sonde", cause=o["evenement"], compte=origine.get("compte", ""),
                                     donnees={"cle": o["cle"]})
                    rapport["resolus"] += 1
        for module, mo, fn in list(self.moteurs):
            k = (module, mo.id)
            if mo.mode != "periodique" or maintenant - self._moteurs_derniere.get(k, 0) < mo.toutes_les_s:
                continue
            self.battement()
            self._moteurs_derniere[k] = maintenant
            rapport["moteurs"] += 1
            if self._lancer_moteur(module, mo, fn)["statut"] in ("echec", "fige"):
                rapport["pannes"] += 1
        return rapport

    def boucle(self, pause: float = 5.0) -> None:
        """Le cycle en continu. Sous systemd, chaque passe (et chaque détecteur) donne signe de vie : une boucle
        figée est tuée puis relancée de l'extérieur, et `reprendre()` referme ce qu'elle laissait ouvert."""
        self.battement = lambda: systemd.battement()
        systemd.pret("%d module(s), %d détecteur(s)" % (len(self.rapport.get("ordre", [])), len(self.detecteurs)))
        log.info("cycle démarré (pause %.0f s)", pause)
        try:
            while True:
                try:
                    self._surveiller()
                    r = self.tick()
                    systemd.battement("passe : %d ouvert(s), %d résolu(s), %d panne(s)" % (r["ouverts"], r["resolus"], r["pannes"]))
                except Exception:
                    log.exception("passe en échec")
                time.sleep(pause)
        except KeyboardInterrupt:
            systemd.arret()

    # ---------- état ----------
    def etat(self) -> dict:
        caps = self.catalogue.lister()
        paliers = {}
        for e in caps:
            p = self.catalogue.savoir(e.cle)["palier"]
            paliers[p] = paliers.get(p, 0) + 1
        return {
            "version": manifeste.VERSION_NOYAU, "modules": sorted(self._branches),
            "capacites": len(caps), "implementees": sum(1 for e in caps if e.implementee), "paliers": paliers,
            "objets": self.registre.compter(portee=TOUT), "detecteurs": len(self.detecteurs), "moteurs": len(self.moteurs),
            "moteurs_a_surveiller": sorted(m["cle"] for m in self.etat_moteurs() if m["etat"] != "actif"), "suspendus": sorted("%s.%s" % k for k in self._suspendus),
            "constats_ouverts": self.base.lire("SELECT COUNT(*) AS n FROM constats WHERE etat='ouvert'")[0]["n"],
            "evenements": self.base.lire("SELECT COUNT(*) AS n FROM evenements")[0]["n"],
            "crise": self.en_crise(),
        }


# ---------- ligne de commande ----------
def _donnees() -> Path:
    return Path(os.environ.get("CASSANDRA_DONNEES") or RACINE / "donnees")


def _extensions():
    """Le dossier des modules greffés après coup : $CASSANDRA_EXTENSIONS. Il est surveillé MÊME s'il n'existe pas
    encore : une greffe déposée après le démarrage doit être vue."""
    return os.environ.get("CASSANDRA_EXTENSIONS") or None


def _actifs():
    """Les modules actifs, lus dans $CASSANDRA_CONFIG/modules.actifs ; None (tous) si le fichier n'existe pas."""
    dossier = os.environ.get("CASSANDRA_CONFIG")
    f = Path(dossier) / "modules.actifs" if dossier else None
    if not f or not f.exists():
        return None
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]


def _manifestes(avec_extensions: bool = True) -> list:
    racines = [(RACINE / "modules", False)]
    if avec_extensions and _extensions():
        racines.append((Path(_extensions()), True))
    ms, _ = chargeur.decouvrir_tout(racines)
    return [m for m, _ in ms]


def verifier() -> int:
    """Manifestes, isolation, ordre. Une extension refusée n'arrête pas le noyau au démarrage, mais ICI elle fait
    échouer la vérification : c'est ce qu'on veut avant d'activer une greffe."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            n = Noyau(tmp, extensions=_extensions())
            rapport = n.brancher(annoncer=False)
    except manifeste.ManifesteInvalide as ex:
        print(ex, file=sys.stderr)
        return 1
    if rapport["refuses"]:
        for r in rapport["refuses"]:
            print("extension refusée : %s" % r["module"], file=sys.stderr)
            for x in r["raisons"]:
                print("  - %s" % x, file=sys.stderr)
        return 1
    par_id = {m.id: m for m in _manifestes()}
    print("noyau %s : %d module(s), ordre d'installation :" % (manifeste.VERSION_NOYAU, len(rapport["ordre"])))
    for i, mid in enumerate(rapport["ordre"], 1):
        m = par_id[mid]
        print("  %d. %-12s v%s  %d objet(s), %d capacité(s) dont %d qui écrivent, %d détecteur(s)" % (
            i, m.id, m.version, len(m.objets), len(m.capacites), sum(1 for c in m.capacites if c.ecrit), len(m.detecteurs)))
    if rapport["a_porter"]:
        print("à porter depuis la V18 : %s" % ", ".join(rapport["a_porter"]))
    return 0


def commande_module(argv) -> int:
    """python main.py module liste | activer ID | desactiver ID | installe ID | oublier ID | actif ID
    N'agit que sur l'ÉTAT : le noyau en marche le voit et branche ou débranche à chaud. C'est aussi ce que
    l'interface appellera pour son menu des modules."""
    sous = argv[2] if len(argv) > 2 else "liste"
    n = Noyau(_donnees(), extensions=_extensions(), gerer_modules=True, amorce=_actifs)
    n._amorcer()
    ids = [a for a in argv[3:] if not a.startswith("--")]
    opts = {a for a in argv[3:] if a.startswith("--")}
    if sous == "liste":
        for m in n.catalogue_modules():
            print("%-14s %-12s %-11s v%-7s %s%s" % (m["id"], m["famille"], m["etat"], m["version"], m["nom"], "  [essentiel]" if m["essentiel"] else ""))
        return 0
    if not ids:
        print("module %s : un identifiant est attendu" % sous, file=sys.stderr)
        return 2
    mid = ids[0]
    if sous == "actif":
        e = n.etat_modules.get(mid)
        return 0 if e and e["actif"] else 1
    if sous == "installe":
        n.etat_modules.poser(mid, installe=True, par="installateur")
        return 0
    if sous == "oublier":
        n.etat_modules.oublier(mid)
        return 0
    if sous == "activer":
        r = n.activer(mid, acteur="humain", avec_dependances="--sans-dependances" not in opts, appliquer=False)
        print(("activé : " + ", ".join(r["actives"]) if r["actives"] else "déjà actif") if r["ok"] else "refusé : " + r["raison"], file=sys.stderr if not r["ok"] else sys.stdout)
        return 0 if r["ok"] else 1
    if sous == "desactiver":
        r = n.desactiver(mid, acteur="humain", cascade="--en-cascade" in opts, forcer="--forcer" in opts, appliquer=False)
        print(("désactivé : " + ", ".join(r["desactives"]) if r["desactives"] else "déjà inactif") if r["ok"] else "refusé : " + r["raison"], file=sys.stderr if not r["ok"] else sys.stdout)
        return 0 if r["ok"] else 1
    print("module : sous-commande inconnue : %s" % sous, file=sys.stderr)
    return 2


def commande_agir(argv) -> int:
    """python main.py agir CAPACITE [cle=valeur ...] [--acteur humain|compte|cassandra|itare] [--compte C] [--essai]
    Lance une capacité à la main et imprime le résultat en JSON. Les valeurs sont lues comme du JSON (5, true, "x") sinon comme du texte."""
    import json
    if len(argv) < 3:
        print("agir CAPACITE [cle=valeur ...] [--acteur A] [--essai]", file=sys.stderr)
        return 2
    cle, args, acteur, essai, compte = argv[2], {}, "humain", False, ""
    reste = argv[3:]
    i = 0
    while i < len(reste):
        a = reste[i]
        if a == "--acteur" and i + 1 < len(reste):
            acteur = reste[i + 1]
            i += 2
            continue
        if a == "--compte" and i + 1 < len(reste):
            compte = reste[i + 1]
            i += 2
            continue
        if a == "--essai":
            essai = True
        elif "=" in a and not a.startswith("--"):
            k, v = a.split("=", 1)
            try:
                args[k] = json.loads(v)
            except ValueError:
                args[k] = v
        else:
            print("argument illisible : %s" % a, file=sys.stderr)
            return 2
        i += 1
    gerer = bool(os.environ.get("CASSANDRA_CONFIG"))
    try:
        n = Noyau(_donnees(), actifs=None, extensions=_extensions(), gerer_modules=gerer, amorce=_actifs)
        n.brancher(annoncer=False)
    except manifeste.ManifesteInvalide as ex:
        print(ex, file=sys.stderr)
        return 1
    r = n.executeur.executer(cle, acteur, args, essai=essai, compte=compte)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    return 0 if r["statut"] in ("faite", "simulee", "racontee") else 1


def commande_palier(argv) -> int:
    """python main.py palier                  les capacités qui écrivent, avec leur palier et ceux permis
    python main.py palier CLE PALIER          règle jusqu'où Cassandra agit seule sur cette capacité (raconter | auto | maitre)"""
    gerer = bool(os.environ.get("CASSANDRA_CONFIG"))
    try:
        n = Noyau(_donnees(), actifs=None, extensions=_extensions(), gerer_modules=gerer, amorce=_actifs)
        n.brancher(annoncer=False)
    except manifeste.ManifesteInvalide as ex:
        print(ex, file=sys.stderr)
        return 1
    if len(argv) >= 4:
        r = n.regler_palier(argv[2], argv[3])
        print(("%s : %s -> %s" % (argv[2], r["de"], r["a"])) if r["ok"] else "refusé : %s" % r["raison"], file=sys.stdout if r["ok"] else sys.stderr)
        return 0 if r["ok"] else 1
    for e in n.catalogue.lister():
        if e.actif and e.capacite.ecrit:
            print("%-40s %-9s palier %-8s permis : %s" % (e.cle, e.capacite.risque, n.catalogue.savoir(e.cle)["palier"], ", ".join(e.capacite.paliers)))
    return 0


def _cles() -> Path:
    """Les clés de confiance des éditeurs : $CASSANDRA_CONFIG/cles/<editeur>.pub."""
    c = os.environ.get("CASSANDRA_CONFIG")
    return Path(c) / "cles" if c else RACINE / "cles"


def commande_paquet(argv) -> int:
    """python main.py paquet construire DOSSIER --cle PRIVEE.pem [--sortie F] | verifier ARCHIVE | extraire ARCHIVE DEST [--non-signe]"""
    sous = argv[2] if len(argv) > 2 else ""
    args = argv[3:]

    def option(nom):
        return args[args.index(nom) + 1] if nom in args and args.index(nom) + 1 < len(args) else None
    pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--cle", "--sortie"))]
    try:
        if sous == "construire" and pos and option("--cle"):
            print(paquets.construire(pos[0], option("--cle"), option("--sortie")))
            return 0
        if sous == "verifier" and pos:
            v = paquets.verifier(pos[0], _cles())
            print("%s %s %s" % (v["id"], v["version"], ("signé par " + v["editeur"]) if v["signe"] else "non signé"))
            return 0 if v["signe"] else 3
        if sous == "extraire" and len(pos) >= 2:
            v = paquets.extraire(pos[0], pos[1], _cles(), exiger_signature="--non-signe" not in args)
            print("%s %s %s" % (v["id"], v["version"], ("signé par " + v["editeur"]) if v["signe"] else "non signé"))
            return 0
    except (paquets.PaquetInvalide, manifeste.ManifesteInvalide) as ex:
        print("paquet refusé : %s" % ex, file=sys.stderr)
        return 1
    print("paquet : construire DOSSIER --cle PRIVEE.pem | verifier ARCHIVE | extraire ARCHIVE DEST [--non-signe]", file=sys.stderr)
    return 2


def main(argv) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    commande = argv[1] if len(argv) > 1 else "verifier"
    if commande == "verifier":
        return verifier()
    if commande in ("ordre", "versions"):
        try:
            ms = _manifestes(avec_extensions=commande == "ordre")
            if commande == "versions":
                print(chr(10).join("%s %s" % (m.id, m.version) for m in ms))
            else:
                print(chr(10).join(manifeste.avec_dependances(ms, argv[2:]) if argv[2:] else manifeste.ordre_installation(ms)))
        except manifeste.ManifesteInvalide as ex:
            print(ex, file=sys.stderr)
            return 1
        return 0
    if commande == "module":
        return commande_module(argv)
    if commande == "paquet":
        return commande_paquet(argv)
    if commande == "agir":
        return commande_agir(argv)
    if commande == "palier":
        return commande_palier(argv)
    if commande in ("etat", "tick", "demarrer", "moteurs"):
        try:
            gerer = bool(os.environ.get("CASSANDRA_CONFIG"))     # en exploitation : l'état des modules vit dans la base
            n = Noyau(_donnees(), actifs=None if gerer else _actifs(), extensions=_extensions(), lire_actifs=None if gerer else _actifs,
                      gerer_modules=gerer, amorce=_actifs)
            n.brancher(annoncer=commande != "etat")
        except manifeste.ManifesteInvalide as ex:
            print(ex, file=sys.stderr)
            return 1
        if commande == "etat":
            for k, v in n.etat().items():
                print("%-16s %s" % (k, v))
        elif commande == "moteurs":
            for m in n.etat_moteurs():
                quand = "toutes les %d s" % m["toutes_les_s"] if m["mode"] == "periodique" else ("sur " + m["sur"] if m["mode"] == "evenement" else "à la demande")
                print("%-34s %-9s %-26s %4d exéc. %3d échec(s) %s" % (m["cle"], m["etat"], quand, m["executions"], m["echecs"], m["erreur"][:40]))
        elif commande == "tick":
            print(n.tick())
        else:
            n.boucle()
        return 0
    print("commande inconnue : %s (verifier | ordre | versions | module | paquet | agir | palier | etat | moteurs | tick | demarrer)" % commande, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
