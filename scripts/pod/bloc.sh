#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD : un bloc de prereg_S2 (amendement A). Usage : bash scripts/pod/bloc.sh <nom> [VAR=valeur ...] [-- jeux]
#   bash scripts/pod/bloc.sh R0                                        # Franzen, 25 jeux, 1 passage
#   bash scripts/pod/bloc.sh V1 CHRYS_MONITEUR=1 CHRYS_REFLEXES=1 CHRYS_ROUTEUR=1 CHRYS_VERIF=1
#   bash scripts/pod/bloc.sh FC2 -- '["ls20","ft09","vc33","sp80","r11l"]'
# Sert le modèle s'il ne répond pas, lance le harnais, mesure CPU (cgroup) et GPU, écrit /workspace/runs/<nom>/FINI ou ARRET.
set -uo pipefail
[ -f /workspace/pod_env.sh ] && . /workspace/pod_env.sh   # RUNPOD_POD_ID, absent des sessions distantes
cd "$(dirname "$0")/../.."
D=$PWD; W=/workspace; nom=$1; shift
jeux=""; envs=()
while [ $# -gt 0 ]; do
  if [ "$1" = "--" ]; then jeux=$2; shift 2; else envs+=("$1"); shift; fi
done
# TÉMOINS (docs/TEMOINS.md) : jamais mesurés hors jalon. Sans liste, le bloc prend les 20 NON témoins ; une liste qui cite un
# témoin est refusée, sauf JALON=1 explicite (18/10 : S1on/S1off, FC2b et F14 avaient tourné témoins compris, CCM-175-A).
TEMOINS="vc33 tu93 wa30 s5i5 cn04"
if [ "${JALON:-0}" != "1" ]; then
  [ -z "$jeux" ] && jeux='["ar25","bp35","cd82","dc22","ft09","g50t","ka59","lf52","lp85","ls20","m0r0","r11l","re86","sb26","sc25","sk48","sp80","su15","tn36","tr87"]'
  for t in $TEMOINS; do echo "$jeux" | grep -q "$t" && { echo "REFUS : témoin $t hors jalon (JALON=1 pour un jalon)" > "$W/runs/$nom.REFUS"; exit 2; }; done
fi
R=$W/runs/$nom; mkdir -p "$R"
pgrep -f veille_inactivite.sh >/dev/null || nohup "$W/veille_inactivite.sh" >/dev/null 2>&1 &
if ! curl -sf http://127.0.0.1:8011/health >/dev/null; then
  touch "$W/KEEPALIVE"   # chargement du modèle : GPU calme quelques minutes, le garde-fou ne doit pas couper
  python3 "$D/scripts/pod/franzen_lanceur.py" > "$W/runs/lanceur.log" 2>&1
  rm -f "$W/KEEPALIVE"
  curl -sf http://127.0.0.1:8011/health >/dev/null || { echo "serveur absent" > "$R/ARRET"; exit 1; }
fi
set -a; . "$D/scripts/pod/franzen_env.sh"; set +a
for e in "${envs[@]}"; do export "$e"; done
# surcharge décidée APRÈS le lancement de la chaîne (CW-053) : scripts/pod/env_<nom>.sh, lu à neuf, tracé dans env.txt
[ -f "$D/scripts/pod/env_$nom.sh" ] && . "$D/scripts/pod/env_$nom.sh" && echo "surcharge env_$nom.sh appliquée" > "$R/surcharge.txt"
export CHRYS_DOSSIER=$R/chrysalide
env | grep -E "^(CHRYS_|ARC3_|MULTIMODAL_)" | sort > "$R/env.txt"
cd "$W/harnais"
nohup make interactive CONFIG_PATH="$D/scripts/pod/franzen_inference.json" RUN_NAME="$nom" EXPERIMENTS_DIR="$R" \
  ENVIRONMENTS_DIR="$W/environment_files" ${jeux:+GAME="$jeux"} > "$R/run.log" 2>&1 < /dev/null &
pid=$!
echo $pid > "$R/pid"
nohup bash "$D/scripts/pod/mesure_cpu.sh" "$pid" > "$R/util.csv" 2>&1 &   # GPU %, VRAM, cœurs (cgroup), toutes les 30 s (CW-045)
wait $pid; code=$?
echo "code $code $(date '+%d/%m %H:%M')" > "$R/$([ $code -eq 0 ] && echo FINI || echo ARRET)"
tail -5 "$R/run.log" >> "$R/$([ $code -eq 0 ] && echo FINI || echo ARRET)"
# crochet de suite (CW-051) : un bloc ajouté APRÈS le lancement de la chaîne, sans éditer chaine_nuit.sh en cours
[ -f "$D/scripts/pod/apres_$nom.sh" ] && bash "$D/scripts/pod/apres_$nom.sh"
exit $code
