# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #9d0cde
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie : l'événement dans le bureau (projet et tâches créés dans les VRAIS modules Projets et Tâches, au nom du compte).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9d0cde ▼▼▼
"""Bancs de la billetterie : l'événement dans le bureau (projet et tâches créés dans les VRAIS modules Projets et Tâches, au nom du compte)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                                   # noqa: E402
from CN_test_billetterie_base import Monde, BEA            # noqa: E402


class Fond(Monde):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("billetterie", "droits", "comptes", "projets", "taches", "agenda", "contacts"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "billetterie", "projets", "taches", "agenda", "contacts"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["billetterie"]
        self.n.droits.regler_admin(BEA, True)
        self.e = self.evenement(date_iso="2027-06-12")

    def autoriser_les_agents(self):
        for cle in ("projets.creer", "taches.creer", "agenda.evenement_enregistrer", "contacts.creer", "contacts.supprimer"):
            self.n.regler_palier(cle, "auto")

    def ex_mod(self, cle, **a):
        return self.n.executeur.executer(cle, "humain", a, compte=BEA)


class Creation(Fond):
    def test_le_projet_et_ses_taches_naissent_dans_les_vrais_modules(self):
        self.autoriser_les_agents()
        r = self.ok("evenement_projet", evenement_id=self.e["id"])
        self.assertEqual(len(r["taches"]), 10)
        p = self.ex_mod("projets.voir", id=r["projet_id"])
        self.assertEqual(p["statut"], "faite", p)
        self.assertIn("Événement · Soirée d'hiver", str(p["resultat"]))
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["projet_ref"], "projet:%s" % r["projet_id"])

    def test_les_echeances_suivent_la_date_de_la_soiree(self):
        self.autoriser_les_agents()
        appels, orig = [], self.ctx.agir
        self.ctx.agir = lambda cap, args=None, acteur="itare", **k: (appels.append((cap, dict(args or {}))), orig(cap, args, acteur=acteur, **k))[1]
        self.ok("evenement_projet", evenement_id=self.e["id"])
        taches = [a for c, a in appels if c == "taches.creer"]
        self.assertEqual(sorted(t["echeance"] for t in taches)[0], "2027-04-13")                  # 60 jours avant le 12 juin 2027
        self.assertIn("2027-06-05", [t["echeance"] for t in taches])                                # la décision, 7 jours avant
        self.assertEqual(max(t["echeance"] for t in taches), "2027-06-19")                          # le solde, 7 jours après
        ref = self.ok("evenement", id=self.e["id"])["evenement"]["ref"]
        self.assertEqual(sorted(t["origine"] for t in taches), sorted("%s:%d" % (ref, i) for i in range(1, 11)))

    def test_une_etape_deja_en_retard_est_a_faire_aujourd_hui(self):
        self.autoriser_les_agents()
        proche = self.evenement(nom="Dans trois jours", date_iso=__import__("datetime").date.today().replace(year=__import__("datetime").date.today().year + 0).isoformat())
        appels, orig = [], self.ctx.agir
        self.ctx.agir = lambda cap, args=None, acteur="itare", **k: (appels.append((cap, dict(args or {}))), orig(cap, args, acteur=acteur, **k))[1]
        self.ok("evenement_projet", evenement_id=proche["id"])
        auj = __import__("datetime").date.today().isoformat()
        taches = [a for c, a in appels if c == "taches.creer"]
        self.assertTrue(all(t["echeance"] >= auj for t in taches))

    def test_un_evenement_n_a_qu_un_projet(self):
        self.autoriser_les_agents()
        self.ok("evenement_projet", evenement_id=self.e["id"])
        self.assertIn("déjà son projet", self.echec("evenement_projet", evenement_id=self.e["id"]))

    def test_sans_date_pas_de_projet(self):
        e = self.evenement(nom="Sans date", date_iso="")
        self.assertIn("date", self.echec("evenement_projet", evenement_id=e["id"]))

    def test_sans_les_taches_le_projet_seul_est_cree(self):
        self.autoriser_les_agents()
        r = self.ok("evenement_projet", evenement_id=self.e["id"], avec_taches=False)
        self.assertEqual(r["taches"], [])

    def test_defaire_detache_le_projet_et_le_laisse_dans_le_bureau(self):
        self.autoriser_les_agents()
        r = self.ok("evenement_projet", evenement_id=self.e["id"])
        self.defaire("evenement_projet", r)
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["projet_ref"], "")
        self.assertEqual(self.ex_mod("projets.voir", id=r["projet_id"])["statut"], "faite")
        self.ok("evenement_projet", evenement_id=self.e["id"], avec_taches=False)     # on peut en refaire un (sans les tâches : Tâches ne crée jamais deux fois la même)

    def test_le_projet_appartient_au_compte_qui_le_demande_et_a_personne_d_autre(self):
        self.autoriser_les_agents()
        self.n.droits.regler_groupe("billet", "Billetterie")
        self.n.droits.regler_membre("gestion@x.fr", "billet", True)
        self.n.droits.regler("groupe", "billet", "billetterie.gerer", "accorde")
        r = self.n.executeur.executer("billetterie.evenement_projet", "humain", {"evenement_id": self.e["id"]}, compte="gestion@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        pid = r["resultat"]["projet_id"]
        self.assertEqual(self.n.executeur.executer("projets.voir", "humain", {"id": pid}, compte="gestion@x.fr")["statut"], "faite")
        autre = self.ex_mod("projets.voir", id=pid)                               # le titulaire de l'instance n'est pas le propriétaire : le cloisonnement par compte tient
        self.assertNotEqual(autre["statut"], "faite", autre)


class Agenda(Fond):
    def test_la_soiree_entre_dans_l_agenda_rattachee_au_projet_avec_un_rappel(self):
        self.autoriser_les_agents()
        r = self.ok("evenement_projet", evenement_id=self.e["id"])
        self.assertIsNotNone(r["agenda_id"])
        a = self.ex_mod("agenda.evenement", id=r["agenda_id"])
        self.assertEqual(a["statut"], "faite", a)
        t = str(a["resultat"])
        self.assertIn("2027-06-12 20:00", t)
        self.assertIn("2027-06-12 23:00", t)
        self.assertIn("Soirée d'hiver", t)

    def test_l_agenda_en_attente_de_validation_ne_bloque_pas_le_projet(self):
        for cle in ("projets.creer", "taches.creer"):
            self.n.regler_palier(cle, "auto")
        r = self.ok("evenement_projet", evenement_id=self.e["id"])                 # l'agenda reste au palier « raconter »
        self.assertTrue(r["projet_id"] and len(r["taches"]) == 10)
        self.assertIsNone(r["agenda_id"])


class Repertoire(Fond):
    def setUp(self):
        super().setUp()
        self.autoriser_les_agents()
        fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.nova = self.ok("artiste_save", scene="Nova", formule_id=fa["id"], mail="nova@exemple.org", tel="0600000001")
        self.muet = self.ok("artiste_save", scene="Sans coordonnées", formule_id=fa["id"])
        self.lea = self.ok("revendeur_save", nom="Léa Martin", mail="lea@exemple.org")

    def test_chaque_fiche_avec_coordonnees_devient_un_contact_et_les_autres_sont_dites(self):
        r = self.ok("repertoire_synchroniser")
        self.assertEqual(sorted((x["genre"], x["fiche"][:3]) for x in r["crees"]), [("artiste", "ART"), ("revendeur", "REV")])
        self.assertEqual([x["raison"][:2] for x in r["refuses"]], ["ni"])
        v = self.ex_mod("contacts.voir", id=r["crees"][0]["contact_id"])
        self.assertEqual(v["statut"], "faite", v)

    def test_une_fiche_deja_liee_n_est_jamais_doublee(self):
        self.ok("repertoire_synchroniser")
        r = self.ok("repertoire_synchroniser")
        self.assertEqual((r["crees"], r["deja"]), ([], 2))

    def test_une_adresse_deja_prise_par_un_autre_contact_est_dite_sans_rien_casser(self):
        self.ex_mod("contacts.creer", display_name="Quelqu'un", emails=["nova@exemple.org"])
        r = self.ok("repertoire_synchroniser")
        self.assertEqual([x["genre"] for x in r["crees"]], ["revendeur"])
        self.assertTrue([x for x in r["refuses"] if "adresse" in x["raison"] or "appartient" in x["raison"]])

    def test_defaire_supprime_les_contacts_crees_et_leurs_liens(self):
        r = self.ok("repertoire_synchroniser")
        self.defaire("repertoire_synchroniser", r)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM contacts_lies")[0]["n"], 0)
        r2 = self.ok("repertoire_synchroniser")                                    # les contacts supprimés sont en corbeille et gardent leurs adresses : la billetterie le dit au lieu de les doubler
        self.assertEqual(r2["crees"], [])
        self.assertEqual(len([x for x in r2["refuses"] if "appartient" in x["raison"]]), 2)

    def test_au_palier_raconter_rien_n_est_cree_et_on_le_dit(self):
        self.n.regler_palier("contacts.creer", "raconter")
        r = self.ok("repertoire_synchroniser")
        self.assertTrue(r["racontee"] and r["crees"] == [])
        self.assertIn("palier", r["message"])


class PalierRaconter(Fond):
    def test_tant_que_le_palier_est_raconter_rien_n_est_cree_et_on_le_dit(self):
        r = self.ok("evenement_projet", evenement_id=self.e["id"])
        self.assertTrue(r["racontee"] and r["projet_id"] is None)
        self.assertIn("palier", r["message"])
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["projet_ref"], "")

    def test_le_projet_cree_et_les_taches_racontees_laissent_le_projet_lie(self):
        self.n.regler_palier("projets.creer", "auto")
        r = self.ok("evenement_projet", evenement_id=self.e["id"])
        self.assertEqual((bool(r["projet_id"]), r["taches"]), (True, []))
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["projet_ref"], "projet:%s" % r["projet_id"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Bureau
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
