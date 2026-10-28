# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module courrier
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #dee561
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module courrier : un vrai noyau, de vrais imaplib et smtplib, un serveur IMAP et un serveur SMTP de poche.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=dee561 ▼▼▼
"""Bancs du module courrier : un vrai noyau, de vrais imaplib et smtplib, un serveur IMAP et un serveur SMTP de poche."""
import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402
from CN_faux_serveurs_courrier import Boite, ServeurImap, ServeurSmtp, message   # noqa: E402

BEA, LEO = "bea@x.fr", "leo@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.boite = Boite(BEA, "mdp-imap")
        self.imap = ServeurImap(self.boite)
        self.addCleanup(self.imap.arreter)
        self.smtp = ServeurSmtp(BEA, "mdp-smtp")
        self.addCleanup(self.smtp.arreter)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "courrier", mods / "courrier", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("courrier")["ok"])
        self.n.droits.regler_admin(BEA, True)
        self.ctx = self.n.executeur.contextes["courrier"]
        self.reglages_de(BEA, "127.0.0.1", self.imap.port, BEA, "mdp-imap")
        self.n.reglages.poser("courrier.smtp_hote", "127.0.0.1", BEA)
        self.n.reglages.poser("courrier.smtp_port", self.smtp.port, BEA)
        self.n.reglages.poser("courrier.smtp_mot_de_passe", "mdp-smtp", BEA)
        self.comptes = [{"compte": BEA}, {"compte": LEO}]
        self.ctx.executer_lecture = lambda cap, **a: {"comptes": self.comptes}
        self.e = self.n.executeur.executer

    def reglages_de(self, compte, hote, port, identifiant, mdp, chiffre=False):
        r = self.n.reglages
        r.poser("courrier.imap_hote", hote, compte)
        r.poser("courrier.imap_port", port, compte)
        r.poser("courrier.imap_chiffre", chiffre, compte)
        r.poser("courrier.imap_identifiant", identifiant, compte)
        r.poser("courrier.imap_mot_de_passe", mdp, compte)

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("courrier." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def retour(self, cap, res):
        self.n.catalogue.get("courrier." + cap).defaire(self.ctx, res)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def ajouter(self, n=1, dossier="INBOX", flags=(), **kw):
        return [self.boite.ajouter(dossier, message(objet=kw.pop("objet", "Message %d" % i) if n == 1 else "Message %d" % i, **kw), flags) for i in range(1, n + 1)]

    def flags(self, dossier, uid):
        return next(m["flags"] for m in self.boite.dossiers[dossier] if m["uid"] == uid)

    def commandes(self):
        return [c.split(" ")[0] + " " + (c.split(" ")[1] if " " in c else "") for c in self.boite.commandes]


class Connexion(Monde):
    def test_sans_boite_rien_n_est_configure(self):
        self.assertFalse(self.ok("etat", compte=LEO)["configuree"])
        r = self.ex("lister", compte=LEO)
        self.assertEqual(r["statut"], "echec")
        self.assertIn("aucune boîte", json.dumps(r, ensure_ascii=False))

    def test_tester_la_boite(self):
        r = self.ok("tester_boite")
        self.assertTrue(r["ok"])
        self.assertEqual(r["dossiers"], 4)
        self.assertIn("MOVE", r["capacites"])

    def test_un_mauvais_mot_de_passe_se_dit_sans_le_citer(self):
        self.n.reglages.poser("courrier.imap_mot_de_passe", "mauvais-mdp-secret", BEA)
        r = self.ok("tester_boite")
        self.assertFalse(r["ok"])
        self.assertNotIn("mauvais-mdp-secret", json.dumps(r))
        self.assertNotIn("mauvais-mdp-secret", json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str))

    def test_une_connexion_non_chiffree_vers_un_hote_distant_est_refusee(self):
        self.reglages_de(LEO, "imap.exemple.fr", 143, LEO, "x", chiffre=False)
        r = self.ok("tester_boite", compte=LEO)
        self.assertFalse(r["ok"])
        self.assertIn("non chiffrée", r["erreur"])
        self.assertEqual(self.boite.commandes, [])

    def test_une_boite_par_compte_jamais_celle_d_un_autre(self):
        self.assertEqual(self.ex("dossiers", compte=LEO)["statut"], "echec")
        self.assertEqual(self.ex("lister", compte="cassandra")["statut"], "echec")
        self.assertEqual(self.ex("lister", compte="")["statut"], "echec")

    def test_une_session_tombee_entre_deux_appels_est_reprise_une_fois(self):
        self.ajouter(2)
        self.ok("lister")
        self.boite.coupures = 1
        r = self.ok("lister")
        self.assertEqual(len(r["messages"]), 2)

    def test_les_deux_comptes_ont_chacun_sa_session(self):
        boite2 = Boite(LEO, "mdp-leo")
        imap2 = ServeurImap(boite2)
        self.addCleanup(imap2.arreter)
        self.reglages_de(LEO, "127.0.0.1", imap2.port, LEO, "mdp-leo")
        boite2.ajouter("INBOX", message(objet="Pour Leo"), ())
        self.ajouter(1, objet="Pour Bea")
        self.assertEqual([m["objet"] for m in self.ok("lister", compte=BEA)["messages"]], ["Pour Bea"])
        self.assertEqual([m["objet"] for m in self.ok("lister", compte=LEO)["messages"]], ["Pour Leo"])


