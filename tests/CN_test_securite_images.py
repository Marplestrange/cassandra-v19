# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de Sécurité › En images
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #6691f4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de Sécurité › En images : la composition (pure) à partir de l'état de la machine et des totaux du collecteur, et la capacité du module.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6691f4 ▼▼▼
"""Bancs de Sécurité › En images : la composition (pure) à partir de l'état de la machine et des totaux du collecteur, et la capacité du module."""
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                                                                    # noqa: E402
from modules.securite import CN_analyse as an, CN_images as im                                  # noqa: E402
from tests.CN_test_securite_analyse import releves, ecoute                                   # noqa: E402
from tests.CN_test_securite_gestes import FauxCourtier, ADMIN, SIMPLE                        # noqa: E402

MAINTENANT = datetime(2026, 10, 17, 12, 0, 0)


def secu(**kw):
    base = {"jours": [{"jour": "2026-10-16", "s": 30, "r": 20, "n": 5000, "b": 1000}], "heures": [{"jour": "2026-10-16", "heure": 3, "attaques": 42}],
            "chemins": [{"chemin": "/wp-login.php", "n": 900}], "ips_n": 120, "ips_total": 1000, "ips_top10": 400,
            "attaquants": [{"ip": "198.51.100.7", "n": 300, "jours": 5, "premier": "2026-10-08", "dernier": "2026-10-16"}, {"ip": "192.168.1.9", "n": 20, "jours": 1, "premier": "2026-10-16", "dernier": "2026-10-16"}],
            "sites": [{"site": "a.fr", "n": 4000, "b": 1000}], "robots": {"a.fr": [{"robot": "GPTBot", "n": 700}]},
            "diverses": [{"cle": "domaine_courriel.a.fr", "valeur": "SPF strict · DKIM : sel1 · DMARC rejette", "severite": "ok"},
                         {"cle": "box.wifi", "valeur": "WPS actif", "severite": "ok"}, {"cle": "box.upnp", "valeur": "désactivé", "severite": "ok"}],
            "sauvegarde": {"wkey": "sauvegarde.hors_machine", "value": "hier à 03:00", "severity": "ok"}}
    base.update(kw)
    return base


def etat(**kw):
    return an.etat(releves(ecoutes=[ecoute("tcp", "0.0.0.0", 22, "sshd"), ecoute("tcp", "127.0.0.1", 9000, "python3")], **kw), "2026-10-17 12:00:00")


class Composition(unittest.TestCase):
    def test_une_machine_saine_a_l_indice_cent(self):
        p = im.composer(etat(), secu(), maintenant=MAINTENANT)
        self.assertTrue(p["ok"])
        self.assertTrue(p["indice"] <= 100 and p["indice"] >= 0)
        self.assertEqual(p["manques"], [])

    def test_l_indice_retire_six_par_famille_a_regarder_et_quinze_par_panne(self):
        d = etat()
        d["verdict"]["familles"] = [{"lib": "A", "niveau": "regarder", "dit": ""}, {"lib": "B", "niveau": "panne", "dit": ""}, {"lib": "C", "niveau": "ok", "dit": ""}]
        self.assertEqual(im.composer(d, None, maintenant=MAINTENANT)["indice"], 100 - 6 - 15)

    def test_le_courriel_et_la_sauvegarde_s_ajoutent_aux_familles(self):
        libs = [f["lib"] for f in im.composer(etat(), secu(), maintenant=MAINTENANT)["familles"]]
        self.assertIn("Courriel", libs)
        self.assertIn("Sauvegarde", libs)

    def test_les_controles_courriel(self):
        e = im.courriel_etats("AUCUN SPF · AUCUN DMARC")
        self.assertEqual([x[0] for x in e], ["danger", "danger", "danger"])
        e = im.courriel_etats("SPF strict · DKIM : sel1 · DMARC rejette")
        self.assertEqual([x[0] for x in e], ["ok", "ok", "ok"])
        self.assertEqual(im.courriel_etats("SPF ~all · DKIM : aucune · p=none")[1][0], "danger")
        p = im.composer(etat(), secu(), maintenant=MAINTENANT)
        self.assertEqual([k["v"] for k in p["kpis"] if k["lib"] == "contrôles courriel au vert"], ["3 / 3"])

    def test_la_chaleur_est_une_grille_de_sept_jours_par_vingt_quatre_heures(self):
        c = im.composer(etat(), secu(), maintenant=MAINTENANT)["chaleur"]
        self.assertEqual(len(c["jours"]), 7)
        self.assertTrue(all(len(l) == 24 for l in c["grille"]))
        self.assertEqual(c["grille"][c["jours"].index("2026-10-16")][3], 42)
        self.assertEqual(sum(sum(l) for l in c["grille"]), 42)

    def test_les_anneaux_rangent_chaque_service_sur_le_plus_lointain_qui_l_atteint(self):
        a = {x["lib"]: x["services"] for x in im.composer(etat(), secu(), maintenant=MAINTENANT)["anneaux"]}
        self.assertIn("Cassandra", a["La machine seule"])
        self.assertTrue("SSH" in a["Internet"] or "SSH" in a["Réseau local"])

    def test_un_attaquant_de_la_maison_est_marque_de_confiance_et_un_banni_se_voit(self):
        d = etat(outils_etat={"crowdsec": {"installe": True, "convient": True, "resultat": {"moteur": True, "videur": True, "bannies": [{"ip": "Ip:198.51.100.7"}], "pays_7j": [{"pays": "CN", "n": 50}]}}})
        p = im.composer(d, secu(), maintenant=MAINTENANT)
        att = {a["ip"]: a for a in p["attaquants"]}
        self.assertTrue(att["198.51.100.7"]["banni"])
        self.assertFalse(att["198.51.100.7"]["confiance"])
        self.assertTrue(att["192.168.1.9"]["confiance"])
        self.assertEqual(p["pays"], [{"pays": "Chine", "n": 50}])

    def test_la_part_de_robots_d_un_site(self):
        r = im.composer(etat(), secu(), maintenant=MAINTENANT)["robots"][0]
        self.assertEqual((r["site"], r["part"]), ("a.fr", 25))
        self.assertEqual(r["noms"][0]["robot"], "GPTBot")

    def test_les_conteneurs_nomment_les_images_d_trivy(self):
        d = etat(outils_etat={"trivy": {"installe": True, "convient": True, "resultat": {"images": [{"image": "nginx:1", "critiques": 2, "hautes": 5}, {"image": "x", "erreur": "boom"}]}}})
        p = im.composer(d, secu(), docker_ps="nginx:1|web\nredis:7|cache", maintenant=MAINTENANT)
        self.assertEqual(p["trivy"], [{"image": "nginx:1", "critiques": 2, "hautes": 5, "conteneur": "web"}])

    def test_la_box_avertit_pour_wps(self):
        box = {b["lib"]: b["niveau"] for b in im.composer(etat(), secu(), maintenant=MAINTENANT)["box"]}
        self.assertEqual((box["Wi-Fi"], box["UPnP"]), ("warn", "ok"))

    def test_le_premier_certificat_donne_le_niveau_du_compteur(self):
        for jours, niveau in ((5, "danger"), (15, "warn"), (60, "ok")):
            k = [x for x in im.composer(etat(), secu(), certs=[{"domaine": "a.fr", "jours": jours}], maintenant=MAINTENANT)["kpis"] if x["lib"] == "avant le 1er certificat"][0]
            self.assertEqual(k["niveau"], niveau)
        self.assertEqual([x["v"] for x in im.composer(etat(), secu(), maintenant=MAINTENANT)["kpis"] if x["lib"] == "avant le 1er certificat"], ["—"])

    def test_un_collecteur_muet_laisse_les_sections_vides_et_le_dit(self):
        p = im.composer(etat(), None, maintenant=MAINTENANT)
        self.assertEqual(p["manques"], ["collecteur"])
        self.assertEqual((p["jours"], p["chemins"], p["attaquants"], p["robots"]), ([], [], [], []))
        k = [x for x in p["kpis"] if x["lib"] == "adresses attaquantes"][0]
        self.assertEqual((k["v"], k["niveau"]), ("—", "warn"))                      # « — », pas « 0 » : zéro serait une mesure

    def test_les_gardiens_et_fail2ban(self):
        p = im.composer(etat(), secu(), maintenant=MAINTENANT)
        self.assertEqual(p["gardiens"]["fail2ban"], {"prisons": 1, "total": 5, "bannies": 2, "actif": True})
        self.assertFalse(p["gardiens"]["lynis"]["installe"])
        self.assertEqual([k["v"] for k in p["kpis"] if k["lib"] == "gardiens en service"], ["0 / 4"])


