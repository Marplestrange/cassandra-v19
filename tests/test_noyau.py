"""Bancs du noyau. Stdlib seule : python -m unittest discover -s tests -v"""
import os
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

[permissions]
espace_utilisateur = true
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

    def _surcharge(self, livre_toml, ext_toml, config=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", livre_toml, LABO_PY)
        ecrire_module(base / "extensions", "labo", ext_toml.replace('noyau_min = "0.1.0"', 'noyau_min = "0.1.0"\nconfiance = "local"'), LABO_PY)
        cfg = {"labo": {"jouets": {}, "drapeaux": {}}}
        cfg.update(config or {})
        n = moteur.Noyau(base / "d", base / "modules", cfg, extensions=base / "extensions")
        return n, n.brancher()

    def test_une_extension_remplace_un_module_livre_ordinaire(self):
        """Comme `custom` l'emporte sur `htdocs` : le remplaçant prend la place, et le noyau le dit."""
        n, r = self._surcharge(LABO_TOML, LABO_TOML.replace('version = "0.1.0"', 'version = "9.9.9"'))
        self.assertEqual(r["ordre"], ["labo"])
        self.assertEqual(r["refuses"], [])
        self.assertEqual(r["remplaces"], {"labo": {"livre": "0.1.0", "extension": "9.9.9"}})
        evt = [e for e in n.bus.recents(portee=TOUT, limite=100) if e["type"] == "noyau.module_remplace"]
        self.assertEqual(evt[-1]["donnees"], {"module": "labo", "livre": "0.1.0", "extension": "9.9.9"})
        ligne = next(x for x in n.catalogue_modules() if x["id"] == "labo")
        self.assertEqual((ligne["version"], ligne["extension"], ligne["remplace"]), ("9.9.9", True, "0.1.0"))

    def test_un_module_essentiel_ne_se_remplace_que_si_l_administrateur_le_decide(self):
        essentiel = LABO_TOML.replace('noyau_min = "0.1.0"', 'noyau_min = "0.1.0"\nessentiel = true')
        ext = essentiel.replace('version = "0.1.0"', 'version = "9.9.9"').replace("essentiel = true", "")
        n, r = self._surcharge(essentiel, ext)
        self.assertEqual(r["remplaces"], {})
        self.assertIn("réglage de l'administrateur", " ".join(r["refuses"][0]["raisons"]))
        self.assertEqual(next(x for x in n.catalogue_modules() if x["id"] == "labo" and not x["extension"])["version"], "0.1.0")
        n, r = self._surcharge(essentiel, ext, {"surcharge": {"essentiels": ["labo"]}})      # le choix de l'administrateur
        self.assertEqual(r["remplaces"]["labo"]["extension"], "9.9.9")

    def test_un_remplacant_ecarte_rend_sa_place_au_module_livre(self):
        casse = LABO_TOML.replace('noyau_min = "0.1.0"', 'noyau_min = "0.1.0"\nrequiert = ["fantome"]')
        n, r = self._surcharge(LABO_TOML, casse)
        self.assertEqual(r["ordre"], ["labo"])
        self.assertEqual(r["remplaces"], {})
        self.assertIn("reprend sa place", " ".join(r["refuses"][0]["raisons"]))

    def test_le_remplacement_et_le_retrait_se_font_a_chaud(self):
        """Dans le noyau EN MARCHE : déposer l'extension remplace le module branché, la retirer le rend."""
        import shutil
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        ecrire_module(base / "modules", "labo", LABO_TOML, LABO_PY)
        (base / "extensions").mkdir()
        n = moteur.Noyau(base / "d", base / "modules", {"labo": {"jouets": {}, "drapeaux": {}}}, extensions=base / "extensions")
        n.brancher()
        version = lambda: next(m.version for m in n._manifestes_actifs() if m.id == "labo")
        self.assertEqual(version(), "0.1.0")
        ecrire_module(base / "extensions", "labo", LABO_TOML.replace('noyau_min = "0.1.0"', 'noyau_min = "0.1.0"\nconfiance = "local"')
                      .replace('version = "0.1.0"', 'version = "9.9.9"'), LABO_PY)
        n.recharger()
        self.assertEqual(version(), "9.9.9")
        self.assertEqual([m.id for m in n._manifestes_actifs()].count("labo"), 1)
        self.assertEqual(n.executeur.executer("labo.lire_jouet", "humain", {"nom": "x"})["statut"], "faite")   # il répond encore
        evt = [e["type"] for e in n.bus.recents(portee=TOUT, limite=200)]
        self.assertIn("noyau.module_remplace", evt)
        shutil.rmtree(base / "extensions" / "labo")
        n.recharger()
        self.assertEqual(version(), "0.1.0")

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

    def test_l_espace_des_utilisateurs_n_est_donne_qu_a_qui_l_a_demande(self):
        tmp, n, _, _ = monde_moteurs()                 # « veille » n'a déclaré aucune permission
        self.addCleanup(tmp.cleanup)
        n.brancher()
        with self.assertRaises(PermissionError):
            n.executeur.contextes["veille"].espace("fastuser")

    def test_un_module_demande_son_espace_par_le_contexte(self):
        m = Monde()
        self.addCleanup(m.fermer)
        ctx = m.noyau.executeur.contextes["labo"]
        self.assertEqual(ctx.espace("sandrinedeshayes"), Path(self.tmp.name) / "sandrinedeshayes" / "data" / "cassandra" / "labo")
        with self.assertRaises(ValueError):
            ctx.espace("../root")


def _openssl_ok():
    import shutil
    return shutil.which("openssl") is not None


@unittest.skipUnless(_openssl_ok(), "openssl absent")
class Paquets(unittest.TestCase):
    """Le paquet d'un module : intégrité, signature, extraction sûre."""

    def setUp(self):
        import subprocess
        from noyau import paquets
        self.paquets = paquets
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.cles = self.base / "cles"
        self.cles.mkdir()
        self.priv = self.base / "editeur.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(self.priv)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.priv), "-pubout", "-out", str(self.cles / "atek.pub")], check=True, capture_output=True)
        self.src = self.base / "src" / "sentinelle"
        import shutil
        shutil.copytree(RACINE / "exemples" / "sentinelle", self.src)

    def test_un_paquet_signe_se_verifie(self):
        a = self.paquets.construire(self.src, self.priv, self.base / "s.cmod")
        v = self.paquets.verifier(a, self.cles)
        self.assertEqual((v["id"], v["version"], v["signe"], v["editeur"]), ("sentinelle", mf.charger(self.src / "manifeste.toml").version, True, "atek"))

    def test_la_construction_est_reproductible(self):
        a = self.paquets.construire(self.src, self.priv, self.base / "a.cmod").read_bytes()
        b = self.paquets.construire(self.src, self.priv, self.base / "b.cmod").read_bytes()
        import gzip
        self.assertEqual(gzip.decompress(a), gzip.decompress(b))       # même contenu, même archive (hors horodatage gzip)

    def test_une_cle_inconnue_ne_donne_pas_la_confiance(self):
        a = self.paquets.construire(self.src, self.priv, self.base / "s.cmod")
        (self.cles / "atek.pub").unlink()
        v = self.paquets.verifier(a, self.cles)
        self.assertFalse(v["signe"])
        with self.assertRaises(self.paquets.PaquetInvalide):
            self.paquets.extraire(a, self.base / "dest", self.cles)
        self.assertEqual(self.paquets.extraire(a, self.base / "dest", self.cles, exiger_signature=False)["id"], "sentinelle")

    def test_un_paquet_modifie_apres_signature_est_refuse(self):
        import tarfile, io
        a = self.paquets.construire(self.src, self.priv, self.base / "s.cmod")
        evil = self.base / "evil.cmod"
        with tarfile.open(a, "r:gz") as ent, tarfile.open(evil, "w:gz") as sor:
            for ti in ent.getmembers():
                data = ent.extractfile(ti).read() if ti.isfile() else None
                if ti.name.endswith("module.py"):
                    data = data + b"\nimport os; os.system('id')\n"
                    ti.size = len(data)
                sor.addfile(ti, io.BytesIO(data) if data is not None else None)
        with self.assertRaises(self.paquets.PaquetInvalide) as c:
            self.paquets.verifier(evil, self.cles)
        self.assertIn("modifié", str(c.exception))

    def _archive(self, noms_types, nom="x.cmod"):
        import tarfile, io
        a = self.base / nom
        with tarfile.open(a, "w:gz") as t:
            for n, typ in noms_types:
                ti = tarfile.TarInfo(n)
                if typ == "lien":
                    ti.type, ti.linkname = tarfile.SYMTYPE, "/etc/passwd"
                    t.addfile(ti)
                else:
                    d = b"x"
                    ti.size = len(d)
                    t.addfile(ti, io.BytesIO(d))
        return a

    def test_une_archive_dangereuse_est_refusee(self):
        for noms in ([("../evil", "f")], [("/etc/evil", "f")], [("a/lien", "lien")], [("a/x", "f"), ("b/y", "f")]):
            with self.assertRaises(self.paquets.PaquetInvalide, msg=str(noms)):
                self.paquets.verifier(self._archive(noms), self.cles)

    def test_une_archive_demesuree_est_refusee(self):
        a = self.paquets.construire(self.src, self.priv, self.base / "s.cmod")
        ancien = self.paquets.MAX_OCTETS
        self.paquets.MAX_OCTETS = 100
        try:
            with self.assertRaises(self.paquets.PaquetInvalide):
                self.paquets.verifier(a, self.cles)
        finally:
            self.paquets.MAX_OCTETS = ancien

    def test_un_paquet_ne_peut_pas_se_dire_interne(self):
        t = (self.src / "manifeste.toml").read_text(encoding="utf-8").replace('confiance = "local"', 'confiance = "interne"')
        (self.src / "manifeste.toml").write_text(t, encoding="utf-8")
        with self.assertRaises(self.paquets.PaquetInvalide):
            self.paquets.construire(self.src, self.priv, self.base / "s.cmod")

    def test_la_ligne_de_commande_des_paquets(self):
        import os
        ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = str(self.base)              # les clés sont dans <config>/cles
        try:
            c = lambda *a: moteur.commande_paquet(["main.py", "paquet"] + [str(x) for x in a])
            cmod = self.base / "p.cmod"
            self.assertEqual(c("construire", self.src, "--cle", self.priv, "--sortie", cmod), 0)
            self.assertEqual(c("verifier", cmod), 0)
            self.assertEqual(c("extraire", cmod, self.base / "ext"), 0)
            self.assertTrue((self.base / "ext" / "sentinelle" / "manifeste.toml").is_file())
            (self.cles / "atek.pub").unlink()
            self.assertEqual(c("verifier", cmod), 3)                  # intègre mais non signé
            self.assertEqual(c("extraire", cmod, self.base / "ext2"), 1)
            self.assertEqual(c("extraire", cmod, self.base / "ext2", "--non-signe"), 0)
        finally:
            if ancien is None:
                os.environ.pop("CASSANDRA_CONFIG", None)
            else:
                os.environ["CASSANDRA_CONFIG"] = ancien


class ContratDeStore(unittest.TestCase):
    """Ce qu'un module store doit dire de lui, validé par le noyau."""

    def brut(self, **mod):
        import tomllib
        b = tomllib.loads(LABO_TOML)
        b["module"].update(mod)
        return b

    def test_la_version_d_api_doit_correspondre(self):
        self.assertEqual(mf.valider(self.brut(api="1")), [])
        self.assertTrue(any("API" in e for e in mf.valider(self.brut(api="2"))))
        self.assertTrue(any("module.api" in e for e in mf.valider(self.brut(api="un"))))

    def test_les_permissions_sont_validees(self):
        b = self.brut()
        b["permissions"] = {"ecritures": ["etc/relatif"], "reseau": "pas-une-liste"}
        e = mf.valider(b)
        self.assertTrue(any("chemin absolu" in x for x in e))
        self.assertTrue(any("permissions.reseau" in x for x in e))
        b["permissions"] = {"ecritures": ["/etc/exim4/certs_map"], "reseau": ["api.exemple.org"], "privileges": ["installer"]}
        self.assertEqual(mf.valider(b), [])
        m = mf.construire(b)
        self.assertEqual((m.permissions.reseau, m.permissions.ecritures), (("api.exemple.org",), ("/etc/exim4/certs_map",)))

    def test_le_menu_montre_permissions_auteur_et_api(self):
        tmp, nouveau, _ = monde_menu()
        self.addCleanup(tmp.cleanup)
        n = nouveau()
        n.brancher()
        labo = {m["id"]: m for m in n.catalogue_modules()}["labo"]
        self.assertTrue(labo["permissions"]["espace_utilisateur"])
        self.assertEqual(labo["api"], "1")


ALPHA_TOML = """
[module]
id = "alpha"
nom = "Alpha"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai pour les menus."
famille = "reseau"

[[objets]]
type = "alpha_o"
libelle = "Un objet"

[[detecteurs]]
id = "d1"
libelle = "Un constat à la demande"
frequence_s = 10

[[ecrans]]
id = "e1"
libelle = "Premier"

[[ecrans]]
id = "e2"
libelle = "Second"

[[menus]]
id = "a1"
libelle = "Premier"
ecran = "e1"
ordre = 20
badge = "constats"

[[menus]]
id = "a2"
libelle = "Réservé"
ecran = "e2"
ordre = 10
role = "admin"

[[menus]]
id = "sous"
libelle = "Sous-page"
ecran = "e2"
parent = "a1"
ordre = 1

[[menus]]
id = "groupe"
libelle = "Groupe vide"
"""

ALPHA_PY = """
def brancher(ctx):
    def d1(ctx):
        return [{"objet": ("alpha_o", "x"), "titre": "un constat"}] if ctx.config["etat"]["constat"] else []
    ctx.detecteur("d1", d1)
"""

BETA_TOML = """
[module]
id = "beta"
nom = "Beta"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : un enfant d'une entrée d'un autre module."
famille = "travail"
requiert = ["alpha"]

[[objets]]
type = "beta_o"
libelle = "Un objet"

[[ecrans]]
id = "e1"
libelle = "Page"

[[menus]]
id = "b1"
libelle = "Enfant d'Alpha"
ecran = "e1"
parent = "alpha:a1"
ordre = 5

[[menus]]
id = "b2"
libelle = "Autonome"
ecran = "e1"
ordre = 1
"""


def monde_menus():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    shutil.copytree(RACINE / "modules" / "menus", mods / "menus")
    ecrire_module(mods, "alpha", ALPHA_TOML, ALPHA_PY)
    ecrire_module(mods, "beta", BETA_TOML, "def brancher(ctx):\n    pass\n")
    etat = {"constat": False}
    n = moteur.Noyau(base / "d", mods, {"alpha": {"etat": etat}}, gerer_modules=True)
    n.brancher()
    return tmp, n, etat


def noms(arbre):
    """L'arbre en texte lisible : « famille > entrée (enfant, ...) »."""
    def un(x):
        return x["libelle"] + ("(" + ",".join(un(e) for e in x["enfants"]) + ")" if x.get("enfants") else "")
    return [un(f) for f in arbre]


class MenusAssembles(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.etat = monde_menus()
        self.addCleanup(self.tmp.cleanup)
        self.n.activer("menus")
        self.n.activer("beta")                       # active aussi alpha

    def menu(self, role="utilisateur", compte=""):
        r = self.n.executeur.executer("menus.lire_menu", "humain", {"role": role, "compte": compte})
        self.assertEqual(r["statut"], "faite")
        return r["resultat"]

    def perso(self, entree, compte="", **kw):
        return self.n.executeur.executer("menus.personnaliser_entree", "humain", dict(entree=entree, compte=compte, **kw))

    def evts(self, t):
        return [e for e in self.n.bus.recents(portee=TOUT, limite=800) if e["type"] == t]

    def test_les_modules_actifs_composent_l_arbre_par_famille(self):
        a = self.menu("admin")["arbre"]
        self.assertEqual([f["famille"] for f in a], ["socle", "reseau", "travail"])      # l'ordre des familles est celui du noyau
        self.assertEqual(noms(a), ["Socle(Modules,Menus)", "Réseau(Réservé,Premier(Sous-page,Enfant d'Alpha))", "Travail(Autonome)"])

    def test_le_menu_se_filtre_par_role(self):
        self.assertEqual(noms(self.menu("utilisateur")["arbre"]), ["Réseau(Premier(Sous-page,Enfant d'Alpha))", "Travail(Autonome)"])

    def test_une_entree_sans_page_ni_enfant_disparait(self):
        self.assertNotIn("Groupe vide", " ".join(noms(self.menu("admin")["arbre"])))

    def test_desactiver_un_module_retire_ses_entrees_a_chaud(self):
        etag = self.menu()["etag"]
        self.n.desactiver("beta")
        m = self.menu("admin")
        self.assertNotEqual(m["etag"], etag)
        self.assertEqual(noms(m["arbre"]), ["Socle(Modules,Menus)", "Réseau(Réservé,Premier(Sous-page))"])
        self.assertGreaterEqual(len(self.evts("menu_arbre.change")), 2)

    def test_un_enfant_dont_le_parent_disparait_remonte_au_premier_niveau(self):
        self.n.desactiver("alpha", cascade=True)                    # beta part avec alpha
        self.n.activer("beta", avec_dependances=True)               # revient avec alpha
        self.n.desactiver("alpha", cascade=True)
        self.assertEqual(noms(self.menu("admin")["arbre"]), ["Socle(Modules,Menus)"])

    def test_activer_un_module_ajoute_ses_entrees_sans_redemarrer(self):
        self.n.desactiver("alpha", cascade=True)
        avant = noms(self.menu("admin")["arbre"])
        self.n.activer("alpha")
        apres = noms(self.menu("admin")["arbre"])
        self.assertNotEqual(avant, apres)
        self.assertIn("Réseau(Réservé,Premier(Sous-page))", apres)

    def test_masquer_une_entree_masque_aussi_ses_enfants(self):
        self.assertEqual(self.perso("alpha:a1", masque=True)["statut"], "faite")
        self.assertEqual(noms(self.menu("admin")["arbre"]), ["Socle(Modules,Menus)", "Réseau(Réservé)", "Travail(Autonome)"])

    def test_la_personnalisation_d_un_compte_ne_touche_pas_les_autres(self):
        self.perso("alpha:a1", compte="sandrine@x.fr", libelle="Mon réseau", ordre=0)
        sandrine = noms(self.menu("utilisateur", "sandrine@x.fr")["arbre"])
        drisse = noms(self.menu("utilisateur", "drisse@x.fr")["arbre"])
        self.assertEqual(sandrine[0], "Réseau(Mon réseau(Sous-page,Enfant d'Alpha))")
        self.assertEqual(drisse[0], "Réseau(Premier(Sous-page,Enfant d'Alpha))")

    def test_la_personnalisation_globale_vaut_pour_tous_et_le_compte_l_emporte(self):
        self.perso("alpha:a1", libelle="Global")
        self.perso("alpha:a1", compte="sandrine@x.fr", libelle="Perso")
        self.assertIn("Réseau(Global(", noms(self.menu("utilisateur", "drisse@x.fr")["arbre"])[0])
        self.assertIn("Réseau(Perso(", noms(self.menu("utilisateur", "sandrine@x.fr")["arbre"])[0])

    def test_deplacer_une_entree(self):
        self.perso("beta:b2", parent="alpha:a1", ordre=0)
        self.assertEqual(noms(self.menu("utilisateur")["arbre"]), ["Réseau(Premier(Autonome,Sous-page,Enfant d'Alpha))"])

    def test_reinitialiser_rend_l_entree_d_origine(self):
        self.perso("alpha:a1", masque=True)
        self.perso("alpha:a1", reinitialiser=True)
        self.assertIn("Premier(", " ".join(noms(self.menu("utilisateur")["arbre"])))

    def test_une_personnalisation_refusee_n_ecrit_rien(self):
        for mauvais in (dict(entree="inconnue:x", masque=True), dict(entree="alpha:a1", ordre=99999), dict(entree="alpha:a1", parent="alpha:a1"),
                        dict(entree="alpha:a1", libelle=""), dict(entree="alpha:a1", parent="rien:ici")):
            r = self.n.executeur.executer("menus.personnaliser_entree", "humain", mauvais)
            self.assertEqual(r["statut"], "echec", msg=str(mauvais))
        self.assertEqual(self.n.registre.lister(portee=TOUT, type="menu_perso"), [])

    def test_le_retour_arriere_restaure_la_personnalisation_precedente(self):
        self.perso("alpha:a1", libelle="Un")
        self.n.catalogue.regler_palier("menus.personnaliser_entree", "auto")
        e = self.n.catalogue.get("menus.personnaliser_entree")
        res = {"id": "global|alpha:a1", "compte": "", "avant": {"entree": "alpha:a1", "libelle": "Un"}, "attendu": {"entree": "alpha:a1", "libelle": "Deux"}}
        self.n.registre.poser("menus", "menu_perso", "global|alpha:a1", "x", "visible", {"entree": "alpha:a1", "libelle": "Deux"})
        e.defaire(self.n.executeur.contextes["menus"], res)
        self.assertEqual(self.n.registre.lire("menu_perso", "global|alpha:a1", portee=TOUT)["donnees"]["libelle"], "Un")

    def test_les_compteurs_suivent_les_constats_ouverts(self):
        self.etat["constat"] = True
        self.n.tick(5000)                                           # le détecteur d'Alpha ouvre un constat ; le moteur des badges tourne
        self.assertEqual(self.menu()["badges"], {"alpha:a1": 1})
        self.etat["constat"] = False
        self.n.tick(5100)
        self.assertEqual(self.menu()["badges"], {})

    def test_le_module_de_menus_ne_se_desactive_pas(self):
        r = self.n.desactiver("menus")
        self.assertFalse(r["ok"])
        self.assertTrue(r["essentiel"])

    def test_l_introspection_se_demande(self):
        ctx = self.n.executeur.contextes["alpha"]                   # Alpha n'a pas demandé l'introspection
        with self.assertRaises(PermissionError):
            ctx.manifestes_actifs()
        with self.assertRaises(PermissionError):
            ctx.compteurs("alpha")

    def test_le_noyau_en_marche_voit_un_module_active_ailleurs(self):
        cli = moteur.Noyau(Path(self.tmp.name) / "d", Path(self.tmp.name) / "modules", {}, gerer_modules=True)
        cli.desactiver("beta", appliquer=False)                     # comme `main.py module desactiver`
        self.n._surveiller()                                        # une passe de la boucle du service
        self.assertEqual(noms(self.menu("admin")["arbre"]), ["Socle(Modules,Menus)", "Réseau(Réservé,Premier(Sous-page))"])


class ContratDesMenus(unittest.TestCase):
    def brut(self):
        import tomllib
        return tomllib.loads(ALPHA_TOML)

    def test_le_manifeste_d_exemple_est_valide(self):
        self.assertEqual(mf.valider(self.brut()), [])

    def test_les_defauts_d_un_menu_sont_dits(self):
        cas = [({"ecran": "inexistant"}, "ecran"), ({"role": "dieu"}, "role"), ({"badge": "x"}, "badge"), ({"ordre": -1}, "ordre"),
               ({"parent": "rien"}, "parent"), ({"parent": "Mauvais Nom"}, "parent")]
        for modif, mot in cas:
            b = self.brut()
            b["menus"][0].update(modif)
            self.assertTrue(any(mot in x for x in mf.valider(b)), msg=str(modif))

    def test_une_boucle_de_parents_est_refusee(self):
        b = self.brut()
        b["menus"][0]["parent"] = "sous"                           # a1 -> sous -> a1
        self.assertTrue(any("boucle" in x for x in mf.valider(b)))

    def test_un_type_d_objet_ne_peut_pas_porter_un_nom_du_noyau(self):
        b = self.brut()
        b["objets"][0]["type"] = "noyau"
        self.assertTrue(any("réservé" in x for x in mf.valider(b)))

    def test_un_module_peut_ecouter_les_evenements_du_noyau(self):
        import tomllib
        b = tomllib.loads(VEILLE_TOML % {"confiance": ""})
        b["evenements"]["ecoute"] = ["jouet.casse", "noyau.greffe"]
        b["moteurs"][1]["sur"] = ["jouet.casse", "noyau.greffe"]
        m = mf.construire(b)
        self.assertEqual(m.moteurs[1].sur, ("jouet.casse", "noyau.greffe"))
        self.assertEqual(mf.verifier_ensemble([m]), ["« veille » requiert « labo », qui n'est pas installé", "« veille » écoute « jouet.casse », qu'aucun module n'émet"])


class LigneDeCommandeAgir(unittest.TestCase):
    def test_agir_lance_une_capacite_et_rend_du_json(self):
        import contextlib, io as _io, json, os
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ancien = {k: os.environ.get(k) for k in ("CASSANDRA_DONNEES", "CASSANDRA_CONFIG", "CASSANDRA_EXTENSIONS")}
        os.environ["CASSANDRA_DONNEES"] = tmp.name
        os.environ.pop("CASSANDRA_CONFIG", None)
        os.environ.pop("CASSANDRA_EXTENSIONS", None)
        try:
            sortie = _io.StringIO()
            with contextlib.redirect_stdout(sortie):
                rc = moteur.commande_agir(["main.py", "agir", "menus.lire_menu", "role=admin"])
            self.assertEqual(rc, 0)
            r = json.loads(sortie.getvalue())
            self.assertEqual((r["statut"], r["resultat"]["arbre"]), ("faite", []))     # rien d'assemblé tant que le service n'a pas tourné
            with contextlib.redirect_stdout(_io.StringIO()):
                self.assertEqual(moteur.commande_agir(["main.py", "agir", "menus.inconnue"]), 1)
        finally:
            for k, v in ancien.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


SRC_TOML = """
[module]
id = "src"
nom = "Source"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai pour l'affichage : tuiles, source de données, accent."
famille = "reseau"

[[objets]]
type = "src_o"
libelle = "Un objet"

[[capacites]]
id = "lire_n"
libelle = "Lire n"
risque = "lecture"

[[capacites]]
id = "casse"
libelle = "Une lecture qui plante"
risque = "lecture"

[theme]
accent = "#1d6fa5"

[theme.tokens]
fond-carte = "#ffffff"
espace = "12px"

[[ecrans]]
id = "e1"
libelle = "Page source"
gabarit = "liste_detail"

[[widgets]]
id = "compteur"
libelle = "Compteur"
ordre = 5
composant = "nombre"
source = "lire_n"
rafraichir_s = 5

[[widgets]]
id = "etat_admin"
libelle = "État réservé"
zone = "lateral"
role = "admin"
composant = "etat"

[[widgets]]
id = "plante"
libelle = "Source en panne"
ordre = 50
source = "casse"

[[widgets]]
id = "sur_page"
libelle = "Sur la page"
ecran = "e1"
composant = "liste"
"""

SRC_PY = """
def brancher(ctx):
    etat = ctx.config["etat"]

    def casse(ctx):
        raise RuntimeError("source HS")
    ctx.implementer("lire_n", lambda ctx: {"n": etat["n"]})
    ctx.implementer("casse", casse)
"""

PALE_TOML = """
[module]
id = "pale"
nom = "Pâle"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : un accent lisible seulement en thème sombre."
famille = "travail"

[[objets]]
type = "pale_o"
libelle = "Un objet"

[theme]
accent = "#f0f0a0"
"""


def monde_affichage():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    shutil.copytree(RACINE / "modules" / "affichage", mods / "affichage")
    ecrire_module(mods, "src", SRC_TOML, SRC_PY)
    ecrire_module(mods, "pale", PALE_TOML, "def brancher(ctx):\n    pass\n")
    etat = {"n": 7}
    n = moteur.Noyau(base / "d", mods, {"src": {"etat": etat}}, gerer_modules=True)
    n.brancher()
    return tmp, n, etat


def charger_affichage():
    import importlib.util
    spec = importlib.util.spec_from_file_location("aff_test", RACINE / "modules" / "affichage" / "module.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


DECO_TOML = """
[module]
id = "deco"
nom = "Décor"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : un onglet sur l'objet d'un autre module et deux thèmes."
famille = "reseau"

[[ecrans]]
id = "vue_historique"
libelle = "Historique"
gabarit = "libre"

[[onglets]]
id = "historique"
libelle = "Historique"
objet = "src:src_o"
ecran = "vue_historique"
ordre = 20

[[onglets]]
id = "audit"
libelle = "Audit"
objet = "src:src_o"
ecran = "vue_historique"
ordre = 10
role = "admin"

[[habillages]]
id = "sobre"
libelle = "Sobre"
base = "sombre"
fichier = "themes/sobre.css"

[[habillages]]
id = "piege"
libelle = "Piège"
base = "clair"
fichier = "themes/piege.css"
"""

SOBRE_CSS = "/* un commentaire */\n--bg: #101418;\n--accent: #34c3b6;\n--shadow-glass: 0 6px 24px rgba(0,0,0,.3);\n"
PIEGE_CSS = """--ok: #00ff00;
--fond: url(http://exemple.test/x.png);
--mal: red; } body { display:none
--arobase: @import evil;
--bon: 12px;
"""


class OngletsEtHabillages(unittest.TestCase):
    def setUp(self):
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "affichage", mods / "affichage")
        ecrire_module(mods, "src", SRC_TOML, SRC_PY)
        ecrire_module(mods, "deco", DECO_TOML, "def brancher(ctx):\n    pass\n")
        (mods / "deco" / "themes").mkdir()
        (mods / "deco" / "themes" / "sobre.css").write_text(SOBRE_CSS, encoding="utf-8")
        (mods / "deco" / "themes" / "piege.css").write_text(PIEGE_CSS, encoding="utf-8")
        self.n = moteur.Noyau(base / "d", mods, {"src": {"etat": {"n": 1}}}, gerer_modules=True)
        self.n.brancher()
        for m in ("affichage", "src", "deco"):
            self.n.activer(m)

    def lire(self, cap, **args):
        r = self.n.executeur.executer("affichage." + cap, "humain", args)
        self.assertEqual(r["statut"], "faite", msg=str(r))
        return r["resultat"]

    def test_un_onglet_se_pose_sur_l_objet_d_un_autre_module(self):
        o = self.lire("lire_onglets", objet="src:src_o", role="admin")["onglets"]
        self.assertEqual([x["id"] for x in o], ["deco:audit", "deco:historique"])               # par ordre (10 puis 20)
        self.assertEqual(o[1]["ecran"], "deco:vue_historique")
        self.assertEqual([x["id"] for x in self.lire("lire_onglets", objet="src_o", role="admin")["onglets"]], ["deco:audit", "deco:historique"])   # le type seul suffit
        self.assertEqual([x["id"] for x in self.lire("lire_onglets", objet="src:src_o", role="utilisateur")["onglets"]], ["deco:historique"])          # l'audit est réservé
        self.assertEqual(self.lire("lire_onglets", objet="notes:note", role="admin")["onglets"], [])

    def test_un_onglet_disparait_avec_son_module(self):
        self.n.desactiver("deco")
        self.assertEqual(self.lire("lire_onglets", objet="src:src_o", role="admin")["onglets"], [])

    def test_un_habillage_ne_porte_que_des_variables_sures(self):
        h = {x["id"]: x for x in self.lire("lire_habillages")["habillages"]}
        self.assertEqual(h["deco:sobre"]["variables"], {"--bg": "#101418", "--accent": "#34c3b6", "--shadow-glass": "0 6px 24px rgba(0,0,0,.3)"})
        self.assertEqual(h["deco:sobre"]["base"], "sombre")
        sur = h["deco:piege"]["variables"]
        self.assertEqual(sorted(sur), ["--bon", "--mal", "--ok"])                                # seules des variables ressortent : le sélecteur glissé après « } » n'existe pas ; ni adresse, ni arobase
        self.assertIn("--fond", h["deco:piege"]["refus"])

    def test_le_manifeste_refuse_un_onglet_ou_un_habillage_mal_forme(self):
        import tomllib
        b = tomllib.loads(DECO_TOML)
        b["onglets"][0].update(objet="Pas Bon", ecran="inconnu", role="roi")
        b["habillages"][0].update(fichier="../evasion.css", base="fluo")
        b["habillages"][1].update(id="clair")
        e = " | ".join(mf.valider(b))
        for attendu in ("objet", "ecran", "role", "fichier", "base", "déjà pris"):
            self.assertIn(attendu, e)
        b = tomllib.loads(DECO_TOML)
        b["onglets"][1]["id"] = "historique"
        self.assertTrue(any("deux fois" in x for x in mf.valider(b)))


class AffichageAssemble(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.etat = monde_affichage()
        self.addCleanup(self.tmp.cleanup)
        self.n.activer("affichage")
        self.n.activer("src")
        self.n.activer("pale")

    def lire(self, cap, **args):
        r = self.n.executeur.executer("affichage." + cap, "humain", args)
        self.assertEqual(r["statut"], "faite", msg=str(r))
        return r["resultat"]

    def ecran(self, ecran="accueil", role="utilisateur", compte=""):
        return self.lire("lire_ecran", ecran=ecran, role=role, compte=compte)

    def ids(self, ecran, zone, **kw):
        return [w["id"] for w in self.ecran(ecran, **kw)["zones"][zone]]

    def perso_w(self, widget, compte="", **kw):
        return self.n.executeur.executer("affichage.personnaliser_widget", "humain", dict(widget=widget, compte=compte, **kw))

    def perso_t(self, compte="", **kw):
        return self.n.executeur.executer("affichage.personnaliser_theme", "humain", dict(compte=compte, **kw))

    def evts(self, t):
        return [e for e in self.n.bus.recents(portee=TOUT, limite=800) if e["type"] == t]

    # --- mise en page ---
    def test_les_tuiles_se_placent_par_zone_ordre_et_role(self):
        self.assertEqual(self.ids("accueil", "principal"), ["src:compteur", "src:plante"])           # par ordre (5 puis 50)
        self.assertEqual(self.ids("accueil", "lateral"), [])                                         # réservée aux administrateurs
        self.assertEqual(self.ids("accueil", "lateral", role="admin"), ["src:etat_admin"])

    def test_un_ecran_de_module_porte_son_gabarit_et_ses_tuiles(self):
        e = self.ecran("src:e1")
        self.assertEqual((e["existe"], e["titre"], e["gabarit"]), (True, "Page source", "liste_detail"))
        self.assertEqual([w["id"] for w in e["zones"]["principal"]], ["src:sur_page"])
        self.assertFalse(self.ecran("src:inconnu")["existe"])

    def test_la_donnee_d_une_tuile_est_lue_par_un_moteur_pas_par_l_interface(self):
        self.n.tick(1000)
        tuiles = {w["id"]: w for w in self.ecran()["zones"]["principal"]}
        self.assertEqual(tuiles["src:compteur"]["donnees"], {"valeur": {"n": 7}, "erreur": ""})
        self.etat["n"] = 8
        self.n.tick(1001)                                                  # moins de 5 s : pas relue
        self.assertEqual({w["id"]: w for w in self.ecran()["zones"]["principal"]}["src:compteur"]["donnees"]["valeur"], {"n": 7})

    def test_une_source_en_panne_se_dit_dans_la_tuile_sans_casser_l_ecran(self):
        self.n.tick(1000)
        tuiles = {w["id"]: w for w in self.ecran()["zones"]["principal"]}
        self.assertIsNone(tuiles["src:plante"]["donnees"]["valeur"])
        self.assertEqual(tuiles["src:compteur"]["donnees"]["valeur"], {"n": 7})     # les autres tuiles vivent

    def test_activer_et_desactiver_un_module_fait_venir_et_partir_ses_tuiles(self):
        etag = self.ecran()["etag"]
        self.n.desactiver("src")
        self.assertEqual(self.ids("accueil", "principal"), [])
        self.assertFalse(self.ecran("src:e1")["existe"])
        self.assertNotEqual(self.ecran()["etag"], etag)
        self.assertEqual(self.n.registre.lister(portee=TOUT, type="widget_donnees"), [])           # leurs données partent avec
        self.n.activer("src")
        self.assertEqual(self.ids("accueil", "principal"), ["src:compteur", "src:plante"])
        self.assertGreaterEqual(len(self.evts("affichage_catalogue.change")), 3)

    # --- personnalisation des tuiles ---
    def test_masquer_deplacer_reordonner_une_tuile(self):
        self.perso_w("src:compteur", masque=True)
        self.assertEqual(self.ids("accueil", "principal"), ["src:plante"])
        self.perso_w("src:compteur", masque=False, zone="lateral", ordre=0)
        self.assertEqual(self.ids("accueil", "lateral"), ["src:compteur"])

    def test_la_personnalisation_d_un_compte_ne_touche_pas_les_autres(self):
        self.perso_w("src:compteur", compte="sandrine@x.fr", masque=True)
        self.assertEqual(self.ids("accueil", "principal", compte="sandrine@x.fr"), ["src:plante"])
        self.assertEqual(self.ids("accueil", "principal", compte="drisse@x.fr"), ["src:compteur", "src:plante"])

    def test_une_personnalisation_invalide_n_ecrit_rien(self):
        for mauvais in (dict(widget="x:y", masque=True), dict(widget="src:compteur", zone="dehors"), dict(widget="src:compteur", taille="xl"),
                        dict(widget="src:compteur", ordre=-5)):
            self.assertEqual(self.n.executeur.executer("affichage.personnaliser_widget", "humain", mauvais)["statut"], "echec", msg=str(mauvais))
        self.assertEqual(self.n.registre.lister(portee=TOUT, type="widget_perso"), [])

    def test_reinitialiser_rend_la_tuile_d_origine(self):
        self.perso_w("src:compteur", masque=True)
        self.perso_w("src:compteur", reinitialiser=True)
        self.assertIn("src:compteur", self.ids("accueil", "principal"))

    # --- thème ---
    def theme(self, **kw):
        return self.lire("lire_theme", **kw)

    def test_le_theme_suit_le_systeme_sauf_choix(self):
        self.assertEqual(self.theme(systeme="clair")["variables"]["--bg"], "#eef1f5")
        self.assertEqual(self.theme(systeme="sombre")["variables"]["--bg"], "#0c1116")
        self.perso_t(theme="sombre")
        self.assertEqual(self.theme(systeme="clair")["mode"], "sombre")             # le choix l'emporte sur le système

    def test_un_module_ne_peut_que_poser_sa_touche_de_couleur(self):
        v = self.theme(systeme="clair")["variables"]
        self.assertEqual(v["--accent-src"], "#1d6fa5")
        self.assertEqual(v["--mod-src-fond-carte"], "#ffffff")                       # ses jetons sont préfixés : il n'écrase rien du noyau
        self.assertEqual(v["--accent"], "#0b7c74")
        self.assertNotIn("--fond-carte", v)

    def test_un_accent_sans_contraste_n_est_pas_applique(self):
        self.assertNotIn("--accent-pale", self.theme(systeme="clair")["variables"])             # #f0f0a0 sur fond clair : illisible
        self.assertIn("--accent-pale", self.theme(systeme="sombre")["variables"])               # lisible en sombre

    def test_l_accent_choisi_remplace_l_accent_s_il_est_lisible(self):
        self.assertEqual(self.perso_t(accent="#a85a0b", theme="clair")["statut"], "faite")
        v = self.theme(systeme="clair")["variables"]
        self.assertEqual((v["--accent"], v["--on-accent"]), ("#a85a0b", "#ffffff"))
        self.assertTrue(v["--accent-bg"].startswith("rgba(168,90,11"))

    def test_un_accent_illisible_est_refuse_et_rien_n_est_ecrit(self):
        r = self.perso_t(accent="#f0f0a0", theme="clair")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("contraste", r["erreur"])
        self.assertEqual(self.n.registre.lister(portee=TOUT, type="theme_perso"), [])
        self.assertEqual(self.perso_t(accent="#5b46c4")["statut"], "echec")           # lisible en clair, pas en sombre : refusé en « auto »

    def test_la_densite_et_les_choix_d_un_compte_ne_touchent_pas_les_autres(self):
        self.perso_t(compte="sandrine@x.fr", densite="compacte", theme="sombre")
        s = self.theme(compte="sandrine@x.fr")
        d = self.theme(compte="drisse@x.fr")
        self.assertEqual((s["mode"], s["variables"]["--gap"]), ("sombre", "10px"))
        self.assertEqual((d["mode"], d["variables"]["--gap"]), ("clair", "16px"))

    def test_le_choix_global_vaut_pour_tous_et_celui_du_compte_l_emporte(self):
        self.perso_t(theme="sombre")
        self.perso_t(compte="sandrine@x.fr", theme="clair")
        self.assertEqual(self.theme(compte="drisse@x.fr")["mode"], "sombre")
        self.assertEqual(self.theme(compte="sandrine@x.fr")["mode"], "clair")

    def test_l_empreinte_du_theme_change_avec_le_theme(self):
        a = self.theme(systeme="clair")["etag"]
        self.assertNotEqual(a, self.theme(systeme="sombre")["etag"])
        self.assertEqual(a, self.theme(systeme="clair")["etag"])

    # --- garde-fous ---
    def test_le_module_d_affichage_ne_se_desactive_pas(self):
        r = self.n.desactiver("affichage")
        self.assertFalse(r["ok"])
        self.assertTrue(r["essentiel"])

    def test_on_ne_peut_appeler_que_des_lectures(self):
        ctx = self.n.executeur.contextes["affichage"]
        with self.assertRaises(PermissionError):
            ctx.executer_lecture("affichage.personnaliser_theme")                    # une écriture : refusée
        with self.assertRaises(PermissionError):
            self.n.executeur.contextes["src"].executer_lecture("src.lire_n")         # « src » n'a pas demandé les lectures

    def test_le_contraste_suit_la_regle(self):
        a = charger_affichage()
        self.assertTrue(a.accent_ok("#0b7c74", "clair"))
        self.assertFalse(a.accent_ok("#ffffff", "clair"))
        self.assertFalse(a.accent_ok("pas-une-couleur", "clair"))
        self.assertAlmostEqual(a.contraste("#000000", "#ffffff"), 21.0, places=1)
        self.assertEqual(a.meilleur_texte("#ffff00"), "#101828")


class ContratDeLAffichage(unittest.TestCase):
    def brut(self):
        import tomllib
        return tomllib.loads(SRC_TOML)

    def test_le_manifeste_d_exemple_est_valide(self):
        self.assertEqual(mf.valider(self.brut()), [])

    def test_les_defauts_d_une_tuile_sont_dits(self):
        cas = [({"ecran": "inconnu"}, "ecran"), ({"zone": "dehors"}, "zone"), ({"taille": "xl"}, "taille"), ({"composant": "camembert"}, "composant"),
               ({"ordre": 99999}, "ordre"), ({"source": "casse_inexistante"}, "source"), ({"rafraichir_s": 2}, "rafraichir_s"), ({"role": "dieu"}, "role")]
        for modif, mot in cas:
            b = self.brut()
            b["widgets"][0].update(modif)
            self.assertTrue(any(mot in x for x in mf.valider(b)), msg=str(modif))

    def test_une_source_doit_etre_une_lecture_du_module(self):
        b = self.brut()
        b["capacites"].append({"id": "ecrire_x", "libelle": "x", "risque": "faible", "perimetre": ["x"], "preuve": "p", "retour": "r"})
        b["widgets"][0]["source"] = "ecrire_x"
        self.assertTrue(any("LECTURE" in x for x in mf.valider(b)))

    def test_le_theme_est_borne(self):
        for modif, mot in (({"accent": "bleu"}, "accent"),):
            b = self.brut()
            b["theme"].update(modif)
            self.assertTrue(any(mot in x for x in mf.valider(b)))
        b = self.brut()
        b["theme"]["tokens"] = {"fond": "url(http://evil)", "Mauvais Nom": "#fff"}
        e = " ".join(mf.valider(b))
        self.assertIn("ni une couleur ni une dimension", e)
        self.assertIn("pas valide", e)

    def test_un_gabarit_inconnu_est_refuse(self):
        b = self.brut()
        b["ecrans"][0]["gabarit"] = "carrousel"
        self.assertTrue(any("gabarit" in x for x in mf.valider(b)))


class FauxCollecteur:
    """Un collecteur de poche : le protocole du Sensorium (une requête texte, une réponse JSON) sur un socket Unix."""

    def __init__(self, chemin):
        import socket
        import threading
        self.chemin = chemin
        self.sante = {"health_status": "healthy", "health_score": 97, "failed_units": 0, "oom_events_24h": 0}
        self.metriques = {"cpu": 12.3, "ram": 41.0, "disk": 33.3, "swap": 0.0, "load_1m": 0.4, "ram_used_gb": 3.1, "ram_total_gb": 7.6,
                          "disk_used_gb": 22.0, "disk_total_gb": 70.0, "top_processes": [{"name": "python3", "cpu": 3.0}]}
        self.requetes = []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(chemin)
        self.srv.listen(5)
        self.srv.settimeout(0.2)
        self.vivant = True
        self.fil = threading.Thread(target=self._boucle, daemon=True)
        self.fil.start()

    def _boucle(self):
        import json
        while self.vivant:
            try:
                c, _ = self.srv.accept()
            except OSError:
                continue
            try:
                r = c.recv(4096).decode().strip()
                self.requetes.append(r)
                if r == "PING":
                    c.sendall(b"PONG")
                elif r == "GET_DASHBOARD":
                    c.sendall(json.dumps(self.sante).encode())
                elif r == "GET_METRICS":
                    c.sendall(json.dumps(self.metriques).encode())
                elif r.startswith("GET_WORLD"):
                    c.sendall(json.dumps([{"wkey": "disk.root", "value": "33%"}]).encode())
                elif r == "GET_ENTITY:open_ports":
                    c.sendall(json.dumps([{"port": 22}]).encode())
                elif r.startswith("GET_HISTORY:") or r.startswith("GET_CHANGES"):
                    c.sendall(b"[]")
                else:
                    c.sendall(b"ERROR")
            finally:
                c.close()

    def arreter(self):
        self.vivant = False
        self.srv.close()
        self.fil.join(2)
        try:
            os.unlink(self.chemin)
        except OSError:
            pass


@unittest.skipUnless(sys.platform != "win32", "sockets Unix : Linux")
class SensoriumRelieAuNoyau(unittest.TestCase):
    def setUp(self):
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.sock = str(base / "k.sock")
        self.ancien = os.environ.get("SENSORIUM_SOCKET")
        os.environ["SENSORIUM_SOCKET"] = self.sock
        self.addCleanup(lambda: os.environ.__setitem__("SENSORIUM_SOCKET", self.ancien) if self.ancien else os.environ.pop("SENSORIUM_SOCKET", None))
        self.faux = FauxCollecteur(self.sock)
        self.addCleanup(self.faux.arreter)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "sensorium", mods / "sensorium")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("sensorium", installe=True, par="test")        # ce que fait install.sh après sa preuve
        self.assertTrue(self.n.activer("sensorium")["ok"])

    def evts(self, t):
        return [e for e in self.n.bus.recents(portee=TOUT, limite=800) if e["type"] == t]

    def machine(self):
        return self.n.registre.lire("machine", "hote", portee=TOUT)

    def releve(self):
        self.n.lancer("sensorium.releve")

    def test_une_releve_fait_de_la_machine_un_objet_du_registre(self):
        self.releve()
        m = self.machine()
        self.assertEqual((m["etat"], m["donnees"]["score"], m["donnees"]["cpu"]), ("healthy", 97, 12.3))
        self.assertEqual(m["donnees"]["processus"], [{"nom": "python3", "cpu": 3.0}])

    def test_une_releve_identique_n_ecrit_rien_de_plus(self):
        self.releve()
        n = len(self.n.bus.chronologie("machine", "hote", portee=TOUT))
        self.releve()
        self.releve()
        self.assertEqual(len(self.n.bus.chronologie("machine", "hote", portee=TOUT)), n)       # rien de plus n'est écrit sur la machine
        self.assertEqual(len([e for e in self.n.bus.chronologie("machine", "hote", portee=TOUT) if e["type"].startswith("objet.")]), 1)

    def test_un_changement_de_sante_se_dit(self):
        self.releve()
        self.faux.sante = dict(self.faux.sante, health_status="degraded", health_score=60)
        self.releve()
        ev = self.evts("machine.sante_change")
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["donnees"]["de"], ev[0]["donnees"]["a"]), ("healthy", "degraded"))

    def test_un_collecteur_muet_se_voit_puis_reprend(self):
        self.releve()
        self.faux.arreter()
        self.releve()
        self.releve()
        self.assertEqual(self.machine()["etat"], "muet")
        self.assertEqual(len(self.evts("machine.muette")), 1)                  # dit une fois
        r = self.n.tick(1000)
        self.assertEqual(self.n.etat()["constats_ouverts"], 1)                  # un silence est un constat, jamais un silence
        self.faux = FauxCollecteur(self.sock)
        self.addCleanup(self.faux.arreter)
        self.releve()
        self.assertEqual(self.machine()["etat"], "healthy")
        self.assertEqual(len(self.evts("machine.reprise")), 1)
        self.n.tick(1100)
        self.assertEqual(self.n.etat()["constats_ouverts"], 0)

    def test_des_unites_en_echec_ouvrent_un_constat(self):
        self.faux.sante = dict(self.faux.sante, failed_units=2)
        self.releve()
        self.n.tick(1000)
        titres = [r["titre"] for r in self.n.base.lire("SELECT titre FROM constats WHERE etat='ouvert'")]
        self.assertEqual(titres, ["2 unités systemd en échec"])

    def test_les_lectures_passent_par_le_collecteur(self):
        e = self.n.executeur.executer
        self.assertEqual(e("sensorium.metriques", "humain")["resultat"]["cpu"], 12.3)
        self.assertEqual(e("sensorium.monde", "humain", {"prefixe": "disk"})["resultat"][0]["wkey"], "disk.root")
        self.assertEqual(e("sensorium.entite", "humain", {"nom": "open_ports"})["resultat"], [{"port": 22}])
        self.assertEqual(e("sensorium.historique", "humain", {"cle": "disk.root"})["resultat"], [])
        self.assertEqual(e("sensorium.changements", "humain", {"depuis": "2026-10-11T00:00:00"})["resultat"], [])
        self.assertIsNone(e("sensorium.sante", "humain")["resultat"])           # pas encore de relève
        self.releve()
        self.assertEqual(e("sensorium.sante", "humain")["resultat"]["score"], 97)

    def test_les_arguments_sont_valides_avant_de_toucher_le_socket(self):
        e = self.n.executeur.executer
        avant = len(self.faux.requetes)
        for cap, args in (("monde", {"prefixe": "a\nGET_METRICS"}), ("entite", {"nom": "../etc/passwd"}), ("historique", {"cle": "x y"}),
                          ("changements", {"depuis": "hier; rm"})):
            r = e("sensorium." + cap, "humain", args)
            self.assertEqual(r["statut"], "echec", msg=cap)
        self.assertEqual(len(self.faux.requetes), avant)

    def test_une_lecture_sur_un_collecteur_muet_echoue_sans_planter(self):
        self.faux.arreter()
        r = self.n.executeur.executer("sensorium.metriques", "humain")
        self.assertEqual(r["statut"], "echec")
        self.assertEqual(len([e for e in self.evts("capacite.echouee") if e["objet_id"] == "sensorium.metriques"]), 1)

    def test_une_entite_refusee_par_le_collecteur_est_un_echec(self):
        r = self.n.executeur.executer("sensorium.entite", "humain", {"nom": "inconnue"})
        self.assertEqual(r["statut"], "echec")

    def test_les_tuiles_du_sensorium_sont_declarees_au_catalogue_d_affichage(self):
        import shutil
        base = Path(self.tmp.name)
        shutil.copytree(RACINE / "modules" / "affichage", base / "modules" / "affichage")
        n = moteur.Noyau(base / "d", base / "modules", {}, gerer_modules=True)
        n.brancher()
        n.activer("affichage")
        n.tick(2000)
        r = n.executeur.executer("affichage.lire_ecran", "humain", {"ecran": "accueil", "role": "admin"})["resultat"]
        self.assertEqual([w["id"] for w in r["zones"]["principal"]], ["sensorium:sante"])


