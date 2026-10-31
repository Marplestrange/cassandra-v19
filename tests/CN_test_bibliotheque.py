# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module bibliotheque
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #922bee
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module bibliotheque.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=922bee ▼▼▼
"""Bancs du module bibliotheque : états et transitions, déduplication, cloisonnement par société, cohérence de l'index FTS, écriture réservée à Amizo."""
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_manifeste import ACTEURS        # noqa: E402

BEA, LEO, AMIZO, AMIZO_AUTRE = "bea@x.fr", "leo@x.fr", "amizo@x.fr", "amizo2@x.fr"
MDP = "Essai-Local-1234"
JOUR = 86400
TEXTE = "Le tarif de l'abonnement fibre est de vingt euros par mois, engagement de douze mois, installation offerte."
URL_A, URL_B, URL_C = "https://exemple-a.test/tarifs", "https://exemple-b.test/offres", "https://exemple-a.test/autre"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "bibliotheque", mods / "bibliotheque", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("bibliotheque")["ok"])
        self.ctx = self.n.executeur.contextes["bibliotheque"]
        self.db = self.ctx.stockage
        self.glob = self.n.catalogue.get("bibliotheque.noter").faire.__globals__
        self.t = [time.time()]
        self.glob["_HORLOGE"][0] = lambda: self.t[0]
        self.addCleanup(lambda: self.glob["_HORLOGE"].__setitem__(0, time.time))
        for c in (BEA, AMIZO):
            self.n.identite.creer(c, MDP)
        self.n.identite.societe_creer("Autre société", "autre")
        for c in (LEO, AMIZO_AUTRE):
            self.n.identite.creer(c, MDP, societe="autre")
        self.n.identite.module_regler("autre", "bibliotheque", True)
        for c in (AMIZO, AMIZO_AUTRE):
            self.n.droits.regler("compte", c, "bibliotheque.noter", "accorde")
        for c in (BEA, LEO):
            self.n.droits.regler("compte", c, "bibliotheque.verifier", "accorde")
        self.n.reglages.poser("bibliotheque.compte_amizo", AMIZO, "")
        self.n.catalogue.regler_palier("bibliotheque.noter", "auto")          # Amizo agit seule quand l'administrateur l'a décidé

    # ── aides ────────────────────────────────────────────────────────────────
    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("bibliotheque." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def refuse(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertIn(r["statut"], ("refuse", "echec"), r)
        return r

    def noter(self, source=URL_A, titre="Tarifs", corps=TEXTE, etagere="externe", compte=AMIZO, **kw):
        return self.ok("noter", compte=compte, acteur="agent", etagere=etagere, source=source, titre=titre, corps=corps, **kw)

    def vivre(self, jours):
        self.t[0] += jours * JOUR

    def ids(self, r):
        return [x["ref"] for x in r["resultats"]]

    def chercher(self, q="abonnement fibre", **kw):
        return self.ok("chercher", q=q, **kw)

    def coherent(self):
        """L'index plein texte dit la même chose que la table des passages (le contrôle de FTS5 compare les deux)."""
        c = sqlite3.connect(self.db.chemin)
        try:
            c.execute("INSERT INTO passages_fts(passages_fts, rank) VALUES('integrity-check', 1)")
            n_fts = c.execute("SELECT COUNT(*) FROM passages_fts_docsize").fetchone()[0]
            n_tab = c.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
        finally:
            c.close()
        self.assertEqual(n_fts, n_tab)


class Etats(Monde):
    def test_un_contenu_externe_arrive_en_quarantaine_et_ne_repond_pas_d_office(self):
        r = self.noter()
        self.assertEqual((r["action"], r["etat"]), ("cree", "quarantaine"))
        self.assertEqual(self.chercher()["resultats"], [])
        trouve = self.chercher(etats=["quarantaine"])["resultats"]
        self.assertEqual([x["ref"] for x in trouve], [r["ref"]])
        self.assertFalse(trouve[0]["fiable"])

    def test_un_contenu_interne_est_verifie_d_emblee(self):
        r = self.noter(etagere="interne", source="finance:tarifs/fibre.md")
        self.assertEqual(r["etat"], "verifie")
        self.assertEqual(self.ids(self.chercher()), [r["ref"]])

    def test_l_accord_d_un_utilisateur_verifie_la_fiche(self):
        r = self.noter()
        v = self.ok("verifier", ref=r["ref"])
        self.assertEqual(v["etat"], "verifie")
        f = self.ok("fiche", ref=r["ref"])
        self.assertEqual((f["etat"], f["verifie_par"]), ("verifie", BEA))
        self.assertEqual(self.ids(self.chercher()), [r["ref"]])
        self.assertIn("déjà vérifiée", self.refuse("verifier", ref=r["ref"])["erreur"])

    def test_une_fiche_bloquee_ne_se_cherche_jamais_et_se_debloque_par_accord(self):
        r = self.noter()
        self.ok("verifier", ref=r["ref"])
        self.ok("bloquer", ref=r["ref"], motif="contenu trompeur")
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "bloque")
        self.assertEqual(self.chercher(etats=["verifie", "quarantaine", "perime"])["resultats"], [])
        self.assertIn("bloquée ne se cherche pas", self.refuse("chercher", q="fibre", etats=["bloque"])["erreur"])
        self.ok("verifier", ref=r["ref"])
        self.assertEqual(self.ids(self.chercher()), [r["ref"]])

    def test_bloquer_exige_un_motif(self):
        r = self.noter()
        self.assertIn("motif", self.refuse("bloquer", ref=r["ref"], motif="")["erreur"])

    def test_au_dela_de_quatre_vingt_dix_jours_la_fiche_est_perimee(self):
        r = self.noter()
        self.ok("verifier", ref=r["ref"])
        self.vivre(89)
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "verifie")
        self.vivre(2)
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "perime")
        self.assertEqual(self.chercher()["resultats"], [])
        self.assertEqual(self.ids(self.chercher(etats=["perime"])), [r["ref"]])
        self.assertEqual(self.ok("etagere", nom="externe")["comptes"]["externe"]["perime"], 1)

    def test_une_fiche_perimee_se_relit_avant_de_se_verifier_et_une_relecture_la_rajeunit(self):
        r = self.noter()
        self.vivre(120)
        self.assertIn("périmée", self.refuse("verifier", ref=r["ref"])["erreur"])
        relue = self.noter()                                        # le même texte, relu aujourd'hui
        self.assertEqual((relue["action"], relue["ref"]), ("rafraichi", r["ref"]))
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "quarantaine")
        self.ok("verifier", ref=r["ref"])

    def test_le_delai_de_peremption_est_un_reglage(self):
        r = self.noter()
        self.n.reglages.poser("bibliotheque.jours_peremption", 10, "")
        self.vivre(11)
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "perime")

    def test_un_texte_change_repart_en_quarantaine_et_garde_l_ancienne_version(self):
        r = self.noter()
        self.ok("verifier", ref=r["ref"])
        v2 = self.noter(corps=TEXTE + " Tarif révisé au premier janvier.")
        self.assertEqual((v2["action"], v2["version"], v2["etat"]), ("version", 2, "quarantaine"))
        f = self.ok("fiche", ref=r["ref"])
        self.assertEqual((f["etat"], f["verifie_par"]), ("quarantaine", ""))
        self.assertEqual([x["numero"] for x in f["versions"]], [1])
        self.assertEqual(self.chercher()["resultats"], [])

    def test_une_fiche_retiree_sort_de_la_recherche_et_revient_entiere(self):
        r = self.noter(etagere="interne", source="finance:tarifs/fibre.md")
        res = self.ok("retirer", ref=r["ref"], motif="obsolète")
        self.assertEqual(self.chercher()["resultats"], [])
        self.assertIn("introuvable", self.refuse("fiche", ref=r["ref"])["erreur"])
        self.n.catalogue.get("bibliotheque.retirer").defaire(self.ctx, res)
        self.assertEqual(self.ids(self.chercher()), [r["ref"]])
        self.coherent()

    def test_une_source_bloquee_ferme_la_porte_et_bloque_ses_fiches(self):
        a = self.noter(source=URL_A)
        self.noter(source=URL_C, titre="Autre", corps="Une page sans rapport sur les tarifs de la fibre optique en zone rurale.")
        res = self.ok("bloquer", source="exemple-a.test", motif="site de contrefaçon")
        self.assertEqual(len(res["bloquees"]), 2)
        self.assertIn("source bloquée", self.refuse("noter", compte=AMIZO, acteur="agent", etagere="externe", source="https://www.exemple-a.test/x", titre="t", corps="un texte nouveau")["erreur"])
        self.assertIn("bloquée", self.refuse("verifier", ref=a["ref"])["erreur"])
        self.n.catalogue.get("bibliotheque.bloquer").defaire(self.ctx, res)
        self.assertEqual(self.ok("fiche", ref=a["ref"])["etat"], "quarantaine")
        self.assertEqual(self.ok("sources")["sources"][0]["statut"], "inconnue")

    def test_autoriser_une_source_monte_la_confiance_sans_verifier_ses_fiches(self):
        r = self.noter()
        s = self.ok("verifier", source="exemple-a.test")
        self.assertEqual(s["statut"], "autorisee")
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "quarantaine")
        self.assertEqual(self.ok("sources", statut="autorisee")["total"], 1)


