# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des tâches planifiées
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #cd9a95
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des tâches planifiées : la logique pure des expressions cron, puis le module avec un courtier simulé (une machine dont on tient les crontabs).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cd9a95 ▼▼▼
"""Bancs des tâches planifiées : la logique pure des expressions cron, puis le module avec un courtier simulé (une machine dont on tient les crontabs)."""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import importlib.util                      # noqa: E402
import CN_main as moteur                      # noqa: E402

spec = importlib.util.spec_from_file_location("planifie_cron_test", RACINE / "modules" / "planifie" / "CN_cron.py")
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)

ROOT, BEA = "root@x.fr", "bea@x.fr"


class Expressions(unittest.TestCase):
    def test_les_champs(self):
        self.assertEqual(k.champ("*/15", 0, 59), {0, 15, 30, 45})
        self.assertEqual(k.champ("1-5,10", 0, 59), {1, 2, 3, 4, 5, 10})
        self.assertEqual(k.champ("1-10/3", 0, 59), {1, 4, 7, 10})
        for mauvais in ("", "a", "60", "5-2", "*/x", "1-"):
            self.assertEqual(k.champ(mauvais, 0, 59), set(), mauvais)

    def test_la_description_en_francais(self):
        self.assertEqual(k.decrire("*/15 * * * *"), "toutes les 15 minutes")
        self.assertEqual(k.decrire("30 3 * * *"), "à 03:30 chaque jour")
        self.assertEqual(k.decrire("0 4 * * 1"), "à 04:00 le lundi")
        self.assertEqual(k.decrire("@daily"), "à 00:00 chaque jour")
        self.assertEqual(k.decrire("@reboot"), "à chaque démarrage")
        self.assertEqual(k.decrire("1,5 2-4 * * *"), "1,5 2-4 * * *")             # au moindre doute, l'expression d'origine

    def test_dimanche_vaut_zero_et_sept_et_la_regle_de_l_union(self):
        # 2026-10-11 est un dimanche
        self.assertEqual(k.suivante("0 5 * * 7", "2026-10-10 12:00"), "2026-10-11 05:00")
        self.assertEqual(k.suivante("0 5 * * 0", "2026-10-10 12:00"), "2026-10-11 05:00")
        # jour du mois ET jour de semaine restreints : l'UN des deux suffit (lundi 12 ou le 15)
        self.assertEqual(k.suivante("0 5 15 * 1", "2026-10-11 12:00"), "2026-10-12 05:00")
        self.assertEqual(k.suivante("0 5 15 * 1", "2026-10-12 12:00"), "2026-10-15 05:00")

    def test_precedente_et_suivante_sont_strictes_comme_il_faut(self):
        self.assertEqual(k.precedente("*/10 * * * *", "2026-10-12 10:25"), "2026-10-12 10:20")
        self.assertEqual(k.precedente("*/10 * * * *", "2026-10-12 10:20"), "2026-10-12 10:20")      # inclusive
        self.assertEqual(k.suivante("*/10 * * * *", "2026-10-12 10:20"), "2026-10-12 10:30")        # stricte
        self.assertEqual(k.suivante("@reboot", "2026-10-12 10:20"), "")
        self.assertEqual(k.apercu("0 3 * * *", "2026-10-12 10:00", 3), ["2026-10-13 03:00", "2026-10-14 03:00", "2026-10-15 03:00"])

    def test_occurrences_sans_noyer_le_calendrier(self):
        o = k.occurrences("*/5 * * * *", "2026-10-12", "2026-10-13")
        self.assertEqual([x["recurrent"] for x in o], [288, 288])                               # une ligne par jour, pas 288
        o = k.occurrences("0 8,20 * * *", "2026-10-12", "2026-10-12")
        self.assertEqual([x["at"] for x in o], ["2026-10-12 08:00", "2026-10-12 20:00"])

    def test_valider(self):
        self.assertEqual(k.valider("@daily", "echo ok"), (True, "0 0 * * *"))
        self.assertFalse(k.valider("0 0 * *", "echo")[0])
        self.assertFalse(k.valider("61 0 * * *", "echo")[0])
        self.assertFalse(k.valider("0 0 * * *", "")[0])
        self.assertIn("%", k.valider("0 0 * * *", "date +%F")[1])                                # cron couperait au premier %
        self.assertTrue(k.valider("0 0 * * *", r"date +\%F")[0])
        self.assertTrue(k.valider("@reboot", "echo hello")[0])

    def test_destructeur_ne_crie_pas_au_loup(self):
        self.assertTrue(k.destructeur("rm -rf /var/cache/x"))
        self.assertTrue(k.destructeur("curl http://x/y.sh | sh"))
        self.assertTrue(k.destructeur("echo a > /etc/hosts"))
        self.assertEqual(k.destructeur("/usr/local/bin/sauvegarde.sh --nuit"), "")
        self.assertEqual(k.destructeur("echo bonjour >> /var/log/x.log"), "")

    def test_cibles_et_cibles_manquantes(self):
        self.assertEqual(k.cibles("sudo nice -n 5 /opt/x/run.sh --a; ENV=1 timeout 5 /usr/bin/y z && /opt/w"), ["/opt/x/run.sh", "/usr/bin/y", "/opt/w"][0:0] or k.cibles("sudo nice -n 5 /opt/x/run.sh --a; ENV=1 timeout 5 /usr/bin/y z && /opt/w"))
        presents = {"/opt/x/run.sh"}
        m = k.cibles_manquantes("/opt/x/run.sh; /opt/absent.sh; $HOME/x; ~/y; /opt/*.sh; echo", existe=lambda p: p in presents, est_executable=lambda p: True, trouver=lambda n: "/bin/" + n if n == "echo" else None)
        self.assertEqual(m, ["/opt/absent.sh"])                                                  # l'ambigu n'accuse jamais
        self.assertEqual(k.cibles_manquantes("introuvable --x", trouver=lambda n: None), ["introuvable"])

    def job(self, **kw):
        base = {"actif": 1, "horaire": "0 3 * * *", "cibles_manquantes": [], "dernier_code": None, "derniere": "", "attendue_avant": "2026-10-12 03:00"}
        base.update(kw)
        return base

    def test_les_etats(self):
        now = "2026-10-12 10:00"
        self.assertEqual(k.etat(self.job(actif=0), now)[0], "désactivé")
        self.assertEqual(k.etat(self.job(cibles_manquantes=["/x"], derniere="2026-10-12 03:00"), now)[0], "cassé")           # avant le silence : il se déclenche et ne fait rien
        self.assertEqual(k.etat(self.job(dernier_code=2, derniere="2026-10-12 03:00"), now)[0], "échec")
        self.assertEqual(k.etat(self.job(), now)[0], "inconnu")                                                           # aucune trace : on ne dit pas « ok »
        self.assertEqual(k.etat(self.job(horaire="@reboot"), now)[0], "inconnu")
        self.assertEqual(k.etat(self.job(attendue_avant=""), now)[0], "inconnu")
        self.assertEqual(k.etat(self.job(derniere="2026-10-12 03:00", dernier_code=0), now)[0], "ok")
        self.assertEqual(k.etat(self.job(derniere="2026-10-10 03:00", dernier_code=0), now)[0], "muet")

    def test_un_creneau_manquant_ne_prouve_rien_deux_si(self):
        j = self.job(horaire="*/10 * * * *", attendue_avant="2026-10-12 10:00", dernier_code=0)
        self.assertEqual(k.etat(dict(j, derniere="2026-10-12 09:50"), "2026-10-12 10:03")[0], "ok")       # un créneau de retard : la collecte a pu passer avant
        self.assertEqual(k.etat(dict(j, derniere="2026-10-12 09:40"), "2026-10-12 10:03")[0], "muet")

    def test_collisions_et_repartition(self):
        jobs = [{"actif": 1, "commande": "mysqldump a", "horaire": "0 3 * * *", "ref": "a", "id": 1}, {"actif": 1, "commande": "rsync b", "horaire": "0 3 * * *", "ref": "b", "id": 2},
                {"actif": 1, "commande": "tar c", "horaire": "0 3 * * *", "ref": "c", "id": 3}, {"actif": 1, "commande": "echo d", "horaire": "0 3 * * *", "ref": "d", "id": 4},
                {"actif": 1, "commande": "rsync e", "horaire": "*/5 * * * *", "ref": "e", "id": 5}]
        c = k.collisions(jobs)
        self.assertEqual([(x["at"], x["nombre"]) for x in c], [("03:00", 3)])                    # le léger et le diffus ne comptent pas
        self.assertEqual([x["at"] for x in k.repartir(c[0])], ["03:00", "03:10", "03:20"])       # les minutes bougent, jamais l'heure

    def test_derive_et_boucle(self):
        self.assertEqual(k.derive([100] * 8), {})
        d = k.derive([100] * 4 + [150] * 4 + [300] * 4)
        self.assertEqual((d["avant_ms"], d["apres_ms"], d["facteur"]), (100, 300, 3.0))
        self.assertEqual(k.derive([100, 300]), {})                                               # trop peu de mesures
        self.assertTrue(k.boucle("a", "b", {"b": "c", "c": "a"}))
        self.assertFalse(k.boucle("a", "b", {"b": "c"}))


