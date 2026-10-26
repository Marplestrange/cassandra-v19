# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'autonomie de Cassandra sur les modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modules
# ZONE       : CN
# VERSION CN : 0.1.0  #064fcc
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'autonomie de Cassandra sur les modules : ce qu'elle fait seule, ce qu'elle se refuse, et le récit de ce qu'elle a fait.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=064fcc ▼▼▼
"""L'autonomie de Cassandra sur les modules : ce qu'elle fait seule, ce qu'elle se refuse, et le récit de ce qu'elle a fait.

Le principe (IA souveraine) : Cassandra n'attend JAMAIS un utilisateur pour agir sur les modules ; l'utilisateur peut agir aussi, en parallèle.
La sûreté ne vient donc pas d'une permission mais de la réversibilité : chaque geste est prouvé, a son retour arrière, et laisse un
récit où chaque acte porte le geste qui le défait ET le pourquoi. Le réglage « autonomie » ne dit pas « à qui demander » : il dit jusqu'où Cassandra va.

  observer   : elle regarde et raconte ce qu'elle ferait ; elle n'agit pas.
  entretien  : elle entretient (module révoqué retiré, mise à jour sans permission en plus, module en échec mis en pause, remise de version).
  reine      : elle gère tout (en plus : elle ajoute et retire des modules, et prend des mises à jour qui demandent plus de permissions).

Ce qu'elle ne fait seule à AUCUN niveau : installer ce qui ne vient pas du registre officiel ou d'un éditeur vérifié, ni un module révoqué ;
désactiver un module vital (le noyau le refuse) ; toucher à un module VERROUILLÉ par l'utilisateur. Un refus de cette règle n'est pas un échec :
il se dit, sans rétrograder sa capacité.

La fenêtre de maintenance (nuit, dimanche, hors heures de bureau, à tout moment) règle QUAND elle applique une mise à jour ou un ajout ;
une urgence (module révoqué, module qui échoue) ne l'attend pas.
"""
import time

NIVEAUX = ("observer", "entretien", "reine")
HUMAINS = ("humain", "compte")
SOURCES_SURES = ("officiel", "verifie")                     # les niveaux de confiance qu'elle installe seule
GESTES_REVERSIBLES = ("activer", "desactiver", "retour_arriere", "abandonner", "telecharger")
ACTEURS_REINE = ("cassandra", "itare", "agent", "noyau")
FENETRES = {"nuit": "la nuit, de 02:00 à 05:00", "dimanche": "le dimanche matin, de 06:00 à 12:00", "hors_bureau": "hors des heures de bureau", "tout": "à tout moment"}


def niveau_de(valeur) -> str:
    v = str(valeur or "reine")
    return v if v in NIVEAUX else "reine"


def fenetre_de(valeur) -> str:
    v = str(valeur or "nuit")
    return v if v in FENETRES else "nuit"


def rang(niveau: str) -> int:
    return NIVEAUX.index(niveau_de(niveau))


def dans_fenetre(fenetre: str, maintenant=None) -> bool:
    """Est-ce l'heure (celle du serveur) où Cassandra applique une mise à jour ou un ajout ?"""
    t = time.localtime(maintenant if maintenant is not None else time.time())
    h, jour = t.tm_hour + t.tm_min / 60.0, t.tm_wday                  # jour : 0 lundi … 6 dimanche
    f = fenetre_de(fenetre)
    if f == "nuit":
        return 2 <= h < 5
    if f == "dimanche":
        return jour == 6 and 6 <= h < 12
    if f == "hors_bureau":
        return not (jour < 5 and 8 <= h < 19)
    return True


