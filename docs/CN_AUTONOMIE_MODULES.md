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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=716b92 ▼▼▼ -->
# L'autonomie de Cassandra sur les modules

Principe (IA souveraine) : **Cassandra n'attend jamais un utilisateur pour gérer les modules.** L'utilisateur peut agir aussi, en parallèle, et Cassandra sait tout ce qu'il fait. La sûreté ne vient pas d'une permission mais de la **réversibilité** : chaque geste est prouvé, a son retour arrière, et laisse un récit où chaque acte porte le geste qui le défait.

## Le réglage `modules.autonomie`
| Niveau | Ce que Cassandra fait seule |
|---|---|
| `observer` | Rien : elle constate et raconte ce qu'elle ferait. |
| `entretien` | Elle retire un module révoqué, prend une mise à jour **sans permission en plus**, remet la version d'avant si une mise à jour tourne mal, met en pause un module qui échoue. |
| `reine` (défaut) | Tout : en plus, elle **ajoute** des modules du registre, retire, active, désactive, et prend des mises à jour qui demandent plus de permissions **si elles viennent du registre officiel**. |

À **aucun** niveau : installer ce qui n'est pas signé (registre officiel ou éditeur vérifié seulement), installer ou garder un module révoqué, désactiver un module vital (le noyau le refuse), prendre seule plus de permissions chez un éditeur tiers, purger des données (geste de l'utilisateur), **toucher à un module verrouillé**. Le verdict est `modules/modules/CN_autonomie.py : verdict()`, testé en matrice.

## Les gestes (capacités du module `modules`)
- `activer`, `desactiver`, `retour_arriere`, `desinstaller`, `abandonner`, `telecharger` : ouverts à Cassandra, Itare et aux agents, **palier de départ « auto »** (elle agit ; l'administrateur peut le ramener à « raconter » : `savoir`). Deux échecs de suite la ramènent d'un palier, comme partout.
- `ajouter` (nouveau) : télécharger, examiner, vérifier la règle, installer, activer, d'un seul tenant. C'est le geste qu'elle emploie quand on lui dit « installe X ». `installer` (avec un jeton déposé à la main) reste réservé à l'utilisateur.
- `entretien` (nouveau) : une passe, déclenchée par le moteur **toutes les heures** ou à la demande. `simuler = vrai` dit ce qu'elle ferait sans le faire ; `forcer = vrai` (le « Maintenant » de l'utilisateur) passe outre la fenêtre.
- `verrouiller` (nouveau, **utilisateur seulement** : Cassandra ne se verrouille ni ne se déverrouille elle-même) : un module verrouillé n'est touché par aucun agent, ni mis à jour, ni mis en pause, ni retiré, même révoqué. La liste est `donnees/modules_verrous.json` ; chaque pose et levée entre au journal.
- `activite` (lecture) : le récit des actes — qui, quoi, **pourquoi** et le geste qui le défait — avec le niveau, la fenêtre, les verrous et l'état du frein « gel ». Le récit n'a **qu'un seul journal** (`donnees/modules_installations.json`, tenu par le cycle) : installations, retours, retraits, activations, désactivations, tous avec leur pourquoi. `annuler` : défait un acte du récit.

## La fenêtre de maintenance (`modules.fenetre`)
`nuit` (02:00–05:00, défaut), `dimanche` (matin), `hors_bureau` (hors lundi–vendredi 08:00–19:00), `tout`. Elle règle QUAND Cassandra applique une mise à jour ou un ajout (heure du serveur) ; une urgence (module révoqué, module qui échoue) ne l'attend pas, et un « Maintenant » de l'utilisateur non plus.

## Le pourquoi
Chaque geste porte son pourquoi : celui que l'acteur a donné (`pourquoi = "…"` accepté par `activer`, `desactiver`, `ajouter`, `retour_arriere`, `desinstaller`), sinon « Geste de l'utilisateur. » ou « Décision de Cassandra. » ; l'entretien écrit la règle appliquée (« révoqué par le registre », « mise à jour sans permission en plus, source officielle »…).

**Un refus de la règle n'est pas un échec.** Il se rend comme un résultat `{ "refuse": raison }` (prouvé), il ne compte pas dans l'apprentissage et ne rétrograde pas la capacité.

## Rassurer l'utilisateur
Par défaut l'utilisateur ne voit pas de boutons à manipuler : un état calme (« Tout va bien »), le récit de ce que Cassandra a fait avec un « Défaire » par ligne, une zone « Demander à Cassandra », un bouton **Pause** (le frein « gel » du noyau, posé par `urgence.geler` : les agents observent, n'agissent plus ; `activite` dit s'il est posé), et le niveau d'autonomie. Les interrupteurs, installations et retraits directs sont derrière un « Mode avancé ». Un utilisateur qui agit passe toujours (voie parallèle), et son acte entre au récit.

Maquette : `docs/maquettes/CN_maquette-logitheque.html` (Vue d'ensemble, Installés, Sécurité).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
