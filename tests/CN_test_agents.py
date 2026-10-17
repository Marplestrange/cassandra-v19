# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module agents, avec les vrais modules notes, modeles et memoire et un faux modèle
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #2a1f1a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module agents, avec les vrais modules notes, modeles et memoire et un faux modèle qui appelle des outils.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2a1f1a ▼▼▼
"""Bancs du module agents, avec les vrais modules notes, modeles et memoire et un faux modèle qui appelle des outils."""
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

import CN_main as moteur                      # noqa: E402

BEA, LEO, ROOT = "bea@x.fr", "leo@x.fr", "root@x.fr"
CLE_ROLE, CLE_BEA = "sk-LA-CLE-DE-LA-MAISON", "sk-LA-CLE-DE-BEA"


def texte(t):
    return (200, {"choices": [{"message": {"role": "assistant", "content": t}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}})


def appel(nom, args, contenu="", ident=None, brut=None):
    return (200, {"choices": [{"message": {"role": "assistant", "content": contenu, "tool_calls": [{"id": ident or "call_1", "type": "function",
                  "function": {"name": nom, "arguments": brut if brut is not None else json.dumps(args)}}]}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 9, "completion_tokens": 4}})


class FauxModele:
    def __init__(self):
        self.reponses, self.requetes = [], []
        faux = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(n).decode()) if n else {}
                faux.requetes.append({"auth": self.headers.get("Authorization", ""), "corps": corps})
                r = faux.reponses.pop(0) if faux.reponses else texte("ok")
                statut, c = r() if callable(r) else r
                data = json.dumps(c).encode()
                self.send_response(statut)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("agents", "notes", "modeles", "memoire"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("modeles", "memoire", "notes", "agents"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ROOT, True)
        self.faux = FauxModele()
        self.addCleanup(self.faux.arreter)
        # le modèle de la maison, lié au rôle de Cassandra ; Bea a le sien pour Itare
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="maison", cle=CLE_ROLE, base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="principal", modele_id=mid)
        for cap in ("notes.creer", "notes.ecrire", "notes.supprimer"):
            self.n.catalogue.regler_palier(cap, "auto")
        self.ctx = self.n.executeur.contextes["agents"]
        self.db = self.ctx.stockage

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def agent(self, cap, compte=BEA, **args):
        r = self.ex("agents." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def causer(self, message, reponses=None, **kw):
        if reponses:
            self.faux.reponses += reponses
        return self.agent("converser", message=message, **kw)

    def notes(self, compte=BEA):
        return self.ex("notes.lister", compte=compte)["resultat"]["notes"]

    def msgs(self, cid, compte=BEA):
        return self.agent("conversation", id=cid, compte=compte)["messages"]


class Conversation(Monde):
    def test_un_tour_simple_garde_les_messages_titre_la_conversation_et_cite_la_memoire(self):
        self.n.reglages.poser("memoire.seuil_rappel_pct", 5, "")
        self.ex("memoire.ecrire", compte=BEA, acteur="cassandra", categorie="config", cle="nginx-port", valeur="nginx écoute sur le port 8080 pour le site principal", nature="constat", provenance="dit")
        self.n.catalogue.regler_palier("memoire.ecrire", "auto")
        self.ex("memoire.ecrire", compte=BEA, categorie="config", cle="nginx-port", valeur="nginx écoute sur le port 8080 pour le site principal", nature="constat", provenance="dit")
        r = self.causer("Sur quel port nginx écoute-t-il ?", [texte("Sur le port 8080 [M:1].")])
        self.assertEqual((r["texte"], r["agent"], r["actions"]), ("Sur le port 8080 [M:1].", "cassandra", []))
        m = self.msgs(r["conversation_id"])
        self.assertEqual([(x["role"], x["contenu"][:20]) for x in m], [("user", "Sur quel port nginx "), ("assistant", "Sur le port 8080 [M:")])
        self.assertEqual(self.agent("conversations")["conversations"][0]["titre"], "Sur quel port nginx écoute-t-il ?")
        q = self.faux.requetes[0]
        self.assertEqual(q["auth"], "Bearer " + CLE_ROLE)
        sysm = q["corps"]["messages"][0]["content"]
        self.assertIn("Tu es CASSANDRA", sysm)
        self.assertIn("Tu parles avec **%s**" % BEA, sysm)
        self.assertIn("nginx écoute sur le port 8080", sysm)                  # le rappel de la mémoire est dans le prompt
        self.assertIn("## RÈGLES (non négociables)", sysm)
        self.assertEqual(q["corps"]["messages"][-1], {"role": "user", "content": "Sur quel port nginx écoute-t-il ?"})
        self.assertTrue(any(t["function"]["name"] == "outil_cherche" for t in q["corps"]["tools"]))

    def test_le_fil_est_relu_au_tour_suivant(self):
        r = self.causer("Bonjour", [texte("Bonjour !")])
        self.causer("Et maintenant ?", [texte("Maintenant, rien.")], conversation_id=r["conversation_id"])
        roles = [(m["role"], m["content"]) for m in self.faux.requetes[1]["corps"]["messages"] if m["role"] != "system"]
        self.assertEqual(roles, [("user", "Bonjour"), ("assistant", "Bonjour !"), ("user", "Et maintenant ?")])

    def test_le_ton_de_l_instance_et_celui_du_compte_entrent_dans_le_prompt(self):
        self.n.reglages.poser("agents.persona_cassandra", "Réponds toujours en trois phrases au plus.", "")
        self.n.reglages.poser("modeles.ton", "Tutoie-moi, s'il te plaît.", BEA)
        self.causer("Salut", [texte("Salut.")])
        s = self.faux.requetes[0]["corps"]["messages"][0]["content"]
        self.assertIn("Réponds toujours en trois phrases au plus.", s)
        self.assertIn("Tutoie-moi, s'il te plaît.", s)

    def test_les_refus_et_le_cloisonnement(self):
        for args in (dict(message="  "), dict(message="x" * 20001)):
            self.assertEqual(self.ex("agents.converser", **args)["statut"], "echec", args)
        r = self.causer("Un message de Bea", [texte("Reçu.")])
        cid = r["conversation_id"]
        for cap, args in (("conversation", {}), ("conversation_renommer", dict(titre="x")), ("conversation_supprimer", {}), ("arreter", {})):
            self.assertEqual(self.ex("agents." + cap, compte=LEO, id=cid, **args)["statut"], "echec", cap)
        self.assertEqual(self.ex("agents.converser", compte=LEO, conversation_id=cid, message="intrus")["statut"], "echec")
        self.assertEqual(self.agent("conversations", compte=LEO)["conversations"], [])
        for compte in ("", "cassandra", "itare"):
            self.assertEqual(self.ex("agents.converser", compte=compte, message="x")["statut"], "echec")

    def test_un_tour_a_la_fois_par_conversation(self):
        r = self.causer("Bonjour", [texte("Bonjour !")])
        self.db.ecrire("UPDATE conversations SET en_cours=? WHERE id=?", (__import__("time").time(), r["conversation_id"]))
        e = self.ex("agents.converser", conversation_id=r["conversation_id"], message="Encore")
        self.assertEqual((e["statut"], "déjà en cours" in e["erreur"]), ("echec", True))
        self.db.ecrire("UPDATE conversations SET en_cours=? WHERE id=?", (__import__("time").time() - 700, r["conversation_id"]))     # un tour mort depuis dix minutes ne bloque plus
        self.causer("Encore", [texte("Oui.")], conversation_id=r["conversation_id"])

    def test_crud_et_retours(self):
        c = self.ex("agents.conversation_creer", agent="itare", titre="Mon bureau")
        cid = c["resultat"]["id"]
        self.assertEqual(self.agent("conversations")["conversations"][0]["agent"], "itare")
        self.assertEqual(self.ex("agents.conversation_creer", agent="inconnu")["statut"], "echec")
        r = self.ex("agents.conversation_renommer", id=cid, titre="Autre")
        self.n.catalogue.get("agents.conversation_renommer").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.agent("conversations")["conversations"][0]["titre"], "Mon bureau")
        self.assertEqual(self.ex("agents.conversation_renommer", id=cid, titre=" ")["statut"], "echec")
        self.causer("Bonjour", [texte("Bonjour !")], conversation_id=cid)
        d = self.ex("agents.conversation_supprimer", id=cid)
        self.assertEqual(self.agent("conversations")["conversations"], [])
        self.n.catalogue.get("agents.conversation_supprimer").defaire(self.ctx, d["resultat"])
        self.assertEqual(len(self.msgs(cid)), 2)
        self.n.catalogue.get("agents.conversation_creer").defaire(self.ctx, c["resultat"])
        self.assertEqual(self.agent("conversations")["conversations"], [])

    def test_le_retour_d_un_tour_retire_ses_messages(self):
        r = self.ex("agents.converser", message="Bonjour")
        self.faux.reponses.clear()
        res = r["resultat"]
        self.assertEqual(len(self.msgs(res["conversation_id"])), 2)
        self.n.catalogue.get("agents.converser").defaire(self.ctx, res)
        self.assertEqual(self.msgs(res["conversation_id"]), [])


class Outils(Monde):
    def test_les_outils_derivent_du_catalogue_et_respectent_les_droits_du_compte(self):
        noms = {t["cle"] for t in self.agent("outils")["outils"]}
        self.assertIn("notes.creer", noms)
        self.assertIn("memoire.rappeler", noms)
        self.assertNotIn("modeles.usage", noms)                             # le droit d'administrer manque à Bea
        self.assertNotIn("agents.converser", noms)                          # un agent n'appelle pas les agents
        self.assertIn("modeles.usage", {t["cle"] for t in self.agent("outils", compte=ROOT)["outils"]})
        t = {x["cle"]: x for x in self.agent("outils")["outils"]}["notes.creer"]
        self.assertEqual((t["risque"], t["palier"], "titre" in t["arguments"]), ("faible", "auto", True))

    def test_un_outil_appele_agit_au_nom_du_compte_et_le_resultat_revient_au_modele(self):
        r = self.causer("Crée une note « Courses » avec du lait", [appel("notes__creer", {"titre": "Courses", "corps": "du lait"}), texte("C'est fait : la note Courses existe.")])
        self.assertEqual(r["texte"], "C'est fait : la note Courses existe.")
        self.assertEqual([(n["titre"], n["id"]) for n in self.notes()], [("Courses", "N-0001")])
        self.assertEqual(self.notes(LEO), [])                                # la note est à Bea
        self.assertEqual([(a["cle"], a["statut"], a["risque"]) for a in r["actions"]], [("notes.creer", "faite", "faible")])
        # l'ordre exigé par l'API : l'assistant (avec ses appels) PUIS la réponse de l'outil
        m2 = self.faux.requetes[1]["corps"]["messages"]
        assert_ordre = [(x["role"], bool(x.get("tool_calls"))) for x in m2 if x["role"] != "system"]
        self.assertEqual(assert_ordre, [("user", False), ("assistant", True), ("tool", False)])
        self.assertEqual(m2[-1]["tool_call_id"], "call_1")
        self.assertIn('"ref": "N-0001"', m2[-1]["content"])
        m = self.msgs(r["conversation_id"])
        self.assertEqual([x["role"] for x in m], ["user", "assistant", "tool", "assistant"])
        self.assertEqual((m[1]["appels"][0]["function"]["name"], m[2]["nom"], m[2]["statut"]), ("notes__creer", "notes__creer", "faite"))
        j = [e for e in self.n.bus.recents(portee="*", limite=500) if e["type"] == "capacite.demandee" and e["acteur"] == "cassandra" and e["objet_id"] == "notes.creer"]
        self.assertEqual((len(j), j[0]["compte"]), (1, BEA))                 # l'acte est au journal, de l'agent, au nom de Bea

    def test_un_outil_au_palier_raconter_n_a_rien_fait_et_l_agent_le_sait(self):
        self.n.catalogue.regler_palier("notes.creer", "raconter")
        r = self.causer("Crée une note Courses", [appel("notes__creer", {"titre": "Courses"}), texte("Je ne l'ai pas créée : l'outil est seulement raconté.")])
        self.assertEqual(self.notes(), [])
        tool = self.faux.requetes[1]["corps"]["messages"][-1]["content"]
        self.assertIn("Non exécuté", tool)
        self.assertIn("palier « raconter »", tool)
        self.assertIn("créerait la note « Courses »", tool)                 # ce que l'acte aurait été
        self.assertEqual(r["actions"][0]["statut"], "racontee")

    def test_chaque_appel_recoit_sa_reponse_meme_inconnu_illisible_ou_en_echec(self):
        r = self.causer("Teste", [
            (200, {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
                {"id": "a", "type": "function", "function": {"name": "outil_inexistant", "arguments": "{}"}},
                {"id": "b", "type": "function", "function": {"name": "notes__creer", "arguments": "{pas du json"}},
                {"id": "c", "type": "function", "function": {"name": "notes__creer", "arguments": json.dumps({"titre": "  "})}},
                {"id": "d", "type": "function", "function": {"name": "notes__creer", "arguments": json.dumps({"titre": "ok", "inconnu": 1})}}]}, "finish_reason": "tool_calls"}]}),
            texte("J'ai corrigé.")])
        tools = [m for m in self.faux.requetes[1]["corps"]["messages"] if m["role"] == "tool"]
        self.assertEqual([t["tool_call_id"] for t in tools], ["a", "b", "c", "d"])
        self.assertIn("Outil inconnu", tools[0]["content"])
        self.assertIn("Arguments illisibles", tools[1]["content"])
        self.assertIn("Échec : une note a besoin d'un titre", tools[2]["content"])
        self.assertTrue(tools[3]["content"].startswith("Échec"))
        self.assertEqual(r["texte"], "J'ai corrigé.")
        self.assertEqual(self.notes(), [])

    def test_outil_cherche_et_outil_appeler_atteignent_toute_la_surface(self):
        self.n.reglages.poser("agents.max_outils", 10, "")
        r = self.causer("Fais un truc", [appel("outil_cherche", {"requete": "créer une note"}),
                                          appel("outil_appeler", {"cle": "notes.creer", "arguments": {"titre": "Via la meta"}}, ident="call_2"), texte("Fait.")])
        trouve = json.loads(self.faux.requetes[1]["corps"]["messages"][-1]["content"])
        self.assertIn("notes.creer", [t["cle"] for t in trouve])
        self.assertEqual([n["titre"] for n in self.notes()], ["Via la meta"])
        n_presentes = len([t for t in self.faux.requetes[0]["corps"]["tools"] if t["function"]["name"] not in ("outil_cherche", "outil_appeler")])
        self.assertLessEqual(n_presentes, 10)

    def test_les_outils_presentes_sont_ceux_qui_touchent_la_demande(self):
        outils = self.agent("outils")["outils"]
        o = self.n.catalogue.get("agents.converser").faire.__globals__["o"]
        tous = [dict(t, parametres={"properties": {}}) for t in outils]
        choisis = o.choisir_outils(tous, "peux-tu créer une note sur le certificat ?", 5)
        self.assertEqual(choisis[0]["cle"], "notes.creer")
        self.assertEqual(len(choisis), 5)
        sans = o.choisir_outils(tous, "zzz", 3)
        self.assertEqual(len(sans), 3)                                        # sans rien qui touche : des lectures, utiles pour vérifier
        self.assertTrue(all(t["risque"] == "lecture" for t in sans))


