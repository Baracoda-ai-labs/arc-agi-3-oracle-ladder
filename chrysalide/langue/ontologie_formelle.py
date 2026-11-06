# SPDX-License-Identifier: MIT-0
# ruff: noqa: C408 — contrats écrits en dict(clé=…) : plus lisibles pour un fichier de données déclaratif
"""Ontologie formelle v1 (B, CW-373) en Python DÉCLARATIF : données seulement, aucune exécution de règle ici.
Trois étages (relecture d'Astra, `experiments/defi_llm/astra_noyau/…/RELECTURE_ONTOLOGIE.md`, et mesures de B du 21/10) :
  1. PROTOCOLE universel (référence sémantique GDL) : seul étage imposé à TOUT jeu ; ses contraintes ASP sont vérifiées
     contre les vrais jeux et nos programmes exacts (`experiments/meta_modele/non_contradiction.py`, tests).
  2. MECANISMES : contrats de templates (organisation VGDL) — paramètres, préconditions, effets, phase, fluents écrits,
     contre-exemples connus, coup qui départage. Ils ne s'appliquent qu'une fois choisis et liés par une théorie.
  3. OPTIONS_DOMAINE : ce qui ressemblait à un axiome mais varie selon le jeu (victoire prioritaire, économie, blocage,
     mémoire) ; chaque option a une valeur par défaut DÉCLARÉE et se confirme par l'observation.
Rôles : uniquement ceux de `docs/ONTOLOGIE.md` (`chrysalide.langue.roles`)."""

# 1. PROTOCOLE — mots GDL et contraintes universelles (ASP, notation à pas de temps T)
PROTOCOLE = {
    "mots": {
        "role": "un seul joueur (l'agent)",
        "init": "état du niveau lu dans la 1re observation du niveau (jamais les objets internes du moteur, sauf banc)",
        "true": "fluents de BASE vrais au pas T (positions, attributs, sélection, réserve, mémoire) ; relations dérivées "
                "recalculées, jamais persistées",
        "legal": "actions offertes par le jeu au pas T (flèches, action, clic paramétré par une case, annuler, RESET)",
        "does": "UNE action par pas",
        "next": "fluents de base au pas T+1, calculés par PHASES ordonnées (micro-événements, ONTOLOGIE v2.2)",
        "terminal": "séparés : but candidat atteint ≠ niveau terminé ≠ partie gagnée ≠ défaite",
        "goal": "utilité du joueur ; ne lit JAMAIS le budget humain h (métadonnée d'évaluation)",
    },
    "contraintes": {
        # vérifiée sur les 20 vrais jeux (non_contradiction.py, 21/10) : 0 violation
        "U1_une_action": "1 { does(A,T) : legal(A,T) } 1 :- pas(T), not fini(T).",
        "U2_fin_exclusive": ":- fin_niveau(T), defaite(T).",
        # vérifiée sur les 20 vrais jeux : 0 violation ; ancre d'une INSTANCE rigide dans un repère déclaré
        "U3_une_ancre": ":- pos(O,X1,Y1,T), pos(O,X2,Y2,T), (X1,Y1) != (X2,Y2).",
        # DÉFAITE = axiome (Thomas, CW-382) : terminale pour la tentative, sortie SEULEMENT par RESET (le niveau recommence),
        # tous les coups restent comptés. Les vies sont une OPTION (OPTIONS_DOMAINE['vies']).
        "U5_defaite_terminale": ":- defaite(T), does(A,T2), T2 > T, A != reset, not reset_entre(T,T2).",
        # inertie des seuls fluents de base non modifiés (pas des relations dérivées, pas des objets détruits)
        "U4_inertie_base": "holds(F,T+1) :- holds(F,T), base(F), not modifie(F,T), not detruit(F,T), not change_niveau(T).",
    },
    "retire_de_l_universel": {
        "victoire_prime": "devenue OPTIONS_DOMAINE['victoire_prime'] (vérifiée dans 9 jeux sur 20 seulement)",
        "jauge": "devenue OPTIONS_DOMAINE['economie'] (barème, seuil et recharge varient : CW-324 P2)",
        "solidite": "devenue le mécanisme 'blocage' : violée dans 16 jeux sur 20 au drapeau bloquant du moteur",
        "image_finale": "faux dès qu'une mémoire ou un état caché agit : l'image est une PROJECTION de l'état",
    },
}