class Dossiers(Monde):
    def test_roles_compteurs_et_noms_lisibles(self):
        self.boite.dossiers["Envoy&AOk-s clients"] = []
        self.ajouter(3, flags=())
        self.ajouter(1, flags=("\\Seen",))
        ds = {d["nom"]: d for d in self.ok("dossiers")["dossiers"]}
        self.assertEqual((ds["INBOX"]["total"], ds["INBOX"]["non_lus"]), (4, 3))
        self.assertEqual((ds["Sent"]["role"], ds["Trash"]["role"], ds["Drafts"]["role"]), ("sent", "trash", "drafts"))
        self.assertIn("Envoyés clients", ds)

    def test_creer_un_dossier_prouve_et_defait(self):
        r = self.ex("dossier_creer", nom="Clients 2026")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("Clients 2026", self.boite.dossiers)
        self.retour("dossier_creer", r["resultat"])
        self.assertNotIn("Clients 2026", self.boite.dossiers)

    def test_creer_un_dossier_accentue_l_encode_pour_le_serveur(self):
        self.ok("dossier_creer", nom="Éléments")
        self.assertIn("&AMk-l&AOk-ments", self.boite.dossiers)
        self.assertIn("Éléments", [d["nom"] for d in self.ok("dossiers")["dossiers"]])

    def test_un_dossier_deja_la_ou_sans_nom_est_refuse(self):
        self.assertEqual(self.ex("dossier_creer", nom="Sent")["statut"], "echec")
        self.assertEqual(self.ex("dossier_creer", nom="  ")["statut"], "echec")

    def test_renommer_prouve_et_defait_mais_pas_la_reception(self):
        self.boite.dossiers["Vieux"] = []
        r = self.ex("dossier_renommer", ancien="Vieux", nouveau="Récent")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("Récent", [d["nom"] for d in self.ok("dossiers")["dossiers"]])
        self.retour("dossier_renommer", r["resultat"])
        self.assertIn("Vieux", self.boite.dossiers)
        self.assertEqual(self.ex("dossier_renommer", ancien="INBOX", nouveau="Autre")["statut"], "echec")


