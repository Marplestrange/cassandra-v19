# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Fastpanel : la lecture du panneau (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #1a1ce5
# HÔTE CN    : CN_module.py · lecture @1.0
# RÔLE       : s'adapte à la version de FastPanel : choisit les requêtes selon les colonnes que le schéma porte, puis met en forme ce qui a été lu, sans jamais toucher la base.
# MÉTHODE    : fonctions pures : le plan lit un schéma (tables et colonnes) et rend des requêtes SELECT ; la forme lit des lignes et rend des dictionnaires ; le nexus exécute les requêtes (lecture seule), jamais l'EC.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=lecture contrat=@1.0 version=EC0 empreinte=1a1ce5 ▼▼▼
from datetime import datetime
import re

RE_HOTE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$")

ETATS_ACTIFS = {"active", "running", "started", "on", "up", "1", "true", "enabled"}

def _t(v):
    return "" if v is None else str(v)

def _mo(v):
    try:
        return round(float(v or 0) / 1048576.0, 2)
    except (TypeError, ValueError):
        return 0.0

def _vrai(v):
    return str(v).strip().lower() in ("1", "true", "t", "yes", "active", "enabled")

def nom_hote(d):
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d

def hote_valide(d):
    """Un nom d'hôte, rien d'autre : ni le « _ » de la page par défaut de nginx, ni un joker (deux sites fantômes ont reçu des alertes en V18)."""
    return bool(RE_HOTE.match(str(d or "").strip().rstrip(".").lower()))

def php_normalise(v):
    """« 83 » -> « 8.3 » : FastPanel range la version PHP d'un backend sous la forme compacte."""
    s = str(v or "").strip()
    if not s or not any(c.isdigit() for c in s):
        return ""
    return s[0] + "." + s[1:] if s.isdigit() and len(s) >= 2 else s

