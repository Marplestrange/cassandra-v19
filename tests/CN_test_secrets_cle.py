# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la clé des secrets
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #366063
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la clé des secrets : fournie hors des données, repli signalé, anciens secrets relisibles, rien de la clé dans une erreur.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=366063 ▼▼▼
"""Bancs de la clé des secrets : fournie hors des données, repli signalé, anciens secrets relisibles, rien de la clé dans une erreur."""
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from noyau import CN_reglages as rgl          # noqa: E402
from noyau.CN_base import Base                # noqa: E402
from noyau.CN_manifeste import Reglage        # noqa: E402

FAUX = "valeur-inventee-pour-le-banc-7731"
CLE_HEX = "ab" * 32                           # une clé d'essai : 32 octets en hexadécimal


def declarer(rg):
    rg.connus["cof.mdp"] = ("cof", Reglage(id="mdp", libelle="Mot de passe", type="secret"))
    rg.connus["cof.jeton"] = ("cof", Reglage(id="jeton", libelle="Jeton", type="secret"))


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.donnees = Path(self.tmp.name) / "donnees"
        self.hors = Path(self.tmp.name) / "hors"
        self.hors.mkdir()
        self.base = Base(self.donnees / "noyau.db")
        self.repli = self.donnees / "secrets.cle"
        # aucun credential ni variable de l'environnement réel ne doit se mêler aux bancs
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for nom in ("CREDENTIALS_DIRECTORY", rgl.ENV_FICHIER_CLE):
            os.environ.pop(nom, None)

    def reglages(self, **kw):
        rg = rgl.Reglages(self.base, self.repli, **kw)
        declarer(rg)
        return rg

    def cle_hors(self, texte=CLE_HEX, nom="cle"):
        p = self.hors / nom
        p.write_text(texte, encoding="ascii")
        return p


class CleHorsDesDonnees(Monde):
    def test_un_credential_systemd_fournit_la_cle_et_aucun_fichier_de_repli_naitrait(self):
        (self.hors / rgl.NOM_CREDENTIAL).write_text(CLE_HEX, encoding="ascii")
        with mock.patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": str(self.hors)}):
            rg = self.reglages()
            rg.poser("cof.mdp", FAUX, "", "chef")
            self.assertEqual(rg.valeur("cof.mdp"), FAUX)
            self.assertEqual(rg.origine_cle, "credential")
        self.assertFalse(self.repli.exists(), "avec une clé fournie, aucun fichier de clé n'est écrit dans les données")

    def test_une_variable_d_environnement_donne_le_chemin_de_la_cle(self):
        p = self.cle_hors()
        with mock.patch.dict(os.environ, {rgl.ENV_FICHIER_CLE: str(p)}):
            rg = self.reglages()
            rg.poser("cof.mdp", FAUX, "", "chef")
            self.assertEqual(rg.valeur("cof.mdp"), FAUX)
            self.assertEqual(rg.origine_cle, "fichier externe")
        self.assertFalse(self.repli.exists())

    def test_la_cle_peut_etre_brute_hexadecimale_ou_base64(self):
        import base64
        octets = bytes(range(32))
        valeurs = []
        for i, texte in enumerate((octets, octets.hex().encode(), base64.b64encode(octets))):
            p = self.hors / ("k%d" % i)
            p.write_bytes(texte)
            rg = self.reglages(fichier_externe=p)
            rg.poser("cof.mdp", FAUX, "", "chef")
            valeurs.append(rg.base.lire("SELECT valeur FROM reglages WHERE cle='cof.mdp'")[0]["valeur"])
            self.assertEqual(rg.valeur("cof.mdp"), FAUX)
            self.base.ecrire("DELETE FROM reglages")
        self.assertEqual(len(valeurs), 3)

    def test_une_cle_invalide_ou_absente_refuse_sans_la_montrer_et_sans_creer_de_repli(self):
        p = self.cle_hors("pas-une-cle-" + FAUX)
        rg = self.reglages(fichier_externe=p)
        with self.assertRaises(rgl.SecretIllisible) as e:
            rg.poser("cof.mdp", FAUX, "", "chef")
        self.assertNotIn(FAUX, str(e.exception))
        rg2 = self.reglages(fichier_externe=self.hors / "absente")
        with self.assertRaises(rgl.SecretIllisible):
            rg2.poser("cof.mdp", FAUX, "", "chef")
        self.assertFalse(self.repli.exists(), "une clé annoncée mais absente ne doit pas être remplacée en silence par une clé neuve")

    def test_l_ancien_secret_reste_lisible_puis_est_rechiffre_sous_la_nouvelle_cle(self):
        ancien = self.reglages()                                        # d'avant : clé de repli à côté de la base
        ancien.poser("cof.mdp", FAUX, "", "chef")
        ancien.poser("cof.jeton", FAUX + "-bis", "", "chef")
        avant = self.base.lire("SELECT valeur FROM reglages WHERE cle='cof.mdp'")[0]["valeur"]
        self.assertTrue(self.repli.exists())
        p = self.cle_hors()
        neuf = self.reglages(fichier_externe=p)
        self.assertEqual(neuf.valeur("cof.mdp"), FAUX, "un secret écrit avant le changement reste lisible")
        with self.assertLogs("noyau.CN_reglages", level="WARNING") as j:
            neuf.demarrer()
        self.assertTrue(any("rechiffré" in m for m in j.output))
        apres = self.base.lire("SELECT valeur FROM reglages WHERE cle='cof.mdp'")[0]["valeur"]
        self.assertNotEqual(avant, apres)
        self.repli.unlink()                                             # le fichier de repli peut partir
        seul = self.reglages(fichier_externe=p)
        self.assertEqual(seul.valeur("cof.mdp"), FAUX)
        self.assertEqual(seul.valeur("cof.jeton"), FAUX + "-bis")
        self.assertFalse(self.repli.exists())

    def test_la_date_de_pose_ne_bouge_pas_au_rechiffrement(self):
        ancien = self.reglages()
        ancien.poser("cof.mdp", FAUX, "", "chef")
        self.base.ecrire("UPDATE reglages SET maj=1000.0")
        neuf = self.reglages(fichier_externe=self.cle_hors())
        neuf.demarrer()
        self.assertEqual(self.base.lire("SELECT maj FROM reglages")[0]["maj"], 1000.0)


class RepliSignale(Monde):
    def test_le_repli_avertit_et_dit_comment_en_sortir(self):
        rg = self.reglages()
        with self.assertLogs("noyau.CN_reglages", level="WARNING") as j:
            rg.poser("cof.mdp", FAUX, "", "chef")
        texte = "\n".join(j.output)
        self.assertIn("dans le dossier des données", texte)
        self.assertIn(rgl.NOM_CREDENTIAL, texte)
        self.assertNotIn(FAUX, texte)
        self.assertEqual(rg.origine_cle, "fichier de repli")

    def test_une_cle_fournie_dans_le_dossier_des_donnees_est_signalee(self):
        p = self.donnees / "ailleurs.cle"
        p.write_text(CLE_HEX, encoding="ascii")
        rg = self.reglages(fichier_externe=p)
        with self.assertLogs("noyau.CN_reglages", level="WARNING") as j:
            rg.poser("cof.mdp", FAUX, "", "chef")
        self.assertTrue(any("n'en est pas séparée" in m for m in j.output))

    def test_sans_cle_fournie_demarrer_ne_cree_aucun_fichier(self):
        self.reglages().demarrer()
        self.assertFalse(self.repli.exists())


if __name__ == "__main__":
    logging.disable(logging.NOTSET)
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : declarer, Monde, CleHorsDesDonnees, RepliSignale
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
