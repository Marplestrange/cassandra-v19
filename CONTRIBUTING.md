# Contribuer à Cassandra V19

Merci de votre intérêt. La V19 est faite pour cela : un **module** est un dossier indépendant, avec son manifeste, ses droits, ses tests, et le noyau ne change pas pour
l'accueillir. (La V18, un seul fichier de plus de 150 000 lignes, ne se prête pas aux contributions extérieures : elle reste la version de production.)

Avant de commencer, lisez dans cet ordre : le [`README`](README.md), `docs/CN_MODULES_DEVELOPPEUR.md` (écrire, distribuer et installer un module), `docs/CN_NEXUS.md`
(ce qui est intouchable) et `docs/CN_FORMAT.md` (l'anatomie de chaque fichier).

## Mise en place

Python 3.11 ou plus, et la bibliothèque `cryptography`.

```
python CN_main.py verifier                                        manifestes, isolation, ordre d'installation, capacités à porter
python -m unittest discover -s tests -p "CN_test*.py" -v          la suite complète (longue : lancez les bancs du module concerné d'abord)
python CN_main.py demarrer                                        l'interface sur le port 9000
```

Les données d'essai vont dans `donnees/` (ignoré par git). N'utilisez **jamais** de vraies données : ni adresses, ni noms de domaine, ni mots de passe, ni clés. Les bancs
utilisent des exemples fictifs (`exemple.test`, adresses de documentation).

## Écrire un module

```
python CN_main.py module nouveau mon_module --nom "Mon module" --importance optionnel
```

Cela crée un module valide et activable (manifeste, code, une capacité qui répond, un LISEZ-MOI). Ce qu'on attend ensuite d'un module :

- **Un manifeste** (`CN_manifeste.toml`) : `id`, `nom`, `version`, `noyau_min`, `description`, `importance` (`vital`, `important`, `optionnel`) et, en une phrase, `sans` : ce qui s'arrête sans lui.
- **Au moins un droit** (`[[droits]]`). Un module sans droit est refusé : sans lui, aucun compte ni groupe ne pourrait se voir accorder ou refuser le module.
- **Des capacités honnêtes.** Une capacité qui écrit déclare son `risque`, son `droit`, son `perimetre`, sa `preuve` (comment on relit ce qu'on a fait), son `retour` (comment on le défait),
  ses `paliers` et ses acteurs (`qui`). Pas de preuve ni de retour, pas de capacité : le manifeste est refusé. Dans le code, `ctx.implementer(id, faire, prouver, defaire)`.
- **Des permissions explicites** (`[permissions]`) : stockage, lecture des autres modules, réseau, etc. Ne demandez que ce qui est vrai.
- **Des menus** déclarés dans le manifeste, chacun avec le `droit` qui l'ouvre ; l'arbre est assemblé par le noyau.
- **Des migrations** (`migrations/CN_001_*.sql`) si le module a sa base. Un module peut déclarer une base par société (`stockage_par_societe`).
- **Une écoute qui se déclare** : un module qui écoute l'événement d'un autre doit le `requiert`, sinon il n'est pas branché, sans bruit.
- **Des bancs** (`tests/CN_test_<module>.py`, `unittest`) qui couvrent les droits, les refus, la preuve et le retour arrière, pas seulement le cas qui marche.
- **Pour l'interface** : une scène `CASS.sceneSurMesure.<module>` dans `interface/CN_<module>-ecran.js`, et un essai Playwright dans `tests-ui/` (voir `tests-ui/README.md`).

## Nexus ou évolution ?

Ne mettez dans un point d'évolution que du calcul pur (voir « Deux sortes de code » dans le README). Tout ce qui décide d'un droit, d'un secret, d'un envoi, d'une suppression
ou d'une preuve est du **nexus** : il ne s'optimise pas tout seul.

## Avant de proposer

1. Les bancs de votre module et ceux qu'il touche passent.
2. `python CN_main.py verifier` ne signale rien de nouveau.
3. **Rescellez les empreintes**, sinon le banc de conformité du dépôt échoue :
   ```
   python outils/CN_entete.py --ecrire
   python outils/CN_bornes.py --sceller
   python -m unittest tests.CN_test_depot_conforme tests.CN_test_eligibilite
   ```
4. Aucun secret, aucune adresse réelle, aucun nom de domaine personnel dans le code, les tests, les captures ou les journaux.
5. Un commit par idée, un message qui dit **pourquoi** (en français, comme le reste du dépôt).

## Signaler un défaut ou une idée

Ouvrez un ticket. Pour une faille de sécurité, n'ouvrez pas de ticket public : écrivez en privé, voir [`SECURITY.md`](SECURITY.md).
