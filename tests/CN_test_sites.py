# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Sites
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #78ff87
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Sites : un vrai noyau, des comptes simulés, un panneau et une sonde simulés.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=78ff87 ▼▼▼
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
        self.n.reglages.poser("sites.preuve_exigee", False, "")     # la preuve de propriété a ses bancs à elle (classe Preuve) ; ailleurs un site déclaré est tout de suite au compte
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
        voisin = getattr(self, "voisins", {}).get(cap)
        if voisin is not None and cap.split(".")[0] in ("contacts", "notes", "ged"):      # des lectures que tout compte a pour lui-même
            return voisin(a) if callable(voisin) else voisin
        if self.droits_reels and compte and compte != CHEF:
            return None
        if voisin is not None:                                                             # Sensorium, panneau, DNS : des droits qu'un compte ordinaire n'a pas
            return voisin(a) if callable(voisin) else voisin
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



class Incidents(Monde):
    """Une panne est un objet : elle s'ouvre confirmée, se dépanne, se clôt avec sa cause."""

    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")
        self.sonde()

    def tomber(self):
        self.reponses["bea.exemple.fr"] = (502, 60, "")
        self.sonde()
        self.sonde()

    def revenir(self):
        self.reponses.pop("bea.exemple.fr")
        self.sonde()

    def liste(self, etat="ouverts", compte=BEA):
        return self.ex("incidents", compte=compte, etat=etat)["resultat"]["incidents"]

    def test_une_panne_confirmee_ouvre_un_incident_avec_son_diagnostic(self):
        self.reponses["bea.exemple.fr"] = (502, 60, "")
        self.sonde()
        self.assertEqual(self.liste(), [])                                       # une mesure ratée n'ouvre rien
        self.sonde()
        i = self.liste()
        self.assertEqual([(x["domaine"], x["etat"]) for x in i], [("bea.exemple.fr", "ouvert")])
        self.assertIn("HTTP 502", i[0]["diagnostic"])
        self.sonde()
        self.assertEqual(len(self.liste()), 1)                                   # une panne qui dure n'en ouvre pas un second
        v = self.ex("vue")["resultat"]
        ligne = next(s for s in v["sites"] if s["domaine"] == "bea.exemple.fr")
        self.assertEqual(ligne["incident"]["id"], i[0]["id"])
        self.assertEqual(v["portee"]["incidents_ouverts"], 1)
        vig = next(x for x in v["vigilances"] if x["niveau"] == "panne")
        self.assertEqual((vig["geste"], vig["incident"]), ("depanner", i[0]["id"]))
        self.assertEqual(self.evts("site.panne")[0]["donnees"]["incident"], i[0]["id"])

    def test_revenu_seul_l_incident_se_clot_seul_et_sa_cause_se_note_apres(self):
        self.tomber()
        self.revenir()
        self.assertEqual(self.liste(), [])
        r = self.liste("resolus")
        self.assertEqual([(x["etat"], x["clos_par"], x["cause"]) for x in r], [("resolu", "sonde", "")])
        self.assertEqual(self.ex("incident_clore", id=r[0]["id"])["statut"], "echec")           # déjà clos : il faut une cause à noter
        self.assertEqual(self.ex("incident_clore", id=r[0]["id"], cause="pic de charge")["statut"], "faite")
        self.assertEqual(self.liste("resolus")[0]["cause"], "pic de charge")

    def test_pris_en_charge_il_attend_sa_cause_puis_se_clot_et_se_defait(self):
        self.tomber()
        iid = self.liste()[0]["id"]
        p = self.ex("incident_prendre", id=iid)
        self.assertEqual(p["statut"], "faite", p)
        self.assertEqual(self.liste()[0]["etat"], "depannage")
        self.assertEqual(self.ex("incident_prendre", id=iid)["statut"], "echec")               # il s'en occupe déjà
        self.assertEqual(self.ex("incident_clore", id=iid, cause="x")["statut"], "echec")       # le site ne répond pas encore
        self.assertEqual(self.ex("incident_noter", id=iid, texte="PHP saturé, je relance")["statut"], "faite")
        self.revenir()
        self.assertEqual(self.liste()[0]["etat"], "retabli")                                    # quelqu'un s'en occupait : il attend sa cause
        v = self.ex("vue")["resultat"]
        self.assertTrue(any(x["geste"] == "depanner" and x["niveau"] == "regarder" for x in v["vigilances"]))
        self.assertEqual(v["portee"]["incidents_ouverts"], 0)
        r = self.ex("incident_clore", id=iid, cause="PHP saturé")
        self.assertEqual(r["statut"], "faite", r)
        d = self.ex("incident", id=iid)["resultat"]
        self.assertEqual((d["etat"], d["cause"], d["clos_par"]), ("resolu", "PHP saturé", BEA))
        self.assertEqual([f["genre"] for f in d["faits"]], ["ouvert", "pris", "note", "retour", "clos"])
        self.assertTrue(d["gestes"]["cause"])
        self.n.catalogue.get("sites.incident_clore").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ex("incident", id=iid)["resultat"]["etat"], "retabli")
        self.n.catalogue.get("sites.incident_prendre").defaire(self.ctx, p["resultat"])         # il n'est plus « en dépannage » : rien à rendre
        self.assertEqual(self.ex("incident", id=iid)["resultat"]["etat"], "retabli")

    def test_une_panne_connue_se_tait_sans_se_fermer(self):
        self.tomber()
        iid = self.liste()[0]["id"]
        self.assertEqual(len(self.ctx_detecter("panne")), 1)
        r = self.ex("incident_connu", id=iid, heures=4)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ctx_detecter("panne"), [])                                        # le constat se tait…
        self.assertEqual(self.liste()[0]["etat"], "ouvert")                                     # … l'incident reste ouvert
        self.assertIsNotNone(self.liste()[0]["connu_jusqu"])
        self.assertEqual(self.ex("incident_connu", id=iid, heures=0)["statut"], "faite")
        self.assertEqual(len(self.ctx_detecter("panne")), 1)
        self.assertEqual(self.ex("incident_connu", id=iid, heures="beaucoup")["statut"], "echec")

    def ctx_detecter(self, nom):
        f = next(x[2] for x in self.n.detecteurs if x[0] == "sites" and x[1].id == nom)
        return f(self.ctx)

    def test_le_proprietaire_est_prevenu_de_la_panne_de_son_site(self):
        self.tomber()
        k = self.ctx_detecter("panne_proprietaire")
        self.assertEqual([(x["objet"], x["compte"]) for x in k], [(("site", "bea.exemple.fr"), BEA)])       # un constat adressé à son compte
        self.assertIn("HTTP 502", k[0]["detail"])
        self.n.tick()
        ouverts = [e for e in self.evts("constat.ouvert") if e["donnees"]["detecteur"] == "panne_proprietaire"]
        self.assertEqual([e["compte"] for e in ouverts], [BEA])
        self.ex("incident_connu", id=self.liste()[0]["id"], heures=4)
        self.assertEqual(self.ctx_detecter("panne_proprietaire"), [])                                        # une panne connue se tait pour lui aussi
        # le site d'un administrateur : il a déjà le constat des administrateurs, pas de doublon
        self.e("sites.attribuer", "humain", {"domaine": "chef.exemple.fr", "compte": CHEF}, compte=CHEF)
        self.reponses["chef.exemple.fr"] = (200, 50, "")
        self.sonde()
        self.reponses["chef.exemple.fr"] = (500, 50, "")
        self.sonde()
        self.sonde()
        self.assertEqual([x["objet"][1] for x in self.ctx_detecter("panne")], ["chef.exemple.fr"])          # celle de Béa est dite connue
        self.assertEqual(self.ctx_detecter("panne_proprietaire"), [])

    def test_l_incident_d_un_autre_n_existe_pas(self):
        self.tomber()
        iid = self.liste()[0]["id"]
        self.assertEqual(self.liste(compte=LEO), [])
        for cap, args in (("incident", {}), ("incident_prendre", {}), ("incident_noter", {"texte": "x"}), ("incident_connu", {}), ("incident_clore", {"cause": "x"})):
            self.assertEqual(self.ex(cap, compte=LEO, id=iid, **args)["statut"], "echec", cap)
        self.assertEqual(len(self.liste(compte=CHEF)), 1)                                       # l'administrateur voit l'état de tous

    def test_relever_mesure_tout_de_suite_et_peut_fermer_la_panne(self):
        self.tomber()
        iid = self.liste()[0]["id"]
        self.ctx.stockage.ecrire("UPDATE mesures SET ts = ts - 120")
        self.reponses.pop("bea.exemple.fr")
        r = self.ex("relever", domaine="bea.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["up"])
        self.assertFalse(r["resultat"]["recente"])
        self.assertEqual(self.liste(), [])                                                      # la relève a vu le retour : l'incident s'est clos seul
        self.assertIn("releve", [f["genre"] for f in self.ex("incident", id=iid)["resultat"]["faits"]])
        self.assertTrue(self.ex("relever", domaine="bea.exemple.fr")["resultat"]["recente"])    # pas deux mesures en trente secondes
        self.assertEqual(self.ex("relever", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("relever", domaine="inconnu.bea.exemple.fr")["statut"], "echec")   # un sous-domaine qu'on ne suit pas ne se mesure pas

    def test_un_site_deja_en_panne_recoit_son_incident_et_un_site_retire_le_perd(self):
        self.tomber()
        self.ctx.stockage.ecrire("DELETE FROM incident_faits")
        self.ctx.stockage.ecrire("DELETE FROM incidents")                                       # comme une base d'avant les incidents
        self.sonde()
        i = self.liste()
        self.assertEqual(len(i), 1)
        depuis = self.ctx.stockage.lire("SELECT depuis FROM etat_vu WHERE domaine='bea.exemple.fr'")[0]["depuis"]
        self.assertEqual(i[0]["debut"], depuis)                                                 # daté du début de la panne, pas de ce tour
        self.assertEqual(self.ex("retirer", domaine="bea.exemple.fr")["statut"], "faite")
        self.sonde()
        r = self.ex("incidents", compte=CHEF, etat="resolus")["resultat"]["incidents"]
        self.assertEqual([(x["etat"], x["cause"]) for x in r], [("resolu", "Le site n'est plus suivi.")])


class Calendrier(Monde):
    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")
        self.db = self.ctx.stockage

    def jours(self, n=3):
        """Les `n` derniers jours, finissant maintenant : n débuts de journée puis la fin."""
        fin = time.time() + 60
        return [fin - (n - k) * 86400 for k in range(n)] + [fin]

    def test_chaque_jour_dit_son_etat_et_ce_qui_s_y_est_passe(self):
        b = self.jours(3)
        # avant-hier : 100 mesures bonnes ; hier : 100 dont 30 ratées (coupure longue) ; aujourd'hui : 100 dont 1 ratée (courte)
        for k, rates in ((0, 0), (1, 30), (2, 1)):
            for i in range(100):
                self.db.ecrire("INSERT INTO mesures(ts, domaine, code, ms, up, ssl_jours, erreur) VALUES (?,?,?,?,?,?,?)",
                               (b[k] + 100 + i * 60, "bea.exemple.fr", 200 if i >= rates else 502, 120 + i, 1 if i >= rates else 0, 60, ""))
        iid = self.db.ecrire("INSERT INTO incidents(domaine, debut, fin, etat, diagnostic, code, erreur, cause) VALUES (?,?,?,?,?,?,?,?)",
                             ("bea.exemple.fr", b[1] + 100, b[1] + 1900, "resolu", "x", 502, "", "PHP saturé"))
        self.db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail, duree_min) VALUES (?,?,?,?,?)", (b[1] + 100, "bea.exemple.fr", "panne", "Injoignable", 0))
        self.ex("lier", domaine="bea.exemple.fr", genre="note", ref="à surveiller")
        r = self.ex("calendrier", domaine="bea.exemple.fr", jours=b)
        self.assertEqual(r["statut"], "faite", r)
        c = r["resultat"]
        self.assertEqual([j["etat"] for j in c["jours"]], ["ok", "longue", "courte"])
        self.assertEqual([j["rates"] for j in c["jours"]], [0, 30, 1])
        hier = c["jours"][1]["evenements"]
        self.assertEqual([(e["genre"], e["incident"]) for e in hier], [("incident", iid), ("retour", iid)])       # la panne n'est pas dite deux fois
        self.assertIn("PHP saturé", hier[1]["texte"])
        self.assertIn("geste", [e["genre"] for e in c["jours"][2]["evenements"]])                # le lien posé aujourd'hui (et la déclaration)
        m = c["mois"]
        self.assertEqual((m["jours_mesures"], m["jours_coupure"], m["incidents"]), (3, 2, 1))
        self.assertEqual(m["disponibilite"], round(100.0 * 269 / 300, 2))
        self.assertFalse(m["tenu"])
        self.assertIsNone(m["avant"])                                                            # pas de mesure sur la période d'avant : pas de chiffre emprunté

    def test_un_mois_ecrit_se_lit_et_un_mois_sans_mesure_le_dit(self):
        r = self.ex("calendrier", domaine="bea.exemple.fr", mois="2026-02")
        self.assertEqual(r["statut"], "faite", r)
        c = r["resultat"]
        self.assertEqual(len(c["jours"]), 28)
        self.assertEqual({j["etat"] for j in c["jours"]}, {"sans"})
        self.assertIsNone(c["mois"]["disponibilite"])
        self.assertIsNone(c["mois"]["tenu"])
        self.assertEqual(len(self.ex("calendrier", domaine="bea.exemple.fr", mois="2024-02")["resultat"]["jours"]), 29)
        self.assertEqual(self.ex("calendrier", domaine="bea.exemple.fr", mois="fevrier")["statut"], "echec")
        self.assertEqual(self.ex("calendrier", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")

    def test_l_objectif_se_pose_par_site_et_se_defait(self):
        v = self.ex("vue")["resultat"]
        self.assertEqual(v["portee"]["objectif"], 99.9)
        self.assertFalse(v["sites"][0]["objectif_propre"])
        r = self.ex("objectif", domaine="bea.exemple.fr", pct="99,5")
        self.assertEqual(r["statut"], "faite", r)
        ligne = next(s for s in self.ex("vue")["resultat"]["sites"] if s["domaine"] == "bea.exemple.fr")
        self.assertEqual((ligne["objectif"], ligne["objectif_propre"]), (99.5, True))
        self.assertEqual(self.ex("calendrier", domaine="bea.exemple.fr")["resultat"]["mois"]["objectif"], 99.5)
        for mauvais in (50, 101, "haut"):
            self.assertEqual(self.ex("objectif", domaine="bea.exemple.fr", pct=mauvais)["statut"], "echec", mauvais)
        self.assertEqual(self.ex("objectif", compte=LEO, domaine="bea.exemple.fr", pct=99)["statut"], "echec")
        self.n.catalogue.get("sites.objectif").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ex("vue")["resultat"]["sites"][0]["objectif"], 99.9)
        self.n.reglages.poser("sites.objectif_pct", "99", "")
        self.assertEqual(self.ex("vue")["resultat"]["portee"]["objectif"], 99.0)


class Preuve(Monde):
    """Hors du panneau, rien ne dit à qui est un site : c'est la preuve qui le dit."""

    def setUp(self):
        super().setUp()
        self.n.reglages.poser("sites.preuve_exigee", True, "")
        self.visible = {}                                    # {domaine: jeton visible dans le DNS ou le fichier}
        self.mod._preuve_trouvee = lambda d, jeton, delai, interne=False: "dns" if self.visible.get(d) == jeton else ""

    def test_un_site_declare_n_est_a_personne_tant_qu_il_n_est_pas_prouve(self):
        r = self.ex("declarer", domaine="bea.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["preuve"], "attente")
        jeton = r["resultat"]["jeton"]
        self.assertEqual(r["resultat"]["dns"], {"nom": "_cassandra.bea.exemple.fr", "valeur": "cassandra-site=" + jeton})
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM sites WHERE domaine='bea.exemple.fr'"), [])
        v = self.ex("vue")["resultat"]
        ligne = next(s for s in v["sites"] if s["domaine"] == "bea.exemple.fr")
        self.assertEqual(ligne["preuve"]["jeton"], jeton)
        self.assertTrue(any(x["geste"] == "prouver" for x in v["vigilances"]))
        self.sonde()
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM mesures WHERE domaine='bea.exemple.fr'"), [])       # pas mesuré tant qu'il n'est à personne
        f = self.ex("fiche", domaine="bea.exemple.fr")["resultat"]
        self.assertTrue(f["gestes"]["prouver"])
        self.assertEqual(f["preuve"]["fichier"]["adresse"], "https://bea.exemple.fr/.well-known/cassandra-site.txt")
        self.assertEqual(self.ex("historique", domaine="bea.exemple.fr")["statut"], "echec")                       # ni portée, ni sous-domaines
        self.assertTrue(self.ex("concerne")["resultat"]["concerne"])
        # l'administrateur voit la déclaration en attente, sans le jeton
        va = self.ex("vue", compte=CHEF)["resultat"]
        self.assertIsNone(next(s for s in va["sites"] if s["domaine"] == "bea.exemple.fr")["preuve"]["jeton"])
        self.assertEqual([p["compte"] for p in self.ex("demandes", compte=CHEF)["resultat"]["preuves"]], [BEA])

    def test_la_preuve_trouvee_donne_le_site_et_fait_tomber_les_autres_declarations(self):
        jb = self.ex("declarer", domaine="bea.exemple.fr")["resultat"]["jeton"]
        rl = self.ex("declarer", compte=LEO, domaine="bea.exemple.fr")
        self.assertEqual(rl["statut"], "faite", rl)                                             # un autre peut encore le réclamer
        self.assertNotEqual(rl["resultat"]["jeton"], jb)
        self.assertEqual(self.ex("prouver", domaine="bea.exemple.fr")["statut"], "echec")       # rien n'est encore visible
        self.assertEqual(self.ctx.stockage.lire("SELECT essais FROM preuves WHERE compte=?", (BEA,))[0]["essais"], 1)
        self.visible["bea.exemple.fr"] = jb
        self.assertEqual(self.ex("prouver", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")   # le jeton visible n'est pas le sien
        r = self.ex("prouver", domaine="bea.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["par"], "dns")
        self.assertEqual(self.ctx.stockage.lire("SELECT compte FROM sites WHERE domaine='bea.exemple.fr'")[0]["compte"], BEA)
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM preuves"), [])
        self.assertEqual(self.ex("declarer", compte=LEO, domaine="bea.exemple.fr")["statut"], "echec")   # prouvé : il est à quelqu'un
        self.assertIsNone(next(s for s in self.ex("vue")["resultat"]["sites"] if s["domaine"] == "bea.exemple.fr")["preuve"])
        self.n.catalogue.get("sites.prouver").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM sites WHERE domaine='bea.exemple.fr'"), [])
        self.assertEqual({p["compte"] for p in self.ctx.stockage.lire("SELECT compte FROM preuves")}, {BEA, LEO})

    def test_une_declaration_se_retire_s_atteste_ou_tombe_seule(self):
        r = self.ex("declarer", domaine="bea.exemple.fr")
        ret = self.ex("retirer", domaine="bea.exemple.fr")
        self.assertEqual(ret["statut"], "faite", ret)
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM preuves"), [])
        self.n.catalogue.get("sites.retirer").defaire(self.ctx, ret["resultat"])
        self.assertEqual(len(self.ctx.stockage.lire("SELECT 1 FROM preuves")), 1)
        # l'administrateur atteste : il attribue, la preuve n'a plus lieu d'être
        a = self.e("sites.attribuer", "humain", {"domaine": "bea.exemple.fr", "compte": BEA}, compte=CHEF)
        self.assertEqual(a["statut"], "faite", a)
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM preuves"), [])
        self.assertEqual(self.ctx.stockage.lire("SELECT origine FROM sites WHERE domaine='bea.exemple.fr'")[0]["origine"], "attribue")
        # une déclaration de plus de sept jours tombe au tour de sonde
        self.ex("declarer", domaine="vieux.exemple.fr")
        self.ctx.stockage.ecrire("UPDATE preuves SET cree = cree - 8 * 86400")
        self.assertNotIn("vieux.exemple.fr", {s["domaine"] for s in self.ex("vue")["resultat"]["sites"]})
        self.sonde()
        self.assertEqual(self.ctx.stockage.lire("SELECT 1 FROM preuves"), [])
        self.assertEqual(r["resultat"]["compte"], BEA)

    def test_l_administrateur_declare_sans_preuve(self):
        r = self.ex("declarer", compte=CHEF, domaine="chef.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertNotIn("preuve", r["resultat"])
        self.assertEqual(self.ctx.stockage.lire("SELECT compte FROM sites WHERE domaine='chef.exemple.fr'")[0]["compte"], CHEF)

    def test_la_preuve_se_lit_dans_le_dns_ou_dans_un_fichier(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("sites_seul", RACINE / "modules" / "sites" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m._txt_dns = lambda nom, delai=4: ["v=spf1 -all", "cassandra-site=abc123"] if nom == "_cassandra.x.exemple.fr" else []
        m._fichier_preuve = lambda d, delai, interne=False: "def456\n" if d == "y.exemple.fr" else ""
        self.assertEqual(m._preuve_trouvee("x.exemple.fr", "abc123", 5), "dns")
        self.assertEqual(m._preuve_trouvee("www.x.exemple.fr", "abc123", 5), "dns")
        self.assertEqual(m._preuve_trouvee("x.exemple.fr", "autre", 5), "")
        self.assertEqual(m._preuve_trouvee("y.exemple.fr", "def456", 5), "fichier")
        self.assertEqual(m._preuve_trouvee("y.exemple.fr", "def45", 5), "")                     # un jeton entier, pas un morceau
        self.assertIn("HTTP 502", m.diagnostic(502, ""))
        self.assertIn("DNS", m.diagnostic(None, "[Errno -2] Name or service not known"))
        self.assertIn("délai", m.diagnostic(None, "timed out"))


class Societes(Monde):
    """Chaque société ne voit que ses sites, ses administrateurs aussi ; seul le superadministrateur les voit toutes."""

    INES, MAX = "ines@x.fr", "max@x.fr"

    def setUp(self):
        super().setUp()
        idt = self.n.identite
        self.nord = idt.societe_creer("Nord")["societe"]
        self.sud = idt.societe_creer("Sud")["societe"]
        self.soc = {CHEF: "1", BEA: self.nord, self.INES: self.nord, LEO: self.sud, self.MAX: self.sud}
        idt.societe_de = lambda c: self.soc.get(c, "1")
        idt.est_superadmin = lambda c: c == CHEF
        idt.module_ouvert = lambda *a, **k: True
        self.ctx._intro["societe_de"] = idt.societe_de
        self.n.droits.regler_admin(self.INES, True)
        self.n.droits.regler_admin(self.MAX, True)
        self.comptes += [{"compte": self.INES, "sites": [], "fp_account": ""}, {"compte": self.MAX, "sites": [], "fp_account": ""}]
        self.ex("declarer", domaine="bea.exemple.fr")                       # Nord, par son compte
        self.ex("declarer", compte=LEO, domaine="leo.exemple.fr")           # Sud, par son compte ; fiche.exemple.fr aussi (fiche de Léo)

    def doms(self, compte):
        return {s["domaine"] for s in self.ex("vue", compte=compte)["resultat"]["sites"]}

    def test_l_administrateur_d_une_societe_ne_voit_que_les_sites_de_sa_societe(self):
        self.assertEqual(self.doms(self.INES), {"bea.exemple.fr", "pan.exemple.fr"})                       # ceux des comptes de Nord
        self.assertEqual(self.doms(self.MAX), {"leo.exemple.fr", "fiche.exemple.fr"})
        self.assertEqual(self.doms(CHEF), {"bea.exemple.fr", "pan.exemple.fr", "leo.exemple.fr", "fiche.exemple.fr", "autre.exemple.fr"})
        p = self.ex("vue", compte=self.INES)["resultat"]["portee"]
        self.assertEqual((p["admin"], p["super"], p["multi"], p["societe"]), (True, False, True, self.nord))
        self.assertTrue(self.ex("vue", compte=CHEF)["resultat"]["portee"]["super"])
        self.assertEqual(self.doms(BEA), {"bea.exemple.fr", "pan.exemple.fr"})                             # un compte : les siens, comme avant

    def test_hors_de_sa_societe_rien_ne_se_lit_ni_ne_se_fait(self):
        for cap in ("fiche", "historique", "journal", "calendrier"):
            self.assertEqual(self.ex(cap, compte=self.INES, domaine="leo.exemple.fr")["statut"], "echec", cap)
            self.assertEqual(self.ex(cap, compte=self.INES, domaine="bea.exemple.fr")["statut"], "faite", cap)
        self.assertEqual(self.e("sites.retirer", "humain", {"domaine": "leo.exemple.fr"}, compte=self.INES)["statut"], "echec")
        self.assertEqual(self.e("sites.transferer", "humain", {"domaine": "leo.exemple.fr", "vers": BEA}, compte=self.INES)["statut"], "echec")
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "autre.exemple.fr", "compte": BEA}, compte=self.INES)["statut"], "echec")   # un site du panneau sans société
        self.assertEqual(self.e("sites.attribuer", "humain", {"domaine": "neuf.exemple.fr", "compte": BEA}, compte=self.INES)["statut"], "faite")    # un nom que personne ne suit
        self.ex("demander", compte=LEO, domaine="leo.exemple.fr", message="au panneau")
        self.assertEqual(self.ex("demandes", compte=self.INES)["resultat"]["demandes"], [])
        did = self.ex("demandes", compte=self.MAX)["resultat"]["demandes"][0]["id"]
        self.assertEqual(self.e("sites.repondre_demande", "humain", {"id": did, "decision": "fait"}, compte=self.INES)["statut"], "echec")
        lignes = self.ex("journal", compte=self.INES)["resultat"]["lignes"]
        self.assertTrue(lignes)
        self.assertNotIn("leo.exemple.fr", {x["domaine"] for x in lignes})

    def test_le_superadministrateur_attribue_un_site_a_une_societe(self):
        v = self.ex("vue", compte=CHEF)["resultat"]
        s = {x["domaine"]: x for x in v["sites"]}
        self.assertEqual((s["bea.exemple.fr"]["societe"], s["bea.exemple.fr"]["societe_source"]), (self.nord, "compte"))
        self.assertEqual((s["autre.exemple.fr"]["societe"], s["autre.exemple.fr"]["societe_source"]), ("", ""))
        self.assertEqual({x["id"] for x in v["portee"]["societes"]}, {"1", self.nord, self.sud})
        self.assertTrue(any(x["geste"] == "attribuer_societe" and x["site"] == "autre.exemple.fr" for x in v["vigilances"]))
        self.assertEqual(self.e("sites.attribuer_societe", "humain", {"domaine": "autre.exemple.fr", "societe": self.sud}, compte=self.INES)["statut"], "echec")   # réservé
        self.assertEqual(self.e("sites.attribuer_societe", "humain", {"domaine": "autre.exemple.fr", "societe": "nulle-part"}, compte=CHEF)["statut"], "echec")
        r = self.e("sites.attribuer_societe", "humain", {"domaine": "autre.exemple.fr", "societe": self.sud}, compte=CHEF)
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("autre.exemple.fr", self.doms(self.MAX))
        self.assertNotIn("autre.exemple.fr", self.doms(self.INES))
        # un site de Nord attribué à Sud : les administrateurs de Sud le voient, son compte aussi, plus ceux de Nord
        self.assertEqual(self.e("sites.attribuer_societe", "humain", {"domaine": "bea.exemple.fr", "societe": self.sud}, compte=CHEF)["statut"], "faite")
        self.assertIn("bea.exemple.fr", self.doms(self.MAX))
        self.assertNotIn("bea.exemple.fr", self.doms(self.INES))
        self.assertIn("bea.exemple.fr", self.doms(BEA))
        self.n.catalogue.get("sites.attribuer_societe").defaire(self.ctx, r["resultat"])
        self.assertNotIn("autre.exemple.fr", self.doms(self.MAX))
        self.assertFalse(any(x["geste"] == "attribuer_societe" for x in self.ex("vue", compte=self.INES)["resultat"]["vigilances"]))

    def test_une_instance_a_une_seule_societe_ne_cloisonne_rien(self):
        self.ctx._intro["societes"] = lambda: ["1"]
        self.assertEqual(self.doms(self.INES), self.doms(CHEF))
        p = self.ex("vue", compte=self.INES)["resultat"]["portee"]
        self.assertEqual((p["multi"], p["societes"]), (False, []))
        self.assertFalse(any(x["geste"] == "attribuer_societe" for x in self.ex("vue", compte=CHEF)["resultat"]["vigilances"]))

    def test_qui_est_concerne(self):
        self.comptes.append({"compte": "nul@x.fr", "sites": [], "fp_account": ""})
        self.assertEqual(self.ex("concerne", compte="nul@x.fr")["resultat"], {"concerne": False, "sites": 0, "a_prouver": 0, "admin": False})
        self.assertTrue(self.ex("concerne", compte=BEA)["resultat"]["concerne"])
        self.assertTrue(self.ex("concerne", compte=self.INES)["resultat"]["admin"])
        g = {x["id"]: x for x in self.ex("gestes")["resultat"]["gestes"]}
        self.assertEqual(g["attribuer_societe"]["droit"], "sites.administrer")
        self.assertNotIn("vue", g)
        self.assertIn("cassandra", g["incident_prendre"]["qui"])


class Voisinage(Monde):
    """Ce que les autres modules savent d'un site (Sensorium, panneau, DNS, Contacts) : Sites le lit, ne le refait pas, et le montre au propriétaire."""

    def setUp(self):
        super().setUp()
        self.ex("declarer", domaine="bea.exemple.fr")
        self.fenetres, self.acquits = [], {}
        self.voisins = {
            "sensorium.etat": lambda a: {"ok": True, "muet": False, "fenetres": [],
                                         "rows": [{"wkey": "web." + d, "value": "ne répond pas", "severity": "info", "acquit": q} for d, q in self.acquits.items()]},
            "sensorium.fenetres": lambda a: {"vivantes": self.fenetres, "finies": []},
            "sensorium.entite": lambda a: [{"domain": "pan.exemple.fr", "cms_type": "WordPress", "version": "6.4", "theme": "astra", "plugins_count": 12}] if a.get("nom") == "cms_sites" else [],
            "sensorium.secu": {"sites": [{"site": "pan.exemple.fr", "n": 4200, "b": 900}], "robots": {"pan.exemple.fr": [{"robot": "Googlebot", "n": 300}]}},
            "fastpanel.bases": [{"nom": "pan_prod", "moteur": "mysql", "taille_mo": 120, "site": "pan.exemple.fr", "derniere_copie": "2026-11-09"}],
            "fastpanel.mail": [{"adresse": "a@pan.exemple.fr", "domaine": "pan.exemple.fr", "quota_mo": 1000, "utilise_mo": 200},
                               {"adresse": "b@pan.exemple.fr", "domaine": "pan.exemple.fr", "quota_mo": 500, "utilise_mo": 50}],
            "fastpanel.audit": {"sauvegardes": {"seuil_j": 2, "sans": ["autre.exemple.fr"], "perimees": [], "total": 2}},
            "fastpanel.php": {"fin_de_support": [{"domaine": "autre.exemple.fr", "php": "7.4", "fin": "2022-11-28"}], "bientot": [], "version_non_lue": []},
            "fastpanel.scans_cibles": {"sites": [{"domaine": "pan.exemple.fr", "actif": True, "planning": "hebdomadaire", "dernier": "2026-11-08", "rapports": 3}]},
            "dns.etat": {"zones": [{"domaine": "exemple.fr", "expiration": time.strftime("%Y-%m-%d", time.gmtime(time.time() + 12 * 86400))}]},
        }
        self.panneau[0].update({"statut": "actif", "fichiers_mo": 840, "bases_mo": 120, "erreurs": 3})

    def utc(self, dans_s):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + dans_s))

    def detecter(self, nom):
        f = next(x[2] for x in self.n.detecteurs if x[0] == "sites" and x[1].id == nom)
        return f(self.ctx)

    def tomber(self):
        self.sonde()
        self.reponses["bea.exemple.fr"] = (502, 60, "")
        self.sonde()
        self.sonde()

    def test_le_proprietaire_lit_ce_que_le_panneau_et_le_sensorium_savent_de_son_site(self):
        self.sonde()
        self.droits_reels = True                              # Béa n'a ni « fastpanel.voir » ni « sensorium.voir_infra » : elle lit le miroir de la sonde
        f = self.ex("fiche", domaine="pan.exemple.fr")
        self.assertEqual(f["statut"], "faite", f)
        v = f["resultat"]["voisins"]
        self.assertEqual(v["cms"], {"type": "WordPress", "version": "6.4", "theme": "astra", "extensions": 12})
        self.assertEqual((v["trafic"]["requetes"], v["trafic"]["robots"], v["trafic"]["premiers_robots"]), (4200, 900, ["Googlebot"]))
        h = v["hebergement"]
        self.assertEqual((h["disque_mo"], h["bases_mo"], h["erreurs"]), (840, 120, 3))
        self.assertEqual([b["nom"] for b in h["bases"]], ["pan_prod"])
        self.assertEqual(h["courrier"], {"boites": 2, "utilise_mo": 250, "quota_mo": 1500})
        self.assertTrue(h["analyse"]["actif"])
        self.assertEqual(v["sauvegarde"]["etat"], "ok")
        self.assertEqual((v["nom"]["zone"], v["nom"]["jours"] in (11, 12)), ("exemple.fr", True))
        vue = self.ex("vue")["resultat"]
        ligne = next(s for s in vue["sites"] if s["domaine"] == "pan.exemple.fr")
        self.assertEqual(ligne["cms"]["type"], "WordPress")
        noms = [x for x in vue["vigilances"] if "expire dans" in x["titre"]]
        self.assertEqual(len(noms), 1)                        # un nom, une alerte : pas une par site qu'il porte
        self.assertEqual(noms[0]["niveau"], "regarder")
        self.assertIsNone(self.ex("fiche", domaine="bea.exemple.fr")["resultat"]["voisins"]["hebergement"])     # hors panneau : pas d'hébergement à montrer

    def test_un_site_sans_sauvegarde_ou_sur_un_php_abandonne_se_signale(self):
        self.sonde()
        vig = {x["titre"]: x for x in self.ex("vue", compte=CHEF)["resultat"]["vigilances"] if x["site"] == "autre.exemple.fr"}
        self.assertEqual(vig["autre.exemple.fr : aucune sauvegarde connue"]["niveau"], "regarder")
        self.assertEqual(vig["autre.exemple.fr : PHP 7.4 n'est plus maintenu"]["niveau"], "regarder")
        self.assertFalse(any("sauvegarde" in x["titre"] for x in self.ex("vue", compte=CHEF)["resultat"]["vigilances"] if x["site"] == "bea.exemple.fr"))

    def test_une_fenetre_de_maintenance_du_sensorium_fait_taire_le_site_ici_aussi(self):
        self.tomber()
        self.assertEqual(len(self.detecter("panne")), 1)
        self.assertEqual(len(self.detecter("panne_proprietaire")), 1)
        self.fenetres.append({"id": 7, "portee": "machine:nas", "debut": self.utc(-600), "fin": self.utc(3600), "motif": "disque", "annulee": ""})
        self.sonde()
        self.assertEqual(len(self.detecter("panne")), 1)                                     # une fenêtre sur une machine ne couvre pas ce site
        self.fenetres.append({"id": 8, "portee": "site:bea.exemple.fr", "debut": self.utc(-600), "fin": self.utc(3600), "motif": "mise à jour", "annulee": "", "par": CHEF})
        self.droits_reels = True
        self.assertEqual(self.ex("voisins")["resultat"]["fenetres_en_cours"], 1)                # Béa n'a pas le droit de lire le Sensorium : rien ne change, l'ancienne fenêtre reste
        self.assertEqual(len(self.detecter("panne")), 1)
        self.assertEqual(self.ex("voisins", compte=CHEF)["resultat"]["fenetres_en_cours"], 2)   # l'administrateur relit tout de suite, sans attendre la sonde
        self.droits_reels = False
        self.assertEqual(self.detecter("panne"), [])
        self.assertEqual(self.detecter("panne_proprietaire"), [])
        vue = self.ex("vue")["resultat"]
        ligne = next(s for s in vue["sites"] if s["domaine"] == "bea.exemple.fr")
        self.assertEqual((ligne["maintenance"]["id"], ligne["maintenance"]["motif"], ligne["maintenance"]["ce_site"]), (8, "mise à jour", True))
        self.assertEqual([x["niveau"] for x in vue["vigilances"] if x["site"] == "bea.exemple.fr" and "ne répond pas" in x["titre"]], ["info"])
        self.assertEqual(len(self.ex("incidents", etat="ouverts")["resultat"]["incidents"]), 1)   # l'incident, lui, reste ouvert : on se tait, on n'oublie pas
        self.assertEqual(self.ex("incident", id=1)["resultat"]["maintenance"]["id"], 8)
        cal = self.ex("calendrier", domaine="bea.exemple.fr", jours=[time.time() - 86400, time.time() + 60])["resultat"]
        self.assertIn("maintenance", [e["genre"] for e in cal["jours"][0]["evenements"]])
        self.fenetres[:] = [dict(self.fenetres[1], annulee=self.utc(0))]                      # annulée : le site reparle
        self.sonde()
        self.assertEqual(len(self.detecter("panne")), 1)
        self.fenetres[:] = [{"id": 9, "portee": "famille:web", "debut": self.utc(-60), "fin": self.utc(600), "motif": "", "annulee": ""}]   # tous les sites
        self.sonde()
        self.assertEqual(self.detecter("panne"), [])

    def test_une_alerte_acceptee_dans_le_sensorium_se_tait_ici_aussi(self):
        self.tomber()
        self.acquits["bea.exemple.fr"] = {"raison": "site en refonte", "jusqua": self.utc(86400), "par": CHEF}
        self.sonde()
        self.assertEqual(self.detecter("panne"), [])
        ligne = next(s for s in self.ex("vue")["resultat"]["sites"] if s["domaine"] == "bea.exemple.fr")
        self.assertEqual(ligne["acceptee"]["raison"], "site en refonte")
        self.acquits.clear()
        self.sonde()
        self.assertEqual(len(self.detecter("panne")), 1)

    def test_les_rattachements_se_lisent_chez_ceux_qui_les_portent(self):
        self.voisins["contacts.pour_cible"] = lambda a: {"contacts": [{"id": 3, "display_name": "Zoé Martin", "company": "Hébergeur", "role": "technique"}]} if a == {"kind": "domain", "ref": "bea.exemple.fr"} else {"contacts": []}
        self.voisins["notes.de"] = lambda a: {"notes": [{"id": "N-0011", "titre": "Accès et particularités"}]} if a.get("ref") == "bea.exemple.fr" else {"notes": []}
        self.droits_reels = True
        r = self.ex("fiche", domaine="bea.exemple.fr")["resultat"]["rattaches"]
        self.assertEqual(r["contacts"], [{"id": 3, "nom": "Zoé Martin", "societe": "Hébergeur", "role": "technique"}])
        self.assertEqual(r["notes"], [{"id": "N-0011", "titre": "Accès et particularités"}])
        self.assertEqual(r["documents"], [])                                                      # la GED ne répond pas : rien, et c'est dit
        self.assertNotEqual(r["sources"]["documents"], "ok")

    def test_sans_voisins_rien_ne_manque_et_rien_n_est_invente(self):
        self.voisins = {}
        self.sonde()
        f = self.ex("fiche", domaine="pan.exemple.fr")["resultat"]["voisins"]
        self.assertEqual((f["cms"], f["trafic"], f["nom"], f["sauvegarde"], f["maintenance"], f["sensorium_lu"]), (None, None, None, None, None, False))
        self.assertEqual(f["hebergement"]["bases"], [])
        self.assertEqual(set(f["sources"].values()), {"absent"})


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
        self.assertEqual(vues, ["vue", "sites", "incidents", "alertes", "dispo", "calendrier", "demandes", "journal", "reglages"])
        self.assertTrue(all(f["onglet"] == "mysites" for f in sites["enfants"]))
        ecran = self.lire("interface", "CN_sites-ecran.js")
        for v in vues:                                                                                # chaque sous-entrée a sa page dans l'écran
            self.assertRegex(ecran, r"(?m)^\s+(async )?%s\(\)" % v, v)
        self.assertIn('entreeId === "sites"', self.lire("interface", "CN_disposition.js"))


class MenuConcerne(unittest.TestCase):
    """Le menu de gauche ne montre « Sites » qu'à un compte concerné : il a un site, ou il administre."""

    MODULES = ("droits", "comptes", "menus", "affichage", "jour", "salon", "sites")

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        for m in cls.MODULES:
            shutil.copytree(RACINE / "modules" / m, base / "modules" / m, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", base / "modules", {}, gerer_modules=True)
        cls.n.brancher()
        for m in cls.MODULES:
            assert cls.n.activer(m)["ok"], m
        cls.n.droits.regler_admin(CHEF, True)
        r = cls.n.lancer("menus.reconstruire_regulierement")
        assert r.get("statut") == "fait", r

    @classmethod
    def tearDownClass(cls):
        cls.n.arreter()
        cls.tmp.cleanup()

    def entrees(self, compte):
        r = self.n.executeur.executer("affichage.lire_disposition", "humain", {}, compte=compte)
        self.assertEqual(r["statut"], "faite", r)
        return {e["id"] for g in r["resultat"]["groupes"] for e in g["entrees"]}

    def test_l_entree_sites_ne_parait_que_pour_un_compte_concerne(self):
        self.assertIn("sites", self.entrees(CHEF))                      # l'administrateur administre : il la voit toujours
        self.assertNotIn("sites", self.entrees(BEA))                    # aucun site : on ne lui montre pas un écran vide
        self.n.executeur.contextes["sites"].stockage.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", ("bea.exemple.fr", BEA, "attribue", time.time(), CHEF))
        self.assertIn("sites", self.entrees(BEA))                       # dès qu'un site lui est attribué, l'entrée paraît
        self.assertNotIn("sites", self.entrees(LEO))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _ModuleGlobals, Monde, Portee, Declarations, Sonde, Demandes, AccordsLiensJournal
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
