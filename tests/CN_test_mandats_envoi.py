# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'envoi par mandat
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #382b6b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'envoi par mandat : destinataire déréférencé, accord, courrier qui ne poste que la file, minuterie.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=382b6b ▼▼▼
"""Bancs de l'envoi par mandat : le destinataire déréférencé depuis le carnet, l'accord d'un humain, le courrier qui ne poste que ce que la file contient, la minuterie.
Un vrai noyau, les modules mandats, courrier et contacts, un serveur IMAP et un serveur SMTP de poche."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_main as moteur                                  # noqa: E402
from CN_faux_serveurs_courrier import Boite, ServeurImap, ServeurSmtp   # noqa: E402

BEA = "bea@x.fr"
MODULES = ("droits", "comptes", "contacts", "courrier", "mandats")


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
        self.ctx = self.n.executeur.contextes["mandats"]
        self.base = self.ctx.stockage
        self.fiche = self.ex("contacts.creer", display_name="Léa Martin", emails=["lea@exemple.fr"], company="Atelier Lune")

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        r = self.n.executeur.executer(cap, acteur, args, compte=compte)
        return r

    def ok(self, cap, **args):
        r = self.ex(cap, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def mandat(self, **kw):
        d = dict(nom="Relance", declencheurs=["chat"], dst_source="document", objet="Bonjour {{prenom}}", corps="Bonjour {{prenom}}, votre dossier est prêt.",
                 variables=[{"nom": "prenom", "type": "texte", "source": "fiche"}], controle="accord", quota_jour=5, heure_debut="00:00", heure_fin="23:59")
        d.update(kw)
        return self.ok("mandats.save", **d)["id"]

    def etat(self, eid):
        return self.base.lire("SELECT * FROM mandat_envois WHERE id=?", (eid,))[0]


class Destinataire(Monde):
    def test_l_adresse_vient_de_la_fiche_jamais_de_la_demande(self):
        mid = self.mandat()
        r = self.ok("mandats.essai", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["destinataires"], ["lea@exemple.fr"])
        self.assertEqual(r["objet"], "Bonjour Léa")
        self.assertIn("fiche", r["via"])
        pirate = self.ok("mandats.essai", mandat=str(mid), contexte={"destinataire": "pirate@x.fr"})
        self.assertFalse(pirate["ok"])
        self.assertEqual(pirate["refus"], "destinataire")
        inconnu = self.ok("mandats.essai", mandat=str(mid), contexte={"reference": "pirate@x.fr"})
        self.assertFalse(inconnu["ok"])
        self.assertIn("n'invente pas d'adresse", inconnu["reason"])

    def test_une_liste_fermee_ignore_l_adresse_donnee(self):
        mid = self.mandat(nom="Liste", dst_source="liste", dst_valeur="compta@exemple.fr", variables=[], objet="Facture", corps="Voici.")
        r = self.ok("mandats.essai", mandat=str(mid), contexte={"destinataire": "pirate@x.fr"})
        self.assertEqual(r["destinataires"], ["compta@exemple.fr"])

    def test_une_variable_ne_peut_pas_porter_une_adresse(self):
        mid = self.mandat(nom="Var", dst_source="liste", dst_valeur="compta@exemple.fr", objet="Facture", corps="Pour {{qui}}",
                          variables=[{"nom": "qui", "type": "texte", "source": "agent"}])
        r = self.ok("mandats.essai", mandat=str(mid), contexte={"variables": {"qui": "voir www.pirate.fr"}})
        self.assertFalse(r["ok"])
        self.assertEqual(r["refus"], "variables")

    def test_un_essai_ne_met_rien_en_file(self):
        mid = self.mandat()
        self.ok("mandats.essai", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertEqual(self.base.lire("SELECT COUNT(*) AS n FROM mandat_envois")[0]["n"], 0)


class Accord(Monde):
    def declencher(self, mid, **ctx):
        return self.ok("mandats.declencher", mandat=str(mid), contexte=ctx or {"reference": "Léa"})

    def test_l_accord_fait_poster_le_courrier_avec_ce_que_la_file_contient(self):
        mid = self.mandat()
        d = self.declencher(mid)
        self.assertTrue(d["ok"], d)
        self.assertEqual(d["etat"], "attente")
        self.assertEqual(self.smtp.recus, [])                                   # rien ne part sans l'accord
        self.assertEqual(len(self.ok("mandats.envois", etat="attente,differe")["envois"]), 1)
        eid = d["envoi_id"]
        self.ok("mandats.accord", envoi=eid)
        self.assertEqual(self.etat(eid)["etat"], "autorise")
        p = self.ok("courrier.envoyer_mandat", envoi=eid)
        self.ok("mandats.sortie", envoi=eid, message_id=p["message_id"])
        self.assertEqual(self.etat(eid)["etat"], "envoye")
        self.assertEqual(len(self.smtp.recus), 1)
        self.assertEqual(self.smtp.recus[0]["a"], ["lea@exemple.fr"])
        self.assertIn(b"votre dossier est pr", self.smtp.recus[0]["raw"])

    def test_le_courrier_ne_poste_pas_un_envoi_non_autorise(self):
        d = self.declencher(self.mandat())
        r = self.ex("courrier.envoyer_mandat", envoi=d["envoi_id"])
        self.assertEqual(r["statut"], "echec", r)
        self.assertEqual(self.smtp.recus, [])
        self.assertEqual(self.ex("courrier.envoyer_mandat", envoi=999)["statut"], "echec")

    def test_un_agent_ne_donne_pas_l_accord(self):
        d = self.declencher(self.mandat())
        for acteur in ("itare", "cassandra", "agent"):
            self.assertEqual(self.ex("mandats.accord", acteur=acteur, envoi=d["envoi_id"])["statut"], "refuse", acteur)
        self.assertEqual(self.etat(d["envoi_id"])["etat"], "attente")

    def test_annuler_arrete_l_envoi_en_attente(self):
        d = self.declencher(self.mandat())
        self.ok("mandats.annuler", envoi=d["envoi_id"])
        self.assertEqual(self.etat(d["envoi_id"])["etat"], "annule")
        r = self.ex("mandats.annuler", envoi=d["envoi_id"])
        self.assertEqual(r["statut"], "echec")

    def test_un_envoi_identique_ne_part_pas_deux_fois(self):
        mid = self.mandat(unique_par="prenom")
        self.assertTrue(self.declencher(mid)["ok"])
        deux = self.declencher(mid)
        self.assertFalse(deux["ok"])
        self.assertEqual(deux["refus"], "double")

    def test_le_quota_du_jour_borne_les_envois(self):
        mid = self.mandat(quota_jour=1)
        d = self.declencher(mid)
        self.ok("mandats.accord", envoi=d["envoi_id"])
        p = self.ok("courrier.envoyer_mandat", envoi=d["envoi_id"])
        self.ok("mandats.sortie", envoi=d["envoi_id"], message_id=p["message_id"])
        deux = self.declencher(mid)
        self.assertFalse(deux["ok"])
        self.assertEqual(deux["refus"], "quota")

    def test_un_mandat_suspendu_ou_une_origine_inconnue_refuse(self):
        mid = self.mandat()
        self.ok("mandats.suspendre", mid=mid, motif="pause")
        r = self.ok("mandats.essai", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertEqual(r["refus"], "suspendu")
        self.ok("mandats.suspendre", mid=mid, reprendre=True)
        r = self.ok("mandats.declencher", mandat=str(mid), contexte={"reference": "Léa"}, origine="mail_lu")
        self.assertEqual(r["refus"], "origine")
        self.assertEqual(self.base.lire("SELECT suspendu FROM mandats WHERE id=?", (mid,))[0]["suspendu"][:9], "tentative")      # l'incident suspend le mandat


class Automatique(Monde):
    def test_sans_palier_un_mandat_auto_retombe_a_l_accord(self):
        mid = self.mandat(controle="auto")
        d = self.ok("mandats.declencher", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertTrue(d["ok"], d)
        self.assertEqual(d["etat"], "attente")                                  # le courrier est au palier « raconter » : il ne part pas seul
        self.assertEqual(self.smtp.recus, [])

    def test_avec_le_palier_auto_le_mandat_part_seul(self):
        self.n.catalogue.regler_palier("courrier.envoyer_mandat", "auto")
        mid = self.mandat(controle="auto")
        d = self.ok("mandats.declencher", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertEqual(d["etat"], "envoye", d)
        self.assertEqual(len(self.smtp.recus), 1)

    def test_la_minuterie_fait_partir_un_envoi_differe_arretable(self):
        self.n.catalogue.regler_palier("courrier.envoyer_mandat", "auto")
        mid = self.mandat(controle="differe", differe_min=5)
        d = self.ok("mandats.declencher", mandat=str(mid), contexte={"reference": "Léa"})
        self.assertEqual(d["etat"], "differe")
        minuterie = next(f for (_m, mo, f) in self.ctx._moteurs if mo.id == "minuterie")
        minuterie(self.ctx)
        self.assertEqual(self.etat(d["envoi_id"])["etat"], "differe")            # la minuterie n'est pas écoulée
        self.base.ecrire("UPDATE mandat_envois SET part_a=datetime('now','-1 minute') WHERE id=?", (d["envoi_id"],))
        minuterie(self.ctx)
        self.assertEqual(self.etat(d["envoi_id"])["etat"], "envoye")
        self.assertEqual(len(self.smtp.recus), 1)
        autre = self.ok("mandats.declencher", mandat=str(mid), contexte={"reference": "Léa"})
        self.ok("mandats.annuler", envoi=autre["envoi_id"])
        self.base.ecrire("UPDATE mandat_envois SET part_a=datetime('now','-1 minute') WHERE id=?", (autre["envoi_id"],))
        minuterie(self.ctx)
        self.assertEqual(self.etat(autre["envoi_id"])["etat"], "annule")          # arrêté : il ne part pas
        self.assertEqual(len(self.smtp.recus), 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Destinataire, Accord, Automatique
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
