# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'affichage des menus
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #2cd2db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'affichage des menus : le contrat Menu (groupe, zone), la disposition rangée par le point d'évolution et filtrée par le nexus, les idées du panneau, l'organisation, les pages épinglées et les fils du panneau. Ce qui est décisif (qui voit q
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2cd2db ▼▼▼
"""L'affichage des menus : le contrat Menu (groupe, zone), la disposition rangée par le point d'évolution et filtrée par le nexus, les idées du panneau, l'organisation,
les pages épinglées et les fils du panneau. Ce qui est décisif (qui voit quoi, qui peut régler l'organisation) se vérifie ici : le point d'évolution ne décide d'aucun accès."""
import base64
import importlib.util
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402
from noyau import CN_manifeste as manifeste   # noqa: E402

BEA, ROOT = "bea@x.fr", "root@x.fr"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * 40).decode()

FLOTTE_TOML = """
[module]
id = "flotte"
nom = "Flotte d'essai"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : une entrée de menu et une alerte de la machine."
famille = "reseau"

[[capacites]]
id = "signal"
libelle = "L'alerte de la machine"
risque = "lecture"

[[signaux]]
id = "machine"
libelle = "Alerte de la machine"
capacite = "signal"
admin = true

[[ecrans]]
id = "vue"
libelle = "Flotte"
gabarit = "libre"

[[menus]]
id = "flotte"
libelle = "Flotte"
ecran = "vue"
role = "admin"
"""
FLOTTE_PY = """
def brancher(ctx):
    def signal(c):
        return {"items": [{"bande": "brule", "quoi": "alerte", "titre": "Disque plein", "detail": "Disque plein", "nat": "", "ref": "", "poids": 100, "ou": "flotte"}]}
    ctx.implementer("signal", signal)
"""
CRM_TOML = """
[module]
id = "crm"
nom = "CRM d'essai"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : un menu qui dit son groupe, une sous-entrée, une entrée de l'avatar."
famille = "gestion"

[[ecrans]]
id = "liste"
libelle = "Clients"
gabarit = "libre"

[[ecrans]]
id = "reglages"
libelle = "Réglages"
gabarit = "libre"

[[menus]]
id = "clients"
libelle = "Clients"
ecran = "liste"
groupe = "metier"
ordre = 10

[[menus]]
id = "fiches"
libelle = "Fiches"
ecran = "liste"
parent = "clients"
ordre = 10

[[menus]]
id = "prefs"
libelle = "Préférences clients"
ecran = "reglages"
zone = "avatar"
role = "admin"
"""
PY_VIDE = "def brancher(ctx):\n    pass\n"