class Dedoublonnage(Monde):
    def test_le_meme_texte_d_une_autre_adresse_est_une_attestation_pas_une_fiche(self):
        a = self.noter(source=URL_A)
        b = self.noter(source=URL_C, titre="Copie", corps="  " + TEXTE.upper() + "  ")          # casse et espaces ne changent pas l'empreinte
        self.assertEqual((b["action"], b["ref"]), ("doublon", a["ref"]))
        self.assertEqual(self.ok("etagere")["total"], 1)
        f = self.ok("fiche", ref=a["ref"])
        self.assertEqual(len(f["attestations"]), 2)
        self.assertEqual(f["etat"], "quarantaine")                       # même domaine : une seule source concordante

    def test_deux_domaines_qui_concordent_verifient_la_fiche_sans_utilisateur(self):
        a = self.noter(source=URL_A)
        b = self.noter(source=URL_B, titre="Offres")
        self.assertEqual((b["action"], b["auto_verifie"], b["concordance"], b["etat"]), ("doublon", True, 2, "verifie"))
        f = self.ok("fiche", ref=a["ref"])
        self.assertEqual((f["etat"], f["verifie_par"]), ("verifie", "concordance"))
        self.assertEqual(self.ids(self.chercher()), [a["ref"]])

    def test_defaire_une_concordance_remet_la_quarantaine(self):
        a = self.noter(source=URL_A)
        b = self.noter(source=URL_B)
        self.n.catalogue.get("bibliotheque.noter").defaire(self.ctx, b)
        f = self.ok("fiche", ref=a["ref"])
        self.assertEqual((f["etat"], len(f["attestations"])), ("quarantaine", 1))

    def test_relire_a_l_identique_n_ajoute_rien(self):
        a = self.noter()
        self.vivre(3)
        b = self.noter()
        self.assertEqual((b["action"], b["ref"]), ("rafraichi", a["ref"]))
        self.assertEqual(self.ok("etagere")["total"], 1)
        self.assertEqual(self.ok("fiche", ref=a["ref"])["version"], 1)

    def test_les_passages_gardent_leur_position(self):
        long_ = "\n\n".join("Paragraphe numéro %d : %s" % (i, "mot " * 120) for i in range(6))
        r = self.noter(corps=long_)
        f = self.ok("fiche", ref=r["ref"])
        self.assertGreater(len(f["passages"]), 2)
        self.assertEqual([p["position"] for p in f["passages"]], list(range(len(f["passages"]))))
        self.assertTrue(f["passages"][0]["texte"].startswith("Paragraphe numéro 0"))

    def test_defaire_une_version_rend_l_ancien_texte(self):
        r = self.noter()
        v2 = self.noter(corps="Un tout autre texte sur les offres de téléphonie mobile.")
        self.n.catalogue.get("bibliotheque.noter").defaire(self.ctx, v2)
        f = self.ok("fiche", ref=r["ref"])
        self.assertEqual((f["version"], f["corps"], f["versions"]), (1, TEXTE, []))
        self.assertEqual(self.ids(self.chercher(etats=["quarantaine"])), [r["ref"]])
        self.coherent()


