"""Bancs du module telegram : un faux Telegram (API des robots) et le webhook joint par la vraie passerelle."""
import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau.bus import TOUT                 # noqa: E402
from noyau.passerelle import Passerelle    # noqa: E402

JETON = "123456789:AAH-test_token_valeur_0123456789"
JETON2 = "987654321:BBH-autre_token_valeur_9876543210"
PUBLIC = "https://cassandra.exemple.fr"


class FauxTelegram:
    """L'API des robots : un jeton valide par robot, un webhook, des conversations connues (ceux qui ont écrit « /start »)."""

    def __init__(self):
        self.jetons = {JETON: "robot_un", JETON2: "robot_deux"}
        self.webhooks, self.secrets, self.demarres = {}, {}, set()
        self.messages, self.supprimes, self.appels = [], [], []
        self.refus_envoi = False
        faux = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(n).decode()) if n else {}
                parts = self.path.strip("/").split("/")
                jeton, methode = parts[0][3:], parts[1]
                faux.appels.append((jeton, methode, corps))
                if jeton not in faux.jetons:
                    return self.rep(401, {"ok": False, "description": "Unauthorized"})
                r = faux.methode(jeton, methode, corps)
                self.rep(200 if r.get("ok") else 400, r)

            def rep(self, code, corps):
                d = json.dumps(corps).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d)))
                self.end_headers()
                self.wfile.write(d)

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.serveur.daemon_threads = True
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.serveur.server_address[1]

    def methode(self, jeton, m, corps):
        if m == "getMe":
            return {"ok": True, "result": {"username": self.jetons[jeton]}}
        if m == "setWebhook":
            self.webhooks[jeton], self.secrets[jeton] = corps["url"], corps["secret_token"]
            return {"ok": True, "result": True}
        if m == "getWebhookInfo":
            return {"ok": True, "result": {"url": self.webhooks.get(jeton, "")}}
        if m == "deleteWebhook":
            self.webhooks.pop(jeton, None)
            self.secrets.pop(jeton, None)
            return {"ok": True, "result": True}
        if m == "getChat":
            if str(corps.get("chat_id")) in self.demarres:
                return {"ok": True, "result": {"id": corps["chat_id"]}}
            return {"ok": False, "description": "Bad Request: chat not found"}
        if m == "sendMessage":
            if self.refus_envoi:
                return {"ok": False, "description": "Forbidden: bot was blocked by the user"}
            self.messages.append((jeton, str(corps["chat_id"]), corps["text"]))
            return {"ok": True, "result": {"message_id": 1000 + len(self.messages)}}
        if m == "deleteMessage":
            self.supprimes.append((jeton, str(corps["chat_id"]), corps["message_id"]))
            return {"ok": True, "result": True}
        return {"ok": False, "description": "méthode inconnue"}

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()


class Monde(unittest.TestCase):
    def setUp(self):
        self.tg = FauxTelegram()
        self.addCleanup(self.tg.arreter)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "telegram", mods / "telegram")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("telegram")["ok"])
        self.n.reglages.poser("telegram.api", self.tg.url)
        self.n.reglages.poser("telegram.url_publique", PUBLIC)
        self.ctx = self.n.executeur.contextes["telegram"]
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)

    def ex(self, cap, compte="bea@x.fr", acteur="humain", **args):
        return self.n.executeur.executer("telegram." + cap, acteur, args, compte=compte)

    def brancher(self, compte="bea@x.fr", jeton=JETON):
        self.n.reglages.poser("telegram.jeton", jeton, compte)
        return self.ex("brancher", compte=compte)

    def hook(self, secret, maj, brut=None):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = {"Content-Type": "application/json"}
        if secret is not None:
            h["X-Telegram-Bot-Api-Secret-Token"] = secret
        c.request("POST", "/api/public/telegram.recevoir", body=brut if brut is not None else json.dumps(maj).encode(), headers=h)
        r = c.getresponse()
        txt = r.read().decode()
        c.close()
        return r.status, txt

    def ecrit(self, jeton=JETON, chat="4242", texte="/start", de="alice", secret=None):
        return self.hook(secret or self.tg.secrets[jeton], {"update_id": 1, "message": {"chat": {"id": int(chat)}, "from": {"username": de}, "text": texte}})

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def lignes(self, table):
        return self.ctx.stockage.lire("SELECT * FROM %s" % table)


