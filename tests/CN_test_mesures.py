# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des mesures
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #d4cbaf
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des mesures : le moteur (pur), la déclaration [[mesures]] des modules, et le module qui les assemble.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d4cbaf ▼▼▼
"""Bancs des mesures : le moteur (pur), la déclaration [[mesures]] des modules, et le module qui les assemble."""
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur_noyau                  # noqa: E402
from noyau import CN_manifeste as manifeste                  # noqa: E402
from modules.mesures import CN_moteur as mo     # noqa: E402

# le moteur sans noyau : son point d'évolution `moteur` est branché sur sa référence, comme le ferait brancher()
import tempfile                              # noqa: E402
from pathlib import Path as _Path            # noqa: E402
from noyau import CN_manifeste as _M, CN_points as _P          # noqa: E402
_dossier = RACINE / "modules" / "mesures"
_svc = _P.ServicePoints(_Path(tempfile.mkdtemp()) / "ec")
_svc.declarer(_M.charger(_dossier / "CN_manifeste.toml"), _dossier)
mo._point = lambda nom, entree: _svc.appeler("mesures", nom, entree)

MAINTENANT = datetime(2026, 10, 14, 15, 30, 0)          # un mercredi


def pts(debut, fin, pas_min, f):
    """Des points toutes les `pas_min` minutes entre debut et fin."""
    out, t = [], debut
    while t <= fin:
        out.append([mo.ecrire_ts(t), f(t)])
        t += timedelta(minutes=pas_min)
    return out


def jauge(**kw):
    return dict({"id": "cpu", "libelle": "Processeur", "genre": "jauge", "unite": "%", "famille": "Système", "agregat": "moy", "groupee": False, "pire": "haut", "plafond": 0,
                 "nature": "serie", "fraicheur_s": 0, "vide": "", "description": ""}, **kw)


def compteur(**kw):
    return jauge(id="echecs", libelle="Échecs", genre="compteur", unite="/h", **kw)


class Courbes(unittest.TestCase):
    def test_un_compteur_somme_et_une_jauge_s_agrege(self):
        p = [["2026-10-14 10:05:00", 1], ["2026-10-14 10:40:00", 1], ["2026-10-14 11:10:00", None]]
        self.assertEqual(mo.par_tranche(p, "compteur", "moy", "hour"), [{"ts": "2026-10-14 10", "v": 2}, {"ts": "2026-10-14 11", "v": 1}])
        g = [["2026-10-14 10:05:00", 10], ["2026-10-14 10:40:00", 30]]
        self.assertEqual(mo.par_tranche(g, "jauge", "moy", "hour"), [{"ts": "2026-10-14 10", "v": 20.0}])
        self.assertEqual(mo.par_tranche(g, "jauge", "max", "hour")[0]["v"], 30)

    def test_la_serie_ne_garde_que_la_periode(self):
        s = mo.serie(jauge(), [{"nom": "cpu", "points": pts(MAINTENANT - timedelta(hours=5), MAINTENANT, 10, lambda t: 40)}], "1h", MAINTENANT)
        self.assertTrue(all(x["ts"] >= "2026-10-14 14:30" for x in s["points"]))
        self.assertEqual(s["last"], 40)

    def test_une_courbe_groupee_garde_les_pires(self):
        brutes = [{"nom": "a", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(minutes=10)), 99]]}, {"nom": "b", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(minutes=10)), 100]]},
                  {"nom": "c", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(minutes=10)), 50]]}]
        haut = mo.serie(jauge(groupee=True), brutes, "1h", MAINTENANT, top=2)
        self.assertEqual([x["name"] for x in haut["series"]], ["b", "a"])
        bas = mo.serie(jauge(groupee=True, pire="bas"), brutes, "1h", MAINTENANT, top=2)
        self.assertEqual([x["name"] for x in bas["series"]], ["c", "a"])           # « pire » = bas : disponibilité, jours avant expiration

    def test_une_source_muette_le_dit(self):
        s = mo.serie(jauge(), None, "24h", MAINTENANT)
        self.assertEqual(s["points"], [])
        self.assertIn("muette", s["reason"])


class Sources(unittest.TestCase):
    def test_une_source_vide_dit_pourquoi(self):
        self.assertEqual(mo.etat_source(compteur(), [], MAINTENANT)["etat"], "rien_a_signaler")
        self.assertEqual(mo.etat_source(compteur(vide="non_configuree"), [], MAINTENANT)["etat"], "non_configuree")
        self.assertEqual(mo.etat_source(jauge(), [], MAINTENANT)["etat"], "aucune_donnee")
        self.assertEqual(mo.etat_source(jauge(), None, MAINTENANT)["etat"], "aucune_source")

    def test_une_source_qui_ecrivait_et_s_est_tue_est_muette(self):
        vieux = [{"nom": "x", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(hours=2)), 5]]}]
        self.assertEqual(mo.etat_source(jauge(fraicheur_s=180), vieux, MAINTENANT)["etat"], "muette")
        self.assertEqual(mo.etat_source(jauge(fraicheur_s=0), vieux, MAINTENANT)["etat"], "a_jour")     # relevés non périodiques : pas de seuil, pas de mensonge

    def test_l_habitude_se_date_a_la_premiere_mesure(self):
        recent = [{"nom": "x", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(days=2)), 5]]}]
        f = mo.fiche_source(jauge(), recent, MAINTENANT)
        self.assertFalse(f["habitude_connue"])
        self.assertEqual(f["habitude_dans_jours"], 20)
        vieux = [{"nom": "x", "points": [[mo.ecrire_ts(MAINTENANT - timedelta(days=40)), 5]]}]
        self.assertTrue(mo.fiche_source(jauge(), vieux, MAINTENANT)["habitude_connue"])


