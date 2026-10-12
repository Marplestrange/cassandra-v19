"""Bancs du module notes."""
import base64
import io
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau.bus import TOUT                 # noqa: E402

BEA, LEO = "bea@x.fr", "leo@x.fr"
J = lambda n: (datetime.now() + timedelta(days=n)).strftime("%Y-%m-%d")


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "notes", mods / "notes", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("notes")["ok"])
        self.ctx = self.n.executeur.contextes["notes"]
        self.db = self.ctx.stockage
        self.glob = self.n.catalogue.get("notes.creer").faire.__globals__
        self.taches = {}
        self.ctx.executer_lecture = self.lecture

    def lecture(self, cap, **a):
        if cap == "taches.fiche":
            t = self.taches.get(int(a["id"]))
            if t is None:
                raise ValueError("tâche introuvable")
            return {"tache": t}
        if cap == "projets.equipe":
            if int(a["id"]) == 7:
                return {"projet": "Refonte", "mon_role": "auteur"}
            raise ValueError("projet introuvable")
        raise ValueError("lecture inconnue " + cap)

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("notes." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "echec", r)
        return r["erreur"]

    def retour(self, cap, res):
        self.n.catalogue.get("notes." + cap).defaire(self.ctx, res)

    def note(self, titre="Idée", corps="", compte=BEA, **kw):
        return self.ok("creer", titre=titre, corps=corps, compte=compte, **kw)["ref"]

    def fiche(self, ref, compte=BEA):
        return self.ok("fiche", ref=ref, compte=compte)

    def corps(self, ref, compte=BEA):
        return self.fiche(ref, compte)["corps"]

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]


class Cycle(Monde):
    def test_resoudre_et_cibles_pour_les_ecrans_qui_renvoient(self):
        a = self.ok("creer", titre="Alpha", corps="rien")
        self.ok("creer", titre="Beta", corps="voir [[Alpha]] et [[N-0099]]")
        r = self.ok("resoudre", texte="a [[Alpha]] b [[Inconnue]]")["liens"]
        self.assertEqual([(x["ref"], x["existe"]) for x in r], [("Alpha", True), ("Inconnue", False)])
        lots = self.ok("resoudre", textes=["[[Alpha]]", "rien", "[[N-0099]]"])["lots"]
        self.assertEqual([len(x) for x in lots], [1, 0, 1])
        c = self.ok("cibles", q="alp")
        self.assertEqual([x["ecriture"] for x in c["cibles"]], ["[[note:%s]]" % a["ref"]])
        tout = self.ok("cibles")
        self.assertEqual(tout["total"], 2)                     # sans module des projets ni des tâches : une nature absente ne vide pas les autres
        self.assertEqual(self.ok("cibles", q="beta", compte=BEA)["total"], 1)

    def test_creer_numerote_prouve_et_se_defait_sans_reutiliser_le_numero(self):
        r = self.ex("creer", titre="Première", corps="# Titre\ntexte", etiquettes=["a", "b", "a"], projet="Refonte")
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(r["resultat"]["ref"])
        self.assertEqual((f["id"], f["titre"], f["etiquettes"], f["projet"], f["dossier"]), ("N-0001", "Première", ["a", "b"], "Refonte", "Refonte"))
        self.assertEqual(f["activite"][-1]["quoi"], "Créée")
        self.assertEqual(len(self.evts("note.creee")), 1)
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.retour("creer", r["resultat"])
        self.assertEqual(self.ok("lister")["notes"], [])
        self.assertEqual(self.note("Seconde"), "N-0002")

    def test_les_refus_de_creation(self):
        for args in (dict(titre="  "), dict(titre="x", etat="fini"), dict(titre="x", dossier="Inconnu"), dict(titre="x", relire="demain"), dict(titre="x", relire="2026-13-40"),
                     dict(titre="x", rattache=["blabla"]), dict(titre="x", rattache=["inconnu:12"]), dict(titre="x", dossier="a/b/c")):
            self.assertEqual(self.ex("creer", **args)["statut"], "echec", args)
        for compte in ("", "cassandra", "itare"):
            self.assertEqual(self.ex("creer", titre="x", compte=compte)["statut"], "echec")

    def test_ecrire_est_un_patch_qui_laisse_la_version_d_avant(self):
        ref = self.note("Plan", "version un")
        self.ok("ecrire", ref=ref, corps="version deux")
        self.ok("ecrire", ref=ref, etiquettes=["x"])            # métadonnée seule : pas de version
        f = self.fiche(ref)
        self.assertEqual((f["corps"], f["etiquettes"], len(f["versions"])), ("version deux", ["x"], 1))
        v = self.ok("version_lire", ref=ref, version=f["versions"][0]["id"])
        self.assertEqual(v["contenu"], "version un")
        self.assertEqual(self.ex("ecrire", ref=ref)["statut"], "echec")

    def test_le_retour_d_une_ecriture_remet_la_note_et_retire_sa_version(self):
        ref = self.note("Plan", "un", etiquettes=["a"])
        r = self.ex("ecrire", ref=ref, corps="deux", titre="Autre", etiquettes=["b"], epinglee=True, etat="stable", relire=J(5))
        self.assertEqual(r["statut"], "faite", r)
        self.retour("ecrire", r["resultat"])
        f = self.fiche(ref)
        self.assertEqual((f["corps"], f["titre"], f["etiquettes"], f["epinglee"], f["etat"], f["relire"], len(f["versions"])), ("un", "Plan", ["a"], False, "brouillon", "", 0))

    def test_revenir_est_lui_meme_versionne_et_se_defait(self):
        ref = self.note("Plan", "un")
        self.ok("ecrire", ref=ref, corps="deux")
        vid = self.fiche(ref)["versions"][0]["id"]
        r = self.ex("revenir", ref=ref, version=vid)
        self.assertEqual(self.corps(ref), "un")
        self.assertEqual(len(self.fiche(ref)["versions"]), 2)    # « deux » est devenu une version à son tour
        self.retour("revenir", r["resultat"])
        self.assertEqual((self.corps(ref), len(self.fiche(ref)["versions"])), ("deux", 1))
        self.assertEqual(self.ex("revenir", ref=ref, version=99999)["statut"], "echec")

    def test_vingt_versions_au_plus(self):
        ref = self.note("Long", "0")
        for i in range(1, 26):
            self.ok("ecrire", ref=ref, corps=str(i))
        self.assertEqual(len(self.fiche(ref)["versions"]), 20)

    def test_une_note_se_trouve_par_numero_ou_par_titre_et_le_titre_change_sans_casser_le_renvoi(self):
        a = self.note("Cible", "x")
        b = self.note("Source", "voir [[%s]] et [[Cible]]" % a)
        self.ok("ecrire", ref=a, titre="Renommée")
        self.assertEqual(self.fiche("renommée")["id"], a)
        self.assertEqual(self.fiche("n-1")["id"], a)
        self.assertEqual([x["id"] for x in self.fiche(a)["entrants"]], [b])
        liens = self.fiche(b)["liens"]
        self.assertEqual([(l["existe"], l["titre"]) for l in liens], [(True, "Renommée"), (False, "Cible")])       # le renvoi par TITRE casse, celui par numéro tient

    def test_une_note_d_un_compte_n_est_pas_a_un_autre_ni_a_l_administrateur(self):
        ref = self.note("Secret", "mot de passe")
        self.n.droits.regler_admin(LEO, True)                                   # administrer n'est pas voir
        for cap, args in (("fiche", {}), ("ecrire", dict(corps="x")), ("supprimer", {}), ("exporter", {}), ("versions", {}), ("partage_creer", {}), ("case_basculer", dict(ligne=0))):
            self.assertEqual(self.ex(cap, ref=ref, compte=LEO, **args)["statut"], "echec", cap)
        self.assertEqual(self.ok("lister", compte=LEO)["notes"], [])
        self.assertEqual(self.ex("fiche", ref="Secret", compte=LEO)["statut"], "echec")

    def test_on_ne_cherche_pas_un_numero_forge_dans_le_compte_d_un_autre(self):
        self.note("A moi", compte=LEO)
        self.assertEqual(self.ex("fiche", ref="N-0001")["statut"], "echec")
        self.assertEqual(self.note("Chez Bea"), "N-0001")                    # numérotation par compte


