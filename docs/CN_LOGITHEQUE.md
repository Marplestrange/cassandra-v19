<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : La Logithèque -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : La Logithèque -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=377a5c ▼▼▼ -->
# La Logithèque

Une page (menu de l'avatar, administrateurs) où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux. Elle **remplace** « Modules et Applications » et « App Store » (leurs entrées de menu et l'ancienne page des modules ont disparu ; la page App Store sert encore de « Boutique » dedans). Pour un compte ordinaire : **Mes applications**.

Fichiers : `interface/CN_logitheque.js` (la page : `CASS.pageLogitheque`, `CASS.pageMesApplications`), `interface/CN_disposition.js` (les montages `pageLogitheque`, `pageMesApplications`, et `demander`), `interface/CN_appstore.js` (la Boutique), `interface/CN_modules-ui.js` (le catalogue et les réglages du module). Maquette : `brouillons/maquette-logitheque.html`. Tests : `tests-ui/logitheque.spec.js`, `tests-ui/logitheque-gestes.spec.js`.

## Le principe
Cassandra gère les modules **seule** (voir `docs/CN_AUTONOMIE_MODULES.md`). La page ne demande donc rien à l'utilisateur : elle lui montre ce que Cassandra a fait (le récit, avec le **pourquoi**), lui laisse tout **défaire**, la **mettre en pause**, **verrouiller** un module ou lui **demander** quelque chose. Les gestes directs (interrupteurs, retrait) sont derrière un **Mode avancé**, avec un bandeau, et leur **impact se dit avant** (ce qui s'arrêterait ou s'activerait aussi).

## Les sections
| Section | Ce qu'elle montre | D'où ça vient |
|---|---|---|
| Vue d'ensemble | « Tout va bien », Pause, Demander à Cassandra, le récit, le niveau d'autonomie, ce qu'elle a laissé de côté | `modules.activite`, `modules.entretien` (simuler), `urgence.geler`, réglage `modules.autonomie` |
| Installés | les modules rangés par **section**, filtres, tiroir (aperçu, dépendances, permissions, santé, versions, verrou) | `modules.lister` (avec `sections`), `modules.verrouiller` |
| Mises à jour | ce qui vient, ce qu'elle laisse de côté, la fenêtre de maintenance, « Maintenant » | `modules.registre`, `modules.entretien`, `modules.ajouter`, réglage `modules.fenetre` |
| Boutique | le registre officiel et les archives (page App Store montée dedans) | `CASS.pageAppStore` |
| Sources | le registre officiel (verrouillé, daté), les éditeurs vérifiés, un autre registre | `modules.registre`, réglage `modules.registre_url` |
| Sécurité et confiance | ce qu'elle se refuse, la politique, les révocations, les permissions de chaque module, les verrous | `modules.registre`, réglage `modules.politique_confiance` |
| Santé | chaque module actif, en une passe | `modules.sante` sans module (`sante_tous` : une requête, pas une par module) |
| Journal et versions | le même récit, filtrable | `modules.activite` |
| Développeur | le générateur, la publication | texte |
| Réglages | les réglages du module `modules` (autonomie, fenêtre, confiance, autre registre) | `CASS.modulesUi` |

## L'accueil d'une instance neuve
Sans module non vital actif et sans rien au récit (hors instance de développement), la Vue d'ensemble devient un accueil : les modules vitaux sont « déjà en place », deux **ensembles** (Hébergeur complet, Bureau personnel) se **cumulent**, « Tout installer » les prend tous, un récapitulatif dit le nombre de modules à activer (dépendances comprises), « Mettre en place » les active, « Laisse Cassandra décider » passe la main, « Plus tard » ferme l'accueil.

## Mes applications (compte ordinaire)
Entrée de menu pour le rôle utilisateur. Elle liste les applications que le compte peut voir (`menus.mes_entrees`), chacune avec « Dans mon menu » (`menus.personnaliser_entree`, **pour son compte seulement** : un compte ordinaire ne personnalise que son menu, jamais celui des autres ni celui de tous), « Ouvrir », et une zone pour demander à Cassandra ce qui manque. Aucune gestion, donc rien à casser.

## Ce qui n'y est pas encore
Les notifications (elles naissent des constats de la Proactivité : il faut un détecteur dans le module des modules), le lot de changements en attente avec calcul d'impact global de l'ancienne page (remplacé par l'impact dit avant chaque geste direct), le dossier surveillé et le miroir hors ligne, la fiche détaillée d'un module de la boutique.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
