# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les formes des relevés de « La machine »
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.4.1  #5464a9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les formes des relevés de « La machine » : ce que le collecteur lit (docker inspect, nginx -T, ps, /proc, systemctl, w, le journal de sshd, /proc/cpuinfo, lsblk) devient ici des lignes prêtes à écrire. Aucune commande, aucun fichier : du te
# MÉTHODE    : fonctions pures, du texte des commandes aux lignes prêtes à écrire ; aucune commande ni fichier, les lectures restent dans CN_sensorium.py
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.1 empreinte=5464a9 ▼▼▼
"""Les formes des relevés de « La machine » : ce que le collecteur lit (docker inspect, nginx -T, ps, /proc, systemctl, w, le journal de sshd,
/proc/cpuinfo, lsblk) devient ici des lignes prêtes à écrire. Aucune commande, aucun fichier : du texte en entrée, des dictionnaires en sortie,
pour que chaque forme se vérifie sans machine. Les lectures, elles, restent dans CN_sensorium.py.

Rien de secret ne sort d'ici : d'un conteneur on ne garde ni ses variables d'environnement ni sa commande ; d'une clé SSH, son commentaire seul."""
import fnmatch
import ipaddress
import re

# ══ Conteneurs ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def portee(adresse: str) -> str:
    """Qui peut joindre un port publié sur cette adresse de la machine : « machine » (elle seule), « prive » (un réseau privé), « public »."""
    a = (adresse or "").strip().strip("[]")
    if a in ("", "0.0.0.0", "::", "*"):
        return "public"
    try:
        ip = ipaddress.ip_address(a)
    except ValueError:
        return "public"
    if ip.is_loopback:
        return "machine"
    if ip.is_link_local or any(ip.version == r.version and ip in r for r in _RESEAUX_PRIVES):
        return "prive"
    return "public"


# Les plages privées, nommées une à une : `is_private` de Python y range aussi les plages de documentation, qui ne sont pas des réseaux privés.
_RESEAUX_PRIVES = [ipaddress.ip_network(r) for r in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7")]


def distribution(os_release: str) -> str:
    """Le nom lisible d'un système, tiré de son /etc/os-release ; '' quand le fichier ne dit rien."""
    m = re.search(r'^PRETTY_NAME=(.*)$', os_release or "", re.M)
    return m.group(1).strip().strip('"\'')[:80] if m else ""


def images(inspects: list) -> dict:
    """{identifiant d'image: {taille_mo, cree}} depuis `docker image inspect`."""
    out = {}
    for im in inspects or []:
        if isinstance(im, dict) and im.get("Id"):
            try:
                taille = round(int(im.get("Size") or 0) / 1048576.0)
            except (TypeError, ValueError):
                taille = 0
            out[im["Id"]] = {"taille_mo": taille, "cree": str(im.get("Created") or "")[:19],
                             "empreintes": sorted({d.rsplit("@", 1)[1] for d in im.get("RepoDigests") or [] if isinstance(d, str) and "@" in d})}
    return out


def reference_image(ref: str):
    """{registre, depot, etiquette} d'une référence d'image, ou None quand elle est épinglée par son empreinte ou désignée par son identifiant (rien à comparer).
    « searxng/searxng » -> le registre de Docker, dépôt searxng/searxng, étiquette latest ; « nginx » -> library/nginx ; « ghcr.io/x/y:1.2 » -> ghcr.io."""
    ref = str(ref or "").strip()
    if not ref or "@" in ref or ref.startswith("sha256:") or re.fullmatch(r"[0-9a-f]{12,64}", ref):
        return None
    tete, _, reste = ref.partition("/")
    if reste and ("." in tete or ":" in tete or tete == "localhost"):
        registre, chemin = tete, reste
    else:
        registre, chemin = "registry-1.docker.io", (ref if "/" in ref else "library/" + ref)
    depot, _, etiquette = chemin.rpartition(":") if ":" in chemin.rsplit("/", 1)[-1] else (chemin, "", "latest")
    if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", depot) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", etiquette):
        return None
    return {"registre": "registry-1.docker.io" if registre in ("docker.io", "index.docker.io") else registre, "depot": depot, "etiquette": etiquette}


