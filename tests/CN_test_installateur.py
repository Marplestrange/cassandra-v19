# ══════════════════════════════════════════════
# TITRE      : Bancs de l'installateur des moteurs
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du lot 2 de la maquette d'Évolution : catalogue scellé, paquets épinglés par empreinte, retour arrière, jamais actif d'office.
# MÉTHODE    : un exécuteur de banc pour le réseau (aucun paquet n'est téléchargé) ; un vrai environnement virtuel pour la mécanique.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
"""Bancs de l'installateur : ce qu'il refuse, l'ordre de ses étapes, ce qu'il défait."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_installateur as I  # noqa: E402
from noyau import CN_moteurs as MO  # noqa: E402

CLE = b"cle-de-banc-" * 3
H = "sha256:" + "a" * 64


def entree(**kw):
    e = {"id": "openevolve", "nom": "OpenEvolve", "version": "0.2.1", "adaptateur": "json", "paquets": [{"requis": "openevolve==0.2.1", "empreintes": [H]}]}
    e.update(kw)
    return e


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.journal = []
        self.registre = MO.Registre(self.base / "moteurs.json")

    def catalogue(self, *moteurs, sceller=True):
        cat = {"moteurs": list(moteurs)}
        chemin = self.base / "catalogue.json"
        chemin.write_text(json.dumps(cat), encoding="utf-8")
        sceau = chemin.with_suffix(".sceau")
        if sceller:
            sceau.write_text(I.sceller_catalogue(cat, CLE), encoding="utf-8")
        elif sceau.exists():
            sceau.unlink()                                    # un banc qui rappelle `catalogue` ne garde pas le sceau du précédent
        return chemin

    def faux(self, echec_sur=None):
        """Un exécuteur qui ne télécharge rien : il note la commande, crée le venv pour de faux, et échoue sur demande."""
        def executer(commande, delai_s, cwd):
            self.journal.append(commande)
            if "venv" in commande and commande[1:3] == ["-m", "venv"]:
                Path(commande[3]).mkdir(parents=True)
                return (1, "venv refusé") if echec_sur == "venv" else (0, "")
            if "pip" in commande:
                return (1, "hash mismatch") if echec_sur == "pip" else (0, "")
            return (1, "ModuleNotFoundError") if echec_sur == "import" else (0, "")
        return executer

    def inst(self, chemin, **kw):
        return I.Installateur(self.base / "moteurs", chemin, CLE, registre=self.registre, **kw)


class Catalogue(Banc):
    def test_un_catalogue_scelle_se_lit(self):
        self.assertEqual(I.lire_catalogue(self.catalogue(entree()), CLE)["moteurs"][0]["id"], "openevolve")

    def test_un_catalogue_sans_sceau_est_refuse(self):
        with self.assertRaises(I.InstallationRefusee):
            I.lire_catalogue(self.catalogue(entree(), sceller=False), CLE)

    def test_un_catalogue_modifie_apres_le_sceau_est_refuse(self):
        chemin = self.catalogue(entree())
        cat = json.loads(chemin.read_text(encoding="utf-8"))
        cat["moteurs"][0]["paquets"][0]["requis"] = "pirate==9.9"
        chemin.write_text(json.dumps(cat), encoding="utf-8")
        with self.assertRaises(I.InstallationRefusee) as c:
            I.lire_catalogue(chemin, CLE)
        self.assertIn("modifié", str(c.exception))

    def test_un_sceau_d_une_autre_cle_est_refuse(self):
        with self.assertRaises(I.InstallationRefusee):
            I.lire_catalogue(self.catalogue(entree()), b"une-autre-cle" * 3)

    def test_un_paquet_non_epingle_ou_sans_empreinte_est_refuse(self):
        for p in ({"requis": "openevolve", "empreintes": [H]}, {"requis": "openevolve>=0.2", "empreintes": [H]}, {"requis": "openevolve==0.2.1", "empreintes": []},
                  {"requis": "openevolve==0.2.1", "empreintes": ["md5:abc"]}):
            with self.assertRaises(I.InstallationRefusee, msg=p):
                I.verifier_entree(entree(paquets=[p]))

    def test_un_identifiant_ou_un_adaptateur_dangereux_est_refuse(self):
        for kw in ({"id": "../x"}, {"id": "A B"}, {"adaptateur": "os; rm -rf /"}, {"adaptateur": "a/b"}):
            with self.assertRaises(I.InstallationRefusee, msg=kw):
                I.verifier_entree(entree(**kw))


class Installation(Banc):
    def test_les_etapes_dans_l_ordre_et_le_moteur_est_installe_pas_actif(self):
        r = self.inst(self.catalogue(entree()), executer=self.faux()).installer("openevolve")
        self.assertTrue(r["ok"], r)
        self.assertEqual([e["nom"] for e in r["etapes"]], ["catalogue scellé", "entrée du catalogue", "environnement à part", "paquets épinglés par empreinte",
                                                           "banc d'import de l'adaptateur", "registre des moteurs"])
        m = self.registre.liste()[0]
        self.assertEqual((m["id"], m["etat"], m["genre"]), ("openevolve", "installe", "externe"))
        self.assertEqual(self.registre.moteurs_actifs(), [])

    def test_pip_exige_les_empreintes_et_ne_voit_que_le_fichier_ecrit(self):
        self.inst(self.catalogue(entree()), executer=self.faux()).installer("openevolve")
        pip = [c for c in self.journal if "pip" in c][0]
        self.assertIn("--require-hashes", pip)
        exigences = (self.base / "moteurs" / "openevolve" / "exigences.txt").read_text(encoding="utf-8")
        self.assertEqual(exigences, "openevolve==0.2.1 --hash=%s\n" % H)

    def test_un_echec_a_chaque_etape_defait_tout_et_ne_touche_pas_le_registre(self):
        for ou in ("venv", "pip", "import"):
            with self.subTest(ou):
                self.journal.clear()
                r = self.inst(self.catalogue(entree()), executer=self.faux(echec_sur=ou)).installer("openevolve")
                self.assertFalse(r["ok"], r)
                self.assertEqual([e["nom"] for e in r["etapes"]][-1], "retour arrière")
                self.assertTrue(r["etapes"][-1]["ok"])
                self.assertFalse((self.base / "moteurs" / "openevolve").exists())
                self.assertEqual(self.registre.liste(), [])

    def test_un_moteur_hors_catalogue_ou_un_catalogue_sans_sceau_n_installe_rien(self):
        self.assertFalse(self.inst(self.catalogue(entree()), executer=self.faux()).installer("autre")["ok"])
        self.assertFalse(self.inst(self.catalogue(entree(), sceller=False), executer=self.faux()).installer("openevolve")["ok"])
        self.assertEqual(self.journal, [])                                                  # aucune commande n'a été lancée
        self.assertFalse((self.base / "moteurs").exists())

    def test_une_installation_n_en_ecrase_pas_une_autre(self):
        i = self.inst(self.catalogue(entree()), executer=self.faux())
        self.assertTrue(i.installer("openevolve")["ok"])
        r = i.installer("openevolve")
        self.assertFalse(r["ok"])
        self.assertEqual(r["etapes"][-1]["nom"], "déjà installé")

    def test_desinstaller_supprime_l_environnement_et_remet_prevu(self):
        i = self.inst(self.catalogue(entree()), executer=self.faux())
        i.installer("openevolve")
        self.assertTrue(i.desinstaller("openevolve")["ok"])
        self.assertFalse((self.base / "moteurs" / "openevolve").exists())
        self.assertEqual(self.registre.liste()[0]["etat"], "prevu")
        with self.assertRaises(I.InstallationRefusee):
            i.desinstaller("../..")

    def test_disponibles_dit_ce_qui_est_deja_installe(self):
        i = self.inst(self.catalogue(entree()), executer=self.faux())
        self.assertEqual([m["installe"] for m in i.disponibles()], [False])
        i.installer("openevolve")
        self.assertEqual([m["installe"] for m in i.disponibles()], [True])


class VraiEnvironnement(Banc):
    def test_un_vrai_venv_sans_paquet_se_cree_et_l_adaptateur_s_importe(self):
        """Pas de réseau : l'entrée n'a aucun paquet, son adaptateur est de la bibliothèque standard. La mécanique, elle, est réelle (venv, interpréteur du venv, import)."""
        r = self.inst(self.catalogue(entree(paquets=[], adaptateur="json"))).installer("openevolve")
        self.assertTrue(r["ok"], r)
        self.assertTrue((self.base / "moteurs" / "openevolve" / "venv").is_dir())
        self.assertTrue(Path(self.registre.liste()[0]["python"]).exists())

    def test_un_adaptateur_introuvable_defait_le_vrai_venv(self):
        r = self.inst(self.catalogue(entree(paquets=[], adaptateur="paquet_qui_n_existe_pas"))).installer("openevolve")
        self.assertFalse(r["ok"])
        self.assertFalse((self.base / "moteurs" / "openevolve").exists())


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs de l'installateur.
# LIEN : noyau/CN_installateur.py, noyau/CN_moteurs.py.
