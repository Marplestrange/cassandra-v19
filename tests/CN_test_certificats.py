# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module certificats
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #4c8bd7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module certificats : la lecture du certificat servi est simulée, le reste (états, quota, événements, constats) tourne dans un vrai noyau.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4c8bd7 ▼▼▼
"""Bancs du module certificats : la lecture du certificat servi est simulée, le reste (états, quota, événements, constats) tourne dans un vrai noyau."""
import importlib.util
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("dns", "certificats"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("certificats", installe=True, actif=False, par="test")        # son installation (CN_installer.sh) est l'affaire de l'administrateur système
        self.assertTrue(self.n.activer("certificats")["ok"])
        self.ctx = self.n.executeur.contextes["certificats"]
        self.panneau = [{"domaine": "a.exemple.fr"}, {"domaine": "www.b.exemple.org"}, {"domaine": "c.exemple.fr"}]
        # Panel Detect : la route de « sites » mène au panneau simulé du banc ; toute autre lecture rend ce même panneau
        self.ctx.executer_lecture = lambda cap, **a: {"capacite": "fastpanel.sites"} if cap == "paneldetect.route" else self.panneau
        self.certs = {}
        g = self.n.catalogue.get("certificats.etat").faire.__globals__
        g["lire_certificat"] = lambda h, d: self.certs.get(h, {"erreur": "connexion refusée"})
        self.e = self.n.executeur.executer

    def cert(self, jours, emetteur="Let's Encrypt"):
        return {"jours": jours, "echeance": (datetime.utcnow() + timedelta(days=jours)).strftime("%Y-%m-%d"), "emetteur": emetteur, "noms": []}

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def etat(self, h):
        o = self.n.registre.lire("certificat", h, portee=TOUT)
        return o["etat"] if o else None

    def sonde(self):
        self.n.lancer("certificats.sonde")

    def ex(self, cap, **args):
        return self.e("certificats." + cap, "humain", args, compte="")


class Sonde(Monde):
    def test_la_sonde_suit_aussi_les_sites_declares_hors_du_panneau(self):
        self.ctx.executer_lecture = lambda cap, **a: {"capacite": "fastpanel.sites"} if cap == "paneldetect.route" else {"sites": [{"domaine": "declare.exemple.fr"}]} if cap == "sites.vue" else self.panneau
        self.certs["declare.exemple.fr"] = self.cert(40)
        self.sonde()
        self.assertEqual(self.etat("declare.exemple.fr"), "valide")      # Sites ne lit plus les certificats : c'est ici qu'un site déclaré trouve son échéance

    def test_les_etats_et_le_domaine_inconnu_n_est_pas_sans_certificat(self):
        self.certs = {"a.exemple.fr": self.cert(80), "b.exemple.org": self.cert(10), "c.exemple.fr": self.cert(-3)}
        self.n.reglages.poser("certificats.hotes", "d.exemple.fr")
        self.sonde()
        self.assertEqual([self.etat(h) for h in ("a.exemple.fr", "b.exemple.org", "c.exemple.fr", "d.exemple.fr")], ["valide", "proche", "echu", "inconnu"])
        self.assertIn("refusée", self.n.registre.lire("certificat", "d.exemple.fr", portee=TOUT)["donnees"]["erreur"])

    def test_le_passage_sous_le_seuil_est_dit_une_fois(self):
        self.certs = {"a.exemple.fr": self.cert(80)}
        self.sonde()
        self.certs["a.exemple.fr"] = self.cert(15)
        self.sonde()
        self.sonde()
        self.assertEqual(len(self.evts("certificat.proche_expiration")), 1)

    def test_le_seuil_est_un_reglage(self):
        self.certs = {"a.exemple.fr": self.cert(30)}
        self.sonde()
        self.assertEqual(self.etat("a.exemple.fr"), "valide")
        self.n.reglages.poser("certificats.seuil_jours", 45)
        self.sonde()
        self.assertEqual(self.etat("a.exemple.fr"), "proche")

    def test_constats_critique_sous_sept_jours_avec_le_quota(self):
        self.certs = {"a.exemple.fr": self.cert(4), "b.exemple.org": self.cert(15), "c.exemple.fr": self.cert(70)}
        self.sonde()
        self.n.tick()
        ouverts = {e["donnees"]["titre"]: e["donnees"] for e in self.evts("constat.ouvert")}
        self.assertEqual(len(ouverts), 2)
        crit = [d for t, d in ouverts.items() if "a.exemple.fr" in t][0]
        self.assertEqual(crit["niveau"], "critique")
        self.assertIn("Il reste 5 émission(s)", crit["detail"])

    def test_un_certificat_renouvele_resout_le_constat(self):
        self.certs = {"a.exemple.fr": self.cert(4)}
        self.sonde()
        self.n.tick()
        self.certs["a.exemple.fr"] = self.cert(85)
        self.sonde()
        self.n.tick(time.time() + 4000)
        self.assertEqual(len(self.evts("constat.resolu")), 1)

    def test_etat_liste_les_certificats(self):
        self.certs = {"a.exemple.fr": self.cert(80)}
        self.sonde()
        e = {c["hote"]: c for c in self.ex("etat")["resultat"]["certificats"]}
        self.assertEqual((e["a.exemple.fr"]["etat"], e["c.exemple.fr"]["etat"]), ("valide", "inconnu"))


class Quota(Monde):
    def emission(self, domaine):
        self.n.bus.emettre("fastpanel.certificat_renouvele", source="fastpanel", acteur="cassandra", objet=("fastpanel", domaine), donnees={"domaine": domaine})
        self.n.lancer("certificats.emission")

    def test_une_emission_du_panneau_compte_au_domaine_enregistre(self):
        self.emission("www.a.exemple.fr")
        self.emission("blog.a.exemple.fr")
        q = self.ex("quota", domaine="x.a.exemple.fr")["resultat"]
        self.assertEqual((q["domaine"], q["utilisees"], q["restantes"], q["bloque"]), ("exemple.fr", 2, 3, False))
        self.assertEqual(len(self.evts("certificat.renouvele")), 2)

    def test_cinq_emissions_bloquent_et_le_quota_se_libere_apres_sept_jours(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        q = self.ex("quota", domaine="exemple.fr")["resultat"]
        self.assertTrue(q["bloque"] and q["libre_le"])
        self.ctx.stockage.ecrire("UPDATE emissions SET ts = ts - ?", (8 * 86400,))
        self.assertFalse(self.ex("quota", domaine="exemple.fr")["resultat"]["bloque"])

    def test_le_quota_est_dit_dans_le_constat(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        self.certs = {"a.exemple.fr": self.cert(3)}
        self.sonde()
        self.n.tick()
        self.assertIn("Quota Let's Encrypt épuisé", " ".join(e["donnees"]["detail"] for e in self.evts("constat.ouvert")))

    def test_le_quota_est_par_domaine(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        self.assertEqual(self.ex("quota", domaine="b.exemple.org")["resultat"]["restantes"], 5)

    def test_un_evenement_n_est_compte_qu_une_fois(self):
        self.emission("a.exemple.fr")
        self.n.lancer("certificats.emission")
        self.n.lancer("certificats.sonde")
        self.assertEqual(self.ex("quota", domaine="exemple.fr")["resultat"]["utilisees"], 1)

    def test_le_module_n_exige_pas_que_le_panneau_soit_la(self):
        self.assertEqual(self.ex("quota", domaine="exemple.fr")["resultat"]["utilisees"], 0)

    def test_un_evenement_sans_domaine_ne_casse_rien(self):
        self.n.bus.emettre("fastpanel.certificat_renouvele", source="fastpanel", acteur="cassandra", objet=("fastpanel", "x"), donnees={})
        self.n.lancer("certificats.emission")
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM emissions")[0]["n"], 0)


class Lecture(Monde):
    def test_relire_un_hote_et_les_refus(self):
        self.certs = {"a.exemple.fr": self.cert(40)}
        r = self.ex("relire_expiration", hote="https://www.a.exemple.fr/accueil")
        self.assertEqual((r["statut"], r["resultat"]["hote"], r["resultat"]["jours"]), ("faite", "a.exemple.fr", 40))
        self.assertEqual(self.ex("relire_expiration", hote="pas un hote")["statut"], "echec")
        self.assertEqual(self.ex("relire_expiration", hote="inconnu.exemple.fr")["resultat"]["erreur"], "connexion refusée")

    def test_la_lecture_reelle_d_un_port_ferme_est_une_erreur_et_pas_une_exception(self):
        spec = importlib.util.spec_from_file_location("c", RACINE / "modules" / "certificats" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertIn("erreur", m.lire_certificat("127.0.0.1", 1))


def _pem(nom, jours=90, algo="ec"):
    """Un certificat auto-signé PUBLIC pour les bancs (sa clé reste dans un dossier temporaire et n'est jamais relue)."""
    import subprocess
    d = tempfile.mkdtemp()
    cle, crt = d + "/k.pem", d + "/c.pem"
    cmd = ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1"] if algo == "ec" else ["openssl", "req", "-x509", "-newkey", "rsa:2048"]
    subprocess.run(cmd + ["-nodes", "-keyout", cle, "-out", crt, "-days", str(jours), "-subj", "/CN=" + nom, "-addext", "subjectAltName=DNS:" + nom], check=True, capture_output=True)
    with open(crt, encoding="utf-8") as f:
        return f.read()


class Cycle(Monde):
    def lignes(self, table):
        return self.ctx.stockage.lire("SELECT * FROM " + table)

    def test_une_demande_sur_un_hote_suivi_sans_approbation_est_validee_d_office(self):
        r = self.ex("demander", hote="a.exemple.fr", modele="public")
        self.assertEqual((r["statut"], r["resultat"]["etat"]), ("faite", "validee"))
        self.assertIn("automatique", self.lignes("demande")[0]["valideur"])

    def test_une_demande_sur_un_hote_inconnu_attend_un_validateur(self):
        r = self.ex("demander", hote="nouveau.exemple.fr", modele="public")
        self.assertEqual(r["resultat"]["etat"], "a_valider")
        self.assertEqual(len(self.evts("certificat.demande")), 1)

    def test_les_refus_de_saisie(self):
        for args in ({"hote": "pas un hote"}, {"hote": "*.exemple.fr", "modele": "wildcard"}, {"hote": "*.exemple.fr", "modele": "public", "justification": "x"},
                     {"hote": "x.exemple.fr", "sans": "pas valide!"}, {"hote": "x.exemple.fr", "modele": "inconnu"}):
            self.assertEqual(self.ex("demander", **args)["statut"], "echec", args)
        self.assertEqual(self.ex("demander", hote="*.exemple.fr", modele="wildcard", justification="sous-domaines clients")["statut"], "faite")

    def test_un_hote_valide_ne_se_redemande_pas_et_pas_deux_demandes_en_cours(self):
        self.certs = {"a.exemple.fr": self.cert(80)}
        self.sonde()
        self.assertEqual(self.ex("demander", hote="a.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("demander", hote="n.exemple.fr")["statut"], "faite")
        self.assertEqual(self.ex("demander", hote="n.exemple.fr")["statut"], "echec")

    def test_on_ne_valide_jamais_sa_propre_demande(self):
        i = self.ex("demander", hote="n.exemple.fr", brouillon=True)["resultat"]["id"]
        self.assertEqual(self.lignes("demande")[0]["etat"], "brouillon")
        self.assertEqual(self.ex("soumettre", id=i)["resultat"]["etat"], "a_valider")
        self.ctx.stockage.ecrire("UPDATE demande SET demandeur='alice' WHERE id=?", (i,))
        fn = self.n.catalogue.get("certificats.valider").faire
        self.ctx._compte.valeur = "alice"
        try:
            with self.assertRaises(PermissionError):
                fn(self.ctx, id=i)
        finally:
            self.ctx._compte.valeur = ""
        self.assertTrue([a for a in self.lignes("audit") if a["resultat"] == "refus"])
        self.assertEqual(self.ex("valider", id=i)["resultat"]["etat"], "validee")                 # un autre compte (ici le système) valide

    def test_un_refus_exige_un_motif_et_se_rouvre(self):
        i = self.ex("demander", hote="n.exemple.fr")["resultat"]["id"]
        self.assertEqual(self.ex("refuser", id=i)["statut"], "echec")
        self.assertEqual(self.ex("refuser", id=i, motif="hors périmètre")["resultat"]["etat"], "refusee")
        self.assertEqual(self.ex("rouvrir", id=i)["resultat"]["etat"], "brouillon")
        self.assertEqual(self.ex("valider", id=i)["statut"], "echec")                                # un brouillon n'attend pas de validation

    def test_cloturer_une_demande_et_inscrire_l_echec_au_quota_sans_le_compter(self):
        i = self.ex("demander", hote="a.exemple.fr")["resultat"]["id"]
        self.assertEqual(self.ex("cloturer_demande", id=i, ok=False, motif="date inchangée")["resultat"]["etat"], "echec")
        q = self.ex("quota", domaine="a.exemple.fr")["resultat"]
        self.assertEqual((q["utilisees"], q["echecs_heure"]), (0, 1))
        self.assertEqual(self.ex("noter_echec", hote="a.exemple.fr", motif="refus du panneau")["statut"], "faite")
        self.assertEqual(self.ex("quota", domaine="a.exemple.fr")["resultat"]["echecs_heure"], 2)

    def test_revoquer_archiver_et_leur_retour(self):
        self.certs = {"a.exemple.fr": self.cert(10), "z.exemple.net": self.cert(10)}
        self.n.reglages.poser("certificats.hotes", "z.exemple.net")
        self.sonde()
        self.assertEqual(self.ex("revoquer", hote="z.exemple.net", raison="x")["statut"], "echec")        # seulement sondé
        self.assertEqual(self.ex("revoquer", hote="a.exemple.fr")["statut"], "echec")                      # raison obligatoire
        self.assertEqual(self.ex("revoquer", hote="a.exemple.fr", raison="clé compromise")["statut"], "faite")
        f = {x["hote"]: x for x in self.ex("lister")["resultat"]["certificats"]}["a.exemple.fr"]
        self.assertEqual((f["etat"], f["force"]), ("revoque", "revoque"))
        self.assertEqual(self.ex("archiver", hote="a.exemple.fr")["statut"], "faite")                      # un révoqué s'archive pour sortir de la liste
        self.assertEqual(self.ex("archiver", hote="a.exemple.fr")["statut"], "echec")
        self.assertEqual(self.ex("desarchiver", hote="a.exemple.fr")["resultat"]["etat"], "revoque")       # et redevient révoqué, raison comprise
        self.assertEqual(self.ctx.stockage.lire("SELECT note FROM cert_meta WHERE hote='a.exemple.fr'")[0]["note"], "clé compromise")
        self.assertEqual(self.ex("archiver", hote="jamais.exemple.fr")["statut"], "echec")                  # jamais lu : pas suivi
        self.assertEqual(self.ex("archiver", hote="z.exemple.net")["statut"], "faite")
        self.assertEqual(self.ex("desarchiver", hote="z.exemple.net")["statut"], "faite")
        self.assertEqual(self.ex("desarchiver", hote="z.exemple.net")["statut"], "echec")

    def test_un_certificat_archive_n_est_plus_sonde_ni_signale(self):
        self.certs = {"a.exemple.fr": self.cert(3)}
        self.sonde()
        self.ex("archiver", hote="a.exemple.fr")
        self.assertEqual(self.ex("signal_jour")["resultat"]["items"], [])
        self.certs["a.exemple.fr"] = self.cert(80)
        self.sonde()
        self.assertEqual(self.etat("a.exemple.fr"), "proche")                                           # pas relu : l'archivé sort de la sonde

    def test_importer_un_certificat_public_et_refuser_une_cle(self):
        if not shutil.which("openssl"):
            self.skipTest("openssl absent")
        pem = _pem("mail.exemple.fr", 200)
        self.assertEqual(self.ex("importer", hote="mail.exemple.fr", pem=pem + "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----")["statut"], "echec")
        self.assertEqual(self.ex("importer", hote="mail.exemple.fr", pem="n'importe quoi")["statut"], "echec")
        self.assertEqual(self.ex("importer", hote="autre.exemple.fr", pem=pem)["statut"], "echec")           # ne couvre pas ce nom
        r = self.ex("importer", hote="mail.exemple.fr", pem=pem)
        self.assertEqual((r["statut"], r["resultat"]["jours"] >= 199), ("faite", True))
        f = {x["hote"]: x for x in self.ex("lister")["resultat"]["certificats"]}["mail.exemple.fr"]
        self.assertEqual((f["source"], f["etat"], f["algo"]), ("importe", "valide", "ECDSA P-256"))

    def test_lire_x509_algo_et_empreinte(self):
        if not shutil.which("openssl"):
            self.skipTest("openssl absent")
        spec = importlib.util.spec_from_file_location("c", RACINE / "modules" / "certificats" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        x = m.lire_x509(_pem("r.exemple.fr", 30, "rsa").encode(), "PEM")
        self.assertEqual((x["algo"], x["noms"]), ("RSA 2048", ["r.exemple.fr"]))
        self.assertEqual(len(x["empreinte"].split(":")), 32)
        with self.assertRaises(ValueError):
            m.lire_x509(b"rien", "PEM")

    def test_la_synthese_compte_et_les_cles_ne_montrent_jamais_de_cle(self):
        self.certs = {"a.exemple.fr": self.cert(80), "b.exemple.org": self.cert(5), "c.exemple.fr": self.cert(-3)}
        self.sonde()
        s = self.ex("synthese")["resultat"]
        self.assertEqual((s["suivis"], s["valides"], s["proches"], s["echus"], s["inconnus"]), (3, 1, 1, 1, 0))
        self.assertEqual(sum(t["n"] for t in s["histogramme"]), 3)
        self.assertNotIn("PRIVATE", str(self.ex("cles")["resultat"]))

    def test_l_audit_se_filtre_et_les_rapports(self):
        self.ex("demander", hote="n.exemple.fr")
        a = self.ex("audit")["resultat"]["audit"]
        self.assertTrue(any(x["action"] == "demande.soumise" for x in a))
        self.assertEqual(self.ex("audit", resultat="refus")["resultat"]["audit"], [])
        self.assertEqual(self.ex("rapport", nom="Inventaire complet")["statut"], "faite")
        self.assertEqual(self.ex("rapport", nom="inconnu")["statut"], "echec")

    def test_la_defaite_d_une_demande_la_supprime(self):
        r = self.ex("demander", hote="n.exemple.fr")
        self.assertEqual(len(self.lignes("demande")), 1)
        self.n.catalogue.get("certificats.demander").defaire(self.ctx, r["resultat"])
        self.assertEqual(self.lignes("demande"), [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Sonde, Quota, Lecture, Cycle
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