class Cloisonnement(Monde):
    def test_une_societe_ne_voit_jamais_les_fiches_d_une_autre(self):
        a = self.noter()
        self.ok("verifier", ref=a["ref"])
        self.assertEqual(self.chercher(compte=LEO)["resultats"], [])
        self.assertEqual(self.ok("etagere", compte=LEO)["total"], 0)
        self.assertEqual(self.ok("sources", compte=LEO)["total"], 0)
        for cap, kw in (("fiche", {}), ("verifier", {}), ("retirer", {}), ("bloquer", {"motif": "x"})):
            self.assertIn("introuvable", self.refuse(cap, compte=LEO, ref=a["ref"], **kw)["erreur"], cap)
        self.assertEqual(self.ok("fiche", ref=a["ref"])["etat"], "verifie")

    def test_le_meme_texte_vit_a_part_dans_chaque_societe(self):
        a = self.noter()
        self.n.reglages.poser("bibliotheque.compte_amizo", AMIZO_AUTRE, "")
        b = self.noter(compte=AMIZO_AUTRE)
        self.assertEqual(b["action"], "cree")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.ok("etagere", compte=LEO)["total"], 1)
        self.assertEqual(self.ok("etagere", compte=BEA)["total"], 1)

    def test_une_source_bloquee_chez_l_une_ne_l_est_pas_chez_l_autre(self):
        self.noter()
        self.ok("bloquer", source="exemple-a.test", motif="x")
        self.n.reglages.poser("bibliotheque.compte_amizo", AMIZO_AUTRE, "")
        self.assertEqual(self.noter(compte=AMIZO_AUTRE)["action"], "cree")


