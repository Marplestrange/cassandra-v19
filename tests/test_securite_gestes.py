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
import main as moteur                      # noqa: E402
from tests.test_securite_analyse import releves, ecoute   # noqa: E402

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


def charger_commande():
    chemin = RACINE / "modules" / "securite" / "commandes" / "agir"
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
