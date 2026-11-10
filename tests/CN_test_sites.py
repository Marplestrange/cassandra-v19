# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Sites
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c9f321
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Sites : un vrai noyau, des comptes simulés, un panneau et une sonde simulés.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c9f321 ▼▼▼
"""Bancs du module Sites : un vrai noyau, des comptes simulés, un panneau et une sonde simulés."""
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402

CHEF, BEA, LEO = "chef@x.fr", "bea@x.fr", "leo@x.fr"


class _ModuleGlobals:
    """Les globales du module tel que le noyau l'a chargé : y poser une fonction la remplace pour le module (il la cherche à chaque appel)."""

    def __init__(self, g):
        object.__setattr__(self, "_g", g)

    def __setattr__(self, k, v):
        self._g[k] = v

    def __getattr__(self, k):
        return self._g[k]


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "sites", mods / "sites")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("sites")["ok"])
        self.n.droits.regler_admin(CHEF, True)
        self.ctx = self.n.executeur.contextes["sites"]
        self.comptes = [{"compte": CHEF, "sites": [], "fp_account": ""}, {"compte": BEA, "sites": [], "fp_account": "bea"}, {"compte": LEO, "sites": ["fiche.exemple.fr"], "fp_account": ""}]
        self.panneau = [{"domaine": "pan.exemple.fr", "proprietaire": "bea", "ssl": {"etat": "actif", "jours": 80}, "php": "8.3"},
                        {"domaine": "autre.exemple.fr", "proprietaire": "zoe", "ssl": {"etat": "actif", "jours": 80}, "php": "8.2"}]
        self.pan_dispo = True
        self.certificats = None                       # None : module Certificats absent ; sinon {hote: jours} et il fait foi
        self.seuil_certificats = 21
        self.droits_reels = False                     # vrai : « comptes.lister » et « fastpanel.sites » sont refusés à un compte ordinaire, comme en service
        self.ctx.executer_lecture = self.lecture
        self.mod = _ModuleGlobals(self.n.catalogue.get("sites.vue").faire.__globals__)
        self.reponses = {}
        self.mod._sonder_http = lambda d, delai: self.reponses.get(d, (200, 120, ""))
        self.certs = {}
        self.mod._cert_jours = lambda d, delai: self.certs.get(d, 60)
        self.e = self.n.executeur.executer

    def lecture(self, cap, **a):
        """Les lectures des autres modules, simulées. Comme le noyau : pour le compte au nom duquel on agit (aucun pour un moteur), et None quand le droit manque."""
        compte = self.ctx.compte
        if cap == "comptes.moi":
            return next((dict(c) for c in self.comptes if c["compte"] == compte), None)
        if self.droits_reels and compte and compte != CHEF:
            return None
        if cap.startswith("certificats.") and self.certificats is not None:
            return {"jours": self.seuil_certificats} if cap == "certificats.seuil" else {"certificats": [{"hote": h, "jours": j, "etat": "valide"} for h, j in self.certificats.items()]}
        if cap == "comptes.lister":
            return {"comptes": self.comptes}
        if cap == "fastpanel.sites":
            return self.panneau if self.pan_dispo else None
        raise PermissionError("« %s » n'est pas une capacité de lecture" % cap)

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("sites." + cap, acteur, args, compte=compte)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def sonde(self):
        self.n.lancer("sites.sonde")


