# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la fiche d'un compte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #dbaf9d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la fiche d'un compte : validation (refus, jamais de coupure), migration des anciens champs, colonnes anciennes dérivées, corbeille, agents sans fiche.
# MÉTHODE    : un noyau jetable avec les modules droits et comptes ; les gestes passent par les capacités comptes.* comme à l'usage.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=dbaf9d ▼▼▼
"""Bancs de la fiche d'un compte : validation, migration, colonnes anciennes dérivées, corbeille, agents sans fiche."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                   # noqa: E402
from noyau import CN_fiche as fiche                        # noqa: E402

MDP = "Abcdefgh1!"


class Pure(unittest.TestCase):
    def test_valider_refuse_et_ne_coupe_jamais(self):
        p, e = fiche.valider({"lastname": "x" * 51})
        self.assertEqual(p, {})
        self.assertIn("rien n'est coupé", e[0])
        p, e = fiche.valider({"job": "j" * 128, "address": "a" * 255, "zip": "z" * 25, "office_phone": "0" * 30})
        self.assertEqual(e, [])
        self.assertEqual(len(p["job"]), 128)

    def test_formes(self):
        p, e = fiche.valider({"color": "#0A726B", "lang": "fr", "birth": "1980-02-03", "country_code": "fr", "employee": True,
                              "socialnetworks": {"mastodon": "@x"}, "tz": "Europe/Paris", "gender": "woman", "email": "a@b.fr", "office_phone": "+33 1 02.03"})
        self.assertEqual(e, [])
        self.assertEqual((p["color"], p["lang"], p["country_code"], p["employee"]), ("0A726B", "fr_FR", "FR", "1"))
        self.assertEqual(json.loads(p["socialnetworks"]), {"mastodon": "@x"})
        for mauvais in ({"color": "xyz"}, {"birth": "03/02/1980"}, {"email": "pas un courriel"}, {"office_phone": "abc"}, {"gender": "x"},
                        {"tz": "pas un fuseau"}, {"socialnetworks": "[1]"}, {"inconnu": "1"}, {"country_code": "FRA"}, {"civility_code": "TROPLONG"}):
            self.assertTrue(fiche.valider(mauvais)[1], mauvais)

    def test_les_noms(self):
        self.assertEqual(fiche.couper_nom("Marie Anne Dupont"), ("Marie Anne", "Dupont"))
        self.assertEqual(fiche.couper_nom("Dupont"), ("", "Dupont"))
        self.assertEqual(fiche.couper_nom(""), ("", ""))
        self.assertEqual(fiche.nom_affiche({"firstname": "Marie", "lastname": "Dupont"}), "Marie Dupont")
        self.assertEqual(fiche.langue_dolibarr("fr"), "fr_FR")
        self.assertEqual(fiche.langue_courte("fr_FR"), "fr")


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("comptes")["ok"])
        self.idt = self.n.identite
        self.idt.unix = lambda nom: "/bin/bash"
        self.idt.fastpanel = lambda: False

    def ex(self, cap, au_nom_de="operateur", **args):
        return self.n.executeur.executer(cap, "humain", args, compte=au_nom_de)

    def creer(self, compte, **profil):
        r = self.ex("comptes.creer", compte=compte, mot_de_passe=MDP, **profil)
        self.assertEqual(r["statut"], "faite", r)
        return r


class Fiche(Monde):
    def test_un_compte_cree_a_sa_fiche_et_les_colonnes_anciennes_en_derivent(self):
        self.creer("a@x.fr", display_name="Marie Dupont", role_label="Cheffe", contact_email="m@x.fr", phone="0102030405", lang="fr")
        f = self.idt.fiche("a@x.fr")
        self.assertEqual((f["firstname"], f["lastname"], f["job"], f["email"], f["office_phone"], f["lang"]), ("Marie", "Dupont", "Cheffe", "m@x.fr", "0102030405", "fr_FR"))
        a = self.idt.lire("a@x.fr")
        self.assertEqual((a["display_name"], a["role_label"], a["contact_email"], a["phone"], a["lang"]), ("Marie Dupont", "Cheffe", "m@x.fr", "0102030405", "fr"))
        self.assertEqual(self.idt.nom_affiche("a@x.fr"), "Marie Dupont")

    def test_ecrire_la_fiche_met_a_jour_les_colonnes_anciennes_et_refuse_le_trop_long(self):
        self.creer("a@x.fr", display_name="Marie Dupont")
        r = self.idt.fiche_ecrire("a@x.fr", {"firstname": "Anne", "job": "Directrice", "town": "Paris", "color": "#0a726b"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["avant"]["firstname"], "Marie")
        self.assertEqual(self.idt.lire("a@x.fr")["display_name"], "Anne Dupont")
        self.assertEqual(self.idt.lire("a@x.fr")["role_label"], "Directrice")
        self.assertEqual(self.idt.fiche("a@x.fr")["color"], "0a726b")
        avant = self.idt.fiche("a@x.fr")
        r = self.idt.fiche_ecrire("a@x.fr", {"lastname": "x" * 51, "town": "Lyon"})
        self.assertFalse(r["ok"])
        self.assertEqual(self.idt.fiche("a@x.fr"), avant)                                    # rien n'a été écrit, même pas le champ valable

    def test_le_geste_modifier_moi_passe_par_la_fiche_et_se_defait(self):
        self.creer("a@x.fr", display_name="Marie Dupont", role_label="Cheffe")
        r = self.ex("comptes.modifier_moi", au_nom_de="a@x.fr", display_name="Anne Martin", role_label="Directrice", town="Lyon")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.idt.fiche("a@x.fr")["firstname"], "Anne")
        self.assertEqual(self.idt.fiche("a@x.fr")["town"], "Lyon")
        r = self.ex("comptes.modifier_moi", au_nom_de="a@x.fr", lastname="y" * 60)
        self.assertEqual(r["statut"], "echec")

    def test_un_agent_n_a_pas_de_fiche(self):
        self.creer("a@x.fr")
        self.assertIsNone(self.idt.fiche("noyau"))
        self.assertIsNone(self.idt.fiche("inconnu@x.fr"))
        self.assertFalse(self.idt.fiche_ecrire("noyau", {"job": "x"})["ok"])
        self.assertEqual(self.idt.nom_affiche("noyau"), self.idt.lire("noyau")["display_name"] or "noyau")

    def test_la_migration_cree_la_fiche_des_comptes_anciens_sans_rien_perdre(self):
        self.creer("a@x.fr")
        self.creer("b@x.fr")
        for c, dn in (("a@x.fr", "Marie Anne Dupont"), ("b@x.fr", "Cher Prénom")):
            self.n.base.ecrire("UPDATE comptes SET display_name=?, role_label=?, contact_email=?, phone=?, lang='fr' WHERE compte=?", (dn, "J" * 130, "c@x.fr", "0102", c))
        self.n.base.ecrire("DELETE FROM comptes_fiche")                                      # des comptes d'avant la fiche
        rap = self.idt.migrer_fiches()
        self.assertEqual((rap["lus"], rap["creees"]), (2, 2))
        self.assertEqual(self.idt.fiche("a@x.fr")["firstname"], "Marie Anne")
        self.assertEqual(self.idt.fiche("a@x.fr")["lastname"], "Dupont")
        self.assertEqual(len(self.idt.fiche("a@x.fr")["job"]), 128)
        self.assertEqual({t["compte"] for t in rap["tronques"]}, {"a@x.fr", "b@x.fr"})      # signalé : l'original est gardé dans le rapport
        self.assertEqual(rap["tronques"][0]["original"], "J" * 130)
        self.assertEqual([r["compte"] for r in rap["noms_a_relire"]], ["a@x.fr"])             # plus de deux mots : le découpage est à relire
        self.assertEqual(self.idt.migrer_fiches()["creees"], 0)                              # idempotent
        self.assertTrue(json.loads(self.n.base.lire("SELECT valeur FROM etat_noyau WHERE cle='fiches_migration'")[0]["valeur"])["creees"])

    def test_un_compte_non_migre_se_lit_comme_la_migration_le_donnerait(self):
        self.creer("a@x.fr", display_name="Marie Dupont")
        self.n.base.ecrire("DELETE FROM comptes_fiche")
        self.assertEqual(self.idt.fiche("a@x.fr")["lastname"], "Dupont")
        self.assertEqual(self.n.base.lire("SELECT COUNT(*) AS n FROM comptes_fiche")[0]["n"], 0)    # lire n'écrit rien

    def test_la_corbeille_emporte_la_fiche_et_la_restauration_la_rend(self):
        self.creer("b@x.fr")                                                                   # le premier compte est le superadministrateur : on ne supprime pas le dernier
        self.creer("a@x.fr", display_name="Marie Dupont")
        self.idt.fiche_ecrire("a@x.fr", {"town": "Lyon", "birth": "1980-02-03", "socialnetworks": {"m": "@a"}})
        self.idt.portrait_source_poser("a@x.fr", "fastpanel")
        r = self.ex("comptes.supprimer", compte="a@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.n.base.lire("SELECT COUNT(*) AS n FROM comptes_fiche WHERE compte='a@x.fr'")[0]["n"], 0)
        cor = self.ex("comptes.corbeille")["resultat"]["corbeille"][0]["id"] if "corbeille" in self.ex("comptes.corbeille")["resultat"] else None
        self.assertIsNotNone(cor)
        r = self.ex("comptes.restaurer", corbeille=cor)
        self.assertEqual(r["statut"], "faite", r)
        f = self.idt.fiche("a@x.fr")
        self.assertEqual((f["town"], f["birth"], f["firstname"], f["photo_source"]), ("Lyon", "1980-02-03", "Marie", "fastpanel"))

    def test_la_source_du_portrait(self):
        self.creer("a@x.fr")
        self.assertTrue(self.idt.portrait_source_poser("a@x.fr", "dolibarr")["ok"])
        self.assertEqual(self.idt.fiche("a@x.fr")["photo_source"], "dolibarr")
        self.assertFalse(self.idt.portrait_source_poser("a@x.fr", "facebook")["ok"])
        self.assertFalse(self.idt.portrait_source_poser("noyau", "propre")["ok"])
class Capacites(Monde):
    def test_moi_rend_la_fiche_et_le_nom_affiche(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr", display_name="Marie Dupont")
        r = self.ex("comptes.moi", au_nom_de="a@x.fr")["resultat"]
        self.assertEqual((r["fiche"]["firstname"], r["fiche"]["lastname"], r["nom_affiche"]), ("Marie", "Dupont", "Marie Dupont"))

    def test_lire_la_fiche_d_un_autre_cache_le_prive_sauf_droit_et_se_journalise(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        self.creer("b@x.fr", display_name="Bea Martin")
        self.ex("comptes.modifier_moi", au_nom_de="b@x.fr", personal_email="bea@maison.fr", personal_mobile="0600000000", birth="1990-01-02", job="Comptable", office_phone="0102")
        self.ex("droits.regler", sujet="a@x.fr", droit="comptes.gerer")
        r = self.ex("comptes.lire", au_nom_de="a@x.fr", compte="b@x.fr")["resultat"]
        self.assertEqual((r["fiche"]["job"], r["fiche"]["office_phone"]), ("Comptable", "0102"))          # le professionnel se voit
        self.assertEqual((r["fiche"]["personal_email"], r["fiche"]["personal_mobile"], r["fiche"]["birth"]), ("", "", ""))
        self.ex("droits.regler", sujet="a@x.fr", droit="comptes.fiche_voir_perso")
        r = self.ex("comptes.lire", au_nom_de="a@x.fr", compte="b@x.fr")["resultat"]
        self.assertEqual((r["fiche"]["personal_email"], r["fiche"]["birth"]), ("bea@maison.fr", "1990-01-02"))
        moi = self.ex("comptes.lire", au_nom_de="root@x.fr", compte="root@x.fr")["resultat"]                # soi-même : rien de caché, rien de journalisé
        self.assertEqual(moi["fiche"]["personal_email"], "")
        vues = [e for e in self.n.journal_evenements() if e.get("type") == "compte.fiche_vue"] if hasattr(self.n, "journal_evenements") else None
        if vues is not None:
            self.assertEqual({e["objet_id"] for e in vues}, {"b@x.fr"})

    def test_modifier_la_fiche_d_un_autre_demande_son_droit_et_se_defait(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        self.creer("b@x.fr", display_name="Bea Martin")
        self.assertEqual(self.ex("comptes.fiche_modifier", au_nom_de="a@x.fr", compte="b@x.fr", champs={"job": "X"})["statut"], "refuse")
        self.ex("droits.regler", sujet="a@x.fr", droit="comptes.fiche_modifier_autres")
        r = self.ex("comptes.fiche_modifier", au_nom_de="a@x.fr", compte="b@x.fr", champs={"job": "Comptable", "town": "Lyon"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.idt.fiche("b@x.fr")["town"], "Lyon")
        self.assertEqual(self.idt.lire("b@x.fr")["role_label"], "Comptable")
        self.assertEqual(self.ex("comptes.fiche_modifier", au_nom_de="a@x.fr", compte="b@x.fr", champs={"zip": "z" * 26})["statut"], "echec")
        self.assertEqual(self.ex("comptes.fiche_modifier", au_nom_de="a@x.fr", compte="a@x.fr", champs={"job": "X"})["statut"], "echec")      # la sienne : modifier_moi
        self.assertEqual(self.ex("comptes.fiche_modifier", au_nom_de="a@x.fr", compte="noyau", champs={"job": "X"})["statut"], "echec")        # un compte système n'a pas de fiche

    def test_choisir_la_source_de_son_portrait(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        r = self.ex("comptes.portrait_source", au_nom_de="a@x.fr", source="fastpanel")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("comptes.moi", au_nom_de="a@x.fr")["resultat"]["fiche"]["photo_source"], "fastpanel")
        self.assertEqual(self.ex("comptes.portrait_source", au_nom_de="a@x.fr", source="facebook")["statut"], "echec")
class Portrait(Monde):
    PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40

    def b64(self, octets):
        import base64
        return base64.b64encode(octets).decode("ascii")

    def test_sans_image_ce_sont_les_initiales(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr", display_name="Marie Dupont")
        r = self.ex("comptes.portrait", au_nom_de="a@x.fr")["resultat"]
        self.assertEqual((r["source"], r["present"], r["initiales"]), ("initiales", False, "MD"))

    def test_televerser_une_image_la_choisit_et_la_retirer_rend_les_initiales(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr", display_name="Marie Dupont")
        r = self.ex("comptes.portrait_poser", au_nom_de="a@x.fr", image=self.b64(self.PNG))
        self.assertEqual(r["statut"], "faite", r)
        p = self.ex("comptes.portrait", au_nom_de="a@x.fr")["resultat"]
        self.assertEqual((p["source"], p["present"], p["type"]), ("propre", True, "image/png"))
        self.assertEqual(self.idt.fiche("a@x.fr")["photo_source"], "propre")
        r = self.ex("comptes.portrait_retirer", au_nom_de="a@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("comptes.portrait", au_nom_de="a@x.fr")["resultat"]["source"], "initiales")
        self.assertEqual(self.idt.fiche("a@x.fr")["photo_source"], "")

    def test_une_image_mauvaise_est_refusee(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        for image in (self.b64(b"GIF89a" + b"0" * 20), self.b64(b"%PDF-1.4"), self.b64(self.PNG + b"0" * (300 * 1024)), "", "pas du base64 !"):
            self.assertEqual(self.ex("comptes.portrait_poser", au_nom_de="a@x.fr", image=image)["statut"], "echec", image[:20])
        self.assertIsNone(self.idt.portrait_lire("a@x.fr"))
        self.assertEqual(self.idt.portrait_poser("a@x.fr", b"RIFF1234AVI " + b"0" * 20)["ok"], False)                  # RIFF mais pas WebP
        self.assertTrue(self.idt.portrait_poser("a@x.fr", b"RIFF1234WEBP" + b"0" * 20)["ok"])

    def test_une_source_absente_laisse_le_repli_sans_ecraser_l_image_propre(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        self.ex("comptes.portrait_poser", au_nom_de="a@x.fr", image=self.b64(self.PNG))
        self.assertEqual(self.ex("comptes.portrait_source", au_nom_de="a@x.fr", source="fastpanel")["statut"], "faite")
        p = self.ex("comptes.portrait", au_nom_de="a@x.fr", detail=True)["resultat"]
        self.assertEqual((p["demandee"], p["source"]), ("fastpanel", "propre"))                                       # le panneau n'a rien : le repli, pas le vide
        self.assertEqual(p["disponibles"], {"propre": True, "dolibarr": False, "fastpanel": False, "telegram": False})
        self.assertEqual(self.idt.portrait_lire("a@x.fr")[1], self.PNG)                                               # l'image propre n'a pas bougé
        self.assertEqual(self.ex("comptes.portrait", au_nom_de="a@x.fr", source="initiales")["resultat"]["source"], "initiales")
        self.assertEqual(self.ex("comptes.portrait", au_nom_de="a@x.fr", source="facebook")["statut"], "echec")

    def test_un_agent_n_a_pas_de_portrait(self):
        self.creer("root@x.fr")
        self.assertEqual(self.ex("comptes.portrait", au_nom_de="noyau")["statut"], "echec")

    def test_le_portrait_suit_la_corbeille(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        self.ex("comptes.portrait_poser", au_nom_de="a@x.fr", image=self.b64(self.PNG))
        self.ex("comptes.supprimer", compte="a@x.fr")
        self.assertIsNone(self.idt.portrait_lire("a@x.fr"))


class AvatarFastPanel(unittest.TestCase):
    def test_la_capacite_avatar_est_branchee_et_pas_seulement_declaree(self):
        with tempfile.TemporaryDirectory() as d:
            mods = Path(d) / "modules"
            shutil.copytree(RACINE / "modules" / "fastpanel", mods / "fastpanel")
            n = moteur.Noyau(Path(d) / "d", mods, {}, gerer_modules=True)
            n.brancher()
            n.etat_modules.poser("fastpanel", installe=True, par="test")
            self.assertTrue(n.activer("fastpanel")["ok"])
            self.assertTrue(n.catalogue.get("fastpanel.avatar").implementee, "fastpanel.avatar est déclarée au manifeste mais le module ne l'enregistre pas")

    def test_le_fichier_se_trouve_par_identifiant_puis_par_login_sans_jamais_prendre_celui_d_un_autre(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mod_fastpanel_avatar", RACINE / "modules" / "fastpanel" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "12.png").write_bytes(b"x")
            (Path(d) / "marie").write_bytes(b"y")
            (Path(d) / "autre.jpg").write_bytes(b"z")
            (Path(d) / "lisez-moi.txt").write_text("pas une image")
            self.assertEqual(Path(m._avatar_fichier("12", "marie", (d,))).name, "12.png")                      # l'identifiant d'abord
            self.assertEqual(Path(m._avatar_fichier("99", "marie", (d,))).name, "marie")                        # puis le login, même sans extension
            self.assertEqual(Path(m._avatar_fichier("", "autre", (d,))).name, "autre.jpg")
            self.assertEqual(m._avatar_fichier("99", "inconnu", (d,)), "")                                      # aucun nom ne correspond : rien, pas le portrait d'un autre
            self.assertEqual(m._avatar_fichier("", "", (d,)), "")
            self.assertEqual(m._avatar_fichier("1", "x", (d + "/absent",)), "")
class JournalDeMonCompte(Monde):
    def test_le_journal_ne_montre_que_mon_histoire(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr", display_name="Marie Dupont")
        self.creer("b@x.fr", display_name="Bea Martin")
        self.ex("comptes.ouvrir_session", au_nom_de="a@x.fr", compte="a@x.fr", mot_de_passe=MDP, ip="203.0.113.5", agent="Firefox")
        self.ex("comptes.ouvrir_session", au_nom_de="b@x.fr", compte="b@x.fr", mot_de_passe=MDP, ip="198.51.100.9", agent="Chrome")
        self.ex("comptes.ouvrir_session", au_nom_de="a@x.fr", compte="a@x.fr", mot_de_passe="Mauvais1!x", ip="203.0.113.6", agent="Firefox")
        self.ex("comptes.modifier_moi", au_nom_de="a@x.fr", town="Lyon")
        self.ex("comptes.modifier_moi", au_nom_de="b@x.fr", town="Nice")
        self.ex("comptes.lire", au_nom_de="root@x.fr", compte="a@x.fr")                   # le superadministrateur consulte ma fiche
        self.ex("comptes.lire", au_nom_de="root@x.fr", compte="b@x.fr")
        j = self.ex("comptes.mon_journal", au_nom_de="a@x.fr")["resultat"]["evenements"]
        textes = [e["texte"] for e in j]
        self.assertIn("Connexion", textes)
        self.assertIn("Connexion refusée", textes)
        self.assertIn("Fiche ou profil modifié", textes)
        self.assertTrue(any(t.startswith("Fiche consultée par") for t in textes), textes)       # qui a regardé ma fiche
        self.assertEqual(sum(1 for e in j if e["type"] == "compte.fiche_vue"), 1)                # celle de Bea n'est pas dans mon journal
        self.assertEqual(sum(1 for e in j if e["type"] == "compte.modifie"), 1)                  # ni la modification de Bea
        self.assertNotIn("198.51.100.9", " ".join(e["ip"] for e in j))
        self.assertEqual(self.ex("comptes.mon_journal", au_nom_de="")["statut"], "refuse")                # sans compte : rien
        self.assertLessEqual(len(self.ex("comptes.mon_journal", au_nom_de="a@x.fr", limite=2)["resultat"]["evenements"]), 2)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Pure, Monde, Fiche
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : noyau/CN_fiche.py, noyau/CN_identite.py
