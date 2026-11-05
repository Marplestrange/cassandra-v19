# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La famille d'un agent
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #2fc433
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La famille d'un agent : l'agent propriétaire d'un module garde tous les outils de ce module, quoi qu'il arrive ; un autre agent peut en être doté, et la dotation se retire.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2fc433 ▼▼▼
"""La famille d'un agent : l'agent propriétaire d'un module garde tous les outils de ce module, quoi qu'il arrive ; un autre agent peut en être doté, et la dotation se retire.

Le propriétaire est celui que le manifeste du module déclare (`proprietaire`), la tuile du menu celle de son `groupe`. Les listes de répartition (CN_equipe.json) ne font que
décider du reste : elles ne privent jamais un propriétaire de ses outils (le module `mandats` est à Cassandra, mais la liste « bureau » le range avec le bureau d'Itare)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                        # noqa: E402

BEA, ROOT = "bea@x.fr", "root@x.fr"
MODULES = ("modeles", "memoire", "notes", "mandats", "dns", "vue", "agents")      # dns et vue sont dans la tuile « parc » : à Cassandra, hors de la liste du bureau d'Itare


class Famille(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        for m in MODULES:
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in MODULES:
            if not cls.n.activer(m)["ok"]:
                raise AssertionError("le module %s ne s'active pas dans le monde d'essai" % m)
        cls.n.droits.regler_admin(ROOT, True)
        cls.ctx = cls.n.executeur.contextes["agents"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tearDown(self):
        """Chaque cas repart d'une équipe sans dotation ni retrait : on les défait comme un administrateur le ferait."""
        for a in self.agent("dotations")["agents"]:
            for d in a["dotations"]:
                self.ex("agents.dotation_retirer", agent=a["agent"], portee=d["portee"], cible=d["cible"])
        self.ctx.stockage.ecrire("DELETE FROM agent_paliers")

    def ex(self, capacite, compte=ROOT, **args):
        return self.n.executeur.executer(capacite, "humain", args, compte=compte)

    def agent(self, cap, compte=ROOT, **args):
        r = self.ex("agents." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def cles(self, agent):
        """Les outils que l'agent a vraiment : ce que montre son écran, pour le compte de l'administrateur."""
        return {o["cle"] for o in self.agent("agent", id=agent)["outils"]}

    def de(self, agent, *modules):
        return sorted(k for k in self.cles(agent) if k.split(".", 1)[0] in modules)

    def modules_de(self, proprio):
        return {m for m, (p, _) in self.ctx.proprietaires().items() if p == proprio}

    def tous_les_outils_de_ses_modules(self, agent):
        propres = self.modules_de(agent)
        return {t["cle"] for t in self.ctx.outils(agent) if t["cle"].split(".", 1)[0] in propres}

    # ------------------------------------------------------------------ le propriétaire n'est jamais dépossédé
    def test_les_manifestes_disent_qui_possede_quoi(self):
        p = self.ctx.proprietaires()
        self.assertEqual(p["mandats"][0], "cassandra")
        self.assertEqual(p["notes"], ("itare", "desk"))
        self.assertEqual(p["dns"], ("cassandra", "parc"))

    def test_cassandra_garde_les_outils_de_ses_modules_meme_quand_une_liste_les_range_au_bureau(self):
        """`mandats` est dans la liste « bureau » (Cassandra n'a pas le bureau) mais il est à Cassandra : elle en garde tous les outils."""
        attendus = self.tous_les_outils_de_ses_modules("cassandra")
        self.assertTrue([k for k in attendus if k.startswith("mandats.")], "le module mandats n'offre aucun outil à Cassandra")
        self.assertEqual(attendus - self.cles("cassandra"), set())

    def test_itare_garde_les_outils_de_ses_modules(self):
        attendus = self.tous_les_outils_de_ses_modules("itare")
        self.assertTrue([k for k in attendus if k.startswith("notes.")])
        self.assertEqual(attendus - self.cles("itare"), set())

    def test_les_modules_d_un_autre_restent_hors_de_la_famille(self):
        """Rien ne change pour le reste : Cassandra n'a toujours pas le bureau d'Itare, Itare toujours pas l'infrastructure."""
        self.assertEqual(self.de("cassandra", "notes"), [])
        self.assertEqual(self.de("itare", "dns"), [])
        self.assertTrue(self.de("itare", "vue"), "un module commun (aucune liste) reste aux deux")

    def test_un_outil_de_sa_propre_famille_ne_se_retire_pas(self):
        outil = [k for k in self.tous_les_outils_de_ses_modules("cassandra") if k.startswith("dns.")][0]
        r = self.ex("agents.palier_regler", agent="cassandra", outil=outil, palier="retire")
        self.assertNotEqual(r["statut"], "faite", r)
        self.assertIn("propriétaire", str(r))
        self.assertIn(outil, self.cles("cassandra"))

    def test_un_retrait_deja_pose_sur_un_outil_propre_ne_compte_plus(self):
        outil = [k for k in self.tous_les_outils_de_ses_modules("cassandra") if k.startswith("dns.")][0]
        self.ctx.stockage.ecrire("INSERT INTO agent_paliers(agent, compte, outil, palier, confirmer, maj) VALUES (?,?,?,?,?,?)", ("cassandra", "", outil, "retire", 0, 1.0))
        o = {x["cle"]: x for x in self.agent("agent", id="cassandra")["outils"]}
        self.assertIn(outil, o)
        self.assertFalse(o[outil]["retire"])

    def test_un_outil_qui_n_est_pas_a_l_agent_se_retire_toujours(self):
        """Le retrait reste possible pour ce qu'on n'a pas en propre : un outil commun d'un module qu'un autre agent possède."""
        communs = self.de("itare", "memoire")
        self.assertTrue(communs)
        r = self.ex("agents.palier_regler", compte=BEA, agent="itare", outil=communs[0], palier="retire")
        self.assertEqual(r["statut"], "faite", r)

    # ------------------------------------------------------------------ doter un autre agent, et le lui retirer
    def test_doter_itare_de_la_tuile_parc_lui_donne_les_outils_de_ses_modules_puis_se_retire(self):
        self.assertEqual(self.de("itare", "dns"), [])
        r = self.agent("dotation_poser", agent="itare", portee="tuile", cible="parc")
        self.assertEqual(r["modules"], 2)
        self.assertTrue(self.de("itare", "dns"))
        self.agent("dotation_retirer", agent="itare", portee="tuile", cible="parc")
        self.assertEqual(self.de("itare", "dns"), [])

    def test_doter_un_module_seul_ne_donne_que_celui_la(self):
        """Doter le module `dns` ne rend pas pour autant le bureau de Cassandra à Itare, ni l'inverse : seul `dns` change."""
        avant = self.cles("itare")
        self.agent("dotation_poser", agent="itare", portee="module", cible="dns")
        apres = self.cles("itare")
        self.assertTrue(self.de("itare", "dns"))
        self.assertEqual({k.split(".", 1)[0] for k in apres - avant}, {"dns"})
        self.assertEqual(avant - apres, set())

    def test_doter_cassandra_de_la_famille_d_itare_puis_la_reprendre(self):
        self.assertEqual(self.de("cassandra", "notes"), [])
        self.agent("dotation_poser", agent="cassandra", portee="agent", cible="itare")
        self.assertTrue(self.de("cassandra", "notes"))
        self.agent("dotation_retirer", agent="cassandra", portee="agent", cible="itare")
        self.assertEqual(self.de("cassandra", "notes"), [])

    def test_retirer_une_dotation_ne_prend_jamais_la_famille_propre(self):
        attendus = self.tous_les_outils_de_ses_modules("cassandra")
        r = self.ex("agents.dotation_retirer", agent="cassandra", portee="module", cible="dns")
        self.assertNotEqual(r["statut"], "faite", r)
        self.assertEqual(attendus - self.cles("cassandra"), set())

    def test_la_famille_propre_ne_se_prete_pas(self):
        r = self.ex("agents.dotation_poser", agent="cassandra", portee="module", cible="dns")
        self.assertNotEqual(r["statut"], "faite", r)
        self.assertIn("propriétaire", str(r))

    def test_une_dotation_ne_donne_pas_ce_que_la_capacite_refuse_a_l_acteur(self):
        """La dotation lève la liste de répartition, jamais la règle propre à la capacité ([qui]) ni le droit du compte."""
        self.agent("dotation_poser", agent="itare", portee="tuile", cible="parc")
        permis = {t["cle"] for t in self.ctx.outils("itare")}
        self.assertEqual(self.cles("itare") - permis, set())

    def test_seul_l_administrateur_dote_et_retire(self):
        for cap in ("dotation_poser", "dotation_retirer"):
            r = self.ex("agents." + cap, compte=BEA, agent="itare", portee="module", cible="dns")
            self.assertNotEqual(r["statut"], "faite", (cap, r))
        self.assertEqual(self.agent("dotations", compte=BEA), {"agents": []})

    def test_les_agents_qui_n_ont_pas_de_famille_n_en_recoivent_pas(self):
        for a in ("amizo", "vision"):
            r = self.ex("agents.dotation_poser", agent=a, portee="module", cible="dns")
            self.assertNotEqual(r["statut"], "faite", (a, r))

    def test_une_dotation_inconnue_ou_vide_est_refusee(self):
        for portee, cible in (("module", "nexiste_pas"), ("tuile", "nulle_part"), ("region", "dns"), ("module", "")):
            r = self.ex("agents.dotation_poser", agent="itare", portee=portee, cible=cible)
            self.assertNotEqual(r["statut"], "faite", (portee, cible, r))
        r = self.ex("agents.dotation_retirer", agent="itare", portee="module", cible="dns")
        self.assertNotEqual(r["statut"], "faite", r)

    def test_la_lecture_dit_ce_qui_est_a_chacun_et_ce_qui_est_prete(self):
        self.agent("dotation_poser", agent="itare", portee="module", cible="dns")
        d = {a["agent"]: a for a in self.agent("dotations")["agents"]}
        self.assertIn("mandats", d["cassandra"]["propres"])
        self.assertIn("notes", d["itare"]["propres"])
        self.assertEqual(d["itare"]["dotations"], [{"portee": "module", "cible": "dns", "modules": 1}])
        self.assertEqual(d["cassandra"]["dotations"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Famille
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