class Portee(Monde):
    def test_un_compte_ne_voit_que_les_siens(self):
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "faite")
        doms = {s["domaine"] for s in self.ex("vue")["resultat"]["sites"]}
        self.assertEqual(doms, {"bea.exemple.fr", "pan.exemple.fr"})           # le sien déclaré + celui du panneau de son compte lié
        doms_leo = {s["domaine"] for s in self.ex("vue", compte=LEO)["resultat"]["sites"]}
        self.assertEqual(doms_leo, {"fiche.exemple.fr"})                       # inscrit dans sa fiche

    def test_l_administrateur_voit_l_etat_de_tous_avec_les_proprietaires(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        v = self.ex("vue", compte=CHEF)["resultat"]
        self.assertTrue(v["portee"]["admin"])
        s = {x["domaine"]: x for x in v["sites"]}
        self.assertEqual(set(s), {"bea.exemple.fr", "pan.exemple.fr", "autre.exemple.fr", "fiche.exemple.fr"})
        self.assertEqual(s["pan.exemple.fr"]["comptes"], [BEA])
        self.assertIsNone(self.ex("vue")["resultat"]["sites"][0]["comptes"])     # un compte ordinaire ne voit pas les propriétaires

    def test_un_site_hors_portee_est_refuse_partout(self):
        for cap in ("fiche", "historique", "journal", "liens"):
            self.assertEqual(self.ex(cap, domaine="fiche.exemple.fr")["statut"], "echec", cap)
        self.assertEqual(self.ex("lier", domaine="fiche.exemple.fr", genre="note", ref="x")["statut"], "echec")

    def test_un_sous_domaine_d_un_site_de_la_portee_est_accepte(self):
        r = self.ex("historique", domaine="blog.pan.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)

    def test_le_panneau_muet_est_dit_et_ne_donne_pas_un_parc_vide_trompeur(self):
        self.pan_dispo = False
        v = self.ex("vue", compte=CHEF)["resultat"]
        self.assertFalse(v["portee"]["panneau_lu"])
        self.assertNotIn("pan.exemple.fr", {s["domaine"] for s in v["sites"]})

    def test_sans_module_de_comptes_le_reste_fonctionne(self):
        def absent(cap, **a):                                                  # ce que fait le noyau quand le module n'est pas là
            raise PermissionError("« %s » n'est pas une capacité de lecture" % cap)
        self.ctx.executer_lecture = absent
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "faite")
        self.assertEqual({s["domaine"] for s in self.ex("vue")["resultat"]["sites"]}, {"bea.exemple.fr"})
        self.assertEqual(self.ex("vue", compte=CHEF)["statut"], "faite")
        self.sonde()                                                           # et la sonde tourne sans eux
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "x.exemple.fr", "compte": LEO}, compte=CHEF)["statut"], "faite")

    def test_des_comptes_muets_et_jamais_lus_interdisent_de_declarer(self):
        self.ctx.executer_lecture = lambda cap, **a: None                      # les modules sont là mais ne répondent pas : on ne sait pas à qui sont les sites
        r = self.ex("declarer", domaine="bea.exemple.fr")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("lisibles", json.dumps(r, ensure_ascii=False))


class DroitsReels(Monde):
    """Comme en service : un compte ordinaire n'a ni « comptes.gerer » ni « fastpanel.voir ». Les bancs d'avant donnaient ces lectures à tout le monde."""

    def setUp(self):
        super().setUp()
        self.droits_reels = True

    def doms(self, compte):
        return {s["domaine"] for s in self.ex("vue", compte=compte)["resultat"]["sites"]}

    def test_un_compte_ordinaire_voit_tout_de_suite_les_sites_de_sa_fiche(self):
        self.assertEqual(self.doms(LEO), {"fiche.exemple.fr"})                 # par sa propre fiche (comptes.moi), sans attendre la sonde

    def test_apres_un_tour_de_sonde_il_voit_aussi_ceux_du_panneau(self):
        self.assertEqual(self.doms(BEA), set())
        self.sonde()
        self.assertEqual(self.doms(BEA), {"pan.exemple.fr"})
        self.assertTrue(self.ex("vue")["resultat"]["portee"]["panneau_lu"])
        self.assertNotIn("autre.exemple.fr", self.doms(BEA))                   # le miroir ne lui montre pas le panneau des autres

    def test_il_ne_s_approprie_ni_le_site_d_une_fiche_ni_celui_du_panneau(self):
        self.sonde()
        self.assertEqual(self.ex("declarer", domaine="fiche.exemple.fr")["statut"], "echec")     # à Leo, par sa fiche
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="pan.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="autre.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "faite")

    def test_avant_le_premier_tour_rien_ne_se_declare(self):
        self.assertEqual(self.ex("declarer", domaine="fiche.exemple.fr")["statut"], "echec")

    def test_un_panneau_muet_garde_son_dernier_miroir_pour_les_refus(self):
        self.sonde()
        self.pan_dispo = False
        self.ctx.stockage.ecrire("UPDATE miroir SET ts = ts - 7200")           # miroir périmé : plus montré, mais encore opposé à une déclaration
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="pan.exemple.fr")["statut"], "echec")