# 2. MÉCANISMES — contrats de templates ; « phase » = ordre dans le pas ; « test » = coup qui départage
MECANISMES = {
    "deplacement": dict(roles=["controle"], params=["dx", "dy"], pre="action flèche ; objet contrôlé ; case visée libre "
                        "pour le mécanisme 'blocage'", effets="ancre += (dx, dy)", phase=1, ecrit=["pos"],
                        contre_exemples=["flèche sans effet contre un mur", "objet sélectionné autre que l'attendu"],
                        test="jouer une flèche loin de tout obstacle : un seul objet bouge d'un pas"),
    "blocage": dict(roles=["solide"], params=["mobile", "obstacle", "mode", "etat"], pre="mobile en mouvement vers "
                    "l'empreinte de l'obstacle", effets="le mouvement n'a pas lieu (ou s'arrête avant)", phase=1,
                    ecrit=["pos"], contre_exemples=["fantôme qui traverse", "porte qui se referme sur le joueur",
                                                    "glissement qui traverse une barre (ka59 c15)"],
                    test="pousser le contrôlé contre lui : il reste sur place"),
    "poussee": dict(roles=["poussable"], params=["chaine"], pre="le contrôlé entre dans l'empreinte du poussable ; case "
                    "suivante libre", effets="le poussable avance d'un pas, puis le contrôlé", phase=1, ecrit=["pos"],
                    contre_exemples=["poussable contre un solide : aucun ne bouge"], test="avancer vers lui"),
    "glissement": dict(roles=["poussable", "controle"], params=["jusqu_a", "traverse"], pre="mouvement commencé",
                       effets="avance jusqu'au premier obstacle, en un seul coup réel ; `traverse` = classes qu'il "
                       "franchit et que la MARCHE ne franchit pas (ka59, CW-375 : le blocage dépend du mode)", phase=1,
                       ecrit=["pos"], contre_exemples=["arrêt après un pas (pas de glissement)",
                                                       "supposer que glissement et marche ont les mêmes obstacles"],
                       test="faire glisser vers une classe qui arrête la marche : il la traverse-t-il ?"),
    "prolongation": dict(roles=["poussable", "controle"], params=["surface"], pre="mouvement qui laisserait une surface "
                         "occupée (ka59, CW-375)", effets="le mouvement se prolonge jusqu'à dégager la surface", phase=1,
                         ecrit=["pos"], contre_exemples=["arrêt exactement au pas demandé"],
                         test="pousser d'un pas au bord d'une surface : finit-il au-delà de la surface ?"),
    "ramassage": dict(roles=["ramassable"], params=["effet"], pre="le contrôlé couvre son empreinte",
                      effets="il disparaît ; effet éventuel ailleurs", phase=2, ecrit=["present"],
                      contre_exemples=[], test="passer dessus"),
    "transformation": dict(roles=["modificateur"], params=["attribut", "valeur"], pre="contact avec le modificateur",
                           effets="attribut du contrôlé (ou de l'indicateur) ← valeur", phase=2, ecrit=["attr"],
                           contre_exemples=[], test="passer dessus : couleur, forme ou rotation change"),
    "selection_clic": dict(roles=["selectionnable"], params=[], pre="clic sur l'empreinte d'un sélectionnable",
                           effets="il devient l'objet contrôlé ; marqueur déplacé", phase=0, ecrit=["selection"],
                           contre_exemples=["re-cliquer la même pièce efface le marqueur trop tôt (export, Astra)"],
                           test="cliquer l'autre objet, jouer une flèche : c'est lui qui bouge"),
    "bouton": dict(roles=["bouton"], params=["effet", "tenue"], pre="activation (passage, clic, occupation)",
                   effets="effet ailleurs ; si tenue : seulement tant qu'il est occupé (porte tenue, g50t)", phase=3,
                   ecrit=["attr", "present"], contre_exemples=["porte qui se referme dès que la dalle se libère"],
                   test="l'activer puis s'en écarter : l'effet reste-t-il ?"),
    "autonome": dict(roles=["autonome"], params=["politique"], pre="après l'action du joueur",
                     effets="il bouge selon sa politique (poursuite, patrouille, rejeu du trajet mémorisé)", phase=4,
                     ecrit=["pos", "memoire"], contre_exemples=[], test="jouer un coup sans effet : il bouge quand même"),
    "teleportation": dict(roles=[], params=["sortie"], pre="entrée dans un portail", effets="ancre ← sortie", phase=2,
                          ecrit=["pos"], contre_exemples=[], test="entrer dans le portail"),
    "creation": dict(roles=[], params=["modele", "lieu"], pre="déclencheur observé", effets="nouvel objet", phase=3,
                     ecrit=["present"], contre_exemples=[], test="refaire le déclencheur : un objet apparaît"),
}

