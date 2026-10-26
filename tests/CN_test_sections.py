# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les sections
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e1db85
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les sections : les rubriques où se rangent les modules sont DÉCLARÉES (noyau + modules), plus écrites en dur dans l'interface. Le noyau en déclare un jeu ; un module en apporte de nouvelles ([[sections]]) mais ne redéfinit jamais celles du 
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e1db85 ▼▼▼
"""Les sections : les rubriques où se rangent les modules sont DÉCLARÉES (noyau + modules), plus écrites en dur dans l'interface.
Le noyau en déclare un jeu ; un module en apporte de nouvelles ([[sections]]) mais ne redéfinit jamais celles du noyau ;
une section que personne n'a déclarée existe quand même, pour qu'aucun module ne disparaisse de la page."""
import copy
import sys
import tomllib
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as M, CN_sections as S  # noqa: E402

BASE = {"module": {"id": "essai_sec", "nom": "Essai", "version": "0.1.0", "noyau_min": "0.1.0", "description": "Un module d'essai.", "importance": "optionnel", "sans": "Rien."}}


def man(**plus):
    d = copy.deepcopy(BASE)
    for k, v in plus.pop("module", {}).items():
        d["module"][k] = v
    d.update(plus)
    return d


def construit(mid="essai_sec", **plus):
    d = man(**plus)
    d["module"]["id"] = mid
    return M.construire(d)


class SectionsDuNoyau(unittest.TestCase):
    def test_le_noyau_declare_ses_sections_en_donnees(self):
        n = S.noyau()
        self.assertTrue({"socle", "securite", "reseau", "gestion", "finance", "supervision", "autres"} <= set(n))
        self.assertTrue(all(s.libelle and s.origine == "noyau" for s in n.values()))
        self.assertEqual(sorted(s.ordre for s in n.values())[-1], n["autres"].ordre)          # « Divers » en dernier

    def test_chaque_module_livre_se_range_dans_une_section_declaree_ou_declare_la_sienne(self):
        ms = []
        for f in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
            ms.append(M.charger(f))
        secs, remarques = S.resoudre(ms)
        ids = {s.id for s in secs}
        implicites = [s.id for s in secs if s.origine == "implicite"]
        self.assertEqual(implicites, [], "modules rangés dans une section que personne ne déclare : %s" % implicites)
        self.assertTrue(all((m.famille or "autres") in ids for m in ms))
        self.assertEqual(remarques, [])


class SectionsDesModules(unittest.TestCase):
    def test_un_module_apporte_sa_section_avec_un_ordre(self):
        m = construit(module={"section": "paye"}, sections=[{"id": "paye", "libelle": "Paie et RH", "icone": "fam_finance", "ordre": 95}])
        self.assertEqual(m.famille, "paye")
        secs, rem = S.resoudre([m])
        p = next(s for s in secs if s.id == "paye")
        self.assertEqual((p.libelle, p.icone, p.ordre, p.origine), ("Paie et RH", "fam_finance", 95, "essai_sec"))
        ids = [s.id for s in secs]
        self.assertLess(ids.index("finance"), ids.index("paye"))
        self.assertLess(ids.index("paye"), ids.index("travail"))                               # l'ordre déclaré place la section
        self.assertEqual(rem, [])

    def test_section_est_le_nom_actuel_famille_reste_lu(self):
        self.assertEqual(construit(module={"section": "reseau"}).famille, "reseau")
        self.assertEqual(construit(module={"famille": "reseau"}).famille, "reseau")
        self.assertEqual(construit(module={"section": "securite", "famille": "reseau"}).famille, "securite")

    def test_un_module_ne_redefinit_pas_une_section_du_noyau(self):
        m = construit(module={"section": "securite"}, sections=[{"id": "securite", "libelle": "Pirates", "ordre": 1}])
        secs, rem = S.resoudre([m])
        self.assertEqual(next(s for s in secs if s.id == "securite").libelle, "Sécurité et accès")
        self.assertTrue(any("noyau" in r and "securite" in r for r in rem), rem)

    def test_entre_deux_modules_le_premier_par_identifiant_l_emporte(self):
        a = construit("aa_mod", module={"section": "labo"}, sections=[{"id": "labo", "libelle": "Labo A"}])
        b = construit("bb_mod", module={"section": "labo"}, sections=[{"id": "labo", "libelle": "Labo B"}])
        secs, rem = S.resoudre([b, a])
        self.assertEqual(next(s for s in secs if s.id == "labo").libelle, "Labo A")
        self.assertTrue(any("bb_mod" in r and "aa_mod" in r for r in rem), rem)

    def test_l_ancienne_declaration_implicite_fonctionne_et_ne_fait_pas_de_remarque(self):
        m = construit(module={"famille": "compta", "famille_libelle": "Comptabilité", "famille_icone": "fam_finance"})
        n = construit("zz_mod", module={"famille": "compta"})
        secs, rem = S.resoudre([m, n])
        c = next(s for s in secs if s.id == "compta")
        self.assertEqual((c.libelle, c.icone, c.origine), ("Comptabilité", "fam_finance", "essai_sec"))
        self.assertEqual(rem, [])
        f = construit("fin_mod", module={"famille": "finance", "famille_libelle": "Finance et ventes"})
        self.assertEqual(S.resoudre([f])[1], [])                                                # répéter la section du noyau à l'ancienne n'est pas un conflit

    def test_une_section_que_personne_ne_declare_existe_quand_meme(self):
        secs, _ = S.resoudre([construit(module={"section": "mes_outils"})])
        s = next(x for x in secs if x.id == "mes_outils")
        self.assertEqual((s.libelle, s.origine, s.ordre), ("Mes outils", "implicite", S.ORDRE_IMPLICITE))

    def test_les_refuses_sont_une_section_virtuelle_en_dernier(self):
        secs, _ = S.resoudre([], avec_refuses=True)
        self.assertEqual(secs[-1].id, S.REFUSES)
        self.assertNotIn(S.REFUSES, [s.id for s in S.resoudre([])[0]])


