# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'hébergement et du système (routes V18 portées)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #87684b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'hébergement et du système : les gestes de la machine (OOM, unités, sessions, services, journal), la rotation, la vérification et la restauration des sauvegardes, et la table des routes de la V18.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=87684b ▼▼▼
"""Bancs de l'hébergement et du système : chaque geste porté de la V18 est prouvé et défait (ou dit n'avoir aucun retour), le courtier est simulé."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402
from tests.CN_test_securite_analyse import releves   # noqa: E402

ADMIN = "root@x.fr"


class FauxCourtier:
    """Ce que répondrait le courtier : `mesurer` rend l'état de la machine simulée, `agir` ce qu'on lui a préparé, `lister`/`purger`/`copier` les destinations rclone."""
    def __init__(self):
        self.machine = releves()
        self.agir = {"ok": True}
        self.appels = []
        self.dossiers = ["2026-10-01", "2026-10-02", "2026-10-03", "autre"]
        self.au_geste = None

    def demander(self, module, commande, args=(), stdin=None, delai=30):
        self.appels.append((commande, list(args)))
        if commande == "mesurer":
            return {"ok": True, "code": 0, "sortie": json.dumps(self.machine), "erreur": ""}
        if commande == "agir":
            if self.agir.get("ok") and self.au_geste and args[0] == "faire":
                self.au_geste(self.machine)
            return {"ok": bool(self.agir.get("ok")), "code": 0 if self.agir.get("ok") else 1, "sortie": json.dumps(self.agir), "erreur": ""}
        if commande == "lister":
            return {"ok": True, "code": 0, "sortie": json.dumps([{"Path": d, "Name": d, "IsDir": True} for d in self.dossiers]), "erreur": ""}
        if commande == "purger":
            garder = int(args[1])
            datés = sorted(d for d in self.dossiers if re.match(r"^\d{4}-\d{2}-\d{2}$", d))
            self.dossiers = [d for d in self.dossiers if d not in datés[:-garder]]
            return {"ok": True, "code": 0, "sortie": "purge", "erreur": ""}
        if commande == "copier":
            return {"ok": True, "code": 0, "sortie": "Copied (new)\nCopied (new)\n", "erreur": ""}
        return {"ok": False, "erreur": "commande inconnue"}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("securite", "sauvegardes", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("securite", "sauvegardes"):
            self.n.etat_modules.poser(m, installe=True, par="banc")
        for m in ("droits", "comptes", "securite", "sauvegardes"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ADMIN, True)
        self.c = FauxCourtier()
        self.n.racine.demander = self.c.demander

    def ex(self, cap, **a):
        return self.n.executeur.executer(cap, "humain", a, compte=ADMIN)

    def ctx(self, module):
        return self.n.executeur.contextes[module]

    def defaire(self, cap, res):
        self.n.catalogue.get(cap).defaire(self.ctx(cap.split(".")[0]), res)


class Machine(Monde):
    def test_un_oom_acquitte_se_retient_et_se_defait(self):
        r = self.ex("securite.oom_acquitter", signatures=["2026-10-01 10:00:00_mysqld"])
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("securite.oom_acquits")["resultat"]["signatures"], ["2026-10-01 10:00:00_mysqld"])
        self.defaire("securite.oom_acquitter", r["resultat"])
        self.assertEqual(self.ex("securite.oom_acquits")["resultat"]["signatures"], [])

    def test_rien_a_acquitter_est_refuse(self):
        self.assertIn(self.ex("securite.oom_acquitter", signatures=[])["statut"], ("echec", "refuse"))

    def test_les_unites_remises_a_zero_se_prouvent_par_un_releve_et_n_ont_pas_de_retour(self):
        self.c.agir = {"ok": True, "avant": ["x.service"]}
        r = self.ex("securite.unites_reinitialiser")
        self.assertEqual(r["statut"], "faite", r)
        with self.assertRaises(ValueError) as e:
            self.defaire("securite.unites_reinitialiser", r["resultat"])
        self.assertIn("aucun retour", str(e.exception))

    def test_des_unites_encore_en_echec_ne_sont_pas_prouvees(self):
        self.c.machine["maj"]["unites_en_echec"] = ["x.service"]
        self.c.agir = {"ok": True}
        self.assertEqual(self.ex("securite.unites_reinitialiser")["statut"], "annulation_impossible")

    def test_fermer_une_session_passe_par_le_courtier_et_n_a_pas_de_retour(self):
        self.c.agir = {"ok": True, "tty": "pts/3"}
        r = self.ex("securite.session_fermer", user="marple", ip="100.64.0.2")
        self.assertEqual(r["statut"], "faite", r)
        verbe, geste, args = [a for a in self.c.appels if a[0] == "agir"][-1][1]
        self.assertEqual((verbe, geste), ("faire", "session_fermer"))
        self.assertEqual(json.loads(args), {"user": "marple", "ip": "100.64.0.2"})
        with self.assertRaises(ValueError):
            self.defaire("securite.session_fermer", r["resultat"])

    def test_une_session_sans_terminal_n_est_pas_prouvee(self):
        self.c.agir = {"ok": True}
        self.assertEqual(self.ex("securite.session_fermer", user="marple")["statut"], "annulation_impossible")

    def test_recharger_nginx_est_un_geste_de_la_table(self):
        self.c.agir = {"ok": True, "unite": "nginx.service", "detail": "reload nginx.service, actif"}
        r = self.ex("securite.systeme_geste", service="nginx", action="reload")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(json.loads([a for a in self.c.appels if a[0] == "agir"][-1][1][2]), {"service": "nginx", "action": "reload"})

    def test_le_journal_d_un_service_se_lit(self):
        self.c.agir = {"ok": True, "service": "nginx", "texte": "2026-11-01 nginx démarré"}
        r = self.ex("securite.journal_service", service="nginx")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("nginx démarré", r["resultat"]["texte"])

    def test_un_refus_du_courtier_est_une_erreur_dite(self):
        self.c.agir = {"ok": False, "erreur": "service hors de la table fermée"}
        r = self.ex("securite.systeme_geste", service="sshd", action="stop")
        self.assertIn(r["statut"], ("echec", "refuse"))
        self.assertIn("table fermée", r.get("erreur", ""))


class Courtier(unittest.TestCase):
    """Le programme root lui-même : sa table est fermée, il refuse ce qui n'y est pas."""
    def charge(self):
        import importlib.machinery
        import importlib.util
        chemin = RACINE / "modules" / "securite" / "commandes" / "CN_agir"
        spec = importlib.util.spec_from_loader("agir_test", importlib.machinery.SourceFileLoader("agir_test", str(chemin)))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_la_table_des_services_est_fermee(self):
        m = self.charge()
        self.assertEqual(set(m.SERVICES), {"nginx", "ollama", "noyau"})
        self.assertEqual(m.SERVICES["nginx"][1], ("reload",))
        self.assertIn("sensorium", m.JOURNAUX)
        self.assertNotIn("sshd", m.JOURNAUX)

    def test_un_nom_d_utilisateur_ou_un_terminal_illisible_est_repousse(self):
        m = self.charge()
        self.assertTrue(m.RE_UTILISATEUR.match("marple"))
        self.assertFalse(m.RE_UTILISATEUR.match("root; rm -rf /"))
        self.assertTrue(m.RE_TTY.match("pts/12"))
        self.assertFalse(m.RE_TTY.match("pts/1; id"))


