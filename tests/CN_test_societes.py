# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Sociétés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #9e0cde
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du socle société : tout compte a une société, la fiche est cloisonnée, les fonctions ne valent que dans la leur.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9e0cde ▼▼▼
"""Bancs du socle société : rattachement obligatoire des comptes, fiche cloisonnée, fonctions attachées à une société, superadministrateur seul maître de l'ensemble."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402
from noyau import CN_chemins as chemins       # noqa: E402

BEA, CAM, DAN, EVE = "bea@x.fr", "cam@x.fr", "dan@x.fr", "eve@x.fr"
MDP = "Abcdefgh1!"
IBAN = "FR1420041010050500013M02606"
FORM = "lumen-formation"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes", "societes", "coffre", "ged", "reglages", "contacts"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "societes", "coffre", "ged", "reglages", "contacts"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.multi = True
        self.n.executeur.contextes["societes"].reglage = lambda nom, compte=None: self.multi if nom == "multi" else None
        self.idt = self.n.identite

    # ── aides ────────────────────────────────────────────────────────────────
    def ex(self, cap, compte=BEA, dans="", **args):
        """`dans` : la société choisie pour l'acte (l'en-tête X-Societe) ; `societe=` reste un argument de la capacité."""
        return self.n.executeur.executer(cap, "humain", args, compte=compte, societe=dans)

    def ok(self, cap, compte=BEA, dans="", **args):
        r = self.ex(cap, compte=compte, dans=dans, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def non(self, cap, compte=BEA, dans="", **args):
        r = self.ex(cap, compte=compte, dans=dans, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r

    def monde(self):
        """BEA (superadministrateur, société principale), CAM (principale), une 2e société et DAN dedans."""
        for c in (BEA, CAM):
            r = self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="")
            self.assertEqual(r["statut"], "faite", r)
        self.ok("societes.creer", compte=BEA, nom="Lumen Formation", identifiant=FORM)
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": DAN, "mot_de_passe": MDP, "societe": FORM}, compte=BEA)
        self.assertEqual(r["statut"], "faite", r)

    # ── le rattachement ──────────────────────────────────────────────────────
    def test_la_societe_principale_existe_et_tout_compte_en_a_une(self):
        self.monde()
        self.assertEqual(self.idt.societe("1")["principale"], 1)
        self.assertEqual((self.idt.societe_de(BEA), self.idt.societe_de(CAM), self.idt.societe_de(DAN)), ("1", "1", FORM))

    def test_un_compte_ne_se_cree_pas_sans_societe_valide(self):
        self.monde()
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": EVE, "mot_de_passe": MDP, "societe": "inconnue"}, compte=BEA)
        self.assertIn(r["statut"], ("echec", "refuse"))
        self.assertFalse(self.idt.existe(EVE))

    def test_seul_le_superadministrateur_range_un_compte_dans_une_autre_societe(self):
        self.monde()
        self.n.executeur.executer("droits.admin", "humain", {"compte": CAM, "admin": True}, compte=BEA)
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": EVE, "mot_de_passe": MDP, "societe": FORM}, compte=CAM)
        self.assertEqual(r["statut"], "echec", r)
        self.assertIn("superadministrateur", r["erreur"])

    def test_l_espace_d_un_utilisateur_est_dans_le_repertoire_de_sa_societe(self):
        p = chemins.espace_compte("lumen-formation", "dan@x.fr", "ged")
        self.assertEqual(p.parts[-4:], ("lumen-formation", "utilisateurs", "dan@x.fr", "ged"))
        with self.assertRaises(ValueError):
            chemins.espace_compte("../dehors", "dan@x.fr", "ged")

    # ── la gestion de l'ensemble des sociétés ────────────────────────────────
    def test_seul_le_superadministrateur_cree_archive_et_rouvre_une_societe(self):
        self.monde()
        self.n.executeur.executer("droits.admin", "humain", {"compte": CAM, "admin": True}, compte=BEA)      # CAM : administratrice de l'instance, pas superadministratrice
        for cap, args in (("societes.creer", {"nom": "X"}), ("societes.archiver", {"societe": FORM}), ("societes.rouvrir", {"societe": FORM})):
            r = self.non(cap, compte=CAM, **args)
            self.assertIn("superadministrateur", r.get("erreur", ""), r)

    def test_plusieurs_societes_demandent_le_module_multi_societes(self):
        self.monde()
        self.multi = False
        r = self.non("societes.creer", compte=BEA, nom="Une autre")
        self.assertIn("Multi-sociétés", r["erreur"])

    def test_une_societe_avec_des_comptes_ne_s_archive_pas_et_la_principale_jamais(self):
        self.monde()
        self.assertIn("transférez", self.non("societes.archiver", compte=BEA, societe=FORM)["erreur"])
        self.assertIn("principale", self.non("societes.archiver", compte=BEA, societe="1")["erreur"])
        self.ok("societes.creer", compte=BEA, nom="Vide", identifiant="vide")
        self.ok("societes.archiver", compte=BEA, societe="vide")
        self.assertTrue(self.idt.societe("vide")["archivee"])
        self.ok("societes.rouvrir", compte=BEA, societe="vide")
        self.assertFalse(self.idt.societe("vide")["archivee"])

    def test_creer_une_societe_ouvre_ses_fonctions_et_son_espace_de_coffre(self):
        self.monde()
        r = self.ok("societes.creer", compte=BEA, nom="Studio", identifiant="studio", administrateur=DAN)
        self.assertEqual(r["societe"], "studio")
        noms = {f["fonction"] for f in self.ok("societes.fonctions", compte=BEA, societe="studio")["fonctions"]}
        self.assertEqual(noms, {"titulaire", "admin", "gestion", "compta", "conformite", "membre", "invite"})
        self.assertEqual(self.idt.societe("studio")["principale"], 0)

    def test_une_creation_se_defait(self):
        self.monde()
        res = self.ex("societes.creer", compte=BEA, nom="Passager", identifiant="passager")
        self.assertEqual(res["statut"], "faite")
        self.n.catalogue.get("societes.creer").defaire(self.n.executeur.contextes["societes"], res["resultat"])
        self.assertIsNone(self.idt.societe("passager"))

    # ── le cloisonnement de la fiche ─────────────────────────────────────────
    def test_une_societe_ne_lit_pas_la_fiche_d_une_autre_meme_pour_un_administrateur_d_instance(self):
        self.monde()
        self.n.executeur.executer("droits.admin", "humain", {"compte": CAM, "admin": True}, compte=BEA)      # administratrice, pas superadministratrice
        for compte, societe in ((DAN, "1"), (CAM, FORM)):
            self.non("societes.fiche_lire", compte=compte, societe=societe)
        self.assertEqual(self.ok("societes.fiche_lire", compte=BEA, societe=FORM)["societe"], FORM)            # le superadministrateur, lui, peut les administrer toutes

    def test_sans_fonction_on_ne_voit_pas_la_fiche_mais_on_nomme_la_societe(self):
        self.monde()
        f = self.ok("societes.fiche_lire", compte=CAM)
        self.assertEqual(f["rubriques"], {})
        self.assertEqual(self.ok("societes.carte", compte=CAM)["nom"], "Société principale")             # les modules, eux, ont de quoi nommer
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="membre")
        vu = self.ok("societes.fiche_lire", compte=CAM)
        self.assertIn("identite", vu["rubriques"])
        self.assertNotIn("banque", vu["rubriques"])
        self.non("societes.fiche_regler", compte=CAM, rubrique="siege", valeurs={"ville": "Bordeaux"})     # voir n'est pas modifier

    def test_modifier_la_fiche_demande_le_niveau_modifier_et_se_defait(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="gestion")
        res = self.ex("societes.fiche_regler", compte=CAM, rubrique="siege", valeurs={"ville": "Bordeaux", "email": "contact@x.fr"})
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.ok("societes.fiche_lire", compte=CAM)["rubriques"]["siege"]["ville"], "Bordeaux")
        self.n.catalogue.get("societes.fiche_regler").defaire(self.n.executeur.contextes["societes"], res["resultat"])
        self.assertEqual(self.ok("societes.fiche_lire", compte=CAM)["rubriques"]["siege"]["ville"], "")

    def test_les_valeurs_sont_validees(self):
        self.monde()
        for rub, v in (("identite", {"siren": "123456789"}), ("siege", {"email": "pas-un-mail"}), ("habillage", {"accent": "rouge"}),
                       ("regional", {"fuseau": "Paris"}), ("siege", {"inconnu": "x"}), ("horaires", {"jours": [1, 2]}), ("banque", {"iban": "FR00"})):
            self.non("societes.fiche_regler", compte=BEA, rubrique=rub, valeurs=v)
        self.ok("societes.fiche_regler", compte=BEA, rubrique="identite", valeurs={"siren": "123 456 782", "forme": "SAS"})
        self.assertEqual(self.ok("societes.fiche_lire", compte=BEA)["rubriques"]["identite"]["siren"], "123456782")

    def test_la_banque_est_sensible_l_iban_est_masque_et_son_affichage_journalise(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="compta")
        self.ok("societes.fiche_regler", compte=CAM, rubrique="banque", valeurs={"iban": IBAN, "banque": "Banque exemple"})
        masque = self.ok("societes.fiche_lire", compte=CAM)["rubriques"]["banque"]["iban"]
        self.assertNotIn("0500013M", masque)
        self.assertTrue(masque.endswith("2606"))
        self.assertEqual(self.ok("societes.iban_voir", compte=CAM)["iban"].replace(" ", ""), IBAN)
        self.ok("societes.affecter", compte=BEA, utilisateur=DAN, fonction="")                                  # DAN n'est pas de cette société : aucun accès
        histoire = " ".join(h["resume"] for h in self.ok("societes.historique", compte=BEA)["historique"])
        self.assertIn("a affiché l'IBAN", histoire)
        # l'historique ne garde jamais l'IBAN en clair
        lignes = self.n.executeur.contextes["societes"].stockage.lire("SELECT avant, apres FROM historique")
        self.assertFalse(any("0500013M" in (l["avant"] + l["apres"]) for l in lignes))

    def test_un_gestionnaire_ne_voit_pas_l_iban(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="gestion")
        self.non("societes.iban_voir", compte=CAM)

    def test_les_echeances_viennent_des_pieces_et_de_l_exercice(self):
        self.monde()
        self.ok("societes.fiche_regler", compte=BEA, rubrique="pieces", valeurs={"items": [{"id": "1", "nom": "Assurance", "exp": "2999-01-01"}]})
        e = self.ok("societes.echeances", compte=BEA)["echeances"]
        self.assertEqual({x["genre"] for x in e}, {"piece", "exercice"})

    # ── les fonctions : des groupes attachés à une société ───────────────────
    def test_une_fonction_ne_donne_rien_hors_de_sa_societe(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")                           # CAM : administratrice de « 1 »
        d = self.n.droits
        self.assertTrue(d.raison(CAM, "societes.equipe_gerer", "1")["accord"])
        self.assertFalse(d.raison(CAM, "societes.equipe_gerer", FORM)["accord"])
        self.assertFalse(d.raison(CAM, "societes.equipe_gerer", "")["accord"])
        self.assertNotIn("societes.equipe_gerer", d.detenus(CAM)["droits"])                                    # hors société : rien

    def test_un_seul_titulaire_et_jamais_zero(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="titulaire")
        self.ok("societes.affecter", compte=BEA, utilisateur=BEA, fonction="titulaire")
        par = {f["fonction"]: f["membres"] for f in self.ok("societes.fonctions", compte=BEA)["fonctions"]}
        self.assertEqual(par["titulaire"], [BEA])
        self.assertEqual(par["admin"], [CAM])                                                                  # l'ancien titulaire est devenu administrateur
        self.assertIn("titulaire", self.non("societes.affecter", compte=BEA, utilisateur=BEA, fonction="")["erreur"])

    def test_personne_ne_donne_plus_que_ce_qu_il_a(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")                            # admin : banque au niveau 2 seulement
        r = self.non("societes.fonction_regler", compte=CAM, fonction="membre", domaine="banque", niveau=3)
        self.assertIn("pas plus que ce qu'on a", r["erreur"])
        self.ok("societes.fonction_regler", compte=CAM, fonction="membre", domaine="banque", niveau=2)
        self.non("societes.fonction_regler", compte=CAM, fonction="titulaire", domaine="banque", niveau=0)    # la fonction de titulaire est fixe

    def test_creer_une_fonction_et_s_en_servir(self):
        self.monde()
        r = self.ok("societes.fonction_creer", compte=BEA, nom="Responsable boutique", partir_de="gestion")
        self.assertEqual(r["fonction"], "responsable-boutique")
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction=r["fonction"])
        self.assertIn("identite", self.ok("societes.fiche_lire", compte=CAM)["rubriques"])

    def test_une_affectation_se_defait(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="membre")
        res = self.ex("societes.affecter", compte=BEA, utilisateur=CAM, fonction="gestion")
        self.assertEqual(res["statut"], "faite")
        self.n.catalogue.get("societes.affecter").defaire(self.n.executeur.contextes["societes"], res["resultat"])
        par = {f["fonction"]: f["membres"] for f in self.ok("societes.fonctions", compte=BEA)["fonctions"]}
        self.assertEqual((par["membre"], par["gestion"]), ([CAM], []))

    # ── la société active d'un acte ──────────────────────────────────────────
    def test_on_n_agit_pas_dans_une_societe_qui_n_est_pas_la_sienne(self):
        self.monde()
        r = self.ex("societes.lister", compte=DAN, dans="1")
        self.assertEqual(r["statut"], "refuse", r)
        self.assertEqual(self.ok("societes.lister", compte=DAN)["societe"], FORM)
        self.assertEqual([s["id"] for s in self.ok("societes.lister", compte=DAN)["societes"]], [FORM])
        self.assertEqual({s["id"] for s in self.ok("societes.lister", compte=BEA)["societes"]}, {"1", FORM})   # le superadministrateur les voit toutes

    def test_une_fonction_dans_une_autre_societe_ouvre_cette_societe(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=CAM, fonction="membre")
        self.assertEqual({s["id"] for s in self.ok("societes.lister", compte=CAM)["societes"]}, {"1", FORM})
        self.assertIn("identite", self.ok("societes.fiche_lire", compte=CAM, societe=FORM)["rubriques"])
        self.assertEqual(self.ok("societes.fiche_lire", compte=CAM)["rubriques"], {})                         # …mais rien de plus chez soi

    # ── les comptes : chacun dans une société, cloisonnés ────────────────────
    def test_un_administrateur_de_societe_ne_voit_que_les_comptes_de_sa_societe(self):
        self.monde()
        self.n.executeur.executer("droits.admin", "humain", {"compte": CAM, "admin": True}, compte=BEA)      # administratrice de l'instance, pas superadministratrice
        vus = {c["compte"] for c in self.ok("comptes.lister", compte=CAM)["comptes"]}
        self.assertIn(CAM, vus)
        self.assertNotIn(DAN, vus)                                                                            # DAN est d'une autre société
        r = self.n.executeur.executer("comptes.lire", "humain", {"compte": DAN}, compte=CAM)
        self.assertEqual(r["statut"], "echec", r)
        self.assertIn("pas dans votre société", r["erreur"])
        self.assertEqual({c["compte"] for c in self.ok("comptes.lister", compte=BEA)["comptes"]} >= {BEA, CAM, DAN}, True)   # le superadministrateur voit tout

    def test_seul_le_superadministrateur_change_un_compte_de_societe_et_cela_se_defait(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")
        self.n.executeur.executer("droits.admin", "humain", {"compte": CAM, "admin": True}, compte=BEA)
        r = self.n.executeur.executer("comptes.transferer", "humain", {"compte": CAM, "societe": FORM}, compte=CAM)
        self.assertEqual(r["statut"], "echec", r)
        res = self.n.executeur.executer("comptes.transferer", "humain", {"compte": CAM, "societe": FORM}, compte=BEA)
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.idt.societe_de(CAM), FORM)
        self.assertEqual(self.n.droits.groupes_de(CAM, "1"), [])                                               # ses fonctions d'avant sont tombées
        self.n.catalogue.get("comptes.transferer").defaire(self.n.executeur.contextes["comptes"], res["resultat"])
        self.assertEqual(self.idt.societe_de(CAM), "1")
        self.assertEqual(self.n.droits.groupes_de(CAM, "1"), ["s1.admin"])

    # ── chaque société a ses modules ─────────────────────────────────────────
    def test_un_module_n_est_ouvert_que_dans_les_societes_ou_on_l_a_ouvert(self):
        self.monde()
        self.ok("ged.sources", compte=CAM)                                                                    # la société principale a tout ce qui est actif
        r = self.non("ged.sources", compte=DAN)                                                               # une autre société : rien d'ouvert d'office
        self.assertIn("n'est pas ouvert", r.get("raison", "") + r.get("erreur", ""))
        self.ok("societes.module_regler", compte=BEA, societe=FORM, module="ged", ouvert=True)
        self.ok("ged.sources", compte=DAN)
        self.ok("societes.module_regler", compte=BEA, societe=FORM, module="ged", ouvert=False)
        self.non("ged.sources", compte=DAN)
        self.ok("societes.module_regler", compte=BEA, societe="1", module="ged", ouvert=False)               # on peut aussi fermer un module à la société principale
        self.non("ged.sources", compte=CAM)

    def test_les_modules_vitaux_sont_ouverts_partout(self):
        self.monde()
        self.ok("societes.lister", compte=DAN)                                                                # societes, comptes, droits, coffre : vitaux
        self.ok("coffre.espaces", compte=DAN)
        self.ok("comptes.moi", compte=DAN)
        r = self.non("societes.module_regler", compte=BEA, societe=FORM, module="comptes", ouvert=False)
        self.assertIn("vital", r["erreur"])

    def test_l_administrateur_d_une_societe_choisit_les_modules_de_sa_societe_seulement(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.module_regler", compte=DAN, societe=FORM, module="ged", ouvert=True)
        self.ok("ged.sources", compte=DAN)
        self.ok("societes.module_regler", compte=DAN, societe=FORM, module="ged", ouvert=False)
        self.non("ged.sources", compte=DAN)
        self.non("societes.module_regler", compte=DAN, societe="1", module="ged", ouvert=False)                # pas celle des autres
        self.assertTrue(self.ok("societes.modules", compte=DAN, societe=FORM)["peut_regler"])
        mods = {m["id"]: m for m in self.ok("societes.modules", compte=DAN, societe=FORM)["modules"]}
        self.assertTrue(mods["comptes"]["ouvert"] and mods["comptes"]["vital"])

    def test_un_membre_ordinaire_n_ouvre_aucun_module(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="membre")
        self.non("societes.module_regler", compte=DAN, societe=FORM, module="ged", ouvert=True)
        self.assertFalse(self.ok("societes.modules", compte=DAN, societe=FORM)["peut_regler"])

    def test_un_module_d_instance_n_existe_que_dans_la_societe_principale(self):
        self.monde()
        idt = self.n.identite
        self.assertTrue(idt.module_ouvert("1", "x", "optionnel", False, True))
        self.assertFalse(idt.module_ouvert(FORM, "x", "optionnel", False, True))
        idt.module_regler(FORM, "x", True)                                                                      # même « ouvert » par erreur : jamais ailleurs
        self.assertFalse(idt.module_ouvert(FORM, "x", "vital", True, True))
        self.assertTrue(idt.module_ouvert(FORM, "y", "vital", False, False))

    def test_un_reglage_d_instance_ne_se_pose_que_depuis_la_societe_principale(self):
        self.monde()
        r = self.non("reglages.regler", compte=BEA, dans=FORM, cle="ged.docs_base", valeur="/tmp/x")
        self.assertIn("société principale", r.get("erreur", "") + r.get("raison", ""))
        self.ok("reglages.regler", compte=BEA, cle="ged.docs_base", valeur="")

    # ── les partages entre sociétés ─────────────────────────────────────────
    def test_sans_partage_un_administrateur_de_societe_ne_range_pas_un_utilisateur_d_une_autre(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        r = self.non("societes.affecter", compte=DAN, societe=FORM, utilisateur=CAM, fonction="membre")
        self.assertIn("partagé", r.get("erreur", ""))
        self.assertEqual(self.ok("societes.partageables", compte=DAN, societe=FORM)["utilisateurs"], [])

    def test_un_partage_met_les_utilisateurs_d_une_societe_a_la_disposition_d_une_autre(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="tous")
        liste = {u["compte"] for u in self.ok("societes.partageables", compte=DAN, societe=FORM)["utilisateurs"]}
        self.assertEqual(liste, {BEA, CAM})
        self.ok("societes.affecter", compte=DAN, societe=FORM, utilisateur=CAM, fonction="membre")
        self.assertIn(FORM, self.n.droits.societes_de(CAM))
        p = self.ok("societes.partages", compte=DAN, societe=FORM)
        self.assertEqual([x["source"] for x in p["entrants"]], ["1"])
        self.assertFalse(p["peut_decider"])

    def test_un_partage_choisi_ne_met_a_disposition_que_ceux_qu_on_a_choisis(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="choisis", elements=[CAM])
        self.assertEqual([u["compte"] for u in self.ok("societes.partageables", compte=DAN, societe=FORM)["utilisateurs"]], [CAM])
        self.non("societes.affecter", compte=DAN, societe=FORM, utilisateur=BEA, fonction="membre")
        self.non("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="choisis", elements=[DAN])      # DAN n'est pas de la société qui partage

    def test_seul_le_superadministrateur_decide_d_un_partage_et_le_retrait_le_referme(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        r = self.non("societes.partager", compte=DAN, source=FORM, destinataire="1", mode="tous")
        self.assertIn("superadministrateur", r["erreur"])
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="tous")
        self.ok("societes.partage_retirer", compte=BEA, source="1", destinataire=FORM)
        self.non("societes.affecter", compte=DAN, societe=FORM, utilisateur=CAM, fonction="membre")
        self.non("societes.partage_retirer", compte=BEA, source="1", destinataire=FORM)                               # il n'existe plus
        self.non("societes.partager", compte=BEA, source="1", destinataire="1", mode="tous")                          # pas avec soi-même

    # ── le profil d'une personne dans une société, et les modèles recopiés ──
    def test_une_personne_a_un_profil_par_societe(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="tous")
        self.ok("societes.affecter", compte=DAN, societe=FORM, utilisateur=CAM, fonction="membre")                  # CAM travaille dans deux sociétés
        self.ok("societes.profil_regler", compte=CAM, societe="1", nom="Cam Dupont", fonction="Comptable", email="cam@principale.fr")
        self.ok("societes.profil_regler", compte=CAM, societe=FORM, dans=FORM, nom="Cam D.", fonction="Intervenante", tel="0102")
        self.assertEqual(self.ok("societes.profil_lire", compte=CAM, societe="1")["fonction"], "Comptable")
        p = self.ok("societes.profil_lire", compte=CAM, societe=FORM, dans=FORM)
        self.assertEqual((p["nom"], p["fonction"], p["tel"], p["email"]), ("Cam D.", "Intervenante", "0102", ""))     # un profil par société, rien de commun
        self.non("societes.profil_regler", compte=CAM, societe="1", email="pas-une-adresse")
        self.non("societes.profil_lire", compte=CAM, societe="1", utilisateur=BEA)                                  # le profil d'un autre : pour l'administrateur seulement

    def test_le_profil_d_un_autre_ne_se_lit_et_ne_se_regle_que_pour_son_administrateur(self):
        self.monde()
        self.ok("societes.profil_regler", compte=CAM, societe="1", nom="Cam")                                      # chacun règle le sien
        self.non("societes.profil_regler", compte=CAM, societe="1", utilisateur=BEA, nom="Béa")                    # un membre ordinaire ne règle pas le profil d'un autre
        self.ok("societes.profil_regler", compte=BEA, societe="1", utilisateur=CAM, fonction="Compta")             # le superadministrateur, si
        self.assertEqual(self.ok("societes.profil_lire", compte=CAM, societe="1")["fonction"], "Compta")

    def test_les_modeles_d_une_societe_se_recopient_si_elle_les_partage_jamais_la_banque(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.fiche_regler", compte=BEA, societe="1", rubrique="habillage", valeurs={"accent": "#ff0000"})
        self.ok("societes.fiche_regler", compte=BEA, societe="1", rubrique="banque", valeurs={"pref_devis": "DEV-", "pref_facture": "FAC-", "iban": IBAN})
        self.non("societes.modeles_recopier", compte=DAN, societe=FORM, dans=FORM, depuis="1")                      # pas de partage : rien
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, type="modeles")
        self.ok("societes.modeles_recopier", compte=DAN, societe=FORM, dans=FORM, depuis="1")
        self.assertEqual(self.ok("societes.fiche_lire", compte=DAN, societe=FORM, dans=FORM)["rubriques"]["habillage"]["accent"], "#ff0000")
        ban = self.ok("societes.fiche_lire", compte=DAN, societe=FORM, dans=FORM)["rubriques"].get("banque", {})
        self.assertEqual((ban.get("pref_devis"), ban.get("pref_facture")), ("DEV-", "FAC-"))
        self.assertFalse(ban.get("iban"))                                                                          # la banque ne se recopie jamais
        self.non("societes.modeles_recopier", compte=DAN, societe=FORM, dans=FORM, depuis=FORM)                    # pas depuis soi-même

    def test_une_societe_creee_peut_reprendre_les_modeles_d_une_autre(self):
        self.monde()
        self.ok("societes.fiche_regler", compte=BEA, societe="1", rubrique="habillage", valeurs={"accent": "#123456", "entete": "bandeau"})
        self.ok("societes.creer", compte=BEA, nom="Fille", identifiant="fille", modeles_de="1")
        h = self.ok("societes.fiche_lire", compte=BEA, societe="fille")["rubriques"]["habillage"]
        self.assertEqual((h["accent"], h["entete"]), ("#123456", "bandeau"))

    def test_la_vue_consolidee_resume_toutes_les_societes_pour_le_superadministrateur(self):
        self.monde()
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, mode="tous")
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("societes.module_demander", compte=DAN, societe=FORM, nom="Documents", motif="classer")
        v = {x["id"]: x for x in self.ok("societes.vue_consolidee", compte=BEA)["societes"]}
        self.assertEqual(set(v), {"1", FORM})
        self.assertEqual((v["1"]["utilisateurs"], v[FORM]["utilisateurs"]), (2, 1))                                # BEA et CAM chez la principale, DAN chez Lumen
        self.assertEqual((v["1"]["partages_donnes"], v[FORM]["partages_recus"]), (1, 1))
        self.assertEqual((v[FORM]["demandes"], v["1"]["demandes"]), (1, 0))
        self.assertGreater(v["1"]["modules"], v[FORM]["modules"])                                                  # la principale a tout ce qui est actif, Lumen les modules vitaux
        self.non("societes.vue_consolidee", compte=CAM)                                                            # réservée au superadministrateur

    def test_les_membres_d_une_societe_sont_des_personnes_pas_des_agents(self):
        self.monde()
        comptes = {m["compte"] for m in self.ok("societes.membres", compte=BEA, societe="1")["membres"]}
        self.assertEqual(comptes, {BEA, CAM})                                                                      # ni cassandra, ni itare, ni le noyau

    # ── les demandes de module ──────────────────────────────────────────────
    def test_une_societe_secondaire_demande_un_module_et_la_principale_l_attribue(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.non("societes.module_demander", compte=DAN, societe=FORM, nom="Documents", motif="")                   # sans motif, rien
        d = self.ok("societes.module_demander", compte=DAN, societe=FORM, nom="Documents", motif="classer les contrats", source="logithèque")
        self.non("societes.module_demandes", compte=CAM, toutes=True)                                              # seul le superadministrateur les voit toutes
        self.assertEqual([x["nom"] for x in self.ok("societes.module_demandes", compte=BEA, toutes=True)["demandes"]], ["Documents"])
        self.assertEqual(len(self.ok("societes.module_demandes", compte=DAN, societe=FORM)["demandes"]), 1)       # la société voit les siennes
        r = self.non("societes.module_demande_decider", compte=DAN, id=d["id"], decision="accepter", module="ged")
        self.assertIn("superadministrateur", r["erreur"])
        self.non("societes.module_demande_decider", compte=BEA, id=d["id"], decision="accepter", module="inexistant")
        self.non("societes.module_demande_decider", compte=BEA, id=d["id"], decision="accepter", module="comptes")  # un module vital est déjà partout
        self.non("ged.sources", compte=DAN)                                                                        # rien n'est ouvert tant qu'on n'a pas décidé
        self.ok("societes.module_demande_decider", compte=BEA, id=d["id"], decision="accepter", module="ged", reponse="installé")
        self.ok("ged.sources", compte=DAN)                                                                         # attribué à la société demandeuse
        self.non("ged.sources", compte=CAM)                                                                        # installé pour eux : la principale ne l'a pas d'office
        self.non("societes.module_demande_decider", compte=BEA, id=d["id"], decision="refuser")                    # une demande se décide une fois
        etat = self.ok("societes.module_demandes", compte=DAN, societe=FORM)["demandes"][0]
        self.assertEqual((etat["etat"], etat["module"], etat["reponse"]), ("acceptee", "ged", "installé"))

    def test_une_demande_refusee_n_ouvre_rien(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        d = self.ok("societes.module_demander", compte=DAN, societe=FORM, nom="Documents", motif="x")
        self.ok("societes.module_demande_decider", compte=BEA, id=d["id"], decision="refuser", reponse="pas maintenant")
        self.non("ged.sources", compte=DAN)
        self.assertEqual(self.ok("societes.module_demandes", compte=DAN, societe=FORM)["demandes"][0]["etat"], "refusee")

    # ── le carnet de la société ─────────────────────────────────────────────
    def test_le_carnet_de_la_societe_est_commun_et_les_carnets_personnels_restent_prives(self):
        self.monde()
        self.ok("contacts.societe_creer", compte=BEA, display_name="Client A", emails=["a@x.fr"], notes="note privée")
        self.assertEqual([f["display_name"] for f in self.ok("contacts.societe_lister", compte=CAM)["contacts"]], ["Client A"])
        self.assertEqual(self.ok("contacts.lister", compte=CAM)["contacts"], [])                                  # son carnet personnel est vide
        self.assertEqual(self.ok("contacts.lister", compte=BEA)["contacts"], [])                                  # et celui de BEA ne contient pas la fiche de la société
        self.non("contacts.societe_creer", compte=CAM, display_name="Client B")                                   # lire est ouvert, écrire demande une fonction
        self.ok("societes.affecter", compte=BEA, societe="1", utilisateur=CAM, fonction="gestion")
        self.ok("contacts.societe_creer", compte=CAM, display_name="Client B")
        self.assertEqual(len(self.ok("contacts.societe_lister", compte=BEA)["contacts"]), 2)

    def test_un_carnet_de_societe_partage_se_lit_sans_les_notes_et_jamais_sans_partage(self):
        self.monde()
        self.ok("societes.module_regler", compte=BEA, societe=FORM, module="contacts", ouvert=True)
        self.ok("societes.affecter", compte=BEA, societe=FORM, utilisateur=DAN, fonction="admin")
        self.ok("contacts.societe_creer", compte=BEA, display_name="Client A", emails=["a@x.fr"], notes="note privée")
        self.non("contacts.societe_partage_lister", compte=DAN, dans=FORM, depuis="1")                              # pas de partage : rien
        self.assertEqual(self.ok("contacts.societe_lister", compte=DAN, dans=FORM)["contacts"], [])               # le carnet de FORM est le sien, vide
        self.ok("societes.partager", compte=BEA, source="1", destinataire=FORM, type="contacts", mode="choisis", elements=["x"])
        liste = self.ok("contacts.societe_partage_lister", compte=DAN, dans=FORM, depuis="1")["contacts"]
        self.assertEqual([f["display_name"] for f in liste], ["Client A"])
        self.assertEqual(liste[0]["emails"], ["a@x.fr"])
        self.assertNotIn("notes", liste[0])
        self.assertEqual(self.ok("contacts.societe_partage_voir", compte=DAN, dans=FORM, depuis="1", id=liste[0]["id"])["contact"]["display_name"], "Client A")
        self.assertEqual(self.ok("societes.partages", compte=DAN, societe=FORM)["entrants"][0]["mode"], "tous")  # un carnet se partage en entier
        self.non("contacts.societe_partage_lister", compte=BEA, dans="1", depuis=FORM)                           # le partage va dans un seul sens

    def test_les_menus_et_les_droits_ne_montrent_que_les_modules_de_la_societe(self):
        self.monde()
        ctx = self.n.executeur.contextes["societes"]
        ctx._societe.valeur = FORM
        try:
            ids = {m.id for m in ctx.manifestes_actifs()}
            self.assertNotIn("ged", ids)
            self.assertIn("comptes", ids)
            self.assertIn("ged", {m.id for m in ctx.manifestes_actifs(toutes=True)})
        finally:
            ctx._societe.valeur = ""

    def test_une_societe_creee_peut_recopier_les_modules_d_une_autre(self):
        self.monde()
        self.ok("societes.creer", compte=BEA, nom="Clone", identifiant="clone", modules_de="1")
        self.assertTrue(self.idt.module_ouvert("clone", "ged"))
        self.ok("societes.creer", compte=BEA, nom="Nu", identifiant="nu")
        self.assertFalse(self.idt.module_ouvert("nu", "ged"))

    # ── la gestion des utilisateurs par l'administrateur d'une société ───────
    def test_l_administrateur_d_une_societe_gere_les_utilisateurs_de_sa_societe_seulement(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")                          # CAM : administratrice de la société « 1 », pas de l'instance
        self.assertFalse(self.n.droits.est_admin(CAM))
        res = self.n.executeur.executer("comptes.creer", "humain", {"compte": EVE, "mot_de_passe": MDP}, compte=CAM)
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.idt.societe_de(EVE), "1")                                                       # rangé dans SA société
        vus = {c["compte"] for c in self.ok("comptes.lister", compte=CAM)["comptes"]}
        self.assertIn(EVE, vus)
        self.assertNotIn(DAN, vus)
        for cap, args in (("comptes.desactiver", {"compte": DAN}), ("comptes.modifier", {"compte": DAN, "display_name": "x"}), ("comptes.supprimer", {"compte": DAN})):
            r = self.n.executeur.executer(cap, "humain", args, compte=CAM)
            self.assertEqual(r["statut"], "echec", (cap, r))
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": "fay@x.fr", "mot_de_passe": MDP, "societe": FORM}, compte=CAM)
        self.assertEqual(r["statut"], "echec", r)                                                             # pas dans une autre société
        r = self.n.executeur.executer("comptes.desactiver", "humain", {"compte": EVE}, compte=CAM)
        self.assertEqual(r["statut"], "faite", r)

    def test_le_droit_de_gerer_les_comptes_ne_vaut_que_dans_la_societe_de_la_fonction(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")
        mes = self.n.executeur.executer("droits.mes_droits", "humain", {"compte": CAM}, compte=CAM)
        self.assertEqual(mes["statut"], "faite", mes)
        self.assertIn("comptes.gerer", mes["resultat"]["droits"])                                             # chez elle
        mes2 = self.n.executeur.executer("droits.mes_droits", "humain", {"compte": CAM}, compte=CAM, societe=FORM)
        self.assertEqual(mes2["statut"], "refuse", mes2)                                                      # elle n'a aucun accès à la société FORM
        self.assertNotIn("comptes.gerer", self.n.droits.detenus(CAM, FORM)["droits"])

    def test_un_utilisateur_peut_avoir_plusieurs_societes_sans_etre_administrateur(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, societe="1", utilisateur=DAN, fonction="membre")             # DAN est de FORM ; membre de la société principale aussi
        self.assertEqual({s["id"] for s in self.ok("societes.lister", compte=DAN)["societes"]}, {"1", FORM})
        self.assertFalse(self.n.droits.est_admin(DAN))
        r = self.ex("societes.lister", compte=DAN, dans="1")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["societe"], "1")
        self.assertIn("identite", self.ok("societes.fiche_lire", compte=DAN, dans="1")["rubriques"])           # voir la fiche de « 1 » avec sa fonction de membre
        r = self.n.executeur.executer("comptes.creer", "humain", {"compte": "zoe@x.fr", "mot_de_passe": MDP}, compte=DAN, societe="1")
        self.assertIn(r["statut"], ("refuse", "echec"), r)                                                    # membre : il ne gère personne

    def test_la_corbeille_des_comptes_est_celle_de_la_societe(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")
        self.n.executeur.executer("comptes.creer", "humain", {"compte": EVE, "mot_de_passe": MDP}, compte=CAM)
        self.n.executeur.executer("comptes.supprimer", "humain", {"compte": EVE}, compte=CAM)
        self.n.executeur.executer("comptes.supprimer", "humain", {"compte": DAN}, compte=BEA)               # un compte de FORM, supprimé par le superadministrateur
        corbeille = self.ok("comptes.corbeille", compte=CAM)["corbeille"]
        self.assertEqual({c["compte"] for c in corbeille}, {EVE})
        tout = {c["compte"] for c in self.ok("comptes.corbeille", compte=BEA)["corbeille"]}
        self.assertEqual(tout, {EVE, DAN})
        id_dan = next(c["id"] for c in self.ok("comptes.corbeille", compte=BEA)["corbeille"] if c["compte"] == DAN)
        r = self.n.executeur.executer("comptes.restaurer", "humain", {"corbeille": id_dan}, compte=CAM)
        self.assertEqual(r["statut"], "echec", r)

    # ── les réglages par société ─────────────────────────────────────────────
    def lu(self, societe, cle="vue_modele"):
        """Ce que le module des contacts lit pour ce réglage quand il agit dans cette société."""
        ctx = self.n.executeur.contextes["contacts"]
        ctx._societe.valeur = societe
        try:
            return ctx.reglage(cle)
        finally:
            ctx._societe.valeur = ""

    def test_un_reglage_par_societe_suit_l_instance_tant_qu_on_ne_l_a_pas_pose(self):
        self.monde()
        self.assertEqual((self.lu("1"), self.lu(FORM)), ("expurgee", "expurgee"))
        self.ok("reglages.regler", compte=BEA, cle="contacts.vue_modele", valeur="complete", pour_societe=FORM)
        self.assertEqual(self.lu(FORM), "complete")
        self.assertEqual(self.lu("1"), "expurgee")                                                            # les autres sociétés ne bougent pas
        self.ok("reglages.reinitialiser", compte=BEA, cle="contacts.vue_modele", pour_societe=FORM)
        self.assertEqual(self.lu(FORM), "expurgee")                                                           # retour à la valeur de l'instance

    def test_seul_l_administrateur_de_la_societe_regle_ses_reglages(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="membre")
        r = self.non("reglages.regler", compte=CAM, cle="contacts.vue_modele", valeur="complete", pour_societe="1")
        self.assertIn("administrateur", r["erreur"])
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")
        self.ok("reglages.regler", compte=CAM, cle="contacts.vue_modele", valeur="complete", pour_societe="1")
        self.assertEqual(self.lu("1"), "complete")
        r = self.non("reglages.regler", compte=CAM, cle="contacts.vue_modele", valeur="complete", pour_societe=FORM)    # pas la sienne
        self.assertIn("pas la vôtre", r["erreur"])

    def test_un_reglage_global_ne_se_pose_pas_pour_une_societe(self):
        self.monde()
        r = self.non("reglages.regler", compte=BEA, cle="comptes.session_heures", valeur=4, pour_societe="1")
        self.assertIn("réglage global", r["erreur"])

    def test_la_liste_des_reglages_dit_ce_que_la_societe_a_pose(self):
        self.monde()
        self.ok("reglages.regler", compte=BEA, cle="contacts.vue_modele", valeur="complete", pour_societe=FORM)
        mine = {x["cle"]: x for x in self.ok("reglages.lire", compte=BEA, pour_societe=FORM)["reglages"] if x["portee"] == "societe"}
        self.assertTrue(mine["contacts.vue_modele"]["pose"])
        self.assertEqual(mine["contacts.vue_modele"]["valeur"], "complete")
        autre = {x["cle"]: x for x in self.ok("reglages.lire", compte=BEA, pour_societe="1")["reglages"] if x["portee"] == "societe"}
        self.assertFalse(autre["contacts.vue_modele"]["pose"])

    def test_renommer_une_societe_se_defait(self):
        self.monde()
        self.ok("societes.affecter", compte=BEA, utilisateur=CAM, fonction="admin")
        res = self.ex("societes.renommer", compte=CAM, nom="Atelier Lumen")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.idt.societe("1")["nom"], "Atelier Lumen")
        self.n.catalogue.get("societes.renommer").defaire(self.n.executeur.contextes["societes"], res["resultat"])
        self.assertEqual(self.idt.societe("1")["nom"], "Société principale")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
