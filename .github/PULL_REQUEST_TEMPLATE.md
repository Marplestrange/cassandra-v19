## Ce que change cette demande, et pourquoi

<!-- Le pourquoi d'abord : le quoi se lit dans le code. -->

## Liste de contrôle

- [ ] Les bancs du module concerné passent (et ceux qu'il touche).
- [ ] `python CN_main.py verifier` ne signale rien de nouveau.
- [ ] Les empreintes sont rescellées : `python outils/CN_entete.py --ecrire`, puis `python outils/CN_bornes.py --sceller`, puis `python -m unittest tests.CN_test_depot_conforme tests.CN_test_eligibilite`.
- [ ] Si un manifeste change : le catalogue est régénéré (`python outils/CN_catalogue_modules.py`).
- [ ] Un geste qui écrit déclare son périmètre, sa preuve et son retour arrière, et a un banc qui les exerce (refus compris).
- [ ] Un module a au moins un droit déclaré ; un menu porte le droit qui l'ouvre.
- [ ] Aucun secret, aucune adresse réelle, aucun nom de domaine personnel (code, bancs, captures, journaux).
- [ ] Une fonction pure qui prétend être un point d'évolution remplit les six conditions de `docs/CN_NEXUS.md` ; sinon elle reste du nexus.
