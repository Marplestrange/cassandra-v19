# Format universel d'un fichier de code

Statut : spécification à valider (17-10-2026). Vient après `docs/NEXUS.md` (ce qu'est le nexus) et sert à `docs/BORNES.md` (l'outil qui le vérifie).
Décision de Drisse : **chaque fichier de code a la même anatomie**, pour que la nature du code (nexus ou évolutif) se lise d'un coup d'œil et se vérifie par programme.

## 1. Les quatre parties, toujours dans cet ordre

1. **En-tête** : identité du fichier (titre, licence, auteur, dépôt, courriel, module, version, zones, rôle, méthode).
2. **Borne CN** (Code Nexus) : le code intouchable, écrit par le dépôt seul. Fermée par **Fin borne CN**.
3. **Borne EC** (Évolution Cassandra) : un **point d'évolution** : la référence du dépôt, remplaçable à l'exécution par une EC. Fermée par **Fin borne EC**. Il peut y en avoir plusieurs (une par point), ou aucune.
4. **Explicatif CN / EC** : en fin de fichier, ce que font les deux zones, comment elles se parlent, ce que l'EC a le droit de changer.

**Règle d'or : aucune ligne de code hors d'une borne.** Un fichier entièrement nexus a une seule borne CN. Un fichier sans point d'évolution n'a pas de borne EC, mais a quand même son explicatif.

## 2. L'en-tête (champs obligatoires)

| Champ | Contenu |
|---|---|
| `TITRE` | nom court et lisible du fichier |
| `LICENCE` | `AGPL-3.0` (celle du dépôt) |
| `AUTEUR` | `Atek Drisse` |
| `GIT` | `github.com/Marplestrange` |
| `MAIL` | `atek.drisse@gmail.com` |
| `MODULE` / `DÉPÔT` | module d'appartenance et sa version dépôt |
| `ZONES` | `CN`, ou `CN + EC (n points : id @contrat, …)` |
| `RÔLE` | **ce que fait** le fichier (1 à 3 lignes) |
| `MÉTHODE` | **comment** il le fait (1 à 3 lignes) |

## 3. Les marqueurs (lisibles par l'outil)

Chaque marqueur est une ligne de commentaire qui contient **exactement** ces mots, pour qu'un programme les retrouve sans ambiguïté :

```
BORNE CN
FIN BORNE CN
BORNE EC point=<identifiant> contrat=@<version>
FIN BORNE EC
EXPLICATIF CN / EC
```

Le préfixe de commentaire dépend du langage : `#` (Python, shell, TOML), `//` (JavaScript), `/* … */` (CSS), `<!-- … -->` (HTML). Un fichier sans commentaires possibles (JSON) reçoit un fichier compagnon `.borne` qui porte la même information.

## 4. Exemple complet (Python) : `modules/vue/composer.py`

```python
# ══════════════════════════════════════════════════════════════════════════════
# TITRE    : Vue d'ensemble : composition du verdict
# LICENCE  : AGPL-3.0
# AUTEUR   : Atek Drisse
# GIT      : github.com/Marplestrange
# MAIL     : atek.drisse@gmail.com
# MODULE   : vue                      DÉPÔT : 0.1.0
# ZONES    : CN + EC (1 point : verdict.composer @1.0)
# RÔLE     : transforme les relevés de toutes les sources en un verdict et des compteurs.
# MÉTHODE  : fonction pure ; une source muette n'est jamais « stable » ; la première panne est citée.
# ══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

# ▼▼▼ BORNE CN : code nexus, intouchable, écrit par le dépôt seul ▼▼▼
def composer_vue(releves):
    """Façade du contrat : valide l'entrée, appelle le point, valide la sortie."""
    return appeler_point("verdict.composer", releves)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ▼▼▼ BORNE EC point=verdict.composer contrat=@1.0 : référence du dépôt, remplaçable par une EC ▼▼▼
SEUIL_TLS_PANNE, SEUIL_TLS_REGARDER = 7, 21

def composer(releves):
    ...                                   # fonction pure : aucune E/S, aucun ctx, aucun état
# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN  : la façade `composer_vue` est la seule entrée publique. Elle garantit le contrat
#       (schéma d'entrée et de sortie, invariants) et sert la référence si l'EC faillit.
# EC  : `composer` calcule le verdict. L'évolution peut en remplacer le corps ; elle ne peut
#       changer ni la signature, ni les invariants (« source muette ≠ stable »), ni importer autre
#       chose que la bibliothèque standard pure.
# LIEN: contrat dans contrats/verdict.composer.json ; corpus doré dans contrats/verdict.composer.corpus.
```

## 5. Ce que vérifie l'outil de bornes (`outils/bornes.py`)

1. L'en-tête est présent et complet ; la licence, l'auteur, le dépôt et le courriel sont ceux du projet.
2. Chaque borne est ouverte puis fermée, sans imbrication ni chevauchement ; aucune ligne de code hors borne.
3. Le champ `ZONES` de l'en-tête correspond aux bornes réellement présentes.
4. Une **borne EC** n'importe que la bibliothèque standard pure et `ec_api`, sans `ctx`, `self`, E/S, horloge ni hasard (voir `docs/NEXUS.md` §3).
5. Chaque `point=` est déclaré dans le manifeste du module, avec son contrat et son corpus ; chaque point déclaré a sa borne.
6. Aucun fichier **intouchable** (`docs/NEXUS.md` §4) ne contient de borne EC.
7. L'**explicatif** existe et nomme la façade CN, chaque point EC et le contrat.
8. **Empreintes** : une empreinte par borne CN et par borne EC, publiées avec la version dépôt (elles alimentent `1.9.0+EC21.a3f9c2`).

## 6. Les EC rangées à part ont le même format

Une EC évoluée, stockée dans `/var/cassandra/ec/<module>/`, est un fichier au **même format universel** : en-tête (avec `ORIGINE : EC21`, l'empreinte du nexus visé, le contrat prouvé), **une seule borne EC**, son explicatif. Aucune borne CN : une EC ne contient jamais de nexus. Le chargeur refuse tout fichier d'EC qui en contient une.

## 7. Mise en place

1. `outils/bornes.py` en **mode audit** : lit les fichiers, signale les écarts au format, ne bloque rien.
2. `outils/entete.py` : génère ou complète l'en-tête et l'explicatif de chaque fichier à partir de l'existant (titre déduit du fichier, rôle repris de l'ancien commentaire) ; les textes sont relus par l'auteur.
3. Application **module par module**, suite de tests verte à chaque pas, en commençant par `vue`.
4. Passage à l'**échec** en intégration continue une fois tout le dépôt conforme.

## 8. Points à trancher

- **Courriel dans chaque fichier** : l'adresse personnelle sera lisible par n'importe qui qui verra le code (dépôt public prévu : AGPL-3.0). Garder `atek.drisse@gmail.com`, ou une adresse dédiée au projet ?
- **Shell, JavaScript, TOML, HTML, CSS** : même anatomie avec leur commentaire ; le `app.js` de l'interface (plus de 35 000 lignes) sera borné par régions, avec le squelette en CN et les vues déclaratives en EC.
- **Fichiers générés** (`index.html`, `app.js` assemblés) : en-tête posé par l'assembleur, pas à la main.
