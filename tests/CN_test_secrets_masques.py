# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des secrets (agents et journal)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #2f0007
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de deux garde-fous : aucun agent n'atteint le coffre (sauf Cassandra, qui gère sans jamais lire une valeur), et aucun secret ne finit en clair dans le journal d'événements.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2f0007 ▼▼▼
"""Bancs de deux garde-fous.

1. Le coffre n'est à aucun agent : ni Itare, ni un agent invité. Cassandra seule le gère (poser, retirer, lister les NOMS) ; la VALEUR d'un secret n'entre
   jamais dans le contexte d'un modèle, donc `coffre.get` n'est un outil pour personne.
2. Tout paramètre qui porte un secret est dans le `masque` de sa capacité : le journal d'événements ne garde jamais un mot de passe ni un jeton en clair.
"""
import inspect
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

SECRETS = {"mot_de_passe", "password", "jeton", "token", "secret", "cle_secrete"}
# `cle` est tantôt un simple nom (de réglage, de profil, d'épingle...), tantôt une clé privée : seules ces capacités le sont, noms de clé et rien d'autre.
CLE_EST_UN_NOM = {
    "affichage.desepingler", "affichage.epingler", "billetterie.legal_modele", "billetterie.legal_page_save", "billetterie.public_legal",
    "memoire.ecrire", "memoire.rappel_poser", "mesures.prevision", "mesures.profil", "mesures.serie", "modules.retour_arriere",
    "notifications.emettre", "notifications.resoudre", "proactif.debloquer", "proactif.regler", "proactif.remettre",
    "reglages.historique", "reglages.regler", "reglages.regler_secret", "reglages.reinitialiser",
}


class Monde(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        base = Path(cls.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules", mods, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        cls.inactifs = []
        for d in sorted(mods.iterdir()):
            if d.is_dir() and not cls.n.activer(d.name).get("ok"):
                cls.inactifs.append(d.name)           # un module qui demande une installation n'a pas de capacités à regarder ici


class Garde(Monde):
    def outils(self, acteur):
        ctx = self.n.executeur.contextes["agents"]          # le module des agents a demandé d'agir : c'est par lui que passent les outils
        return {t["cle"] for t in ctx.outils(acteur) if t["cle"].startswith("coffre.")}

    def test_ni_itare_ni_un_agent_invite_n_ont_un_outil_du_coffre(self):
        for acteur in ("itare", "agent"):
            self.assertEqual(self.outils(acteur), set(), acteur)

    def test_cassandra_gere_sans_jamais_lire_une_valeur(self):
        self.assertEqual(self.outils("cassandra"), {"coffre.set", "coffre.delete", "coffre.list"})

    def test_toute_capacite_du_coffre_refuse_itare_et_un_agent(self):
        for e in self.n.catalogue.lister():
            if e.module == "coffre":
                for acteur in ("itare", "agent"):
                    self.assertNotIn(acteur, e.capacite.qui, "%s ouverte à %s" % (e.cle, acteur))
        r = self.n.executeur.executer("coffre.get", "itare", {"name": "x"}, compte="")
        self.assertEqual(r["statut"], "refuse")

    def test_la_valeur_d_un_secret_est_masquee_au_journal(self):
        self.assertIn("valeur", self.n.catalogue.get("coffre.set").capacite.masque)
        self.assertIn("valeur", self.n.catalogue.get("coffre.get").capacite.masque)


    def test_un_parametre_secret_est_toujours_dans_le_masque(self):
        fautes, vus = [], 0
        for e in self.n.catalogue.lister():
            if e.faire is None:
                continue
            vus += 1
            noms = [p.name for p in list(inspect.signature(e.faire).parameters.values())[1:]]
            secrets = SECRETS | ({"cle"} if e.cle not in CLE_EST_UN_NOM else set())
            fautes += ["%s : « %s » n'est pas dans le masque" % (e.cle, p) for p in noms if p in secrets and p not in e.capacite.masque]
        self.assertGreater(vus, 100, "le parcours n'a presque rien vu : les modules ne se sont pas activés (%s)" % self.inactifs)
        self.assertEqual(fautes, [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲


# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Garde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