# 2 ter. ÉCONOMIE (Thomas, CW-381 : oubliée en v0 et chez Astra, où la réserve était « fournie par l'appelant »)
# Fluents : réserve (jauge de coups), compteurs, vies. Mesuré : 20/20 publics et 104/104 T4 ont une réserve (CW-324 P2,
# `experiments/meta_modele/audit.md`, `budget_reel.py` : 343/367 défaites au bon coup) ; barème, seuil et recharge VARIENT.
ECONOMIE = {
    # correspondance avec l'encodage ASP de F (`economie.lp`, CCM-029-F) : une seule source de noms
    "asp": {"reserve": "reserve(R, T)", "cout_action": "cout(A, C)", "recharge": "recharge(N, T)",
            "defaite_epuisement": "seuil(S), perdu/1", "ordre_victoire_epuisement": "fait epuisement_d_abord. (défaut : "
            "victoire d'abord)", "perception_jauge": "economie_plan.reserve_niveau"},
    "fluents": {"reserve": "réserve de coups du niveau (jauge) ; remise au plein au début du niveau et à RESET",
                "compteur": "valeur cachée ou affichée qui change avec les actions (lf52 : compteur caché)",
                "vies": "nombre de tentatives restantes (OPTION : ls20, r11l, sp80)"},
    "cout_action": dict(params=["action", "contexte", "cout"], pre="action jouée", effets="reserve -= cout(action, "
                        "contexte)", phase=5, ecrit=["reserve"],
                        contre_exemples=["action gratuite : clic hors plateau (su15), mouvement contre un mur (ar25)",
                                         "coût ≠ 1 : chute −20 (dc22), fusion interdite 2 + 2 × pénalité (su15)"],
                        test="jouer une même action sans effet jusqu'à la défaite : compter les coups (budget_reel)"),
    "recharge": dict(params=["source", "valeur", "usage"], pre="contact avec une recharge (rôle `recharge`) ou "
                     "changement de niveau", effets="reserve ← valeur (ou += valeur)", phase=5, ecrit=["reserve"],
                     contre_exemples=["sc25 : +10 au ramassage (min 0)", "T4 : remise à G, une fois par case"],
                     test="passer sur la recharge : la barre se remplit"),
    "defaite_epuisement": dict(params=["seuil"], pre="reserve <= seuil après le décompte", effets="defaite",
                               phase=6, ecrit=["issue"],
                               contre_exemples=["sc25 perd à used > slfh", "m0r0 à la 151e action"],
                               test="épuiser la réserve : défaite au coup mesuré"),
    "ordre_victoire_epuisement": dict(params=["victoire_d_abord"], pre="coup gagnant qui épuise la réserve",
                                      effets="victoire si victoire_d_abord, sinon défaite", phase=6, ecrit=["issue"],
                                      contre_exemples=[], test="gagner au dernier coup de la réserve",
                                      mesure="victoire d'abord vérifiée dans 9 jeux sur 20 (audit CW-321)"),
    "perception_jauge": dict(regle="la jauge DESSINÉE (barre au bord, compteur) se lit par la perception "
                             "(`economie.classer` de D, réserve lue par F) ; aucun compteur visible ne devient "
                             "automatiquement une jauge sans le test", test="jouer un coup compté : la barre recule-t-elle "
                             "d'un cran ?"),
}

# 2 bis. RÈGLES DE PERCEPTION (CW-375, ka59 N4 gagné par Astra : « la première divergence peut ne pas être une loi »)
# Ce que l'on voit n'est pas l'état : une divergence d'image s'explique d'abord par ces règles AVANT d'écrire une loi.
PERCEPTION = {
    "indice_de_rendu": dict(regle="l'indice de rendu (ordre de dessin, calque) n'est PAS la géométrie : un objet dessiné "
                            "par-dessus n'est pas « sur » l'autre au sens du mécanisme", test="déplacer l'objet du "
                            "dessus : l'autre est-il entier dessous ?", ecrit=[],
                            mesure="non vu dans les traces de Franzen (E) : se découvre en EXPÉRIMENTANT"),
    "sol_sous_occultant": dict(regle="sous un objet qui occulte, le sol continue (complétion amodale) : une case cachée "
                               "garde sa dernière valeur observée, elle n'est pas vide", test="déplacer l'occultant : le "
                               "sol réapparaît-il identique ?", ecrit=[],
                               mesure="candidat dans 12 jeux publics sur 20 (E, CCM-066-E, détecteur non confirmé) : "
                               "la seule des 4 leçons de ka59 qui se voit dans les traces de Franzen"),
}

