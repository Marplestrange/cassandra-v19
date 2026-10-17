# Format universel d'un fichier de code

Statut : spécification à valider (17-10-2026). Vient après `docs/NEXUS.md` (ce qu'est le nexus) et sert à `docs/BORNES.md` (l'outil qui le vérifie).
Décisions de Drisse : **chaque fichier a la même anatomie** ; **le code nexus (CN) et le code évolutif (EC) sont dans des fichiers séparés** ; chaque CN dépend d'un ou plusieurs fichiers EC.

## 1. Un fichier = une zone

Un fichier est **soit CN, soit EC**, jamais les deux. Sa structure, toujours dans cet ordre :

1. **En-tête** : identité du fichier (titre, licence, auteur, dépôt, courriel, module, versions, zone, renvois, rôle, méthode).
2. **Borne** : **BORNE CN … FIN BORNE CN**, ou **BORNE EC … FIN BORNE EC**. Tout le code du fichier est dans cette borne.
3. **Explicatif CN / EC** en fin de fichier : ce que fait le fichier, comment il parle à son vis-à-vis, ce que l'EC a le droit de changer.

**Règle d'or : aucune ligne de code hors de la borne.** Un fichier **CN** peut dépendre de fichiers **EC** (ses points d'évolution) ; un fichier **EC** a toujours un hôte CN.

## 2. L'en-tête (champs obligatoires)

| Champ | Contenu |
|---|---|
| `TITRE` | nom court et lisible |
| `LICENCE` | `AGPL-3.0` (celle du dépôt) |
| `AUTEUR` | `Atek Drisse` |
| `GIT` | `github.com/Marplestrange` |
| `MAIL` | `atek.drisse@gmail.com` |
| `MODULE` | module d'appartenance |
| `ZONE` | `CN` ou `EC` |
| `VERSION CN` | fichier CN : version dépôt + empreinte (ex. `0.1.0 #3d90e1`). Fichier EC : `néant` |
| `VERSION EC` | fichier EC : numéro d'EC + empreinte (ex. `EC8 #7be104`) ; pour la référence du dépôt : `EC0 (référence 0.1.0)`. Fichier CN : `néant` |
| `EC LIÉES` | (fichier CN) la liste des points qu'il appelle et le fichier de leur référence |
| `HÔTE CN` | (fichier EC) le fichier CN qui l'appelle, le point et le contrat (ex. `composer.py · verdict.composer @1.0`) |
| `NEXUS VISÉ` / `CONTRAT PROUVÉ` | (fichier EC évolué) version et empreinte du nexus sur lequel il a été prouvé ; contrat |
| `RÔLE` | **ce que fait** le fichier (1 à 3 lignes) |
| `MÉTHODE` | **comment** il le fait (1 à 3 lignes) |

## 3. Les marqueurs (lisibles par l'outil)

Chaque marqueur est une ligne de commentaire qui contient **exactement** ces mots :

```
BORNE CN version=<dépôt> empreinte=<hash>
FIN BORNE CN
BORNE EC point=<identifiant> contrat=@<version> version=<EC> empreinte=<hash>
FIN BORNE EC
EXPLICATIF CN / EC
```

Les **versions sont dans les marqueurs** : on lit sur la borne quelle version du nexus (`CN`) ou quelle EC (`EC`) elle porte. L'empreinte est calculée par l'outil sur le contenu de la borne ; si elle ne correspond plus, la borne a été modifiée sans mise à jour de sa version : l'outil le signale.

Préfixe de commentaire selon le langage : `#` (Python, shell, TOML), `//` (JavaScript), `/* … */` (CSS), `<!-- … -->` (HTML). Un fichier sans commentaires possibles (JSON) reçoit un fichier compagnon `.borne`.

## 3 bis. Nommage : la zone est dans le nom du fichier

Décision de Drisse : le nom d'un fichier dit sa zone. **Préfixe `CN_` ou `EC_`**, suivi du nom : `CN_composer.py`, `EC_verdict_composer.py`.

