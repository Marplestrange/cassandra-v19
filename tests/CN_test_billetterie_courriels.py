# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 7
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #262e71
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 7 : l'envoi réel des courriels (activation, nouvelles tentatives, frein, transport SMTP vrai contre un petit serveur de banc).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=262e71 ▼▼▼
"""Bancs de la billetterie, lot 7 : l'envoi réel des courriels (activation, nouvelles tentatives, frein, transport SMTP vrai contre un petit serveur de banc)."""
import socketserver
import sys
import threading
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402

MDP = "motdepasse-secret-42"


class Courriels(Ventes):
    def setUp(self):
        super().setUp()
        self.cc = self.mod.CN_courriels
        self.envoyes = []
        self.panne = []
        self.cc.ENVOI["smtp"] = self.faux
        self.addCleanup(self.cc.ENVOI.clear)
        self.vendre(1)                                        # une confirmation part en boîte d'envoi

    def faux(self, hote, port, securite, identifiant, mdp, de, a, objet, corps, pieces=None):
        self.pieces = pieces or []
        if self.panne:
            raise RuntimeError(self.panne[0])
        self.envoyes.append((hote, port, securite, identifiant, de, a, objet))

    def regler(self, **k):
        d = dict(courriels_actifs=True, smtp_hote="smtp.exemple.fr", smtp_identifiant="billets@exemple.fr", smtp_mot_de_passe=MDP, smtp_expediteur="Maison Bohème <billets@exemple.fr>")
        d.update(k)
        for cle, val in d.items():
            self.n.reglages.poser("billetterie." + cle, val, "")

    def lot(self):
        return self.cc.expedier_lot(self.ctx, self.ctx.stockage)

    def etats(self):
        return [x["etat"] for x in self.ok("courriels")["courriels"]]


class Envoi(Courriels):
    def test_rien_ne_part_tant_que_l_envoi_n_est_pas_active(self):
        self.assertIn("pas activé", self.lot()["raison"])
        self.assertEqual((self.envoyes, self.etats()), ([], ["a_envoyer"]))

    def test_sans_serveur_regle_rien_ne_part_et_on_dit_pourquoi(self):
        self.n.reglages.poser("billetterie.courriels_actifs", True, "")
        self.assertIn("pas réglé", self.lot()["raison"])

    def test_active_et_regle_le_courriel_part_et_la_boite_le_sait(self):
        self.regler()
        r = self.lot()
        self.assertEqual((r["envoyes"], r["echecs"]), (1, 0))
        hote, port, sec, ident, de, a, objet = self.envoyes[0]
        self.assertEqual((hote, port, sec, de, a), ("smtp.exemple.fr", 587, "starttls", "Maison Bohème <billets@exemple.fr>", "sophie@exemple.org"))
        self.assertIn("Vos billets", objet)
        self.assertEqual(self.etats(), ["envoye"])
        self.assertEqual(self.lot()["envoyes"], 0)                      # une seule fois

    def test_l_expediteur_est_par_defaut_l_adresse_du_titulaire(self):
        self.regler(smtp_expediteur="")
        self.n.reglages.poser("billetterie.titulaire_mail", "contact@exemple.fr", "")
        self.lot()
        self.assertEqual(self.envoyes[0][4], "contact@exemple.fr")


class Pannes(Courriels):
    def test_un_echec_est_retente_plus_tard_et_ne_montre_jamais_le_mot_de_passe(self):
        self.regler()
        self.panne.append("535 authentification refusée pour %s avec %s" % ("billets@exemple.fr", MDP))
        r = self.lot()
        self.assertEqual((r["envoyes"], r["reportes"]), (0, 1))
        m = self.ok("courriels")["courriels"][0]
        self.assertEqual((m["etat"], m["essais"]), ("a_envoyer", 1))
        self.assertNotIn(MDP, m["erreur"])
        self.assertIn("***", m["erreur"])
        self.assertEqual(self.lot()["reportes"], 0)                     # pas encore dû
        self.avance(301)
        self.panne.clear()
        self.assertEqual(self.lot()["envoyes"], 1)

    def test_apres_cinq_echecs_le_courriel_passe_en_echec_et_se_relance(self):
        self.regler()
        self.panne.append("serveur injoignable")
        for i in range(5):
            self.lot()
            self.avance(300 * 2 ** i + 1)
        self.assertEqual(self.etats(), ["echec"])
        i = self.ok("courriels")["courriels"][0]["id"]
        r = self.ok("courriel_relancer", id=i)
        self.assertEqual(self.etats(), ["a_envoyer"])
        self.defaire("courriel_relancer", r)
        self.assertEqual(self.etats(), ["echec"])
        self.assertIn("introuvable", self.echec("courriel_relancer", id=i + 99))

    def test_le_frein_envois_arrete_tout(self):
        self.regler()
        self.ctx.frein_actif = lambda nom: nom == "envois"
        self.assertIn("frein", self.lot()["raison"])
        self.assertEqual(self.envoyes, [])
        self.assertTrue(self.ok("courriels_etat")["frein_envois"])