def defi_bearer(entete: str) -> dict:
    """{realm, service, scope} du défi « WWW-Authenticate: Bearer … » qu'un registre rend à une lecture anonyme ; {} quand ce n'en est pas un."""
    if not str(entete or "").strip().lower().startswith("bearer "):
        return {}
    return dict(re.findall(r'(\w+)="([^"]*)"', entete))


def etat_maj(empreinte_distante: str, empreintes_locales) -> str:
    """« a_jour », « disponible », ou '' quand on ne sait pas (registre muet, image sans empreinte locale : construite ici, ou jamais tirée d'un registre)."""
    locales = set(empreintes_locales or [])
    if not empreinte_distante or not locales:
        return ""
    return "a_jour" if empreinte_distante in locales else "disponible"


def oom_services(lignes) -> dict:
    """{pid: service} depuis les lignes « oom-kill:… task_memcg=/system.slice/<service>.service … pid=<n> » du noyau : à quel service appartenait le processus tué."""
    out = {}
    for ligne in lignes or []:
        m = re.search(r"task_memcg=(\S*?),.*?\bpid=(\d+)", ligne)
        if m:
            s = re.search(r"/([^/,]+)\.service(?:/|$)", m.group(1))
            out[m.group(2)] = s.group(1) if s else ""
    return out


def conteneurs(inspects: list, images_: dict = None, distributions: dict = None) -> dict:
    """{nom: fiche} depuis `docker inspect` (ou podman). ports : [adresse de la machine, port publié, port interne, protocole, portée]."""
    images_, distributions, out = images_ or {}, distributions or {}, {}
    for c in inspects or []:
        if not isinstance(c, dict):
            continue
        nom = str(c.get("Name") or "").lstrip("/")
        if not nom:
            continue
        etat, hote, reseau_ = c.get("State") or {}, c.get("HostConfig") or {}, c.get("NetworkSettings") or {}
        ports, vus = [], set()
        for interne, pubs in sorted((reseau_.get("Ports") or {}).items()):
            num, _, proto = str(interne).partition("/")
            for p in pubs or []:
                adr = str(p.get("HostIp") or "")
                adr = "0.0.0.0" if adr in ("", "::", "0.0.0.0") else adr                    # la même publication en IPv4 et en IPv6 n'en fait qu'une
                try:
                    cle = (adr, int(p.get("HostPort") or 0), int(num), proto or "tcp")
                except (TypeError, ValueError):
                    continue
                if cle not in vus:
                    vus.add(cle)
                    ports.append(list(cle) + [portee(adr)])
        reseaux = reseau_.get("Networks") or {}
        mode = str(hote.get("NetworkMode") or "")
        mode = "bridge" if mode == "default" else mode
        ip = next((str(v.get("IPAddress")) for v in reseaux.values() if isinstance(v, dict) and v.get("IPAddress")), "")
        volumes = []
        for m in c.get("Mounts") or []:
            source = str(m.get("Name") or m.get("Source") or "")
            if m.get("Type") == "volume" and re.fullmatch(r"[0-9a-f]{64}", source):
                source = "volume anonyme"
            volumes.append([str(m.get("Type") or ""), source[:160], str(m.get("Destination") or "")[:160]])
        etiq = (c.get("Config") or {}).get("Labels") or {}
        compose = ""
        if etiq.get("com.docker.compose.project"):
            fichier = str(etiq.get("com.docker.compose.project.config_files") or etiq.get("com.docker.compose.project.working_dir") or etiq["com.docker.compose.project"]).split(",")[0]
            compose = fichier + (" · service " + str(etiq["com.docker.compose.service"]) if etiq.get("com.docker.compose.service") else "")
        sante = etat.get("Health") or {}
        image_id = str(c.get("Image") or "")
        im = images_.get(image_id) or {}
        try:
            redemarrages = int(c.get("RestartCount") or 0)
        except (TypeError, ValueError):
            redemarrages = 0
        out[nom] = {"ident": str(c.get("Id") or "")[:12], "state": str(etat.get("Status") or ""), "sante": str(sante.get("Status") or "") if isinstance(sante, dict) else "",
                    "demarre": str(etat.get("StartedAt") or "")[:19], "redemarrages": redemarrages, "politique": str((hote.get("RestartPolicy") or {}).get("Name") or "no"),
                    "reseau": mode, "ip": ip, "ports": ports, "volumes": volumes, "compose": compose[:200], "ref": str((c.get("Config") or {}).get("Image") or "")[:200], "image_id": image_id,
                    "taille_mo": im.get("taille_mo") or 0, "created": im.get("cree") or "", "distribution": distributions.get(image_id) or ""}
    return out


