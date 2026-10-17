"""Bancs du générateur d'en-têtes : il ajoute des commentaires, jamais du code ; il est idempotent ; ce qu'il écrit est conforme à l'outil de bornes."""
import ast
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import CN_bornes as B  # noqa: E402
import CN_entete as E  # noqa: E402

SOURCE = '"""Un module d\'essai : il additionne.\n\nDeuxième paragraphe.\n"""\nfrom __future__ import annotations\n\n\ndef ajouter(a, b):\n    return a + b\n'


class Generateur(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._r = (B.RACINE, E.RACINE)
        B.RACINE = E.RACINE = self.tmp
        self.addCleanup(lambda: setattr(B, "RACINE", self._r[0]))
        self.addCleanup(lambda: setattr(E, "RACINE", self._r[1]))
        (self.tmp / "modules" / "essai").mkdir(parents=True)
        (self.tmp / "modules" / "essai" / "CN_manifeste.toml").write_text('nom = "Essai"\nversion = "2.3.4"\ndescription = "Un essai"\n', encoding="utf-8")

    def poser(self, nom, texte):
        p = self.tmp / "modules" / "essai" / nom
        p.write_text(texte, encoding="utf-8", newline="\n")
        return "modules/essai/" + nom

    def test_le_code_ne_change_pas(self):
        c = self.poser("CN_a.py", SOURCE)
        neuf = E.transformer(c, SOURCE)
        self.assertEqual(ast.dump(ast.parse(SOURCE)), ast.dump(ast.parse(neuf)))
        self.assertIn("def ajouter(a, b):", neuf)

    def test_l_en_tete_reprend_la_docstring_et_la_version_du_module(self):
        c = self.poser("CN_a.py", SOURCE)
        neuf = E.transformer(c, SOURCE)
        self.assertIn("# TITRE      : Un module d'essai", neuf)
        self.assertIn("# VERSION CN : 2.3.4", neuf)
        self.assertIn("# MODULE     : essai", neuf)

    def test_le_resultat_est_conforme_a_l_outil_de_bornes(self):
        c = self.poser("CN_a.py", SOURCE)
        (self.tmp / c).write_text(E.transformer(c, SOURCE), encoding="utf-8", newline="\n")
        B.sceller(c)
        self.assertEqual(B.analyser(c)["erreurs"], [])
        self.assertFalse([i for i in B.analyser(c)["infos"] if "empreinte" in i])

    def test_idempotent(self):
        c = self.poser("CN_a.py", SOURCE)
        un = E.transformer(c, SOURCE)
        self.assertIsNone(E.transformer(c, un))

    def test_un_shebang_reste_en_premiere_ligne(self):
        src = "#!/usr/bin/env bash\n# CN_install.sh : installe le noyau.\nset -e\necho ok\n"
        c = self.poser("CN_i.sh", src)
        neuf = E.transformer(c, src)
        self.assertEqual(neuf.splitlines()[0], "#!/usr/bin/env bash")
        self.assertIn("TITRE      : CN_install.sh", neuf)
        self.assertIn("echo ok", neuf)

    def test_un_manifeste_toml_reste_un_toml_valide(self):
        import tomllib
        src = 'nom = "Essai"\nversion = "2.3.4"\ndescription = "Un essai"\n'
        c = self.poser("CN_manifeste.toml", src)
        neuf = E.transformer(c, src)
        self.assertEqual(tomllib.loads(neuf), tomllib.loads(src))
        self.assertIn("Manifeste du module Essai", neuf)

    def test_une_migration_sql_n_est_jamais_modifiee_et_recoit_un_compagnon(self):
        sql = "CREATE TABLE t(a INTEGER);\n"
        c = self.poser("001_init.sql", sql)
        cp = E.compagnon(c)
        self.assertIn("ZONE       : CN", cp)
        self.assertIn("empreinte du contenu", cp)
        (self.tmp / (c + ".borne")).write_text(cp, encoding="utf-8", newline="\n")
        self.assertEqual((self.tmp / c).read_text(encoding="utf-8"), sql)                  # le contenu n'a pas bougé : la somme de contrôle du migrateur reste vraie
        self.assertEqual([e for e in B.analyser(c)["erreurs"] if "compagnon" in e], [])


if __name__ == "__main__":
    unittest.main()
