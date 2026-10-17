# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des outils purs du courrier
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #f48469
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des outils purs du courrier : noms de dossiers, en-têtes, classement, et surtout le nettoyage du HTML face aux vecteurs d'attaque connus.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f48469 ▼▼▼
"""Bancs des outils purs du courrier : noms de dossiers, en-têtes, classement, et surtout le nettoyage du HTML face aux vecteurs d'attaque connus."""
import email
import importlib.util
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("courrier_outils", RACINE / "modules" / "courrier" / "CN_outils.py")
o = importlib.util.module_from_spec(spec)
sys.modules["courrier_outils"] = o
spec.loader.exec_module(o)


class Dossiers(unittest.TestCase):
    def test_utf7_aller_retour(self):
        for nom in ("envoyés", "Brouillons", "Éléments supprimés", "日本語", "A&B", "a/b é/c"):
            self.assertEqual(o.utf7_decoder(o.utf7_encoder(nom)), nom, nom)
        self.assertEqual(o.utf7_encoder("envoyés"), "envoy&AOk-s")
        self.assertEqual(o.utf7_decoder("envoy&AOk-s"), "envoyés")
        self.assertEqual(o.utf7_encoder("A&B"), "A&-B")

    def test_citer(self):
        self.assertEqual(o.citer("INBOX"), "INBOX")
        self.assertEqual(o.citer("Mes dossiers"), '"Mes dossiers"')
        self.assertEqual(o.citer('a"b'), '"a\\"b"')

    def test_les_roles_viennent_du_serveur_puis_du_nom(self):
        self.assertEqual(o.role_du_dossier("Corbeille", "\\hasnochildren \\trash"), "trash")
        self.assertEqual(o.role_du_dossier("Papiers", "\\hasnochildren \\sent"), "sent")
        self.assertEqual(o.role_du_dossier("Messages envoyés", ""), "sent")
        self.assertEqual(o.role_du_dossier("INBOX", ""), "inbox")
        self.assertEqual(o.role_du_dossier("Clients", ""), "")

    def test_un_role_n_appartient_qu_a_un_dossier(self):
        ds = [{"nom": "Trash", "role": "trash", "role_flag": True}, {"nom": "Deleted Messages", "role": "trash", "role_flag": False},
              {"nom": "Sent", "role": "sent", "role_flag": False}, {"nom": "Sent Messages", "role": "sent", "role_flag": False}]
        o.roles_uniques(ds)
        self.assertEqual([(d["nom"], d["role"]) for d in ds], [("Trash", "trash"), ("Deleted Messages", ""), ("Sent", "sent"), ("Sent Messages", "")])
        self.assertEqual(ds[1]["role_ecarte"], "trash")

    def test_un_jeu_d_uid_n_accepte_que_des_entiers(self):
        self.assertEqual(o.ensemble_uid(["1", 2, b"3", " 4 ", "5;DELETE", "1:*", "", "x", "-3", "2"]), ["1", "2", "3", "4"])
        self.assertEqual(o.ensemble_uid("12"), ["12"])
        self.assertEqual(o.ensemble_uid(None), [])
        self.assertEqual(o.ensemble_uid("1 UID FETCH 1:*"), [])


class Entetes(unittest.TestCase):
    def test_dates_normalisees_et_triables(self):
        a = o.date_iso("Mon, 05 Jan 2026 10:00:00 +0200")
        b = o.date_iso("Tue, 07 Jul 2026 10:00:00 +0000")
        self.assertEqual(a, "2026-01-05 08:00:00")
        self.assertLess(a, b)
        self.assertEqual(o.date_iso("n'importe quoi"), "")
        self.assertEqual(o.date_iso(""), "")

    def test_adresses(self):
        self.assertEqual(o.adresse_parts('=?utf-8?q?Jos=C3=A9?= <Jose@Exemple.FR>'), ("José", "jose@exemple.fr"))
        self.assertEqual(o.adresse_parts("seul@exemple.fr"), ("seul", "seul@exemple.fr"))
        self.assertEqual(o.adresse_parts(""), ("", ""))

    def test_le_fil_prefere_les_en_tetes_a_l_objet(self):
        def m(**h):
            msg = email.message_from_string("\n".join("%s: %s" % (k.replace("_", "-"), v) for k, v in h.items()) + "\n\ncorps")
            return o.cle_de_fil(msg)
        self.assertEqual(m(References="<a@x> <b@x>", Subject="Re: x"), "<a@x>")
        self.assertEqual(m(In_Reply_To="<r@x>", Subject="x"), "<r@x>")
        self.assertEqual(m(Message_ID="<m@x>", Subject="x"), "<m@x>")
        self.assertEqual(m(Subject="Re: RE: Fwd: Facture"), "suj:facture")
        self.assertEqual(m(Subject="Re: Facture"), m(Subject="Facture"))

    def test_classement(self):
        tech = {"from_addr": "root@serveur.exemple.fr", "subject": "Cron <root@serveur> /usr/bin/backup"}
        client = {"from_addr": "client@exemple.fr", "subject": "Sauvegarde de notre devis"}
        self.assertEqual(o.etat_du_message(tech), "tech")
        self.assertEqual(o.etat_du_message(dict(tech, answered=1)), "tech")           # la nature décide, pas ce qu'on en a fait
        self.assertEqual(o.etat_du_message(client), "traiter")                          # « sauvegarde » chez un client parle d'un devis
        self.assertEqual(o.etat_du_message(dict(client, answered=1)), "attente")
        self.assertEqual(o.etat_du_message({"from_addr": "certbot@x.fr", "subject": "ok"}), "tech")


