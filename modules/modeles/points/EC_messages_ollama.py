# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Modeles : les messages au format Ollama (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modeles
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #1235f4
# HÔTE CN    : CN_module.py · messages_ollama @1.0
# RÔLE       : traduit une conversation du format OpenAI vers celui d'Ollama, pour que les deux sachent parler à Cassandra.
# MÉTHODE    : fonction pure : les arguments d'appel deviennent des objets ; un résultat d'outil retrouve le nom de l'outil par l'identifiant de l'appel ; rien d'autre n'est touché.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=messages_ollama contrat=@1.0 version=EC0 empreinte=1235f4 ▼▼▼
import json

def messages_ollama(msgs):
    """Le format OpenAI vers le natif d'Ollama : arguments en objet, résultat d'outil avec le nom de l'outil."""
    noms, out = {}, []
    for m in msgs:
        m = dict(m)
        m["content"] = m.get("content") or ""
        if m.get("tool_calls"):
            tcs = []
            for tc in m["tool_calls"]:
                f = dict(tc.get("function") or {})
                noms[str(tc.get("id"))] = f.get("name", "")
                if isinstance(f.get("arguments"), str):
                    try:
                        f["arguments"] = json.loads(f["arguments"] or "{}")
                    except ValueError:
                        f["arguments"] = {}
                tcs.append({"function": f})
            m["tool_calls"] = tcs
        if m.get("role") == "tool":
            m["tool_name"] = noms.get(str(m.pop("tool_call_id", "")), m.get("name", ""))
        out.append(m)
    return out

def point_messages_ollama(entree):
    """Le point d'évolution `messages_ollama` (contrat 1.0) : les messages au format OpenAI en entrée, au format natif d'Ollama en sortie."""
    return {"valeur": messages_ollama(entree["msgs"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_messages_ollama(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de modeles (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_messages_ollama.json ; corpus doré dans contrats/CN_messages_ollama.corpus.json (sorties de l'ancien code, données synthétiques).