class Liens(Monde):
    def test_renvois_entrants_morts_ancres_et_inclusions(self):
        a = self.note("Décision", "On part là. ^decision")
        b = self.note("Compte rendu", "Voir [[%s#^decision]], ![[%s]] et [[N-0099]]." % (a, a))
        f = self.fiche(b)
        self.assertEqual([(l["existe"], l["inclus"]) for l in f["liens"]], [(True, False), (True, True), (False, False)])
        self.assertEqual(self.fiche(a)["ancres"][0]["ancre"], "decision")
        self.assertEqual([x["id"] for x in self.fiche(a)["entrants"]], [b])
        morts = [s for s in f["sante"] if s["cle"] == "liens"][0]
        self.assertEqual((morts["niveau"], "N-0099" in morts["detail"]), ("avoir", True))
        inv = self.ok("liens")
        self.assertEqual((inv["total"], inv["morts"]), (3, 1))

    def test_les_cibles_hors_des_notes_sont_verifiees_aupres_de_leur_module(self):
        self.taches[5] = {"texte": "Appeler", "statut": "todo"}
        r = self.note("Mixte", "[[projet:7]] [[tache:5]] [[projet:8]] [[contact:Zoé]]")
        liens = {(l["kind"], l["ref"]): (l["existe"], l["titre"]) for l in self.fiche(r)["liens"]}
        self.assertEqual(liens[("projet", "7")], (True, "Refonte"))
        self.assertEqual(liens[("tache", "5")], (True, "Appeler"))
        self.assertEqual(liens[("projet", "8")][0], False)
        self.assertIsNone(liens[("contact", "Zoé")][0])                      # non vérifiable ici : jamais déclaré « mort »

    def test_de_rend_le_sens_inverse_et_normalise_les_domaines(self):
        self.note("Site", "relancer [[site:Proche.FR]]")
        self.note("Autre", "voir [[domain:https://www.proche.fr/accueil]]")
        self.note("Ailleurs", "voir [[site:autre.fr]]")
        r = self.ok("de", kind="domain", ref="www.PROCHE.fr")
        self.assertEqual(sorted(x["titre"] for x in r["notes"]), ["Autre", "Site"])
        self.assertEqual(self.ex("de", kind="", ref="x")["statut"], "echec")

    def test_mentions_non_liees_proposees_jamais_ecrites(self):
        a = self.note("Proche", "x")
        self.note("Web", "x")
        b = self.note("Journal", "Rappeler Proche demain, et web aussi.")
        m = self.ok("mentions", ref=b)["mentions"]
        self.assertEqual([x["mot"] for x in m], ["Proche"])                  # « Web » est trop court pour désigner quelqu'un
        self.assertEqual(m[0]["ecriture"], "[[%s]]" % a)
        self.assertEqual(self.corps(b), "Rappeler Proche demain, et web aussi.")
        self.ok("ecrire", ref=b, corps="Rappeler [[%s]] demain." % a)
        self.assertEqual(self.ok("mentions", ref=b)["mentions"], [])         # ce qui est lié n'est plus une mention


