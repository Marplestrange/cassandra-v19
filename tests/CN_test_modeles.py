"""Bancs du module modeles, contre de faux serveurs OpenAI-compatible et Ollama."""
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

BEA, LEO, ROOT = "bea@x.fr", "leo@x.fr", "root@x.fr"
CLE = "sk-TRES-SECRETE-1234"


class Faux:
    """Un serveur qui répond à une file de réponses {statut, corps} et note tout ce qu'il reçoit."""

    def __init__(self):
        self.reponses, self.requetes, self.pull = [], [], []
        self.tags = {"models": [{"name": "qwen2.5:3b", "size": 1}]}
        faux = self

        class H(BaseHTTPRequestHandler):
            def _lire(self):
                n = int(self.headers.get("Content-Length") or 0)
                corps = self.rfile.read(n).decode() if n else ""
                faux.requetes.append({"methode": self.command, "chemin": self.path, "auth": self.headers.get("Authorization", ""), "corps": json.loads(corps) if corps else None})
                return faux.requetes[-1]

            def _rendre(self, statut, corps, brut=None):
                data = brut if brut is not None else json.dumps(corps).encode()
                self.send_response(statut)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._lire()
                self._rendre(200, faux.tags) if self.path == "/api/tags" else self._rendre(404, {})

            def do_DELETE(self):
                q = self._lire()
                faux.tags["models"] = [m for m in faux.tags["models"] if m["name"] != q["corps"]["model"]]
                self._rendre(200, {})

            def do_POST(self):
                q = self._lire()
                if self.path == "/api/pull":
                    self._rendre(200, None, "".join(json.dumps(x) + "\n" for x in faux.pull).encode())
                    return
                statut, corps = faux.reponses.pop(0) if faux.reponses else (200, ouvert("ok"))
                self._rendre(statut, corps)

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()