# 3. OPTIONS DE DOMAINE — défaut DÉCLARÉ, à confirmer par jeu (statut LANGUE_PYTHON § 7)
OPTIONS_DOMAINE = {
    "victoire_prime": dict(defaut=True, mesure="victoire testée avant le décompte : 9 jeux sur 20 (audit CW-321)",
                           asp="perdu(T) :- defaite_brute(T), not gagne(T)."),
    "economie": dict(defaut=None, params=["cout(action, contexte)", "seuil", "recharge", "ordre_victoire"],
                     mesure="20/20 publics et 104/104 T4 ont une réserve ; barème, seuil et recharge varient (P2)",
                     asp="perdu(T) :- reserve(R,T), seuil(S), R <= S, not gagne(T)."),
    "vies": dict(defaut=False, params=["nombre", "affichage", "cause_perte", "effet_apres_perte", "recharges"],
                 mesure="ls20, r11l (5 contacts), sp80 (4 versements ratés) ; la DÉFAITE finale reste l'axiome U5",
                 asp="defaite(T) :- vies(0,T)."),
    "memoire": dict(defaut=False, mesure="trajet mémorisé (g50t), état caché : l'image ne suffit pas",
                    asp="holds(memoire(M),T+1) :- holds(memoire(M),T), not efface_memoire(T)."),
    "minuteur": dict(defaut=False, mesure="bp35 (plafond toutes les 2 actions), ka59 (bombes)",
                     asp="avance(minuteur,T) :- does(_,T)."),
}


# ===================== FUSION v1 (B, 22/10 7 h, CW-382 / CW-386 / CW-388) =====================
# Apports de l'agent cloud (`experiments/defi_llm/agent_cloud/livraison_boucle/ONTOLOGIE_V1.md`, éprouvé sur ka59 N1-N5)
# et de la couche 6 (`experiments/defi_llm/couche6/strategies/`). Comparaison : `experiments/meta_modele/fusion_ontologie_v1.md`.
# À confirmer par Cowork : les deux contradictions sont tranchées ici selon la PROPOSITION de B (marquées « proposition B »).

# Phases de `next` (agent cloud) : un contrat déclare sa phase ; plusieurs contrats d'une même phase s'appliquent dans
# l'ordre de la théorie. Le rendu (9-10) n'écrit AUCUN fluent : c'est la projection.
# CCM-078-G (24/10) : la table de l'agent cloud (1 clic, 2 mouvement, 4 économie) ne suivait pas la numérotation
# des contrats (MECANISMES, ECONOMIE). Unifiée sur celle des contrats ; aucun code ne lisait ce champ (l'ordre
# d'exécution vient du champ « phase » des lois du langage, distinct).
PHASES = {0: "scène et sélection (complétion, clic, marqueur)", 1: "mouvement (déplacement, blocage, poussée, "
          "glissement, prolongation)", 2: "interaction au contact (ramassage, transformation, téléportation)",
          3: "déclencheurs et horloge (bouton, création, piston, fantôme, porte tenue)",
          4: "autonomes à politique (poursuite, patrouille)", 5: "économie (coût, recharge)",
          6: "issue (défaite à l'épuisement, ordre victoire/épuisement)", 9: "rendu : trou", 10: "rendu : indices"}

# État latent (agent cloud) : ce que l'image ne montre pas (ou pas entièrement) ; reconstruit par rejeu des actions
ETAT_LATENT = {"sel": "instance sélectionnée", "porte": "passager vivant d'une instance (trou)",
               "t": "horloge du niveau, modulo le PPCM des périodes autonomes", "memoire": "trajet borné (fantôme)",
               "reserve": "jauge (ECONOMIE)"}

# Contrats ajoutés (agent cloud) — même forme que MECANISMES
MECANISMES.update({
    "piston": dict(roles=["autonome"], params=["direction", "periode", "phase0", "charge", "base", "portee", "pas"],
                   pre="horloge t", effets="charge k = (phase0 + t) mod periode ; à k = periode, la zone de `portee` "
                   "devant pousse les instances jusqu'à la dégager", phase=3, ecrit=["pos"],
                   contre_exemples=["apparence cyclique imprévue (écart AUTONOME)"],
                   test="attendre (coups sans effet) : l'apparence revient-elle avec une période ?"),
    "memoire_fantome": dict(roles=["autonome"], params=["pilote", "declencheur", "retour", "longueur"],
                            pre="action déclencheur (ESPACE)", effets="le pilote revient au départ ; un fantôme "
                            "rejoue le trajet mémorisé", phase=3, ecrit=["pos", "memoire"],
                            contre_exemples=["fantôme absent ou décalé d'un coup"],
                            test="marcher, déclencher : un fantôme refait-il le même trajet ?"),
})

