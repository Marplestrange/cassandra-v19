# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la gestion d'un serveur NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #f03b54
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de ce que le module netbird sait faire d'un serveur NetBird auto-hébergé : l'installer (par la commande root, simulée) et l'administrer par son API (simulée : un faux serveur qui répond comme lui). Rien n'est installé, aucun réseau n'est touché.
# MÉTHODE    : un vrai noyau, une fausse commande root `serveur`, une fausse API NetBird ; on vérifie les garde-fous, le secret qui ne traîne nulle part et le retour de chaque geste.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f03b54 ▼▼▼
"""Bancs de la gestion d'un serveur NetBird : commande root et API NetBird SIMULÉES, noyau réel."""
import copy
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from tests.CN_test_netbird import Monde, Echec     # noqa: E402

JETON = "nbp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
SHA = "a" * 64
CLE_COMPLETE = "11111111-2222-3333-4444-555555555555"


class FauxServeur:
    """L'API de gestion de NetBird, en mémoire : peers, setup-keys, groups, policies."""

    def __init__(self):
        self.peers = {"p1": {"id": "p1", "name": "orion", "ip": "100.92.1.6", "connected": True, "os": "Linux", "version": "0.40.0", "groups": [{"id": "g1", "name": "All"}], "last_seen": "2026-11-09T10:00:00Z",
                             "ssh_enabled": False, "login_expiration_enabled": True, "inactivity_expiration_enabled": False}}
        self.keys, self.groups, self.policies = {}, {"g1": {"id": "g1", "name": "All", "peers_count": 1, "issued": "api"}}, {}
        self.suivant = 0
        self.appels = []
        self.jeton_ok = JETON
        self.hors_ligne = False

    def id(self, p):
        self.suivant += 1
        return "%s%d" % (p, self.suivant + 1)

    def __call__(self, methode, url, jeton, corps=None, delai=15):
        self.appels.append((methode, url, jeton, copy.deepcopy(corps)))
        if self.hors_ligne:
            return None, "Connection refused"
        chemin = url.split("/api", 1)[1] if "/api" in url else url
        if chemin == "/instance":
            return 200, {"setup_required": True}
        if jeton != self.jeton_ok:
            return 401, {"message": "unauthorized", "code": 401}
        parts = [x for x in chemin.split("/") if x]
        coll, i = parts[0], (parts[1] if len(parts) > 1 else None)
        magasin = {"peers": self.peers, "setup-keys": self.keys, "groups": self.groups, "policies": self.policies}[coll]
        if methode == "GET":
            if i is None:
                return 200, copy.deepcopy(list(magasin.values()))
            return (200, copy.deepcopy(magasin[i])) if i in magasin else (404, {"message": "not found"})
        if methode == "DELETE":
            return (200, {}) if magasin.pop(i, None) is not None else (404, {"message": "not found"})
        if methode == "POST":
            n = self.id(coll[0])
            d = dict(corps, id=n)
            if coll == "setup-keys":
                d.update(key=CLE_COMPLETE, valid=True, revoked=False, used_times=0, state="valid", expires="2026-12-09T10:00:00Z")
            magasin[n] = d
            return 200, copy.deepcopy(d)
        if methode == "PUT":
            if i not in magasin:
                return 404, {"message": "not found"}
            magasin[i].update(corps)
            return 200, copy.deepcopy(magasin[i])
        return 405, {}


