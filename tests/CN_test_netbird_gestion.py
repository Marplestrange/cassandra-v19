# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la gestion d'un serveur NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de ce que le module netbird sait faire d'un serveur NetBird auto-hébergé : l'installer (par la commande root, simulée) et l'administrer par son API (simulée : un faux serveur qui répond comme lui). Rien n'est installé, aucun réseau n'est touché.
# MÉTHODE    : un vrai noyau, une fausse commande root `serveur`, une fausse API NetBird ; on vérifie les garde-fous, le secret qui ne traîne nulle part et le retour de chaque geste.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
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
        self.installe, self.conteneurs = False, []
        self.g["_SERVEUR"]["meta"] = None
        racine_client = self.g["_racine"]

        def racine(verbe, args=(), entree=None, delai=30, commande="piloter"):
            if commande != "serveur":
                return racine_client(verbe, args, entree, delai)
            self.racines.append(("serveur:" + verbe, list(args), entree))
            if verbe == "etat":
                return {"ok": True, "docker": True, "jq": True, "installe": self.installe, "dossier": "/opt/netbird-serveur",
                        "meta": {"domaine": "netbird.exemple.fr", "version": "v0.40.0", "proxy": "nginx"} if self.installe else {}, "conteneurs": self.conteneurs}
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
                return {"ok": True, "code": 0, "sortie": "à jour"}
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

    def test_retirer_sans_serveur_est_refuse(self):
        with self.assertRaises(Echec):
            self.lire("serveur_retirer")

    def test_sans_la_commande_root_le_module_le_dit(self):
        self.g["_racine"] = lambda *a, **k: {"ok": False, "erreur": "commande absente"}
        self.assertFalse(self.lire("serveur_etat")["disponible"])
        with self.assertRaises(Echec) as q:
            self.lire("serveur_redemarrer")
        self.assertIn("commande absente", str(q.exception))


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


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/netbird/CN_module.py, tests/CN_test_netbird.py (le faux monde réutilisé)
