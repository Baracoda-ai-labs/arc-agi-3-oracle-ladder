# Code et composants de tiers
Ces composants ne sont **pas** sous MIT-0. Leur licence et leur attribution d'origine s'appliquent.
| Composant | Licence | Source | Usage ici |
|---|---|---|---|
| Solution ARC-AGI-3 de Daniel Franzen | Apache-2.0 (`LICENSE-APACHE-2.0`) | github.com/da-fr/arc-agi-3-solution, révision 10882e33 | Base du carnet Kaggle soumis (RO v7), récupérée par `scripts/pod/setup_franzen.sh`, modifiée par `scripts/arc3/patcher_*.py`. Fragments cités dans ces patchers. |
| Cadre « Duck » de Tufa Labs (Jeroen Cottaar et Tufa Labs) | **aucun fichier de licence** dans github.com/Tufalabs/duck-harness (relu le 2/11 à la révision 7652836 citée par Franzen et sur la branche par défaut) | dont dérive la solution Franzen, qui l'inclut (`ARC3-Inference/`, `tufa-arc-agi-framework/`) | Non copié dans notre code. `duck.py` est une réimplémentation en salle blanche, sous MIT-0. Attribution conservée. |
| Dépendances Python, poids de modèles, données de la compétition | leurs licences respectives | voir `pyproject.toml`, `uv.lock` et les entrées du carnet Kaggle (modèle Qwen3.8-Flash-Next, quantifications RadixArk et Intel, runtime SGLang « pennyroyal ») | Non redistribués par ce dépôt. |

Relu le 2/11 : le dépôt Franzen à 10882e33 contient un seul `LICENSE` Apache-2.0 (texte standard) et **aucun fichier NOTICE** ; il n'y a donc pas de NOTICE amont à reproduire. Les patchers marquent nos modifications, comme le demande l'article 4(b).
**À vérifier avant publication (8/11) :** (1) le statut du code Tufa Labs inclus dans la solution Franzen, puisque son dépôt d'origine n'a pas de licence ; (2) les licences des poids et du runtime chargés par le carnet. Ce sont des questions de droit, pas de code : décision de Thomas.
