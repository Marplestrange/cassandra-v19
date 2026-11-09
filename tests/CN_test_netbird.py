# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module netbird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #8c1b2b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module netbird : le client NetBird, Docker et le courtier sont SIMULÉS (un faux monde qui répond comme eux), le reste tourne dans un vrai noyau. On vérifie les états, la voie choisie (natif direct, natif par le courtier, conteneur)
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8c1b2b ▼▼▼
"""Bancs du module netbird : le client NetBird, Docker et le courtier sont SIMULÉS (un faux monde qui répond comme eux), le reste tourne dans un vrai noyau.
On vérifie les états, la voie choisie (natif direct, natif par le courtier, conteneur), la clé qui ne traîne nulle part, l'installation et le retrait du conteneur, le journal et le retour."""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

CLE = "ABCDEF12-3456-7890-ABCD-EF1234567890"


class Echec(Exception):
    pass


def statut(brut="Connected", **plus):
    d = {"daemonStatus": brut, "fqdn": "argos.netbird.cloud", "netbirdIp": "100.92.1.5/16", "daemonVersion": "0.40.0", "cliVersion": "0.40.0", "profileName": "default", "usesKernelInterface": True,
         "management": {"url": "https://api.netbird.io:443", "connected": True, "error": ""}, "signal": {"url": "https://signal.netbird.io:443", "connected": True, "error": ""},
         "relays": {"total": 2, "available": 1, "details": []}, "networks": ["192.168.1.0/24"], "dnsServers": [{"servers": ["100.92.0.1:53"], "domains": ["netbird.cloud"], "enabled": True, "error": ""}],
         "sshServer": {"enabled": False, "sessions": []}, "peers": {"total": 0, "connected": 0, "details": []}}
    d.update(plus)
    return d


