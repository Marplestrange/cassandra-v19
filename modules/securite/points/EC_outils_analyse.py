# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : Lynis, Trivy, ClamAV, CrowdSec : optionnels, jamais requis. L'état vient de leur programme (à root) ; sans lui, seulement ce qui est présent sur la machine (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #4970c7
# HÔTE CN    : CN_module.py · outils_analyse @1.0
# RÔLE       : Lynis, Trivy, ClamAV, CrowdSec : optionnels, jamais requis. L'état vient de leur programme (à root) ; sans lui, seulement ce qui est présent sur la machine.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=outils_analyse contrat=@1.0 version=EC0 empreinte=4970c7 ▼▼▼

OUTILS = {"lynis": ("Lynis", "Audit de durcissement du système, chaque semaine : un score et des conseils."),
          "trivy": ("Trivy", "Failles connues dans les images Docker, chaque semaine."),
          "clamav": ("ClamAV", "Antivirus des fichiers venus de l'extérieur (sites, documents, dossiers personnels), chaque semaine."),
          "crowdsec": ("CrowdSec", "Bloque les attaquants repérés ici et ceux que sa communauté signale ; réseaux de confiance jamais bannis.")}

def _niveau_outil(k, o):
    """(niveau, texte) de l'outil `k`, pour l'écran et le verdict. Un résultat illisible est « premier passage à venir », jamais « ok »."""
    if not o.get("installe"):
        return "", "non installé" + (" · " + o["pourquoi"] if not o.get("convient", True) and o.get("pourquoi") else "")
    r = o.get("resultat") or {}
    if not r:
        return "pas_encore", "installé · premier passage à venir"
    pl = lambda n, mot: mot + ("s" if n > 1 else "")                    # noqa: E731
    if k == "lynis":
        av = len(r.get("avertissements") or [])
        sg = r.get("suggestions_n", 0)
        return ("regarder" if av else "ok"), "score %s/100 · %d %s · %d %s" % (r.get("score") if r.get("score") is not None else "?", av, pl(av, "avertissement"), sg, pl(sg, "conseil"))
    if k == "trivy":
        imgs = r.get("images") or []
        crit = sum(i.get("critiques", 0) for i in imgs)
        corr = sum(i.get("corrigeables", 0) for i in imgs)
        return ("regarder" if crit else "ok"), "%d %s · %d %s · %d déjà %s par leur auteur, en attente d'une nouvelle image" % (
            len(imgs), pl(len(imgs), "image"), crit, "failles critiques" if crit > 1 else "faille critique", corr, "corrigées" if corr > 1 else "corrigée")
    if k == "clamav":
        n = len(r.get("infectes") or [])
        if n:
            return "panne", "%d FICHIER%s INFECTÉ%s" % (n, "S" if n > 1 else "", "S" if n > 1 else "")
        fait = ("%d fichiers analysés" % r["analyses"]) if r.get("analyses") is not None else ("balayage complet en %d min" % r["duree_min"] if r.get("duree_min") is not None else "balayage complet")
        return ("regarder" if r.get("erreur") else "ok"), "%s · aucune menace · signatures du %s" % (fait, r.get("signatures") or "?")
    if k == "crowdsec":
        if not (r.get("moteur") and r.get("videur")):
            return "panne", "moteur %s · videur %s" % ("actif" if r.get("moteur") else "ARRÊTÉ", "actif" if r.get("videur") else "ARRÊTÉ")
        loc, a24 = r.get("decisions_locales", 0), r.get("alertes_24h", 0)
        return "ok", "%d %s ici · %d de la liste communautaire · %d %s en 24 h" % (loc, "adresses bannies" if loc > 1 else "adresse bannie", r.get("liste_communautaire", 0), a24, pl(a24, "alerte"))
    return "", ""

def outils(m):
    """Lynis, Trivy, ClamAV, CrowdSec : optionnels, jamais requis. L'état vient de leur programme (à root) ; sans lui, seulement ce qui est présent sur la machine."""
    etat_complet = m.get("outils_etat") or {}
    pres = m.get("outils") or {}
    sortie = {}
    for k, (nom, role) in OUTILS.items():
        e = dict(etat_complet.get(k) or {})
        e.setdefault("installe", bool(pres.get(k)))
        e.setdefault("convient", True)
        e.setdefault("pourquoi", "")
        e.setdefault("resultat", None)
        e.update({"nom": nom, "role": role, "present": True})
        e["niveau"], e["dit"] = _niveau_outil(k, e)
        sortie[k] = e
    return sortie

def point_outils_analyse(entree):
    """Le point d'évolution `outils_analyse` (contrat 1.0)."""
    return {"valeur": outils(entree["m"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_outils_analyse(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_outils_analyse.json ; corpus doré dans contrats/CN_outils_analyse.corpus.json (sorties de l'ancien code, données synthétiques).
