<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : courrier — la boîte IMAP de chaque compte -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : courrier -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.2  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : courrier — la boîte IMAP de chaque compte -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.2 empreinte=86cc78 ▼▼▼ -->
# courrier — la boîte IMAP de chaque compte

Porté de la V18 (`_imap_*`, `itare_mail_*`, `mail_*`, `_courrier_*`, ~2 000 lignes lues). Le noyau apprend que **un module est un paquet de son dossier** (`from . import outils`).

## Réglages (PAR COMPTE, secrets chiffrés)
`courrier.imap_hote`, `imap_port`, `imap_chiffre`, `imap_identifiant`, `imap_mot_de_passe` (secret) ; `smtp_hote`, `smtp_port`, `smtp_identifiant`, `smtp_mot_de_passe` (secret), `smtp_expediteur`. Globaux : `jours_gardes` (90), `lot_corps` (25), `delai_s`. Un compte pose sa propre boîte sans droit particulier ; personne n'a la boîte d'un autre, le serveur non plus.

## Ce que fait le module
- **Lire** : état sans toucher au serveur, dossiers (rôles par drapeau du serveur, noms lisibles en UTF-7 modifié), liste paginée avec recherche par le serveur et classement (à traiter / en attente / technique), message (texte + HTML nettoyé), pièces jointes (25 Mo), journal des envois. Ouvrir ne marque pas lu.
- **Gestes réversibles** : drapeaux, déplacer / supprimer (corbeille) / archiver (retrouvés par Message-ID pour le retour, l'UID change de dossier), copier, créer et renommer un dossier, préparer un brouillon.
- **Envoyer** : réservé à un humain ou à son compte (risque élevé, jamais « maître ») ; un agent prépare un brouillon. Un courriel lu ne fait jamais partir un courriel.
- **Passe** (5 min) : dossiers et compteurs, en-têtes neufs (réception + envoyés), texte des 90 derniers jours par lots, disparus du serveur ; événement `courrier.nouveau` par message neuf ; constat « votre boîte ne se lit plus » visible de son seul compte.

## Sécurité
- **HTML par liste blanche** (`CN_outils.py`, html.parser) et non par expressions régulières : ne passe que ce qui est nommé. Aucune image distante sans accord, les pixels espions ne sont jamais chargés, les liens sont durcis et un texte qui affiche un domaine pour mener ailleurs est dénoncé. 40 vecteurs d'attaque dans les bancs.
- Un jeu d'UID n'accepte que des entiers. Une connexion non chiffrée n'est tolérée que vers la boucle locale (pas de mot de passe en clair sur le réseau), en IMAP comme en SMTP.

## Non porté
- **Suppression définitive** (`mail_delete(permanent=True)`) et **suppression d'un dossier avec son contenu** : irréversibles.
- **Envoi avec pièces jointes** (`_mail_joindre`) ; **réponses/relances** (`mail_relance_proposer`), **fil → projet**, **avatars/BIMI/favicons**, **index des médias**, **règles de tri** (`_MAIL_RULE_*`), **mandats d'envoi** : modules suivants.
- **Boîte « du serveur »** (alertes SMTP du serveur lui-même, `cassandra_send_mail`) : relève du canal d'alerte, pas d'une boîte personnelle.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
