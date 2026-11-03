# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des messages en cours et programmés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #becd38
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des messages en cours et programmés : enregistrement, envoi à la main, départ programmé, cloisonnement.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=becd38 ▼▼▼
"""Bancs des messages : un message se rédige et se relit sans rien envoyer, il part à la main (le courrier ne reçoit qu'un numéro, l'adresse est celle enregistrée),
il peut être programmé pour partir seul (la minuterie), un message tiré d'un courrier reçu ne part jamais seul, et personne ne voit les messages d'un autre.
Un vrai noyau, les modules messages et courrier, un serveur IMAP et un serveur SMTP de poche."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_main as moteur                                  # noqa: E402
from CN_faux_serveurs_courrier import Boite, ServeurImap, ServeurSmtp   # noqa: E402

BEA, CAM = "bea@x.fr", "cam@x.fr"
MODULES = ("droits", "comptes", "contacts", "courrier", "notifications", "taches", "messages")


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
        for m in MODULES:
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in MODULES:
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.assertEqual(self.n.recharger()["refuses"], [])
        self.n.droits.regler_admin(BEA, True)
        r = self.n.reglages
        r.poser("courrier.imap_hote", "127.0.0.1", BEA)
        r.poser("courrier.imap_port", self.imap.port, BEA)
        r.poser("courrier.imap_chiffre", False, BEA)
        r.poser("courrier.imap_identifiant", BEA, BEA)
        r.poser("courrier.imap_mot_de_passe", "mdp-imap", BEA)
        r.poser("courrier.smtp_hote", "127.0.0.1", BEA)
        r.poser("courrier.smtp_port", self.smtp.port, BEA)
        r.poser("courrier.smtp_mot_de_passe", "mdp-smtp", BEA)
        self.ctx = self.n.executeur.contextes["messages"]
        self.base = self.ctx.stockage

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(cap, acteur, args, compte=compte)

    def ok(self, cap, **args):
        r = self.ex(cap, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def message(self, **kw):
        d = dict(to="lea@exemple.fr", subject="Bonjour", body="Votre dossier est prêt.")
        d.update(kw)
        return self.ok("messages.save", **d)["id"]

    def etat(self, mid):
        return self.base.lire("SELECT * FROM messages WHERE id=?", (mid,))[0]

    def minuterie(self):
        next(f for (_m, mo, f) in self.ctx._moteurs if mo.id == "minuterie")(self.ctx)


class Redaction(Monde):
    def test_un_message_s_enregistre_et_dit_ce_qui_manque(self):
        r = self.ok("messages.save", to="", subject="", body="")
        self.assertEqual(r["manque"], ["un destinataire", "un objet", "un texte"])
        mid = self.message()
        liste = self.ok("messages.liste")
        self.assertEqual([m["id"] for m in liste["prets"]], [mid])
        self.assertEqual(len(liste["a_finir"]), 1)
        self.assertEqual(self.smtp.recus, [])                                    # rédiger n'envoie rien

    def test_une_adresse_fausse_est_dite_a_finir(self):
        self.message(to="pas-une-adresse")
        self.assertEqual(len(self.ok("messages.liste")["a_finir"]), 1)

    def test_les_messages_sont_a_leur_personne(self):
        mid = self.message()
        self.assertEqual(self.ok("messages.liste", compte=CAM)["total"], 0)
        self.assertNotEqual(self.ex("messages.voir", compte=CAM, id=mid)["statut"], "faite")
        self.assertNotEqual(self.ex("messages.supprimer", compte=CAM, id=mid)["statut"], "faite")
        self.assertNotEqual(self.ex("messages.programmer", compte=CAM, id=mid, quand="2030-01-01 10:00")["statut"], "faite")

    def test_enregistrer_et_supprimer_se_defont(self):
        res = self.ex("messages.save", to="lea@exemple.fr", subject="a", body="b")
        mid = res["resultat"]["id"]
        self.n.catalogue.get("messages.save").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.base.lire("SELECT COUNT(*) AS n FROM messages")[0]["n"], 0)
        mid = self.message()
        sup = self.ex("messages.supprimer", id=mid)
        self.assertEqual(sup["statut"], "faite", sup)
        self.assertEqual(self.ok("messages.liste")["total"], 0)
        self.n.catalogue.get("messages.supprimer").defaire(self.ctx, sup["resultat"])
        self.assertEqual(self.ok("messages.liste")["total"], 1)

    def test_les_destinataires_viennent_du_carnet_de_la_personne(self):
        self.ok("contacts.creer", display_name="Léa Martin", emails=["lea@exemple.fr"])
        r = self.ok("messages.destinataires", q="Léa")
        self.assertEqual([c["addr"] for c in r["contacts"]], ["lea@exemple.fr"])
        self.assertEqual(self.ok("messages.destinataires", compte=CAM, q="Léa")["contacts"], [])


class Envoi(Monde):
    def poster(self, mid):
        self.ok("messages.preparer_envoi", id=mid)
        p = self.ok("courrier.envoyer_programme", message=mid)
        self.ok("messages.sortie", id=mid, message_id=p["message_id"])
        return p

    def test_l_envoi_a_la_main_poste_ce_qui_est_enregistre(self):
        mid = self.message()
        self.poster(mid)
        self.assertEqual(self.etat(mid)["etat"], "envoye")
        self.assertEqual(len(self.smtp.recus), 1)
        self.assertEqual(self.smtp.recus[0]["a"], ["lea@exemple.fr"])
        self.assertIn(b"dossier est pr", self.smtp.recus[0]["raw"])
        self.assertEqual(self.ok("messages.liste")["total"], 0)                  # parti : ce n'est plus un message en cours

    def test_le_courrier_ne_poste_pas_un_message_qui_n_est_pas_en_partance(self):
        mid = self.message()
        self.assertNotEqual(self.ex("courrier.envoyer_programme", message=mid)["statut"], "faite")
        self.assertEqual(self.smtp.recus, [])

    def test_un_message_incomplet_ne_se_met_pas_en_partance(self):
        mid = self.message(subject="")
        self.assertNotEqual(self.ex("messages.preparer_envoi", id=mid)["statut"], "faite")

    def test_un_envoi_en_echec_laisse_le_message_intact(self):
        mid = self.message()
        self.ok("messages.preparer_envoi", id=mid)
        self.smtp.arreter()
        r = self.ex("courrier.envoyer_programme", message=mid)
        self.assertNotEqual(r["statut"], "faite")
        self.ok("messages.sortie", id=mid, erreur="envoi impossible")
        self.assertEqual(self.etat(mid)["etat"], "echec")
        self.assertEqual(self.etat(mid)["corps"], "Votre dossier est prêt.")
        self.assertEqual(self.ok("messages.liste")["total"], 1)                  # il reste à reprendre


class Programme(Monde):
    def test_la_minuterie_fait_partir_un_message_programme(self):
        self.n.catalogue.regler_palier("courrier.envoyer_programme", "auto")
        mid = self.message()
        self.ok("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.assertEqual(self.etat(mid)["etat"], "programme")
        self.minuterie()
        self.assertEqual(self.etat(mid)["etat"], "programme")                    # l'heure n'est pas venue
        self.base.ecrire("UPDATE messages SET quand=? WHERE id=?", (time.time() - 60, mid))
        self.minuterie()
        self.assertEqual(self.etat(mid)["etat"], "envoye")
        self.assertEqual(len(self.smtp.recus), 1)
        self.minuterie()
        self.assertEqual(len(self.smtp.recus), 1)                                # il ne part pas deux fois

    def test_modifier_un_message_programme_retire_la_programmation(self):
        self.n.catalogue.regler_palier("courrier.envoyer_programme", "auto")
        mid = self.message()
        self.ok("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.ok("messages.save", id=mid, to="lea@exemple.fr", subject="Autre", body="Autre texte.")
        self.assertEqual(self.etat(mid)["etat"], "brouillon")
        self.base.ecrire("UPDATE messages SET quand=? WHERE id=?", (time.time() - 60, mid))
        self.minuterie()
        self.assertEqual(self.smtp.recus, [])

    def test_la_programmation_se_retire_et_se_defait(self):
        mid = self.message()
        res = self.ex("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.assertEqual(res["statut"], "faite", res)
        self.n.catalogue.get("messages.programmer").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.etat(mid)["etat"], "brouillon")
        self.ok("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.ok("messages.programmer", id=mid, quand="")
        self.assertEqual(self.etat(mid)["etat"], "brouillon")

    def test_un_message_tire_d_un_courrier_recu_ne_part_jamais_seul(self):
        mid = self.message(teinte="courrier de pirate@x.fr")
        r = self.ex("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.assertNotEqual(r["statut"], "faite")
        self.assertEqual(self.etat(mid)["etat"], "brouillon")

    def test_le_palier_raconter_ne_laisse_rien_partir_seul(self):
        mid = self.message()
        self.ok("messages.programmer", id=mid, quand="2030-01-01 10:00")
        self.base.ecrire("UPDATE messages SET quand=? WHERE id=?", (time.time() - 60, mid))
        self.minuterie()                                                          # le palier de la capacité n'est pas « auto » : rien ne part
        self.assertEqual(self.smtp.recus, [])
        self.assertEqual(self.etat(mid)["etat"], "echec")
        self.assertIn("ne part pas seul", self.etat(mid)["erreur"])

    def test_une_date_illisible_ou_un_message_incomplet_sont_refuses(self):
        mid = self.message()
        self.assertNotEqual(self.ex("messages.programmer", id=mid, quand="demain")["statut"], "faite")
        vide = self.message(subject="")
        self.assertNotEqual(self.ex("messages.programmer", id=vide, quand="2030-01-01 10:00")["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Redaction, Envoi, Programme
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
