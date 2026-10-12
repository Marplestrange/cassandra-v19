"""L'exécuteur : la seule porte par laquelle une capacité s'exécute.

Le contrat de souveraineté tient ici, en un seul endroit :
  - personne n'attend personne : le palier de la capacité dit si Cassandra agit seule ;
  - un humain agit en voie parallèle, jamais bloqué par un palier, et Cassandra le sait (événement) ;
  - toute écriture est suivie de sa preuve ; une preuve qui manque déclenche le retour arrière, seul ;
  - tout se raconte au bus, avec la cause et le compte : la lignée est complète et cloisonnée ;
  - le résultat d'une écriture est consigné AVANT sa preuve : si le processus meurt entre les deux,
    `reprendre()` (main.py) sait quoi prouver ou défaire au redémarrage.

Un module qui écrit doit donc rendre un dict (ou rien) sérialisable en JSON.

Non fait dans cette version (à porter de la V18) : second avis pour le risque élevé, point de
restauration générique, budget de ressources, application du périmètre par une cage (voir README).
"""
from __future__ import annotations

import logging

from .catalogue import ORDRE

log = logging.getLogger("noyau.executeur")


class Executeur:
    def __init__(self, catalogue, bus, crise, droits=None, identite=None, exiger_compte=False):
        self.identite = identite
        self.exiger_compte = exiger_compte   # vrai en service : un acte SANS compte, ou au nom d'un compte inconnu, est refusé ET surveillé
        self.droits = droits          # le service des droits (noyau/droits.py) ; None : aucun droit n'est vérifié
        self.catalogue = catalogue
        self.bus = bus
        self.crise = crise            # appelable : True quand le noyau est en crise (seule la lecture passe)
        self.contextes = {}           # module -> Contexte

    @staticmethod
    def _masquer(donnees, cles):
        """Remplace par *** les valeurs que la capacité déclare secrètes : ni mot de passe ni jeton ne doivent finir dans un journal."""
        if not cles or not isinstance(donnees, dict):
            return donnees
        return {k: ("***" if k in cles else v) for k, v in donnees.items()}

    def _evt(self, type, e, acteur, cause, donnees=None, compte=""):
        return self.bus.emettre(type, source=e.module, acteur=acteur, objet=("capacite", e.cle), cause=cause, donnees=donnees or {}, compte=compte)

    def executer(self, cle: str, acteur: str, args=None, cause=None, essai: bool = False, compte: str = "", interne: bool = False) -> dict:
        """`interne` : réservé au code du noyau lui-même (détecteurs, lectures d'un module pour un autre, reprise). Aucune entrée extérieure ne le pose."""
        args = dict(args or {})
        e = self.catalogue.get(cle)
        if e is None:
            return {"statut": "refuse", "raison": "capacité inconnue : %s" % cle}
        c = e.capacite
        # Une capacité qui se déclare PUBLIQUE (qui = ["anonyme"]) s'exécute avant toute connexion (clé de sécurité, code de secours, robot Telegram) :
        # l'acteur est « anonyme », sans compte, et rien d'autre que ce qu'elle déclare n'est joignable ainsi. L'acte reste journalisé, avec son origine.
        public = acteur == "anonyme" and "anonyme" in c.qui and not c.ecrit_sans_preuve
        if self.exiger_compte and not interne and not public:
            # Un acte sans compte n'est pas un acte anonyme ordinaire : c'est une anomalie (ou une attaque) qu'on refuse et qu'on signale.
            if not compte:
                self._evt("capacite.refusee", e, acteur, cause, {"raison": "sans compte", "alerte": True}, compte)
                return {"statut": "refuse", "raison": "aucun compte n'agit : tout acte a un compte, et celui-ci est signalé"}
            if self.identite is not None and not self.identite.existe(compte):
                self._evt("capacite.refusee", e, acteur, cause, {"raison": "compte inconnu", "alerte": True, "compte_pretendu": compte}, compte)
                return {"statut": "refuse", "raison": "le compte « %s » n'existe pas : signalé" % compte}
        if acteur not in c.qui:
            self._evt("capacite.refusee", e, acteur, cause, {"raison": "acteur non autorisé"}, compte)
            return {"statut": "refuse", "raison": "« %s » n'est pas autorisé à utiliser %s" % (acteur, cle)}
        if not e.actif:
            return {"statut": "refuse", "raison": "le module « %s » est désactivé" % e.module}
        if not e.implementee:
            return {"statut": "refuse", "raison": "capacité déclarée mais pas encore portée : %s" % cle}
        if compte and c.droit and self.droits is not None:
            # quel que soit l'acteur : Itare ou Cassandra qui agissent AU NOM d'un compte n'ont pas plus de droits que lui
            d = self.droits.raison(compte, c.droit)
            if not d["accord"]:
                self._evt("capacite.refusee", e, acteur, cause, {"raison": "droit manquant", "droit": c.droit, "parce": d["parce"]}, compte)
                return {"statut": "refuse", "raison": "le compte « %s » n'a pas le droit « %s » (%s)" % (compte, c.droit, d["parce"]), "droit": c.droit}
        if c.ecrit and self.crise():
            self._evt("capacite.refusee", e, acteur, cause, {"raison": "crise : seule la lecture passe"}, compte)
            return {"statut": "refuse", "raison": "le noyau est en crise : seule la lecture passe"}

        demande = self._evt("capacite.demandee", e, acteur, cause, {"args": self._masquer(args, c.masque), "essai": essai}, compte)
        ctx = self.contextes.get(e.module)
        if ctx is not None:
            ctx._cause.valeur, ctx._compte.valeur, ctx._acteur.valeur = demande, compte, acteur
        try:
            if not c.ecrit:
                try:
                    res = e.faire(ctx, **args)
                except Exception as ex:      # une lecture (socket muet, source en panne) se dit, elle ne fait pas tomber l'appelant
                    log.warning("lecture en échec : %s : %s", e.cle, ex)
                    self._evt("capacite.echouee", e, acteur, demande, {"erreur": str(ex)[:300], "lecture": True}, compte)
                    return {"statut": "echec", "erreur": str(ex), "evenement": demande}
                self._evt("capacite.faite", e, acteur, demande, {"lecture": True}, compte)
                return {"statut": "faite", "resultat": res, "evenement": demande}

            if essai:
                sim = e.simuler(ctx, **args) if e.simuler else None
                self._evt("capacite.simulee", e, acteur, demande, {"simulation": sim if e.simuler else "pas de simulation fournie"}, compte)
                return {"statut": "simulee", "simulation": sim, "evenement": demande}

            palier = self.catalogue.savoir(cle)["palier"]
            if acteur != "humain" and palier == "raconter":
                self._evt("capacite.racontee", e, acteur, demande, {"palier": palier, "args": self._masquer(args, c.masque)}, compte)
                return {"statut": "racontee", "evenement": demande}

            return self._ecrire(e, acteur, args, demande, ctx, compte)
        finally:
            if ctx is not None:
                ctx._cause.valeur, ctx._compte.valeur, ctx._acteur.valeur = None, "", ""

    def _ecrire(self, e, acteur, args, demande, ctx, compte) -> dict:
        humain = acteur == "humain"
        try:
            res = e.faire(ctx, **args)
        except Exception as ex:
            log.exception("échec de %s", e.cle)
            self._evt("capacite.echouee", e, acteur, demande, {"erreur": str(ex)[:300]}, compte)
            self._apprendre(e, False, humain, demande, compte)
            return {"statut": "echec", "erreur": str(ex), "evenement": demande}
        res = {} if res is None else res
        # consigné AVANT la preuve : de quoi prouver ou défaire après une mort du processus
        fait = self._evt("capacite.faite", e, acteur, demande, {"resultat": self._masquer(res, e.capacite.masque)}, compte)
        prouve, motif = self.prouver(e, ctx, res)
        if prouve:
            self._evt("capacite.prouvee", e, acteur, fait, {}, compte)
            self._apprendre(e, True, humain, fait, compte)
            return {"statut": "faite", "resultat": res, "evenement": demande}
        annule, detail = self.defaire(e, ctx, res)
        self._evt("capacite.annulee" if annule else "capacite.annulation_impossible", e, acteur, fait, {"motif": motif, "detail": detail}, compte)
        self._apprendre(e, False, humain, fait, compte)
        return {"statut": "annulee" if annule else "annulation_impossible", "motif": motif, "evenement": demande}

    @staticmethod
    def prouver(e, ctx, res):
        try:
            ok = bool(e.prouver(ctx, res))
            return ok, "" if ok else "la preuve n'est pas là"
        except Exception as ex:
            return False, "la preuve a échoué : %s" % str(ex)[:200]

    @staticmethod
    def defaire(e, ctx, res):
        try:
            e.defaire(ctx, res)
            return True, ""
        except Exception as ex:
            log.exception("retour arrière impossible pour %s", e.cle)
            return False, str(ex)[:200]

    def _apprendre(self, e, succes, humain, cause, compte):
        bouge = self.catalogue.apprendre(e.cle, succes, compte_echec=not humain)
        if bouge:
            monte = ORDRE.index(bouge[1]) > ORDRE.index(bouge[0])
            self._evt("savoir.promu" if monte else "savoir.retrograde", e, "noyau", cause, {"de": bouge[0], "a": bouge[1]}, compte)
