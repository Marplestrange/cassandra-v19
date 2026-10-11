"""Bancs du noyau. Stdlib seule : python -m unittest discover -s tests -v"""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau import manifeste as mf          # noqa: E402
from noyau.bus import TOUT                 # noqa: E402

LABO_TOML = """
[module]
id = "labo"
nom = "Labo"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : des jouets qui cassent et qu'on répare."

[[objets]]
type = "jouet"
libelle = "Un jouet"

[evenements]
emet = ["jouet.casse"]

[[capacites]]
id = "lire_jouet"
libelle = "Lire l'état d'un jouet"
risque = "lecture"

[[capacites]]
id = "reparer_jouet"
libelle = "Réparer un jouet"
risque = "faible"
perimetre = ["les jouets du labo"]
preuve = "relire l'état du jouet"
retour = "remettre l'état d'avant"
paliers = ["raconter", "auto", "maitre"]
qui = ["cassandra", "humain"]

[[detecteurs]]
id = "jouet_casse"
libelle = "Un jouet est cassé"
frequence_s = 10
capacite = "reparer_jouet"
"""

LABO_PY = '''
def brancher(ctx):
    jouets = ctx.config["jouets"]
    drapeaux = ctx.config["drapeaux"]

    def detecter(ctx):
        sortie = []
        for nom, etat in jouets.items():
            ctx.poser("jouet", nom, nom, etat)
            if etat == "casse":
                sortie.append({"objet": ("jouet", nom), "titre": nom + " est cassé", "args": {"nom": nom}})
        if drapeaux.get("panne"):
            raise RuntimeError("sonde HS")
        return sortie

    def reparer(ctx, nom):
        avant = jouets[nom]
        jouets[nom] = "casse" if drapeaux.get("rater") else "ok"
        return {"nom": nom, "avant": avant}

    ctx.implementer("reparer_jouet", reparer,
                    prouver=lambda ctx, res: jouets[res["nom"]] == "ok",
                    defaire=lambda ctx, res: jouets.__setitem__(res["nom"], res["avant"]),
                    simuler=lambda ctx, nom: "réparerait " + nom)
    ctx.implementer("lire_jouet", lambda ctx, nom: jouets.get(nom))
    ctx.detecteur("jouet_casse", detecter)
'''


def ecrire_module(racine, mid, toml, py=None):
    d = Path(racine) / mid
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifeste.toml").write_text(toml, encoding="utf-8")
    if py is not None:
        (d / "module.py").write_text(textwrap.dedent(py), encoding="utf-8")


