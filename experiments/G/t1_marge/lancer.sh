#!/bin/bash
# T1 (C, CW-455/456) : copie de travail du paquet v2 + relève MoteurC (`CHRYS_P1_MOTEUR=observe|joue`, absent = v2).
# Le `chrysalide` du DÉPÔT est utilisé (MoteurC). Usage : [CHRYS_P1_MOTEUR=…] lancer_t1.sh <jeux> <sortie> [--graine g]
set -euo pipefail
ICI=$(cd "$(dirname "$0")" && pwd); W=$ICI/paquet; R=$(cd "$ICI/../../.." && pwd)
JEUX=$1; SORTIE=$2; shift 2
for t in vc33 tu93 wa30 s5i5 cn04; do [ -e "$JEUX/$t" ] && { echo "REFUS : témoin $t" >&2; exit 3; }; done
export CHRYS_FILMS_P1=3 CHRYS_G_NOUV=1 CHRYS_F_CLE=bande3 CHRYS_BUT_SUPPOSE=1
export PYTHONPATH=$W:$R:$W/livraison_p1/code:$W/references/astra4/livraison_astra4/ajouts:$W/livraison_explo/code
exec "$R/.venv/bin/python" -B "$W/livraison_explo/code/runner.py" --jeux "$JEUX" --sortie "$SORTIE" --explorateur generique \
     --mode complet --memoire_depart "$W/livraison_p1/memoire_depart" --budget 150 "$@"
