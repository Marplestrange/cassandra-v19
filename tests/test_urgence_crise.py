"""Bancs de la crise AUTOMATIQUE : le moteur de décision (pur), la veille du module (courtier simulé), la commande de mesure."""
import importlib.machinery
import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from modules.urgence import crise as cr                      # noqa: E402
from tests.test_urgence import Monde, BEA, CHEF              # noqa: E402
from noyau.bus import TOUT                                   # noqa: E402


def attaque(n=60):
    return {"ok": True, "services": {}, "adresses": ["198.51.100.%d" % i for i in range(1, n + 1)]}


CALME = {"ok": True, "services": {}, "adresses": []}


class Decision(unittest.TestCase):
    """Le moteur de décision : pur, sans horloge ni machine."""
    def mesure(self, **kw):
        return dict({"paralysie": False, "attaque": False, "detail": []}, **kw)

    def test_les_adresses_de_la_maison_ne_sont_pas_des_attaquants(self):
        for a in ("192.168.1.5", "10.1.2.3", "127.0.0.1", "100.64.0.10", "::1", "fd7a:115c:a1e0::5", "pas-une-ip"):
            self.assertTrue(cr.de_confiance(a), a)
        self.assertFalse(cr.de_confiance("198.51.100.7"))
        self.assertTrue(cr.de_confiance("198.51.100.7", extra=["198.51.100.0/24"]))

    def test_une_attaque_est_un_afflux_d_adresses_nouvelles_pas_de_la_maison(self):
        ev = cr.evaluer({}, None, ["198.51.100.%d" % i for i in range(60)])
        self.assertTrue(ev["attaque"])
        self.assertIn("60 adresses", ev["detail"][0])
        self.assertFalse(cr.evaluer({}, None, ["198.51.100.%d" % i for i in range(10)])["attaque"])
        self.assertFalse(cr.evaluer({}, None, ["192.168.1.%d" % i for i in range(1, 200)])["attaque"])         # 200 adresses, toutes locales : rien

    def test_une_paralysie_demande_au_moins_quatre_services_connus(self):
        s = {n: {"enabled": True, "active": False} for n in ("a", "b", "c")}
        self.assertFalse(cr.evaluer(s, None, None)["paralysie"])                      # trois services : pas assez pour juger
        s["d"] = {"enabled": True, "active": True}
        ev = cr.evaluer(s, None, None)
        self.assertTrue(ev["paralysie"])
        self.assertIn("3 services critiques sur 4", ev["detail"][0])

    def test_un_service_desactive_ne_compte_pas(self):
        s = {"a": {"enabled": False, "active": False}}
        s.update({n: {"enabled": True, "active": True} for n in ("b", "c", "d", "e")})
        self.assertFalse(cr.evaluer(s, None, None)["paralysie"])

    def test_des_sites_qui_ne_repondent_plus(self):
        self.assertTrue(cr.evaluer(None, [{"up": False}, {"up": False}, {"up": True}], None)["paralysie"])
        self.assertFalse(cr.evaluer(None, [{"up": False}], None)["paralysie"])           # un seul site : pas un échantillon
        self.assertFalse(cr.evaluer(None, [{"up": True}, {"up": True}], None)["paralysie"])

    def test_une_mesure_qui_echoue_ne_declenche_jamais_rien(self):
        ev = cr.evaluer(None, None, None)
        self.assertEqual((ev["paralysie"], ev["attaque"]), (False, False))

    def test_la_paralysie_doit_tenir_cinq_minutes(self):
        m = self.mesure(paralysie=True, detail=["3 services sur 4"])
        d = cr.decider(m, {}, 1000, {"palier": "auto"})
        self.assertIsNone(d["action"])                                                # première minute : on note, on ne déclenche pas
        d = cr.decider(m, d["etat"], 1000 + 299, {"palier": "auto"})
        self.assertIsNone(d["action"])
        d = cr.decider(m, d["etat"], 1000 + 301, {"palier": "auto"})
        self.assertEqual(d["action"][0], "declencher")

    def test_une_paralysie_qui_s_arrete_remet_le_compteur_a_zero(self):
        m = self.mesure(paralysie=True)
        d = cr.decider(m, {}, 1000, {"palier": "auto"})
        d = cr.decider(self.mesure(), d["etat"], 1100, {"palier": "auto"})
        d = cr.decider(m, d["etat"], 1400, {"palier": "auto"})
        self.assertIsNone(d["action"])                                                # elle a recommencé à 1400 : pas encore cinq minutes

    def test_une_attaque_declenche_tout_de_suite(self):
        d = cr.decider(self.mesure(attaque=True, detail=["60 adresses"]), {}, 1000, {"palier": "auto"})
        self.assertEqual(d["action"], ("declencher", "60 adresses", ["attaque"]))

    def test_en_raconter_elle_retient_et_ne_le_redit_pas_chaque_minute(self):
        m = self.mesure(attaque=True, detail=["60 adresses"])
        d = cr.decider(m, {}, 1000, {"palier": "raconter"})
        self.assertEqual(d["action"][0], "retenir")
        d = cr.decider(m, d["etat"], 1060, {"palier": "raconter"})
        self.assertIsNone(d["action"])
        d = cr.decider(m, d["etat"], 1000 + 901, {"palier": "raconter"})
        self.assertEqual(d["action"][0], "retenir")                                   # un quart d'heure après : on le redit

    def test_le_palier_par_defaut_est_prudent(self):
        self.assertEqual(cr.decider(self.mesure(attaque=True), {}, 1000, {})["action"][0], "retenir")

    def test_en_crise_le_retour_au_calme_se_dit_une_fois_apres_quinze_minutes(self):
        d = cr.decider(self.mesure(), {"actif": True}, 1000, {})
        self.assertIsNone(d["action"])
        d = cr.decider(self.mesure(), d["etat"], 1000 + 899, {})
        self.assertIsNone(d["action"])
        d = cr.decider(self.mesure(), d["etat"], 1000 + 901, {})
        self.assertEqual(d["action"], ("calme",))
        d = cr.decider(self.mesure(), d["etat"], 1000 + 2000, {})
        self.assertIsNone(d["action"])                                                # une seule fois

    def test_la_crise_ne_se_leve_jamais_seule(self):
        d = {"etat": {"actif": True}}
        for t in (1000, 5000, 90000):
            d = cr.decider(self.mesure(), d["etat"], t, {})
            self.assertTrue(d["action"] in (None, ("calme",)))
        self.assertTrue(d["etat"]["actif"])

    def test_un_nouveau_trouble_pendant_la_crise_remet_le_calme_a_zero(self):
        d = cr.decider(self.mesure(), {"actif": True}, 1000, {})
        d = cr.decider(self.mesure(attaque=True), d["etat"], 1500, {})
        self.assertIsNone(d["etat"]["calme_depuis"])


