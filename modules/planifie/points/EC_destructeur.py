# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : Le motif destructeur reconnu dans la commande, ou « ». On ne demande confirmation que sur ce qui détruit vraiment : un avertissement qui s'affiche à chaque enregistrement n'avertit plus de rien (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #f009f0
# HÔTE CN    : CN_module.py · destructeur @1.0
# RÔLE       : Le motif destructeur reconnu dans la commande, ou « ». On ne demande confirmation que sur ce qui détruit vraiment : un avertissement qui s'affiche à chaque enregistrement n'avertit plus de rien.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=destructeur contrat=@1.0 version=EC0 empreinte=f009f0 ▼▼▼
import re

DESTRUCTEURS = [r"\brm\s+-[rf]", r"\bdd\s+if=", r"\bmkfs", r"\breboot\b", r"\bshutdown\b", r"\bsed\s+-i\b", r"\b(perl|python3?|ruby)\s+.*-i\b", r"\bchmod\b", r"\bchown\b",
                r"\btee\b", r"\bkill(all)?\b", r"\bpkill\b", r"\buserdel\b", r"\bmkswap\b", r"\biptables\b", r"\bsystemctl\s+(stop|disable|mask|restart)\b", r"\btruncate\b"]

DESTRUCTEURS_EN_PLUS = [
    (r">\s*/(etc|boot|usr|bin|sbin|lib|var/lib)/", "écriture dans une arborescence système"),
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b", "exécution directe d'un contenu téléchargé"),
]

def destructeur(commande):
    """Le motif destructeur reconnu dans la commande, ou « ». On ne demande confirmation que sur ce qui détruit vraiment : un avertissement qui s'affiche à chaque enregistrement n'avertit plus de rien."""
    cmd = (commande or "").strip()
    for pat in DESTRUCTEURS:
        if re.search(pat, cmd):
            return "motif destructeur : %s" % pat.replace(r"\b", "").replace("\\s+", " ")
    for pat, libelle in DESTRUCTEURS_EN_PLUS:
        if re.search(pat, cmd):
            return libelle
    return ""

def point_destructeur(entree):
    """Le point d'évolution `destructeur` (contrat 1.0)."""
    return {"valeur": destructeur(entree["commande"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_destructeur(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_destructeur.json ; corpus doré dans contrats/CN_destructeur.corpus.json (sorties de l'ancien code, données synthétiques).
