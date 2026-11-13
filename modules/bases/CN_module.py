# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bases de données
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : bases
# ZONE       : CN
# VERSION CN : 0.1.0  #c4af87
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bases de données : les bases du serveur, lues par le panneau détecté.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c4af87 ▼▼▼
"""Bases de données : les bases du serveur, lues par le panneau détecté.

Ce module ne nomme aucun panneau. Il demande à Panel Detect quelle capacité sert chaque fonction (« bases », « comptes », « adresse »)
et lit la réponse pour le compte qui regarde. Les gestes (créer, supprimer) ne passent pas par lui : l'écran appelle la capacité
que Panel Detect lui donne, au nom de la personne, avec sa confirmation.

Trois états, dits tels quels à l'écran, jamais confondus :
  - « absent » : aucun panneau piloté ne sert les bases (pas de panneau, deux panneaux, ou un panneau sans module) ;
  - « muet »   : le panneau les sert mais n'a pas répondu (ce n'est pas « aucune base ») ;
  - « ok »     : la liste, éventuellement vide.
"""
from __future__ import annotations


def _liste(valeur) -> list:
    if isinstance(valeur, dict):
        valeur = valeur.get("bases") or valeur.get("items") or []
    return [x for x in (valeur or []) if isinstance(x, dict)]


def brancher(ctx):
    def route(c, fonction: str) -> str:
        """La capacité qui sert la fonction chez le panneau détecté ('' : aucune)."""
        try:
            r = c.executer_lecture("paneldetect.route", fonction=fonction)
        except PermissionError:
            return ""                                                  # Panel Detect n'est pas là : comme un panneau absent
        return str(r.get("capacite") or "") if isinstance(r, dict) else ""

    def lire(c, fonction: str):
        """(état, valeur) : « absent » (aucune route), « muet » (la capacité ne répond pas ou refuse à ce compte), « ok »."""
        cap = route(c, fonction)
        if not cap:
            return "absent", None
        try:
            v = c.executer_lecture(cap)
        except PermissionError:
            return "absent", None
        return ("ok", v) if v is not None else ("muet", None)

    def base(x: dict) -> dict:
        users = [u.strip() for u in str(x.get("utilisateurs") or "").split(",") if u.strip()]
        copie = str(x.get("derniere_copie") or "").strip()
        return {"id": x.get("id"), "nom": str(x.get("nom") or ""), "moteur": str(x.get("moteur") or ""), "taille_mo": x.get("taille_mo"),
                "proprietaire": str(x.get("proprietaire") or ""), "site": str(x.get("site") or ""), "utilisateurs": users,
                "cree": str(x.get("cree") or ""), "derniere_copie": copie, "copiee": bool(copie)}

    def lister(c):
        """Les bases du serveur, avec de quoi remplir le formulaire de création (utilisateurs existants, comptes du panneau) et l'adresse de phpMyAdmin."""
        etat, brut = lire(c, "bases")
        bases = sorted((base(x) for x in _liste(brut)), key=lambda b: b["nom"].lower())
        comptes, adresse = [], ""
        if etat == "ok":
            _, cpts = lire(c, "comptes")
            comptes = sorted({str(x.get("compte") or "") for x in _liste(cpts)} - {""})
            _, adr = lire(c, "adresse")
            adresse = str((adr or {}).get("url") or "") if isinstance(adr, dict) else ""
        utilisateurs = sorted({u for b in bases for u in b["utilisateurs"]})
        return {"etat": etat, "bases": bases, "utilisateurs": utilisateurs, "comptes": comptes, "adresse": adresse,
                "gestes": {"creer": bool(route(c, "base_creer")), "supprimer": bool(route(c, "base_supprimer"))},
                "total_mo": round(sum(float(b["taille_mo"] or 0) for b in bases), 1), "sans_copie": sum(1 for b in bases if not b["copiee"])}

    ctx.implementer("lister", lister)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _liste, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