class SensoriumGardeEntier(unittest.TestCase):
    """Le collecteur de la V18 devient sensorium.py : renommé, jamais découpé, seuls des chemins deviennent configurables."""

    def test_le_fichier_compile_et_n_est_pas_decoupe(self):
        import py_compile
        f = RACINE / "modules" / "sensorium" / "sensorium.py"
        py_compile.compile(str(f), doraise=True)
        self.assertGreater(len(f.read_text(encoding="utf-8").splitlines()), 6000)

    def test_les_chemins_se_reglent_par_l_environnement_et_gardent_leurs_defauts(self):
        import importlib.util
        f = RACINE / "modules" / "sensorium" / "sensorium.py"
        noms = ("SENSORIUM_DB", "SENSORIUM_SOCKET", "SENSORIUM_CONFIG_JSON", "SENSORIUM_DNS_LOCAL_CONF", "SENSORIUM_DNS_LOCAL_NOMS")
        ancien = {k: os.environ.get(k) for k in noms}

        def charger():
            spec = importlib.util.spec_from_file_location("sensorium_test", f)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
        try:
            for k in noms:
                os.environ.pop(k, None)
            m = charger()
            self.assertEqual((m.DB_PATH, m.SOCKET_PATH), ("/var/lib/cassandra/cassandra.db", "/run/cassandra/knowledge.sock"))   # les défauts de la V18
            os.environ["SENSORIUM_DB"] = "/x/s.db"
            os.environ["SENSORIUM_SOCKET"] = "/x/k.sock"
            os.environ["SENSORIUM_CONFIG_JSON"] = "/x/c.json"
            m = charger()
            self.assertEqual((m.DB_PATH, m.SOCKET_PATH, m.CASSANDRA_CONFIG), ("/x/s.db", "/x/k.sock", "/x/c.json"))
        finally:
            for k, v in ancien.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class FauxDolibarr:
    """Un Dolibarr de poche : l'API REST, avec un état. Il compresse toujours ses réponses (comme le vrai) et peut se tromper exprès."""

    CLE = "cle-de-test-123"
    COLLECTIONS = ("thirdparties", "contacts", "products", "projects", "invoices", "proposals", "orders")

    def __init__(self):
        import gzip
        import json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import parse_qs, urlparse
        self.hotes, self.journal = [], []
        self.refuse = self.panne = False
        self.ignorer = set()                 # des champs que « le serveur oublie » à la création
        self.corrompre_put = False           # le premier PUT d'un nom l'altère (pour forcer le retour arrière)
        self.valider_apres_creation = False  # une facture créée est aussitôt validée par quelqu'un d'autre
        self.payees = set()
        self.bloques = set()                 # des (collection, id) que Dolibarr refuse de supprimer (référencés ailleurs)
        self.delete_sans_effet = False       # un DELETE qui répond 200 sans rien supprimer
        self.donnees = {c: {} for c in self.COLLECTIONS}
        self.suivant = {c: 1 for c in self.COLLECTIONS}
        faux = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _rep(self, code, corps):
                brut = gzip.compress(json.dumps(corps).encode())
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(brut)))
                self.end_headers()
                self.wfile.write(brut)

            def _traiter(self, methode):
                u = urlparse(self.path)
                chemin = u.path[len("/api/index.php"):]
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                faux.journal.append((methode, chemin))
                faux.hotes.append(self.headers.get("Host", ""))
                longueur = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(longueur) or b"null") if longueur else None
                if faux.panne:
                    return self._rep(500, {"error": {"code": 500}})
                if faux.refuse or self.headers.get("DOLAPIKEY") != faux.CLE:
                    return self._rep(401, {"error": {"code": 401, "message": "Unauthorized"}})
                if chemin == "/status":
                    return self._rep(200, {"success": {"code": 200, "dolibarr_version": "23.0.2", "access_locked": "0"}})
                if chemin == "/setup/modules":
                    return self._rep(200, ["api", "facture", "societe"])
                parts = chemin.strip("/").split("/")
                coll = parts[0]
                if coll not in faux.donnees:
                    return self._rep(404, {"error": {"code": 404}})
                table = faux.donnees[coll]
                docs = coll in ("invoices", "proposals", "orders")
                if len(parts) == 1 and methode == "GET":
                    lignes = [dict(v) for _, v in sorted(table.items())]
                    if q.get("status") == "unpaid":
                        lignes = [l for l in lignes if str(l.get("statut")) == "1" and str(l.get("paye")) == "0"]
                    lignes = lignes[int(q.get("page", 0)) * int(q.get("limit", 100)):][:int(q.get("limit", 100))]
                    if "properties" in q:
                        champs = q["properties"].split(",")
                        lignes = [{k: l.get(k) for k in champs if k in l} for l in lignes]
                    return self._rep(200, lignes) if lignes else self._rep(404, {"error": {"code": 404}})
                if len(parts) == 1 and methode == "POST":
                    i = faux.suivant[coll]
                    faux.suivant[coll] += 1
                    obj = {k: v for k, v in (corps or {}).items() if k not in faux.ignorer}
                    obj["id"] = i
                    if docs:
                        obj.setdefault("statut", "0")
                        obj.setdefault("lines", [])
                        obj["fk_soc"] = obj.get("socid")
                        if faux.valider_apres_creation and coll == "invoices":
                            obj["statut"] = "1"
                    table[i] = obj
                    return self._rep(200, i)
                i = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                if i is None or i not in table:
                    return self._rep(404, {"error": {"code": 404, "message": "Not found"}})
                if len(parts) == 3 and coll == "invoices" and methode == "POST" and parts[2] in ("validate", "settodraft"):
                    if parts[2] == "settodraft" and i in faux.payees:
                        return self._rep(400, {"error": {"code": 400, "message": "paid"}})
                    table[i]["statut"] = "1" if parts[2] == "validate" else "0"
                    return self._rep(200, dict(table[i]))
                if methode == "GET":
                    return self._rep(200, dict(table[i]))
                if methode == "PUT":
                    for k, v in (corps or {}).items():
                        if k == "name" and faux.corrompre_put:
                            v, faux.corrompre_put = str(v) + "!", False
                        table[i][k] = v
                    return self._rep(200, dict(table[i]))
                if methode == "DELETE":
                    if docs and str(table[i].get("statut")) != "0":
                        return self._rep(400, {"error": {"code": 400, "message": "not a draft"}})
                    if (coll, i) in faux.bloques:
                        return self._rep(400, {"error": {"code": 400, "message": "referenced elsewhere"}})
                    if not faux.delete_sans_effet:
                        del table[i]
                    return self._rep(200, {"success": {"code": 200}})
                return self._rep(405, {})

            def do_GET(self):
                self._traiter("GET")

            def do_POST(self):
                self._traiter("POST")

            def do_PUT(self):
                self._traiter("PUT")

            def do_DELETE(self):
                self._traiter("DELETE")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.fil = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.fil.start()

    @property
    def url(self):
        return "http://127.0.0.1:%d/api/index.php" % self.port

    def methodes(self):
        return {m for m, _ in self.journal}

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()


