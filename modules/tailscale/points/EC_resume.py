# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Tailscale : Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #48d415
# HÔTE CN    : CN_module.py · resume @1.0
# RÔLE       : Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=resume contrat=@1.0 version=EC0 empreinte=48d415 ▼▼▼

ETATS = {"Running": "connecte", "NeedsLogin": "a_identifier", "NeedsMachineAuth": "a_approuver", "Stopped": "deconnecte", "Starting": "demarrage", "NoState": "demarrage"}

def resume(d):
    """Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau."""
    moi = d.get("Self") or {}
    etat = ETATS.get(str(d.get("BackendState") or ""), "demarrage")
    reseau = d.get("CurrentTailnet") or {}
    pairs = []
    for p in (d.get("Peer") or {}).values():
        ls = str(p.get("LastSeen") or "")
        court = str(p.get("DNSName") or "").split(".")[0]
        hote = p.get("HostName") or ""
        # Un téléphone ou un conteneur annonce « localhost » : trois pairs du même nom ne se distinguent plus. Le nom DNS court (localhost-1, localhost-2…) est unique dans le réseau.
        nom = court if (court and (not hote or hote.lower() == "localhost")) else (hote or court)
        pairs.append({"nom": nom, "ip": (p.get("TailscaleIPs") or [""])[0], "os": p.get("OS", ""),
                      "en_ligne": bool(p.get("Online")), "vu": "" if ls.startswith("0001") else ls[:16].replace("T", " "), "sortie": bool(p.get("ExitNode")),
                      "offre_sortie": bool(p.get("ExitNodeOption"))})
    pairs.sort(key=lambda x: (not x["en_ligne"], x["nom"].lower()))
    ips = [x for x in (d.get("TailscaleIPs") or []) if x]
    return {"etat": etat, "brut": d.get("BackendState") or "", "lien": d.get("AuthURL") or "", "nom": moi.get("HostName") or "", "dns": str(moi.get("DNSName") or "").rstrip("."),
            "ip4": next((x for x in ips if ":" not in x), ""), "ip6": next((x for x in ips if ":" in x), ""), "reseau": reseau.get("Name") or "", "suffixe": reseau.get("MagicDNSSuffix") or "",
            "version": d.get("Version") or "", "sante": [str(x)[:200] for x in (d.get("Health") or [])][:5], "pairs": pairs,
            "en_ligne": sum(1 for x in pairs if x["en_ligne"]), "ssh": bool(moi.get("sshHostKeys")) or "ssh" in str(moi.get("Capabilities") or "").lower()}

def point_resume(entree):
    """Le point d'évolution `resume` (contrat 1.0)."""
    return {"valeur": resume(entree["d"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_resume(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de tailscale (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_resume.json ; corpus doré dans contrats/CN_resume.corpus.json (sorties de l'ancien code, données synthétiques).
