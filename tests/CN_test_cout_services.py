# ══════════════════════════════════════════════
# TITRE      : Bancs de la dépense des services dans le plafond de coût
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #650ee0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prouve que les appels de modèle d'Évolution (rôle « evolution ») comptent dans le plafond de coût de la maison tenu par Agents IA, et qu'Évolution s'arrête quand il est atteint.
# MÉTHODE    : le faux fournisseur « en ligne » des bancs d'Agents IA ; Modèles note l'usage, Agents IA le lit (jamais d'écriture d'un module chez un autre) ; un faux module « agents » pour le banc d'Évolution.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=650ee0 ▼▼▼
"""Bancs : la dépense des services dans le plafond de coût de la maison."""
import shutil
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

from CN_test_agents import ROOT  # noqa: E402
import CN_test_agents_equipe as AE  # noqa: E402
import CN_test_evolution_module as TM  # noqa: E402


class Depense(AE.Equipe):
    def lier_evolution(self):
        self.jour[0] = time.time()                                                  # Modèles date son usage à l'heure réelle : le « jour » d'Agents IA doit être le même
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="evol", cle="sk-evol", base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="evolution", modele_id=mid)
        d = self.eq.DONNEES["tarif_defaut_cts"]
        avant = dict(d)
        d.update(entree=100000, sortie=100000)                                   # un tour du faux modèle (5 + 3 jetons) coûte 0,8 centime
        self.addCleanup(d.update, avant)

    def appeler(self, role="evolution", fois=1):
        """Comme Évolution : par la lecture d'un module (le rôle ne sert que les acteurs de la maison, jamais un compte)."""
        ctx = self.n.executeur.contextes["agents"]
        for _ in range(fois):
            r = ctx.executer_lecture("modeles.completer", messages=[{"role": "user", "content": "x"}], role=role)
            self.assertTrue(r and r.get("ok"), r)

    def test_modeles_dit_ce_qu_un_role_a_depense_en_ligne_et_en_local(self):
        self.lier_evolution()
        self.appeler(fois=2)
        r = self.ex("modeles.depense_roles", compte=ROOT, prefixes=["evolution"])["resultat"]["evolution"]
        self.assertEqual((r["appels"], r["entrees"], r["sorties"]), (2, 10, 6))
        self.assertEqual((r["entrees_en_ligne"], r["sorties_en_ligne"]), (10, 6))                 # le fournisseur du banc se fait passer pour un service en ligne
        self.assertEqual(self.ex("modeles.depense_roles", compte=ROOT, prefixes=["autre"])["resultat"]["autre"]["appels"], 0)

    def test_un_compte_ordinaire_lit_ces_totaux_sans_etre_administrateur(self):
        self.lier_evolution()
        self.appeler()
        r = self.ex("modeles.depense_roles", compte=AE.BEA, prefixes=["evolution"])
        self.assertEqual(r["statut"], "faite", r)

    def test_la_depense_d_evolution_compte_dans_la_depense_de_la_maison(self):
        self.lier_evolution()
        avant = self.ctx_agents().depense()["c"]
        self.appeler(fois=3)
        time.sleep(1.1)                                                                          # Agents IA garde la dépense des services une seconde
        apres = self.ctx_agents().depense()["c"]
        self.assertAlmostEqual(apres - avant, 3 * 0.8, places=3)

    def ctx_agents(self):
        return self.n.executeur.contextes["agents"].stockage and _Depense(self)

    def test_le_plafond_global_retient_evolution_quand_elle_l_atteint(self):
        self.lier_evolution()
        self.regler("plafond_regler", portee="global", euros=0.02, action="arret")                # 2 centimes
        self.assertFalse(self.agent("service_plafond", compte=AE.BEA, service="evolution")["retient"])
        self.appeler(fois=3)                                                                      # 2,4 centimes
        time.sleep(1.1)
        v = self.agent("service_plafond", compte=AE.BEA, service="evolution")
        self.assertTrue(v["retient"], v)
        self.assertEqual((v["portee"], v["action"]), ("global", "arret"))
        self.assertEqual(v["plafond_euros"], 0.02)

    def test_la_depense_d_evolution_se_lit_avec_celle_des_agents(self):
        self.lier_evolution()
        self.appeler(fois=2)
        lignes = self.agent("couts", compte=ROOT, jours=1)["jours"]
        evo = [x for x in lignes if x["agent"] == "evolution"]
        self.assertEqual(len(evo), 1)
        self.assertEqual((evo[0]["appels"], evo[0]["entrees"], evo[0]["sorties"]), (2, 10, 6))
        self.assertAlmostEqual(evo[0]["euros"] * 100, 2 * 0.8, places=3)
        self.assertTrue({"jour", "agent", "appels", "entrees", "sorties", "euros"} <= set(evo[0]))        # les clés que l'écran Agents lit

    def test_un_modele_local_ne_coute_rien_au_plafond(self):
        self.jour[0] = time.time()
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="local", cle="x", base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="evolution", modele_id=mid)
        d = self.eq.DONNEES["tarif_defaut_cts"]
        avant = dict(d)
        d.update(entree=100000, sortie=100000)
        self.addCleanup(d.update, avant)
        g = self.n.catalogue.get("modeles.completer").faire.__globals__
        g["re"] = g["re"]._vrai                                                                    # on retire le déguisement : le faux serveur écoute en 127.0.0.1, donc local
        self.regler("plafond_regler", portee="global", euros=0.02, action="arret")
        self.appeler(fois=5)
        self.assertFalse(self.agent("service_plafond", compte=AE.BEA, service="evolution")["retient"])

    def test_un_service_inconnu_est_une_erreur_dite(self):
        r = self.ex("agents.service_plafond", compte=AE.BEA, service="magie")
        self.assertNotEqual(r["statut"], "faite")


