# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la vue d'ensemble
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #642cce
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la vue d'ensemble : le verdict est composé, et une source muette n'est jamais comptée « tranquille ».
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=642cce ▼▼▼
"""Bancs de la vue d'ensemble : le verdict est composé, et une source muette n'est jamais comptée « tranquille »."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import json   # noqa: E402
from modules.vue import CN_composer as _facade   # noqa: E402
from modules.vue import CN_machine as machine   # noqa: E402
from noyau import CN_manifeste as _manifeste   # noqa: E402
from noyau.CN_points import ServicePoints   # noqa: E402

DOSSIER = RACINE / "modules" / "vue"
_SVC = ServicePoints(None)                                       # sans stock d'EC : c'est la référence du dépôt qui sert
_DEFAUTS = _SVC.declarer(_manifeste.charger(DOSSIER / "CN_manifeste.toml"), DOSSIER)


def composer(admin, compte, s, quand):
    """Comme le module : par le noyau (ctx.point), donc contrat validé à l'entrée et à la sortie."""
    return _facade.composer(admin, compte, s, quand, appeler=lambda point, entree: _SVC.appeler("vue", point, entree))


def site(d, up=True, ssl=60, code=200):
    return {"domaine": d, "source": "declare", "up": up, "code": code, "ms": 120, "ssl_jours": ssl}


def sources(**kw):
    base = {"sites": {"sites": [site("a.fr")]}, "flotte": {"machines": []}, "metriques": {"disk": 40, "cpu": 10}, "sante": {"score": 95},
            "incidents": {"incidents": []}, "fil": {"fil": []}, "notifs": {"notifications": []}, "autonomie": {"palier": "proposer"}}
    base.update(kw)
    return base


class Vue(unittest.TestCase):
    def test_tout_va_bien_dit_stable(self):
        r = composer(True, "root", sources(), "t")
        self.assertEqual(r["niveau"], "stable")
        self.assertEqual(r["muettes"], [])
        self.assertEqual(r["sites"][0]["domain"], "a.fr")                    # les mots que l'écran lit

    def test_un_site_qui_ne_repond_pas_est_une_panne(self):
        r = composer(True, "root", sources(sites={"sites": [site("a.fr"), site("b.fr", up=False, code=502)]}), "t")
        self.assertEqual(r["niveau"], "panne")
        self.assertIn("b.fr ne répond pas (code 502)", r["titre"])
        self.assertEqual(r["sites"][0]["domain"], "b.fr")                    # le tombé passe en tête

    def test_une_source_muette_n_est_jamais_stable(self):
        r = composer(True, "root", sources(metriques=None), "t")
        self.assertEqual(r["niveau"], "inconnu")
        self.assertIn("collecteur", r["muettes"])
        self.assertIn("se tait", r["titre"])

    def test_une_panne_l_emporte_sur_le_silence(self):
        r = composer(True, "root", sources(metriques=None, sites={"sites": [site("a.fr", up=False)]}), "t")
        self.assertEqual(r["niveau"], "panne")

    def test_le_certificat_a_deux_seuils(self):
        self.assertEqual(composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=5)]}), "t")["niveau"], "panne")
        r = composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=15)]}), "t")
        self.assertEqual(r["niveau"], "regarder")
        self.assertEqual(composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=25)]}), "t")["niveau"], "stable")

    def test_une_machine_attendue_hors_ligne_est_une_panne_pas_une_intermittente(self):
        att = {"nom": "m1", "statut": "attendue", "en_ligne": False, "dernier_contact": "hier"}
        inter = {"nom": "m2", "statut": "intermittente", "en_ligne": False}
        r = composer(True, "r", sources(flotte={"machines": [att, inter]}), "t")
        self.assertEqual(r["niveau"], "panne")
        self.assertEqual(r["flotte"]["hors_ligne"], ["m1"])
        self.assertEqual(composer(True, "r", sources(flotte={"machines": [inter]}), "t")["niveau"], "stable")

    def test_un_disque_presque_plein_se_dit(self):
        self.assertEqual(composer(True, "r", sources(metriques={"disk": 90}), "t")["niveau"], "regarder")
        self.assertEqual(composer(True, "r", sources(metriques={"disk": 97}), "t")["niveau"], "panne")

    def test_le_verdict_reprend_l_age_de_la_sonde_et_du_panneau_que_sites_donne(self):
        avec = {"sites": [site("a.fr")], "portee": {"sonde": "2026-11-11 00:41:28", "panneau_releve": "2026-11-11 00:41:30"}}
        a = composer(True, "r", sources(sites=avec), "t")["ages"]
        self.assertEqual((a["sonde"], a["sites"]), ("2026-11-11 00:41:28", "2026-11-11 00:41:30"))
        a = composer(True, "r", sources(), "t")["ages"]                        # Sites ne dit rien (aucune mesure, panneau muet) : rien, jamais une heure inventée
        self.assertEqual((a["sonde"], a["sites"]), (None, None))
        a = composer(True, "r", sources(sites={"sites": [], "portee": {"sonde": 1794357688.2, "panneau_releve": ""}}), "t")["ages"]
        self.assertEqual((a["sonde"], a["sites"]), (None, None))               # autre chose qu'une heure écrite : ignoré

    def test_un_compte_ne_voit_ni_la_machine_ni_la_flotte(self):
        r = composer(False, "bea", {"sites": {"sites": [site("a.fr")]}, "notifs": {"notifications": [{"niveau": "critique", "titre": "x", "id": 1}]}}, "t")
        self.assertFalse(r["admin"])
        for cle in ("flotte", "machine", "cassandra", "fil"):
            self.assertNotIn(cle, r)
        self.assertEqual(r["cloche"]["total"], 1)
        self.assertEqual([c["cle"] for c in r["compteurs"]], ["sites", "tls", "notifs"])

    def test_un_compte_n_est_pas_dit_muet_pour_ce_qu_il_ne_lit_pas(self):
        r = composer(False, "bea", {"sites": {"sites": [site("a.fr")]}}, "t")
        self.assertEqual(r["muettes"], [])
        self.assertEqual(r["niveau"], "stable")