class Messages(Monde):
    def test_lister_pagine_du_plus_recent_au_plus_ancien_et_classe(self):
        self.ajouter(7)
        self.boite.ajouter("INBOX", message(de="root@serveur.exemple.fr", objet="Cron <root@srv> backup"), ())
        r = self.ok("lister", limite=3)
        self.assertEqual((r["total"], len(r["messages"]), r["encore"]), (8, 3, True))
        self.assertEqual(r["messages"][0]["objet"], "Cron <root@srv> backup")
        self.assertEqual(r["messages"][0]["etat"], "tech")
        r2 = self.ok("lister", limite=3, decalage=6)
        self.assertEqual((len(r2["messages"]), r2["encore"]), (2, False))
        self.assertEqual(r["classes"]["tech"], 0)                           # pas encore au cache lors du premier passage
        self.assertEqual(self.ok("lister")["classes"]["tech"], 1)

    def test_les_drapeaux_viennent_du_serveur_a_chaque_liste(self):
        (u,) = self.ajouter(1, flags=())
        self.assertFalse(self.ok("lister")["messages"][0]["lu"])
        self.flags("INBOX", u).add("\\Seen")
        self.assertTrue(self.ok("lister")["messages"][0]["lu"])

    def test_non_lus_et_recherche_par_le_serveur(self):
        self.ajouter(1, flags=("\\Seen",), objet="Lu")
        self.ajouter(1, flags=(), objet="Neuf", de="zoe@exemple.fr")
        self.assertEqual([m["objet"] for m in self.ok("lister", non_lus=True)["messages"]], ["Neuf"])
        self.assertEqual([m["objet"] for m in self.ok("lister", requete="zoe")["messages"]], ["Neuf"])

    def test_filtrer_par_etat(self):
        self.boite.ajouter("INBOX", message(de="root@serveur.exemple.fr", objet="Cron <root@srv> backup"), ())
        self.boite.ajouter("INBOX", message(de="client@exemple.fr", objet="Devis"), ())
        self.ok("lister")
        self.assertEqual([m["objet"] for m in self.ok("lister", etat="traiter")["messages"]], ["Devis"])
        self.assertEqual(len(self.ok("lister", etat="tech")["messages"]), 1)

    def test_lire_ne_marque_pas_lu(self):
        (u,) = self.ajouter(1, flags=(), corps="Le contenu")
        r = self.ok("lire", uid=str(u))
        self.assertEqual((r["texte"], r["objet"]), ("Le contenu", "Message 1"))
        self.assertNotIn("\\Seen", self.flags("INBOX", u))
        self.assertTrue(any("BODY.PEEK" in c or "BODY[]" in c or "FETCH" in c for c in self.boite.commandes))

    def test_lire_nettoie_le_html_et_bloque_les_images(self):
        (u,) = self.ajouter(1, html='<p onclick="x()">Salut <script>alert(1)</script><img src="http://t.fr/p.png"></p>')
        r = self.ok("lire", uid=str(u), html=True)
        self.assertNotIn("<script", r["html"])
        self.assertNotIn("onclick", r["html"])
        self.assertIn("data-blocked-src", r["html"])
        self.assertTrue(r["images_distantes"])
        r = self.ok("lire", uid=str(u), html=True, images=True)
        self.assertIn(' src="http://t.fr/p.png"', r["html"])

    def test_pieces_jointes(self):
        (u,) = self.ajouter(1, pj=True)
        r = self.ok("lire", uid=str(u))
        self.assertEqual([(p["nom"], p["taille"]) for p in r["pieces"]], [("devis.pdf", 5)])
        p = self.ok("piece", uid=str(u), index=0)
        self.assertEqual((p["nom"], base64.b64decode(p["donnees_b64"])), ("devis.pdf", b"%PDF-"))
        self.assertEqual(self.ex("piece", uid=str(u), index=4)["statut"], "echec")
        self.assertTrue(self.ok("lister")["messages"][0]["pj"])

    def test_un_uid_qui_n_est_pas_un_entier_n_atteint_jamais_le_serveur(self):
        self.ajouter(1)
        self.ok("lister")
        avant = len(self.boite.commandes)
        for uid in ("1;DELETE", "1 UID FETCH 1:*", "x", "", "1,2", "1:*"):
            self.assertEqual(self.ex("lire", uid=uid)["statut"], "echec", uid)
            self.assertEqual(self.ex("drapeau", uids=[uid], champ="seen", valeur=True)["statut"], "echec", uid)
            self.assertEqual(self.ex("deplacer", uids=[uid], destination="Trash")["statut"], "echec", uid)
        self.assertEqual(len(self.boite.commandes), avant)

    def test_un_dossier_inconnu_est_refuse(self):
        self.assertEqual(self.ex("lister", dossier="Inexistant")["statut"], "echec")


