# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'autonomie de Cassandra sur les modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modules
# ZONE       : CN
# VERSION CN : 0.1.0  #490f68
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'autonomie de Cassandra sur les modules : ce qu'elle fait seule, ce qu'elle se refuse, et le récit de ce qu'elle a fait.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=490f68 ▼▼▼
"""L'autonomie de Cassandra sur les modules : ce qu'elle fait seule, ce qu'elle se refuse, et le récit de ce qu'elle a fait.

Le principe (IA souveraine) : Cassandra n'attend JAMAIS un humain pour agir sur les modules ; l'humain peut agir aussi, en parallèle.
La sûreté ne vient donc pas d'une permission mais de la réversibilité : chaque geste est prouvé, a son retour arrière, et laisse un
récit où chaque acte porte le geste qui le défait. Le réglage « autonomie » ne dit pas « à qui demander » : il dit jusqu'où Cassandra va.

  observer   : elle regarde et raconte ce qu'elle ferait ; elle n'agit pas.
  entretien  : elle entretient (module révoqué retiré, mise à jour sans permission en plus, module en échec mis en pause, remise de version).
  reine      : elle gère tout (en plus : elle ajoute et retire des modules, et prend des mises à jour qui demandent plus de permissions).

Ce qu'elle ne fait seule à AUCUN niveau : installer ce qui ne vient pas du registre officiel ou d'un éditeur vérifié, ni un module révoqué ;
désactiver un module vital (le noyau le refuse). Un refus de cette règle n'est pas un échec : il se dit, sans rétrograder sa capacité.
"""
import time

NIVEAUX = ("observer", "entretien", "reine")
HUMAINS = ("humain", "compte")
SOURCES_SURES = ("officiel", "verifie")                     # les niveaux de confiance qu'elle installe seule
GESTES_REVERSIBLES = ("activer", "desactiver", "retour_arriere", "abandonner", "telecharger")
ACTEURS_REINE = ("cassandra", "itare", "agent", "noyau")


def niveau_de(valeur) -> str:
    v = str(valeur or "reine")
    return v if v in NIVEAUX else "reine"


def rang(niveau: str) -> int:
    return NIVEAUX.index(niveau_de(niveau))


def verdict(niveau: str, acteur: str, geste: str, *, source: str = "", elargit: bool = False, revoque: bool = False, nouveau: bool = False) -> tuple:
    """(permis, raison) : un acteur autre qu'humain peut-il faire ce geste, à ce niveau d'autonomie ? Un humain passe toujours (voie parallèle)."""
    if acteur in HUMAINS:
        return True, ""
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
    if geste == "activer":
        return {"capacite": "modules.desactiver", "args": {"module": r.get("module", "")}}
    if geste == "desactiver":
        return {"capacite": "modules.activer", "args": {"module": r.get("module", ""), "avec_dependances": False}}
    if geste in ("installe", "installer", "retour", "retour_arriere"):
        return {"capacite": "modules.retour_arriere", "args": {"module": r.get("id") or r.get("module", "")}} if (r.get("ancienne") or geste in ("retour", "retour_arriere")) \
            else {"capacite": "modules.desinstaller", "args": {"module": r.get("id") or r.get("module", "")}}
    if geste in ("desinstalle", "desinstaller"):
        return {"capacite": "modules.retour_arriere", "args": {"module": r.get("id") or r.get("module", "")}}
    return None


def _ecartee(journal: list, mid: str, version: str) -> bool:
    """Une version que Cassandra a déjà dû retirer (retour arrière) : elle ne la reprend pas seule."""
    return any(x.get("id") == mid and x.get("acte") == "retour" and x.get("par") == "cassandra" and x.get("ancienne") == version for x in journal)