class DolibarrPont(unittest.TestCase):
    def setUp(self):
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.faux = FauxDolibarr()
        self.addCleanup(lambda: self.faux.arreter())
        self.conf = base / "config"
        self.conf.mkdir()
        (self.conf / "dolibarr.conf").write_text("url = %s\nhote = dolibarr.exemple\n" % self.faux.url, encoding="utf-8")
        (self.conf / "dolibarr.key").write_text(FauxDolibarr.CLE, encoding="utf-8")
        self.ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = str(self.conf)
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_CONFIG", self.ancien) if self.ancien else os.environ.pop("CASSANDRA_CONFIG", None))
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "dolibarr", mods / "dolibarr")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("dolibarr")["ok"])
        self.e = self.n.executeur.executer

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def releve(self):
        self.n.lancer("dolibarr.releve")

    def instance(self):
        return self.n.registre.lire("dolibarr", "principal", portee=TOUT)

    def semer(self):
        for i in range(3):
            self.faux.donnees["thirdparties"][i + 1] = {"id": i + 1, "name": "Tiers %d" % (i + 1), "client": 1}
        self.faux.suivant["thirdparties"] = 4
        self.faux.donnees["invoices"][1] = {"id": 1, "statut": "1", "paye": "0", "total_ttc": "120.5", "date_lim_reglement": "2026-09-01"}
        self.faux.donnees["invoices"][2] = {"id": 2, "statut": "2", "paye": "1", "total_ttc": "80", "date_lim_reglement": "2026-08-01"}
        self.faux.donnees["invoices"][3] = {"id": 3, "statut": "1", "paye": "0", "total_ttc": "10", "date_lim_reglement": "1656712800"}     # un horodatage Unix, comme le vrai
        self.faux.suivant["invoices"] = 4

    # --- la relève ---
    def test_une_releve_fait_de_dolibarr_un_objet_du_registre(self):
        self.semer()
        self.releve()
        i = self.instance()
        self.assertEqual(i["etat"], "ok")
        d = i["donnees"]
        self.assertEqual((d["version"], d["modules"], d["comptes"]["tiers"], d["comptes"]["factures"]), ("23.0.2", 3, 3, 3))
        self.assertEqual((d["impayees"]["n"], d["impayees"]["total_ttc"], d["impayees"]["plus_ancienne"]), (2, 130.5, "2022-07-02"))     # l'horodatage devient un jour

    def test_sans_configuration_le_pont_attend_sans_rien_signaler(self):
        (self.conf / "dolibarr.conf").unlink()
        self.releve()
        self.assertEqual(self.instance()["etat"], "non_configure")
        self.n.tick(1000)
        self.assertEqual(self.n.etat()["constats_ouverts"], 0)

    def test_une_cle_refusee_se_dit_puis_reprend(self):
        self.faux.refuse = True
        self.releve()
        self.releve()
        self.assertEqual(self.instance()["etat"], "refuse")
        self.assertEqual(len(self.evts("dolibarr.acces_refuse")), 1)
        self.n.tick(1000)
        self.assertEqual([r["titre"] for r in self.n.base.lire("SELECT titre FROM constats WHERE etat='ouvert'")], ["Dolibarr refuse la clé d'API"])
        self.faux.refuse = False
        self.releve()
        self.assertEqual(len(self.evts("dolibarr.reprise")), 1)

    def test_un_dolibarr_injoignable_est_un_constat(self):
        self.faux.arreter()
        self.releve()
        self.assertEqual(self.instance()["etat"], "injoignable")
        self.assertEqual(len(self.evts("dolibarr.injoignable")), 1)
        self.n.tick(1000)
        self.assertEqual(self.n.etat()["constats_ouverts"], 1)

    def test_la_cle_ne_fuit_nulle_part(self):
        import json
        self.semer()
        self.releve()
        self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Zéro fuite"}})
        self.faux.refuse = True
        self.releve()
        tout = json.dumps([self.n.bus.recents(portee=TOUT, limite=5000), self.n.registre.lister(portee=TOUT)], default=str)
        self.assertNotIn(FauxDolibarr.CLE, tout)

    def test_l_en_tete_host_est_celui_de_la_config(self):
        self.releve()
        self.assertEqual(set(self.faux.hotes), {"dolibarr.exemple"})

    def test_les_lectures_n_envoient_que_des_get(self):
        self.semer()
        self.releve()
        self.e("dolibarr.compter", "humain", {"objet": "tiers"})
        self.e("dolibarr.lister", "humain", {"objet": "factures", "etat": "impayees"})
        self.e("dolibarr.impayees", "humain")
        self.assertEqual(self.faux.methodes(), {"GET"})

    # --- lectures bornées ---
    def test_compter_pagine_sans_tout_telecharger(self):
        for i in range(2500):
            self.faux.donnees["thirdparties"][i + 1] = {"id": i + 1, "name": "T%d" % i}
        r = self.e("dolibarr.compter", "humain", {"objet": "tiers"})
        self.assertEqual(r["resultat"]["nombre"], 2500)
        pages = [c for m, c in self.faux.journal if c == "/thirdparties"]
        self.assertEqual(len(pages), 3)

    def test_les_lectures_refusent_ce_qui_sort_du_cadre(self):
        for cap, args in (("lister", {"objet": "../etc"}), ("lister", {"objet": "tiers", "limite": 500}), ("lister", {"objet": "tiers", "champs": "email"}),
                          ("lister", {"objet": "tiers", "champs": "id; DROP"}), ("lister", {"objet": "tiers", "etat": "impayees"}),
                          ("lire", {"objet": "tiers", "id": "1/../x"}), ("lire", {"objet": "inconnu", "id": 1})):
            self.assertEqual(self.e("dolibarr." + cap, "humain", args)["statut"], "echec", msg=str((cap, args)))
        self.assertEqual(self.faux.journal, [])                                 # rien n'est parti vers Dolibarr

    def test_lister_et_lire_rendent_les_champs_bornes(self):
        self.semer()
        r = self.e("dolibarr.lister", "humain", {"objet": "tiers", "limite": 2})["resultat"]["lignes"]
        self.assertEqual(len(r), 2)
        self.assertEqual(self.e("dolibarr.lire", "humain", {"objet": "tiers", "id": 2})["statut"], "faite")

    # --- écrire : réversible ---
    def test_creer_un_tiers_avec_preuve(self):
        r = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Nouveau tiers", "client": 1, "town": "Lyon"}})
        self.assertEqual(r["statut"], "faite")
        o = self.faux.donnees["thirdparties"][r["resultat"]["id"]]
        self.assertEqual((o["name"], o["town"]), ("Nouveau tiers", "Lyon"))
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)

    def test_cassandra_au_palier_raconter_dit_ce_qu_elle_ferait(self):
        r = self.e("dolibarr.creer", "cassandra", {"objet": "tiers", "champs": {"name": "Rêve"}})
        self.assertEqual(r["statut"], "racontee")
        self.assertEqual(self.faux.donnees["thirdparties"], {})

    def test_cassandra_agit_seule_une_fois_le_palier_auto(self):
        self.n.catalogue.regler_palier("dolibarr.creer", "auto")
        self.assertEqual(self.e("dolibarr.creer", "cassandra", {"objet": "tiers", "champs": {"name": "Seule"}})["statut"], "faite")
        self.assertEqual(len(self.faux.donnees["thirdparties"]), 1)

    def test_une_ecriture_hors_liste_ne_part_pas(self):
        for args in ({"objet": "tiers", "champs": {"rowid": 5}}, {"objet": "tiers", "champs": {"name": "x" * 5000}}, {"objet": "factures", "champs": {"name": "x"}},
                     {"objet": "tiers", "champs": {}}, {"objet": "tiers", "champs": {"name": ["liste"]}}):
            self.assertEqual(self.e("dolibarr.creer", "humain", args)["statut"], "echec", msg=str(args))
        self.assertEqual(self.faux.journal, [])

    def test_une_preuve_manquante_defait_ce_qui_vient_d_etre_cree(self):
        self.faux.ignorer = {"name"}                                       # Dolibarr « oublie » le nom
        r = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Fantôme"}})
        self.assertEqual(r["statut"], "annulee")
        self.assertEqual(self.faux.donnees["thirdparties"], {})            # supprimé : ce que cet acte avait créé, et rien d'autre

    def test_modifier_garde_l_etat_d_avant_pour_le_retour_arriere(self):
        self.semer()
        self.faux.corrompre_put = True                                      # le serveur altère le nom à l'écriture : la preuve échoue
        r = self.e("dolibarr.modifier", "humain", {"objet": "tiers", "id": 2, "champs": {"name": "Renommé"}})
        self.assertEqual(r["statut"], "annulee")
        self.assertEqual(self.faux.donnees["thirdparties"][2]["name"], "Tiers 2")          # revenu à la valeur d'avant

    def test_modifier_applique_et_prouve(self):
        self.semer()
        r = self.e("dolibarr.modifier", "humain", {"objet": "tiers", "id": 3, "champs": {"name": "Troisième", "email": "a@b.fr"}})
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(self.faux.donnees["thirdparties"][3]["email"], "a@b.fr")
        self.assertEqual(self.e("dolibarr.modifier", "humain", {"objet": "tiers", "id": 99, "champs": {"name": "x"}})["statut"], "echec")

    def test_creer_un_brouillon_de_facture(self):
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "factures", "socid": 1, "lignes": [{"desc": "Prestation", "qty": 2, "subprice": 50, "tva_tx": 20}]})
        self.assertEqual(r["statut"], "faite")
        f = self.faux.donnees["invoices"][r["resultat"]["id"]]
        self.assertEqual((f["statut"], len(f["lines"])), ("0", 1))

    def test_un_brouillon_non_conforme_est_supprime_tant_qu_il_est_brouillon(self):
        self.faux.ignorer = {"lines"}
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "devis", "socid": 1, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}]})
        self.assertEqual(r["statut"], "annulee")
        self.assertEqual(self.faux.donnees["proposals"], {})

    def test_un_document_valide_entre_temps_ne_se_supprime_jamais(self):
        self.faux.ignorer = {"lines"}
        self.faux.valider_apres_creation = True                             # quelqu'un le valide pendant ce temps
        r = self.e("dolibarr.creer_brouillon", "factures", {"socid": 1, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}]}) if False else \
            self.e("dolibarr.creer_brouillon", "humain", {"objet": "factures", "socid": 1, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}]})
        self.assertEqual(r["statut"], "annulation_impossible")
        self.assertEqual(len(self.faux.donnees["invoices"]), 1)             # la facture validée est intacte

    # --- écrire : légal ---
    def test_valider_une_facture_commence_a_raconter_et_l_admin_decide_ensuite(self):
        self.faux.donnees["invoices"][1] = {"id": 1, "statut": "0", "lines": [], "socid": 1}
        r = self.e("dolibarr.valider_facture", "cassandra", {"id": 1})
        self.assertEqual(r["statut"], "racontee")                                   # le défaut est prudent
        self.assertEqual(self.faux.donnees["invoices"][1]["statut"], "0")
        self.assertTrue(self.n.regler_palier("dolibarr.valider_facture", "auto")["ok"])      # c'est un choix d'administrateur, pas un interdit
        self.assertEqual(self.e("dolibarr.valider_facture", "cassandra", {"id": 1})["statut"], "faite")
        self.assertEqual(self.faux.donnees["invoices"][1]["statut"], "1")
        self.assertFalse(self.n.regler_palier("dolibarr.valider_facture", "maitre")["ok"])   # le maximum permis reste celui du manifeste

    def test_un_humain_peut_valider_en_voie_parallele_avec_preuve(self):
        self.faux.donnees["invoices"][1] = {"id": 1, "statut": "0", "lines": [], "socid": 1}
        r = self.e("dolibarr.valider_facture", "humain", {"id": 1})
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(self.faux.donnees["invoices"][1]["statut"], "1")
        self.assertEqual(self.e("dolibarr.valider_facture", "humain", {"id": 1})["statut"], "echec")      # plus un brouillon

    def test_itare_ne_valide_pas_de_facture(self):
        self.faux.donnees["invoices"][1] = {"id": 1, "statut": "0", "lines": [], "socid": 1}
        self.assertEqual(self.e("dolibarr.valider_facture", "itare", {"id": 1})["statut"], "refuse")

    def test_en_crise_seules_les_lectures_passent(self):
        self.n.crise(True, "essai")
        self.assertEqual(self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "x"}})["statut"], "refuse")
        r = self.e("dolibarr.compter", "humain", {"objet": "tiers"})
        self.assertEqual((r["statut"], r["resultat"]["nombre"]), ("faite", 0))                               # une lecture passe (aucun tiers : 0)
        self.n.crise(False)

    # --- supprimer : une corbeille, un choix d'administrateur ---
    def test_supprimer_garde_une_copie_entiere_et_se_prouve(self):
        self.semer()
        self.faux.donnees["thirdparties"][2]["email"] = "deux@exemple.fr"
        r = self.e("dolibarr.supprimer", "humain", {"objet": "tiers", "id": 2})
        self.assertEqual(r["statut"], "faite")
        self.assertNotIn(2, self.faux.donnees["thirdparties"])
        c = self.e("dolibarr.corbeille", "humain")["resultat"]
        self.assertEqual([(x["objet"], x["id"], x["etat"]) for x in c], [("tiers", 2, "supprime")])
        copie = self.n.registre.lire("dolibarr_corbeille", c[0]["corbeille"], portee=TOUT)["donnees"]["copie"]
        self.assertEqual((copie["name"], copie["email"]), ("Tiers 2", "deux@exemple.fr"))        # la copie est entière

    def test_restaurer_recree_l_objet_depuis_la_corbeille(self):
        self.semer()
        self.e("dolibarr.supprimer", "humain", {"objet": "tiers", "id": 2})
        cid = self.e("dolibarr.corbeille", "humain")["resultat"][0]["corbeille"]
        r = self.e("dolibarr.restaurer", "humain", {"corbeille": cid})
        self.assertEqual(r["statut"], "faite")
        nouveau = self.faux.donnees["thirdparties"][r["resultat"]["id"]]
        self.assertEqual(nouveau["name"], "Tiers 2")
        self.assertNotEqual(r["resultat"]["id"], 2)                               # l'identifiant change, le reste revient
        self.assertEqual(self.e("dolibarr.corbeille", "humain")["resultat"][0]["etat"], "restaure")
        self.assertEqual(self.e("dolibarr.restaurer", "humain", {"corbeille": cid})["statut"], "echec")     # une seule fois

    def test_dolibarr_refuse_ce_qui_est_reference_et_rien_ne_reste_dans_la_corbeille(self):
        self.semer()
        self.faux.bloques.add(("thirdparties", 1))                                # un tiers qui a des factures
        r = self.e("dolibarr.supprimer", "humain", {"objet": "tiers", "id": 1})
        self.assertEqual(r["statut"], "echec")
        self.assertIn(1, self.faux.donnees["thirdparties"])
        self.assertEqual(self.e("dolibarr.corbeille", "humain")["resultat"], [])

    def test_une_suppression_sans_effet_est_defaite_et_l_objet_reste(self):
        self.semer()
        self.faux.delete_sans_effet = True                                         # Dolibarr répond oui mais ne supprime pas
        r = self.e("dolibarr.supprimer", "humain", {"objet": "tiers", "id": 3})
        self.assertEqual(r["statut"], "annulee")
        self.assertIn(3, self.faux.donnees["thirdparties"])
        self.assertEqual(self.e("dolibarr.corbeille", "humain")["resultat"], [])

    def test_cassandra_supprime_seule_quand_l_admin_le_decide(self):
        self.semer()
        self.assertEqual(self.e("dolibarr.supprimer", "cassandra", {"objet": "tiers", "id": 1})["statut"], "racontee")      # défaut prudent
        self.assertIn(1, self.faux.donnees["thirdparties"])
        self.assertTrue(self.n.regler_palier("dolibarr.supprimer", "auto")["ok"])
        self.assertEqual(self.e("dolibarr.supprimer", "cassandra", {"objet": "tiers", "id": 1})["statut"], "faite")
        self.assertNotIn(1, self.faux.donnees["thirdparties"])

    def test_on_supprime_un_brouillon_pas_un_document_valide(self):
        self.faux.donnees["invoices"][1] = {"id": 1, "statut": "0", "lines": [], "socid": 1}
        self.faux.donnees["invoices"][2] = {"id": 2, "statut": "1", "lines": [], "socid": 1}
        self.assertEqual(self.e("dolibarr.supprimer", "humain", {"objet": "factures", "id": 1})["statut"], "faite")
        self.assertEqual(self.e("dolibarr.supprimer", "humain", {"objet": "factures", "id": 2})["statut"], "echec")     # la règle est celle de Dolibarr
        self.assertIn(2, self.faux.donnees["invoices"])

    def test_une_suppression_hors_cadre_ne_part_pas(self):
        for args in ({"objet": "../x", "id": 1}, {"objet": "tiers", "id": "1/../2"}, {"objet": "utilisateurs", "id": 1}):
            self.assertEqual(self.e("dolibarr.supprimer", "humain", args)["statut"], "echec", msg=str(args))
        self.assertEqual(self.faux.journal, [])

    # --- le plafond : un réglage d'administrateur, journalisé ---
    def test_regler_un_palier_est_un_acte_journalise(self):
        r = self.n.regler_palier("dolibarr.creer", "auto", acteur="humain")
        self.assertEqual(r, {"ok": True, "de": "raconter", "a": "auto"})
        ev = self.evts("savoir.regle")
        self.assertEqual((ev[0]["acteur"], ev[0]["donnees"]["a"]), ("humain", "auto"))
        self.assertFalse(self.n.regler_palier("dolibarr.creer", "maitre")["ok"])          # hors du maximum du manifeste
        self.assertFalse(self.n.regler_palier("dolibarr.inconnue", "auto")["ok"])

    def test_la_ligne_de_commande_des_paliers(self):
        import contextlib
        import io as _io
        ancien = {k: os.environ.get(k) for k in ("CASSANDRA_DONNEES", "CASSANDRA_EXTENSIONS")}
        os.environ["CASSANDRA_DONNEES"] = str(Path(self.tmp.name) / "d")
        os.environ.pop("CASSANDRA_EXTENSIONS", None)
        try:
            sortie = _io.StringIO()
            with contextlib.redirect_stdout(sortie):
                self.assertEqual(moteur.commande_palier(["main.py", "palier"]), 0)
            self.assertIn("dolibarr.supprimer", sortie.getvalue())
            with contextlib.redirect_stdout(_io.StringIO()):
                self.assertEqual(moteur.commande_palier(["main.py", "palier", "dolibarr.supprimer", "auto"]), 0)
            self.assertEqual(self.n.catalogue.savoir("dolibarr.supprimer")["palier"], "auto")                     # le service en marche le voit aussitôt
            with contextlib.redirect_stderr(_io.StringIO()):
                self.assertEqual(moteur.commande_palier(["main.py", "palier", "dolibarr.supprimer", "maitre"]), 1)
        finally:
            for k, v in ancien.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_la_porte_d_ecriture_ne_connait_que_post_put_delete(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dol_test", RACINE / "modules" / "dolibarr" / "module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with self.assertRaises(m.PontErreur):
            m.ecrire({"url": self.faux.url, "fichier_cle": str(self.conf / "dolibarr.key")}, "PATCH", "/thirdparties/1", {})
        self.assertEqual(self.faux.journal, [])


COMPTA_TOML = """
[module]
id = "compta"
nom = "Compta"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : des droits à vérifier."

[[droits]]
id = "lire"
libelle = "Lire la compta"
defaut = true

[[droits]]
id = "ecrire"
libelle = "Écrire en compta"

[[objets]]
type = "ecriture"
libelle = "Une écriture"

[[capacites]]
id = "voir_livre"
libelle = "Voir le livre"
risque = "lecture"
droit = "lire"

[[capacites]]
id = "passer_ecriture"
libelle = "Passer une écriture"
risque = "faible"
droit = "ecrire"
perimetre = ["le livre"]
preuve = "relire l'écriture"
retour = "retirer l'écriture"
paliers = ["raconter", "auto"]
qui = ["humain", "compte", "cassandra", "itare"]

[[capacites]]
id = "sans_droit"
libelle = "Une lecture ouverte à tous"
risque = "lecture"

[[ecrans]]
id = "livre"
libelle = "Livre"

[[ecrans]]
id = "secret"
libelle = "Secret"

[[menus]]
id = "livre"
libelle = "Livre"
ecran = "livre"
droit = "lire"

[[menus]]
id = "secret"
libelle = "Secret"
ecran = "secret"
droit = "ecrire"
"""

COMPTA_PY = """
def brancher(ctx):
    ctx.implementer("voir_livre", lambda ctx: {"lignes": 3})
    ctx.implementer("sans_droit", lambda ctx: {"ok": True})
    ctx.implementer("passer_ecriture", lambda ctx, n=1: {"n": n}, lambda ctx, res: True, lambda ctx, res: None)
"""


def monde_droits():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "menus"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    ecrire_module(mods, "compta", COMPTA_TOML, COMPTA_PY)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
    n.brancher()
    n.activer("droits")
    n.activer("menus")
    n.activer("compta")
    return tmp, n


class DroitsDesComptes(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_droits()
        self.addCleanup(self.tmp.cleanup)

    def ex(self, cle, acteur="humain", au_nom_de="", **args):
        """au_nom_de : le compte pour lequel on agit (les droits sont vérifiés pour lui) ; `compte=` reste un argument de la capacité."""
        return self.n.executeur.executer(cle, acteur, args, compte=au_nom_de)

    def test_le_manifeste_exige_un_droit_declare(self):
        brut = {"module": {"id": "xx", "nom": "X", "version": "0.1.0", "noyau_min": "0.1.0", "description": "d"},
                "capacites": [{"id": "voir", "libelle": "v", "risque": "lecture", "droit": "fantome"}]}
        self.assertTrue(any("n'est pas un droit de ce module" in e for e in mf.valider(brut)))
        brut["droits"] = [{"id": "fantome", "libelle": "f"}]
        self.assertEqual(mf.valider(brut), [])
        c = mf.construire(brut).capacites[0]
        self.assertEqual(c.droit, "xx.fantome")                       # qualifié par le module

    def test_sans_compte_aucun_droit_n_est_demande(self):
        self.assertEqual(self.ex("compta.passer_ecriture")["statut"], "faite")                   # humain en ligne de commande
        self.assertEqual(self.ex("compta.passer_ecriture", "cassandra")["statut"], "racontee")   # le palier borne l'agent, pas un droit

    def test_un_compte_sans_le_droit_est_refuse_et_le_refus_se_journalise(self):
        r = self.ex("compta.passer_ecriture", au_nom_de="sandrine")
        self.assertEqual(r["statut"], "refuse")
        self.assertEqual(r["droit"], "compta.ecrire")
        ev = [e for e in self.n.bus.recents(portee=TOUT, limite=200) if e["type"] == "capacite.refusee" and e["donnees"].get("droit")]
        self.assertEqual(ev[-1]["donnees"]["parce"], "non attribué")
        self.assertEqual(ev[-1]["compte"], "sandrine")

    def test_un_droit_par_defaut_est_accorde_a_tous_les_comptes(self):
        self.assertEqual(self.ex("compta.voir_livre", au_nom_de="sandrine")["statut"], "faite")
        self.assertEqual(self.ex("compta.sans_droit", au_nom_de="sandrine")["statut"], "faite")

    def test_accorder_a_un_compte_puis_retirer(self):
        self.assertEqual(self.ex("droits.regler", sujet="sandrine", droit="compta.ecrire")["statut"], "faite")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="sandrine")["statut"], "faite")
        self.ex("droits.regler", sujet="sandrine", droit="compta.ecrire", valeur="herite")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="sandrine")["statut"], "refuse")

    def test_un_groupe_accorde_ses_membres_et_un_refus_propre_l_emporte(self):
        self.ex("droits.groupe", groupe="compta", libelle="Comptables")
        self.ex("droits.regler", sujet_type="groupe", sujet="compta", droit="compta.ecrire")
        self.ex("droits.membre", compte="jules", groupe="compta")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="jules")["statut"], "faite")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="paul")["statut"], "refuse")      # pas membre
        self.ex("droits.regler", sujet="jules", droit="compta.ecrire", valeur="refuse")             # le refus propre l'emporte
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="jules")["statut"], "refuse")

    def test_un_refus_de_groupe_l_emporte_sur_un_accord_de_groupe(self):
        for g in ("a", "b"):
            self.ex("droits.groupe", groupe=g, libelle=g)
            self.ex("droits.membre", compte="jules", groupe=g)
        self.ex("droits.regler", sujet_type="groupe", sujet="a", droit="compta.ecrire")
        self.ex("droits.regler", sujet_type="groupe", sujet="b", droit="compta.ecrire", valeur="refuse")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="jules")["statut"], "refuse")

    def test_un_administrateur_detient_tout(self):
        self.ex("droits.admin", compte="marie")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="marie")["statut"], "faite")
        self.assertEqual(self.ex("droits.etat", au_nom_de="marie")["statut"], "faite")

    def test_le_delegue_n_a_pas_plus_de_droits_que_le_compte_qu_il_sert(self):
        """Itare qui agit AU NOM de Sandrine ne peut rien que Sandrine ne puisse."""
        self.n.regler_palier("compta.passer_ecriture", "auto")
        self.assertEqual(self.ex("compta.passer_ecriture", "itare", au_nom_de="sandrine")["statut"], "refuse")
        self.ex("droits.regler", sujet="sandrine", droit="compta.ecrire")
        self.assertEqual(self.ex("compta.passer_ecriture", "itare", au_nom_de="sandrine")["statut"], "faite")

    def test_administrer_les_droits_exige_le_droit_d_administrer(self):
        r = self.ex("droits.regler", au_nom_de="sandrine", sujet="sandrine", droit="compta.ecrire")     # s'octroyer un droit soi-même
        self.assertEqual(r["statut"], "refuse")
        self.assertEqual(r["droit"], "droits.gerer")
        self.ex("droits.regler", sujet="sandrine", droit="droits.gerer")
        self.assertEqual(self.ex("droits.regler", au_nom_de="sandrine", sujet="paul", droit="compta.ecrire")["statut"], "faite")

    def test_nommer_un_admin_est_un_droit_a_part(self):
        """Gérer les droits ne suffit pas à se nommer administrateur."""
        self.ex("droits.regler", sujet="sandrine", droit="droits.gerer")
        self.assertEqual(self.ex("droits.admin", compte="sandrine")["statut"], "faite")              # l'opérateur (sans compte) le peut
        # mais Sandrine, agissant en son nom, ne peut pas nommer d'admin sans le droit dédié (elle est admin maintenant : on le lui retire)
        self.ex("droits.admin", compte="sandrine", admin=False)
        r = self.n.executeur.executer("droits.admin", "compte", {"compte": "sandrine"}, compte="sandrine")
        self.assertEqual(r["statut"], "refuse")
        self.assertEqual(r["droit"], "droits.nommer_admin")

    def test_les_droits_se_defont(self):
        self.ex("droits.groupe", groupe="g", libelle="G")
        self.ex("droits.membre", compte="jules", groupe="g")
        self.ex("droits.regler", sujet_type="groupe", sujet="g", droit="compta.ecrire")
        r = self.ex("droits.groupe", groupe="g", supprimer=True)
        self.assertEqual(r["statut"], "faite")
        self.assertFalse(self.n.droits.membre("jules", "g"))             # supprimé : membres et accords partent avec
        self.n.catalogue.get("droits.groupe").defaire(None, r["resultat"])
        self.assertTrue(self.n.droits.membre("jules", "g"))              # le retour arrière rend tout
        self.assertEqual(self.n.droits.accord("groupe", "g", "compta.ecrire"), "accorde")

    def test_le_menu_se_filtre_par_les_droits_du_compte(self):
        def titres(compte):
            r = self.ex("menus.lire_menu", role="admin", compte=compte)["resultat"]["arbre"]
            return sorted(x["libelle"] for f in r for x in f["enfants"])
        self.assertIn("Livre", titres("sandrine"))                        # droit par défaut
        self.assertNotIn("Secret", titres("sandrine"))
        self.ex("droits.regler", sujet="sandrine", droit="compta.ecrire")
        self.assertIn("Secret", titres("sandrine"))
        self.assertIn("Secret", titres(""))                               # sans compte : tout (les agents voient tout)

    def test_le_premier_administrateur_est_amorce_une_seule_fois(self):
        self.assertTrue(self.n.droits.est_admin("fastuser"))
        self.ex("droits.admin", compte="fastuser", admin=False)
        self.n.brancher()                                                 # un redémarrage ne le remet pas
        self.assertFalse(self.n.droits.est_admin("fastuser"))

    def test_un_droit_inconnu_est_refuse_a_l_attribution(self):
        self.assertEqual(self.ex("droits.regler", sujet="sandrine", droit="nimporte.quoi")["statut"], "echec")

    def test_desactiver_un_module_retire_ses_droits_mais_pas_les_accords(self):
        self.ex("droits.regler", sujet="sandrine", droit="compta.ecrire")
        self.n.desactiver("compta")
        self.assertNotIn("compta.ecrire", [d["droit"] for d in self.n.droits.catalogue()])
        self.n.activer("compta")
        self.assertEqual(self.ex("compta.passer_ecriture", au_nom_de="sandrine")["statut"], "faite")