class Veille(Monde):
    def setUp(self):
        super().setUp()
        self.n.reglages.poser("urgence.crise_auto_palier", "auto")

    def veille(self):
        r = self.n.lancer("urgence.veille")
        self.assertEqual(r["statut"], "fait", r)

    def objet(self):
        return self.ctx.lire("crise", "auto", portee=self.ctx.TOUT)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def test_une_attaque_coupe_les_envois_et_retient_les_agents(self):
        self.c.crise = attaque()
        self.veille()
        self.assertTrue(self.frein("envois") and self.frein("gel"))
        o = self.objet()
        self.assertEqual(o["donnees"]["types"], ["attaque"])
        self.assertTrue(o["donnees"]["envois_pose"] and o["donnees"]["gel_pose"])
        self.assertEqual(len(self.evts("crise.declenchee")), 1)
        e = self.ex("etat")["resultat"]["etat"]["crise"]
        self.assertTrue(e["actif"] and e["auto"])
        self.assertIn("60 adresses", e["raison"])

    def test_elle_ne_ferme_aucun_acces(self):
        self.c.crise = attaque()
        self.veille()
        self.assertEqual([a for a in self.c.appels if a[0] in ("poser", "lever", "confirmer")], [])      # ni le réseau, ni SSH : la crise est mince

    def test_une_seconde_veille_ne_redeclenche_pas(self):
        self.c.crise = attaque()
        self.veille()
        self.veille()
        self.assertEqual(len(self.evts("crise.declenchee")), 1)

    def test_en_raconter_rien_n_est_coupe_mais_c_est_dit(self):
        self.n.reglages.poser("urgence.crise_auto_palier", "raconter")
        self.c.crise = attaque()
        self.veille()
        self.assertFalse(self.frein("envois") or self.frein("gel"))
        self.assertIsNone(self.objet())
        self.assertEqual(len(self.evts("crise.retenue")), 1)
        self.assertTrue(self.ex("etat")["resultat"]["etat"]["crise"]["retenue"].startswith("60"))

    def test_une_mesure_qui_echoue_ne_declenche_rien(self):
        self.c.muet = True
        self.veille()
        self.assertFalse(self.frein("envois"))
        self.assertIsNone(self.objet())

    def test_une_attaque_de_la_maison_ne_declenche_rien(self):
        self.c.crise = {"ok": True, "services": {}, "adresses": ["192.168.1.%d" % i for i in range(1, 100)]}
        self.veille()
        self.assertIsNone(self.objet())

    def test_la_veille_peut_etre_eteinte(self):
        self.n.reglages.poser("urgence.crise_auto_actif", False)
        self.c.crise = attaque()
        self.veille()
        self.assertIsNone(self.objet())
        self.assertEqual(self.c.appels, [])                                           # elle n'a même pas mesuré

    def test_lever_la_crise_rend_ce_que_la_crise_avait_coupe(self):
        self.c.crise = attaque()
        self.veille()
        r = self.ex("crise_auto_lever", motif="réglé : l'attaquant est bloqué en amont")
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(self.frein("envois") or self.frein("gel"))
        self.assertIsNone(self.objet())
        self.assertEqual(len(self.evts("crise.levee")), 1)

    def test_lever_ne_touche_pas_a_un_gel_pose_avant(self):
        self.ex("geler", actif=True)
        self.c.crise = attaque()
        self.veille()
        self.assertFalse(self.objet()["donnees"]["gel_pose"])
        self.ex("crise_auto_lever")
        self.assertTrue(self.frein("gel"))
        self.assertFalse(self.frein("envois"))

    def test_lever_sans_crise_est_refuse(self):
        self.assertEqual(self.ex("crise_auto_lever")["statut"], "echec")

    def test_le_retour_arriere_remet_la_crise(self):
        self.c.crise = attaque()
        self.veille()
        r = self.ex("crise_auto_lever")
        self.n.catalogue.get("urgence.crise_auto_lever").defaire(self.ctx, r["resultat"])
        self.assertTrue(self.frein("envois") and self.frein("gel"))
        self.assertIsNotNone(self.objet())

    def test_seul_un_administrateur_leve_la_crise_et_jamais_un_agent(self):
        self.c.crise = attaque()
        self.veille()
        self.assertEqual(self.ex("crise_auto_lever", compte=BEA)["statut"], "refuse")
        self.assertEqual(self.n.executeur.executer("urgence.crise_auto_lever", "cassandra", {}, compte=CHEF)["statut"], "refuse")
        self.assertTrue(self.frein("envois"))

    def test_le_retour_au_calme_se_dit_mais_la_crise_reste(self):
        self.c.crise = attaque()
        self.veille()
        veille = [f for m, mo, f in self.n.moteurs if m == "urgence" and mo.id == "veille"][0]
        cr_mod = veille.__globals__["cr"]
        ancien = cr_mod.CALME_S
        cr_mod.CALME_S = 0
        self.addCleanup(setattr, cr_mod, "CALME_S", ancien)
        self.c.crise = CALME                                                          # tout est redevenu calme
        self.veille()
        self.veille()
        self.assertEqual(len(self.evts("crise.calme")), 1)
        self.assertTrue(self.objet()["donnees"]["calme_dit"])
        self.assertTrue(self.frein("envois"))                                         # elle ne se lève pas seule
        self.assertTrue(self.ex("etat")["resultat"]["etat"]["crise"]["calme_dit"])

    def test_la_crise_se_voit_comme_un_constat(self):
        self.c.crise = attaque()
        self.veille()
        det = [f for m, d, f in self.n.detecteurs if m == "urgence" and d.id == "crise"][0]
        items = det(self.ctx)
        self.assertEqual(len(items), 1)
        self.assertIn("Crise automatique en cours", items[0]["titre"])

    def test_une_crise_retenue_se_voit_comme_un_constat_tant_que_la_cause_tient(self):
        self.n.reglages.poser("urgence.crise_auto_palier", "raconter")
        self.c.crise = attaque()
        self.veille()
        det = [f for m, d, f in self.n.detecteurs if m == "urgence" and d.id == "crise"][0]
        self.assertIn("non déclenchée", det(self.ctx)[0]["titre"])
        self.c.crise = CALME
        self.veille()
        self.assertEqual(det(self.ctx), [])                                           # la cause a disparu : le constat se referme

    def test_la_mesure_demande_les_services_du_reglage(self):
        self.n.reglages.poser("urgence.crise_services_critiques", "nginx, mysql")
        self.veille()
        arg = [a for a in self.c.appels if a[0] == "crise"][0][1]
        self.assertEqual(arg["services"], ["nginx", "mysql"])
        self.assertEqual(arg["fenetre_min"], 10)

    def test_une_paralysie_de_services_ne_se_declenche_pas_a_la_premiere_minute(self):
        self.c.crise = {"ok": True, "services": {n: {"enabled": True, "active": n == "ssh"} for n in ("nginx", "mysql", "php-fpm", "ssh")}, "adresses": []}
        self.veille()
        self.assertIsNone(self.objet())                                               # elle doit TENIR


