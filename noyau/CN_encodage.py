# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le service d'encodage partagé
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #8a0d8b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le service d'encodage partagé : transforme un texte en vecteur (le sens), pour la recherche par le sens de la bibliothèque et de ce qui viendra.
# MÉTHODE    : sentence-transformers, chargé au PREMIER USAGE seulement (2,4 Go en mémoire) ; sans la bibliothèque, il se dit indisponible et rien ne casse.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8a0d8b ▼▼▼
"""Le service d'encodage partagé : un seul modèle pour toute l'instance.

Un fournisseur est un objet qui a `nom`, `pret()` et `encoder(textes, genre)`. `pret()` dit « le modèle peut servir » : la bibliothèque sentence-transformers
est installée et l'encodage n'est pas coupé. Le modèle lui-même ne se charge qu'au premier `encoder` : une machine qui n'a rien à indexer ne paie rien.

Réglages (environnement) : CASSANDRA_EMBED_MODEL (défaut intfloat/multilingual-e5-large : ne pas changer en cours de route, les vecteurs d'un autre modèle ne se comparent pas),
CASSANDRA_EMBED_THREADS (2), CASSANDRA_DISABLE_EMBED=1 (coupe tout)."""
from __future__ import annotations

import importlib.util
import logging
import os
import threading

log = logging.getLogger("noyau.CN_encodage")

MODELE_DEFAUT = "intfloat/multilingual-e5-large"
CACHE_REQUETES = 256


class Encodage:
    def __init__(self, nom: str = ""):
        self.nom = nom or os.environ.get("CASSANDRA_EMBED_MODEL", "").strip() or MODELE_DEFAUT
        self._modele = None
        self._echec = ""
        self._verrou = threading.Lock()
        self._requetes: dict = {}

    def pret(self) -> bool:
        """Le service peut-il servir ? (sans rien charger)"""
        if os.environ.get("CASSANDRA_DISABLE_EMBED") == "1" or self._echec:
            return False
        return importlib.util.find_spec("sentence_transformers") is not None

    def charge(self) -> bool:
        return self._modele is not None

    def _charger(self):
        with self._verrou:
            if self._modele is not None:
                return self._modele
            donnees = os.environ.get("CASSANDRA_DONNEES")
            if donnees:
                os.environ.setdefault("HF_HOME", os.path.join(donnees, "huggingface"))            # les modèles dans le dossier de données, pas dans un dossier personnel
            try:
                import torch
                torch.set_num_threads(int(os.environ.get("CASSANDRA_EMBED_THREADS", "2")))     # le modèle ne doit pas étrangler le reste de la machine
            except Exception:
                pass
            try:
                from sentence_transformers import SentenceTransformer
                self._modele = SentenceTransformer(self.nom)
                log.info("modèle d'encodage « %s » chargé", self.nom)
            except Exception as ex:
                self._echec = str(ex)[:200]
                log.warning("encodage indisponible : %s", ex)
                raise
            return self._modele

    def _prefixe(self, texte: str, genre: str) -> str:
        if "e5" in self.nom.lower():            # les modèles e5 donnent leur pleine qualité seulement avec ces préfixes
            return ("query: " if genre == "query" else "passage: ") + texte
        return texte

    def encoder(self, textes, genre: str = "passage") -> list:
        """Des vecteurs normalisés (le produit scalaire est le cosinus). genre : « passage » (ce qu'on range) ou « query » (ce qu'on cherche)."""
        liste = [str(t or "") for t in textes]
        if genre == "query" and len(liste) == 1 and liste[0][:512] in self._requetes:
            return [self._requetes[liste[0][:512]]]
        modele = self._charger()
        vecs = modele.encode([self._prefixe(t, genre) for t in liste], normalize_embeddings=True, batch_size=8, show_progress_bar=False)
        sortie = [[float(x) for x in v] for v in vecs]
        if genre == "query" and len(liste) == 1:
            if len(self._requetes) >= CACHE_REQUETES:
                self._requetes.pop(next(iter(self._requetes)))
            self._requetes[liste[0][:512]] = sortie[0]
        return sortie


_SERVICE = {"s": None}


def service() -> Encodage:
    """L'unique service de l'instance."""
    if _SERVICE["s"] is None:
        _SERVICE["s"] = Encodage()
    return _SERVICE["s"]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
