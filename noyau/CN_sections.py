# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les sections
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #c8cff8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les sections : les rubriques où se rangent les modules (page Modules, boutique).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c8cff8 ▼▼▼
"""Les sections : les rubriques où se rangent les modules (page Modules, boutique).

Une section est une DÉCLARATION, pas une entrée de menu :
  - le noyau en déclare un jeu (CN_sections.toml) ;
  - un module peut en apporter de nouvelles avec [[sections]] dans son manifeste ;
  - un module nomme la sienne avec  section = "..."  (ancien nom : famille, toujours lu).
Les règles : on ne redéfinit jamais une section du noyau ; entre deux modules, le premier (par identifiant) l'emporte ;
une section que personne n'a déclarée existe quand même (nom lisible tiré de son identifiant), pour qu'aucun module ne disparaisse.
"""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

CHEMIN_NOYAU = Path(__file__).with_name("CN_sections.toml")
ID = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
ICONE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
ORDRE_MODULE = 500             # une section nouvelle sans ordre : après celles du noyau, avant « Divers »
ORDRE_IMPLICITE = 800          # une section que personne n'a déclarée
REFUSES = "refusés"            # virtuelle : les extensions écartées
ORDRE_REFUSES = 990


@dataclass(frozen=True)
class Section:
    id: str
    libelle: str
    icone: str = ""            # une clé d'icône de l'interface
    icone_trace: str = ""      # ou un tracé de <path> apporté par un module (voir CN_manifeste.trace_valide)
    ordre: int = ORDRE_MODULE
    origine: str = "noyau"     # « noyau », l'identifiant du module qui l'a déclarée, ou « implicite »


def humaniser(ident: str) -> str:
    return ident.replace("_", " ").strip().capitalize() if ident else "Divers"


def noyau(chemin=None) -> dict:
    """Les sections du noyau, par identifiant. Un fichier illisible est une erreur franche : le noyau ne démarre pas avec des rubriques à moitié connues."""
    brut = tomllib.loads(Path(chemin or CHEMIN_NOYAU).read_text(encoding="utf-8"))
    sortie = {}
    for s in brut.get("section", []):
        if not ID.match(str(s.get("id", ""))) or not str(s.get("libelle", "")).strip():
            raise ValueError("section du noyau invalide : %r" % (s,))
        if s["id"] in sortie:
            raise ValueError("section du noyau déclarée deux fois : %s" % s["id"])
        sortie[s["id"]] = Section(s["id"], s["libelle"].strip(), str(s.get("icone", "")), "", int(s.get("ordre", ORDRE_MODULE)), "noyau")
    return sortie


def declarees_par(m) -> list:
    """Les sections qu'un manifeste apporte : ses [[sections]], et l'ancienne déclaration implicite (famille_libelle / famille_icone / famille_icone_trace)."""
    sortie = [Section(d.id, d.libelle, d.icone, d.icone_trace, d.ordre, m.id) for d in getattr(m, "sections", ())]
    ids = {s.id for s in sortie}
    if m.famille and m.famille not in ids and (m.famille_libelle or m.famille_icone or m.famille_icone_trace):
        sortie.append(Section(m.famille, m.famille_libelle.strip() or humaniser(m.famille), m.famille_icone, m.famille_icone_trace, ORDRE_MODULE, m.id))
    return sortie


def resoudre(manifestes, chemin_noyau=None, avec_refuses=False):
    """(sections triées, remarques) : le noyau d'abord, puis ce que les modules déclarent, puis ce que les modules utilisent sans l'avoir déclaré."""
    sections = dict(noyau(chemin_noyau))
    remarques = []
    ms = sorted(manifestes, key=lambda x: x.id)
    for m in ms:
        explicites = {d.id for d in getattr(m, "sections", ())}
        for s in declarees_par(m):
            if s.id in sections:
                if s.id not in explicites:
                    continue               # l'ancienne déclaration implicite (famille_libelle...) : plusieurs modules la répètent, ce n'est pas un conflit
                if sections[s.id].origine == "noyau":
                    remarques.append("%s : la section « %s » est celle du noyau, elle n'est pas redéfinie" % (m.id, s.id))
                elif sections[s.id].origine != m.id:
                    remarques.append("%s : la section « %s » est déjà déclarée par %s" % (m.id, s.id, sections[s.id].origine))
                continue
            sections[s.id] = s
    for m in ms:
        ident = m.famille or "autres"
        if ident not in sections:
            sections[ident] = Section(ident, humaniser(ident), "", "", ORDRE_IMPLICITE, "implicite")
    if avec_refuses:
        sections[REFUSES] = Section(REFUSES, "Refusés", "fam_refuses", "", ORDRE_REFUSES, "noyau")
    return sorted(sections.values(), key=lambda s: (s.ordre, s.libelle.lower(), s.id)), remarques
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Section, humaniser, noyau, declarees_par, resoudre
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