class Index(Monde):
    def test_un_seul_declencheur_par_evenement_sur_les_passages(self):
        c = sqlite3.connect(self.db.chemin)
        try:
            lignes = c.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='passages'").fetchall()
        finally:
            c.close()
        evenements = []
        for nom, sql in lignes:
            mots = sql.upper().split()
            evenements.append(next(m for m in mots if m in ("INSERT", "UPDATE", "DELETE")))
        self.assertEqual(sorted(evenements), ["DELETE", "INSERT", "UPDATE"], lignes)
        self.assertEqual(len(set(evenements)), len(evenements))

    def test_l_index_reste_coherent_apres_chaque_geste(self):
        a = self.noter()
        self.coherent()
        self.noter(corps="Un texte entièrement neuf sur les routeurs, la fibre et le wifi.")
        self.coherent()
        self.noter(source=URL_B, titre="Autre", corps="Les tarifs du gaz de ville évoluent chaque trimestre.")
        self.coherent()
        c = sqlite3.connect(self.db.chemin)
        try:
            c.execute("UPDATE passages SET texte = texte || ' et le cuivre' WHERE fiche_id=%d" % a["id"])      # une mise à jour directe : le déclencheur d'UPDATE seul travaille
            c.commit()
        finally:
            c.close()
        self.coherent()
        self.assertEqual(self.ids(self.chercher("cuivre", etats=["quarantaine"])), [a["ref"]])
        self.ok("retirer", ref=a["ref"])
        self.coherent()
        self.assertEqual(self.chercher("cuivre", etats=["quarantaine"])["resultats"], [])

    def test_la_recherche_ignore_accents_et_operateurs(self):
        r = self.noter(etagere="interne", source="rh:accueil.md", titre="Accueil", corps="La cérémonie d'accueil des nouveaux arrivants a lieu le lundi.")
        self.assertEqual(self.ids(self.chercher("ceremonie")), [r["ref"]])
        self.assertEqual(self.ids(self.chercher('accueil" OR NOT (')), [r["ref"]])
        self.assertIn("question", self.refuse("chercher", q="   ")["erreur"])

    def test_le_classement_prefere_la_fraicheur_et_la_confiance(self):
        vieux = self.noter(etagere="interne", source="a:vieux.md", titre="Vieux", corps="Procédure de sauvegarde des serveurs : procédure ancienne détaillée alpha.")
        self.vivre(60)
        neuf = self.noter(etagere="interne", source="a:neuf.md", titre="Neuf", corps="Procédure de sauvegarde des serveurs : procédure ancienne détaillée bravo.")
        r = self.chercher("procédure sauvegarde serveurs")
        self.assertEqual(self.ids(r)[0], neuf["ref"])
        self.assertGreater(r["resultats"][0]["fraicheur"], r["resultats"][1]["fraicheur"])
        ext = self.noter(source=URL_A, titre="Ext", corps="Procédure de sauvegarde des serveurs : procédure ancienne détaillée charlie.")
        self.ok("verifier", ref=ext["ref"])
        classe = {x["ref"]: x for x in self.chercher("procédure sauvegarde serveurs")["resultats"]}
        self.assertGreater(classe[neuf["ref"]]["confiance"], classe[ext["ref"]]["confiance"])
        self.assertIn(vieux["ref"], classe)

    def test_le_modele_des_vecteurs_est_ecrit_et_rien_n_est_calcule_tant_qu_il_n_est_pas_pret(self):
        c = sqlite3.connect(self.db.chemin)
        try:
            self.assertEqual(c.execute("SELECT valeur FROM meta WHERE cle='modele_vecteurs'").fetchone()[0], "intfloat/multilingual-e5-large")
        finally:
            c.close()
        self.noter()
        e = self.ok("etagere")["index"]
        self.assertEqual((e["recherche"], e["vecteurs"]["actif"], e["vecteurs"]["calcules"], e["vecteurs"]["pret"]), ("plein_texte", False, 0, False))
        rattraper = self.glob["brancher"].rattraper_vecteurs
        self.assertEqual(rattraper(), 0)                                      # pas de fournisseur : rien

        class Fournisseur:
            nom, prete = "intfloat/multilingual-e5-large", False

            def pret(self):
                return self.prete

            def encoder(self, textes):
                return [[0.1, 0.2, 0.3] for _ in textes]
        f = Fournisseur()
        self.glob["brancher_vecteurs"](f)
        self.addCleanup(lambda: self.glob["brancher_vecteurs"](None))
        self.assertEqual(rattraper(), 0)                                      # le modèle n'est pas prêt : rien
        f.prete = True
        self.assertEqual(rattraper(), 1)
        self.assertEqual(self.ok("etagere")["index"]["vecteurs"]["calcules"], 1)
        self.assertEqual(rattraper(), 0)                                      # rien à rattraper
        self.noter(corps="Un texte entièrement neuf, sans rapport.")          # la nouvelle version efface les vecteurs de l'ancienne
        self.assertEqual(self.ok("etagere")["index"]["vecteurs"]["calcules"], 0)
        self.assertEqual(rattraper(), 1)
        self.coherent()