class Gestes(Monde):
    def test_drapeau_prouve_et_defait(self):
        a, b = self.ajouter(2, flags=())
        self.flags("INBOX", b).add("\\Flagged")
        r = self.ex("drapeau", uids=[a, b], champ="seen", valeur=True)
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue("\\Seen" in self.flags("INBOX", a) and "\\Seen" in self.flags("INBOX", b))
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.retour("drapeau", r["resultat"])
        self.assertTrue("\\Seen" not in self.flags("INBOX", a) and "\\Seen" not in self.flags("INBOX", b))
        self.assertIn("\\Flagged", self.flags("INBOX", b))                    # un autre drapeau n'est pas touché

    def test_le_retour_d_un_drapeau_respecte_l_etat_d_avant_message_par_message(self):
        a, b = self.ajouter(2, flags=())
        self.flags("INBOX", a).add("\\Seen")
        r = self.ex("drapeau", uids=[a, b], champ="seen", valeur=True)
        self.retour("drapeau", r["resultat"])
        self.assertIn("\\Seen", self.flags("INBOX", a))                      # il était déjà lu : il le reste
        self.assertNotIn("\\Seen", self.flags("INBOX", b))

    def test_un_drapeau_inconnu_est_refuse(self):
        (u,) = self.ajouter(1)
        self.assertEqual(self.ex("drapeau", uids=[u], champ="deleted", valeur=True)["statut"], "echec")

    def test_deplacer_avec_move_puis_retour_par_message_id(self):
        a, b = self.ajouter(2)
        self.boite.ajouter("Trash", message(objet="Déjà là"), ())
        r = self.ex("deplacer", uids=[a], destination="Trash")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["methode"], "MOVE")
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Trash"])), (1, 2))
        self.retour("deplacer", r["resultat"])
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Trash"])), (2, 1))
        self.assertEqual({m["raw"].split(b"Subject: ")[1].split(b"\r\n")[0] for m in self.boite.dossiers["INBOX"]}, {b"Message 1", b"Message 2"})

    def test_deplacer_sans_move_copie_marque_et_expunge(self):
        self.boite.move = False
        (a,) = self.ajouter(1)
        r = self.ex("deplacer", uids=[a], destination="Trash")
        self.assertEqual((r["statut"], r["resultat"]["methode"]), ("faite", "COPY"), r)
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Trash"])), (0, 1))
        self.retour("deplacer", r["resultat"])
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Trash"])), (1, 0))

    def test_deplacer_vers_soi_meme_ou_un_dossier_inconnu_est_refuse(self):
        (a,) = self.ajouter(1)
        self.assertEqual(self.ex("deplacer", uids=[a], destination="INBOX")["statut"], "echec")
        self.assertEqual(self.ex("deplacer", uids=[a], destination="Inconnu")["statut"], "echec")
        self.assertEqual(self.ex("deplacer", uids=[a], destination="")["statut"], "echec")
        self.assertEqual(len(self.boite.dossiers["INBOX"]), 1)

    def test_le_cache_oublie_ce_qui_a_quitte_le_dossier(self):
        a, b = self.ajouter(2)
        self.ok("lister")
        self.ok("deplacer", uids=[a], destination="Trash")
        self.assertEqual([m["uid"] for m in self.ok("lister")["messages"]], [str(b)])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM messages WHERE uid=?", (str(a),))[0]["n"], 0)

    def test_supprimer_va_a_la_corbeille_jamais_a_l_oubli(self):
        (a,) = self.ajouter(1)
        r = self.ex("supprimer", uids=[a])
        self.assertEqual((r["statut"], r["resultat"]["destination"]), ("faite", "Trash"), r)
        self.assertEqual(len(self.boite.dossiers["Trash"]), 1)
        self.retour("supprimer", r["resultat"])
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Trash"])), (1, 0))

    def test_sans_corbeille_on_refuse_au_lieu_d_effacer(self):
        del self.boite.dossiers["Trash"]
        (a,) = self.ajouter(1)
        r = self.ex("supprimer", uids=[a])
        self.assertEqual(r["statut"], "echec")
        self.assertIn("corbeille", json.dumps(r, ensure_ascii=False))
        self.assertEqual(len(self.boite.dossiers["INBOX"]), 1)

    def test_supprimer_depuis_la_corbeille_est_refuse(self):
        (a,) = self.ajouter(1, dossier="Trash")
        self.assertEqual(self.ex("supprimer", uids=[a], dossier="Trash")["statut"], "echec")

    def test_archiver_cree_le_dossier_au_besoin(self):
        (a,) = self.ajouter(1)
        r = self.ex("archiver", uids=[a])
        self.assertEqual((r["statut"], r["resultat"]["destination"]), ("faite", "Archive"), r)
        self.assertEqual(len(self.boite.dossiers["Archive"]), 1)
        self.retour("archiver", r["resultat"])
        self.assertEqual(len(self.boite.dossiers["Archive"]), 0)

    def test_copier_garde_la_source_et_le_retour_retire_les_copies(self):
        a, b = self.ajouter(2)
        r = self.ex("copier", uids=[a], destination="Sent")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Sent"])), (2, 1))
        self.retour("copier", r["resultat"])
        self.assertEqual((len(self.boite.dossiers["INBOX"]), len(self.boite.dossiers["Sent"])), (2, 0))


