# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : la dernière exécution d un cron (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #3a0315
# HÔTE CN    : CN_module.py · cron_derniere @1.0
# RÔLE       : rattache une ligne de crontab à sa dernière exécution, même quand cron a retouché la commande (échappement, redirection).
# MÉTHODE    : fonction pure : égalité stricte d'abord, puis inclusion sur les cent vingt premiers caractères, la plus récente gagne ; vide plutôt qu'un faux rattachement.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=cron_derniere contrat=@1.0 version=EC0 empreinte=3a0315 ▼▼▼

def _cron_run_lookup(runs: dict, user: str, command: str) -> str:
    """Dernière exécution d'une commande de crontab.

    Le journal reproduit la commande telle qu'écrite, mais cron applique parfois
    des retouches (échappement des %, redirections). On tente l'égalité stricte,
    puis l'inclusion, avant d'abandonner — mieux vaut « inconnu » qu'un faux
    rattachement qui masquerait un cron réellement muet."""
    cmd = (command or "").strip()[:300]
    exact = runs.get((user, cmd))
    if exact:
        return exact
    best = ""
    for (u, c), ts in runs.items():
        if u != user:
            continue
        if c.startswith(cmd[:120]) or cmd.startswith(c[:120]):
            if ts > best:
                best = ts
    return best

def point_cron_derniere(entree):
    """Le point d'évolution `cron_derniere` (contrat 1.0) : les exécutions connues [[compte, commande, date]], le compte et la commande en entrée, la date de la dernière exécution en sortie."""
    runs = {(u, c): ts for u, c, ts in entree["runs"]}
    return {"valeur": _cron_run_lookup(runs, entree["user"], entree["command"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_cron_derniere(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_cron_derniere.json ; corpus doré dans contrats/CN_cron_derniere.corpus.json (sorties de l'ancien code, données synthétiques).
