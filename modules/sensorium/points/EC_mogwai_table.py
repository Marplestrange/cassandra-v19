# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : la table de mogwai (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #afd6eb
# HÔTE CN    : CN_module.py · mogwai_table @1.0
# RÔLE       : lit la sortie tabulaire de mogwai, dont les colonnes sont séparées par des tabulations ou par des espaces multiples.
# MÉTHODE    : fonction pure : s'il y a des tabulations dans l'en-tête, on ne coupe que sur elles (sinon une cellule vide fait glisser les colonnes) ; sinon sur deux espaces ou plus ; les lignes courtes sont complétées.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=mogwai_table contrat=@1.0 version=EC0 empreinte=afd6eb ▼▼▼
import re

def _mogwai_parse_table(output: str) -> list[dict]:
    """Parse la sortie tabulaire de mogwai (colonnes séparées par des espaces multiples)."""
    if not output:
        return []
    lines = output.strip().splitlines()
    if len(lines) < 2:
        return []
    # Ligne 0 = en-têtes, lignes 1+ = données
    # mogwai sépare par des TABULATIONS et complète chaque cellule d'espaces ; une cellule vide n'est
    # que des espaces. Couper sur « tabulation OU deux espaces » faisait glisser les colonnes (20-09 :
    # l'OWNER d'un site devenait son alias). Quand il y a des tabulations, on ne coupe que sur elles.
    sep = r'\t' if "\t" in lines[0] else r'  +'
    headers = re.split(sep, lines[0].strip())
    headers = [h.strip().lower().replace(" ", "_") for h in headers if h.strip()]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = re.split(sep, line.strip())
        vals = [v.strip() for v in vals]
        # Aligner sur le nombre de colonnes
        while len(vals) < len(headers):
            vals.append("")
        row = {headers[i]: vals[i] for i in range(len(headers))}
        rows.append(row)
    return rows

def point_mogwai_table(entree):
    """Le point d'évolution `mogwai_table` (contrat 1.0)."""
    return {"valeur": _mogwai_parse_table(entree["output"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_mogwai_table(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_mogwai_table.json ; corpus doré dans contrats/CN_mogwai_table.corpus.json (sorties de l'ancien code, données synthétiques).