def verdict(niveau: str, acteur: str, geste: str, *, source: str = "", elargit: bool = False, revoque: bool = False, nouveau: bool = False, verrouille: bool = False) -> tuple:
    """(permis, raison) : un acteur autre qu'utilisateur peut-il faire ce geste, à ce niveau d'autonomie ? Un utilisateur passe toujours (voie parallèle)."""
    if acteur in HUMAINS:
        return True, ""
    if verrouille:
        return False, "ce module est verrouillé : on m'a demandé de ne pas y toucher"
    n = rang(niveau)
    if n == 0:
        return False, "mon autonomie est réglée sur « observer » : je raconte ce que je ferais, je n'agis pas"
    if geste in GESTES_REVERSIBLES:
        return True, ""
    if geste in ("installer", "mettre_a_jour", "ajouter"):
        if revoque:
            return False, "ce module est révoqué par le registre : je ne l'installe pas"
        if source not in SOURCES_SURES:
            return False, "je n'installe seule que le registre officiel et les éditeurs vérifiés"
        if nouveau and n < 2:
            return False, "ajouter un nouveau module demande l'autonomie « reine »"
        if elargit and not (n >= 2 and source == "officiel"):
            return False, "cette version demande plus de permissions : je ne la prends seule que depuis le registre officiel, en autonomie « reine »"
        return True, ""
    if geste == "desinstaller":
        if revoque:
            return True, ""
        return (n >= 2), ("" if n >= 2 else "retirer un module qui n'est pas révoqué demande l'autonomie « reine »")
    return False, "geste inconnu : %s" % geste


def inverse(geste: str, resultat: dict) -> dict:
    """Le geste qui défait un acte déjà fait (None : rien d'automatique)."""
    r = resultat or {}
    mid = r.get("id") or r.get("module", "")
    if geste in ("activer", "active"):
        return {"capacite": "modules.desactiver", "args": {"module": mid}}
    if geste in ("desactiver", "desactive"):
        return {"capacite": "modules.activer", "args": {"module": mid, "avec_dependances": False}}
    if geste in ("installe", "installer", "retour", "retour_arriere"):
        return {"capacite": "modules.retour_arriere", "args": {"module": mid}} if (r.get("ancienne") or geste in ("retour", "retour_arriere")) \
            else {"capacite": "modules.desinstaller", "args": {"module": mid}}
    if geste in ("desinstalle", "desinstaller"):
        return {"capacite": "modules.retour_arriere", "args": {"module": mid}}
    return None


def _ecartee(journal: list, mid: str, version: str) -> bool:
    """Une version que Cassandra a déjà dû retirer (retour arrière) : elle ne la reprend pas seule."""
    return any(x.get("id") == mid and x.get("acte") == "retour" and x.get("par") == "cassandra" and x.get("ancienne") == version for x in journal)


