<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : L'écran « Zones DNS » -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : L'écran « Zones DNS » : ce que montre l'écran du module dns et comment il se comporte -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=166220 ▼▼▼ -->
# L'écran « Zones DNS »

Fichier : `interface/CN_dns-ecran.js` (crochet `CASS.sceneSurMesure.dns`, chargé par l'assembleur). Il remplace la console générique du module `dns`.

- **Bandeau** : l'adresse publique du serveur face à sa référence (et combien d'enregistrements pointent encore sur l'ancienne), les zones par état, la prochaine échéance de domaine.
- **Une carte par zone**, les plus urgentes en tête : adresse à corriger, expiration proche (14 jours, ou le seuil `dns.expire_jours`), dérives, zones jamais relevées.
- **La zone choisie**, en quatre onglets : *Enregistrements* (groupés, comparés à la référence après un relevé), *Dérives* (avec les gestes), *Courrier et sécurité* (MX, SPF, DMARC, DKIM, CAA, www, lus dans le relevé ou la référence), *Historique* des versions de la référence.
- **Pas de réseau à l'ouverture** : l'écran lit `dns.etat` et `dns.reference` (base). Le relevé en direct (`dns.relever_zone`) ne part qu'au clic.
- **Gestes** : `dns.accepter_reference` et `dns.corriger_enregistrement`, toujours après une confirmation sur place. Sans jeton Cloudflare, la correction n'est pas proposée : l'écran dit où la faire.
- **Suivre un domaine** écrit le réglage `dns.domaines` (`reglages.regler`) ; les domaines du panneau d'hébergement sont suivis d'office.

Test : `tests-ui/dns.spec.js` (données simulées : le serveur d'essai n'a ni domaine ni réseau).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description de l'écran -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : interface/CN_dns-ecran.js (l'écran), modules/dns (le module), tests-ui/dns.spec.js (le test) -->
