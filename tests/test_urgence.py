"""Bancs des gestes d'urgence : les freins du noyau, le confinement (le courtier est simulé), l'échéance, et la commande root (ses règles et ses garde-fous)."""
import http.client
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import main as moteur                      # noqa: E402
from noyau.passerelle import Passerelle    # noqa: E402

MDP = "Mdp-Solide-42!"
CHEF, BEA = "chef@x.fr", "bea@x.fr"


class FauxConfiner:
    """Le programme root, simulé : un état, les mêmes réponses. `casse` fait échouer la pose ; `muet` fait taire le courtier."""
    def __init__(self):
        self.actif = False
        self.e = {}
        self.appels = []
        self.casse = ""
        self.muet = False

    def demander(self, module, commande, args=(), stdin=None, delai=30):
        if commande != "confiner":
            return {"ok": False, "erreur": "commande inconnue"}
        if self.muet:
            return {"ok": False, "erreur": "le courtier ne répond pas", "sortie": ""}
        verbe = args[0]
        a = json.loads(args[1]) if len(args) > 1 else {}
        self.appels.append((verbe, a))

        def rep(d):
            return {"ok": bool(d.get("ok")), "code": 0 if d.get("ok") else 1, "sortie": json.dumps(d), "erreur": ""}
        if verbe == "etat":
            return rep(dict(self.e, ok=True, actif=self.actif, chaine=self.actif and self.e.get("niveau", 0) >= 2) if self.actif else {"ok": True, "actif": False})
        if verbe == "poser":
            if self.casse:
                return rep({"ok": False, "erreur": self.casse})
            faites = ["ssh_mdp"] + (["reseau"] if a["niveau"] >= 2 else []) + (["docker"] if a["niveau"] >= 3 else [])
            self.actif, self.e = True, {"niveau": a["niveau"], "ip": a["ip"], "par": a["par"], "motif": a["motif"], "fin": time.time() + a["minutes"] * 60, "faites": faites, "confirme": False}
            return rep({"ok": True, "niveau": a["niveau"], "ip": a["ip"], "fin": self.e["fin"], "faites": faites})
        if verbe == "confirmer":
            self.e.update({"fin": time.time() + a["minutes"] * 60, "confirme": True})
            return rep({"ok": True, "fin": self.e["fin"]})
        if verbe in ("lever", "lever_auto"):
            avait = self.actif
            self.actif, self.e = False, {}
            return rep({"ok": True, "defaits": ["reseau", "ssh"] if avait else [], "etait_actif": avait})
        return rep({"ok": False, "erreur": "verbe inconnu"})


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("urgence", "droits", "comptes", "notifications"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.n.etat_modules.poser("urgence", installe=True, par="banc")
        for m in ("droits", "comptes", "notifications", "urgence"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        for c in (CHEF, BEA):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="operateur")
        self.n.droits.regler_admin(CHEF, True)
        self.c = FauxConfiner()
        self.n.racine.demander = self.c.demander
        self.ctx = self.n.executeur.contextes["urgence"]
        self.jeton_chef = self.n.identite.ouvrir(CHEF, MDP, ip="10.0.0.1")["jeton"]
        self.jeton_bea = self.n.identite.ouvrir(BEA, MDP, ip="10.0.0.2")["jeton"]

    def ex(self, cap, compte=CHEF, acteur="humain", **a):
        return self.n.executeur.executer("urgence." + cap, acteur, a, compte=compte)

    def sessions(self):
        return self.n.identite.base.lire("SELECT COUNT(*) AS n FROM sessions")[0]["n"]

    def confiner(self, **kw):
        a = {"niveau": 2, "mot": "CONFINER", "motif": "un agent a été manipulé hier soir", "minutes": 30, "ip_session": "203.0.113.9", "courant": self.jeton_chef}
        a.update(kw)
        return self.ex("confiner", **a)

    def frein(self, nom):
        return nom in self.n.freins()


class Freins(Monde):
    def test_le_gel_arrete_les_agents_pas_les_lectures_ni_l_humain(self):
        self.assertEqual(self.ex("geler", actif=True)["statut"], "faite")
        self.assertTrue(self.frein("gel"))
        refus = self.n.executeur.executer("urgence.couper_envois", "cassandra", {"actif": True}, compte=CHEF)
        self.assertEqual(refus["statut"], "refuse")                                       # un agent n'est pas autorisé : la capacité est humaine
        # un agent qui écrit (il en a le droit : l'émission d'une notification) est refusé tant que l'autonomie est gelée
        r = self.n.executeur.executer("notifications.emettre", "cassandra", {"titre": "essai", "corps": "x", "source": "banc"}, compte=CHEF)
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("gelée", r["raison"])
        self.assertEqual(self.n.executeur.executer("notifications.emettre", "humain", {"titre": "essai", "corps": "x", "source": "banc"}, compte=CHEF)["statut"], "faite")       # l'humain, lui, passe
        self.assertEqual(self.ex("etat")["statut"], "faite")                               # la lecture continue
        self.assertEqual(self.ex("geler", actif=False)["statut"], "faite")
        self.assertFalse(self.frein("gel"))

    def test_couper_les_envois_se_prouve_et_se_defait(self):
        r = self.ex("couper_envois", actif=True)
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(self.frein("envois"))
        self.n.catalogue.get("urgence.couper_envois").defaire(self.ctx, r["resultat"])
        self.assertFalse(self.frein("envois"))

    def test_la_coupure_des_envois_arrete_toute_capacite_sortante_meme_pour_l_humain(self):
        import dataclasses
        e = self.n.catalogue.get("notifications.emettre")
        e.capacite = dataclasses.replace(e.capacite, sortant=True)               # une capacité qui fait SORTIR quelque chose de la maison
        a = {"titre": "essai", "corps": "x", "source": "banc"}
        r0 = self.n.executeur.executer("notifications.emettre", "humain", a, compte=CHEF)
        self.assertEqual(r0["statut"], "faite", r0)
        self.ex("couper_envois", actif=True)
        for acteur in ("humain", "cassandra"):
            r = self.n.executeur.executer("notifications.emettre", acteur, a, compte=CHEF)
            self.assertEqual(r["statut"], "refuse", acteur)
            self.assertIn("envois sont coupés", r["raison"])
        self.ex("couper_envois", actif=False)
        self.assertEqual(self.n.executeur.executer("notifications.emettre", "humain", a, compte=CHEF)["statut"], "faite")

    def test_un_frein_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            self.n.freiner("peut-etre", True)

    def test_un_compte_ordinaire_n_a_aucun_geste_d_urgence(self):
        for cap, a in (("etat", {}), ("geler", {"actif": True}), ("couper_envois", {"actif": True}), ("lever", {}), ("crise_lever", {}),
                       ("confiner", {"niveau": 1, "mot": "CONFINER", "motif": "dix caractères au moins", "ip_session": "1.2.3.4", "courant": self.jeton_bea})):
            self.assertEqual(self.ex(cap, compte=BEA, **a)["statut"], "refuse", cap)
        self.assertFalse(self.frein("gel"))
        self.assertEqual(self.c.appels, [])

    def test_aucun_geste_n_est_un_outil_d_agent(self):
        for cap in ("geler", "couper_envois", "sessions_revoquer", "crise_lever", "confiner", "lever", "confirmer"):
            self.assertEqual(self.n.executeur.executer("urgence." + cap, "itare", {}, compte=CHEF)["statut"], "refuse", cap)

    def test_la_crise_du_noyau_se_leve(self):
        self.n.crise(True, "essai")
        self.assertTrue(self.ex("etat")["resultat"]["etat"]["crise"]["actif"])
        r = self.n.executeur.executer("urgence.crise_lever", "humain", {}, compte=CHEF)
        self.assertEqual(r["statut"], "refuse")                                            # le noyau en crise refuse toute ECRITURE, même ce geste…
        self.n.crise(False)                                                                # …c'est donc le noyau (le propriétaire de la crise) qu'on lève ici
        self.assertFalse(self.n.en_crise())

    def test_les_sessions_des_autres_se_ferment_pas_la_mienne(self):
        self.assertEqual(self.sessions(), 2)
        r = self.ex("sessions_revoquer", courant=self.jeton_chef)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["revoquees"], 1)
        self.assertEqual(self.sessions(), 1)
        self.assertTrue(self.n.identite.valider(self.jeton_chef)["ok"])
        self.assertFalse(self.n.identite.valider(self.jeton_bea)["ok"])

    def test_sans_la_session_courante_rien_n_est_ferme(self):
        self.assertEqual(self.ex("sessions_revoquer", courant="")["statut"], "echec")
        self.assertEqual(self.sessions(), 2)