class Sauvegardes(Monde):
    def plan(self, **kw):
        a = dict(nom="Docs", portee="doc", source="/srv/docs", destination="nas:backup", garder=2, date_dossier=1)
        a.update(kw)
        r = self.ex("sauvegardes.plan_save", **a)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]["id"]

    def copie(self, pid, dest="nas:backup/2026-10-03"):
        self.ctx("sauvegardes").stockage.ecrire("INSERT INTO sauv_copies (plan_id, resultat, destination) VALUES (?,?,?)", (pid, "3 copié(s)", dest))
        return self.ctx("sauvegardes").stockage.lire("SELECT id FROM sauv_copies ORDER BY id DESC LIMIT 1")[0]["id"]

    def test_la_rotation_ne_garde_que_les_dossiers_dates_recents_et_ne_touche_pas_aux_autres(self):
        pid = self.plan(garder=2)
        r = self.ex("sauvegardes.purger", pid=pid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["purges"], ["2026-10-01"])
        self.assertIn("autre", self.c.dossiers)
        with self.assertRaises(ValueError) as e:
            self.defaire("sauvegardes.purger", r["resultat"])
        self.assertIn("aucun retour", str(e.exception))

    def test_un_plan_sans_rotation_ne_purge_rien(self):
        pid = self.plan(garder=2, date_dossier=0)
        r = self.ex("sauvegardes.purger", pid=pid)
        self.assertEqual(r["resultat"]["purges"], [])
        self.assertEqual([a for a in self.c.appels if a[0] == "purger"], [])

    def test_une_copie_presente_est_verifiee_et_le_verdict_se_defait(self):
        pid = self.plan()
        cid = self.copie(pid)
        r = self.ex("sauvegardes.verifier", copie_id=cid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["ok"])
        self.assertIn("présence seulement", r["resultat"]["detail"])
        self.defaire("sauvegardes.verifier", r["resultat"])
        self.assertEqual(self.ctx("sauvegardes").stockage.lire("SELECT verifie FROM sauv_copies WHERE id=?", (cid,))[0]["verifie"], 0)

    def test_une_copie_absente_de_la_destination_est_dite_absente(self):
        pid = self.plan()
        cid = self.copie(pid, dest="nas:backup/2026-09-01")
        r = self.ex("sauvegardes.verifier", copie_id=cid)
        self.assertFalse(r["resultat"]["ok"])
        self.assertIn("ABSENT", r["resultat"]["detail"])

    def test_restaurer_est_a_blanc_et_a_cote_par_defaut(self):
        pid = self.plan()
        cid = self.copie(pid)
        r = self.ex("sauvegardes.restaurer", copie_id=cid)
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertTrue(res["blanc"] and res["a_cote"])
        self.assertIn("/srv/docs-restauration/", res["cible"])
        self.assertEqual(res["fichiers"], 2)
        self.assertEqual([a for a in self.c.appels if a[0] == "copier"][-1][1][2], "1")
        self.defaire("sauvegardes.restaurer", res)                       # un essai à blanc n'a rien écrit : rien à défaire

    def test_restaurer_sur_place_dit_qu_il_n_a_pas_de_retour(self):
        pid = self.plan()
        cid = self.copie(pid)
        r = self.ex("sauvegardes.restaurer", copie_id=cid, blanc=False, a_cote=False)
        self.assertEqual(r["statut"], "faite", r)
        with self.assertRaises(ValueError) as e:
            self.defaire("sauvegardes.restaurer", r["resultat"])
        self.assertIn("écrasé", str(e.exception))

    def test_une_copie_du_panneau_se_restaure_depuis_le_panneau(self):
        pid = self.plan(portee="site", source="exemple.org", destination="fp:plan")
        cid = self.copie(pid)
        self.assertIn("panneau", self.ex("sauvegardes.restaurer", copie_id=cid).get("erreur", ""))


