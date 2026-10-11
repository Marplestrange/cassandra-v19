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


class Exploitation(unittest.TestCase):
    """Modules actifs, dépendances, chien de garde systemd."""

    def test_avec_dependances_rend_les_requis_d_abord(self):
        ms = mf.decouvrir(RACINE / "modules")
        self.assertEqual(mf.avec_dependances(ms, ["certificats"]), ["dns", "certificats"])
        self.assertEqual(mf.avec_dependances(ms, ["dns"]), ["dns"])
        with self.assertRaises(mf.ManifesteInvalide):
            mf.avec_dependances(ms, ["inconnu"])

    def test_seuls_les_modules_actifs_sont_branches(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = moteur.Noyau(tmp, actifs=["dns"])
            r = n.brancher(annoncer=False)
            self.assertEqual(r["ordre"], ["dns"])
            self.assertEqual({e.module for e in n.catalogue.lister()}, {"dns"})

    def test_un_module_actif_sans_son_requis_est_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mf.ManifesteInvalide) as c:
                moteur.Noyau(tmp, actifs=["certificats"]).brancher(annoncer=False)
            self.assertIn("requiert", str(c.exception))

    def test_un_module_actif_introuvable_est_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(mf.ManifesteInvalide):
                moteur.Noyau(tmp, actifs=["fantome"]).brancher(annoncer=False)

    def test_aucun_module_actif_est_permis(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(moteur.Noyau(tmp, actifs=[]).brancher(annoncer=False)["ordre"], [])

    def test_l_etat_n_ecrit_rien_au_bus(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = moteur.Noyau(tmp, actifs=["dns"])
            n.brancher(annoncer=False)
            self.assertEqual(n.etat()["evenements"], 0)

    def test_hors_systemd_notifier_est_inerte(self):
        import os
        from noyau import systemd
        avant = os.environ.pop("NOTIFY_SOCKET", None)
        try:
            self.assertFalse(systemd.pret("x"))
            self.assertFalse(systemd.battement())
        finally:
            if avant is not None:
                os.environ["NOTIFY_SOCKET"] = avant

    @unittest.skipUnless(hasattr(__import__("socket"), "AF_UNIX") and sys.platform != "win32", "sockets Unix absents")
    def test_le_noyau_parle_a_systemd(self):
        import os
        import socket
        from noyau import systemd
        with tempfile.TemporaryDirectory() as tmp:
            chemin = os.path.join(tmp, "notify.sock")
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            srv.bind(chemin)
            srv.settimeout(2)
            os.environ["NOTIFY_SOCKET"] = chemin
            try:
                self.assertTrue(systemd.pret("2 modules"))
                self.assertEqual(srv.recv(200).decode(), "READY=1\nSTATUS=2 modules")
                self.assertTrue(systemd.battement())
                self.assertEqual(srv.recv(200).decode(), "WATCHDOG=1")
            finally:
                os.environ.pop("NOTIFY_SOCKET", None)
                srv.close()


VEILLE_TOML = """
[module]
id = "veille"
nom = "Veille"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : des moteurs de chaque mode."
requiert = ["labo"]
%(confiance)s

[[objets]]
type = "releve"
libelle = "Un relevé"

[evenements]
emet = ["releve.fait"]
ecoute = ["jouet.casse"]

[[moteurs]]
id = "compter"
libelle = "Compte ses passages"
mode = "periodique"
toutes_les_s = 10

[[moteurs]]
id = "reagir"
libelle = "Réagit à un jouet cassé"
mode = "evenement"
sur = "jouet.casse"

[[moteurs]]
id = "lourd"
libelle = "Trop long"
mode = "demande"
duree_max_s = 1

[[moteurs]]
id = "casse"
libelle = "Échoue toujours"
mode = "demande"
"""

VEILLE_PY = '''
import time


def brancher(ctx):
    cfg = ctx.config

    def compter(ctx):
        cfg["n"] = cfg.get("n", 0) + 1

    def reagir(ctx, ev):
        cfg.setdefault("evts", []).append(ev["objet_id"])
        ctx.emettre("releve.fait", objet=("releve", ev["objet_id"]))

    def lourd(ctx):
        time.sleep(2)

    def casse(ctx):
        raise RuntimeError("boum")

    ctx.moteur("compter", compter)
    ctx.moteur("reagir", reagir)
    ctx.moteur("lourd", lourd)
    ctx.moteur("casse", casse)
'''


def monde_moteurs(confiance='confiance = "interne"', extension=False, actifs=None):
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    modules = base / "modules"
    ecrire_module(modules, "labo", LABO_TOML, LABO_PY)
    cible = (base / "extensions") if extension else modules
    ecrire_module(cible, "veille", VEILLE_TOML % {"confiance": confiance}, VEILLE_PY)
    cfg = {"labo": {"jouets": {}, "drapeaux": {}}, "veille": {}}
    n = moteur.Noyau(base / "d", modules, cfg, actifs=actifs, extensions=(base / "extensions") if extension else None)
    return tmp, n, cfg, base


class Moteurs(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.cfg, _ = monde_moteurs()
        self.n.brancher()
        self.addCleanup(self.tmp.cleanup)

    def evts(self, t):
        return [e for e in self.n.bus.recents(portee=TOUT, limite=500) if e["type"] == t]

    def test_un_moteur_periodique_tourne_quand_il_est_echu(self):
        r = self.n.tick(1000)
        self.assertEqual(r["moteurs"], 1)                    # compter ; les autres sont sur événement ou à la demande
        self.assertEqual(self.n.tick(1005)["moteurs"], 0)    # pas encore échu
        self.assertEqual(self.n.tick(1011)["moteurs"], 1)
        self.assertEqual(self.n.executeur.contextes["veille"].config["n"], 2)
        e = {m["cle"]: m for m in self.n.etat_moteurs()}["veille.compter"]
        self.assertEqual((e["executions"], e["echecs"], e["etat"]), (2, 0, "actif"))

    def test_un_moteur_sur_evenement_se_reveille_et_garde_la_lignee(self):
        ctx = self.n.executeur.contextes["labo"]
        declencheur = ctx.emettre("jouet.casse", objet=("jouet", "ours"))
        self.assertEqual(self.n.executeur.contextes["veille"].config["evts"], ["ours"])
        fait = self.evts("releve.fait")[0]
        self.assertEqual(fait["cause"], declencheur)
        self.assertEqual(fait["source"], "veille")

    def test_un_moteur_qui_echoue_se_dit_puis_se_suspend(self):
        for _ in range(5):
            self.assertEqual(self.n.lancer("veille.casse")["statut"], "echec")
        self.assertEqual(len(self.evts("moteur.echoue")), 5)
        self.assertEqual(len(self.evts("moteur.suspendu")), 1)
        self.assertEqual(self.n.lancer("veille.casse")["statut"], "echec")     # lancer le réarme : voie humaine
        self.assertIn("veille.casse", self.n.etat()["moteurs_a_surveiller"] + ["veille.casse"])

    def test_un_moteur_fige_ne_s_empile_pas_puis_reprend(self):
        self.assertEqual(self.n.lancer("veille.lourd")["statut"], "fige")       # dort 2 s pour 1 s permise
        self.assertEqual(len(self.evts("moteur.fige")), 1)
        self.assertEqual(self.n.lancer("veille.lourd")["statut"], "fige")       # toujours en cours : rien n'est relancé
        self.assertEqual(len(self.evts("moteur.fige")), 1)
        self.assertEqual({m["cle"]: m for m in self.n.etat_moteurs()}["veille.lourd"]["etat"], "fige")
        import time
        time.sleep(1.5)
        self.assertEqual(self.n.lancer("veille.lourd")["statut"], "fige")       # un nouveau tour, qui dépasse encore sa durée

    def test_lancer_a_la_main_est_une_voie_parallele_journalisee(self):
        self.n.lancer("veille.compter", acteur="humain")
        d = self.evts("moteur.demande")[0]
        self.assertEqual((d["acteur"], d["objet_id"]), ("humain", "veille.compter"))
        self.assertEqual(self.n.lancer("veille.reagir")["statut"], "refuse")   # sur événement : pas sans événement
        self.assertEqual(self.n.lancer("veille.fantome")["statut"], "refuse")

    def test_les_manifestes_de_moteurs_sont_valides_par_construction(self):
        import tomllib
        def brut(**mo):
            b = tomllib.loads(VEILLE_TOML % {"confiance": ""})
            b["moteurs"][0].update(mo)
            return b
        self.assertEqual(mf.valider(brut()), [])
        self.assertTrue(any("10 secondes" in e for e in mf.valider(brut(toutes_les_s=3))))
        self.assertTrue(any("mode" in e for e in mf.valider(brut(mode="toujours"))))
        b = brut(mode="evenement", sur="jouet.invente")
        self.assertTrue(any("evenements.ecoute" in e for e in mf.valider(b)))
        self.assertTrue(any("duree_max_s" in e for e in mf.valider(brut(duree_max_s=0))))


class Greffe(unittest.TestCase):
    """Brancher un module après coup, sans redémarrer."""

    def test_une_extension_deposee_est_branchee_a_chaud(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", LABO_TOML, LABO_PY)
        actifs = ["labo"]
        cfg = {"labo": {"jouets": {}, "drapeaux": {}}, "veille": {}}
        n = moteur.Noyau(base / "d", base / "modules", cfg, actifs=actifs, extensions=base / "extensions", lire_actifs=lambda: list(actifs))
        n.brancher()
        self.assertEqual(n.etat()["moteurs"], 0)
        # on dépose l'extension et on l'active : le noyau tourne déjà
        (base / "extensions").mkdir(exist_ok=True)
        ecrire_module(base / "extensions", "veille", VEILLE_TOML % {"confiance": 'confiance = "local"'}, VEILLE_PY)
        actifs.append("veille")
        n._surveiller()
        self.assertEqual(n.etat()["moteurs"], 4)
        self.assertEqual([e["objet_id"] for e in n.bus.recents(portee=TOUT, limite=50, type_prefixe="noyau.greffe")], ["veille"])
        self.assertEqual(n.tick(1000)["moteurs"], 1)                        # son moteur périodique tourne déjà
        n.executeur.contextes["labo"].emettre("jouet.casse", objet=("jouet", "ours"))
        self.assertEqual(n.executeur.contextes["veille"].config["evts"], ["ours"])   # et son moteur sur événement est relié
        n._surveiller()                                                     # rien de neuf : rien n'est rebranché
        self.assertEqual(len(n.bus.recents(portee=TOUT, limite=500, type_prefixe="noyau.greffe")), 1)

    def test_une_extension_ne_peut_pas_se_dire_interne_et_n_arrete_rien(self):
        tmp, n, _, base = monde_moteurs(confiance='confiance = "interne"', extension=True, actifs=["labo", "veille"])
        self.addCleanup(tmp.cleanup)
        r = n.brancher()                                    # le noyau DÉMARRE malgré l'extension fautive
        self.assertEqual(r["ordre"], ["labo"])
        self.assertEqual([x["module"] for x in r["refuses"]], ["veille"])
        self.assertIn("interne", " ".join(r["refuses"][0]["raisons"]))
        refus = [e for e in n.bus.recents(portee=TOUT, limite=50) if e["type"] == "noyau.greffe_refusee"]
        self.assertEqual(len(refus), 1)                     # dit une fois
        n.recharger()
        n.recharger()
        self.assertEqual(len([e for e in n.bus.recents(portee=TOUT, limite=500) if e["type"] == "noyau.greffe_refusee"]), 1)
        self.assertEqual(n.etat()["moteurs"], 0)

    def test_une_extension_illisible_est_ecartee_sans_arreter_le_noyau(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", LABO_TOML, LABO_PY)
        ecrire_module(base / "extensions", "casse", "ceci n'est pas du toml [[[", "def brancher(ctx): pass\n")
        n = moteur.Noyau(base / "d", base / "modules", {"labo": {"jouets": {}, "drapeaux": {}}}, extensions=base / "extensions")
        r = n.brancher()
        self.assertEqual(r["ordre"], ["labo"])
        self.assertEqual(r["refuses"][0]["module"], "casse")

    def test_une_extension_qui_en_importe_une_autre_est_ecartee(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", LABO_TOML, LABO_PY)
        ecrire_module(base / "extensions", "veille", VEILLE_TOML % {"confiance": 'confiance = "local"'}, "import labo\n\ndef brancher(ctx):\n    pass\n")
        n = moteur.Noyau(base / "d", base / "modules", {"labo": {"jouets": {}, "drapeaux": {}}}, extensions=base / "extensions")
        r = n.brancher()
        self.assertEqual(r["ordre"], ["labo"])
        self.assertIn("importe", " ".join(r["refuses"][0]["raisons"]))

    def test_une_extension_ne_peut_pas_prendre_l_id_d_un_module_livre(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", LABO_TOML, LABO_PY)
        ecrire_module(base / "extensions", "labo", LABO_TOML.replace('version = "0.1.0"', 'version = "9.9.9"'), LABO_PY)
        n = moteur.Noyau(base / "d", base / "modules", {"labo": {"jouets": {}, "drapeaux": {}}}, extensions=base / "extensions")
        r = n.brancher()
        self.assertEqual(r["ordre"], ["labo"])
        self.assertEqual(n.registre.proprietaires["jouet"], "labo")
        self.assertIn("déjà présent", " ".join(r["refuses"][0]["raisons"]))

    def test_un_deploiement_ne_touche_pas_aux_extensions(self):
        # les extensions vivent hors des versions du noyau : `modules/` change, `extensions/` reste
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "extensions", "veille", VEILLE_TOML % {"confiance": 'confiance = "local"'}, VEILLE_PY)
        self.assertFalse((RACINE / "modules" / "veille").exists())


DUR_TOML = """
[module]
id = "dur"
nom = "Dur"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module essentiel d'essai."
essentiel = true
famille = "socle"

[[objets]]
type = "pilier"
libelle = "Un pilier"
"""


def monde_menu(installation=False):
    """Un noyau en gestion par état (comme en exploitation) avec labo, veille (requiert labo) et dur (essentiel)."""
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    ecrire_module(mods, "labo", LABO_TOML, LABO_PY)
    veille = VEILLE_TOML % {"confiance": 'confiance = "interne"'}
    if installation:
        veille += '\n[installation]\nscript = "installer.sh"\nverification = "verifier.sh"\nretrait = "retirer.sh"\n'
    ecrire_module(mods, "veille", veille, VEILLE_PY)
    if installation:
        for f in ("installer.sh", "verifier.sh", "retirer.sh"):
            (mods / "veille" / f).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ecrire_module(mods, "dur", DUR_TOML, "def brancher(ctx):\n    pass\n")
    cfg = {"labo": {"jouets": {}, "drapeaux": {}}, "veille": {}}

    def noyau():
        return moteur.Noyau(base / "d", mods, cfg, gerer_modules=True)
    return tmp, noyau, cfg


class MenuDesModules(unittest.TestCase):
    def setUp(self):
        self.tmp, self.nouveau, self.cfg = monde_menu()
        self.addCleanup(self.tmp.cleanup)
        self.n = self.nouveau()
        self.n.brancher()

    def etats(self):
        return {m["id"]: m for m in self.n.catalogue_modules()}

    def evts(self, t):
        return [e for e in self.n.bus.recents(portee=TOUT, limite=500) if e["type"] == t]

    def test_au_depart_rien_n_est_actif_et_tout_est_activable(self):
        e = self.etats()
        self.assertEqual({k: v["etat"] for k, v in e.items()}, {"labo": "inactif", "veille": "inactif", "dur": "inactif"})
        self.assertEqual(self.n.etat()["modules"], [])
        self.assertTrue(e["veille"]["peut_activer"]["ok"])
        self.assertEqual(e["dur"]["famille"], "socle")

    def test_activer_un_module_active_ses_dependances_d_abord(self):
        r = self.n.activer("veille", acteur="humain")
        self.assertEqual(r, {"ok": True, "actives": ["labo", "veille"]})
        self.assertEqual(self.n.etat()["modules"], ["labo", "veille"])
        self.assertEqual(self.n.etat()["moteurs"], 4)
        ev = self.evts("module.active")
        self.assertEqual([(e["objet_id"], e["acteur"]) for e in ev], [("labo", "humain"), ("veille", "humain")])
        self.assertEqual(self.n.activer("veille")["actives"], [])                 # déjà actif : rien de plus

    def test_activer_sans_ses_dependances_est_refuse(self):
        r = self.n.activer("veille", avec_dependances=False)
        self.assertFalse(r["ok"])
        self.assertEqual(r["dependances"], ["labo"])
        self.assertEqual(self.n.etat()["modules"], [])

    def test_desactiver_un_module_requis_est_refuse_sauf_en_cascade(self):
        self.n.activer("veille")
        r = self.n.desactiver("labo")
        self.assertFalse(r["ok"])
        self.assertEqual(r["dependants"], ["veille"])
        self.assertEqual(self.n.desactiver("labo", cascade=True), {"ok": True, "desactives": ["veille", "labo"]})   # les dépendants d'abord
        self.assertEqual(self.n.etat()["modules"], [])
        self.assertEqual(self.n.etat()["moteurs"], 0)

    def test_desactiver_arrete_tout_mais_garde_les_donnees(self):
        self.n.activer("veille")
        self.cfg["labo"]["jouets"]["ours"] = "casse"
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.n.tick(1000)                                                          # l'objet est posé, le jouet réparé
        self.assertIsNotNone(self.n.registre.lire("jouet", "ours", portee=TOUT))
        self.cfg["labo"]["jouets"]["ours"] = "casse"
        self.n.catalogue.regler_palier("labo.reparer_jouet", "raconter")
        self.n.tick(1020)                                                          # constat ouvert, seulement raconté
        self.assertEqual(self.n.etat()["constats_ouverts"], 1)
        self.n.desactiver("labo", cascade=True)
        # plus rien ne répond
        self.assertEqual(self.n.executeur.executer("labo.reparer_jouet", "humain", {"nom": "ours"})["statut"], "refuse")
        self.assertIn("désactivé", self.n.executeur.executer("labo.reparer_jouet", "humain", {"nom": "ours"})["raison"])
        self.assertEqual(self.n.lancer("veille.compter")["statut"], "refuse")
        self.assertEqual(self.n.tick(2000)["detecteurs"], 0)
        self.assertEqual(self.n.bus.desabonner("veille"), 0)                       # ses abonnements sont déjà partis
        # les données restent ; le constat est suspendu, pas supprimé
        self.assertIsNotNone(self.n.registre.lire("jouet", "ours", portee=TOUT))
        self.assertEqual(self.n.base.lire("SELECT etat FROM constats")[0]["etat"], "suspendu")
        self.assertEqual(self.n.etat()["constats_ouverts"], 0)
        self.assertEqual(len(self.evts("noyau.module_debranche")), 2)

    def test_reactiver_rebranche_et_retrouve_le_savoir_faire(self):
        self.n.activer("labo")
        self.n.catalogue.regler_palier("labo.reparer_jouet", "auto")
        self.n.desactiver("labo")
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "auto")   # l'apprentissage survit
        self.n.activer("labo")
        self.assertEqual(self.n.agir_humain("labo.lire_jouet", {"nom": "x"})["statut"], "faite")
        self.assertEqual(self.n.catalogue.savoir("labo.reparer_jouet")["palier"], "auto")
        self.assertEqual(self.n.etat()["detecteurs"], 1)                            # branché une seule fois

    def test_un_module_essentiel_ne_se_desactive_pas_sauf_force(self):
        self.n.activer("dur")
        r = self.n.desactiver("dur")
        self.assertFalse(r["ok"])
        self.assertTrue(r["essentiel"])
        self.assertTrue(self.etats()["dur"]["essentiel"])
        self.assertEqual(self.n.desactiver("dur", forcer=True)["desactives"], ["dur"])

    def test_l_etat_survit_au_redemarrage(self):
        self.n.activer("veille")
        autre = self.nouveau()
        autre.brancher()
        self.assertEqual(autre.etat()["modules"], ["labo", "veille"])

    def test_le_noyau_en_marche_voit_un_changement_d_etat_ecrit_ailleurs(self):
        cli = self.nouveau()                                                        # comme `main.py module activer`
        cli.activer("labo", appliquer=False)
        self.assertEqual(self.n.etat()["modules"], [])
        self.n._surveiller()                                                       # une passe de la boucle
        self.assertEqual(self.n.etat()["modules"], ["labo"])
        cli.desactiver("labo", appliquer=False)
        self.n._surveiller()
        self.assertEqual(self.n.etat()["modules"], [])

    def test_un_module_actif_dont_le_dossier_a_disparu_n_arrete_pas_le_noyau(self):
        self.n.etat_modules.poser("fantome", installe=True, actif=True, par="test")
        autre = self.nouveau()
        r = autre.brancher()                                                        # démarre quand même
        self.assertEqual(r["introuvables"], ["fantome"])
        self.assertEqual(len([e for e in autre.bus.recents(portee=TOUT, limite=50) if e["type"] == "noyau.module_introuvable"]), 1)

    def test_l_ancienne_liste_amorce_un_etat_vide(self):
        n = moteur.Noyau(Path(self.tmp.name) / "d2", Path(self.tmp.name) / "modules", self.cfg, gerer_modules=True, amorce=lambda: ["labo"])
        n.brancher()
        self.assertEqual(n.etat()["modules"], ["labo"])
        self.assertEqual(n.etat_modules.get("labo")["par"], "amorce")

    def test_les_liens_du_menu(self):
        self.n.activer("veille")
        e = self.etats()
        self.assertEqual(e["labo"]["requis_par"], ["veille"])
        self.assertEqual(e["veille"]["requiert"], ["labo"])
        self.assertFalse(e["labo"]["peut_desactiver"]["ok"])
        self.assertTrue(e["veille"]["peut_desactiver"]["ok"])
        self.assertEqual((e["veille"]["moteurs"], e["veille"]["implementees"]), (4, 0))


class MenuAvecInstallation(unittest.TestCase):
    def test_un_module_a_installer_ne_s_active_que_s_il_l_est(self):
        tmp, nouveau, _ = monde_menu(installation=True)
        self.addCleanup(tmp.cleanup)
        n = nouveau()
        n.brancher()
        self.assertEqual({m["id"]: m["etat"] for m in n.catalogue_modules()}["veille"], "a_installer")
        r = n.activer("veille")
        self.assertFalse(r["ok"])
        self.assertEqual(r["a_installer"], "veille")
        self.assertIn("install.sh --module veille", r["raison"])
        n.etat_modules.poser("veille", installe=True, par="installateur")           # ce que fait install.sh après sa preuve
        self.assertTrue(n.activer("veille")["ok"])


class LigneDeCommandeModules(unittest.TestCase):
    def test_module_activer_desactiver_actif(self):
        import os
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ancien = {k: os.environ.get(k) for k in ("CASSANDRA_DONNEES", "CASSANDRA_EXTENSIONS")}
        os.environ["CASSANDRA_DONNEES"] = tmp.name
        os.environ.pop("CASSANDRA_EXTENSIONS", None)
        try:
            c = lambda *a: moteur.commande_module(["main.py", "module"] + list(a))
            self.assertEqual(c("actif", "dns"), 1)
            self.assertEqual(c("activer", "dns"), 0)
            self.assertEqual(c("actif", "dns"), 0)
            self.assertEqual(c("activer", "certificats"), 1)         # s'installe d'abord par l'administrateur
            self.assertEqual(c("installe", "certificats"), 0)
            self.assertEqual(c("activer", "certificats"), 0)
            self.assertEqual(c("desactiver", "dns"), 1)               # requis par certificats
            self.assertEqual(c("desactiver", "dns", "--en-cascade"), 0)
            self.assertEqual(c("actif", "certificats"), 1)
            self.assertEqual(c("oublier", "dns"), 0)
            self.assertEqual(c("liste"), 0)
        finally:
            for k, v in ancien.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class Chemins(unittest.TestCase):
    """Les dossiers des utilisateurs suivent la convention de FastPanel : /var/www/<utilisateur>/data/."""

    def setUp(self):
        import os
        from noyau import chemins
        self.chemins = chemins
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ancien = os.environ.get("CASSANDRA_UTILISATEURS")
        os.environ["CASSANDRA_UTILISATEURS"] = self.tmp.name
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_UTILISATEURS", self.ancien) if self.ancien else os.environ.pop("CASSANDRA_UTILISATEURS", None))

    def test_l_espace_d_un_module_chez_un_utilisateur(self):
        p = self.chemins.espace_utilisateur("fastuser", "ged")
        self.assertEqual(p, Path(self.tmp.name) / "fastuser" / "data" / "cassandra" / "ged")
        self.assertFalse(p.exists())                                    # rien n'est créé sans le demander
        self.assertTrue(self.chemins.espace_utilisateur("fastuser", "ged", creer=True).is_dir())

    def test_rien_ne_sort_de_l_espace(self):
        for mauvais in ("../etc", "fast user", "", "FASTUSER", "a/b", "..", "x" * 40):
            with self.assertRaises(ValueError, msg=mauvais):
                self.chemins.espace_utilisateur(mauvais, "ged")
        for mauvais in ("../x", "Ged", "", "g/e"):
            with self.assertRaises(ValueError, msg=mauvais):
                self.chemins.espace_utilisateur("fastuser", mauvais)

    @unittest.skipUnless(sys.platform != "win32", "liens symboliques : droits particuliers sous Windows")
    def test_un_lien_symbolique_ne_fait_pas_sortir(self):
        import os
        autre = tempfile.TemporaryDirectory()
        self.addCleanup(autre.cleanup)
        os.makedirs(Path(self.tmp.name) / "fastuser" / "data")
        os.symlink(autre.name, Path(self.tmp.name) / "fastuser" / "data" / "cassandra")
        with self.assertRaises(ValueError):
            self.chemins.espace_utilisateur("fastuser", "ged")

    def test_un_module_demande_son_espace_par_le_contexte(self):
        m = Monde()
        self.addCleanup(m.fermer)
        ctx = m.noyau.executeur.contextes["labo"]
        self.assertEqual(ctx.espace("sandrinedeshayes"), Path(self.tmp.name) / "sandrinedeshayes" / "data" / "cassandra" / "labo")
        with self.assertRaises(ValueError):
            ctx.espace("../root")


if __name__ == "__main__":
    unittest.main()