class Corbeille(Monde):
    def test_supprimer_restaurer_et_les_retours(self):
        ref = self.note("À jeter", "x")
        r = self.ex("supprimer", ref=ref)
        self.assertEqual(self.ok("lister")["notes"], [])
        self.assertEqual([x["id"] for x in self.ok("corbeille")["notes"]], [ref])
        self.assertEqual(self.ex("fiche", ref=ref)["statut"], "echec")
        self.retour("supprimer", r["resultat"])
        self.assertEqual(self.fiche(ref)["titre"], "À jeter")
        self.ok("supprimer", ref=ref)
        r2 = self.ex("restaurer", ref=ref)
        self.assertEqual(self.fiche(ref)["titre"], "À jeter")
        self.retour("restaurer", r2["resultat"])
        self.assertEqual(len(self.ok("corbeille")["notes"]), 1)
        self.assertEqual(self.ex("restaurer", ref="N-0042")["statut"], "echec")

    def test_vider_la_corbeille_efface_et_se_defait_avec_versions_et_numero_reserve(self):
        a, b = self.note("A", "un"), self.note("B", "deux")
        self.ok("ecrire", ref=a, corps="un bis")
        self.ok("supprimer", ref=a)
        r = self.ex("vider_corbeille")
        self.assertEqual((r["statut"], r["resultat"]["videes"]), ("faite", 1))
        self.assertEqual(self.ok("corbeille")["notes"], [])
        self.assertEqual(self.note("C"), "N-0003")                            # le numéro de A n'est jamais réattribué
        self.assertEqual(self.fiche(b)["titre"], "B")                         # la vivante n'est pas touchée
        self.retour("vider_corbeille", r["resultat"])
        self.ok("restaurer", ref=a)
        f = self.fiche(a)
        self.assertEqual((f["corps"], len(f["versions"])), ("un bis", 1))

    def test_la_corbeille_d_un_compte_ne_vide_pas_celle_d_un_autre(self):
        self.note("A"); self.ok("supprimer", ref="N-0001")
        self.note("L", compte=LEO); self.ok("supprimer", ref="N-0001", compte=LEO)
        self.ok("vider_corbeille")
        self.assertEqual(len(self.ok("corbeille", compte=LEO)["notes"]), 1)


class Fusion(Monde):
    def test_fusion_redirige_reecrit_les_renvois_et_se_defait(self):
        a, b = self.note("Alpha", "texte a", etiquettes=["x"]), self.note("Beta", "texte b", etiquettes=["x", "y"], projet="Refonte")
        c = self.note("Tiers", "vers [[%s]], ![[%s#^p]] et [[%s|alias]] mais pas [[N-0050]]" % (a, a, b))
        r = self.ex("fusionner", refs=[a, b], titre="Tout")
        self.assertEqual(r["statut"], "faite", r)
        f = r["resultat"]["ref"]
        fm = self.fiche(f)
        self.assertEqual((fm["etiquettes"], fm["projet"], fm["source"]), (["x", "y"], "Refonte", "fusion"))
        self.assertIn("# Alpha\n\ntexte a", fm["corps"])
        self.assertEqual(self.corps(c), "vers [[%s]], ![[%s#^p]] et [[%s|alias]] mais pas [[N-0050]]" % (f, f, f))
        self.assertEqual(self.fiche(a)["id"], f)                              # l'ancien numéro redirige vers la fusion
        self.assertEqual({x["id"] for x in self.ok("corbeille")["notes"]}, {a, b})
        self.assertEqual(len(self.fiche(c)["versions"]), 1)
        self.retour("fusionner", r["resultat"])
        self.assertEqual(self.fiche(a)["titre"], "Alpha")
        self.assertEqual(self.ok("corbeille")["notes"], [])
        self.assertIn("[[%s]]" % a, self.corps(c))
        self.assertEqual(len(self.fiche(c)["versions"]), 0)

    def test_les_refus_de_fusion(self):
        a = self.note("Alpha")
        for args in (dict(refs=[a], titre="x"), dict(refs=[a, a], titre="x"), dict(refs=[a, "N-0099"], titre="x")):
            self.assertEqual(self.ex("fusionner", **args)["statut"], "echec", args)
        b = self.note("Beta")
        self.assertEqual(self.ex("fusionner", refs=[a, b], titre=" ")["statut"], "echec")
        self.assertEqual(self.ex("fusionner", refs=[a, b], titre="x", compte=LEO)["statut"], "echec")


