# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des mesures d'horloge et de résolution DNS du collecteur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #124392
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des mesures d'horloge et de résolution DNS du collecteur : chrony, horloge matérielle, résolveur configuré comparé à un résolveur public, réponses « puits ». Le collecteur est chargé sur une base temporaire ; run_cmd (chronyc, timedat
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=124392 ▼▼▼
"""Bancs des mesures d'horloge et de résolution DNS du collecteur : chrony, horloge matérielle, résolveur configuré comparé à un résolveur public, réponses « puits ».
Le collecteur est chargé sur une base temporaire ; run_cmd (chronyc, timedatectl, dig) et les fichiers système sont simulés : aucune commande, aucun réseau, aucun service."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from tests.CN_test_sensorium_v19 import charger_demon  # noqa: E402

CHRONY = """Reference ID    : A9FEA97B (169.254.169.123)
Stratum         : 4
System time     : %s seconds %s of NTP time
Last offset     : -0.000010344 seconds
Leap status     : %s
"""


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m = charger_demon(self.tmp)
        self.outils = {"chronyc", "timedatectl", "dig"}
        self.sorties = {}
        self.resolv = self.tmp / "resolv.conf"
        self.rtc = self.tmp / "rtc"
        for nom, val in (("_RESOLV_CONF", str(self.resolv)), ("_RTC_DIR", str(self.tmp / "absent"))):
            p = mock.patch.object(self.m, nom, val)
            p.start()
            self.addCleanup(p.stop)
        for nom, f in (("_qui", lambda n: "/usr/bin/" + n if n in self.outils else ""), ("run_cmd", self.run_cmd)):
            p = mock.patch.object(self.m, nom, f)
            p.start()
            self.addCleanup(p.stop)

    def run_cmd(self, cmd, timeout=10, input_data=None):
        if cmd[0] == "dig":
            return self.sorties.get((cmd[5], cmd[6].lstrip("@")), "")
        return self.sorties.get(cmd[0], "")

    def ligne(self, rows, cle):
        r = [x for x in rows if x["cle"] == cle]
        return r[0] if r else None


class Horloge(Banc):
    def test_synchronisee(self):
        self.sorties["chronyc"] = CHRONY % ("0.000012000", "fast", "Normal")
        r = self.ligne(self.m.collect_horloge(), "horloge.synchronisation")
        self.assertEqual(r["severite"], "info")
        self.assertIn("synchronisée", r["valeur"])
        self.assertIn("+0.000", r["valeur"])

    def test_derive_en_avance_et_en_retard(self):
        for sens, signe in (("fast", "+2.300"), ("slow", "-2.300")):
            self.sorties["chronyc"] = CHRONY % ("2.3", sens, "Normal")
            r = self.ligne(self.m.collect_horloge(), "horloge.synchronisation")
            self.assertEqual(r["severite"], "warning")
            self.assertIn("DÉRIVE", r["valeur"])
            self.assertIn(signe, r["valeur"])

    def test_non_synchronisee(self):
        self.sorties["chronyc"] = CHRONY % ("0.1", "slow", "Not synchronised")
        r = self.ligne(self.m.collect_horloge(), "horloge.synchronisation")
        self.assertEqual(r["severite"], "warning")
        self.assertIn("NON SYNCHRONISÉE", r["valeur"])

    def test_horloge_jamais_reglee(self):
        self.sorties["chronyc"] = CHRONY % ("0.0", "fast", "Normal")
        with mock.patch.object(self.m.time, "time", return_value=86400.0 * 400):                # 1971
            r = self.ligne(self.m.collect_horloge(), "horloge.synchronisation")
        self.assertEqual(r["severite"], "warning")
        self.assertIn("NON RÉGLÉE", r["valeur"])
        self.assertIn("1971", r["valeur"])

    def test_sans_chrony_timedatectl_dit_oui_ou_non(self):
        self.outils.discard("chronyc")
        self.sorties["timedatectl"] = "NTPSynchronized=yes"
        self.assertEqual(self.ligne(self.m.collect_horloge(), "horloge.synchronisation")["severite"], "info")
        self.sorties["timedatectl"] = "NTPSynchronized=no"
        self.assertEqual(self.ligne(self.m.collect_horloge(), "horloge.synchronisation")["severite"], "warning")

    def test_sans_aucun_outil_aucune_mesure_inventee(self):
        self.outils.clear()
        self.assertEqual(self.m.collect_horloge(), [])

    def test_sortie_de_chrony_illisible_retombe_sur_ntp(self):
        self.sorties["chronyc"] = "506 Cannot talk to daemon"
        self.sorties["timedatectl"] = "NTPSynchronized=yes"
        r = self.ligne(self.m.collect_horloge(), "horloge.synchronisation")
        self.assertIn("(NTP)", r["valeur"])

    def test_chrony_seul_illisible_ne_dit_rien(self):
        self.outils.discard("timedatectl")
        self.sorties["chronyc"] = "506 Cannot talk to daemon"
        self.assertIsNone(self.ligne(self.m.collect_horloge(), "horloge.synchronisation"))

    def test_pas_d_horloge_materielle(self):
        self.sorties["chronyc"] = CHRONY % ("0.0", "fast", "Normal")
        self.sorties["timedatectl"] = "NTPSynchronized=yes"
        (self.tmp / "rtc").mkdir()
        p = mock.patch.object(self.m, "_RTC_DIR", str(self.rtc))
        p.start()
        self.addCleanup(p.stop)
        r = self.ligne(self.m.collect_horloge(), "horloge.materielle")
        self.assertEqual(r["severite"], "info")
        self.assertIn("aucune horloge matérielle", r["valeur"])
        self.sorties["timedatectl"] = "NTPSynchronized=no"
        self.assertEqual(self.ligne(self.m.collect_horloge(), "horloge.materielle")["severite"], "warning", "sans pile ET sans réseau de temps : l'heure est fausse")

    def test_avec_horloge_materielle_ou_sans_dossier_rien_a_dire(self):
        (self.rtc).mkdir()
        (self.rtc / "rtc0").mkdir()
        p = mock.patch.object(self.m, "_RTC_DIR", str(self.rtc))
        p.start()
        self.addCleanup(p.stop)
        self.assertIsNone(self.ligne(self.m.collect_horloge(), "horloge.materielle"))
        p.stop()
        self.assertIsNone(self.ligne(self.m.collect_horloge(), "horloge.materielle"), "un conteneur n'a pas de dossier rtc : on ne l'invente pas")

    def test_les_cles_sont_relues_par_le_modele_du_monde(self):
        self.assertIn("horloge.", self.m.PREFIXES_DIVERSES)
        self.assertIn(self.m.collect_horloge, [f for f in vars(self.m).values() if callable(f) and f.__name__ == "collect_horloge"])


class DNS(Banc):
    def avec_resolveur(self, adresse="192.168.1.1"):
        self.resolv.write_text("# généré\nnameserver %s\nnameserver 8.8.4.4\nsearch maison\n" % adresse, encoding="utf-8")

    def test_sans_dig_sans_resolv_ou_en_ipv6_rien(self):
        self.avec_resolveur()
        self.outils.discard("dig")
        self.assertEqual(self.m.collect_dns_sante(), [])
        self.outils.add("dig")
        self.resolv.unlink()
        self.assertEqual(self.m.collect_dns_sante(), [])
        self.resolv.write_text("nameserver fe80::1\n", encoding="utf-8")
        self.assertEqual(self.m.collect_dns_sante(), [])

    def test_un_resolveur_qui_repond_juste(self):
        self.avec_resolveur()
        for nom, ip in (("iana.org", "192.0.43.8"), ("example.com", "93.184.216.34")):
            self.sorties[(nom, "192.168.1.1")] = ip
        r = self.m.collect_dns_sante()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["cle"], r[0]["severite"]), ("dns.sante", "info"))
        self.assertIn("192.168.1.1 répond juste", r[0]["valeur"])

    def test_un_puits_127_0_0_1_est_detecte_et_compare_au_public(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "192.168.1.1"): "127.0.0.1", ("iana.org", "1.1.1.1"): "192.0.43.8",
                             ("example.com", "192.168.1.1"): "93.184.216.34"})
        r = self.m.collect_dns_sante()[0]
        self.assertEqual(r["severite"], "warning")
        self.assertIn("PUITS", r["valeur"])
        self.assertIn("127.0.0.1", r["valeur"])
        self.assertIn("192.0.43.8", r["valeur"])

    def test_0_0_0_0_est_un_puits_aussi(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "192.168.1.1"): "0.0.0.0", ("iana.org", "9.9.9.9"): "192.0.43.8", ("example.com", "192.168.1.1"): "93.184.216.34"})
        self.assertIn("PUITS", self.m.collect_dns_sante()[0]["valeur"], "le premier public muet, le second répond")

    def test_une_reponse_melee_n_est_pas_un_puits(self):
        self.assertFalse(self.m._dns_puits(["127.0.0.1", "192.0.43.8"]))
        self.assertTrue(self.m._dns_puits(["127.0.0.1", "127.0.0.2"]))
        self.assertFalse(self.m._dns_puits([]))

    def test_un_resolveur_muet_alors_que_le_public_repond(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "1.1.1.1"): "192.0.43.8", ("example.com", "192.168.1.1"): "93.184.216.34"})
        r = self.m.collect_dns_sante()[0]
        self.assertEqual(r["severite"], "warning")
        self.assertIn("ne répond pas pour iana.org", r["valeur"])

    def test_rien_ne_repond_nulle_part_n_est_pas_une_panne_du_resolveur(self):
        self.avec_resolveur()
        r = self.m.collect_dns_sante()[0]
        self.assertEqual(r["severite"], "info")
        self.assertIn("Internet est peut-être coupé", r["valeur"])

    def test_des_adresses_differentes_du_public_ne_sont_pas_une_panne(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "192.168.1.1"): "10.0.0.5", ("example.com", "192.168.1.1"): "10.0.0.6", ("iana.org", "1.1.1.1"): "192.0.43.8"})
        self.assertEqual(self.m.collect_dns_sante()[0]["severite"], "info")

    def test_seules_les_adresses_ipv4_comptent(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "192.168.1.1"): "iana.org.cdn.exemple.\nrésolu\n192.0.43.8", ("example.com", "192.168.1.1"): "93.184.216.34"})
        self.assertEqual(self.m.collect_dns_sante()[0]["severite"], "info")

    def test_un_resolveur_lent_alerte(self):
        self.avec_resolveur()
        self.sorties.update({("iana.org", "192.168.1.1"): "192.0.43.8", ("example.com", "192.168.1.1"): "93.184.216.34"})
        horloges = iter([0.0, 2.0, 2.0, 4.0])                                             # deux questions de deux secondes
        with mock.patch.object(self.m.time, "perf_counter", lambda: next(horloges)):
            r = self.m.collect_dns_sante()[0]
        self.assertEqual(r["severite"], "warning")
        self.assertIn("2000 ms", r["valeur"])

    def test_la_mesure_est_relue_et_dite_en_francais(self):
        self.assertIn("dns.", self.m.PREFIXES_DIVERSES)
        import CN_lecture as lec
        self.assertEqual(lec.libelle("dns.sante"), "DNS — santé de la résolution")
        self.assertEqual(lec.famille_de("dns.sante"), "reseau")
        self.assertEqual(lec.famille_de("horloge.synchronisation"), "system")
        self.assertEqual(lec.libelle("horloge.materielle"), "Horloge — pile matérielle")

    def test_une_panne_de_la_mesure_ne_casse_pas_la_relève(self):
        """Les mesures diverses les appellent dans une boucle qui attrape tout : on vérifie qu'elles y sont inscrites."""
        import inspect
        src = inspect.getsource(self.m.collect_mesures_diverses)
        self.assertIn("collect_horloge", src)
        self.assertIn("collect_dns_sante", src)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Banc, Horloge, DNS
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