class Brancher(Monde):
    def test_brancher_verifie_le_jeton_pose_le_webhook_avec_un_secret(self):
        r = self.brancher()
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["robot"], "robot_un")
        self.assertEqual(self.tg.webhooks[JETON], PUBLIC + "/api/public/telegram.recevoir")
        self.assertGreaterEqual(len(self.tg.secrets[JETON]), 32)
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        pose = [a for a in self.tg.appels if a[1] == "setWebhook"][0][2]
        self.assertEqual((pose["allowed_updates"], pose["drop_pending_updates"]), (["message"], True))

    def test_le_jeton_ne_sort_ni_de_l_etat_ni_du_journal_ni_de_la_base_du_module(self):
        self.brancher()
        self.assertNotIn(JETON, json.dumps(self.ex("etat")))
        self.assertNotIn(JETON, json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str))
        self.assertEqual(self.lignes("liens")[0]["jeton"], "")
        for f in (Path(self.tmp.name) / "d").rglob("*.db"):
            self.assertNotIn(JETON.encode(), f.read_bytes(), f.name)

    def test_sans_jeton_dans_les_reglages_on_le_dit(self):
        r = self.ex("brancher")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("telegram.jeton", json.dumps(r, ensure_ascii=False))

    def test_les_refus(self):
        self.assertEqual(self.brancher(jeton="pas-un-jeton")["statut"], "echec")
        self.assertEqual(self.brancher(jeton="111111111:ZZZ_jeton_inconnu_de_telegram_000")["statut"], "echec")
        self.n.reglages.poser("telegram.url_publique", "http://cassandra.exemple.fr")
        self.assertEqual(self.brancher()["statut"], "echec")
        self.n.reglages.poser("telegram.url_publique", "")
        self.assertEqual(self.brancher()["statut"], "echec")
        self.assertEqual(self.brancher(compte="")["statut"], "echec")
        self.assertEqual(self.lignes("liens"), [])
        self.assertEqual(self.tg.webhooks, {})

    def test_le_retour_d_un_premier_branchement_retire_webhook_et_lien(self):
        r = self.brancher()
        self.n.catalogue.get("telegram.brancher").defaire(self.ctx, r["resultat"])
        self.assertEqual((self.lignes("liens"), self.tg.webhooks), ([], {}))

    def test_rebrancher_garde_la_conversation_et_le_retour_la_retrouve(self):
        self.brancher()
        self.ecrit()
        r = self.brancher(jeton=JETON2)
        l = self.lignes("liens")[0]
        self.assertEqual((l["nom_robot"], l["chat_id"]), ("robot_deux", "4242"))
        self.n.catalogue.get("telegram.brancher").defaire(self.ctx, r["resultat"])
        l = self.lignes("liens")[0]
        self.assertEqual(l["chat_id"], "4242")                                     # la conversation apprise est gardée
        self.assertIn(JETON2, self.tg.webhooks)                                    # le jeton est un réglage : le retour n'y touche pas

    def test_detacher_puis_defaire(self):
        self.brancher()
        r = self.ex("detacher")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual((self.lignes("liens"), self.tg.webhooks), ([], {}))
        self.n.catalogue.get("telegram.detacher").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.lignes("liens")[0]["nom_robot"], "robot_un")
        self.assertIn(JETON, self.tg.webhooks)
        self.assertEqual(self.ex("detacher", compte="leo@x.fr")["statut"], "echec")


