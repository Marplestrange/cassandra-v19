# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'autonomie de Cassandra sur les modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #3fcdbb
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'autonomie de Cassandra sur les modules : jusqu'où elle va seule, ce qu'elle se refuse, et que tout ce qu'elle fait se défait. La sûreté vient de la réversibilité, pas d'une permission : un refus de la règle n'est pas un échec (il ne rétro
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3fcdbb ▼▼▼
"""L'autonomie de Cassandra sur les modules : jusqu'où elle va seule, ce qu'elle se refuse, et que tout ce qu'elle fait se défait.
La sûreté vient de la réversibilité, pas d'une permission : un refus de la règle n'est pas un échec (il ne rétrograde pas sa capacité),
et chaque acte du récit porte le geste qui le défait."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur  # noqa: E402
import CN_test_registre_officiel as decor  # noqa: E402
from noyau import CN_paquets as paquets  # noqa: E402
from modules.modules import CN_autonomie as au  # noqa: E402


class Verdict(unittest.TestCase):
    def test_un_humain_passe_toujours(self):
        for n in au.NIVEAUX:
            for g in ("activer", "desinstaller", "installer", "ajouter"):
                self.assertTrue(au.verdict(n, "humain", g, source="")[0], (n, g))

    def test_observer_ne_fait_rien_et_le_dit(self):
        ok, raison = au.verdict("observer", "cassandra", "activer")
        self.assertFalse(ok)
        self.assertIn("observer", raison)

    def test_entretien_fait_le_reversible_et_retire_le_revoque_mais_n_ajoute_pas(self):
        for g in ("activer", "desactiver", "retour_arriere", "abandonner", "telecharger"):
            self.assertTrue(au.verdict("entretien", "cassandra", g)[0], g)
        self.assertTrue(au.verdict("entretien", "cassandra", "desinstaller", revoque=True)[0])
        self.assertFalse(au.verdict("entretien", "cassandra", "desinstaller", revoque=False)[0])
        self.assertFalse(au.verdict("entretien", "cassandra", "ajouter", source="officiel", nouveau=True)[0])
        self.assertTrue(au.verdict("entretien", "cassandra", "mettre_a_jour", source="officiel")[0])
        self.assertFalse(au.verdict("entretien", "cassandra", "mettre_a_jour", source="officiel", elargit=True)[0])

    def test_reine_gere_tout_ce_qui_vient_d_une_source_sure(self):
        self.assertTrue(au.verdict("reine", "cassandra", "ajouter", source="officiel", nouveau=True)[0])
        self.assertTrue(au.verdict("reine", "itare", "ajouter", source="verifie", nouveau=True)[0])
        self.assertTrue(au.verdict("reine", "cassandra", "mettre_a_jour", source="officiel", elargit=True)[0])
        self.assertTrue(au.verdict("reine", "cassandra", "desinstaller")[0])

    def test_a_aucun_niveau_ni_non_signe_ni_revoque_ni_permissions_de_plus_chez_un_tiers(self):
        for n in ("entretien", "reine"):
            self.assertFalse(au.verdict(n, "cassandra", "ajouter", source="", nouveau=True)[0])
            self.assertFalse(au.verdict(n, "cassandra", "ajouter", source="local", nouveau=True)[0])
            self.assertFalse(au.verdict(n, "cassandra", "ajouter", source="officiel", revoque=True, nouveau=True)[0])
        self.assertFalse(au.verdict("reine", "cassandra", "mettre_a_jour", source="verifie", elargit=True)[0])

    def test_un_module_verrouille_n_est_touche_par_aucun_agent_a_aucun_niveau_mais_l_utilisateur_passe(self):
        for n in au.NIVEAUX:
            for g in ("activer", "desactiver", "retour_arriere", "desinstaller", "mettre_a_jour"):
                ok, raison = au.verdict(n, "cassandra", g, source="officiel", revoque=(g == "desinstaller"), verrouille=True)
                self.assertFalse(ok, (n, g))
                self.assertIn("verrouillé", raison)
            self.assertTrue(au.verdict(n, "humain", "desactiver", verrouille=True)[0])

    def test_la_fenetre_de_maintenance(self):
        def t(annee, mois, jour, h, m=0):
            return time.mktime((annee, mois, jour, h, m, 0, 0, 0, -1))
        lundi_3h, lundi_14h, dimanche_7h, samedi_22h = t(2026, 10, 26, 3), t(2026, 10, 26, 14), t(2026, 11, 1, 7), t(2026, 10, 31, 22)
        self.assertTrue(au.dans_fenetre("nuit", lundi_3h))
        self.assertFalse(au.dans_fenetre("nuit", lundi_14h))
        self.assertFalse(au.dans_fenetre("nuit", t(2026, 10, 26, 5)))                     # 05:00 est la fin : exclue
        self.assertTrue(au.dans_fenetre("dimanche", dimanche_7h))
        self.assertFalse(au.dans_fenetre("dimanche", lundi_3h))
        self.assertFalse(au.dans_fenetre("hors_bureau", lundi_14h))
        self.assertTrue(au.dans_fenetre("hors_bureau", samedi_22h))
        self.assertTrue(au.dans_fenetre("hors_bureau", lundi_3h))
        self.assertTrue(au.dans_fenetre("tout", lundi_14h))
        self.assertEqual(au.fenetre_de("n'importe quoi"), "nuit")

    def test_niveau_inconnu_ou_vide_retombe_sur_le_defaut(self):
        self.assertEqual(au.niveau_de("n'importe quoi"), "reine")
        self.assertEqual(au.niveau_de(""), "reine")

    def test_chaque_geste_a_son_inverse(self):
        self.assertEqual(au.inverse("activer", {"module": "a"})["capacite"], "modules.desactiver")
        self.assertEqual(au.inverse("desactiver", {"module": "a"})["capacite"], "modules.activer")
        self.assertEqual(au.inverse("installe", {"id": "a", "ancienne": "0.1"})["capacite"], "modules.retour_arriere")
        self.assertEqual(au.inverse("installe", {"id": "a", "ancienne": ""})["capacite"], "modules.desinstaller")
        self.assertEqual(au.inverse("desinstalle", {"id": "a"})["capacite"], "modules.retour_arriere")
        self.assertEqual(au.inverse("active", {"id": "a"})["capacite"], "modules.desactiver")
        self.assertEqual(au.inverse("desactive", {"id": "a"})["capacite"], "modules.activer")
        self.assertIsNone(au.inverse("inconnu", {}))


class FauxG:
    """Le strict nécessaire de gestion_modules pour l'entretien : le catalogue, la pause d'un module et sa santé."""

    def __init__(self, cycle):
        self.cy = cycle
        self.actifs = set()
        self.sante_de = {}
        self.pauses = []

    def catalogue(self):
        return [{"id": m.id, "nom": m.nom, "version": m.version, "extension": ext, "etat": "actif" if m.id in self.actifs else "inactif"} for m, ext in self.cy.connus()]

    def desactiver(self, mid, acteur="", cascade=False, forcer=False, appliquer=False):
        self.actifs.discard(mid)
        self.pauses.append(mid)
        return {"ok": True, "desactives": [mid]}

    def sante(self, mid):
        return self.sante_de.get(mid, {"verdict": "sain", "en_echec": []})


class Entretien(decor.Officiel):
    """Sur le registre officiel d'essai de CN_test_registre_officiel : une vraie archive signée, un vrai cycle, une vraie installation."""

    for _nom in [n for n in dir(decor.Officiel) if n.startswith("test_")]:                     # le décor du registre d'essai, pas ses propres bancs (ils tournent dans leur fichier)
        locals()[_nom] = None

    def installer(self, mid, par="humain"):
        e = self.cycle.telecharger_officiel(mid)
        return self.cycle.installer(e["jeton"], e["empreinte_permissions"], "signes", par=par)

    def version_suivante(self, mid, priv, editeur, version, reseau=None):
        src = self.base / "src2" / version / mid
        shutil.copytree(RACINE / "exemples" / "sentinelle", src)
        f = src / "CN_manifeste.toml"
        t = f.read_text(encoding="utf-8").replace('id = "sentinelle"', 'id = "%s"' % mid, 1).replace('version = "0.1.2"', 'version = "%s"' % version, 1)
        if reseau:
            t += '\n[permissions]\nreseau = ["%s"]\n' % reseau
        f.write_text(t, encoding="utf-8")
        a = paquets.construire(src, priv, self.base / ("%s-%s.cmod" % (mid, version))).read_bytes()
        self.archives[mid] = {"octets": a, "editeur": editeur, "version": version}
        self.fichiers["/modules/%s.cmod" % mid] = a

    def publier_versions(self):
        import hashlib
        mods = [{"id": mid, "nom": mid.capitalize(), "version": a.get("version", "0.1.2"), "description": "essai", "url": "modules/%s.cmod" % mid,
                 "sha256": hashlib.sha256(a["octets"]).hexdigest(), "taille": len(a["octets"]), "editeur": a["editeur"]} for mid, a in self.archives.items()]
        self.publier(modules=mods)

    def passe(self, niveau, agir=True, g=None):
        g = g or FauxG(self.cycle)
        return g, au.entretien(g, self.cycle, "signes", niveau, agir=agir)

    # ---- révocation
    def test_un_module_revoque_est_retire_seul_et_le_geste_qui_le_remet_est_dit(self):
        self.installer("sentinelle")
        self.revocations = [{"id": "sentinelle", "versions": "<1.0", "raison": "faille connue"}]
        self.publier()
        g, r = self.passe("reine")
        self.assertEqual([(a["geste"], a["module"]) for a in r["actions"]], [("desinstalle", "sentinelle")])
        self.assertEqual(r["actions"][0]["inverse"]["capacite"], "modules.retour_arriere")
        self.assertFalse(any(m.id == "sentinelle" for m, _ in self.cycle.connus()))

    def test_en_observer_elle_constate_et_ne_touche_a_rien(self):
        self.installer("sentinelle")
        self.revocations = [{"id": "sentinelle", "versions": "<1.0", "raison": "faille connue"}]
        self.publier()
        g, r = self.passe("observer")
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("révoqué" in c for c in r["constats"]), r["constats"])
        self.assertTrue(any(m.id == "sentinelle" for m, _ in self.cycle.connus()))

    def test_agir_faux_dit_ce_qu_elle_ferait_sans_le_faire(self):
        self.installer("sentinelle")
        self.revocations = [{"id": "sentinelle", "versions": "<1.0", "raison": "faille connue"}]
        self.publier()
        g, r = self.passe("reine", agir=False)
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("retirerais" in c for c in r["constats"]), r["constats"])

    # ---- mises à jour
    def test_une_mise_a_jour_sans_permission_en_plus_est_prise_des_le_niveau_entretien(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3")
        self.publier_versions()
        g, r = self.passe("entretien")
        self.assertEqual([(a["geste"], a["version"]) for a in r["actions"]], [("installe", "0.1.3")])
        self.assertEqual(r["actions"][0]["inverse"]["capacite"], "modules.retour_arriere")
        self.assertEqual(next(m.version for m, _ in self.cycle.connus() if m.id == "sentinelle"), "0.1.3")

    def test_une_mise_a_jour_qui_demande_plus_attend_le_niveau_reine_et_la_source_officielle(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3", reseau="api.exemple.org")
        self.publier_versions()
        g, r = self.passe("entretien")
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("permissions" in c for c in r["constats"]), r["constats"])
        self.assertEqual(next(m.version for m, _ in self.cycle.connus() if m.id == "sentinelle"), "0.1.2")
        g, r = self.passe("reine")
        self.assertEqual([a["version"] for a in r["actions"]], ["0.1.3"])
        self.assertIn("api.exemple.org", r["actions"][0]["detail"])

    def test_chez_un_editeur_verifie_des_permissions_en_plus_ne_passent_jamais_seules(self):
        self.installer("chezacme")
        self.version_suivante("chezacme", self.acme_priv, "acme", "0.1.3", reseau="api.exemple.org")
        self.publier_versions()
        g, r = self.passe("reine")
        self.assertEqual(r["actions"], [])
        self.assertEqual(next(m.version for m, _ in self.cycle.connus() if m.id == "chezacme"), "0.1.2")

    def test_une_version_qu_elle_a_du_remettre_en_arriere_n_est_pas_reprise(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3")
        self.publier_versions()
        g, r = self.passe("reine")
        self.assertEqual(len(r["actions"]), 1)
        self.cycle.retour_arriere("sentinelle", par="cassandra")                       # elle la remet en arrière (la mise à jour tournait mal)
        g, r = self.passe("reine")
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("déjà" in c for c in r["constats"]), r["constats"])

    # ---- la fenêtre, le verrou, le pourquoi
    def test_une_mise_a_jour_attend_sa_fenetre_et_une_urgence_non(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3")
        self.publier_versions()
        lundi_14h = time.mktime((2026, 10, 26, 14, 0, 0, 0, 0, -1))
        lundi_3h = time.mktime((2026, 10, 26, 3, 0, 0, 0, 0, -1))
        g = FauxG(self.cycle)
        r = au.entretien(g, self.cycle, "signes", "reine", fenetre="nuit", maintenant=lundi_14h)
        self.assertEqual(r["actions"], [])
        self.assertFalse(r["fenetre_ouverte"])
        self.assertTrue(any("la nuit" in c for c in r["constats"]), r["constats"])
        r = au.entretien(g, self.cycle, "signes", "reine", fenetre="nuit", maintenant=lundi_14h, forcer=True)
        self.assertEqual([a["version"] for a in r["actions"]], ["0.1.3"])                  # « maintenant » : l'utilisateur force
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.4")
        self.publier_versions()
        r = au.entretien(g, self.cycle, "signes", "reine", fenetre="nuit", maintenant=lundi_3h)
        self.assertEqual([a["version"] for a in r["actions"]], ["0.1.4"])                  # dans la fenêtre : elle la prend
        self.installer("chezacme")
        self.revocations = [{"id": "chezacme", "versions": "<1.0", "raison": "faille connue"}]
        self.publier_versions()
        r = au.entretien(g, self.cycle, "signes", "reine", fenetre="nuit", maintenant=lundi_14h)
        self.assertEqual([(a["geste"], a["module"]) for a in r["actions"]], [("desinstalle", "chezacme")])   # hors fenêtre, mais une urgence n'attend pas

    def test_un_module_verrouille_n_est_pas_touche_meme_revoque(self):
        self.installer("sentinelle")
        self.cycle.verrouiller("sentinelle", True, par="drisse")
        self.revocations = [{"id": "sentinelle", "versions": "<1.0", "raison": "faille connue"}]
        self.publier()
        g, r = self.passe("reine")
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("verrouillé" in c for c in r["constats"]), r["constats"])
        self.assertTrue(any(m.id == "sentinelle" for m, _ in self.cycle.connus()))
        self.cycle.verrouiller("sentinelle", False, par="drisse")
        g, r = self.passe("reine")
        self.assertEqual([a["geste"] for a in r["actions"]], ["desinstalle"])

    def test_le_verrou_survit_au_redemarrage_et_se_journalise(self):
        self.cycle.verrouiller("sentinelle", True, par="drisse")
        autre = self.nouveau_cycle()
        self.assertEqual(autre.verrous(), {"sentinelle"})
        self.assertIn("verrou", [x["acte"] for x in autre.journal()])

    def test_chaque_acte_de_l_entretien_dit_pourquoi_dans_le_recit(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3")
        self.publier_versions()
        g, r = self.passe("entretien")
        self.assertIn("sans permission en plus", r["actions"][0]["pourquoi"])
        ligne = au.recit(self.cycle)[0]
        self.assertEqual((ligne["geste"], ligne["par"], ligne["module"]), ("installe", "cassandra", "sentinelle"))
        self.assertIn("sans permission en plus", ligne["pourquoi"])
        self.assertEqual(ligne["defaire"]["capacite"], "modules.retour_arriere")
        g.actifs.add("sentinelle")
        g.sante_de["sentinelle"] = {"verdict": "en_echec", "en_echec": ["sentinelle.mesure"]}
        g, r2 = self.passe("reine", g=g)
        retour = next(x for x in au.recit(self.cycle) if x["geste"] == "retour")
        self.assertIn("tournait mal", retour["pourquoi"])

    # ---- la santé
    def test_une_mise_a_jour_qui_tourne_mal_est_remise_en_arriere(self):
        self.installer("sentinelle")
        self.version_suivante("sentinelle", self.racine_priv, "cassandra", "0.1.3")
        self.publier_versions()
        g, r = self.passe("reine")
        g.actifs.add("sentinelle")
        g.sante_de["sentinelle"] = {"verdict": "en_echec", "en_echec": ["sentinelle.mesure"]}
        g, r2 = self.passe("reine", g=g)
        self.assertEqual([(a["geste"], a["version"]) for a in r2["actions"]], [("retour", "0.1.2")])
        self.assertEqual(next(m.version for m, _ in self.cycle.connus() if m.id == "sentinelle"), "0.1.2")

    def test_un_module_qui_echoue_sans_mise_a_jour_recente_est_mis_en_pause(self):
        self.installer("sentinelle")
        g = FauxG(self.cycle)
        g.actifs.add("sentinelle")
        g.sante_de["sentinelle"] = {"verdict": "en_echec", "en_echec": ["sentinelle.mesure"]}
        g, r = self.passe("entretien", g=g)
        self.assertEqual([(a["geste"], a["module"]) for a in r["actions"]], [("desactive", "sentinelle")])
        self.assertEqual(r["actions"][0]["inverse"]["capacite"], "modules.activer")
        self.assertNotIn("sentinelle", g.actifs)

    def test_un_registre_muet_ne_fait_pas_tomber_la_passe(self):
        self.fichiers.pop("/index.json")
        g, r = self.passe("reine")
        self.assertEqual(r["actions"], [])
        self.assertTrue(any("ne répond pas" in c for c in r["constats"]), r["constats"])


class Monde(unittest.TestCase):
    """Sur une vraie instance : Cassandra appelle les capacités comme un acteur, le palier de départ est « auto », un refus ne rétrograde rien."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("modules", "droits", "comptes", "taches", "notes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "modules"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin("root@x.fr", True)

    def ex(self, cap, acteur="cassandra", **args):
        return self.n.executeur.executer("modules." + cap, acteur, args, compte="root@x.fr")

    def regler(self, valeur):
        self.n.executeur.contextes["modules"]._intro["reglages"].poser("modules.autonomie", valeur, "", par="essai")

    def test_cassandra_active_et_desactive_un_module_seule_des_le_depart(self):
        self.assertEqual(self.n.catalogue.savoir("modules.activer")["palier"], "auto")
        r = self.ex("activer", module="taches")
        self.assertEqual(r["statut"], "faite", r)
        self.assertNotIn("refuse", r["resultat"])
        self.assertEqual(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["etat"], "actif")
        r = self.ex("desactiver", module="taches")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["etat"], "inactif")

    def test_cassandra_ne_peut_pas_installer_une_archive_deposee_mais_peut_ajouter_du_registre(self):
        self.assertEqual(self.ex("installer", jeton="x", consentement="x")["statut"], "refuse")          # installer reste humain : elle passe par « ajouter »
        self.assertEqual(self.n.catalogue.savoir("modules.ajouter")["palier"], "auto")

    def test_un_refus_de_la_regle_n_est_pas_un_echec_et_ne_retrograde_pas(self):
        r = self.ex("ajouter", module="inconnu_du_registre")
        self.assertIn(r["statut"], ("echec", "faite", "refuse", "annulee"))                                   # le registre officiel n'est pas joignable ici : une erreur franche
        avant = self.n.catalogue.savoir("modules.desinstaller")
        r = self.ex("desinstaller", module="taches")                                                         # livré avec le noyau : refusé par le cycle, pas par la règle
        apres = self.n.catalogue.savoir("modules.desinstaller")
        self.assertEqual(avant["palier"], apres["palier"])

    def test_en_observer_elle_raconte_sans_rien_faire_et_sans_etre_rétrogradée(self):
        self.regler("observer")
        for _ in range(3):
            r = self.ex("activer", module="taches")
            self.assertEqual(r["statut"], "faite", r)
            self.assertIn("observer", r["resultat"]["refuse"])
        self.assertEqual(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["etat"], "inactif")
        self.assertEqual(self.n.catalogue.savoir("modules.activer")["palier"], "auto")                          # trois refus de règle : aucun échec compté
        self.assertEqual(self.ex("activer", acteur="humain", module="taches")["statut"], "faite")                # l'humain, lui, passe toujours (voie parallèle)

    def test_le_recit_et_l_annulation(self):
        self.ex("activer", module="taches")
        a = self.ex("activite")["resultat"]
        self.assertEqual(a["autonomie"], "reine")
        ligne = next(x for x in a["actes"] if x["geste"] == "active" and x["module"] == "taches")
        self.assertEqual(ligne["par"], "cassandra")
        self.assertEqual(ligne["pourquoi"], "Décision de Cassandra.")
        self.assertEqual(ligne["defaire"]["capacite"], "modules.desactiver")
        r = self.ex("annuler", acteur="humain", module="taches", geste="activer")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["etat"], "inactif")

    def test_le_pourquoi_donne_par_l_acteur_est_garde_et_celui_d_un_utilisateur_est_dit(self):
        self.ex("activer", module="taches", pourquoi="Itare en a besoin pour ses rappels.")
        self.ex("desactiver", acteur="humain", module="taches")
        actes = self.ex("activite")["resultat"]["actes"]
        self.assertEqual([(x["geste"], x["pourquoi"]) for x in actes if x["module"] == "taches"],
                         [("desactive", "Geste de l'utilisateur."), ("active", "Itare en a besoin pour ses rappels.")])

    def test_le_verrou_ferme_la_porte_aux_agents_et_seul_l_utilisateur_le_pose(self):
        self.assertEqual(self.ex("verrouiller", module="taches")["statut"], "refuse")                            # Cassandra ne se verrouille pas elle-même… ni ne se déverrouille
        self.assertEqual(self.ex("verrouiller", acteur="humain", module="taches")["statut"], "faite")
        r = self.ex("activer", module="taches")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("verrouillé", r["resultat"]["refuse"])
        self.assertEqual(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["etat"], "inactif")
        self.assertTrue(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["verrou"])
        self.assertEqual(self.ex("activer", acteur="humain", module="taches")["statut"], "faite")                # l'utilisateur, lui, passe
        self.assertEqual(self.ex("verrouiller", acteur="humain", module="taches", verrou=False)["statut"], "faite")
        self.assertFalse(next(m for m in self.ex("lister")["resultat"]["modules"] if m["id"] == "taches")["verrou"])

    def test_l_activite_dit_le_niveau_la_fenetre_et_le_gel(self):
        a = self.ex("activite")["resultat"]
        self.assertEqual((a["autonomie"], a["fenetre"], a["gel"], a["verrous"]), ("reine", "nuit", False, []))
        self.n.freiner("gel", True, "essai", acteur="humain")
        self.assertTrue(self.ex("activite")["resultat"]["gel"])

    def test_l_entretien_se_declenche_a_la_demande_et_sait_simuler(self):
        r = self.ex("entretien", acteur="humain", simuler=True)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["niveau"], "reine")
        self.assertEqual(r["resultat"]["actions"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Verdict, FauxG, Entretien, Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
