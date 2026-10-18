# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : Une conversation que l'API accepte : chaque message assistant porteur de `tool_calls` est suivi d'une réponse `tool` pour CHACUN de ses identifiants, et aucune réponse `tool` n'est orpheline (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #baad70
# HÔTE CN    : CN_module.py · coherents @1.0
# RÔLE       : Une conversation que l'API accepte : chaque message assistant porteur de `tool_calls` est suivi d'une réponse `tool` pour CHACUN de ses identifiants, et aucune réponse `tool` n'est orpheline.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=coherents contrat=@1.0 version=EC0 empreinte=baad70 ▼▼▼

def coherents(msgs):
    """Une conversation que l'API accepte : chaque message assistant porteur de `tool_calls` est suivi d'une réponse `tool` pour CHACUN de ses identifiants, et aucune réponse `tool` n'est orpheline.
    Sinon DeepSeek rejette tout le tour (« insufficient tool messages following tool_calls ») et le travail du tour est perdu. Ce qui manque est complété par une réponse explicite plutôt que deviné ;
    ce qui traîne est retiré."""
    out, i = [], 0
    while i < len(msgs):
        m = msgs[i]
        if m.get("role") == "tool":
            i += 1                                           # orpheline : un résultat sans appel devant lui
            continue
        out.append(m)
        i += 1
        if m.get("role") == "assistant" and m.get("tool_calls"):
            attendus = [tc.get("id") for tc in m["tool_calls"] if isinstance(tc, dict) and tc.get("id")]
            vus = set()
            while i < len(msgs) and msgs[i].get("role") == "tool":
                if msgs[i].get("tool_call_id") in attendus and msgs[i].get("tool_call_id") not in vus:
                    vus.add(msgs[i]["tool_call_id"])
                    out.append(msgs[i])
                i += 1
            for a in attendus:
                if a not in vus:
                    out.append({"role": "tool", "tool_call_id": a, "content": "(résultat perdu : l'appel n'a pas abouti)"})
    return out

def point_coherents(entree):
    """Le point d'évolution `coherents` (contrat 1.0)."""
    return {"valeur": coherents(entree["msgs"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_coherents(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_coherents.json ; corpus doré dans contrats/CN_coherents.corpus.json (sorties de l'ancien code, données synthétiques).