class Monde:
    """Un noyau jetable avec le module « labo » branché."""

    def __init__(self, jouets=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.modules = Path(self.tmp.name) / "modules"
        ecrire_module(self.modules, "labo", LABO_TOML, LABO_PY)
        self.jouets = dict(jouets or {"ours": "casse"})
        self.drapeaux = {}
        self.noyau = moteur.Noyau(Path(self.tmp.name) / "d", self.modules, {"labo": {"jouets": self.jouets, "drapeaux": self.drapeaux}})
        self.noyau.brancher()

    def evenements(self, type_):
        return [e for e in self.noyau.bus.recents(portee=TOUT, limite=500) if e["type"] == type_]

    def fermer(self):
        self.tmp.cleanup()


class Manifestes(unittest.TestCase):
    def test_modules_reels_valides_et_ordonnes(self):
        ms = mf.decouvrir(RACINE / "modules")
        self.assertEqual(mf.verifier_ensemble(ms), [])
        ordre = mf.ordre_installation(ms)
        self.assertLess(ordre.index("dns"), ordre.index("certificats"))

    def _brut(self, **cap):
        import tomllib
        b = tomllib.loads(LABO_TOML)
        b["capacites"][1].update(cap)
        return b

    def test_une_capacite_qui_ecrit_porte_sa_surete(self):
        for champ in ("preuve", "retour"):
            b = self._brut(); del b["capacites"][1][champ]
            self.assertTrue(any(champ in e for e in mf.valider(b)), champ)
        b = self._brut(); del b["capacites"][1]["perimetre"]
        self.assertTrue(any("périmètre" in e for e in mf.valider(b)))

    def test_risque_eleve_jamais_maitre(self):
        b = self._brut(risque="eleve")
        self.assertTrue(any("maitre" in e for e in mf.valider(b)))

    def test_un_module_nomme_ses_evenements_d_apres_ses_objets(self):
        import tomllib
        b = tomllib.loads(LABO_TOML); b["evenements"]["emet"] = ["site.tombe"]
        self.assertTrue(any("site.tombe" in e for e in mf.valider(b)))

    def test_version_noyau_exigee(self):
        import tomllib
        b = tomllib.loads(LABO_TOML); b["module"]["noyau_min"] = "9.0.0"
        self.assertTrue(any("noyau" in e for e in mf.valider(b)))

    def test_script_d_installation_exige_verification_et_retrait(self):
        import tomllib
        b = tomllib.loads(LABO_TOML); b["installation"] = {"script": "i.sh"}
        e = mf.valider(b)
        self.assertTrue(any("vérification" in x for x in e) and any("retrait" in x for x in e))

    def test_cycle_et_dependance_absente(self):
        import tomllib
        def m(mid, req):
            b = tomllib.loads(LABO_TOML); b["module"]["id"] = mid; b["module"]["requiert"] = req
            b["objets"][0]["type"] = mid + "_o"; b["evenements"]["emet"] = [mid + "_o.x"]; b["detecteurs"] = []
            return mf.construire(b)
        with self.assertRaises(mf.ManifesteInvalide) as c:
            mf.ordre_installation([m("aa", ["bb"]), m("bb", ["aa"])])
        self.assertIn("cycle", str(c.exception))
        self.assertTrue(mf.verifier_ensemble([m("aa", ["zz"])]))

    def test_evenement_ecoute_sans_emetteur(self):
        import tomllib
        b = tomllib.loads(LABO_TOML); b["evenements"]["ecoute"] = ["fantome.x"]
        self.assertTrue(mf.verifier_ensemble([mf.construire(b)]))


class Cycle(unittest.TestCase):
    def setUp(self):
        self.m = Monde()
        self.n = self.m.noyau
        self.addCleanup(self.m.fermer)

    def test_au_palier_raconter_cassandra_dit_ce_qu_elle_ferait(self):
        r = self.n.tick(1000)
        self.assertEqual(r["ouverts"], 1)
        self.assertEqual(r["actions"][0]["statut"], "racontee")
        self.assertEqual(self.m.jouets["ours"], "casse")
        self.assertEqual(len(self.m.evenements("capacite.racontee")), 1)

    def test_un_constat_n_agit_qu_une_fois(self):
        self.n.tick(1000); r = self.n.tick(1020)
        self.assertEqual(r["ouverts"], 0)
        self.assertEqual(len(self.m.evenements("constat.ouvert")), 1)

    def test_au_palier_auto_elle_repare_seule_et_prouve(self):
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        r = self.n.tick(1000)
        self.assertEqual(r["actions"][0]["statut"], "faite")
        self.assertEqual(self.m.jouets["ours"], "ok")
        self.assertEqual(len(self.m.evenements("capacite.prouvee")), 1)
        r2 = self.n.tick(1020)
        self.assertEqual(r2["resolus"], 1)
        self.assertEqual(self.n.etat()["constats_ouverts"], 0)

    def test_la_lignee_relie_perception_decision_action_preuve(self):
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.n.tick(1000)
        racine = self.m.evenements("constat.ouvert")[0]["id"]
        types = [e["type"] for e in self.n.bus.lignee(racine, portee=TOUT)["suites"]]
        self.assertEqual(types, ["capacite.demandee", "capacite.faite", "capacite.prouvee"])
        prouvee = self.m.evenements("capacite.prouvee")[0]["id"]
        self.assertEqual(self.n.bus.lignee(prouvee, portee=TOUT)["causes"][0]["id"], racine)

    def test_preuve_manquante_retour_arriere_seul_puis_retrogradation(self):
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.m.drapeaux["rater"] = True
        r = self.n.tick(1000)
        self.assertEqual(r["actions"][0]["statut"], "annulee")
        self.assertEqual(self.m.jouets["ours"], "casse")          # l'état d'avant est revenu
        self.assertEqual(len(self.m.evenements("capacite.annulee")), 1)
        self.n.base.ecrire("UPDATE constats SET etat='resolu'")   # le constat revient
        self.n.tick(1020)
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "raconter")
        self.assertEqual(len(self.m.evenements("savoir.retrograde")), 1)

    def test_l_humain_agit_en_parallele_sans_attendre_de_palier(self):
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "raconter")
        r = self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(self.m.jouets["ours"], "ok")
        self.assertEqual(self.m.evenements("capacite.demandee")[0]["acteur"], "humain")

    def test_dix_reussites_humaines_font_monter_le_palier(self):
        for _ in range(10):
            self.m.jouets["ours"] = "casse"
            self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "auto")
        self.assertEqual(len(self.m.evenements("savoir.promu")), 1)

    def test_un_echec_humain_ne_retrograde_pas(self):
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.m.drapeaux["rater"] = True
        for _ in range(3):
            self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "auto")

    def test_essai_a_blanc_n_ecrit_rien(self):
        r = self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"}, essai=True)
        self.assertEqual(r["statut"], "simulee")
        self.assertEqual(self.m.jouets["ours"], "casse")

    def test_acteur_non_autorise_refuse(self):
        r = self.n.executeur.executer("labo.reparer_jouet", "itare", {"nom": "ours"})
        self.assertEqual(r["statut"], "refuse")
        self.assertEqual(len(self.m.evenements("capacite.refusee")), 1)

    def test_crise_seule_la_lecture_passe(self):
        self.n.crise(True, "essai")
        self.assertEqual(self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})["statut"], "refuse")
        self.assertEqual(self.n.agir_humain("labo.lire_jouet", {"nom": "ours"})["statut"], "faite")
        self.n.crise(False)
        self.assertEqual(self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})["statut"], "faite")

    def test_un_detecteur_en_panne_ne_ressemble_pas_a_rien_a_signaler(self):
        self.m.drapeaux["panne"] = True
        r = self.n.tick(1000)
        self.assertEqual(r["pannes"], 1)
        self.assertEqual(len(self.m.evenements("noyau.detecteur_en_panne")), 1)

    def test_les_objets_vont_au_registre_avec_leur_chronologie(self):
        self.n.tick(1000)
        self.assertEqual(self.n.registre.lire("jouet", "ours", portee=TOUT)["etat"], "casse")
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})
        self.m.jouets["ours"] = "ok"
        self.n.tick(1020)
        types = [e["type"] for e in self.n.bus.chronologie("jouet", "ours", portee=TOUT)]
        self.assertIn("objet.pose", types)
        self.assertIn("objet.change", types)

    def test_un_geste_hors_noyau_entre_au_cycle(self):
        eid = self.n.signaler_geste_humain("crontab modifié en SSH", objet=("machine", "orion"))
        e = self.n.bus.lire(eid, portee=TOUT)
        self.assertEqual((e["type"], e["acteur"]), ("humain.geste", "humain"))