def entretien(g, cy, politique: str, niveau: str, agir: bool = True, acteur: str = "cassandra", maintenant=None) -> dict:
    """Une passe d'entretien : ce que Cassandra constate et, si son niveau le permet et que `agir` est vrai, ce qu'elle fait.
    {niveau, actions: [{geste, module, version, detail, inverse}], constats: [texte], erreurs: [texte]}"""
    niveau = niveau_de(niveau)
    sortie = {"niveau": niveau, "actions": [], "constats": [], "erreurs": []}
    maintenant = maintenant or time.time()
    catalogue = {m["id"]: m for m in g.catalogue()}

    def noter(geste, mid, version, detail, inv):
        sortie["actions"].append({"geste": geste, "module": mid, "version": version, "detail": detail, "inverse": inv})

    def peut(geste, **kw):
        ok, raison = verdict(niveau, acteur, geste, **kw)
        return ok and agir, raison

    # 1. le registre officiel : l'état de ce qui est installé (révocations, mises à jour)
    try:
        reg = cy.registre_officiel()
    except Exception as ex:                                              # un registre muet ne fait pas tomber l'entretien : on le dit et on passe à la santé
        reg = None
        sortie["constats"].append("le registre officiel ne répond pas (%s) : je regarde la santé des modules seulement" % str(ex)[:120])

    if reg:
        for x in reg.get("installes_revoques", []):
            mid = x["id"]
            ok, raison = peut("desinstaller", revoque=True)
            if not ok:
                sortie["constats"].append("%s %s est révoqué (%s)%s" % (x["nom"], x["version"], x["raison"], "" if agir else " : je le retirerais" if rang(niveau) else " : je ne touche à rien"))
                continue
            try:
                if (catalogue.get(mid) or {}).get("etat") == "actif":
                    r = g.desactiver(mid, acteur=acteur, cascade=True, appliquer=False)
                    if not r.get("ok"):
                        sortie["erreurs"].append("%s est révoqué mais ne se désactive pas : %s" % (mid, r.get("raison")))
                        continue
                cy.desinstaller(mid, par=acteur)
                noter("desinstalle", mid, x["version"], "révoqué par le registre : %s" % x["raison"], inverse("desinstalle", {"id": mid}))
            except Exception as ex:
                sortie["erreurs"].append("retirer %s : %s" % (mid, ex))

        journal = cy.journal()
        for m in reg.get("modules", []):
            if m.get("etat") != "mise_a_jour" or m.get("revoque"):
                continue
            mid = m["id"]
            if _ecartee(journal, mid, m["version"]):
                sortie["constats"].append("%s %s : je l'ai déjà remise en arrière, je n'y retouche pas" % (m["nom"], m["version"]))
                continue
            try:
                exam = cy.telecharger_officiel(mid, politique)
            except Exception as ex:
                sortie["erreurs"].append("télécharger %s : %s" % (mid, ex))
                continue
            elargit = bool(exam.get("permissions_elargies"))
            ok, raison = peut("mettre_a_jour", source=exam.get("niveau", ""), elargit=elargit)
            if not ok:
                cy.abandonner(exam["jeton"])
                if raison:
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
                noter("installe", mid, r["version"], detail, inverse("installe", r))
            except Exception as ex:
                sortie["erreurs"].append("installer %s : %s" % (mid, ex))

    # 2. la santé : une mise à jour récente qui tourne mal est remise en arrière ; un module qui échoue est mis en pause
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
            ok, raison = peut("retour_arriere")
            if ok:
                try:
                    cy.retour_arriere(mid, par=acteur)
                    noter("retour", mid, recent[mid]["ancienne"], "la mise à jour %s tournait mal : version précédente remise" % recent[mid]["version"], inverse("retour", {"id": mid}))
                except Exception as ex:
                    sortie["erreurs"].append("remettre %s : %s" % (mid, ex))
            else:
                sortie["constats"].append("%s tourne mal depuis sa mise à jour : je remettrais la version précédente" % m["nom"])
            continue
        ok, raison = peut("desactiver")
        if ok:
            r = g.desactiver(mid, acteur=acteur, cascade=False, appliquer=False)
            if r.get("ok"):
                noter("desactive", mid, m.get("version", ""), "il échouait (%s) : mis en pause" % ", ".join(s.get("en_echec", []))[:120], inverse("desactiver", {"module": mid}))
            else:
                sortie["erreurs"].append("pause de %s : %s" % (mid, r.get("raison")))
        else:
            sortie["constats"].append("%s échoue (%s) : je le mettrais en pause" % (m["nom"], ", ".join(s.get("en_echec", []))[:80]))
    return sortie


def recit(ctx, cy, limite: int = 40) -> list:
    """Ce qui est arrivé aux modules, le plus récent d'abord : chaque ligne dit QUI (Cassandra, Itare ou un humain), QUOI, et le geste qui le défait."""
    lignes = []
    for x in cy.journal()[-200:]:
        mid = x.get("id", "")
        acte = x.get("acte", "")
        if acte not in ("installe", "retour", "desinstalle"):
            continue
        lignes.append({"ts": x.get("ts", 0), "par": x.get("par") or "humain", "geste": acte, "module": mid, "version": x.get("version", ""),
                       "detail": ("mise à jour %s → %s" % (x["ancienne"], x["version"])) if acte == "installe" and x.get("ancienne") else "",
                       "defaire": inverse(acte, dict(x, ancienne=x.get("ancienne")))})
    try:
        evs = ctx.evenements("capacite.faite", 400)
    except Exception:
        evs = []
    for e in evs:
        cle = e.get("objet_id") or ""
        if e.get("source") != "modules" or cle not in ("modules.activer", "modules.desactiver"):
            continue
        res = (e.get("donnees") or {}).get("resultat") or {}
        geste = cle.split(".", 1)[1]
        mid = res.get("module", "")
        lignes.append({"ts": e.get("ts", 0), "par": e.get("acteur") or "humain", "geste": geste, "module": mid, "version": "",
                       "detail": "avec " + ", ".join(res.get("actives", [])[1:]) if geste == "activer" and len(res.get("actives", [])) > 1 else "",
                       "defaire": inverse(geste, res)})
    lignes.sort(key=lambda l: l["ts"], reverse=True)
    return lignes[:int(limite)]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : niveau_de, rang, verdict, inverse, _ecartee, entretien, recit
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