# Projection image (agent cloud) — n'écrit aucun fluent ; complète PERCEPTION (B)
PROJECTION = {
    "trou": dict(params=["classe", "sel", "passager", "vide"], phase=9,
                 regle="le trou d'une instance montre le marqueur si sélectionnée, le passager s'il vit, sinon `vide`"),
    "regle_rendu": dict(params=["classe", "selecteur", "couleur", "condition"], phase=10,
                        regle="indice de rendu paramétré en direction (bord(d) ∧ contact(d) ∧ sel) ; pas une loi"),
    "completion_scene": dict(params=["portee", "couleur", "pixels"], phase=0,
                             regle="décor sous les instances : a priori « sol de l'anneau », corrigé à chaque dévoilement"),
    "hud": dict(params=["lignes"], phase=10, regle="lignes d'interface exclues des comparaisons de géométrie (elles "
                "portent l'économie)"),
}

# Catalogue des types d'écart (agent cloud) : signature calculable → hypothèses générées (cœur de la boucle qui apprend)
TYPES_ECART = {
    "TRAVERSEE": ("prévu immobile, réel déplacé dans le sens de l'action", ["blocage", "poussee", "glissement"]),
    "BLOCAGE": ("prévu déplacé, réel immobile", ["blocage", "poussee"]),
    "DISTANCE": ("même sens, longueur différente", ["glissement", "prolongation", "blocage"]),
    "AUTONOME": ("instance non concernée qui change (cycle ou déplacement)", ["piston", "autonome", "memoire_fantome"]),
    "RENDU": ("géométrie exacte, pixels différents dans une empreinte", ["regle_rendu", "trou"]),
    "SCENE": ("géométrie exacte, pixels découverts ≠ scène supposée", ["completion_scene"]),
    "DECOR": ("autre pixel du décor différent (porte, apparition)", ["bouton", "creation"]),
    "INCONNU": ("sens incohérent sans explication", []),
    "CERTIFICAT": ("but inaccessible dans la théorie (UNSAT ASP), sans écart", ["blocage"]),
}
# Coûts MDL des patchs (agent cloud) ; égalité de coût ⇒ expérience discriminante (≤ 4 coups, bornée par la jauge)
COUTS_MDL = {"bloquant": 2, "poussee": 2, "poussee_classe_jamais_vue": 1, "prolongation": 3, "parametre": 3, "fond": 9}

# Couche 6 (CW-388) : familles → techniques → persona ; l'ordre ne fait que PRIORISER (fiche = priorité, pas filtre, CW-365)
FAMILLES = {
    "pousse_cibles": (["impasse_sokoban", "cases_mortes", "ordonner_sous_buts", "recherche_guidee"], "prudent"),
    "navigation_sortie": (["chemin_grille", "bfs", "plan_sous_reserve", "impasse_relaxee"], "prudent"),
    "conditionnel": (["ordonner_sous_buts", "plan_sous_reserve", "recherche_guidee"], "reflechi"),
    "collecte": (["tournee", "plan_sous_reserve"], "econome"),
    "interrupteurs_clic": (["interrupteurs", "table_retrograde", "bfs"], "reflechi"),
    "correspondance_modele": (["ordonner_sous_buts", "recherche_guidee", "table_retrograde"], "reflechi"),
    "selection_deplacement": (["ordonner_sous_buts", "recherche_guidee"], "prudent"),
    "glissade": (["macro_glissades", "bfs"], "prudent"),
    "memoire_fantome": (["table_retrograde", "recherche_guidee"], "reflechi"),
    "inconnue": (["recherche_guidee"], "explorateur"),
    # familles manquantes proposées par E (CCM-070-E, accord couche 6 / fiches : 5/20 seulement) — PROPOSÉES : pas
    # encore de technique dédiée dans la couche 6 ; techniques génériques en attendant
    "faire_disparaitre": (["ordonner_sous_buts", "recherche_guidee"], "reflechi"),       # but « absent » (lf52, m0r0)
    "commande_distance_miroir": (["recherche_guidee", "bfs"], "reflechi"),               # miroir, distance (m0r0, ar25)
    "apparier": (["ordonner_sous_buts", "recherche_guidee"], "prudent"),                 # paires (ka59, re86, r11l, lp85)
    "sequence": (["table_retrograde", "ordonner_sous_buts"], "reflechi"),               # ordre imposé (sb26, sk48)
    "ecoulement": (["table_retrograde", "bfs"], "reflechi"),                             # liquide (sp80) ≠ glissade
}
FAMILLES_PROPOSEES = ("faire_disparaitre", "commande_distance_miroir", "apparier", "sequence", "ecoulement")
PERSONAS = ("prudent", "explorateur", "reflechi", "econome", "a_rebours")
# La couche 6 lit la section `strategies` de la mémoire globale de diagnostic SEULEMENT (politiques générales, aucune vérité par jeu) : conforme
# à CW-367.1 ; `classes`, `parametres` et le champ `jeux` des lois restent du diagnostic (tests/test_memoire_diagnostic.py).