class Frontieres(unittest.TestCase):
    def setUp(self):
        self.m = Monde()
        self.addCleanup(self.m.fermer)

    def test_un_module_n_emet_que_ce_qu_il_a_declare(self):
        ctx = self.m.noyau.executeur.contextes["labo"]
        with self.assertRaises(PermissionError):
            ctx.emettre("jouet.invente")
        self.assertTrue(ctx.emettre("jouet.casse", objet=("jouet", "ours")))

    def test_un_module_n_ecrit_que_ses_types(self):
        with self.assertRaises(PermissionError):
            self.m.noyau.registre.poser("autre", "jouet", "x", "x")

    def test_ecrire_sans_preuve_ni_retour_est_refuse_a_l_implementation(self):
        with self.assertRaises(ValueError):
            self.m.noyau.catalogue.implementer("labo", "reparer_jouet", lambda ctx, nom: None)

    def test_un_module_qui_en_importe_un_autre_est_refuse(self):
        t2 = LABO_TOML.replace('id = "labo"', 'id = "intrus"').replace('type = "jouet"', 'type = "intrus_o"').replace('"jouet.casse"', '"intrus_o.x"')
        t2 = t2.replace("[[capacites]]\nid = \"reparer_jouet\"", "[[capacites]]\nid = \"reparer_jouet\"")
        t2 = t2.split("[[detecteurs]]")[0]
        ecrire_module(self.m.modules, "intrus", t2, "import labo\n\ndef brancher(ctx):\n    pass\n")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mf.ManifesteInvalide) as c:
                moteur.Noyau(tmp, self.m.modules, {"labo": {"jouets": {}, "drapeaux": {}}}).brancher()
        self.assertIn("importe", str(c.exception))


