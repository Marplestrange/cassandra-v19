# ══════════════════════════════════════════════
# TITRE      : Bancs de l'installation depuis l'écran (répertoire, épinglage, adaptateur généré, mise à jour, tâches de fond)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #7f2410
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prouve que tout chercheur du répertoire peut être préparé, installé et mis à jour depuis l'écran : l'épinglage, Python posé, le repli de l'adaptateur généré (vérifié sans être exécuté), la mise à jour qui bascule ou qui revient, les tâches de fond.
# MÉTHODE    : aucun réseau, aucun vrai pip : un exécuteur de banc écrit des faux environnements ; le modèle est une fonction de banc.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7f2410 ▼▼▼
"""Bancs de l'installation depuis l'écran."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_adaptateur_gen as G  # noqa: E402
from noyau import CN_epinglage as E  # noqa: E402
from noyau import CN_installateur as I  # noqa: E402
from noyau import CN_moteurs as MO  # noqa: E402
from noyau import CN_repertoire as R  # noqa: E402
ESSAI_REEL = G.essai_a_blanc                       # d'autres bancs remplacent G.essai_a_blanc : on garde le vrai pour juger sa règle
from noyau import CN_taches as T  # noqa: E402

CLE = b"cle-de-banc-" * 3
CODE_BON = ('IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    import monpaquet  # noqa\n    monpaquet.Optimiseur(1)\n    sortie = modele("réécris " + contexte["source_reference"], "executant")\n'
            '    return [{"texte": sortie, "hypothese": "banc"}]\n')


class Faux:
    """Un exécuteur de banc : pip « résout » et « télécharge » sans réseau, un venv est un dossier, Python se « pose »."""

    def __init__(self, base, version_pip="1.0.0", echec=None):
        self.base, self.version, self.echec, self.journal = Path(base), version_pip, echec, []

    def __call__(self, commande, delai_s, cwd):
        self.journal.append(list(commande))
        c = commande
        if c[:1] == ["env"]:                                                         # uv, par `env VAR=… uv …`
            c = [x for x in c if "=" not in x or x.startswith("-")][1:] if False else [x for x in c[1:] if not (("=" in x) and not x.startswith("/"))]
            if "install" in c:
                return (1, "pas de réseau") if self.echec == "python" else (0, "installé")
            if "find" in c:
                chemin = self.base / "pythons" / "py313" / "bin" / "python"
                chemin.parent.mkdir(parents=True, exist_ok=True)
                chemin.write_text("#!/bin/sh\n", encoding="utf-8")
                return 0, str(chemin)
        if c[1:3] == ["-m", "venv"]:
            cible = Path(c[3])
            (cible / "lib" / "python3.11" / "site-packages").mkdir(parents=True)
            (cible / "bin").mkdir(parents=True)
            (cible / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
            return (1, "venv refusé") if self.echec == "venv" else (0, "")
        if "-c" in c and "inspect.signature" in c[c.index("-c") + 1]:                 # la sonde de l'interface du paquet
            return 0, json.dumps([{"module": m, "version": "1", "doc": "un paquet de banc", "membres": [{"nom": "Optimiseur", "type": "type", "sig": "(x)", "doc": "optimise"}]} for m in c[c.index("-c") + 2:]])
        if "pip" in c and "install" in c and c[-1] == "uv":                            # uv s'installe dans son propre environnement
            (Path(c[0]).parent / "uv").write_text("#!/bin/sh\n", encoding="utf-8")
            return 0, ""
        if "pip" in c and "freeze" in c:
            return 0, "monpaquet==%s\nlibutile==2.1\n-e /x\n" % self.version
        if "pip" in c and "download" in c:
            d = Path(c[c.index("-d") + 1])
            (d / "x-1.whl").write_bytes(("contenu de " + c[-1]).encode("utf-8"))
            return (1, "introuvable") if self.echec == "telecharger" else (0, "")
        if "pip" in c:
            return (1, "hash mismatch") if self.echec == "pip" else (0, "")
        if "-c" in c and "site.getsitepackages" in c[c.index("-c") + 1]:
            return 0, str(Path(c[0]).parent.parent / "lib" / "python3.11" / "site-packages")
        if "-c" in c and "importlib" in c[c.index("-c") + 1]:
            return (1, "ModuleNotFoundError") if self.echec == "import" else (0, "")
        if "--version" in c:
            return 0, "Python 3.13.5"
        return 0, ""


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.catalogue = self.base / "moteurs-catalogue.json"
        self.registre = MO.Registre(self.base / "moteurs.json")
        self.faux = Faux(self.base)

    def inst(self, **kw):
        (self.base / "moteurs").mkdir(exist_ok=True)
        return I.Installateur(self.base / "moteurs", self.catalogue, CLE, registre=self.registre, executer=self.faux, **kw)

    def rep(self, **kw):
        base = {"id": "banc", "nom": "Banc", "paquet": "monpaquet", "adaptateur": "json", "cible": "code", "cout": "sobre", "qui": "x", "desc": "d", "force": []}
        base.update(kw)
        return base


class Repertoire(unittest.TestCase):
    def test_chaque_chercheur_a_une_fiche_complete_et_s_installe_sans_piste(self):
        ids = [e["id"] for e in R.REPERTOIRE]
        self.assertEqual(len(ids), len(set(ids)))
        for e in R.REPERTOIRE:
            for cle in ("id", "nom", "qui", "cible", "cout", "desc", "force"):
                self.assertIn(cle, e, e["id"])
            self.assertIn(e["cible"], ("code", "texte"))
            self.assertTrue(e.get("paquet") or e.get("github") or e.get("methode"), "%s : ni paquet, ni dépôt, ni méthode" % e["id"])

    def test_un_adaptateur_ecrit_existe_vraiment_dans_le_depot_sinon_il_sera_genere(self):
        for e in R.REPERTOIRE:
            if e["adaptateur"]:
                self.assertTrue((RACINE / "orfan" / "adaptateurs" / (e["adaptateur"] + ".py")).exists(), e["id"])
            elif e.get("paquet"):
                self.assertTrue(e.get("importer"), "%s : un adaptateur généré a besoin de savoir quoi sonder" % e["id"])

    def test_les_quatre_adaptateurs_ecrits_a_la_main_sont_le_repertoire_de_depart(self):
        self.assertEqual(sorted(e["id"] for e in R.REPERTOIRE if e["adaptateur"]), ["codeevolve", "gepa", "openevolve", "shinka"])


class Epinglage(Banc):
    def test_epingler_fige_chaque_paquet_par_son_empreinte(self):
        e = E.epingler(self.rep(), executer=self.faux)
        self.assertEqual(e["version"], "1.0.0")
        self.assertEqual([p["requis"] for p in e["paquets"]], ["monpaquet==1.0.0", "libutile==2.1"])
        self.assertTrue(all(h.startswith("sha256:") and len(h) == 71 for p in e["paquets"] for h in p["empreintes"]))
        I.verifier_entree(e)                                                       # l'entrée épinglée est une entrée valide du catalogue

    def test_le_gel_des_versions_est_lu_en_entier_meme_si_l_executeur_coupe_la_sortie(self):
        class Coupe(Faux):
            def __call__(s, commande, delai_s, cwd):
                code, sortie = super().__call__(commande, delai_s, cwd)
                return code, sortie[-40:]                                          # l'exécuteur de l'installateur ne garde que la fin
        gros = Faux(self.base)
        gros_freeze = "".join("paquet%d==1.%d\n" % (i, i) for i in range(60))
        gros.__call__ = None
        class Gros(Faux):
            def __call__(s, commande, delai_s, cwd):
                if "pip" in commande and "freeze" in commande:
                    return 0, "monpaquet==1.0.0\n" + gros_freeze
                return super().__call__(commande, delai_s, cwd)
        e = E.epingler(self.rep(), executer=Coupe(self.base), executer_plein=Gros(self.base))
        self.assertEqual(len(e["paquets"]), 61)                                    # 61 paquets figés, pas les 2 ou 3 qui tiennent dans 40 caractères

    def test_le_code_extrait_n_est_pas_coupe_par_des_barrieres_qu_il_contient_lui_meme(self):
        reponse = "```python\nimport re\nBLOCS = re.compile(r\"```(?:python)?\\s*\\n(.*?)```\")\nIMPORTER = ['x']\n```\nvoilà"
        code = G.extraire_code(reponse)
        self.assertIn("IMPORTER", code)                                              # le premier « ``` » interne n'est pas la fin du bloc
        self.assertEqual(G.extraire_code("Idée\n```python\ndef f(x):\n    return 1\n```"), "def f(x):\n    return 1\n")

    def test_un_adaptateur_a_generer_est_marque_dans_l_entree(self):
        e = E.epingler(self.rep(adaptateur=None, importer=["monpaquet"]), executer=self.faux)
        self.assertTrue(e["adaptateur_genere"])
        self.assertEqual(e["adaptateur"], "CN_adaptateur_banc")
        self.assertEqual(e["importer"], ["monpaquet"])

    def test_une_methode_sans_paquet_n_epingle_rien(self):
        e = E.epingler(self.rep(paquet=None, adaptateur=None, methode="évoluer des textes"), executer=self.faux)
        self.assertEqual((e["paquets"], e["version"]), ([], "méthode"))
        self.assertEqual(self.faux.journal, [])                                    # aucun environnement, aucun pip

    def test_un_depot_github_est_epingle_par_son_commit_exact(self):
        sha = "a" * 40
        e = E.epingler(self.rep(paquet=None, github="o/d", paquet_nom="monpaquet"), executer=self.faux, commit=sha, empreinte_url=lambda u: "sha256:" + "b" * 64)
        self.assertEqual(e["paquets"][0]["requis"], "monpaquet @ https://codeload.github.com/o/d/tar.gz/" + sha)
        self.assertEqual(e["paquets"][0]["empreintes"], ["sha256:" + "b" * 64])
        self.assertEqual(e["version"], sha[:12])
        I.verifier_entree(e)

    def test_un_depot_invalide_est_refuse_avant_tout_reseau(self):
        with self.assertRaises(I.InstallationRefusee):
            E.resoudre_commit("pas un depot")
        self.assertEqual(E.resoudre_commit("o/d", "a" * 40), "a" * 40)

    def test_un_pip_qui_echoue_est_une_raison_dite(self):
        for echec in ("venv", "pip", "telecharger"):
            with self.assertRaises(I.InstallationRefusee, msg=echec):
                E.epingler(self.rep(), executer=Faux(self.base, echec="pip" if echec == "pip" else None) if echec == "pip" else Faux(self.base, echec=echec))

    def test_inscrire_scelle_et_refuse_un_catalogue_modifie(self):
        e = E.epingler(self.rep(), executer=self.faux)
        E.inscrire(self.catalogue, e, CLE)
        self.assertEqual(I.lire_catalogue(self.catalogue, CLE)["moteurs"][0]["id"], "banc")
        cat = json.loads(self.catalogue.read_text(encoding="utf-8"))
        cat["moteurs"][0]["paquets"][0]["requis"] = "pirate==9"
        self.catalogue.write_text(json.dumps(cat), encoding="utf-8")
        with self.assertRaises(I.InstallationRefusee):
            E.inscrire(self.catalogue, e, CLE)                                     # jamais réécrit : on ne fait pas passer un catalogue modifié pour sain

    def test_inscrire_remplace_l_entree_du_meme_chercheur_et_garde_les_autres(self):
        E.inscrire(self.catalogue, {"id": "autre", "nom": "A", "adaptateur": "json", "paquets": []}, CLE)
        E.inscrire(self.catalogue, E.epingler(self.rep(), executer=self.faux), CLE)
        E.inscrire(self.catalogue, E.epingler(self.rep(), executer=Faux(self.base, version_pip="2.0.0")), CLE)
        cat = I.lire_catalogue(self.catalogue, CLE)["moteurs"]
        self.assertEqual(sorted((m["id"], m.get("version", "")) for m in cat), [("autre", ""), ("banc", "2.0.0")])


class PythonEtInstallation(Banc):
    def entree(self, **kw):
        e = E.epingler(self.rep(), executer=self.faux)
        e.update(kw)
        E.inscrire(self.catalogue, e, CLE)
        return e

    def test_l_avancement_est_rendu_a_chaque_etape(self):
        self.entree()
        vus = []
        r = self.inst().installer("banc", progres=lambda etapes: vus.append([x["nom"] for x in etapes]))
        self.assertTrue(r["ok"], r)
        self.assertEqual(vus[0], ["catalogue scellé"])
        self.assertEqual(vus[-1][-1], "registre des moteurs")
        self.assertTrue(all(len(b) == len(a) + 1 for a, b in zip(vus, vus[1:])))   # une étape de plus à chaque fois

    def test_un_progres_qui_plante_ne_coupe_pas_l_installation(self):
        self.entree()
        def mauvais(etapes):
            raise RuntimeError("écran fermé")
        self.assertTrue(self.inst().installer("banc", progres=mauvais)["ok"])

    def test_python_est_pose_quand_le_serveur_ne_l_a_pas(self):
        self.entree(interpreteur=str(self.base / "pythons" / "py313" / "bin" / "python"), python="3.13.5")
        r = self.inst().installer("banc")
        self.assertTrue(r["ok"], r)
        self.assertIn("Python posé", [e["nom"] for e in r["etapes"]])
        self.assertTrue(any(c[:1] == ["env"] and "UV_PYTHON_INSTALL_DIR=%s" % (self.base / "pythons") in c for c in self.faux.journal))

    def test_un_python_qui_ne_se_pose_pas_est_une_raison_dite_et_l_environnement_est_supprime(self):
        self.faux.echec = None
        self.entree(interpreteur=str(self.base / "absent" / "python"), python="3.13.5")
        faux = Faux(self.base, echec="python")
        r = I.Installateur(self.base / "moteurs", self.catalogue, CLE, registre=self.registre, executer=faux).installer("banc")
        self.assertFalse(r["ok"])
        self.assertIn("Python 3.13.5", " ".join(e["detail"] for e in r["etapes"]))
        self.assertFalse((self.base / "moteurs" / "banc").exists())

    def test_une_version_de_python_invalide_est_refusee(self):
        with self.assertRaises(I.InstallationRefusee):
            self.inst().poser_python("3.13; rm -rf /")


class AdaptateurGenere(Banc):
    def entree_generee(self):
        e = E.epingler(self.rep(adaptateur=None, importer=["monpaquet"]), executer=self.faux)
        E.inscrire(self.catalogue, e, CLE)
        return e

    def generateur(self, code=CODE_BON, essai_a_blanc=""):
        etapes_vues = []

        def modele(prompt, role="executant"):
            etapes_vues.append(prompt)
            return "Voici :\n```python\n%s```\n" % code

        def gen(entree, python, racine, etape):
            G.essai_a_blanc = lambda *a, **k: essai_a_blanc
            return G.generer(entree, self.rep(adaptateur=None, importer=["monpaquet"]), python, racine, etape, modele, self.faux, RACINE / "orfan" / "adaptateurs")
        gen.prompts = etapes_vues
        return gen

    def test_le_repli_ecrit_l_adaptateur_dans_l_environnement_du_chercheur_et_l_epingle(self):
        self.entree_generee()
        gen = self.generateur()
        r = self.inst(generateur=gen).installer("banc")
        self.assertTrue(r["ok"], r)
        fichiers = list((self.base / "moteurs" / "banc" / "venv").glob("lib/python*/site-packages/CN_adaptateur_banc.py"))
        self.assertEqual(len(fichiers), 1)
        self.assertEqual(fichiers[0].read_text(encoding="utf-8"), G.assembler(CODE_BON))
        fiche = [m for m in self.registre.liste() if m["id"] == "banc"][0]
        self.assertFalse(fiche["adaptateur_genere"]["relu"])                       # à relire : rien n'est approuvé d'office
        self.assertEqual(len(fiche["adaptateur_genere"]["empreinte"]), 64)
        self.assertIn("adaptateur généré", [e["nom"] for e in r["etapes"]])

    def test_le_prompt_donne_le_contrat_de_l_operateur_et_l_interface_du_paquet(self):
        self.entree_generee()
        gen = self.generateur()
        self.inst(generateur=gen).installer("banc")
        p = gen.prompts[0]
        for morceau in ("produire(contexte, modele)", "NE DÉFINIS PAS proposer", "N'attrape PAS les exceptions", "IMPORTER", "AUCUN réseau", "INTERFACE RÉELLE"):
            self.assertIn(morceau, p)

    def test_sans_generateur_un_adaptateur_a_generer_est_refuse_et_rien_ne_reste(self):
        self.entree_generee()
        r = self.inst().installer("banc")
        self.assertFalse(r["ok"])
        self.assertIn("générateur", " ".join(e["detail"] for e in r["etapes"]))
        self.assertFalse((self.base / "moteurs" / "banc").exists())
        self.assertEqual([m for m in self.registre.liste() if m["id"] == "banc"], [])

    def test_un_code_dangereux_est_rejete_sans_jamais_etre_execute(self):
        for mauvais in ('import subprocess\nIMPORTER = []\n\ndef proposer(contexte, modele):\n    return []\n',
                        'IMPORTER = []\n\ndef proposer(contexte, modele):\n    import os\n    os.system("id")\n    return []\n',
                        'IMPORTER = []\n\ndef proposer(contexte, modele)\n    return []\n',
                        'def proposer(contexte, modele):\n    return []\n',
                        'IMPORTER = []\n\ndef autre(contexte):\n    return []\n'):
            self.assertTrue(G.verifier_code(mauvais), mauvais)
        self.assertEqual(G.verifier_code(G.assembler(CODE_BON)), "")

    def test_un_adaptateur_qui_echoue_a_l_essai_a_blanc_est_rejete_puis_corrige(self):
        self.entree_generee()
        appels = []

        def modele(prompt, role="executant"):
            appels.append(prompt)
            return "```python\n%s```" % CODE_BON
        etats = iter(["l'essai à blanc a échoué : boum", ""])
        G.essai_a_blanc = lambda *a, **k: next(etats)
        gen = lambda e, p, r_, et: G.generer(e, self.rep(adaptateur=None, importer=["monpaquet"]), p, r_, et, modele, self.faux, RACINE / "orfan" / "adaptateurs")
        r = self.inst(generateur=gen).installer("banc")
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(appels), 2)
        self.assertIn("TA VERSION PRÉCÉDENTE A ÉCHOUÉ", appels[1])                # l'erreur est redonnée au modèle
        self.assertIn("def produire", appels[1])                                  # avec son code précédent, pour qu'il corrige CETTE erreur-là

    def test_un_modele_muet_est_une_raison_dite(self):
        self.entree_generee()

        def muet(prompt, role="executant"):
            raise RuntimeError("le rôle n'est lié à aucun modèle")
        gen = lambda e, p, r_, et: G.generer(e, self.rep(adaptateur=None, importer=["monpaquet"]), p, r_, et, muet, self.faux, RACINE / "orfan" / "adaptateurs")
        r = self.inst(generateur=gen).installer("banc")
        self.assertFalse(r["ok"])
        self.assertIn("modèle", " ".join(e["detail"] for e in r["etapes"]))
        self.assertFalse((self.base / "moteurs" / "banc").exists())

    def test_l_approbation_exige_la_bonne_empreinte(self):
        self.entree_generee()
        self.inst(generateur=self.generateur()).installer("banc")
        emp = [m for m in self.registre.liste() if m["id"] == "banc"][0]["adaptateur_genere"]["empreinte"]
        with self.assertRaises(ValueError):
            self.registre.approuver_adaptateur("banc", "0" * 64)
        self.registre.approuver_adaptateur("banc", emp)
        self.assertTrue([m for m in self.registre.liste() if m["id"] == "banc"][0]["adaptateur_genere"]["relu"])
        with self.assertRaises(ValueError):
            self.registre.approuver_adaptateur("orfan", emp)                       # un chercheur sans adaptateur généré n'a rien à approuver


class MiseAJour(Banc):
    def installer_v1(self, **kw):
        E.inscrire(self.catalogue, E.epingler(self.rep(), executer=self.faux), CLE)
        self.assertTrue(self.inst(**kw).installer("banc")["ok"])

    def passer_en_v2(self):
        E.inscrire(self.catalogue, E.epingler(self.rep(), executer=Faux(self.base, version_pip="2.0.0")), CLE)

    def test_la_nouvelle_version_s_installe_a_cote_puis_bascule(self):
        self.installer_v1()
        (self.base / "moteurs" / "banc" / "marque-ancienne").write_text("v1", encoding="utf-8")
        self.passer_en_v2()
        r = self.inst().mettre_a_jour("banc")
        self.assertTrue(r["ok"], r)
        self.assertFalse((self.base / "moteurs" / "banc" / "marque-ancienne").exists())           # c'est bien le nouvel environnement qui est en place
        self.assertFalse((self.base / "moteurs" / "banc.nouveau").exists())
        self.assertFalse((self.base / "moteurs" / "banc.ancien").exists())
        self.assertEqual([m for m in self.registre.liste() if m["id"] == "banc"][0]["version"], "2.0.0")
        self.assertEqual(r["etapes"][-1]["nom"], "bascule")

    def test_un_echec_laisse_l_ancienne_version_intacte(self):
        self.installer_v1()
        (self.base / "moteurs" / "banc" / "marque-ancienne").write_text("v1", encoding="utf-8")
        self.passer_en_v2()
        faux = Faux(self.base, echec="pip")
        r = I.Installateur(self.base / "moteurs", self.catalogue, CLE, registre=self.registre, executer=faux).mettre_a_jour("banc")
        self.assertFalse(r["ok"])
        self.assertTrue((self.base / "moteurs" / "banc" / "marque-ancienne").exists())            # l'ancienne n'a pas bougé
        self.assertFalse((self.base / "moteurs" / "banc.nouveau").exists())
        self.assertEqual([m for m in self.registre.liste() if m["id"] == "banc"][0]["version"], "1.0.0")
        self.assertEqual(r["etapes"][-1]["nom"], "ancienne version")

    def test_une_bascule_qui_ne_charge_pas_remet_l_ancienne(self):
        self.installer_v1()
        (self.base / "moteurs" / "banc" / "marque-ancienne").write_text("v1", encoding="utf-8")
        self.passer_en_v2()
        compte = {"n": 0}

        class DeuxiemeImportEchoue(Faux):
            def __call__(s, commande, delai_s, cwd):
                if "-c" in commande and "importlib" in commande[commande.index("-c") + 1]:
                    compte["n"] += 1
                    if compte["n"] == 2:                                                   # le banc d'import fait APRÈS la bascule
                        return 1, "ModuleNotFoundError"
                return super().__call__(commande, delai_s, cwd)
        r = I.Installateur(self.base / "moteurs", self.catalogue, CLE, registre=self.registre, executer=DeuxiemeImportEchoue(self.base)).mettre_a_jour("banc")
        self.assertFalse(r["ok"])
        self.assertTrue((self.base / "moteurs" / "banc" / "marque-ancienne").exists())
        self.assertEqual(r["etapes"][-1]["nom"], "retour arrière")

    def test_rien_a_mettre_a_jour_si_le_chercheur_n_est_pas_installe(self):
        E.inscrire(self.catalogue, E.epingler(self.rep(), executer=self.faux), CLE)
        self.assertFalse(self.inst().mettre_a_jour("banc")["ok"])

    def test_desinstaller_efface_aussi_les_restes_d_une_mise_a_jour_interrompue(self):
        self.installer_v1()
        for reste in ("banc.nouveau", "banc.ancien"):
            (self.base / "moteurs" / reste).mkdir()
        self.inst().desinstaller("banc")
        self.assertEqual(sorted(os.listdir(self.base / "moteurs")), [])


class Taches(unittest.TestCase):
    def attendre(self, t, num):
        for _ in range(200):
            if t.lire(num)["fini"]:
                return t.lire(num)
            time.sleep(0.02)
        self.fail("la tâche ne finit pas")

    def test_une_tache_rend_son_avancement_puis_sa_fin(self):
        t = T.Taches()
        porte = threading.Event()

        def travail(progres):
            progres([{"nom": "a", "ok": True, "detail": ""}], "étape b…")
            porte.wait(2)
            return {"ok": True, "etapes": [{"nom": "a", "ok": True, "detail": ""}, {"nom": "b", "ok": True, "detail": ""}]}
        num = t.lancer("installer", "banc", travail, ["a", "b"])
        for _ in range(100):
            if t.lire(num)["en_cours"]:
                break
            time.sleep(0.02)
        vu = t.lire(num)
        self.assertEqual((vu["fini"], vu["en_cours"], len(vu["etapes"]), vu["plan"]), (False, "étape b…", 1, ["a", "b"]))
        porte.set()
        fin = self.attendre(t, num)
        self.assertEqual((fin["ok"], len(fin["etapes"]), fin["en_cours"]), (True, 2, ""))

    def test_une_tache_qui_plante_se_dit_sans_tuer_le_serveur(self):
        t = T.Taches()
        num = t.lancer("installer", "banc", lambda progres: 1 / 0)
        fin = self.attendre(t, num)
        self.assertFalse(fin["ok"])
        self.assertIn("ZeroDivisionError", fin["erreur"])

    def test_une_seule_tache_a_la_fois_par_chercheur(self):
        t = T.Taches()
        porte = threading.Event()
        num = t.lancer("installer", "banc", lambda progres: porte.wait(2) and {"ok": True})
        self.assertTrue(t.actif("banc"))
        self.assertFalse(t.actif("autre"))
        porte.set()
        self.attendre(t, num)
        self.assertFalse(t.actif("banc"))

    def test_une_tache_inconnue_est_une_erreur_dite(self):
        with self.assertRaises(ValueError):
            T.Taches().lire("perdue")

    def test_seules_les_dernieres_taches_sont_gardees(self):
        t = T.Taches()
        nums = [t.lancer("x", "c%d" % i, lambda progres: {"ok": True}) for i in range(T.Taches.CONSERVEES + 5)]
        time.sleep(0.3)
        with self.assertRaises(ValueError):
            t.lire(nums[0])
        self.assertTrue(t.lire(nums[-1]))


class OperateurEtGabarit(unittest.TestCase):
    REP = {"importer": ["monpaquet"]}

    def test_un_bon_operateur_passe(self):
        self.assertEqual(G.verifier_operateur(CODE_BON, self.REP), "")

    def test_definir_proposer_est_refuse(self):
        code = CODE_BON + "\n\ndef proposer(contexte, modele):\n    return []\n"
        self.assertIn("ne définis pas proposer", G.verifier_operateur(code, self.REP))

    def test_une_panne_avalee_est_refusee(self):
        for avale in ("    except Exception:\n        return []\n", "    except Exception:\n        pass\n", "    except Exception:\n        return None\n"):
            code = 'IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    import monpaquet\n    try:\n        return [modele("x", "executant")]\n' + avale
            self.assertIn("n'avale pas", G.verifier_operateur(code, self.REP), avale)

    def test_un_except_qui_fait_autre_chose_passe(self):
        code = 'IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    import monpaquet\n    monpaquet.Optimiseur(1)\n    for _ in range(2):\n        try:\n            return [modele("x", "executant")]\n        except ValueError:\n            continue\n    return []\n'
        self.assertEqual(G.verifier_operateur(code, self.REP), "")

    def test_ne_pas_utiliser_le_paquet_est_refuse_sauf_methode_reimplementee(self):
        code = 'IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    return [modele("x", "executant")]\n'
        self.assertIn("n'utilise pas le paquet", G.verifier_operateur(code, self.REP))
        self.assertEqual(G.verifier_operateur(code, {"importer": ["monpaquet"], "reimplemente": "une méthode"}), "")
        self.assertEqual(G.verifier_operateur(code.replace('["monpaquet"]', "[]"), {"importer": [], "methode": "une méthode"}), "")

    def test_importer_le_paquet_sans_rien_en_appeler_est_refuse(self):
        decore = 'IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    import monpaquet\n\n    class Lm(monpaquet.Base):\n        pass\n    return [modele("x", "executant")]\n'
        self.assertIn("n'en APPELLE rien", G.verifier_operateur(decore, self.REP))
        vrai = decore.replace("    return [modele", "    monpaquet.Optimiseur(1)\n    return [modele")
        self.assertEqual(G.verifier_operateur(vrai, self.REP), "")
        depuis = 'IMPORTER = ["monpaquet"]\n\n\ndef produire(contexte, modele):\n    from monpaquet import Optimiseur as O\n    O()\n    return []\n'
        self.assertEqual(G.verifier_operateur(depuis, self.REP), "")

    def test_sans_produire_c_est_refuse(self):
        self.assertIn("manque la fonction produire", G.verifier_operateur('IMPORTER = []\n', {}))

    def _gabarit(self):
        sys.path.insert(0, str(RACINE / "orfan" / "adaptateurs"))
        try:
            import CN_gabarit_adaptateur as GAB
        finally:
            sys.path.pop(0)
        return GAB

    CTX = {"source_reference": "def f(x):\n    return sorted(x)[0]\n", "fonction": "f", "entrees": [[3, 1, 2], [9, 4]], "budget": 2, "tombes": []}

    def test_le_gabarit_garde_une_variante_equivalente_et_ecarte_le_reste(self):
        GAB = self._gabarit()
        bonnes = ["```python\ndef f(x):\n    return min(x)\n```", "def f(x):\n    return sorted(x)[0]\n", "def f(x):\n    return max(x)\n", "pas du code", {"texte": "def f(x):\n    return min(x) + 0\n", "hypothese": "ajout neutre"}]
        r = GAB.executer(dict(self.CTX), None, lambda c, m: bonnes, "essai")
        self.assertEqual([v["texte"].strip().splitlines()[1].strip() for v in r], ["return min(x)", "return min(x) + 0"])          # la référence, la fausse (max) et le texte sans code sont écartés
        self.assertEqual(r[1]["hypothese"], "ajout neutre")

    def test_le_gabarit_ecarte_une_variante_deja_refusee_et_respecte_le_budget(self):
        GAB = self._gabarit()
        ctx = dict(self.CTX, tombes=["def f(x):\n    return min(x)\n"], budget=1)
        r = GAB.executer(ctx, None, lambda c, m: ["def f(x):\n    return min(x)\n", "def f(x):\n    return min(x) + 0\n", "def f(x):\n    return min(x) + 0 + 0\n"], "essai")
        self.assertEqual(len(r), 1)
        self.assertIn("+ 0", r[0]["texte"])

    def test_le_gabarit_ne_cache_jamais_une_panne_de_l_operateur(self):
        GAB = self._gabarit()

        def casse(c, m):
            raise KeyError("config")
        with self.assertRaises(GAB.OperateurEnEchec) as cm:
            GAB.executer(dict(self.CTX), None, casse, "mon_chercheur")
        self.assertIn("mon_chercheur", str(cm.exception))
        self.assertIn("KeyError", str(cm.exception))                                 # le modèle recevra ceci pour corriger son opérateur

    def test_a_l_essai_a_blanc_un_rien_s_explique_et_en_production_il_reste_une_liste_vide(self):
        GAB = self._gabarit()
        faux = lambda c, m: ["def f(x):\n    return max(x)\n", "pas de code du tout"]
        self.assertEqual(GAB.executer(dict(self.CTX), None, faux, "x"), [])                       # une vraie recherche sans résultat n'est pas une panne
        with self.assertRaises(GAB.OperateurEnEchec) as cm:
            GAB.executer(dict(self.CTX, controle=True), None, faux, "x")
        self.assertIn("pas équivalente", str(cm.exception))                                    # le modèle saura POURQUOI
        self.assertIn("sans code", str(cm.exception))

    def test_le_gabarit_refuse_un_resultat_qui_n_est_pas_une_liste(self):
        GAB = self._gabarit()
        with self.assertRaises(GAB.OperateurEnEchec):
            GAB.executer(dict(self.CTX), None, lambda c, m: 42, "x")


class EssaiABlancExigeUneVariante(unittest.TestCase):
    def _mot(self, rendu):
        class Faux:
            class MoteurProcessus:
                def __init__(s, *a, **k):
                    pass

                def proposer(s, contexte):
                    if isinstance(rendu, Exception):
                        raise rendu
                    return rendu
        return Faux

    def test_une_liste_vide_est_un_echec_dit(self):
        raison = ESSAI_REEL({}, "python", "CN_adaptateur_x", "auto", self._mot([]))
        self.assertIn("aucune variante", raison)

    def test_une_variante_rendue_passe(self):
        self.assertEqual(ESSAI_REEL({}, "python", "CN_adaptateur_x", "auto", self._mot([{"texte": "def f(x):\n    return min(x)\n", "hypothese": "h"}])), "")

    def test_un_resultat_qui_n_est_pas_une_liste_est_refuse(self):
        self.assertIn("pas rendu une liste", ESSAI_REEL({}, "python", "CN_adaptateur_x", "auto", self._mot({"a": 1})))

    def test_une_exception_est_dite(self):
        self.assertIn("a échoué", ESSAI_REEL({}, "python", "CN_adaptateur_x", "auto", self._mot(RuntimeError("boum"))))


class SondeEtAvertissements(unittest.TestCase):
    def test_la_ligne_de_json_se_lit_meme_entouree_d_avertissements_du_paquet(self):
        sortie = "[transformers] avant\n" + json.dumps([{"module": "x", "version": "1", "membres": []}]) + "\n[transformers] PyTorch was not found.\n"
        r = G.sonder("python", ["x"], lambda cmd, delai, cwd: (0, sortie))
        self.assertEqual(r[0]["module"], "x")
        self.assertNotIn("erreur", r[0])

    def test_une_sonde_sans_json_dit_ce_qu_elle_a_vu(self):
        r = G.sonder("python", ["x"], lambda cmd, delai, cwd: (1, "Traceback : boum"))
        self.assertIn("boum", r[0]["erreur"])


def _elf(types_flags):
    """Un ELF 64 bits minimal : l'en-tête et une table d'en-têtes de programme (type, drapeaux)."""
    import struct
    n = len(types_flags)
    entete = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\0" * 8 + struct.pack("<HHIQQQIHHHHHH", 3, 62, 1, 0, 64, 0, 0, 64, 56, n, 0, 0, 0)
    table = b"".join(struct.pack("<IIQQQQQQ", t, fl, 0, 0, 0, 0, 0, 8) for t, fl in types_flags)
    return entete + table


class PileNonExecutable(unittest.TestCase):
    def _etat(self, types_flags):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "bin"
            p.write_bytes(_elf(types_flags))
            r = I.pile_non_executable(p)
            return r, p.read_bytes()

    def test_un_binaire_sans_marqueur_en_recoit_un_a_la_place_de_la_note(self):
        import struct
        r, octets = self._etat([(1, 5), (4, 4), (1, 6)])
        self.assertEqual(r, "corrige")
        t, fl = struct.unpack_from("<II", octets, 64 + 56)
        self.assertEqual((t, fl), (0x6474E551, 6))                                    # lecture et écriture, jamais d'exécution

    def test_un_marqueur_executable_perd_son_drapeau_d_execution(self):
        import struct
        r, octets = self._etat([(1, 5), (0x6474E551, 7)])
        self.assertEqual(r, "corrige")
        self.assertEqual(struct.unpack_from("<I", octets, 64 + 56 + 4)[0], 6)

    def test_un_binaire_deja_en_ordre_n_est_pas_touche(self):
        r, octets = self._etat([(1, 5), (0x6474E551, 6)])
        self.assertEqual(r, "deja")
        self.assertEqual(octets, _elf([(1, 5), (0x6474E551, 6)]))

    def test_sans_note_a_remplacer_il_le_dit_et_ne_touche_a_rien(self):
        r, octets = self._etat([(1, 5), (1, 6)])
        self.assertEqual(r, "impossible")
        self.assertEqual(octets, _elf([(1, 5), (1, 6)]))

    def test_un_fichier_qui_n_est_pas_un_elf_est_ignore(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "x.so"
            p.write_text("pas un binaire", encoding="utf-8")
            self.assertEqual(I.pile_non_executable(p), "pas_elf")


class MoteurRenomme(unittest.TestCase):
    def test_l_ancienne_fiche_passe_sous_le_nouveau_nom_sans_perdre_son_historique(self):
        from noyau import CN_moteurs as M
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "moteurs.json"
            p.write_text(json.dumps({"moteurs": {"evolutif": {"nom": "Évolutif", "genre": "natif", "etat": "actif", "jetons": 100, "essais": 2},
                                                  "sedal": {"nom": "Sedal", "genre": "natif", "etat": "actif", "jetons": 5, "essais": 1}},
                                     "cascade": [{"id": "evolutif", "on": True}], "courses": [{"etage": "evolutif", "gain": 3, "libelle": "Évolutif · populations et mutations"}],
                                     "journal": [{"texte": "ordre orfan, evolutif"}]}), encoding="utf-8")
            r = M.Registre(p)
            d = r._lire()
            self.assertNotIn("evolutif", d["moteurs"])
            self.assertEqual(d["moteurs"]["sedal"]["jetons"], 105)                  # les compteurs s'additionnent
            self.assertEqual(d["moteurs"]["sedal"]["nom"], "Sedal")
            self.assertEqual(d["cascade"][0]["id"], "sedal")
            self.assertEqual(d["courses"][0]["etage"], "sedal")
            self.assertEqual(d["courses"][0]["libelle"], "Sedal · populations et mutations")      # le libellé gardé avec un résultat suit
            self.assertIn("evolutif", d["journal"][0]["texte"])                     # l'histoire dite n'est pas réécrite
            self.assertNotIn("evolutif", json.loads(p.read_text(encoding="utf-8"))["moteurs"])   # et la migration est écrite
            self.assertEqual(r._lire()["moteurs"]["sedal"]["jetons"], 105)          # idempotent


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs de l'installation depuis l'écran.
# LIEN : noyau/CN_epinglage.py, noyau/CN_installateur.py, noyau/CN_adaptateur_gen.py, noyau/CN_taches.py, noyau/CN_repertoire.py.
