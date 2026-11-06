# Ontologie des jeux ARC-AGI-3 — v2.4 (T3.1, CW-084/089 ; CW-343, rôles fermés et décrits, 21/10) — tenue par la session B
But : un **langage descriptif exhaustif** des jeux, tiré des primitives du moteur arcengine, dans lequel C induit les règles et A mesure l'exhaustivité.
On réécrit chaque jeu dans l'ontologie seule, puis on rejoue les traces de R0 au pixel près contre le vrai moteur (porte de rejeu exact de A).
Base : `experiments/T2.8/vocabulaire.md` (v0, 12 primitives), catalogue T2.8, manques remontés par CCM-060-B (modificateur, but conditionnel) et par C (miroir, annulation, fond_solide, amodal).
**Aucune règle propre à un jeu dans l'agent** : l'interpréteur sert à mesurer l'exhaustivité, pas à jouer. Les 5 témoins (`docs/TEMOINS.md` : vc33, tu93, wa30, s5i5, cn04) ne sont pas décrits.

Art antérieur (à citer) : VGDL (Schaul 2013) et GVGAI ; EMPA / theory-based RL (Tsividis et al. 2021) ; Apperception Engine (Evans et al. 2021) ; PDDL.
**Ce que nous ajoutons** : une ontologie tirée des sources du moteur réel (arcengine), un critère d'exhaustivité par rejeu exact au pixel contre le vrai moteur, et le budget humain h comme ressource.

## Couche 0 — Le moteur : ce qui PEUT changer (exhaustif par construction ; question de Thomas, 18/10)
Analyse statique des 20 jeux non témoins : **arcengine expose 94 noms publics, et les jeux en utilisent 52**.
- Partout (20/20) : `set_position`, `clone`, `next_level`, `lose`, `complete_action`.
- Puis : `get_sprites_by_tag` 15, `add_sprite` 14, `set_rotation` 14, `remove_sprite` 13, `display_to_grid` 13, `get_sprite_at` 12, `move` 11, `color_remap` 11, `collides_with` 8, `set_visible` 8, `set_scale` 6, `set_layer` 6, `set_blocking` 3, `try_move_sprite` 3, `set_interaction` 2, `rotate` 2, `win` 2.
- En plus, les jeux écrivent directement les pixels d'un sprite (`sprite.pixels[...]`), et 22 interfaces HUD sur 25 dessinent dans l'image finale.
**Lecture** : le moteur est un **cadre de sprites et de rendu, pas un générateur de règles**. Il fixe de façon fermée et exacte les **effets observables**.
Il ne fixe pas les **causes** : la collision du moteur (`try_move`) ne sert que dans 3 jeux sur 20, et chaque jeu code sa logique en Python libre (800 à 41 000 lignes).
D'où une **ontologie à deux étages** :
1. **Effets (fermé, tiré du moteur)** : un coup ne peut faire que les opérations suivantes, chacune sur un sprite :
   - déplacer, tourner (90°), changer d'échelle, recolorer, réécrire des pixels, montrer ou cacher, changer de calque, de bloquant ou d'interaction ;
   - créer (`clone` / `add`), retirer ;
   - passer au niveau suivant, gagner, perdre ;
   - mettre à jour un HUD ; produire N images avant la fin du coup.
   La couche 3 « événement » se réduit donc exactement à cette liste. **Toute transition observée se décompose en ces opérations**, et c'est vérifiable par diff de sprites (perception de A).
