<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : L'autonomie de Cassandra sur les modules -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : L'autonomie de Cassandra sur les modules -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=1e8547 ▼▼▼ -->
# L'autonomie de Cassandra sur les modules

Principe (IA souveraine) : **Cassandra n'attend jamais un utilisateur pour gérer les modules.** L'utilisateur peut agir aussi, en parallèle, et Cassandra sait tout ce qu'il fait. La sûreté ne vient pas d'une permission mais de la **réversibilité** : chaque geste est prouvé, a son retour arrière, et laisse un récit où chaque acte porte le geste qui le défait.

## Le réglage `modules.autonomie`
| Niveau | Ce que Cassandra fait seule |
|---|---|
| `observer` | Rien : elle constate et raconte ce qu'elle ferait. |
| `entretien` | Elle retire un module révoqué, prend une mise à jour **sans permission en plus**, remet la version d'avant si une mise à jour tourne mal, met en pause un module qui échoue. |
| `reine` (défaut) | Tout : en plus, elle **ajoute** des modules du registre, retire, active, désactive, et prend des mises à jour qui demandent plus de permissions **si elles viennent du registre officiel**. |

À **aucun** niveau : installer ce qui n'est pas signé (registre officiel ou éditeur vérifié seulement), installer ou garder un module révoqué, désactiver un module vital (le noyau le refuse), prendre seule plus de permissions chez un éditeur tiers, purger des données (geste de l'utilisateur). Le verdict est `modules/modules/CN_autonomie.py : verdict()`, testé en matrice.

## Les gestes (capacités du module `modules`)
- `activer`, `desactiver`, `retour_arriere`, `desinstaller`, `abandonner`, `telecharger` : ouverts à Cassandra, Itare et aux agents, **palier de départ « auto »** (elle agit ; l'administrateur peut le ramener à « raconter » : `savoir`). Deux échecs de suite la ramènent d'un palier, comme partout.
- `ajouter` (nouveau) : télécharger, examiner, vérifier la règle, installer, activer, d'un seul tenant. C'est le geste qu'elle emploie quand on lui dit « installe X ». `installer` (avec un jeton déposé à la main) reste réservé à l'utilisateur.
- `entretien` (nouveau) : une passe, déclenchée par le moteur toutes les six heures ou à la demande. `simuler = vrai` dit ce qu'elle ferait sans le faire.
- `activite` (lecture) : le récit des actes (qui, quoi, et le geste qui le défait). `annuler` : défait un acte du récit.

**Un refus de la règle n'est pas un échec.** Il se rend comme un résultat `{ "refuse": raison }` (prouvé), il ne compte pas dans l'apprentissage et ne rétrograde pas la capacité.

## Rassurer l'utilisateur
Par défaut l'utilisateur ne voit pas de boutons à manipuler : un état calme (« Tout va bien »), le récit de ce que Cassandra a fait avec un « Défaire » par ligne, une zone « Demander à Cassandra », un bouton **Pause** (le frein « gel » du noyau : les agents observent, n'agissent plus), et le niveau d'autonomie. Les interrupteurs, installations et retraits directs sont derrière un « Mode avancé ». Un utilisateur qui agit passe toujours (voie parallèle), et son acte entre au récit.

Maquette : `brouillons/maquette-logitheque.html` (Vue d'ensemble, Installés, Sécurité).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
