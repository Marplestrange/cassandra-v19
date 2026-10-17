"""Bancs du salon : fils, messages, cloisonnement, présence des agents résidents (avec un faux modèle réel : la chaîne agents -> modèles est celle du service)."""
import importlib.util
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402
from CN_test_agents import FauxModele, texte, CLE_ROLE   # noqa: E402

spec = importlib.util.spec_from_file_location("salon_module_test", RACINE / "modules" / "salon" / "CN_module.py")
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)

BEA, LEO, ROOT = "bea@x.fr", "leo@x.fr", "root@x.fr"


class Pures(unittest.TestCase):
    def test_les_destinataires_sont_un_champ_normalise(self):
        self.assertEqual(sm.destinataires_de("@Cassandra, itare  tous"), ["cassandra", "itare", sm.TOUS])
        self.assertEqual(sm.destinataires_de(["Humain:bea@x.fr", "invité:Claude", "x" * 80]), ["humain:bea@x.fr", "claude", "x" * 32])
        self.assertEqual(sm.destinataires_de(None), [])
        self.assertEqual(sm.destinataires_de(["cassandra", "CASSANDRA", "@cassandra"]), ["cassandra"])

    def test_la_requete_plein_texte_est_sure(self):
        self.assertEqual(sm.requete_fts('sauvegarde" OR 1=1 --'), '"sauvegarde"* AND "or"*')                  # la syntaxe du moteur ne passe jamais : des mots entiers, entre guillemets
        self.assertEqual(sm.requete_fts("  "), "")
        self.assertEqual(sm.requete_fts("migration serveur"), '"migration"* AND "serveur"*')


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("salon", "agents", "modeles", "memoire", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "modeles", "memoire", "agents", "comptes", "salon"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ROOT, True)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        for c in (BEA, LEO):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": "Essai-Local-1234"}, compte="operateur")
        self.faux = FauxModele()
        self.addCleanup(self.faux.arreter)
        self.addCleanup(self.n.arreter)
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="maison", cle=CLE_ROLE, base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="principal", modele_id=mid)
        self.ex("modeles.role_lier", compte=ROOT, role="itare_citadelle", modele_id=mid)
        self.ctx = self.n.executeur.contextes["salon"]
        self.db = self.ctx.stockage
        for cap in ("dire", "fil_creer", "fil_supprimer", "fil_statut", "fil_mode", "fil_terrain", "message_supprimer", "membre_inviter", "membre_retirer", "ranger", "vu", "relancer"):
            self.n.catalogue.regler_palier("salon." + cap, "auto")

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("salon." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def inviter(self, fil, cible, par=BEA):
        """Inviter : « compte » est ici l'invité, et c'est `par` qui agit."""
        r = self.n.executeur.executer("salon.membre_inviter", "humain", {"fil": fil, "compte": cible}, compte=par)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def retirer(self, fil, cible, par=BEA):
        return self.n.executeur.executer("salon.membre_retirer", "humain", {"fil": fil, "compte": cible}, compte=par)

    def echec(self, cap, compte=BEA, **args):
        r = self.ex("salon." + cap, compte=compte, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def fil(self, compte=BEA, titre="Migration", **kw):
        return self.s("fil_creer", compte=compte, titre=titre, **kw)["id"]

    def attendre(self, fil, auteur, n=1, compte=BEA, delai=40):
        fin = time.time() + delai
        while time.time() < fin:
            msgs = [m for m in self.s("lire", compte=compte, fil=fil)["messages"] if m["auteur"] == auteur]
            if len(msgs) >= n:
                return msgs
            time.sleep(0.2)
        self.fail("aucun message de %s dans le fil %s : %s" % (auteur, fil, [(m["auteur"], m["corps"][:40]) for m in self.s("lire", compte=compte, fil=fil)["messages"]]))


class Fils(Monde):
    def test_un_fil_et_ses_messages(self):
        f = self.fil(but="passer à la v19")
        r = self.s("dire", fil=f, corps="Bonjour le fil", destinataires=["humain:leo@x.fr"])
        self.assertEqual((r["auteur"], r["destinataires"]), ("humain:bea@x.fr", ["humain:leo@x.fr"]))
        m = self.s("lire", fil=f)["messages"]
        self.assertEqual([(x["auteur"], x["humain"], x["corps"]) for x in m], [("humain:bea@x.fr", 1, "Bonjour le fil")])
        self.assertEqual(self.s("fils")["fils"][0]["n"], 1)
        self.assertEqual(self.echec("dire", fil=f, corps="   "), "message vide")

    def test_cloisonne_meme_pour_l_administrateur(self):
        f = self.fil()
        self.s("dire", fil=f, corps="secret de Bea")
        for compte in (LEO, ROOT):
            self.assertEqual(self.s("fils", compte=compte)["fils"], [])
            self.assertEqual(self.echec("lire", compte=compte, fil=f), "fil inconnu")
            self.assertEqual(self.echec("dire", compte=compte, fil=f, corps="intrus"), "fil inconnu")
            self.assertEqual(self.s("chercher", compte=compte, question="secret")["resultats"], [])
        self.assertEqual(len(self.s("chercher", question="secret")["resultats"]), 1)

    def test_inviter_quitter_et_les_gestes_du_proprietaire(self):
        f = self.fil()
        res = self.inviter(f, LEO)
        self.assertEqual([x["id"] for x in self.s("fils", compte=LEO)["fils"]], [f])
        self.s("dire", compte=LEO, fil=f, corps="Leo entre")
        self.assertIn("propriétaire", self.echec("fil_supprimer", compte=LEO, fil=f))
        self.assertEqual(self.n.executeur.executer("salon.membre_inviter", "humain", {"fil": f, "compte": "inconnu@x.fr"}, compte=BEA)["statut"], "echec")
        self.assertIn("le propriétaire ne quitte pas", self.n.executeur.executer("salon.membre_retirer", "humain", {"fil": f, "compte": BEA}, compte=BEA)["erreur"])
        self.assertEqual(self.retirer(f, LEO, par=LEO)["statut"], "faite")                       # on quitte son fil soi-même
        self.assertEqual(self.s("fils", compte=LEO)["fils"], [])
        self.n.catalogue.get("salon.membre_inviter").defaire(self.ctx, res)
        self.assertEqual(self.s("membres", fil=f)["membres"], [])

    def test_ranger_est_un_rangement_du_compte_pas_un_statut_du_fil(self):
        f = self.fil()
        self.inviter(f, LEO)
        self.s("ranger", compte=LEO, fil=f)
        self.assertEqual(self.s("fils", compte=LEO)["fils"], [])
        self.assertEqual(self.s("fils", compte=LEO, archives=True)["fils"][0]["range"], "archive")
        self.assertEqual([x["id"] for x in self.s("fils", compte=BEA)["fils"]], [f])              # pour Bea, le fil est toujours là
        self.s("ranger", compte=LEO, fil=f, archive=False)
        self.assertEqual(len(self.s("fils", compte=LEO)["fils"]), 1)

    def test_les_non_lus_se_comptent_depuis_ce_que_chacun_a_lu(self):
        f = self.fil()
        self.inviter(f, LEO)
        for i in range(3):
            self.s("dire", fil=f, corps="message %d" % i)
        self.assertEqual(self.s("fils", compte=LEO)["fils"][0]["nonlus"], 3)
        self.assertEqual(self.s("fils", compte=BEA)["fils"][0]["nonlus"], 0)                     # ses propres messages ne sont pas « non lus »
        r = self.s("vu", compte=LEO, fil=f)
        self.assertEqual(self.s("fils", compte=LEO)["fils"][0]["nonlus"], 0)
        self.s("dire", fil=f, corps="un de plus")
        self.assertEqual(self.s("fils", compte=LEO)["fils"][0]["nonlus"], 1)
        self.n.catalogue.get("salon.vu").defaire(self.ctx, dict(r, fil=f))

    def test_un_humain_qui_parle_rouvre_un_fil_en_attente(self):
        f = self.fil()
        self.s("fil_statut", fil=f, statut="attente")
        self.assertEqual(self.s("fils")["fils"][0]["statut"], "attente")
        self.s("dire", fil=f, corps="je reprends")
        self.assertEqual(self.s("fils")["fils"][0]["statut"], "ouvert")
        self.assertIn("statut inconnu", self.echec("fil_statut", fil=f, statut="n'importe quoi"))

    def test_modes_et_terrains(self):
        f = self.fil(terrain="desk")
        self.assertEqual(self.s("fils")["fils"][0]["terrain"], "desk")
        r = self.s("fil_terrain", fil=f, terrain="citadelle")
        self.assertIn("terrain inconnu", self.echec("fil_terrain", fil=f, terrain="lune"))
        self.assertIn("terrain inconnu", self.echec("fil_creer", titre="x", terrain="lune"))
        self.n.catalogue.get("salon.fil_terrain").defaire(self.ctx, r)
        self.assertEqual(self.s("fils")["fils"][0]["terrain"], "desk")
        self.s("fil_mode", fil=f, mode="plan")
        self.assertIn("mode inconnu", self.echec("fil_mode", fil=f, mode="foncer"))

    def test_supprimer_laisse_la_trace_avant_et_se_defait(self):
        f = self.fil(titre="À jeter")
        a = self.s("dire", fil=f, corps="un")["id"]
        self.s("dire", fil=f, corps="deux")
        res = self.s("fil_supprimer", fil=f)
        self.assertEqual(self.s("fils")["fils"], [])
        j = self.s("journal")["journal"][0]
        self.assertEqual((j["geste"], j["titre"], j["messages"]), ("suppression", "À jeter", 2))   # qui, quoi, combien : écrit avant d'effacer
        self.assertEqual(self.db.lire("SELECT COUNT(*) AS n FROM messages_fts WHERE messages_fts MATCH 'deux'")[0]["n"], 0)
        self.n.catalogue.get("salon.fil_supprimer").defaire(self.ctx, res)
        self.assertEqual(len(self.s("lire", fil=f)["messages"]), 2)
        self.assertEqual(len(self.s("chercher", question="deux")["resultats"]), 1)                # l'index suit la restauration
        m = self.s("message_supprimer", fil=f, id=a)
        self.assertEqual(self.s("journal")["journal"][0]["geste"], "message supprimé")
        self.n.catalogue.get("salon.message_supprimer").defaire(self.ctx, m)
        self.assertEqual(len(self.s("lire", fil=f)["messages"]), 2)

    def test_seuls_l_auteur_ou_le_proprietaire_suppriment_un_message(self):
        f = self.fil()
        self.inviter(f, LEO)
        m = self.s("dire", compte=LEO, fil=f, corps="de Leo")["id"]
        b = self.s("dire", fil=f, corps="de Bea")["id"]
        self.assertIn("seul l'auteur", self.echec("message_supprimer", compte=LEO, fil=f, id=b))
        self.s("message_supprimer", compte=BEA, fil=f, id=m)                                      # le propriétaire du fil peut

    def test_lire_par_pages_et_incrementalement(self):
        f = self.fil()
        ids = [self.s("dire", fil=f, corps="m%d" % i)["id"] for i in range(7)]
        self.assertEqual([m["id"] for m in self.s("lire", fil=f, limite=3)["messages"]], ids[-3:])
        self.assertEqual([m["id"] for m in self.s("lire", fil=f, depuis=ids[4])["messages"]], ids[5:])
        self.assertEqual([m["id"] for m in self.s("lire", fil=f, avant=ids[4], limite=2)["messages"]], ids[2:4])

    def test_attendre_rend_le_message_qui_arrive(self):
        f = self.fil()
        dernier = self.s("dire", fil=f, corps="avant")["id"]
        import threading
        threading.Timer(0.6, lambda: self.ex("salon.dire", fil=f, corps="arrive")).start()
        t0 = time.time()
        r = self.s("attendre", fil=f, depuis=dernier, delai=10)
        self.assertEqual([m["corps"] for m in r["messages"]], ["arrive"])
        self.assertLess(time.time() - t0, 8)
        self.assertEqual(self.s("attendre", fil=f, depuis=r["messages"][0]["id"], delai=1)["messages"], [])


class Presence(Monde):
    def test_un_message_adresse_a_cassandra_la_fait_repondre_dans_le_fil(self):
        f = self.fil(titre="Disque", but="comprendre le disque plein")
        self.faux.reponses.append(texte("Le disque est à 91 %, c'est /var/log."))
        t0 = time.time()
        self.s("dire", fil=f, corps="Cassandra, où en est le disque ?", destinataires=["cassandra"])
        self.assertLess(time.time() - t0, 5)                                                    # poster ne retient pas : le tour se passe à part
        r = self.attendre(f, "cassandra")[0]
        self.assertEqual(r["corps"], "Le disque est à 91 %, c'est /var/log.")
        self.assertEqual(r["destinataires"], ["humain:bea@x.fr"])                               # elle répond à celui qui a parlé
        envoye = json.dumps(self.faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("comprendre le disque plein", envoye)                                     # elle connaît le but du fil
        self.assertIn("où en est le disque", envoye)
        # la présence revient à « veille » une fois le tour TERMINÉ : le message apparaît avant le `fin` du tour (le fil asynchrone n'a pas encore posé `fin`)
        fin = time.time() + 5
        while time.time() < fin and not self.db.lire("SELECT 1 FROM tours WHERE agent='cassandra' AND fin IS NOT NULL"):
            time.sleep(0.05)
        self.assertEqual(self.s("etat")["residents"][0]["etat"], "veille")

    def test_un_message_sans_destinataire_ne_reveille_personne(self):
        f = self.fil()
        self.s("dire", fil=f, corps="je note pour moi")
        time.sleep(1.0)
        self.assertEqual(self.faux.requetes, [])

    def test_rien_est_une_reponse_de_succes(self):
        f = self.fil()
        self.faux.reponses.append(texte("(rien)"))
        self.s("dire", fil=f, corps="juste pour info", destinataires=["cassandra"])
        fin = time.time() + 15
        while time.time() < fin and not self.db.lire("SELECT 1 FROM tours WHERE fin IS NOT NULL"):
            time.sleep(0.1)
        self.assertEqual([m["auteur"] for m in self.s("lire", fil=f)["messages"]], ["humain:bea@x.fr"])      # rien n'est posé

    def test_une_panne_se_dit_dans_le_fil(self):
        f = self.fil()
        self.faux.reponses.append((500, {"error": {"message": "panne du fournisseur"}}))
        self.s("dire", fil=f, corps="tu m'entends ?", destinataires=["cassandra"])
        m = self.attendre(f, "cassandra")[0]
        self.assertTrue(m["corps"].startswith("⚠️ Cassandra n'a pas pu répondre"))
        # la panne est écrite au tour APRÈS le message : attendre la fin du tour (le fil asynchrone n'a pas encore posé `erreur`)
        fin = time.time() + 5
        while time.time() < fin and not self.db.lire("SELECT 1 FROM tours WHERE fin IS NOT NULL"):
            time.sleep(0.05)
        self.assertEqual(self.db.lire("SELECT erreur FROM tours")[0]["erreur"] != "", True)

    def test_chaque_agent_adresse_repond_a_son_tour_et_une_seule_fois(self):
        f = self.fil()
        self.faux.reponses += [texte("Réponse de Cassandra"), texte("Réponse d'Itare")]
        self.s("dire", fil=f, corps="Vous deux : un avis ?", destinataires=["cassandra", "itare"])
        self.attendre(f, "cassandra")
        self.attendre(f, "itare")
        time.sleep(0.5)
        auteurs = [m["auteur"] for m in self.s("lire", fil=f)["messages"]]
        self.assertEqual(auteurs.count("cassandra"), 1)
        self.assertEqual(auteurs.count("itare"), 1)

    def test_deux_messages_de_suite_ne_se_perdent_pas(self):
        f = self.fil()
        self.faux.reponses += [texte("premier"), texte("second")]
        self.s("dire", fil=f, corps="question 1", destinataires=["cassandra"])
        self.s("dire", fil=f, corps="question 2", destinataires=["cassandra"])
        msgs = self.attendre(f, "cassandra", n=2)
        self.assertEqual([m["corps"] for m in msgs], ["premier", "second"])                     # en file, dans l'ordre : un tour long n'avale pas le suivant

    def test_le_budget_borne_la_conversation_d_agents(self):
        f = self.fil()
        self.n.reglages.poser("salon.budget_tours", 2, "")
        self.faux.reponses += [texte("un"), texte("deux")]
        self.s("dire", fil=f, corps="parlez-vous", destinataires=["cassandra"])
        self.attendre(f, "cassandra")
        # deux messages d'agents de suite sans humain : le budget est atteint, plus aucun tour ne part
        self.db.ecrire("INSERT INTO messages(fil, ts, auteur, destinataires, corps, humain) VALUES (?,?,?,?,?,0)", (f, time.time(), "itare", '["cassandra"]', "tu en penses quoi ?"))
        self.assertIn("budget", self.echec("relancer", fil=f, agent="cassandra"))
        n = len(self.faux.requetes)
        self.s("dire", fil=f, corps="à Itare ?", destinataires=["itare"])                       # un humain reprend : le compteur repart
        self.attendre(f, "itare", n=2)
        self.assertGreater(len(self.faux.requetes), n)

    def test_relancer_demande_une_reponse_maintenant(self):
        f = self.fil()
        self.s("dire", fil=f, corps="Cassandra ?", destinataires=["humain:leo@x.fr"])           # adressé à une personne : personne ne se réveille
        time.sleep(0.5)
        self.assertEqual(self.faux.requetes, [])
        self.faux.reponses.append(texte("Me voici."))
        r = self.s("relancer", fil=f, agent="cassandra")
        self.assertEqual(r["erreur"], "")
        self.assertEqual(self.attendre(f, "cassandra")[0]["corps"], "Me voici.")
        self.n.catalogue.get("salon.relancer").defaire(self.ctx, r)
        self.assertEqual([m for m in self.s("lire", fil=f)["messages"] if m["auteur"] == "cassandra"], [])
        self.assertIn("résident inconnu", self.echec("relancer", fil=f, agent="claude"))

    def test_le_terrain_et_le_mode_du_fil_passent_a_l_agent(self):
        f = self.fil(terrain="cherche")
        self.s("fil_mode", fil=f, mode="plan")
        self.faux.reponses.append(texte("ok"))
        self.s("dire", fil=f, corps="regarde", destinataires=["cassandra"])
        self.attendre(f, "cassandra")
        envoye = json.dumps(self.faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("TERRAIN DU FIL", envoye)
        self.assertIn("MODE PLAN", envoye)

    def test_un_agent_sait_ce_qui_s_est_dit_depuis_sa_derniere_lecture(self):
        f = self.fil()
        self.inviter(f, LEO)
        self.faux.reponses += [texte("un"), texte("deux")]
        self.s("dire", fil=f, corps="Première question", destinataires=["cassandra"])
        self.attendre(f, "cassandra")
        self.s("dire", compte=LEO, fil=f, corps="Leo glisse une idée", destinataires=["humain:bea@x.fr"])       # pas pour elle, mais dans le fil
        self.s("dire", fil=f, corps="Seconde question", destinataires=["cassandra"])
        self.attendre(f, "cassandra", n=2)
        derniere = json.dumps(self.faux.requetes[-1]["corps"], ensure_ascii=False)
        self.assertIn("Leo glisse une idée", derniere)
        self.assertNotIn("Première question", derniere.split("Ce qui s'est dit depuis ta dernière lecture")[-1])      # ce qu'elle a déjà lu ne revient pas


class Agents(Monde):
    def test_un_agent_invite_poste_sous_son_nom_pour_son_invitant_et_ses_gestes_se_racontent(self):
        f = self.fil()
        inv = self.ex("comptes.inviter_agent", compte=BEA, nom="claude")
        self.assertEqual(inv["statut"], "faite", inv)
        agent = inv["resultat"]["compte"]
        self.n.catalogue.regler_palier("salon.dire", "raconter")
        r = self.ex("salon.dire", compte=agent, acteur="agent", fil=f, corps="Bonjour de l'invité")
        self.assertEqual(r["statut"], "racontee")                                                # un agent raconte d'abord, tant que l'administrateur n'a pas dit « auto »
        self.n.catalogue.regler_palier("salon.dire", "auto")
        r = self.ex("salon.dire", compte=agent, acteur="agent", fil=f, corps="Bonjour de l'invité", auteur="Cassandra")
        self.assertEqual(r["statut"], "faite", r)
        m = self.s("lire", fil=f)["messages"][0]
        self.assertEqual((m["auteur"], m["humain"]), ("claude", 0))                              # son nom à lui, jamais celui qu'il se donne
        self.assertEqual(self.s("fils", compte=LEO)["fils"], [])
        r = self.ex("salon.lire", compte=agent, acteur="agent", fil=self.fil(compte=LEO, titre="Autre"))
        self.assertIn(r["statut"], ("echec", "refuse"))                                          # il n'entre que dans les fils de son invitant

    def test_un_agent_ne_se_fait_pas_passer_pour_un_resident(self):
        # « cassandra » est un nom réservé : comptes n'invite pas un agent qui s'appellerait ainsi. Si un compte d'agent portait
        # malgré tout ce nom, le salon ne le laisse pas s'en servir : il parle en « inconnu », jamais sous l'identité d'un résident.
        f = self.fil()
        self.n.base.ecrire("INSERT INTO comptes(compte, hash, type, invite_par, cree, maj) VALUES ('agent:cassandra', '', 'agent', ?, ?, ?)",
                           (BEA, time.time(), time.time()))
        self.n.catalogue.regler_palier("salon.dire", "auto")
        self.ex("salon.dire", compte="agent:cassandra", acteur="agent", fil=f, corps="je suis qui ?")
        self.assertEqual(self.s("lire", fil=f)["messages"][0]["auteur"], "inconnu")

if __name__ == "__main__":
    unittest.main()
