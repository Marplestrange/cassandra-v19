# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 9
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #f1233c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 9 : le QR code en Python (vecteurs de référence), le billet en PDF (structure, une page par billet, accents), son téléchargement par jeton, et la pièce jointe du courriel de confirmation.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f1233c ▼▼▼
"""Bancs de la billetterie, lot 9 : le QR code en Python (vecteurs de référence), le billet en PDF (structure, une page par billet, accents), son téléchargement par jeton, et la pièce jointe du courriel de confirmation."""
import base64
import hashlib
import importlib
import importlib.util
import socketserver
import sys
import threading
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402


def empreinte(mat):
    return hashlib.sha256("\n".join("".join("1" if c else "0" for c in r) for r in mat).encode()).hexdigest()[:20]


class QrPython(unittest.TestCase):
    """Les empreintes viennent de la bibliothèque de référence `qrcode` (niveau M, masque imposé) : le dessin du billet imprimé ne dérive pas."""

    def setUp(self):
        racine = RACINE / "modules" / "billetterie"
        sp = importlib.util.spec_from_file_location("cassandra_module_billetterie_qr", racine / "CN_module.py", submodule_search_locations=[str(racine)])
        mod = importlib.util.module_from_spec(sp)
        sys.modules["cassandra_module_billetterie_qr"] = mod
        self.addCleanup(sys.modules.pop, "cassandra_module_billetterie_qr", None)
        sp.loader.exec_module(mod)
        self.qr = importlib.import_module("cassandra_module_billetterie_qr.CN_qrcode")
        self.pdf = importlib.import_module("cassandra_module_billetterie_qr.CN_pdf")

    def test_les_matrices_sont_celles_de_la_reference(self):
        for texte, masque, attendu in (("cass1.a-0011.wpawej", 0, "a7ab1e0a0cdf132c6bb5"), ("cass1.a-0011.wpawej", 5, "5c0717eb5671a1f2b6cd"), ("x" * 100, 0, "898a791db8daf87950e6"), ("x" * 100, 5, "103b849692b0e6f972b0")):
            self.assertEqual(empreinte(self.qr.matrice(texte, masque)), attendu, (texte[:10], masque))

    def test_la_taille_suit_la_version(self):
        self.assertEqual(len(self.qr.matrice("a")), 21)
        self.assertEqual(len(self.qr.matrice("CASS1.A-0011.WPAWEJ")), 25)
        with self.assertRaises(ValueError):
            self.qr.matrice("z" * 300)

    def test_les_dates_s_ecrivent_en_francais(self):
        self.assertEqual(self.pdf.date_longue("2026-12-12"), "samedi 12 décembre 2026")
        self.assertEqual(self.pdf.date_longue(""), "Date à venir")

    def test_un_pdf_sans_billet_est_refuse(self):
        with self.assertRaises(ValueError):
            self.pdf.billets_pdf([])

    def test_les_caracteres_speciaux_ne_cassent_pas_le_pdf(self):
        b = {"evenement": "Soirée (été) \\ 100 % « Folk »", "date": "2026-12-12", "numero": "A-0001", "code": "A-0001-ABCDEF", "qr": "CASS1.A-0001.ABCDEF", "nom": "Zoë Ñandú ☃"}
        data = self.pdf.billets_pdf([b])
        self.assertTrue(data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"startxref", data)


class Billets(Boutique):
    def setUp(self):
        super().setUp()
        self.n.reglages.poser("billetterie.titulaire_nom", "Maison Bohème", "")
        self.n.reglages.poser("billetterie.titulaire_mail", "contact@exemple.fr", "")

    def payee(self, n=2):
        c = self.commander(n)
        self.ok("commande_encaisser", ref=c["commande"], moyen="stripe", reference_externe="pi_" + c["commande"])
        return c

    @staticmethod
    def pages(pdf):
        return pdf.count(b"/Type /Page /Parent")


class Telechargement(Billets):
    def test_le_client_telecharge_un_pdf_d_une_page_par_billet(self):
        c = self.payee(3)
        r = self.pub_ok("public_billets_pdf", commande=c["commande"], suivi=c["suivi"])
        data = base64.b64decode(r["pdf"])
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual((r["billets"], self.pages(data), r["nom"]), (3, 3, "billets-%s.pdf" % c["commande"]))

    def test_le_qr_du_pdf_est_celui_de_l_ecran(self):
        c = self.payee(1)
        ecran = self.pub_ok("public_suivre", commande=c["commande"], suivi=c["suivi"])["billets"][0]
        cle = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        with self.ctx.stockage.transaction() as tx:
            d = self.mod.CN_ventes.donnees_pdf(self.ctx, tx, cle, dict(tx.execute("SELECT * FROM commandes WHERE ref = ?", (c["commande"],)).fetchone()))
        self.assertEqual((d[0]["qr"], d[0]["code"], d[0]["numero"]), (ecran["qr"], ecran["code_controle"], ecran["numero"]))
        self.assertEqual((d[0]["organisateur"], d[0]["evenement"], d[0]["type"]), ("Maison Bohème", "Soirée d'hiver", "Plein tarif"))

    def test_il_faut_le_bon_jeton_et_une_commande_payee(self):
        c = self.commander(1)
        self.assertIn("payée", self.pub_echec("public_billets_pdf", commande=c["commande"], suivi=c["suivi"]))
        self.assertIn("introuvable", self.pub_echec("public_billets_pdf", commande=c["commande"], suivi="faux"))

    def test_les_billets_annules_ne_sont_pas_imprimes(self):
        c = self.payee(2)
        self.ok("commande_rembourser", ref=c["commande"], motif="x")
        self.assertIn("payée", self.pub_echec("public_billets_pdf", commande=c["commande"], suivi=c["suivi"]))

    def test_le_titulaire_a_le_meme_pdf(self):
        c = self.payee(2)
        r = self.ok("commande_pdf", ref=c["commande"])
        self.assertEqual((r["billets"], self.pages(base64.b64decode(r["pdf"]))), (2, 2))


