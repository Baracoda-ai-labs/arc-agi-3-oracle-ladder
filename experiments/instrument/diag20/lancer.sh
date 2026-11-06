#!/usr/bin/env bash
# Mac (CW-249 action 1, CW-251) : diagnostic à configurations sur les 20 jeux publics non témoins, niveau 1, K=40, graine 0,
# HEAD du moment, 3 jeux en parallèle. Sorties : experiments/instrument/raw/diag4_k40_g0_d20_<jeu>.json.
cd /Users/ts/models/chrysalide3; O=experiments/instrument/diag20; git log -1 --format=%h > $O/HEAD.txt
xargs -P 3 -I{} sh -c 'DIAG_SUFFIXE=_d20_{} CHRYS_AMODAL=1 PYTHONPATH=$PWD nice -n 10 timeout 5400 uv run python experiments/instrument/diag4.py 40 0 {} > '$O'/{}.log 2>&1' < $O/jeux.txt
touch $O/FINI