class Dossiers(Monde):
    def test_creer_ranger_renommer_supprimer_et_les_retours(self):
        r = self.ex("dossier_creer", chemin="Chantiers/2026")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual([d["chemin"] for d in self.ok("dossiers")["dossiers"]], ["Chantiers", "Chantiers/2026"])
        a = self.note("Plan", dossier="Chantiers/2026")
        self.ok("ecrire", ref=self.note("Libre"), dossier="Chantiers")
        d = {x["chemin"]: x["n"] for x in self.ok("dossiers")["dossiers"]}
        self.assertEqual(d, {"Chantiers": 2, "Chantiers/2026": 1})            # un dossier compte aussi ce qu'il y a dessous
        rn = self.ex("dossier_renommer", chemin="Chantiers", nom="Travaux")
        self.assertEqual(self.fiche(a)["dossier"], "Travaux/2026")
        self.retour("dossier_renommer", rn["resultat"])
        self.assertEqual(self.fiche(a)["dossier"], "Chantiers/2026")
        rs = self.ex("dossier_supprimer", chemin="Chantiers")
        self.assertEqual((rs["statut"], rs["resultat"]["remontees"]), ("faite", 2))
        self.assertEqual(self.fiche(a)["dossier"], "2026")                    # rien ne disparaît : ça remonte d'un cran
        self.assertEqual(self.fiche("Libre")["dossier"], "")
        self.retour("dossier_supprimer", rs["resultat"])
        self.assertEqual((self.fiche(a)["dossier"], self.fiche("Libre")["dossier"]), ("Chantiers/2026", "Chantiers"))
        self.retour("dossier_creer", r["resultat"])                          # le dossier porte des notes : il reste
        self.assertEqual(len(self.ok("dossiers")["dossiers"]), 2)

    def test_les_refus_de_dossier(self):
        for chemin in ("", "a/b/c", "../x", ".versions", "/abs", "a/.b", "x" * 65):
            self.assertEqual(self.ex("dossier_creer", chemin=chemin)["statut"], "echec", chemin)
        self.ok("dossier_creer", chemin="A")
        self.assertEqual(self.ex("dossier_creer", chemin="A")["statut"], "echec")
        self.ok("dossier_creer", chemin="B")
        self.assertEqual(self.ex("dossier_renommer", chemin="A", nom="B")["statut"], "echec")
        self.assertEqual(self.ex("dossier_renommer", chemin="A", nom="x/y")["statut"], "echec")
        self.assertEqual(self.ex("dossier_renommer", chemin="Z", nom="Y")["statut"], "echec")
        self.assertEqual(self.ex("dossier_supprimer", chemin="Z")["statut"], "echec")
        self.assertEqual(self.ex("ecrire", ref=self.note("x"), dossier="Z")["statut"], "echec")

    def test_les_dossiers_sont_a_chaque_compte(self):
        self.ok("dossier_creer", chemin="Privé")
        self.assertEqual(self.ok("dossiers", compte=LEO)["dossiers"], [])
        self.assertEqual(self.ex("creer", titre="x", dossier="Privé", compte=LEO)["statut"], "echec")

    def test_un_projet_range_la_note_dans_le_dossier_de_son_nom_sans_toucher_un_dossier_choisi(self):
        a = self.note("Suivi", projet="Refonte")
        self.assertEqual(self.fiche(a)["dossier"], "Refonte")
        self.ok("ecrire", ref=a, projet="")
        self.assertEqual(self.fiche(a)["dossier"], "")                        # elle était dans le dossier de son ancien projet : elle revient
        self.ok("dossier_creer", chemin="Mien")
        b = self.note("Choisie", dossier="Mien")
        self.ok("ecrire", ref=b, projet="Refonte")
        self.assertEqual(self.fiche(b)["dossier"], "Refonte")                 # un projet donné à une note rangée la suit
        self.ok("ecrire", ref=b, dossier="Mien")
        self.ok("ecrire", ref=b, projet="")
        self.assertEqual(self.fiche(b)["dossier"], "Mien")                    # le dossier choisi n'est pas touché