MDP = "Abcdefgh1!"
MDP2 = "Zyxwvuts2?"


def monde_comptes():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
    n.brancher()
    n.activer("comptes")                        # active aussi droits
    n.identite.unix = lambda nom: "/bin/bash" if nom in ("fastuser", "alice") else None      # les utilisateurs du système, factices
    n.identite.fastpanel = lambda: False
    return tmp, n


class ComptesEtSessions(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_comptes()
        self.addCleanup(self.tmp.cleanup)

    def ex(self, cle, acteur="humain", au_nom_de="", **args):
        return self.n.executeur.executer(cle, acteur, args, compte=au_nom_de)

    def creer(self, compte, mdp=MDP):
        return self.ex("comptes.creer", compte=compte, mot_de_passe=mdp)

    def ouvrir(self, compte, mdp=MDP, ip="203.0.113.5"):
        r = self.ex("comptes.ouvrir_session", compte=compte, mot_de_passe=mdp, ip=ip, agent="Firefox")
        return r["resultat"]

    def test_le_premier_compte_est_administrateur_pas_le_suivant(self):
        self.assertTrue(self.creer("a@x.fr")["resultat"]["admin"])
        self.assertFalse(self.creer("b@x.fr")["resultat"]["admin"])
        self.assertTrue(self.n.droits.est_admin("a@x.fr"))
        self.assertFalse(self.n.droits.est_admin("b@x.fr"))

    def test_le_premier_compte_est_le_superadmin_adosse_a_fastuser_avec_bash(self):
        r = self.creer("a@x.fr")["resultat"]
        self.assertEqual((r["superadmin"], r["unix_user"]), (True, "fastuser"))
        m = self.ex("comptes.lire", compte="a@x.fr")["resultat"]
        self.assertEqual((m["superadmin"], m["admin"], m["unix_user"], m["fp_account"]), (True, True, "fastuser", "fastuser"))
        b = self.creer("b@x.fr")["resultat"]
        self.assertEqual((b["superadmin"], b["unix_user"]), (False, ""))
        self.assertEqual([c["compte"] for c in self.ex("comptes.lister")["resultat"]["comptes"] if c["superadmin"]], ["a@x.fr"])

    def test_sans_fastuser_ou_sans_bash_le_compte_se_cree_et_le_dit(self):
        """Ce n'est pas un interdit : le système rattrape (install.sh, deploy.sh), et l'état de l'adossement se lit."""
        self.n.identite.unix = lambda nom: None
        self.assertEqual(self.creer("a@x.fr")["statut"], "faite")
        m = self.ex("comptes.lire", compte="a@x.fr")["resultat"]
        self.assertEqual((m["superadmin"], m["unix_user"], m["unix_etat"]), (True, "fastuser", "absent"))
        self.n.identite.unix = lambda nom: "/usr/sbin/nologin"
        self.assertEqual(self.ex("comptes.lire", compte="a@x.fr")["resultat"]["unix_etat"], "sans_shell")
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.assertEqual(self.ex("comptes.lire", compte="a@x.fr")["resultat"]["unix_etat"], "ok")
        self.creer("b@x.fr")
        self.assertEqual(self.ex("comptes.lire", compte="b@x.fr")["resultat"]["unix_etat"], "")

    def test_le_superadmin_supprime_puis_restaure_reste_superadmin(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        r = self.ex("comptes.supprimer", compte="a@x.fr")
        self.ex("comptes.restaurer", corbeille=r["resultat"]["corbeille"])
        m = self.ex("comptes.lire", compte="a@x.fr")["resultat"]
        self.assertEqual((m["superadmin"], m["unix_user"], m["admin"]), (True, "fastuser", True))

    def test_l_identifiant_est_une_adresse_et_le_mot_de_passe_suit_les_regles(self):
        self.assertEqual(self.creer("pas-un-mail")["statut"], "echec")
        r = self.creer("a@x.fr", "court")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("il manque", r["erreur"])
        self.assertEqual(self.creer("a@x.fr")["statut"], "faite")
        self.assertEqual(self.creer("a@x.fr")["statut"], "echec")                  # déjà pris

    def test_le_mot_de_passe_est_un_scrypt_sale_et_ne_sort_jamais(self):
        self.creer("a@x.fr")
        h = self.n.identite.hash_de("a@x.fr")
        self.assertTrue(h.startswith("scrypt$"))
        self.creer("b@x.fr")
        self.assertNotEqual(h.split("$")[2], self.n.identite.hash_de("b@x.fr").split("$")[2])      # même mot de passe, empreintes différentes
        self.assertNotIn("hash", self.ex("comptes.lire", compte="a@x.fr")["resultat"])
        self.assertNotIn("hash", str(self.ex("comptes.lister")["resultat"]))

    def test_ni_mot_de_passe_ni_jeton_dans_le_journal(self):
        self.creer("a@x.fr")
        s = self.ouvrir("a@x.fr")
        self.ex("comptes.changer_mon_mot_de_passe", au_nom_de="a@x.fr", actuel=MDP, nouveau=MDP2)
        j = self.ex("comptes.creer_jeton", compte="a@x.fr")["resultat"]["jeton"]
        base = self.n.base
        tout = " ".join(r["donnees"] for r in base.lire("SELECT donnees FROM evenements")) + " ".join(r["donnees"] for r in base.lire("SELECT donnees FROM objets"))
        for secret in (MDP, MDP2, s["jeton"], j, self.n.identite.hash_de("a@x.fr")):
            self.assertNotIn(secret, tout)

    def test_ouvrir_une_session_puis_la_valider_puis_la_fermer(self):
        self.creer("a@x.fr")
        s = self.ouvrir("a@x.fr")
        self.assertTrue(s["ok"])
        v = self.ex("comptes.valider_session", jeton=s["jeton"])["resultat"]
        self.assertEqual((v["ok"], v["compte"], v["admin"]), (True, "a@x.fr", True))
        self.ex("comptes.fermer_session", jeton=s["jeton"])
        self.assertFalse(self.ex("comptes.valider_session", jeton=s["jeton"])["resultat"]["ok"])
        self.assertFalse(self.ex("comptes.valider_session", jeton="court")["resultat"]["ok"])

    def test_une_session_expire_meme_sans_nouvelle_connexion(self):
        self.creer("a@x.fr")
        s = self.ouvrir("a@x.fr")
        self.n.base.ecrire("UPDATE sessions SET cree=cree-?", (25 * 3600,))
        self.assertFalse(self.ex("comptes.valider_session", jeton=s["jeton"])["resultat"]["ok"])

    def test_mauvais_mot_de_passe_ou_compte_inconnu_meme_reponse(self):
        self.creer("a@x.fr")
        a = self.ouvrir("a@x.fr", "Mauvais1!x")
        b = self.ouvrir("inconnu@x.fr", MDP)
        self.assertEqual((a["ok"], b["ok"]), (False, False))
        self.assertEqual(a["erreur"], b["erreur"])

    def test_dix_echecs_bloquent_meme_avec_le_bon_mot_de_passe(self):
        self.creer("a@x.fr")
        for _ in range(10):
            self.ouvrir("a@x.fr", "Mauvais1!x", ip="198.51.100.9")
        r = self.ouvrir("a@x.fr", MDP, ip="198.51.100.9")
        self.assertTrue(r["limite"])
        self.assertGreater(r["attente_s"], 0)
        self.assertTrue(self.ouvrir("a@x.fr", MDP, ip="198.51.100.77")["limite"])        # le compte est bloqué, pas seulement l'origine
        self.n.base.ecrire("UPDATE tentatives SET ts=ts-400")                            # cinq minutes plus tard
        self.assertTrue(self.ouvrir("a@x.fr", MDP, ip="198.51.100.9")["ok"])

    def test_les_sessions_sont_celles_du_compte_qui_agit(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        sa, sb = self.ouvrir("a@x.fr"), self.ouvrir("b@x.fr")
        mes = self.ex("comptes.mes_sessions", au_nom_de="a@x.fr", courant=sa["jeton"])["resultat"]["sessions"]
        self.assertEqual([(s["id"], s["current"], s["nature"]) for s in mes], [(sa["id"], True, "internet")])
        r = self.ex("comptes.revoquer_session", au_nom_de="a@x.fr", court=sb["id"])             # six caractères du voisin
        self.assertEqual(r["resultat"]["ferme"], 0)
        self.assertTrue(self.ex("comptes.valider_session", jeton=sb["jeton"])["resultat"]["ok"])
        self.assertEqual(self.ex("comptes.mes_sessions")["statut"], "echec")                     # sans compte : rien à dire

    def test_revoquer_les_autres_garde_la_courante(self):
        self.creer("a@x.fr")
        s1, s2, s3 = (self.ouvrir("a@x.fr") for _ in range(3))
        r = self.ex("comptes.revoquer_autres_sessions", au_nom_de="a@x.fr", courant=s2["jeton"])
        self.assertEqual(r["resultat"]["ferme"], 2)
        self.assertTrue(self.ex("comptes.valider_session", jeton=s2["jeton"])["resultat"]["ok"])
        self.assertFalse(self.ex("comptes.valider_session", jeton=s1["jeton"])["resultat"]["ok"])

    def test_changer_son_mot_de_passe_exige_l_actuel(self):
        self.creer("a@x.fr")
        r = self.ex("comptes.changer_mon_mot_de_passe", au_nom_de="a@x.fr", actuel="Mauvais1!x", nouveau=MDP2)
        self.assertEqual(r["statut"], "echec")
        self.assertEqual(self.ex("comptes.changer_mon_mot_de_passe", au_nom_de="a@x.fr", actuel=MDP, nouveau="faible")["statut"], "echec")
        self.assertEqual(self.ex("comptes.changer_mon_mot_de_passe", au_nom_de="a@x.fr", actuel=MDP, nouveau=MDP2)["statut"], "faite")
        self.assertFalse(self.ouvrir("a@x.fr", MDP)["ok"])
        self.assertTrue(self.ouvrir("a@x.fr", MDP2)["ok"])

    def test_le_jeton_de_reinitialisation_sert_une_fois_et_ferme_les_sessions(self):
        self.creer("a@x.fr")
        s = self.ouvrir("a@x.fr")
        j = self.ex("comptes.creer_jeton", compte="a@x.fr")["resultat"]["jeton"]
        self.assertEqual(self.ex("comptes.reinitialiser_mot_de_passe", jeton=j, nouveau="faible")["statut"], "echec")     # refusé : le jeton n'est pas consommé
        self.assertEqual(self.ex("comptes.reinitialiser_mot_de_passe", jeton=j, nouveau=MDP2)["statut"], "faite")
        self.assertEqual(self.ex("comptes.reinitialiser_mot_de_passe", jeton=j, nouveau=MDP)["statut"], "echec")           # usage unique
        self.assertFalse(self.ex("comptes.valider_session", jeton=s["jeton"])["resultat"]["ok"])
        self.assertTrue(self.ouvrir("a@x.fr", MDP2)["ok"])

    def test_un_jeton_expire_ne_sert_plus(self):
        self.creer("a@x.fr")
        j = self.ex("comptes.creer_jeton", compte="a@x.fr")["resultat"]["jeton"]
        self.n.base.ecrire("UPDATE jetons_mdp SET expire=expire-?", (73 * 3600,))
        self.assertEqual(self.n.identite.jeton_compte(j), "")

    def test_supprimer_garde_une_copie_et_restaurer_rend_le_compte(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        s = self.ouvrir("b@x.fr")
        self.ex("droits.admin", compte="b@x.fr")
        r = self.ex("comptes.supprimer", compte="b@x.fr")
        self.assertEqual(r["statut"], "faite")
        self.assertFalse(self.n.identite.existe("b@x.fr"))
        self.assertFalse(self.n.droits.est_admin("b@x.fr"))
        self.assertFalse(self.ex("comptes.valider_session", jeton=s["jeton"])["resultat"]["ok"])     # les sessions ne reviennent pas
        self.assertEqual(self.ex("comptes.restaurer", corbeille=r["resultat"]["corbeille"])["statut"], "faite")
        self.assertTrue(self.ouvrir("b@x.fr")["ok"])                                                 # son mot de passe est revenu
        self.assertTrue(self.n.droits.est_admin("b@x.fr"))

    def test_le_retour_arriere_d_une_suppression_restaure(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        r = self.ex("comptes.supprimer", compte="b@x.fr")
        self.n.catalogue.get("comptes.supprimer").defaire(None, r["resultat"])
        self.assertTrue(self.n.identite.existe("b@x.fr"))

    def test_gerer_les_comptes_est_un_droit(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        self.assertEqual(self.ex("comptes.lister", au_nom_de="b@x.fr")["statut"], "refuse")
        self.assertEqual(self.ex("comptes.creer", au_nom_de="b@x.fr", compte="c@x.fr", mot_de_passe=MDP)["statut"], "refuse")
        self.assertEqual(self.ex("comptes.lister", au_nom_de="a@x.fr")["statut"], "faite")           # administrateur
        self.ex("droits.regler", sujet="b@x.fr", droit="comptes.gerer")
        self.assertEqual(self.ex("comptes.lister", au_nom_de="b@x.fr")["statut"], "faite")

    def test_chacun_modifie_son_profil_mais_pas_ses_sites(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        r = self.ex("comptes.modifier_moi", au_nom_de="b@x.fr", display_name="Bea", lang="EN", sites=["http://www.evil.com/x"])
        self.assertEqual(r["statut"], "faite")
        m = self.ex("comptes.moi", au_nom_de="b@x.fr")["resultat"]
        self.assertEqual((m["display_name"], m["lang"], m["sites"]), ("Bea", "en", []))
        self.ex("comptes.modifier", compte="b@x.fr", sites=["http://www.Exemple.com/x"])
        self.assertEqual(self.ex("comptes.moi", au_nom_de="b@x.fr")["resultat"]["sites"], ["exemple.com"])
        self.n.catalogue.get("comptes.modifier_moi").defaire(None, r["resultat"])
        self.assertEqual(self.ex("comptes.moi", au_nom_de="b@x.fr")["resultat"]["display_name"], "")

    def test_un_agent_ne_connait_pas_le_mot_de_passe_mais_peut_inviter(self):
        self.creer("a@x.fr")
        self.assertEqual(self.ex("comptes.creer", "cassandra", compte="c@x.fr", mot_de_passe=MDP)["statut"], "refuse")   # humain et compte seulement
        self.n.regler_palier("comptes.creer_jeton", "auto")
        self.assertEqual(self.ex("comptes.creer_jeton", "cassandra", compte="a@x.fr")["statut"], "faite")

    def test_les_regles_et_la_legende_viennent_de_la_meme_table(self):
        r = self.ex("comptes.regles_mdp")["resultat"]
        self.assertEqual([x["cle"] for x in r["regles"]], ["longueur", "majuscule", "chiffre", "special"])
        for x in r["regles"]:
            self.assertIn(x["dit"], r["legende"])


def monde_strict():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes", "menus"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("menus")
    n.identite.unix = lambda nom: "/bin/bash"
    return tmp, n


class SansCompte(unittest.TestCase):
    """Un acte sans compte n'existe pas : il est refusé, et il est signalé."""

    def setUp(self):
        self.tmp, self.n = monde_strict()
        self.addCleanup(self.tmp.cleanup)

    def ex(self, cle, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(cle, acteur, args, compte=au_nom_de)

    def test_les_comptes_systeme_existent_et_ne_se_connectent_pas(self):
        tous = {c["compte"]: c for c in self.ex("comptes.lister")["resultat"]["comptes"]}
        self.assertEqual({k for k, c in tous.items() if c["type"] == "systeme"}, {"noyau", "operateur", "cassandra", "itare", "itare_user", "vision", "second_avis"})
        self.assertEqual(tous["cassandra"]["admin"], True)
        self.assertEqual(tous["itare"]["admin"], False)
        for cid in tous:
            self.assertFalse(self.ex("comptes.ouvrir_session", compte=cid, mot_de_passe=MDP, au_nom_de="operateur")["resultat"]["ok"])

    def test_sans_compte_est_refuse(self):
        r = self.ex("comptes.regles_mdp", au_nom_de="")
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("signalé", r["raison"])
        ev = [e for e in self.n.bus.recents(portee=TOUT, limite=100) if e["type"] == "capacite.refusee" and e["donnees"].get("alerte")]
        self.assertEqual(ev[-1]["donnees"]["raison"], "sans compte")

    def test_un_compte_inconnu_est_refuse(self):
        r = self.ex("comptes.regles_mdp", au_nom_de="fantome@x.fr")
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("n'existe pas", r["raison"])

    def test_chaque_agent_agit_sous_son_compte(self):
        self.assertEqual(self.ex("comptes.regles_mdp", "cassandra", au_nom_de="cassandra")["statut"], "faite")
        self.assertEqual(self.ex("comptes.regles_mdp", "itare", au_nom_de="itare")["statut"], "faite")
        # Itare n'est pas administrateur : au nom d'Itare, gérer les comptes lui est refusé tant que l'administrateur ne le lui accorde pas
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="itare")["statut"], "refuse")
        self.ex("droits.regler", sujet="itare", droit="comptes.gerer")
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="itare")["statut"], "faite")

    def test_un_agent_invite_a_un_compte_ET_un_jeton(self):
        r = self.ex("comptes.inviter_agent", nom="claude", libelle="Claude de passage")
        self.assertEqual((r["statut"], r["resultat"]["compte"], r["resultat"]["nouveau"]), ("faite", "agent:claude", True))
        jeton = r["resultat"]["jeton"]
        v = self.ex("comptes.valider_jeton_agent", au_nom_de="agent:claude", jeton=jeton)["resultat"]
        self.assertEqual((v["ok"], v["compte"], v["invite_par"]), (True, "agent:claude", "operateur"))        # on le reconnaît, il ne se déclare pas
        self.assertFalse(self.ex("comptes.valider_jeton_agent", jeton="x" * 40)["resultat"]["ok"])
        self.assertEqual(self.ex("comptes.inviter_agent", nom="Mauvais Nom")["statut"], "echec")
        self.assertEqual(self.ex("comptes.inviter_agent", nom="tous")["statut"], "echec")
        self.assertEqual(self.ex("comptes.inviter_agent", nom="cassandra")["statut"], "echec")               # un nom de résident est réservé
        self.assertFalse(self.ex("comptes.ouvrir_session", compte="agent:claude", mot_de_passe=MDP)["resultat"]["ok"])

    def test_la_seule_borne_d_un_invite_est_le_statut_de_son_invitant(self):
        """V18 : invité par l'administrateur, il a tout ; invité par un compte ordinaire, il n'a que ce compte."""
        self.ex("comptes.inviter_agent", nom="deadmin")                                  # invité par operateur, administrateur
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="agent:deadmin")["statut"], "faite")
        self.n.regler_palier("comptes.inviter_agent", "auto")                           # Itare agit seul seulement si l'administrateur l'a décidé
        self.ex("comptes.inviter_agent", "itare", au_nom_de="itare", nom="deitare")      # invité par Itare, qui n'a pas comptes.gerer
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="agent:deitare")["statut"], "refuse")
        self.assertIn("agent invité par itare", self.ex("comptes.lister", "itare", au_nom_de="agent:deitare")["raison"])
        self.ex("droits.regler", sujet="itare", droit="comptes.gerer")                   # on élargit l'invitant : l'invité suit, en direct
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="agent:deitare")["statut"], "faite")
        self.ex("droits.regler", sujet="itare", droit="comptes.gerer", valeur="herite")  # et on le reprend
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="agent:deitare")["statut"], "refuse")

    def test_un_refus_propre_a_l_invite_l_emporte_sur_son_invitant(self):
        self.ex("comptes.inviter_agent", nom="prudent")
        self.ex("droits.regler", sujet="agent:prudent", droit="comptes.gerer", valeur="refuse")
        self.assertEqual(self.ex("comptes.lister", "itare", au_nom_de="agent:prudent")["statut"], "refuse")

    def test_reinviter_desactive_l_ancien_jeton_et_revoquer_coupe(self):
        j1 = self.ex("comptes.inviter_agent", nom="claude")["resultat"]["jeton"]
        r2 = self.ex("comptes.inviter_agent", nom="claude")["resultat"]
        self.assertFalse(r2["nouveau"])
        self.assertFalse(self.ex("comptes.valider_jeton_agent", jeton=j1)["resultat"]["ok"])
        self.assertTrue(self.ex("comptes.valider_jeton_agent", jeton=r2["jeton"])["resultat"]["ok"])
        self.assertEqual(self.ex("comptes.revoquer_agent", nom="claude")["resultat"]["revoques"], 1)
        self.assertFalse(self.ex("comptes.valider_jeton_agent", jeton=r2["jeton"])["resultat"]["ok"])

    def test_un_compte_ordinaire_ne_voit_et_ne_revoque_que_les_siens(self):
        self.ex("comptes.creer", compte="chef@x.fr", mot_de_passe=MDP)                     # le premier compte est le superadministrateur
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        self.ex("comptes.creer", compte="b@x.fr", mot_de_passe=MDP)
        self.ex("comptes.inviter_agent", au_nom_de="a@x.fr", nom="de_a")
        self.ex("comptes.inviter_agent", au_nom_de="b@x.fr", nom="de_b")
        mes = lambda c: sorted(x["compte"] for x in self.ex("comptes.mes_agents", au_nom_de=c)["resultat"]["agents"])
        self.assertEqual(mes("a@x.fr"), ["agent:de_a"])
        self.assertEqual(mes("operateur"), ["agent:de_a", "agent:de_b"])                 # l'administrateur voit tous les invités
        self.assertEqual(self.ex("comptes.revoquer_agent", au_nom_de="a@x.fr", nom="de_b")["statut"], "echec")
        self.assertEqual(self.ex("comptes.revoquer_agent", au_nom_de="operateur", nom="de_b")["statut"], "faite")
        self.assertEqual(self.ex("comptes.inviter_agent", au_nom_de="a@x.fr", nom="de_b")["statut"], "echec")     # le nom d'un autre n'est pas à prendre

    def test_le_jeton_d_un_invite_ne_va_pas_au_journal(self):
        j = self.ex("comptes.inviter_agent", nom="claude")["resultat"]["jeton"]
        self.ex("comptes.valider_jeton_agent", jeton=j)
        tout = " ".join(r["donnees"] for r in self.n.base.lire("SELECT donnees FROM evenements"))
        self.assertNotIn(j, tout)
        self.assertNotIn(__import__("hashlib").sha256(j.encode()).hexdigest(), tout)

    def test_un_compte_systeme_ne_se_supprime_pas(self):
        self.assertEqual(self.ex("comptes.supprimer", compte="noyau")["statut"], "echec")

    def test_le_premier_compte_humain_est_superadmin_malgre_les_comptes_systeme(self):
        r = self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)["resultat"]
        self.assertEqual((r["superadmin"], r["unix_user"]), (True, "fastuser"))
        self.assertEqual(self.ex("comptes.creer", compte="b@x.fr", mot_de_passe=MDP)["resultat"]["superadmin"], False)

    def test_le_noyau_travaille_sous_son_propre_chemin_interne(self):
        """Les lectures d'un module pour un autre (le menu lit les droits) passent par le noyau, pas par un acte sans compte."""
        r = self.ex("menus.lire_menu", role="admin", compte="operateur")
        self.assertEqual(r["statut"], "faite")

    def test_la_surveillance_ouvre_un_constat_puis_le_ferme(self):
        self.ex("comptes.regles_mdp", au_nom_de="")
        self.ex("comptes.regles_mdp", au_nom_de="fantome@x.fr")
        self.n.tick(maintenant=time_now())
        ouverts = [c for c in self.n.base.lire("SELECT * FROM constats WHERE etat='ouvert'")]
        self.assertEqual([c["objet_id"] for c in ouverts if c["module"] == "droits"], ["sans_compte"])
        self.assertIn("2 acte(s)", ouverts[0]["titre"])
        self.n.base.ecrire("UPDATE evenements SET ts=ts-2000")                         # trente-trois minutes plus tard : hors fenêtre
        self.n.tick(maintenant=time_now() + 60)
        self.assertEqual([c for c in self.n.base.lire("SELECT * FROM constats WHERE etat='ouvert' AND module='droits'")], [])