class Teinte(Monde):
    def setUp(self):
        super().setUp()
        # notes.lister vient de l'extérieur, le partage sort de la maison : les drapeaux que portent courrier et telegram
        object.__setattr__(self.n.catalogue.get("notes.lister").capacite, "externe", True)
        object.__setattr__(self.n.catalogue.get("notes.partage_creer").capacite, "sortant", True)
        for cap in ("notes.partage_creer", "notes.vider_corbeille"):                     # ces gestes sont réservés aux humains : on les ouvre aux agents le temps du banc
            c = self.n.catalogue.get(cap).capacite
            object.__setattr__(c, "qui", tuple(c.qui) + ("cassandra", "itare"))
        self.n.catalogue.regler_palier("notes.partage_creer", "auto")
        self.ex("notes.creer", acteur="humain", titre="À partager", corps="x")

    def test_apres_une_lecture_exterieure_ce_qui_sort_ne_part_pas_seul(self):
        r = self.causer("Partage ma note", [appel("notes__lister", {}), appel("notes__partage_creer", {"ref": "N-0001"}, ident="call_2"), texte("Je n'ai rien partagé : il faut ta confirmation.")])
        tool = self.faux.requetes[2]["corps"]["messages"][-1]["content"]
        self.assertIn("Non exécuté : ce tour a lu du contenu venu de l'extérieur (notes.lister)", tool)
        self.assertEqual(self.ex("notes.partages")["resultat"]["liens"], [])
        self.assertEqual(r["teinte"], ["notes.lister"])
        self.assertEqual([a["statut"] for a in r["actions"]], ["faite", "retenue"])

    def test_au_tour_suivant_la_personne_confirme_et_ca_part(self):
        c = self.causer("Partage ma note", [appel("notes__lister", {}), appel("notes__partage_creer", {"ref": "N-0001"}, ident="call_2"), texte("Il faut ta confirmation.")])
        self.causer("Oui, partage-la", [appel("notes__partage_creer", {"ref": "N-0001"}), texte("Partagée.")], conversation_id=c["conversation_id"])
        self.assertEqual(len(self.ex("notes.partages")["resultat"]["liens"]), 1)

    def test_sans_lecture_exterieure_le_partage_part_au_palier_choisi(self):
        self.causer("Partage ma note", [appel("notes__partage_creer", {"ref": "N-0001"}), texte("Partagée.")])
        self.assertEqual(len(self.ex("notes.partages")["resultat"]["liens"]), 1)

    def test_une_ecriture_a_risque_moyen_est_aussi_retenue_apres_une_lecture_etrangere(self):
        self.n.catalogue.regler_palier("notes.supprimer", "auto")
        self.causer("Nettoie", [appel("notes__lister", {}), appel("outil_appeler", {"cle": "notes.vider_corbeille", "arguments": {}}, ident="call_2"), texte("Retenu.")])
        self.assertIn("Non exécuté", self.faux.requetes[2]["corps"]["messages"][-1]["content"])