def _l(cle, valeur, grave=False, **plus):
    """Une ligne du monde du Sensorium."""
    return dict({"wkey": cle, "value": valeur, "severity": "warning" if grave else "info", "libelle": cle, "famille": cle.split(".")[0], "gravite": "info"}, **plus)


def _machine(**sources):
    """Les sources de la page « La machine », toutes lues, sur une petite machine ; `sources` remplace (None = muette, "absent" = module non installé)."""
    monde = [_l("system.hostname", "atlas"), _l("system.os", "Debian GNU/Linux 12 (bookworm) · x86_64 · kvm"), _l("system.kernel", "6.1.0-1-amd64"), _l("system.uptime", "3 j 2 h"),
             _l("system.redemarrage_requis", "non"), _l("maj.paquets", "3 en attente (apt), dont 1 de sécurité"), _l("interface.eth0", "up · 203.0.113.5, 2001:db8::1 · route par défaut"),
             _l("health.score", "65/100 (à surveiller) · 2 alertes, ressources 95/100", True, detail=json.dumps({"ressources": 95, "alertes": ["a", "b"]})),
             _l("montage./", "81% (58/75 Go, ext4) · inodes 9%"), _l("prevision.disque./", "plein dans ~2 jours (+6.2 Go/jour, 17 Go libres)", True, famille="prevision"),
             _l("exposition.22", "sshd · PUBLIC (joignable sur 203.0.113.5) · SSH", True, famille="exposition"), _l("fail2ban.sshd", "8 adresses bannies"),
             _l("ssh.echecs", "41 échecs en 1 h · surtout 198.51.100.7 (10), 198.51.100.9 (6)"), _l("logiciel.docker", "installé (/usr/bin/docker)"), _l("logiciel.wg", "absent"),
             _l("conteneur_ressources.coffre", "CPU 0.04% · mémoire 44.84MiB / 7.569GiB (0.58%)"), _l("image.coffre", "image exemple/coffre:latest construite il y a 12 j")]
    s = {"etat": ("ok", {"rows": monde, "muet": False, "age_s": 20, "fige": False, "hote": "atlas"}),
         "metriques": ("ok", {"cpu": 12.5, "ram": 36.5, "disk": 81.0, "swap": 5.6, "load_1m": 0.2, "load_5m": 0.4, "load_15m": 0.5, "ram_used_gb": 2.8, "ram_total_gb": 7.6,
                              "top_processes": [{"user": "www-data", "cpu": 61.5, "command": "php-fpm: pool boutique.exemple.test"}]}),
         "sante": ("ok", {"score": 95}),
         "services": ("ok", [{"name": "nginx", "status": "active", "enabled": 1, "active": 1, "description": "nginx", "sub_state": "running", "unit_file_state": "enabled"},
                             {"name": "ssh", "status": "active", "enabled": 1, "active": 1, "description": "OpenBSD Secure Shell server", "sub_state": "running", "unit_file_state": "enabled"},
                             {"name": "php8.3-fpm", "status": "failed", "enabled": 1, "active": 0, "description": "PHP", "sub_state": "failed", "unit_file_state": "enabled"}]),
         "echecs": ("ok", [{"unit": "php8.3-fpm.service", "active_state": "failed"}, {"unit": "●", "active_state": "failed"}]),
         "ports": ("ok", [{"port": 80, "protocol": "tcp", "process": "nginx"}, {"port": 443, "protocol": "tcp", "process": "nginx"}, {"port": 22, "protocol": "tcp", "process": "sshd"}]),
         "conteneurs": ("ok", [{"name": "coffre", "image": "exemple/coffre:latest", "status": "Up 36 hours (healthy)"}, {"name": "recherche", "image": "exemple/recherche", "status": "Exited (1) 2 hours ago"}]),
         "sessions": ("ok", [{"user": "sshd", "ip": "203.0.113.24", "login_time": "2026-11-11T00:06:10.7"}, {"user": "lea", "ip": "100.64.0.11", "login_time": "2026-11-10T22:41:03"}]),
         "oom": ("ok", [{"ts": "t1", "killed_process": "php-fpm", "memory_used_mb": 1840}, {"ts": "t2", "killed_process": "mysqld", "memory_used_mb": 2310}]), "acquits": ("ok", {"signatures": ["t2_mysqld"]}),
         "certificats": ("ok", {"certificats": [{"jours": 82, "hote": "chat.exemple.test"}, {"jours": 5, "hote": "boutique.exemple.test"}]}),
         "tailscale": ("ok", {"etat": "connecte", "pairs": [{"nom": "tel-lea", "ip": "100.64.0.11", "en_ligne": True}, {"nom": "atlas-2", "ip": "100.64.0.12", "en_ligne": False}]}),
         "netbird": ("absent", None), "depots": ("ok", {"destinations": []}), "panneau_sites": ("absent", None)}
    for k, v in sources.items():
        s[k] = ("muet", None) if v is None else ("absent", None) if v == "absent" else ("ok", v)
    return machine.composer(s, "2026-11-11 14:09:06")


