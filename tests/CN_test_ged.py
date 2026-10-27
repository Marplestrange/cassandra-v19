# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la GED
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #292f75
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la GED : cloisonnement des racines, dépôt, listage, fiche, corbeille réversible, règles de classement.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=292f75 ▼▼▼
"""Bancs de la GED : cloisonnement des racines, dépôt, listage, fiche, corbeille réversible, règles de classement."""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

spec = importlib.util.spec_from_file_location("ged_module_test", RACINE / "modules" / "ged" / "CN_module.py")
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

# le module sans noyau : ses points d'évolution sont branchés sur leurs références, comme le ferait brancher()
import tempfile                              # noqa: E402
from noyau import CN_manifeste as _M, CN_points as _P          # noqa: E402
_dossier = RACINE / "modules" / "ged"
_svc = _P.ServicePoints(Path(tempfile.mkdtemp()) / "ec")
_svc.declarer(_M.charger(_dossier / "CN_manifeste.toml"), _dossier)
POINT = lambda nom, entree: _svc.appeler("ged", nom, entree)

BEA, LEO = "bea@x.fr", "leo@x.fr"


class Pures(unittest.TestCase):
    def test_le_nom_de_dossier_est_nettoye_plus_empreinte(self):
        n = gm._nt_dossier_compte("Bea@X.fr")
        self.assertNotIn("@", n)
        self.assertEqual(len(n.split("-")[-1]), 8)          # l'empreinte
        self.assertNotEqual(gm._nt_dossier_compte("Bea@X.fr"), gm._nt_dossier_compte("Bea@X.org"))

    def test_le_depot_refuse_ce_qui_s_interprete(self):
        self.assertEqual(gm._depot_refuse("note.pdf"), "")
        self.assertEqual(gm._depot_refuse("photo.jpg"), "")
        self.assertIn("actif", gm._depot_refuse("page.html"))
        self.assertIn("actif", gm._depot_refuse("logo.svg"))
        self.assertIn("refusé", gm._depot_refuse("virus.exe"))
        self.assertIn("sans extension", gm._depot_refuse("README"))

    def test_l_affichage_en_ligne_est_une_liste_blanche(self):
        self.assertEqual(gm._inline_type("photo.png"), "image/png")
        self.assertEqual(gm._inline_type("notes.md"), "text/plain")
        self.assertEqual(gm._inline_type("archive.zip"), "")       # reste en téléchargement

    def test_le_type_media(self):
        self.assertEqual(gm._media_kind("a.PDF", POINT), "pdf")
        self.assertEqual(gm._media_kind("a.png", POINT), "image")
        self.assertEqual(gm._media_kind("a.mp3", POINT), "audio")
        self.assertEqual(gm._media_kind("a.mp4", POINT), "video")


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("ged", "comptes", "droits"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "ged"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(BEA, True)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        self.n.executeur.executer("comptes.creer", "humain", {"compte": BEA, "mot_de_passe": "Essai-Local-1234"}, compte="operateur")
        self.ctx = self.n.executeur.contextes["ged"]
        self.db = self.ctx.stockage
        # la base des documents : un dossier propre dans le monde de test
        self.docs = Path(self.tmp.name) / "d" / "documents"
        self.ctx.reglage = lambda nom, compte=None: str(self.docs) if nom == "docs_base" else ""

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("ged." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, compte=BEA, **args):
        r = self.ex("ged." + cap, compte=compte, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    # ── racines et cloisonnement ─────────────────────────────────────────────
    def test_un_compte_voit_sa_source_et_le_commun_pas_celle_d_un_autre(self):
        self.s("dossier_creer", compte=BEA)
        # la source de BEA n'est pas visible de LEO, le commun l'est
        srcs_bea = self.s("sources", compte=BEA)["groupes"][0]["l"]
        srcs_leo = self.s("sources", compte=LEO)["groupes"][0]["l"]
        miennes = [x for x in srcs_bea if x.get("mien")]
        self.assertEqual(len(miennes), 1)
        miennes_leo = [x for x in srcs_leo if x.get("mien")]
        self.assertEqual(len(miennes_leo), 0)

    def test_un_dossier_de_compte_est_cree_et_declare(self):
        r = self.s("dossier_creer", compte=BEA)
        self.assertTrue(os.path.isdir(r["dossier"]))
        self.assertTrue(r["declaree"])
        # idempotent : le second appel ne re-déclare pas
        r2 = self.s("dossier_creer", compte=BEA)
        self.assertEqual(r2["declaree"], False)

    # ── le grand répertoire de la société ────────────────────────────────────
    def test_le_dossier_d_un_utilisateur_vit_dans_le_repertoire_de_sa_societe(self):
        r = self.s("dossier_creer", compte=BEA)
        self.assertEqual(Path(r["dossier"]).parent, self.docs / "1")                  # BEA est de la société principale
        self.n.identite.societe_creer("Autre société", "autre")
        self.n.identite.creer(LEO, "Essai-Local-1234", societe="autre")
        r2 = self.s("dossier_creer", compte=LEO)
        self.assertEqual(Path(r2["dossier"]).parent, self.docs / "autre")             # LEO, d'une autre : dans le grand répertoire de la sienne

    def test_les_anciens_dossiers_entrent_dans_la_societe_principale_une_seule_fois(self):
        (self.docs / "ancien-compte").mkdir(parents=True)
        (self.docs / "ancien-compte" / "a.txt").write_text("avant les sociétés", encoding="utf-8")
        (self.docs / "_public").mkdir()
        self.s("sources", compte=BEA)                                                  # le premier accès range l'existant
        self.assertTrue((self.docs / "1" / "ancien-compte" / "a.txt").is_file())
        self.assertTrue((self.docs / "1" / "_public").is_dir())
        self.assertFalse((self.docs / "ancien-compte").exists())
        self.s("sources", compte=BEA)                                                  # et ne recommence pas
        self.assertTrue((self.docs / "1" / "ancien-compte" / "a.txt").is_file())

    # ── dépôt, listage, fiche ────────────────────────────────────────────────
    def test_deposer_lister_et_fiche(self):
        r = self.s("dossier_creer", compte=BEA)
        src = "local:" + r["dossier"]
        d = self.s("deposer", source=src, chemin="", nom="note.txt", contenu_b64="SGVsbG8gR0VE")   # "Hello GED"
        self.assertTrue(os.path.isfile(d["cible"]))
        items = self.s("lister", source=src, chemin="")["items"]
        self.assertEqual([x["nom"] for x in items], ["note.txt"])
        f = self.s("fiche", fid=d["id"])["fichier"]
        self.assertEqual((f["nom"], f["taille"], f["kind"]), ("note.txt", 9, "texte"))

    def test_un_depot_refuse_un_document_actif(self):
        r = self.s("dossier_creer", compte=BEA)
        self.assertIn("actif", self.echec("deposer", source="local:" + r["dossier"], nom="x.html", contenu_b64="PHNjcmlwdD4="))

    # ── corbeille réversible ─────────────────────────────────────────────────
    def test_la_corbeille_deplace_puis_se_defait(self):
        r = self.s("dossier_creer", compte=BEA)
        src = "local:" + r["dossier"]
        d = self.s("deposer", source=src, chemin="", nom="a.txt", contenu_b64="YQ==")
        res = self.ex("ged.corbeille", fid=d["id"], confirme=True)
        self.assertEqual(res["statut"], "faite", res)
        self.assertFalse(os.path.isfile(d["cible"]))
        self.assertIn("corbeille", res["resultat"]["vers"])
        # le retour arrière remet le fichier et sa ligne
        self.n.catalogue.get("ged.corbeille").defaire(self.ctx, res["resultat"])
        self.assertTrue(os.path.isfile(d["cible"]))
        self.assertEqual(self.s("fiche", fid=d["id"])["fichier"]["nom"], "a.txt")

    # ── règles de classement ─────────────────────────────────────────────────
    def test_les_regles_par_defaut_et_le_test_a_blanc(self):
        regles = self.s("regles")["regles"]
        self.assertGreaterEqual(len(regles), 2)
        pieces = [{"filename": "facture.pdf", "subject": "votre facture", "size": 1000, "kind": "pdf"}]
        t = self.s("regles_test", pieces=pieces)
        self.assertEqual(t["total"], 1)
        self.assertGreaterEqual(len(t["par_regle"]), 1)

    def test_une_regle_s_enregistre_et_se_defait(self):
        res = self.ex("ged.regle_save", libelle="Contrats", si_nom="contrat", dest="/Contrats", ordre=5, actif=1)
        self.assertEqual(res["statut"], "faite", res)
        rid = res["resultat"]["id"]
        self.assertIn(rid, [r["id"] for r in self.s("regles")["regles"]])
        self.n.catalogue.get("ged.regle_save").defaire(self.ctx, res["resultat"])
        self.assertNotIn(rid, [r["id"] for r in self.s("regles")["regles"]])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Pures, Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
