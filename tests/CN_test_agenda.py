"""Bancs du module agenda."""
import base64
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402

BEA, LEO = "bea@x.fr", "leo@x.fr"
J = lambda n: (datetime.now() + timedelta(days=n)).strftime("%Y-%m-%d")
D = lambda n, h="09:00": "%s %s" % (J(n), h)


class FauxCalDav:
    """Un serveur CalDAV qui répond à REPORT et note ce qu'il reçoit."""

    def __init__(self, ics="", statut=207):
        self.ics, self.statut, self.requetes = ics, statut, []
        faux = self

        class H(BaseHTTPRequestHandler):
            def do_REPORT(self):
                n = int(self.headers.get("Content-Length") or 0)
                faux.requetes.append({"auth": self.headers.get("Authorization", ""), "depth": self.headers.get("Depth", ""), "corps": self.rfile.read(n).decode()})
                corps = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response><d:propstat><d:prop><c:calendar-data>%s</c:calendar-data></d:prop></d:propstat></d:response></d:multistatus>'
                         % faux.ics.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")).encode()
                self.send_response(faux.statut)
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "agenda", mods / "agenda", ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("agenda")["ok"])
        self.ctx = self.n.executeur.contextes["agenda"]
        self.db = self.ctx.stockage
        self.glob = self.n.catalogue.get("agenda.rappels").faire.__globals__
        self.taches, self.jalons = [], {}
        self.ctx.executer_lecture = self.lecture

    def lecture(self, cap, **a):
        if cap == "taches.lister":
            return {"taches": self.taches}
        if cap == "taches.fiche":
            for t in self.taches:
                if t["id"] == int(a["id"]):
                    return {"tache": t}
            raise ValueError("tâche introuvable")
        if cap == "projets.equipe":
            if int(a["id"]) == 7:
                return {"projet": "Refonte", "mon_role": "auteur"}
            raise ValueError("projet introuvable")
        if cap == "projets.lister":
            return {"projets": [{"id": 7, "nom": "Refonte"}]}
        if cap == "projets.voir":
            return {"jalons": self.jalons.get(int(a["id"]), [])}
        if cap == "notes.fiche":
            return {"titre": "Compte rendu", "etat_n": "En cours"}
        if cap == "contacts.voir":
            return {"display_name": "Claire Mercier", "company": "Proche", "job_title": "DG"}
        raise ValueError("lecture inconnue " + cap)

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("agenda." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "echec", r)
        return r["erreur"]

    def retour(self, cap, res):
        self.n.catalogue.get("agenda." + cap).defaire(self.ctx, res)

    def evt(self, titre="Réunion", debut=None, compte=BEA, **kw):
        return self.ok("evenement_enregistrer", titre=titre, debut=debut or D(3, "14:00"), compte=compte, **kw)["id"]

    def fiche(self, eid, compte=BEA):
        return self.ok("evenement", id=eid, compte=compte)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]


