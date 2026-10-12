"""Tâches planifiées et automatismes. Porté depuis V18.

Leçons de la V18 préservées ici :
  - V18 : cd expliquait 24 des 73 refus. `cd /opt && sed -n ...` doit être libre.
  - V18 : `sudo`, `env`, `nohup` masquaient la vraie cible : _resolve_binary les saute.
  - V18 : Redirections non-/dev/null écrivent.
  - V18 : `awk '{print > "x"}'` et `sed 's/a/b/w a.txt'` sont des écritures (options w, e, ou system()).
  - V18 : curl `-d`, `-T`, `-K` sont des écritures/envois ou chargement inconnu.
  - V18 : dmesg -C et journalctl --vacuum effacent les traces.
  - V18 : sqlite3 -readonly est sûr (le binaire lui-même le garantit).
  - V18 : `$((...))` n'est pas une exécution, `$(...)` l'est.
  - V18 : cron ne sait pas faire un verrou, une fenêtre, un réessai, ou une suite. L'enrobage s'en charge.
  - V18 : l'état d'un cron est inconnu s'il n'y a pas d'occurrence, pas "ok".
  - V18 : Marge d'une occurrence pour le silence.
  - V18 : Code de sortie non nul = échec.

Ce qu'on n'a pas pu porter (les "# TODO") :
  - Le courtier: L'exécution en subprocess.run et crontab systemctl/os.makedirs, remplacés par un message ou désactivés (le noyau V19 ne touche pas au système).
  - Le module système (pour fastpanel_crons), projets (pour liens projets/mandats), sauvegardes (pour resumes).
"""
import re
import os
import time
import json
import hashlib
from datetime import datetime, timedelta

def _utcnow():
    return datetime.utcnow()

# Les constantes V18
_WRAPPERS = {"sudo", "nohup", "command", "builtin", "exec", "stdbuf", "nice",
             "ionice", "time", "env", "setsid"}
_WRAPPERS_ONE_ARG = {"timeout"}
_REDIR_SAFE_TARGETS = {"/dev/null", "/dev/stderr", "/dev/stdout", "&1", "&2", "1", "2"}
_SEGMENT_SEPARATORS = {";", "|", "||", "&&", "&", "\n"}

RISKY_PATTERNS = [
    r'\brm\s+-[rf]', r'\bdd\s+if=', r'\bmkfs', r'\breboot\b', r'\bshutdown\b',
    r'\bsed\s+-i\b', r'\b(perl|python3?|ruby)\s+.*-i\b', r'\bchmod\b', r'\bchown\b',
    r'\btee\b', r'\bkill(all)?\b', r'\bpkill\b', r'\buserdel\b', r'\bmkswap\b',
    r'\biptables\b', r'\bsystemctl\s+(stop|disable|mask|restart)\b', r'\btruncate\b',
]

_OPENSSL_DANGER = {
    "req", "genrsa", "genpkey", "enc", "pkeyutl", "rsautl", "dgst", "smime",
    "cms", "ca", "s_client", "s_server", "s_time", "rand", "passwd", "ts",
}

_CURL_ENVOI = {
    "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode",
    "--data-ascii", "-F", "--form", "--form-string", "-T", "--upload-file",
    "-K", "--config",
}

_SED_SUR = re.compile(r"^\s*(?:\$\(\([^()]*\)\)|[0-9$,~+])*\s*[pdq]\s*$")
_SUBSTITUTION = re.compile(r"`|\$\((?!\()|<\(|>\(")
_INPLACE_TOOLS = {"sed", "perl", "ruby", "awk", "gawk"}
_WRITE_TOOLS = {"tee", "truncate", "install", "cp", "mv", "ln", "dd", "touch"}

_CRON_DOW_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
_CRON_SHORTCUTS = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
_CRON_TAG = "# cassandra-id:"
_CRON_WRAP_VERSION = "2"

_CRON_DANGER_EXTRA = [
    (r'>\s*/(etc|boot|usr|bin|sbin|lib|var/lib)/', "écriture dans une arborescence système"),
    (r'\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b', "exécution directe d'un contenu téléchargé"),
]
_CRON_HEAVY = re.compile(
    r"\b(mysqldump|pg_dump|rsync|tar|borg|restic|duplicity|gzip|bzip2|xz|zip|"
    r"7z|dd|find|du|clamscan|freshclam|apt-get|apt|yum|dnf|certbot|ffmpeg|"
    r"convert|composer|npm|docker)\b")

_CRON_REG_DEFAUT = {"fenetre_min": 0, "verrou": 0, "essais": 0, "motif_echec": "",
                    "apres_ref": "", "apres_si_ok": 1, "nom": ""}

_CRON_SUGGEST_SYS = (
    "Tu convertis une demande en tâche planifiée Linux pour un serveur Debian.\n"
    "Réponds UNIQUEMENT par un objet JSON, sans texte autour :\n"
    '{"description": "...", "cron_expr": "m h jm mois js", "command": "...", '
    '"explication": "une phrase"}\n'
    "Règles : expression cron à 5 champs ; chemins absolus ; commande non interactive ; "
    "pas de sudo ; échapper % en \\% ; privilégier la commande la moins destructrice."
)