CONNECTE = statut(peers={"total": 2, "connected": 1, "details": [
    {"fqdn": "hermes.netbird.cloud", "netbirdIp": "100.92.1.7", "status": "Disconnected", "connectionType": "", "lastStatusUpdate": "0001-01-01T00:00:00Z", "latency": 0, "networks": []},
    {"fqdn": "orion.netbird.cloud", "netbirdIp": "100.92.1.6", "status": "Connected", "connectionType": "P2P", "latency": 12000000, "transferReceived": 100, "transferSent": 50,
     "lastStatusUpdate": "2026-11-09T10:00:00Z", "networks": ["10.0.0.0/24"], "relayAddress": "", "quantumResistance": False}]})


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "netbird", mods / "netbird", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("netbird", installe=True, actif=False, par="test")
        self.assertTrue(self.n.activer("netbird")["ok"])
        self.e = self.n.executeur.executer
        self.ctx = self.n.executeur.contextes["netbird"]
        self.g = self.n.catalogue.get("netbird.etat").faire.__globals__
        self.valeurs = {"conteneur": "netbird", "mode": "auto"}
        self.ctx.reglage = lambda nom, defaut="": self.valeurs.get(nom, defaut)
        self.g["_TTL"] = 0
        self.g["_direct"] = self.faux_direct
        self.g["_racine"] = self.faux_racine
        self.g["time"] = types.SimpleNamespace(time=__import__("time").time, sleep=lambda s: None)
        self.g["_MODE"].update(t=0.0, val=None)
        self.g["_SSO"].update(lien="", t=0.0)
        self.directs, self.racines = [], []
        self.natif = True                    # le client est installé sur la machine
        self.droit_natif = True              # le noyau a le droit de lui parler
        self.docker = True
        self.conteneur = "absent"            # absent | arrete | en_marche | autre
        self.etat = statut("Idle")
        self.courtier = True
        self.refus = {}                      # (verbe ou premier argument) -> (code, sortie)
        self.maj_change = True               # la mise à jour du conteneur a trouvé une image plus récente
        self.maj_echoue = False

    # ---- le faux monde
    def cli(self, args, entree=None):
        """Ce que répond le client NetBird, où qu'il tourne."""
        self.dernier_cli = (list(args), entree)
        premier = args[0]
        if premier in self.refus:
            return self.refus[premier]
        if args[:2] == ["status", "--json"]:
            return 0, json.dumps(self.etat)
        if premier == "version":
            return 0, "0.40.0"
        if premier == "up":
            self.etat = statut("Connected")
            return 0, "Connected"
        if premier == "down":
            self.etat = statut("Idle")
            return 0, ""
        return 0, ""

    def faux_direct(self, args, delai=15):
        self.directs.append(list(args))
        if not self.natif:
            return None, "absent"
        if not self.droit_natif:
            return 1, "Error: rpc error: connect: permission denied"
        return self.cli(args)

    def faux_racine(self, verbe, args=(), entree=None, delai=30):
        self.racines.append((verbe, list(args), entree))
        if not self.courtier:
            return {"ok": False, "erreur": "commande absente", "courtier": False}
        if verbe == "etat":
            return {"ok": True, "natif": self.natif, "docker": self.docker, "conteneur": self.conteneur, "image": "netbirdio/netbird:latest" if self.conteneur != "absent" else ""}
        if verbe == "cli":
            if args[0] == "natif" and not self.natif:
                return {"ok": False, "erreur": "le client NetBird n'est pas installé sur cette machine"}
            code, sortie = self.cli(args[3:], entree)
            return {"ok": code == 0, "code": code, "sortie": sortie}
        if verbe == "sso":
            self.etat = statut("NeedsLogin")
            return {"ok": True, "lien": "https://login.netbird.io/device?user_code=ABCD-EFGH", "pid": 4242}
        if verbe == "sso_annuler":
            self.etat = statut("Idle")
            return {"ok": True, "code": 0, "sortie": ""}
        if verbe == "docker_installer":
            if not self.docker:
                return {"ok": False, "erreur": "Docker n'est pas installé sur cette machine"}
            self.conteneur = "en_marche"
            self.etat = statut("Connected") if entree else statut("NeedsLogin")
            return {"ok": True, "code": 0, "sortie": "abc123"}
        if verbe == "docker_maj":
            if self.conteneur not in ("en_marche", "arrete"):
                return {"ok": False, "erreur": "le conteneur n'existe pas"}
            if self.maj_echoue:
                return {"ok": False, "code": 1, "sortie": "pull access denied"}
            self.conteneur = "en_marche"
            return {"ok": True, "change": self.maj_change, "code": 0, "sortie": ""}
        if verbe == "docker_retirer":
            self.conteneur = "absent"
            return {"ok": True, "code": 0, "sortie": ""}
        return {"ok": False, "erreur": "verbe inconnu"}

    def lire(self, cap, **a):
        r = self.e("netbird." + cap, "humain", a, compte="")
        if r.get("statut") != "faite":
            raise Echec(r.get("erreur") or r.get("raison") or str(r))
        return r["resultat"]

    def appels_cli(self, *debut):
        return [r for r in self.racines if r[0] == "cli" and tuple(r[1][3:3 + len(debut)]) == debut] + [d for d in self.directs if tuple(d[:len(debut)]) == debut]