def charger_crise():
    chemin = RACINE / "modules" / "urgence" / "commandes" / "crise"
    loader = importlib.machinery.SourceFileLoader("crise_cmd", str(chemin))
    spec = importlib.util.spec_from_loader("crise_cmd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class CommandeCrise(unittest.TestCase):
    def setUp(self):
        self.m = charger_crise()

    def lancer(self, *argv):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = self.m.main(["crise"] + list(argv))
        return code, json.loads(sortie.getvalue())

    def test_un_nom_de_service_illisible_est_refuse(self):
        for noms in (["nginx; rm -rf /"], ["../x"], ["a b"], ["x" * 61]):
            code, r = self.lancer("mesurer", json.dumps({"services": noms}))
            self.assertEqual(code, 1, noms)
            self.assertFalse(r["ok"])

    def test_un_verbe_inconnu_est_refuse(self):
        self.assertEqual(self.lancer("effacer", "{}")[0], 1)

    def test_les_services_absents_de_la_machine_n_apparaissent_pas(self):
        def run(cmd, timeout=20):
            if cmd[:2] == ["systemctl", "is-enabled"]:
                return (0, "enabled") if cmd[2] == "nginx.service" else (1, "not-found")
            if cmd[:2] == ["systemctl", "is-active"]:
                return 3, "inactive"
            return None, ""
        with mock.patch.object(self.m, "run", side_effect=run), mock.patch.object(self.m.shutil, "which", return_value=None):
            code, r = self.lancer("mesurer", json.dumps({"services": ["nginx", "inexistant"]}))
        self.assertEqual(code, 0)
        self.assertEqual(r["services"], {"nginx": {"enabled": True, "active": False}})
        self.assertIsNone(r["adresses"])                                              # CrowdSec absent : la mesure manque, elle n'est pas « zéro »

    def test_les_adresses_sont_celles_des_alertes_de_la_fenetre(self):
        alertes = json.dumps([{"source": {"value": "198.51.100.1"}}, {"source": {"value": "198.51.100.1"}}, {"source": {"value": "198.51.100.2"}}, {"source": {}}])
        with mock.patch.object(self.m, "run", return_value=(0, alertes)), mock.patch.object(self.m.shutil, "which", return_value="/usr/bin/cscli"):
            self.assertEqual(self.m.adresses(10), ["198.51.100.1", "198.51.100.2"])
        with mock.patch.object(self.m, "run", return_value=(1, "")), mock.patch.object(self.m.shutil, "which", return_value="/usr/bin/cscli"):
            self.assertIsNone(self.m.adresses(10))


if __name__ == "__main__":
    unittest.main()