class Cycle(Monde):
    def test_creer_prouve_journalise_et_se_defait(self):
        r = self.ex("evenement_enregistrer", titre="Réunion", debut=D(3, "14:00"), fin=D(3, "15:30"), lieu="Salle 2", description="ordre du jour", projet_id=7, alarme="15m", url="https://visio.example/x")
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(r["resultat"]["id"])
        e = f["evenement"]
        self.assertEqual((e["titre"], e["debut"], e["fin"], e["journee"], e["lieu"], e["alarme"], e["source"]), ("Réunion", D(3, "14:00"), D(3, "15:30"), 0, "Salle 2", "15m", "manuel"))
        self.assertEqual(f["projet"], {"id": 7, "nom": "Refonte"})
        self.assertEqual(f["journal"][0]["texte"], "Créé")
        self.assertEqual(len(self.evts("evenement.cree")), 1)
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.retour("evenement_enregistrer", r["resultat"])
        self.assertEqual(self.ok("evenements", du=J(0), au=J(10))["evenements"], [])

    def test_une_date_seule_est_une_journee_et_la_journee_se_force(self):
        e = self.fiche(self.evt("Congé", J(5)))["evenement"]
        self.assertEqual((e["debut"], e["journee"]), (J(5), 1))
        e2 = self.fiche(self.evt("Appel", J(5), journee=False))["evenement"]
        self.assertEqual((e2["debut"], e2["journee"]), (J(5) + " 09:00", 0))
        e3 = self.fiche(self.evt("Séminaire", D(5, "10:00"), fin=D(6, "16:00"), journee=True))["evenement"]
        self.assertEqual((e3["debut"], e3["fin"], e3["journee"]), (J(5), J(6), 1))

    def test_deplacer_et_renommer_se_racontent_et_le_retour_les_efface(self):
        eid = self.evt("Point", D(3, "10:00"))
        r1 = self.ex("evenement_enregistrer", id=eid, debut=D(4, "10:00"))
        self.ok("evenement_enregistrer", id=eid, titre="Point hebdo")
        j = [x["texte"] for x in self.fiche(eid)["journal"]]
        self.assertEqual(j[0], "Renommé — « Point hebdo »")
        self.assertEqual(j[1], "Déplacé du %s au %s" % (D(3, "10:00"), D(4, "10:00")))
        self.retour("evenement_enregistrer", r1["resultat"])
        f = self.fiche(eid)
        self.assertEqual(f["evenement"]["debut"], D(3, "10:00"))
        self.assertEqual([x["texte"] for x in f["journal"]], ["Renommé — « Point hebdo »", "Créé"])

    def test_la_modification_est_un_patch(self):
        eid = self.evt("Point", D(3, "10:00"), lieu="Bureau", description="x", alarme="1h")
        self.ok("evenement_enregistrer", id=eid, lieu="Salle")
        e = self.fiche(eid)["evenement"]
        self.assertEqual((e["titre"], e["lieu"], e["description"], e["alarme"], e["debut"]), ("Point", "Salle", "x", "1h", D(3, "10:00")))
        self.ok("evenement_enregistrer", id=eid, alarme="")
        self.assertEqual(self.fiche(eid)["evenement"]["alarme"], "")

    def test_les_refus(self):
        base = dict(titre="x", debut=D(3, "10:00"))
        for args in (dict(base, titre=" "), dict(base, debut=""), dict(base, debut="un jour"), dict(base, fin=D(2, "10:00")), dict(base, recurrence="tous les mardis"),
                     dict(base, recurrence="FREQ=MONTHLY;BYMONTHDAY=15"), dict(base, alarme="bientôt"), dict(base, url="ftp://x"), dict(base, url="javascript:alert(1)"), dict(base, projet_id=99)):
            self.assertEqual(self.ex("evenement_enregistrer", **args)["statut"], "echec", args)
        for compte in ("", "cassandra", "itare"):
            self.assertEqual(self.ex("evenement_enregistrer", compte=compte, **base)["statut"], "echec")
        self.assertEqual(self.ex("evenement_enregistrer", id=99, titre="x")["statut"], "echec")

    def test_l_agenda_d_un_compte_n_est_pas_a_un_autre(self):
        eid = self.evt("Rendez-vous privé")
        for cap, args in (("evenement", {}), ("evenement_enregistrer", dict(titre="piraté")), ("evenement_supprimer", {}), ("lien_ajouter", dict(kind="url", ref="http://x.fr")), ("lien_retirer", dict(kind="url", ref="x"))):
            self.assertEqual(self.ex(cap, id=eid, compte=LEO, **args)["statut"], "echec", cap)
        self.assertEqual(self.ok("evenements", du=J(0), au=J(30), compte=LEO)["evenements"], [])
        self.assertEqual(self.fiche(eid)["evenement"]["titre"], "Rendez-vous privé")

    def test_supprimer_emporte_liens_et_journal_et_le_retour_les_rend(self):
        eid = self.evt("Réunion")
        self.ok("lien_ajouter", id=eid, kind="url", ref="http://x.fr", label="ordre du jour")
        self.ok("lien_ajouter", id=eid, kind="tache", ref="5")
        r = self.ex("evenement_supprimer", id=eid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.db.lire("SELECT (SELECT COUNT(*) FROM liens) + (SELECT COUNT(*) FROM journal) + (SELECT COUNT(*) FROM evenements) AS n")[0]["n"], 0)
        self.retour("evenement_supprimer", r["resultat"])
        f = self.fiche(eid)
        self.assertEqual((len(f["liens"]), f["evenement"]["titre"]), (2, "Réunion"))
        self.assertGreaterEqual(len(f["journal"]), 2)


