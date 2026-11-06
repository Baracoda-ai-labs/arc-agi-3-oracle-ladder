#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# CW-434 essai (c), H : Franzen pur (aucun drapeau CHRYS_*) sur les 3 jeux T4 neufs de experiments/essais_vast/generer_t4_essai.py,
# hors ligne, un passage ; mesure : niveaux gagnés par heure de carte. Calqué sur bloc.sh, seul le dossier des jeux change.
# Usage (sur la machine d'essai, serveur déjà prêt sur 8011) :
#   tar xzf t4essai.tgz -C $W/t4essai && bash scripts/pod/essai_t4.sh T4E '["t4e0","t4e1","t4e2"]'
# Puis : python3 scripts/pod/resume_bloc.py $W/runs/T4E   (après FINI seulement)
set -uo pipefail
cd "$(dirname "$0")/../.."
D=$PWD; W=${W:-/workspace}; nom=$1; jeux=$2
E_DIR=$W/t4essai/environment_files
[ -d "$E_DIR" ] || { echo "jeux T4 absents : $E_DIR"; exit 1; }
for t in vc33 tu93 wa30 s5i5 cn04; do echo "$jeux" | grep -q "$t" && { echo "REFUS : témoin $t"; exit 2; }; done
curl -sf http://127.0.0.1:8011/health >/dev/null || { echo "serveur absent sur 8011"; exit 1; }
R=$W/runs/$nom; mkdir -p "$R"
set -a; . "$D/scripts/pod/franzen_env.sh"; set +a
env | grep -E "^(CHRYS_|ARC3_|MULTIMODAL_)" | sort > "$R/env.txt"
grep -q "^CHRYS_" "$R/env.txt" && { echo "REFUS : drapeau CHRYS_ présent, l'essai est Franzen pur"; exit 2; }
date +%s > "$R/debut"
cd "$W/harnais"
nohup make interactive CONFIG_PATH="$D/scripts/pod/franzen_inference.json" RUN_NAME="$nom" EXPERIMENTS_DIR="$R" \
  ENVIRONMENTS_DIR="$E_DIR" GAME="$jeux" > "$R/run.log" 2>&1 < /dev/null &
pid=$!; echo $pid > "$R/pid"
nohup bash "$D/scripts/pod/mesure_cpu.sh" "$pid" > "$R/util.csv" 2>&1 &
wait $pid; code=$?
echo "code $code $(date '+%d/%m %H:%M') durée $(( $(date +%s) - $(cat "$R/debut") )) s" > "$R/$([ $code -eq 0 ] && echo FINI || echo ARRET)"
exit $code
