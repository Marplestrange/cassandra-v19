# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Tailscale : Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #64785b
# HÔTE CN    : CN_module.py · erreur @1.0
# RÔLE       : Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=erreur contrat=@1.0 version=EC0 empreinte=64785b ▼▼▼
import re

def _erreur(sortie, cle=""):
    """Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès."""
    t = str(sortie or "").strip()
    if cle:
        t = t.replace(cle, "tskey-…")
    t = re.sub(r"tskey-[A-Za-z0-9_-]+", "tskey-…", t)
    if re.search(r"access denied|profiles access denied|use 'sudo tailscale'|permission denied", t, re.I):
        return "Cassandra n'a pas le droit de piloter Tailscale : sur la machine, `sudo tailscale set --operator=cassandra` (l'installateur du module le fait)."
    if re.search(r"failed to connect to local tailscaled|tailscaled.*not running|connect: no such file", t, re.I):
        return "tailscaled ne tourne pas : `sudo systemctl enable --now tailscaled`."
    lignes = [x for x in t.splitlines() if x.strip()]
    return (lignes[-1] if lignes else "le client n'a rien répondu")[:300]

def point_erreur(entree):
    """Le point d'évolution `erreur` (contrat 1.0)."""
    return {"valeur": _erreur(entree["sortie"], entree["cle"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_erreur(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de tailscale (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_erreur.json ; corpus doré dans contrats/CN_erreur.corpus.json (sorties de l'ancien code, données synthétiques).
