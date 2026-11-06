#!/usr/bin/env bash
# un niveau frontière (CW-260), depuis la copie figée 5ae36a9
cd /private/tmp/claude-501/-Users-ts-models-chrysalide3/62f2ec93-cde8-4b1b-9894-b71007d9b620/scratchpad/fige_5ae36a9 && CHRYS_PARTIEL=2 CHRYS_AMODAL=1 CHRYS_BUT_SUPPOSE=1 CHRYS_MOTEUR_BUDGET_S=2 PYTHONPATH=/private/tmp/claude-501/-Users-ts-models-chrysalide3/62f2ec93-cde8-4b1b-9894-b71007d9b620/scratchpad/fige_5ae36a9 nice -n 10 timeout 3600 \
  /Users/ts/models/chrysalide3/.venv/bin/python experiments/instrument/banc_rates.py "$1" /Users/ts/models/chrysalide3/experiments/instrument/rates/"$1".json 10 200000 300 > /Users/ts/models/chrysalide3/experiments/instrument/rates/"$1".log 2>&1
