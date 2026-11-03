# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'atelier des projets
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #235ee8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'atelier des projets : dossier de fichiers, versions, liens, fil, commentaires, courrier rangé, cadrage, navigateur.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=235ee8 ▼▼▼
"""Bancs de l'atelier des projets : un vrai noyau, le module projets seul, des comptes simulés. Le dossier de fichiers vit dans un espace de société jetable."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

CHEF, BEA, LEO, ZOE = "chef@x.fr", "bea@x.fr", "leo@x.fr", "zoe@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        ancien = os.environ.get("CASSANDRA_SOCIETES")
        os.environ["CASSANDRA_SOCIETES"] = str(base / "societes")
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_SOCIETES", ancien) if ancien else os.environ.pop("CASSANDRA_SOCIETES", None))
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "projets", mods / "projets", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("projets")["ok"])
        self.n.droits.regler_admin(CHEF, True)
        self.ctx = self.n.executeur.contextes["projets"]
        self.pages = {}
        self.ctx.executer_lecture = self.lecture
        self.e = self.n.executeur.executer

    def lecture(self, cap, **a):
        if cap == "comptes.lister":
            return {"comptes": [{"compte": x, "display_name": x.split("@")[0].title()} for x in (CHEF, BEA, LEO, ZOE)]}
        if cap == "web.lire":
            if a["url"] not in self.pages:
                raise ValueError("lecture impossible")
            return dict(self.pages[a["url"]], url=a["url"])
        return None

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("projets." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def refus(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertNotEqual(r["statut"], "faite", r)
        return r

    def retour(self, cap, res):
        self.n.catalogue.get("projets." + cap).defaire(self.ctx, res)

    def projet(self, nom="Roman", compte=BEA, **kw):
        pid = self.ok("creer", nom=nom, compte=compte, **kw)["id"]
        self.ok("dossier_local", id=pid, compte=compte)
        return pid

    def equipe(self, pid, cible, role, par=BEA):
        r = self.e("projets.inviter", "humain", {"id": pid, "compte": cible, "role": role}, compte=par)
        self.assertEqual(r["statut"], "faite", r)
        self.ok("repondre_invitation", id=pid, accepter=True, compte=cible)


class Dossier(Monde):
    def test_le_dossier_local_porte_le_nom_du_projet_et_se_defait(self):
        pid = self.ok("creer", nom="Roman : suite")["id"]
        r = self.ok("dossier_local", id=pid)
        self.assertEqual(r["dossier"], "local:/Roman _ suite")
        self.assertEqual(self.ok("voir", id=pid)["projet"]["dossier"], r["dossier"])
        self.refus("dossier_local", id=pid)                    # déjà un dossier
        self.retour("dossier_local", r)
        self.assertEqual(self.ok("voir", id=pid)["projet"]["dossier"], "")

    def test_sans_dossier_l_atelier_le_dit(self):
        pid = self.ok("creer", nom="Sans")["id"]
        self.assertIn("n'a pas de dossier", self.refus("coffre_lister", id=pid, chemin="")["erreur"])

    def test_parcourir_creer_et_corbeille(self):
        self.assertEqual(self.ok("dossier_parcourir")["machines"][0]["nom"], "local")
        r = self.ok("dossier_creer", machine="local", chemin="/", nom="Vrac")
        self.assertEqual(r["chemin"], "/Vrac")
        self.assertIn("Vrac", self.ok("dossier_parcourir", machine="local", chemin="/")["dossiers"])
        self.refus("dossier_creer", machine="ssh", chemin="/", nom="X")
        e = self.ok("dossier_creer", machine="local", chemin="/", nom="../évasion")             # le nom est assaini : il ne remonte nulle part
        self.assertEqual(e["chemin"], "/_évasion")
        self.refus("dossier_creer", machine="local", chemin="/../..", nom="X")
        c = self.ok("dossier_corbeille", machine="local", chemin="/Vrac")
        self.assertNotIn("Vrac", self.ok("dossier_parcourir", machine="local", chemin="/")["dossiers"])
        self.retour("dossier_corbeille", c)
        self.assertIn("Vrac", self.ok("dossier_parcourir", machine="local", chemin="/")["dossiers"])

    def test_le_dossier_d_un_projet_ne_va_pas_a_la_corbeille(self):
        self.projet("Roman")
        self.assertIn("Roman", self.refus("dossier_corbeille", machine="local", chemin="/Roman")["erreur"])

    def test_lier_un_depot_existant_et_refuser_une_machine_distante(self):
        pid = self.ok("creer", nom="Lien")["id"]
        self.ok("dossier_creer", machine="local", chemin="/", nom="Existant")
        self.refus("dossier_lier", id=pid, dossier="athena:/volume1/x")
        self.refus("dossier_lier", id=pid, dossier="local:/Absent")
        r = self.ok("dossier_lier", id=pid, dossier="local:/Existant")
        self.assertEqual(self.ok("voir", id=pid)["projet"]["dossier"], "local:/Existant")
        self.retour("dossier_lier", r)
        self.assertEqual(self.ok("voir", id=pid)["projet"]["dossier"], "")


class Fichiers(Monde):
    def test_ecrire_lire_versions_et_conflit(self):
        pid = self.projet()
        w = self.ok("coffre_ecrire", id=pid, chemin="ch1.md", texte="Un", creer=True)
        self.assertTrue(w["cree"])
        self.refus("coffre_ecrire", id=pid, chemin="ch1.md", texte="Deux", creer=True)       # existe déjà
        lu = self.ok("coffre_lire", id=pid, chemin="ch1.md")
        self.assertEqual(lu["texte"], "Un")
        w2 = self.ok("coffre_ecrire", id=pid, chemin="ch1.md", texte="Deux", empreinte=lu["empreinte"])
        self.assertEqual(w2["version"], 2)
        # quelqu'un d'autre a écrit entre-temps : rien n'est écrasé
        c = self.ok("coffre_ecrire", id=pid, chemin="ch1.md", texte="Trois", empreinte=lu["empreinte"])
        self.assertTrue(c["conflit"])
        self.assertEqual(c["texte"], "Deux")
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="ch1.md")["texte"], "Deux")
        vs = self.ok("coffre_versions", id=pid, chemin="ch1.md")["versions"]
        self.assertEqual([v["n"] for v in vs], [2, 1])
        self.assertEqual(self.ok("coffre_version", id=pid, chemin="ch1.md", n=1)["texte"], "Un")
        # l'inchangé n'écrit rien
        self.assertTrue(self.ok("coffre_ecrire", id=pid, chemin="ch1.md", texte="Deux")["inchange"])

    def test_le_retour_d_une_ecriture_remet_l_etat_d_avant(self):
        pid = self.projet()
        w1 = self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Un", creer=True)
        w2 = self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Deux")
        self.retour("coffre_ecrire", w2)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Un")
        self.retour("coffre_ecrire", w1)
        self.refus("coffre_lire", id=pid, chemin="a.md")

    def test_rien_ne_sort_du_dossier(self):
        pid = self.projet()
        for ch in ("../autre.md", "/../../etc/passwd", "a/../../x.md"):
            self.refus("coffre_ecrire", id=pid, chemin=ch, texte="x", creer=True)
            self.refus("coffre_lire", id=pid, chemin=ch)
        self.refus("coffre_ecrire", id=pid, chemin="image.png", texte="x", creer=True)          # seul le texte s'écrit
        self.refus("coffre_ecrire", id=pid, chemin="", texte="x", creer=True)

    def test_deplacer_reecrit_les_liens_et_se_defait(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="cible.md", texte="# Cible", creer=True)
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Voir [[cible]] et [[cible|l'alias]] et [x](cible.md).", creer=True)
        self.ok("coffre_dossier", id=pid, chemin="Archive")
        d = self.ok("coffre_deplacer", id=pid, chemin="cible.md", vers="Archive/cible2.md")
        self.assertEqual(d["liens"], 3)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Voir [[cible2]] et [[cible2|l'alias]] et [x](Archive/cible2.md).")
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="Archive/cible2.md")["texte"], "# Cible")
        self.refus("coffre_deplacer", id=pid, chemin="a.md", vers="Archive/cible2.md")         # existe déjà
        self.retour("coffre_deplacer", d)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Voir [[cible]] et [[cible|l'alias]] et [x](cible.md).")

    def test_retirer_un_fichier_le_garde_en_version_et_se_defait(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Précieux", creer=True)
        r = self.ok("coffre_retirer", id=pid, chemin="a.md")
        self.refus("coffre_lire", id=pid, chemin="a.md")
        self.assertEqual(self.ok("coffre_version", id=pid, chemin="a.md", n=r["version"])["texte"], "Précieux")
        self.retour("coffre_retirer", r)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Précieux")

    def test_retirer_un_dossier_va_a_la_corbeille_et_revient(self):
        pid = self.projet()
        self.ok("coffre_dossier", id=pid, chemin="Brouillons")
        self.ok("coffre_ecrire", id=pid, chemin="Brouillons/x.md", texte="x", creer=True)
        r = self.ok("coffre_retirer", id=pid, chemin="Brouillons")
        self.assertTrue(r["dossier"])
        self.refus("coffre_lister", id=pid, chemin="Brouillons")
        self.retour("coffre_retirer", r)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="Brouillons/x.md")["texte"], "x")
        self.refus("coffre_retirer", id=pid, chemin="")                                         # jamais la racine

    def test_remettre_une_version(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Un", creer=True)
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Deux")
        r = self.ok("coffre_remettre", id=pid, chemin="a.md", n=1)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Un")
        self.retour("coffre_remettre", r)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Deux")
        self.refus("coffre_remettre", id=pid, chemin="a.md", n=99)

    def test_lister_index_etat_et_fichier(self):
        pid = self.projet()
        self.ok("coffre_dossier", id=pid, chemin="Sous")
        self.ok("coffre_ecrire", id=pid, chemin="Sous/n.md", texte="n", creer=True)
        racine = self.ok("coffre_lister", id=pid, chemin="")
        self.assertEqual([i["nom"] for i in racine["items"]], ["Sous"])
        self.assertEqual(self.ok("coffre_index", id=pid)["notes"], ["Sous/n.md"])
        self.assertGreater(self.ok("coffre_etat", id=pid, chemin="Sous/n.md")["mt"], 0)
        dossier = self.n.executeur.contextes["projets"]
        racine_dep = Path(os.environ["CASSANDRA_SOCIETES"])
        img = next(racine_dep.rglob("Roman")) / "Sous" / "p.png"
        img.write_bytes(b"\x89PNG-faux")
        self.assertEqual(self.ok("coffre_fichier", id=pid, chemin="Sous/p.png")["mime"], "image/png")
        self.assertIn("non affichable", self.refus("coffre_fichier", id=pid, chemin="Sous/n.md")["erreur"])
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="Sous/p.png")["binaire"], True)

    def test_la_fiche_d_un_document(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="cible.md", texte="# Cible", creer=True)
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Voir [[cible]].", creer=True)
        self.ok("commenter", id=pid, chemin="cible.md", citation="Cible", texte="Bien vu")
        f = self.ok("atelier_fiche", id=pid, chemin="cible.md")
        self.assertEqual(f["cite_par"], ["a.md"])
        self.assertEqual(f["versions"], 1)
        self.assertEqual(f["commentaires"], 1)
        self.assertEqual(f["auteurs"][0]["auteur"], BEA)


class Roles(Monde):
    def test_un_projet_d_autrui_est_introuvable_meme_pour_l_administrateur(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="secret", creer=True)
        for qui in (LEO, CHEF):
            for cap, kw in (("coffre_lire", {"chemin": "a.md"}), ("coffre_lister", {"chemin": ""}), ("coffre_index", {}), ("fil", {}), ("commentaires", {"chemin": "a.md"}),
                            ("atelier_sources", {}), ("presence", {}), ("garde", {})):
                self.assertIn("introuvable", self.refus(cap, id=pid, compte=qui, **kw)["erreur"], (qui, cap))
            self.refus("coffre_ecrire", id=pid, compte=qui, chemin="b.md", texte="x", creer=True)
            self.refus("fil_publier", id=pid, compte=qui, texte="x")
            self.refus("dossier_local", id=pid, compte=qui)

    def test_un_lecteur_lit_commente_et_ne_modifie_rien(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Texte", creer=True)
        self.equipe(pid, LEO, "lecteur")
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md", compte=LEO)["texte"], "Texte")
        self.ok("commenter", id=pid, chemin="a.md", citation="Texte", texte="Une remarque", compte=LEO)
        self.ok("fil_publier", id=pid, texte="Bonjour", compte=LEO)
        for cap, kw in (("coffre_ecrire", {"chemin": "a.md", "texte": "x"}), ("coffre_retirer", {"chemin": "a.md"}), ("coffre_deplacer", {"chemin": "a.md", "vers": "b.md"}),
                        ("coffre_dossier", {"chemin": "D"}), ("coffre_remettre", {"chemin": "a.md", "n": 1}), ("fil_publier", {"genre": "journal", "texte": "x"}),
                        ("fil_publier", {"genre": "decision", "texte": "x"}), ("proposer", {}), ("dossier_lier", {"dossier": ""}), ("nav_clipper", {})):
            self.assertIn("rôle", self.refus(cap, id=pid, compte=LEO, **kw).get("erreur", ""), cap)
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Texte")

    def test_un_auteur_ecrit_et_un_projet_archive_n_ecrit_plus(self):
        pid = self.projet()
        self.equipe(pid, ZOE, "auteur")
        self.ok("coffre_ecrire", id=pid, chemin="z.md", texte="Zoé", creer=True, compte=ZOE)
        self.assertEqual(self.ok("coffre_versions", id=pid, chemin="z.md")["versions"][0]["auteur"], ZOE)
        self.ok("archiver", id=pid, archive=True)
        self.assertIn("archivé", self.refus("coffre_ecrire", id=pid, chemin="z.md", texte="x")["erreur"])
        self.assertIn("archivé", self.refus("fil_publier", id=pid, texte="x", compte=ZOE)["erreur"])
        self.assertIn("archivé", self.refus("commenter", id=pid, chemin="z.md", texte="x", compte=ZOE)["erreur"])
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="z.md")["texte"], "Zoé")        # la lecture reste

    def test_ce_qu_itare_ecrit_entre_dans_la_file_a_relire_et_s_annule(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="Original", creer=True)
        self.n.catalogue.regler_palier("projets.coffre_ecrire", "auto")
        r = self.ex("coffre_ecrire", acteur="itare", id=pid, chemin="a.md", texte="Retouche d'Itare")
        self.assertEqual(r["statut"], "faite", r)
        a_relire = [x for x in self.ok("fil", id=pid)["fil"] if x["genre"] == "relire"]
        self.assertEqual(len(a_relire), 1)
        self.assertEqual(self.ok("fil", id=pid)["attente"]["relire"], 1)
        self.ok("fil_relire", id=pid, fid=a_relire[0]["id"], action="annuler")
        self.assertEqual(self.ok("coffre_lire", id=pid, chemin="a.md")["texte"], "Original")
        self.assertEqual(self.ok("fil", id=pid)["attente"]["relire"], 0)


class Fil(Monde):
    def test_messages_mentions_et_journal(self):
        pid = self.projet()
        self.equipe(pid, LEO, "auteur")
        r = self.ok("fil_publier", id=pid, texte="On en parle @Leo ?")
        self.assertEqual(r["mentions"], [LEO])
        evs = [x for x in self.n.bus.recents(portee=__import__("noyau.CN_bus", fromlist=["TOUT"]).TOUT, limite=900) if x["type"] == "projet.mention"]
        self.assertEqual(len(evs), 1)
        q = self.ok("fil_publier", id=pid, texte="@Itare où en est-on ?")
        self.assertTrue(q["itare"])
        j = self.ok("fil_publier", id=pid, genre="journal", texte="Chapitre 3 fini")
        self.assertIn("Chapitre 3 fini", [x["texte"] for x in self.ok("voir", id=pid)["projet"]["journal"]])
        genres = [x["genre"] for x in self.ok("fil", id=pid)["fil"]]
        self.assertEqual(genres.count("message"), 2)
        self.retour("fil_publier", j)
        self.assertNotIn("Chapitre 3 fini", [x["texte"] for x in self.ok("voir", id=pid)["projet"]["journal"]])
        self.refus("fil_publier", id=pid, texte="   ")

    def test_une_decision_s_ouvre_recoit_des_avis_et_se_tranche(self):
        pid = self.projet()
        self.equipe(pid, LEO, "auteur")
        d = self.ok("fil_publier", id=pid, genre="decision", texte="Quel titre ?")
        self.assertEqual(self.ok("fil", id=pid)["attente"]["decisions"], 1)
        self.ok("fil_avis", id=pid, fid=d["fid"], avis="pour", compte=LEO)
        self.refus("fil_avis", id=pid, fid=d["fid"], avis="peut-être")
        t = self.ok("fil_trancher", id=pid, fid=d["fid"], issue="Le premier", raison="Plus court")
        ligne = next(x for x in self.ok("fil", id=pid)["fil"] if x["id"] == d["fid"])
        self.assertEqual((ligne["etat"], ligne["meta"]["issue"], ligne["meta"]["avis"]), ("decidee", "Le premier", {LEO: "pour"}))
        self.refus("fil_trancher", id=pid, fid=d["fid"], issue="Autre")                          # déjà tranchée
        self.assertEqual(self.ok("fil", id=pid)["attente"]["decisions"], 0)
        self.retour("fil_trancher", t)
        self.assertEqual(self.ok("fil", id=pid)["attente"]["decisions"], 1)

    def test_l_activite_du_dossier_est_regroupee(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="1", creer=True)
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="2")
        act = [x for x in self.ok("fil", id=pid)["fil"] if x["genre"] == "activite"]
        self.assertEqual((len(act), act[0]["meta"]["n"], act[0]["ref"]), (1, 2, "a.md"))


class Commentaires(Monde):
    def test_commenter_repondre_resoudre(self):
        pid = self.projet()
        self.equipe(pid, LEO, "lecteur")
        c = self.ok("commenter", id=pid, chemin="a.md", citation="le passage", texte="Revoir ceci")
        self.ok("commenter", id=pid, chemin="a.md", texte="D'accord", parent=c["cid"], compte=LEO)
        L = self.ok("commentaires", id=pid, chemin="a.md")["commentaires"]
        self.assertEqual([(x["parent"], x["citation"]) for x in L], [(0, "le passage"), (c["cid"], "")])
        self.refus("commentaire_resoudre", id=pid, cid=c["cid"], compte=LEO)                     # un lecteur ne résout pas
        r = self.ok("commentaire_resoudre", id=pid, cid=c["cid"])
        self.assertTrue(self.ok("commentaires", id=pid, chemin="a.md")["commentaires"][0]["resolu"].startswith(BEA))
        self.retour("commentaire_resoudre", r)
        self.assertEqual(self.ok("commentaires", id=pid, chemin="a.md")["commentaires"][0]["resolu"], "")
        self.assertEqual(self.ok("commentaires", id=pid, chemin="autre.md")["commentaires"], [])

    def test_la_presence_ne_s_ecrit_pas_et_ne_montre_que_les_autres(self):
        pid = self.projet()
        self.equipe(pid, LEO, "lecteur")
        self.assertEqual(self.ok("presence", id=pid, chemin="a.md")["presents"], [])
        self.assertEqual(self.ok("presence", id=pid, chemin="b.md", compte=LEO)["presents"], [{"compte": BEA, "chemin": "a.md"}])


class Cadrage(Monde):
    def test_le_cadrage_rend_un_diff_sans_rien_ecrire(self):
        pid = self.projet()
        r = self.ok("cadrage_proposer", id=pid, reponses={"objectif": "Écrire le tome 2", "perimetre_out": "traduction, audio", "reussite": "300 pages; relu", "jalon": "remise le 14/03/2027"})
        genres = [(p["genre"], p["quoi"]) for p in r["propositions"]]
        self.assertEqual(genres, [("entete", "Objectif"), ("entete", "Hors périmètre — 2 point(s)"), ("entete", "Critères de réussite — 2"), ("jalon", "Étape — 2027-03-14")])
        self.assertEqual(r["flou"], [])
        self.assertEqual(self.ok("voir", id=pid)["projet"]["objectif"], "")
        v = self.ok("cadrage_proposer", id=pid, reponses={"jalon": "bientôt"})
        self.assertEqual(v["propositions"], [])
        self.assertIn("Aucune date lisible", v["flou"][0])
        self.assertEqual(len(v["flou"]), 4)
        self.assertEqual(self.ok("modeles")["questions"][0]["cle"], "objectif")

    def test_les_suites_proposees_viennent_des_faits(self):
        pid = self.projet()
        self.ok("jalon_enregistrer", id=pid, nom="Remise", date="2020-01-01")
        self.ok("decision_enregistrer", id=pid, question="Quelle police ?")
        r = self.ok("proposer", id=pid)
        self.assertEqual(len(r["items"]), 3)
        self.assertIn("Remise", r["items"][0])
        self.retour("proposer", r)


class Courrier(Monde):
    def test_sans_module_courrier_la_boite_est_dite_absente(self):
        pid = self.projet()
        self.assertEqual(self.ok("courrier", id=pid)["fils"], [])
        self.assertFalse(self.ok("courrier", id=pid)["boite"])
        self.refus("courrier_ranger", id=pid, folder="INBOX", uid="1")


class Navigateur(Monde):
    def test_aller_retour_clipper_fermer(self):
        pid = self.projet()
        self.pages["https://exemple.org/a"] = {"titre": "Page A", "texte": "Le texte de A"}
        self.pages["https://exemple.org/b"] = {"titre": "Page B", "texte": "Le texte de B"}
        self.refus("nav_clipper", id=pid)                                                       # rien d'ouvert
        self.refus("nav_retour")
        self.assertEqual(self.ok("nav_aller", url="exemple.org/a")["titre"], "Page A")
        self.assertEqual(self.ok("nav_aller", url="https://exemple.org/b")["pages"], 2)
        self.assertEqual(self.ok("nav_retour")["titre"], "Page A")
        c = self.ok("nav_clipper", id=pid, dossier="Clips")
        self.assertEqual(c["chemin"], "Clips/Page A.md")
        self.assertIn("Le texte de A", self.ok("coffre_lire", id=pid, chemin="Clips/Page A.md")["texte"])
        self.assertEqual(self.ok("nav_clipper", id=pid)["chemin"], "Clips/Page A (2).md")
        self.refus("nav_aller", url="https://introuvable.test/")
        self.retour("nav_clipper", c)
        self.refus("coffre_lire", id=pid, chemin="Clips/Page A.md")
        self.ok("nav_fermer")
        self.refus("nav_clipper", id=pid)

    def test_chaque_compte_a_son_navigateur(self):
        self.pages["https://exemple.org/a"] = {"titre": "Page A", "texte": "A"}
        self.ok("nav_aller", url="https://exemple.org/a")
        self.refus("nav_retour", compte=LEO)


class Purge(Monde):
    def test_purger_un_projet_efface_ce_qu_il_portait_en_base(self):
        pid = self.projet()
        self.ok("coffre_ecrire", id=pid, chemin="a.md", texte="x", creer=True)
        self.ok("fil_publier", id=pid, texte="Bonjour")
        self.ok("supprimer", id=pid)
        self.ok("purger", id=pid)
        for t in ("pj_versions", "pj_fil", "pj_activite"):
            self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM %s" % t)[0]["n"], 0, t)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Dossier, Fichiers, Roles, Fil, Commentaires, Cadrage, Courrier, Navigateur, Purge
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
