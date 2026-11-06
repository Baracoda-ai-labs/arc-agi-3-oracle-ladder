#!/usr/bin/env bash
# Mac (CW-260) : 13 niveaux frontière, copie figée 5ae36a9, 3 en parallèle
xargs -P 3 -n 1 bash /Users/ts/models/chrysalide3/experiments/instrument/rates/un.sh < /Users/ts/models/chrysalide3/experiments/instrument/rates/jeux.txt
touch /Users/ts/models/chrysalide3/experiments/instrument/rates/FINI
