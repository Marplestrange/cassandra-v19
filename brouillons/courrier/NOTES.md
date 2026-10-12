- **Volume** : Le code de la V18 pour ce module fait ~15 000 lignes. Seul un squelette représentatif est codé dans `module.py` ; j'ai concentré le portage sur l'architecture V19 (`manifeste.toml` strict, schéma complet de la base, moteurs et capacités avec `ctx`).
- **TODO Inter-modules** : Les accès aux boîtes reposaient sur des appels natifs vers le `coffre` (identifiants) et la `ged` (pièces jointes). Conformément aux consignes, ces appels ont été remplacés par des `# TODO(coffre)` et `# TODO(ged)`.
- **Cloisonnement** : La V18 stockait l'utilisateur courant via `threading.local()` (`_MAIL_QUI`). La V19 rend la variable `ctx.compte` disponible nativement dans les capacités et moteurs. J'ai explicité cette transition.
- **Leçons portées** : Les regex critiques pour la sanitisation HTML (pixels invisibles de tracking, scripts, ressources automatiques) sont préservées, documentées avec leurs tickets (B23, B49, B32, LOT 3).
- **Hypothèses** : Les données du carnet d'adresses (`contacts`, `contact_emails`, etc.) font bien partie de ce module, comme stipulé par la liste des fonctions exigées (`mail_contacts_verser` etc). L'ensemble a été unifié sous la DB du module Courrier.

Bancs de brouillon à corriger (marqués skip) : test_etat_boite_vide_renseigne_souci