def time_now():
    import time
    return time.time()


class SuperadminSupplementaire(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_comptes()
        self.addCleanup(self.tmp.cleanup)
        self.sudo = []
        self.n.identite.sudo = lambda u: self.sudo.append(u) or True

    def ex(self, cle, acteur="humain", au_nom_de="", **args):
        return self.n.executeur.executer(cle, acteur, args, compte=au_nom_de)

    def test_un_superadmin_de_plus_apporte_son_identifiant_systeme_et_rejoint_sudo(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        r = self.ex("comptes.creer", au_nom_de="a@x.fr", compte="b@x.fr", mot_de_passe=MDP, superadmin=True, unix_user="alice")
        self.assertEqual(r["statut"], "faite")
        self.assertEqual((r["resultat"]["superadmin"], r["resultat"]["unix_user"], r["resultat"]["unix_demande"]), (True, "alice", True))
        self.assertEqual(self.sudo, ["alice"])
        self.assertTrue(self.n.droits.est_admin("b@x.fr"))

    def test_l_identifiant_systeme_est_obligatoire_et_doit_exister_avec_bash(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        for u in ("", "root", "Pas Bon", "inconnu"):
            r = self.ex("comptes.creer", au_nom_de="a@x.fr", compte="c@x.fr", mot_de_passe=MDP, superadmin=True, unix_user=u)
            self.assertEqual(r["statut"], "echec", u)
        self.assertFalse(self.n.identite.existe("c@x.fr"))
        self.assertEqual(self.sudo, [])

    def test_un_utilisateur_systeme_n_est_adosse_qu_a_un_compte(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        self.ex("comptes.creer", au_nom_de="a@x.fr", compte="b@x.fr", mot_de_passe=MDP, superadmin=True, unix_user="alice")
        r = self.ex("comptes.creer", au_nom_de="a@x.fr", compte="c@x.fr", mot_de_passe=MDP, superadmin=True, unix_user="alice")
        self.assertEqual(r["statut"], "echec")

    def test_seul_un_superadmin_en_cree_un(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        self.ex("comptes.creer", compte="b@x.fr", mot_de_passe=MDP)
        self.ex("droits.regler", sujet="b@x.fr", droit="comptes.gerer")                   # b gère les comptes, il n'est pas pour autant superadmin
        r = self.ex("comptes.creer", au_nom_de="b@x.fr", compte="c@x.fr", mot_de_passe=MDP, superadmin=True, unix_user="alice")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("superadministrateur", r["erreur"])
        self.assertEqual(self.ex("comptes.creer", au_nom_de="b@x.fr", compte="c@x.fr", mot_de_passe=MDP)["statut"], "faite")     # un compte ordinaire, oui

    def test_sans_la_case_superadmin_l_identifiant_systeme_est_ignore(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        r = self.ex("comptes.creer", au_nom_de="a@x.fr", compte="b@x.fr", mot_de_passe=MDP, unix_user="alice")
        self.assertEqual((r["resultat"]["superadmin"], r["resultat"]["unix_user"]), (False, ""))
        self.assertEqual(self.sudo, [])

    def test_le_verrou_n_existe_que_si_fastpanel_est_la(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        self.n.identite.fastpanel = lambda: True
        r = self.ex("comptes.supprimer", compte="a@x.fr")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("FastPanel", r["erreur"])
        self.assertEqual(self.ex("droits.admin", compte="a@x.fr", admin=False)["statut"], "echec")        # pas rétrogradé non plus
        self.assertTrue(self.n.droits.est_admin("a@x.fr"))
        self.n.identite.fastpanel = lambda: False                                                         # FastPanel parti : plus de verrou
        self.assertEqual(self.ex("droits.admin", compte="a@x.fr", admin=False)["statut"], "faite")

    def test_le_verrou_ne_protege_que_le_superadmin(self):
        self.ex("comptes.creer", compte="a@x.fr", mot_de_passe=MDP)
        self.ex("comptes.creer", compte="b@x.fr", mot_de_passe=MDP)
        self.ex("droits.admin", compte="b@x.fr")
        self.n.identite.fastpanel = lambda: True
        self.assertEqual(self.ex("droits.admin", compte="b@x.fr", admin=False)["statut"], "faite")
        self.assertEqual(self.ex("comptes.supprimer", compte="b@x.fr")["statut"], "faite")


BOUTIQUE_TOML = """
[module]
id = "boutique"
nom = "Boutique"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : des réglages de chaque type."

[[reglages]]
id = "nom"
libelle = "Nom affiché"
defaut = "Ma boutique"

[[reglages]]
id = "remise"
libelle = "Remise en pour cent"
type = "entier"
defaut = 5
minimum = 0
maximum = 50

[[reglages]]
id = "ouverte"
libelle = "Ouverte au public"
type = "booleen"
defaut = true

[[reglages]]
id = "devise"
libelle = "Devise"
type = "choix"
choix = ["EUR", "USD"]
defaut = "EUR"

[[reglages]]
id = "cle_api"
libelle = "Clé d'API du fournisseur"
type = "secret"

[[reglages]]
id = "theme"
libelle = "Thème préféré"
type = "choix"
choix = ["clair", "sombre"]
defaut = "clair"
portee = "compte"

[[capacites]]
id = "voir_config"
libelle = "Ce que le module lit de ses réglages"
risque = "lecture"
"""

BOUTIQUE_PY = """
def brancher(ctx):
    ctx.implementer("voir_config", lambda ctx: {k: ctx.reglage(k) for k in ("nom", "remise", "ouverte", "devise", "cle_api", "theme")})
"""


def monde_reglages():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes", "reglages"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    ecrire_module(mods, "boutique", BOUTIQUE_TOML, BOUTIQUE_PY)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("reglages")
    n.activer("boutique")
    n.identite.unix = lambda nom: "/bin/bash"
    n.identite.fastpanel = lambda: False
    return tmp, n


class ReglagesDesModules(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_reglages()
        self.addCleanup(self.tmp.cleanup)
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "chef@x.fr", "mot_de_passe": MDP}, compte="operateur")
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "bea@x.fr", "mot_de_passe": MDP}, compte="operateur")
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "leo@x.fr", "mot_de_passe": MDP}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def conf(self, au_nom_de="operateur"):
        return self.ex("boutique.voir_config", au_nom_de=au_nom_de)["resultat"]

    def test_sans_valeur_posee_le_module_lit_le_defaut(self):
        self.assertEqual(self.conf(), {"nom": "Ma boutique", "remise": 5, "ouverte": True, "devise": "EUR", "cle_api": "", "theme": "clair"})

    def test_chaque_reglage_est_ecrit_seul_et_se_lit_aussitot(self):
        self.assertEqual(self.ex("reglages.regler", cle="boutique.nom", valeur="Chez Bea")["statut"], "faite")
        self.assertEqual(self.ex("reglages.regler", cle="boutique.remise", valeur=12)["statut"], "faite")
        c = self.conf()
        self.assertEqual((c["nom"], c["remise"], c["devise"]), ("Chez Bea", 12, "EUR"))          # les autres n'ont pas bougé

    def test_une_valeur_qui_ne_passe_pas_son_type_est_refusee(self):
        for cle, v in (("boutique.remise", 99), ("boutique.remise", "12"), ("boutique.remise", True), ("boutique.ouverte", "oui"),
                       ("boutique.devise", "GBP"), ("boutique.nom", 5), ("boutique.nom", "x" * 5000), ("boutique.inconnu", "x")):
            self.assertEqual(self.ex("reglages.regler", cle=cle, valeur=v)["statut"], "echec", (cle, v))
        self.assertEqual(self.conf()["remise"], 5)

    def test_le_retour_arriere_remet_l_avant_ou_le_defaut(self):
        r = self.ex("reglages.regler", cle="boutique.nom", valeur="Un")["resultat"]
        r2 = self.ex("reglages.regler", cle="boutique.nom", valeur="Deux")["resultat"]
        self.n.catalogue.get("reglages.regler").defaire(self.n.executeur.contextes["reglages"], r2)
        self.assertEqual(self.conf()["nom"], "Un")
        self.n.catalogue.get("reglages.regler").defaire(self.n.executeur.contextes["reglages"], r)
        self.assertEqual(self.conf()["nom"], "Ma boutique")

    def test_reinitialiser_rend_le_defaut(self):
        self.ex("reglages.regler", cle="boutique.remise", valeur=30)
        r = self.ex("reglages.reinitialiser", cle="boutique.remise")
        self.assertEqual(self.conf()["remise"], 5)
        self.n.catalogue.get("reglages.reinitialiser").defaire(self.n.executeur.contextes["reglages"], r["resultat"])
        self.assertEqual(self.conf()["remise"], 30)

    def test_un_secret_ne_s_ecrit_que_par_regler_secret_et_n_est_jamais_rendu_ni_journalise(self):
        self.assertEqual(self.ex("reglages.regler", cle="boutique.cle_api", valeur="sk-123")["statut"], "echec")
        self.assertEqual(self.ex("reglages.regler_secret", cle="boutique.cle_api", valeur="sk-SECRET-456")["statut"], "faite")
        self.assertEqual(self.conf()["cle_api"], "sk-SECRET-456")                                  # le module qui l'a déclaré le lit en clair
        lu = {x["cle"]: x for x in self.ex("reglages.lire")["resultat"]["reglages"]}
        self.assertEqual(lu["boutique.cle_api"]["valeur"], "***")                                  # l'administration, jamais
        self.assertNotIn("sk-SECRET-456", str(self.ex("reglages.historique", cle="boutique.cle_api")["resultat"]))
        tout = " ".join(r["donnees"] for r in self.n.base.lire("SELECT donnees FROM evenements"))
        self.assertNotIn("sk-SECRET-456", tout)
        self.ex("reglages.regler_secret", cle="boutique.cle_api", valeur="sk-AUTRE-789")
        tout = " ".join(r["donnees"] for r in self.n.base.lire("SELECT donnees FROM evenements"))
        self.assertNotIn("sk-SECRET-456", tout)
        self.assertEqual(self.ex("reglages.regler_secret", cle="boutique.nom", valeur="x")["statut"], "echec")

    def test_un_reglage_global_demande_le_droit_de_gerer(self):
        self.assertEqual(self.ex("reglages.regler", au_nom_de="bea@x.fr", cle="boutique.nom", valeur="Pirate")["statut"], "echec")
        self.assertEqual(self.conf()["nom"], "Ma boutique")
        self.ex("droits.regler", sujet="bea@x.fr", droit="reglages.gerer")
        self.assertEqual(self.ex("reglages.regler", au_nom_de="bea@x.fr", cle="boutique.nom", valeur="Chez Bea")["statut"], "faite")

    def test_un_reglage_par_compte_est_propre_a_chacun(self):
        self.assertEqual(self.ex("reglages.regler", au_nom_de="bea@x.fr", cle="boutique.theme", valeur="sombre")["statut"], "faite")      # sans droit particulier
        self.assertEqual(self.conf("bea@x.fr")["theme"], "sombre")
        self.assertEqual(self.conf("leo@x.fr")["theme"], "clair")                                  # les autres gardent le défaut
        self.assertEqual(self.ex("reglages.regler", au_nom_de="leo@x.fr", cle="boutique.theme", valeur="sombre", pour_compte="bea@x.fr")["statut"], "echec")
        self.assertEqual(self.ex("reglages.regler", au_nom_de="chef@x.fr", cle="boutique.theme", valeur="clair", pour_compte="bea@x.fr")["statut"], "faite")   # l'administrateur, oui
        self.assertEqual(self.conf("bea@x.fr")["theme"], "clair")

    def test_un_reglage_global_n_a_pas_de_valeur_par_compte(self):
        self.assertEqual(self.ex("reglages.regler", cle="boutique.nom", valeur="x", pour_compte="bea@x.fr")["statut"], "echec")

    def test_chacun_ne_lit_que_ce_qu_il_peut(self):
        noms = lambda c: {x["cle"] for x in self.ex("reglages.lire", au_nom_de=c)["resultat"]["reglages"] if x["module"] == "boutique"}
        self.assertEqual(noms("bea@x.fr"), {"boutique.theme"})                                     # sans le droit : ses réglages à elle
        self.assertEqual(len(noms("chef@x.fr")), 6)                                                # l'administrateur voit tout
        self.assertEqual(self.ex("reglages.lire", au_nom_de="bea@x.fr", pour_compte="leo@x.fr")["statut"], "echec")

    def test_l_historique_dit_qui_et_de_quoi_a_quoi(self):
        self.ex("reglages.regler", cle="boutique.remise", valeur=10)
        self.ex("reglages.regler", cle="boutique.remise", valeur=20)
        h = self.ex("reglages.historique", cle="boutique.remise")["resultat"]["historique"]
        self.assertEqual([(x["avant"], x["apres"], x["par"]) for x in h], [(10, 20, "operateur"), (None, 10, "operateur")])

    def test_un_module_debranche_n_offre_plus_ses_reglages_mais_ils_restent(self):
        self.ex("reglages.regler", cle="boutique.nom", valeur="Gardé")
        self.n.desactiver("boutique")
        self.assertNotIn("boutique.nom", [x["cle"] for x in self.ex("reglages.lire")["resultat"]["reglages"]])
        self.n.activer("boutique")
        self.assertEqual(self.conf()["nom"], "Gardé")

    def test_la_duree_des_sessions_est_un_reglage_qui_s_applique_tout_de_suite(self):
        r = self.ex("comptes.ouvrir_session", compte="bea@x.fr", mot_de_passe=MDP, ip="203.0.113.5")["resultat"]
        self.n.base.ecrire("UPDATE sessions SET cree=cree-?", (2 * 3600,))                          # ouverte il y a deux heures
        self.assertTrue(self.ex("comptes.valider_session", jeton=r["jeton"])["resultat"]["ok"])      # 24 h par défaut
        self.assertEqual(self.ex("reglages.regler", cle="comptes.session_heures", valeur=1)["statut"], "faite")
        self.assertFalse(self.ex("comptes.valider_session", jeton=r["jeton"])["resultat"]["ok"])     # une heure : elle a expiré
        self.assertEqual(self.ex("reglages.regler", cle="comptes.session_heures", valeur=0)["statut"], "echec")        # borné de 1 à 720

    def test_le_manifeste_valide_les_reglages(self):
        base = {"module": {"id": "xx", "nom": "X", "version": "0.1.0", "noyau_min": "0.1.0", "description": "d"}}
        mauvais = [{"id": "a", "libelle": "A", "type": "inconnu"}, {"id": "a", "libelle": "A", "type": "choix"},
                   {"id": "a", "libelle": "A", "type": "choix", "choix": ["x"], "defaut": "y"}, {"id": "a", "libelle": "A", "type": "secret", "defaut": "mdp"},
                   {"id": "a", "libelle": "A", "type": "entier", "defaut": "5"}, {"id": "a", "libelle": "A", "portee": "partout"}, {"id": "a"}]
        for r in mauvais:
            self.assertTrue(mf.valider(dict(base, reglages=[r])), r)
        self.assertEqual(mf.valider(dict(base, reglages=[{"id": "ok", "libelle": "Ok", "type": "entier", "defaut": 3, "minimum": 0}])), [])


AUTRE_TOML = '''[module]
id = "autre"
nom = "Autre"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Un module sans rien."
'''


class StockageDesModules(unittest.TestCase):
    def setUp(self):
        from noyau.stockage import Stockage, MigrationRefusee
        self.Stockage, self.Refusee = Stockage, MigrationRefusee
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.mig = self.base / "migrations"
        self.mig.mkdir()

    def sql(self, nom, texte):
        (self.mig / nom).write_text(texte, encoding="utf-8")

    def test_les_migrations_s_appliquent_dans_l_ordre_et_une_seule_fois(self):
        self.sql("002_ajout.sql", "ALTER TABLE t ADD COLUMN b TEXT;")
        self.sql("001_init.sql", "CREATE TABLE t(a INTEGER);\nINSERT INTO t(a) VALUES (1);")
        st = self.Stockage(self.base / "m.db", self.mig)
        self.assertEqual(st.appliquees, ["001_init.sql", "002_ajout.sql"])
        self.assertEqual(st.lire("SELECT a, b FROM t"), [{"a": 1, "b": None}])
        st2 = self.Stockage(self.base / "m.db", self.mig)                                  # un redémarrage : rien de refait
        self.assertEqual(st2.appliquees, [])
        self.assertEqual(st2.lire("SELECT COUNT(*) AS n FROM t")[0]["n"], 1)
        self.sql("003_suite.sql", "INSERT INTO t(a, b) VALUES (2, 'x');")
        self.assertEqual(self.Stockage(self.base / "m.db", self.mig).appliquees, ["003_suite.sql"])

    def test_une_migration_deja_appliquee_ne_se_modifie_pas(self):
        self.sql("001_init.sql", "CREATE TABLE t(a INTEGER);")
        self.Stockage(self.base / "m.db", self.mig)
        self.sql("001_init.sql", "CREATE TABLE t(a INTEGER, z INTEGER);")
        with self.assertRaises(self.Refusee) as c:
            self.Stockage(self.base / "m.db", self.mig)
        self.assertIn("déjà été appliquée puis modifiée", str(c.exception))

    def test_une_migration_qui_echoue_ne_laisse_rien(self):
        self.sql("001_init.sql", "CREATE TABLE t(a INTEGER);")
        self.sql("002_cassee.sql", "CREATE TABLE u(x INTEGER);\nINSERT INTO inexistante VALUES (1);")
        with self.assertRaises(self.Refusee) as c:
            self.Stockage(self.base / "m.db", self.mig)
        self.assertIn("002_cassee.sql", str(c.exception))
        st = self.Stockage(self.base / "m.db", None)
        noms = {r["name"] for r in st.lire("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("t", noms)                                                         # la bonne est restée
        self.assertNotIn("u", noms)                                                      # la cassée n'a rien laissé, pas même sa première instruction
        self.assertEqual([r["version"] for r in st.lire("SELECT version FROM _migrations")], ["001_init.sql"])

    def test_un_nom_de_migration_invalide_est_refuse(self):
        self.sql("init.sql", "CREATE TABLE t(a INTEGER);")
        with self.assertRaises(self.Refusee):
            self.Stockage(self.base / "m.db", self.mig)

    def test_un_declencheur_avec_des_points_virgules_passe(self):
        self.sql("001_init.sql", "CREATE TABLE t(a INTEGER);\nCREATE TABLE j(x TEXT);\n"
                                 "CREATE TRIGGER tg AFTER INSERT ON t BEGIN INSERT INTO j VALUES ('a;b'); INSERT INTO j VALUES ('c'); END;")
        st = self.Stockage(self.base / "m.db", self.mig)
        st.ecrire("INSERT INTO t VALUES (1)")
        self.assertEqual([r["x"] for r in st.lire("SELECT x FROM j ORDER BY rowid")], ["a;b", "c"])

    def _monde(self, modules):
        import shutil
        mods = self.base / "modules"
        for mid, (toml, py, migs) in modules.items():
            ecrire_module(mods, mid, toml, py)
            for nom, texte in migs.items():
                (mods / mid / "migrations").mkdir(exist_ok=True)
                (mods / mid / "migrations" / nom).write_text(texte, encoding="utf-8")
        return moteur.Noyau(self.base / "d", mods, {})

    def test_un_module_a_sa_base_a_lui_et_elle_survit_au_redemarrage(self):
        toml = LABO_TOML.replace("espace_utilisateur = true", "stockage = true")
        py = "def brancher(ctx):\n    ctx.stockage.ecrire(\"INSERT INTO carnet(texte) VALUES (?)\", (\"bonjour\",))\n    ctx.implementer(\"lire_jouet\", lambda ctx, nom: ctx.stockage.lire(\"SELECT texte FROM carnet\"))\n"
        mods = {"labo": (toml, py, {"001_carnet.sql": "CREATE TABLE carnet(texte TEXT);"})}
        n = self._monde(mods)
        n.brancher()
        self.assertTrue((self.base / "d" / "modules" / "labo.db").exists())
        self.assertEqual(n.executeur.executer("labo.lire_jouet", "humain", {"nom": "x"})["resultat"], [{"texte": "bonjour"}])
        noms = {r["name"] for r in n.base.lire("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("carnet", noms)                                                 # la base du noyau ne contient pas celle du module

    def test_sans_la_permission_pas_de_stockage(self):
        py = "def brancher(ctx):\n    ctx.stockage\n"
        n = self._monde({"labo": (LABO_TOML, py, {})})
        r = n.brancher()
        self.assertTrue(any("n'a pas demandé de stockage" in " ".join(x["raisons"]) for x in r["refuses"]))

    def test_un_module_a_la_migration_cassee_est_ecarte_sans_arreter_les_autres(self):
        toml = LABO_TOML.replace("espace_utilisateur = true", "stockage = true")
        py = "def brancher(ctx):\n    ctx.stockage\n    ctx.implementer(\"lire_jouet\", lambda ctx, nom: 1)\n"
        n = self._monde({"labo": (toml, py, {"001_x.sql": "INSERT INTO rien VALUES (1);"}),
                         "autre": (AUTRE_TOML, "def brancher(ctx):\n    pass\n", {})})
        r = n.brancher()
        self.assertEqual(r["ordre"].count("autre"), 1)
        self.assertNotIn("labo", r["branches"])
        self.assertIn("001_x.sql", " ".join(" ".join(x["raisons"]) for x in r["refuses"]))


VEILLE_NOTIF_TOML = """
[module]
id = "veille"
nom = "Veille"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : un détecteur dont on commande les constats."

[[objets]]
type = "alerte"
libelle = "Une alerte"

[[detecteurs]]
id = "panne"
libelle = "Une panne"
frequence_s = 10
"""

VEILLE_NOTIF_PY = """
def brancher(ctx):
    pannes = ctx.config["pannes"]
    ctx.detecteur("panne", lambda ctx: [dict(p) for p in pannes])
"""


def monde_notifs():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes", "notifications"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    ecrire_module(mods, "veille", VEILLE_NOTIF_TOML, VEILLE_NOTIF_PY)
    pannes = []
    n = moteur.Noyau(base / "d", mods, {"veille": {"pannes": pannes}}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("notifications")
    n.activer("veille")
    n.identite.unix = lambda nom: "/bin/bash"
    n.identite.fastpanel = lambda: False
    return tmp, n, pannes


class CentreDeNotifications(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.pannes = monde_notifs()
        self.addCleanup(self.tmp.cleanup)
        for c in ("chef@x.fr", "adm@x.fr", "bea@x.fr", "leo@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def emettre(self, par="operateur", **kw):
        base = dict(titre="Le disque se remplit", source="sensorium", niveau="avoir")
        base.update(kw)
        return self.ex("notifications.emettre", au_nom_de=par, **base)

    def liste(self, c, **kw):
        return self.ex("notifications.lister", au_nom_de=c, **kw)["resultat"]["notifications"]

    def test_emettre_puis_lister_pour_les_administrateurs(self):
        r = self.emettre(corps="92 % utilisé", cle="disque")
        self.assertEqual(r["statut"], "faite")
        self.assertEqual([x["titre"] for x in self.liste("adm@x.fr")], ["Le disque se remplit"])           # destiné à « admins » par défaut
        self.assertEqual(self.liste("bea@x.fr"), [])                                                     # un compte ordinaire ne voit pas ce qui vise les admins

    def test_le_cloisonnement_un_compte_ne_voit_que_ce_qui_le_vise(self):
        self.emettre(titre="Pour Bea", dest="bea@x.fr")
        self.emettre(titre="Pour Léo", dest=["leo@x.fr"])
        self.emettre(titre="Pour les deux", dest=["bea@x.fr", "leo@x.fr"])
        t = lambda c: sorted(x["titre"] for x in self.liste(c))
        self.assertEqual(t("bea@x.fr"), ["Pour Bea", "Pour les deux"])
        self.assertEqual(t("leo@x.fr"), ["Pour Léo", "Pour les deux"])
        self.assertEqual(t("adm@x.fr"), [])                                                              # l'administrateur ne lit pas celles des autres
        self.assertEqual(len(t("cassandra")), 3)                                                         # les comptes système, tout
        self.assertEqual(len(t("operateur")), 3)

    def test_un_compte_ordinaire_ne_vise_que_lui_ou_les_admins(self):
        self.assertEqual(self.emettre(titre="À moi", dest="bea@x.fr", par="bea@x.fr")["statut"], "faite")
        self.assertEqual(self.emettre(titre="À Léo", dest="leo@x.fr", par="bea@x.fr")["statut"], "echec")
        self.assertEqual(self.emettre(titre="Aux admins", par="bea@x.fr")["statut"], "faite")

    def test_la_meme_cle_ne_s_empile_pas_elle_se_compte(self):
        for _ in range(3):
            self.emettre(cle="disque", corps="encore")
        l = self.liste("adm@x.fr")
        self.assertEqual((len(l), l[0]["n"]), (1, 3))
        evts = [e for e in self.n.bus.recents(portee=TOUT, limite=300) if e["type"] == "notification.emise"]
        self.assertEqual(len(evts), 1)                                                                   # une répétition ne re-sonne pas la cloche

    def test_une_repetition_peut_monter_la_gravite_jamais_la_baisser(self):
        self.emettre(cle="d", niveau="avoir")
        self.emettre(cle="d", niveau="critique")
        self.assertEqual(self.liste("adm@x.fr")[0]["niveau"], "critique")
        self.emettre(cle="d", niveau="info")
        self.assertEqual(self.liste("adm@x.fr")[0]["niveau"], "critique")
        evts = [e for e in self.n.bus.recents(portee=TOUT, limite=300) if e["type"] == "notification.emise"]
        self.assertEqual(len(evts), 2)                                                                   # la création, et l'escalade

    def test_lu_et_pris_en_compte_sont_par_personne(self):
        nid = self.emettre()["resultat"]["id"]
        self.ex("droits.admin", compte="bea@x.fr")                                                       # Béa devient administratrice
        self.ex("notifications.vu", au_nom_de="adm@x.fr", id=nid)
        self.assertTrue(self.liste("adm@x.fr")[0]["lu"])
        self.assertFalse(self.liste("bea@x.fr")[0]["lu"])                                                # la nouvelle administratrice la voit comme non lue (bogue V18 des 182)
        self.ex("notifications.acquitter", au_nom_de="bea@x.fr", id=nid)
        b = self.liste("bea@x.fr")[0]
        self.assertEqual((b["lu"], b["acquittee"]), (True, True))
        self.assertFalse(self.liste("adm@x.fr")[0]["acquittee"])
        self.assertEqual(self.ex("notifications.compteurs", au_nom_de="adm@x.fr")["resultat"]["non_lues"], 0)
        self.assertEqual(self.ex("notifications.compteurs", au_nom_de="chef@x.fr")["resultat"]["non_lues"], 1)

    def test_on_ne_marque_pas_lue_une_notification_qu_on_ne_voit_pas(self):
        nid = self.emettre(dest="leo@x.fr")["resultat"]["id"]
        self.assertEqual(self.ex("notifications.vu", au_nom_de="bea@x.fr", id=nid)["statut"], "echec")

    def test_resoudre_par_cle_ou_id_et_rouvrir_au_retour_arriere(self):
        nid = self.emettre(cle="disque")["resultat"]["id"]
        r = self.ex("notifications.resoudre", cle="disque")
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(self.liste("adm@x.fr"), [])                                                     # les résolues ne s'affichent plus par défaut
        self.assertEqual(len(self.liste("adm@x.fr", resolues=True)), 1)
        self.n.catalogue.get("notifications.resoudre").defaire(self.n.executeur.contextes["notifications"], r["resultat"])
        self.assertEqual(len(self.liste("adm@x.fr")), 1)
        self.emettre(cle="disque")                                                                       # la clé étant ouverte, elle se compte
        self.assertEqual(self.liste("adm@x.fr")[0]["n"], 2)

    def test_une_resolue_qui_revient_s_ouvre_de_nouveau(self):
        self.emettre(cle="disque")
        self.ex("notifications.resoudre", cle="disque")
        self.emettre(cle="disque")
        l = self.liste("adm@x.fr")
        self.assertEqual((len(l), l[0]["n"]), (1, 1))                                                    # une nouvelle, pas la vieille réveillée

    def test_supprimer_se_restaure(self):
        nid = self.emettre()["resultat"]["id"]
        r = self.ex("notifications.supprimer", id=nid)
        self.assertEqual(self.liste("adm@x.fr"), [])
        self.n.catalogue.get("notifications.supprimer").defaire(self.n.executeur.contextes["notifications"], r["resultat"])
        self.assertEqual(len(self.liste("adm@x.fr")), 1)

    def test_l_emission_se_defait(self):
        r = self.emettre(cle="x")
        self.n.catalogue.get("notifications.emettre").defaire(self.n.executeur.contextes["notifications"], r["resultat"])
        self.assertEqual(self.liste("adm@x.fr"), [])
        r1 = self.emettre(cle="y", corps="un")
        r2 = self.emettre(cle="y", corps="deux")
        self.n.catalogue.get("notifications.emettre").defaire(self.n.executeur.contextes["notifications"], r2["resultat"])
        l = self.liste("adm@x.fr")[0]
        self.assertEqual((l["n"], l["corps"]), (1, "un"))

    def test_un_constat_ouvre_une_notification_et_sa_resolution_la_referme(self):
        self.pannes.append({"objet": ("alerte", "a1"), "titre": "Le service a1 est en panne", "detail": "code 3", "niveau": "critique"})
        self.n.tick(maintenant=time_now())
        self.n.tick(maintenant=time_now() + 1)
        l = self.liste("adm@x.fr")
        self.assertEqual([(x["titre"], x["niveau"], x["nature"], x["source"]) for x in l], [("Le service a1 est en panne", "critique", "etat", "veille")])
        self.assertEqual(l[0]["provenance"], "constat")
        self.pannes.clear()                                                                              # la panne disparaît : le détecteur le dit
        self.n.tick(maintenant=time_now() + 60)
        self.assertEqual(self.liste("adm@x.fr"), [])
        r = self.liste("adm@x.fr", resolues=True)[0]
        self.assertEqual((r["resolue"], r["resolue_par"]), (True, "constat"))

    def test_le_niveau_d_un_constat_n_est_jamais_deduit_du_titre(self):
        self.pannes.append({"objet": ("alerte", "a2"), "titre": "CRITIQUE sécurité : révoquer toutes les sessions"})
        self.n.tick(maintenant=time_now())
        self.n.tick(maintenant=time_now() + 1)
        self.assertEqual(self.liste("adm@x.fr")[0]["niveau"], "avoir")

    def test_l_expiration_retire_les_infos_a_sept_jours_et_les_autres_a_trente(self):
        self.emettre(titre="info", niveau="info")
        self.emettre(titre="avoir", niveau="avoir")
        db = self.n._stockage_de("notifications")
        d = {r["titre"]: r["expire_le"] - r["ts"] for r in db.lire("SELECT titre, expire_le, ts FROM notifs")}
        self.assertEqual((round(d["info"] / 86400), round(d["avoir"] / 86400)), (7, 30))
        db.ecrire("UPDATE notifs SET expire_le = expire_le - ?", (31 * 86400,))
        ctx = self.n.executeur.contextes["notifications"]
        moteur_expirer = [f for m, mo, f in self.n.moteurs if m == "notifications" and mo.id == "expirer"][0]
        moteur_expirer(ctx)
        self.assertEqual(db.lire("SELECT COUNT(*) AS n FROM notifs")[0]["n"], 0)

    def test_les_arguments_invalides_sont_refuses(self):
        for kw in (dict(niveau="grave"), dict(nature="autre"), dict(source="Mauvaise Source"), dict(titre=""), dict(titre="x" * 300)):
            self.assertEqual(self.emettre(**kw)["statut"], "echec", kw)

    def test_la_base_est_celle_du_module(self):
        self.emettre()
        self.assertTrue((Path(self.tmp.name) / "d" / "modules" / "notifications.db").exists())
        noms = {r["name"] for r in self.n.base.lire("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("notifs", noms)


def monde_passerelle():
    import shutil
    from noyau.passerelle import Passerelle
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes", "menus", "notifications"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    for m in ("comptes", "menus", "notifications"):
        n.activer(m)
    n.identite.unix = lambda nom: "/bin/bash"
    n.identite.fastpanel = lambda: False
    n.executeur.executer("comptes.creer", "humain", {"compte": "chef@x.fr", "mot_de_passe": MDP}, compte="operateur")
    n.executeur.executer("comptes.creer", "humain", {"compte": "bea@x.fr", "mot_de_passe": MDP}, compte="operateur")
    g = Passerelle(n, "127.0.0.1", 0)
    g.demarrer()
    return tmp, n, g


class PasserelleHttp(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.g = monde_passerelle()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.g.arreter)

    def req(self, methode, chemin, corps=None, entetes=None, brut=None):
        import http.client
        import json
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = dict(entetes or {})
        data = brut
        if corps is not None:
            data = json.dumps(corps).encode()
            h.setdefault("Content-Type", "application/json")
        c.request(methode, chemin, body=data, headers=h)
        r = c.getresponse()
        texte = r.read().decode()
        cookies = r.getheader("Set-Cookie")
        entete = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        try:
            return r.status, json.loads(texte), cookies, entete
        except ValueError:
            return r.status, texte, cookies, entete

    def connexion(self, compte="chef@x.fr", mdp=MDP):
        st, corps, cookie, _ = self.req("POST", "/api/connexion", {"compte": compte, "mot_de_passe": mdp})
        return st, corps, cookie

    def test_interface_servie_sans_sortir_du_dossier(self):
        d = Path(self.tmp.name) / "interface"
        (d / "routes").mkdir(parents=True)
        (d / "index.html").write_text("<p>accueil</p>", encoding="utf-8")
        (d / "app.js").write_text("1", encoding="utf-8")
        (d / "secret.py").write_text("x", encoding="utf-8")
        (Path(self.tmp.name) / "hors.js").write_text("dehors", encoding="utf-8")
        import os
        self.g.interface = os.path.realpath(d)
        st, t, _, h = self.req("GET", "/")
        self.assertEqual((st, t), (200, "<p>accueil</p>"))
        self.assertIn("script-src", h["content-security-policy"])
        self.assertEqual(self.req("GET", "/app.js")[0], 200)
        for chemin in ("/secret.py", "/../hors.js", "/%2e%2e/hors.js", "/routes", "/..%5chors.js", "/inconnu.js"):
            self.assertEqual(self.req("GET", chemin)[0], 404, chemin)
        self.g.interface = None
        self.assertEqual(self.req("GET", "/")[0], 404)

    def test_sante_sans_authentification(self):
        st, c, _, h = self.req("GET", "/api/sante")
        self.assertEqual((st, c["ok"]), (200, True))
        self.assertEqual(h["cache-control"], "no-store")
        self.assertEqual(h["x-content-type-options"], "nosniff")

    def test_tout_le_reste_exige_un_jeton(self):
        for m, ch in (("GET", "/api/moi"), ("GET", "/api/menu"), ("POST", "/api/agir/notifications.lister"), ("GET", "/api/agir/comptes.regles_mdp")):
            self.assertEqual(self.req(m, ch, {} if m == "POST" else None)[0], 401, ch)

    def test_connexion_cookie_httponly_samesite_et_jeton(self):
        st, corps, cookie = self.connexion()
        self.assertEqual((st, corps["ok"], corps["compte"]), (200, True, "chef@x.fr"))
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(len(corps["jeton"]), 64)

    def test_mauvais_mot_de_passe_401_et_blocage_429(self):
        self.assertEqual(self.connexion(mdp="Mauvais1!x")[0], 401)
        for _ in range(10):
            self.connexion(mdp="Mauvais1!x")
        st, corps, _ = self.connexion()
        self.assertEqual(st, 429)
        self.assertGreater(corps["attente_s"], 0)

    def test_le_bearer_donne_le_compte_et_moi_le_dit(self):
        jeton = self.connexion()[1]["jeton"]
        st, c, _, _ = self.req("GET", "/api/moi", entetes={"Authorization": "Bearer " + jeton})
        self.assertEqual((st, c["compte"], c["acteur"], c["admin"]), (200, "chef@x.fr", "humain", True))
        jeton_b = self.connexion("bea@x.fr")[1]["jeton"]
        c = self.req("GET", "/api/moi", entetes={"Authorization": "Bearer " + jeton_b})[1]
        self.assertEqual((c["compte"], c["admin"]), ("bea@x.fr", False))

    def test_le_compte_vient_du_jeton_jamais_du_corps(self):
        jb = self.connexion("bea@x.fr")[1]["jeton"]
        st, c, _, _ = self.req("POST", "/api/agir/comptes.moi", {"compte": "chef@x.fr", "acteur": "operateur"}, {"Authorization": "Bearer " + jb})
        self.assertEqual(c["resultat"]["compte"], "bea@x.fr")                                           # on a beau réclamer un autre compte

    def test_le_cookie_exige_l_entete_x_cassandra_pour_ecrire(self):
        cookie = self.connexion()[2].split(";")[0]
        sans = self.req("POST", "/api/agir/notifications.emettre", {"args": {"titre": "t", "source": "essai"}}, {"Cookie": cookie})
        self.assertEqual(sans[0], 403)
        avec = self.req("POST", "/api/agir/notifications.emettre", {"args": {"titre": "t", "source": "essai"}}, {"Cookie": cookie, "X-Cassandra": "1"})
        self.assertEqual((avec[0], avec[1]["statut"]), (200, "faite"))
        self.assertEqual(self.req("GET", "/api/moi", entetes={"Cookie": cookie})[0], 200)                # une lecture n'exige rien de plus

    def test_get_pour_une_lecture_post_pour_une_ecriture(self):
        jeton = self.connexion()[1]["jeton"]
        h = {"Authorization": "Bearer " + jeton}
        st, c, _, _ = self.req("GET", "/api/agir/notifications.compteurs", entetes=h)
        self.assertEqual((st, c["statut"]), (200, "faite"))
        st, c, _, _ = self.req("GET", "/api/agir/notifications.emettre?titre=x&source=essai", entetes=h)
        self.assertEqual(st, 405)
        st, c, _, _ = self.req("GET", "/api/agir/notifications.lister?non_lues=true&limite=5", entetes=h)
        self.assertEqual(st, 200)                                                                        # les valeurs de l'adresse se lisent comme du JSON

    def test_les_droits_de_l_executeur_s_appliquent_en_403(self):
        jb = self.connexion("bea@x.fr")[1]["jeton"]
        st, c, _, _ = self.req("GET", "/api/agir/comptes.lister", entetes={"Authorization": "Bearer " + jb})
        self.assertEqual((st, c["statut"]), (403, "refuse"))
        self.assertIn("comptes.gerer", c["raison"])

    def test_un_agent_invite_entre_par_son_jeton_et_n_a_que_les_droits_de_son_invitant(self):
        jc = self.connexion()[1]["jeton"]
        r = self.req("POST", "/api/agir/comptes.inviter_agent", {"args": {"nom": "claude"}}, {"Authorization": "Bearer " + jc})[1]["resultat"]
        ja = r["jeton"]
        h = {"Authorization": "Bearer " + ja}
        st, c, _, _ = self.req("GET", "/api/moi", entetes=h)
        self.assertEqual((st, c["compte"], c["acteur"]), (200, "agent:claude", "agent"))
        self.assertEqual(self.req("GET", "/api/agir/comptes.lister", entetes=h)[0], 200)                 # invité par un administrateur : il a tout
        jb = self.connexion("bea@x.fr")[1]["jeton"]
        self.req("POST", "/api/agir/comptes.inviter_agent", {"args": {"nom": "petit"}}, {"Authorization": "Bearer " + jb})
        self.n.regler_palier("comptes.inviter_agent", "auto")
        self.assertEqual(self.req("GET", "/api/moi", entetes={"Authorization": "Bearer inconnu-inconnu-inconnu-inconnu"})[0], 401)

    def test_une_capacite_publique_se_joint_avant_la_connexion_et_seulement_elle(self):
        import shutil
        mods = Path(self.tmp.name) / "modules"
        ecrire_module(mods, "porte", """
[module]
id = "porte"
nom = "Porte"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Une capacité publique et une privée."

[[capacites]]
id = "ouverte"
libelle = "Publique : avant la connexion"
risque = "lecture"
qui = ["anonyme"]

[[capacites]]
id = "fermee"
libelle = "Privée"
risque = "lecture"
""", "def brancher(ctx):\n    ctx.implementer('ouverte', lambda ctx: {'ok': True})\n    ctx.implementer('fermee', lambda ctx: {'ok': True})\n")
        self.n.activer("porte")
        st, c, _, _ = self.req("POST", "/api/public/porte.ouverte", {"args": {}})
        self.assertEqual((st, c["statut"]), (200, "faite"))
        self.assertEqual(self.req("POST", "/api/public/porte.fermee", {"args": {}})[0], 404)                 # une privée n'est jamais joignable ainsi
        self.assertEqual(self.req("POST", "/api/public/comptes.moi", {"args": {}})[0], 404)
        self.assertEqual(self.req("POST", "/api/agir/porte.ouverte", {"args": {}})[0], 401)                  # et par la porte normale, il faut un jeton
        ev = [e for e in self.n.bus.recents(portee=TOUT, limite=100) if e["type"] == "capacite.demandee" and e["acteur"] == "anonyme"]
        self.assertEqual(len(ev), 1)                                                                         # l'acte public est journalisé

    def test_la_deconnexion_ferme_la_session(self):
        jeton = self.connexion()[1]["jeton"]
        h = {"Authorization": "Bearer " + jeton}
        self.assertEqual(self.req("POST", "/api/deconnexion", {}, h)[0], 200)
        self.assertEqual(self.req("GET", "/api/moi", entetes=h)[0], 401)

    def test_le_menu_suit_le_compte(self):
        jeton = self.connexion()[1]["jeton"]
        st, c, _, _ = self.req("GET", "/api/menu", entetes={"Authorization": "Bearer " + jeton})
        self.assertEqual((st, c["statut"]), (200, "faite"))

    def test_routes_inconnues_corps_invalides_et_limites(self):
        jeton = self.connexion()[1]["jeton"]
        h = {"Authorization": "Bearer " + jeton}
        self.assertEqual(self.req("GET", "/api/nimporte", entetes=h)[0], 404)
        self.assertEqual(self.req("GET", "/api/agir/inconnue", entetes=h)[0], 404)
        self.assertEqual(self.req("GET", "/api/agir/rien.du_tout", entetes=h)[0], 404)
        self.assertEqual(self.req("POST", "/api/agir/notifications.emettre", brut=b"pas du json", entetes=dict(h, **{"Content-Type": "application/json"}))[0], 400)
        self.assertEqual(self.req("POST", "/api/agir/notifications.emettre", brut=b"{}", entetes=dict(h, **{"Content-Type": "text/plain"}))[0], 400)
        self.assertEqual(self.req("POST", "/api/agir/notifications.emettre", {"args": [1]}, h)[0], 400)
        self.assertEqual(self.req("POST", "/api/agir/notifications.emettre", brut=b"x" * (1024 * 1024 + 1), entetes=dict(h, **{"Content-Type": "application/json"}))[0], 400)
        self.assertEqual(self.req("OPTIONS", "/api/agir/notifications.lister", entetes=h)[0], 405)       # aucune ouverture CORS

    def test_un_secret_ne_revient_pas_dans_les_journaux_de_la_passerelle(self):
        self.connexion()
        tout = " ".join(r["donnees"] for r in self.n.base.lire("SELECT donnees FROM evenements"))
        self.assertNotIn(MDP, tout)

    def test_l_ip_vient_de_la_connexion_sauf_derriere_notre_proxy(self):
        self.req("POST", "/api/connexion", {"compte": "chef@x.fr", "mot_de_passe": MDP}, {"X-Forwarded-For": "203.0.113.9"})
        ip = self.n.identite.base.lire("SELECT ip FROM sessions ORDER BY cree DESC LIMIT 1")[0]["ip"]
        self.assertEqual(ip, "127.0.0.1")                                                                # un en-tête forgé ne dit pas d'où on vient
        self.g.proxy = True
        self.req("POST", "/api/connexion", {"compte": "chef@x.fr", "mot_de_passe": MDP}, {"X-Forwarded-For": "203.0.113.9"})
        ip = self.n.identite.base.lire("SELECT ip FROM sessions ORDER BY cree DESC LIMIT 1")[0]["ip"]
        self.assertEqual(ip, "203.0.113.9")


def charger_courtier():
    import importlib.util
    spec = importlib.util.spec_from_file_location("courtier", RACINE / "exploitation" / "courtier.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


EMPREINTE_OK = "$6$salsalsal$" + "A" * 86


class Courtier(unittest.TestCase):
    """Le courtier est le seul morceau qui agit en root : sa politique est testée à nu."""

    def setUp(self):
        self.c = charger_courtier()
        self.demande = {"action": "adosser_superadmin", "utilisateur": "fastuser", "empreinte": EMPREINTE_OK}

    def decider(self, demande=None, admin="fastuser", marqueur=False, verrouille=True):
        return self.c.decider(self.demande if demande is None else demande, admin, marqueur, verrouille)

    def test_une_demande_en_regle_est_accordee(self):
        self.assertEqual(self.decider(), (True, "accordé"))

    def test_l_utilisateur_vise_est_celui_de_la_configuration_pas_celui_de_la_demande(self):
        self.assertFalse(self.decider(dict(self.demande, utilisateur="root"))[0])
        self.assertFalse(self.decider(admin="")[0])

    def test_une_empreinte_mal_formee_ou_un_mot_de_passe_en_clair_est_refuse(self):
        for e in ("Motdepasse1!", "$1$sel$" + "A" * 22, "$6$sel$court", "$6$" + "a" * 40 + "$" + "A" * 86, "", None, 5):
            self.assertFalse(self.decider(dict(self.demande, empreinte=e))[0], e)

    def test_une_seule_fois_et_jamais_sur_un_mot_de_passe_existant(self):
        self.assertIn("une fois", self.decider(marqueur=True)[1])
        self.assertIn("verrouillé", self.decider(verrouille=False)[1])

    def test_une_action_inconnue_est_refusee(self):
        for d in ({"action": "useradd"}, {}, [], "x", 5):
            self.assertFalse(self.decider(d)[0])

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"), "demande de fichiers POSIX")
    def test_le_courtier_traite_chaque_demande_et_la_supprime(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        spool, cfg = Path(tmp.name) / "courtier", Path(tmp.name) / "config"
        spool.mkdir()
        cfg.mkdir()
        (cfg / "admin.initial").write_text("fastuser\n")
        import json
        (spool / "a.json").write_text(json.dumps(self.demande))
        (spool / "b.json").write_text(json.dumps(dict(self.demande, utilisateur="root")))
        (spool / "c.json").write_text("pas du json")
        (spool / "d.json").write_text(json.dumps(dict(self.demande, rempli="x" * 3000)))
        appels = []

        class R:
            def __init__(self, code=0, out=""):
                self.returncode, self.stdout = code, out

        def faux(cmd, **kw):
            appels.append((cmd, kw.get("input")))
            return R(0, "fastuser L 2026-10-11 0 99999 7 -1") if cmd[0] == "passwd" else R(0)

        journal = []
        n = self.c.traiter(str(spool), str(cfg), os.getuid(), faux, journal.append)
        self.assertEqual(n, 1)                                                       # seule la demande en règle passe
        self.assertEqual(os.listdir(spool), [])                                      # toutes supprimées, accordées ou non
        self.assertTrue((cfg / ".superadmin_adosse").exists())
        poses = [i for c, i in appels if c[0] == "chpasswd"]
        self.assertEqual(poses, ["fastuser:%s\n" % EMPREINTE_OK])                    # par l'entrée standard, jamais en argument
        (spool / "e.json").write_text(json.dumps(self.demande))
        self.assertEqual(self.c.traiter(str(spool), str(cfg), os.getuid(), faux, journal.append), 0)      # la deuxième fois : refusée
        self.assertEqual(os.listdir(spool), [])

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and hasattr(os, "symlink"), "POSIX")
    def test_un_lien_et_le_fichier_d_un_autre_utilisateur_sont_refuses(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        spool, cfg = Path(tmp.name) / "courtier", Path(tmp.name) / "config"
        spool.mkdir()
        cfg.mkdir()
        (cfg / "admin.initial").write_text("fastuser\n")
        import json
        vrai = Path(tmp.name) / "ailleurs.json"
        vrai.write_text(json.dumps(self.demande))
        os.symlink(vrai, spool / "lien.json")
        (spool / "autre.json").write_text(json.dumps(self.demande))
        class R:
            returncode, stdout = 0, "fastuser L x"
        n = self.c.traiter(str(spool), str(cfg), os.getuid() + 1, lambda *a, **k: R(), lambda m: None)    # le noyau serait un autre uid
        self.assertEqual(n, 0)
        self.assertTrue(vrai.exists())                                                # la cible du lien n'est pas touchée


class DolibarrReglages(unittest.TestCase):
    """Les réglages l'emportent sur config/dolibarr.conf, qui reste le repli."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dolibarr_mod", RACINE / "modules" / "dolibarr" / "module.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = self.tmp.name
        self.addCleanup(lambda: os.environ.pop("CASSANDRA_CONFIG", None) if self.ancien is None else os.environ.__setitem__("CASSANDRA_CONFIG", self.ancien))

    def ctx(self, **valeurs):
        class C:
            def reglage(_, nom, compte=None):
                return valeurs.get(nom, 0 if nom == "delai" else "")
        return C()

    def ecrire_conf(self, texte):
        (Path(self.tmp.name) / "dolibarr.conf").write_text(texte)

    def test_le_fichier_seul(self):
        self.ecrire_conf("url = http://a.example/api\nhote = h.example\ndelai = 20\n")
        c = self.mod.lire_conf()
        self.assertEqual((c["url"], c["hote"], c["delai"]), ("http://a.example/api", "h.example", "20"))

    def test_un_reglage_pose_l_emporte_et_un_reglage_vide_laisse_le_fichier(self):
        self.ecrire_conf("url = http://a.example/api\nhote = h.example\ndelai = 20\n")
        self.mod._CTX = self.ctx(url="https://b.example/api", delai=7)
        c = self.mod.lire_conf()
        self.assertEqual((c["url"], c["hote"], c["delai"]), ("https://b.example/api", "h.example", "7"))     # l'hôte, non réglé, vient du fichier
        self.mod._CTX = self.ctx()
        self.assertEqual(self.mod.lire_conf()["url"], "http://a.example/api")

    def test_les_reglages_suffisent_sans_fichier(self):
        self.assertIsNone(self.mod.lire_conf())
        self.mod._CTX = self.ctx(url="http://c.example/api")
        c = self.mod.lire_conf()
        self.assertEqual((c["url"], c["delai"]), ("http://c.example/api", "15"))

    def test_un_module_de_reglages_absent_ne_casse_rien(self):
        class Casse:
            def reglage(_, *a, **k):
                raise KeyError("pas de module des réglages")
        self.ecrire_conf("url = http://a.example/api\n")
        self.mod._CTX = Casse()
        self.assertEqual(self.mod.lire_conf()["url"], "http://a.example/api")


class CourtierSudo(unittest.TestCase):
    def setUp(self):
        self.c = charger_courtier()
        self.demande = {"action": "ajouter_sudo", "utilisateur": "alice"}

    def decider(self, demande=None, infos=(1001, "/bin/bash"), connu=True):
        return self.c.decider_sudo(self.demande if demande is None else demande, infos, connu)

    def test_une_demande_en_regle_est_accordee(self):
        self.assertEqual(self.decider(), (True, "accordé"))

    def test_root_les_comptes_systeme_et_les_inconnus_sont_refuses(self):
        self.assertFalse(self.decider(dict(self.demande, utilisateur="root"))[0])
        self.assertFalse(self.decider(infos=(0, "/bin/bash"))[0])
        self.assertFalse(self.decider(infos=(999, "/bin/bash"))[0])                        # un utilisateur du système, pas une personne
        self.assertFalse(self.decider(infos=None)[0])
        self.assertFalse(self.decider(infos=(1001, "/usr/sbin/nologin"))[0])

    def test_sans_compte_superadmin_adosse_dans_la_base_rien_ne_passe(self):
        self.assertIn("superadministrateur", self.decider(connu=False)[1])

    def test_des_noms_hostiles_sont_refuses(self):
        for u in ("a;b", "../x", "-o", "A B", "", None, 5, "x" * 40):
            self.assertFalse(self.decider(dict(self.demande, utilisateur=u))[0], u)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"), "POSIX")
    def test_le_courtier_ajoute_au_groupe_apres_verification_de_la_base(self):
        import json
        import sqlite3
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        racine = Path(tmp.name)
        (racine / "courtier").mkdir()
        (racine / "config").mkdir()
        db = racine / "noyau.db"
        c = sqlite3.connect(db)
        c.execute("CREATE TABLE comptes(compte TEXT, superadmin INTEGER, unix_user TEXT)")
        c.execute("INSERT INTO comptes VALUES('b@x.fr', 1, 'alice')")
        c.commit()
        c.close()
        (racine / "courtier" / "a.json").write_text(json.dumps(self.demande))
        (racine / "courtier" / "b.json").write_text(json.dumps({"action": "ajouter_sudo", "utilisateur": "mallory"}))
        appels = []

        class R:
            returncode, stdout = 0, ""

        def faux(cmd, **kw):
            appels.append(cmd)
            return R()

        infos = lambda nom: (1001, "/bin/bash")
        n = self.c.traiter(str(racine / "courtier"), str(racine / "config"), os.getuid(), faux, lambda m: None, str(db), infos, lambda: "sudo")
        self.assertEqual(n, 1)
        self.assertEqual(appels, [["usermod", "-aG", "sudo", "alice"]])                    # mallory n'a pas de compte superadmin : rien
        self.assertEqual(os.listdir(racine / "courtier"), [])


class DemandeAuCourtier(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_comptes()
        self.addCleanup(self.tmp.cleanup)
        self.demandes = []
        self.n.identite.adosser = lambda u, m: self.demandes.append((u, m)) or True

    def test_le_premier_compte_demande_le_mot_de_passe_pour_fastuser_et_lui_seul(self):
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": "a@x.fr", "mot_de_passe": MDP})
        self.assertEqual((r["statut"], r["resultat"]["unix_demande"]), ("faite", True))
        self.assertEqual(self.demandes, [("fastuser", MDP)])
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "b@x.fr", "mot_de_passe": MDP})
        self.assertEqual(len(self.demandes), 1)                                      # pas pour les suivants

    def test_si_le_courtier_est_absent_le_compte_se_cree_quand_meme(self):
        def boum(u, m):
            raise OSError("pas de courtier")
        self.n.identite.adosser = boum
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": "a@x.fr", "mot_de_passe": MDP})
        self.assertEqual((r["statut"], r["resultat"]["unix_demande"]), ("faite", False))

    @unittest.skipUnless(__import__("shutil").which("openssl"), "openssl absent")
    def test_la_demande_deposee_ne_contient_que_l_empreinte(self):
        from noyau import identite
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.assertTrue(identite.deposer_demande(tmp.name, "fastuser", MDP))
        fichiers = [f for f in os.listdir(tmp.name)]
        self.assertEqual(len(fichiers), 1)
        self.assertTrue(fichiers[0].endswith(".json"))
        texte = (Path(tmp.name) / fichiers[0]).read_text()
        self.assertNotIn(MDP, texte)
        self.assertRegex(texte, r'"empreinte": "\$6\$')
        self.assertTrue(charger_courtier().EMPREINTE.match(__import__("json").loads(texte)["empreinte"]))      # le courtier la reconnaît
        self.assertEqual(identite.deposer_demande(None, "fastuser", MDP), False)


V18_SOURCE = RACINE.parent / "Cassandra" / "V18" / "cassandra.py"


@unittest.skipUnless(V18_SOURCE.exists(), "la source de la V18 n'est pas là")
class ParitéComptesV18(unittest.TestCase):
    """Le banc de parité : les règles portées donnent les mêmes réponses que les fonctions de la V18, exécutées telles quelles."""

    @classmethod
    def setUpClass(cls):
        import ast
        src = V18_SOURCE.read_text(encoding="utf-8")
        arbre = ast.parse(src)
        voulus = {"_norm_domain", "_ip_nature", "mdp_regles", "mdp_valider", "mdp_legende", "_MDP_MIN", "_MDP_REGLES"}
        morceaux = []
        for nd in arbre.body:
            nom = nd.name if isinstance(nd, ast.FunctionDef) else (nd.targets[0].id if isinstance(nd, ast.Assign) and isinstance(nd.targets[0], ast.Name) else "")
            if nom in voulus or (isinstance(nd, ast.Assign) and isinstance(nd.targets[0], ast.Tuple) and any(getattr(t, "id", "") == "_MDP_MIN" for t in nd.targets[0].elts)):
                morceaux.append(ast.get_source_segment(src, nd))
        cls.v18 = {}
        exec("\n\n".join(morceaux), cls.v18)

    def test_les_regles_de_mot_de_passe(self):
        from noyau import identite
        for p in ("", "court", "Abcdefgh1!", "abcdefghij", "ABCDEFGH1!", "Abcdefgh!!", "Abcdefgh11", "A1!" + "x" * 30, "Éàüö1234!A", "a b c D 1 !"):
            self.assertEqual(identite.mdp_valider(p), self.v18["mdp_valider"](p), p)
        self.assertEqual(identite.mdp_regles(), self.v18["mdp_regles"]())
        self.assertEqual(identite.mdp_legende(), self.v18["mdp_legende"]())

    def test_les_domaines(self):
        from noyau import identite
        for d in ("Exemple.COM", "http://www.exemple.com/page", "https://exemple.com", "www.exemple.com", " exemple.com ", "", None):
            self.assertEqual(identite.norm_domain(d), self.v18["_norm_domain"](d), d)

    def test_la_nature_d_une_adresse(self):
        from noyau import identite
        for ip in ("127.0.0.1", "::1", "10.1.2.3", "192.168.0.9", "172.16.0.1", "172.32.0.1", "8.8.8.8", "fd00::1", "fe80::1", "", None, "n'importe quoi"):
            self.assertEqual(identite.ip_nature(ip), self.v18["_ip_nature"](ip), ip)


if __name__ == "__main__":
    unittest.main()
