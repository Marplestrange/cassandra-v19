"""Bancs du pare-feu du panneau : la validation (pure), le risque de s'enfermer dehors, et l'essai de deux minutes qui se défait seul."""
import json
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from modules.fastpanel import parefeu as pf                  # noqa: E402
from tests.test_fastpanel import Base                          # noqa: E402
from noyau.bus import TOUT                                    # noqa: E402

SSH = {"id": 1, "name": "SSH", "port_range": "22", "proto": "TCP", "type": "INPUT", "policy": "ACCEPT", "rules": []}


class Validation(unittest.TestCase):
    def v(self, **kw):
        d = {"nom": "Web", "ports": "443", "proto": "TCP", "sens": "INPUT", "politique": "ACCEPT", "sources": ""}
        d.update(kw)
        return pf.valider(d)

    def test_une_regle_valide_prend_la_forme_de_l_api(self):
        corps, err = self.v(ports="4500-5500", politique="PARTIAL_ACCEPT", sources="10.0.0.0/8, 192.168.1.5/32")
        self.assertEqual(err, "")
        self.assertEqual(corps["port_range"], "4500-5500")
        self.assertEqual([r["source"] for r in corps["rules"]], ["10.0.0.0/8", "192.168.1.5"])        # une adresse seule perd son /32

    def test_les_refus(self):
        for kw, mot in (({"nom": ""}, "nom"), ({"nom": "x;rm -rf"}, "nom"), ({"ports": "0"}, "ports"), ({"ports": "70000"}, "ports"), ({"ports": "500-100"}, "ports"),
                        ({"ports": "80,443"}, "ports"), ({"proto": "ICMP"}, "protocole"), ({"politique": "PEUTETRE"}, "politique"),
                        ({"politique": "PARTIAL_ACCEPT"}, "au moins une adresse"), ({"sources": "pas-une-ip", "politique": "PARTIAL_DROP"}, "illisible")):
            corps, err = self.v(**kw)
            self.assertIsNone(corps, kw)
            self.assertIn(mot, err, kw)

    def test_les_sources_ne_comptent_que_pour_une_politique_partielle(self):
        corps, _ = self.v(politique="ACCEPT", sources="10.0.0.1")
        self.assertEqual(corps["rules"], [])

    def test_cinquante_adresses_au_plus(self):
        _, err = self.v(politique="PARTIAL_ACCEPT", sources=",".join("10.0.%d.%d" % (i // 250, i % 250 + 1) for i in range(51)))
        self.assertIn("50 adresses", err)


class Risque(unittest.TestCase):
    def regle(self, **kw):
        return dict({"name": "x", "port_range": "22", "proto": "TCP", "type": "INPUT", "policy": "DROP", "rules": []}, **kw)

    def test_refuser_ssh_a_tous_sans_tailscale_laisse_dehors(self):
        refus, _ = pf.risque(self.regle(), [], "ACCEPT", ssh=22, tailscale=False)
        self.assertIn("dehors", refus)

    def test_avec_tailscale_c_est_permis_mais_a_l_essai(self):
        refus, ferme = pf.risque(self.regle(), [], "ACCEPT", ssh=22, tailscale=True)
        self.assertEqual(refus, "")
        self.assertTrue(ferme)

    def test_le_port_ssh_est_celui_de_la_machine(self):
        refus, _ = pf.risque(self.regle(port_range="2222"), [], "ACCEPT", ssh=2222, tailscale=False)
        self.assertIn("2222", refus)
        refus, _ = pf.risque(self.regle(port_range="2222"), [], "ACCEPT", ssh=22, tailscale=False)
        self.assertEqual(refus, "")

    def test_ouvrir_ne_ferme_rien(self):
        self.assertEqual(pf.risque(self.regle(policy="ACCEPT"), [], "ACCEPT"), ("", False))

    def test_retirer_la_regle_qui_ouvrait_sous_une_politique_qui_refuse_ferme(self):
        self.assertEqual(pf.risque(None, [SSH], "DROP", retire=1), ("", True))
        self.assertEqual(pf.risque(None, [SSH], "ACCEPT", retire=1), ("", False))

    def test_refuser_par_defaut_exige_une_regle_ssh(self):
        self.assertIn("exige d'abord", pf.politique_refus("DROP", [], ssh=22, tailscale=False))
        self.assertEqual(pf.politique_refus("DROP", [SSH], ssh=22, tailscale=False), "")
        self.assertEqual(pf.politique_refus("DROP", [], ssh=22, tailscale=True), "")
        self.assertIn("ACCEPT ou DROP", pf.politique_refus("PARTIAL", [SSH]))

    def test_une_regle_se_recree_telle_que_l_api_l_a_rendue(self):
        r = dict(SSH, rules=[{"source": "1.2.3.4"}, {"source": ""}], extra="ignoré")
        self.assertEqual(pf.corps_de(r), {"name": "SSH", "port_range": "22", "proto": "TCP", "type": "INPUT", "policy": "ACCEPT", "rules": [{"source": "1.2.3.4"}]})


class Panneau(Base):
    def setUp(self):
        super().setUp()
        self.noyau()
        self.ctx = self.n.executeur.contextes["fastpanel"]

    def faire(self, cap, **args):
        return self.e("fastpanel." + cap, "humain", args, compte="")

    def essais(self):
        return self.ctx.lister(portee=TOUT, type="fastpanel_essai")

    def test_lire_le_pare_feu(self):
        r = self.faire("parefeu")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["politique"], "ACCEPT")
        self.assertEqual(r["resultat"]["regles"][0]["nom"], "SSH")

    def test_poser_une_regle_qui_ouvre_est_prouve_sans_essai(self):
        r = self.faire("parefeu_regle_poser", nom="Web", ports="443", politique="ACCEPT")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("Web", [x["name"] for x in self.faux.regles])
        self.assertNotIn("essai", r["resultat"])                              # ce qui n'a pas pu fermer n'a pas besoin de filet

    def test_une_regle_qui_refuse_est_posee_a_l_essai(self):
        r = self.faire("parefeu_regle_poser", nom="Pas MySQL", ports="3306", politique="DROP")
        self.assertEqual(r["statut"], "faite", r)
        essai = r["resultat"]["essai"]
        self.assertAlmostEqual(essai["fin"] - time.time(), 120, delta=5)
        self.assertEqual([e["id"] for e in self.essais()], [essai["jeton"]])

    def test_garder_l_essai_arrete_le_filet_et_laisse_la_regle(self):
        j = self.faire("parefeu_regle_poser", nom="Pas MySQL", ports="3306", politique="DROP")["resultat"]["essai"]["jeton"]
        r = self.faire("parefeu_trancher", jeton=j, garder=True)
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("Pas MySQL", [x["name"] for x in self.faux.regles])
        self.assertEqual(self.essais(), [])

    def test_defaire_l_essai_remet_tout_de_suite(self):
        j = self.faire("parefeu_regle_poser", nom="Pas MySQL", ports="3306", politique="DROP")["resultat"]["essai"]["jeton"]
        self.assertEqual(self.faire("parefeu_trancher", jeton=j, garder=False)["statut"], "faite")
        self.assertNotIn("Pas MySQL", [x["name"] for x in self.faux.regles])
        self.assertEqual(self.faire("parefeu_trancher", jeton=j, garder=False)["statut"], "echec")        # déjà tranché

    def test_le_filet_defait_seul_un_essai_echu(self):
        j = self.faire("parefeu_regle_poser", nom="Pas MySQL", ports="3306", politique="DROP")["resultat"]["essai"]["jeton"]
        o = self.ctx.lire("fastpanel_essai", j, portee=TOUT)
        self.ctx.poser("fastpanel_essai", j, o["libelle"], etat="en_cours", donnees=dict(o["donnees"], fin=time.time() - 1))
        self.assertEqual(self.n.lancer("fastpanel.filet")["statut"], "fait")
        self.assertNotIn("Pas MySQL", [x["name"] for x in self.faux.regles])
        self.assertEqual(self.essais(), [])
        self.assertEqual(len([e for e in self.evts("fastpanel.essai_defait")]), 1)

    def test_un_essai_qui_n_est_pas_echu_reste(self):
        self.faire("parefeu_regle_poser", nom="Pas MySQL", ports="3306", politique="DROP")
        self.assertEqual(self.n.lancer("fastpanel.filet")["statut"], "fait")
        self.assertIn("Pas MySQL", [x["name"] for x in self.faux.regles])

    def test_refuser_ssh_a_tous_est_refuse_sans_tailscale(self):
        if __import__("os").path.exists("/sys/class/net/tailscale0"):
            self.skipTest("cette machine a Tailscale")
        r = self.faire("parefeu_regle_poser", nom="Pas SSH", ports="22", politique="DROP")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("dehors", r["erreur"])
        self.assertNotIn("Pas SSH", [x["name"] for x in self.faux.regles])

    def test_modifier_une_regle_se_defait_comme_avant(self):
        r = self.faire("parefeu_regle_poser", id=1, nom="SSH", ports="2200", politique="ACCEPT")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.faux.regles[0]["port_range"], "2200")
        self.n.catalogue.get("fastpanel.parefeu_regle_poser").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.faux.regles[0]["port_range"], "22")

    def test_retirer_la_regle_ssh_sous_refus_par_defaut_est_a_l_essai(self):
        self.faux.politique = "DROP"
        r = self.faire("parefeu_regle_retirer", id=1)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.faux.regles, [])
        self.assertIn("essai", r["resultat"])
        self.faire("parefeu_trancher", jeton=r["resultat"]["essai"]["jeton"], garder=False)
        self.assertEqual([x["name"] for x in self.faux.regles], ["SSH"])         # la règle est recréée telle que l'API l'avait rendue

    def test_la_politique_refuser_exige_ssh_et_se_pose_a_l_essai(self):
        r = self.faire("parefeu_politique", politique="DROP")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.faux.politique, "DROP")
        self.assertIn("essai", r["resultat"])
        self.faire("parefeu_trancher", jeton=r["resultat"]["essai"]["jeton"], garder=False)
        self.assertEqual(self.faux.politique, "ACCEPT")

    def test_la_politique_drop_sans_regle_ssh_est_refusee(self):
        if __import__("os").path.exists("/sys/class/net/tailscale0"):
            self.skipTest("cette machine a Tailscale")
        self.faux.regles = []
        r = self.faire("parefeu_politique", politique="DROP")
        self.assertEqual(r["statut"], "echec")
        self.assertEqual(self.faux.politique, "ACCEPT")

    def test_une_regle_invalide_n_atteint_pas_le_panneau(self):
        avant = len(self.faux.requetes)
        r = self.faire("parefeu_regle_poser", nom="", ports="443", politique="ACCEPT")
        self.assertEqual(r["statut"], "echec")
        self.assertFalse(any(q[0] == "PUT" and "firewall" in q[1] for q in self.faux.requetes[avant:]))


if __name__ == "__main__":
    unittest.main()