class Liens(Monde):
    def test_les_liens_portent_l_etat_de_ce_qu_ils_designent(self):
        eid = self.evt()
        self.taches.append({"id": 5, "texte": "Préparer le dossier", "statut": "fait", "echeance": D(2), "projet": "Refonte"})
        self.taches.append({"id": 6, "texte": "Imprimer", "statut": "todo", "echeance": D(2, "10:00"), "projet": ""})
        for kind, ref in (("tache", "5"), ("tache", "6"), ("contact", "12"), ("note", "N-0003"), ("projet", "7"), ("serveur", "web1")):
            self.ok("lien_ajouter", id=eid, kind=kind, ref=ref)
        f = self.fiche(eid)
        par = {(l["kind"], l["ref"]): l for l in f["liens"]}
        self.assertEqual((par[("tache", "5")]["nom"], par[("tache", "5")]["fait"]), ("Préparer le dossier", 1))
        self.assertEqual((par[("contact", "12")]["nom"], par[("contact", "12")]["detail"]), ("Claire Mercier", "Proche · DG"))
        self.assertEqual((par[("note", "N-0003")]["nom"], par[("projet", "7")]["nom"], par[("serveur", "web1")]["nom"]), ("Compte rendu", "Refonte", "web1"))
        self.assertEqual(f["prep"], {"total": 2, "faites": 1})

    def test_ajouter_normalise_le_domaine_ne_double_pas_et_se_defait(self):
        eid = self.evt()
        r = self.ex("lien_ajouter", id=eid, kind="domaine", ref="https://www.Exemple.fr/accueil", label="Le site")
        self.assertEqual((r["statut"], r["resultat"]["ref"]), ("faite", "exemple.fr"))
        self.assertTrue(self.ok("lien_ajouter", id=eid, kind="domaine", ref="exemple.fr")["existait"])
        self.assertEqual(len(self.fiche(eid)["liens"]), 1)
        self.assertIn("Rattaché — domaine « Le site »", [x["texte"] for x in self.fiche(eid)["journal"]])
        self.retour("lien_ajouter", r["resultat"])
        self.assertEqual(self.fiche(eid)["liens"], [])
        for args in (dict(kind="inconnu", ref="x"), dict(kind="url", ref="")):
            self.assertEqual(self.ex("lien_ajouter", id=eid, **args)["statut"], "echec", args)

    def test_une_tache_liee_n_ajoute_pas_de_ligne_au_journal(self):
        eid = self.evt()
        self.ok("lien_ajouter", id=eid, kind="tache", ref="5")
        self.assertEqual([x["texte"] for x in self.fiche(eid)["journal"]], ["Créé"])

    def test_retirer_et_son_retour(self):
        eid = self.evt()
        self.ok("lien_ajouter", id=eid, kind="contact", ref="12", label="Claire")
        r = self.ex("lien_retirer", id=eid, kind="contact", ref="12")
        self.assertEqual(self.fiche(eid)["liens"], [])
        self.retour("lien_retirer", r["resultat"])
        self.assertEqual(self.fiche(eid)["liens"][0]["label"], "Claire")
        self.assertEqual(self.ex("lien_retirer", id=eid, kind="contact", ref="99")["statut"], "echec")