# ══ Reverse proxy (nginx) ══════════════════════════════════════════════════════════════════════════════════════════════════════════════

def _jetons(texte: str):
    """Les mots, les accolades et les points-virgules d'une configuration nginx ; les commentaires partent, les guillemets tombent."""
    i, n, mot = 0, len(texte), []
    while i < n:
        c = texte[i]
        if c == "#" and not mot:
            while i < n and texte[i] != "\n":
                i += 1
            continue
        if c in "\"'":
            j = i + 1
            while j < n and texte[j] != c:
                j += 2 if texte[j] == "\\" else 1
            mot.append(texte[i + 1:j])
            i = j + 1
            continue
        if c in "{};" or c.isspace():
            if mot:
                yield "".join(mot)
                mot = []
            if c in "{};":
                yield c
            i += 1
            continue
        mot.append(c)
        i += 1
    if mot:
        yield "".join(mot)


def _arbre(texte: str) -> list:
    """[(mots, bloc ou None)] : une instruction par entrée, ses instructions intérieures quand elle ouvre un bloc."""
    racine, pile, mots = [], [], []
    courant = racine
    for j in _jetons(texte):
        if j == ";":
            if mots:
                courant.append((mots, None))
            mots = []
        elif j == "{":
            bloc = []
            courant.append((mots, bloc))
            pile.append(courant)
            courant, mots = bloc, []
        elif j == "}":
            mots = []
            if pile:
                courant = pile.pop()
        else:
            mots.append(j)
    return racine


def _fichiers_nginx(sortie: str) -> list:
    """[(chemin, texte)] depuis `nginx -T`, dans l'ordre : le premier est la configuration principale."""
    morceaux = re.split(r"^# configuration file (\S+?):\s*$", sortie or "", flags=re.M)
    return [(morceaux[i], morceaux[i + 1]) for i in range(1, len(morceaux) - 1, 2)]