def ouvert(texte, fin="stop", reflexion="", usage=(11, 7)):
    msg = {"role": "assistant", "content": texte}
    if reflexion:
        msg["reasoning_content"] = reflexion
    return {"choices": [{"message": msg, "finish_reason": fin}], "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "modeles", mods / "modeles", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("modeles")["ok"])
        self.n.droits.regler_admin(ROOT, True)
        self.ctx = self.n.executeur.contextes["modeles"]
        self.db = self.ctx.stockage
        self.faux = Faux()
        self.addCleanup(self.faux.arreter)
        self.n.reglages.poser("modeles.ollama_hote", self.faux.url, "")

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("modeles." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "echec", r)
        return r["erreur"]

    def retour(self, cap, res):
        self.n.catalogue.get("modeles." + cap).defaire(self.ctx, res)

    def mien(self, nom="gpt-4o-mini", compte=BEA, prov="personnalise", cle=CLE):
        return self.ok("ajouter", fournisseur=prov, nom=nom, cle=cle, base_url=self.faux.url, compte=compte)["id"]

    def instance(self, nom="deepseek-flash", prov="personnalise", cle=CLE):
        return self.ok("instance_ajouter", fournisseur=prov, nom=nom, cle=cle, base_url=self.faux.url, compte=ROOT)["id"]

    def tout_le_journal(self):
        return json.dumps(self.n.bus.recents(portee=__import__("noyau.CN_bus", fromlist=["TOUT"]).TOUT, limite=2000), default=str)


class Registre(Monde):
    def test_declarer_un_modele_chiffre_la_cle_et_ne_la_rend_jamais(self):
        r = self.ex("ajouter", fournisseur="personnalise", nom="gpt-4o-mini", cle=CLE, base_url=self.faux.url)
        self.assertEqual(r["statut"], "faite", r)
        mid = r["resultat"]["id"]
        brut = self.db.lire("SELECT cle FROM modeles WHERE id=?", (mid,))[0]["cle"]
        self.assertTrue(brut.startswith("enc1:"))
        self.assertNotIn(CLE, brut)
        liste = self.ok("lister")
        self.assertNotIn(CLE, json.dumps(liste))
        self.assertEqual([(m["nom"], m["a_cle"], m["portee"], m["en_ligne"]) for m in liste["modeles"]], [("gpt-4o-mini", True, "compte", False)])
        self.assertNotIn(CLE, self.tout_le_journal())

    def test_le_chiffre_est_lie_a_son_modele(self):
        a, b = self.mien("un"), self.mien("deux")
        ca = self.db.lire("SELECT cle FROM modeles WHERE id=?", (a,))[0]["cle"]
        self.db.ecrire("UPDATE modeles SET cle=? WHERE id=?", (ca, b))               # une clé recopiée sur un autre modèle ne se lit plus
        r = self.ex("completer", modele_id=b, messages=[{"role": "user", "content": "x"}])
        self.assertEqual(r["statut"], "faite")
        self.assertFalse(r["resultat"]["ok"])
        self.assertNotIn(CLE, json.dumps(r))

    def test_les_refus_de_declaration(self):
        base = dict(fournisseur="personnalise", nom="m", cle="k", base_url=self.faux.url)
        for args in (dict(base, fournisseur="inconnu"), dict(base, nom=" "), dict(base, nom="https://x.fr/m"), dict(base, nom="mo del"), dict(base, base_url=""),
                     dict(base, base_url="ftp://x"), dict(fournisseur="openai", nom="gpt-4o", cle="")):
            self.assertEqual(self.ex("ajouter", **args)["statut"], "echec", args)
        for compte in ("", "cassandra", "itare"):
            self.assertEqual(self.ex("ajouter", compte=compte, **base)["statut"], "echec")

    def test_un_nom_copie_d_une_phrase_perd_sa_ponctuation_et_un_local_n_a_pas_de_cle(self):
        mid = self.ok("ajouter", fournisseur="openai", nom="gpt-4o-mini.", cle="k")["id"]
        self.assertEqual(self.db.lire("SELECT nom FROM modeles WHERE id=?", (mid,))[0]["nom"], "gpt-4o-mini")
        loc = self.ok("ajouter", fournisseur="ollama", nom="qwen2.5:3b", cle="ignorée")["id"]
        self.assertEqual(self.db.lire("SELECT cle FROM modeles WHERE id=?", (loc,))[0]["cle"], "")

    def test_ajouter_se_defait_et_les_modeles_sont_a_chaque_compte(self):
        r = self.ex("ajouter", fournisseur="openai", nom="gpt-4o", cle="k")
        self.mien("autre", compte=LEO)
        self.assertEqual([m["nom"] for m in self.ok("lister", compte=LEO)["modeles"]], ["autre"])
        self.retour("ajouter", r["resultat"])
        self.assertEqual(self.ok("lister")["modeles"], [])

    def test_un_modele_d_instance_exige_le_droit_d_administrer_et_se_voit_de_tous_sans_cle(self):
        self.assertEqual(self.ex("instance_ajouter", fournisseur="personnalise", nom="m", cle="k", base_url=self.faux.url, compte=BEA)["statut"], "refuse")
        mid = self.instance()
        v = self.ok("lister", compte=LEO)
        self.assertEqual([(m["id"], m["portee"], m["a_cle"]) for m in v["modeles"]], [(mid, "instance", True)])
        self.assertNotIn(CLE, json.dumps(v))
        self.assertEqual(self.ex("instance_retirer", id=mid, compte=LEO)["statut"], "refuse")
        self.assertEqual(self.ex("retirer", id=mid, compte=LEO)["statut"], "echec")             # un modèle d'instance ne se retire pas par la porte des comptes

    def test_retirer_se_defait_avec_sa_cle_et_refuse_un_modele_utilise(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.assertIn("choix", self.echec("retirer", id=mid))
        self.ok("choisir", modele_id="")
        r = self.ex("retirer", id=mid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertNotIn(CLE, self.tout_le_journal())
        self.retour("retirer", r["resultat"])
        c = self.ex("completer", modele_id=mid, messages=[{"role": "user", "content": "x"}])
        self.assertTrue(c["resultat"]["ok"])                                                      # la clé chiffrée est revenue avec le modèle
        i = self.instance()
        self.ok("role_lier", role="principal", modele_id=i, compte=ROOT)
        self.assertIn("rôle", self.echec("instance_retirer", id=i, compte=ROOT))

    def test_les_fournisseurs(self):
        f = self.ok("fournisseurs")
        self.assertEqual({x["id"] for x in f["fournisseurs"]}, {"deepseek", "openrouter", "openai", "google", "groq", "ollama", "personnalise"})
        self.assertTrue([x for x in f["fournisseurs"] if x["id"] == "deepseek"][0]["raisonneur"])


class Roles(Monde):
    def test_lier_delier_et_les_retours(self):
        i = self.instance()
        r = self.ex("role_lier", role="relecteur", modele_id=i, compte=ROOT)
        self.assertEqual(self.ok("lister", acteur="cassandra")["roles"], {"relecteur": i})
        self.retour("role_lier", r["resultat"])
        self.assertEqual(self.ok("lister", acteur="cassandra")["roles"], {})
        self.ok("role_lier", role="relecteur", modele_id=i, compte=ROOT)
        d = self.ex("role_lier", role="relecteur", modele_id="", compte=ROOT)
        self.retour("role_lier", d["resultat"])
        self.assertEqual(self.ok("lister", acteur="cassandra")["roles"], {"relecteur": i})

    def test_les_refus(self):
        i, m = self.instance(), self.mien()
        self.assertIn("instance", self.echec("role_lier", role="vision", modele_id=m, compte=ROOT))
        for role in ("", "V", "x", "avec espace", "a" * 41):
            self.assertEqual(self.ex("role_lier", role=role, modele_id=i, compte=ROOT)["statut"], "echec", role)
        self.assertEqual(self.ex("role_lier", role="vision", modele_id="introuvable", compte=ROOT)["statut"], "echec")
        self.assertEqual(self.ex("role_lier", role="vision", modele_id=i)["statut"], "refuse")

    def test_les_roles_ne_sont_pas_montres_aux_comptes(self):
        self.ok("role_lier", role="vision", modele_id=self.instance(), compte=ROOT)
        self.assertEqual(self.ok("lister")["roles"], {})

    def test_le_choix_d_un_compte_ne_porte_que_sur_ses_modeles(self):
        m, autre = self.mien(), self.mien("a-lui", compte=LEO)
        i = self.instance()
        for mid in (autre, i, "introuvable"):
            self.assertEqual(self.ex("choisir", modele_id=mid)["statut"], "echec", mid)
        r = self.ex("choisir", modele_id=m)
        self.assertEqual(self.ok("lister")["choix"], m)
        self.assertTrue([x for x in self.ok("lister")["modeles"] if x["id"] == m][0]["choisi"])
        self.retour("choisir", r["resultat"])
        self.assertEqual(self.ok("lister")["choix"], "")


class Appels(Monde):
    MSG = [{"role": "user", "content": "Bonjour"}]

    def test_completer_parle_openai_avec_la_cle_et_compte_les_jetons(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses.append((200, ouvert("Salut !", usage=(12, 5))))
        r = self.ok("completer", messages=self.MSG, systeme="Sois bref.", max_tokens=200, temperature=0.2)
        self.assertEqual((r["ok"], r["texte"], r["usage"]), (True, "Salut !", {"prompt_tokens": 12, "completion_tokens": 5}))
        q = self.faux.requetes[-1]
        self.assertEqual((q["chemin"], q["auth"]), ("/chat/completions", "Bearer " + CLE))
        self.assertEqual(q["corps"]["messages"], [{"role": "system", "content": "Sois bref."}] + self.MSG)
        self.assertEqual((q["corps"]["model"], q["corps"]["max_tokens"], q["corps"]["temperature"]), ("gpt-4o-mini", 200, 0.2))
        u = self.ok("usage", compte=ROOT)["total"]
        self.assertEqual(u, {"appels": 1, "echecs": 0, "entrees": 12, "sorties": 5})
        self.assertNotIn("Bonjour", self.tout_le_journal())                      # le contenu des échanges ne va pas au journal
        self.assertNotIn("Salut !", self.tout_le_journal())

    def test_pas_de_modele_pas_de_cle_du_serveur_pour_un_compte(self):
        i = self.instance()
        self.ok("role_lier", role="principal", modele_id=i, compte=ROOT)
        self.assertIn("aucun modèle", self.ok("completer", messages=self.MSG)["erreur"])
        self.assertIn("rôle de la maison", self.ok("completer", messages=self.MSG, role="principal")["erreur"])
        self.assertIn("introuvable", self.ok("completer", messages=self.MSG, modele_id=i)["erreur"])
        self.assertEqual(self.faux.requetes, [])

    def test_un_compte_n_utilise_pas_le_modele_d_un_autre(self):
        autre = self.mien("a-lui", compte=LEO)
        self.assertIn("introuvable", self.ok("completer", messages=self.MSG, modele_id=autre)["erreur"])
        self.assertEqual(self.faux.requetes, [])

    def test_les_acteurs_de_la_maison_servent_les_roles(self):
        i = self.instance()
        self.ok("role_lier", role="relecteur", modele_id=i, compte=ROOT)
        for acteur in ("cassandra", "itare", "agent"):
            r = self.ok("completer", messages=self.MSG, role="relecteur", acteur=acteur)
            self.assertTrue(r["ok"], acteur)
        self.assertIn("n'est lié à aucun modèle", self.ok("completer", messages=self.MSG, role="vision", acteur="itare")["erreur"])
        u = self.ok("usage", compte=ROOT)["lignes"][0]
        self.assertEqual((u["role"], u["appels"]), ("relecteur", 3))

    def test_un_modele_raisonneur_qui_rend_vide_est_rejoue_une_fois_avec_un_budget_triple(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses += [(200, ouvert("", fin="length", reflexion="je réfléchis longuement…")), (200, ouvert("Voilà."))]
        r = self.ok("completer", messages=self.MSG, max_tokens=400, allow_reasoning=False)
        self.assertEqual((r["ok"], r["texte"]), (True, "Voilà."))
        a, b = self.faux.requetes
        self.assertEqual((a["corps"]["max_tokens"], b["corps"]["max_tokens"]), (400, 3000))
        self.assertIn("réflexion a consommé", b["corps"]["messages"][-1]["content"])
        self.faux.reponses += [(200, ouvert("", reflexion="r")), (200, ouvert("", reflexion="r"))]
        r = self.ok("completer", messages=self.MSG, allow_reasoning=False)
        self.assertFalse(r["ok"])
        self.assertIn("VIDE", r["erreur"])
        self.assertEqual(len(self.faux.requetes), 4)                              # un seul rejeu

    def test_le_repli_sur_la_reflexion_est_refusable(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses += [(200, ouvert("", fin="stop", reflexion="{\"a\": 1}")), (200, ouvert("", fin="stop", reflexion="{\"a\": 1}"))]
        r = self.ok("completer", messages=self.MSG, allow_reasoning=True)
        self.assertEqual((r["ok"], r["texte"]), (True, "{\"a\": 1}"))

    def test_une_reponse_coupee_est_dite(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses.append((200, ouvert("def f(", fin="length")))
        r = self.ok("completer", messages=self.MSG, max_tokens=50)
        self.assertEqual(r["texte"], "def f(")
        self.assertIn("TRONQUÉE", r["avertissement"])

    def test_un_endpoint_qui_refuse_la_temperature_est_rejoue_sans(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses += [(400, {"error": "temperature not supported"}), (200, ouvert("ok"))]
        r = self.ok("completer", messages=self.MSG, temperature=0.0)
        self.assertTrue(r["ok"])
        self.assertIn("temperature", self.faux.requetes[0]["corps"])
        self.assertNotIn("temperature", self.faux.requetes[1]["corps"])

    def test_une_panne_est_un_resultat_qui_dit_la_cause_sans_la_cle(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        self.faux.reponses.append((401, {"error": {"message": "bad key %s" % CLE}}))
        r = self.ok("completer", messages=self.MSG)
        self.assertFalse(r["ok"])
        self.assertIn("HTTP 401", r["erreur"])
        self.assertNotIn(CLE, json.dumps(r))
        self.assertEqual(self.ok("usage", compte=ROOT)["total"]["echecs"], 1)
        self.faux.arreter()
        r = self.ok("completer", messages=self.MSG)
        self.assertFalse(r["ok"])
        self.assertNotIn(CLE, json.dumps(r))

    def test_ollama_parle_son_api_native_avec_think_et_num_ctx(self):
        loc = self.ok("ajouter", fournisseur="ollama", nom="qwen2.5:3b")["id"]
        self.ok("choisir", modele_id=loc)
        self.n.reglages.poser("modeles.ollama_num_ctx", 4096, "")
        self.faux.reponses.append((200, {"message": {"content": "Bonjour"}, "done_reason": "stop", "prompt_eval_count": 9, "eval_count": 3}))
        r = self.ok("completer", messages=self.MSG, max_tokens=100, reflexion=False)
        self.assertEqual((r["ok"], r["texte"], r["usage"]), (True, "Bonjour", {"prompt_tokens": 9, "completion_tokens": 3}))
        q = self.faux.requetes[-1]
        self.assertEqual(q["chemin"], "/api/chat")
        self.assertEqual((q["corps"]["think"], q["corps"]["options"]["num_predict"], q["corps"]["options"]["num_ctx"], q["corps"]["stream"]), (False, 100, 4096, False))
        self.assertEqual(q["auth"], "")

    def test_un_modele_local_qui_refuse_think_est_rejoue_sans(self):
        loc = self.ok("ajouter", fournisseur="ollama", nom="petit:1b")["id"]
        self.ok("choisir", modele_id=loc)
        self.faux.reponses += [(400, {"error": "does not support thinking"}), (200, {"message": {"content": "ok"}, "done_reason": "stop"})]
        r = self.ok("completer", messages=self.MSG)
        self.assertEqual(r["texte"], "ok")
        self.assertIn("think", self.faux.requetes[0]["corps"])
        self.assertNotIn("think", self.faux.requetes[1]["corps"])

    def test_un_local_vide_dit_pourquoi(self):
        loc = self.ok("ajouter", fournisseur="ollama", nom="qwen3:4b")["id"]
        self.ok("choisir", modele_id=loc)
        self.faux.reponses.append((200, {"message": {"content": "", "thinking": "hmm"}, "done_reason": "length"}))
        r = self.ok("completer", messages=self.MSG, allow_reasoning=False, reflexion=True)
        self.assertFalse(r["ok"])
        self.assertIn("VIDE", r["erreur"])
        self.assertIn("réflexion demandée", r["erreur"])

    def test_les_parametres_invalides(self):
        mid = self.mien()
        self.ok("choisir", modele_id=mid)
        for args in (dict(messages=[]), dict(messages="x"), dict(messages=self.MSG, max_tokens="beaucoup"), dict(messages=self.MSG, temperature="chaud")):
            self.assertFalse(self.ok("completer", **args)["ok"], args)
        self.assertEqual(self.faux.requetes, [])

    def test_essayer_mesure_garde_le_dernier_essai_et_se_defait(self):
        mid = self.mien()
        self.faux.reponses.append((200, ouvert("prêt")))
        r = self.ex("essayer", id=mid)
        self.assertEqual((r["statut"], r["resultat"]["ok"], r["resultat"]["reponse"]), ("faite", True, "prêt"))
        e = self.ok("lister")["modeles"][0]["essai"]
        self.assertEqual((e["ok"], e["message"]), (True, "prêt"))
        self.retour("essayer", r["resultat"])
        self.assertIsNone(self.ok("lister")["modeles"][0]["essai"])
        self.faux.reponses.append((500, {"error": "boom"}))
        f = self.ok("essayer", id=mid)
        self.assertEqual((f["ok"], "HTTP 500" in f["erreur"]), (False, True))
        self.assertFalse(self.ok("lister")["modeles"][0]["essai"]["ok"])
        self.assertEqual(self.ex("essayer", id=mid, compte=LEO)["statut"], "echec")

    def test_usage_est_reserve_aux_administrateurs(self):
        self.assertEqual(self.ex("usage")["statut"], "refuse")


class Ollama(Monde):
    def test_les_modeles_locaux_et_l_absence_d_ollama(self):
        self.assertEqual([m["name"] for m in self.ok("locaux")["modeles"]], ["qwen2.5:3b"])
        self.assertEqual(self.ok("lister")["locaux"], ["qwen2.5:3b"])
        self.faux.arreter()
        l = self.ok("locaux")
        self.assertEqual((l["repond"], l["modeles"]), (False, []))
        self.assertEqual(self.ok("lister")["locaux"], [])

    def test_telecharger_met_en_file_et_le_moteur_tire_avec_sa_progression(self):
        r = self.ex("ollama_telecharger", nom="llama3.2:1b", compte=ROOT)
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("déjà", self.echec("ollama_telecharger", nom="llama3.2:1b", compte=ROOT))
        self.faux.pull = [{"status": "pulling manifest"}, {"status": "downloading", "total": 100, "completed": 40}, {"status": "success"}]
        self.n.lancer("modeles.pulls")
        p = self.ok("locaux")["telechargements"][0]
        self.assertEqual((p["etat"], p["pourcent"], p["detail"]), ("fait", 100, "success"))
        self.assertEqual([x["corps"]["model"] for x in self.faux.requetes if x["chemin"] == "/api/pull"], ["llama3.2:1b"])
        self.assertEqual(self.ex("ollama_telecharger", nom="x y", compte=ROOT)["statut"], "echec")
        self.assertEqual(self.ex("ollama_telecharger", nom="m:", compte=ROOT)["statut"], "echec")
        self.assertEqual(self.ex("ollama_telecharger", nom="autre", compte=BEA)["statut"], "refuse")

    def test_un_echec_de_tirage_se_dit_et_ne_bloque_pas_la_file(self):
        self.ok("ollama_telecharger", nom="inconnu:1b", compte=ROOT)
        self.ok("ollama_telecharger", nom="bon:1b", compte=ROOT)
        self.faux.pull = [{"error": "model not found"}]
        self.n.lancer("modeles.pulls")
        self.faux.pull = [{"status": "success"}]
        self.n.lancer("modeles.pulls")
        etats = {p["nom"]: (p["etat"], p["detail"]) for p in self.ok("locaux")["telechargements"]}
        self.assertEqual(etats["inconnu:1b"], ("echec", "model not found"))
        self.assertEqual(etats["bon:1b"][0], "fait")

    def test_la_demande_non_commencee_se_retire(self):
        r = self.ex("ollama_telecharger", nom="m:1b", compte=ROOT)
        self.retour("ollama_telecharger", r["resultat"])
        self.assertEqual(self.ok("locaux")["telechargements"], [])

    def test_supprimer_un_local_refuse_un_modele_utilise_et_se_defait_en_remettant_le_tirage_en_file(self):
        loc = self.ok("ajouter", fournisseur="ollama", nom="qwen2.5:3b")["id"]
        self.ok("choisir", modele_id=loc)
        self.assertIn("choix", self.echec("ollama_supprimer", nom="qwen2.5:3b", compte=ROOT))
        self.ok("choisir", modele_id="")
        r = self.ex("ollama_supprimer", nom="qwen2.5:3b", compte=ROOT)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ok("locaux")["modeles"], [])
        self.assertEqual(self.ok("lister")["modeles"], [])
        self.retour("ollama_supprimer", r["resultat"])
        self.assertEqual(self.ok("locaux")["telechargements"][0]["nom"], "qwen2.5:3b")


if __name__ == "__main__":
    unittest.main()