class Ecrire(Monde):
    def test_un_brouillon_se_prepare_sans_rien_envoyer_et_se_defait(self):
        r = self.ex("brouillon_creer", a="zoe@exemple.fr", objet="Devis", texte="Bonjour Zoé")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(len(self.boite.dossiers["Drafts"]), 1)
        self.assertIn("\\Draft", self.boite.dossiers["Drafts"][0]["flags"])
        self.assertEqual(self.smtp.recus, [])
        self.retour("brouillon_creer", r["resultat"])
        self.assertEqual(len(self.boite.dossiers["Drafts"]), 0)

    def test_sans_dossier_de_brouillons_on_refuse(self):
        del self.boite.dossiers["Drafts"]
        self.assertEqual(self.ex("brouillon_creer", a="zoe@exemple.fr", objet="x", texte="y")["statut"], "echec")

    def test_les_adresses_sont_verifiees(self):
        for a in ("", "pas-une-adresse", "a@b", "zoe@exemple.fr, @x.fr", ",".join("u%d@exemple.fr" % i for i in range(21))):
            self.assertEqual(self.ex("brouillon_creer", a=a, objet="x", texte="y")["statut"], "echec", a)
        self.assertEqual(self.ex("brouillon_creer", a="zoe@exemple.fr", cc="mauvaise", objet="x", texte="y")["statut"], "echec")

    CARTE = {"nom": "Atelier Lumen", "forme": "SAS", "siren": "123456782", "adresse": "12 quai des Chartrons", "cp": "33000", "ville": "Bordeaux", "tel": "0102030405",
             "email": "contact@lumen.test", "web": "https://lumen.test", "signature": "complete"}

    def envoyer_avec_carte(self, carte):
        self.ctx.executer_lecture = lambda cap, **a: carte if cap == "societes.carte" else {"comptes": self.comptes}
        r = self.ex("envoyer", a="zoe@exemple.fr", objet="Devis", texte="Voici le devis")
        self.assertEqual(r["statut"], "faite", r)
        return self.smtp.recus[-1]["raw"].decode()

    def test_la_signature_de_la_societe_ne_s_ajoute_que_si_elle_est_voulue(self):
        self.assertNotIn("Atelier Lumen", self.envoyer_avec_carte(self.CARTE))                  # réglage éteint : rien n'est ajouté
        self.n.reglages.poser("courrier.signature_societe", True, "")
        txt = self.envoyer_avec_carte(self.CARTE)
        self.assertIn("Atelier Lumen SAS", txt)
        self.assertIn("SIREN 123456782", txt)
        self.assertIn("33000 Bordeaux", txt)
        self.assertIn("Voici le devis", txt)
        courte = self.envoyer_avec_carte(dict(self.CARTE, signature="courte"))
        self.assertIn("Atelier Lumen SAS", courte)
        self.assertNotIn("SIREN", courte)                                                        # la courte : le nom et le site seulement
        self.assertIn("https://lumen.test", courte)
        self.assertNotIn("Atelier Lumen", self.envoyer_avec_carte({"nom": ""}))                  # une fiche sans nom : aucune signature

    def test_envoyer_par_smtp_journalise_et_garde_une_copie(self):
        r = self.ex("envoyer", a="zoe@exemple.fr", cc="paul@exemple.fr", objet="Devis", texte="Voici le devis", repond_a_message="<orig@exemple.fr>")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(len(self.smtp.recus), 1)
        recu = self.smtp.recus[0]
        self.assertEqual((recu["de"], recu["a"]), (BEA, ["zoe@exemple.fr", "paul@exemple.fr"]))
        txt = recu["raw"].decode()
        self.assertIn("Subject: Devis", txt)
        self.assertIn("In-Reply-To: <orig@exemple.fr>", txt)
        self.assertIn("Voici le devis", txt)
        self.assertTrue(r["resultat"]["copie_gardee"])
        self.assertEqual(len(self.boite.dossiers["Sent"]), 1)
        j = self.ok("envoyes")["envois"]
        self.assertEqual((j[0]["a"], j[0]["objet"], j[0]["ok"]), ("zoe@exemple.fr", "Devis", 1))

    def test_le_mot_de_passe_smtp_refuse_est_dit_sans_etre_cite_et_consigne(self):
        self.n.reglages.poser("courrier.smtp_mot_de_passe", "mauvais-smtp-secret", BEA)
        r = self.ex("envoyer", a="zoe@exemple.fr", objet="x", texte="y")
        self.assertEqual(r["statut"], "echec")
        self.assertNotIn("mauvais-smtp-secret", json.dumps(r) + json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str))
        j = self.ok("envoyes")["envois"]
        self.assertEqual((j[0]["ok"], "refus" in j[0]["raison"].lower() or "535" in j[0]["raison"] or "auth" in j[0]["raison"].lower()), (0, True))

    def test_le_smtp_reprend_les_identifiants_de_la_boite_quand_ils_ne_sont_pas_donnes(self):
        self.n.reglages.poser("courrier.smtp_mot_de_passe", "", BEA)
        self.smtp.mdp = "mdp-imap"
        self.assertEqual(self.ex("envoyer", a="zoe@exemple.fr", objet="x", texte="y")["statut"], "faite")

    def test_sans_serveur_d_envoi_regle_on_le_dit(self):
        self.n.reglages.poser("courrier.smtp_hote", "", BEA)
        r = self.ex("envoyer", a="zoe@exemple.fr", objet="x", texte="y")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("smtp", json.dumps(r).lower())

    def test_un_agent_ne_fait_jamais_partir_un_courriel(self):
        for acteur in ("cassandra", "itare", "agent", "anonyme"):
            r = self.e("courrier.envoyer", acteur, {"a": "zoe@exemple.fr", "objet": "x", "texte": "y"}, compte=BEA)
            self.assertEqual(r["statut"], "refuse", acteur)
        self.assertEqual(self.smtp.recus, [])

    def test_un_agent_peut_preparer_un_brouillon_au_palier_voulu(self):
        r = self.e("courrier.brouillon_creer", "itare", {"a": "zoe@exemple.fr", "objet": "x", "texte": "y"}, compte=BEA)
        self.assertEqual(r["statut"], "racontee")
        self.assertEqual(len(self.boite.dossiers["Drafts"]), 0)

    def test_l_envoi_est_de_risque_eleve_et_n_atteint_pas_le_palier_maitre(self):
        self.assertNotIn("maitre", self.n.catalogue.get("courrier.envoyer").capacite.paliers)


