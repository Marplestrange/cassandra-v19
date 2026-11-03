# ══════════════════════════════════════════════
# TITRE      : Le moteur frugal d'Orfan
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #a93db5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le moins de jetons possible : les règles gratuites d'abord, puis un petit modèle sur le seul point chaud, puis un gros modèle seulement si le petit a échoué.
# MÉTHODE    : trois étages ; chaque étage s'arrête dès qu'une variante équivalente et plus rapide existe ; sans point chaud (profil étalé), aucune dépense.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a93db5 ▼▼▼
"""Le moteur frugal (la famille de FrugalEvo).

  étage 1 · règles déterministes : zéro jeton ;
  étage 2 · un petit modèle (rôle « executant »), prompt réduit à la fonction et à sa ligne chaude : seulement si le profil montre un point chaud (>= 40 % du travail sur une ligne) ;
  étage 3 · un modèle fort (rôle « strategie ») : seulement si l'étage 2 n'a rien rendu de prouvé, et on lui dit ce qui a échoué.

Tourne dans la cage (voir orfan/CN_evolutif.py) : il vérifie ses candidats sur les entrées visibles avant d'en rendre un.
"""


class MoteurFrugal:
    nom = "frugal"

    def __init__(self, orfan, appeler_modele=None, seuil_chaud_pct: float = 40.0):
        self.orfan, self.appeler_modele, self.seuil = orfan, appeler_modele, float(seuil_chaud_pct)
        self.etages = []                                        # ce que chaque étage a fait, dit au journal

    def _valides(self, candidats, source, fonction, entrees):
        sortie, vus = [], set()
        for c in candidats:
            texte = (c if isinstance(c, str) else str(c.get("texte", ""))).rstrip("\n") + "\n"
            if texte in vus:
                continue
            vus.add(texte)
            ok, rapport = self.orfan.comparer_local(source, texte, fonction, entrees)
            if ok and rapport > 1.0:
                hyp = "" if isinstance(c, str) else str(c.get("hypothese", ""))
                sortie.append((rapport, {"texte": texte, "hypothese": "%s (×%.2f sur le vu)" % (hyp or "variante frugale", rapport), "origine": "frugal"}))
        sortie.sort(key=lambda x: -x[0])
        return [c for _, c in sortie]

    def proposer(self, contexte: dict) -> list:
        O = self.orfan
        source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
        budget = max(1, int(contexte.get("budget", 3)))
        trouves = self._valides(O.optimisations(source), source, fonction, entrees)
        self.etages.append("règles : %d variante(s) prouvée(s)" % len(trouves))
        if trouves:
            return trouves[:budget]
        chaud = O.point_chaud(source, fonction, entrees, self.seuil)
        if chaud is None:
            self.etages.append("aucun point chaud : aucune dépense")
            return []
        if self.appeler_modele is None:
            self.etages.append("point chaud à la ligne %d, mais aucun modèle branché" % chaud["ligne"])
            return []
        prompt = O.construire_prompt(dict(contexte, tombes=[]), [chaud])
        try:
            petit = O.extraire_blocs(self.appeler_modele(prompt, "executant"))
        except Exception as e:
            self.etages.append("petit modèle indisponible : %s" % str(e)[:80])
            petit = []
        trouves = self._valides(petit, source, fonction, entrees)
        self.etages.append("petit modèle : %d variante(s) prouvée(s)" % len(trouves))
        if trouves:
            return trouves[:budget]
        note = "\n\nUne première tentative avec un modèle plus petit n'a rien produit de plus rapide ET équivalent. Concentre-toi sur la ligne %d : « %s »." % (chaud["ligne"], chaud["texte"])
        try:
            fort = O.extraire_blocs(self.appeler_modele(prompt + note, "strategie"))
        except Exception as e:
            self.etages.append("modèle fort indisponible : %s" % str(e)[:80])
            return []
        trouves = self._valides(fort, source, fonction, entrees)
        self.etages.append("modèle fort : %d variante(s) prouvée(s)" % len(trouves))
        return trouves[:budget]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un moteur ne s'évolue pas).
# CN : les trois étages et la règle de dépense ; il ne juge jamais, il rend des textes déjà vérifiés sur le vu.
# LIEN : orfan/CN_orfan.py (règles, profil, point chaud, mesure locale), orfan/CN_moteur_hote.py, noyau/CN_moteurs.py.