class Etats(Monde):
    def test_connecte_et_les_machines_du_reseau(self):
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["mode"], r["nom"], r["ip"], r["version"]), ("connecte", "natif_direct", "argos", "100.92.1.5", "0.40.0"))
        self.assertEqual([p["nom"] for p in r["pairs"]], ["orion", "hermes"], "en ligne d'abord")
        orion, hermes = r["pairs"]
        self.assertEqual((orion["chemin"], orion["ms"], orion["octets"], orion["vu"], orion["reseaux"]), ("direct", 12.0, 150, "2026-11-09 10:00", ["10.0.0.0/24"]))
        self.assertEqual((hermes["en_ligne"], hermes["vu"], hermes["ms"]), (False, "", None))
        self.assertEqual((r["en_ligne"], r["relais_dispo"], r["relais_total"], r["gestion"]["connecte"], r["reseaux"]), (1, 1, 2, True, ["192.168.1.0/24"]))

    def test_les_etats_du_demon_sont_distincts(self):
        for brut, attendu in (("Connected", "connecte"), ("Connecting", "demarrage"), ("Idle", "deconnecte"), ("NeedsLogin", "a_identifier"), ("LoginFailed", "echec_connexion"),
                              ("SessionExpired", "session_expiree"), ("Inedit", "inconnu")):
            self.etat = statut(brut)
            self.assertEqual(self.lire("etat")["etat"], attendu, brut)

    def test_un_avertissement_du_client_ne_fait_pas_croire_que_le_demon_est_arrete(self):
        orig = self.cli
        self.cli = lambda args, entree=None: (0, "Warning: client 0.39 != daemon 0.40\n" + json.dumps(CONNECTE) + "\nautre avertissement") if args[:2] == ["status", "--json"] else orig(args, entree)
        self.assertEqual(self.lire("etat")["etat"], "connecte")

    def test_sans_client_mais_avec_docker_on_propose_l_installation(self):
        self.natif = False
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["docker"], r["mode"]), ("a_installer", True, "absent"))
        self.assertIn("Docker", r["texte"])

    def test_sans_client_ni_docker(self):
        self.natif = self.docker = False
        self.assertEqual(self.lire("etat")["etat"], "absent")

    def test_deux_clients_sur_la_machine_sont_signales(self):
        self.conteneur = "en_marche"
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertTrue(r["conflit"])
        self.assertEqual(r["mode"], "natif_direct", "le client natif garde la main : le conteneur ne se pilote pas par-dessus")
        self.conteneur = "absent"
        self.g["_MODE"].update(t=0.0, val=None)
        self.assertFalse(self.lire("etat")["conflit"])

    def test_le_conteneur_d_un_autre_service_n_est_pas_un_client(self):
        self.natif = False
        self.conteneur = "autre"
        r = self.lire("etat")
        self.assertEqual(r["etat"], "absent")
        self.assertIn("n'est pas un conteneur NetBird", r["texte"])

    def test_le_client_est_dans_le_conteneur(self):
        self.natif = False
        self.conteneur = "en_marche"
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["mode"]), ("connecte", "docker"))
        self.assertEqual(self.racines[-1][:2], ("cli", ["docker", "netbird", "--", "status", "--json"]))

    def test_un_conteneur_arrete_est_dit_arrete(self):
        self.natif = False
        self.conteneur = "arrete"
        self.refus["status"] = (1, "Error: failed to connect to daemon: connection refused")
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["mode"], r["conteneur"]), ("arrete", "docker", "arrete"))
        self.assertIn("démon NetBird ne tourne pas", r["texte"])

    def test_un_client_natif_sans_droit_passe_par_le_courtier(self):
        self.droit_natif = False
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["mode"]), ("connecte", "natif_racine"))
        self.assertEqual(self.racines[-1][:2], ("cli", ["natif", "netbird", "--", "status", "--json"]))

    def test_le_reglage_mode_force_la_voie(self):
        self.conteneur = "en_marche"
        self.valeurs["mode"] = "docker"
        self.etat = CONNECTE
        self.assertEqual(self.lire("etat")["mode"], "docker")
        self.valeurs["mode"] = "natif"
        self.g["_MODE"].update(t=0.0, val=None)
        self.assertEqual(self.lire("etat")["mode"], "natif_direct")

    def test_etat_reutilise_sa_lecture_puis_les_gestes_relisent(self):
        self.g["_TTL"] = 60
        self.etat = CONNECTE
        self.lire("etat")
        n = len(self.appels_cli("status"))
        self.lire("etat")
        self.assertEqual(len(self.appels_cli("status")), n, "deuxième lecture : servie par le cache")
        self.lire("deconnecter")
        self.assertEqual(self.lire("etat")["etat"], "deconnecte", "un geste qui écrit relit à neuf")


