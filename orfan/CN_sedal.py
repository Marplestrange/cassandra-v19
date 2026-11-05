# ══════════════════════════════════════════════
# TITRE      : Le moteur évolutif d'Orfan
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #995bca
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Une recherche par populations (générations, archive par niche de taille) : les règles déterministes se composent, un modèle mute le meilleur parent, chaque enfant est mesuré avant d'être gardé.
# MÉTHODE    : graine fixe par point (même entrée, même recherche), forme MAP-Elites réduite (une niche par taille de code), fitness = rapport de temps sur les entrées visibles, équivalence vérifiée d'abord.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=995bca ▼▼▼
"""Le moteur évolutif (la famille d'OpenEvolve, réduite à ce qui tient dans la cage).

Une population de variantes ÉQUIVALENTES sur les entrées visibles. Chaque génération : les meilleurs parents (plus un parent d'une autre niche de taille, pour ne pas s'enfermer dans
une seule forme de code) donnent des enfants — les règles déterministes d'Orfan appliquées au parent, et, si un modèle est branché, une mutation qu'il écrit. Un enfant n'entre dans
l'archive que s'il répond comme la référence sur les entrées visibles ET va plus vite ; l'archive garde un seul représentant par niche (le plus rapide).

TOURNE DANS LA CAGE SEULEMENT (orfan/CN_moteur_hote.py) : il exécute des candidats écrits par un modèle. Le juge du noyau décide ensuite, sur tout le corpus et le jeu réservé.
"""
import ast
import hashlib
import random


class MoteurEvolutif:
    nom = "evolutif"

    def __init__(self, orfan, appeler_modele=None, generations: int = 1, parents: int = 2, essais: int = 2):
        """Mesuré sur 17 fonctions (docs/CN_EVOLUTIF-SEMANTIQUE.md) : une génération trouve les mêmes gains que deux pour 4× moins de temps ; le modèle varie d'un tirage à l'autre, d'où `essais` tirages indépendants par parent."""
        self.orfan, self.appeler_modele = orfan, appeler_modele
        self.generations, self.parents, self.essais = max(1, int(generations)), max(1, int(parents)), max(1, int(essais))
        self.journal = []

    @staticmethod
    def _niche(texte: str) -> int:
        """La niche d'un code : sa taille en lignes, par tranches de 4 (une forme courte et une forme longue ne se font pas concurrence)."""
        return len([l for l in texte.splitlines() if l.strip()]) // 4

    @staticmethod
    def _cle(texte: str) -> str:
        try:
            return ast.dump(ast.parse(texte))
        except SyntaxError:
            return texte

    def proposer(self, contexte: dict) -> list:
        O = self.orfan
        source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
        rng = random.Random(int(hashlib.sha256(str(contexte.get("point", "")).encode("utf-8")).hexdigest()[:8], 16))
        budget = max(1, int(contexte.get("budget", 3)))
        vus = {self._cle(source)}
        archive = {}                                           # niche -> (rapport, texte, hypothèse, génération)

        def examiner(candidats, generation):
            gardes = []
            for c in candidats:
                texte = (c if isinstance(c, str) else str(c.get("texte", ""))).rstrip("\n") + "\n"
                cle = self._cle(texte)
                if cle in vus:
                    continue
                vus.add(cle)
                ok, rapport = O.comparer_local(source, texte, fonction, entrees)
                if not ok or rapport <= 1.0:
                    continue
                hyp = "" if isinstance(c, str) else str(c.get("hypothese", ""))
                niche = self._niche(texte)
                if niche not in archive or rapport > archive[niche][0]:
                    archive[niche] = (rapport, texte, hyp or "variante évolutive", generation)
                    gardes.append(texte)
            return gardes

        examiner(O.optimisations(source), 0)                  # la génération 0 : ce que les règles trouvent seules
        for g in range(1, self.generations + 1):
            classes = sorted(archive.values(), key=lambda v: -v[0])
            if not classes and g == 1:
                parents_texte = [source]
            else:
                pool = [v[1] for v in classes[:self.parents]]
                autres = [v[1] for k, v in archive.items() if v[1] not in pool]
                if autres:
                    pool.append(rng.choice(sorted(autres)))
                parents_texte = pool or [source]
            enfants = []
            for parent in parents_texte:
                if parent is not source:
                    enfants += O.optimisations(parent)             # les règles se composent : un parent déjà amélioré se réduit encore
                if self.appeler_modele is not None:
                    sous = dict(contexte, source_reference=parent)
                    chauds = O.point_chaud(parent, fonction, entrees, 0.0, 0)
                    prompt = O.construire_prompt(sous, [chauds] if chauds else [])
                    for _ in range(self.essais):                   # plusieurs tirages indépendants : un seul peut tomber à côté, les doublons sont écartés par `vus`
                        try:
                            enfants += O.extraire_blocs(self.appeler_modele(prompt, "executant"))
                        except Exception as e:                     # un modèle muet ou plafonné arrête la mutation, pas la recherche : on garde ce qu'on a
                            self.journal.append("génération %d : modèle indisponible (%s)" % (g, str(e)[:80]))
                            self.appeler_modele = None
                            break
            examiner(enfants, g)
        classes = sorted(archive.values(), key=lambda v: -v[0])
        return [{"texte": t, "hypothese": "%s (génération %d, ×%.2f sur le vu)" % (h, gen, r), "origine": "evolutif"} for r, t, h, gen in classes[:budget]]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un moteur d'évolution ne s'évolue pas : c'est du R&D, docs/CN_EVOLUTION.md).
# CN : la recherche par populations ; il ne juge jamais, il rend des textes.
# LIEN : orfan/CN_orfan.py (règles, profil, mesure locale), orfan/CN_moteur_hote.py (qui le fait tourner dans la cage), noyau/CN_moteurs.py.
