# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Sociétés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du socle société : tout compte a une société, la fiche est cloisonnée, les fonctions ne valent que dans la leur.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
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
        for m in ("droits", "comptes", "societes", "coffre"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "societes", "coffre"):
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