class Machine(unittest.TestCase):
    """La page « La machine » : une fonction pure, des relevés des modules à ce que l'écran dessine. Rien n'est inventé."""
    def test_la_fiche_se_lit_dans_les_releves_du_sensorium(self):
        m = _machine()["machine"]
        self.assertEqual((m["nom"], m["os"], m["archi"], m["nature"], m["noyau"], m["allumee"]), ("atlas", "Debian GNU/Linux 12 (bookworm)", "x86_64", "kvm", "6.1.0-1-amd64", "3 j 2 h"))
        self.assertFalse(m["redemarrage"])
        self.assertEqual((m["maj"]["total"], m["maj"]["secu"]), (3, 1))
        self.assertEqual(m["interfaces"], [{"nom": "eth0", "etat": "up", "v4": ["203.0.113.5"], "v6": ["2001:db8::1"], "defaut": True}])

    def test_la_sante_est_la_note_d_ensemble_pas_celle_des_ressources(self):
        self.assertEqual(_machine()["sante"], {"score": 65, "mot": "à surveiller", "alertes": 2, "ressources": 95})

    def test_ce_qui_cloche_met_la_machine_avant_l_exposition(self):
        self.assertEqual([x["cle"] for x in _machine()["cloche"]], ["prevision.disque./", "exposition.22"])       # la note de santé n'est pas une alerte : elle les compte

    def test_le_disque_porte_sa_prevision(self):
        d = _machine()["disques"][0]
        self.assertEqual((d["montage"], d["pct"], d["utilise_go"], d["total_go"], d["type"], d["inodes_pct"], d["alerte"]), ("/", 81, 58.0, 75.0, "ext4", 9, True))
        self.assertIn("plein dans", d["prevision"])

    def test_un_conteneur_qui_tourne_est_dit_tourner(self):
        """La page d'avant cherchait « run » dans « Up 36 hours » : tous les conteneurs étaient rouges."""
        c = {x["nom"]: x for x in _machine()["conteneurs"]}
        self.assertEqual((c["coffre"]["tourne"], c["coffre"]["etat"]), (True, "tourne depuis 36 h · sain"))
        self.assertEqual((c["coffre"]["image_age_j"], c["coffre"]["cpu"], c["coffre"]["memoire"]), (12, 0.04, "44.84 Mo"))
        self.assertEqual((c["recherche"]["tourne"], c["recherche"]["etat"]), (False, "arrêté depuis 2 h (code 1)"))
        self.assertEqual(machine.etat_conteneur("Up 3 minutes (Paused)"), ("en pause", True, True))

    def test_un_service_en_echec_et_les_ports_de_chacun(self):
        s = _machine()["services"]
        par = {x["unite"]: x for x in s["suivis"]}
        self.assertEqual(s["echecs"], ["php8.3-fpm"])                                             # la puce « ● » n'est pas une unité
        self.assertEqual((par["php8.3-fpm"]["etat"], par["nginx"]["etat"], par["nginx"]["ports"], par["ssh"]["ports"]), ("echec", "actif", ["80/tcp", "443/tcp"], ["22/tcp"]))
        self.assertTrue(par["ssh"]["protege"])                                                    # il ne s'arrête pas d'ici
        self.assertEqual(par["nginx"]["geste"], "nginx")                                          # recharger nginx existe déjà

    def test_une_session_dit_d_ou_elle_vient(self):
        a, b = _machine()["sessions"]
        self.assertEqual((a["utilisateur"], a["reseau"], a["anonyme"]), ("sshd", "Internet", True))                # « sshd » : personne n'est encore entré
        self.assertEqual((b["utilisateur"], b["reseau"], b["machine"], b["anonyme"]), ("lea", "Tailscale", "tel-lea", False))
        self.assertEqual(_machine()["refus"]["adresses"], [["198.51.100.7", 10], ["198.51.100.9", 6]])

    def test_un_oom_acquitte_ne_revient_pas(self):
        self.assertEqual([o["processus"] for o in _machine()["oom"]], ["php-fpm"])

    def test_une_vignette_de_voisin_n_existe_que_si_le_sujet_est_la(self):
        v = {x["cle"]: x for x in _machine()["voisins"]}
        self.assertEqual(sorted(v), ["bannies", "certs", "depots", "ports", "tailscale"])        # ni NetBird ni FastPanel sur cette machine : pas de case vide
        self.assertEqual((v["ports"]["chiffre"], v["bannies"]["chiffre"], v["certs"]["pastille"], v["tailscale"]["chiffre"]), (3, 8, ["5 j", "d"], "1 / 2"))
        self.assertEqual(v["tailscale"]["lignes"][0], "hors ligne : atlas-2")

    def test_un_logiciel_trouve_sans_module_donne_une_vignette_detectee(self):
        monde = [_l("interface.wt0", "unknown · 100.72.0.10"), _l("interface.wg0", "up · 10.8.0.1")]
        v = {x["cle"]: x for x in _machine(etat={"rows": monde, "muet": False})["voisins"]}
        self.assertEqual((v["netbird"]["etat"], v["netbird"]["preuve"]), ("detecte", "interface wt0"))             # le module NetBird n'est pas installé
        self.assertEqual(v["wireguard"]["etat"], "detecte")

    def test_une_source_muette_ne_donne_ni_zero_ni_tout_va_bien(self):
        r = _machine(etat=None, metriques=None, services=None, conteneurs=None, sessions=None, oom=None, ports=None)
        self.assertTrue(r["source"]["muet"])
        for cle in ("ressources", "services", "conteneurs", "sessions", "oom"):
            self.assertIsNone(r[cle], cle)                                                        # « inconnu », jamais une liste vide
        self.assertNotIn("ports", {x["cle"] for x in r["voisins"]})
        self.assertIsNone(r["sante"]["score"])

    def test_des_releves_figes_sont_dits(self):
        r = _machine(etat={"rows": [_l("system.hostname", "atlas")], "muet": False, "age_s": 50000, "fige": True})
        self.assertEqual((r["source"]["fige"], r["source"]["age_s"], r["source"]["muet"]), (True, 50000, False))