class Capacites(Courriels):
    def test_l_etat_dit_ou_en_est_l_envoi(self):
        e = self.ok("courriels_etat")
        self.assertEqual((e["actif"], e["serveur_regle"], e["a_envoyer"]), (False, False, 1))
        self.regler()
        self.assertEqual(self.ok("courriels_etat")["serveur_regle"], True)

    def test_la_capacite_envoie_comme_le_moteur(self):
        self.regler()
        self.assertEqual(self.ok("courriels_envoyer")["envoyes"], 1)


class Smtp(unittest.TestCase):
    """Le vrai transport contre un petit serveur SMTP de banc : l'en-tête, l'encodage, la connexion sans chiffrement permise seulement sans mot de passe."""

    @classmethod
    def setUpClass(cls):
        recu = cls.recu = []

        class Gestionnaire(socketserver.StreamRequestHandler):
            def handle(self):
                w = lambda t: self.wfile.write((t + "\r\n").encode())
                w("220 banc ESMTP")
                msg, data = [], False
                for brut in self.rfile:
                    l = brut.decode("utf-8", "replace").rstrip("\r\n")
                    if data:
                        if l == ".":
                            data = False
                            recu.append("\n".join(msg))
                            w("250 ok")
                        else:
                            msg.append(l)
                        continue
                    u = l.upper()
                    if u.startswith("EHLO") or u.startswith("HELO"):
                        w("250 banc")
                    elif u.startswith("MAIL") or u.startswith("RCPT"):
                        w("250 ok")
                    elif u == "DATA":
                        data = True
                        w("354 go")
                    elif u == "QUIT":
                        w("221 bye")
                        return
                    else:
                        w("250 ok")

        cls.srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Gestionnaire)
        cls.srv.daemon_threads = True
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def charger(self):
        import importlib.util as u
        racine = RACINE / "modules" / "billetterie"
        sp = u.spec_from_file_location("cassandra_module_billetterie_smtp", racine / "CN_module.py", submodule_search_locations=[str(racine)])
        mod = u.module_from_spec(sp)
        sys.modules["cassandra_module_billetterie_smtp"] = mod
        self.addCleanup(sys.modules.pop, "cassandra_module_billetterie_smtp", None)
        sp.loader.exec_module(mod)
        import importlib
        return importlib.import_module("cassandra_module_billetterie_smtp.CN_courriels")

    def test_un_courriel_part_vraiment_avec_ses_en_tetes_et_son_accent(self):
        cc = self.charger()
        cc.envoyer_smtp("127.0.0.1", self.port, "aucune", "", "", "Maison Bohème <billets@exemple.fr>", "sophie@exemple.org", "Vos billets · Soirée", "Bonjour Sophie,\nÀ bientôt !")
        txt = self.recu[-1]
        self.assertIn("To: sophie@exemple.org", txt)
        self.assertIn("Subject:", txt)
        self.assertIn("Message-ID:", txt)

    def test_jamais_de_mot_de_passe_sans_chiffrement_hors_boucle_locale(self):
        cc = self.charger()
        with self.assertRaises(ValueError):
            cc.envoyer_smtp("smtp.exemple.fr", 25, "aucune", "billets", "secret", "a@exemple.fr", "b@exemple.fr", "x", "y")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Courriels, Envoi, Pannes, Capacites, Smtp
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