def proxys_nginx(sortie: str) -> list:
    """Chaque renvoi de nginx vers un service local : [{nom, chemin, vers, port, genre, tls}]. `sortie` est celle de `nginx -T`.
    Les inclusions sont suivies (un panneau d'hébergement range les `location` d'un site dans un fichier à part) et les `upstream` résolus."""
    fichiers = _fichiers_nginx(sortie)
    if not fichiers:
        return []
    arbres = {chemin: _arbre(texte) for chemin, texte in fichiers}
    racine = fichiers[0][0].rsplit("/", 1)[0] + "/"

    def developper(noeuds, prof=0):
        out = []
        for mots, bloc in noeuds:
            if mots and mots[0] == "include" and bloc is None:
                motif = mots[1] if len(mots) > 1 else ""
                motif = motif if motif.startswith("/") else racine + motif
                if prof < 8:
                    for chemin in sorted(arbres):
                        if fnmatch.fnmatchcase(chemin, motif):
                            out.extend(developper(arbres[chemin], prof + 1))
            else:
                out.append((mots, developper(bloc, prof) if bloc is not None else None))
        return out

    arbre = developper(arbres[fichiers[0][0]])
    amonts = {}

    def chercher_amonts(noeuds):
        for mots, bloc in noeuds:
            if bloc is None:
                continue
            if mots[:1] == ["upstream"] and len(mots) > 1:
                serveur = next((m[1] for m, b in bloc if b is None and m[:1] == ["server"] and len(m) > 1), "")
                if serveur:
                    amonts[mots[1]] = serveur
            else:
                chercher_amonts(bloc)

    chercher_amonts(arbre)
    lignes, vus = [], set()

    def cible(directive, url):
        m = re.match(r"(?:(\w+)://)?([^/\s]+)", url or "")
        if not m or "$" in m.group(2):
            return None
        schema, hote = (m.group(1) or "http").lower(), amonts.get(m.group(2), m.group(2))
        if hote.startswith("unix:"):
            return None
        port = hote.rsplit(":", 1)[1] if ":" in hote and not hote.endswith("]") else ("443" if schema in ("https", "grpcs") else "80")
        if not port.isdigit():
            return None
        if ":" not in hote or hote.endswith("]"):
            hote = hote + ":" + port
        return hote, int(port), ("grpc" if directive == "grpc_pass" else schema)

    def lire_serveur(bloc):
        noms = [a for mots, b in bloc if b is None and mots[:1] == ["server_name"] for a in mots[1:] if a not in ("_", "--", "")]
        if not noms:
            return
        tls = any(b is None and mots[:1] == ["listen"] and ("ssl" in mots or "quic" in mots) for mots, b in bloc)

        def passer(noeuds, chemin):
            for mots, b in noeuds:
                if b is None and mots[:1] in (["proxy_pass"], ["grpc_pass"]) and len(mots) > 1:
                    c = cible(mots[0], mots[1])
                    if c and (noms[0], chemin, c[0]) not in vus:
                        vus.add((noms[0], chemin, c[0]))
                        lignes.append({"nom": noms[0], "chemin": chemin[:120], "vers": c[0], "port": c[1], "genre": c[2], "tls": 1 if tls else 0})
                elif b is not None and mots[:1] == ["location"]:
                    passer(b, " ".join(mots[1:]) or "/")
                elif b is not None and mots[:1] in (["if"], ["limit_except"]):
                    passer(b, chemin)

        passer(bloc, "/")

    def chercher_serveurs(noeuds):
        for mots, bloc in noeuds:
            if bloc is None:
                continue
            if mots[:1] == ["server"]:
                lire_serveur(bloc)
            else:
                chercher_serveurs(bloc)

    chercher_serveurs(arbre)
    directs = {(l["nom"], l["vers"]) for l in lignes if not l["chemin"].startswith("@")}
    return [l for l in lignes if not (l["chemin"].startswith("@") and (l["nom"], l["vers"]) in directs)]     # un repli nommé (@fallback) qui redit le même renvoi


# ══ Processus et mémoire ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════

SONDE_PS = ["ps", "-eo", "user:32,pid,pcpu,rss,etimes,args", "--no-headers"]


def appartenance(cgroup: str, conteneurs_par_id: dict = None) -> tuple:
    """(genre, nom) de ce qui porte un processus, lu dans son /proc/<pid>/cgroup : un service systemd, un conteneur, une session, le système."""
    chemin = ""
    for ligne in (cgroup or "").splitlines():
        p = ligne.split(":", 2)
        if len(p) == 3 and (p[0] == "0" or "systemd" in p[1] or not chemin):
            chemin = p[2].strip()
            if p[0] == "0" or "systemd" in p[1]:
                break
    m = re.search(r"(?:docker[-/]|libpod-|crio-)([0-9a-f]{12,64})", chemin)
    if m:
        ident = m.group(1)
        for cle, nom in (conteneurs_par_id or {}).items():
            if cle and (ident.startswith(cle) or cle.startswith(ident)):
                return "conteneur", nom
        return "conteneur", ident[:12]
    m = re.search(r"/user-(\d+)\.slice", chemin)
    if m:
        return "session", m.group(1)
    m = re.search(r"/([^/]+)\.service(?:/|$)", chemin)
    if m:
        return "service", m.group(1)
    if chemin.endswith("init.scope"):
        return "système", ""
    return ("noyau", "") if chemin in ("", "/") else ("système", "")