class EcritureReservee(Monde):
    CAPACITES_ECRITURE = ("noter", "verifier", "bloquer", "retirer")

    def test_toute_capacite_nomme_un_droit_et_aucune_ne_lit_un_bureau(self):
        m = self.n.executeur.contextes["bibliotheque"].manifeste
        for c in m.capacites:
            self.assertTrue(c.droit, c.id)
        self.assertFalse(m.permissions.espace_utilisateur)
        self.assertFalse(m.permissions.stockage_lecture)
        self.assertFalse(m.permissions.lectures)

    def test_la_seule_ecriture_de_contenu_est_noter_et_elle_est_pour_un_agent(self):
        m = self.n.executeur.contextes["bibliotheque"].manifeste
        ecrivent = {c.id: c for c in m.capacites if c.ecrit}
        self.assertEqual(sorted(ecrivent), sorted(self.CAPACITES_ECRITURE))
        self.assertEqual(ecrivent["noter"].qui, ("agent",))
        for cid in ("verifier", "bloquer", "retirer"):
            self.assertEqual(sorted(ecrivent[cid].qui), ["compte", "humain"], cid)
            self.assertEqual(ecrivent[cid].droit, "bibliotheque.verifier")

    def test_aucun_acteur_autre_qu_amizo_n_ecrit(self):
        """Échoue si une capacité d'écriture peut être jouée par un acteur ou un compte qui n'est pas celui d'Amizo."""
        r = self.noter()
        args = {"noter": dict(etagere="externe", source="https://autre.test/p", titre="t", corps="un texte qui ne doit jamais entrer"),
                "verifier": dict(ref=r["ref"]), "bloquer": dict(ref=r["ref"], motif="x"), "retirer": dict(ref=r["ref"])}
        for acteur in ACTEURS:
            for compte in (BEA, LEO, AMIZO_AUTRE, AMIZO):
                if acteur == "agent" and compte == AMIZO:
                    continue
                res = self.ex("noter", compte=compte, acteur=acteur, **args["noter"])
                self.assertNotEqual(res["statut"], "faite", (acteur, compte, res))
        self.assertEqual(self.ok("etagere")["total"], 1)
        for cap in ("verifier", "bloquer", "retirer"):
            for acteur in ("cassandra", "itare", "agent", "anonyme"):
                for compte in (BEA, AMIZO):
                    res = self.ex(cap, compte=compte, acteur=acteur, **args[cap])
                    self.assertEqual(res["statut"], "refuse", (cap, acteur, compte, res))
        self.assertEqual(self.ok("fiche", ref=r["ref"])["etat"], "quarantaine")

    def test_sans_compte_amizo_designe_personne_n_ecrit(self):
        self.n.reglages.poser("bibliotheque.compte_amizo", "", "")
        res = self.ex("noter", compte=AMIZO, acteur="agent", etagere="externe", source=URL_A, titre="t", corps=TEXTE)
        self.assertEqual(res["statut"], "echec")
        self.assertIn("seul Amizo", res["erreur"])

    def test_l_agent_amizo_sans_le_droit_noter_est_refuse(self):
        self.n.droits.regler("compte", AMIZO, "bibliotheque.noter", "refuse")
        res = self.ex("noter", compte=AMIZO, acteur="agent", etagere="externe", source=URL_A, titre="t", corps=TEXTE)
        self.assertEqual(res["statut"], "refuse")

    def test_un_utilisateur_sans_le_droit_verifier_est_refuse(self):
        r = self.noter()
        self.n.identite.creer("tom@x.fr", MDP)                                  # ni administrateur ni titulaire du droit
        self.assertEqual(self.ex("verifier", compte="tom@x.fr", ref=r["ref"])["statut"], "refuse")
        self.n.droits.regler("compte", "tom@x.fr", "bibliotheque.verifier", "accorde")
        self.assertEqual(self.ex("verifier", compte="tom@x.fr", ref=r["ref"])["statut"], "faite")

    def test_les_champs_sont_valides(self):
        for kw, mot in ((dict(source="ftp://x.test/a"), "http"), (dict(source=""), "source"), (dict(titre=""), "titre"), (dict(corps=""), "texte"),
                        (dict(etagere="autre"), "étagère"), (dict(etagere="interne", source="https://x.test/a"), "espace")):
            base = dict(etagere="externe", source=URL_A, titre="t", corps=TEXTE)
            base.update(kw)
            self.n.catalogue.regler_palier("bibliotheque.noter", "auto")      # deux échecs de suite font redescendre le palier : on le remet
            res = self.ex("noter", compte=AMIZO, acteur="agent", **base)
            self.assertEqual(res["statut"], "echec", kw)
            self.assertIn(mot, res["erreur"], kw)

    def test_le_contenu_lu_au_dehors_est_marque_externe(self):
        m = self.n.executeur.contextes["bibliotheque"].manifeste
        self.assertTrue(all(c.externe for c in m.capacites if c.id in ("chercher", "fiche")))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Etats, Dedoublonnage, Cloisonnement, Index, EcritureReservee
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
