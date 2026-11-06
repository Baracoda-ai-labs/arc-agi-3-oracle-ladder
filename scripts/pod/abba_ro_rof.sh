#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD (Codex/Thomas 29/10) : mesure appariée ABBA RO / ROF, ordre RO1 ROF1 ROF2 RO2, 20 jeux publics NON témoins
# (liste par défaut de bloc.sh), 48 min murales par jeu (MAX_RUNTIME_MINUTES exporté avant `make`, prioritaire sur les 121
# de franzen_inference.json), réglages du carnet v3 (franzen_env.sh) + ceux de la cellule 12.
# Harnais : RO_EXACT=1 bash scripts/pod/setup_franzen.sh (franzen, garde, outils, faits — l'ordre de la cellule 12).
# Les deux bras jouent le MÊME harnais ; seul CHRYS_FAITS diffère, posé EXPLICITEMENT dans les deux (0 / 1).
# Usage : RO_EXACT=1 bash scripts/pod/setup_franzen.sh > /workspace/setup.log 2>&1 && setsid nohup bash scripts/pod/abba_ro_rof.sh &
# Sortie : /workspace/bancs/abba_ro_rof.FINI = QUATRE passages complets (code 0) ; sinon abba_ro_rof.INCOMPLET (verdict suspendu).
# N'arrête PAS le pod : l'extinction est faite par l'exécutant 1 / Cowork à la lecture de FINI ou INCOMPLET.
set -uo pipefail
cd "$(dirname "$0")/../.."
D=$PWD; W=/workspace; mkdir -p $W/bancs $W/runs
PASSAGES="RO1 ROF1 ROF2 RO2"
j() { echo "$(date '+%d/%m %H:%M') abba_ro_rof : $*" | tee -a $W/runs/chaine_etapes.txt; }
incomplet() { echo "$*" > $W/bancs/abba_ro_rof.INCOMPLET; j "INCOMPLET : $* — verdict suspendu"; exit 1; }
A=$W/harnais/inference/agent/tool_agent.py
grep -q "CHRYSALIDE-FAITS-VISUELS" $A && grep -q "CHRYSALIDE-OUTILS" $A || incomplet "harnais non aligné (RO_EXACT=1 setup_franzen.sh)"
grep -q "CHRYSALIDE-PERCEPTION" $A && incomplet "patch perception présent"
for n in $PASSAGES; do   # sorties neuves ; aucune surcharge ni crochet que bloc.sh chargerait en silence
  [ -e $W/runs/$n ] && incomplet "dossier $W/runs/$n déjà présent"
  for f in scripts/pod/env_$n.sh scripts/pod/apres_$n.sh; do [ -e "$f" ] && incomplet "$f présent (bloc.sh le chargerait)"; done
done
rm -f $W/bancs/abba_ro_rof.FINI $W/bancs/abba_ro_rof.INCOMPLET
RO="CHRYS_OUTILS=1 CHRYS_OUTILS_APRES=40 CHRYS_FAITS=0 CHRYS_FAITS_APRES=40"
ROF="CHRYS_OUTILS=1 CHRYS_OUTILS_APRES=40 CHRYS_FAITS=1 CHRYS_FAITS_APRES=40"
{ echo "chrysalide3 $(git rev-parse HEAD)"; echo "lanceur_sha256 $(sha256sum scripts/pod/abba_ro_rof.sh | cut -c1-64)"
  echo "franzen $(cat $W/franzen.commit)"
  echo "modele_depot $(cat $W/modele_id.txt 2>/dev/null || echo 'albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE (setup_franzen.sh)')"
  for f in config.json generation_config.json model.safetensors.index.json; do
    [ -f $W/modele/$f ] && echo "modele_$f $(sha256sum $W/modele/$f | cut -c1-64)"; done
  echo "modele_poids_sha256 $(cd $W/modele && ls *.safetensors 2>/dev/null | sort | xargs -r sha256sum | sha256sum | cut -c1-64)"
  echo "harnais_py_sha256 $(cd $W/harnais && find . -path ./.venv -prune -o -type f -name '*.py' -print | sort | xargs sha256sum | sha256sum | cut -c1-64)"
  echo "jeux_ordonnances_en_parallele $(python3 -c "import json;print(json.load(open('scripts/pod/franzen_inference.json'))['environment']['concurrent_jobs'])" 2>/dev/null)"
  echo "flux_llm_actifs $(grep ARC3_MAX_ACTIVE_STREAMS scripts/pod/franzen_env.sh | cut -d"'" -f2)"
  echo "minutes_par_jeu 48 (MAX_RUNTIME_MINUTES, env ; config : $(python3 -c "import json;print(json.load(open('scripts/pod/franzen_inference.json'))['environment']['max_runtime_minutes'])" 2>/dev/null))"
  nvidia-smi --query-gpu=name,memory.total,driver_version,power.limit --format=csv,noheader; free -g | head -2
  echo "RO: $RO"; echo "ROF: $ROF"; } > $W/manifeste_abba_ro_rof.txt
j "manifeste écrit ($W/manifeste_abba_ro_rof.txt) ; attente de AUTORISE_RO1 (revue Codex)"
while [ ! -f $W/bancs/AUTORISE_RO1 ]; do [ -f $W/bancs/STOP_RO_ROF ] && incomplet "STOP avant RO1"; sleep 30; done
for n in $PASSAGES; do
  [ -f $W/bancs/STOP_RO_ROF ] && incomplet "STOP avant $n"
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || incomplet "moins de 4 Go libres avant $n"
  case $n in ROF*) a=($ROF);; *) a=($RO);; esac
  j "début $n (${a[*]})"
  bash scripts/pod/bloc.sh $n "${a[@]}" ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  code=$?
  python3 scripts/pod/compter_faits.py $W/runs/$n > $W/runs/$n.faits.json 2>&1
  j "fin $n (code $code) ; faits : $(cat $W/runs/$n.faits.json | head -c 200)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
  [ $code -eq 0 ] && [ -f $W/runs/$n/FINI ] || incomplet "$n : code $code ou FINI absent"
done
touch $W/bancs/abba_ro_rof.FINI; j "quatre passages complets — rapatrier puis détruire le pod"