class Corps(unittest.TestCase):
    def test_texte_html_et_pieces(self):
        brut = ('From: a@x.fr\nSubject: =?utf-8?q?D=C3=A9j=C3=A0?=\nMIME-Version: 1.0\nContent-Type: multipart/mixed; boundary="B"\n\n'
                '--B\nContent-Type: multipart/alternative; boundary="C"\n\n--C\nContent-Type: text/plain; charset=utf-8\n\nBonjour le texte\n'
                '--C\nContent-Type: text/html; charset=utf-8\n\n<p>Bonjour <b>le html</b></p>\n--C--\n'
                '--B\nContent-Type: application/pdf; name="devis.pdf"\nContent-Disposition: attachment; filename="devis.pdf"\nContent-Transfer-Encoding: base64\n\nJVBERi0=\n--B--\n')
        msg = email.message_from_string(brut)
        texte, page = o.corps(msg)
        self.assertEqual((texte, "le html" in page), ("Bonjour le texte", True))
        pj = o.pieces_jointes(msg)
        self.assertEqual([(p["nom"], p["type"], p["taille"]) for p in pj], [("devis.pdf", "application/pdf", 5)])
        self.assertEqual(o.piece_numero(msg, 0), ("devis.pdf", "application/pdf", b"%PDF-"))
        self.assertIsNone(o.piece_numero(msg, 3))

    def test_html_seul_est_aplati_en_texte(self):
        msg = email.message_from_string("Content-Type: text/html; charset=utf-8\n\n<style>p{}</style><p>Un</p><p>Deux &amp; trois<br>quatre</p><script>x()</script>")
        texte, _ = o.corps(msg)
        self.assertEqual(texte, "Un\n\nDeux & trois\nquatre")