class Enjeux(unittest.TestCase):
    """Sécurité (cloisonnement), résilience (reprise, disjoncteur), évolution (récurrences)."""

    def setUp(self):
        self.m = Monde()
        self.n = self.m.noyau
        self.addCleanup(self.m.fermer)

    # --- sécurité : le compte ne traverse pas, l'oubli est une erreur ---
    def test_la_portee_est_obligatoire_partout(self):
        with self.assertRaises(TypeError):
            self.n.bus.recents()
        with self.assertRaises(TypeError):
            self.n.registre.lister()
        with self.assertRaises(ValueError):
            self.n.bus.recents(portee="")           # « aucun compte » ne vaut PAS « tout voir »
        with self.assertRaises(ValueError):
            self.n.bus.recents(portee=None)

    def test_un_compte_ne_voit_que_le_sien_et_le_commun(self):
        b = self.n.bus
        a = b.emettre("noyau.essai", source="noyau", compte="sandrine@x.fr", donnees={"secret": "solde"})
        c = b.emettre("noyau.essai", source="noyau", compte="")
        d = b.emettre("noyau.essai", source="noyau", compte="drisse@x.fr")
        vus = {e["id"] for e in b.recents(portee="drisse@x.fr", limite=500, type_prefixe="noyau.essai")}
        self.assertEqual(vus, {c, d})
        self.assertIsNone(b.lire(a, portee="drisse@x.fr"))
        self.assertEqual({e["id"] for e in b.recents(portee=TOUT, limite=500, type_prefixe="noyau.essai")}, {a, c, d})

    def test_la_lignee_ne_fuit_pas_vers_un_autre_compte(self):
        b = self.n.bus
        racine = b.emettre("noyau.essai", source="noyau", compte="")
        b.emettre("noyau.essai", source="noyau", compte="sandrine@x.fr", cause=racine)
        b.emettre("noyau.essai", source="noyau", compte="drisse@x.fr", cause=racine)
        suites = b.lignee(racine, portee="drisse@x.fr")["suites"]
        self.assertEqual([s["compte"] for s in suites], ["drisse@x.fr"])

    def test_les_objets_d_un_compte_sont_cloisonnes(self):
        ctx = self.n.executeur.contextes["labo"]
        ctx.poser("jouet", "ours-a", "Ours A", "ok", compte="sandrine@x.fr")
        ctx.poser("jouet", "ours-b", "Ours B", "ok", compte="drisse@x.fr")
        ids = {o["id"] for o in self.n.registre.lister(portee="drisse@x.fr", type="jouet")}
        self.assertEqual(ids, {"ours-b"})
        self.assertIsNone(self.n.registre.lire("jouet", "ours-a", portee="drisse@x.fr"))
        self.assertEqual(self.n.registre.compter(portee="drisse@x.fr"), {"jouet": 1})

    def test_le_compte_suit_la_capacite_mais_jamais_d_un_fil_a_l_autre(self):
        self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"}, compte="sandrine@x.fr")
        ev = [e for e in self.n.bus.recents(portee=TOUT, limite=500) if e["type"].startswith("capacite.")]
        self.assertTrue(ev and all(e["compte"] == "sandrine@x.fr" for e in ev))
        self.assertEqual(self.n.executeur.contextes["labo"].compte, "")    # remis à zéro après la capacité

    # --- résilience ---
    def test_reprise_apres_mort_du_processus_prouve_ce_qui_est_bon(self):
        self.m.jouets["ours"] = "ok"
        self.n.bus.emettre("capacite.faite", source="labo", acteur="cassandra", objet=("capacite", "labo.reparer_jouet"),
                           donnees={"resultat": {"nom": "ours", "avant": "casse"}})
        self.assertEqual(self.n.reprendre(), [("labo.reparer_jouet", "prouvee")])
        self.assertEqual(self.n.reprendre(), [])                            # idempotent

    def test_reprise_apres_mort_du_processus_defait_ce_qui_n_est_pas_prouve(self):
        self.m.jouets["ours"] = "a-moitie"
        self.n.bus.emettre("capacite.faite", source="labo", acteur="cassandra", objet=("capacite", "labo.reparer_jouet"),
                           donnees={"resultat": {"nom": "ours", "avant": "casse"}})
        self.assertEqual(self.n.reprendre(), [("labo.reparer_jouet", "annulee")])
        self.assertEqual(self.m.jouets["ours"], "casse")

    def test_une_ecriture_menee_a_terme_n_est_pas_reprise(self):
        self.n.agir_humain("labo.reparer_jouet", {"nom": "ours"})
        self.assertEqual(self.n.reprendre(), [])

    def test_le_disjoncteur_suspend_un_detecteur_qui_plante_et_le_dit_une_fois(self):
        self.m.drapeaux["panne"] = True
        for i in range(8):
            self.n.tick(1000 + 20 * i)
        self.assertEqual(len(self.m.evenements("noyau.detecteur_en_panne")), 5)
        self.assertEqual(len(self.m.evenements("noyau.detecteur_suspendu")), 1)
        self.assertEqual(self.n.etat()["suspendus"], ["labo.jouet_casse"])
        self.m.drapeaux["panne"] = False
        self.n.rearmer_detecteur("labo", "jouet_casse")
        self.assertEqual(self.n.tick(2000)["pannes"], 0)

    # --- évolution ---
    def test_un_constat_qui_revient_est_signale_comme_recurrence(self):
        t = 1000
        for _ in range(3):
            self.m.jouets["ours"] = "casse"; self.n.tick(t); t += 20
            self.m.jouets["ours"] = "ok"; self.n.tick(t); t += 20
        r = self.n.recurrences(jours=14, seuil=3)
        self.assertEqual([(x["module"], x["detecteur"], x["objet_id"], x["n"]) for x in r], [("labo", "jouet_casse", "ours", 3)])
        self.assertEqual(self.n.recurrences(jours=14, seuil=4), [])


if __name__ == "__main__":
    unittest.main()