def processus(sortie_ps: str, cgroup_de=None, conteneurs_par_id: dict = None, limite: int = 10) -> list:
    """Les `limite` plus gourmands en processeur et les `limite` plus gourmands en mémoire (réunis, le processeur d'abord), avec leur numéro, leur
    mémoire, leur âge et ce qui les porte. `sortie_ps` est celle de SONDE_PS ; `cgroup_de(pid)` rend le texte de /proc/<pid>/cgroup."""
    tous = []
    for ligne in (sortie_ps or "").splitlines():
        p = ligne.split(None, 5)
        if len(p) < 6 or p[5].startswith("ps -eo user:32"):                                 # la sonde ne se compte pas elle-même
            continue
        try:
            tous.append({"user": p[0], "pid": int(p[1]), "cpu": float(p[2]), "mem_mb": round(int(p[3]) / 1024.0, 1), "age_s": int(p[4]), "command": p[5][:120]})
        except ValueError:
            continue
    choisis = {x["pid"]: x for x in sorted(tous, key=lambda x: -x["cpu"])[:limite]}
    choisis.update({x["pid"]: x for x in sorted(tous, key=lambda x: -x["mem_mb"])[:limite]})
    out = sorted(choisis.values(), key=lambda x: (-x["cpu"], -x["mem_mb"]))
    for x in out:
        x["genre"], x["a_qui"] = appartenance(cgroup_de(x["pid"]) if cgroup_de else "", conteneurs_par_id)
    return out


def memoire(mi: dict) -> dict:
    """La répartition de la mémoire, en Mo, depuis /proc/meminfo (en ko) : ce que tiennent les programmes, le cache que le noyau rend à la demande, le libre."""
    def mo(*cles):
        return round(sum(int(mi.get(c) or 0) for c in cles) / 1024.0)
    if not mi or not mi.get("MemTotal"):
        return {}
    cache = mo("Buffers", "Cached", "SReclaimable")
    return {"total_mo": mo("MemTotal"), "applis_mo": max(mo("MemTotal") - mo("MemFree") - cache, 0), "cache_mo": cache, "libre_mo": mo("MemFree"),
            "disponible_mo": mo("MemAvailable"), "echange_mo": max(mo("SwapTotal") - mo("SwapFree"), 0), "echange_total_mo": mo("SwapTotal")}


# ══ Services ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

PROPRIETES_SERVICE = "Id,LoadState,ActiveState,SubState,UnitFileState,Type,Description,MainPID,MemoryCurrent,CPUUsageNSec,ActiveEnterTimestamp,NRestarts"


def mesures_service(u: dict, precedent: tuple = None, maintenant: float = 0.0) -> dict:
    """Le numéro de processus, la mémoire, le processeur (entre deux passes), le démarrage et les relances d'une unité, depuis `systemctl show`.
    `precedent` = (nanosecondes de processeur, instant) de la passe d'avant ; sans elle, le processeur est inconnu (None), pas zéro."""
    def entier(cle):
        v = str(u.get(cle) or "")
        return int(v) if v.isdigit() else None
    mem, ns = entier("MemoryCurrent"), entier("CPUUsageNSec")
    cpu = None
    if ns is not None and precedent and precedent[0] is not None and maintenant > precedent[1] and ns >= precedent[0]:
        cpu = round((ns - precedent[0]) / 1e9 / (maintenant - precedent[1]) * 100.0, 1)
    quand = str(u.get("ActiveEnterTimestamp") or "").split()
    return {"pid": entier("MainPID") or 0, "memoire_mo": round(mem / 1048576.0, 1) if mem is not None else None, "cpu_pct": cpu, "cpu_ns": ns,
            "depuis": (quand[1] + "T" + quand[2]) if len(quand) >= 3 else "", "redemarrages": entier("NRestarts") or 0}


