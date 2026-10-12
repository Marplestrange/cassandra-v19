"""Bancs de la racine : ce que le noyau demande au courtier (root), et la politique du courtier. Le contrôle est pur ; l'exécution réelle n'a lieu que sous POSIX."""
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import main as moteur                      # noqa: E402
from noyau import manifeste as mf          # noqa: E402
from noyau import racine as rc             # noqa: E402

POSIX = hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and hasattr(os, "getuid")


def charger_courtier():
    spec = importlib.util.spec_from_file_location("courtier_racine", RACINE / "exploitation" / "courtier.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Validation(unittest.TestCase):
    def test_une_demande_bien_formee(self):
        args, stdin, d = rc.valider("planifie", "ecrire_cron", ["-u", "root"], "texte", 20)
        self.assertEqual((args, stdin, d), (["-u", "root"], "texte", 20))

    def test_les_refus(self):
        for module, commande in (("Plan", "x"), ("planifie", "../etc"), ("planifie", "a b"), ("p", "ecrire"), ("planifie", "")):
            with self.assertRaises(ValueError, msg=(module, commande)):
                rc.valider(module, commande, [], None, 10)
        for args in ("pas une liste", ["x"] * 41, ["a\x00b"], ["x" * 5000]):
            with self.assertRaises(ValueError):
                rc.valider("planifie", "lire", args, None, 10)
        with self.assertRaises(ValueError):
            rc.valider("planifie", "lire", [], "x" * 70000, 10)
        for delai in (0, 301, -5):
            with self.assertRaises(ValueError):
                rc.valider("planifie", "lire", [], None, delai)

    def test_pas_de_courtier_pas_d_attente(self):
        r = rc.Racine("").demander("planifie", "lire", [], None, 5)
        self.assertFalse(r["ok"])
        self.assertIn("pas de courtier", r["erreur"])


class PolitiqueDuCourtier(unittest.TestCase):
    def setUp(self):
        self.c = charger_courtier()

    def demande(self, **kw):
        return dict({"action": "racine", "id": "1760000000-" + "a" * 12, "module": "planifie", "commande": "lire", "args": ["-l"], "stdin": None, "delai": 30}, **kw)

    def test_une_demande_en_regle(self):
        self.assertEqual(self.c.valider_racine(self.demande()), (True, "ok"))

    def test_le_courtier_ne_croit_rien(self):
        for kw in (dict(id="../../etc/passwd"), dict(module="Pl an"), dict(commande="../x"), dict(args="rm -rf /"), dict(args=["a\x00"]), dict(stdin=5), dict(delai=0), dict(delai=999), dict(delai=True), dict(action="autre")):
            self.assertFalse(self.c.valider_racine(self.demande(**kw))[0], kw)
        self.assertFalse(self.c.valider_racine("x")[0])


@unittest.skipUnless(POSIX, "fichiers et propriétaires POSIX")
class ExecutionDuCourtier(unittest.TestCase):
    def setUp(self):
        self.c = charger_courtier()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.libexec, self.spool = base / "libexec", base / "courtier"
        (self.spool / "resultats").mkdir(parents=True)
        (self.libexec / "planifie").mkdir(parents=True)
        for d in (self.libexec, self.libexec / "planifie"):
            os.chmod(d, 0o755)
        self.uid = os.getuid()                                        # les bancs ne sont pas root : « root » est celui qui lance le banc
        self.journal = []

    def programme(self, nom, corps, mode=0o755):
        p = self.libexec / "planifie" / nom
        p.write_text("#!/bin/sh\n" + corps + "\n", encoding="utf-8")
        os.chmod(p, mode)

    def lancer(self, **kw):
        d = {"action": "racine", "id": "1760000000-" + "b" * 12, "module": "planifie", "commande": "lire", "args": [], "stdin": None, "delai": 10}
        d.update(kw)
        ok = self.c.executer_racine(d, str(self.spool), str(self.libexec), self.c.subprocess.run, self.journal.append, uid_racine=self.uid)
        res = json.loads((self.spool / "resultats" / (d["id"] + ".json")).read_text())
        return ok, res

    def test_la_commande_nommee_s_execute_sans_shell_avec_ses_arguments(self):
        self.programme("lire", 'echo "args: $1 | $2"; cat; exit 0')
        ok, res = self.lancer(args=["a b", "$(touch pwn)"], stdin="entrée")
        self.assertTrue(ok)
        self.assertIn("args: a b | $(touch pwn)", res["sortie"])           # les arguments sont des chaînes, rien ne s'interprète
        self.assertIn("entrée", res["sortie"])
        self.assertFalse(Path("pwn").exists())

    def test_un_echec_est_un_resultat(self):
        self.programme("lire", 'echo oups >&2; exit 3')
        ok, res = self.lancer()
        self.assertFalse(ok)
        self.assertEqual((res["ok"], res["code"], res["erreur"].strip()), (False, 3, "oups"))

    def test_le_delai_coupe_la_commande(self):
        self.programme("lire", "sleep 5")
        ok, res = self.lancer(delai=1)
        self.assertEqual((ok, res["code"]), (False, 124))

    def test_une_commande_absente_ou_non_sure_n_est_jamais_lancee(self):
        ok, res = self.lancer(commande="absente")
        self.assertFalse(ok)
        self.assertIn("absente ou non sûre", res["erreur"])
        self.programme("lire", "exit 0", mode=0o777)                    # modifiable par tous
        self.assertIn("modifiable", self.lancer()[1]["erreur"])
        self.programme("lire", "exit 0", mode=0o644)                    # pas exécutable
        self.assertIn("exécutable", self.lancer()[1]["erreur"])
        self.programme("lire", "exit 0")
        os.chmod(self.libexec / "planifie", 0o777)                      # le dossier du module modifiable par tous : le noyau pourrait y glisser son programme
        self.assertIn("modifiable", self.lancer()[1]["erreur"])
        os.chmod(self.libexec / "planifie", 0o755)
        autre = self.libexec / "planifie" / "autre"
        autre.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(autre, 0o755)
        (self.libexec / "planifie" / "lien").symlink_to(autre)
        self.assertIn("lien symbolique", self.lancer(commande="lien")[1]["erreur"])

    def test_le_noyau_ne_peut_pas_faire_ecrire_root_ailleurs(self):
        self.programme("lire", "exit 0")
        cible = Path(self.tmp.name) / "cible"
        cible.write_text("intact")
        (self.spool / "resultats" / ("1760000000-" + "b" * 12 + ".tmp")).symlink_to(cible)
        ok = self.c.executer_racine({"action": "racine", "id": "1760000000-" + "b" * 12, "module": "planifie", "commande": "lire", "args": [], "stdin": None, "delai": 5},
                                    str(self.spool), str(self.libexec), self.c.subprocess.run, self.journal.append, uid_racine=self.uid)
        self.assertFalse(ok)                                            # O_EXCL | O_NOFOLLOW : le lien posé d'avance fait échouer l'écriture
        self.assertEqual(cible.read_text(), "intact")

    def test_traiter_aiguille_les_demandes_racine(self):
        self.programme("lire", "echo bonjour")
        cfg = Path(self.tmp.name) / "config"
        cfg.mkdir()
        d = {"action": "racine", "id": "1760000000-" + "c" * 12, "module": "planifie", "commande": "lire", "args": [], "stdin": None, "delai": 10}
        (self.spool / "racine-x.json").write_text(json.dumps(d))
        n = self.c.traiter(str(self.spool), str(cfg), self.uid, journal=self.journal.append, libexec=str(self.libexec), uid_racine=self.uid)
        self.assertEqual(n, 1)
        self.assertFalse((self.spool / "racine-x.json").exists())        # la demande est supprimée après examen
        self.assertIn("bonjour", json.loads((self.spool / "resultats" / (d["id"] + ".json")).read_text())["sortie"])


@unittest.skipUnless(POSIX, "fichiers et propriétaires POSIX")
class DeBoutEnBout(unittest.TestCase):
    """Le client dépose, un courtier simulé (le vrai code, dans un fil) répond, le client relit."""

    def test_aller_retour(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        spool, libexec, cfg = base / "courtier", base / "libexec", base / "config"
        (libexec / "planifie").mkdir(parents=True)
        cfg.mkdir()
        os.chmod(libexec, 0o755)
        os.chmod(libexec / "planifie", 0o755)
        p = libexec / "planifie" / "lire"
        p.write_text('#!/bin/sh\necho "reçu: $1"\n')
        os.chmod(p, 0o755)
        c = charger_courtier()
        arret = threading.Event()

        def courtier():
            while not arret.is_set():
                if spool.exists() and any(f.name.endswith(".json") and f.name.startswith("racine-") for f in spool.iterdir()):
                    c.traiter(str(spool), str(cfg), os.getuid(), libexec=str(libexec), uid_racine=os.getuid(), journal=lambda m: None)
                time.sleep(0.05)
        t = threading.Thread(target=courtier, daemon=True)
        t.start()
        self.addCleanup(t.join, 2)
        self.addCleanup(arret.set)
        r = rc.Racine(str(spool))
        r.pause = 0.05
        res = r.demander("planifie", "lire", ["salut"], None, 10)
        self.assertEqual((res["ok"], res["sortie"].strip()), (True, "reçu: salut"))
        self.assertEqual(r.demander("planifie", "absente", [], None, 10)["ok"], False)


class ContratDuManifeste(unittest.TestCase):
    TOML = """
[module]
id = "plan"
nom = "Plan"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai"
famille = "reseau"

[[racine]]
id = "lire_cron"
libelle = "Lire les tâches planifiées de tous les utilisateurs"
lecture = true

[[racine]]
id = "ecrire_cron"
libelle = "Écrire la table des tâches d'un utilisateur"

[permissions]
racine = true
"""

    def brut(self):
        import tomllib
        return tomllib.loads(self.TOML)

    def test_un_module_declare_ses_commandes_root(self):
        self.assertEqual(mf.valider(self.brut()), [])
        m = mf.construire(self.brut())
        self.assertEqual([(c.id, c.lecture) for c in m.racine], [("lire_cron", True), ("ecrire_cron", False)])
        self.assertTrue(m.permissions.racine)

    def test_on_ne_demande_pas_du_root_sans_le_dire(self):
        b = self.brut()
        b["permissions"]["racine"] = False
        self.assertTrue(any("permissions] racine" in e for e in mf.valider(b)))
        b = self.brut()
        b["racine"] = []
        self.assertTrue(any("aucune commande" in e for e in mf.valider(b)))
        b = self.brut()
        b["racine"][1]["id"] = "lire_cron"
        self.assertTrue(any("deux fois" in e for e in mf.valider(b)))
        b = self.brut()
        b["racine"][0]["id"] = "../x"
        self.assertTrue(any("invalide" in e for e in mf.valider(b)))

    def test_un_module_ne_peut_demander_que_ce_qu_il_a_declare(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        d = base / "modules" / "plan"
        d.mkdir(parents=True)
        (d / "manifeste.toml").write_text(self.TOML, encoding="utf-8")
        n = moteur.Noyau(base / "d", base / "modules", {}, gerer_modules=True)
        n.brancher()
        n.activer("plan")
        ctx = n.executeur.contextes["plan"]
        ctx._intro["racine"] = type("Faux", (), {"demander": lambda self, m, c, a, s, d: {"ok": True, "code": 0, "sortie": "%s/%s %s" % (m, c, list(a)), "erreur": ""}})()
        self.assertEqual(ctx.racine("lire_cron", ["-l"])["sortie"], "plan/lire_cron ['-l']")
        with self.assertRaises(PermissionError):
            ctx.racine("formater_disque")


if __name__ == "__main__":
    unittest.main()
