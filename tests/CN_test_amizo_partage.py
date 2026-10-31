# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Amizo ne lit que du partagé d'une société (champ `partage`, acteur amizo)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b3ae3b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Amizo ne lit que du partagé d'une société : le champ `partage`, l'acteur « amizo » jamais par défaut, l'invariant sur tous les manifestes.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b3ae3b ▼▼▼
"""Amizo (la connaissance) ne lit que du PARTAGÉ d'une société : le champ `partage` d'une capacité, l'acteur « amizo » jamais par défaut, et l'invariant sur tous les manifestes."""
import copy
import shutil
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                          # noqa: E402
from noyau import CN_manifeste as mf                              # noqa: E402


def manifestes_bruts():
    for p in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        with open(p, "rb") as f:
            yield p.parent.name, tomllib.load(f)


def brut_societes():
    with open(RACINE / "modules" / "societes" / "CN_manifeste.toml", "rb") as f:
        return tomllib.load(f)


def erreurs_de(brut, **champs):
    """Les erreurs de validation de la capacité `carte` de « societes », une fois ses champs remplacés."""
    b = copy.deepcopy(brut)
    for c in b["capacites"]:
        if c["id"] == "carte":
            c.update(champs)
            for k in [k for k, v in champs.items() if v is None]:
                c.pop(k)
    return [x for x in mf.valider(b) if "carte" in x]


class ChampPartage(unittest.TestCase):
    def test_la_reference_est_valide(self):
        self.assertEqual(erreurs_de(brut_societes()), [])

    def test_amizo_est_un_acteur_connu_mais_jamais_un_defaut(self):
        self.assertIn("amizo", mf.ACTEURS)
        brut = brut_societes()
        sans_qui = [c for c in brut["capacites"] if "qui" not in c]
        self.assertTrue(sans_qui)
        for m in mf.construire(brut).capacites:
            if m.id not in {c["id"] for c in brut["capacites"] if "amizo" in c.get("qui", ())}:
                self.assertNotIn("amizo", m.qui, m.id)

    def test_partage_vide_par_defaut_et_lu_par_construire(self):
        caps = {c.id: c for c in mf.construire(brut_societes()).capacites}
        self.assertEqual(caps["carte"].partage, "societe")
        self.assertEqual(caps["lister"].partage, "")

    def test_valeur_inconnue_refusee(self):
        e = erreurs_de(brut_societes(), partage="monde")
        self.assertTrue(any("partage" in x and "inconnu" in x for x in e), e)

    def test_partage_refuse_sur_une_ecriture(self):
        e = erreurs_de(brut_societes(), risque="faible", partage="societe", perimetre=["x"], preuve="p", retour="r", qui=["itare"])
        self.assertTrue(any("partage" in x and "lecture" in x for x in e), e)

    def test_amizo_exige_la_lecture(self):
        e = erreurs_de(brut_societes(), risque="faible", perimetre=["x"], preuve="p", retour="r", partage=None, qui=["amizo"])
        self.assertTrue(any("amizo" in x and "lecture" in x for x in e), e)

    def test_amizo_lit_le_web_sans_partage(self):
        self.assertEqual(erreurs_de(brut_societes(), partage=None, externe=True, qui=["amizo"]), [])

    def test_la_liste_blanche_des_ecritures_est_courte(self):
        self.assertEqual(mf.ECRITURES_AMIZO, ("bibliotheque.noter", "information.transmettre"))
        b = brut_societes()
        for c in b["capacites"]:
            if c["id"] == "carte":
                c.update(risque="faible", perimetre=["x"], preuve="p", retour="r", qui=["amizo"], partage="")
        b["module"]["id"] = "bibliotheque"
        b["capacites"] = [dict(c, id="noter") if c["id"] == "carte" else c for c in b["capacites"]]
        self.assertEqual([x for x in mf.valider(b) if "amizo" in x], [])      # bibliotheque.noter : permise
        b["module"]["id"] = "societes"
        self.assertTrue([x for x in mf.valider(b) if "amizo" in x])           # societes.noter : refusée

    def test_amizo_exige_le_partage(self):
        e = erreurs_de(brut_societes(), partage=None, qui=["amizo"])
        self.assertTrue(any("amizo" in x and "partage" in x for x in e), e)
        self.assertEqual(erreurs_de(brut_societes(), qui=["amizo"]), [])


class InvarianteDuDepot(unittest.TestCase):
    def test_tout_amizo_du_depot_lit_du_partage(self):
        vus = 0
        for mod, brut in manifestes_bruts():
            for c in brut.get("capacites", []) or []:
                ou = "%s.%s" % (mod, c.get("id"))
                if c.get("partage"):
                    self.assertEqual(c.get("risque"), "lecture", ou + " : `partage` n'existe que sur une lecture")
                    self.assertIn(c["partage"], mf.PARTAGES, ou)
                if "amizo" in (c.get("qui") or ()):
                    vus += 1
                    if ou in mf.ECRITURES_AMIZO:
                        continue
                    self.assertEqual(c.get("risque"), "lecture", ou + " : amizo n'agit jamais (hors liste blanche)")
                    self.assertTrue(c.get("partage") in mf.PARTAGES or c.get("externe"), ou + " : amizo ne lit que du partagé ou du web")
        self.assertGreaterEqual(vus, 1)

    def test_les_modules_exclus_n_ont_pas_amizo(self):
        for mod, brut in manifestes_bruts():
            if mod in ("coffre", "flotte", "modules", "telegram", "billetterie", "ged", "projets", "salon", "notes"):
                for c in brut.get("capacites", []) or []:
                    self.assertNotIn("amizo", c.get("qui") or (), "%s.%s" % (mod, c.get("id")))


class OutilsDAmizo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("societes", "ged", "projets", "salon"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("societes", "ged", "projets", "salon"):
            self.n.activer(m)

    def test_amizo_n_a_que_des_lectures_partagees(self):
        outils = self.n._outils("", "amizo")
        self.assertTrue(outils, "au moins la carte de la société")
        for o in outils:
            e = self.n.catalogue.get(o["cle"])
            if o["cle"] in mf.ECRITURES_AMIZO:
                continue
            self.assertEqual(e.capacite.risque, "lecture", o["cle"])
            self.assertTrue(e.capacite.partage == "societe" or e.capacite.externe, o["cle"])
            self.assertEqual(o["partage"], e.capacite.partage, o["cle"])
        self.assertIn("societes__carte", {o["nom"] for o in outils})

    def test_un_acteur_ordinaire_voit_aussi_le_champ_mais_pas_amizo_les_autres(self):
        cles_amizo = {o["cle"] for o in self.n._outils("", "amizo")}
        autres = {o["cle"]: o for o in self.n._outils("", "itare")}
        self.assertTrue(cles_amizo <= set(autres))
        self.assertTrue(len(autres) > len(cles_amizo))
        for k, o in autres.items():
            self.assertEqual(o["partage"], "societe" if k in cles_amizo else "", k)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Catalogue
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)