def entretien(g, cy, politique: str, niveau: str, agir: bool = True, acteur: str = "cassandra", maintenant=None, fenetre: str = "tout", forcer: bool = False) -> dict:
    """Une passe d'entretien : ce que Cassandra constate et, si son niveau le permet, que `agir` est vrai et que c'est l'heure, ce qu'elle fait.
    {niveau, fenetre_ouverte, actions: [{geste, module, version, detail, pourquoi, inverse}], constats: [texte], erreurs: [texte]}"""
    niveau = niveau_de(niveau)
    maintenant = maintenant if maintenant is not None else time.time()
    verrous = cy.verrous()
    ouverte = forcer or dans_fenetre(fenetre, maintenant)
    sortie = {"niveau": niveau, "fenetre_ouverte": ouverte, "actions": [], "constats": [], "erreurs": []}
    catalogue = {m["id"]: m for m in g.catalogue()}

    def noter(geste, mid, version, detail, pourquoi, inv):
        sortie["actions"].append({"geste": geste, "module": mid, "version": version, "detail": detail, "pourquoi": pourquoi, "inverse": inv})

    def peut(geste, mid=None, urgent=False, **kw):
        """(on_le_fait, raison) : la règle d'abord ; puis, hors urgence, l'heure ; puis `agir` (une simulation ne fait rien)."""
        ok, raison = verdict(niveau, acteur, geste, verrouille=bool(mid and mid in verrous), **kw)
        if not ok:
            return False, raison
        if not urgent and not ouverte:
            return False, "fenetre"
        return agir, ""

    # 1. le registre officiel : l'état de ce qui est installé (révocations, mises à jour)
    try:
        reg = cy.registre_officiel()
    except Exception as ex:                                              # un registre muet ne fait pas tomber l'entretien : on le dit et on passe à la santé
        reg = None
        sortie["constats"].append("le registre officiel ne répond pas (%s) : je regarde la santé des modules seulement" % str(ex)[:120])

    if reg:
        for x in reg.get("installes_revoques", []):
            mid = x["id"]
            ok, raison = peut("desinstaller", mid, urgent=True, revoque=True)
            if not ok:
                sortie["constats"].append("%s %s est révoqué (%s)%s" % (x["nom"], x["version"], x["raison"], " : %s" % raison if raison else (" : je le retirerais" if rang(niveau) and not agir else "")))
                continue
            pourquoi = "Le registre officiel l'a déclaré révoqué : %s. Retiré dès le niveau Entretien ; il reste 30 jours en corbeille." % x["raison"]
            try:
                if (catalogue.get(mid) or {}).get("etat") == "actif":
                    r = g.desactiver(mid, acteur=acteur, cascade=True, appliquer=False)
                    if not r.get("ok"):
                        sortie["erreurs"].append("%s est révoqué mais ne se désactive pas : %s" % (mid, r.get("raison")))
                        continue
                    cy.noter_acte("desactive", mid, acteur, pourquoi=pourquoi)
                cy.desinstaller(mid, par=acteur)
                cy.annoter(mid, "desinstalle", pourquoi)
                noter("desinstalle", mid, x["version"], "révoqué par le registre : %s" % x["raison"], pourquoi, inverse("desinstalle", {"id": mid}))
            except Exception as ex:
                sortie["erreurs"].append("retirer %s : %s" % (mid, ex))

        journal = cy.journal()
        for m in reg.get("modules", []):
            if m.get("etat") != "mise_a_jour" or m.get("revoque"):
                continue
            mid = m["id"]
            if mid in verrous:
                sortie["constats"].append("%s %s : le module est verrouillé, je n'y touche pas" % (m["nom"], m["version"]))
                continue
            if _ecartee(journal, mid, m["version"]):
                sortie["constats"].append("%s %s : je l'ai déjà remise en arrière, je n'y retouche pas" % (m["nom"], m["version"]))
                continue
            try:
                exam = cy.telecharger_officiel(mid, politique)
            except Exception as ex:
                sortie["erreurs"].append("télécharger %s : %s" % (mid, ex))
                continue
            elargit = bool(exam.get("permissions_elargies"))
            ok, raison = peut("mettre_a_jour", mid, source=exam.get("niveau", ""), elargit=elargit)
            if not ok:
                cy.abandonner(exam["jeton"])
                if raison == "fenetre":
                    sortie["constats"].append("%s %s : je la prendrai %s" % (m["nom"], m["version"], FENETRES[fenetre_de(fenetre)]))
                elif raison:
                    sortie["constats"].append("%s %s : %s" % (m["nom"], m["version"], raison))
                else:
                    sortie["constats"].append("%s %s est disponible : je la prendrais%s" % (m["nom"], m["version"], " (elle demande en plus : %s)" % ", ".join(exam["permissions_elargies"]) if elargit else ""))
                continue
            if not exam.get("autorise"):
                cy.abandonner(exam["jeton"])
                sortie["constats"].append("%s %s : l'examen la refuse (%s)" % (m["nom"], m["version"], "; ".join(exam.get("raisons", []))[:160]))
                continue
            try:
                r = cy.installer(exam["jeton"], exam["empreinte_permissions"], politique, par=acteur)
                detail = "mise à jour %s → %s" % (r.get("ancienne") or "?", r["version"]) + (" (permissions en plus : %s)" % ", ".join(exam["permissions_elargies"]) if elargit else "")
                pourquoi = ("Mise à jour avec des permissions en plus, depuis le registre officiel (niveau Reine)." if elargit else
                            "Mise à jour sans permission en plus, source %s, appliquée %s ; surveillée 15 minutes." % ("officielle" if exam.get("niveau") == "officiel" else "éditeur vérifié", FENETRES[fenetre_de(fenetre)]))
                cy.annoter(mid, "installe", pourquoi)
                noter("installe", mid, r["version"], detail, pourquoi, inverse("installe", r))
            except Exception as ex:
                sortie["erreurs"].append("installer %s : %s" % (mid, ex))

    # 2. la santé : une mise à jour récente qui tourne mal est remise en arrière ; un module qui échoue est mis en pause (urgent : l'heure n'y change rien)
    recent = {x["id"]: x for x in cy.journal() if x.get("acte") == "installe" and x.get("par") == acteur and maintenant - x.get("ts", 0) < 86400}
    for mid, m in catalogue.items():
        if m.get("etat") != "actif" or not m.get("extension"):
            continue
        try:
            s = g.sante(mid)
        except Exception:
            continue
        if s.get("verdict") != "en_echec":
            continue
        if mid in recent and recent[mid].get("ancienne"):
            ok, raison = peut("retour_arriere", mid, urgent=True)
            if ok:
                try:
                    pourquoi = "La mise à jour %s tournait mal (la santé du module est en échec) : version précédente remise, et je ne la reprendrai pas." % recent[mid]["version"]
                    cy.retour_arriere(mid, par=acteur)
                    cy.annoter(mid, "retour", pourquoi)
                    noter("retour", mid, recent[mid]["ancienne"], "la mise à jour %s tournait mal : version précédente remise" % recent[mid]["version"], pourquoi, inverse("retour", {"id": mid}))
                except Exception as ex:
                    sortie["erreurs"].append("remettre %s : %s" % (mid, ex))
            else:
                sortie["constats"].append("%s tourne mal depuis sa mise à jour : %s" % (m["nom"], raison or "je remettrais la version précédente"))
            continue
        ok, raison = peut("desactiver", mid, urgent=True)
        if ok:
            r = g.desactiver(mid, acteur=acteur, cascade=False, appliquer=False)
            if r.get("ok"):
                pourquoi = "Il échouait (%s) : mis en pause, ses données restent." % (", ".join(s.get("en_echec", []))[:100] or "santé en échec")
                cy.noter_acte("desactive", mid, acteur, pourquoi=pourquoi)
                noter("desactive", mid, m.get("version", ""), "il échouait (%s) : mis en pause" % ", ".join(s.get("en_echec", []))[:120], pourquoi, inverse("desactiver", {"module": mid}))
            else:
                sortie["erreurs"].append("pause de %s : %s" % (mid, r.get("raison")))
        else:
            sortie["constats"].append("%s échoue (%s) : %s" % (m["nom"], ", ".join(s.get("en_echec", []))[:80], raison or "je le mettrais en pause"))
    return sortie


