# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : Le cycle de vie d'un module venu d'une archive
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c51989
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le cycle de vie d'un module venu d'une archive : examiner, installer avec consentement, mettre à jour, revenir en arrière, désinstaller.
# MÉTHODE    : construit de vraies archives signées (openssl, Ed25519) du module d'exemple et déroule le cycle dans des dossiers jetables
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c51989 ▼▼▼
"""Rien ne se pose sans examen, rien ne s'examine sans quarantaine, rien ne s'installe sans le consentement aux permissions telles que montrées ;
ce qui part (ancienne version, module désinstallé, données purgées) part en sauvegarde et peut revenir."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_cycle as C, CN_manifeste as mf, CN_paquets as paquets  # noqa: E402


@unittest.skipUnless(shutil.which("openssl"), "openssl absent")
class Cycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        b = self.base = Path(self.tmp.name)
        self.cles = b / "cles"
        self.cles.mkdir()
        self.priv = b / "editeur.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(self.priv)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.priv), "-pubout", "-out", str(self.cles / "atek.pub")], check=True, capture_output=True)
        self.ext = b / "extensions"
        self.ext.mkdir()
        self.donnees = b / "donnees"
        self.actifs = set()
        self.livres = []
        self.cycle = C.Cycle(self.ext, self.donnees, self.cles, self.connus, lambda: self.actifs)

    def connus(self):
        en_place = [(mf.charger(f), True) for f in sorted(self.ext.glob("*/CN_manifeste.toml"))]
        return list(self.livres) + en_place

    def archive(self, version=None, reseau=None, signe=True, nom="s", confiance=None):
        """Une archive du module d'exemple, dans la version et avec les permissions voulues."""
        src = self.base / ("src_" + nom) / "sentinelle"
        if src.parent.exists():
            shutil.rmtree(src.parent)
        shutil.copytree(RACINE / "exemples" / "sentinelle", src)
        f = src / "CN_manifeste.toml"
        t = f.read_text(encoding="utf-8")
        if version:
            t = re.sub(r'^version = ".*"', 'version = "%s"' % version, t, count=1, flags=re.M)
        if confiance:
            t = re.sub(r'^confiance = ".*"', 'confiance = "%s"' % confiance, t, count=1, flags=re.M)
        if reseau:
            t += "\n[permissions]\nreseau = [%s]\n" % ", ".join('"%s"' % x for x in reseau)
        f.write_text(t, encoding="utf-8")
        sortie = self.base / (nom + ".cmod")
        if signe:
            paquets.construire(src, self.priv, sortie)
        else:
            inconnue = self.base / "inconnue.pem"
            subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(inconnue)], check=True, capture_output=True)   # signée par une clé que personne ne connaît
            paquets.construire(src, inconnue, sortie)
        return sortie.read_bytes()

    def poser(self, octets, politique="signes"):
        e = self.cycle.examiner(octets, politique)
        return e, self.cycle.installer(e["jeton"], e["empreinte_permissions"], politique, par="admin")

    def test_l_examen_ne_pose_rien_et_dit_ce_que_l_archive_ferait(self):
        e = self.cycle.examiner(self.archive())
        self.assertEqual((e["id"], e["statut"], e["signe"], e["editeur"], e["autorise"]), ("sentinelle", "nouveau", True, "atek", True))
        self.assertEqual(list(self.ext.iterdir()), [])                                     # rien n'est posé
        self.assertTrue((self.donnees / "quarantaine" / (e["jeton"] + ".cmod")).is_file())
        self.assertIn("CN_manifeste.toml", " ".join(e["fichiers"]))

    def test_un_paquet_non_signe_est_refuse_par_la_politique_par_defaut(self):
        e = self.cycle.examiner(self.archive(signe=False))
        self.assertFalse(e["autorise"])
        self.assertTrue(any("non signé" in r for r in e["raisons"]), e["raisons"])
        with self.assertRaises(C.CycleErreur):
            self.cycle.installer(e["jeton"], e["empreinte_permissions"])
        e2 = self.cycle.examiner(self.archive(signe=False), "tous")                          # la politique « tous » l'admet, avec un avertissement
        self.assertTrue(e2["autorise"])
        self.assertTrue(e2["avertissements"])

    def test_sans_le_consentement_aux_permissions_montrees_rien_ne_s_installe(self):
        e = self.cycle.examiner(self.archive())
        with self.assertRaisesRegex(C.CycleErreur, "consentement"):
            self.cycle.installer(e["jeton"], "autre-chose")
        self.assertFalse((self.ext / "sentinelle").exists())

    def test_installer_depose_le_dossier_note_le_journal_et_vide_la_quarantaine(self):
        e, r = self.poser(self.archive())
        self.assertTrue((self.ext / "sentinelle" / "CN_manifeste.toml").is_file())
        self.assertEqual((r["id"], r["statut"]), ("sentinelle", "nouveau"))
        self.assertFalse((self.donnees / "quarantaine" / (e["jeton"] + ".cmod")).exists())
        self.assertEqual([x["acte"] for x in self.cycle.journal()], ["installe"])
        e2 = self.cycle.examiner(self.archive())
        self.assertEqual(e2["statut"], "identique")
        with self.assertRaisesRegex(C.CycleErreur, "déjà installée"):
            self.cycle.installer(e2["jeton"], e2["empreinte_permissions"])

    def test_une_mise_a_jour_dit_ce_qui_est_demande_en_plus_et_sauvegarde_l_ancienne(self):
        self.poser(self.archive(version="0.1.2"))
        e = self.cycle.examiner(self.archive(version="0.2.0", reseau=["api.exemple.org"]))
        self.assertEqual((e["statut"], e["version_en_place"]), ("mise_a_jour", "0.1.2"))
        self.assertTrue(any("api.exemple.org" in x for x in e["permissions_elargies"]), e["permissions_elargies"])
        r = self.cycle.installer(e["jeton"], e["empreinte_permissions"], par="admin")
        self.assertEqual(mf.charger(self.ext / "sentinelle" / "CN_manifeste.toml").version, "0.2.0")
        self.assertTrue(Path(r["sauvegarde"]).is_dir())
        self.assertEqual([v["version"] for v in self.cycle.versions("sentinelle")["sauvegardes"]], ["0.1.2"])

    def test_le_retour_arriere_remet_la_version_d_avant_et_garde_celle_qu_il_remplace(self):
        self.poser(self.archive(version="0.1.2"))
        self.poser(self.archive(version="0.2.0", nom="v2"))
        r = self.cycle.retour_arriere("sentinelle", par="admin")
        self.assertEqual((r["version"], r["ancienne"]), ("0.1.2", "0.2.0"))
        self.assertEqual(mf.charger(self.ext / "sentinelle" / "CN_manifeste.toml").version, "0.1.2")
        self.assertIn("0.2.0", [v["version"] for v in self.cycle.versions("sentinelle")["sauvegardes"]])        # on peut revenir sur son retour

    def test_un_retour_arriere_sans_sauvegarde_est_refuse(self):
        self.poser(self.archive())
        with self.assertRaisesRegex(C.CycleErreur, "aucune sauvegarde"):
            self.cycle.retour_arriere("sentinelle")

    def test_desinstaller_refuse_un_module_actif_puis_met_le_dossier_en_sauvegarde(self):
        self.poser(self.archive())
        self.actifs = {"sentinelle"}
        with self.assertRaisesRegex(C.CycleErreur, "actif"):
            self.cycle.desinstaller("sentinelle")
        self.actifs = set()
        r = self.cycle.desinstaller("sentinelle", par="admin")
        self.assertFalse((self.ext / "sentinelle").exists())
        self.assertTrue(Path(r["sauvegarde"]).is_dir())
        self.cycle.retour_arriere("sentinelle")                                              # un module désinstallé revient aussi
        self.assertTrue((self.ext / "sentinelle").is_dir())

    def test_les_donnees_ne_se_purgent_que_d_un_module_absent_et_partent_en_sauvegarde(self):
        self.poser(self.archive())
        (self.donnees / "modules").mkdir(parents=True)
        base = self.donnees / "modules" / "sentinelle.db"
        base.write_text("données", encoding="utf-8")
        with self.assertRaisesRegex(C.CycleErreur, "encore présent"):
            self.cycle.purger_donnees("sentinelle")
        self.cycle.desinstaller("sentinelle")
        r = self.cycle.purger_donnees("sentinelle")
        self.assertTrue(r["purge"] and not base.exists())
        self.assertTrue(any(f.name == "sentinelle.db" for f in Path(r["sauvegarde"]).iterdir()))

    def test_un_module_livre_avec_le_noyau_ne_se_remplace_ni_ne_se_desinstalle_par_archive(self):
        livre = mf.charger(RACINE / "exemples" / "sentinelle" / "CN_manifeste.toml")
        self.livres = [(livre, False)]
        e = self.cycle.examiner(self.archive())
        self.assertFalse(e["autorise"])
        self.assertTrue(any("livré avec le noyau" in r for r in e["raisons"]))
        with self.assertRaisesRegex(C.CycleErreur, "livré avec le noyau"):
            self.cycle.desinstaller("sentinelle")

    def test_la_confiance_interne_est_reservee_aux_modules_livres(self):
        with self.assertRaisesRegex(paquets.PaquetInvalide, "interne"):                    # on ne peut même pas CONSTRUIRE un paquet qui la revendique
            self.archive(confiance="interne")

    def test_une_archive_alteree_ou_demesuree_est_refusee_des_l_examen(self):
        with self.assertRaises(C.CycleErreur):
            self.cycle.examiner(b"pas une archive")
        with self.assertRaises(C.CycleErreur):
            self.cycle.examiner(b"")
        with self.assertRaisesRegex(C.CycleErreur, "trop grande"):
            self.cycle.examiner(b"x" * (C.TAILLE_MAX + 1))
        self.assertEqual(list((self.donnees / "quarantaine").glob("*.cmod")), [])         # ce qui est refusé ne reste pas en quarantaine

    def test_un_jeton_forge_ne_sort_pas_de_la_quarantaine(self):
        for mauvais in ("../../etc/passwd", "", "ZZZ", "a" * 24):
            with self.assertRaises(C.CycleErreur):
                self.cycle.installer(mauvais, "x")

    def test_abandonner_met_l_archive_en_corbeille_et_elle_peut_revenir(self):
        e = self.cycle.examiner(self.archive())
        self.cycle.abandonner(e["jeton"])
        self.assertFalse((self.donnees / "quarantaine" / (e["jeton"] + ".cmod")).exists())
        with self.assertRaises(C.CycleErreur):
            self.cycle.installer(e["jeton"], e["empreinte_permissions"])
        self.cycle.restaurer(e["jeton"])
        self.assertEqual(self.cycle.installer(e["jeton"], e["empreinte_permissions"])["id"], "sentinelle")

    def test_les_archives_oubliees_s_effacent(self):
        e = self.cycle.examiner(self.archive())
        f = self.donnees / "quarantaine" / (e["jeton"] + ".cmod")
        self.assertEqual(self.cycle.purger_quarantaine(age_s=3600), 0)
        os.utime(f, (time.time() - 90000, time.time() - 90000))
        self.assertEqual(self.cycle.purger_quarantaine(age_s=3600), 1)


class Permissions(unittest.TestCase):
    def test_ce_qui_est_demande_en_plus_se_dit(self):
        self.assertEqual(C.elargies({"reseau": ["a.org"]}, {"reseau": ["a.org"]}), [])
        self.assertEqual(C.elargies({"reseau": ["a.org"]}, {"reseau": ["a.org", "b.org"]}), ["reseau : b.org"])
        self.assertEqual(C.elargies({}, {"privileges": ["installer"], "racine": True}), ["privileges : installer", "racine : oui"])

    def test_l_empreinte_ne_depend_pas_de_l_ordre(self):
        self.assertEqual(C.empreinte_permissions({"a": [1], "b": True}), C.empreinte_permissions({"b": True, "a": [1]}))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc du cycle de vie d'un module.
# EC : néant.
# LIEN : noyau/CN_cycle.py (le cycle), exemples/sentinelle (le module d'essai).