class PieceJointe(Billets):
    def setUp(self):
        super().setUp()
        self.cc = self.mod.CN_courriels
        self.recus = []

        def faux(hote, port, securite, identifiant, mdp, de, a, objet, corps, pieces=None):
            self.recus.append((a, objet, pieces or []))
        self.cc.ENVOI["smtp"] = faux
        self.addCleanup(self.cc.ENVOI.clear)
        for cle, val in (("courriels_actifs", True), ("courriels_hote", "smtp.exemple.fr"), ("courriels_expediteur", "billets@exemple.fr")):
            self.n.reglages.poser("billetterie." + cle, val, "")

    def expedier(self):
        return self.cc.expedier_lot(self.ctx, self.ctx.stockage)

    def test_la_confirmation_part_avec_les_billets_en_pdf(self):
        self.payee(3)
        self.expedier()
        a, objet, pieces = [x for x in self.recus if "Vos billets" in x[1]][0]
        self.assertEqual(len(pieces), 1)
        nom, type_, octets = pieces[0]
        self.assertEqual((type_, nom.endswith(".pdf"), octets[:4], self.pages(octets)), ("application/pdf", True, b"%PDF", 3))

    def test_un_billet_rembourse_avant_l_envoi_ne_part_pas(self):
        c = self.payee(2)
        self.ok("commande_rembourser", ref=c["commande"], motif="x")
        self.expedier()
        self.assertEqual([x[2] for x in self.recus if "Vos billets" in x[1]], [[]])

    def test_les_autres_courriels_n_ont_pas_de_piece_jointe(self):
        self.pub_ok("public_compte_lien", mail="x@exemple.org", ip="203.0.113.3")
        self.expedier()
        self.assertEqual([x[2] for x in self.recus if "lien de connexion" in x[1]], [[]])


class SmtpAvecPiece(unittest.TestCase):
    """Le vrai transport : un courriel MIME avec son PDF joint arrive chez un petit serveur de banc."""

    def test_le_pdf_arrive_en_piece_jointe(self):
        recu = []

        class H(socketserver.StreamRequestHandler):
            def handle(self):
                w = lambda t: self.wfile.write((t + "\r\n").encode())
                w("220 banc")
                data, msg = False, []
                for brut in self.rfile:
                    l = brut.decode("latin-1").rstrip("\r\n")
                    if data:
                        if l == ".":
                            data = False
                            recu.append("\n".join(msg))
                            w("250 ok")
                        else:
                            msg.append(l)
                        continue
                    u = l.upper()
                    if u == "DATA":
                        data = True
                        w("354 go")
                    elif u == "QUIT":
                        w("221 bye")
                        return
                    else:
                        w("250 ok")
        srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        racine = RACINE / "modules" / "billetterie"
        sp = importlib.util.spec_from_file_location("cassandra_module_billetterie_pj", racine / "CN_module.py", submodule_search_locations=[str(racine)])
        mod = importlib.util.module_from_spec(sp)
        sys.modules["cassandra_module_billetterie_pj"] = mod
        self.addCleanup(sys.modules.pop, "cassandra_module_billetterie_pj", None)
        sp.loader.exec_module(mod)
        cc = importlib.import_module("cassandra_module_billetterie_pj.CN_courriels")
        pdf = importlib.import_module("cassandra_module_billetterie_pj.CN_pdf")
        data = pdf.billets_pdf([{"evenement": "Soirée", "date": "2026-12-12", "numero": "A-0001", "code": "A-0001-ABCDEF", "qr": "CASS1.A-0001.ABCDEF"}])
        cc.envoyer_smtp("127.0.0.1", srv.server_address[1], "aucune", "", "", "a@exemple.fr", "b@exemple.fr", "Vos billets", "Bonjour", pieces=[("billets.pdf", "application/pdf", data)])
        txt = recu[-1]
        self.assertIn("Content-Type: application/pdf", txt)
        self.assertIn('filename="billets.pdf"', txt)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : empreinte, QrPython, Billets, Telechargement, PieceJointe, SmtpAvecPiece
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
