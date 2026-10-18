# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : message technique (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #71489b
# HÔTE CN    : CN_module.py · motif_technique @1.0
# RÔLE       : reconnaît un message technique (certbot, cron, supervision, sauvegarde, système de courrier) pour le ranger à part.
# MÉTHODE    : fonction pure : un signal sur l'EXPÉDITEUR est exigé ; l'objet seul ne suffit jamais.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=motif_technique contrat=@1.0 version=EC0 empreinte=71489b ▼▼▼
import re

TECH_EXP = re.compile(r"(certbot|let'?s\s*encrypt|cron|logwatch|monit|nagios|zabbix|netdata|fail2ban|backup|borg|restic|rsnapshot|mdadm|smartd|unattended-upgrades|postmaster|mailer-daemon|no-?reply@|root@|admin@)", re.I)

TECH_SUJ = re.compile(r"(cron\s*<|certificat|certificate|expir|renew|sauvegarde|backup|disk\s*(space|usage)|s\.m\.a\.r\.t|raid|degraded|failed|échec|erreur\s*serveur|security\s*update|reboot required|anacron|logwatch)", re.I)

def motif_technique(m):
    """Motif technique reconnu, ou ''. Un signal sur l'EXPÉDITEUR est exigé : « sauvegarde » dans l'objet d'un client parle d'un devis, pas d'un serveur."""
    exp, suj = m.get("from_addr") or m.get("from") or "", m.get("subject") or ""
    if TECH_EXP.search(exp):
        return "expéditeur technique"
    if TECH_SUJ.search(suj) and TECH_EXP.search(exp + " " + suj):
        return "objet et expéditeur techniques"
    return ""

def point_motif_technique(entree):
    """Le point d'évolution `motif_technique` (contrat 1.0)."""
    return {"valeur": motif_technique(entree["m"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_motif_technique(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_motif_technique.json ; corpus doré dans contrats/CN_motif_technique.corpus.json (sorties de l'ancien code, données synthétiques).