class Module(unittest.TestCase):
    def monter(self, avec_sensorium):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("securite", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        if avec_sensorium:                                                              # un faux collecteur : la capacité `secu` du vrai module
            (mods / "sensorium").mkdir()
            (mods / "sensorium" / "CN_manifeste.toml").write_text('''[module]
id = "sensorium"
nom = "Faux collecteur"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Pour les bancs"
confiance = "interne"

[[capacites]]
id = "secu"
libelle = "Les totaux"
risque = "lecture"
''', encoding="utf-8")
            (mods / "sensorium" / "CN_module.py").write_text("def brancher(ctx):\n    ctx.implementer('secu', lambda c: %r)\n" % (secu(),), encoding="utf-8")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("securite", installe=True, par="banc")
        for m in ["droits", "comptes", "securite"] + (["sensorium"] if avec_sensorium else []):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ADMIN, True)
        self.c = FauxCourtier()
        self.c.machine["docker_ps"] = "nginx:1|web"
        self.n.racine.demander = self.c.demander

    def ex(self, compte=ADMIN):
        return self.n.executeur.executer("securite.images", "humain", {}, compte=compte)

    def test_la_page_se_compose_avec_le_collecteur(self):
        self.monter(True)
        r = self.ex()
        self.assertEqual(r["statut"], "faite", r)
        p = r["resultat"]
        self.assertEqual(p["manques"], [])
        self.assertEqual(p["chemins"][0]["chemin"], "/wp-login.php")
        self.assertIn("Courriel", [f["lib"] for f in p["familles"]])

    def test_sans_collecteur_la_page_se_compose_quand_meme_et_le_dit(self):
        self.monter(False)
        p = self.ex()["resultat"]
        self.assertEqual(p["manques"], ["collecteur"])
        self.assertEqual(p["jours"], [])
        self.assertTrue(p["familles"])                                                  # l'état de la machine, lui, est là

    def test_un_compte_ordinaire_ne_voit_pas_la_page(self):
        self.monter(True)
        self.assertEqual(self.ex(SIMPLE)["statut"], "refuse")

    def test_les_gestes_recents_viennent_du_journal(self):
        self.monter(True)
        self.n.executeur.executer("securite.noter", "humain", {"geste": "ssh_x11", "cible": "sshd"}, compte=ADMIN)
        self.assertEqual(self.ex()["resultat"]["gestes"][0]["geste"], "ssh_x11")

    def test_la_page_est_gardee_une_minute(self):
        self.monter(True)
        self.ex()
        n = len([a for a in self.c.appels if a[0] == "mesurer"])
        self.ex()
        self.assertEqual(len([a for a in self.c.appels if a[0] == "mesurer"]), n)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : secu, etat, Composition, Module
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
