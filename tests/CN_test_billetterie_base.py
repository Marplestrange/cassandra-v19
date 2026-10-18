# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 1
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #dbfe6e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 1 : les bases, les formules, les événements, la mise en vente, le calcul de la commission, les identifiants jamais réutilisés.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=dbfe6e ▼▼▼
"""Bancs de la billetterie, lot 1 : les bases, les formules, les événements, la mise en vente, le calcul de la commission, les identifiants jamais réutilisés."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("billetterie", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "billetterie"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["billetterie"]
        self.n.droits.regler_admin(BEA, True)               # le titulaire de l'instance

    # ── aides ────────────────────────────────────────────────────────────────
    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("billetterie." + capacite, acteur, args, compte=compte)

    def ok(self, capacite, **args):
        r = self.ex(capacite, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, capacite, **args):
        r = self.ex(capacite, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def defaire(self, capacite, resultat):
        self.n.catalogue.get("billetterie." + capacite).defaire(self.ctx, resultat)

    def liste(self, pluriel):
        return self.ok(pluriel)[pluriel]

    def salle(self, **k):
        d = dict(nom="Salle des fêtes", assis=80, debout=140, location=10000, acompte=3000)
        d.update(k)
        return self.ok("salle_save", **d)

    def formule(self, **k):
        d = dict(nom="Formule C", role="independant", com=300, palier_n=12, palier_com=500)
        d.update(k)
        return self.ok("formule_save", **d)

    def evenement(self, **k):
        s = self.salle() if "salle_id" not in k else None
        d = dict(nom="Soirée d'hiver", date_iso="2026-12-12", salle_id=(s["id"] if s else None), conf="debout", quota=120, prix=1500)
        d.update(k)
        return self.ok("evenement_save", **d)


class Salles(Monde):
    def test_une_salle_se_cree_avec_sa_reference_et_se_defait(self):
        r = self.salle()
        self.assertEqual(r["ref"], "SAL-000001")
        self.assertEqual(len(self.liste("salles")), 1)
        self.defaire("salle_save", r)
        self.assertEqual(self.liste("salles"), [])

    def test_une_reference_n_est_jamais_reutilisee(self):
        a = self.salle()
        self.defaire("salle_save", a)                       # créée puis annulée
        b = self.salle(nom="Autre")
        self.assertEqual(b["ref"], "SAL-000002")
        c = self.salle(nom="Encore")
        self.ok("salle_delete", id=c["id"])                  # supprimée
        d = self.salle(nom="Une dernière")
        self.assertEqual(d["ref"], "SAL-000004")

    def test_une_salle_a_une_capacite(self):
        self.assertIn("capacité", self.echec("salle_save", nom="Vide", assis=0, debout=0))

    def test_ne_modifier_qu_un_champ_laisse_les_autres(self):
        r = self.salle(adresse="1 rue de la Mairie")
        self.ok("salle_save", id=r["id"], nom="Salle renommée")
        s = self.ok("salle", id=r["id"])["salle"]
        self.assertEqual((s["nom"], s["adresse"], s["debout"]), ("Salle renommée", "1 rue de la Mairie", 140))

    def test_supprimer_se_defait_avec_la_meme_reference(self):
        r = self.salle()
        res = self.ok("salle_delete", id=r["id"])
        self.assertEqual(self.liste("salles"), [])
        self.defaire("salle_delete", res)
        self.assertEqual([s["ref"] for s in self.liste("salles")], ["SAL-000001"])

    def test_une_salle_utilisee_ne_se_supprime_pas(self):
        e = self.evenement()
        s = self.liste("salles")[0]
        self.assertIn("événement", self.echec("salle_delete", id=s["id"]))
        self.assertTrue(e["id"])


class Formules(Monde):
    def test_les_trois_groupes_ne_gardent_que_leurs_champs(self):
        a = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500, fixe=999, palier_n=5, palier_com=900)
        f = self.ok("formule", id=a["id"])["formule"]
        self.assertEqual((f["forfait"], f["com"], f["fixe"], f["palier"]), (8000, 500, 0, 0))
        c = self.ok("formule_save", nom="Cachet", role="cachet", forfait=10000, com=700)
        f = self.ok("formule", id=c["id"])["formule"]
        self.assertEqual((f["forfait"], f["com"]), (10000, 0))
        i = self.formule(forfait=5555, fixe=2000)
        f = self.ok("formule", id=i["id"])["formule"]
        self.assertEqual((f["forfait"], f["com"], f["fixe"], f["palier"], f["palier_n"]), (0, 300, 2000, 1, 12))

    def test_le_groupe_d_une_formule_est_definitif(self):
        a = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.assertIn("définitif", self.echec("formule_save", id=a["id"], role="independant"))

    def test_un_palier_de_zero_place_n_est_pas_un_palier(self):
        f = self.formule(palier_n=0, palier_com=900)
        self.assertEqual(self.ok("formule", id=f["id"])["formule"]["palier"], 0)

    def test_l_argent_se_donne_en_centimes_entiers(self):
        self.assertIn("centimes", self.echec("formule_save", nom="X", role="independant", com=3.5))

    def test_une_formule_utilisee_ne_se_supprime_pas(self):
        f = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.ok("artiste_save", scene="Les Marées", formule_id=f["id"])
        self.assertIn("artiste", self.echec("formule_delete", id=f["id"]))

    def test_le_calcul_de_la_commission_passe_par_le_point(self):
        f = self.formule(fixe=1000)                           # 3 € jusqu'à 12 places, 5 € au-delà, 10 € de fixe
        self.assertEqual(self.ok("commission", formule_id=f["id"], places=0)["total"], 0)
        self.assertEqual(self.ok("commission", formule_id=f["id"], places=1)["total"], 1300)
        self.assertEqual(self.ok("commission", formule_id=f["id"], places=12)["total"], 4600)
        r = self.ok("commission", formule_id=f["id"], places=14)
        self.assertEqual((r["commission"], r["fixe"], r["total"]), (3600 + 1000, 1000, 4600 + 1000))
        a = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.assertEqual(self.ok("commission", formule_id=a["id"], places=18)["total"], 8000 + 9000)


class Artistes(Monde):
    def test_un_artiste_qui_vend_devient_revendeur(self):
        f = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        a = self.ok("artiste_save", scene="Les Marées", formule_id=f["id"], vend=1, mail="contact@lesmarees.fr")
        self.assertEqual(a["ref"], "ART-000001")
        fiche = self.ok("artiste", id=a["id"])["artiste"]
        rev = [r for r in self.liste("revendeurs") if r["id"] == fiche["revendeur_id"]][0]
        self.assertEqual((rev["type"], rev["nom"], rev["artiste_id"], rev["actif"]), ("artiste", "Les Marées", a["id"], 1))
        self.assertRegex(rev["code"], r"^LES-[0-9A-Z]{4}$")

    def test_qui_cesse_de_vendre_voit_son_compte_suspendu_pas_efface(self):
        f = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        a = self.ok("artiste_save", scene="Les Marées", formule_id=f["id"], vend=1)
        rid = self.ok("artiste", id=a["id"])["artiste"]["revendeur_id"]
        self.ok("artiste_save", id=a["id"], vend=0)
        rev = self.ok("revendeur", id=rid)["revendeur"]
        self.assertEqual(rev["actif"], 0)
        self.ok("artiste_save", id=a["id"], vend=1)
        self.assertEqual(self.ok("revendeur", id=rid)["revendeur"]["actif"], 1)
        self.assertEqual(len(self.liste("revendeurs")), 1)       # la même casquette, pas un doublon

    def test_creer_l_artiste_vendeur_puis_annuler_retire_aussi_le_revendeur_et_garde_le_code_retire(self):
        f = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        res = self.ex("artiste_save", scene="Les Marées", formule_id=f["id"], vend=1)["resultat"]
        code = [r for r in self.liste("revendeurs")][0]["code"]
        self.defaire("artiste_save", res)
        self.assertEqual((self.liste("artistes"), self.liste("revendeurs")), ([], []))
        r2 = self.ok("revendeur_save", nom="Les Marées")           # même nom : le code ne peut pas revenir
        self.assertNotEqual(r2["ref"], "REV-000001")
        self.assertNotEqual(self.ok("revendeur", id=r2["id"])["revendeur"]["code"], code)

    def test_un_artiste_ne_prend_pas_une_formule_de_revendeur(self):
        f = self.formule()
        self.assertIn("revendeur", self.echec("artiste_save", scene="X", formule_id=f["id"]))

    def test_un_artiste_qui_vend_a_une_formule_d_artiste(self):
        c = self.ok("formule_save", nom="Cachet", role="cachet", forfait=10000)
        self.assertIn("formule d'artiste", self.echec("artiste_save", scene="X", formule_id=c["id"], vend=1))
        self.assertIn("formule d'artiste", self.echec("artiste_save", scene="X", vend=1))

    def test_courriel_et_statut_sont_verifies(self):
        self.assertIn("courriel", self.echec("artiste_save", scene="X", mail="pas-une-adresse"))
        self.assertIn("statut", self.echec("artiste_save", scene="X", statut="Banque"))


class Revendeurs(Monde):
    def test_un_revendeur_independant_recoit_un_code_unique(self):
        a = self.ok("revendeur_save", nom="Léa Martin", mail="lea@exemple.org")
        b = self.ok("revendeur_save", nom="Léa Martin")
        ca, cb = [self.ok("revendeur", id=x["id"])["revendeur"]["code"] for x in (a, b)]
        self.assertNotEqual(ca, cb)
        self.assertTrue(ca.startswith("LEA-"))

    def test_un_revendeur_artiste_naît_de_la_fiche_de_l_artiste(self):
        self.assertIn("artiste", self.echec("revendeur_save", nom="X", type="artiste"))

    def test_le_code_ne_se_modifie_pas_et_une_suppression_le_retire_pour_toujours(self):
        a = self.ok("revendeur_save", nom="Léa Martin")
        code = self.ok("revendeur", id=a["id"])["revendeur"]["code"]
        self.ok("revendeur_save", id=a["id"], code="PIRATE-1", nom="Léa M.")
        self.assertEqual(self.ok("revendeur", id=a["id"])["revendeur"]["code"], code)
        self.ok("revendeur_delete", id=a["id"])
        nouveau = self.ok("revendeur_save", nom="Léa Martin")
        self.assertNotEqual(self.ok("revendeur", id=nouveau["id"])["revendeur"]["code"], code)


class Evenements(Monde):
    def test_une_date_doit_etre_une_date(self):
        s = self.salle()
        self.assertIn("date", self.echec("evenement_save", nom="X", date_iso="12/12/2026", salle_id=s["id"], quota=10))

    def test_la_configuration_doit_exister_dans_la_salle(self):
        s = self.salle(nom="Théâtre", assis=200, debout=0)
        self.assertIn("configuration", self.echec("evenement_save", nom="X", salle_id=s["id"], conf="debout", quota=10))

    def test_publier_exige_date_salle_et_places(self):
        e = self.ok("evenement_save", nom="Brouillon")
        self.assertIn("il faut", self.echec("evenement_publier", id=e["id"]))

    def test_publier_cree_deux_billets_et_se_defait(self):
        e = self.evenement()
        res = self.ok("evenement_publier", id=e["id"])
        fiche = self.ok("evenement_fiche", id=e["id"])
        self.assertEqual(fiche["evenement"]["statut"], "en vente")
        self.assertEqual([(t["nom"], t["prix"]) for t in fiche["types"]], [("Plein tarif", 1500), ("Tarif réduit", 1000)])
        self.defaire("evenement_publier", res)
        fiche = self.ok("evenement_fiche", id=e["id"])
        self.assertEqual((fiche["evenement"]["statut"], fiche["types"]), ("brouillon", []))

    def test_la_jauge_de_la_salle_bloque_la_mise_en_vente(self):
        e = self.evenement(quota=130)                          # 140 debout
        self.ok("invitation_save", evenement_id=e["id"], categorie="Presse", quota=20)
        self.assertIn("jauge", self.echec("evenement_publier", id=e["id"]))
        self.ok("evenement_save", id=e["id"], quota=100)
        self.ok("evenement_publier", id=e["id"])

    def test_on_ne_publie_pas_deux_fois(self):
        e = self.evenement()
        self.ok("evenement_publier", id=e["id"])
        self.assertIn("brouillon", self.echec("evenement_publier", id=e["id"]))

    def test_retirer_de_la_vente_puis_remettre(self):
        e = self.evenement()
        self.ok("evenement_publier", id=e["id"])
        res = self.ok("evenement_depublier", id=e["id"])
        self.assertEqual(self.ok("evenement_fiche", id=e["id"])["evenement"]["statut"], "brouillon")
        self.defaire("evenement_depublier", res)
        self.assertEqual(self.ok("evenement_fiche", id=e["id"])["evenement"]["statut"], "en vente")

    def test_un_evenement_qui_a_des_enfants_ne_se_supprime_pas(self):
        e = self.evenement()
        self.ok("type_billet_save", evenement_id=e["id"], nom="VIP", prix=3000)
        self.assertIn("type(s) de billet", self.echec("evenement_delete", id=e["id"]))

    def test_les_frais_sans_compte_se_regient_par_evenement(self):
        e = self.evenement(achat="obligatoire", frais_sans_compte=300)
        f = self.ok("evenement", id=e["id"])["evenement"]
        self.assertEqual((f["achat"], f["frais_sans_compte"]), ("obligatoire", 300))
        self.assertIn("achat", self.echec("evenement_save", id=e["id"], achat="jamais"))


class Programme(Monde):
    def setUp(self):
        super().setUp()
        self.e = self.evenement()
        self.fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.fc = self.formule()
        self.a1 = self.ok("artiste_save", scene="Les Marées", formule_id=self.fa["id"])
        self.a2 = self.ok("artiste_save", scene="Nova", formule_id=self.fa["id"])

    def test_les_passages_prennent_leur_rang_dans_l_ordre(self):
        p1 = self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"], duree=45)
        p2 = self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a2["id"], duree=30)
        prog = self.ok("evenement_fiche", id=self.e["id"])["programme"]
        self.assertEqual([(p["scene"], p["ordre"], p["duree"]) for p in prog], [("Les Marées", 1, 45), ("Nova", 2, 30)])
        self.assertEqual(prog[0]["formule_id"], self.fa["id"])          # la formule de l'artiste par défaut
        self.assertTrue(p1["id"] and p2["id"])

    def test_deux_passages_ne_partagent_pas_le_meme_rang(self):
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"])
        self.assertIn("rang", self.echec("passage_save", evenement_id=self.e["id"], artiste_id=self.a2["id"], ordre=1))

    def test_un_passage_refuse_une_formule_de_revendeur(self):
        self.assertIn("formule d'artiste", self.echec("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"], formule_id=self.fc["id"]))

    def test_reordonner_se_defait(self):
        p1 = self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"])
        p2 = self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a2["id"])
        res = self.ok("programme_ordonner", evenement_id=self.e["id"], passages=[p2["id"], p1["id"]])
        self.assertEqual([p["scene"] for p in self.ok("evenement_fiche", id=self.e["id"])["programme"]], ["Nova", "Les Marées"])
        self.defaire("programme_ordonner", res)
        self.assertEqual([p["scene"] for p in self.ok("evenement_fiche", id=self.e["id"])["programme"]], ["Les Marées", "Nova"])

    def test_reordonner_exige_tous_les_passages(self):
        p1 = self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"])
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a2["id"])
        self.assertIn("tous les passages", self.echec("programme_ordonner", evenement_id=self.e["id"], passages=[p1["id"]]))

    def test_un_artiste_au_programme_ne_se_supprime_pas(self):
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.a1["id"])
        self.assertIn("passage", self.echec("artiste_delete", id=self.a1["id"]))


class Affectations(Monde):
    def setUp(self):
        super().setUp()
        self.e = self.evenement()
        self.fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        self.fc = self.formule()
        self.rev = self.ok("revendeur_save", nom="Léa Martin")

    def test_un_revendeur_independant_prend_une_formule_de_revendeur(self):
        a = self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"], quota=20)
        self.assertEqual(a["ref"], "AFF-000001")
        self.assertEqual(self.ok("evenement_fiche", id=self.e["id"])["affectations"][0]["formule"], "Formule C")

    def test_jamais_une_formule_d_artiste(self):
        self.assertIn("formule de revendeur", self.echec("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fa["id"]))

    def test_un_artiste_vendeur_ne_s_affecte_pas_il_vend_par_son_passage(self):
        a = self.ok("artiste_save", scene="Les Marées", formule_id=self.fa["id"], vend=1)
        rid = self.ok("artiste", id=a["id"])["artiste"]["revendeur_id"]
        self.assertIn("passage", self.echec("affectation_save", evenement_id=self.e["id"], revendeur_id=rid, formule_id=self.fc["id"]))

    def test_la_meme_affectation_ne_se_double_pas(self):
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"])
        self.assertIn("doublon", self.echec("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"]))

    def test_un_revendeur_suspendu_ne_recoit_pas_de_places(self):
        self.ok("revendeur_save", id=self.rev["id"], actif=0)
        self.assertIn("suspendu", self.echec("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"]))

    def test_un_revendeur_affecte_ne_se_supprime_pas(self):
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"])
        self.assertIn("affectation", self.echec("revendeur_delete", id=self.rev["id"]))


class Droits(Monde):
    def test_sans_le_droit_gerer_rien_ne_passe(self):
        r = self.ex("salle_save", compte="intrus@x.fr", nom="X", assis=10)
        self.assertIn(r["statut"], ("refuse", "echec"), r)
        self.assertEqual(self.liste("salles"), [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Salles, Formules, Artistes, Revendeurs, Evenements, Programme, Affectations …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