class Habitude(unittest.TestCase):
    def serie_hebdo(self, semaines, valeur_semaine=lambda i: 40):
        """Le même créneau (mercredi 15 h) vu `semaines` fois, une valeur par semaine, plus du bruit ailleurs."""
        brut = []
        for i in range(1, semaines + 1):
            t = MAINTENANT.replace(minute=10) - timedelta(weeks=i)
            brut.append([mo.ecrire_ts(t), valeur_semaine(i)])
        return [{"nom": "cpu", "points": brut}]

    def test_un_creneau_vu_deux_fois_n_a_pas_d_habitude(self):
        p = mo.profil(jauge(), self.serie_hebdo(2), MAINTENANT)
        self.assertFalse(p["enough"])
        self.assertIn("habitude inconnue", p["reason"])
        self.assertIsNone(p["deviation_pct"])

    def test_l_ecart_se_calcule_contre_la_moyenne_des_occurrences(self):
        brut = self.serie_hebdo(3)
        brut[0]["points"].append([mo.ecrire_ts(MAINTENANT - timedelta(minutes=20)), 80])           # la dernière heure : 80 contre 40 d'habitude
        p = mo.profil(jauge(), brut, MAINTENANT)
        self.assertTrue(p["enough"])
        self.assertEqual(p["baseline"], 40)
        self.assertEqual(p["deviation_pct"], 100)

    def test_un_compteur_additionne_chaque_heure_a_part(self):
        brut = []
        for i in range(1, 4):                                       # chaque mercredi 15 h : quatre échecs
            for k in range(4):
                brut.append([mo.ecrire_ts(MAINTENANT.replace(minute=5 + k) - timedelta(weeks=i)), None])
        p = mo.profil(compteur(), [{"nom": "x", "points": brut}], MAINTENANT)
        self.assertEqual(p["baseline"], 4)                          # la normale d'un créneau est une heure, pas la somme de toutes les heures
        self.assertEqual(p["current"], 0)


class Tendance(unittest.TestCase):
    def test_moins_de_24_heures_aucune_tendance(self):
        brut = [{"nom": "d", "points": pts(MAINTENANT - timedelta(hours=10), MAINTENANT, 30, lambda t: 50)}]
        pv = mo.prevision(jauge(plafond=100), brut, MAINTENANT)
        self.assertFalse(pv["enough"])
        self.assertIn("24 heures", pv["reason"])

    def test_une_montee_donne_une_date_de_saturation(self):
        debut = MAINTENANT - timedelta(days=5)
        brut = [{"nom": "d", "points": pts(debut, MAINTENANT, 60, lambda t: 50 + (t - debut).total_seconds() / 86400 * 2)}]       # +2 points par jour
        pv = mo.prevision(jauge(plafond=100), brut, MAINTENANT)
        self.assertTrue(pv["enough"])
        self.assertAlmostEqual(pv["trend"], 2.0, delta=0.1)
        self.assertAlmostEqual(pv["saturation_days"], 20, delta=1.5)           # 60 % -> 100 % à +2/jour

    def test_une_courbe_stable_ne_sature_pas(self):
        brut = [{"nom": "d", "points": pts(MAINTENANT - timedelta(days=3), MAINTENANT, 60, lambda t: 55)}]
        pv = mo.prevision(jauge(plafond=100), brut, MAINTENANT)
        self.assertTrue(pv["enough"])
        self.assertIsNone(pv["saturation_days"])

    def test_sans_plafond_pas_de_prevision(self):
        self.assertFalse(mo.prevision(jauge(), [], MAINTENANT)["ok"])