class Pannes(Monde):
    def test_une_panne_du_modele_est_gardee_a_part_et_ne_revient_pas_dans_le_contexte(self):
        self.faux.reponses.append((500, {"error": "boom"}))
        r = self.causer("Bonjour")
        self.assertEqual(r["texte"], "")
        self.assertEqual([a["statut"] for a in r["actions"]], ["panne"])
        m = self.msgs(r["conversation_id"])
        self.assertEqual([x["role"] for x in m], ["user", "panne"])
        self.assertIn("Panne de Cassandra", m[1]["contenu"])
        self.assertIn("HTTP 500", m[1]["contenu"])
        self.causer("Tu es là ?", [texte("Oui.")], conversation_id=r["conversation_id"])
        envoye = [x["content"] for x in self.faux.requetes[-1]["corps"]["messages"] if x["role"] != "system"]
        self.assertEqual(envoye, ["Bonjour", "Tu es là ?"])

    def test_pas_de_modele_lie_se_dit_au_lieu_de_planter(self):
        self.ex("modeles.role_lier", compte=ROOT, role="principal", modele_id="")
        r = self.causer("Bonjour")
        self.assertIn("n'est lié à aucun modèle", self.msgs(r["conversation_id"])[-1]["contenu"])

    def test_trop_d_etapes_arrete_le_tour_en_le_disant(self):
        self.n.reglages.poser("agents.max_tours", 3, "")
        r = self.causer("Boucle", [appel("notes__lister", {}, ident="c%d" % i) for i in range(5)])
        m = self.msgs(r["conversation_id"])
        self.assertEqual(m[-1]["role"], "panne")
        self.assertIn("Trop d'étapes", m[-1]["contenu"])
        self.assertEqual(len([x for x in m if x["role"] == "tool"]), 3)

    def test_des_outils_puis_rien_le_modele_est_prie_de_conclure_une_fois(self):
        r = self.causer("Liste", [appel("notes__lister", {}), texte(""), texte("Voilà : aucune note.")])
        self.assertEqual(r["texte"], "Voilà : aucune note.")
        dernier = self.faux.requetes[-1]["corps"]["messages"][-1]
        self.assertEqual(dernier["role"], "user")
        self.assertIn("Conclus maintenant en clair", dernier["content"])

    def test_arreter_est_lu_entre_deux_etapes_et_une_action_lancee_finit(self):
        cid = self.agent("conversation_creer")["id"]

        def demander_l_arret():
            self.ex("agents.arreter", id=cid)
            return appel("notes__creer", {"titre": "Lancée avant l'arrêt"})
        r = self.causer("Crée puis continue", [demander_l_arret, texte("Ne devrait pas être lu.")], conversation_id=cid)
        self.assertEqual([n["titre"] for n in self.notes()], ["Lancée avant l'arrêt"])          # l'action en cours a fini
        self.assertEqual(r["texte"], "")
        self.assertEqual(r["actions"][-1]["statut"], "arrete")
        self.assertEqual(self.msgs(cid)[-1]["contenu"], "Tour arrêté à ta demande.")
        self.assertEqual(len(self.faux.requetes), 1)                                        # le modèle n'a pas été rappelé
        self.causer("Reprenons", [texte("Reprise.")], conversation_id=cid)                  # la demande d'arrêt s'efface au début du tour suivant

    def test_le_fil_incoherent_est_remis_en_ordre_avant_l_envoi(self):
        o = self.n.catalogue.get("agents.converser").faire.__globals__["o"]
        msgs = [{"role": "tool", "tool_call_id": "z", "content": "orpheline"}, {"role": "user", "content": "a"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x", "arguments": "{}"}}, {"id": "2", "type": "function", "function": {"name": "y", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "1", "content": "r1"}, {"role": "assistant", "content": "fin"}]
        out = o.coherents(msgs)
        self.assertEqual([(m["role"], m.get("tool_call_id")) for m in out], [("user", None), ("assistant", None), ("tool", "1"), ("tool", "2"), ("assistant", None)])
        self.assertIn("résultat perdu", out[3]["content"])


class Itare(Monde):
    def test_itare_parle_par_le_modele_du_compte_puis_par_son_role(self):
        mien = self.ex("modeles.ajouter", fournisseur="personnalise", nom="le-sien", cle=CLE_BEA, base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.choisir", modele_id=mien)
        r = self.causer("Range mon bureau", [texte("Rangé.")], agent="itare")
        self.assertEqual((r["agent"], self.faux.requetes[0]["auth"]), ("itare", "Bearer " + CLE_BEA))
        self.assertIn("Tu es ITARE", self.faux.requetes[0]["corps"]["messages"][0]["content"])
        self.ex("modeles.choisir", modele_id="")
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="citadelle", cle="sk-citadelle", base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="itare_citadelle", modele_id=mid)
        self.causer("Encore", [texte("Oui.")], conversation_id=r["conversation_id"])
        self.assertEqual(self.faux.requetes[1]["auth"], "Bearer sk-citadelle")

    def test_un_compte_sans_modele_ne_se_sert_pas_de_la_cle_de_la_maison_pour_itare(self):
        r = self.causer("Bonjour", agent="itare")
        self.assertEqual(self.faux.requetes, [])
        self.assertIn("panne", [m["role"] for m in self.msgs(r["conversation_id"])])


class Memoire(Monde):
    def test_la_fin_d_un_tour_nourrit_l_episode_et_met_la_distillation_en_file(self):
        r = self.causer("Retiens que le serveur de courrier est exim4", [texte("C'est noté.")])
        mem = self.n.executeur.contextes["memoire"].stockage
        self.assertEqual(len(mem.lire("SELECT * FROM episodes")), 1)
        self.assertEqual([m["role"] for m in mem.lire("SELECT role FROM messages")], ["user", "assistant"])
        f = mem.lire("SELECT * FROM file")
        self.assertEqual((len(f), f[0]["declencheur"], f[0]["compte"], f[0]["acteur"]), (1, "reponse_utilisateur", BEA, "cassandra"))
        self.assertEqual(mem.lire("SELECT question FROM tours WHERE compte=?", (BEA,))[0]["question"], "Retiens que le serveur de courrier est exim4")

    def test_repondre_a_un_doute_dans_le_chat_le_resout(self):
        self.n.catalogue.regler_palier("memoire.ecrire", "auto")
        self.ex("memoire.ecrire", categorie="config", cle="k", valeur="nginx écoute sur le port 8080 pour le site", nature="constat", provenance="dit")
        self.ex("memoire.ecrire", categorie="config", cle="k", valeur="nginx écoute sur le port 8081 pour le site", nature="constat", provenance="infere")
        d = self.ex("memoire.doutes")["resultat"]["doutes"][0]["id"]
        self.causer("doute %d : active" % d, [texte("Gardé.")])
        self.assertEqual(self.ex("memoire.doutes", statut="resolu")["resultat"]["doutes"][0]["id"], d)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : texte, appel, FauxModele, Monde, Conversation, Outils, Teinte, Pannes …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