class Recurrence(Monde):
    def occ(self, regle, debut, du, au, journee=0):
        f = self.glob["occurrences"]
        d = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M")
        return f(regle, debut, journee, d(du + " 00:00"), d(au + " 23:59"))

    def test_une_serie_ancienne_atteint_aujourd_hui_malgre_le_plafond(self):
        s, m = self.occ("FREQ=DAILY", "2023-01-01 08:00", "2026-10-10", "2026-10-12")
        self.assertEqual((s, m), (["2026-10-10 08:00", "2026-10-11 08:00", "2026-10-12 08:00"], ""))
        s, _ = self.occ("FREQ=WEEKLY;BYDAY=MO,WE", "2022-01-03 09:00", "2026-10-12", "2026-10-18")
        self.assertEqual(s, ["2026-10-12 09:00", "2026-10-14 09:00"])
        s, _ = self.occ("FREQ=DAILY;INTERVAL=3", "2026-10-01 08:00", "2026-10-06", "2026-10-13")
        self.assertEqual(s, ["2026-10-07 08:00", "2026-10-10 08:00", "2026-10-13 08:00"])

    def test_un_mois_court_ne_decale_pas_les_suivants(self):
        s, _ = self.occ("FREQ=MONTHLY", "2026-01-31 10:00", "2026-01-01", "2026-04-30")
        self.assertEqual(s, ["2026-01-31 10:00", "2026-02-28 10:00", "2026-03-31 10:00", "2026-04-30 10:00"])
        s, _ = self.occ("FREQ=YEARLY", "2024-02-29 08:00", "2025-01-01", "2028-12-31")
        self.assertEqual(s, ["2025-02-28 08:00", "2026-02-28 08:00", "2027-02-28 08:00", "2028-02-29 08:00"])

    def test_count_until_et_la_borne_de_la_plage(self):
        s, _ = self.occ("FREQ=DAILY;COUNT=3", "2026-10-01 08:00", "2026-01-01", "2026-12-31")
        self.assertEqual(len(s), 3)
        s, _ = self.occ("FREQ=WEEKLY;BYDAY=MO,TH;COUNT=3", "2026-10-05 08:00", "2026-01-01", "2026-12-31")
        self.assertEqual(s, ["2026-10-05 08:00", "2026-10-08 08:00", "2026-10-12 08:00"])
        s, _ = self.occ("FREQ=DAILY;UNTIL=20261003", "2026-10-01 08:00", "2026-01-01", "2026-12-31")
        self.assertEqual(s, ["2026-10-01 08:00", "2026-10-02 08:00", "2026-10-03 08:00"])      # UNTIL inclut son jour
        s, _ = self.occ("FREQ=DAILY;COUNT=10", "2026-10-01 08:00", "2026-10-05", "2026-10-06")
        self.assertEqual(s, ["2026-10-05 08:00", "2026-10-06 08:00"])                           # COUNT compte depuis le début de la série, pas depuis la plage
        s, _ = self.occ("FREQ=DAILY", "2026-10-20 08:00", "2026-10-01", "2026-10-10")
        self.assertEqual(s, [])

    def test_une_regle_non_geree_est_dite(self):
        for regle, mot in (("FREQ=MONTHLY;BYMONTHDAY=15", "BYMONTHDAY"), ("FREQ=HOURLY", "HOURLY"), ("COUNT=3", "FREQ"), ("FREQ=MONTHLY;BYDAY=MO", "BYDAY"), ("FREQ=DAILY;BYMONTH=3", "BYMONTH")):
            s, m = self.occ(regle, "2026-10-01 08:00", "2026-10-01", "2026-10-31")
            self.assertEqual(s, [], regle)
            self.assertIn(mot, m)

    def test_les_evenements_se_repetent_a_la_lecture_avec_leur_duree(self):
        eid = self.evt("Stand-up", D(-30, "09:00"), fin=D(-30, "09:15"), recurrence="weekly")
        ev = self.ok("evenements", du=J(0), au=J(14))["evenements"]
        self.assertEqual(len(ev), 2)
        self.assertTrue(all(e["id"] == eid and e["occurrence_de"] == eid for e in ev))
        a, b = datetime.strptime(ev[0]["debut"], "%Y-%m-%d %H:%M"), datetime.strptime(ev[0]["fin"], "%Y-%m-%d %H:%M")
        self.assertEqual(b - a, timedelta(minutes=15))
        self.assertEqual((datetime.strptime(ev[1]["debut"], "%Y-%m-%d %H:%M") - a).days, 7)
        self.assertEqual(len(self.fiche(eid)["prochaines"]), 6)

    def test_les_formes_de_recurrence_acceptees(self):
        for rec in ("daily", "Weekly", "mensuel", "RRULE:FREQ=WEEKLY;BYDAY=MO", "FREQ=YEARLY"):
            e = self.fiche(self.evt("x", recurrence=rec))["evenement"]
            self.assertTrue(e["recurrence"].startswith("FREQ="), rec)
        self.ok("evenement_enregistrer", id=1, recurrence="")
        self.assertEqual(self.fiche(1)["evenement"]["recurrence"], "")

    def test_un_evenement_simple_hors_plage_n_apparait_pas(self):
        self.evt("Dans la plage", D(2))
        self.evt("Hors plage", D(120))
        self.assertEqual([e["titre"] for e in self.ok("evenements", du=J(0), au=J(10))["evenements"]], ["Dans la plage"])
        self.assertEqual(len(self.ok("evenements")["evenements"]), 1)                         # sans bornes : aujourd'hui et 90 jours
        self.assertEqual(self.echec("evenements", du="demain"), "date attendue au format AAAA-MM-JJ")
        self.assertIn("précède", self.echec("evenements", du=J(5), au=J(1)))