- Le soulignement garde un nom Python valide et lisible. La zone se lit d'un coup d'œil dans l'éditeur, dans les listes de fichiers et dans les messages d'erreur (`File EC_composer.py, line 12`).
- `CN_` : code nexus. `EC_` : point d'évolution (la référence du dépôt, ou une EC évoluée).
- **Aucune exception pour les fichiers que nous écrivons** (décision de Drisse : une architecture sans cas particulier, même si le gain est nul, pour qu'aucune erreur ne soit possible). Y compris `manifeste.toml` → `CN_manifeste.toml`, `module.py` → `CN_module.py`, `installer.sh`, `verifier.sh`, `retirer.sh`, les programmes de `commandes/`, `main.py`, `install.sh`, `deploy.sh`, `pousser.sh`, les migrations `.sql`, les tests (`CN_test_*.py`), l'interface (`CN_shell.js`…), `exploitation/*`, les maquettes, et les **documents de projet** (`CN_NEXUS.md`, `CN_FORMAT.md`…). Écrits par le dépôt, ils sont CN ; seuls les fichiers de zone évolutive prennent `EC_`.
- **Seule liste fermée : les noms imposés par un outil extérieur** : `__init__.py` (convention de l'interpréteur Python), `LICENSE`, `README.md`, `.gitignore` (hébergement git, détection de licence), `__pycache__`. La liste est codée dans l'outil de bornes ; la modifier est un changement signé du dépôt.
- **Noms imposés sur la machine cible** (unités systemd, configuration nginx, sudoers, programmes racine de `/usr/libexec/cassandra/`) : le préfixe vaut **pour le dépôt, jamais pour la machine**. Le fichier du dépôt s'appelle `CN_cassandra-noyau.service` ; l'installateur le copie sous son nom réel `cassandra-noyau.service`. La table de correspondance est déclarée (`CN_installation.toml`). Les listes blanches du courtier racine désignent les noms installés : **elles ne changent pas**.
- **EC évoluées** dans le stock : `EC_<point>__<EC>.py`, ex. `EC_verdict_composer__EC8.py` (le double soulignement sépare le point du numéro d'EC).
- Vérification : le préfixe égale le champ `ZONE` de l'en-tête et le dossier ; un fichier sans préfixe, hors de la liste fermée, est une erreur.

## 4. Où vivent les fichiers

```
modules/vue/
  CN_composer.py                       CN   la façade du contrat, appelle le point
  points/EC_verdict_composer.py        EC   la RÉFÉRENCE du dépôt (EC0), écrite par le dépôt
  contrats/CN_verdict_composer.*       CN   schéma, invariants, corpus doré
/var/cassandra/ec/vue/verdict.composer/EC_verdict_composer__EC8.py     EC évoluée, écrite par l'évolution seule
```

Au chargement, le nexus résout un point : **EC en service** (stock) si elle est compatible et saine, sinon **référence** du dépôt. Le dépôt n'écrit jamais dans le stock ; l'évolution n'écrit jamais dans `modules/`.

## 5. Exemple : deux fichiers pour le point `verdict.composer`

**`modules/vue/CN_composer.py`** (CN)

```python
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Vue d'ensemble : façade de la composition du verdict
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : atek.drisse@gmail.com
# MODULE     : vue
# ZONE       : CN
# VERSION CN : 0.1.0  #3d90e1
# VERSION EC : néant
# EC LIÉES   : verdict.composer @1.0 -> points/EC_verdict_composer.py
# RÔLE       : reçoit les relevés des sources, garantit le contrat, rend le verdict.
# MÉTHODE    : valide l'entrée, appelle le point d'évolution, valide la sortie, sert la référence si l'EC faillit.
# ══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

# ▼▼▼ BORNE CN version=0.1.0 empreinte=3d90e1 ▼▼▼
def composer_vue(releves):
    entree = valider_entree("verdict.composer", releves)
    sortie = appeler_point("verdict.composer", entree)
    return valider_sortie("verdict.composer", sortie)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : `composer_vue` est la seule entrée publique ; elle porte le contrat et le filet (référence).
# EC : le calcul vit dans le point `verdict.composer`, remplaçable sans toucher à ce fichier.
```

**`modules/vue/points/EC_verdict_composer.py`** (référence EC0)

```python
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Vue d'ensemble : composition du verdict (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : atek.drisse@gmail.com
# MODULE     : vue
# ZONE       : EC
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.1.0)  #b81c07
# HÔTE CN    : CN_composer.py · verdict.composer @1.0
# RÔLE       : transforme les relevés de toutes les sources en un verdict et des compteurs.
# MÉTHODE    : fonction pure ; une source muette n'est jamais « stable » ; la première panne est citée.
# ══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

# ▼▼▼ BORNE EC point=verdict.composer contrat=@1.0 version=EC0 empreinte=b81c07 ▼▼▼
SEUIL_TLS_PANNE, SEUIL_TLS_REGARDER = 7, 21

def composer(releves):
    ...                      # pure : aucune E/S, aucun ctx, aucun état, ni heure ni hasard
# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : cette fonction est remplaçable par une EC ; elle ne peut changer ni sa signature ni les
#      invariants du contrat (« source muette ≠ stable ») et n'importe que la bibliothèque standard pure.
# CN : appelée uniquement par la façade `composer_vue` (CN_composer.py).
```

## 6. Ce que vérifie l'outil de bornes (`outils/bornes.py`)

1. L'en-tête est complet ; licence, auteur, dépôt et courriel sont ceux du projet.
2. **Un fichier = une zone** : `ZONE` correspond à la borne présente ; aucune ligne de code hors borne ; borne ouverte puis fermée.
   **Nommage** : le préfixe `CN_` / `EC_` du fichier égale `ZONE` et le dossier (sauf la liste fermée des noms imposés de l'extérieur).
3. **Renvois** : chaque point listé dans `EC LIÉES` d'un CN existe comme fichier EC qui le désigne comme `HÔTE CN`, et inversement.
4. Un fichier **EC** n'importe que la bibliothèque standard pure et `ec_api`, sans `ctx`, `self`, E/S, horloge ni hasard (`docs/NEXUS.md` §3).
5. Chaque `point=` est déclaré dans le manifeste du module, avec son contrat et son corpus ; chaque point déclaré a sa référence.
6. Aucun fichier **intouchable** (`docs/NEXUS.md` §4) n'est de zone EC, et aucun fichier EC ne contient de nexus.
7. L'**explicatif** existe et nomme le vis-à-vis (façade ou point) et le contrat.
8. **Versions et empreintes** : chaque borne porte sa version (`CN` : dépôt ; `EC` : numéro d'EC) et son empreinte, recalculée à chaque passage. Une borne dont l'empreinte change sans que la version ne monte est une erreur. Les versions de l'en-tête égalent celles des marqueurs, et la `VERSION CN` égale celle du manifeste. Ces empreintes alimentent `1.9.0+EC21.a3f9c2`.

## 7. Les EC évoluées

Une EC rangée dans `/var/cassandra/ec/<module>/<point>/EC_<point>__EC<n>.py` suit **le même format** : `ZONE : EC`, `VERSION EC : EC21 #…`, `HÔTE CN`, `NEXUS VISÉ`, `CONTRAT PROUVÉ`, une seule borne EC, son explicatif. Le chargeur refuse tout fichier de ce dossier qui contient du nexus, ou dont l'hôte CN ne désigne pas le point.

## 8. Mise en place

0. **Renommage atomique** (avant tout le reste) : l'outil `outils/renommer.py` (a) simule d'abord (liste des `git mv` et des références à réécrire), (b) renomme avec `git mv` et réécrit chaque référence (imports, chemins, manifestes, scripts, documents, motifs de découverte des tests et des migrations), (c) en **un seul commit dédié**, (d) suite verte en local puis rejeu complet sur Amizo (déploiement avec retour automatique) avant de poursuivre. Mesure de l'ampleur au 17-10 : 395 fichiers suivis (157 Python, 54 TOML, 41 SQL, 40 JS, 34 MD, 33 shell) ; les noms les plus référencés (`manifeste.toml`, `module.py`, `installer.sh`) apparaissent dans 27 à 31 fichiers chacun. Réversible par git.
   **Sans exception, la règle est mécanique** : une seule règle (tout fichier suivi, hors de la liste fermée, reçoit `CN_`, ou `EC_` pour une zone évolutive), **idempotente** (un fichier déjà préfixé est sauté), et **vérifiable par simple recherche** : (i) `git ls-files` ne contient plus de nom sans préfixe hors de la liste fermée ; (ii) aucune référence à un ancien nom ne subsiste dans le dépôt. Seuls les **fichiers** sont préfixés, pas les dossiers.
1. `outils/bornes.py` en **mode audit** : lit les fichiers, signale les écarts au format, ne bloque rien.
2. `outils/entete.py` : génère ou complète l'en-tête et l'explicatif de chaque fichier à partir de l'existant ; les textes sont relus par l'auteur.
3. **Extraction** des fonctions pures vers `points/`, module par module, suite de tests verte à chaque pas, en commençant par `vue`.
4. Passage à l'**échec** en intégration continue une fois le dépôt conforme.

## 9. Points à trancher

- **Courriel dans chaque fichier** : l'adresse personnelle sera lisible par quiconque verra le code (dépôt public prévu, AGPL-3.0). Garder `atek.drisse@gmail.com` ou une adresse dédiée au projet ?
- **L'interface** (`app.js`, plus de 35 000 lignes) : le squelette devient des fichiers CN, les vues déclaratives des fichiers EC (descriptions, jamais de script).
- **Fichiers assemblés** (`index.html`, `app.js` générés) : en-tête posé par l'assembleur, pas à la main.