_RO_BINARIES = {
    "ls", "cat", "head", "tail", "wc", "nl", "tac", "strings", "file", "stat",
    "cd", "pushd", "popd", "readlink", "realpath", "basename", "dirname", "echo", "printf", "true",
    "false", "test", "date", "uptime", "uname", "hostname", "hostnamectl", "whoami", "id", "groups", "pwd", "df", "du", "free", "vmstat", "iostat",
    "mpstat", "nproc", "lscpu", "lsblk", "blkid", "lsusb", "lspci", "dmidecode",
    "sensors", "ps", "pgrep", "pidof", "pstree", "top", "htop", "ss", "netstat",
    "lsof", "ip", "ifconfig", "route", "arp", "ping", "ping6", "dig", "host",
    "nslookup", "traceroute", "mtr", "whois", "getent", "grep", "egrep", "fgrep",
    "rg", "awk", "gawk", "sed", "cut", "sort", "uniq", "tr", "column", "paste",
    "join", "comm", "diff", "cmp", "md5sum", "sha1sum", "sha256sum", "seq",
    "sleep", "which", "whereis", "type", "printenv", "locale", "dmesg",
    "journalctl", "last", "lastlog", "who", "w", "zcat", "zgrep", "jq", "xxd",
    "od", "base64", "find", "fuser", "runlevel", "dpkg-query", "needrestart",
    "crontab", "openssl", "curl", "wc", "sqlite3",
}
_RO_SUBCOMMANDS = {
    "systemctl": {"status", "is-active", "is-enabled", "is-failed", "list-units",
                  "list-unit-files", "list-timers", "list-sockets", "show", "cat",
                  "get-default", "list-dependencies", "list-jobs"},
    "apt":       {"list", "show", "policy", "search", "depends", "rdepends"},
    "apt-get":   {"check"},
    "apt-cache": {"policy", "show", "showpkg", "search", "depends", "madison", "stats"},
    "dpkg":      {"-l", "-L", "-s", "-S", "-p", "--list", "--status", "--audit",
                  "--search", "--listfiles", "--print-architecture", "--get-selections"},
    "docker":    {"ps", "images", "logs", "inspect", "version", "info", "stats", "top", "port", "diff"},
    "git":       {"status", "log", "diff", "show", "branch", "remote", "describe", "blame", "rev-parse", "ls-files", "tag"},
    "tailscale": {"status", "version", "ip", "netcheck", "whois", "ping"},
    "nginx":     {"-t", "-v", "-V", "-T"},
    "certbot":   {"certificates"},
    "ufw":       {"status"},
    "pip":       {"list", "show", "freeze"},
    "pip3":      {"list", "show", "freeze"},
    "npm":       {"list", "ls", "view", "outdated"},
    "python3":   {"--version", "-V"},
    "perl":      {"-v", "-c", "--version"},
}

