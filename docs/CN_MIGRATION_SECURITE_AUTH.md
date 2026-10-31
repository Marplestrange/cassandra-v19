# Authentification : note de migration (audit du 31-10-2026, points H4, M2, M3, M4)

Rien ne casse : aucun compte, aucune session ouverte, aucune empreinte existante n'est invalidée par ces changements. Voici ce qui change, point par point.

## H4 — cookie `Secure` et HSTS

- Le cookie de session part désormais **avec `Secure` par défaut** dès que l'écoute n'est pas une boucle locale (`127.0.0.1`, `::1`) ou qu'un proxy de confiance (`CASSANDRA_PROXY`) est devant.
- Forcer : `CASSANDRA_COOKIE_SECURE=1` (ou `oui`). Couper explicitement : `CASSANDRA_COOKIE_SECURE=0` (ou `non`). L'argument `cookie_secure` de `Passerelle` accepte les mêmes mots ; `None` ou `False` = « pas de choix », le défaut sûr s'applique.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` est ajouté quand le cookie est `Secure`, que le proxy est de confiance et que la requête est arrivée avec `X-Forwarded-Proto: https`.
- **À vérifier** : une instance qui écoute hors boucle locale en HTTP simple (test sur un réseau local) ne pourra plus garder sa session dans un navigateur : poser `CASSANDRA_COOKIE_SECURE=0`, ou mettre un TLS devant.

## M2 — coût de scrypt

- Mots de passe : `scrypt n=2**17, r=8, p=1` (OWASP), ~0,5 s et 128 Mo par hachage (`maxmem` levé à 512 Mo : `hashlib` plafonne à 32 Mo sinon).
- Format de l'empreinte : `scrypt$n=131072,r=8,p=1$sel$hash`. L'ancien `scrypt$sel$hash` (n=2**14) reste vérifiable ; il est **réécrit au paramètre courant à la prochaine connexion réussie** du compte (jamais sur un échec). Des paramètres hors bornes (base altérée) sont refusés sans calcul.
- Les codes de secours du second facteur (secrets tirés au hasard, huit vérifications par essai) gardent le coût léger `n=2**14`, stocké dans l'empreinte comme les autres.
- Conséquence : une connexion coûte ~0,5 s de calcul et une rafale de connexions demande de la mémoire (128 Mo chacune) ; le blocage par compte et par adresse (10 échecs en 5 minutes) borne l'abus.

## M3 — sessions

- Nouveau délai d'**inactivité** : 8 h pour un utilisateur, 2 h pour un administrateur (0 = sans délai). La durée maximale (`comptes.session_heures`, 24 h) reste en vigueur. Une session fermée pour inactivité demande de se reconnecter, comme une session expirée.
- **Ressaisie du second facteur** pour les gestes sensibles (capacité à risque `eleve`, ou dont le droit est déclaré `sensible`) quand la session d'un administrateur qui a un second facteur date de plus de 60 minutes (connexion ou dernière ressaisie). La passerelle répond `401` avec `second_facteur`, `reverification`, `methodes` et `invite` ; le client signe puis envoie `POST /api/reverifier {"preuve": {...}}` et redemande le geste. Sans second facteur posé sur le compte, rien ne change.
- Réglages (clés `comptes.…`) : `inactivite_heures`, `inactivite_admin_heures`, `admin_reverif_minutes`. **À déclarer dans `modules/comptes/CN_manifeste.toml`** (hors du périmètre de ce lot) ; en attendant, ils se lisent depuis `Identite.securite` (valeurs de départ ci-dessus) :

```toml
[[reglages]]
id = "inactivite_heures"
libelle = "Délai d'inactivité d'une session, en heures (0 : aucun)"
type = "entier"
defaut = 8
minimum = 0
maximum = 720

[[reglages]]
id = "inactivite_admin_heures"
libelle = "Délai d'inactivité d'une session d'administrateur, en heures (0 : aucun)"
type = "entier"
defaut = 2
minimum = 0
maximum = 720

[[reglages]]
id = "admin_reverif_minutes"
libelle = "Âge d'une session d'administrateur au-delà duquel un geste sensible redemande le second facteur, en minutes (0 : jamais)"
type = "entier"
defaut = 60
minimum = 0
maximum = 1440
```

## M4 — second facteur obligatoire pour les administrateurs

- Réglage d'instance `comptes.admin_second_facteur_obligatoire` (**désactivé par défaut**) et `comptes.admin_second_facteur_grace_jours` (7 par défaut). Même remarque : à déclarer au manifeste ; booléen et entier :

```toml
[[reglages]]
id = "admin_second_facteur_obligatoire"
libelle = "Second facteur obligatoire pour les administrateurs"
type = "booleen"
defaut = false
aide = "Active une période de grâce : les administrateurs sans clé de sécurité sont prévenus à chaque connexion, puis refusés une fois la grâce écoulée."

[[reglages]]
id = "admin_second_facteur_grace_jours"
libelle = "Période de grâce, en jours, après l'activation de l'obligation"
type = "entier"
defaut = 7
minimum = 0
maximum = 90
```

- À l'activation, un administrateur sans second facteur **entre encore** pendant la grâce, et la réponse de `POST /api/connexion` porte `avertissement` (`code`, `jusqu_au`, `message` en clair avec la date). La grâce court de la première connexion qui constate l'obligation ; la couper puis la rallumer la fait repartir.
- La grâce écoulée, la connexion est refusée avec un message clair (qui dit comment lever l'obligation). Garde-fous : rien n'est exigé si aucun module de second facteur n'est branché ; les utilisateurs ordinaires ne sont pas concernés ; une connexion par clé d'accès (qui est elle-même un facteur fort) n'est pas touchée.

## Tests

`tests/CN_test_securite_auth.py` couvre les quatre points (cookie et HSTS, paramètres et réécriture des empreintes, inactivité, ressaisie, obligation et grâce).