class PointDEvolution(unittest.TestCase):
    def test_le_point_est_declare_sans_defaut(self):
        self.assertEqual(_DEFAUTS, [])
        self.assertEqual(_SVC.points("vue"), ["vue.verdict.composer"])
        self.assertEqual(_SVC.etat("vue", "verdict.composer")["sert"], "reference")

    def test_la_reference_rejoue_son_corpus_dore_a_l_identique(self):
        """Le corpus a été produit par l'ANCIEN composer, avant sa conversion en point d'évolution : l'égalité prouve que rien n'a changé."""
        corpus = json.loads((DOSSIER / "contrats" / "CN_verdict_composer.corpus.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(corpus["cas"]), 15)
        for c in corpus["cas"]:
            e = c["entree"]
            self.assertEqual(composer(e["admin"], e["compte"], e["sources"], e["quand"]), c["sortie"], c["cas"])

    def test_la_facade_refuse_de_court_circuiter_le_noyau(self):
        with self.assertRaises(TypeError):
            _facade.composer(True, "root", sources(), "t")

    def test_une_ec_defaillante_ne_change_rien_pour_l_utilisateur(self):
        """Le disjoncteur sur un vrai point : une EC qui rend n'importe quoi est remplacée par la référence, dans le même appel."""
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        d = tmp / "vue" / "verdict.composer"
        d.mkdir(parents=True)
        corps = "def composer(entree):" + chr(10) + "    return {'niveau': 'stable'}" + chr(10)
        tete = chr(10).join(["# ZONE       : EC", "# RUNTIME    : python", "# VERSION EC : EC1  #aaaaaa", "# CONTRAT PROUVÉ : @1.0"]) + chr(10)
        (d / "EC_verdict_composer__EC1.py").write_text(tete + corps, encoding="utf-8")
        (d / "ACTIVE").write_text("EC_verdict_composer__EC1.py", encoding="utf-8")
        svc = ServicePoints(tmp)
        svc.declarer(_manifeste.charger(DOSSIER / "CN_manifeste.toml"), DOSSIER)
        svc.router("vue", "verdict.composer", "service", 100)       # sans routage posé, une EC ne sert pas : ce banc veut une EC qui sert, et qui se trompe
        sortie = _facade.composer(True, "root", sources(metriques=None), "t", appeler=lambda p, e: svc.appeler("vue", p, e))
        self.assertEqual(sortie["niveau"], "inconnu")                      # la vérité de la référence, pas le « stable » mensonger de l'EC
        self.assertEqual(svc.etat("vue", "verdict.composer")["fautes_recentes"], 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : composer, site, sources, Vue, PointDEvolution
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