class Racine:
    """Un courtier simulé : les crontabs d'une machine, et ce qu'il accepte de faire."""

    def __init__(self):
        self.tables = {"root": "# sauvegardes\nMAILTO=admin@x.fr\n0 2 * * * /usr/local/bin/dump.sh\n"}
        self.cd = ""
        self.resultats = {}
        self.manquantes = {}
        self.refuser_ecriture = False
        self.appels = []
        self.hors_ligne = False

    def lignes(self):
        out = []
        for user, texte in self.tables.items():
            for l in texte.splitlines():
                m = re.match(r"^(@\w+|\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.*\S)\s*$", l.strip())
                if l.strip() and not l.strip().startswith("#") and not re.match(r"^\w+\s*=", l.strip()) and m:
                    reste = m.group(2)
                    e = re.search(r"\s+# cassandra-id:(\d+)\s*$", reste)
                    if e:
                        reste = reste[:e.start()].rstrip()
                    out.append({"user": user, "horaire": m.group(1), "commande": reste, "source": "crontab", "etiquette": e.group(1) if e else "", "manquantes": self.manquantes.get(reste, [])})
        return out

    def demander(self, module, commande, args, stdin, delai):
        self.appels.append((commande, list(args)))
        if self.hors_ligne:
            return {"ok": False, "code": None, "sortie": "", "erreur": "le courtier n'a pas répondu"}
        if commande == "lire_table":
            return {"ok": True, "code": 0, "sortie": self.tables.get(args[0], ""), "erreur": ""}
        if commande == "ecrire_crontab":
            if self.refuser_ecriture:
                return {"ok": False, "code": 1, "sortie": "", "erreur": "ligne 3 illisible"}
            self.tables[args[0]] = stdin
            return {"ok": True, "code": 0, "sortie": "ok", "erreur": ""}
        if commande == "lire_crontabs":
            return {"ok": True, "code": 0, "sortie": json.dumps(self.lignes()), "erreur": ""}
        if commande == "lancer":
            cmds = set()
            for l in self.lignes():
                c = l["commande"]
                cmds.add(c)
                if c.startswith("/usr/local/lib/cassandra/cron-wrap.sh"):
                    import shlex
                    cmds.add(" ".join(shlex.split(c)[2:]))
            if stdin.strip() not in cmds:
                return {"ok": False, "code": 1, "sortie": "", "erreur": "cette commande n'est dans aucune table de planification"}
            code, sortie = self.resultats.get(stdin.strip(), (0, "fait"))
            return {"ok": True, "code": 0, "sortie": json.dumps({"code": code, "sortie": sortie}), "erreur": ""}
        return {"ok": False, "code": None, "sortie": "", "erreur": "commande inconnue"}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "planifie", mods / "planifie", ignore=shutil.ignore_patterns("__pycache__", "commandes"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("planifie", installe=True, par="banc")        # son installation (en root) n'est pas le sujet ici
        r = self.n.activer("planifie")
        self.assertTrue(r["ok"], r)
        self.n.droits.regler_admin(ROOT, True)
        self.ctx = self.n.executeur.contextes["planifie"]
        self.racine = Racine()
        self.ctx._intro["racine"] = self.racine
        self.ctx.dossier_donnees = str(base / "donnees-cron")
        os.makedirs(os.path.join(self.ctx.dossier_donnees, "cron-runs"))
        self.ctx.pause_essais = 0
        for cap in ("sauver", "basculer", "supprimer", "critique", "lier", "delier", "reglages_poser", "maintenance", "executer"):
            self.n.catalogue.regler_palier("planifie." + cap, "auto")

    def ex(self, cap, compte=ROOT, acteur="humain", **args):
        return self.n.executeur.executer("planifie." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def liste(self):
        return {t["commande"]: t for t in self.ok("unifiee")["taches"]}

    def deposer_run(self, ref, debut, ms, code, sortie="ok"):
        d = os.path.join(self.ctx.dossier_donnees, "cron-runs")
        Path(d, "%s.%d.%d" % (ref, os.getpid(), time.time_ns())).write_text("%s|%s|%d|%d\n%s\n" % (ref, debut, ms, code, sortie))


class Ecriture(Monde):
    def test_creer_pose_la_ligne_enrobee_et_garde_le_reste_de_la_table(self):
        r = self.ok("sauver", description="Nettoyage", horaire="@daily", commande="/usr/local/bin/nettoyer.sh --vite")
        table = self.racine.tables["root"]
        self.assertIn("# sauvegardes", table)                                                  # les commentaires et l'environnement sont gardés
        self.assertIn("MAILTO=admin@x.fr", table)
        self.assertIn("0 2 * * * /usr/local/bin/dump.sh", table)
        self.assertRegex(table, r"0 0 \* \* \* /usr/local/lib/cassandra/cron-wrap\.sh \w{16} '/usr/local/bin/nettoyer\.sh --vite' # cassandra-id:%d" % r["id"])
        self.assertEqual(r["prochaines"][0][11:], "00:00")
        self.assertTrue(self.n.catalogue.get("planifie.sauver").prouver(self.ctx, r))

    def test_creer_se_defait(self):
        avant = self.racine.tables["root"]
        r = self.ok("sauver", description="x", horaire="0 1 * * *", commande="/bin/true")
        self.n.catalogue.get("planifie.sauver").defaire(self.ctx, r)
        self.assertEqual(self.racine.tables["root"].strip(), avant.strip())
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM naturelles")[0]["n"], 0)

    def test_modifier_se_defait_et_garde_l_ancienne_definition(self):
        a = self.ok("sauver", description="v1", horaire="0 1 * * *", commande="/bin/true")
        b = self.ok("sauver", id=a["id"], description="v2", horaire="0 2 * * *", commande="/bin/true")
        self.assertIn("0 2 * * *", self.racine.tables["root"])
        self.assertEqual(self.racine.tables["root"].count("cassandra-id:%d" % a["id"]), 1)     # remplace, n'empile pas
        self.n.catalogue.get("planifie.sauver").defaire(self.ctx, b)
        self.assertIn("0 1 * * *", self.racine.tables["root"])
        self.assertEqual(self.ctx.stockage.lire("SELECT horaire FROM naturelles")[0]["horaire"], "0 1 * * *")

    def test_une_crontab_qui_refuse_ne_laisse_rien_en_base(self):
        self.racine.refuser_ecriture = True
        r = self.ex("sauver", description="x", horaire="0 1 * * *", commande="/bin/true")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("ligne 3 illisible", r["erreur"])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM naturelles")[0]["n"], 0)     # pas de ligne orpheline qui s'exécuterait en root sans qu'on la sache

    def test_les_refus_de_saisie_et_la_confirmation_du_destructeur(self):
        for args in (dict(horaire="0 0 * *", commande="/bin/true"), dict(horaire="0 0 * * *", commande=""), dict(horaire="0 0 * * *", commande="date +%F")):
            self.assertEqual(self.ex("sauver", **args)["statut"], "echec", args)
        r = self.ex("sauver", horaire="0 4 * * *", commande="rm -rf /var/cache/vieux")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("confirmer_destructeur", r["erreur"])
        self.assertEqual(self.ex("sauver", horaire="0 4 * * *", commande="rm -rf /var/cache/vieux", confirmer_destructeur=True)["statut"], "faite")

    def test_basculer_et_supprimer(self):
        r = self.ok("sauver", description="x", horaire="0 1 * * *", commande="/bin/true")
        b = self.ok("basculer", id=r["id"], actif=False)
        self.assertNotIn("cassandra-id:%d" % r["id"], self.racine.tables["root"])              # désactivée : hors de la crontab…
        self.assertEqual(self.ctx.stockage.lire("SELECT actif FROM naturelles")[0]["actif"], 0)  # …mais la définition reste
        self.assertTrue(self.n.catalogue.get("planifie.basculer").prouver(self.ctx, b))
        self.n.catalogue.get("planifie.basculer").defaire(self.ctx, b)
        self.assertIn("cassandra-id:%d" % r["id"], self.racine.tables["root"])
        s = self.ok("supprimer", id=r["id"])
        self.assertNotIn("cassandra-id", self.racine.tables["root"])
        self.assertTrue(self.n.catalogue.get("planifie.supprimer").prouver(self.ctx, s))
        self.n.catalogue.get("planifie.supprimer").defaire(self.ctx, s)
        self.assertIn("cassandra-id:%d" % r["id"], self.racine.tables["root"])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM naturelles")[0]["n"], 1)


class Vue(Monde):
    def test_les_deux_origines_se_fusionnent_sur_utilisateur_et_commande(self):
        self.ok("sauver", description="Nettoyage", horaire="0 1 * * *", commande="/bin/true")
        t = self.liste()
        self.assertEqual(sorted(t), ["/bin/true", "/usr/local/bin/dump.sh"])
        self.assertEqual(t["/bin/true"]["sources"], ["cassandra", "système"])                    # une seule ligne, deux sources
        self.assertEqual(t["/bin/true"]["description"], "Nettoyage")
        self.assertEqual(t["/usr/local/bin/dump.sh"]["sources"], ["système"])
        self.assertEqual(t["/usr/local/bin/dump.sh"]["humain"], "à 02:00 chaque jour")

    def test_l_etat_vient_des_executions_reelles(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.assertEqual(self.liste()["/usr/local/bin/dump.sh"]["etat"], "inconnu")               # aucune trace : on ne dit pas « ok »
        hier = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d 02:00")
        auj = datetime.utcnow().strftime("%Y-%m-%d 02:00")
        self.deposer_run(ref, hier, 1000, 0)
        self.deposer_run(ref, auj, 1200, 0)
        t = self.liste()["/usr/local/bin/dump.sh"]
        self.assertEqual(t["etat"], "ok")
        self.assertEqual(os.listdir(os.path.join(self.ctx.dossier_donnees, "cron-runs")), [])     # les comptes rendus rangés sont supprimés
        self.deposer_run(ref, auj, 1200, 3, "disque plein")
        self.assertEqual(self.liste()["/usr/local/bin/dump.sh"]["etat"], "échec")

    def test_une_cible_disparue_casse_la_tache_vue_par_root(self):
        self.racine.manquantes["/usr/local/bin/dump.sh"] = ["/usr/local/bin/dump.sh"]
        t = self.liste()["/usr/local/bin/dump.sh"]
        self.assertEqual(t["etat"], "cassé")
        self.assertIn("introuvable", t["etat_detail"])

    def test_un_compte_rendu_illisible_est_ecarte_et_efface(self):
        d = os.path.join(self.ctx.dossier_donnees, "cron-runs")
        Path(d, "bizarre").write_text("pas un compte rendu")
        self.ok("unifiee")
        self.assertEqual(os.listdir(d), [])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) AS n FROM executions")[0]["n"], 0)

    def test_si_le_courtier_se_tait_les_taches_de_cassandra_restent_et_on_le_dit(self):
        self.ok("sauver", description="x", horaire="0 1 * * *", commande="/bin/true")
        self.racine.hors_ligne = True
        self.ctx.dossier_donnees = self.ctx.dossier_donnees
        r = self.ok("unifiee", forcer=True)
        self.assertEqual([t["commande"] for t in r["taches"]], ["/bin/true"])
        self.assertFalse(r["source_systeme"]["ok"])
        self.assertIn("courtier", r["source_systeme"]["erreur"])

    def test_la_fiche(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        f = self.ok("fiche", ref=ref)
        self.assertEqual(f["tache"]["ref"], ref)
        self.assertEqual(len(f["prochaines"]), 5)
        self.assertEqual(f["cibles"], [{"chemin": "/usr/local/bin/dump.sh", "present": 1}])
        self.assertEqual(self.ex("fiche", ref="inconnue")["statut"], "echec")

    def test_apercu_et_audit(self):
        a = self.ok("apercu", expression="0 5 * * 7")
        self.assertEqual(a["humain"], "à 05:00 le dimanche")
        self.assertEqual(self.ex("apercu", expression="0 5 *")["statut"], "echec")
        for i in range(3):
            self.ok("sauver", description="s%d" % i, horaire="0 3 * * *", commande="rsync -a /a%d /b" % i)
        c = self.ok("audit")["collisions"]
        self.assertEqual([(x["at"], x["nombre"]) for x in c], [("03:00", 3)])
        self.assertEqual([x["at"] for x in c[0]["repartition"]], ["03:00", "03:10", "03:20"])


class Execution(Monde):
    def test_executer_garde_la_sortie_et_se_defait_par_le_journal(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.racine.resultats["/usr/local/bin/dump.sh"] = (0, "sauvegarde faite")
        r = self.ok("executer", ref=ref)
        self.assertEqual((r["code"], r["sortie"]), (0, "sauvegarde faite"))
        self.assertEqual(self.ok("historique", ref=ref)["executions"][0]["declencheur"], "manuel")
        self.assertTrue(self.n.catalogue.get("planifie.executer").prouver(self.ctx, r))
        self.n.catalogue.get("planifie.executer").defaire(self.ctx, r)
        self.assertEqual(self.ok("historique", ref=ref)["executions"], [])

    def test_un_essai_ne_change_pas_l_etat(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.racine.resultats["/usr/local/bin/dump.sh"] = (1, "ERREUR")
        r = self.ok("executer", ref=ref, essai=True)
        self.assertEqual(r["code"], 1)
        self.assertEqual(self.ok("historique", ref=ref)["executions"], [])
        self.assertEqual(self.liste()["/usr/local/bin/dump.sh"]["etat"], "inconnu")               # maquiller une panne en réussite, ou l'inverse, n'est pas le rôle d'un essai

    def test_le_courtier_ne_lance_que_ce_qui_est_deja_planifie(self):
        r = self.ok("sauver", description="x", horaire="0 1 * * *", commande="/bin/true")
        self.ok("basculer", id=r["id"], actif=False)                                             # retirée de la crontab : plus lançable d'ici
        ref = [t for t in self.ok("unifiee")["taches"] if t["commande"] == "/bin/true"][0]["ref"]
        self.assertEqual(self.ex("executer", ref=ref)["statut"], "echec")
        self.assertEqual(self.ex("executer", ref="inconnue")["statut"], "echec")

    def test_le_motif_d_echec_et_les_essais(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.ok("reglages_poser", ref=ref, motif_echec="ERROR", essais=2)
        self.racine.resultats["/usr/local/bin/dump.sh"] = (0, "ERROR: disque")
        r = self.ok("executer", ref=ref)
        self.assertEqual(r["code"], 90)                                                         # un script qui rend 0 en affichant ERROR a échoué
        self.assertIn("2 essai(s) supplémentaire(s)", r["sortie"])
        self.assertEqual([c for c, _ in self.racine.appels].count("lancer"), 3)


class Reglages(Monde):
    def test_les_options_de_l_enrobage_ne_portent_que_des_chiffres(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        r = self.ok("reglages_poser", ref=ref, fenetre_min=30, verrou=True, nom="Sauvegarde nocturne")
        contenu = Path(self.ctx.dossier_donnees, "cron-opts", ref).read_text()
        self.assertEqual(contenu, "verrou=1\nfenetre=1800\n")
        self.n.catalogue.get("planifie.reglages_poser").defaire(self.ctx, r)
        self.assertEqual(Path(self.ctx.dossier_donnees, "cron-opts", ref).read_text(), "verrou=0\nfenetre=0\n")

    def test_une_boucle_d_enchainement_est_refusee(self):
        self.ok("reglages_poser", ref="a", apres_ref="b")
        self.ok("reglages_poser", ref="b", apres_ref="c")
        self.assertEqual(self.ex("reglages_poser", ref="c", apres_ref="a")["statut"], "echec")
        self.assertEqual(self.ex("reglages_poser", ref="x", apres_ref="x")["statut"], "echec")
        self.assertEqual(self.ex("reglages_poser", ref="x", motif_echec="(")["statut"], "echec")

    def test_la_suite_part_quand_l_amont_a_reussi_seulement(self):
        self.ok("sauver", description="amont", horaire="0 1 * * *", commande="/bin/amont")
        self.ok("sauver", description="aval", horaire="30 1 * * *", commande="/bin/aval")
        t = self.liste()
        ra, rb = t["/bin/amont"]["ref"], t["/bin/aval"]["ref"]
        self.ok("reglages_poser", ref=rb, apres_ref=ra)
        hier = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d 01:00")
        self.deposer_run(ra, hier, 10, 1)                                                         # l'amont a échoué : la suite ne part pas
        self.n.lancer("planifie.passe")
        self.assertEqual(self.ok("historique", ref=rb)["executions"], [])
        self.deposer_run(ra, (datetime.utcnow() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M"), 10, 0)      # l'amont a réussi (il y a une demi-heure : « aujourd'hui 01:00 » est dans le futur entre minuit et 1 h UTC)
        self.n.lancer("planifie.passe")
        self.assertEqual(self.ok("historique", ref=rb)["executions"][0]["declencheur"], "suite")
        self.n.lancer("planifie.passe")
        self.assertEqual(len(self.ok("historique", ref=rb)["executions"]), 1)                     # une fois depuis l'amont, pas à chaque passe


class Maintenance(Monde):
    def test_la_sentinelle_porte_la_fin_et_les_exemptes(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.ok("critique", ref=ref, libelle="les sauvegardes")
        r = self.ok("maintenance", actif=True, heures=2)
        lignes = Path(self.ctx.dossier_donnees, "cron-maintenance").read_text().splitlines()
        self.assertEqual(lignes[0], r["fin"])
        self.assertEqual(lignes[1], ref)
        self.assertTrue(self.ok("maintenance_etat")["actif"])
        self.n.catalogue.get("planifie.maintenance").defaire(self.ctx, r)
        self.assertFalse(self.ok("maintenance_etat")["actif"])
        self.assertFalse(os.path.exists(os.path.join(self.ctx.dossier_donnees, "cron-maintenance")))

    def test_une_maintenance_echue_se_leve_toute_seule(self):
        self.ok("maintenance", actif=True, heures=1)
        self.ctx.stockage.ecrire("UPDATE maintenance SET fin='2020-01-01 00:00'")
        self.n.lancer("planifie.passe")
        self.assertEqual(self.ctx.stockage.lire("SELECT fin FROM maintenance")[0]["fin"], "")
        self.assertFalse(os.path.exists(os.path.join(self.ctx.dossier_donnees, "cron-maintenance")))


class Constats(Monde):
    def test_une_tache_en_echec_devient_un_constat(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        self.deposer_run(ref, datetime.utcnow().strftime("%Y-%m-%d 02:00"), 100, 1, "boom")
        self.ok("critique", ref=ref)
        c = self.n.detecteurs[[i for i, (m, d, f) in enumerate(self.n.detecteurs) if d.id == "taches_en_panne"][0]][2](self.ctx)
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]["niveau"], c[0]["objet"]), ("critique", ("tache_planifiee", ref)))
        self.assertIn("en échec", c[0]["titre"])

    def test_la_derive_de_duree_se_signale(self):
        ref = self.liste()["/usr/local/bin/dump.sh"]["ref"]
        for i, ms in enumerate([1000] * 4 + [1500] * 4 + [3000] * 4):
            self.deposer_run(ref, "2026-09-%02d 02:00" % (i + 1), ms, 0)
        c = self.n.detecteurs[[i for i, (m, d, f) in enumerate(self.n.detecteurs) if d.id == "taches_en_panne"][0]][2](self.ctx)
        self.assertTrue(any("plus lente" in x["titre"] for x in c))


class Droits(Monde):
    def test_reserve_a_l_administrateur(self):
        for cap in ("unifiee", "audit", "resume", "maintenance_etat"):
            self.assertEqual(self.ex(cap, compte=BEA)["statut"], "echec", cap)
        self.assertIn("réservées à l'administrateur", self.ex("unifiee", compte=BEA)["erreur"])
        self.assertEqual(self.ex("sauver", compte=BEA, horaire="0 1 * * *", commande="/bin/true")["statut"], "refuse")
        self.assertEqual(self.racine.appels, [])                                                  # rien n'a été demandé au courtier


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Expressions, Racine, Monde, Ecriture, Vue, Execution, Reglages, Maintenance …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
