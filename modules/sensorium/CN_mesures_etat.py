# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'état d'une mesure, calculé sans rien lire ni écrire
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.3.0  #c1ce40
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'état d'une mesure, calculé sans rien lire ni écrire : fonctions pures (l'heure arrive en paramètre).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=c1ce40 ▼▼▼
"""L'état d'une mesure, calculé sans rien lire ni écrire : fonctions pures (l'heure arrive en paramètre).

Le silence n'est jamais un « ok » : une mesure est `ok`, `alerte` ou `inconnu`. Une lecture trop ancienne, de confiance trop basse, ou jugée avec une horloge qui n'est pas fiable donne `inconnu`.
La fraîcheur se juge sur l'instant où NOUS avons reçu la lecture (`recu_a`), jamais sur celui que l'émetteur revendique (`observe_a`) : une machine sans horloge matérielle peut dire n'importe quelle heure.
"""
import re

CLE = re.compile(r"^[a-z0-9][a-z0-9_.:/\-]{0,119}$")
ESPACE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,39}$")
HORLOGE_MIN = 1735689600            # 2025-01-01 UTC : avant, l'horloge de CETTE machine n'a pas été réglée (pas de pile, pas encore de NTP)
DECALAGE_MAX_S = 300                # au-delà, l'heure revendiquée par l'émetteur est jugée fausse
FUSION_S = 30                       # une clé n'annonce pas deux changements à moins de 30 s
GRAVITES = ("ok", "warning", "critical")
ETATS = ("ok", "alerte", "inconnu")
VISIBILITES = ("instance", "toutes")


_INVISIBLES = re.compile("[" + chr(0) + "-" + chr(31) + chr(127) + "-" + chr(159) + chr(0x200b) + "-" + chr(0x200f) + chr(0x2028) + "-" + chr(0x202e) + chr(0x2060) + "-" + chr(0x2069) + chr(0xfeff) + "]")
_BLANCS = re.compile(r"\s+")


def texte_sur(valeur, longueur) -> str:
    """Le texte libre d'un capteur, sans rien qui trompe l'œil ou le terminal : plus de caractères de contrôle (échappements de terminal compris), de retournement du sens d'écriture ni de caractères de
    largeur nulle ; les retours à la ligne et tabulations deviennent un espace ; coupé à `longueur`. Les chevrons ne sont PAS touchés : échapper ici ferait un double échappement à l'affichage,
    et c'est à l'écran de traiter ce texte comme du texte (textContent), jamais comme du balisage."""
    t = "" if valeur is None else str(valeur)
    t = _BLANCS.sub(" ", t.replace(chr(0), ""))
    return _INVISIBLES.sub("", t).strip()[: max(0, int(longueur))]


def cle_valide(cle) -> bool:
    return isinstance(cle, str) and bool(CLE.match(cle))


def espace_de(cle: str) -> str:
    """L'espace de noms d'une clé : ce qui précède le premier point (« dns.resolveur.latence » -> « dns »)."""
    return str(cle).split(".", 1)[0].split(":", 1)[0]


def horloge_fiable(maintenant: float) -> bool:
    return isinstance(maintenant, (int, float)) and maintenant >= HORLOGE_MIN


def nombre(v):
    """Un nombre fini, ou None (un booléen n'est pas une mesure)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v and v not in (float("inf"), float("-inf")) else None


def gravite_des_seuils(valeur, alerte=None, critique=None, pire="haut") -> str:
    """`ok`, `warning` ou `critical` d'une valeur numérique selon les seuils du capteur (« haut » : trop grand est mauvais ; « bas » : trop petit)."""
    v = nombre(valeur)
    if v is None:
        return "ok"
    a, c = nombre(alerte), nombre(critique)
    if pire == "bas":
        if c is not None and v <= c:
            return "critical"
        return "warning" if a is not None and v <= a else "ok"
    if c is not None and v >= c:
        return "critical"
    return "warning" if a is not None and v >= a else "ok"