class Confinement(Monde):
    def test_les_gardes_de_la_demande(self):
        for kw, mot in (({"mot": "confiner pas"}, "CONFINER"), ({"mot": ""}, "CONFINER"), ({"motif": "court"}, "justification"), ({"niveau": 4}, "niveau"), ({"niveau": 0}, "niveau"),
                        ({"ip_session": ""}, "adresse"), ({"courant": ""}, "session courante")):
            r = self.confiner(**kw)
            self.assertEqual(r["statut"], "echec", kw)
            self.assertIn(mot, r["erreur"], kw)
        self.assertEqual(self.c.appels, [])                                               # rien n'est arrivé jusqu'au courtier
        self.assertEqual(self.sessions(), 2)
        self.assertFalse(self.frein("gel"))

    def test_le_mot_se_tape_en_majuscules_ou_pas(self):
        self.assertEqual(self.confiner(mot=" confiner ", niveau=1)["statut"], "faite")

    def test_un_confinement_de_niveau_2_fait_tout_dans_l_ordre(self):
        r = self.confiner()
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual(res["faites"], ["ssh_mdp", "reseau", "gel", "envois", "sessions"])           # ce qui ne se rend pas vient en dernier
        self.assertTrue(self.frein("gel") and self.frein("envois"))
        self.assertEqual(self.sessions(), 1)
        self.assertEqual(self.c.appels[0][0], "poser")
        self.assertEqual(self.c.appels[0][1]["ip"], "203.0.113.9")                          # l'adresse protégée est celle de la session
        e = self.ex("etat", ip_session="203.0.113.9")["resultat"]
        self.assertTrue(e["etat"]["confine"])
        self.assertEqual((e["etat"]["confinement"]["niveau"], e["etat"]["confinement"]["ip"]), (2, "203.0.113.9"))
        self.assertRegex(e["etat"]["confinement"]["fin"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual(e["ip"], "203.0.113.9")

    def test_le_niveau_1_ne_coupe_pas_les_envois(self):
        self.assertEqual(self.confiner(niveau=1)["statut"], "faite")
        self.assertTrue(self.frein("gel"))
        self.assertFalse(self.frein("envois"))

    def test_un_echec_du_courtier_ne_laisse_rien_en_place(self):
        self.c.casse = "aucune clé autorisée : vous seriez dehors"
        r = self.confiner()
        self.assertEqual(r["statut"], "echec")
        self.assertIn("dehors", r["erreur"])
        self.assertFalse(self.frein("gel") or self.frein("envois"))
        self.assertEqual(self.sessions(), 2)                                                # personne n'a été déconnecté
        self.assertIsNone(self.ctx.lire("confinement", "courant", portee=self.ctx.TOUT))

    def test_un_echec_en_route_defait_ce_qui_etait_fait(self):
        avec = self.n.identite
        with mock.patch.object(type(avec), "revoquer_toutes_autres", side_effect=RuntimeError("base verrouillée")):
            r = self.confiner()
        self.assertEqual(r["statut"], "echec")
        self.assertFalse(self.c.actif)                                                       # le courtier a été prié de tout lever
        self.assertFalse(self.frein("gel") or self.frein("envois"))
        self.assertIsNone(self.ctx.lire("confinement", "courant", portee=self.ctx.TOUT))

    def test_un_second_confinement_est_refuse(self):
        self.assertEqual(self.confiner()["statut"], "faite")
        r = self.confiner()
        self.assertEqual(r["statut"], "echec")
        self.assertIn("déjà confiné", r["erreur"])

    def test_lever_rend_les_freins_que_le_confinement_avait_poses(self):
        self.confiner()
        r = self.ex("lever")
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(self.frein("gel") or self.frein("envois"))
        self.assertFalse(self.c.actif)
        self.assertFalse(self.ex("etat")["resultat"]["etat"]["confine"])
        self.assertIsNone(self.ctx.lire("confinement", "courant", portee=self.ctx.TOUT))

    def test_lever_ne_touche_pas_a_un_gel_pose_avant(self):
        self.ex("geler", actif=True)                                                         # l'administrateur avait gelé AVANT
        self.confiner()
        self.ex("lever")
        self.assertTrue(self.frein("gel"))                                                   # il reste : ce n'est pas le confinement qui l'avait posé
        self.assertFalse(self.frein("envois"))

    def test_confirmer_repousse_l_echeance(self):
        self.confiner(minutes=30)
        avant = self.c.e["fin"]
        r = self.ex("confirmer", minutes=240)
        self.assertEqual(r["statut"], "faite", r)
        self.assertGreater(self.c.e["fin"] - avant, 3 * 3600)
        self.assertTrue(self.ex("etat")["resultat"]["etat"]["confinement"]["confirme"])

    def test_confirmer_sans_confinement_est_refuse(self):
        self.assertEqual(self.ex("confirmer")["statut"], "echec")

    def test_le_retour_arriere_d_un_confinement_est_la_levee(self):
        r = self.confiner()
        self.n.catalogue.get("urgence.confiner").defaire(self.ctx, r["resultat"])
        self.assertFalse(self.c.actif)
        self.assertFalse(self.frein("gel"))

    def test_une_preuve_qui_manque_defait_le_confinement(self):
        orig = self.c.demander

        def sans_chaine(module, commande, args=(), stdin=None, delai=30):
            r = orig(module, commande, args, stdin, delai)
            if args and args[0] == "etat" and self.c.actif:
                d = json.loads(r["sortie"])
                d["chaine"] = False                                                          # le réseau n'est pas réellement fermé
                return {"ok": True, "code": 0, "sortie": json.dumps(d), "erreur": ""}
            return r
        self.n.racine.demander = sans_chaine
        r = self.confiner(niveau=2)
        self.assertEqual(r["statut"], "annulee", r)
        self.assertFalse(self.c.actif)
        self.assertFalse(self.frein("gel"))


class Echeance(Monde):
    def test_a_l_echeance_les_freins_se_rendent(self):
        self.confiner()
        self.c.actif, self.c.e = False, {}                                                   # la minuterie systemd a levé le réseau
        self.assertEqual(self.n.lancer("urgence.echeance")["statut"], "fait")
        self.assertFalse(self.frein("gel") or self.frein("envois"))
        self.assertIsNone(self.ctx.lire("confinement", "courant", portee=self.ctx.TOUT))

    def test_une_echeance_depassee_sans_minuterie_est_levee_par_cassandra(self):
        self.confiner()
        self.c.e["fin"] = time.time() - 5
        orig = self.c.demander
        self.c.demander = lambda m, cmd, args=(), stdin=None, delai=30: (lambda r: r)(orig(m, cmd, args, stdin, delai) if not (args and args[0] == "etat") else
                                                                                   {"ok": True, "code": 0, "sortie": json.dumps(dict(self.c.e, ok=True, actif=True, echu=True)), "erreur": ""})
        self.n.racine.demander = self.c.demander
        self.n.lancer("urgence.echeance")
        self.assertIn("lever", [a[0] for a in self.c.appels])
        self.assertFalse(self.frein("gel"))

    def test_un_confinement_encore_valable_reste_en_place(self):
        self.confiner()
        self.n.lancer("urgence.echeance")
        self.assertTrue(self.frein("gel") and self.c.actif)

    def test_un_courtier_muet_ne_leve_rien(self):
        self.confiner()
        self.c.muet = True
        self.n.lancer("urgence.echeance")
        self.assertTrue(self.frein("gel"))                                                   # on ne devine pas : on réessaie à la minute suivante
        self.assertIsNotNone(self.ctx.lire("confinement", "courant", portee=self.ctx.TOUT))

    def test_l_etat_dit_que_le_courtier_ne_repond_pas(self):
        self.c.muet = True
        e = self.ex("etat")["resultat"]["etat"]["confinement"]
        self.assertIn("lecture_impossible", e)


class AdresseDeLaConnexion(unittest.TestCase):
    """L'adresse protégée vient de la connexion TCP, jamais de la demande : sinon on s'enfermerait dehors en s'autorisant quelqu'un d'autre."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("urgence", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.n.etat_modules.poser("urgence", installe=True, par="banc")
        for m in ("droits", "comptes", "urgence"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        self.n.executeur.executer("comptes.creer", "humain", {"compte": CHEF, "mot_de_passe": MDP}, compte="operateur")
        self.n.droits.regler_admin(CHEF, True)
        self.n.racine.demander = FauxConfiner().demander
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)

    def req(self, chemin, corps, jeton=""):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = {"Content-Type": "application/json", "X-Cassandra": "1"}
        if jeton:
            h["Authorization"] = "Bearer " + jeton
        c.request("POST", chemin, body=json.dumps(corps).encode(), headers=h)
        r = c.getresponse()
        t = r.read().decode()
        c.close()
        return r.status, json.loads(t)

    def test_l_adresse_du_corps_est_ecrasee_par_celle_de_la_connexion(self):
        st, d = self.req("/api/connexion", {"compte": CHEF, "mot_de_passe": MDP})
        jeton = d["jeton"]
        st, r = self.req("/api/agir/urgence.etat", {"args": {"ip_session": "6.6.6.6"}}, jeton)
        self.assertEqual(st, 200, r)
        self.assertEqual(r["resultat"]["ip"], "127.0.0.1")                                   # jamais 6.6.6.6

    def test_un_argument_ip_session_n_est_pas_accepte_par_une_capacite_qui_ne_le_declare_pas(self):
        st, d = self.req("/api/connexion", {"compte": CHEF, "mot_de_passe": MDP})
        st, r = self.req("/api/agir/urgence.geler", {"args": {"actif": True, "ip_session": "6.6.6.6"}}, d["jeton"])
        self.assertEqual(st, 200, r)                                                         # l'argument est retiré, la capacité s'exécute


def charger_commande():
    chemin = RACINE / "modules" / "urgence" / "commandes" / "confiner"
    loader = importlib.machinery.SourceFileLoader("confiner_cmd", str(chemin))
    spec = importlib.util.spec_from_loader("confiner_cmd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class CommandeRoot(unittest.TestCase):
    def setUp(self):
        self.m = charger_commande()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.m.ETAT = str(Path(self.tmp.name) / "confinement.json")
        p = mock.patch.object(os, "geteuid", create=True, return_value=0)
        p.start()
        self.addCleanup(p.stop)

    def lancer(self, *argv):
        sortie = io.StringIO()
        with redirect_stdout(sortie), self.assertRaises(SystemExit) as e:
            self.m.main(["confiner"] + list(argv))
        return e.exception.code, json.loads(sortie.getvalue())

    def test_la_session_est_autorisee_avant_toute_regle_qui_ferme(self):
        for niveau in (2, 3):
            r = self.m.regles(niveau, "203.0.113.9", 4)
            self.assertIn(["-s", "203.0.113.9", "-j", "ACCEPT"], r)
            lignes = ["-A CASSANDRA-CONFINEMENT " + " ".join(x) for x in r]
            self.assertTrue(self.m.a_une_session_avant_toute_fermeture(lignes, "203.0.113.9"))

    def test_la_machine_les_connexions_etablies_et_tailscale_passent_toujours(self):
        r = self.m.regles(3, "203.0.113.9", 4)
        self.assertEqual(r[0], ["-i", "lo", "-j", "ACCEPT"])
        self.assertIn(["-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"], r)
        self.assertIn(["-i", "tailscale0", "-j", "ACCEPT"], r)

    def test_le_niveau_2_ferme_ssh_le_niveau_3_ferme_tout(self):
        self.assertEqual(self.m.regles(2, "203.0.113.9", 4, port_ssh=2222)[-1], ["-p", "tcp", "--dport", "2222", "-j", "DROP"])
        self.assertEqual(self.m.regles(3, "203.0.113.9", 4)[-1], ["-j", "DROP"])

    def test_une_adresse_v4_n_ouvre_pas_la_chaine_v6_mais_la_ferme_pour_les_autres(self):
        r6 = self.m.regles(3, "203.0.113.9", 6)
        self.assertFalse(any(x[:1] == ["-s"] for x in r6))
        self.assertEqual(r6[-1], ["-j", "DROP"])
        self.assertIn(["-s", "2001:db8::1", "-j", "ACCEPT"], self.m.regles(3, "2001:db8::1", 6))

    def test_une_fermeture_avant_l_ouverture_est_detectee(self):
        lignes = ["-A C -p tcp --dport 22 -j DROP", "-A C -s 203.0.113.9/32 -j ACCEPT"]
        self.assertFalse(self.m.a_une_session_avant_toute_fermeture(lignes, "203.0.113.9"))
        self.assertFalse(self.m.a_une_session_avant_toute_fermeture(["-A C -j DROP"], "203.0.113.9"))

    def test_le_niveau_et_l_adresse_sont_valides_avant_tout(self):
        for a in ({"niveau": 4, "ip": "1.2.3.4"}, {"niveau": 2, "ip": "pas-une-ip"}, {"niveau": 2, "ip": ""}):
            code, r = self.lancer("poser", json.dumps(a))
            self.assertEqual(code, 1, a)
            self.assertFalse(r["ok"])
        self.assertFalse(os.path.exists(self.m.ETAT))                                        # rien n'a été écrit

    def test_pas_root_pas_de_confinement(self):
        with mock.patch.object(os, "geteuid", create=True, return_value=1000):
            self.assertIn("root", self.lancer("poser", json.dumps({"niveau": 1, "ip": "1.2.3.4"}))[1]["erreur"])

    def test_sans_cle_ssh_le_niveau_1_est_refuse_et_rien_n_est_laisse(self):
        with mock.patch.object(self.m, "cles_autorisees", return_value=0), mock.patch.object(self.m, "port_ssh", return_value=22), \
                mock.patch.object(self.m, "chaine_presente", return_value=False), mock.patch.object(self.m, "run", return_value=(0, "")), \
                mock.patch.object(self.m, "dropin_lire", return_value=None):
            code, r = self.lancer("poser", json.dumps({"niveau": 1, "ip": "1.2.3.4"}))
        self.assertEqual(code, 1)
        self.assertIn("dehors", r["erreur"])
        self.assertFalse(os.path.exists(self.m.ETAT))                                        # l'état écrit en premier est effacé par la levée

    def test_lever_sans_confinement_est_inoffensif(self):
        with mock.patch.object(self.m, "run", return_value=(1, "")), mock.patch.object(self.m, "chaine_presente", return_value=False):
            code, r = self.lancer("lever")
        self.assertEqual(code, 0)
        self.assertFalse(r["etait_actif"])

    def test_un_confinement_deja_en_cours_est_refuse(self):
        Path(self.m.ETAT).write_text(json.dumps({"niveau": 1, "fin": time.time() + 600}), encoding="utf-8")
        code, r = self.lancer("poser", json.dumps({"niveau": 1, "ip": "1.2.3.4"}))
        self.assertEqual(code, 1)
        self.assertIn("déjà", r["erreur"])

    def test_l_etat_dit_une_echeance_depassee(self):
        Path(self.m.ETAT).write_text(json.dumps({"niveau": 2, "ip": "1.2.3.4", "fin": time.time() - 10}), encoding="utf-8")
        with mock.patch.object(self.m, "chaine_presente", return_value=True):
            code, r = self.lancer("etat")
        self.assertTrue(r["actif"] and r["echu"])

    def test_le_fichier_ssh_garde_ce_qui_y_etait(self):
        t = self.m.texte_dropin("MaxAuthTries 3\nPasswordAuthentication yes\n")
        self.assertIn("MaxAuthTries 3", t)
        self.assertIn("PasswordAuthentication no", t)
        self.assertNotIn("PasswordAuthentication yes", t)

    def test_un_verbe_inconnu_est_refuse(self):
        self.assertFalse(self.lancer("formater")[1]["ok"])


if __name__ == "__main__":
    unittest.main()