# Contradictions tranchées selon la proposition de B (à confirmer par Cowork)
DECISIONS_FUSION = {
    "defaite_epuisement": "proposition B : CONFIRMÉE dans tous les jeux mesurés (20/20 publics, 104/104 T4) ; seul le "
                          "barème est à apprendre (l'agent cloud la tenait pour « jamais testée »)",
    "fond_solide": "proposition B : cas particulier du contrat `blocage` (obstacle = fond), pas une option à part",
}

# Correspondance des noms vers le code de l'agent cloud (`boucle/ontologie.py`) : une seule source de noms
NOMS_BOUCLE = {"SelectionClic": "selection_clic", "Deplacement": "deplacement", "Glissement": "glissement",
               "Piston": "piston", "Trou": "trou", "RegleRendu": "regle_rendu", "CompletionScene": "completion_scene",
               "Jauge": "ECONOMIE", "ButEmboite": "but (ONTOLOGIE couche 5 : emboite)", "Memoire": "memoire_fantome",
               "Fantome": "memoire_fantome", "Plaque": "bouton (tenue)", "Porte": "bouton (tenue)"}

# Le TEMPS au premier rang (avis d'expert, CW-389) : l'état d'un pas n'est pas qu'une image ; une loi peut lire le
# pas d'avant, un événement passé ou un historique borné, et son effet peut être différé.
TEMPS = {
    "fluents": {"prec(F)": "valeur du fluent F au pas précédent (déplacement, sens, changement)",
                "evenement(E,T)": "micro-événement daté (ONTOLOGIE v2.2, couche 3) : poussé, tombé, recoloré, ouvert",
                "historique(K)": "K derniers pas (mémoire bornée ; trajet du fantôme, séquence de boutons)",
                "horloge": "t modulo le PPCM des périodes autonomes (ETAT_LATENT['t'])"},
    "formes_de_loi": {"immediate": "effet au même pas que la cause (phase de l'action)",
                      "differee": "effet k pas après la cause (minuteur, bombe, piston chargé)",
                      "persistante": "effet tant qu'une condition tient (porte tenue par une dalle)",
                      "sequentielle": "effet après une suite ordonnée d'événements (boutons dans l'ordre)"},
}

# Opérateur de réparation causale (avis d'expert, CW-389) : à partir d'un écart, les PLUS PETITES modifications
# structurelles TYPÉES d'une loi, chacune rejouée sur toutes les transitions observées (frontière de réparation).
# Elles complètent TYPES_ECART (quelles hypothèses) par la FORME du changement.
REPARATIONS = {
    "spatial_vers_temporel": "le déclencheur n'est pas une position mais un moment (après k pas, à la période p)",
    "local_vers_distant": "la cause agit sur un objet éloigné (bouton → porte)",
    "ajout_etat_persistant": "une variable cachée retient un fait passé (clé ramassée, dalle déjà pressée)",
    "immediat_vers_differe": "l'effet arrive k pas plus tard",
    "precondition_de_mode": "la loi ne vaut que dans un mode (glissement ≠ marche, sélection active)",
    "objet_vers_classe": "la loi vaut pour toute la classe, pas pour l'instance vue",
    "composition_ordonnee": "deux lois s'enchaînent dans un ordre de phase précis",
}
# Hypothèses JOINTES but × mécanisme (CW-389) : on ne garde pas un but en inventant une mécanique pour le sauver ; on
# garde des classes d'équivalence de couples (but, théorie) et on ne tranche que si leurs actions diffèrent.
HYPOTHESES_JOINTES = {"principe": "classes d'équivalence de couples (but, théorie) ; trancher seulement par une "
                                  "expérience dont les prédictions diffèrent (persona `reflechi`)"}