def brancher(ctx):
    db = ctx.stockage

    # Constantes dynamiques basées sur un réglage global (s'il existe), pour simuler V18 proprement sans système
    _CRON_WRAP_DIR = "/usr/local/lib/cassandra"
    _CRON_WRAP_PATH = _CRON_WRAP_DIR + "/cron-wrap.sh"
    _CRON_SPOOL = "/tmp/cron-runs-spool"  # TODO(courtier): dossier dynamique d'ingestion

    # === Fonctions d'analyse (V18 conservées) ===
    def _split_segments(cmd: str):
        import shlex
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            return None
        segments, cur = [], []
        for tok in tokens:
            if tok in _SEGMENT_SEPARATORS:
                segments.append(cur)
                cur = []
            else:
                cur.append(tok)
        segments.append(cur)
        return [s for s in segments if s]

    def _resolve_binary(tokens):
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', t):
                i += 1
            elif t in _WRAPPERS:
                i += 1
            elif t in _WRAPPERS_ONE_ARG:
                i += 2
            else:
                break
        if i >= len(tokens):
            return "", []
        return tokens[i].rsplit("/", 1)[-1], tokens[i + 1:]

    def _sed_scripts(args) -> list:
        out, i = [], 0
        while i < len(args):
            a = args[i]
            if a in ("-e", "--expression"):
                if i + 1 < len(args): out.append(args[i + 1])
                i += 2
                continue
            if a.startswith("--expression="):
                out.append(a.split("=", 1)[1])
                i += 1
                continue
            if a.startswith("-"):
                i += 1
                continue
            out.append(a)
            break
        return out

    def _segment_is_readonly(tokens) -> bool:
        binary, args = _resolve_binary(tokens)
        if not binary: return False
        _noms = [a.split("=", 1)[0] if a.startswith("--") and "=" in a else a for a in args]
        for j, t in enumerate(args):
            if t in (">", ">>", "<>"):
                target = args[j + 1] if j + 1 < len(args) else ""
                if target not in _REDIR_SAFE_TARGETS: return False
        if binary in ("apt", "apt-get", "aptitude", "dpkg", "yum", "dnf") and any(
                a in ("-s", "--simulate", "--dry-run", "--just-print", "--no-act", "--assume-no") for a in args):
            return True
        if binary in _RO_SUBCOMMANDS:
            allowed = _RO_SUBCOMMANDS[binary]
            sub = next((a for a in args if not a.startswith("-")), None)
            first = args[0] if args else ""
            return (sub in allowed) or (first in allowed)
        if binary not in _RO_BINARIES:
            return False
        if binary in ("sed", "awk", "gawk", "perl") and any(a.startswith("-i") for a in args): return False
        if binary == "find" and any(a in ("-delete", "-exec", "-execdir", "-ok") for a in args): return False
        if binary in ("fuser", "lsof") and any(a.startswith("-k") for a in args): return False
        if binary == "openssl":
            if any(n in _OPENSSL_DANGER for n in _noms): return False
            if any(a in ("-out", "-keyout", "-signature", "-sigfile") for a in args): return False
        if binary == "sqlite3":
            if not any(a in ("-readonly", "--readonly") for a in args): return False
            if re.search(r"(?i)\battach\b", " ".join(args)): return False
        if binary == "journalctl" and any(n in ("--rotate", "--flush", "--sync", "--relinquish-var") or n.startswith("--vacuum") for n in _noms): return False
        if binary == "dmesg" and any(n in ("-C", "-c", "--clear", "--read-clear") for n in _noms): return False
        if binary == "crontab" and "-l" not in args: return False
        if binary == "curl":
            if any(n in _CURL_ENVOI or n.startswith("--data") or n.startswith("--form") for n in _noms): return False
            if any(n in ("-O", "--remote-name", "--remote-name-all") for n in _noms): return False
            for j, a in enumerate(args):
                if a in ("-o", "--output"):
                    if (args[j + 1] if j + 1 < len(args) else "") not in _REDIR_SAFE_TARGETS: return False
        if binary in ("awk", "gawk", "mawk", "nawk"):
            if any(a in ("-f", "--file", "--exec", "--source", "-E") for a in args): return False
            if re.search(r"system\s*\(|close\s*\(|ENVIRON|getline|[>|]", " ".join(args)): return False
        if binary == "sed":
            if any(a in ("-f", "--file") or a.startswith("--file=") or (a.startswith("-f") and len(a) > 2) for a in args): return False
            for _s in _sed_scripts(args):
                if _SED_SUR.match(_s): continue
                _m = re.match(r"^\s*s(.)(.*)\1([A-Za-z0-9]*)\s*$", _s, re.S)
                if _m and not re.search(r"[we]", _m.group(3)): continue
                return False
        if binary == "find" and any(a in ("-fprintf", "-fprint", "-fprint0", "-fls") for a in args): return False
        if binary == "xxd":
            _ops, _k = [], 0
            while _k < len(args):
                if args[_k] in ("-c", "-g", "-l", "-o", "-s", "-C"): _k += 2; continue
                if args[_k].startswith("-"): _k += 1; continue
                _ops.append(args[_k]); _k += 1
            if len(_ops) >= 2: return False
        return True

    def is_risky_command(cmd: str) -> bool:
        if not cmd or not cmd.strip(): return False
        if _SUBSTITUTION.search(cmd or ""): return True
        segments = _split_segments(cmd)
        if segments is None: return True
        return not all(_segment_is_readonly(s) for s in segments)

    # === Manipulation chronologique (V18) ===
    def _cron_field(spec: str, lo: int, hi: int) -> set:
        spec = (spec or "").strip()
        if not spec: return set()
        out = set()
        for part in spec.split(","):
            part = part.strip()
            step = 1
            if "/" in part:
                part, _, s = part.partition("/")
                try: step = max(1, int(s))
                except ValueError: return set()
            if part in ("*", ""): a, b = lo, hi
            elif "-" in part:
                try: a, b = [int(x) for x in part.split("-", 1)]
                except ValueError: return set()
            else:
                try: a = b = int(part)
                except ValueError: return set()
            if a > b or a < lo or b > hi: return set()
            out.update(range(a, b + 1, step))
        return out

    def cron_occurrences(expr: str, date_from: str, date_to: str, max_per_day: int = 4) -> list:
        fields = (expr or "").split()
        if len(fields) != 5: return []
        mins = _cron_field(fields[0], 0, 59)
        hours = _cron_field(fields[1], 0, 23)
        doms = _cron_field(fields[2], 1, 31)
        months = _cron_field(fields[3], 1, 12)
        dows = _cron_field(fields[4], 0, 7)
        if not (mins and hours and doms and months and dows): return []
        dows = {0 if d == 7 else d for d in dows}
        dom_all = _cron_field("*", 1, 31) == doms
        dow_all = {0, 1, 2, 3, 4, 5, 6} <= dows
        try:
            d = datetime.strptime(date_from[:10], "%Y-%m-%d")
            end = datetime.strptime(date_to[:10], "%Y-%m-%d")
        except Exception: return []
        out = []
        while d <= end and len(out) < 400:
            dow = (d.weekday() + 1) % 7
            if d.month in months:
                if dom_all and dow_all: match = True
                elif dom_all: match = dow in dows
                elif dow_all: match = d.day in doms
                else: match = (d.day in doms) or (dow in dows)
                if match:
                    times = sorted((h, m) for h in hours for m in mins)
                    if len(times) > max_per_day:
                        h, m = times[0]
                        out.append({"at": "%s %02d:%02d" % (d.strftime("%Y-%m-%d"), h, m), "recurrent": len(times)})
                    else:
                        for h, m in times:
                            out.append({"at": "%s %02d:%02d" % (d.strftime("%Y-%m-%d"), h, m), "recurrent": 0})
            d += timedelta(days=1)
        return out

    def cron_normalize(expr: str) -> str:
        e = (expr or "").strip()
        return _CRON_SHORTCUTS.get(e.lower(), e)

    def cron_describe(expr: str) -> str:
        e = cron_normalize(expr)
        if e.lower() == "@reboot": return "à chaque démarrage"
        f = e.split()
        if len(f) != 5: return e
        mi, ho, dom, mon, dow = f
        def _every(spec): return spec.strip() in ("*", "")
        def _step(spec):
            if spec.startswith("*/"):
                try: return int(spec[2:])
                except ValueError: return 0
            return 0
        jours = ""
        if not _every(dow):
            d = _cron_field(dow, 0, 7)
            if d:
                noms = sorted({_CRON_DOW_FR[0 if x == 7 else x] for x in d})
                jours = " le " + ", ".join(noms) if len(noms) < 7 else ""
        if not _every(dom): jours += " le %s du mois" % dom
        if not _every(mon): jours += " (mois %s)" % mon
        smi, sho = _step(mi), _step(ho)
        if smi and _every(ho): return ("toutes les %d minutes" % smi) + jours
        if sho and mi.isdigit(): return ("toutes les %d heures (à H+%s)" % (sho, mi)) + jours
        if _every(mi) and _every(ho): return "chaque minute" + jours
        if mi.isdigit() and _every(ho): return ("à la minute %s de chaque heure" % mi) + jours
        if mi.isdigit() and ho.isdigit():
            base = "à %02d:%02d" % (int(ho), int(mi))
            return (base + jours) if jours else base + " chaque jour"
        return e

    def _cron_parse(expr: str):
        f = cron_normalize(expr).split()
        if len(f) != 5: return None
        mins, hours, doms, months, dows = _cron_field(f[0], 0, 59), _cron_field(f[1], 0, 23), _cron_field(f[2], 1, 31), _cron_field(f[3], 1, 12), _cron_field(f[4], 0, 7)
        if not (mins and hours and doms and months and dows): return None
        dows = {0 if x == 7 else x for x in dows}
        dom_all, dow_all = _cron_field("*", 1, 31) == doms, {0, 1, 2, 3, 4, 5, 6} <= dows
        def day_ok(d):
            if d.month not in months: return False
            dow = (d.weekday() + 1) % 7
            if dom_all and dow_all: return True
            if dom_all: return dow in dows
            if dow_all: return d.day in doms
            return (d.day in doms) or (dow in dows)
        return sorted(mins), sorted(hours), day_ok

    def cron_prev_occurrence(expr: str, ref: str = "", lookback_days: int = 21) -> str:
        parsed = _cron_parse(expr)
        if not parsed: return ""
        mins, hours, day_ok = parsed
        now = ref or _utcnow().strftime("%Y-%m-%d %H:%M")
        try: d = datetime.strptime(now[:16], "%Y-%m-%d %H:%M")
        except Exception: return ""
        cut_h, cut_m = d.hour, d.minute
        day = d.replace(hour=0, minute=0)
        for i in range(lookback_days + 1):
            if day_ok(day):
                for h in reversed(hours):
                    if i == 0 and h > cut_h: continue
                    for m in reversed(mins):
                        if i == 0 and h == cut_h and m > cut_m: continue
                        return "%s %02d:%02d" % (day.strftime("%Y-%m-%d"), h, m)
            day -= timedelta(days=1)
        return ""

    def cron_next_occurrence(expr: str, ref: str = "", ahead_days: int = 45) -> str:
        parsed = _cron_parse(expr)
        if not parsed: return ""
        mins, hours, day_ok = parsed
        now = ref or _utcnow().strftime("%Y-%m-%d %H:%M")
        try: d = datetime.strptime(now[:16], "%Y-%m-%d %H:%M")
        except Exception: return ""
        cut_h, cut_m = d.hour, d.minute
        day = d.replace(hour=0, minute=0)
        for i in range(ahead_days + 1):
            if day_ok(day):
                for h in hours:
                    if i == 0 and h < cut_h: continue
                    for m in mins:
                        if i == 0 and h == cut_h and m <= cut_m: continue
                        return "%s %02d:%02d" % (day.strftime("%Y-%m-%d"), h, m)
            day += timedelta(days=1)
        return ""

    def _cron_ref(user: str, command: str) -> str:
        return hashlib.sha1(("%s|%s" % ((user or "").strip(), (command or "").strip()[:300])).encode("utf-8")).hexdigest()[:16]

    # === Intégrations Base de données ===
    def cron_critical_refs() -> set:
        return {r["ref"] for r in db.lire("SELECT ref FROM cron_critical")}

    def cron_modifs(ref: str, limit: int = 12) -> list:
        return db.lire("SELECT ts, acteur, quoi FROM cron_modifs WHERE ref=? ORDER BY id DESC LIMIT ?", (ref, int(limit)))

    def cron_modif(ref: str, quoi: str, acteur: str = "") -> None:
        db.ecrire("INSERT INTO cron_modifs (ref, acteur, quoi) VALUES (?,?,?)", (str(ref or ""), str(acteur or "système")[:60], str(quoi)[:300]))
        db.ecrire("DELETE FROM cron_modifs WHERE ref=? AND id NOT IN (SELECT id FROM cron_modifs WHERE ref=? ORDER BY id DESC LIMIT 40)", (str(ref or ""), str(ref or "")))

    def cron_reglages(ref: str = "") -> dict:
        if ref:
            r = db.lire("SELECT * FROM cron_reglages WHERE ref=?", (ref,))
            return r[0] if r else dict(_CRON_REG_DEFAUT, ref=ref)
        return {r["ref"]: r for r in db.lire("SELECT * FROM cron_reglages")}

    def _cron_state(job: dict, now: str) -> tuple:
        if not job.get("enabled"): return "désactivé", "cron désactivé"
        manquantes = job.get("missing_targets") or []
        if manquantes: return "cassé", "introuvable ou non exécutable : %s" % ", ".join(manquantes[:3])
        code = job.get("last_exit")
        if code is not None and code != 0: return "échec", "dernière exécution en échec (code %s) le %s" % (code, (job.get("last_run") or "?"))
        expr = job.get("schedule") or ""
        if cron_normalize(expr).lower() == "@reboot": return "inconnu", "déclenché au démarrage, non projetable"
        exp_prev = job.get("expected_prev") or ""
        if not exp_prev: return "inconnu", "planning illisible ou aucune exécution attendue récemment"
        last = (job.get("last_run") or "").strip()[:16].replace("T", " ")
        if not last: return "inconnu", "aucune trace d'exécution dans le journal"
        try:
            avant = (datetime.strptime(exp_prev[:16], "%Y-%m-%d %H:%M") - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
            tol = cron_prev_occurrence(expr, avant) or exp_prev
        except Exception: tol = exp_prev
        if last >= tol: return "ok", "dernière exécution le %s" % last
        try: retard = int((datetime.strptime(exp_prev[:16], "%Y-%m-%d %H:%M") - datetime.strptime(last[:16], "%Y-%m-%d %H:%M")).total_seconds() // 3600)
        except Exception: retard = 0
        return "muet", ("attendu le %s, dernière trace le %s (%dh de retard)" % (exp_prev, last, retard))

    def cron_targets(command: str) -> list:
        segs = _split_segments(command or "")
        if segs is None: return []
        out = []
        for tokens in segs:
            i = 0
            while i < len(tokens):
                t = tokens[i]
                if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', t): i += 1
                elif t in _WRAPPERS: i += 1
                elif t in _WRAPPERS_ONE_ARG: i += 2
                else: break
            if i < len(tokens) and tokens[i]: out.append(tokens[i])
        return out

    def cron_missing_targets(command: str) -> list:
        missing = []
        for t in cron_targets(command):
            if "$" in t or "*" in t or t.startswith("~"): continue
            if os.path.isabs(t):
                if not (os.path.isfile(t) and os.access(t, os.X_OK)): missing.append(t)
            elif "/" not in t:
                import shutil
                if shutil.which(t) is None: missing.append(t)
        return missing

    def cron_unified_list() -> list:
        now = _utcnow().strftime("%Y-%m-%d %H:%M")
        by_ref = {}
        def _put(ref, data):
            cur = by_ref.get(ref)
            if cur is None:
                by_ref[ref] = data
                return
            for k, v in data.items():
                if v and not cur.get(k): cur[k] = v
            cur["sources"] = sorted(set(cur.get("sources", []) + data.get("sources", [])))
            
        rows = db.lire("SELECT id, description, cron_expr, command, created_at, active, wrapped FROM cron_natural")
        for r in rows:
            cmd = r["command"] or ""
            _put(_cron_ref("root", cmd), {
                "ref": _cron_ref("root", cmd), "user": "root", "schedule": r["cron_expr"] or "",
                "command": cmd, "description": r["description"] or "", "enabled": 1 if r["active"] else 0,
                "last_run": "", "last_status": "", "created_at": r["created_at"] or "", "natural_id": r["id"],
                "wrapped": 1 if r["wrapped"] else 0, "sources": ["cassandra"]})

        # TODO(systeme): _fp_crons_brut() manquant, on simule l'intégration système
        fp = []
        for c in fp:
            user, cmd = c.get("user") or "root", c.get("command") or ""
            if not cmd: continue
            _put(_cron_ref(user, cmd), {
                "ref": _cron_ref(user, cmd), "user": user, "schedule": c.get("schedule") or "", "command": cmd,
                "description": "", "enabled": 1 if c.get("enabled", 1) else 0,
                "last_run": c.get("last_run") or "", "last_status": c.get("last_status") or "",
                "created_at": "", "natural_id": None, "sources": ["système"]})

        manual = {}
        for r in db.lire("SELECT ref, started_at, exit_code, trigger FROM cron_runs WHERE id IN (SELECT MAX(id) FROM cron_runs GROUP BY ref)"):
            manual[r["ref"]] = (r["started_at"] or "", r["exit_code"], r["trigger"] or "")

        links = {} # TODO(projets): _cron_links_by_ref() -> {}
        critiques = cron_critical_refs()
        out = []
        for ref, j in by_ref.items():
            expr = j.get("schedule") or ""
            mts, mcode, mtrig = manual.get(ref, ("", None, ""))
            if mts and mts >= (j.get("last_run") or ""):
                j["last_run"] = mts
                j["last_status"] = "%s (code %s)" % (mtrig or "enregistré", mcode)
                j["last_exit"] = mcode
            j["has_history"] = ref in manual
            j["missing_targets"] = cron_missing_targets(j.get("command") or "")
            j["human"] = cron_describe(expr)
            j["next_run"] = cron_next_occurrence(expr, now) if j["enabled"] else ""
            j["expected_prev"] = cron_prev_occurrence(expr, now) if j["enabled"] else ""
            j["projects"] = links.get(ref, [])
            j["critical"] = 1 if ref in critiques else 0
            j["state"], j["state_detail"] = _cron_state(j, now)
            out.append(j)
        out.sort(key=lambda x: ({"cassé": 0, "échec": 1, "muet": 2, "inconnu": 3, "ok": 4, "désactivé": 5}.get(x["state"], 6), x.get("user") or "", x.get("command") or ""))
        return out

    def cron_is_destructive(command: str) -> str:
        cmd = (command or "").strip()
        if not cmd: return ""
        for pat in RISKY_PATTERNS:
            if re.search(pat, cmd): return "motif destructeur : %s" % pat.replace(r"\b", "").replace("\\s+", " ")
        for pat, label in _CRON_DANGER_EXTRA:
            if re.search(pat, cmd): return label
        return ""

    def cron_preview(cron_expr: str, count: int = 5) -> list:
        out, ref = [], _utcnow().strftime("%Y-%m-%d %H:%M")
        for _ in range(max(1, min(int(count or 5), 12))):
            nxt = cron_next_occurrence(cron_expr, ref)
            if not nxt: break
            out.append(nxt)
            ref = nxt
        return out

    def cron_validate(cron_expr: str, command: str) -> dict:
        expr = cron_normalize(cron_expr)
        cmd = (command or "").strip()
        if not cmd: return {"ok": False, "reason": "commande vide"}
        if expr.lower() != "@reboot":
            if len(expr.split()) != 5: return {"ok": False, "reason": "expression cron invalide"}
            if not _cron_parse(expr): return {"ok": False, "reason": "expression cron illisible"}
        if "\n" in cmd or "%" in cmd.replace("\\%", ""): return {"ok": False, "reason": "le caractère % doit être échappé (\\%)"}
        return {"ok": True, "expr": expr, "command": cmd}

    # === Les Moteurs ===
    def ingest_runs(ctx):
        if not os.path.isdir(_CRON_SPOOL): return
        fichiers = sorted(os.listdir(_CRON_SPOOL))[:500]
        for nom in fichiers:
            chemin = os.path.join(_CRON_SPOOL, nom)
            if nom.endswith(".tmp"): continue
            try:
                with open(chemin, "r", encoding="utf-8", errors="replace") as f:
                    contenu = f.read()
                tete, _, corps = contenu.partition("\n")
                parts = tete.split("|")
                if len(parts) == 4:
                    db.ecrire("INSERT INTO cron_runs (ref, started_at, duration_ms, exit_code, output, trigger) VALUES (?,?,?,?,?,?)",
                              (parts[0], parts[1], int(parts[2]), int(parts[3]), corps.strip()[:4000], "cron"))
            except Exception: pass
            try: os.remove(chemin)
            except Exception: pass

    def tick_apres(ctx):
        regs = cron_reglages()
        chainees = {r: v for r, v in regs.items() if v.get("apres_ref")}
        if not chainees: return
        derniers = {r["ref"]: (r["started_at"] or "", r["exit_code"]) for r in db.lire("SELECT ref, started_at, exit_code FROM cron_runs WHERE id IN (SELECT MAX(id) FROM cron_runs GROUP BY ref)")}
        for ref, r in chainees.items():
            amont = r["apres_ref"]
            ts_amont, code_amont = derniers.get(amont, ("", None))
            if not ts_amont: continue
            if r.get("apres_si_ok") and code_amont not in (0, None): continue
            ts_moi = (derniers.get(ref) or ("", None))[0]
            if ts_moi and ts_moi >= ts_amont: continue
            # TODO(courtier): cron_run_now équivalent via courtier, au lieu de subprocess en root
            ctx.emettre("tache.executee", donnees={"ref": ref, "declencheur": "tick_apres"})

    ctx.moteur("ingest_runs", ingest_runs)
    ctx.moteur("tick_apres", tick_apres)

    # === Détecteur de Pannes (V18: cron_silence_pass) ===
    def pannes_detecteur(ctx):
        jobs = cron_unified_list()
        constats = []
        for j in jobs:
            if j.get("state") in ("cassé", "échec", "muet"):
                constats.append({
                    "objet": ("tache", j["ref"]),
                    "titre": "Tâche en panne : " + j["ref"],
                    "detail": j.get("state_detail", ""),
                    "niveau": "critique" if j.get("critical") else "avoir",
                    "capacite": "planifie.fiche",
                    "args": {"ref": j["ref"]}
                })
        return constats
    ctx.detecteur("pannes", pannes_detecteur)

    # === Les Capacités ===
    def lister(ctx):
        return {"taches": cron_unified_list()}

    def fiche(ctx, ref=""):
        job = next((j for j in cron_unified_list() if j["ref"] == ref), None)
        if not job: return {"ok": False, "reason": "tâche introuvable"}
        runs = db.lire("SELECT started_at, duration_ms, exit_code, output, trigger FROM cron_runs WHERE ref=? ORDER BY id DESC LIMIT 40", (ref,))
        reg = cron_reglages(ref)
        expr = job.get("schedule") or ""
        moy_row = db.lire("SELECT AVG(duration_ms) as m FROM cron_runs WHERE ref=? AND duration_ms > 0", (ref,))
        moy = int(moy_row[0]["m"]) if moy_row and moy_row[0]["m"] else 0
        def _cron_interval_min(e):
            now = _utcnow().strftime("%Y-%m-%d %H:%M")
            a = cron_next_occurrence(e, now)
            if not a: return 0
            b = cron_next_occurrence(e, a)
            if not b: return 0
            return int((datetime.strptime(b[:16], "%Y-%m-%d %H:%M") - datetime.strptime(a[:16], "%Y-%m-%d %H:%M")).total_seconds() // 60)
        inter = _cron_interval_min(expr)
        return {"ok": True, "job": job, "runs": runs, "reglages": reg, "prochaines": cron_preview(expr, 5) if job.get("enabled") else [],
                "duree_moyenne_ms": moy, "intervalle_min": inter, "lourde": 1 if _CRON_HEAVY.search(job.get("command") or "") else 0}

    def resume(ctx):
        jobs = cron_unified_list()
        mauvais = [j for j in jobs if j.get("state") in ("cassé", "échec", "muet")]
        return {"familles": [{"cle": "crons", "nom": "Tâches planifiées", "total": len(jobs), "ennuis": len(mauvais), "pire": ("%d en panne" % len(mauvais)) if mauvais else "tout à l'heure", "etat": "danger" if mauvais else "ok"}]}

    def sauver(ctx, description="", cron_expr="", command="", cron_id=None, enabled=True, confirm_risky=False, wrapped=True):
        v = cron_validate(cron_expr, command)
        if not v["ok"]: return v
        expr, cmd = v["expr"], v["command"]
        danger = cron_is_destructive(cmd)
        if danger and not confirm_risky:
            return {"ok": False, "needs_confirm": True, "reason": "Commande destructrice (%s)." % danger, "command": cmd}
        if cron_id:
            prev = db.lire("SELECT description, cron_expr, command, active, wrapped FROM cron_natural WHERE id=?", (int(cron_id),))
            if not prev: return {"ok": False, "reason": "tâche introuvable"}
            db.ecrire("UPDATE cron_natural SET description=?, cron_expr=?, command=?, active=?, wrapped=? WHERE id=?", (description, expr, cmd, 1 if enabled else 0, 1 if wrapped else 0, int(cron_id)))
            nid = int(cron_id)
            avant = prev[0]
        else:
            nid = db.ecrire("INSERT INTO cron_natural (description, cron_expr, command, active, wrapped) VALUES (?,?,?,?,?)", (description, expr, cmd, 1 if enabled else 0, 1 if wrapped else 0))
            avant = None
        # TODO(courtier): appliquer à la crontab via subprocess
        ctx.emettre("tache.creee" if not cron_id else "tache.modifiee", donnees={"id": nid})
        return {"ok": True, "id": nid, "avant": avant, "apres": {"description": description, "expr": expr, "cmd": cmd, "active": 1 if enabled else 0}}

    def prouver_sauver(ctx, res):
        return bool(db.lire("SELECT 1 FROM cron_natural WHERE id=?", (res["id"],)))

    def defaire_sauver(ctx, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM cron_natural WHERE id=?", (res["id"],))
        else:
            db.ecrire("UPDATE cron_natural SET description=?, cron_expr=?, command=?, active=?, wrapped=? WHERE id=?", (res["avant"]["description"], res["avant"]["cron_expr"], res["avant"]["command"], res["avant"]["active"], res["avant"]["wrapped"], res["id"]))

    def basculer(ctx, cron_id, enabled):
        row = db.lire("SELECT active FROM cron_natural WHERE id=?", (int(cron_id),))
        if not row: return {"ok": False, "reason": "introuvable"}
        avant = row[0]["active"]
        db.ecrire("UPDATE cron_natural SET active=? WHERE id=?", (1 if enabled else 0, int(cron_id)))
        # TODO(courtier): appliquer la bascule crontab
        return {"ok": True, "id": int(cron_id), "avant": avant, "apres": 1 if enabled else 0}

    def prouver_basculer(ctx, res):
        r = db.lire("SELECT active FROM cron_natural WHERE id=?", (res["id"],))
        return r and r[0]["active"] == res["apres"]

    def defaire_basculer(ctx, res):
        db.ecrire("UPDATE cron_natural SET active=? WHERE id=?", (res["avant"], res["id"]))

    def supprimer(ctx, cron_id):
        row = db.lire("SELECT * FROM cron_natural WHERE id=?", (int(cron_id),))
        if not row: return {"ok": False, "reason": "introuvable"}
        db.ecrire("DELETE FROM cron_natural WHERE id=?", (int(cron_id),))
        # TODO(courtier): appliquer la suppression crontab
        ctx.emettre("tache.supprimee", donnees={"id": int(cron_id)})
        return {"ok": True, "id": int(cron_id), "avant": row[0]}

    def prouver_supprimer(ctx, res):
        return not db.lire("SELECT 1 FROM cron_natural WHERE id=?", (res["id"],))

    def defaire_supprimer(ctx, res):
        db.ecrire("INSERT INTO cron_natural (id, description, cron_expr, command, created_at, active, wrapped) VALUES (?,?,?,?,?,?,?)", (res["id"], res["avant"]["description"], res["avant"]["cron_expr"], res["avant"]["command"], res["avant"]["created_at"], res["avant"]["active"], res["avant"]["wrapped"]))

    def executer(ctx, ref=""):
        # TODO(courtier): Remplacer le subprocess.run par un appel courtier
        return {"ok": False, "reason": "Exécution directe désactivée pour éviter les lancements root depuis le noyau. Utilisez le courtier."}

    def regler(ctx, ref, fenetre_min=0, verrou=0, essais=0, motif_echec="", apres_ref="", apres_si_ok=1, nom=""):
        avant = cron_reglages(ref)
        db.ecrire("INSERT OR REPLACE INTO cron_reglages (ref, fenetre_min, verrou, essais, motif_echec, apres_ref, apres_si_ok, nom) VALUES (?,?,?,?,?,?,?,?)", (ref, fenetre_min, verrou, essais, motif_echec, apres_ref, apres_si_ok, nom))
        cron_modif(ref, "réglages modifiés", ctx.compte)
        return {"ok": True, "ref": ref, "avant": avant, "apres": {"fenetre_min": fenetre_min, "verrou": verrou}}

    def prouver_regler(ctx, res):
        return True

    def defaire_regler(ctx, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO cron_reglages (ref, fenetre_min, verrou, essais, motif_echec, apres_ref, apres_si_ok, nom) VALUES (?,?,?,?,?,?,?,?)", (res["ref"], a.get("fenetre_min", 0), a.get("verrou", 0), a.get("essais", 0), a.get("motif_echec", ""), a.get("apres_ref", ""), a.get("apres_si_ok", 1), a.get("nom", "")))

    def maintenance(ctx, actif=True, heures=4):
        fin_actuelle = ctx.reglage("cron_maintenance_fin")
        fin = (_utcnow() + timedelta(hours=max(1, min(24, int(heures or 4))))).strftime("%Y-%m-%d %H:%M") if actif else ""
        # TODO(reglages): ctx.reglage_set("cron_maintenance_fin", fin)
        return {"ok": True, "actif": bool(fin), "fin": fin, "avant": fin_actuelle}

    def prouver_maintenance(ctx, res):
        return True

    def defaire_maintenance(ctx, res):
        pass # TODO(reglages): ctx.reglage_set("cron_maintenance_fin", res["avant"])

    ctx.implementer("lister", lister)
    ctx.implementer("fiche", fiche)
    ctx.implementer("resume", resume)
    ctx.implementer("sauver", sauver, prouver_sauver, defaire_sauver)
    ctx.implementer("basculer", basculer, prouver_basculer, defaire_basculer)
    ctx.implementer("supprimer", supprimer, prouver_supprimer, defaire_supprimer)
    ctx.implementer("executer", executer, lambda c,r: True, lambda c,r: None)
    ctx.implementer("regler", regler, prouver_regler, defaire_regler)
    ctx.implementer("maintenance", maintenance, prouver_maintenance, defaire_maintenance)