# ══ Sessions ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

_ACCEPTE = re.compile(r"^(\S+)\s+\S+\s+sshd\[(\d+)\]:\s+Accepted (\S+) for (\S+) from (\S+) port (\d+)(?:\s+ssh2)?(?::\s+(\S+)\s+(SHA256:\S+))?")
METHODES = {"publickey": "clé", "password": "mot de passe", "keyboard-interactive": "mot de passe (interactif)", "hostbased": "machine de confiance"}


def sessions_w(texte: str) -> list:
    """Les lignes de `w -h -i` : [{user, tty, ip, inactivite, commande}]."""
    out = []
    for ligne in (texte or "").splitlines():
        p = ligne.split(None, 7)
        if len(p) >= 8:
            out.append({"user": p[0], "tty": p[1], "ip": "" if p[2] in ("-", ":0") else p[2], "inactivite": p[4], "commande": p[7].strip()[:120]})
    return out


def acceptes(journal: str) -> list:
    """Les connexions SSH réussies, depuis le journal de sshd (format short-iso) : [{quand, pid, methode, user, ip, port, algo, empreinte}]."""
    out = []
    for ligne in (journal or "").splitlines():
        m = _ACCEPTE.match(ligne)
        if m:
            out.append({"quand": m.group(1)[:19], "pid": int(m.group(2)), "methode": m.group(3), "user": m.group(4), "ip": m.group(5), "port": int(m.group(6)),
                        "algo": m.group(7) or "", "empreinte": m.group(8) or ""})
    return out


def cles_connues(sorties_keygen) -> dict:
    """{empreinte: commentaire} depuis les sorties de `ssh-keygen -lf <authorized_keys>`."""
    out = {}
    for sortie in sorties_keygen or []:
        for ligne in (sortie or "").splitlines():
            p = ligne.split()
            if len(p) >= 3 and p[1].startswith("SHA256:"):
                out[p[1]] = " ".join(p[2:-1] if p[-1].startswith("(") else p[2:])[:80]
    return out


def _cle_lisible(a: dict, cles: dict) -> str:
    """« ED25519 « commentaire » » : jamais l'empreinte, qui ne dit rien à personne."""
    if a.get("methode") != "publickey":
        return ""
    com = (cles or {}).get(a.get("empreinte") or "")
    return ((a.get("algo") or "clé") + (" « %s »" % com if com else " (absente des fichiers authorized_keys lus)")).strip()


def enrichir_sessions(sessions: list, w: list, acceptes_: list, cles: dict, refus_par_ip: dict) -> list:
    """Ajoute à chaque session ouverte son terminal, son inactivité, ce qu'elle fait, comment elle s'est identifiée, et ce que l'on sait de son
    adresse (connexions réussies sur la période du journal lu, tentatives refusées dans l'heure). Toutes les lignes portent les mêmes clés."""
    out = []
    for s in sessions or []:
        ip, user = str(s.get("ip") or ""), str(s.get("user") or "")
        ligne_w = next((x for x in w or [] if x["ip"] == ip and x["user"] == user), None) or next((x for x in w or [] if ip and x["ip"] == ip), None) or {}
        de_l_ip = [a for a in acceptes_ or [] if a["ip"] == ip] if ip else []
        dernier = next((a for a in reversed(de_l_ip) if a["user"] == user), None) or (de_l_ip[-1] if de_l_ip and user in ("", "sshd") else None) or {}
        out.append(dict(s, tty=ligne_w.get("tty", ""), inactivite=ligne_w.get("inactivite", ""), commande=ligne_w.get("commande", ""),
                        methode=METHODES.get(dernier.get("methode", ""), dernier.get("methode", "")), cle=_cle_lisible(dernier, cles),
                        connexions_30j=len(de_l_ip), refus_1h=int((refus_par_ip or {}).get(ip, 0))))
    return out