class Gestion(Monde):
    def setUp(self):
        super().setUp()
        self.api = FauxServeur()
        self.g["_http"] = self.api
        self.valeurs.update(url_api="https://netbird.exemple.fr", jeton_api=JETON)
        self.installe, self.conteneurs, self.occupes = False, [], []
        self.sauvegardes, self.sauvegarde_echoue, self.pf_ouverts, self.version_serveur = [], False, [], "v0.40.0"
        self.jq = True
        self.compose = True
        self.github = {"tag_name": "v0.41.0"}
        faux_netbird = self.api

        def http(methode, url, jeton, corps=None, delai=15):
            if "api.github.com" in url:
                self.urls_github.append(url)
                return (200, self.github) if self.github else (None, "Connection refused")
            return faux_netbird(methode, url, jeton, corps, delai)
        self.urls_github = []
        self.g["_http"] = http
        self.g["_VERSIONS"].update(t=0.0, val="")
        self.panneau = {"fastpanel.sites": [{"domaine": "netbird.exemple.fr"}, {"domaine": "Boutique.exemple.fr"}], "fastpanel.dns": [{"zone": "exemple.fr", "nom": "@", "type": "A", "valeur": "1.2.3.4"}, {"zone": "autre.org", "nom": "@", "type": "A", "valeur": "1.2.3.4"}]}

        def lecture(cap, **a):
            if self.panneau is None:
                raise RuntimeError("le panneau ne répond pas")
            return self.panneau.get(cap)
        self.ctx.executer_lecture = lecture
        self.g["_SERVEUR"]["meta"] = None
        racine_client = self.g["_racine"]

        def racine(verbe, args=(), entree=None, delai=30, commande="piloter"):
            if commande != "serveur":
                return racine_client(verbe, args, entree, delai)
            self.racines.append(("serveur:" + verbe, list(args), entree))
            if verbe == "etat":
                return {"ok": True, "docker": True, "jq": self.jq, "compose": self.compose, "installe": self.installe, "dossier": "/opt/netbird-serveur",
                        "meta": {"domaine": "netbird.exemple.fr", "version": self.version_serveur, "proxy": "nginx"} if self.installe else {}, "conteneurs": self.conteneurs,
                        **({} if self.installe else {"occupes": self.occupes})}
            if verbe == "telecharger":
                return {"ok": True, "version": args[0], "sha256": SHA, "taille": 1234, "url": "https://github.com/…"}
            if verbe == "installer":
                self.installe = True
                self.conteneurs = [{"service": "management", "etat": "running", "image": "netbirdio/management"}]
                return {"ok": True, "code": 0, "sortie": "fait"}
            if verbe == "commande":
                return {"ok": True, "code": 0, "sortie": "ligne de journal" if args[0] == "logs" else ""}
            if verbe == "retirer":
                self.conteneurs = []
                return {"ok": True, "code": 0, "sortie": "", "purge": bool(args)}
            if verbe == "nginx":
                return {"ok": True, "conf": "server {}"}
            if verbe == "mettre_a_jour":
                if args:
                    self.version_serveur = args[0]
                return {"ok": True, "code": 0, "sortie": "à jour"}
            if verbe == "sauvegarder":
                if self.sauvegarde_echoue:
                    return {"ok": False, "erreur": "disque plein"}
                self.sauvegardes.append("2026110%d-143200" % len(self.sauvegardes))
                return {"ok": True, "id": self.sauvegardes[-1], "raison": args[0] if args else "manuelle", "volumes": 1, "taille": 1234}
            if verbe == "sauvegardes":
                return {"ok": True, "sauvegardes": [{"id": i, "quand": "2026-11-09 14:32:00", "raison": "manuelle", "version": "v0.40.0", "taille": 1234, "volumes": 1} for i in reversed(self.sauvegardes)], "dossier": "/var/backups/cassandra/netbird", "garde": 10}
            if verbe == "restaurer":
                return {"ok": True, "code": 0, "sortie": "", "id": args[0], "securite": "20261109-999999", "volumes": 1, "images_remises": 1 if "images" in args else 0}
            if verbe == "pare_feu":
                return {"ok": True, "outil": "ufw", "actif": True, "ouverts": list(self.pf_ouverts)}
            if verbe == "pare_feu_ouvrir":
                neufs = [p for p in (["80/tcp"] if args[0] == "traefik" else []) + ["443/tcp", "3478/udp"] if p not in self.pf_ouverts]
                self.pf_ouverts += neufs
                return {"ok": True, "outil": "ufw", "ouverts_par_nous": neufs, "deja_ouverts": []}
            if verbe == "pare_feu_fermer":
                self.pf_ouverts = [p for p in self.pf_ouverts if p not in args]
                return {"ok": True, "outil": "ufw", "fermes": list(args)}
            if verbe == "installer_compose":
                self.compose = True
                return {"ok": True, "code": 0, "sortie": "", "commande": "docker-compose"}
            if verbe == "installer_jq":
                self.jq = True
                return {"ok": True, "code": 0, "sortie": "jq installé"}
            if verbe == "ip":
                return {"ok": True, "ip": "93.184.216.34", "privee": False}
            return {"ok": False, "erreur": "verbe inconnu"}
        self.g["_racine"] = racine

    def ecrire(self, cap, **a):
        return self.lire(cap, **a)

    def journal_brut(self):
        return json.dumps([dict(r) for r in self.ctx.stockage.lire("SELECT * FROM gestes")], default=str)


