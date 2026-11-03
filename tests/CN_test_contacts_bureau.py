# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des portraits et des documents d'une fiche
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #4cfc3a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des portraits (contacts.photos) et des documents d'une fiche (ged.documents_de).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4cfc3a ▼▼▼
"""Bancs des portraits en lot et des documents d'une fiche : chacun ne lit que son carnet et ses documents, un modèle ne reçoit pas de portrait,
le lien d'un document vit du côté du document."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA, CAM = "bea@x.fr", "cam@x.fr"
PNG = "data:image/png;base64,iVBORw0KGgo="


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes", "contacts", "ged"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "contacts", "ged"):
            self.assertTrue(self.n.activer(m)["ok"], m)

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(cap, acteur, args, compte=compte)

    def ok(self, cap, **args):
        r = self.ex(cap, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_les_portraits_sortent_en_lot_et_restent_au_carnet_de_la_personne(self):
        a = self.ok("contacts.creer", display_name="Léa", emails=["lea@exemple.fr"], photo=PNG)["id"]
        b = self.ok("contacts.creer", display_name="Max", emails=["max@exemple.fr"])["id"]
        r = self.ok("contacts.photos", ids=[a, b])
        self.assertEqual(list(r["photos"]), [str(a)])                                # une fiche sans portrait n'y figure pas
        self.assertEqual(self.ok("contacts.photos", compte=CAM, ids=[a])["photos"], {})
        self.assertEqual(self.ex("contacts.photos", acteur="itare", ids=[a])["statut"], "refuse")        # un modèle ne reçoit pas de portrait

    def test_les_documents_d_une_fiche_se_lisent_chez_la_ged(self):
        fid = self.ok("contacts.creer", display_name="Léa", emails=["lea@exemple.fr"])["id"]
        base = self.n.executeur.contextes["ged"].stockage
        f = base.ecrire("INSERT INTO ged_fichiers(source, chemin, nom, taille, kind, compte) VALUES('local:/x','devis.pdf','devis.pdf',10,'pdf',?)", (BEA,))
        base.ecrire("INSERT INTO ged_liens(fichier_id, kind, ref, label) VALUES(?, 'contact', ?, 'Devis')", (f, str(fid)))
        autre = base.ecrire("INSERT INTO ged_fichiers(source, chemin, nom, taille, kind, compte) VALUES('local:/y','secret.pdf','secret.pdf',10,'pdf',?)", (CAM,))
        base.ecrire("INSERT INTO ged_liens(fichier_id, kind, ref, label) VALUES(?, 'contact', ?, 'Autre')", (autre, str(fid)))
        r = self.ok("ged.documents_de", kind="contact", ref=str(fid))
        self.assertEqual([d["nom"] for d in r["documents"]], ["devis.pdf"])         # le document d'un autre compte, même lié au même numéro, ne sort pas
        self.assertEqual(self.ok("ged.documents_de", compte=CAM, kind="contact", ref=str(fid))["documents"][0]["nom"], "secret.pdf")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