# CW-392 : 1re victoire sur un niveau tenu à l'écart (g50t N7, 44 coups, agent cloud P0) grâce à un mécanisme INVENTÉ
# (absent de la v4), réutilisé tel quel sur N7. Deux contrats, ajoutés tels que décrits par Cowork (aucun code P0 lu).
MECANISMES.update({
    "autonome_couloir": dict(roles=["autonome"], params=["couloir", "depart", "declencheur_retour"],
                             pre="un coup EFFECTIF du joueur", effets="avance d'un pas le long de son couloir ; revient "
                             "au départ sur ACTION5 ; écrasé par une porte qui se ferme sur lui", phase=3,
                             ecrit=["pos", "present"], contre_exemples=["avance aussi sur un coup sans effet",
                                                                        "traverse une porte fermée"],
                             test="jouer un coup effectif puis un coup sans effet : n'avance-t-il qu'au premier ?",
                             source="g50t N6 (développement) et N7 (tenu à l'écart), CW-392"),
    "active_declencheurs_traverses": dict(roles=["autonome", "bouton"], params=["mobile", "declencheurs"],
                                          pre="le mobile (joueur OU autonome) passe sur un déclencheur",
                                          effets="le déclencheur s'active comme si le joueur l'avait pressé (dalle, "
                                          "portail : autre famille de déclencheur en N7)", phase=3, ecrit=["attr"],
                                          contre_exemples=["seul le joueur active les dalles"],
                                          test="laisser l'autonome passer sur une dalle : la porte réagit-elle ?",
                                          source="CW-392"),
    # CW-400 (3) : explication RIVALE de g50t N6 (Astra brief 6, `latch(not occupied(capteur))`), décrite par Cowork.
    "latch_rendu": dict(roles=["bouton"], params=["capteur", "condition"],
                        pre="le capteur passe dans l'état `condition` (ex. « non occupé »)",
                        effets="l'état du capteur est VERROUILLÉ ; il persiste au rendu et dans la loi même quand "
                        "la condition cesse", phase=3, ecrit=["attr"],
                        contre_exemples=["la porte se referme dès que le mobile quitte la dalle (tenue)"],
                        test="poser un mobile sur la dalle, puis l'en retirer : la porte reste-t-elle dans son état ?",
                        source="Astra brief 6 (P0), CW-400"),
})

# Explications rivales d'un même niveau (identifiabilité, CW-400) : on les garde côte à côte, statut « non départagées »,
# jusqu'au coup dont les prédictions diffèrent. Le verdict n'est PAS écrit ici (la bibliothèque ne porte aucune vérité).
RIVALES = {
    "g50t_N6": dict(hypotheses=["active_declencheurs_traverses", "latch_rendu", "bouton(tenue) + memoire_fantome"],
                    statut="non_departagees",
                    coups_qui_departagent=[
                        "un mobile quitte la dalle : la porte se referme (tenue) ou reste (latch) ?",
                        "seul le fantôme ou l'autonome se pose sur la dalle, le joueur ailleurs : la porte réagit-elle ?",
                        "l'autonome avance-t-il sur un coup sans effet ? (couloir propre ou trajet rejoué du joueur)"]),
}

# Ce qui se GARDE d'un niveau à l'autre et ce qui se RECALCULE (CW-404, C + B ; l'erreur la plus coûteuse est la valeur
# codée en dur transférée). Par défaut un paramètre inconnu se recalcule : on ne transfère jamais une valeur par mégarde.
TRANSFERT = {
    "garde": ("roles", "pre", "effets", "phase", "ecrit", "contre_exemples", "test", "conditions", "invariants",
              "experiences_utiles"),
    "recalcule": ("positions", "identifiants", "instances", "liaisons", "but", "budget", "scene"),
    "params_garde": frozenset({"dx", "dy", "mode", "jusqu_a", "traverse", "tenue", "attribut", "valeur", "politique",
                               "direction", "pilote", "declencheur", "declencheur_retour", "retour", "mobile",
                               "obstacle", "modele", "condition"}),
    "params_reverifie": frozenset({"periode", "charge", "portee", "pas", "longueur", "effet", "etat"}),
}


def separer_pour_transfert(theorie: dict) -> dict:
    """Coupe une théorie {mecanisme, params, …} en garde / à re-vérifier au 1er pas / à recalculer sur la scène."""
    garde = {k: v for k, v in theorie.items() if k in TRANSFERT["garde"] or k == "mecanisme"}
    recalcule = [k for k in theorie if k not in garde and k != "params"]
    reverifie, pg = {}, {}
    for p, v in (theorie.get("params") or {}).items():
        if p in TRANSFERT["params_garde"]:
            pg[p] = v
        elif p in TRANSFERT["params_reverifie"]:
            reverifie[p] = v
        else:
            recalcule.append(p)
    garde["params"] = pg
    return {"garde": garde, "reverifie": reverifie, "recalcule": sorted(recalcule)}

# --- Fusion v1 faite par B (CW-406.1 : plus d'attente de relecture). Sources : v1.2 de B, ONTOLOGIE_V1 de l'agent
# cloud (déjà reprise : PHASES, ETAT_LATENT, PROJECTION, TYPES_ECART, COUTS_MDL), contrats d'Astra 3 et 4, couche 6
# (FAMILLES identiques à `couche6/strategies/familles.py`, vérifié par test), temps, économie, rivales de g50t N6.