class Serveur(Gestion):
    def test_rien_n_est_installe_au_depart(self):
        r = self.lire("serveur_etat")
        self.assertEqual((r["disponible"], r["installe"]), (True, False))

    def test_telecharger_exige_une_version_explicite(self):
        for v in ("", "latest", "v0.40", "v0.40.0; rm -rf /"):
            with self.assertRaises(Echec):
                self.lire("serveur_telecharger", version=v)
        self.assertEqual(self.lire("serveur_telecharger", version="v0.40.0")["sha256"], SHA)

    def test_installer_refuse_ce_qui_n_est_pas_confirme(self):
        bon = dict(version="v0.40.0", sha256=SHA, domaine="netbird.exemple.fr", email="admin@exemple.fr", proxy="nginx")
        for faux in ({"sha256": "abc"}, {"domaine": "pas un domaine"}, {"email": "x"}, {"proxy": "apache"}, {"version": "latest"}):
            with self.assertRaises(Echec, msg=str(faux)):
                self.lire("serveur_installer", **dict(bon, **faux))
        self.assertFalse([x for x in self.racines if x[0] == "serveur:installer"], "refusé avant d'appeler la commande root")

    def test_installer_passe_par_la_commande_root_et_se_prouve(self):
        r = self.lire("serveur_installer", version="v0.40.0", sha256=SHA, domaine="Netbird.Exemple.fr", email="admin@exemple.fr", proxy="nginx")
        self.assertTrue(r["installe"])
        verbe = [x for x in self.racines if x[0] == "serveur:installer"][0]
        self.assertEqual(verbe[1], ["v0.40.0", SHA, "netbird.exemple.fr", "admin@exemple.fr", "nginx"])
        self.assertEqual(self.lire("journal")["gestes"][0]["libelle"], "Serveur NetBird installé (netbird.exemple.fr, nginx)")

    def installer(self, domaine):
        return self.lire("serveur_installer", version="v0.40.0", sha256=SHA, domaine=domaine, email="admin@exemple.fr", proxy="nginx")

    def test_un_site_du_panneau_est_un_domaine_administre(self):
        self.assertTrue(self.installer("netbird.exemple.fr")["installe"])

    def test_un_nom_de_la_zone_dns_du_panneau_est_administre(self):
        self.assertTrue(self.installer("vpn.exemple.fr")["installe"], "sous-domaine d'une zone que le panneau héberge")

    def test_un_domaine_que_cassandra_n_administre_pas_est_refuse(self):
        with self.assertRaises(Echec) as q:
            self.installer("netbird.inconnu.net")
        self.assertIn("n'administre", str(q.exception))
        self.assertFalse([x for x in self.racines if x[0] == "serveur:installer"], "refusé avant la commande root")

    def test_un_domaine_hors_cassandra_se_declare_expressement(self):
        r = self.lire("serveur_installer", version="v0.40.0", sha256=SHA, domaine="netbird.inconnu.net", email="admin@exemple.fr", proxy="nginx", hors_cassandra=True)
        self.assertTrue(r["installe"] and r["domaine_hors_cassandra"])
        self.assertIn("domaine hors Cassandra", self.lire("journal")["gestes"][0]["libelle"])

    def test_la_case_hors_cassandra_ne_change_rien_pour_un_domaine_administre(self):
        r = self.installer_hors("netbird.exemple.fr")
        self.assertFalse(r["domaine_hors_cassandra"])

    def installer_hors(self, domaine):
        return self.lire("serveur_installer", version="v0.40.0", sha256=SHA, domaine=domaine, email="admin@exemple.fr", proxy="nginx", hors_cassandra=True)

    def test_un_domaine_hors_cassandra_reste_valide_comme_un_nom(self):
        for d in ("pas un domaine", "../x", "a..b"):
            with self.assertRaises(Echec, msg=d):
                self.installer_hors(d)

    def test_ports_avant_installation_selon_le_proxy(self):
        self.occupes = ["tcp/443", "tcp/8081"]
        r = self.lire("serveur_ports", proxy="nginx")
        etat = {"%s/%d" % (p["proto"], p["port"]): p["etat"] for p in r["ports"]}
        self.assertEqual((etat["tcp/443"], etat["tcp/8081"], etat["udp/3478"], etat["tcp/8080"]), ("pris_par_proxy", "occupe", "libre", "libre"))
        self.assertNotIn("tcp/80", etat, "nginx n'a pas besoin du port 80 de NetBird")
        t = self.lire("serveur_ports", proxy="traefik")
        self.assertEqual({"%s/%d" % (p["proto"], p["port"]) for p in t["ports"]}, {"tcp/80", "tcp/443", "udp/3478"})

    def test_ports_reels_une_fois_installe(self):
        self.installe = True
        self.conteneurs = [{"service": "netbird-server", "etat": "running", "image": "x", "ports": ["127.0.0.1:8081->80/tcp"]}, {"service": "coturn", "etat": "running", "image": "y", "ports": []}]
        r = self.lire("serveur_ports")
        self.assertEqual((r["installe"], r["proxy"], r["reels"]), (True, "nginx", [{"service": "netbird-server", "ports": ["127.0.0.1:8081->80/tcp"]}]))
        self.assertTrue(all(p["etat"] == "inconnu" for p in r["ports"]), "installé : l'occupation n'est plus un obstacle")

    def test_ports_proxy_inconnu_refuse(self):
        with self.assertRaises(Echec):
            self.lire("serveur_ports", proxy="apache")

    def test_un_nom_qui_finit_comme_une_zone_sans_en_etre_une_est_refuse(self):
        with self.assertRaises(Echec):
            self.installer("netbird.mauvaisexemple.fr")

    def test_panneau_muet_on_ne_devine_pas(self):
        self.panneau = None
        with self.assertRaises(Echec) as q:
            self.installer("netbird.exemple.fr")
        self.assertIn("ne répond pas", str(q.exception))

    def test_le_reglage_domaine_libre_autorise_un_domaine_non_administre(self):
        self.valeurs["domaine_libre"] = True
        self.assertTrue(self.installer("netbird.inconnu.net")["installe"])

    def test_la_liste_propose_les_sites_et_un_sous_domaine_par_zone(self):
        r = self.lire("serveur_domaines")
        self.assertEqual((r["disponible"], r["administre"]), (True, None))
        self.assertIn("netbird.exemple.fr", r["propositions"])
        self.assertIn("netbird.autre.org", r["propositions"])
        self.assertEqual(r["zones"], ["autre.org", "exemple.fr"])

    def test_la_liste_dit_pourquoi_un_domaine_est_administre_ou_non(self):
        self.assertEqual(self.lire("serveur_domaines", domaine="vpn.exemple.fr")["par"], "zone DNS « exemple.fr » hébergée par le panneau")
        self.assertEqual(self.lire("serveur_domaines", domaine="boutique.exemple.fr")["par"], "site du panneau")
        r = self.lire("serveur_domaines", domaine="x.net")
        self.assertEqual((r["administre"], bool(r["raison"])), (False, True))

    def test_journaux_redemarrage_mise_a_jour_nginx(self):
        self.installe = True
        self.assertEqual(self.lire("serveur_journaux")["journaux"], "ligne de journal")
        self.lire("serveur_redemarrer")
        self.assertIn(("serveur:commande", ["restart"], None), self.racines)
        self.assertIn("à jour", self.lire("serveur_mettre_a_jour")["mise_a_jour"])
        self.assertEqual(self.lire("serveur_nginx")["conf"], "server {}")

    def test_retirer_dit_ce_qui_est_perdu(self):
        self.installe, self.conteneurs = True, [{"service": "management", "etat": "running", "image": "x"}]
        self.lire("serveur_retirer", purger=True)
        self.assertIn(("serveur:retirer", ["purger"], None), self.racines)
        self.assertIn("comptes et machines perdus", self.lire("journal")["gestes"][0]["libelle"])

    def test_retirer_rend_ce_que_la_commande_root_a_fait(self):
        self.installe, self.conteneurs = True, [{"service": "management", "etat": "running", "image": "x"}]
        racine = self.g["_racine"]

        def avec_avertissement(verbe, args=(), entree=None, delai=30, commande="piloter"):
            if commande == "serveur" and verbe == "retirer":
                self.conteneurs = []
                return {"ok": True, "code": 0, "sortie": "", "purge": True, "avertissement": "le dossier n'a pas pu être effacé"}
            return racine(verbe, args, entree, delai, commande)
        self.g["_racine"] = avec_avertissement
        r = self.lire("serveur_retirer")                                            # sans « purger » : la commande a purgé quand même (installation inachevée)
        self.assertTrue(r["purge"])
        self.assertIn("pas pu être effacé", r["avertissement"])

    def test_retirer_sans_serveur_est_refuse(self):
        with self.assertRaises(Echec):
            self.lire("serveur_retirer")

    def test_sans_la_commande_root_le_module_le_dit(self):
        self.g["_racine"] = lambda *a, **k: {"ok": False, "erreur": "commande absente"}
        self.assertFalse(self.lire("serveur_etat")["disponible"])
        with self.assertRaises(Echec) as q:
            self.lire("serveur_redemarrer")
        self.assertIn("commande absente", str(q.exception))


