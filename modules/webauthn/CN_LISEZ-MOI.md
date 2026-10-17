<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : webauthn — la clé de sécurité -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : webauthn -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : webauthn — la clé de sécurité -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=071b03 ▼▼▼ -->
# webauthn — la clé de sécurité

Porté de la V18 (`wa_*`, 570 lignes), lu en entier. Le noyau gagne une prise : un module peut brancher un **second facteur** (`ctx.second_facteur`), que la connexion consulte (`Identite.ouvrir(..., preuve)`), et une capacité publique peut **ouvrir une session** (`ouvre_session` → cookie par la passerelle).

## Fonctionnement
- **Régler d'abord** `webauthn.rp_id` (le domaine de la page de connexion). Sans lui, rien ne s'enregistre ; changer ce domaine rend les clés existantes inutilisables.
- Enregistrer une clé **n'exige rien**. On l'éprouve, puis `exiger` (huit codes de secours rendus une seule fois).
- Connexion avec la clé exigée : `POST /api/connexion {compte, mot_de_passe}` répond 401 `second_facteur` avec une `invite` (défi, identifiants, domaine) ; le navigateur signe puis renvoie la même requête avec `preuve` (assertion, ou `{"secours": code}`).
- Entrée sans mot de passe : `POST /api/public/webauthn.passkey_defi`, puis `webauthn.passkey_ouvrir` (compte déduit de la clé, PIN ou empreinte obligatoires).
- Garde-fous : défi en mémoire, usage unique ; origine = le domaine réglé, en https ; compteur qui recule refusé ; on ne retire pas la dernière clé exigée ; un second facteur défaillant **refuse** l'entrée ; l'entrée par clé d'accès commence au palier « auto » et l'administrateur la coupe en la mettant à « raconter » ; un refus est un résultat, jamais une exception (les échecs de n'importe qui ne doivent pas faire redescendre le palier).

## Non porté / à savoir
- L'interface (JS du navigateur : `navigator.credentials`) relève du chantier interface.
- Seuls ES256 et RS256 sont pris en charge ; pas d'attestation vérifiée (`fmt: none` suffit, comme en V18).
- Les codes de secours sont vérifiés un à un (empreinte salée) : 8 vérifications scrypt par essai, bornées par le blocage des tentatives de l'identité.
- Preuve faite avec un authentificateur logiciel (ES256) ; **pas encore avec une vraie clé matérielle ni un navigateur**.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