def recit(cy, limite: int = 40) -> list:
    """Ce qui est arrivé aux modules, le plus récent d'abord : chaque ligne dit QUI (Cassandra, Itare ou un utilisateur), QUOI, POURQUOI, et le geste qui le défait."""
    lignes = []
    for rang_j, x in enumerate(cy.journal()[-300:]):
        acte = x.get("acte", "")
        if acte not in ("installe", "retour", "desinstalle", "active", "desactive"):
            continue
        detail = x.get("detail", "")
        if acte == "installe" and x.get("ancienne"):
            detail = "mise à jour %s → %s" % (x["ancienne"], x.get("version", ""))
        elif acte == "retour" and x.get("ancienne"):
            detail = "remis en %s (à la place de %s)" % (x.get("version", ""), x["ancienne"])
        elif acte in ("active", "desactive") and x.get("avec"):
            detail = "avec : " + ", ".join(x["avec"])
        lignes.append({"ts": x.get("ts", 0), "_n": rang_j, "par": x.get("par") or "utilisateur", "geste": acte, "module": x.get("id", ""), "version": x.get("version", ""),
                       "detail": detail, "pourquoi": x.get("pourquoi", ""), "defaire": inverse(acte, x)})
    lignes.sort(key=lambda l: (l["ts"], l["_n"]), reverse=True)                  # à égalité d'horloge, l'ordre du journal décide
    for l in lignes:
        l.pop("_n")
    return lignes[:int(limite)]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : niveau_de, rang, verdict, inverse, _ecartee, entretien, recit
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
