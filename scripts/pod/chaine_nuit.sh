#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD : chaîne complète sans temps mort (CW-045) : attend la fin de setup_franzen.sh, puis
#   R0 → V1 → P → V2' (si son amendement est scellé) → F-C2 → courbe CPU, puis ARRÊT DU POD (trap).
# Usage : setsid nohup bash scripts/pod/chaine_nuit.sh > /workspace/runs/chaine.log 2>&1 < /dev/null &
# Installation ratée → la chaîne s'arrête SANS arrêter le pod (pour réparer ; le garde-fou d'inactivité coupe après 30 min).
# Un bloc qui échoue n'arrête pas la chaîne. Budget : chaque bloc ≤ 121 min par jeu en parallèle (≈ 2 h 15) ; limite
# globale LIMITE_H (13 h ≈ 33 $ à 2,52 $/h, sous l'alerte de 35 €).
set -uo pipefail
[ -f /workspace/pod_env.sh ] && . /workspace/pod_env.sh   # RUNPOD_POD_ID, absent des sessions distantes
cd "$(dirname "$0")/../.."
W=/workspace; mkdir -p $W/runs; LIMITE_S=$(( ${LIMITE_H:-13} * 3600 )); t0=$(date +%s)
journal() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
while ps -eo args | grep -q "[s]etup_franzen.sh"; do sleep 30; done
grep -q "INSTALLATION FRANZEN OK" $W/setup.log || { journal "installation ratée : chaîne non lancée"; exit 1; }
trap 'journal "fin de chaîne, arrêt du pod"; runpodctl stop pod "$RUNPOD_POD_ID"' EXIT
reste() { [ $(( $(date +%s) - t0 )) -lt $LIMITE_S ]; }
bloc() { journal "début $1"; bash scripts/pod/bloc.sh "$@"; journal "fin $1 (code $?)"; }
V1="CHRYS_MONITEUR=1 CHRYS_REFLEXES=1 CHRYS_ROUTEUR=1 CHRYS_VERIF=1"
reste && bloc R0
reste && bloc V1 $V1
reste && [ -f scripts/pod/bloc_P.sh ] && { journal "début P"; bash scripts/pod/bloc_P.sh; journal "fin P (code $?)"; }
reste && [ -f experiments/arc3/prereg_S2_amendement_V2prime.md ] && bloc V2p $V1 CHRYS_OUTILS=1
reste && bloc FC2 -- '["ls20","ft09","vc33","sp80","r11l"]'
reste && { journal "début courbe CPU"; timeout 1200 $W/harnais/.venv/bin/python scripts/pod/courbe_cpu.py $W/environment_files \
  $W/runs/courbe_cpu.json > $W/runs/courbe_cpu.log 2>&1; journal "fin courbe CPU"; }
