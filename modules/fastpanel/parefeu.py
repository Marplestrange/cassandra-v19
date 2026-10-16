"""Le pare-feu du panneau : la validation d'une règle, le calcul du risque de s'enfermer dehors, et la mise en forme. Fonctions pures, testées sans panneau.

Leçons de la V18 gardées :
  - rien n'est envoyé au panneau sans passer par `valider` ;
  - refuser SSH à tous sur une machine sans Tailscale laisserait dehors : refus net ;
  - tout ce qui PEUT fermer (une règle qui refuse, une politique « refuser par défaut », la suppression d'une règle qui ouvrait) est posé À L'ESSAI :
    il se défait seul au bout de deux minutes si l'administrateur ne le garde pas, et sans filet pas de réglage — le réglage est défait aussitôt ;
  - le corps qui RECRÉE une règle est celui que l'API a rendu (de quoi la remettre à l'identique).
"""
from __future__ import annotations

import ipaddress
import re

POLITIQUES = ("ACCEPT", "DROP", "PARTIAL_ACCEPT", "PARTIAL_DROP")
DELAI_ESSAI_S = 120


def valider(data):
    """(corps de la règle pour l'API, erreur)."""
    nom = re.sub(r"\s+", " ", str(data.get("nom") or "")).strip()
    if not nom or len(nom) > 60 or not re.match(r"^[\w .]+$", nom, re.U):
        return None, "nom : 1 à 60 signes, lettres, chiffres, espaces"
    ports = str(data.get("ports") or "").replace(" ", "")
    m = re.match(r"^(\d{1,5})(?:-(\d{1,5}))?$", ports)
    if not m or not (1 <= int(m.group(1)) <= 65535) or (m.group(2) and not (int(m.group(1)) < int(m.group(2)) <= 65535)):
        return None, "ports : un port (443) ou une plage croissante (4500-5500), de 1 à 65535"
    proto = str(data.get("proto") or "TCP").upper()
    sens = str(data.get("sens") or "INPUT").upper()
    pol = str(data.get("politique") or "").upper()
    if proto not in ("TCP", "UDP", "ALL") or sens not in ("INPUT", "OUTPUT") or pol not in POLITIQUES:
        return None, "protocole, sens ou politique hors de la liste"
    sources = []
    for x in re.split(r"[\s,;]+", str(data.get("sources") or "")):
        if not x:
            continue
        try:
            n = ipaddress.ip_network(x, strict=False)
        except ValueError:
            return None, "adresse illisible : %s" % x[:60]
        sources.append(str(n.network_address) if n.prefixlen == n.max_prefixlen else str(n))
    if pol.startswith("PARTIAL") and not sources:
        return None, "« seulement ces adresses » demande au moins une adresse"
    if len(sources) > 50:
        return None, "50 adresses au plus par règle"
    return {"name": nom, "port_range": ports, "proto": proto, "type": sens, "policy": pol, "rules": [{"source": s} for s in (sources if pol.startswith("PARTIAL") else [])]}, ""


def ports_de(r):
    a, _, b = str(r.get("port_range") or "").partition("-")
    try:
        return int(a), int(b or a)
    except ValueError:
        return 0, -1


def couvre(r, port, proto="TCP"):
    a, b = ports_de(r)
    return str(r.get("type") or "INPUT").upper() == "INPUT" and a <= port <= b and str(r.get("proto") or "").upper() in (proto, "ALL")


def risque(corps, regles, politique, ssh=22, tailscale=False, retire=0):
    """(refus, peut_fermer). Refus net : couper SSH à tous sur une machine sans Tailscale. Peut fermer : le changement doit se défaire seul si l'administrateur ne le garde pas."""
    if corps is not None:
        if corps["type"] == "INPUT" and corps["policy"] == "DROP" and couvre(corps, ssh) and not tailscale:
            return "refuser SSH (port %d) à tous sur une machine sans Tailscale vous laisserait dehors ; restreignez-le plutôt à vos adresses" % ssh, True
        return "", corps["policy"] != "ACCEPT"
    r = next((x for x in regles if int(x.get("id") or 0) == int(retire)), None)            # une suppression ferme quand la politique globale refuse et que la règle ouvrait
    return "", bool(r and politique == "DROP" and str(r.get("policy") or "") in ("ACCEPT", "PARTIAL_ACCEPT"))


def politique_refus(pol, regles, ssh=22, tailscale=False):
    """Pourquoi on ne peut pas poser cette politique globale ('' si on peut)."""
    if pol not in ("ACCEPT", "DROP"):
        return "politique : ACCEPT ou DROP"
    if pol == "DROP" and not tailscale and not any(couvre(x, ssh) and str(x.get("policy")) in ("ACCEPT", "PARTIAL_ACCEPT") for x in regles):
        return "sans Tailscale, « refuser par défaut » exige d'abord une règle qui ouvre SSH (port %d)" % ssh
    return ""


def corps_de(r):
    """Le corps qui RECRÉE une règle telle que l'API l'a rendue."""
    return {"name": r.get("name"), "port_range": r.get("port_range"), "proto": r.get("proto"), "type": r.get("type"), "policy": r.get("policy"),
            "rules": [{"source": x.get("source")} for x in (r.get("rules") or []) if x.get("source")]}


def vers_panneau(r):
    """Une règle de l'API, dans les mots de l'écran."""
    return {"id": r.get("id"), "nom": r.get("name") or "", "ports": r.get("port_range") or "", "proto": r.get("proto") or "", "sens": r.get("type") or "",
            "politique": r.get("policy") or "", "action": r.get("action") or "", "sources": ",".join(x.get("source") or "" for x in (r.get("rules") or []))}