class Cloisons(Monde):
    def test_un_nom_partage_ne_se_declare_pas(self):
        for d in ("github.io", "gouv.fr", "co.uk"):
            self.assertEqual(self.ex("declarer", domaine=d)["statut"], "echec", d)
        self.assertEqual(self.ex("declarer", domaine="bea.github.io")["statut"], "faite")

    def test_le_parent_du_site_d_un_autre_ne_se_declare_pas(self):
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="blog.bea.exemple.fr")["statut"], "faite")
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("declarer", domaine="exemple.fr")["statut"], "echec")              # parent de pan, autre, fiche

    def test_le_sous_domaine_suivi_pour_un_autre_n_est_pas_dans_la_portee(self):
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "bea.exemple.fr", "compte": BEA}, compte=CHEF)["statut"], "faite")
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "blog.bea.exemple.fr", "compte": LEO}, compte=CHEF)["statut"], "faite")
        self.assertEqual(self.ex("historique", domaine="blog.bea.exemple.fr")["statut"], "echec")   # à Leo, bien que sous le site de Bea
        self.assertEqual(self.ex("lier", domaine="blog.bea.exemple.fr", genre="note", ref="x")["statut"], "echec")
        self.assertEqual(self.ex("historique", domaine="autre.bea.exemple.fr")["statut"], "faite")   # à personne d'autre : c'est le sien

    def test_l_accord_de_l_ancien_proprietaire_ne_vaut_plus_apres_un_transfert(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        self.ex("lier", domaine="bea.exemple.fr", genre="note", ref="n1", note="à moi")
        self.ex("demander", domaine="bea.exemple.fr")
        self.assertEqual(self.ex("accorder", domaine="bea.exemple.fr")["statut"], "faite")
        self.assertIsNotNone(self.ex("accord", compte=CHEF, domaine="bea.exemple.fr")["resultat"]["accord"])
        r = self.e("sites.transferer", "humain", {"domaine": "bea.exemple.fr", "vers": LEO}, compte=CHEF)
        self.assertEqual(r["statut"], "faite", r)
        self.assertIsNone(self.ex("accord", compte=CHEF, domaine="bea.exemple.fr")["resultat"]["accord"])
        self.assertEqual(self.ex("liens", compte=LEO, domaine="bea.exemple.fr")["resultat"]["liens"], [])   # les notes de Bea ne passent pas à Leo
        self.assertEqual(self.ex("demandes", compte=CHEF)["resultat"]["demandes"], [])
        self.n.catalogue.get("sites.transferer").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ex("liens", domaine="bea.exemple.fr")["resultat"]["liens"][0]["note"], "à moi")
        self.assertEqual(len(self.ex("demandes", compte=CHEF)["resultat"]["demandes"]), 1)

    def test_un_accord_reste_sans_effet_si_le_site_est_redeclare_par_un_autre(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        self.ex("accorder", domaine="bea.exemple.fr")
        self.ctx.stockage.ecrire("UPDATE sites SET compte=? WHERE domaine='bea.exemple.fr'", (LEO,))   # le site a changé de mains sans passer par le geste
        self.assertIsNone(self.ex("accord", compte=CHEF, domaine="bea.exemple.fr")["resultat"]["accord"])

    def test_un_geste_d_accord_inconnu_est_refuse(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        self.assertEqual(self.ex("accorder", domaine="bea.exemple.fr", geste="tout_casser")["statut"], "echec")

    def test_les_nombres_illisibles_sont_refuses_en_clair(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        for cap, args in (("accorder", {"domaine": "bea.exemple.fr", "heures": "abc"}), ("historique", {"domaine": "bea.exemple.fr", "heures": "abc"}),
                          ("disponibilite", {"jours": "x"}), ("journal", {"limite": "x"})):
            r = self.ex(cap, **args)
            self.assertEqual(r["statut"], "echec", cap)
            self.assertIn("nombre entier", json.dumps(r, ensure_ascii=False), cap)
            self.assertNotIn("invalid literal", json.dumps(r, ensure_ascii=False), cap)

    def test_le_nom_d_hote_perd_port_identifiants_et_point_final(self):
        for brut in ("https://moi:secret@www.Bea.exemple.fr:8443/x?y=1#z", "bea.exemple.fr.", "BEA.exemple.fr?x", "http://bea.exemple.fr#a"):
            self.assertEqual(self.mod.nom_hote(brut), "bea.exemple.fr", brut)


class Declarations(Monde):
    def test_declarer_puis_retirer_avec_preuve_et_retour(self):
        r = self.ex("declarer", domaine="https://www.Bea.exemple.fr/accueil")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["domaine"], "bea.exemple.fr")
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.assertEqual(self.ex("retirer", domaine="bea.exemple.fr")["statut"], "faite")
        self.assertEqual([s["domaine"] for s in self.ex("vue")["resultat"]["sites"] if s["domaine"] == "bea.exemple.fr"], [])

    def test_le_retour_d_une_declaration_la_defait(self):
        r = self.ex("declarer", domaine="bea.exemple.fr")
        self.n.catalogue.get("sites.declarer").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.mod_lignes("sites"), 0)

    def mod_lignes(self, table):
        return len(self.ctx.stockage.lire("SELECT * FROM %s" % table))

    def test_refus_nom_invalide_panneau_et_autre_compte(self):
        self.assertEqual(self.ex("declarer", domaine="pas un nom")["statut"], "echec")
        self.assertEqual(self.ex("declarer", domaine="pan.exemple.fr")["statut"], "echec")           # géré par le panneau
        self.assertEqual(self.ex("declarer", domaine="fiche.exemple.fr")["statut"], "echec")         # à Leo
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "faite")
        self.assertEqual(self.ex("declarer", domaine="bea.exemple.fr")["statut"], "echec")           # déjà à moi
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")

    def test_sans_compte_pas_de_declaration(self):
        self.assertEqual(self.ex("declarer", compte="", domaine="x.exemple.fr")["statut"], "echec")

    def test_un_site_de_la_fiche_ne_se_retire_pas_ici(self):
        r = self.ex("retirer", compte=LEO, domaine="fiche.exemple.fr")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("fiche", json.dumps(r, ensure_ascii=False))

    def test_attribuer_est_reserve_a_l_administrateur(self):
        self.assertIn(self.e("sites.attribuer", "humain", {"domaine": "x.exemple.fr", "compte": LEO}, compte=BEA)["statut"], ("refuse", "echec"))
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "x.exemple.fr", "compte": LEO}, compte=CHEF)["statut"], "faite")

    def test_un_site_attribue_ne_se_retire_pas_par_son_compte(self):
        self.e("sites.attribuer", "humain", {"domaine": "x.exemple.fr", "compte": LEO}, compte=CHEF)
        self.assertEqual(self.ex("retirer", compte=LEO, domaine="x.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("retirer", compte=CHEF, domaine="x.exemple.fr")["statut"], "faite")

    def test_attribuer_a_un_compte_inconnu_ou_deja_pris_est_refuse(self):
        a = lambda d, c: self.e("sites.attribuer", "humain", {"domaine": d, "compte": c}, compte=CHEF)["statut"]
        self.assertEqual(a("x.exemple.fr", "inconnu@x.fr"), "echec")
        self.assertEqual(a("fiche.exemple.fr", BEA), "echec")                    # à Leo : il se transfère
        self.assertEqual(a("fiche.exemple.fr", LEO), "echec")                    # déjà à lui

    def test_transferer_et_defaire(self):
        self.ex("declarer", domaine="bea.exemple.fr")
        r = self.e("sites.transferer", "humain", {"domaine": "bea.exemple.fr", "vers": LEO}, compte=CHEF)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ctx.stockage.lire("SELECT compte FROM sites")[0]["compte"], LEO)
        self.n.catalogue.get("sites.transferer").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ctx.stockage.lire("SELECT compte, origine FROM sites")[0]["compte"], BEA)

    def test_transferer_ce_qui_n_est_a_personne_est_refuse(self):
        self.assertEqual(self.e("sites.transferer", "humain", {"domaine": "x.exemple.fr", "vers": LEO}, compte=CHEF)["statut"], "echec")