def confiance_effective(declaree, decalage_s=0) -> float:
    """La confiance déclarée (0 à 1, 1 par défaut), plafonnée à 0,5 quand l'heure de l'émetteur s'écarte de la nôtre de plus de cinq minutes."""
    c = nombre(declaree)
    c = 1.0 if c is None else max(0.0, min(1.0, c))
    if abs(decalage_s or 0) > DECALAGE_MAX_S:
        c = min(c, 0.5)
    return round(c, 3)


def decalage(observe_a, recu_a):
    """Écart (secondes) entre l'heure revendiquée et la nôtre, ou None si l'émetteur n'en a pas donné."""
    o = nombre(observe_a)
    return None if o is None else round(o - float(recu_a), 1)


def calculer_etat(lecture, capteur, maintenant) -> dict:
    """{etat, raison, age_s, niveau}. `lecture` : {recu_a, gravite, confiance} ou None ; `capteur` : {fraicheur_s, confiance_min} ou None."""
    if not horloge_fiable(maintenant):
        return {"etat": "inconnu", "raison": "horloge de la machine non fiable", "age_s": None, "niveau": "inconnu"}
    if not lecture:
        return {"etat": "inconnu", "raison": "jamais lue", "age_s": None, "niveau": "inconnu"}
    recu = nombre(lecture.get("recu_a"))
    if recu is None:
        return {"etat": "inconnu", "raison": "lecture sans date de réception", "age_s": None, "niveau": "inconnu"}
    if recu > maintenant + DECALAGE_MAX_S:
        return {"etat": "inconnu", "raison": "lecture datée du futur : l'horloge a reculé", "age_s": None, "niveau": "inconnu"}
    age = max(0.0, maintenant - recu)
    fraicheur = nombre((capteur or {}).get("fraicheur_s")) or 300.0
    if age > fraicheur:
        return {"etat": "inconnu", "raison": "muette depuis %d s (attendue toutes les %d s)" % (age, fraicheur), "age_s": round(age, 1), "niveau": "inconnu"}
    mini = nombre((capteur or {}).get("confiance_min")) or 0.0
    conf = nombre(lecture.get("confiance"))
    if conf is not None and conf < mini:
        return {"etat": "inconnu", "raison": "confiance insuffisante (%.2f < %.2f)" % (conf, mini), "age_s": round(age, 1), "niveau": "inconnu"}
    g = lecture.get("gravite") if lecture.get("gravite") in GRAVITES else "ok"
    return {"etat": "ok" if g == "ok" else "alerte", "raison": "", "age_s": round(age, 1), "niveau": g}


def doit_annoncer(etat_annonce, etat_nouveau, derniere_annonce, maintenant) -> bool:
    """Un changement d'état s'annonce au bus s'il diffère du dernier annoncé et si la dernière annonce de cette clé a plus de FUSION_S secondes.
    Un état qui revient à celui déjà annoncé pendant la fusion ne dit rien (le va-et-vient est fusionné)."""
    if etat_nouveau == etat_annonce:
        return False
    return derniere_annonce is None or maintenant - derniere_annonce >= FUSION_S


def visible_pour(visibilite, societe, privilegie) -> bool:
    """Qui voit l'état d'une clé : un privilégié (administrateur, moteur interne) toujours ; sinon `toutes`, ou `societes:1,2` quand la société de l'acte y figure. Défaut : personne d'autre."""
    if privilegie:
        return True
    v = str(visibilite or "instance")
    if v == "toutes":
        return True
    if v.startswith("societes:") and societe:
        return str(societe) in [x for x in v[len("societes:"):].split(",") if x]
    return False


def visibilite_valide(v) -> bool:
    if v in VISIBILITES:
        return True
    return isinstance(v, str) and bool(re.match(r"^societes:[A-Za-z0-9_\-]{1,40}(,[A-Za-z0-9_\-]{1,40}){0,19}$", v))


def raison_courte(raison) -> str:
    """La raison sans chiffres (« muette », « confiance insuffisante ») : la fraîcheur attendue et les niveaux de confiance sont de l'infrastructure."""
    return str(raison or "").split(" (")[0].split(" depuis")[0]