# Ce que chaque mécanisme LIT (Astra 3 a des contrats lit/écrit ; B n'avait que `ecrit`). Sert aux paires
# d'actions indépendantes (sonde de G, CW-403) : deux mécanismes sont indépendants si aucun n'écrit ce que l'autre lit
# ou écrit, phases 3 et 4 comprises.
# « selection » = QUI est contrôlé (écrit par `selection_clic`) : tout mécanisme qui agit sur le contrôlé la lit
# (oubli trouvé par la mesure de commutation, CW-410 : flèche et clic de sélection ne commutent pas).
_LIT = {"deplacement": ["action", "pos", "selection"], "blocage": ["pos", "empreinte", "mode", "etat"],
        "poussee": ["pos", "empreinte", "selection"], "glissement": ["pos", "empreinte", "mode", "selection"],
        "prolongation": ["pos", "surface", "selection"],
        "ramassage": ["pos", "present"], "transformation": ["pos", "attr"],
        "selection_clic": ["action", "empreinte", "selection"], "bouton": ["pos", "present", "attr"],
        "autonome": ["horloge", "pos", "memoire"], "teleportation": ["pos", "liaison"],
        "creation": ["evenement", "present"], "piston": ["horloge", "pos", "charge"],
        "memoire_fantome": ["action", "historique", "pos"], "autonome_couloir": ["action", "pos"],
        "active_declencheurs_traverses": ["pos", "present"], "latch_rendu": ["pos", "attr"]}
for _n, _l in _LIT.items():
    MECANISMES[_n]["lit"] = _l

# Contrats d'Astra 3 (`livraison_astra3/resultats/contrats.json`) et 4 (`livraison_astra4/contrats.json`) → les nôtres.
# Aucun n'est un mécanisme nouveau ; deux précisent des paramètres (ci-dessous).
NOMS_ASTRA = {"seuil_distance": "glissement (jusqu_a)", "continuer_glissement": "glissement",
              "prolongation_surface": "prolongation", "ajouter_memoire": "memoire_fantome",
              "retour_depart": "memoire_fantome (retour)", "vider_enregistrement": "memoire_fantome",
              "bascule_entree": "bouton (tenue=bascule)", "porte": "bouton (tenue)", "collision": "blocage",
              "portail": "teleportation", "perception": "PERCEPTION", "economie": "ECONOMIE"}
MECANISMES["memoire_fantome"]["params"] += ["capacite", "politique_pleine"]   # Astra 4 : capacity ≥ 1, clear | fifo
MECANISMES["bouton"]["valeurs"] = {"tenue": ["tenue", "inverse", "bascule"]}  # Astra 4 : held | inverse | toggle
TRANSFERT["params_reverifie"] = TRANSFERT["params_reverifie"] | {"capacite"}
TRANSFERT["params_garde"] = TRANSFERT["params_garde"] | {"politique_pleine"}

# Les deux points contradictoires de la fusion, ADOPTÉS par B (CW-406.1) après le contrôle positif de non-contradiction
# (`tests/test_ontologie_formelle.py::test_programme_ne_contredit_pas_le_protocole`, 20 programmes).
DECISIONS_FUSION = {k: v.replace("proposition B", "ADOPTÉ (B, CW-406)") for k, v in DECISIONS_FUSION.items()}
VERSION = "v1 fusionnée (22/10, CW-406)"

# CCM-038-H / CW-429 : contrat proposé par H, ADOPTÉ par B sous son nom. C'est la loi « sélection par cycle » (mémoire
# globale : ar25 et re86 au SPACE, tr87 à la flèche latérale), que la v1 ne portait pas (`selection_clic` exige un clic).
# Rôle : l'hôte est un `selectionnable` (liste fermée de 12 rôles) ; le marqueur est un élément de perception, pas un rôle.
MECANISMES["selection_marqueur"] = dict(
    roles=["selectionnable"], params=["action", "hotes", "sauts"],
    pre="action sélecteur (clavier, pas un clic) ; un marqueur est posé sur un hôte",
    effets="le marqueur saute vers l'hôte suivant (table `sauts` : forme de départ → forme d'arrivée, décalage) ; "
           "l'objet sous le marqueur devient le contrôlé et le suit",
    phase=0, ecrit=["selection"], lit=["action", "selection", "empreinte"],
    contre_exemples=["la sélection exige un clic (selection_clic)", "l'ordre des hôtes est l'ordre de lecture"],
    test="jouer le sélecteur puis une flèche : c'est l'objet sous le marqueur qui bouge (re86)",
    source="H, CCM-038-H (traducteur théorie → contrats) ; adopté par B, CW-429")