def charger_ec(nom):
    spec = importlib.util.spec_from_file_location("ec_" + nom, str(RACINE / "modules" / "affichage" / "points" / ("EC_%s.py" % nom)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def entree(id, module, libelle, ordre=100, famille="", groupe="", zone="principal", role="utilisateur", parent=""):
    return {"id": id, "module": module, "libelle": libelle, "ecran": module + ":vue", "ordre": ordre, "role": role, "icone": "", "parent": parent,
            "famille": famille, "groupe": groupe, "zone": zone, "droit": ""}


class Contrat(unittest.TestCase):
    """Le contrat Menu : un groupe d'affichage et une zone, validés au manifeste."""

    def brut(self, **menu):
        return {"module": {"id": "essai", "nom": "Essai", "version": "0.1.0", "noyau_min": "0.1.0", "description": "d"},
                "ecrans": [{"id": "ecran1", "libelle": "E"}], "menus": [dict({"id": "menu1", "libelle": "X", "ecran": "ecran1"}, **menu)]}

    def test_un_menu_peut_dire_son_groupe_et_sa_zone(self):
        self.assertEqual(manifeste.valider(self.brut(groupe="parc", zone="avatar")), [])
        m = manifeste.construire(self.brut(groupe="parc", zone="avatar"))
        self.assertEqual((m.menus[0].groupe, m.menus[0].zone), ("parc", "avatar"))

    def test_une_zone_inconnue_est_refusee(self):
        self.assertTrue(any("zone" in e for e in manifeste.valider(self.brut(zone="ailleurs"))))

    def test_un_groupe_mal_forme_est_refuse(self):
        self.assertTrue(any("groupe" in e for e in manifeste.valider(self.brut(groupe="Pas Valide"))))

    def test_par_defaut_ni_groupe_ni_zone_speciale(self):
        self.assertEqual(manifeste.valider(self.brut()), [])
        d = manifeste.Menu("x", "X")
        self.assertEqual((d.groupe, d.zone), ("", "principal"))


class Points(unittest.TestCase):
    """Les deux points d'évolution, appelés tels quels : ce que dit leur contrat."""

    @classmethod
    def setUpClass(cls):
        cls.D = charger_ec("disposition")
        cls.I = charger_ec("idees")

    def disp(self, entrees, modules=(), badges=None, signaux=None):
        return self.D.point_disposition({"entrees": entrees, "modules": list(modules), "badges": badges or {}, "signaux": signaux or {}})["valeur"]

    def ids(self, v):
        out = []
        for g in v["groupes"]:
            for e in g["entrees"]:
                out.append(e["id"])
                out += [f["id"] for f in e["enfants"]]
        return out + [e["id"] for e in v["avatar"]]

    def test_une_entree_recue_parait_une_seule_fois(self):
        es = [entree("a:a", "a", "A", 10, "securite"), entree("b:b", "b", "B", 20, "supervision"), entree("c:c", "c", "C", 30, "inconnue"),
              entree("d:d", "d", "D", 40, "gestion", zone="avatar"), entree("e:e", "e", "E", 50, "gestion", parent="a:a")]
        ids = self.ids(self.disp(es, ["a", "b", "c", "d", "e"]))
        recus = sorted(x["id"] for x in es)
        self.assertEqual(sorted(i for i in ids if ":" in i), recus)            # les entrées du pont (sans « : ») s'ajoutent, aucune des reçues ne manque ni ne double

    def test_l_ordre_des_entrees_recues_ne_change_rien(self):
        es = [entree("a:a", "a", "Alpha", 10, "securite"), entree("b:b", "b", "Beta", 10, "securite"), entree("c:c", "c", "Gamma", 5, "securite")]
        self.assertEqual(self.disp(es, "abc"), self.disp(list(reversed(es)), "abc"))

    def test_un_groupe_vide_n_existe_pas_et_les_groupes_suivent_la_table(self):
        v = self.disp([entree("z:z", "z", "Z", 10, "supervision"), entree("y:y", "y", "Y", 10, "securite")], ["z", "y"])
        ordre = [g["id"] for g in v["groupes"]]
        self.assertEqual(ordre, sorted(ordre, key=[g[0] for g in self.D.GROUPES].index))
        self.assertNotIn("metier", ordre)
        self.assertLessEqual(len(v["groupes"]), self.D.MAX_GROUPES)

    def test_une_famille_inconnue_n_est_pas_perdue(self):
        v = self.disp([entree("x:x", "x", "Exotique", 10, "bizarre")], ["x"])
        self.assertEqual([g["id"] for g in v["groupes"] if any(e["id"] == "x:x" for e in g["entrees"])], ["modules"])
        self.assertEqual(v["orphelines"], ["x:x"])

    def test_le_pont_couvre_le_module_de_l_ancienne_interface(self):
        v = self.disp([entree("journal:journal", "journal", "Journal", 10, "supervision")], ["journal"])
        self.assertEqual(self.ids(v).count("journal:journal"), 0)
        self.assertIn("journaux", self.ids(v))
        sans = self.disp([entree("journal:journal", "journal", "Journal", 10, "supervision")], [])
        self.assertIn("journal:journal", self.ids(sans))            # sans le pont (module absent des actifs), l'entrée déclarée reste

    def test_le_salon_n_est_plus_une_entree(self):
        v = self.disp([entree("salon:salon", "salon", "Le Salon", 10, "echanges")], ["salon"])
        self.assertNotIn("salon:salon", self.ids(v))

    def test_le_pire_niveau_remonte(self):
        v = self.disp([], ["flotte", "memoire"], signaux={"flotte": {"brule": 1}, "memoire": {"regarder": 3}, "inconnu": {"brule": 9}})
        niveaux = {g["id"]: g["niveau"] for g in v["groupes"]}
        self.assertEqual((niveaux["parc"], niveaux["auto"], v["niveau"]), ("danger", "alerte", "danger"))
        self.assertEqual(self.disp([], ["flotte"])["niveau"], "ok")

    def test_les_idees_classent_ce_qui_brule_d_abord_avec_sa_raison(self):
        ssl = {"bande": "brule", "quoi": "ssl", "titre": "Certificat : 6 jour(s).", "detail": "6 jours", "nat": "ssl", "ref": "a.fr", "poids": 190, "ou": "sites"}
        tache = {"bande": "jour", "quoi": "tache", "titre": "Une tâche", "detail": "", "nat": "", "ref": "t", "poids": 5, "ou": ""}
        v = self.I.point_idees({"contexte": {"mode": "cassandra", "heure": 15, "entree": "securite"}, "items": [tache, ssl], "actes": []})["valeur"]
        self.assertTrue(v["idees"][0]["id"].startswith("q:ssl"))
        self.assertEqual(v["idees"][0]["raison"], "6 jours")
        self.assertTrue(v["urgent"])
        self.assertTrue(all(i["titre"] and "score" in i and i["genre"] in ("question", "acte") for i in v["idees"]))

    def test_un_geste_n_est_propose_que_s_il_est_dans_la_liste_et_pour_le_bon_interlocuteur(self):
        ssl = {"bande": "brule", "quoi": "ssl", "titre": "t", "detail": "d", "nat": "ssl", "ref": "a.fr", "poids": 190, "ou": "sites"}
        acte = {"id": "relire", "titre": "Relire", "nat": "ssl", "qui": "cassandra", "risque": "lecture", "etat": ""}
        ctx = {"mode": "cassandra", "heure": 15}
        genres = lambda actes, mode="cassandra": [i["genre"] for i in self.I.point_idees({"contexte": dict(ctx, mode=mode), "items": [ssl], "actes": actes})["valeur"]["idees"]]
        self.assertIn("acte", genres([acte]))
        self.assertNotIn("acte", genres([]))
        self.assertNotIn("acte", genres([acte], "itare"))
        self.assertNotIn("acte", genres([dict(acte, etat="refuse")]))
        self.assertIn("question", genres([dict(acte, etat="fait")]))      # le suivi d'un geste fait

    def test_les_memes_entrees_donnent_les_memes_idees(self):
        e = {"contexte": {"mode": "itare", "heure": 9}, "items": [{"bande": "jour", "quoi": "tache", "titre": "x", "ref": "1", "poids": 3}], "actes": []}
        self.assertEqual(self.I.point_idees(e), self.I.point_idees(e))

    def test_au_plus_le_nombre_demande(self):
        items = [{"bande": "regarder", "quoi": "tache", "titre": "t%d" % i, "ref": str(i), "poids": i} for i in range(20)]
        self.assertEqual(len(self.I.point_idees({"contexte": {"mode": "itare"}, "items": items, "actes": [], "max": 3})["valeur"]["idees"]), 3)
        self.assertLessEqual(len(self.I.point_idees({"contexte": {"mode": "itare"}, "items": items, "actes": [], "max": 99})["valeur"]["idees"]), 8)


class Affichage(unittest.TestCase):
    """Le module dans un noyau : ce que voit un compte, ce que voit un administrateur."""

    @classmethod
    def setUpClass(cls):
        """Un seul noyau pour toute la classe (le monter coûte une dizaine de secondes) : chaque banc se sert de ses propres comptes ou remet ce qu'il touche."""
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        ig = shutil.ignore_patterns("__pycache__")
        for m in ("droits", "comptes", "menus", "affichage", "jour", "salon"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=ig)
        for nom, toml, py in (("flotte", FLOTTE_TOML, FLOTTE_PY), ("crm", CRM_TOML, PY_VIDE)):
            (mods / nom).mkdir()
            (mods / nom / "CN_manifeste.toml").write_text(toml, encoding="utf-8")
            (mods / nom / "CN_module.py").write_text(textwrap.dedent(py), encoding="utf-8")
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in ("droits", "comptes", "menus", "affichage", "jour", "salon", "flotte", "crm"):
            assert cls.n.activer(m)["ok"], m
        cls.n.droits.regler_admin(ROOT, True)
        r = cls.n.lancer("menus.reconstruire_regulierement")
        assert r.get("statut") == "fait", r

    @classmethod
    def tearDownClass(cls):
        cls.n.arreter()
        cls.tmp.cleanup()

    def ex(self, cap, qui=BEA, acteur="humain", **args):
        return self.n.executeur.executer(cap, acteur, args, compte=qui)

    def ok(self, cap, qui=BEA, **args):
        r = self.ex(cap, qui, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def disposition(self, compte=BEA):
        return self.ok("affichage.lire_disposition", compte)

    def entrees(self, d):
        return {e["id"]: (g["id"], e) for g in d["groupes"] for e in g["entrees"]}

    # ---- ce que voit chacun
    def test_un_administrateur_voit_les_groupes_et_le_menu_de_l_avatar(self):
        d = self.disposition(ROOT)
        e = self.entrees(d)
        self.assertEqual(e["crm:clients"][0], "metier")                 # le module dit son groupe
        self.assertEqual([f["id"] for f in e["crm:clients"][1]["enfants"]], ["crm:fiches"])
        self.assertEqual(e["flotte"][0], "parc")                        # le pont, pour l'ancienne interface
        self.assertEqual(e["flotte"][1]["onglet"], "fleet")
        self.assertIn("affichage:societe", [a["id"] for a in d["avatar"]])
        self.assertIn("crm:prefs", [a["id"] for a in d["avatar"]])
        self.assertTrue(d["cassandra_ok"])

    def test_un_compte_ne_voit_pas_ce_qui_est_reserve_a_l_administrateur(self):
        d = self.disposition(BEA)
        e = self.entrees(d)
        self.assertIn("crm:clients", e)
        self.assertNotIn("flotte", e)
        self.assertNotIn("crm:prefs", [a["id"] for a in d["avatar"]])
        self.assertNotIn("affichage:societe", [a["id"] for a in d["avatar"]])
        self.assertFalse(d["cassandra_ok"])
        self.assertTrue(all(g["interlocuteur"] == "itare" for g in d["groupes"]))      # Cassandra ne répond pas à un compte : le nexus tranche

    def test_un_compte_ne_peut_pas_se_dire_administrateur(self):
        e = self.entrees(self.ok("affichage.lire_disposition", BEA, role="admin", compte=ROOT))
        self.assertNotIn("flotte", e)

    def test_l_alerte_de_la_machine_remonte_pour_l_administrateur_seulement(self):
        self.assertEqual(self.disposition(ROOT)["niveau"], "danger")
        grp = {g["id"]: g["niveau"] for g in self.disposition(ROOT)["groupes"]}
        self.assertEqual(grp["parc"], "danger")
        self.assertEqual(self.disposition(BEA)["niveau"], "ok")

    def test_le_salon_n_a_plus_d_entree(self):
        self.assertFalse(any(i.startswith("salon") for i in self.entrees(self.disposition(ROOT))))

    # ---- l'organisation
    def modifier(self, section, valeurs=None, qui=ROOT, **plus):
        return self.ex("affichage.modifier_organisation", qui, section=section, valeurs=valeurs or {}, **plus)

    def test_l_organisation_se_regle_par_un_administrateur_seulement(self):
        self.addCleanup(lambda: [self.modifier(s, reinitialiser=True) for s in ("organisation", "reseaux", "heures", "soustraitants")])
        self.assertEqual(self.ok("affichage.lire_organisation", BEA)["nom"], "Cassandra")
        self.assertNotEqual(self.modifier("organisation", {"raison_sociale": "Pirate"}, qui=BEA)["statut"], "faite")
        r = self.modifier("organisation", {"raison_sociale": "Maison Exemple", "devise": "EUR", "pays": "FR", "telephone": "01 02 03 04 05", "logo": PNG, "logo_carre": PNG})
        self.assertEqual(r["statut"], "faite", r)
        o = self.ok("affichage.lire_organisation", ROOT)
        self.assertEqual((o["organisation"]["raison_sociale"], o["organisation"]["telephone"], o["organisation"]["logo"], o["complet"]), ("Maison Exemple", "01 02 03 04 05", PNG, True))
        self.assertEqual(self.disposition(BEA)["organisation"], {"nom": "Maison Exemple", "logo": PNG, "logo_carre": PNG})

    def test_un_compte_ne_lit_que_le_nom_et_les_logos(self):
        self.addCleanup(lambda: [self.modifier(s, reinitialiser=True) for s in ("organisation", "soustraitants")])
        self.modifier("organisation", {"telephone": "0102030405", "note": "secret de la maison"})
        self.modifier("soustraitants", {"comptabilite": {"raison_sociale": "Cabinet Dupont", "siren": "123456789"}})
        vu = self.ok("affichage.lire_organisation", BEA)
        self.assertEqual(set(vu), {"nom", "logo", "logo_carre", "complet"})
        self.assertFalse(vu["complet"])
        self.assertNotIn("secret", str(self.disposition(BEA)["organisation"]))
        plein = self.ok("affichage.lire_organisation", ROOT)
        self.assertEqual(plein["soustraitants"]["comptabilite"]["siren"], "123456789")

    def test_chaque_rubrique_s_enregistre_a_part(self):
        self.addCleanup(lambda: [self.modifier(s, reinitialiser=True) for s in ("organisation", "reseaux", "heures", "soustraitants")])
        self.assertEqual(self.modifier("reseaux", {"instagram": {"id": "maisondelaboheme", "url": "https://instagram.com/maisondelaboheme"}})["statut"], "faite")
        self.assertEqual(self.modifier("heures", {"lundi": "9h-18h", "dimanche": "fermé"})["statut"], "faite")
        self.assertEqual(self.modifier("soustraitants", {"informatique": {"raison_sociale": "Atelier Web", "email": "contact@atelier.fr", "web": "https://atelier.fr"}})["statut"], "faite")
        o = self.ok("affichage.lire_organisation", ROOT)
        self.assertEqual(o["reseaux"]["instagram"]["id"], "maisondelaboheme")
        self.assertEqual(o["reseaux"]["facebook"], {"id": "", "url": ""})
        self.assertEqual((o["heures"]["lundi"], o["heures"]["mardi"], o["heures"]["dimanche"]), ("9h-18h", "", "fermé"))
        self.assertEqual(o["soustraitants"]["informatique"]["email"], "contact@atelier.fr")
        self.assertEqual(o["organisation"]["raison_sociale"], "Cassandra")            # les autres rubriques n'ont pas bougé

    def test_une_rubrique_se_remet_a_son_defaut(self):
        self.addCleanup(lambda: self.modifier("heures", reinitialiser=True))
        self.modifier("heures", {"mercredi": "10h-12h"})
        self.assertEqual(self.modifier("heures", reinitialiser=True)["statut"], "faite")
        self.assertEqual(self.ok("affichage.lire_organisation", ROOT)["heures"]["mercredi"], "")

    def test_une_organisation_invalide_est_refusee(self):
        self.addCleanup(lambda: self.modifier("organisation", reinitialiser=True))
        mauvais = [("organisation", {"raison_sociale": ""}), ("organisation", {"raison_sociale": "x" * 81}), ("organisation", {"pays": "France"}), ("organisation", {"devise": "euro"}),
                   ("organisation", {"email": "pas-un-mail"}), ("organisation", {"web": "javascript:alert(1)"}), ("organisation", {"inconnu": "x"}),
                   ("organisation", {"logo": "data:image/svg+xml;base64,PHN2Zz4="}), ("organisation", {"logo_carre": "http://exemple.fr/logo.png"}),
                   ("organisation", {"logo": "data:image/png;base64," + "A" * 200000}),
                   ("reseaux", {"myspace": {"id": "x"}}), ("reseaux", {"facebook": {"url": "ftp://x"}}), ("reseaux", {"facebook": {"autre": "x"}}),
                   ("heures", {"jeudi_soir": "x"}), ("heures", {"lundi": "x" * 61}),
                   ("soustraitants", {"avocat": {"raison_sociale": "x"}}), ("soustraitants", {"comptabilite": {"inconnu": "x"}}), ("soustraitants", {"comptabilite": {"email": "x"}}),
                   ("rubrique_inconnue", {"a": "b"})]
        for section, v in mauvais:
            self.assertNotEqual(self.modifier(section, v)["statut"], "faite", (section, v))
        self.assertEqual(self.ok("affichage.lire_organisation", ROOT)["organisation"]["raison_sociale"], "Cassandra")

    # ---- les pages épinglées
    def test_une_epingle_appartient_a_son_compte(self):
        ep = "ep1@x.fr"
        self.ok("affichage.epingler", ep, cle="desk|accueil|jour", groupe="desk", entree="accueil", vue="jour", libelle="Aujourd'hui · Accueil")
        self.assertEqual([p["cle"] for p in self.disposition(ep)["epingles"]], ["desk|accueil|jour"])
        self.assertEqual(self.disposition(ROOT)["epingles"], [])
        self.ok("affichage.desepingler", ep, cle="desk|accueil|jour")
        self.assertEqual(self.disposition(ep)["epingles"], [])
        self.assertNotEqual(self.ex("affichage.desepingler", ep, cle="desk|accueil|jour")["statut"], "faite")

    def test_au_plus_douze_epingles_et_des_cles_sages(self):
        ep = "ep2@x.fr"
        for i in range(12):
            self.ok("affichage.epingler", ep, cle="g|e%d" % i, groupe="g", entree="e%d" % i)
        self.assertNotEqual(self.ex("affichage.epingler", ep, cle="g|trop", groupe="g", entree="trop")["statut"], "faite")
        self.assertNotEqual(self.ex("affichage.epingler", ep, cle="<script>", groupe="g", entree="x")["statut"], "faite")

    # ---- les idées
    def test_les_idees_d_itare_ne_parlent_que_du_poste_de_travail(self):
        v = self.ok("affichage.lire_idees", ROOT, mode="itare", groupe="desk", heure=9)
        self.assertEqual(v["mode"], "itare")
        self.assertFalse(any("Disque" in i["titre"] for i in v["idees"]))        # l'alerte de la machine est pour Cassandra
        self.assertEqual(v["idees"][0]["id"], "h:matin")

    def test_les_idees_de_cassandra_voient_le_parc_et_proposent_des_gestes(self):
        v = self.ok("affichage.lire_idees", ROOT, mode="cassandra", groupe="parc", entree="flotte", heure=15)
        self.assertTrue(any("Disque plein" in i["titre"] for i in v["idees"]))
        self.assertTrue(v["urgent"])

    def test_un_compte_ne_parle_pas_a_cassandra(self):
        self.assertEqual(self.ok("affichage.lire_idees", BEA, mode="cassandra", groupe="parc")["mode"], "itare")

    def test_le_mode_se_regle_selon_le_groupe_quand_il_n_est_pas_dit(self):
        self.assertEqual(self.ok("affichage.lire_idees", ROOT, groupe="desk")["mode"], "itare")
        self.assertEqual(self.ok("affichage.lire_idees", ROOT, groupe="secu")["mode"], "cassandra")

    # ---- la session
    def test_la_session_rend_le_compte_et_son_role(self):
        s = self.ok("affichage.lire_session", ROOT)
        self.assertEqual((s["compte"], s["role"]), (ROOT, "admin"))
        self.assertEqual(self.ok("affichage.lire_session", BEA)["role"], "utilisateur")

    # ---- le plan du jour
    JOUR = "2026-10-19"

    def plan(self, blocs, qui=BEA, jour=JOUR):
        return self.ex("affichage.modifier_plan", qui, jour=jour, blocs=blocs)

    def test_un_compte_pose_des_blocs_sur_sa_journee_et_les_relit(self):
        self.addCleanup(lambda: self.plan([]))
        b = [{"id": "t12", "titre": "Relire le chapitre 4", "deb": 600, "duree": 45, "tache": 12},
             {"id": "libre-a", "titre": "Appeler le notaire", "deb": 540, "duree": 15, "fait": True, "couleur": "#7c5cd6"}]
        self.assertEqual(self.plan(b)["statut"], "faite")
        p = self.ok("affichage.lire_plan", BEA, jour=self.JOUR)
        self.assertEqual([(x["id"], x["deb"], x["duree"], x["fait"]) for x in p["blocs"]], [("libre-a", 540, 15, True), ("t12", 600, 45, False)])   # triés par heure

    def test_le_plan_est_a_soi(self):
        self.addCleanup(lambda: self.plan([]))
        self.plan([{"id": "t1", "titre": "Privé", "deb": 600, "duree": 30}])
        self.assertEqual(self.ok("affichage.lire_plan", ROOT, jour=self.JOUR)["blocs"], [])

    def test_un_bloc_peut_passer_minuit(self):
        self.addCleanup(lambda: self.plan([]))
        self.assertEqual(self.plan([{"id": "n1", "titre": "Sauvegarde de nuit", "deb": 1500, "duree": 60}])["statut"], "faite")
        self.assertEqual(self.ok("affichage.lire_plan", BEA, jour=self.JOUR)["blocs"][0]["deb"], 1500)

    def test_un_plan_vide_se_retire(self):
        self.plan([{"id": "t1", "titre": "A", "deb": 600, "duree": 30}])
        self.assertEqual(self.plan([])["statut"], "faite")
        self.assertEqual(self.ok("affichage.lire_plan", BEA, jour=self.JOUR)["blocs"], [])

    def test_un_plan_invalide_est_refuse(self):
        self.addCleanup(lambda: self.plan([]))
        bon = {"id": "t1", "titre": "A", "deb": 600, "duree": 30}
        mauvais = [dict(bon, titre=""), dict(bon, titre="x" * 121), dict(bon, deb=-1), dict(bon, deb=2880), dict(bon, deb="10h"), dict(bon, duree=4), dict(bon, duree=481),
                   dict(bon, id="a b"), dict(bon, tache=-3), dict(bon, couleur="rouge"), dict(bon, inconnu=1)]
        for m in mauvais:
            self.assertNotEqual(self.plan([m])["statut"], "faite", m)
        self.assertNotEqual(self.plan([bon, dict(bon)])["statut"], "faite")                       # identifiant en double
        self.assertNotEqual(self.plan([dict(bon, id="b%d" % i) for i in range(61)])["statut"], "faite")
        self.assertNotEqual(self.plan([bon], jour="demain")["statut"], "faite")
        self.assertEqual(self.ok("affichage.lire_plan", BEA, jour=self.JOUR)["blocs"], [])

    # ---- les fils du panneau
    def test_un_fil_du_salon_se_lie_a_un_interlocuteur_et_a_une_page(self):
        fl = "fil1@x.fr"
        f = self.ok("salon.fil_creer", fl, titre="Relecture du contrat")
        fil = f.get("id") or f.get("fil")
        self.assertTrue(fil, f)
        self.ok("affichage.lier_fil", fl, fil=fil, agent="itare", page="desk|accueil|jour")
        fils = self.ok("affichage.lire_fils", fl, agent="itare")["fils"]
        self.assertEqual([(x["fil"], x["titre"], x["page"]) for x in fils], [(fil, "Relecture du contrat", "desk|accueil|jour")])
        self.assertEqual(self.ok("affichage.lire_fils", fl, agent="cassandra")["fils"], [])
        self.assertEqual(self.ok("affichage.lire_fils", ROOT, agent="itare")["fils"], [])           # les fils d'un autre compte restent à lui

    def test_on_ne_lie_pas_le_fil_d_un_autre(self):
        f = self.ok("salon.fil_creer", "fil2@x.fr", titre="Privé")
        fil = f.get("id") or f.get("fil")
        self.assertNotEqual(self.ex("affichage.lier_fil", ROOT, fil=fil, agent="itare")["statut"], "faite")
        self.assertNotEqual(self.ex("affichage.lier_fil", "fil2@x.fr", fil=fil, agent="inconnu")["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : charger_ec, entree, Contrat, Points, Affichage
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
