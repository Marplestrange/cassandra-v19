# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la flotte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #df169a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la flotte : le parc fusionné, la présence, la disponibilité, le contrôle SSH, les commandes nommées. Aucun réseau : l'accès au monde est simulé.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=df169a ▼▼▼
"""Bancs de la flotte : le parc fusionné, la présence, la disponibilité, le contrôle SSH, les commandes nommées. Aucun réseau : l'accès au monde est simulé."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

ROOT, BEA = "root@x.fr", "bea@x.fr"


def pair(online=True, os="linux", ip="100.64.0.2", self_=False, last_seen=""):
    return {"online": online, "os": os, "ip": ip, "last_seen": last_seen, "self": self_, "observe": "2026-10-12 10:00:00"}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "flotte", mods / "flotte", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("flotte")["ok"])
        self.n.droits.regler_admin(ROOT, True)
        self.ctx = self.n.executeur.contextes["flotte"]
        self.ctx.hote_nom = "orion"
        self.ts = {"orion": pair(self_=True, ip="100.64.0.1"), "athena": pair(ip="100.64.0.2"), "rosco": pair(os="windows", ip="100.64.0.3"), "tel": pair(os="iOS", ip="100.64.0.9")}
        self.commandes, self.ssh_ok, self.sortie = [], {"100.64.0.2": True}, {}
        a = self.ctx.acces
        a.tailscale_live = lambda: dict(self.ts)
        a.ssh_sonde = lambda ip, user="root", timeout=12: (True, "Tailscale SSH · %s" % user) if self.ssh_ok.get(ip) else (False, "Permission denied")
        a.ssh_exec = self.ssh_exec
        a.tcp = lambda hote, port, timeout=4: hote == "nas.lan"
        a.http_json = lambda url, jeton="", timeout=6: {"health_score": 90, "cpu": 12.0, "ram": 40.0, "disk": 55.0} if "ok.test" in url else {"_error": "URLError"}
        a.tailscale_ping = lambda ip: "pong from athena (100.64.0.2) via 1.2.3.4:41641 in 12ms\npong in 9ms\n"
        for cap in ("machine_ajouter", "machine_retirer", "machine_basculer", "engagement", "lien_enregistrer", "lien_retirer", "oublier", "service_agir"):
            self.n.catalogue.regler_palier("flotte." + cap, "auto")

    def ssh_exec(self, m, cmd, timeout=30):
        self.commandes.append((m.get("hote"), m.get("auth"), m.get("cle"), cmd))
        for motif, rep in self.sortie.items():
            if motif in cmd:
                return rep
        if "CPU:" in cmd:
            return "CPU:12.5\nRAM:40.2\nDISK:55\nHOST:serveur\nKERN:6.1\nUP:up 3 days\n", "", 0
        return "", "", 0

    def ex(self, cap, compte=ROOT, acteur="humain", **args):
        return self.n.executeur.executer("flotte." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def moteur(self, cle):
        r = self.n.lancer("flotte." + cle)
        self.assertEqual(r["statut"], "fait", r)
        return r

    def evts(self, genre=None):
        return [e for e in self.ok("evenements", limite=300)["evenements"] if genre is None or e["genre"] == genre]

    def machine(self, p, nom):
        return next(m for m in p["machines"] if m["nom"] == nom)


class Parc(Monde):
    def test_les_sources_se_mettent_cote_a_cote_et_le_niveau_se_deduit(self):
        self.ok("machine_ajouter", nom="nas", type="ping", hote="nas.lan")
        self.ok("machine_ajouter", nom="rosco", type="ssh", hote="100.64.0.3", auth="cle", cle="-----KEY-----", systeme="windows")
        p = self.ok("parc")
        orion, athena, rosco, nas, tel = (self.machine(p, n) for n in ("orion", "athena", "rosco", "nas", "tel"))
        self.assertEqual(orion["niveau"], "agent")
        self.assertEqual((athena["niveau"], athena["tailscale_ssh"]), ("signal", False))      # pas encore sondée
        self.assertEqual(rosco["niveau"], "ssh")                                              # une entrée ssh au registre
        self.assertEqual(nas["niveau"], "observation")                                         # au registre, sans accès SSH
        self.assertEqual((tel["groupe"], tel["sources"]["ssh"]["texte"]), ("Mobiles", "sans objet"))
        self.assertEqual(rosco["groupe"], "Postes")
        self.assertEqual(athena["sources"]["tailscale"]["etat"], "ok")
        self.assertEqual(p["compte"]["declarees"], 5)

    def test_la_sonde_sans_cle_donne_le_niveau_ssh_et_une_transition(self):
        self.moteur("presence")
        a = self.machine(self.ok("parc"), "athena")
        self.assertEqual((a["niveau"], a["tailscale_ssh"]), ("ssh", True))
        self.assertEqual(len(self.evts("controle")), 1)
        self.moteur("presence")
        self.assertEqual(len(self.evts("controle")), 1)                                       # pas de nouvel événement tant que rien ne change
        self.ssh_ok["100.64.0.2"] = False
        self.moteur("presence")
        self.assertEqual(len(self.evts("controle")), 2)
        self.assertEqual(self.machine(self.ok("parc"), "athena")["niveau"], "signal")         # le niveau retombe seul

    def test_une_attendue_hors_ligne_est_une_panne_une_intermittente_non(self):
        self.moteur("presence")
        self.ts["athena"] = pair(online=False)
        self.ts["rosco"] = pair(online=False, os="windows", ip="100.64.0.3")
        self.ok("engagement", nom="rosco", statut="intermittente")
        self.moteur("presence")
        p = self.ok("parc")
        self.assertEqual((self.machine(p, "athena")["etat"], self.machine(p, "athena")["libelle"]), ("erreur", "hors ligne · panne"))
        self.assertEqual((self.machine(p, "rosco")["etat"], self.machine(p, "rosco")["libelle"]), ("avert", "hors ligne · volontaire"))
        self.assertEqual(p["compte"]["attendues_hors_ligne"], 1)
        pertes = self.evts("perte")
        self.assertEqual(sorted(e["nom"] for e in pertes), ["athena", "rosco"])               # l'absence est datée dans les deux cas
        self.ts["athena"] = pair()
        self.moteur("presence")
        retour = [e for e in self.evts("retour") if e["nom"] == "athena"]
        self.assertEqual(len(retour), 1)
        self.assertIn("Revenue", retour[0]["detail"])

    def test_une_machine_du_registre_que_tailscale_voit_n_est_pas_hors_ligne_si_sa_sonde_echoue(self):
        self.ok("machine_ajouter", nom="athena", type="ssh", hote="100.64.0.2", auth="cle", cle="K")
        self.sortie["CPU:"] = ("", "Connection refused", 255)
        self.moteur("presence")
        self.assertTrue(self.machine(self.ok("parc"), "athena")["en_ligne"])
        m = self.ok("historique", nom="athena")
        self.assertEqual(m["points"][-1]["en_ligne"], True)                                    # Tailscale d'abord : la sonde mesure, elle ne décide pas
        self.assertIn("Connection refused", m["points"][-1]["erreur"])


class Registre(Monde):
    def test_les_secrets_sont_chiffres_et_ne_ressortent_pas(self):
        self.ok("machine_ajouter", nom="rosco", type="ssh", hote="100.64.0.3", auth="cle", cle="CLE-PRIVEE-SECRETE", mot_de_passe="mdp-secret")
        brut = self.ctx.stockage.lire("SELECT secrets FROM machines")[0]["secrets"]
        self.assertTrue(brut)
        self.assertNotIn("CLE-PRIVEE", brut)
        self.assertNotIn("mdp-secret", brut)
        m = self.ok("machines")["machines"][0]
        self.assertEqual(m["secrets_poses"], ["cle", "mot_de_passe"])
        self.assertNotIn("CLE-PRIVEE", repr(self.ok("parc")))
        self.ok("diagnostic", nom="rosco", action="disques")
        self.assertEqual(self.commandes[-1][2], "CLE-PRIVEE-SECRETE")                          # la clé n'est déchiffrée que pour servir

    def test_ajouter_se_defait_et_les_refus(self):
        r = self.ex("machine_ajouter", nom="Mon Serveur!", type="ssh", hote="x")
        self.assertEqual(r["statut"], "echec")
        for args in (dict(nom="a", type="ssh"), dict(nom="a", type="inconnu", hote="x"), dict(nom="a", type="cassandra", url="ftp://x"), dict(nom="a", type="ssh", hote="x", port=0)):
            self.assertEqual(self.ex("machine_ajouter", **args)["statut"], "echec", args)
        self.ok("machine_ajouter", nom="a", type="ping", hote="nas.lan")
        res = self.ok("machine_ajouter", nom="a", type="ping", hote="autre.lan")                 # une mise à jour garde de quoi revenir
        self.assertEqual(res["action"], "mise à jour")
        self.n.catalogue.get("flotte.machine_ajouter").defaire(self.ctx, res)
        self.assertEqual(self.ctx.stockage.lire("SELECT hote FROM machines")[0]["hote"], "nas.lan")

    def test_retirer_et_basculer(self):
        self.ok("machine_ajouter", nom="nas", type="ping", hote="nas.lan")
        self.ok("machine_basculer", nom="nas", actif=False)
        self.moteur("presence")
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM mesures WHERE nom='nas'")[0]["n"], 0)    # suspendue : on ne la relève pas
        res = self.ok("machine_retirer", nom="nas")
        self.assertEqual(self.ok("machines")["machines"], [])
        self.n.catalogue.get("flotte.machine_retirer").defaire(self.ctx, res)
        self.assertEqual([m["nom"] for m in self.ok("machines")["machines"]], ["nas"])

    def test_une_mesure_absente_est_nulle_jamais_zero(self):
        self.ok("machine_ajouter", nom="nas", type="ping", hote="nas.lan")
        self.ok("machine_ajouter", nom="serveur", type="ssh", hote="10.0.0.5", auth="defaut")
        self.moteur("presence")
        pts = {n: self.ok("historique", nom=n)["points"][-1] for n in ("nas", "serveur")}
        self.assertEqual((pts["nas"]["cpu"], pts["nas"]["ram"]), (None, None))
        self.assertEqual(pts["nas"]["en_ligne"], True)
        self.assertEqual(pts["serveur"]["cpu"], 12.5)

    def test_une_autre_cassandra(self):
        self.ok("machine_ajouter", nom="amie", type="cassandra", url="https://ok.test", jeton="JETON")
        self.ok("machine_ajouter", nom="muette", type="cassandra", url="https://ko.test")
        self.moteur("presence")
        self.assertEqual(self.ok("historique", nom="amie")["points"][-1]["sante"], 90)
        self.assertEqual(self.ok("historique", nom="muette")["points"][-1]["erreur"], "URLError")


class Engagement(Monde):
    def test_les_refus_et_le_retour(self):
        for args in (dict(nom="athena", statut="fantome"), dict(nom="athena", niveau="dieu"), dict(nom="athena", niveau="agent"), dict(nom="athena", niveau="ssh"), dict(nom="athena")):
            self.assertEqual(self.ex("engagement", **args)["statut"], "echec", args)
        res = self.ok("engagement", nom="orion", niveau="agent")
        self.assertEqual(res["niveau"], "agent")
        res = self.ok("engagement", nom="athena", statut="retiree")
        self.assertEqual(self.machine(self.ok("parc"), "athena")["groupe"], "Retirées")
        self.n.catalogue.get("flotte.engagement").defaire(self.ctx, res)
        self.assertEqual(self.machine(self.ok("parc"), "athena")["statut"], "attendue")

    def test_ssh_exige_un_acces_constate(self):
        self.moteur("presence")
        self.assertEqual(self.ok("engagement", nom="athena", niveau="ssh")["niveau"], "ssh")


class Disparues(Monde):
    def test_disparition_oubli_et_retour(self):
        self.moteur("presence")
        del self.ts["tel"]
        self.moteur("presence")
        tel = self.machine(self.ok("parc"), "tel")
        self.assertTrue(tel["disparue"])
        self.assertEqual(tel["groupe"], "Disparues")
        self.assertEqual(len(self.evts("disparition")), 1)
        self.moteur("presence")
        self.assertEqual(len(self.evts("disparition")), 1)                                     # une fois seulement
        self.assertEqual(self.ex("oublier", nom="athena")["statut"], "echec")                   # Tailscale la liste encore
        self.assertEqual(self.ex("oublier", nom="orion")["statut"], "echec")                    # l'hôte
        res = self.ok("oublier", nom="tel")
        self.assertEqual(res["efface"], ["vus"])
        self.assertNotIn("tel", [m["nom"] for m in self.ok("parc")["machines"]])
        self.assertEqual(len(self.evts("oubli")), 1)                                           # l'historique reste, avec la trace de l'oubli
        self.n.catalogue.get("flotte.oublier").defaire(self.ctx, res)
        self.assertIn("tel", [m["nom"] for m in self.ok("parc")["machines"]])

    def test_une_disparue_trop_ancienne_s_oublie_seule(self):
        self.moteur("presence")
        del self.ts["tel"]
        self.moteur("presence")
        self.ctx.stockage.ecrire("UPDATE vus SET ts='2020-01-01 00:00:00' WHERE nom='tel'")
        self.moteur("presence")
        self.assertNotIn("tel", [m["nom"] for m in self.ok("parc")["machines"]])


class Verdict(Monde):
    def test_stable_seulement_si_la_presence_tourne(self):
        self.ok("engagement", nom="orion", niveau="agent")
        self.moteur("presence")
        v = self.ok("verdict")
        self.assertIn(v["niveau"], ("stable", "regarder"))
        self.n.reglages.poser("flotte.presence_active", False, "")
        v = self.ok("verdict")
        self.assertEqual(v["niveau"], "inconnu")
        self.assertIn("Je ne peux pas dire", v["titre"])

    def test_une_panne_passe_avant_le_reste(self):
        self.moteur("presence")
        self.ts["athena"] = pair(online=False)
        self.moteur("presence")
        v = self.ok("verdict")
        self.assertEqual(v["niveau"], "panne")
        self.assertIn("athena est attendue et ne répond plus", v["titre"])
        self.assertEqual(v["lignes"][0]["gestes"][0]["f"], "machine")

    def test_une_machine_attendue_sans_controle_se_dit(self):
        self.moteur("presence")
        v = self.ok("verdict")
        self.assertTrue(any("aucune clé SSH" in l["titre"] and "rosco" in l["titre"] for l in v["lignes"]))

    def test_les_pertes_repetees_se_comptent(self):
        self.moteur("presence")
        for _ in range(2):
            self.ts["athena"] = pair(online=False)
            self.moteur("presence")
            self.ts["athena"] = pair()
            self.moteur("presence")
        v = self.ok("verdict")
        self.assertTrue(any("2 pertes en 24 h" in l["titre"] for l in v["lignes"]))
        d = self.ok("disponibilite", jours=30)["machines"]
        self.assertEqual(next(m for m in d if m["nom"] == "athena")["pannes"], 2)


class Distance(Monde):
    def test_diagnostic_de_lecture_seulement(self):
        self.moteur("presence")
        r = self.ok("diagnostic", nom="athena", action="memoire")
        self.assertEqual(r["code"], 0)
        self.assertEqual(self.commandes[-1][1], "tailscale")                                    # machine virtuelle, sans secret
        for args in (dict(nom="athena", action="svc_stop", service="nginx"), dict(nom="athena", action="rm -rf"), dict(nom="athena", action="svc_status", service="x; reboot"), dict(nom="inconnue", action="disques")):
            self.assertEqual(self.ex("diagnostic", **args)["statut"], "echec", args)
        self.assertTrue(any(e["genre"] == "action" for e in self.evts()))

    def test_arreter_un_service_vital_est_refuse_et_un_service_se_remet_comme_avant(self):
        self.moteur("presence")
        self.assertEqual(self.ex("service_agir", nom="athena", action="svc_stop", service="sshd")["statut"], "echec")
        self.assertEqual(self.ex("service_agir", nom="athena", action="diagnostic", service="nginx")["statut"], "echec")
        self.sortie["is-active"] = ("active\n", "", 0)
        res = self.ok("service_agir", nom="athena", action="svc_restart", service="nginx")
        self.assertEqual(res["etat_avant"], "active")
        self.assertTrue(self.n.catalogue.get("flotte.service_agir").prouver(self.ctx, res))
        self.sortie["is-active"] = ("inactive\n", "", 3)
        self.assertFalse(self.n.catalogue.get("flotte.service_agir").prouver(self.ctx, res))
        n = len(self.commandes)
        self.n.catalogue.get("flotte.service_agir").defaire(self.ctx, res)
        self.assertIn("systemctl start nginx", self.commandes[n][3])                              # il était actif : on le remet actif

    def test_le_ping_lit_la_latence(self):
        self.assertEqual(self.ok("ping", nom="athena")["latence_ms"], 9.0)
        self.assertEqual(self.ok("ping", nom="orion")["latence_ms"], 0)
        self.assertEqual(self.ex("ping", nom="inconnue")["statut"], "echec")

    def test_le_releve_ecrit_ce_qui_compte_et_dit_l_injoignable(self):
        self.moteur("presence")
        self.sortie["DISK"] = ("DISK / 93% 12\nRAM 40\nUP 90000\nLOAD 0.5 4\nREBOOT oui\nFAILED nginx.service\nOS Debian 12\n", "", 0)
        self.moteur("releve")
        r = {x["cle"]: x for x in self.ok("historique", nom="athena")["releves_detail"]}
        self.assertEqual(r["disque./"]["gravite"], "warning")
        self.assertEqual(r["redemarrage_requis"]["valeur"], "oui")
        self.assertIn("nginx.service", r["services_en_echec"]["valeur"])
        self.assertEqual(r["uptime"]["valeur"], "1 j 1 h")
        self.sortie["DISK"] = ("", "no route", 255)
        self.moteur("releve")
        r = {x["cle"]: x for x in self.ok("historique", nom="athena")["releves_detail"]}
        self.assertEqual(r["joignable"]["gravite"], "warning")
        self.assertIn("redemarrage_requis", r)                                                   # les anciens relevés restent, avec leur âge


class Liens(Monde):
    def test_lier_et_delier_se_defont(self):
        res = self.ok("lien_enregistrer", nom="athena", genre="project", ref="12", note="site client")
        self.assertEqual(self.ok("liens", nom="athena")["liens"][0]["note"], "site client")
        self.assertEqual(self.ex("lien_enregistrer", nom="athena", genre="vaisseau", ref="1")["statut"], "echec")
        self.n.catalogue.get("flotte.lien_enregistrer").defaire(self.ctx, res)
        self.assertEqual(self.ok("liens")["liens"], [])
        self.ok("lien_enregistrer", nom="athena", genre="note", ref="N-0001")
        r2 = self.ok("lien_retirer", nom="athena", genre="note", ref="N-0001")
        self.n.catalogue.get("flotte.lien_retirer").defaire(self.ctx, r2)
        self.assertEqual(len(self.ok("liens")["liens"]), 1)


class Droits(Monde):
    def test_un_compte_ordinaire_ne_voit_ni_ne_touche_la_flotte(self):
        for cap in ("parc", "verdict", "machines", "historique", "disponibilite", "evenements", "liens", "actions"):
            self.assertEqual(self.ex(cap, compte=BEA)["statut"], "echec", cap)
        self.assertEqual(self.ex("machine_ajouter", compte=BEA, nom="x", type="ping", hote="h")["statut"], "refuse")
        self.assertIn("réservée à l'administrateur", self.ex("parc", compte=BEA)["erreur"])

    def test_un_agent_lit_et_ses_ecritures_se_racontent_d_abord(self):
        self.n.catalogue.regler_palier("flotte.machine_ajouter", "raconter")
        r = self.ex("machine_ajouter", compte="", acteur="cassandra", nom="x", type="ping", hote="h")
        self.assertEqual(r["statut"], "racontee")
        self.assertEqual(self.ok("machines")["machines"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : pair, Monde, Parc, Registre, Engagement, Disparues, Verdict, Distance …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