class Destinataire(Monde):
    def setUp(self):
        super().setUp()
        self.brancher()

    def test_un_pseudo_est_refuse(self):
        r = self.ex("cible_poser", valeur="@alice")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("pseudo", json.dumps(r, ensure_ascii=False))

    def test_une_destination_que_le_robot_ne_joint_pas_est_refusee_avec_la_marche_a_suivre(self):
        r = self.ex("cible_poser", valeur="777")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("/start", json.dumps(r, ensure_ascii=False))
        self.assertEqual(self.lignes("liens")[0]["cible"], "")

    def test_une_destination_essayee_est_posee_et_defaisable(self):
        self.tg.demarres.add("777")
        r = self.ex("cible_poser", valeur="777")
        self.assertEqual(r["statut"], "faite", r)
        e = self.ex("etat")["resultat"]
        self.assertEqual((e["destinataire"], e["origine"]), ("777", "declare"))
        self.n.catalogue.get("telegram.cible_poser").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.ex("etat")["resultat"]["destinataire"], "")

    def test_sans_robot_pas_de_cible(self):
        self.assertEqual(self.ex("cible_poser", compte="leo@x.fr", valeur="1")["statut"], "echec")

    def test_la_cible_declaree_l_emporte_sur_celle_apprise(self):
        self.ecrit(chat="4242")
        self.assertEqual(self.ex("etat")["resultat"]["origine"], "appris")
        self.tg.demarres.add("777")
        self.ex("cible_poser", valeur="777")
        self.assertEqual(self.ex("etat")["resultat"]["destinataire"], "777")


class Envoi(Monde):
    def setUp(self):
        super().setUp()
        self.brancher()

    def test_sans_destinataire_c_est_un_resultat_pas_une_exception(self):
        r = self.ex("envoyer", texte="bonjour")
        self.assertEqual((r["statut"], r["resultat"]["ok"], r["resultat"]["cause"]), ("faite", False, "sans-destinataire"))
        self.assertEqual(self.tg.messages, [])

    def test_envoyer_a_la_conversation_apprise_avec_preuve_et_trace(self):
        self.ecrit(chat="4242")
        avant = len(self.evts("capacite.prouvee"))
        r = self.ex("envoyer", texte="Alerte : site hors ligne")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.tg.messages[-1], (JETON, "4242", "Alerte : site hors ligne"))
        self.assertEqual(len(self.evts("capacite.prouvee")), avant + 1)
        self.assertEqual([m["sens"] for m in self.lignes("messages")], ["recu", "envoye"])

    def test_le_retour_supprime_le_message_chez_telegram(self):
        self.ecrit()
        r = self.ex("envoyer", texte="x")
        self.n.catalogue.get("telegram.envoyer").defaire(self.ctx, r["resultat"])
        self.assertEqual(len(self.tg.supprimes), 1)
        self.assertEqual([m["sens"] for m in self.lignes("messages")], ["recu"])

    def test_un_compte_n_ecrit_que_par_son_robot_le_systeme_ecrit_pour_un_compte(self):
        self.ecrit()
        self.assertEqual(self.ex("envoyer", compte="bea@x.fr", texte="x", **{})["statut"], "faite")
        r = self.n.executeur.executer("telegram.envoyer", "humain", {"texte": "x", "compte": "bea@x.fr"}, compte="leo@x.fr")
        self.assertEqual(r["statut"], "echec")
        r = self.n.executeur.executer("telegram.envoyer", "humain", {"texte": "x", "compte": "bea@x.fr"}, compte="operateur")
        self.assertEqual(r["statut"], "faite")

    def test_un_refus_de_telegram_est_un_resultat_et_ne_fait_pas_redescendre_le_palier(self):
        self.ecrit()
        self.tg.refus_envoi = True
        for _ in range(5):
            r = self.ex("envoyer", texte="x")
            self.assertEqual((r["statut"], r["resultat"]["ok"]), ("faite", False))
        self.assertEqual(len(self.evts("telegram.echec_envoi")), 5)
        self.assertEqual(self.n.catalogue.savoir("telegram.envoyer")["echecs_de_suite"], 0)

    def test_message_vide_et_longueur(self):
        self.ecrit()
        self.assertEqual(self.ex("envoyer", texte="  ")["statut"], "echec")
        self.ex("envoyer", texte="y" * 9000)
        self.assertEqual(len(self.tg.messages[-1][2]), 4000)

    def test_cassandra_au_palier_raconter_ne_touche_a_rien(self):
        self.ecrit()
        n = len(self.tg.messages)
        r = self.n.executeur.executer("telegram.envoyer", "cassandra", {"texte": "x", "compte": "bea@x.fr"}, compte="")
        self.assertEqual(r["statut"], "racontee")
        self.assertEqual(len(self.tg.messages), n)