class Routes(unittest.TestCase):
    """La table des routes de la V18 (section « Hébergement et système ») : aucune ne répond plus 501."""
    def test_les_cinquante_sept_routes_sont_branchees(self):
        doc = (RACINE / "docs" / "CN_ROUTES_A_PORTER.md").read_text(encoding="utf-8")
        reste = doc.split("## Hébergement et système")[1].split("\n## ")[0] if "## Hébergement et système" in doc else ""
        attendues = []
        for m in re.finditer(r"^- `(/api/[a-z0-9_]+)` \(\d+\) : (.*)$", reste, re.M):
            attendues += [m.group(1) + s for s in re.findall(r"`([^`]*)`", m.group(2))]
        source = "".join(f.read_text(encoding="utf-8") for f in (RACINE / "interface" / "routes").glob("CN_*.js"))
        # Une fois la section portée, le relevé ne les liste plus : on teste alors les routes connues de cette session.
        connues = ["/api/ports", "/api/sessions", "/api/failed", "/api/oom", "/api/oom/clear", "/api/failed/reset", "/api/session/kill", "/api/docker", "/api/ssl", "/api/tailscale",
                   "/api/fail2ban", "/api/remotes", "/api/dashboard", "/api/system", "/api/system/geste", "/api/system/wipe", "/api/exec", "/api/exec/stream", "/api/rollback",
                   "/api/upload", "/api/service/restart/collector", "/api/service/restart/agent", "/api/multiserver/aggregate", "/api/multiserver/resolve_quickconnect",
                   "/api/crons/suggest", "/api/pf/scan", "/api/pf/scans", "/api/pf/scan/note", "/api/sauv/purger", "/api/sauv/restaurer", "/api/sauv/verifier",
                   "/api/securite/direct", "/api/securite/defaire", "/api/securite/audit/rediger", "/api/site/copies", "/api/site/rapport", "/api/site/restaurer",
                   "/api/site/sauvegarde", "/api/site/scan", "/api/site/thumb", "/api/sites/act", "/api/fp/act", "/api/fp/api/creds", "/api/fp/api/test", "/api/fp/db/delete",
                   "/api/fp/db/users", "/api/fp/domain/attach", "/api/fp/domain/context", "/api/fp/scans/configure", "/api/fp/scans/report", "/api/fp/scans/reports",
                   "/api/fp/scans/run", "/api/fp/scans/targets", "/api/fp/service/diagnose", "/api/fp/stats", "/api/fp/user/ssh", "/api/fp/users/link", "/api/fp/websocket/apply"]
        for r in set(attendues + connues):
            self.assertIn('"%s"' % r, source, "route non branchée : " + r)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : FauxCourtier, Monde, Machine, Courtier, Sauvegardes, Routes
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