def connexions(acceptes_: list, cles: dict, limite: int = 12) -> list:
    """Les connexions réussies regroupées par (utilisateur, adresse, clé), la plus récente d'abord."""
    groupes = {}
    for a in acceptes_ or []:
        g = groupes.setdefault((a["user"], a["ip"], a["methode"], a["empreinte"]), {"user": a["user"], "ip": a["ip"], "methode": METHODES.get(a["methode"], a["methode"]),
                                                                                    "cle": _cle_lisible(a, cles), "nombre": 0, "premiere": a["quand"], "derniere": a["quand"]})
        g["nombre"] += 1
        g["premiere"], g["derniere"] = min(g["premiere"], a["quand"]), max(g["derniere"], a["quand"])
    return sorted(groupes.values(), key=lambda g: g["derniere"], reverse=True)[:limite]


# ══ La fiche ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def processeur(cpuinfo: str) -> dict:
    """{modele, coeurs, fils, mhz} depuis /proc/cpuinfo ; un champ absent reste vide ou à zéro, rien n'est deviné."""
    modele, mhz, fils, coeurs = "", 0.0, 0, {}
    physique = "0"
    for ligne in (cpuinfo or "").splitlines():
        cle, _, val = ligne.partition(":")
        cle, val = cle.strip(), val.strip()
        if cle == "processor":
            fils += 1
        elif cle in ("model name", "Model", "Hardware") and not modele:
            modele = val[:80]
        elif cle == "cpu MHz" and not mhz:
            try:
                mhz = float(val)
            except ValueError:
                pass
        elif cle == "physical id":
            physique = val
        elif cle == "cpu cores" and val.isdigit():
            coeurs[physique] = int(val)
    return {"modele": modele, "coeurs": sum(coeurs.values()) or fils, "fils": fils, "mhz": round(mhz)}


def politique_entree(iptables_s: str) -> str:
    """« refuser » ou « accepter » : ce que le pare-feu fait d'une connexion entrante qu'aucune règle ne nomme ; '' quand on ne sait pas."""
    m = re.search(r"^-P INPUT (\w+)", iptables_s or "", re.M)
    return "" if not m else ("accepter" if m.group(1) == "ACCEPT" else "refuser")


def maj_auto(periodique: str) -> str:
    """Les mises à jour automatiques d'apt, depuis /etc/apt/apt.conf.d/20auto-upgrades ; '' quand le fichier n'existe pas."""
    if not (periodique or "").strip():
        return ""
    m = re.search(r'Unattended-Upgrade\s+"(\d+)"', periodique)
    if not m or m.group(1) == "0":
        return "désactivées : les correctifs attendent une main"
    return "automatiques, " + ("chaque jour" if m.group(1) == "1" else "tous les %s jours" % m.group(1))


def disques(lsblk: dict) -> list:
    """[[nom, modèle, taille, genre]] des disques entiers, depuis `lsblk -dJ -o NAME,MODEL,SIZE,ROTA,TYPE`."""
    out = []
    for d in (lsblk or {}).get("blockdevices") or []:
        if d.get("type") == "disk":
            out.append([str(d.get("name") or ""), str(d.get("model") or "").strip()[:60], str(d.get("size") or ""), "à plateaux" if d.get("rota") in (True, "1", 1) else "sans plateaux"])
    return out


def version(sortie: str) -> str:
    """Le premier numéro de version d'une sortie de `--version` ; '' quand il n'y en a pas."""
    m = re.search(r"(?<![\w.])v?(\d+\.\d+(?:\.\d+)?)", sortie or "")
    return m.group(1) if m else ""
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : portee, distribution, images, conteneurs, _jetons, _arbre, _fichiers_nginx, proxys_nginx …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : CN_sensorium.py (les lectures), modules/vue/CN_machine.py (la composition), tests/CN_test_sensorium_releves.py