class Listes(Monde):
    def setUp(self):
        super().setUp()
        self.a = self.note("Procédure SSL", "renouveler le certificat", etiquettes=["procedure", "infra"], projet="Refonte")
        self.b = self.note("Idées", "- [ ] une\n- [x] deux", etiquettes=["vrac"])
        self.c = self.note("Orpheline", "rien")
        self.ok("ecrire", ref=self.b, corps="- [ ] une\n- [x] deux\nvoir [[%s]]" % self.a, epinglee=True)

    def titres(self, **kw):
        return [n["titre"] for n in self.ok("lister", **kw)["notes"]]

    def test_recherche_et_operateurs(self):
        self.assertEqual(self.titres(q="certificat"), ["Procédure SSL"])
        self.assertEqual(self.titres(q="#infra"), ["Procédure SSL"])
        self.assertEqual(self.titres(q="projet:refonte"), ["Procédure SSL"])
        self.assertEqual(self.titres(q="chantier:refonte"), ["Procédure SSL"])
        self.assertEqual(self.titres(q="lié:%s" % self.a), ["Idées"])
        self.assertEqual(self.titres(q="introuvable"), [])

    def test_filtres_groupes_et_tris(self):
        self.assertEqual(self.titres(filtre="epinglees"), ["Idées"])
        self.assertEqual(self.titres(filtre="ouvertes"), ["Idées"])
        self.assertEqual(self.titres(filtre="projet"), ["Procédure SSL"])
        self.assertEqual(self.titres(filtre="orphelines"), ["Orpheline"])
        self.assertEqual(self.titres(groupe="sans"), ["Orpheline"])
        self.assertEqual(self.titres(groupe="pj:Refonte"), ["Procédure SSL"])
        self.assertEqual(self.titres(groupe="et:vrac"), ["Idées"])
        self.assertEqual(self.titres(etiquette="infra"), ["Procédure SSL"])
        self.assertEqual(self.titres(tri="titre"), ["Idées", "Orpheline", "Procédure SSL"])
        self.assertEqual(self.titres()[0], "Idées")                           # l'épinglée d'abord
        r = self.ok("lister")
        self.assertEqual((r["total"], r["groupes"]["sans"], r["etiquettes"][0][1]), (3, 1, 1))

    def test_le_resume_dit_etat_cases_et_liens_sans_ouvrir_la_fiche(self):
        n = {x["titre"]: x for x in self.ok("lister")["notes"]}
        self.assertEqual((n["Idées"]["etat"], n["Idées"]["ouvertes"], n["Idées"]["sortants"]), ("cours", 1, 1))
        self.assertEqual((n["Procédure SSL"]["entrants"], n["Orpheline"]["etat"]), (1, "brouillon"))

    def test_le_filtre_par_dossier(self):
        self.assertEqual(self.titres(dossier="Refonte"), ["Procédure SSL"])
        self.assertEqual(self.titres(dossier=""), ["Idées", "Orpheline"])

    def test_menage_propose_orphelines_et_doublons_sans_rien_faire(self):
        self.note("Procédure SSL bis", "renouveler le certificat", etiquettes=["procedure"])
        m = self.ok("menage")
        self.assertTrue(m["doublons"])
        self.assertIn("Orpheline", [x["titre"] for x in m["a_ranger"]])
        self.assertEqual(len(self.ok("lister")["notes"]), 4)


class Etat(Monde):
    def test_l_etat_se_deduit_et_se_declare_la_relecture_est_une_date(self):
        a = self.note("Liste", "- [ ] à faire")
        self.assertEqual(self.fiche(a)["etat"], "cours")
        self.ok("ecrire", ref=a, etat="stable")
        self.assertEqual(self.fiche(a)["etat_n"], "Stabilisée")
        self.ok("ecrire", ref=a, etat="")
        self.assertEqual(self.fiche(a)["etat"], "cours")
        for mauvais in ("demain", "2026-02-30"):
            self.assertEqual(self.ex("ecrire", ref=a, relire=mauvais)["statut"], "echec", mauvais)
        self.ok("ecrire", ref=a, relire=J(3))
        self.assertEqual([s["niveau"] for s in self.fiche(a)["sante"] if s["cle"] == "relire"], ["info"])
        self.ok("ecrire", ref=a, relire=J(-2))
        self.assertEqual([s["niveau"] for s in self.fiche(a)["sante"] if s["cle"] == "relire"], ["avoir"])
        self.assertEqual(self.fiche(a)["activite"][0]["quoi"], "Relecture prévue")

    def test_le_detecteur_ne_leve_que_les_relectures_echues_du_bon_compte(self):
        a = self.note("Échue", relire=J(-1))
        self.note("Future", relire=J(9))
        arch = self.note("Archivée", relire=J(-5), etat="archive")
        self.note("Chez Léo", relire=J(-1), compte=LEO)
        self.n.tick()
        o = [e for e in self.evts("constat.ouvert") if "Relecture due" in e["donnees"]["titre"]]
        self.assertEqual(sorted((e["compte"], e["donnees"]["titre"]) for e in o), [(BEA, "Relecture due : Échue"), (LEO, "Relecture due : Chez Léo")])

    def test_rattachements_valides_vivants_et_journalises(self):
        a = self.note("Dossier client")
        self.taches[5] = {"texte": "Facturer", "statut": "todo"}
        self.ok("ecrire", ref=a, rattache=["projet:7", "tache:5", "projet:9", "domain:proche.fr", "projet:7"])
        r = {x["brut"]: (x["vivant"], x["titre"]) for x in self.fiche(a)["rattache"]}
        self.assertEqual(r["projet:7"], (True, "Refonte"))
        self.assertEqual(r["tache:5"], (True, "Facturer"))
        self.assertEqual(r["projet:9"][0], False)
        self.assertIsNone(r["domain:proche.fr"][0])
        self.ok("ecrire", ref=a, rattache=["projet:7"])
        quoi = [x["quoi"] + ":" + x["det"] for x in self.fiche(a)["activite"]]
        self.assertIn("Détachée:domain:proche.fr", quoi)
        self.assertIn("Rattachée:tache:5", quoi)

    def test_les_signaux_se_taisent_sur_un_brouillon_et_parlent_sur_une_note_etoffee(self):
        court = self.note("Court", "trois lignes")
        self.assertEqual(self.fiche(court)["sante"], [])
        long = self.note("Long", "mot " * 150)
        s = {x["cle"]: x for x in self.fiche(long)["sante"]}
        self.assertEqual(s["orphelin"]["niveau"], "avoir")
        self.assertNotIn("titres", s)
        longue = self.note("Fleuve", "mot " * 700)
        self.assertIn("titres", {x["cle"] for x in self.fiche(longue)["sante"]})


