#!/usr/bin/env python3
"""Cassandra V19 : le moteur central.

Ce fichier ASSEMBLE, il ne fait pas de métier. Le métier vit dans modules/<id>/ ; les pièces communes
vivent dans noyau/ (bus, registre, catalogue, exécuteur, chargeur). Ici on les relie et on fait battre
le cycle : percevoir (les détecteurs), décider (le palier de la capacité), agir, prouver, apprendre.

    python main.py verifier          lit les manifestes, vérifie l'isolation, donne l'ordre d'installation
    python main.py ordre [id ...]    ordre d'installation des modules demandés et de leurs dépendances (un id par ligne)
    python main.py versions          « id version » de chaque module (pour deploy.sh)
    python main.py etat              résume le noyau sans rien écrire (modules, objets, constats, paliers)
    python main.py tick              une passe de détection
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
import time
from pathlib import Path

from noyau import chargeur, manifeste, systemd
from noyau.base import Base
from noyau.bus import TOUT, Bus
from noyau.catalogue import Catalogue
from noyau.contexte import Contexte
from noyau.executeur import Executeur
from noyau.registre import Registre

RACINE = Path(__file__).resolve().parent
log = logging.getLogger("noyau")
SEUIL_PANNES = 5   # pannes de suite d'un détecteur avant qu'il soit suspendu (disjoncteur)


class Noyau:
    def __init__(self, donnees, modules=None, config=None, actifs=None):
        self.modules = Path(modules or RACINE / "modules")
        self.actifs = actifs         # None : tous les modules du dossier ; sinon la liste des modules actifs
        self.battement = lambda: None   # appelé entre deux détecteurs : le chien de garde de systemd
        self.config = dict(config or {})
        self.base = Base(Path(donnees) / "noyau.db")
        self.bus = Bus(self.base)
        self.registre = Registre(self.base, self.bus)
        self.catalogue = Catalogue(self.base)
        self.executeur = Executeur(self.catalogue, self.bus, self.en_crise)
        self.detecteurs = []       # (module, Detecteur, fonction)
        self._derniere = {}        # (module, detecteur) -> dernier passage
        self._pannes = {}          # (module, detecteur) -> pannes de suite
        self._suspendus = set()    # détecteurs coupés par leur disjoncteur
        self.rapport = {}

    # ---------- démarrage ----------
    def brancher(self, annoncer: bool = True) -> dict:
        """Branche les modules. `annoncer=False` pour une lecture (état, vérification) : rien n'est écrit au bus."""
        def fabriquer(m):
            ctx = Contexte(m, self.bus, self.registre, self.catalogue, self.detecteurs, self.config.get(m.id))
            self.executeur.contextes[m.id] = ctx
            return ctx
        self.rapport = chargeur.brancher(self.modules, fabriquer, self.catalogue, self.registre, self.actifs)
        if annoncer:
            self.bus.emettre("noyau.demarre", source="noyau", donnees={"modules": self.rapport["ordre"], "a_porter": len(self.rapport["a_porter"])})
            self.rapport["reprises"] = self.reprendre()
        return self.rapport

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
        rapport = {"detecteurs": 0, "ouverts": 0, "resolus": 0, "pannes": 0, "actions": []}
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
            "version": manifeste.VERSION_NOYAU, "modules": self.rapport.get("ordre", []),
            "capacites": len(caps), "implementees": sum(1 for e in caps if e.implementee), "paliers": paliers,
            "objets": self.registre.compter(portee=TOUT), "detecteurs": len(self.detecteurs), "suspendus": sorted("%s.%s" % k for k in self._suspendus),
            "constats_ouverts": self.base.lire("SELECT COUNT(*) AS n FROM constats WHERE etat='ouvert'")[0]["n"],
            "evenements": self.base.lire("SELECT COUNT(*) AS n FROM evenements")[0]["n"],
            "crise": self.en_crise(),
        }


# ---------- ligne de commande ----------
def _donnees() -> Path:
    return Path(os.environ.get("CASSANDRA_DONNEES") or RACINE / "donnees")


def _actifs():
    """Les modules actifs, lus dans $CASSANDRA_CONFIG/modules.actifs ; None (tous) si le fichier n'existe pas."""
    dossier = os.environ.get("CASSANDRA_CONFIG")
    f = Path(dossier) / "modules.actifs" if dossier else None
    if not f or not f.exists():
        return None
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]


def verifier() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            n = Noyau(tmp)
            rapport = n.brancher()
    except manifeste.ManifesteInvalide as ex:
        print(ex, file=sys.stderr)
        return 1
    par_id = {m.id: m for m in manifeste.decouvrir(n.modules)}
    print("noyau %s : %d module(s), ordre d'installation :" % (manifeste.VERSION_NOYAU, len(rapport["ordre"])))
    for i, mid in enumerate(rapport["ordre"], 1):
        m = par_id[mid]
        print("  %d. %-12s v%s  %d objet(s), %d capacité(s) dont %d qui écrivent, %d détecteur(s)" % (
            i, m.id, m.version, len(m.objets), len(m.capacites), sum(1 for c in m.capacites if c.ecrit), len(m.detecteurs)))
    if rapport["a_porter"]:
        print("à porter depuis la V18 : %s" % ", ".join(rapport["a_porter"]))
    return 0


def main(argv) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    commande = argv[1] if len(argv) > 1 else "verifier"
    if commande == "verifier":
        return verifier()
    if commande in ("ordre", "versions"):
        try:
            ms = manifeste.decouvrir(RACINE / "modules")
            if commande == "versions":
                print(chr(10).join("%s %s" % (m.id, m.version) for m in ms))
            else:
                print(chr(10).join(manifeste.avec_dependances(ms, argv[2:]) if argv[2:] else manifeste.ordre_installation(ms)))
        except manifeste.ManifesteInvalide as ex:
            print(ex, file=sys.stderr)
            return 1
        return 0
    if commande in ("etat", "tick", "demarrer"):
        try:
            n = Noyau(_donnees(), actifs=_actifs())
            n.brancher(annoncer=commande != "etat")
        except manifeste.ManifesteInvalide as ex:
            print(ex, file=sys.stderr)
            return 1
        if commande == "etat":
            for k, v in n.etat().items():
                print("%-16s %s" % (k, v))
        elif commande == "tick":
            print(n.tick())
        else:
            n.boucle()
        return 0
    print("commande inconnue : %s (verifier | ordre | versions | etat | tick | demarrer)" % commande, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