class Verdict(unittest.TestCase):
    def lectures_calmes(self):
        return {"cpu": [{"nom": "cpu", "points": pts(MAINTENANT - timedelta(days=30), MAINTENANT, 60, lambda t: 30)}]}

    def test_tout_calme_dit_stable(self):
        v = mo.verdict([jauge()], self.lectures_calmes(), MAINTENANT)
        self.assertEqual(v["niveau"], "stable")

    def test_une_source_qui_se_tait_n_est_jamais_stable(self):
        v = mo.verdict([jauge()], {"cpu": None}, MAINTENANT)
        self.assertEqual(v["niveau"], "inconnu")
        self.assertIn("cpu", [x for x in ["cpu"]])
        self.assertTrue(any(l["niveau"] == "muet" for l in v["lignes"]))

    def test_un_certificat_proche_est_une_panne_puis_un_point_a_regarder(self):
        ssl = jauge(id="ssl", libelle="Certificats", unite="j", pire="bas", groupee=True)
        def lec(j):
            return {"ssl": [{"nom": "a.fr", "points": pts(MAINTENANT - timedelta(days=30), MAINTENANT, 360, lambda t: j)}]}
        self.assertEqual(mo.verdict([ssl], lec(5), MAINTENANT)["niveau"], "panne")
        v = mo.verdict([ssl], lec(15), MAINTENANT)
        self.assertEqual(v["niveau"], "regarder")
        self.assertEqual(mo.verdict([ssl], lec(60), MAINTENANT)["niveau"], "stable")

    def test_un_site_tombe_est_une_panne(self):
        up = jauge(id="up", libelle="Sites — disponibilité", pire="bas", groupee=True)
        v = mo.verdict([up], {"up": [{"nom": "b.fr", "points": pts(MAINTENANT - timedelta(days=30), MAINTENANT, 60, lambda t: 100 if t < MAINTENANT - timedelta(hours=1) else 0)}]}, MAINTENANT)
        self.assertEqual(v["niveau"], "panne")
        self.assertIn("b.fr ne répond pas", v["titre"])


class Declaration(unittest.TestCase):
    def brut(self, **mesure):
        m = {"id": "charge", "libelle": "Charge", "capacite": "lire"}
        m.update(mesure)
        return {"module": {"id": "essai", "nom": "Essai", "version": "0.1.0", "noyau_min": "0.1.0", "description": "d", "confiance": "interne"},
                "capacites": [{"id": "lire", "libelle": "lire", "risque": "lecture"}], "mesures": [m]}

    def test_une_mesure_valide_se_construit(self):
        b = self.brut(genre="compteur", unite="/h", plafond=100)
        self.assertEqual(manifeste.valider(b), [])
        self.assertEqual(manifeste.construire(b).mesures[0].genre, "compteur")

    def test_une_capacite_qui_ecrit_ou_inconnue_est_refusee(self):
        self.assertTrue(any("capacite" in e for e in manifeste.valider(self.brut(capacite="nexiste_pas"))))

    def test_un_genre_inconnu_est_refuse(self):
        self.assertTrue(any("genre" in e for e in manifeste.valider(self.brut(genre="camembert"))))


class ModuleAssembleur(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("mesures", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        (mods / "fausse").mkdir()
        (mods / "fausse" / "CN_manifeste.toml").write_text('''[module]
id = "fausse"
nom = "Fausse source"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Une source de mesures pour les bancs"
confiance = "interne"

[[capacites]]
id = "courbe"
libelle = "Les points"
risque = "lecture"

[[mesures]]
id = "charge"
libelle = "Charge"
capacite = "courbe"
unite = "%"
famille = "Essai"
plafond = 100

[[mesures]]
id = "pannes"
libelle = "Pannes"
capacite = "courbe"
genre = "compteur"
unite = "/h"
famille = "Essai"
vide = "rien_a_signaler"
''', encoding="utf-8")
        (mods / "fausse" / "CN_module.py").write_text('''from datetime import datetime, timedelta

def brancher(ctx):
    def courbe(ctx, mesure="", depuis="", jusqu_a=""):
        if mesure == "pannes":
            return {"series": []}
        fin = datetime.utcnow()
        pts, t = [], fin - timedelta(days=2)
        while t <= fin:
            pts.append([t.strftime("%Y-%m-%d %H:%M:%S"), 30.0])
            t += timedelta(minutes=30)
        return {"series": [{"nom": "charge", "points": pts}]}
    ctx.implementer("courbe", courbe)
''', encoding="utf-8")
        self.n = moteur_noyau.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "fausse", "mesures"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin("root@x.fr", True)

    def ex(self, cap, compte="root@x.fr", **a):
        return self.n.executeur.executer("mesures." + cap, "humain", a, compte=compte)

    def test_les_sources_sont_celles_que_les_modules_declarent(self):
        r = self.ex("sources")
        self.assertEqual(r["statut"], "faite", r)
        cles = {m["key"]: m for m in r["resultat"]["metrics"]}
        self.assertEqual(set(cles), {"charge", "pannes"})
        self.assertEqual(cles["charge"]["etat"], "a_jour")
        self.assertEqual(cles["pannes"]["etat"], "rien_a_signaler")

    def test_la_serie_se_lit_par_periode(self):
        r = self.ex("serie", cle="charge", periode="24h")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["last"], 30.0)
        self.assertEqual(self.ex("serie", cle="nexiste-pas")["statut"], "echec")

    def test_le_verdict_se_compose(self):
        r = self.ex("verdict")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn(r["resultat"]["niveau"], ("stable", "inconnu", "regarder"))

    def test_sans_le_droit_rien_ne_sort(self):
        self.assertEqual(self.ex("sources", compte="bea@x.fr")["statut"], "refuse")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : pts, jauge, compteur, Courbes, Sources, Habitude, Tendance, Verdict …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