class Ical(Monde):
    ICS = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
           "BEGIN:VEVENT\r\nUID:a@x\r\nSUMMARY:Réunion\\, importante\r\nDESCRIPTION:Ligne un\\nLigne deux avec une très très très très très très très longue suite qui doit\r\n  se déplier sans rien perdre\r\n"
           "LOCATION:Salle\\; 2\r\nDTSTART:20261020T140000\r\nDTEND:20261020T150000\r\nURL:https://visio.example/x\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:b@x\r\nSUMMARY:Congé\r\nDTSTART;VALUE=DATE:20261105\r\nDTEND;VALUE=DATE:20261106\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:c@x\r\nSUMMARY:Stand-up\r\nDTSTART:20261001T090000\r\nRRULE:FREQ=WEEKLY;BYDAY=MO\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:d@x\r\nSUMMARY:Loyer\r\nDTSTART:20261003T090000\r\nRRULE:FREQ=MONTHLY;BYMONTHDAY=3\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nSUMMARY:Sans uid\r\nDTSTART:20261201T100000\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:z@x\r\nDTSTART:20261201T100000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")

    def par_titre(self):
        return {e["titre"]: e for e in self.ok("evenements", du="2026-10-01", au="2026-12-31")["evenements"]}

    def test_importer_lit_dates_journees_echappements_lignes_pliees_et_recurrences(self):
        r = self.ex("ical_importer", texte=self.ICS, etiquette="agenda perso")
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual((len(res["crees"]), res["total"], res["mises_a_jour"]), (5, 5, []))          # le VEVENT sans titre est ignoré
        e = self.db.lire("SELECT * FROM evenements WHERE uid='a@x'")[0]
        self.assertEqual((e["titre"], e["lieu"], e["debut"], e["fin"], e["source"], e["url"]), ("Réunion, importante", "Salle; 2", "2026-10-20 14:00", "2026-10-20 15:00", "ical:agenda perso", "https://visio.example/x"))
        self.assertIn("Ligne un\nLigne deux", e["description"])
        self.assertIn("doit se déplier", e["description"].replace("  ", " "))
        j = self.db.lire("SELECT * FROM evenements WHERE uid='b@x'")[0]
        self.assertEqual((j["debut"], j["journee"]), ("2026-11-05", 1))
        self.assertEqual(self.db.lire("SELECT recurrence FROM evenements WHERE uid='c@x'")[0]["recurrence"], "FREQ=WEEKLY;BYDAY=MO")
        self.assertEqual(len(self.db.lire("SELECT * FROM evenements WHERE titre='Stand-up'")), 1)    # une ligne pour la série, pas une par occurrence
        stand = [e for e in self.ok("evenements", du="2026-10-01", au="2026-10-31")["evenements"] if e["titre"] == "Stand-up"]
        self.assertEqual([e["debut"][:10] for e in stand], ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"])    # le 1er octobre est un jeudi : la série commence au premier lundi

    def test_une_regle_non_geree_garde_l_evenement_de_base_et_le_dit(self):
        res = self.ok("ical_importer", texte=self.ICS)
        self.assertEqual(len(res["avertissements"]), 1)
        self.assertIn("BYMONTHDAY", res["avertissements"][0])
        self.assertIn("Loyer", res["avertissements"][0])
        self.assertEqual(self.db.lire("SELECT recurrence FROM evenements WHERE titre='Loyer'")[0]["recurrence"], "")
        self.assertEqual(len([e for e in self.ok("evenements", du="2026-10-01", au="2026-12-31")["evenements"] if e["titre"] == "Loyer"]), 1)

    def test_reimporter_met_a_jour_au_lieu_de_dupliquer_et_le_retour_remet_l_etat_d_avant(self):
        self.ok("ical_importer", texte=self.ICS)
        avant = self.db.lire("SELECT COUNT(*) AS n FROM evenements")[0]["n"]
        neuf = self.ICS.replace("SUMMARY:Congé", "SUMMARY:Congé posé")
        r = self.ex("ical_importer", texte=neuf)
        res = r["resultat"]
        self.assertEqual((len(res["crees"]), len(res["mises_a_jour"])), (0, 5))
        self.assertEqual(self.db.lire("SELECT COUNT(*) AS n FROM evenements")[0]["n"], avant)
        self.assertEqual(self.db.lire("SELECT titre FROM evenements WHERE uid='b@x'")[0]["titre"], "Congé posé")
        self.retour("ical_importer", res)
        self.assertEqual(self.db.lire("SELECT titre FROM evenements WHERE uid='b@x'")[0]["titre"], "Congé")

    def test_le_retour_d_un_premier_import_retire_ce_qu_il_a_cree(self):
        r = self.ex("ical_importer", texte=self.ICS)
        self.retour("ical_importer", r["resultat"])
        self.assertEqual(self.db.lire("SELECT COUNT(*) AS n FROM evenements")[0]["n"], 0)

    def test_les_refus_d_import(self):
        for texte in ("", "pas du tout un agenda", "BEGIN:VCALENDAR\r\nEND:VCALENDAR"):
            self.assertEqual(self.ex("ical_importer", texte=texte)["statut"], "echec", texte)
        self.glob["MAX_ICS"] = 100
        self.assertIn("trop gros", self.echec("ical_importer", texte=self.ICS))
        self.glob["MAX_ICS"] = 5 * 1024 * 1024
        self.glob["MAX_EVENEMENTS_ICS"] = 2
        self.assertIn("2 au plus", self.echec("ical_importer", texte=self.ICS))

    def test_un_import_ne_touche_que_le_compte_qui_agit(self):
        self.ok("ical_importer", texte=self.ICS)
        r = self.ok("ical_importer", texte=self.ICS, compte=LEO)
        self.assertEqual((len(r["crees"]), len(r["mises_a_jour"])), (5, 0))
        self.assertEqual(self.db.lire("SELECT COUNT(*) AS n FROM evenements WHERE compte=?", (BEA,))[0]["n"], 5)

    def test_l_heure_utc_est_ramenee_a_l_heure_locale(self):
        self.ok("ical_importer", texte="BEGIN:VEVENT\r\nUID:u\r\nSUMMARY:UTC\r\nDTSTART:20261020T090000Z\r\nEND:VEVENT")
        decalage = datetime.now() - datetime.now(timezone.utc).replace(tzinfo=None)
        attendu = datetime(2026, 10, 20, 9, 0) + timedelta(minutes=round(decalage.total_seconds() / 60.0))
        self.assertEqual(self.db.lire("SELECT debut FROM evenements WHERE uid='u'")[0]["debut"], attendu.strftime("%Y-%m-%d %H:%M"))

    def test_exporter_puis_reimporter_chez_un_autre_compte_redonne_les_memes_evenements(self):
        self.evt("Réunion; importante, très", D(3, "14:00"), fin=D(3, "15:00"), lieu="Salle 2", description="ligne un\nligne deux " + "mot " * 40, recurrence="weekly", url="https://visio.example/x")
        self.evt("Congé", J(9))
        x = self.ok("exporter_ics")
        self.assertEqual((x["mime"], x["evenements"]), ("text/calendar", 2))
        for ligne in x["contenu"].split("\r\n"):
            self.assertLessEqual(len(ligne.encode("utf-8")), 75, ligne)
        self.assertTrue(x["contenu"].startswith("BEGIN:VCALENDAR\r\n"))
        self.assertIn("DTSTART;VALUE=DATE:", x["contenu"])
        self.ok("ical_importer", texte=x["contenu"], compte=LEO)
        a = {e["titre"]: e for e in self.db.lire("SELECT * FROM evenements WHERE compte=?", (BEA,))}
        b = {e["titre"]: e for e in self.db.lire("SELECT * FROM evenements WHERE compte=?", (LEO,))}
        self.assertEqual(set(a), set(b))
        for t in a:
            for k in ("debut", "fin", "journee", "lieu", "description", "recurrence", "url"):
                self.assertEqual(a[t][k], b[t][k], (t, k))

    def test_exporter_borne_par_plage(self):
        self.evt("Proche", D(2))
        self.evt("Lointain", D(60))
        self.assertEqual(self.ok("exporter_ics", du=J(0), au=J(10))["evenements"], 1)
        self.assertEqual(self.ok("exporter_ics", compte=LEO)["evenements"], 0)


class Rappels(Monde):
    def test_creer_modifier_marquer_supprimer_et_les_retours(self):
        r = self.ex("rappel_enregistrer", texte="Appeler le notaire", echeance="+2h")
        self.assertEqual(r["statut"], "faite", r)
        rid = r["resultat"]["id"]
        self.assertEqual(self.ok("rappels")["rappels"][0]["statut"], "attente")
        self.assertEqual(len(self.evts("rappel.cree")), 1)
        m = self.ex("rappel_enregistrer", id=rid, texte="Appeler le notaire demain", echeance=J(1))
        self.assertEqual(self.ok("rappels")["rappels"][0]["echeance"], J(1) + " 09:00")
        self.retour("rappel_enregistrer", m["resultat"])
        self.assertEqual(self.ok("rappels")["rappels"][0]["texte"], "Appeler le notaire")
        s = self.ex("rappel_statut", id=rid, statut="fait")
        self.assertEqual(self.ok("rappels", inclure_faits=False)["rappels"], [])
        self.retour("rappel_statut", s["resultat"])
        self.assertEqual(len(self.ok("rappels", inclure_faits=False)["rappels"]), 1)
        d = self.ex("rappel_supprimer", id=rid)
        self.assertEqual(self.ok("rappels")["rappels"], [])
        self.retour("rappel_supprimer", d["resultat"])
        self.assertEqual(self.ok("rappels")["rappels"][0]["id"], rid)
        self.retour("rappel_enregistrer", r["resultat"])
        self.assertEqual(self.ok("rappels")["rappels"], [])

    def test_les_refus_et_le_cloisonnement(self):
        for args in (dict(texte=" "), dict(texte="x", echeance="un jour"), dict(texte="x", statut="presque")):
            self.assertEqual(self.ex("rappel_enregistrer", **args)["statut"], "echec", args)
        rid = self.ok("rappel_enregistrer", texte="Privé")["id"]
        for cap, args in (("rappel_enregistrer", dict(texte="piraté")), ("rappel_statut", dict(statut="fait")), ("rappel_supprimer", {})):
            self.assertEqual(self.ex(cap, id=rid, compte=LEO, **args)["statut"], "echec", cap)
        self.assertEqual(self.ok("rappels", compte=LEO)["rappels"], [])

    def test_l_ordre_met_les_faits_en_dernier_et_les_sans_date_apres_les_dates(self):
        a = self.ok("rappel_enregistrer", texte="sans date")["id"]
        b = self.ok("rappel_enregistrer", texte="tard", echeance=D(5))["id"]
        c = self.ok("rappel_enregistrer", texte="tôt", echeance=D(1))["id"]
        d = self.ok("rappel_enregistrer", texte="fait", echeance=D(0), statut="fait")["id"]
        self.assertEqual([r["id"] for r in self.ok("rappels")["rappels"]], [c, b, a, d])

    def test_un_rappel_echu_est_un_constat_qui_se_resout_une_fois_fait(self):
        echu = self.ok("rappel_enregistrer", texte="En retard", echeance=D(-1))["id"]
        self.ok("rappel_enregistrer", texte="Plus tard", echeance=D(2))
        self.ok("rappel_enregistrer", texte="Sans date")
        self.ok("rappel_enregistrer", texte="Chez Léo", echeance=D(-1), compte=LEO)
        self.n.tick()
        o = [e for e in self.evts("constat.ouvert") if e["donnees"]["titre"].startswith("Rappel : ")]
        self.assertEqual(sorted((e["compte"], e["donnees"]["titre"]) for e in o), [(BEA, "Rappel : En retard"), (LEO, "Rappel : Chez Léo")])
        self.ok("rappel_statut", id=echu, statut="fait")
        self.n.tick(__import__("time").time() + 4000)
        self.assertEqual(len([e for e in self.evts("constat.resolu")]), 1)


class Alarme(Monde):
    def test_un_evenement_avec_alarme_est_un_constat_de_l_alarme_au_debut(self):
        maintenant = datetime.now()
        self.evt("Dans dix minutes", (maintenant + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"), alarme="15m", lieu="Salle 2")
        self.evt("Dans une heure", (maintenant + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"), alarme="15m")
        self.evt("Sans alarme", (maintenant + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"))
        self.evt("Déjà commencé", (maintenant - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M"), alarme="15m")
        self.evt("Chez Léo", (maintenant + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"), alarme="15m", compte=LEO)
        self.n.tick()
        o = [e for e in self.evts("constat.ouvert") if e["donnees"]["titre"].startswith("Bientôt")]
        self.assertEqual(sorted((e["compte"], e["donnees"]["titre"]) for e in o), [(BEA, "Bientôt : Dans dix minutes"), (LEO, "Bientôt : Chez Léo")])
        self.assertIn("Salle 2", [e for e in o if e["compte"] == BEA][0]["donnees"]["detail"])

    def test_une_serie_avec_alarme_previent_pour_la_bonne_occurrence(self):
        maintenant = datetime.now()
        debut = (maintenant + timedelta(minutes=10)).strftime("%H:%M")
        self.evt("Stand-up", "%s %s" % (J(-14), debut), alarme="15m", recurrence="daily")
        self.n.tick()
        o = [e for e in self.evts("constat.ouvert") if e["donnees"]["titre"].startswith("Bientôt")]
        self.assertEqual(len(o), 1)


class Vue(Monde):
    def test_la_vue_rassemble_ce_qui_tombe_quand(self):
        self.evt("Réunion", D(2, "14:00"))
        self.taches[:] = [
            {"id": 1, "texte": "Livrer", "statut": "todo", "echeance": D(3, "10:00"), "projet": "Refonte", "responsable": ""},
            {"id": 2, "texte": "En retard", "statut": "en cours", "echeance": D(-4, "10:00"), "projet": "", "responsable": ""},
            {"id": 3, "texte": "Faite en retard", "statut": "fait", "echeance": D(-4, "10:00"), "projet": "", "responsable": ""},
            {"id": 4, "texte": "Pour Léo", "statut": "todo", "echeance": D(3, "11:00"), "projet": "", "responsable": LEO},
            {"id": 5, "texte": "Abandonnée", "statut": "abandonnee", "echeance": D(3, "12:00"), "projet": "", "responsable": ""},
            {"id": 6, "texte": "Sans date", "statut": "todo", "echeance": "", "projet": "", "responsable": ""},
            {"id": 7, "texte": "Lointaine", "statut": "todo", "echeance": D(80), "projet": "", "responsable": ""},
            {"id": 8, "texte": "À moi, nommée", "statut": "todo", "echeance": D(4, "08:00"), "projet": "", "responsable": BEA}]
        self.jalons[7] = [{"nom": "Maquette", "date": J(5), "etat": "prevu"}, {"nom": "Cadrage", "date": J(1), "etat": "tenu"}, {"nom": "Sans date", "date": "", "etat": "prevu"}]
        self.ok("rappel_enregistrer", texte="Appeler", echeance=D(1, "09:30"))
        self.ok("rappel_enregistrer", texte="Hors plage", echeance=D(60))
        v = self.ok("calendrier", du=J(0), au=J(10))
        titres = [e["titre"] for e in v["elements"]]
        self.assertEqual(titres, ["⚠ En retard", "✓ Cadrage — Refonte", "Appeler", "Réunion", "Livrer", "À moi, nommée", "◆ Maquette — Refonte"])
        retard = v["elements"][0]
        self.assertEqual((retard["kind"], retard["quand"], retard["retard"], retard["journee"]), ("task", J(0) + " 00:00", J(-4), 1))
        self.assertEqual({e["kind"] for e in v["elements"]}, {"task", "etape", "reminder", "event"})

    def test_une_tache_en_retard_n_est_collee_a_aujourd_hui_que_si_aujourd_hui_est_dans_la_plage(self):
        self.taches[:] = [{"id": 2, "texte": "En retard", "statut": "todo", "echeance": D(-4, "10:00"), "projet": "", "responsable": ""}]
        self.assertEqual(self.ok("calendrier", du=J(3), au=J(9))["elements"], [])
        self.assertEqual([e["titre"] for e in self.ok("calendrier", du=J(-6), au=J(-2))["elements"]], ["En retard"])

    def test_sans_les_autres_modules_la_vue_marche_avec_ses_evenements_et_rappels(self):
        def muet(cap, **a):
            raise ValueError("module absent")
        self.ctx.executer_lecture = muet
        self.evt("Réunion", D(2))
        self.ok("rappel_enregistrer", texte="Appeler", echeance=D(1))
        self.assertEqual([e["kind"] for e in self.ok("calendrier", du=J(0), au=J(5))["elements"]], ["reminder", "event"])

    def test_la_vue_ne_montre_que_mon_agenda(self):
        self.evt("À moi")
        self.evt("À lui", compte=LEO)
        self.ok("rappel_enregistrer", texte="Rappel de Léo", echeance=D(1), compte=LEO)
        self.assertEqual([e["titre"] for e in self.ok("calendrier", du=J(0), au=J(10))["elements"]], ["À moi"])


class CalDav(Monde):
    ICS = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:r1\r\nSUMMARY:Dentiste\r\nDTSTART:%(d1)sT101500\r\nDTEND:%(d1)sT110000\r\nLOCATION:Rue X\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:r2\r\nSUMMARY:Cours\r\nDTSTART:%(d0)sT180000\r\nRRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:r3\r\nSUMMARY:Trop loin\r\nDTSTART:%(d99)sT180000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")

    def setUp(self):
        super().setUp()
        d = lambda n: (datetime.now() + timedelta(days=n)).strftime("%Y%m%d")
        self.faux = FauxCalDav(self.ICS % {"d0": d(0), "d1": d(1), "d99": d(99)})
        self.addCleanup(self.faux.arreter)
        self.n.reglages.poser("agenda.caldav_url", "http://127.0.0.1:%d/cal/" % self.faux.port, BEA)
        self.n.reglages.poser("agenda.caldav_identifiant", "bea", BEA)
        self.n.reglages.poser("agenda.caldav_mot_de_passe", "s3cret", BEA)

    def test_l_etat_ne_rend_jamais_le_mot_de_passe(self):
        e = self.ok("caldav_etat")
        self.assertEqual((e["configuree"], e["identifiant"], e["mot_de_passe_pose"]), (True, "bea", True))
        self.assertNotIn("s3cret", str(e))
        self.assertEqual(self.ok("caldav_etat", compte=LEO), {"configuree": False, "url": "", "identifiant": "", "mot_de_passe_pose": False})

    def test_l_agenda_fusionne_local_et_distant_et_developpe_les_series(self):
        self.evt("Local", D(2, "08:00"))
        a = self.ok("agenda", jours=7)
        self.assertTrue(a["caldav"])
        par = [(e["origine"], e["titre"]) for e in a["evenements"]]
        self.assertEqual(par.count(("caldav", "Cours")), 3)
        self.assertIn(("caldav", "Dentiste"), par)
        self.assertIn(("local", "Local"), par)
        self.assertNotIn(("caldav", "Trop loin"), par)
        self.assertEqual([e["debut"] for e in a["evenements"]], sorted(e["debut"] for e in a["evenements"]))
        q = self.faux.requetes[0]
        self.assertEqual(q["auth"], "Basic " + base64.b64encode(b"bea:s3cret").decode())
        self.assertEqual(q["depth"], "1")
        self.assertIn("calendar-query", q["corps"])
        self.assertIn("time-range", q["corps"])

    def test_chaque_compte_lit_son_propre_serveur(self):
        self.evt("À Léo", D(1), compte=LEO)
        a = self.ok("agenda", compte=LEO)
        self.assertEqual((a["caldav"], [e["titre"] for e in a["evenements"]]), (False, ["À Léo"]))
        self.assertIn("non configuré", a["note"])
        self.assertEqual(len(self.faux.requetes), 0)

    def test_une_panne_caldav_ne_fait_pas_disparaitre_l_agenda_local(self):
        self.evt("Local", D(1))
        self.faux.arreter()
        a = self.ok("agenda")
        self.assertEqual((a["caldav"], [e["titre"] for e in a["evenements"]]), (False, ["Local"]))
        self.assertIn("CalDAV injoignable", a["note"])

    def test_une_adresse_qui_n_est_pas_http_est_refusee_sans_planter(self):
        self.n.reglages.poser("agenda.caldav_url", "file:///etc/passwd", BEA)
        self.evt("Local", D(1))
        a = self.ok("agenda")
        self.assertEqual((a["caldav"], [e["titre"] for e in a["evenements"]]), (False, ["Local"]))

    def test_une_erreur_du_serveur_est_une_panne_pas_un_agenda_vide(self):
        self.faux.statut = 500
        self.evt("Local", D(1))
        a = self.ok("agenda")
        self.assertEqual(a["caldav"], False)
        self.assertEqual([e["titre"] for e in a["evenements"]], ["Local"])


if __name__ == "__main__":
    unittest.main()