class Passe(Monde):
    def passe(self):
        self.n.lancer("courrier.passe")

    def test_la_passe_garde_les_en_tetes_les_textes_et_les_compteurs(self):
        self.ajouter(3, flags=())
        self.boite.ajouter("Sent", message(objet="Parti", de=BEA), ("\\Seen",))
        self.passe()
        e = self.ok("etat")
        self.assertEqual((e["configuree"], e["non_lus"], e["passe"]["nouveaux"], e["passe"]["erreur"]), (True, 3, 3, ""))
        self.assertEqual((e["gardes"]["total"], e["gardes"]["avec_texte"]), (3, 3))
        self.assertEqual(len(e["recents"]), 3)
        self.assertEqual(e["recents"][0]["apercu"], "Le texte")
        self.assertEqual({d["nom"]: d["role"] for d in e["dossiers"]}["Sent"], "sent")
        self.assertEqual(len(self.evts("courrier.nouveau")), 3)
        n = self.ctx.stockage.lire("SELECT COUNT(*) n FROM messages WHERE dossier='Sent'")[0]["n"]
        self.assertEqual(n, 1)

    def test_un_message_deja_vu_n_est_pas_annonce_deux_fois(self):
        self.ajouter(2, flags=())
        self.passe()
        self.passe()
        self.assertEqual(len(self.evts("courrier.nouveau")), 2)
        self.ajouter(1, flags=(), objet="Encore")
        self.passe()
        self.assertEqual(len(self.evts("courrier.nouveau")), 3)

    def test_ce_qui_a_disparu_du_serveur_sort_du_cache(self):
        a, b = self.ajouter(2, flags=())
        self.passe()
        self.boite.dossiers["INBOX"] = [m for m in self.boite.dossiers["INBOX"] if m["uid"] != a]
        self.passe()
        self.assertEqual([r["uid"] for r in self.ctx.stockage.lire("SELECT uid FROM messages WHERE dossier='INBOX'")], [str(b)])

    def test_les_textes_sont_relus_par_lots_bornes(self):
        self.n.reglages.poser("courrier.lot_corps", 5)
        self.ajouter(12, flags=())
        self.passe()
        self.assertEqual(self.ok("etat")["gardes"]["avec_texte"], 5)
        self.passe()
        self.assertEqual(self.ok("etat")["gardes"]["avec_texte"], 10)

    def test_les_messages_trop_vieux_perdent_leur_texte_mais_gardent_leur_en_tete(self):
        self.boite.ajouter("INBOX", message(objet="Ancien", date="Mon, 05 Jan 2015 10:00:00 +0000"), ())
        self.ajouter(1, flags=(), objet="Recent")
        self.n.reglages.poser("courrier.jours_gardes", 30)
        self.passe()
        lignes = {r["objet"]: r for r in self.ctx.stockage.lire("SELECT objet, texte FROM messages")}
        self.assertEqual(lignes["Ancien"]["texte"], "")

    def test_une_boite_en_panne_donne_un_constat_visible_de_son_seul_compte(self):
        self.n.reglages.poser("courrier.imap_mot_de_passe", "mauvais", BEA)
        self.passe()
        self.assertIn("connexion IMAP échouée", self.ok("etat")["passe"]["erreur"])
        self.n.tick()
        c = [e for e in self.evts("constat.ouvert") if "boîte mail" in e["donnees"]["titre"]]
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["compte"], BEA)

    def test_la_passe_est_independante_par_compte(self):
        boite2 = Boite(LEO, "mdp-leo")
        imap2 = ServeurImap(boite2)
        self.addCleanup(imap2.arreter)
        self.reglages_de(LEO, "127.0.0.1", imap2.port, LEO, "mauvais")
        self.ajouter(2, flags=())
        self.passe()
        self.assertEqual(self.ok("etat", compte=BEA)["non_lus"], 2)
        self.assertNotEqual(self.ok("etat", compte=LEO)["passe"]["erreur"], "")
        self.assertEqual(self.ok("etat", compte=BEA)["passe"]["erreur"], "")

    def test_un_compte_sans_boite_est_ignore_par_la_passe(self):
        self.passe()
        self.assertEqual(self.ctx.stockage.lire("SELECT compte FROM passes"), [{"compte": BEA}])


class Secrets(Monde):
    def test_les_mots_de_passe_sont_chiffres_et_absents_du_journal_et_des_resultats(self):
        self.ajouter(1)
        self.ok("lister")
        self.ex("envoyer", a="zoe@exemple.fr", objet="x", texte="y")
        brut = json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str)
        for secret in ("mdp-imap", "mdp-smtp"):
            self.assertNotIn(secret, brut)
            self.assertNotIn(secret.encode(), (Path(self.tmp.name) / "d" / "noyau.db").read_bytes())
        lignes = {l["cle"]: l["valeur"] for l in self.n.reglages.liste("courrier", BEA)}
        self.assertEqual(lignes["courrier.imap_mot_de_passe"], "***")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Connexion, Dossiers, Messages, Gestes, Ecrire, Passe, Secrets
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