class Nettoyage(unittest.TestCase):
    """Les vecteurs d'attaque courants : rien de ce qui s'exécute ou se charge ne doit survivre."""

    DANGER = ("<script", "javascript:", "onerror", "onclick", "onload", "onmouseover", "<iframe", "<object", "<embed", "<form", "<svg", "<meta", "<link", "<base", "expression(",
              "@import", "vbscript:", "<style", "srcdoc")

    VECTEURS = [
        '<script>alert(1)</script>',
        '<SCRIPT SRC=http://pirate/x.js></SCRIPT>',
        '<img src=x onerror=alert(1)>',
        '<img src="x" onerror="alert(1)">',
        '<body onload=alert(1)>',
        '<svg onload=alert(1)>',
        '<svg><script>alert(1)</script></svg>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="JaVaScRiPt:alert(1)">x</a>',
        '<a href="  javascript:alert(1)">x</a>',
        '<a href="jav&#x09;ascript:alert(1)">x</a>',
        '<a href="&#106;avascript:alert(1)">x</a>',
        '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
        '<a href="vbscript:msgbox(1)">x</a>',
        '<iframe src="http://pirate/"></iframe>',
        '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
        '<object data="http://pirate/x.swf"></object>',
        '<embed src="http://pirate/x.swf">',
        '<form action="http://pirate/"><input name=p></form>',
        '<meta http-equiv="refresh" content="0;url=http://pirate/">',
        '<link rel=stylesheet href="http://pirate/x.css">',
        '<base href="http://pirate/">',
        '<style>@import "http://pirate/x.css"; body{background:url(http://pirate/x.png)}</style>',
        '<p style="background:url(http://pirate/x.png)">x</p>',
        '<p style="width:expression(alert(1))">x</p>',
        '<p style="behavior:url(x.htc)">x</p>',
        '<div style="background-image:url(javascript:alert(1))">x</div>',
        '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
        '<table background="javascript:alert(1)"><tr><td>x</td></tr></table>',
        '<img src="javascript:alert(1)">',
        '<img src=`x` onerror=alert(1)>',
        '<<script>alert(1);//<</script>',
        '<scr<script>ipt>alert(1)</scr</script>ipt>',
        '<noscript><p title="</noscript><img src=x onerror=alert(1)>">',
        '<template><script>alert(1)</script></template>',
        '<video><source onerror=alert(1)></video>',
        '<button onclick=alert(1)>x</button>',
        '<a href="x" onmouseover="alert(1)">x</a>',
        '<p onclick = "alert(1)">x</p>',
        "<p\nonclick\n=\nalert(1)>x</p>",
        '<isindex action=javascript:alert(1)>',
        '<input autofocus onfocus=alert(1)>',
    ]

    def test_aucun_vecteur_ne_survit(self):
        for v in self.VECTEURS:
            for images in (False, True):
                sortie, _ = o.assainir_html(v, images)
                bas = sortie.lower()
                for danger in self.DANGER:
                    self.assertNotIn(danger, bas, "%r a laissé %r -> %r" % (v, danger, sortie))
                self.assertNotRegex(bas, r"<[a-z]+[^>]*\son[a-z]+\s*=", v)
                self.assertNotRegex(bas, r"(href|src)\s*=\s*[\"']?\s*(javascript|data:text|vbscript)", v)

    def test_le_texte_dangereux_est_echappe_pas_perdu(self):
        sortie, _ = o.assainir_html("<p>2 < 3 & 4 > 1 <b>gras</b></p>")
        self.assertEqual(sortie, "<p>2 &lt; 3 &amp; 4 &gt; 1 <b>gras</b></p>")
        sortie, _ = o.assainir_html("a &lt;script&gt;alert(1)&lt;/script&gt; b")
        self.assertNotIn("<script", sortie)
        self.assertIn("&lt;script&gt;", sortie)

    def test_la_mise_en_forme_utile_reste(self):
        page = '<table border="1" width="100%"><tr><td style="color:#c00;font-weight:bold;background:url(x)" colspan="2">Total</td></tr></table><p align="center"><font color="red">x</font><br></p><ul><li>un</li></ul>'
        sortie, _ = o.assainir_html(page)
        for garde in ("<table", 'border="1"', 'colspan="2"', "font-weight:bold", "color:#c00", "<ul>", "<li>un</li>", '<p align="center">', "<br>"):
            self.assertIn(garde, sortie)
        self.assertNotIn("url(", sortie)

    def test_les_images_distantes_sont_bloquees_sauf_accord(self):
        page = '<img src="http://e.fr/a.png" alt="logo"><img src="data:image/png;base64,AAAA"><img src="cid:logo1">'
        sortie, distantes = o.assainir_html(page, images=False)
        self.assertTrue(distantes)
        self.assertIn('data-blocked-src="http://e.fr/a.png"', sortie)
        self.assertNotIn(' src="http://', sortie)
        self.assertIn('src="data:image/png;base64,AAAA"', sortie)
        self.assertIn('data-cid="logo1"', sortie)
        sortie, _ = o.assainir_html(page, images=True)
        self.assertIn('src="http://e.fr/a.png"', sortie)

    def test_un_pixel_espion_n_est_jamais_charge_meme_avec_accord(self):
        for pixel in ('<img src="http://t.fr/p.gif" width="1" height="1">', '<img src="http://t.fr/p.gif" width=0>', '<img src="http://t.fr/p.gif" style="width:1px;height:1px">'):
            sortie, _ = o.assainir_html(pixel, images=True)
            self.assertIn("data-tracker-src", sortie, pixel)
            self.assertNotIn(' src="http', sortie, pixel)

    def test_les_liens_sont_durcis_et_un_texte_trompeur_est_denonce(self):
        sortie, _ = o.assainir_html('<a href="https://www.banque.fr/login">Cliquez</a>')
        self.assertIn('target="_blank" rel="noopener noreferrer"', sortie)
        self.assertIn('title="https://www.banque.fr/login"', sortie)
        self.assertNotIn("mène à", sortie)
        sortie, _ = o.assainir_html('<a href="https://pirate.example.org/x">www.banque.fr</a>')
        self.assertIn("⚠ mène à pirate.example.org", sortie)
        sortie, _ = o.assainir_html('<a href="https://banque.fr/x">https://www.banque.fr/espace</a>')
        self.assertNotIn("mène à", sortie)                                              # même domaine : pas d'alerte
        sortie, _ = o.assainir_html('<a href="https://x.fr/rapport.pdf">rapport.pdf</a>')
        self.assertNotIn("mène à", sortie)                                              # un nom de fichier n'est pas un domaine
        sortie, _ = o.assainir_html('<a href="mailto:a@b.fr">écrire</a>')
        self.assertIn('href="mailto:a@b.fr"', sortie)
        sortie, _ = o.assainir_html('<a href="/relatif">x</a><a href="#haut">y</a><a href="ftp://x/">z</a>')
        self.assertNotIn("href=", sortie)

    def test_les_balises_mal_fermees_sont_refermees(self):
        sortie, _ = o.assainir_html("<div><p><b>gras <i>italique")
        self.assertEqual(sortie.count("<"), sortie.count(">"))
        self.assertTrue(sortie.endswith("</i></b></p></div>"))

    def test_html_vide_ou_illisible_ne_leve_pas(self):
        self.assertEqual(o.assainir_html("")[0], "")
        self.assertEqual(o.assainir_html(None)[0], "")
        o.assainir_html("<" * 5000 + "a" * 5000)

    def test_la_taille_est_bornee(self):
        sortie, _ = o.assainir_html("<p>" + "x" * 500000 + "</p>")
        self.assertLessEqual(len(sortie), 400000)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Dossiers, Entetes, Corps, Nettoyage
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