class Cases(Monde):
    def test_les_cases_ont_leur_numero_de_ligne_et_se_basculent_une_a_une(self):
        a = self.note("Courses", "Liste\n- [ ] lait\n- [ ] lait\n  * [x] pain")
        self.assertEqual([(c["ligne"], c["faite"], c["texte"]) for c in self.fiche(a)["taches"]], [(1, False, "lait"), (2, False, "lait"), (3, True, "pain")])
        r = self.ex("case_basculer", ref=a, ligne=2)
        self.assertEqual(self.corps(a), "Liste\n- [ ] lait\n- [x] lait\n  * [x] pain")       # CETTE ligne, pas la ressemblante
        self.retour("case_basculer", r["resultat"])
        self.assertEqual(self.corps(a), "Liste\n- [ ] lait\n- [ ] lait\n  * [x] pain")
        self.assertEqual(len(self.fiche(a)["versions"]), 0)
        self.ok("case_basculer", ref=a, ligne=3)
        self.assertIn("  * [ ] pain", self.corps(a))
        for ligne in (0, 9, -1, "x"):
            self.assertEqual(self.ex("case_basculer", ref=a, ligne=ligne)["statut"], "echec", ligne)

    def test_cases_de_toutes_les_notes(self):
        self.note("A", "- [ ] un\n- [x] deux")
        self.note("B", "- [ ] trois")
        self.note("Z", "- [ ] chez Léo", compte=LEO)
        r = self.ok("cases")
        self.assertEqual((len(r["taches"]), r["ouvertes"]), (3, 2))
        self.assertEqual(len(self.ok("cases", ouvertes_seules=True)["taches"]), 2)

    def test_lier_a_une_tache_voir_les_desaccords_et_reprendre(self):
        a = self.note("Plan", "- [ ] appeler\n- [x] écrire\n- [ ] libre")
        self.taches.update({3: {"texte": "appeler", "statut": "fait"}, 4: {"texte": "écrire", "statut": "todo"}})
        rl = self.ex("case_lier", ref=a, ligne=0, tache_id=3)
        self.ok("case_lier", ref=a, ligne=1, tache_id=4)
        e = {c["ligne"]: c for c in self.ok("cases_etat", ref=a)["cases"]}
        self.assertEqual((e[0]["desaccord"], e[1]["desaccord"], e[2]["tache"]), (True, True, None))
        self.assertEqual(self.ok("cases", compte=BEA)["taches"][0]["tache_id"], 3)
        r = self.ex("cases_reprendre", ref=a)
        self.assertEqual(sorted(r["resultat"]["reprises"]), ["appeler", "écrire"])
        self.assertEqual(self.corps(a), "- [x] appeler\n- [ ] écrire\n- [ ] libre")
        self.assertFalse(any(c["desaccord"] for c in self.ok("cases_etat", ref=a)["cases"]))
        self.assertEqual(self.ok("cases_reprendre", ref=a)["reprises"], [])
        self.retour("cases_reprendre", r["resultat"])
        self.assertEqual(self.corps(a), "- [ ] appeler\n- [x] écrire\n- [ ] libre")
        self.retour("case_lier", rl["resultat"])
        self.assertIsNone(self.ok("cases_etat", ref=a)["cases"][0]["tache"])

    def test_une_case_qui_a_change_de_ligne_est_retrouvee_par_son_texte(self):
        a = self.note("Plan", "- [ ] appeler")
        self.taches[3] = {"texte": "appeler", "statut": "todo"}
        self.ok("case_lier", ref=a, ligne=0, tache_id=3)
        self.ok("ecrire", ref=a, corps="Intro\n\n- [ ] appeler")
        e = self.ok("cases_etat", ref=a)
        self.assertEqual((e["cases"][0]["ligne"], e["cases"][0]["tache"], e["orphelines"]), (2, 3, []))
        self.ok("ecrire", ref=a, corps="plus rien")
        self.assertEqual(self.ok("cases_etat", ref=a)["orphelines"][0]["tache"], 3)

    def test_les_refus_de_lien_et_le_delier(self):
        a = self.note("Plan", "- [ ] un\ntexte")
        self.taches[3] = {"texte": "un", "statut": "todo"}
        for args in (dict(ligne=1, tache_id=3), dict(ligne=0, tache_id=99), dict(ligne="x", tache_id=3)):
            self.assertEqual(self.ex("case_lier", ref=a, **args)["statut"], "echec", args)
        self.assertEqual(self.ex("case_delier", ref=a, ligne=0)["statut"], "echec")
        self.ok("case_lier", ref=a, ligne=0, tache_id=3)
        r = self.ex("case_delier", ref=a, ligne=0)
        self.assertIsNone(self.ok("cases_etat", ref=a)["cases"][0]["tache"])
        self.retour("case_delier", r["resultat"])
        self.assertEqual(self.ok("cases_etat", ref=a)["cases"][0]["tache"], 3)