class Gestes(Monde):
    def test_connecter_sans_cle_rend_un_lien_par_le_courtier(self):
        self.etat = statut("Idle")
        r = self.lire("connecter", nom="argos")
        self.assertEqual((r["etat"], r["en_attente"], r["lien"]), ("a_identifier", True, "https://login.netbird.io/device?user_code=ABCD-EFGH"))
        sso = [x for x in self.racines if x[0] == "sso"][0]
        self.assertEqual(sso[1], ["natif", "netbird", "--hostname=argos"])

    def test_connecter_avec_cle_la_cle_voyage_par_l_entree_standard(self):
        self.valeurs["cle_install"] = CLE
        r = self.lire("connecter", avec_cle=True, nom="argos", url="https://netbird.exemple.fr:443")
        self.assertEqual(r["etat"], "connecte")
        up = [x for x in self.racines if x[0] == "cli" and x[1][3] == "up"][0]
        self.assertEqual(up[1], ["natif", "netbird", "--", "up", "--hostname=argos", "--management-url=https://netbird.exemple.fr:443"])
        self.assertEqual(up[2], CLE)
        self.assertTrue(all(CLE not in str(x[1]) for x in self.racines), "la clé n'est dans aucun argument")
        self.assertFalse([d for d in self.directs if "up" in d], "une clé ne passe jamais par un client lancé directement : l'entrée standard exige le courtier")

    def test_la_cle_ne_fuit_pas_dans_une_erreur(self):
        self.valeurs["cle_install"] = CLE
        self.refus["up"] = (1, "Error: invalid setup key %s : not found" % CLE)
        with self.assertRaises(Echec) as q:
            self.lire("connecter", avec_cle=True)
        self.assertNotIn(CLE, str(q.exception))

    def test_une_cle_mal_formee_est_refusee_avant_tout_appel(self):
        for cle in ("", "n'importe quoi", "court"):
            self.valeurs["cle_install"] = cle
            with self.assertRaises(Echec) as q:
                self.lire("connecter", avec_cle=True)
            self.assertIn("clé d'installation", str(q.exception))
        self.assertFalse(self.appels_cli("up"))

    def test_un_nom_ou_une_adresse_invalides_sont_refuses(self):
        for kw in ({"nom": "mauvais nom; rm -rf /"}, {"url": "ftp://x"}, {"url": "https://x y"}):
            with self.assertRaises(Echec):
                self.lire("connecter", **kw)
        self.assertFalse([r for r in self.racines if r[0] == "sso"])

    def test_deja_connecte_ne_relance_rien(self):
        self.etat = CONNECTE
        self.assertEqual(self.lire("connecter")["etat"], "connecte")
        self.assertFalse([r for r in self.racines if r[0] == "sso"])

    def test_annuler_ne_coupe_pas_une_connexion_qui_marche(self):
        self.etat = CONNECTE
        self.assertEqual(self.lire("annuler")["etat"], "connecte")
        self.assertFalse([r for r in self.racines if r[0] == "sso_annuler"] or self.appels_cli("down"))

    def test_annuler_une_identification_en_attente(self):
        self.etat = statut("Idle")
        self.lire("connecter")
        r = self.lire("annuler")
        self.assertEqual((r["etat"], r["en_attente"]), ("deconnecte", False))

    def test_sans_courtier_le_lien_ne_peut_pas_etre_demande(self):
        self.courtier = False
        with self.assertRaises(Echec) as q:
            self.lire("connecter")
        self.assertIn("commande", str(q.exception))

    def test_deconnecter_puis_le_defaire_depuis_le_journal(self):
        self.etat = CONNECTE
        self.assertEqual(self.lire("deconnecter")["etat"], "deconnecte")
        g = self.lire("journal")["gestes"][0]
        self.assertEqual((g["capacite"], g["libelle"], g["defaisable"]), ("deconnecter", "NetBird coupé", True))
        self.assertEqual(self.lire("defaire_geste", id=g["id"])["etat"], "connecte", "le retour reprend la configuration gardée, sans option")
        self.assertTrue(self.lire("journal")["gestes"][0]["defait"])
        with self.assertRaises(Echec):
            self.lire("defaire_geste", id=g["id"])

    def test_un_refus_d_acces_dit_ce_qu_il_faut_faire(self):
        self.etat = CONNECTE
        self.refus["down"] = (1, "Error: rpc error: connect: permission denied")
        with self.assertRaises(Echec) as q:
            self.lire("deconnecter")
        self.assertIn("droit de parler au démon", str(q.exception))

    def test_un_journal_qui_casse_ne_fait_pas_echouer_le_geste(self):
        from unittest import mock
        self.etat = CONNECTE
        base = self.ctx.stockage
        with mock.patch.object(base, "ecrire", side_effect=RuntimeError("disque plein")):
            self.assertEqual(self.lire("deconnecter")["etat"], "deconnecte")

    def test_le_journal_ne_garde_jamais_la_cle(self):
        self.valeurs["cle_install"] = CLE
        self.lire("connecter", avec_cle=True)
        brut = " ".join(str(l["args"]) + str(l["res"]) for l in self.ctx.stockage.lire("SELECT args, res FROM gestes"))
        self.assertNotIn(CLE, brut)
        self.assertEqual(self.lire("journal", limite=1)["gestes"][0]["libelle"], "Connexion à NetBird par clé")