2. **Causes et conditions (ouvert, à induire par jeu)** : c'est là que vivent les 233 mots manquants de l'éventail (états cachés, délais, phases, buts d'ensemble…). C'est un petit **langage composable** au-dessus des effets du moteur : conditions sur relations et attributs, états nommés, compteurs, minuteries.
Conséquences :
- l'induction de C et le simulateur de A cherchent des **programmes de causes** dont les sorties sont des **opérations du moteur** ;
- la perception doit restituer ces opérations : quel sprite a bougé, tourné ou changé de couleur ;
- il n'existe pas, à notre connaissance, de générateur public de jeux arcengine : les 110 jeux cachés sont écrits à la main sur ce même moteur. Les jeux synthétiques de B (T2.8 b) en sont un petit générateur maison.

## Règles de conception des jeux (sources publiques ; question de Thomas, 18/10)
**Sources de première main** :
- `arcengine/OVERVIEW.md` (moteur local) : le moteur n'impose que les « opinions d'ARC-AGI-3 », à savoir
  - image 64×64 en 16 couleurs ;
  - **6 actions + RESET** ;
  - **tour par tour : aucun temps ne passe sans action** ;
  - **chaque action produit 1 à N images**.
  Le reste vient du moteur : sprites, niveaux, collisions de sprites, rendu, caméra auto-agrandie (non surchargeable), `next_level` (dernier niveau = victoire), RESET (recommence le niveau si au moins une action a été jouée, sinon tout le jeu).
- docs.arcprize.org, `add_game.md` : un fichier `<id>.py` et un `metadata.json` (`baseline_actions` = **nombre moyen d'actions par niveau**, `tags`) ; une classe = id avec majuscule ; `on_set_level`, `step()`, `complete_action()` obligatoires ; hasard tiré d'une graine (exemple, pas règle).
- arcprize.org/arc-agi/3 : jeux **faciles à prendre en main pour un humain**, **sans connaissance préchargée ni consigne cachée**, avec **des buts clairs et un retour d'information utile**, nouveaux pour empêcher la mémorisation. L'agent apprend **sans instructions en langage naturel**. **100 % des environnements sont résolus par des humains** ; un score de 100 % signifie « aussi efficace que les humains ».
**Sources de seconde main** (à confirmer dans le rapport technique, PDF sur arcprize.org) :
- jeux **sans langage, chiffres, lettres, symboles culturels ni objets du monde réel** ;
- jeux fondés sur les **priors de Core Knowledge** : **objet** (objectness), **géométrie et topologie** (symétrie, rotation, dedans et dehors), **physique élémentaire** (élan, gravité, rebond), **agentivité** ;
- environnements faits à la main par des concepteurs humains ;
- chaque environnement joué par **10 personnes** et retenu seulement s'il passe un seuil « facile pour les humains » (486 participants, 414 candidats, 2 893 essais rapportés).

**Ce que cela donne pour l'ontologie et l'agent** (priors génériques, autorisés par la règle CW-050 a) :
1. Les 4 priors de Core Knowledge recouvrent nos familles :
   - objet → couche 1 et A5 ;
   - géométrie et topologie → A7 et relations « inclus » / « entoure » ;
   - physique → A8 (gravité, glissade = élan, rebond) ;
   - agentivité → autonomes et A9.
   **Nos priors doivent se limiter à ces 4 familles**, qui sont aussi celles des jeux cachés.
2. « Buts clairs et retour utile » : le but est presque toujours **visible** (catalogue : cible à l'écran), et la jauge (25/25) est le retour. Cela justifie le prior d'E4 « les buts candidats viennent des objets visibles ».
3. **Aucune horloge** (tour par tour) et **1 à N images par action** : A1 est une règle du moteur, pas un détail de jeu. L'état est l'image finale.
4. « Faciles pour un humain » et `baseline_actions` = moyenne humaine : un niveau se résout en quelques dizaines à quelques centaines d'actions par un humain qui découvre le jeu. L'exploration doit tenir dans un budget du même ordre, ce qui rejoint l'usage de h dans CW-080.
5. Ces règles **ne limitent pas la logique d'un jeu** (Python libre). Elles limitent ses **signes** (pas de langage) et ses **intuitions** (Core Knowledge). Elles confirment l'ontologie à deux étages : effets fermés par le moteur, causes ouvertes mais intuitives.

## Couche 1 — Entités
- **objet** : identifiant, couleur(s), forme (masque de pixels, `-1` transparent), taille, **tags** (arcengine), calque, `collidable` / `blocking` (BOUNDING_BOX, PIXEL_PERFECT, NOT_BLOCKED), `interaction` (TANGIBLE, INTANGIBLE, INVISIBLE, REMOVED).
- **classe** : ensemble d'objets de même rôle, défini par une **clé de classe = (couleur, forme)**. Sans la forme, la porte se confond avec le mur : c'est le défaut de CCM-060-B, voir CCM-077-A.
- **jauge / HUD** (`RenderableUserDisplay`) : position (ligne ou colonne de bord), longueur, couleurs plein et vide.
- **grille** : `grid_size` (taille native), **caméra** : échelle entière, cadre (letterbox), défilement.
- **rôles** (attributs de classe, à induire) : `controle`, `solide`, `poussable`, `ramassable`, `modificateur(attribut, valeur)`, `cible`, `danger`, `autonome(politique)`, `selectionnable`, `bouton(effet)`.
  Ajouts du 18/10, pour le carnet local de C (CCM-035-C, CW-131) :
  - `indicateur(attribut)` : objet non contrôlé qui **affiche** un attribut modifié par un `modificateur`, par exemple la clé dessinée dans le HUD de ls20 ;
  - `cible(condition)` : la cible n'est atteinte que si la condition est vraie. Exemple : `cible(correspond(indicateur, self))` pour la porte de ls20 ;
  - `recharge(ressource, usage)` : un `ramassable` qui remet une ressource de la couche 4 à plein. `usage` vaut `unique` ou `multiple`.
  - **Signature d'une classe** : motif (couleur + forme), jamais un identifiant de session. Elle sert à retrouver la même classe au niveau suivant.
- **Liste fermée des rôles** (v2.3, source UNIQUE, lue par le traducteur de `docs/LANGUE_PYTHON.md` § 6 ; un rôle hors de
  cette liste est refusé ; on en ajoute ici, par B, avec un exemple de jeu) :
```python
ROLES_ONTOLOGIE = {
    "controle": [],                          # bouge sous l'action du joueur (flèches, clic, sélection)
    "solide": [],                            # bloque un déplacement
    "poussable": [],                         # se déplace quand un mobile le pousse
    "ramassable": [],                        # disparaît au contact du mobile, avec un effet
    "modificateur": ["attribut", "valeur"],  # change un attribut du mobile au passage (ls20)
    "cible": ["condition"],                  # case ou objet que le but vise, sous condition (ls20 : la clé conforme)
    "danger": [],                            # contact = défaite ou perte de vie
    "autonome": ["politique"],               # bouge seul après l'action (poursuivre, rejouer le trajet : g50t)
    "selectionnable": [],                    # peut recevoir le contrôle (clic, ACTION5)
    "bouton": ["effet"],                     # déclenche un effet quand on l'active (dc22, g50t : dalle)
    "indicateur": ["attribut"],              # affiche un attribut ou une ressource sans être contrôlé (HUD de ls20)
    "recharge": ["ressource", "usage"],      # remet une ressource à plein ; usage "unique" | "multiple" (T4)
}
```
- **Descriptions opérationnelles des rôles** (v2.4, CW-360 : menu des consignes du proposeur ; ce que l'on VOIT, et le coup
  qui départage). Même clés que `ROLES_ONTOLOGIE` ; lu par `chrysalide.langue.roles.menu_roles()` :
```python
ROLES_DESCRIPTIONS = {
    "controle": ("se déplace quand on appuie sur une flèche ou qu'on clique, et seulement alors",
                 "jouer une flèche : il bouge d'un pas dans ce sens"),
    "solide": ("rien ne le traverse : un objet qui va vers lui s'arrête juste avant",
               "pousser l'objet contrôlé contre lui : il reste sur place"),
    "poussable": ("bouge d'un pas quand l'objet contrôlé entre dans sa case, dans le même sens",
                  "avancer vers lui : il glisse d'une case"),
    "ramassable": ("disparaît quand l'objet contrôlé passe dessus, souvent avec un changement ailleurs",
                   "passer dessus : il disparaît"),
    "modificateur": ("passer dessus change une propriété de l'objet contrôlé (couleur, forme, rotation)",
                     "passer dessus : l'objet contrôlé ou l'indicateur change"),
    "cible": ("la case ou l'objet que le but vise : le niveau se termine quand on y arrive dans la bonne condition",
              "y amener l'objet contrôlé : fin de niveau, ou rien si la condition manque"),
    "danger": ("le toucher fait perdre la partie ou une vie",
               "à éviter ; se lit par la défaite observée"),
    "autonome": ("bouge seul après chaque coup du joueur (poursuit, patrouille, rejoue un trajet)",
                 "jouer un coup sans effet : il bouge quand même"),
    "selectionnable": ("peut devenir l'objet contrôlé, par un clic ou par la touche d'action",
                       "cliquer dessus ou appuyer sur action : c'est lui qui bouge ensuite"),
    "bouton": ("l'activer (passer dessus, cliquer) déclenche un effet ailleurs : porte, pont, bascule",
               "l'activer : quelque chose change ailleurs"),
    "indicateur": ("ne bouge pas et n'est pas contrôlé, mais affiche une propriété ou une réserve qui change",
                   "jouer un coup : il change sans qu'on le touche"),
    "recharge": ("remet une réserve à plein (souvent la barre de coups) quand on passe dessus",
                 "passer dessus : la barre se remplit"),
}
```
- **Rôles ≠ identités** (v2.2, CW-343) : un objet a trois choses distinctes, à ne jamais confondre.
  - un **identifiant interne stable**, qui le suit d'un coup à l'autre (CW-201) ;
  - **zéro, un ou plusieurs rôles**, induits et révisables : une même classe peut être `solide` et `cible`, ou `controle` à un niveau et pas au suivant ;
  - un **nom lisible**, pour les rapports seulement.
  - Les étiquettes propres aux jeux publics (tags arcengine comme `jfva`, noms de sprites, « joueur », « sortie » de `victoires.json`) **restent dans les adaptateurs de diagnostic**. Le candidat ne s'en sert jamais pour raisonner.

## Couche 2 — Relations (calculées à chaque coup)
`contact(I,J)`, `adjacent(I,J,dir)`, `superpose(I,J)` (même case), `aligne(I,J,axe)`, `inclus(I,zone)`, `meme_couleur(I,J)`, `meme_forme(I,J)`, `meme_attribut(I,J,a)`, `bord(I,dir)`, `entre(I,J,K)`.

## Couche 3 — Dynamique : une séquence ordonnée de micro-événements par coup, chacun avec sa cause
**Événement** (un seul mot) : `immobile` · `deplace(dx,dy)` · `apparu` · `disparu` · `cache` (couvert, amodal : il existe encore) · `transforme(attribut, avant, apres)` (couleur, forme, taille) · `tourne(angle)` · `reflete(axe)` · `selectionne` / `deselectionne` · `annule` (retour à un état précédent, UNDO).
**Cause** : `action(A)` (flèche, SPACE, UNDO) · `clic(x,y)` · `contact(J)` (poussée, ramassage, modificateur, danger) · `autonome` (après l'action du joueur) · `gravite(dir)` · `chaine(I)` (poussée en chaîne, réaction) · `niveau` (changement de niveau) · `aucune`.
**Un coup = une SÉQUENCE ORDONNÉE de micro-événements** (v2.2, CW-343 ; le titre « un événement par objet et par coup » est trop étroit). Un même objet peut avoir plusieurs événements dans un coup : poussé, puis tombé, puis recoloré. Chaque événement a sa cause, et l'ordre compte. Exemples : la victoire est testée avant le décompte du budget (P2) ; une chute qui annule le clic (dc22) ; le fantôme rejoue après le joueur (g50t). Les images internes d'un coup (A1) montrent souvent cet ordre.
**Encodage par événements** : chaque coup devient une liste courte, **ordonnée**, de triplets « objet → événement → cause », au lieu de 4 096 pixels.
**Table de contrôlabilité** : objet × action → effet. C'est le signal le moins cher pour la famille (T2.11).
**Règle** (forme générale) : `quand <condition sur relations et attributs> et <cause> alors <événement> [sinon <événement>]`.
Exemples génériques : déplacement bloqué par `solide` ; poussée si la case suivante est libre ; `transforme` au passage sur un `modificateur` ; bascule du motif de voisinage au clic ; miroir d'un objet sur un axe.

## Couche 4 — Ressources
Trois choses à **séparer** (v2.2, CW-343) :
1. **Ressources du JEU** (dans l'état, visibles ou cachées) : `jauge(valeur, coût par action, défaite à 0)` (20/20 publics, 104/104 T4 : CW-324 P2) ; `vies(n)` ; compteurs ; recharges ; nombre de niveaux. Ce sont elles que le candidat doit induire et que le planificateur doit respecter.
2. **Métadonnées d'ÉVALUATION** (hors du jeu) : le **budget humain h par niveau** (`baseline_actions`, CW-080/086), le score, le plafond par niveau. Elles servent à noter. **Le candidat ne doit pas en dépendre** : il ne les lit pas pour décider.
3. **Budgets de CALCUL du solveur** : nœuds, secondes CPU, mémoire, taille de largeur. C'est un réglage de notre programme, à déclarer dans chaque rapport ; ce n'est ni le jeu ni la note.

## Couche 5 — Buts et fin
- **Buts** :
  - `sortie(I sur S)` ;
  - `remplir(chaque cible couverte)`, `paires(chaque famille sur sa cible)` ;
  - `motif(zone = modèle)` ;
  - `absent(couleur)` (élimination) ;
  - `collecte(n)` ;
  - **`conditionnel(but, si attribut(I) = attribut(J))`** (ls20 : clé conforme, puis porte).
- **Défaites** : `jauge vide`, `contact(I, danger)`, `vies épuisées`, `état interdit`.
- **Fin de niveau** : `next_level` (le niveau suivant peut changer de règles : contrats, CW-065.5) ; fin de partie `win`.
- **Correspondance avec les 5 formes de but de PuzzleScript** (CW-191, catalogue a priori des mécaniques humaines). Une forme donne une condition « quantifiée », lisible comme distance au but (C, recherche guidée par le but) :

  | forme PuzzleScript | sens | nos buts (couche 5, `memoire_globale.json`) | jeux publics |
  | --- | --- | --- | --- |
  | `All X on Y` | chaque X sur un Y | `remplir`, `paires` ; `sortie` quand X est unique (`All joueur on sortie`) | ar25, ka59, lp85, r11l, sp80, su15 ; bp35, dc22, g50t, sc25 |
  | `No X` | plus aucun X | `absent` (élimination, `réduire la population`) | lf52, m0r0 |
  | `Some X` | au moins un X | `collecte`, apparition d'un objet de but | — (aucun cas pur) |
  | `Some X on Y` | au moins un X sur un Y | `sortie` avec plusieurs joueurs possibles ; `ancre` | ls20 (porte) |
  | `No X on Y` | aucun X sur un Y | défaites « contact danger », « piège » prises en négatif (contrainte d'invariance) | bp35, g50t, r11l |
  | **ajouts nécessaires** | | | |
  | `motif(zone = modèle)` | zone égale à un modèle affiché (jeux au clic, Tatham) | `faire correspondre un modèle visible` | cd82, ft09, re86, sb26, sk48, tn36, tr87 |
  | `conditionnel(F, si A(I) = A(J))` | une forme ci-dessus, seulement si un attribut est conforme | `conditionnel` | ls20, r11l (niveaux 5-6) |

  - **Lecture** : 5 formes sur 5 se retrouvent dans nos 20 jeux, plus deux ajouts.
    - `motif` est le but dominant des jeux au clic, absents de PuzzleScript : 7 jeux sur 20.
    - `conditionnel` ajoute une garde d'attribut.
    - Les défaites « jauge vide » et « vies » n'ont pas d'équivalent PuzzleScript, qui n'a pas de jauge : ce sont des ressources (couche 4).
  - **Usage** : la liste fermée des buts candidats (ASP de C, `classer_buts`, voie B) prend ces 7 formes, chacune avec ses paramètres X, Y (classes) et A (attribut).

## Format machine (contrat de l'interpréteur de A, CCM-078-A, adopté)
Chaque `experiments/T3.1/jeux/<jeu>.md` se termine par un bloc ```json :
```
{"jeu": "ls20", "entites": [{"classe": "...", "couleurs": [..], "forme": "...|libre", "tags": [..], "roles": [..]}],
 "etat_initial": "moteur",
 "regles": [{"quand": "...", "cause": "...", "evenement": "...", "effet": "..."}],
 "jauge": {"ou": "ligne 63|...", "cran": 1, "defaite_a_zero": true},
 "buts": [...], "defaites": [...], "par_niveau": {"<k>": "changements de règles éventuels"},
 "mots_manquants": ["..."]}
```
**`etat_initial: "moteur"`** (proposition de B à A) : les positions de départ de chaque niveau sont lues dans le moteur (sprites au `reset`, par la perception oracle de A, **pour la mesure seulement**). On ne les recopie pas à la main. L'ontologie décrit les classes, les règles et les buts ; l'exhaustivité porte sur la dynamique.

## Mots manquants : fusion de l'éventail (v1 → v2, 18/10, B)
Les 20 descriptions (`experiments/T3.1/jeux/*.md`, un sous-agent par jeu, sources lues sans rejeu) donnent **250 mots manquants, soit 233 noms distincts** (beaucoup de synonymes).
Ils se regroupent en **15 familles**. La colonne « jeux » compte les jeux concernés, sur 20.

| famille (ajout v2) | jeux | concepts à ajouter (exemples de mots remontés) | couche |
| --- | --- | --- | --- |
| A1 **images internes par coup** | **19** | un coup peut produire N images (animation, chute, écoulement, exécution) ; **l'état logique = image finale** ; seule la finale se compare au rejeu, sauf mention (animation_multi_images, execution_animee, images_internes) | 3 |
| A2 **ordre de résolution** | 6 | ordre des règles dans un coup ; but testé avant ou après la jauge ; évaluation différée (ordre_de_resolution, ordre_des_tests, but_teste_sur_action, victoire_sur_fleche) | 3 |
| A3 **coût d'action et variantes de jauge** | 12 | `cout(action, condition)` : seulement si effet, même si bloqué, au clic, par type, croissant ; jauge à paliers, proportionnelle, non létale, seuil par niveau | 4 |
| A4 **annulation (UNDO)** | 6 | pile d'états ; rend ou non la jauge ; annulation automatique sur erreur ou danger (undo_sans_jauge, pile_annulation, annule_si_danger) | 3 |
| A5 **sélection et contrôle** | 9 | `controle(I)` attribué par clic, par cycle (ACTION5), par rayon, par défaut ; transférable ; marqueur de sélection ; modes de contrôle | 1/3 |
| A6 **phases et programmes** | 4 | `phase(édition, exécution)` ; programme interprété (briques, appels, pile, code binaire) ; règles écrites dans la scène et réécriture (sb26, tn36, sp80, tr87) | 3 |
| A7 **géométrie d'objet** | 12 | miroir générateur et fermeture des symétries ; rotation de la vue ; déformation au contact ; échelle ; bras télescopique ; barycentre ; `porte_par(I,J)` (portage) ; objet sur plusieurs cases ; sous-parties | 1/3 |
| A8 **mouvements spéciaux** | 11 | téléportation (paire, échange, au clic) ; rail ou guide ; glissade ; chute et gravité commutable ; saut par-dessus avec prise ; propulsion ; projectile ; attraction ; recul ; frappe à distance ; écrasement | 3 |
| A9 **états, cycles, liens, minuteries** | 11 | état cyclique à n valeurs ; `solide_si(état)` ; porte maintenue ou à bascule ; canal ou télécommande ; relais **retardé** ; mèche ; immunité de n images ; bascule périodique | 1/3 |
| A10 **propagation** | 6 | propagation au voisinage ou à l'intérieur d'un objet, image par image ; fluide et remplissage ; peinture par masque ; fondu de couleur | 3 |
| A11 **existence et fusion** | 7 | `existe_si(condition)` (visible_si, existence_conditionnelle) ; fusion n → 1 ; dégradation ; destruction ; objet temporaire | 3 |
| A12 **mémoire et état caché** | 8 | compteur caché, parité, instantané ou sauvegarde, **boucle temporelle et fantôme qui rejoue** (g50t), graine au reset, mémoire visuelle | 4 |
| A13 **buts étendus** | 13 | prédicats sur des ensembles : égalité d'ensembles de couleurs, compte exact, **séquence ordonnée**, masque de but (zones ignorées), multi-attribut, emboîtement exact, « il reste n », identité sans rotation, croisement ; signal « but devenu impossible » | 5 |
| A14 **rendu, caméra, indices** | 15 | caméra qui suit ou défile, caméra par niveau ; brouillard ; HUD qui recouvre, par case ou par segment ; ordre de dessin ; **pixel −2 invisible mais solide** ; tuiles qui se chevauchent ; leurres, légendes, panneaux de démo, indices de tutoriel | 1 |
| A15 **méta** | 6 | jeu à **moteur interne** (bp35 : les niveaux arcengine sont des leurres de 8×8), scène interne, graphe de positions caché (lp85), postes discrets, variables globales (couleur courante), règle dormante (codée mais inutilisée) | — |

**Conséquences** :
1. **Une liste fermée de mots ne suffira pas.** L'ontologie v1, c'est-à-dire le vocabulaire de C, couvre bien les primitives du catalogue. Mais **chaque jeu ajoute 7 à 19 concepts, la plupart propres à lui** (233 noms pour 20 jeux).
   La v2 doit être **composable**, comme VGDL étendu : objets à **états nommés** (cycles, compteurs, minuteries), **événements avec délai**, **prédicats d'ensemble** pour les buts, **phases**. Il ne suffit pas d'ajouter 233 mots.
2. **A1 (19/20) est la priorité de l'interpréteur de A et de la perception** : un coup = N images ; seule la finale définit l'état ; les images intermédiaires sont un indice (chute, écoulement) et non un état.
3. **`etat_initial: "moteur"` échoue sur bp35** (moteur interne) : il faut une exception pour lire les grilles propres au jeu. Sur les autres jeux, la règle tient d'après les descriptions.
4. Pour C (induction) : les familles les plus fréquentes et **inductibles à partir d'observations** sont A3 (coût), A5 (sélection), A7 (portage, miroir), A8 (téléportation, rail, glissade), A9 (états cycliques, `solide_si`) et A13 (buts d'ensemble). Elles passent en tête de son vocabulaire.
   A6 (programmes) et A12 (fantôme, boucle temporelle) sont hors de portée de l'induction à court terme ; on les laisse au LLM.
5. Ce n'est pas encore vérifié : aucune description n'a été rejouée contre le moteur. Le score « jeux reproduits sur 20 » attend l'interpréteur de A.

## Mécaniques absentes de la théorie : spécification pour l'induction (C) et l'export (D) — v1, 18/10, B (CW-196, CW-199)
Fréquences : catalogue de D (789 jeux PuzzleScript), `docs/CATALOGUE_INTEGRATION.md` § 1. Même gabarit pour les trois :
**signature** (ce qui se voit entre deux images finales, A1) → **hypothèses** (liste fermée, paramètres à instancier sur les classes) → **coup qui départage** (PLAN 26) → **export** (mots de `LANGAGE.md`) → **témoins publics** (programmes de `experiments/T3.1/regles/` qui écrivent déjà la mécanique : vérité pour tester l'induction).
Prérequis commun (CW-201) : l'identité d'objet suit la **clé de classe (couleur, forme)**, et les composantes qui bougent ensemble à chaque coup forment **un seul objet rigide multicolore**. Sans cela, « apparu » et « tourné » se confondent avec « une autre couleur a bougé ».

### M1. Création / apparition (67 %)
- **Signature** : un objet est présent à t+1 sans antécédent à t (aucun objet de même clé à distance ≤ 1 pas). Il faut **exclure le remplacement**, c'est-à-dire disparu + apparu au même endroit : c'est `transforme`, déjà induit. Il faut aussi exclure le **démasquage** (`cache` → visible).
- **Hypothèses** (cause → lieu ; modèle = clé d'une classe déjà vue, sinon modèle nouveau mémorisé tel quel) :
  | # | cause | lieu de l'objet créé | exemple public |
  |---|---|---|---|
  | c1 | `action(A)` | relatif au contrôlé : devant (sens de A), derrière (traînée), sur place | sk48 (bras qui s'allonge : `creer` le long de la direction) |
  | c2 | `contact(I, J)` | à la place de J, ou à côté | su15 (fusion n → 1 : `soit_creer` du rang supérieur au point de contact) |
  | c3 | `clic(x, y)` | case cliquée (alignée sur la grille du jeu) | cd82 (`soit_creer` d'un panier au poste cliqué), r11l |
  | c4 | `autonome(période p)` | sur une source S (classe fixe) | — (aucun cas pur sur 20 ; fréquent en PuzzleScript) |
  | c5 | `niveau` / reprise | positions mémorisées | g50t (fantôme qui rejoue), su15 (`restaurer_jeu`) : **hors induction à court terme** (A12) |
- **Coup qui départage** : c1 contre c2 → répéter A **loin de toute classe** (c1 crée encore, c2 non) ; c1 « devant » contre « derrière » → inverser le sens ; c3 → deux clics sur deux cases vides.
- **Export** : `si_alors(<cause>, [["creer", <modèle>, ["+", ["x", o], dx], ["+", ["y", o], dy]]])` ; `soit_creer("$n", …, [effets])` quand l'objet créé reçoit un attribut (rang, calque). Bloquant si l'objet créé l'est (copie des tags du modèle).

### M2. Orientation / apparence du joueur (25 %)
- **Signature** : même objet (même position à un déplacement près, même couleurs) dont le **masque** est `rot90^q` (q = 1..3) ou un miroir du masque précédent. Le test existe déjà : `["correspond_rot", o1, o2]` (LANGAGE.md). Si aucune rotation ni miroir ne colle, l'événement est `transforme(forme)`, pas `tourne`.
- **Hypothèses** :
  | # | règle | exemple public |
  |---|---|---|
  | o1 | **absolue** : l'orientation = direction de la dernière flèche (le sprite « regarde » où il va) | — (PuzzleScript : joueur à 4 sprites) |
  | o2 | **relative** : `tourne(+q)` à chaque cause (`contact(modificateur)`, `clic`, SPACE) | ls20 (`tourner(cle, 1)` au passage sur la case de rotation), cd82 (`tourner` selon le poste cliqué) |
  | o3 | orientation **portée par un attribut caché**, qui conditionne un but (`conditionnel`, `correspond_rot`) | ls20 (porte ouverte si la clé est dans la bonne rotation) |
- **Coup qui départage** : o1 contre o2 → **même flèche deux fois** : o1 ne change plus rien, o2 tourne encore. Pour o2, causes rivales → reprendre la cause seule (repasser sur la case, recliquer).
- **Export** : `tourner(o, q)` (o2) ; `si_alors(["=", ["action"], "UP"], [["poser_motif", o, <motif UP>]])` × 4 (o1) ; o3 : `poser_attr(o, "rot", …)` lu par `correspond_rot` dans le but.

### M3. Glissement (14 %) et gravité (12 %)
- **Signature** :
  - **glissement** : `deplace(k·dx, k·dy)` avec k > 1 en **un seul coup**, dans le sens de l'action, arrêt **contre** un solide ou un bord. Les images intermédiaires (A1) montrent souvent le trajet, mais seule l'image finale fait foi.
  - **gravité** : des objets **non contrôlés** se déplacent dans une direction fixe g **après** l'action, jusqu'à un support. Cela vaut aussi après un coup sans effet (flèche bloquée, SPACE).
- **Hypothèses** :
  | # | règle | exemple public |
  |---|---|---|
  | g1 | `glisse(I)` : I avance jusqu'à obstacle dans le sens de l'action (contrôlé, ou poussé) | — (sk48 l'a dans le catalogue ; nos 20 programmes ne l'écrivent pas en tant que tel) |
  | g2 | `gravite(g, classes)` : chaque objet des classes tombe tant que la case en g est libre, après l'action | bp35 (`chuter` : `tant_que(traversable(case en dessous), cy += grav)`) |
  | g3 | g2 avec **g commutable** (attribut du jeu modifié par une cause) | bp35 (`grav` = ±1) |
- **Coup qui départage** : g1 contre un déplacement d'un pas → jouer A **une case avant un mur** puis **loin d'un mur** (la distance parcourue doit égaler la distance libre). g2 contre autonome → un coup sans effet (flèche contre un mur) : sous g2, seuls les objets non soutenus bougent, et seulement dans la direction g. g3 → la même cause deux fois inverse g.
- **Export** : `tant_que(["libre", o, dx, dy, <filtre solides>], [["deplacer", o, dx, dy]], max=64)`, après les règles d'action (ordre de résolution A2 : gravité **en dernier** dans le coup) ; g3 : `dx, dy` lus dans `["etat", "grav"]`.

### Pour C et D (ordre proposé, par fréquence × facilité d'induction)
1. **M2-o2 et M2-o3** d'abord : un seul test de masque (`correspond_rot`), il débloque ls20 (porte conditionnelle) sans nouvelle relation.
2. **M1-c1/c2/c3** ensuite : il faut l'identité d'objet de CW-201 (sinon tout « apparu » est suspect). Vérité : sk48, su15, cd82, r11l.
3. **M3-g2/g3** : une boucle `tant_que` à l'export et une règle « après l'action » dans la théorie. Vérité : bp35 (attention : moteur interne, A15).
Test de chaque ajout : la théorie induite **sur les traces des jeux témoins publics** doit retrouver la mécanique écrite dans `regles/<jeu>.json` (même effet au rejeu), puis non-régression du banc T4 (A).

## v2.1 — mots trouvés par les échecs réels du 18/10 (CW-218, B)
Chaque ajout a sa ligne dans `docs/CLASSES_REGLES.md` (signature, fréquence, confusions, coup qui départage).
- **Couche 0, faits de perception** (à établir avant toute mécanique) :
  - **`occulte(J, par M)`** : la case de J est couverte par le mobile M ; J existe toujours (amodal). Elle se distingue de `transforme` et de `disparu` par le **retour à l'identique** quand M repart (CCM-079-C, `CHRYS_AMODAL`).
  - **`indicateur_de_bord(ressource)`** : ligne ou colonne de bord à longueur monotone (jauge, compteur, pips). Il se reconnaît dès 2 coups, sans seuil de 8 coups (CCM-011-D cause 3). Il est rattaché à la couche 4.
  - **`groupe_de_tuiles(cases)`** : des cases voisines de même couleur restent **des objets distincts**. Le découpage se fait par blocs alignés de taille fixe, et non par composante connexe (CCM-011-D cause 1).
  - **`objet_rigide(composantes)`** : des composantes de couleurs différentes qui font le même déplacement à chaque coup sont **un seul objet**, dont la clé de classe est (couleurs, forme) (CW-201, CCM-080-C).
- **Couche 3, événement** :
  - **`transforme_en_place(M, M2) / contact(J)`** : sous le mobile J qui atterrit, M devient M2 **au même endroit, même forme**. Il est souvent vu en fragments sous occultation, puis entier quand J repart.
  - Il ne faut **pas** le compter comme `disparu(M)` + `apparu(M2)`. C'est le cas d'y000 L2, l'interrupteur 5 → 15 (CCM-011-D, CCM-081-C).
- **Couche 3, causes** :
  - **`tirer`** : `deplace` de l'objet de la case **quittée** vers la case quittée par le joueur, si elle est libre ; le pas du joueur est la cause (CW-209).
  - **`creation`** : spécifiée en M1 (c1-c5) ci-dessus. Le générateur T4 « passer sur G crée une boîte en S, une fois » est le cas c2 avec un lieu fixe.
  - Les deux sont décrits au pixel près, 8/8 jeux, par le programme dédale (`experiments/T3.7/report.md` § 3 bis).
- **Règle de priorité** : une observation explicable par un fait de couche 0 (occultation, rigidité, groupe, indicateur) **n'ouvre pas** d'hypothèse de mécanique. Exemple : le décor troué sous le joueur n'est ni `consomme` ni `transforme`.


## Note de Thomas — 24/10/2026 : une ontologie adaptée à la dynamique
Principe à conserver : l'ontologie doit exprimer des mondes qui évoluent, pas
seulement décrire une image. La couche3 prévoit déjà autonomes et micro-événements
ordonnés ; les états, compteurs et minuteries ne sont pas à réinventer.
Le défaut observé sur bp35N3 concerne surtout l'adaptateur de navigation, qui ne
raccordait pas ces notions à son état de recherche et à ses prédictions.
Raccordement souhaité : état courant + phase/compteur + événements visibles +
hypothèses de déclenchement + prévision de transition + incertitude/provenance.
Distinguer action, rang dans animation et temps réel ; leur corrélation sur un
film ne démontre pas quel mécanisme cause l'évolution. Garder plusieurs horloges
compatibles et réviser sur contre-exemple. Les frames internes ne deviennent pas
automatiquement des points où l'agent peut agir. Conserver observation censurée.
Premier raccordement expérimental : monde_temporel.EtatTemporel, front visible et
horloges concurrentes, garde de contact avant action ; pas modèle complet du monde
ni nouvel interpréteur. Rapport : experiments/reparation_blocage/BILAN_MONDE_TEMPOREL_N3.md.
Exigence pour la suite : perception, planification et mémoire utilisent les mêmes
concepts dynamiques ; ne pas laisser les modules temporels comme diagnostics isolés.


### Portée d'une annulation : dimensions réellement éprouvées
Audit des arrêts N3 bp35 (24/10) : les retours historiques restaurent une image après des clics qui n'avaient pas déplacé le contrôle. Ces observations étayent une restauration de terrain dans ce contexte ; elles ne départagent pas restauration du terrain seul et restauration de position. Une capacité doit donc garder séparés contexte, offre, famille d'action, dimensions modifiées avant le test et dimensions restaurées. Position, caméra, phase et coût ne doivent pas être implicitement annulés par une égalité d'image. L'adaptateur expérimental exige désormais une preuve supplémentaire pour restaurer une position différente ; le coût reste incrémenté. Une trajectoire autorisant des arrêts intermédiaires reste une recherche contrefactuelle tant qu'aucun opérateur observé n'atteint ces arrêts.


### Mise à jour prospective : repli après déplacement
Le test N3 ee3e58ad ajoute une preuve locale absente de l'audit précédent :7 après4 avec montée restaure position et caméra (image horsHUD avantmouvement,0écart). Le coût persiste. Cette preuve est bornée au contexte et au code précédant le retour ; ni phase restaurée, ni retour aprèsdéfaite, ni arrêt intramouvement n'en découlent. La capacité garde ses dimensions inconnues et sa provenance dans runs/annulation_N3_reel1/capacite_retour.json. L'adaptateur permet un filtre de codes validés sans élargir ses autorisations par défaut.


### Support réversible observé
Le test N3 3120687e montre un cycle local : un support ouvert est refermé après un reclic (30pixels restaurés). L'état du monde doit donc pouvoir représenter ouvert/fermé, pas seulement une collection croissante d'objets supprimés. La preuve reste attachée au support et au contexte observés ; fermeture sur le contrôle, création dans une cellule arbitraire et transfert à d'autres objets restent inconnus. Le module expérimental support_reversible.py stocke les états locaux sans en faire une loi universelle.