def _jours(date_iso, maintenant):
    """Jours entre l'instant reçu et une date ISO (les dix premiers caractères comptent). None si la date n'en est pas une."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}", str(date_iso or "")):
        return None
    fin = datetime.strptime(str(date_iso)[:10], "%Y-%m-%d")
    base = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    return (fin - base).days

def _actif(etat):
    e = str(etat or "").strip().lower()
    return e in ETATS_ACTIFS or e.startswith("activ")

def _liste(d):
    """Une réponse de liste : directe, ou enveloppée dans « data »."""
    if isinstance(d, dict) and isinstance(d.get("data"), list):
        d = d["data"]
    elif isinstance(d, dict):
        d = [d] if d else []
    return [x for x in (d or []) if isinstance(x, dict)]

def _cols(schema, table):
    return set((schema or {}).get(table) or [])

def _premiere(cols, *candidats):
    return next((c for c in candidats if c in cols), "")

def plan_utilisateurs(schema, options):
    cols = _cols(schema, "panel_account")

    def c(nom, defaut="''"):
        return "COALESCE(p.%s,%s)" % (nom, defaut) if nom in cols else defaut
    return {"requetes": [
        "SELECT p.username, %s, %s, %s, %s, %s, %s, %s, (SELECT COUNT(*) FROM site s WHERE s.owner_id = p.id), (SELECT COUNT(*) FROM db d WHERE d.owner_id = p.id) "
        "FROM panel_account p ORDER BY p.username" % (c("home_dir"), c("status"), c("roles"), c("ssh_access", "0"), c("quota_value", "0"), c("restore_email"), c("created_at"))]}

def plan_sites(schema, options):
    cert = _cols(schema, "certificate")
    fin = "c.expired_at" if "expired_at" in cert else ("c.expires" if "expires" in cert else "''")
    principale = ("SELECT s.domain, COALESCE(p.username,''), COALESCE(s.status,''), s.certificate_id, %s FROM site s "
                  "LEFT JOIN panel_account p ON s.owner_id = p.id LEFT JOIN certificate c ON s.certificate_id = c.id ORDER BY s.domain" % fin)
    wb = _cols(schema, "website_backends")
    php = None
    if {"frontend_id", "handler", "handler_version"} <= wb:
        ordre = "ORDER BY COALESCE(b.main,0) DESC, b.id" if "main" in wb else "ORDER BY b.id"
        php = "SELECT s.domain, COALESCE(b.handler,''), COALESCE(b.handler_version,'') FROM website_backends b JOIN site s ON b.frontend_id = s.id " + ordre
    stats = None
    if "site_id" in _cols(schema, "site_stats"):
        stats = "SELECT s.domain, COALESCE(t.error_count,0), COALESCE(t.status_code,0), COALESCE(t.size,0), COALESCE(t.databases_size,0) FROM site_stats t JOIN site s ON t.site_id = s.id"
    return {"requetes": [principale, php, stats]}

def plan_bases(schema, options):
    cols = _cols(schema, "db")
    site = "s.domain" if "site_id" in cols else "''"
    jointure = "LEFT JOIN site s ON d.site_id = s.id" if "site_id" in cols else ""

    def c(nom, defaut):
        return "COALESCE(d.%s,%s)" % (nom, defaut) if nom in cols else defaut
    utilisateurs = ("(SELECT GROUP_CONCAT(du.login, ', ') FROM datbases_users lu JOIN database_user du ON du.id = lu.user_id WHERE lu.database_id = d.id)"
                    if _cols(schema, "datbases_users") and _cols(schema, "database_user") else "''")
    return {"requetes": ["SELECT d.name, %s, %s, COALESCE(p.username,''), COALESCE(%s,''), %s, %s, %s, %s, d.id FROM db d LEFT JOIN panel_account p ON d.owner_id = p.id %s ORDER BY d.name"
                         % (c("engine", "'mysql'"), c("size", "0"), site, c("charset", "''"), c("created_at", "''"), c("dump_at", "''"), utilisateurs, jointure)]}

def plan_ftp(schema, options):
    cols = _cols(schema, "ftp_account")
    site = "COALESCE(s.domain,'')" if "virtualhost_id" in cols else "''"
    jointure = "LEFT JOIN site s ON f.virtualhost_id = s.id" if "virtualhost_id" in cols else ""
    dossier = "COALESCE(f.home_dir,'')" if "home_dir" in cols else "''"
    actif = "f.enabled" if "enabled" in cols else "1"
    cree = "COALESCE(f.created,'')" if "created" in cols else "''"
    return {"requetes": ["SELECT f.name, %s, %s, COALESCE(p.username,''), %s, %s FROM ftp_account f LEFT JOIN panel_account p ON f.owner_id = p.id %s ORDER BY f.name" % (dossier, actif, site, cree, jointure)]}

def plan_mail(schema, options):
    cols = _cols(schema, "mailboxes")
    adr = _premiere(cols, "address", "email", "login")
    if not cols or not adr:
        return {"erreur": "la table des boîtes mail est absente ou d'un schéma inconnu (autre version de FastPanel ?)"}
    q, t, a = _premiere(cols, "quota"), _premiere(cols, "size", "used"), _premiere(cols, "enabled", "active")
    dom = "domain_id" in cols and bool(_cols(schema, "email_domain"))
    return {"requetes": ["SELECT m.%s, %s, %s, %s, %s FROM mailboxes m %s ORDER BY m.%s"
                         % (adr, "COALESCE(m.%s,0)" % q if q else "0", "COALESCE(m.%s,0)" % t if t else "0", "COALESCE(m.%s,1)" % a if a else "1",
                            "COALESCE(e.name,'')" if dom else "''", "LEFT JOIN email_domain e ON m.domain_id = e.id" if dom else "", adr)]}

def plan_dns(schema, options):
    cols = _cols(schema, "record")
    nom, typ, val = _premiere(cols, "name", "host"), _premiere(cols, "type", "rtype"), _premiere(cols, "value", "content", "data")
    if not cols or not (nom and typ and val):
        return {"erreur": "la table des enregistrements DNS est absente ou d'un schéma inconnu (autre version de FastPanel ?)"}
    ttl = _premiere(cols, "ttl")
    zone = "domain_id" in cols and bool(_cols(schema, "domain"))
    return {"requetes": ["SELECT %s, r.%s, r.%s, r.%s, %s FROM record r %s ORDER BY 1, r.%s"
                         % ("COALESCE(d.name,'')" if zone else "''", nom, typ, val, "COALESCE(r.%s,0)" % ttl if ttl else "0", "LEFT JOIN domain d ON r.domain_id = d.id" if zone else "", typ)]}

def forme_utilisateurs(jeux, options):
    sortie = []
    for r in jeux[0]:
        if not r[0]:
            continue
        quota = round(float(r[5] or 0) / 1073741824.0, 2)
        sortie.append({"compte": r[0], "dossier": _t(r[1]), "statut": _t(r[2]) or "active", "roles": _t(r[3]), "ssh": _vrai(r[4]),
                       "quota_go": quota if quota > 0 else None, "courriel": _t(r[6]), "cree": _t(r[7])[:19], "sites": r[8], "bases": r[9]})
    return sortie

def forme_sites(jeux, options):
    maintenant = datetime.strptime(options["maintenant"][:19], "%Y-%m-%d %H:%M:%S")
    seuil = options.get("seuil", 30)
    php = {}
    for r in jeux[1]:
        d = nom_hote(r[0])
        if d and d not in php:
            php[d] = {"gestionnaire": _t(r[1]), "php": php_normalise(r[2])}
    stats = {}
    for r in jeux[2]:
        if r[0]:
            stats[nom_hote(r[0])] = {"erreurs": r[1], "code_http": r[2], "fichiers_mo": _mo(r[3]), "bases_mo": _mo(r[4])}
    sortie = []
    for r in jeux[0]:
        if not hote_valide(r[0]):
            continue
        attache = r[3] is not None and str(r[3]) not in ("", "0")
        j = _jours(r[4], maintenant) if attache else None
        etat = "aucun" if not attache else ("inconnu" if j is None else ("echu" if j <= 0 else ("proche" if j <= seuil else "actif")))
        s = {"domaine": r[0], "proprietaire": r[1], "statut": _t(r[2]), "ssl": {"etat": etat, "jours": j, "echeance": _t(r[4])[:10] if j is not None else ""}}
        s.update(php.get(nom_hote(r[0]), {"gestionnaire": "", "php": ""}))
        s.update(stats.get(nom_hote(r[0]), {}))
        sortie.append(s)
    return sortie

def forme_bases(jeux, options):
    return [{"id": r[9], "nom": r[0], "moteur": r[1] or "mysql", "taille_mo": _mo(r[2]), "proprietaire": r[3], "site": r[4], "jeu": r[5],
             "cree": _t(r[6])[:19], "derniere_copie": _t(r[7])[:19], "utilisateurs": _t(r[8])} for r in jeux[0] if r[0]]

def forme_ftp(jeux, options):
    return [{"compte": r[0], "dossier": r[1], "statut": "active" if _vrai(r[2]) else "suspendu", "proprietaire": r[3], "site": r[4], "cree": _t(r[5])[:19]} for r in jeux[0] if r[0]]

def forme_mail(jeux, options):
    sortie = []
    for r in jeux[0]:
        if r[0]:
            sortie.append({"adresse": r[0], "domaine": r[4] or (str(r[0]).split("@")[-1] if "@" in str(r[0]) else ""), "quota_mo": round(float(r[1] or 0) / 1048576.0, 1),
                           "utilise_mo": round(float(r[2] or 0) / 1048576.0, 1), "statut": "active" if _vrai(r[3]) else "suspendue"})
    return sortie

def forme_dns(jeux, options):
    return [{"zone": r[0], "nom": r[1], "type": r[2], "valeur": r[3], "ttl": r[4]} for r in jeux[0] if r[1] or r[3]]

def forme_services(jeux, options):
    """Un service par identifiant : le panneau décrit exim sous deux clés (name et service), les compter deux fois comptait un service de trop."""
    vus, sortie = set(), []
    for s in _liste(jeux[0]):
        ident = s.get("id")
        if ident is None or str(ident) in vus:
            continue
        noms = []
        for cle in ("name", "service", "unit", "title"):
            n = str(s.get(cle) or "").strip()
            if n and n.lower().replace(".service", "") not in [x.lower().replace(".service", "") for x in noms]:
                noms.append(n)
        if not noms:
            continue
        vus.add(str(ident))
        etat = str(s.get("state") or s.get("status") or "")
        sortie.append({"id": str(ident), "nom": noms[0], "alias": [x.lower().replace(".service", "") for x in noms[1:]], "etat": etat, "actif": _actif(etat)})
    return sortie

PLANS = {"utilisateurs": plan_utilisateurs, "sites": plan_sites, "bases": plan_bases, "ftp": plan_ftp, "mail": plan_mail, "dns": plan_dns, "services": lambda schema, options: {"requetes": []}}

FORMES = {"utilisateurs": forme_utilisateurs, "sites": forme_sites, "bases": forme_bases, "ftp": forme_ftp, "mail": forme_mail, "dns": forme_dns, "services": forme_services}

def planifier(op, schema, options):
    return PLANS[op](schema, options)

def mettre_en_forme(op, jeux, options):
    return FORMES[op](jeux, options)

def point_lecture(entree):
    """Le point d'évolution `lecture` (contrat 1.0) : la lecture d'une famille de données du panneau en DEUX temps, le nexus faisant les entrées-sorties.
    Phase « plan » : le schéma de CETTE version du panneau en entrée, les requêtes à poser en sortie. Phase « forme » : les lignes lues en entrée, la valeur mise en forme en sortie."""
    op, schema, options = entree["op"], entree["schema"], entree["options"]
    if entree["phase"] == "plan":
        return planifier(op, schema, options)
    return {"valeur": mettre_en_forme(op, entree["jeux"], options)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_lecture(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de fastpanel (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_lecture.json ; corpus doré dans contrats/CN_lecture.corpus.json (sorties de l'ancien code, données synthétiques).
