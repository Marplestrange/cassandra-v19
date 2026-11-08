# ══════════════════════════════════════════════
# TITRE      : Le gabarit des adaptateurs générés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #a18193
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La partie COMMUNE et relue une fois des adaptateurs que Cassandra génère : tout ce qui juge (extraire le code, écarter le déjà-vu, vérifier l'équivalence sur les exemples) et tout ce qui dit les pannes. Le modèle n'écrit que l'opérateur, `produire`.
# MÉTHODE    : `executer(contexte, modele, produire, nom)` appelle l'opérateur, JAMAIS en avalant son erreur (elle remonte, dite, et le générateur la redonne au modèle pour qu'il corrige) ; puis ne garde que les variantes qui se chargent, rendent le même résultat que la référence sur les entrées d'exemple, et ne sont ni la référence ni une variante déjà refusée.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a18193 ▼▼▼
"""Le gabarit des adaptateurs générés.

Pourquoi : un adaptateur écrit en entier par un modèle contient du code qui juge (équivalence, doublons) et du code qui avale ses pannes ; le relire, c'est relire des centaines de lignes
à chaque fois, et rien ne prouve que l'opérateur marche : une panne avalée rend « aucune variante » comme une recherche sans résultat. Ici, ce code est écrit UNE fois, à la main : le
modèle n'écrit que `produire(contexte, modele)`, qui rend des textes ou des {texte, hypothese}. Une erreur de `produire` n'est jamais avalée.
"""
import copy
import json
import re


class OperateurEnEchec(RuntimeError):
    """L'opérateur du chercheur a levé une erreur : elle est dite, pas cachée derrière une liste vide."""


def _norm(texte):
    return re.sub(r"\s+", " ", str(texte or "")).strip()


def _canon(valeur):
    try:
        return json.dumps(valeur, ensure_ascii=False, sort_keys=True, default=repr, separators=(",", ":"))
    except Exception:
        return repr(valeur)


def _code(brut, fonction):
    """Le code d'une réponse. Le premier « ``` » rencontré n'est pas forcément la fin du bloc (le code peut en contenir) : de la première barrière à la dernière, puis à la suivante."""
    texte = str(brut or "").strip()
    candidats = []
    for motif in (r"```(?:python|py)?[ \t]*\n(.*)```", r"```(?:python|py)?[ \t]*\n(.*?)```"):
        m = re.search(motif, texte, re.S | re.I)
        if m:
            candidats.append(m.group(1).strip())
    candidats.append(texte)
    for c in candidats:
        if re.search(r"(?m)^\s*(?:async\s+)?def\s+" + re.escape(fonction) + r"\s*\(", c):
            try:
                compile(c, "<variante>", "exec")
                return c.strip() + "\n"
            except SyntaxError:
                continue
    return ""


def _charger(code, fonction):
    ns = {}
    try:
        exec(compile(code, "<variante>", "exec"), ns)
    except Exception:
        return None
    f = ns.get(fonction)
    return f if callable(f) else None


def executer(contexte, modele, produire, nom="adaptateur"):
    """Les variantes que l'opérateur `produire` propose et qui tiennent : [{texte, hypothese}], au plus `budget`."""
    source = str(contexte.get("source_reference") or "")
    fonction = str(contexte.get("fonction") or "")
    entrees = list(contexte.get("entrees") or [])[:12]
    try:
        budget = max(1, int(contexte.get("budget", 3)))
    except (TypeError, ValueError):
        budget = 3
    try:
        brut = produire(contexte, modele)
    except Exception as e:
        raise OperateurEnEchec("l'opérateur de « %s » a échoué : %s : %s" % (nom, type(e).__name__, str(e)[:300]))
    if brut is None:
        brut = []
    if isinstance(brut, (str, dict)):
        brut = [brut]
    if not isinstance(brut, (list, tuple)):
        raise OperateurEnEchec("l'opérateur de « %s » doit rendre une liste de textes ou de {texte, hypothese}, il a rendu %s" % (nom, type(brut).__name__))
    ref = _charger(source, fonction)
    attendu = []
    for e in entrees:
        try:
            attendu.append(_canon(ref(copy.deepcopy(e))) if ref else None)
        except Exception:
            attendu.append(None)                                                     # la référence elle-même lève sur cette entrée : on ne peut pas trancher, on la saute
    vus = {_norm(source)}
    for t in contexte.get("tombes") or []:
        vus.add(_norm(t.get("texte") if isinstance(t, dict) else t))
        c = _code(t.get("texte") if isinstance(t, dict) else t, fonction)
        if c:
            vus.add(_norm(c))
    sortie, raisons = [], []
    for item in brut:
        texte, hypothese = (item.get("texte") or item.get("code") or item.get("source") or "", item.get("hypothese") or "") if isinstance(item, dict) else (item, "")
        code = _code(texte, fonction)
        if not code:
            raisons.append("sans code de la fonction « %s » (texte : %r)" % (fonction, str(texte)[:90]))
            continue
        if _norm(code) in vus:
            raisons.append("déjà vu (la référence ou une variante refusée)")
            continue
        cand = _charger(code, fonction)
        if cand is None:
            raisons.append("le code ne se charge pas ou ne définit pas « %s »" % fonction)
            continue
        equivalent, pourquoi = True, ""
        for e, att in zip(entrees, attendu):
            if att is None:
                continue
            try:
                obtenu = _canon(cand(copy.deepcopy(e)))
            except Exception as ex:
                equivalent, pourquoi = False, "lève %s sur %s" % (type(ex).__name__, str(e)[:40])
                break
            if obtenu != att:
                equivalent, pourquoi = False, "rend %s au lieu de %s sur %s" % (obtenu[:40], att[:40], str(e)[:40])
                break
        if not equivalent:
            raisons.append("pas équivalente : " + pourquoi)
            continue
        vus.add(_norm(code))
        sortie.append({"texte": code, "hypothese": (str(hypothese).strip() or "%s : variante proposée" % nom)[:300]})
        if len(sortie) >= budget:
            break
    if not sortie and contexte.get("controle"):                                     # à l'essai à blanc, « rien » doit s'expliquer : les raisons sont redonnées au modèle pour qu'il corrige
        raise OperateurEnEchec("l'opérateur de « %s » a rendu %d proposition(s) et toutes ont été écartées : %s" % (nom, len(brut), " ; ".join(raisons)[:600] or "il n'a rien rendu"))
    return sortie
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un gabarit ne s'évolue pas).
# CN : le socle commun des adaptateurs générés ; il juge à la place de l'opérateur et ne cache aucune panne.
# LIEN : noyau/CN_adaptateur_gen.py (qui ajoute `proposer` en pied de chaque adaptateur généré), orfan/CN_moteur_hote.py (qui charge l'adaptateur).