def minimal(cle, libelle, calcul, depuis) -> dict:
    """Ce qu'un utilisateur ordinaire voit : jamais la valeur, le détail, l'unité, l'hôte ni la confiance."""
    raison = raison_courte(calcul["raison"]) if calcul["etat"] == "inconnu" else ""        # « muette », jamais les chiffres (fraîcheur attendue, confiance)
    return {"cle": cle, "libelle": libelle, "etat": calcul["etat"], "depuis": depuis, "raison": raison}


def invisible(cle) -> dict:
    """La réponse pour une clé inconnue OU non publiée pour le demandeur : la même forme, sans raison, pour ne pas révéler l'existence."""
    return {"cle": cle, "libelle": "", "etat": "inconnu", "depuis": None, "raison": ""}


def prevision(points, seuil, pire, pente_fn, maintenant_j=None) -> dict:
    """Combien de jours avant le seuil. `points` : [(t_jours, valeur)] ; `pente_fn` : le point d'évolution `pente` ([points] -> (pente par jour, r²)).
    Ne rend jamais une date inventée : moins de six points, ajustement trop lâche (r² < 0,5) ou pente du mauvais côté disent pourquoi on ne conclut pas."""
    pts = [(float(t), float(v)) for t, v in points if nombre(t) is not None and nombre(v) is not None]
    s = nombre(seuil)
    if s is None:
        return {"conclu": False, "raison": "pas de seuil à atteindre"}
    if len(pts) < 6:
        return {"conclu": False, "raison": "moins de six points : aucune tendance"}
    pente, r2 = pente_fn(pts)
    if pente is None:
        return {"conclu": False, "raison": "série sans variation de temps"}
    r2 = float(r2 or 0.0)
    derniere = pts[-1][1]
    if (pire == "bas" and derniere <= s) or (pire != "bas" and derniere >= s):
        return {"conclu": True, "jours_avant_seuil": 0.0, "pente_par_jour": round(pente, 4), "r2": round(r2, 3), "raison": "le seuil est déjà atteint"}
    if r2 < 0.5:
        return {"conclu": False, "raison": "tendance trop irrégulière (r² %.2f)" % r2, "pente_par_jour": round(pente, 4), "r2": round(r2, 3)}
    if (pire == "bas" and pente >= 0) or (pire != "bas" and pente <= 0):
        return {"conclu": False, "raison": "la mesure ne s'approche pas du seuil", "pente_par_jour": round(pente, 4), "r2": round(r2, 3)}
    return {"conclu": True, "jours_avant_seuil": round((s - derniere) / pente, 2), "pente_par_jour": round(pente, 4), "r2": round(r2, 3), "raison": ""}


def impact(liens, depart, profondeur=6, noeuds_max=200) -> dict:
    """Qui est touché si `depart` tombe : on remonte les dépendances (X `depend_de` Y : si Y tombe, X est touché). `liens` : [(de, relation, vers)].
    Parcours en largeur, sans boucle, borné en profondeur et en nombre de nœuds."""
    en_amont = {}
    for de, rel, vers in liens:
        en_amont.setdefault(vers, []).append((de, rel))
    vus, front, niveau, touches, tronque = {depart}, [depart], 0, [], False
    while front and niveau < profondeur:
        niveau += 1
        suite = []
        for n in front:
            for de, rel in sorted(en_amont.get(n, [])):
                if de in vus:
                    continue
                if len(touches) >= noeuds_max:
                    tronque = True
                    break
                vus.add(de)
                touches.append({"objet": de, "via": n, "relation": rel, "distance": niveau})
                suite.append(de)
        front = suite
    reste = bool(front) and niveau >= profondeur and any(d not in vus for n in front for d, _ in en_amont.get(n, []))
    return {"depart": depart, "touches": touches, "tronque": tronque or reste}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : cle_valide, espace_de, horloge_fiable, nombre, gravite_des_seuils, confiance_effective, decalage, calculer_etat …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
