# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Ged : genre d'un fichier (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : ged
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #13f924
# HÔTE CN    : CN_module.py · media_kind @1.0
# RÔLE       : range un fichier de la GED dans un genre, d'après son type MIME ou à défaut son extension.
# MÉTHODE    : fonction pure : le type MIME image, vidéo ou audio l'emporte ; sinon l'extension est cherchée dans des listes fermées ; le reste est « autre ».
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=media_kind contrat=@1.0 version=EC0 empreinte=13f924 ▼▼▼

def _media_kind(nom: str, mime: str = "") -> str:
    n = (nom or "").lower()
    if mime and mime.startswith(("image/", "video/", "audio/")):
        return mime.split("/")[0]
    ext = n.rsplit(".", 1)[-1] if "." in n else ""
    if ext in ("png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "heic", "heif", "tif", "tiff"):
        return "image"
    if ext in ("mp4", "m4v", "webm", "mov", "mkv", "avi"):
        return "video"
    if ext in ("mp3", "ogg", "oga", "wav", "flac", "aac", "m4a", "opus"):
        return "audio"
    if ext == "pdf":
        return "pdf"
    if ext in ("txt", "md", "csv", "tsv", "json", "yaml", "yml", "log"):
        return "texte"
    return "autre"

def point_media_kind(entree):
    """Le point d'évolution `media_kind` (contrat 1.0)."""
    return {"valeur": _media_kind(entree["nom"], entree["mime"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_media_kind(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de ged (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_media_kind.json ; corpus doré dans contrats/CN_media_kind.corpus.json (sorties de l'ancien code, données synthétiques).