class Sonde(Monde):
    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")

    def etat(self, d):
        o = self.n.registre.lire("site", d, portee=TOUT)
        return o["etat"] if o else None

    def test_premiere_observation_est_une_decouverte_pas_une_panne(self):
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.sonde()
        self.assertEqual(self.etat("bea.exemple.fr"), "hors_ligne")
        self.assertEqual(self.evts("site.panne"), [])
        ev = self.ctx.stockage.lire("SELECT genre FROM evenements_site WHERE domaine='bea.exemple.fr'")
        self.assertEqual([e["genre"] for e in ev], ["decouverte"])

    def test_une_transition_fait_une_panne_puis_un_retour_avec_sa_duree(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (500, 300, "")
        self.sonde()
        self.assertEqual(self.evts("site.panne"), [])                           # une mesure ratée n'est pas une panne
        self.assertEqual(self.etat("bea.exemple.fr"), "en_ligne")
        self.sonde()
        self.assertEqual(len(self.evts("site.panne")), 1)                       # deux de suite, si
        self.assertEqual(self.etat("bea.exemple.fr"), "hors_ligne")
        self.sonde()
        self.assertEqual(len(self.evts("site.panne")), 1)                       # pas de répétition
        self.ctx.stockage.ecrire("UPDATE etat_vu SET depuis = depuis - 600 WHERE domaine='bea.exemple.fr'")
        self.reponses.pop("bea.exemple.fr")
        self.sonde()
        r = self.evts("site.retour")
        self.assertEqual(len(r), 1)
        self.assertGreaterEqual(r[0]["donnees"]["duree_min"], 10)

    def test_les_codes_3xx_sont_en_ligne_les_4xx_non(self):
        self.reponses["bea.exemple.fr"] = (301, 50, "")
        self.sonde()
        self.assertEqual(self.etat("bea.exemple.fr"), "en_ligne")
        self.reponses["bea.exemple.fr"] = (404, 50, "")
        self.sonde()
        self.sonde()
        self.assertEqual(self.etat("bea.exemple.fr"), "hors_ligne")

    def test_un_echec_isole_ne_fait_ni_panne_ni_retour(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.sonde()
        self.reponses.pop("bea.exemple.fr")
        self.sonde()
        self.assertEqual(self.evts("site.panne") + self.evts("site.retour"), [])
        self.assertFalse(self.n.registre.lire("site", "bea.exemple.fr", portee=TOUT)["donnees"]["douteux"])

    def test_la_panne_commence_au_premier_echec(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.sonde()
        self.ctx.stockage.ecrire("UPDATE mesures SET ts = ts - 300 WHERE domaine='bea.exemple.fr' AND up=0")
        self.sonde()
        depuis = self.ctx.stockage.lire("SELECT depuis FROM etat_vu WHERE domaine='bea.exemple.fr'")[0]["depuis"]
        self.assertLess(depuis, time.time() - 290)

    def test_un_site_retire_quitte_le_registre(self):
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.sonde()
        self.assertEqual(self.etat("bea.exemple.fr"), "hors_ligne")
        self.ex("retirer", domaine="bea.exemple.fr")
        self.sonde()
        self.assertIsNone(self.etat("bea.exemple.fr"))                          # plus de constat « hors ligne » pour un site que personne ne suit
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM etat_vu WHERE domaine='bea.exemple.fr'"), [])

    def test_un_panneau_muet_ne_fait_pas_oublier_ses_sites(self):
        self.sonde()
        self.pan_dispo = False
        self.sonde()
        self.assertEqual(self.etat("pan.exemple.fr"), "en_ligne")

    def test_une_panne_en_cours_compte_dans_la_disponibilite(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.sonde()
        self.sonde()
        self.ctx.stockage.ecrire("UPDATE etat_vu SET depuis = depuis - 1200 WHERE domaine='bea.exemple.fr'")
        d = {s["domaine"]: s for s in self.ex("disponibilite")["resultat"]["sites"]}["bea.exemple.fr"]
        self.assertEqual(d["pannes"], 1)
        self.assertTrue(d["en_panne"])
        self.assertGreaterEqual(d["indisponible_min"], 20)

    def test_un_certificat_echu_est_un_constat(self):
        self.certs["bea.exemple.fr"] = -3
        self.sonde()
        self.n.tick()
        self.assertTrue(any("échu" in json.dumps(e["donnees"], ensure_ascii=False) for e in self.evts("constat.ouvert")))
        v = self.ex("vue")["resultat"]["vigilances"]
        self.assertTrue(any("échu" in x["titre"] and x["niveau"] == "panne" for x in v))

    def test_avec_le_module_certificats_sites_ne_lit_ni_n_alerte(self):
        appels = []
        self.mod._cert_jours = lambda d, delai: appels.append(d) or 50
        self.certificats = {"bea.exemple.fr": 5, "pan.exemple.fr": 80}
        self.seuil_certificats = 30
        self.sonde()
        self.assertEqual(appels, [])                                             # une seule sonde des certificats : celle de Certificats
        s = {x["domaine"]: x for x in self.ex("vue", compte=CHEF)["resultat"]["sites"]}
        self.assertEqual((s["bea.exemple.fr"]["ssl_jours"], s["bea.exemple.fr"]["ssl_source"]), (5, "certificats"))
        self.assertIsNone(self.ctx.stockage.lire("SELECT ssl_jours FROM mesures WHERE domaine='fiche.exemple.fr'")[0]["ssl_jours"])   # pas encore lu là-bas : dit, pas deviné
        self.n.tick()
        self.assertFalse(any("ertificat" in json.dumps(e["donnees"], ensure_ascii=False) for e in self.evts("constat.ouvert")))        # un seul constat : celui de Certificats
        self.certificats["pan.exemple.fr"] = 25
        self.ctx.stockage.ecrire("UPDATE mesures SET ts = ts - 400")
        self.sonde()
        v = self.ex("vue", compte=CHEF)["resultat"]["vigilances"]
        self.assertTrue(any("pan.exemple.fr" in x["titre"] and x["niveau"] == "regarder" for x in v))    # 25 j : sous le seuil de Certificats (30), pas sous celui de Sites (21)

    def test_sans_le_module_certificats_sites_garde_sa_lecture(self):
        self.certs["bea.exemple.fr"] = 5
        self.sonde()
        self.n.tick()
        self.assertTrue(any("bea.exemple.fr" in json.dumps(e, ensure_ascii=False) and "ertificat" in json.dumps(e, ensure_ascii=False) for e in self.evts("constat.ouvert")))

    def test_un_site_protege_est_hors_ligne_sauf_reglage(self):
        self.reponses["bea.exemple.fr"] = (401, 50, "")
        self.sonde()
        self.assertEqual(self.etat("bea.exemple.fr"), "hors_ligne")

    def test_un_long_historique_est_regroupe_sans_perdre_la_coupure(self):
        t = time.time()
        for i in range(2000):
            self.ctx.stockage.ecrire("INSERT INTO mesures(ts, domaine, code, ms, up, ssl_jours, erreur) VALUES (?,?,?,?,?,?,?)",
                                     (t - 86000 + i * 40, "bea.exemple.fr", 200 if i != 1000 else None, 100, 1 if i != 1000 else 0, 60, "" if i != 1000 else "délai"))
        h = self.ex("historique", domaine="bea.exemple.fr", heures=24)["resultat"]
        self.assertEqual(h["mesures"], 2000)
        self.assertLessEqual(len(h["points"]), 720)
        self.assertEqual(sum(1 for p in h["points"] if not p["up"]), 1)
        self.assertEqual(h["disponibilite"], 99.95)

    def test_l_historique_d_une_periode_passee(self):
        t = time.time()
        for age, up in ((40 * 86400, 0), (40 * 86400 - 60, 1), (86400, 1)):
            self.ctx.stockage.ecrire("INSERT INTO mesures(ts, domaine, code, ms, up, ssl_jours, erreur) VALUES (?,?,?,?,?,?,?)", (t - age, "bea.exemple.fr", 200, 100, up, 60, ""))
        h = self.ex("historique", domaine="bea.exemple.fr", debut=t - 45 * 86400, fin=t - 35 * 86400)["resultat"]
        self.assertEqual((h["mesures"], h["disponibilite"]), (2, 50.0))          # la période demandée, pas les derniers jours

    def test_les_sites_du_panneau_sont_sondes_aussi(self):
        self.sonde()
        self.assertEqual(self.etat("pan.exemple.fr"), "en_ligne")
        self.assertEqual(self.etat("fiche.exemple.fr"), "en_ligne")

    def test_le_certificat_n_est_relu_qu_une_fois_par_heure(self):
        appels = []
        self.mod._cert_jours = lambda d, delai: appels.append(d) or 50
        self.sonde()
        n1 = len(appels)
        self.sonde()
        self.assertEqual(len(appels), n1)

    def test_les_constats(self):
        self.reponses["bea.exemple.fr"] = (None, 8000, "délai")
        self.reponses["pan.exemple.fr"] = (200, 4500, "")
        self.certs["fiche.exemple.fr"] = 5
        self.sonde()
        self.n.tick()
        titres = " | ".join(json.dumps(e["donnees"], ensure_ascii=False) + e.get("objet_id", "") for e in self.evts("constat.ouvert"))
        for attendu in ("bea.exemple.fr", "pan.exemple.fr", "fiche.exemple.fr"):
            self.assertIn(attendu, titres)

    def test_la_retention_purge_les_vieilles_mesures(self):
        self.sonde()
        self.ctx.stockage.ecrire("UPDATE mesures SET ts = ts - ?", (200 * 86400,))
        self.sonde()
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM mesures WHERE ts < ?", (time.time() - 100 * 86400,))[0]["n"], 0)

    def test_la_disponibilite_exclut_les_sites_qu_on_ne_mesure_plus(self):
        self.sonde()
        self.ctx.stockage.ecrire("UPDATE mesures SET ts = ts - ? WHERE domaine='bea.exemple.fr'", (5 * 86400,))
        d = self.ex("disponibilite")["resultat"]
        self.assertIn("bea.exemple.fr", d["plus_suivis"])
        self.assertNotIn("bea.exemple.fr", [s["domaine"] for s in d["sites"]])

    def test_historique_et_disponibilite_chiffrees(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (500, 100, "")
        self.sonde()
        h = self.ex("historique", domaine="bea.exemple.fr")["resultat"]
        self.assertEqual((h["mesures"], h["disponibilite"]), (2, 50.0))
        d = {s["domaine"]: s for s in self.ex("disponibilite")["resultat"]["sites"]}
        self.assertEqual(d["bea.exemple.fr"]["disponibilite"], 50.0)


class Demandes(Monde):
    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")

    def test_demander_adossement_une_demande_ouverte_par_site(self):
        r = self.ex("demander", domaine="bea.exemple.fr", message="svp")
        self.assertEqual(r["statut"], "faite", r)
        r2 = self.ex("demander", domaine="bea.exemple.fr", message="encore")
        self.assertTrue(r2["resultat"]["reprise"])
        self.assertEqual(len(self.ex("demandes", compte=CHEF)["resultat"]["demandes"]), 1)
        self.assertEqual(self.ex("demandes", compte=LEO)["resultat"]["demandes"], [])      # cloisonné

    def test_on_ne_demande_que_pour_son_site_declare_et_hors_panneau(self):
        self.assertEqual(self.ex("demander", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("demander", domaine="pan.exemple.fr")["statut"], "echec")

    def test_l_administrateur_repond_et_c_est_reversible(self):
        did = self.ex("demander", domaine="bea.exemple.fr")["resultat"]["id"]
        self.assertIn(self.e("sites.repondre_demande", "humain", {"id": did, "decision": "fait"}, compte=BEA)["statut"], ("refuse", "echec"))
        r = self.e("sites.repondre_demande", "humain", {"id": did, "decision": "refusee", "reponse": "non"}, compte=CHEF)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("demandes", compte=CHEF)["resultat"]["demandes"], [])
        self.n.catalogue.get("sites.repondre_demande").defaire(self.ctx, r["resultat"])
        self.assertEqual(len(self.ex("demandes", compte=CHEF)["resultat"]["demandes"]), 1)

    def test_une_decision_inconnue_n_est_pas_un_refus(self):
        did = self.ex("demander", domaine="bea.exemple.fr")["resultat"]["id"]
        for mot in ("ok", "oui", "accepter", ""):
            self.assertEqual(self.e("sites.repondre_demande", "humain", {"id": did, "decision": mot}, compte=CHEF)["statut"], "echec", mot)
        self.assertEqual(len(self.ex("demandes", compte=CHEF)["resultat"]["demandes"]), 1)           # toujours ouverte
        self.assertEqual(self.e("sites.repondre_demande", "humain", {"id": did, "decision": "fait"}, compte=CHEF)["resultat"]["statut"], "fait")

    def test_retirer_ferme_la_demande_et_le_retour_la_rouvre(self):
        self.ex("demander", domaine="bea.exemple.fr")
        r = self.ex("retirer", domaine="bea.exemple.fr")
        self.assertEqual(self.ex("demandes", compte=CHEF)["resultat"]["demandes"], [])
        self.n.catalogue.get("sites.retirer").defaire(self.ctx, r["resultat"])
        self.assertEqual(len(self.ex("demandes", compte=CHEF)["resultat"]["demandes"]), 1)

    def test_la_demande_ouverte_est_un_constat_pour_l_admin(self):
        self.ex("demander", domaine="bea.exemple.fr", message="svp")
        self.n.tick()
        self.assertTrue(any("bea.exemple.fr" in json.dumps(e, ensure_ascii=False) for e in self.evts("constat.ouvert")))

    def test_la_vue_signale_la_demande_et_le_hors_panneau(self):
        v = self.ex("vue")["resultat"]
        self.assertTrue(any(x["geste"] == "demander" for x in v["vigilances"]))
        self.ex("demander", domaine="bea.exemple.fr")
        v = self.ex("vue")["resultat"]
        self.assertFalse(any(x["geste"] == "demander" for x in v["vigilances"]))
        a = self.ex("vue", compte=CHEF)["resultat"]["vigilances"]
        self.assertTrue(any(x["geste"] == "repondre_demande" for x in a))


class AccordsLiensJournal(Monde):
    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")

    def test_l_accord_est_borne_dans_le_temps_et_au_proprietaire(self):
        self.assertEqual(self.ex("accorder", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")
        r = self.ex("accorder", domaine="bea.exemple.fr", geste="restaurer", heures=2)
        self.assertEqual(r["statut"], "faite", r)
        a = self.ex("accord", compte=CHEF, domaine="bea.exemple.fr")["resultat"]["accord"]
        self.assertEqual(a["par"], BEA)
        self.ctx.stockage.ecrire("UPDATE accords SET jusqu_a = ?", (time.time() - 1,))
        self.assertIsNone(self.ex("accord", compte=CHEF, domaine="bea.exemple.fr")["resultat"]["accord"])

    def test_un_accord_plafonne_a_sept_jours_et_se_revoque(self):
        r = self.ex("accorder", domaine="bea.exemple.fr", heures=9999)
        self.assertLessEqual(r["resultat"]["jusqu_a"] - time.time(), 168 * 3600 + 5)
        self.n.catalogue.get("sites.accorder").defaire(self.ctx, r["resultat"])
        self.assertIsNone(self.ex("accord", domaine="bea.exemple.fr")["resultat"]["accord"])

    def test_lier_delier_et_les_retours(self):
        r = self.ex("lier", domaine="bea.exemple.fr", genre="project", ref="12", note="refonte")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("lier", domaine="bea.exemple.fr", genre="inconnu", ref="1")["statut"], "echec")
        self.assertEqual(self.ex("liens", domaine="bea.exemple.fr")["resultat"]["liens"][0]["ref"], "12")
        d = self.ex("delier", domaine="bea.exemple.fr", genre="project", ref="12")
        self.assertEqual(d["statut"], "faite")
        self.n.catalogue.get("sites.delier").defaire(self.ctx, d["resultat"])
        self.assertEqual(self.ex("liens", domaine="bea.exemple.fr")["resultat"]["liens"][0]["note"], "refonte")

    def test_le_journal_fond_les_gestes_et_la_veille_et_se_cloisonne(self):
        self.sonde_une_fois()
        j = self.ex("journal", domaine="bea.exemple.fr")["resultat"]["lignes"]
        self.assertEqual({x["source"] for x in j}, {"geste", "veille"})
        self.assertEqual(self.ex("journal", compte=LEO)["resultat"]["lignes"].__class__, list)
        tous_leo = {x["domaine"] for x in self.ex("journal", compte=LEO)["resultat"]["lignes"]}
        self.assertNotIn("bea.exemple.fr", tous_leo)

    def sonde_une_fois(self):
        self.n.lancer("sites.sonde")

    def test_la_fiche_dit_ce_que_le_compte_peut_faire(self):
        f = self.ex("fiche", domaine="bea.exemple.fr")["resultat"]
        self.assertTrue(f["mien"] and f["hors_panneau"])
        self.assertTrue(f["gestes"]["demander"] and f["gestes"]["retirer"] and not f["gestes"]["attribuer"])
        fa = self.ex("fiche", compte=CHEF, domaine="bea.exemple.fr")["resultat"]
        self.assertTrue(fa["admin_autrui"] and fa["gestes"]["attribuer"] and fa["gestes"]["transferer"])



class Ecran(unittest.TestCase):
    """L'écran du module est bien branché : son script est servi, le menu de gauche lui donne ses sous-entrées, le shell remplace l'onglet V18."""

    def lire(self, *chemin):
        return RACINE.joinpath(*chemin).read_text(encoding="utf-8")

    def test_le_script_est_charge_par_la_page_et_par_l_assembleur(self):
        self.assertIn('<script src="/sites-ecran.js"></script>', self.lire("interface", "CN_index.html"))
        self.assertIn('<script src="/sites-ecran.js"></script>', self.lire("outils", "ui", "CN_assembler.py"))
        self.assertTrue((RACINE / "interface" / "CN_sites-ecran.js").is_file())

    def test_le_shell_remplace_l_onglet_v18_sans_le_supprimer(self):
        self.assertIn('remplacerV18("mysites", "sites")', self.lire("interface", "CN_shell.js"))
        ecran = self.lire("interface", "CN_sites-ecran.js")
        self.assertIn("CASS.sceneSurMesure.sites", ecran)
        for nom in ("window.stVue", "window.stOpen", "window.loadMySites", "window.stFiltre"):       # Panorama, Hébergement et l'Historique les appellent
            self.assertIn(nom, ecran, nom)
        self.assertIn("function stRendre", self.lire("interface", "CN_app.js"), "le code V18 reste en place : rien n'est retiré sans validation")

    def test_le_menu_de_gauche_porte_les_pages_de_sites(self):
        sys.path.insert(0, str(RACINE / "modules" / "affichage" / "points"))
        import EC_disposition as d
        r = d.disposition([], ["sites"], {}, {})
        sites = next(e for g in r["groupes"] for e in g["entrees"] if e["id"] == "sites")
        vues = [f["vue"] for f in sites["enfants"]]
        self.assertEqual(vues, ["vue", "sites", "alertes", "dispo", "demandes", "journal"])
        self.assertTrue(all(f["onglet"] == "mysites" for f in sites["enfants"]))
        ecran = self.lire("interface", "CN_sites-ecran.js")
        for v in vues:                                                                                # chaque sous-entrée a sa page dans l'écran
            self.assertRegex(ecran, r"(?m)^\s+(async )?%s\(\)" % v, v)
        self.assertIn('entreeId === "sites"', self.lire("interface", "CN_disposition.js"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _ModuleGlobals, Monde, Portee, Declarations, Sonde, Demandes, AccordsLiensJournal
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
