# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : test_securite_machine.py
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #76c585
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : test_securite_machine.py
# MÉTHODE    : charge la commande root « machine » comme un module et remplace son lanceur par une fausse machine tenue en mémoire (aucune commande réelle) ; puis éprouve les capacités du module sur un faux courtier
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=76c585 ▼▼▼
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

ADMIN, SIMPLE = "root@x.fr", "bea@x.fr"


def charger_commande():
    chemin = RACINE / "modules" / "securite" / "commandes" / "CN_machine"
    loader = importlib.machinery.SourceFileLoader("machine_cmd", str(chemin))
    spec = importlib.util.spec_from_loader("machine_cmd", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FausseMachine:
    """Ce que répondraient systemctl, docker, fail2ban, who, shutdown : une machine tenue en mémoire, et le journal des commandes lancées."""
    def __init__(self):
        self.actifs, self.au_demarrage, self.memoire = {"nginx.service", "ssh.service", "mysql.service", "dovecot.service"}, {"nginx.service", "ssh.service", "mysql.service"}, {}
        self.existent = {"nginx.service", "ssh.service", "mysql.service", "dovecot.service", "cron.service", "php8.3-fpm.service"}
        self.conteneurs = {"coffre": "running", "recherche": "exited"}
        self.bannies, self.sessions, self.prevu, self.config_ok, self.sourd = [], [["lea", "pts/0", "100.64.0.11"], ["invite", "pts/1", "203.0.113.24"]], False, True, False
        self.entrees, self.lances = {"198.51.100.20"}, []

    def run(self, args, timeout=30):
        self.lances.append(list(args))
        a = args
        if a[0] == "systemctl":
            v, u = a[1], a[-1] if len(a) > 2 else ""
            if v == "cat":
                return u in self.existent, ""
            if v == "is-active":
                return u in self.actifs, "active" if u in self.actifs else "inactive"
            if v == "is-enabled":
                return u in self.au_demarrage, "enabled" if u in self.au_demarrage else "disabled"
            if v == "show":
                return True, self.memoire.get(a[2], "infinity")
            if v == "set-property":
                self.memoire[a[2]] = a[3].split("=", 1)[1]
                return True, ""
            if v == "list-units":
                return True, ""
            if self.sourd:
                return False, "Job failed"
            {"start": self.actifs.add, "restart": self.actifs.add, "stop": self.actifs.discard, "enable": self.au_demarrage.add, "disable": self.au_demarrage.discard, "reload": lambda u: None}[v](u)
            return True, ""
        if a[0] in ("nginx", "apache2ctl", "sshd"):
            return self.config_ok, "" if self.config_ok else "nginx: [emerg] unexpected end of file"
        if a[0] == "docker":
            if a[1] == "--version":
                return True, "Docker version 27"
            if a[1] == "ps":
                return True, "\n".join(self.conteneurs if "-a" in a else [n + "|id" + n for n, e in self.conteneurs.items() if e == "running"])
            if a[1] == "inspect":
                return True, "always" if "RestartPolicy" in a[3] else self.conteneurs.get(a[-1], "")
            if a[1] == "logs":
                return True, "2026-11-11T10:00:00Z prêt"
            self.conteneurs[a[-1]] = {"start": "running", "restart": "running", "unpause": "running", "stop": "exited", "pause": "paused"}[a[1]]
            return True, a[-1]
        if a[0] == "fail2ban-client":
            if a[1] == "status":
                return True, ("Banned IP list: " + " ".join(self.bannies)) if len(a) > 2 else "Jail list: sshd, recidive"
            (self.bannies.append if a[3] == "banip" else self.bannies.remove)(a[4])
            return True, "1"
        if a[0] == "journalctl":
            if "-g" in a:
                return True, "Accepted publickey for lea" if any(ip.replace(".", "\\.") in a[a.index("-g") + 1] for ip in self.entrees) else ""
            return True, "2026-11-11T10:00:00+0000 machine nginx[1]: prêt"
        if a[0] == "who":
            return True, "\n".join("%s %s 2026-11-11 10:00 (%s)" % (u, t, ip) for u, t, ip in self.sessions)
        if a[0] == "pkill":
            self.sessions = [s for s in self.sessions if s[1] != a[-1]]
            return True, ""
        if a[0] == "ip":
            return True, json.dumps([{"addr_info": [{"local": "203.0.113.52"}]}])
        if a[0] == "pgrep":
            return False, ""
        if a[0] == "shutdown":
            self.prevu = a[1] != "-c"
            return True, ""
        return False, "commande inconnue du banc : %s" % a[0]


class Commande(unittest.TestCase):
    """Le programme tourne en root : sa table fermée, ses refus et ses vérifications sont éprouvés sans toucher à rien."""
    def setUp(self):
        self.m, self.f = charger_commande(), FausseMachine()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for p in (mock.patch.object(os, "geteuid", create=True, return_value=0), mock.patch.object(self.m, "run", self.f.run), mock.patch.object(self.m.time, "sleep", lambda s: None),
                  mock.patch.object(self.m, "MARQUE", str(self.tmp / "marque.json")), mock.patch.object(self.m, "redemarrage_prevu", lambda: "2026-11-12 03:00" if self.f.prevu else ""),
                  mock.patch.object(self.m.socket, "gethostname", return_value="atlas")):
            p.start()
            self.addCleanup(p.stop)

    def lancer(self, verbe, geste, **args):
        sortie = io.StringIO()
        with redirect_stdout(sortie), self.assertRaises(SystemExit) as e:
            self.m.main(["machine", verbe, geste, json.dumps(args)])
        return json.loads(sortie.getvalue().strip().splitlines()[-1])

    def systemctl(self):
        return [c[1:] for c in self.f.lances if c[0] == "systemctl" and c[1] in ("start", "stop", "restart", "reload", "enable", "disable")]

    # ── services
    def test_un_service_hors_de_la_table_ou_un_geste_inconnu_est_refuse(self):
        self.assertIn("hors de la table", self.lancer("faire", "service", service="sshd; rm -rf /", action="arreter")["erreur"])
        self.assertIn("hors de la table", self.lancer("faire", "service", service="cups", action="arreter")["erreur"])
        self.assertFalse(self.lancer("faire", "service", service="mysql", action="effacer")["ok"])
        self.assertFalse(self.lancer("faire", "formater")["ok"])
        self.assertEqual(self.systemctl(), [])

    def test_le_noyau_le_courtier_et_le_collecteur_ne_se_touchent_pas_d_ici(self):
        for s in ("cassandra-noyau", "cassandra-courtier", "sensorium"):
            self.assertFalse(self.lancer("faire", "service", service=s, action="redemarrer")["ok"], s)
        self.assertEqual(self.systemctl(), [])

    def test_ssh_et_nginx_ne_s_arretent_pas_mais_se_redemarrent(self):
        for s in ("ssh", "nginx"):
            self.assertFalse(self.lancer("faire", "service", service=s, action="arreter")["ok"])
            self.assertFalse(self.lancer("faire", "service", service=s, action="desactiver")["ok"])
        self.assertEqual(self.systemctl(), [])
        self.assertTrue(self.lancer("faire", "service", service="nginx", action="redemarrer")["ok"])
        self.assertEqual(self.systemctl(), [["restart", "nginx.service"]])

    def test_une_configuration_refusee_ne_laisse_rien_redemarrer(self):
        self.f.config_ok = False
        r = self.lancer("faire", "service", service="nginx", action="recharger")
        self.assertFalse(r["ok"])
        self.assertIn("rien n’est touché", r["erreur"])
        self.assertEqual(self.systemctl(), [])

    def test_arreter_se_verifie_dit_l_etat_d_avant_et_se_defait(self):
        r = self.lancer("faire", "service", service="mysql", action="arreter")
        self.assertEqual((r["ok"], r["unite"], r["avant"]), (True, "mysql.service", {"actif": True, "au_demarrage": True}))
        self.assertNotIn("mysql.service", self.f.actifs)
        self.assertTrue(self.lancer("defaire", "service", service="mysql", action="arreter", avant=r["avant"])["ok"])
        self.assertIn("mysql.service", self.f.actifs)
        self.assertFalse(self.lancer("defaire", "service", service="mysql", action="redemarrer", avant=r["avant"])["ok"])     # rien à défaire

    def test_un_geste_qui_ne_prend_pas_n_est_pas_dit_fait(self):
        self.f.sourd = True
        r = self.lancer("faire", "service", service="mysql", action="arreter")
        self.assertFalse(r["ok"])
        self.assertIn("n’a pas pris", r["erreur"])

    def test_defaire_ne_touche_pas_a_ce_qui_etait_deja_ainsi(self):
        r = self.lancer("defaire", "service", service="cron", action="demarrer", avant={"actif": True, "au_demarrage": False})
        self.assertTrue(r["ok"])
        self.assertEqual(self.systemctl(), [])

    def test_recharger_un_service_qui_ne_se_recharge_pas_est_refuse_et_php_fpm_est_suivi(self):
        self.assertIn("ne se recharge pas", self.lancer("faire", "service", service="mysql", action="recharger")["erreur"])
        self.assertTrue(self.lancer("faire", "service", service="php8.3-fpm", action="demarrer")["ok"])
        self.assertIn("n’existe pas", self.lancer("faire", "service", service="postgresql", action="demarrer")["erreur"])

    def test_la_limite_de_memoire_a_des_bornes_et_un_retour(self):
        with mock.patch.object(self.m, "lire", lambda c: "MemTotal:        8000000 kB\n" if "meminfo" in c else ""):
            self.assertFalse(self.lancer("faire", "memoire", service="mysql", mo=64)["ok"])
            self.assertFalse(self.lancer("faire", "memoire", service="mysql", mo=99999)["ok"])
            self.assertFalse(self.lancer("faire", "memoire", service="cassandra-noyau", mo=512)["ok"])
            r = self.lancer("faire", "memoire", service="mysql", mo=512)
        self.assertEqual((r["ok"], r["avant"], self.f.memoire["mysql.service"]), (True, "infinity", str(512 * 1048576)))
        self.assertTrue(self.lancer("defaire", "memoire", service="mysql", avant=r["avant"])["ok"])
        self.assertEqual(self.f.memoire["mysql.service"], "infinity")

    def test_le_journal_d_un_service_est_une_lecture_en_table_fermee(self):
        self.assertIn("prêt", self.lancer("lire", "service_journal", service="sensorium")["texte"])                # son journal se lit, même s'il ne se touche pas
        self.assertFalse(self.lancer("lire", "service_journal", service="../../etc/shadow")["ok"])

    # ── conteneurs
    def test_un_conteneur_que_docker_ne_liste_pas_est_refuse(self):
        self.assertFalse(self.lancer("faire", "conteneur", nom="inconnu", action="arreter")["ok"])
        self.assertFalse(self.lancer("faire", "conteneur", nom="coffre --privileged", action="arreter")["ok"])
        self.assertFalse(self.lancer("faire", "conteneur", nom="coffre", action="rm")["ok"])
        self.assertEqual(self.f.conteneurs, {"coffre": "running", "recherche": "exited"})

    def test_un_conteneur_s_arrete_se_met_en_pause_et_se_defait(self):
        r = self.lancer("faire", "conteneur", nom="coffre", action="arreter")
        self.assertEqual((r["ok"], r["avant"], r["apres"]), (True, "running", "exited"))
        self.assertTrue(self.lancer("defaire", "conteneur", nom="coffre", action="arreter", avant="running")["ok"])
        self.assertEqual(self.f.conteneurs["coffre"], "running")
        self.assertEqual(self.lancer("faire", "conteneur", nom="coffre", action="pause")["apres"], "paused")
        self.assertEqual(self.lancer("defaire", "conteneur", nom="coffre", action="pause", avant="running")["apres"], "running")
        self.assertIn("prêt", self.lancer("lire", "conteneur_journal", nom="coffre")["texte"])

    # ── processus
    def proc(self, pid=4242, commande="clamscan -r /var/www", cgroup="0::/system.slice/cron.service\n", vivant=True):
        etat = {"vivant": vivant}

        def lire(chemin):
            if chemin == "/proc/%d/cmdline" % pid:
                return commande.replace(" ", "\x00") if etat["vivant"] else ""
            if chemin == "/proc/%d/cgroup" % pid:
                return cgroup
            if chemin == "/proc/%d/stat" % pid:
                return ("%d (x) S " % pid + " ".join(["0"] * 18) + " 777 0") if etat["vivant"] else ""
            return ""
        return lire, etat

    def test_un_processus_se_termine_s_il_est_bien_celui_que_la_page_montrait(self):
        lire, etat = self.proc()
        tues = []
        with mock.patch.object(self.m, "lire", lire), mock.patch.object(self.m.os, "kill", lambda pid, sig: (tues.append((pid, sig)), etat.update(vivant=False))):
            self.assertIn("n’est plus celui", self.lancer("faire", "processus", pid=4242, action="terminer", commande="autre chose")["erreur"])
            self.assertEqual(tues, [])
            r = self.lancer("faire", "processus", pid=4242, action="terminer", commande="clamscan -r /var/www")
        self.assertEqual((r["ok"], tues), (True, [(4242, self.m.signal.SIGTERM)]))
        self.assertFalse(self.lancer("defaire", "processus", pid=4242, action="terminer", commande="clamscan -r /var/www")["ok"])     # aucun retour, et c'est dit

    def test_les_processus_proteges_ne_se_tuent_pas(self):
        tues = []
        with mock.patch.object(self.m.os, "kill", lambda pid, sig: tues.append(pid)):
            self.assertFalse(self.lancer("faire", "processus", pid=1, action="forcer", commande="/sbin/init")["ok"])
            for service in ("ssh", "cassandra-noyau", "cassandra-courtier", "sensorium"):
                lire, _ = self.proc(cgroup="0::/system.slice/%s.service\n" % service)
                with mock.patch.object(self.m, "lire", lire):
                    self.assertIn("Services", self.lancer("faire", "processus", pid=4242, action="forcer", commande="clamscan -r /var/www")["erreur"], service)
            lire, _ = self.proc(commande="")                                                              # un processus du noyau Linux n'a pas de ligne de commande
            with mock.patch.object(self.m, "lire", lire):
                self.assertFalse(self.lancer("faire", "processus", pid=4242, action="terminer", commande="")["ok"])
        self.assertEqual(tues, [])

    def test_un_processus_sourd_n_est_pas_dit_termine(self):
        lire, _ = self.proc()
        with mock.patch.object(self.m, "lire", lire), mock.patch.object(self.m.os, "kill", lambda pid, sig: None), mock.patch.object(self.m, "disparu", lambda *a: False):
            r = self.lancer("faire", "processus", pid=4242, action="terminer", commande="clamscan -r /var/www")
        self.assertFalse(r["ok"])
        self.assertIn("Forcer", r["erreur"])

    # ── adresses et sessions
    def test_bannir_refuse_les_adresses_qu_il_ne_faut_pas_bannir(self):
        for ip, mot in (("100.64.0.11", "privé"), ("192.168.1.4", "privé"), ("203.0.113.52", "cette machine"), ("198.51.100.20", "dehors"), ("pas-une-ip", "illisible")):
            self.assertIn(mot, self.lancer("faire", "bannir", ip=ip)["erreur"], ip)
        self.assertFalse(self.lancer("faire", "bannir", ip="203.0.113.24", jail="inconnue")["ok"])
        self.assertEqual(self.f.bannies, [])

    def test_bannir_se_verifie_dans_la_liste_et_se_defait(self):
        r = self.lancer("faire", "bannir", ip="203.0.113.24")
        self.assertEqual((r["ok"], r["jail"], self.f.bannies), (True, "sshd", ["203.0.113.24"]))
        self.assertTrue(self.lancer("defaire", "bannir", ip="203.0.113.24", jail="sshd")["ok"])
        self.assertEqual(self.f.bannies, [])

    def test_tout_le_monde_dehors_ferme_chaque_terminal(self):
        r = self.lancer("faire", "sessions_fermer")
        self.assertEqual((r["ok"], [s[1] for s in r["fermees"]], self.f.sessions), (True, ["pts/0", "pts/1"], []))

    # ── redémarrer la machine
    def test_la_machine_ne_part_pas_sans_son_nom_ni_pendant_un_deploiement(self):
        self.assertIn("nom", self.lancer("faire", "redemarrer", quand="maintenant", nom="autre")["erreur"])
        self.assertFalse(self.lancer("faire", "redemarrer", quand="demain", nom="atlas")["ok"])
        with mock.patch.object(self.m, "OBSTACLES", (("un déploiement de Cassandra est en cours", ["docker", "--version"]),)):      # une commande qui réussit : l'obstacle est là
            self.assertIn("déploiement", self.lancer("faire", "redemarrer", quand="maintenant", nom="atlas")["erreur"])
        self.assertFalse(self.f.prevu)

    def test_le_redemarrage_est_prevu_s_annule_et_ne_se_prevoit_pas_deux_fois(self):
        r = self.lancer("faire", "redemarrer", quand="03:00", nom="atlas")
        self.assertEqual((r["ok"], r["prevu"]), (True, "2026-11-12 03:00"))
        self.assertEqual([c for c in self.f.lances if c[0] == "shutdown"][0][:3], ["shutdown", "-r", "03:00"])
        marque = json.loads((self.tmp / "marque.json").read_text(encoding="utf-8"))
        self.assertIn("nginx", marque["services"])                                                         # ce qui tournait : de quoi dire, au retour, ce qui n'est pas revenu
        self.assertIn("déjà prévu", self.lancer("faire", "redemarrer", quand="maintenant", nom="atlas")["erreur"])
        self.assertTrue(self.lancer("defaire", "redemarrer")["ok"])
        self.assertFalse(self.f.prevu)
        self.assertFalse((self.tmp / "marque.json").exists())

    def test_l_etat_dit_ce_qui_ne_reviendra_pas_seul(self):
        r = self.lancer("lire", "redemarrage")
        self.assertEqual((r["machine"], r["obstacles"], r["prevu"], r["retour"]), ("atlas", [], "", None))
        self.assertEqual(r["ne_reviendront_pas"]["services"], ["dovecot"])                                 # il tourne, mais ne se lance pas au démarrage
        self.assertEqual(len(r["sessions"]), 2)

    def test_pas_root_pas_de_geste(self):
        with mock.patch.object(os, "geteuid", create=True, return_value=1000):
            self.assertFalse(self.lancer("faire", "service", service="mysql", action="arreter")["ok"])
        self.assertEqual(self.systemctl(), [])


class FauxCourtier:
    def __init__(self):
        self.reponse, self.appels = {"ok": True}, []

    def demander(self, module, commande, args=(), stdin=None, delai=30):
        self.appels.append((commande, list(args)))
        return {"ok": bool(self.reponse.get("ok")), "code": 0 if self.reponse.get("ok") else 1, "sortie": json.dumps(self.reponse), "erreur": ""}


class Capacites(unittest.TestCase):
    """Les capacités du module : ce qu'elles envoient au courtier, leur preuve, et ce qu'elles rendent pour défaire."""
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

    def ex(self, cap, compte=ADMIN, **a):
        return self.n.executeur.executer("securite." + cap, "humain", a, compte=compte)

    def test_un_geste_de_service_part_au_courtier_et_se_defait_avec_ce_qu_il_a_rendu(self):
        self.c.reponse = {"ok": True, "service": "mysql", "unite": "mysql.service", "action": "arreter", "avant": {"actif": True, "au_demarrage": True}}
        r = self.ex("service_geste", service="mysql", action="arreter")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.c.appels[-1], ("machine", ["faire", "service", json.dumps({"service": "mysql", "action": "arreter"}, ensure_ascii=False)]))
        g = self.ex("machine_gestes")["resultat"]["gestes"]
        self.assertEqual([(x["geste"], x["cible"], x["detail"], x["qui"], x["defaisable"]) for x in g], [("service", "mysql", "arrêter", ADMIN, True)])
        self.c.reponse = {"ok": True, "unite": "mysql.service", "action": "demarrer"}
        d = self.ex("machine_geste_defaire", id=g[0]["id"])
        self.assertEqual(d["statut"], "faite", d)
        verbe, geste, envoi = self.c.appels[-1][1]
        self.assertEqual((verbe, geste), ("defaire", "service"))
        self.assertEqual({k: json.loads(envoi)[k] for k in ("service", "action", "avant")}, {"service": "mysql", "action": "arreter", "avant": {"actif": True, "au_demarrage": True}})
        apres = self.ex("machine_gestes")["resultat"]["gestes"][0]
        self.assertEqual((apres["defaisable"], "défait par" in apres["resultat"]), (False, True))
        self.assertEqual(self.ex("machine_geste_defaire", id=g[0]["id"])["statut"], "echec")              # un geste ne se défait qu'une fois

    def test_un_refus_du_courtier_est_une_erreur_dite(self):
        self.c.reponse = {"ok": False, "erreur": "ssh : l’arrêter fermerait la porte de la machine"}
        r = self.ex("service_geste", service="ssh", action="arreter")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("porte", r["erreur"])

    def test_un_geste_que_le_courtier_ne_prouve_pas_n_est_pas_fait(self):
        self.c.reponse = {"ok": True}                                                                      # ok, mais sans l'unité relue : la preuve manque
        self.assertNotEqual(self.ex("service_geste", service="mysql", action="arreter")["statut"], "faite")

    def test_chaque_geste_envoie_ses_arguments_et_rien_d_autre(self):
        for cap, args, reponse, geste in (
                ("conteneur_geste", {"nom": "coffre", "action": "pause"}, {"ok": True, "nom": "coffre", "action": "pause", "avant": "running", "apres": "paused"}, "conteneur"),
                ("processus_geste", {"pid": 4242, "action": "terminer", "commande": "clamscan -r /var/www"}, {"ok": True, "pid": 4242, "action": "terminer"}, "processus"),
                ("adresse_bannir", {"ip": "203.0.113.24"}, {"ok": True, "jail": "sshd", "ip": "203.0.113.24"}, "bannir"),
                ("service_memoire", {"service": "mysql", "mo": 512}, {"ok": True, "unite": "mysql.service", "mo": 512, "avant": "infinity"}, "memoire"),
                ("machine_redemarrer", {"quand": "03:00", "nom": "atlas"}, {"ok": True, "prevu": "2026-11-12 03:00", "quand": "03:00"}, "redemarrer")):
            self.c.reponse = reponse
            r = self.ex(cap, **args)
            self.assertEqual(r["statut"], "faite", (cap, r))
            commande, (verbe, g, envoi) = self.c.appels[-1]
            self.assertEqual((commande, verbe, g, json.loads(envoi)), ("machine", "faire", geste, args), cap)

    def test_tout_le_monde_dehors_n_a_pas_de_retour_et_le_dit(self):
        self.c.reponse = {"ok": True, "fermees": [["lea", "pts/0", "100.64.0.11"]]}
        r = self.ex("sessions_fermer_toutes")
        self.assertEqual(r["statut"], "faite", r)
        g = self.ex("machine_gestes")["resultat"]["gestes"][0]
        self.assertEqual((g["geste"], g["defaisable"], g["detail"]), ("sessions_fermer", False, "tout le monde dehors : 1 session(s) fermée(s)"))
        retour = self.ex("machine_geste_defaire", id=g["id"])
        self.assertEqual(retour["statut"], "echec")
        self.assertIn("pas de retour", retour["erreur"])
        n = len(self.c.appels)
        self.c.reponse = {"ok": True, "service": "nginx", "unite": "nginx.service", "action": "redemarrer", "avant": {"actif": True, "au_demarrage": True}}
        self.ex("service_geste", service="nginx", action="redemarrer")
        self.assertFalse(self.ex("machine_gestes")["resultat"]["gestes"][0]["defaisable"])                 # un redémarrage n'a rien à défaire : pas de bouton
        self.assertEqual(len(self.c.appels), n + 1)

    def test_les_lectures_passent_par_le_verbe_lire(self):
        self.c.reponse = {"ok": True, "service": "nginx", "texte": "prêt"}
        self.assertEqual(self.ex("service_journal", service="nginx")["resultat"]["texte"], "prêt")
        self.assertEqual(self.c.appels[-1][1][:2], ["lire", "service_journal"])
        self.c.reponse = {"ok": True, "machine": "atlas", "obstacles": [], "prevu": ""}
        self.assertEqual(self.ex("redemarrage_etat")["resultat"]["machine"], "atlas")
        self.assertEqual(self.c.appels[-1][1][:2], ["lire", "redemarrage"])

    def test_sans_le_droit_rien_ne_part(self):
        self.n.droits.regler_admin(SIMPLE, False)
        for cap, args in (("service_geste", {"service": "mysql", "action": "arreter"}), ("machine_redemarrer", {"quand": "maintenant", "nom": "atlas"}), ("service_journal", {"service": "nginx"})):
            self.assertNotEqual(self.ex(cap, compte=SIMPLE, **args)["statut"], "faite", cap)
        self.assertEqual(self.c.appels, [])

    def test_l_installation_pose_la_commande(self):
        for f in ("CN_installer.sh", "CN_verifier.sh"):
            self.assertIn("for c in mesurer agir outils machine; do", (RACINE / "modules" / "securite" / f).read_text(encoding="utf-8"))
        self.assertIn("/usr/libexec/cassandra/securite/machine", (RACINE / "modules" / "securite" / "CN_retirer.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : charger_commande, FausseMachine, Commande, FauxCourtier, Capacites
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/securite/commandes/CN_machine (la table fermée), modules/securite/CN_module.py (les capacités et le journal), interface/CN_machine-ecran.js (les boutons)
