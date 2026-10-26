# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : Les dépendances versionnées des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #62d7b5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les dépendances versionnées des modules : plages de version, conflits, modules suggérés, services fournis.
# MÉTHODE    : fabrique des manifestes d'essai en mémoire et éprouve l'ordre, les refus et les messages
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=62d7b5 ▼▼▼
"""Un module requiert « dns >=0.2, <1 » : la version installée doit y répondre. Il peut refuser la compagnie d'un autre (`conflits`), en suggérer un (`suggere`) et
fournir un nom de service (`fournit = ["courrier"]`) qu'un autre requiert sans savoir QUEL module le rend."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as M  # noqa: E402


def mod(mid, version="1.0.0", **plus):
    m = {"id": mid, "nom": mid.capitalize(), "version": version, "noyau_min": "0.1.0", "description": "Module d'essai " + mid, "confiance": "interne"}
    m.update(plus)
    return M.construire({"module": m}, "essai")


class Versions(unittest.TestCase):
    def test_les_versions_se_comparent_chiffre_a_chiffre(self):
        self.assertEqual(M.version_de("0.2.1"), (0, 2, 1))
        self.assertTrue(M.satisfait("0.10.0", ">=0.9"))              # 10 > 9 : pas une comparaison de textes
        self.assertTrue(M.satisfait("1.2", ">=1.2.0"))
        self.assertTrue(M.satisfait("0.2.1", ">=0.2, <1"))
        self.assertFalse(M.satisfait("1.0.0", ">=0.2, <1"))
        self.assertFalse(M.satisfait("0.1.9", ">=0.2"))
        self.assertTrue(M.satisfait("2.0", ""))                      # sans contrainte : toujours satisfaite
        self.assertTrue(M.satisfait("1.4.0-beta", "==1.4.0"))

    def test_une_dependance_s_ecrit_avec_ou_sans_contrainte(self):
        self.assertEqual(M.lire_requis("dns"), ("dns", ""))
        self.assertEqual(M.lire_requis("dns >=0.2, <1"), ("dns", ">=0.2, <1"))
        for mauvais in ("dns >=", "DNS", "dns ~0.2", "dns >=a.b", ""):
            self.assertIsNone(M.lire_requis(mauvais), mauvais)


class Ensemble(unittest.TestCase):
    def test_une_version_insuffisante_est_dite(self):
        e = M.verifier_ensemble([mod("dns", "0.1.0"), mod("certificats", requiert=["dns >=0.2"])])
        self.assertTrue(any("requiert « dns >=0.2 » mais la version installée est 0.1.0" in x for x in e), e)

    def test_une_version_suffisante_ne_dit_rien(self):
        self.assertEqual(M.verifier_ensemble([mod("dns", "0.2.1"), mod("certificats", requiert=["dns >=0.2, <1"])]), [])

    def test_un_service_fourni_satisfait_la_dependance_et_fixe_l_ordre(self):
        ms = [mod("alerte", requiert=["courrier"]), mod("imap", fournit=["courrier"])]
        self.assertEqual(M.verifier_ensemble(ms), [])
        self.assertEqual(M.ordre_installation(ms), ["imap", "alerte"])                     # le fournisseur d'abord
        self.assertEqual(M.avec_dependances(ms, ["alerte"]), ["imap", "alerte"])

    def test_un_service_sans_fournisseur_est_dit_absent(self):
        e = M.verifier_ensemble([mod("alerte", requiert=["courrier"])])
        self.assertTrue(any("requiert « courrier »" in x for x in e), e)

    def test_l_id_exact_l_emporte_sur_un_fournisseur(self):
        ms = [mod("courrier"), mod("autre", fournit=["courrier"]), mod("alerte", requiert=["courrier"])]
        self.assertEqual(M.requis_reels(ms[2], {m.id: m for m in ms}, M.fournisseurs(ms)), ["courrier"])


class Validation(unittest.TestCase):
    def brut(self, **plus):
        d = {"id": "essai", "nom": "Essai", "version": "1.0.0", "noyau_min": "0.1.0", "description": "x", "confiance": "interne"}
        d.update(plus)
        return {"module": d}

    def test_les_champs_nouveaux_se_valident(self):
        self.assertEqual(M.valider(self.brut(requiert=["dns >=0.2"], conflits=["autre"], suggere=["x" * 3], fournit=["courrier"])), [])
        self.assertTrue(any("mal écrit" in e for e in M.valider(self.brut(requiert=["dns >="]))))
        self.assertTrue(any("se citer lui-même" in e for e in M.valider(self.brut(conflits=["essai"]))))
        self.assertTrue(any("requérir et refuser" in e for e in M.valider(self.brut(requiert=["dns"], conflits=["dns"]))))

    def test_le_manifeste_garde_les_ids_dans_requiert_et_les_contraintes_a_part(self):
        m = mod("certificats", requiert=["dns >=0.2", "droits"], conflits=["xx"], suggere=["yy"], fournit=["tls"])
        self.assertEqual(m.requiert, ("dns", "droits"))
        self.assertEqual(m.contraintes, (("dns", ">=0.2"),))
        self.assertEqual((m.conflits, m.suggere, m.fournit), (("xx",), ("yy",), ("tls",)))


class PointsExtension(unittest.TestCase):
    def brut(self, **extra):
        d = {"module": {"id": "essai", "nom": "Essai", "version": "1.0.0", "noyau_min": "0.1.0", "description": "x", "confiance": "interne"}}
        d.update(extra)
        return d

    def test_la_declaration_se_valide(self):
        ok = self.brut(points_extension=[{"id": "colonne", "libelle": "Une colonne", "attend": ["titre"]}],
                       contributions=[{"point": "autre:liste", "id": "ma_colonne", "libelle": "Ma colonne", "donnees": {"titre": "Prix", "largeur": 80, "gras": True}}])
        self.assertEqual(M.valider(ok), [])
        mauvais = self.brut(points_extension=[{"id": "Mal Ecrit", "libelle": "x"}], contributions=[{"point": "pasbon", "id": "cc", "libelle": "x", "donnees": {"k": [1, 2]}}])
        e = " | ".join(M.valider(mauvais))
        self.assertIn("identifiant invalide", e)
        self.assertIn("« module:point » attendu", e)
        self.assertIn("valeurs simples", e)

    def test_une_contribution_vers_un_point_inexistant_ou_incomplete_est_un_defaut(self):
        hote = M.construire(self.brut(points_extension=[{"id": "colonne", "libelle": "Une colonne", "attend": ["titre"]}]), "essai")
        hote = M.construire({"module": dict(self.brut()["module"], id="hote"), "points_extension": [{"id": "colonne", "libelle": "Une colonne", "attend": ["titre"]}]}, "essai")

        def invite(point, donnees):
            return M.construire({"module": dict(self.brut()["module"], id="invite"), "contributions": [{"point": point, "id": "cc", "libelle": "C", "donnees": donnees}]}, "essai")
        self.assertEqual(M.verifier_ensemble([hote, invite("hote:colonne", {"titre": "Prix"})]), [])
        self.assertTrue(any("n'offre pas ce point" in x for x in M.verifier_ensemble([hote, invite("hote:inconnu", {})])))
        self.assertTrue(any("doit porter : titre" in x for x in M.verifier_ensemble([hote, invite("hote:colonne", {})])))
        self.assertEqual(M.verifier_ensemble([invite("absent:colonne", {})]), [])           # le module visé n'est pas installé : la contribution dort


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc des dépendances versionnées.
# EC : néant.
# LIEN : noyau/CN_manifeste.py (version_de, satisfait, lire_requis, fournisseurs, requis_reels, verifier_ensemble).