class ValidationDesSections(unittest.TestCase):
    def erreurs(self, sections):
        return [e for e in M.valider(man(sections=sections)) if "sections" in e]

    def test_une_declaration_correcte_passe(self):
        self.assertEqual(self.erreurs([{"id": "paye", "libelle": "Paie", "icone": "fam_finance", "icone_trace": "M4 12h16", "ordre": 95}]), [])
        self.assertEqual(self.erreurs([]), [])

    def test_ce_qui_est_refuse(self):
        mauvais = [
            [{"id": "Paye", "libelle": "x"}], [{"id": "p", "libelle": "x"}], [{"id": "paye", "libelle": ""}], [{"id": "paye", "libelle": "x" * 41}],
            [{"id": "paye", "libelle": "x", "icone": "Pas Valide"}], [{"id": "paye", "libelle": "x", "icone_trace": "<script>"}],
            [{"id": "paye", "libelle": "x", "ordre": 0}], [{"id": "paye", "libelle": "x", "ordre": 900}], [{"id": "paye", "libelle": "x", "ordre": True}],
            [{"id": "paye", "libelle": "x", "couleur": "rouge"}], [{"id": "paye", "libelle": "x"}, {"id": "paye", "libelle": "y"}],
            [{"id": "s%d" % i, "libelle": "x"} for i in range(6)], "pas une liste", ["pas une table"],
        ]
        for m in mauvais:
            self.assertTrue(self.erreurs(m), m)


class CatalogueEtApi(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        import CN_main as moteur
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("modules", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "modules"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin("root@x.fr", True)

    def test_le_noyau_rend_les_sections_avec_leurs_comptes(self):
        r = self.n.sections_modules()
        ids = [s["id"] for s in r["sections"]]
        self.assertEqual(ids, sorted(ids, key=lambda i: next(s["ordre"] for s in r["sections"] if s["id"] == i)))
        compte = {s["id"]: s["modules"] for s in r["sections"]}
        self.assertEqual(sum(compte.values()), len(self.n.catalogue_modules()))
        self.assertEqual(r["remarques"], [])
        for s in r["sections"]:
            self.assertEqual(set(s), {"id", "libelle", "icone", "icone_trace", "ordre", "origine", "modules"})

    def test_modules_lister_rend_les_sections_avec_les_modules(self):
        r = self.n.executeur.executer("modules.lister", "humain", {}, compte="root@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("sections", r["resultat"])
        self.assertTrue(all((m["famille"] or "autres") in {s["id"] for s in r["resultat"]["sections"]} for m in r["resultat"]["modules"]))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : man, construit, SectionsDuNoyau, SectionsDesModules, ValidationDesSections, CatalogueEtApi
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