class NoteDuJour(Monde):
    def test_creee_a_la_demande_une_seule_fois_et_le_retour_ne_retire_que_la_sienne(self):
        j = time.strftime("%Y-%m-%d")
        self.assertEqual(self.ok("jour"), {"existe": False, "jour": j})
        self.assertEqual(self.ok("lister")["notes"], [])                       # lire ne crée rien : pas de feuille blanche chaque matin
        r = self.ex("jour_ouvrir")
        self.assertEqual((r["resultat"]["cree"], self.ok("jour")["existe"]), (True, True))
        r2 = self.ex("jour_ouvrir")
        self.assertEqual((r2["resultat"]["cree"], r2["resultat"]["id"]), (False, r["resultat"]["id"]))
        self.retour("jour_ouvrir", r2["resultat"])
        self.assertTrue(self.ok("jour")["existe"])
        self.retour("jour_ouvrir", r["resultat"])
        self.assertFalse(self.ok("jour")["existe"])
        self.assertEqual(self.ex("jour_ouvrir", jour="hier")["statut"], "echec")
        self.assertEqual(self.ok("jour_ouvrir", jour="2026-01-02")["jour"], "2026-01-02")


class Export(Monde):
    def test_trois_formats_et_le_html_echappe_tout(self):
        a = self.note("Titre <script>alert(1)</script>", "# Grand\n**gras** `code` [[N-0002]]\n- item\n> cité\n<img src=x onerror=alert(2)>", etiquettes=["t"])
        md = self.ok("exporter", ref=a, format="md")
        self.assertTrue(md["contenu"].startswith("---\nid: N-0001\n"))
        self.assertEqual(md["mime"], "text/markdown")
        txt = self.ok("exporter", ref=a, format="txt")
        self.assertIn("GRAND", txt["contenu"])
        self.assertIn("gras", txt["contenu"])
        self.assertNotIn("**", txt["contenu"])
        h = self.ok("exporter", ref=a, format="html")["contenu"]
        self.assertNotIn("<script>", h)
        self.assertNotIn("<img", h)
        self.assertIn("&lt;img", h)
        self.assertIn("<strong>gras</strong>", h)
        self.assertEqual(self.ok("exporter", ref=a, format="pdf")["mime"], "text/markdown")

    def test_archive_garde_le_rangement_et_la_borne_se_dit(self):
        self.ok("dossier_creer", chemin="Doss")
        self.note("Une", "a", dossier="Doss")
        self.note("Une", "b")
        self.note("Deux", "c")
        z = self.ok("archive")
        noms = sorted(zipfile.ZipFile(io.BytesIO(base64.b64decode(z["contenu_b64"]))).namelist())
        self.assertEqual((z["notes"], noms), (3, ["Deux.md", "Doss/Une.md", "Une.md"]))
        self.assertEqual(self.ok("archive", portee="dossier", dossier="Doss")["notes"], 1)
        self.assertEqual(self.ok("archive", portee="selection", refs=["N-0003", "Deux", "N-0003"])["notes"], 1)
        self.assertEqual(self.ex("archive", portee="selection", refs=["N-0099"])["statut"], "echec")
        self.assertEqual(self.ex("archive", portee="dossier", dossier="../x")["statut"], "echec")
        self.glob["ZIP_NOTES"] = 2
        self.assertIn("2", self.echec("archive"))
        self.assertEqual(self.ex("archive", compte=LEO)["statut"], "echec")

    def test_importer_relit_l_en_tete_cree_des_notes_neuves_et_se_defait(self):
        self.note("Existante", "garde")
        fichiers = [{"chemin": "Vrac/Idée.md", "contenu": "---\nid: N-0077\ntitre: Importée\netiquettes: [a, b]\nprojet: Refonte\nrelire: 2026-05-01\nepinglee: true\nrattache: [projet:7, bidule]\n---\n\ncorps importé"},
                    {"nom": "brut.md", "contenu": "# Sans en-tête\ntexte"}, {"nom": "vide.md", "contenu": ""}, {"nom": "x", "contenu": "---\ntitre: Mauvais\netat: nimporte\n---\nx"}]
        r = self.ex("importer", fichiers=fichiers)
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual((len(res["creees"]), res["refus"]), (4, []))                # un fichier vide prend le nom du fichier pour titre ; un état inconnu est ignoré
        titres = {n["titre"]: n for n in self.ok("lister")["notes"]}
        self.assertIn("Importée", titres)
        i = self.fiche(titres["Importée"]["id"])
        self.assertNotEqual(i["id"], "N-0077")                                  # un numéro importé ne s'impose pas
        self.assertEqual((i["etiquettes"], i["projet"], i["epinglee"], i["relire"], i["source"], i["corps"]), (["a", "b"], "Refonte", True, "2026-05-01", "import", "corps importé"))
        self.assertEqual([x["brut"] for x in i["rattache"]], ["projet:7"])
        self.assertIn("Sans en-tête", titres)
        self.assertEqual(self.fiche("Existante")["corps"], "garde")
        self.retour("importer", res)
        self.assertEqual([n["titre"] for n in self.ok("lister")["notes"]], ["Existante"])
        self.assertEqual(self.ex("importer", fichiers=[])["statut"], "echec")