class _Depense:
    """Lit la dépense de la maison comme Agents IA la calcule : via sa capacité `couts` (aujourd'hui), agents et services ensemble."""

    def __init__(self, banc):
        self.banc = banc

    def depense(self):
        c = self.banc.agent("couts", compte=ROOT, jours=1)
        return {"c": c["aujourdhui_euros"] * 100}


FAUX_AGENTS = '''[module]
id = "agents"
nom = "Faux agents"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Pour le banc d'Évolution : un plafond de coût que l'on atteint à la demande"
confiance = "interne"

[[droits]]
id = "utiliser"
libelle = "Utiliser"
defaut = true

[[capacites]]
id = "service_plafond"
libelle = "Le plafond est-il atteint ?"
risque = "lecture"
droit = "utiliser"
'''


class DansEvolution(TM.Banc):
    def setUp(self):
        super().setUp()
        base = Path(self.tmp.name) / "modules" / "agents"
        base.mkdir(parents=True)
        (base / "CN_manifeste.toml").write_text(FAUX_AGENTS, encoding="utf-8")
        self.atteint = {"retient": False, "portee": "global", "action": "arret", "depense_euros": 0.05, "plafond_euros": 0.02}
        (base / "CN_module.py").write_text("ETAT = {}\ndef brancher(ctx):\n    ctx.implementer('service_plafond', lambda c, service='evolution': dict(ETAT))\n", encoding="utf-8")
        self.n.brancher()
        self.assertTrue(self.n.activer("agents")["ok"])
        self.ag = sys.modules.get("CN_module_agents") or None
        self.etat = self.n.catalogue.get("agents.service_plafond").faire.__globals__["ETAT"]

    def test_au_plafond_evolution_n_appelle_plus_de_modele_et_le_dit(self):
        self.etat.update(self.atteint, retient=True)
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "modele"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(r["resultat"]["ok"])
        self.assertIn("plafond de dépense", r["resultat"]["raison"])
        self.assertEqual(self.ex("etat")["resultat"]["pieces"], [])

    def test_sous_le_plafond_evolution_appelle_son_modele_comme_avant(self):
        self.etat.update(self.atteint, retient=False)
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "modele"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertNotIn("plafond de dépense", r["resultat"].get("raison", ""))
        self.assertEqual(r["resultat"]["essais"][0]["verdict"], "divergente")                       # le faux modèle a répondu : sa variante a été jugée

    def test_les_moteurs_gratuits_ne_sont_pas_retenus_par_le_plafond(self):
        self.etat.update(self.atteint, retient=True)
        r = self.proposer_stable({"point": "labo.somme_min", "moteur": "deterministe"})
        self.assertTrue(r["resultat"]["ok"], r["resultat"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs de la dépense des services dans le plafond.
# LIEN : modules/modeles (depense_roles), modules/agents (service_plafond, couts), modules/evolution (appeler_modele).