class Maintenance(Gestion):
    def setUp(self):
        super().setUp()
        self.installe, self.conteneurs = True, [{"service": "management", "etat": "running", "image": "x"}]

    def test_installer_compose_depuis_l_ecran_est_prouve_et_journalise(self):
        self.compose = False
        self.assertFalse(self.lire("serveur_etat")["compose"])
        r = self.lire("serveur_installer_compose")
        self.assertTrue(r["compose_installe"] and r["compose"])
        self.assertIn(("serveur:installer_compose", [], None), self.racines)
        self.assertIn("Docker Compose installé (docker-compose)", self.lire("journal")["gestes"][0]["libelle"])

    def test_installer_jq_depuis_l_ecran_est_prouve_et_journalise(self):
        self.jq = False
        self.assertFalse(self.lire("serveur_etat")["jq"])
        r = self.lire("serveur_installer_jq")
        self.assertTrue(r["jq_installe"] and r["jq"])
        self.assertIn(("serveur:installer_jq", [], None), self.racines)
        self.assertIn("jq installé", self.lire("journal")["gestes"][0]["libelle"])

    def test_la_derniere_version_est_lue_chez_github_et_gardee_une_heure(self):
        r = self.lire("versions")
        self.assertEqual((r["derniere"], r["serveur"], r["serveur_a_jour"], r["erreur"]), ("v0.41.0", "v0.40.0", False, ""))
        self.lire("versions")
        self.assertEqual(len(self.urls_github), 1, "une seule demande : GitHub limite les appels sans compte")
        self.assertEqual(self.urls_github[0], "https://api.github.com/repos/netbirdio/netbird/releases/latest")

    def test_a_jour_inconnu_et_github_muet(self):
        self.github = {"tag_name": "v0.40.0"}
        self.assertTrue(self.lire("versions")["serveur_a_jour"])
        self.g["_VERSIONS"].update(t=0.0, val="")
        self.github = None
        r = self.lire("versions")
        self.assertEqual((r["derniere"], r["serveur_a_jour"], r["client_a_jour"]), ("", None, None), "on ne sait pas : ni oui ni non")
        self.assertIn("GitHub ne répond pas", r["erreur"])
        self.github = {"tag_name": "pas-une-version"}
        self.assertEqual(self.lire("versions")["derniere"], "", "une réponse illisible n'est pas retenue")

    def test_github_muet_apres_une_reponse_rend_la_derniere_connue(self):
        self.lire("versions")
        self.g["_VERSIONS"]["t"] = 0.0
        self.github = None
        r = self.lire("versions")
        self.assertEqual(r["derniere"], "v0.41.0")
        self.assertIn("GitHub", r["erreur"])

    def test_mettre_a_jour_sauvegarde_d_abord_puis_se_defait_par_la_restauration(self):
        r = self.lire("serveur_mettre_a_jour")
        verbes = [x[0] for x in self.racines if x[0] in ("serveur:sauvegarder", "serveur:mettre_a_jour")]
        self.assertEqual(verbes, ["serveur:sauvegarder", "serveur:mettre_a_jour"], "la copie est faite AVANT")
        self.assertIn(("serveur:sauvegarder", ["avant_maj"], None), self.racines)
        self.assertIn(("serveur:mettre_a_jour", ["v0.41.0"], None), self.racines, "la version qu'on installe est celle de la dernière publication")
        self.assertEqual((r["version_avant"], r["version_apres"]), ("v0.40.0", "v0.41.0"))
        g = self.lire("journal")["gestes"][0]
        self.assertEqual(g["libelle"], "Serveur NetBird mis à jour : v0.40.0 → v0.41.0 (sauvegarde %s)" % r["sauvegarde"])
        self.assertTrue(g["defaisable"])
        self.lire("defaire_geste", id=g["id"])
        self.assertIn(("serveur:restaurer", [r["sauvegarde"], "images"], None), self.racines, "les données, la config ET les images d'avant")

    def test_une_mise_a_jour_sans_sauvegarde_ne_se_defait_pas(self):
        self.lire("serveur_mettre_a_jour", sauvegarde=False)
        self.assertFalse([x for x in self.racines if x[0] == "serveur:sauvegarder"])
        g = self.lire("journal")["gestes"][0]
        self.assertFalse(g["defaisable"])
        self.assertIn("sans sauvegarde", g["libelle"])
        with self.assertRaises(Echec) as q:
            self.lire("defaire_geste", id=g["id"])
        self.assertIn("rien n'a été gardé", str(q.exception))

    def test_une_sauvegarde_qui_echoue_arrete_la_mise_a_jour(self):
        self.sauvegarde_echoue = True
        with self.assertRaises(Echec) as q:
            self.lire("serveur_mettre_a_jour")
        self.assertIn("disque plein", str(q.exception))
        self.assertFalse([x for x in self.racines if x[0] == "serveur:mettre_a_jour"], "pas de mise à jour sans la copie promise")

    def test_purger_sauvegarde_d_abord_et_sans_copie_ne_purge_pas(self):
        r = self.lire("serveur_retirer", purger=True)
        self.assertEqual([x[0] for x in self.racines if x[0] in ("serveur:sauvegarder", "serveur:retirer")], ["serveur:sauvegarder", "serveur:retirer"])
        self.assertIn(("serveur:sauvegarder", ["avant_retrait"], None), self.racines)
        self.assertTrue(r["sauvegarde"])
        self.assertIn("sauvegarde " + r["sauvegarde"], self.lire("journal")["gestes"][0]["libelle"])
        self.installe, self.conteneurs = True, [{"service": "management", "etat": "running", "image": "x"}]
        self.sauvegarde_echoue = True
        self.racines.clear()
        with self.assertRaises(Echec):
            self.lire("serveur_retirer", purger=True)
        self.assertFalse([x for x in self.racines if x[0] == "serveur:retirer"], "les données ne sont pas détruites sans copie")
        self.sauvegarde_echoue = False
        self.racines.clear()
        self.lire("serveur_retirer")                                                           # sans purge : rien à sauvegarder, les données restent
        self.assertFalse([x for x in self.racines if x[0] == "serveur:sauvegarder"])

    def test_sauvegarder_lister_restaurer(self):
        a = self.lire("serveur_sauvegarder")
        self.assertIn(("serveur:sauvegarder", ["manuelle"], None), self.racines)
        liste = self.lire("serveur_sauvegardes")
        self.assertEqual((liste["sauvegardes"][0]["id"], liste["garde"]), (a["id"], 10))
        r = self.lire("serveur_restaurer", id=a["id"])
        self.assertEqual((r["restauree"], r["securite"]), (a["id"], "20261109-999999"))
        g = self.lire("journal")["gestes"][0]
        self.assertTrue(g["defaisable"])
        self.lire("defaire_geste", id=g["id"])
        self.assertIn(("serveur:restaurer", ["20261109-999999"], None), self.racines, "défaire une restauration remet ce qui était là avant")

    def test_restaurer_refuse_un_identifiant_suspect(self):
        for mauvais in ("", "../x", "20261109", "20261109-143200;ls", 5):
            with self.assertRaises(Echec, msg=mauvais):
                self.lire("serveur_restaurer", id=mauvais)
        self.assertFalse([x for x in self.racines if x[0] == "serveur:restaurer"])

    def test_pare_feu_etat_ouvrir_et_defaire_ne_ferme_que_ce_qu_on_a_ouvert(self):
        self.pf_ouverts = ["443/tcp"]
        e = self.lire("pare_feu_etat")
        self.assertEqual((e["outil"], e["publics"], e["ouverts"], e["proxy"]), ("ufw", ["443/tcp", "3478/udp"], ["443/tcp"], "nginx"))
        r = self.lire("pare_feu_ouvrir")
        self.assertEqual(r["ouverts_par_nous"], ["3478/udp"])
        g = self.lire("journal")["gestes"][0]
        self.assertIn("3478/udp", g["libelle"])
        self.lire("defaire_geste", id=g["id"])
        self.assertIn(("serveur:pare_feu_fermer", ["3478/udp"], None), self.racines)
        self.assertEqual(self.pf_ouverts, ["443/tcp"], "le 443, déjà ouvert avant nous, reste ouvert")

    def test_ouvrir_sans_rien_de_neuf_n_a_rien_a_defaire(self):
        self.pf_ouverts = ["443/tcp", "3478/udp"]
        self.lire("pare_feu_ouvrir")
        self.assertFalse(self.lire("journal")["gestes"][0]["defaisable"])

    def test_l_adresse_de_la_machine_et_la_verification_du_dns(self):
        self.assertEqual(self.lire("serveur_ip")["ip"], "93.184.216.34")
        self.g["_resoudre"] = lambda nom: [(2, 1, 6, "", ("93.184.216.34", 0))]
        r = self.lire("serveur_dns_verifier", domaine="Netbird.Exemple.fr", ip="93.184.216.34")
        self.assertEqual((r["domaine"], r["adresses"], r["resolu"], r["correspond"]), ("netbird.exemple.fr", ["93.184.216.34"], True, True))
        self.assertFalse(self.lire("serveur_dns_verifier", domaine="netbird.exemple.fr", ip="10.0.0.1")["correspond"])
        def muet(nom):
            raise OSError("pas de résolution")
        self.g["_resoudre"] = muet
        r = self.lire("serveur_dns_verifier", domaine="netbird.exemple.fr")
        self.assertEqual((r["adresses"], r["resolu"], r["correspond"]), ([], False, False))
        with self.assertRaises(Echec):
            self.lire("serveur_dns_verifier", domaine="pas un domaine")

    def test_ces_gestes_demandent_le_droit_serveur_et_l_installation_native_le_droit_administrer(self):
        manifeste = (RACINE / "modules" / "netbird" / "CN_manifeste.toml").read_text(encoding="utf-8")
        import tomllib
        m = tomllib.loads(manifeste.split("# ▼▼▼ BORNE CN", 1)[1].split("\n", 1)[1])
        droits = {c["id"]: c["droit"] for c in m["capacites"]}
        for cap in ("serveur_sauvegarder", "serveur_sauvegardes", "serveur_restaurer", "pare_feu_etat", "pare_feu_ouvrir", "serveur_ip", "serveur_dns_verifier"):
            self.assertEqual(droits[cap], "serveur", cap)
        for cap in ("installer_natif", "retirer_natif"):
            self.assertEqual(droits[cap], "administrer", cap)
        self.assertEqual(droits["versions"], "utiliser", "lire la dernière version ne demande aucun droit particulier")