class Docker(Monde):
    def setUp(self):
        super().setUp()
        self.natif = False

    def test_un_seul_client_par_machine_le_natif_interdit_le_conteneur(self):
        self.natif = True
        with self.assertRaises(Echec) as q:
            self.lire("installer_docker")
        self.assertIn("un seul client par machine", str(q.exception))
        self.assertFalse([x for x in self.racines if x[0] == "docker_installer"], "refusé avant d'appeler le courtier")

    def test_installer_dans_docker_puis_le_defaire(self):
        r = self.lire("installer_docker", tag="0.40.0", nom="argos")
        self.assertEqual((r["docker_conteneur"], r["docker_tag"], r["conteneur"], r["mode"]), ("netbird", "0.40.0", "en_marche", "docker"))
        verbe, args, entree = [x for x in self.racines if x[0] == "docker_installer"][0]
        self.assertEqual((args, entree), (["netbird", "0.40.0", "--hostname=argos"], None))
        g = self.lire("journal")["gestes"][0]
        self.assertEqual((g["capacite"], g["defaisable"]), ("installer_docker", True))
        self.assertIn("conteneur netbird", g["libelle"])
        self.lire("defaire_geste", id=g["id"])
        self.assertEqual(self.conteneur, "absent")
        self.assertEqual([x for x in self.racines if x[0] == "docker_retirer"][0][1], ["netbird"], "le retour garde le volume : l'identité de la machine")

    def test_installer_avec_cle_la_cle_va_sur_l_entree_standard(self):
        self.valeurs["cle_install"] = CLE
        r = self.lire("installer_docker", avec_cle=True)
        self.assertEqual(r["etat"], "connecte")
        verbe, args, entree = [x for x in self.racines if x[0] == "docker_installer"][0]
        self.assertEqual(entree, CLE)
        self.assertTrue(all(CLE not in str(x[1]) for x in self.racines))

    def test_installer_refuse_ce_qui_est_suspect_avant_tout_appel(self):
        for kw in ({"tag": "latest;id"}, {"tag": "a b"}, {"url": "ftp://x"}, {"nom": "a b"}):
            with self.assertRaises(Echec, msg=kw):
                self.lire("installer_docker", **kw)
        self.valeurs["cle_install"] = "trop court"
        with self.assertRaises(Echec):
            self.lire("installer_docker", avec_cle=True)
        self.assertFalse([x for x in self.racines if x[0] == "docker_installer"])

    def test_sans_docker_l_installation_le_dit(self):
        self.docker = False
        with self.assertRaises(Echec) as q:
            self.lire("installer_docker")
        self.assertIn("Docker n'est pas installé", str(q.exception))

    def test_sans_courtier_l_installation_dit_quelle_commande_poser(self):
        self.courtier = False
        with self.assertRaises(Echec) as q:
            self.lire("installer_docker")
        self.assertIn("CN_install.sh --module netbird", str(q.exception))

    def test_le_nom_du_conteneur_est_un_reglage(self):
        self.valeurs["conteneur"] = "nb-argos"
        self.lire("installer_docker")
        self.assertEqual([x for x in self.racines if x[0] == "docker_installer"][0][1][0], "nb-argos")
        self.valeurs["conteneur"] = "mauvais nom;"
        self.assertEqual(self.lire("etat")["nom_conteneur"], "netbird", "un nom illisible retombe sur le nom par défaut")

    def test_retirer_le_conteneur_et_la_purge(self):
        self.conteneur = "en_marche"
        self.lire("retirer_docker")
        self.assertEqual([x for x in self.racines if x[0] == "docker_retirer"][0][1], ["netbird"])
        self.conteneur = "arrete"
        self.lire("retirer_docker", purger=True)
        self.assertEqual([x for x in self.racines if x[0] == "docker_retirer"][1][1], ["netbird", "purger"])
        self.assertEqual(self.lire("journal")["gestes"][0]["libelle"], "Conteneur NetBird retiré avec son volume (identité perdue)")

    def test_mettre_a_jour_le_client_docker(self):
        self.conteneur = "en_marche"
        self.maj_change = True
        r = self.lire("mettre_a_jour_client")
        self.assertTrue(r["maj_change"])
        self.assertEqual([x for x in self.racines if x[0] == "docker_maj"][0][1], ["netbird"], "sans étiquette : la même")
        self.assertEqual(self.lire("journal")["gestes"][0]["libelle"], "Client NetBird mis à jour (conteneur recréé, identité gardée)")

    def test_mettre_a_jour_un_client_deja_a_jour_le_dit(self):
        self.conteneur = "en_marche"
        self.maj_change = False
        self.assertFalse(self.lire("mettre_a_jour_client")["maj_change"])
        self.assertEqual(self.lire("journal")["gestes"][0]["libelle"], "Client NetBird déjà à jour")

    def test_mettre_a_jour_avec_une_etiquette_precise(self):
        self.conteneur = "arrete"
        self.lire("mettre_a_jour_client", tag="0.41.0")
        self.assertEqual([x for x in self.racines if x[0] == "docker_maj"][0][1], ["netbird", "0.41.0"])
        for tag in ("latest;id", "a b"):
            with self.assertRaises(Echec, msg=tag):
                self.lire("mettre_a_jour_client", tag=tag)
        self.assertEqual(len([x for x in self.racines if x[0] == "docker_maj"]), 1, "une étiquette suspecte n'arrive pas au courtier")

    def test_mettre_a_jour_le_client_natif_renvoie_au_gestionnaire_de_paquets(self):
        self.natif = True
        with self.assertRaises(Echec) as q:
            self.lire("mettre_a_jour_client")
        self.assertIn("gestionnaire de paquets", str(q.exception))
        self.assertFalse([x for x in self.racines if x[0] == "docker_maj"])

    def test_mettre_a_jour_sans_conteneur_ou_si_le_pull_echoue_est_refuse(self):
        with self.assertRaises(Echec):
            self.lire("mettre_a_jour_client")
        self.conteneur = "en_marche"
        self.maj_echoue = True
        with self.assertRaises(Echec):
            self.lire("mettre_a_jour_client")

    def test_retirer_sans_conteneur_est_refuse(self):

        with self.assertRaises(Echec):
            self.lire("retirer_docker")
        self.assertFalse([x for x in self.racines if x[0] == "docker_retirer"])

    def test_le_retrait_ne_se_defait_pas(self):
        self.conteneur = "en_marche"
        self.lire("retirer_docker")
        g = self.lire("journal")["gestes"][0]
        self.assertEqual((g["capacite"], g["defaisable"]), ("retirer_docker", False))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Echec, statut, Monde, Etats, Gestes, Docker
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
