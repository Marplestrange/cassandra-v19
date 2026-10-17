"""Bancs des gestes de sécurité : l'état par les relevés du courtier (simulé), chaque geste prouvé ou défait, et la table fermée de la commande root."""
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402
from tests.CN_test_securite_analyse import releves, ecoute   # noqa: E402

ADMIN, SIMPLE = "root@x.fr", "bea@x.fr"


class FauxCourtier:
    """Ce que répondrait le courtier : `mesurer` rend l'état courant de la machine simulée, `agir` rend ce qu'on lui a préparé et le consigne."""
    def __init__(self):
        self.machine = releves(ecoutes=[ecoute("tcp", "0.0.0.0", 22, "sshd")])
        self.agir = {"ok": True}
        self.appels = []
        self.au_geste = None                       # une fonction qui fait évoluer la machine quand un geste réussit

    def demander(self, module, commande, args=(), stdin=None, delai=30):
        self.appels.append((commande, list(args)))
        if commande == "mesurer":
            return {"ok": True, "code": 0, "sortie": json.dumps(self.machine), "erreur": ""}
        if commande == "agir":
            if self.agir.get("ok") and self.au_geste and args[0] == "faire":
                self.au_geste(self.machine)
            return {"ok": bool(self.agir.get("ok")), "code": 0 if self.agir.get("ok") else 1, "sortie": json.dumps(self.agir), "erreur": ""}
        return {"ok": False, "erreur": "commande inconnue"}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("securite", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("securite", installe=True, par="banc")
        for m in ("droits", "comptes", "securite"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ADMIN, True)
        self.c = FauxCourtier()
        self.n.racine.demander = self.c.demander
        self.ctx = self.n.executeur.contextes["securite"]

    def ex(self, cap, compte=ADMIN, **a):
        return self.n.executeur.executer("securite." + cap, "humain", a, compte=compte)

    def appels(self, commande):
        return [a for a in self.c.appels if a[0] == commande]


class Etat(Monde):
    def test_l_etat_se_calcule_sur_les_releves(self):
        r = self.ex("etat")
        self.assertEqual(r["statut"], "faite", r)
        d = r["resultat"]
        self.assertEqual(d["verdict"]["niveau"], "stable")
        self.assertEqual(d["exposition"][0]["nom"], "SSH")
        self.assertEqual(d["hote"], "amizo")

    def test_le_releve_est_garde_45_secondes(self):
        self.ex("etat")
        self.ex("etat")
        self.assertEqual(len(self.appels("mesurer")), 1)

    def test_sans_le_droit_rien_ne_sort(self):
        self.assertEqual(self.ex("etat", compte=SIMPLE)["statut"], "refuse")
        self.assertEqual(self.ex("ssh_mdp", compte=SIMPLE)["statut"], "refuse")
        self.assertEqual(self.appels("mesurer"), [])

    def test_un_courtier_muet_donne_une_erreur_pas_un_etat_inventé(self):
        self.n.racine.demander = lambda *a, **k: {"ok": False, "erreur": "le courtier ne répond pas"}
        r = self.ex("etat")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("courtier", r["erreur"])


class Gestes(Monde):
    def test_couper_les_mots_de_passe_ssh_est_prouve_par_un_releve(self):
        self.c.machine["sshd"]["passwordauthentication"] = "yes"
        self.c.au_geste = lambda m: m["sshd"].update(passwordauthentication="no")
        r = self.ex("ssh_mdp")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.appels("agir")[0][1][:2], ["faire", "ssh_mdp"])

    def test_un_geste_que_la_machine_ne_confirme_pas_est_defait(self):
        self.c.machine["sshd"]["passwordauthentication"] = "yes"
        self.c.agir = {"ok": True, "avant": "PasswordAuthentication yes\n"}               # le courtier dit ok, mais le relevé dit « yes » encore
        r = self.ex("ssh_mdp")
        self.assertEqual(r["statut"], "annulee", r)
        retour = self.appels("agir")[-1]
        self.assertEqual(retour[1][:2], ["defaire", "ssh_mdp"])
        self.assertEqual(json.loads(retour[1][2])["avant"], "PasswordAuthentication yes\n")        # il rend le fichier d'avant

    def test_un_refus_du_courtier_est_une_erreur_dite(self):
        self.c.agir = {"ok": False, "erreur": "aucune clé autorisée : vous seriez dehors"}
        r = self.ex("ssh_mdp")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("dehors", r["erreur"])

    def test_arreter_un_service_se_prouve_et_se_defait(self):
        self.c.machine["ecoutes"] = [ecoute("tcp", "0.0.0.0", 111, "rpcbind")]
        self.c.agir = {"ok": True, "unites": ["rpcbind.service"], "etaient_actives": ["rpcbind.service"]}
        self.c.au_geste = lambda m: m.update(ecoutes=[])
        r = self.ex("arret", service="rpcbind")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(json.loads(self.appels("agir")[0][1][2]), {"service": "rpcbind"})
        self.n.catalogue.get("securite.arret").defaire(self.ctx, r["resultat"])
        derniere = self.appels("agir")[-1][1]
        self.assertEqual(derniere[:2], ["defaire", "arret"])
        self.assertEqual(json.loads(derniere[2])["etaient_actives"], ["rpcbind.service"])

    def test_mysql_ne_doit_plus_ecouter_au_dela_de_la_machine(self):
        self.c.machine["ecoutes"] = [ecoute("tcp", "0.0.0.0", 3306, "mysqld")]
        self.c.au_geste = lambda m: m.update(ecoutes=[ecoute("tcp", "127.0.0.1", 3306, "mysqld")])
        self.assertEqual(self.ex("mysql_local")["statut"], "faite")
        self.c.machine["ecoutes"] = [ecoute("tcp", "0.0.0.0", 3306, "mysqld")]
        self.c.au_geste = None
        self.assertEqual(self.ex("mysql_local")["statut"], "annulee")

    def test_debannir_se_prouve_par_la_liste_du_jail(self):
        self.c.agir = {"ok": True, "jail": "sshd", "ip": "1.2.3.4"}
        self.c.au_geste = lambda m: m["fail2ban"]["jails"].update(sshd="Total failed: 9\nCurrently banned: 1\nTotal banned: 5\nBanned IP list: 5.6.7.8")
        r = self.ex("debannir", jail="sshd", ip="1.2.3.4")
        self.assertEqual(r["statut"], "faite", r)

    def test_une_mise_a_jour_n_a_pas_de_retour_et_le_dit(self):
        self.c.agir = {"ok": True, "unite": "cassandra-maj-systeme", "detail": "lancé en arrière-plan"}
        r = self.ex("maj_securite")
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        with self.assertRaises(ValueError) as e:
            self.n.catalogue.get("securite.maj_securite").defaire(self.ctx, res)
        self.assertIn("aucun retour", str(e.exception))

    def test_une_mise_a_jour_sans_unite_n_est_pas_prouvee(self):
        self.c.agir = {"ok": True}                                   # le courtier dit ok sans avoir rien lancé
        self.assertEqual(self.ex("maj_auto")["statut"], "annulation_impossible")

    def test_annuler_rend_au_courtier_ce_que_le_geste_avait_rendu(self):
        r = self.ex("annuler", geste="ssh_x11", avec={"avant": None})
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.appels("agir")[0][1][:2], ["defaire", "ssh_x11"])
        self.assertEqual(self.ex("annuler", geste="ssh_x11", avec="n'importe quoi")["statut"], "echec")