class Partage(Monde):
    def servir(self, jeton, **kw):
        r = self.n.executeur.executer("notes.partage_servir", "anonyme", dict(jeton=jeton, **kw), compte="")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_un_lien_sert_la_note_sans_session_et_ne_compte_que_les_vraies_ouvertures(self):
        a = self.note("Public", "bonjour **monde**")
        p = self.ok("partage_creer", ref=a)
        self.assertEqual((p["format"], p["protege"], p["chemin"]), ("html", False, "/api/public/notes.partage_servir"))
        r = self.servir(p["jeton"])
        self.assertEqual((r["ok"], r["mime"], "<strong>monde</strong>" in r["contenu"]), (True, "text/html", True))
        self.servir(p["jeton"], compter=False)
        self.assertEqual(self.ok("partages")["liens"][0]["n_vues"], 1)
        self.assertEqual(len(self.evts("note.partagee")), 1)
        md = self.servir(self.ok("partage_creer", ref=a, format="md")["jeton"])
        self.assertEqual(md["mime"], "text/markdown")

    def test_les_refus_sont_des_resultats_distincts_jamais_des_exceptions(self):
        a = self.note("Public", "x")
        p = self.ok("partage_creer", ref=a, jours=1)
        self.assertEqual(self.servir("inconnu")["code"], 404)
        for mauvais in ("../../etc/passwd", "a b", "x" * 80, ""):
            self.assertEqual(self.servir(mauvais)["code"], 404, mauvais)
        self.db.ecrire("UPDATE partages SET expire_le=? WHERE jeton=?", (time.time() - 5, p["jeton"]))
        e = self.servir(p["jeton"])
        self.assertEqual((e["ok"], e["code"], e["titre"]), (False, 410, "Public"))
        self.assertTrue(self.ok("partages")["liens"][0]["expire"])
        q = self.ok("partage_creer", ref=a)
        self.ok("supprimer", ref=a)
        self.assertEqual(self.servir(q["jeton"])["code"], 404)                  # la note n'existe plus

    def test_le_mot_de_passe_n_est_jamais_garde_en_clair_et_se_compare_sans_fuite(self):
        a = self.note("Protégée", "secret")
        p = self.ok("partage_creer", ref=a, mdp="rosebud")
        brut = self.db.lire("SELECT mdp FROM partages WHERE jeton=?", (p["jeton"],))[0]["mdp"]
        self.assertNotIn("rosebud", brut)
        self.assertTrue(p["protege"])
        self.assertEqual((self.servir(p["jeton"])["code"], self.servir(p["jeton"])["mdp"]), (401, True))
        w = self.servir(p["jeton"], mdp="faux")
        self.assertEqual((w["code"], w["erreur"]), (401, "mot de passe incorrect"))
        self.assertNotIn("contenu", w)
        self.assertTrue(self.servir(p["jeton"], mdp="rosebud")["ok"])
        q = self.ok("partage_creer", ref=a, mdp="rosebud")
        self.assertNotEqual(self.db.lire("SELECT mdp FROM partages WHERE jeton=?", (q["jeton"],))[0]["mdp"], brut)   # un sel par lien

    def test_les_mots_de_passe_devines_a_la_chaine_sont_refuses(self):
        a = self.note("Protégée", "secret")
        p = self.ok("partage_creer", ref=a, mdp="rosebud")
        for i in range(8):
            self.assertEqual(self.servir(p["jeton"], mdp="essai%d" % i)["code"], 401)
        r = self.servir(p["jeton"], mdp="rosebud")                             # même le bon, une fois la limite atteinte
        self.assertEqual((r["ok"], r["code"], r["limite"]), (False, 429, True))
        self.assertGreater(r["attente_s"], 0)

    def test_retirer_est_immediat_se_defait_et_ne_touche_que_ses_propres_liens(self):
        a = self.note("Public", "x")
        p = self.ok("partage_creer", ref=a)
        self.assertEqual(self.ex("partage_retirer", jeton=p["jeton"], compte=LEO)["statut"], "echec")
        self.assertTrue(self.servir(p["jeton"])["ok"])
        r = self.ex("partage_retirer", jeton=p["jeton"])
        self.assertEqual(self.servir(p["jeton"])["code"], 404)
        self.retour("partage_retirer", r["resultat"])
        self.assertTrue(self.servir(p["jeton"])["ok"])
        self.assertEqual(self.ex("partage_retirer", jeton="inconnu")["statut"], "echec")
        self.assertEqual(self.ok("partages", compte=LEO)["liens"], [])

    def test_creer_le_retour_les_formats_et_la_borne(self):
        a = self.note("Public", "x")
        r = self.ex("partage_creer", ref=a)
        self.retour("partage_creer", r["resultat"])
        self.assertEqual(self.servir(r["resultat"]["jeton"])["code"], 404)
        self.assertEqual(self.ex("partage_creer", ref=a, format="pdf")["statut"], "echec")
        self.assertEqual(self.ex("partage_creer", ref="N-0099")["statut"], "echec")
        self.assertEqual(self.ex("partage_creer", ref=a, compte=LEO)["statut"], "echec")
        self.glob["MAX_PARTAGES"] = 2
        self.ok("partage_creer", ref=a); self.ok("partage_creer", ref=a)
        self.assertIn("trop de liens", self.echec("partage_creer", ref=a))

    def test_un_lien_sans_echeance(self):
        a = self.note("Public", "x")
        p = self.ok("partage_creer", ref=a, jours=0)
        self.assertEqual(p["expire_le"], "")
        self.assertTrue(self.servir(p["jeton"])["ok"])


if __name__ == "__main__":
    unittest.main()
