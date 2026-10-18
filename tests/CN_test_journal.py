# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du journal
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c4b522
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du journal : le fil des agents (trois rôles, signature jamais devinée), le lecteur de sources, l'enveloppe commune, les veilles réversibles, et la lecture en lecture seule de la base d'un autre module.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c4b522 ▼▼▼
"""Bancs du journal : le fil des agents (trois rôles, signature jamais devinée), le lecteur de sources,
l'enveloppe commune, les veilles réversibles, et la lecture en lecture seule de la base d'un autre module."""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

spec = importlib.util.spec_from_file_location("journal_module_test", RACINE / "modules" / "journal" / "CN_module.py")
jm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jm)

# le module sans noyau : ses points d'évolution sont branchés sur leurs références, comme le ferait brancher()
import tempfile                              # noqa: E402
from noyau import CN_manifeste as _M, CN_points as _P          # noqa: E402
_dossier = RACINE / "modules" / "journal"
_svc = _P.ServicePoints(Path(tempfile.mkdtemp()) / "ec")
_svc.declarer(_M.charger(_dossier / "CN_manifeste.toml"), _dossier)
jm._point = lambda nom, entree: _svc.appeler("journal", nom, entree)

BEA = "bea@x.fr"


class Pures(unittest.TestCase):
    def test_l_horodatage_se_normalise(self):
        self.assertEqual(jm._ts_norm("1760000000.0"), "2025-10-09 08:53:20")     # epoch -> ISO
        self.assertEqual(jm._ts_norm("2025-10-08 21:53:12"), "2025-10-08 21:53:12")
        self.assertEqual(jm._ts_norm("2025-10-08T21:53"), "2025-10-08 21:53:00")
        self.assertEqual(jm._ts_norm("08/Oct/2025:21:53:12"), "2025-10-08 21:53:12")   # nginx
        self.assertEqual(jm._ts_norm(""), "")

    def test_la_signature_efface_ce_qui_change(self):
        # deux erreurs qui ne diffèrent que par un port ont la même empreinte
        self.assertEqual(jm._signature("connexion refusée sur le port 54321"),
                         jm._signature("connexion refusée sur le port 54322"))
        self.assertNotEqual(jm._signature("connexion refusée"), jm._signature("disque plein"))

    def test_le_niveau_se_normalise(self):
        self.assertEqual(jm._niveau("ERROR"), "erreur")
        self.assertEqual(jm._niveau("warn"), "avertissement")
        self.assertEqual(jm._niveau(""), "info")
        self.assertEqual(jm._niveau("success"), "info")


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("journal", "salon", "agents", "modeles", "memoire", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "modeles", "memoire", "agents", "comptes", "journal", "salon"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(BEA, True)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        self.ctx = self.n.executeur.contextes["journal"]
        self.db = self.ctx.stockage
        self.n.executeur.executer("comptes.creer", "humain", {"compte": BEA, "mot_de_passe": "Essai-Local-1234"}, compte="operateur")

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("journal." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    # ── le journal des agents ───────────────────────────────────────────────
    def test_une_consultation_garde_la_question_et_la_reponse(self):
        r = self.s("agents_ecrire", qui="itare", modele="qwen", etiquette="dessin du filtre",
                   consigne="que penses-tu de ce filtre ?", dossier="le contexte", reponse="il laisse passer les chiffres")
        self.assertEqual(self.s("agents_lire", n=1)["echanges"][0]["reponse"], "il laisse passer les chiffres")

    def test_la_reponse_est_rognee_sauf_entier(self):
        self.s("agents_ecrire", qui="cassandra", etiquette="x", reponse="R" * 6000)
        rognee = self.s("agents_lire", n=1)["echanges"][0]
        entiere = self.s("agents_lire", n=1, entier=True)["echanges"][0]
        self.assertEqual(len(rognee["reponse"]), 4000)
        self.assertEqual(len(entiere["reponse"]), 6000)

    def test_le_fil_se_lit_dans_l_ordre_ou_il_s_est_dit(self):
        self.s("agents_ecrire", qui="claude", etiquette="a", reponse="premier")
        self.s("agents_ecrire", qui="itare", etiquette="b", reponse="second")
        fil = self.s("fil")["fil"]
        self.assertEqual([e["reponse"] for e in fil], ["premier", "second"])      # du plus ancien au plus récent
        self.assertEqual([e["qui"] for e in fil], ["claude", "itare"])

    def test_une_signature_ne_se_devine_pas(self):
        # un humain parle sous « claude » (le mainteneur), jamais sous un nom passé au hasard
        r = self.s("agents_dire", etiquette="note", message="je reprends la main")
        self.assertEqual(self.s("agents_lire", n=1)["echanges"][0]["qui"], "claude")
        # un « qui » inconnu n'est pas accepté : on retombe sur l'acteur, puis sur « inconnu » (l'agent écrit une fois le palier posé)
        self.n.catalogue.regler_palier("journal.agents_dire", "auto")
        r2 = self.ex("journal.agents_dire", acteur="agent", message="qui suis-je ?", qui="truc")
        self.assertEqual(r2["statut"], "faite", r2)
        self.assertEqual(self.s("agents_lire", n=1)["echanges"][0]["qui"], "inconnu")

    def test_le_prompt_est_court_et_tient_sur_des_lignes(self):
        self.s("agents_ecrire", qui="itare", etiquette="migration", reponse="la table a été renommée")
        p = self.s("prompt", n=3)["texte"]
        self.assertIn("[itare] migration", p)
        self.assertIn("renommée", p)

    # ── le lecteur ──────────────────────────────────────────────────────────
    def test_sources_rend_la_table_du_module_disponible(self):
        srcs = {s["key"]: s for s in self.s("sources")["sources"]}
        self.assertIn("agents", srcs)
        self.assertTrue(srcs["agents"]["available"])
        self.assertGreaterEqual(srcs["agents"]["count"], 0)
        # un fichier système est déclaré au catalogue, disponible ou non selon la machine
        self.assertIn("auth", srcs)
        self.assertEqual(srcs["auth"]["kind"], "file")

    def test_lire_cherche_et_flux(self):
        self.s("agents_ecrire", qui="itare", etiquette="sauvegarde", reponse="la copie hors site a réussi")
        self.s("agents_ecrire", qui="cassandra", etiquette="disque", reponse="le disque est à 91 %")
        r = self.s("lire", source="agents", limit=5)
        self.assertEqual(r["kind"], "table")
        self.assertEqual(len(r["rows"]), 2)
        ch = self.s("chercher", question="disque")
        self.assertEqual([x["key"] for x in ch["results"] if x["total"]], ["agents"])
        fl = self.s("flux", sources=["agents"], limit=20)
        self.assertEqual(len(fl["entrees"]), 2)
        self.assertEqual(fl["entrees"][0]["source"], "agents")
        self.assertEqual(set(fl["entrees"][0].keys()), {"ts", "niveau", "source", "acteur", "action", "sujet", "detail", "label", "icon", "rang", "brut"})

    def test_un_journal_inconnu_est_refuse(self):
        self.assertIn("journal inconnu", self.ex("journal.lire", source="nimporte")["erreur"])

    # ── les veilles ─────────────────────────────────────────────────────────
    def test_poser_modifier_retirer_une_veille_et_revenir(self):
        r = self.s("veille_poser", source="agents", pattern="disque", label="disque plein")
        self.assertEqual(self.s("veilles")["veilles"][0]["pattern"], "disque")
        # modifier
        self.s("veille_poser", wid=r["id"], pattern="mémoire", label="mémoire pleine")
        self.assertEqual(self.s("veilles")["veilles"][0]["pattern"], "mémoire")
        # un motif invalide est refusé
        self.assertIn("motif invalide", self.ex("journal.veille_poser", pattern="(pas fermé")["erreur"])
        # retirer, puis revenir (défaire)
        res = self.ex("journal.veille_retirer", wid=r["id"])
        self.assertEqual(self.s("veilles")["veilles"], [])
        self.n.catalogue.get("journal.veille_retirer").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("veilles")["veilles"][0]["id"], r["id"])

    # ── la lecture d'un AUTRE module, en lecture seule ──────────────────────
    def test_lire_la_table_du_salon_sans_y_ecrire(self):
        # le salon écrit dans sa table « journal » ; le module journal la lit sans y toucher
        sal = self.n.executeur.contextes["salon"]
        saldb = sal.stockage
        saldb.ecrire("INSERT INTO journal(ts, acteur, geste, fil, titre, messages, details) VALUES (?,?,?,?,?,?,?)",
                     (time.time(), "humain:" + BEA, "suppression", 1, "À jeter", 2, "trace avant le geste"))
        r = self.s("lire", source="salon", limit=5)
        self.assertEqual(r["kind"], "table")
        self.assertEqual(len(r["rows"]), 1)
        self.assertEqual(r["rows"][0]["geste"], "suppression")
        # l'enveloppe du salon porte l'acteur et le titre
        self.assertEqual(r["env"][0]["acteur"], "humain:" + BEA)
        self.assertEqual(r["env"][0]["action"], "À jeter")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Pures, Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