class Outils(Monde):
    def setUp(self):
        super().setUp()
        self.c.agir = {"ok": True}

    def racine_outils(self, reponse):
        """Le courtier répond à `outils` (le faux ne connaît que mesurer et agir)."""
        ancien = self.n.racine.demander
        self.appels_outils = []

        def demander(module, commande, args=(), stdin=None, delai=30):
            if commande == "outils":
                self.appels_outils.append(list(args))
                return {"ok": bool(reponse.get("ok")), "code": 0, "sortie": json.dumps(reponse), "erreur": ""}
            return ancien(module, commande, args, stdin, delai)
        self.n.racine.demander = demander

    def test_installer_un_outil_se_lance_en_arriere_plan(self):
        self.racine_outils({"ok": True, "unite": "cassandra-secu-installer-lynis", "detail": "lancé en arrière-plan"})
        r = self.ex("outil_installer", nom="lynis")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.appels_outils, [["en_arriere", "installer", "lynis"]])
        self.assertEqual(r["resultat"]["outil"], "lynis")

    def test_une_installation_n_a_pas_de_retour_et_le_dit(self):
        self.racine_outils({"ok": True, "unite": "u"})
        res = self.ex("outil_installer", nom="trivy")["resultat"]
        with self.assertRaises(ValueError) as e:
            self.n.catalogue.get("securite.outil_installer").defaire(self.ctx, res)
        self.assertIn("aucun retour", str(e.exception))

    def test_un_outil_inconnu_est_refuse_avant_le_courtier(self):
        self.racine_outils({"ok": True, "unite": "u"})
        r = self.ex("outil_installer", nom="nmap")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("inconnu", r["erreur"])
        self.assertEqual(self.appels_outils, [])

    def test_un_passage_se_defait_en_l_arretant(self):
        self.racine_outils({"ok": True, "unite": "cassandra-secu-lancer-clamav"})
        res = self.ex("outil_lancer", nom="clamav")["resultat"]
        self.n.catalogue.get("securite.outil_lancer").defaire(self.ctx, res)
        self.assertEqual(self.appels_outils[-1], ["arreter", "clamav"])

    def test_un_refus_du_programme_est_une_erreur_dite(self):
        self.racine_outils({"ok": False, "erreur": "installer est déjà en cours"})
        r = self.ex("outil_lancer", nom="lynis")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("déjà en cours", r["erreur"])

    def test_sans_le_droit_rien_ne_part(self):
        self.racine_outils({"ok": True, "unite": "u"})
        self.assertEqual(self.ex("outil_installer", compte=SIMPLE, nom="lynis")["statut"], "refuse")
        self.assertEqual(self.appels_outils, [])

    def test_l_etat_lit_les_resultats_rendus_par_le_programme(self):
        self.c.machine["outils_etat"] = {"lynis": {"installe": True, "convient": True, "resultat": {"score": 70, "avertissements": [], "suggestions_n": 4}}}
        d = self.ex("etat")["resultat"]
        self.assertEqual(d["outils"]["lynis"]["niveau"], "ok")
        self.assertIn("score 70/100", d["outils"]["lynis"]["dit"])