class Administration(Gestion):

    def test_sans_jeton_rien_ne_part(self):
        self.valeurs["jeton_api"] = ""
        with self.assertRaises(Echec) as q:
            self.lire("api_machines")
        self.assertIn("jeton", str(q.exception))
        self.assertFalse(self.api.appels)

    def test_le_jeton_refuse_est_dit_sans_le_repeter(self):
        self.api.jeton_ok = "autre"
        with self.assertRaises(Echec) as q:
            self.lire("api_machines")
        self.assertIn("refuse le jeton", str(q.exception))
        self.assertNotIn(JETON, str(q.exception))

    def test_l_adresse_doit_etre_https_ou_locale(self):
        for url in ("http://netbird.exemple.fr", "ftp://x", "https://a b", "file:///etc/passwd", "https://user:pw@h.fr"):
            self.valeurs["url_api"] = url
            with self.assertRaises(Echec, msg=url):
                self.lire("api_machines")
        self.assertFalse(self.api.appels, "le jeton n'a été envoyé nulle part")
        self.valeurs["url_api"] = "http://127.0.0.1:33073"
        self.assertEqual(len(self.lire("api_machines")["machines"]), 1)

    def test_le_jeton_ne_suit_jamais_une_redirection(self):
        redir = self.g["_SansRedirection"]()
        self.assertIsNone(redir.redirect_request(None, None, 302, "Found", {}, "https://ailleurs.fr"))

    def test_serveur_hors_ligne(self):
        self.api.hors_ligne = True
        with self.assertRaises(Echec) as q:
            self.lire("api_groupes")
        self.assertIn("ne répond pas", str(q.exception))

    def test_machines_listees(self):
        m = self.lire("api_machines")["machines"][0]
        self.assertEqual((m["nom"], m["ip"], m["connecte"], m["groupes"]), ("orion", "100.92.1.6", True, ["All"]))
        self.assertTrue(all(a[2] == JETON for a in self.api.appels))

    def test_verifier_compte_les_machines(self):
        self.assertEqual(self.lire("api_verifier")["machines"], 1)

    def test_machine_modifier_puis_defaire(self):
        r = self.lire("machine_modifier", id="p1", nom="orion-bureau", ssh=True)
        self.assertEqual((r["avant"]["name"], r["apres"]["name"], r["apres"]["ssh_enabled"]), ("orion", "orion-bureau", True))
        g = self.lire("journal")["gestes"][0]
        self.assertTrue(g["defaisable"])
        self.lire("defaire_geste", id=g["id"])
        self.assertEqual((self.api.peers["p1"]["name"], self.api.peers["p1"]["ssh_enabled"]), ("orion", False))

    def test_identifiants_et_noms_mal_formes_refuses(self):
        for kw in ({"id": "../etc"}, {"id": ""}, {"id": "p1", "nom": "a b;c"}):
            with self.assertRaises(Echec, msg=str(kw)):
                self.lire("machine_modifier", **kw)

    def test_machine_supprimer(self):
        self.assertEqual(self.lire("machine_supprimer", id="p1")["nom"], "orion")
        self.assertEqual(self.api.peers, {})
        with self.assertRaises(Echec):
            self.lire("machine_supprimer", id="p1")

    def test_cle_creee_la_cle_complete_n_est_rendue_qu_une_fois_et_jamais_gardee(self):
        r = self.lire("cle_creer", nom="portable", type="one-off", jours=7, groupes=["g1"])
        self.assertEqual(r["cle_secrete"], CLE_COMPLETE)
        corps = [a for a in self.api.appels if a[0] == "POST"][0][3]
        self.assertEqual((corps["expires_in"], corps["auto_groups"], corps["type"]), (7 * 86400, ["g1"], "one-off"))
        self.assertNotIn(CLE_COMPLETE, self.journal_brut(), "la clé complète ne va pas au journal du module")
        lues = self.lire("api_cles")["cles"]
        self.assertEqual(lues[0]["nom"], "portable")
        self.assertNotIn(CLE_COMPLETE, json.dumps(lues))
        self.assertNotIn("cle_secrete", json.dumps(self.lire("journal")))

    def test_cle_validations(self):
        for kw in ({"nom": ""}, {"nom": "x", "type": "autre"}, {"nom": "x", "jours": 0}, {"nom": "x", "jours": 999}, {"nom": "x", "limite": -1}, {"nom": "x", "jours": "abc"}, {"nom": "x", "groupes": ["a;b"]}):
            with self.assertRaises(Echec, msg=str(kw)):
                self.lire("cle_creer", **kw)
        self.assertFalse([a for a in self.api.appels if a[0] == "POST"])

    def test_cle_defaire_la_creation(self):
        self.lire("cle_creer", nom="temp")
        self.lire("defaire_geste", id=self.lire("journal")["gestes"][0]["id"])
        self.assertEqual(self.api.keys, {})

    def test_cle_revoquer_puis_retablir(self):
        i = self.lire("cle_creer", nom="k")["id"]
        self.lire("cle_revoquer", id=i)
        self.assertTrue(self.api.keys[i]["revoked"])
        self.lire("defaire_geste", id=self.lire("journal")["gestes"][0]["id"])
        self.assertFalse(self.api.keys[i]["revoked"])

    def test_cle_supprimer_et_inconnue(self):
        i = self.lire("cle_creer", nom="k")["id"]
        self.lire("cle_supprimer", id=i)
        self.assertEqual(self.api.keys, {})
        with self.assertRaises(Echec):
            self.lire("cle_supprimer", id=i)

    def test_groupe_creer_defaire_et_supprimer(self):
        i = self.lire("groupe_creer", nom="serveurs")["id"]
        self.assertIn(i, self.api.groups)
        self.lire("defaire_geste", id=self.lire("journal")["gestes"][0]["id"])
        self.assertNotIn(i, self.api.groups)
        with self.assertRaises(Echec):
            self.lire("groupe_supprimer", id=i)

    def test_politique_creer_activer_desactiver_supprimer(self):
        i = self.lire("politique_creer", nom="ssh admin", sources="g1", destinations=["g1"], protocole="tcp")["id"]
        regle = self.api.policies[i]["rules"][0]
        self.assertEqual((regle["protocol"], regle["sources"], regle["action"], self.api.policies[i]["enabled"]), ("tcp", ["g1"], "accept", True))
        self.lire("politique_activer", id=i, actif=False)
        self.assertFalse(self.api.policies[i]["enabled"])
        self.lire("defaire_geste", id=self.lire("journal")["gestes"][0]["id"])
        self.assertTrue(self.api.policies[i]["enabled"])
        self.lire("politique_supprimer", id=i)
        self.assertEqual(self.api.policies, {})

    def test_politique_sans_source_ou_protocole_inconnu_refusee(self):
        for kw in ({"nom": "x", "sources": "", "destinations": "g1"}, {"nom": "x", "sources": "g1", "destinations": "g1", "protocole": "gre"}, {"nom": "x", "sources": "g1", "destinations": "g1", "action": "peut-etre"}):
            with self.assertRaises(Echec, msg=str(kw)):
                self.lire("politique_creer", **kw)

    def test_le_jeton_n_est_dans_aucun_resultat_ni_journal(self):
        self.lire("machine_modifier", id="p1", nom="x1")
        self.lire("cle_creer", nom="k")
        self.assertNotIn(JETON, self.journal_brut())
        self.assertNotIn(JETON, json.dumps(self.lire("journal")))

    def test_les_gestes_de_l_api_demandent_le_droit_serveur(self):
        manifeste = (RACINE / "modules" / "netbird" / "CN_manifeste.toml").read_text(encoding="utf-8")
        import tomllib
        m = tomllib.loads(manifeste.split("# ▼▼▼ BORNE CN", 1)[1].split("\n", 1)[1])
        droits = {c["id"]: c["droit"] for c in m["capacites"]}
        for cap in [c for c in droits if c.startswith(("serveur_", "api_", "machine_", "cle_", "groupe_", "politique_"))]:
            self.assertEqual(droits[cap], "serveur", cap)
        self.assertEqual(droits["connecter"], "administrer", "le client garde son droit")
        masques = {c["id"]: c.get("masque") for c in m["capacites"]}
        self.assertEqual(masques["cle_creer"], ["cle_secrete"])

    def test_les_menus_separent_le_client_du_serveur(self):
        # « Installation » et « Serveur » prêtaient à confusion : le client rejoint un réseau, le serveur en héberge un.
        manifeste = (RACINE / "modules" / "netbird" / "CN_manifeste.toml").read_text(encoding="utf-8")
        import tomllib
        m = tomllib.loads(manifeste.split("# ▼▼▼ BORNE CN", 1)[1].split("\n", 1)[1])
        for rubrique in ("menus", "ecrans"):
            noms = {x["id"]: x["libelle"] for x in m[rubrique] if x["id"].startswith("n_")}
            self.assertEqual(noms["n_installation"], "Client", rubrique)
            self.assertEqual(noms["n_serveur"], "Serveur", rubrique)
            self.assertEqual(noms["n_gestion"], "Administration", rubrique)
        droits = {x["id"]: x.get("droit") for x in m["menus"]}
        self.assertEqual(droits["n_installation"], "utiliser", "le client ne demande pas le droit serveur")
        self.assertEqual(droits["n_serveur"], "serveur")
        self.assertEqual(droits["n_gestion"], "serveur")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/netbird/CN_module.py, tests/CN_test_netbird.py (le faux monde réutilisé)