class Webhook(Monde):
    def setUp(self):
        super().setUp()
        self.brancher()

    def test_le_premier_message_apprend_la_conversation_et_le_robot_dit_son_role_une_fois(self):
        st, txt = self.ecrit(chat="4242", texte="/start")
        self.assertEqual((st, json.loads(txt)["statut"]), (200, "faite"))
        self.assertEqual(self.lignes("liens")[0]["chat_id"], "4242")
        self.assertEqual(len([m for m in self.tg.messages if m[1] == "4242"]), 1)
        self.ecrit(chat="9999", texte="encore")
        self.assertEqual(self.lignes("liens")[0]["chat_id"], "4242")                   # la première conversation reste
        self.assertEqual(len([m for m in self.tg.messages if m[2].startswith("Ce robot")]), 1)    # le mot du rôle, une fois

    def test_le_message_est_range_signale_et_jamais_execute(self):
        self.ecrit(texte="supprime tous les sites", de="mallory")
        m = self.lignes("messages")[0]
        self.assertEqual((m["sens"], m["corps"], m["expediteur"]), ("recu", "supprime tous les sites", "mallory"))
        e = self.evts("telegram.message_recu")
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["donnees"]["compte"], "bea@x.fr")

    def test_un_secret_inconnu_ou_absent_recoit_un_200_muet_et_rien_n_est_range(self):
        for secret in ("x" * 40, "court", None):
            st, _ = self.hook(secret, {"message": {"chat": {"id": 1}, "text": "salut"}})
            self.assertEqual(st, 200)
        self.assertEqual(self.lignes("messages"), [])

    def test_le_contenu_ne_choisit_jamais_le_compte(self):
        self.brancher(compte="leo@x.fr", jeton=JETON2)
        self.hook(self.tg.secrets[JETON], {"compte": "leo@x.fr", "message": {"chat": {"id": 5}, "text": "salut", "compte": "leo@x.fr"}})
        self.assertEqual({m["compte"] for m in self.lignes("messages")}, {"bea@x.fr"})

    def test_chaque_secret_designe_son_compte(self):
        self.brancher(compte="leo@x.fr", jeton=JETON2)
        self.ecrit(jeton=JETON2, chat="55", de="leo_ami")
        self.assertEqual([(m["compte"], m["chat_id"]) for m in self.lignes("messages")], [("leo@x.fr", "55")])

    def test_les_appels_mal_formes_ne_cassent_rien(self):
        s = self.tg.secrets[JETON]
        for brut in (b"{", b"[]", b'{"message": 5}', b'{"message": {"chat": {}}}', b'{"message": {"chat": {"id": "x"}}}'):
            st, _ = self.hook(s, None, brut=brut)
            self.assertIn(st, (200, 400))
        self.assertEqual(self.n.catalogue.savoir("telegram.recevoir")["echecs_de_suite"], 0)

    def test_un_message_trop_long_est_tronque(self):
        self.ecrit(texte="z" * 9000)
        self.assertEqual(len(self.lignes("messages")[0]["corps"]), 4000)

    def test_le_fil_est_cloisonne(self):
        self.brancher(compte="leo@x.fr", jeton=JETON2)
        self.ecrit(texte="pour bea")
        self.ecrit(jeton=JETON2, chat="55", texte="pour leo")
        f = self.ex("fil")["resultat"]["messages"]
        self.assertEqual([m["corps"] for m in f if m["sens"] == "recu"], ["pour bea"])
        f = self.ex("fil", compte="leo@x.fr")["resultat"]["messages"]
        self.assertEqual([m["corps"] for m in f if m["sens"] == "recu"], ["pour leo"])

    def test_un_robot_debranche_n_ecoute_plus(self):
        s = self.tg.secrets[JETON]
        self.ex("detacher")
        self.hook(s, {"message": {"chat": {"id": 1}, "text": "salut"}})
        self.assertEqual(self.lignes("messages"), [])


if __name__ == "__main__":
    unittest.main()