def charger_programme_outils():
    chemin = RACINE / "modules" / "securite" / "commandes" / "CN_outils"
    loader = importlib.machinery.SourceFileLoader("outils_cmd", str(chemin))
    spec = importlib.util.spec_from_loader("outils_cmd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class ProgrammeOutils(unittest.TestCase):
    """Le programme qui tourne en root : sa liste fermée, ses refus, et la lecture des résultats — sans rien installer."""
    def setUp(self):
        self.o = charger_programme_outils()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.o.SORTIE = self.tmp.name
        p = mock.patch.object(os, "geteuid", create=True, return_value=0)
        p.start()
        self.addCleanup(p.stop)

    def lancer(self, *a):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = self.o.main(list(a))
        return code, sortie.getvalue()

    def test_en_arriere_refuse_un_outil_ou_un_verbe_hors_liste(self):
        for args in (("en_arriere", "installer", "nmap"), ("en_arriere", "formater", "lynis"), ("en_arriere", "installer")):
            code, t = self.lancer(*args)
            self.assertEqual(code, 1, args)
            self.assertFalse(json.loads(t)["ok"])

    def test_arreter_refuse_un_outil_inconnu(self):
        self.assertEqual(self.lancer("arreter", "sshd")[0], 1)

    def test_pas_root_pas_de_lancement(self):
        with mock.patch.object(os, "geteuid", create=True, return_value=1000):
            code, t = self.lancer("en_arriere", "lancer", "lynis")
        self.assertEqual(code, 1)
        self.assertIn("root", json.loads(t)["erreur"])

    def test_un_lancement_en_double_est_refuse(self):
        with mock.patch.object(self.o, "actif", return_value=True):
            r = self.o.en_arriere("lancer", "clamav")
        self.assertFalse(r["ok"])
        self.assertIn("déjà en cours", r["erreur"])

    def test_le_lancement_passe_par_systemd_run_sans_shell(self):
        appels = []
        with mock.patch.object(self.o, "actif", return_value=False), mock.patch.object(self.o, "sh", side_effect=lambda cmd, **k: (appels.append(cmd), (0, ""))[1]):
            r = self.o.en_arriere("installer", "lynis")
        self.assertTrue(r["ok"])
        cmd = appels[0]
        self.assertEqual(cmd[0], "systemd-run")
        self.assertEqual(cmd[-2:], ["installer", "lynis"])                          # le verbe et l'outil, jamais une chaîne composée
        self.assertNotIn("sh", cmd[:1])

    def test_l_etat_rend_le_resultat_du_dernier_passage(self):
        Path(self.tmp.name, "lynis.json").write_text(json.dumps({"score": 55, "avertissements": []}), encoding="utf-8")
        with mock.patch.object(self.o.shutil, "which", side_effect=lambda b: "/usr/bin/" + b if b == "lynis" else None),                 mock.patch.object(self.o, "sh", return_value=(0, "Lynis 3.0.8")), mock.patch.object(self.o, "actif", return_value=False), mock.patch.object(self.o, "memoire_mo", return_value=8000):
            code, t = self.lancer("etat")
        e = json.loads(t)
        self.assertEqual(code, 0)
        self.assertTrue(e["lynis"]["installe"])
        self.assertEqual(e["lynis"]["resultat"]["score"], 55)
        self.assertFalse(e["trivy"]["installe"])
        self.assertIsNone(e["trivy"]["resultat"])
        self.assertEqual(e["lynis"]["version"], "3.0.8")

    def test_une_machine_trop_petite_n_est_pas_candidate_a_clamav(self):
        with mock.patch.object(self.o, "memoire_mo", return_value=1024):
            ok, pourquoi = self.o.convient("clamav")
        self.assertFalse(ok)
        self.assertIn("1024 Mo", pourquoi)

    def test_trivy_sans_docker_n_a_rien_a_analyser(self):
        with mock.patch.object(self.o.shutil, "which", return_value=None):
            self.assertFalse(self.o.convient("trivy")[0])

    def test_le_resultat_se_lit_ecrit_atomiquement(self):
        d = self.o.ecrire("lynis", {"score": 1})
        self.assertEqual(json.loads(Path(self.tmp.name, "lynis.json").read_text(encoding="utf-8"))["score"], 1)
        self.assertIn("quand", d)


def charger_commande():
    chemin = RACINE / "modules" / "securite" / "commandes" / "CN_agir"
    loader = importlib.machinery.SourceFileLoader("agir_cmd", str(chemin))
    spec = importlib.util.spec_from_loader("agir_cmd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class CommandeRoot(unittest.TestCase):
    """La commande est un programme qui tourne en root : sa table fermée et ses validations sont testées sans rien toucher."""
    def setUp(self):
        self.agir = charger_commande()
        patch = mock.patch.object(os, "geteuid", create=True, return_value=0)
        patch.start()
        self.addCleanup(patch.stop)

    def lancer(self, *argv):
        sortie = io.StringIO()
        with redirect_stdout(sortie), self.assertRaises(SystemExit) as e:
            self.agir.main(["agir"] + list(argv))
        return e.exception.code, json.loads(sortie.getvalue())

    def test_un_geste_hors_table_est_refuse(self):
        code, r = self.lancer("faire", "rm_rf")
        self.assertEqual(code, 1)
        self.assertFalse(r["ok"])

    def test_un_verbe_inconnu_est_refuse(self):
        self.assertFalse(self.lancer("effacer", "arret")[1]["ok"])

    def test_les_mises_a_jour_n_ont_pas_de_defaire(self):
        self.assertFalse(self.lancer("defaire", "maj_securite")[1]["ok"])

    def test_un_service_hors_de_la_table_des_arrets_est_refuse(self):
        r = self.lancer("faire", "arret", json.dumps({"service": "sshd"}))[1]
        self.assertFalse(r["ok"])
        self.assertIn("table", r["erreur"])

    def test_une_adresse_ou_un_jail_illisibles_sont_refuses(self):
        with mock.patch.object(self.agir, "jails", return_value=["sshd"]):
            self.assertFalse(self.lancer("faire", "debannir", json.dumps({"jail": "sshd", "ip": "pas-une-ip"}))[1]["ok"])
            self.assertFalse(self.lancer("faire", "debannir", json.dumps({"jail": "../../etc", "ip": "1.2.3.4"}))[1]["ok"])
            self.assertFalse(self.lancer("faire", "debannir", json.dumps({"jail": "inconnu", "ip": "1.2.3.4"}))[1]["ok"])

    def test_couper_les_mots_de_passe_sans_aucune_cle_est_refuse(self):
        with mock.patch.object(self.agir, "cles_autorisees", return_value=0):
            r = self.lancer("faire", "ssh_mdp")[1]
        self.assertFalse(r["ok"])
        self.assertIn("dehors", r["erreur"])

    def test_le_fichier_ssh_fusionne_sans_perdre_ce_qui_y_etait(self):
        t = self.agir.texte_dropin("# un commentaire\nX11Forwarding yes\nMaxAuthTries 3\n", {"X11Forwarding": "no"})
        self.assertIn("X11Forwarding no", t)
        self.assertIn("MaxAuthTries 3", t)
        self.assertNotIn("X11Forwarding yes", t)

    def test_un_geste_ssh_qui_ne_change_pas_la_valeur_effective_remet_tout(self):
        ecrits = []
        with mock.patch.object(self.agir, "cles_autorisees", return_value=1), mock.patch.object(self.agir, "lire_dropin", return_value="ancien\n"), \
                mock.patch.object(self.agir, "ecrire_dropin", side_effect=lambda t: (ecrits.append(t), (True, ""))[1]), \
                mock.patch.object(self.agir, "sshd_effectif", return_value={"x11forwarding": "yes"}):
            code, r = self.lancer("faire", "ssh_x11")
        self.assertFalse(r["ok"])
        self.assertIn("rien n'a changé", r["erreur"])
        self.assertEqual(ecrits[-1], "ancien\n")                      # le fichier d'avant est remis

    def test_un_programme_qui_n_est_pas_root_refuse(self):
        with mock.patch.object(os, "geteuid", create=True, return_value=1000):
            self.assertFalse(self.lancer("faire", "arret", "{}")[1]["ok"])


if __name__ == "__main__":
    unittest.main()
