#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD (décision Thomas 30/10 08 h 25, contrat E_PORTE5) : mesure appariée ABBA RO / variante empirique (v4 isolée + historique + stagnation + arrêts bornés, décision Thomas 15 h 10), ordre PR1 P51 P52 PR2,
# 20 jeux publics NON témoins (liste de bloc.sh), 48 min par jeu, 10 flux. Réglages figés ici AVANT la mesure, jamais ajustés après.
# Avant : archive du dépôt avec experiments/GEL27_moteur_seul_v2 déployée ; harnais repatché par ce script (mêmes patchs, RO_EXACT).
# Ordre : contrôle court du vrai harnais (CTLP5, 3 jeux, 6 min), manifeste, attente de AUTORISE_P5 contenant le SHA-256 du manifeste, puis ABBA.
# Sortie : /workspace/bancs/abba_porte5.FINI (4 passages, code 0) ; sinon abba_porte5.INCOMPLET. N'arrête pas le pod.
set -uo pipefail
cd "$(dirname "$0")/../.."
D=$PWD; W=/workspace; mkdir -p $W/bancs $W/runs
PASSAGES="PR1 P51 P52 PR2"; PAQ=$D/experiments/GEL27_moteur_seul_v2
j() { echo "$(date '+%d/%m %H:%M') abba_porte5 : $*" | tee -a $W/runs/chaine_etapes.txt; }
incomplet() { echo "$*" > $W/bancs/abba_porte5.INCOMPLET; j "INCOMPLET : $* — verdict suspendu"; exit 1; }
[ -f $PAQ/livraison_p1/code/agent_p1/jouer.py ] || incomplet "paquet v4 absent"
(cd $PAQ && sha256sum -c SHA256SUMS --quiet) || incomplet "paquet v4 altéré"
for p in patcher_franzen patcher_garde patcher_outils patcher_faits; do python3 scripts/arc3/$p.py $W/harnais > /dev/null || incomplet "$p"; done
A=$W/harnais/inference
cmp -s chrysalide/arc3/porte_v5_enfant.py $A/chrysalide_arc3/porte_v5_enfant.py || incomplet "enfant du harnais ≠ dépôt"
grep -q "CHRYSALIDE-GARDE" $A/framework/solver.py || incomplet "garde absente du harnais"
grep -q "CHRYSALIDE-PERCEPTION" $A/agent/tool_agent.py && incomplet "patch perception présent"
for n in $PASSAGES; do
  [ -e $W/runs/$n ] && incomplet "dossier $W/runs/$n déjà présent"
  for f in scripts/pod/env_$n.sh scripts/pod/apres_$n.sh; do [ -e "$f" ] && incomplet "$f présent"; done
done
rm -f $W/bancs/abba_porte5.FINI $W/bancs/abba_porte5.INCOMPLET $W/bancs/AUTORISE_P5  # une autorisation ne survit pas à un lancement
[ -e $W/runs/CTLP5 ] && incomplet "dossier $W/runs/CTLP5 déjà présent"
COMMUN="CHRYS_OUTILS=1 CHRYS_OUTILS_APRES=40 CHRYS_FAITS=0 CHRYS_FAITS_APRES=40 CHRYS_GARDE_MUR_S=1800 CHRYS_HISTORIQUE_FIDELE=1 CHRYS_PORTE_V4=0 CHRYS_MONITEUR=0 CHRYS_REFLEXES=0 CHRYS_ROUTEUR=0 CHRYS_VERIF=0 CHRYS_GRAPHE=0 CHRYS_BUDGET=0 CHRYS_MOTEUR=0 ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48"
RO="$COMMUN CHRYS_PORTE5=0 CHRYS_STAGNATION_COUPS=0"
P5="$COMMUN CHRYS_PORTE5=1 CHRYS_STAGNATION_COUPS=40 CHRYS_PORTE_V4_PAQUET=$PAQ CHRYS_PORTE5_ENFANTS=10 CHRYS_PORTE5_BUDGET=150 CHRYS_PORTE5_REPET_MAX=3 CHRYS_PORTE5_ATTENTE_S=90 CHRYS_PORTE5_MUR_S=300 CHRYS_PORTE5_STRICT=0"
controle() {  # vrai harnais, vrai GPU, avant de figer : la porte joue, l'historique revient une fois, aucun drapeau perdu
  bash scripts/pod/bloc.sh CTLP5 $P5 MAX_RUNTIME_MINUTES=6 -- '["g50t","ka59","re86"]' > $W/runs/CTLP5.log 2>&1 < /dev/null
  [ -f $W/runs/CTLP5/FINI ] || incomplet "contrôle court : FINI absent"
  verifier_env CTLP5 $P5
  python3 scripts/pod/controle_porte5.py $W/runs/CTLP5 > $W/runs/CTLP5.verdict.json || incomplet "contrôle court : $(cat $W/runs/CTLP5.verdict.json)"
}
verifier_env() { local r=$1; shift; for e in "$@"; do case $e in MAX_RUNTIME*) ;; *) grep -qxF "$e" $W/runs/$r/env.txt || case $e in ARC3_*|CHRYS_*) incomplet "$r : drapeau non effectif $e";; esac;; esac; done; }
controle
{ echo "depot_commit $(cat COMMIT_SOURCE 2>/dev/null || echo inconnu)"; echo "lanceur_sha256 $(sha256sum scripts/pod/abba_porte5.sh | cut -c1-64)"
  echo "paquet_sha256 $(sha256sum $PAQ/SHA256SUMS | cut -c1-64)"; echo "franzen $(cat $W/franzen.commit)"
  echo "modele_poids_sha256 $(cd $W/modele && ls *.safetensors 2>/dev/null | sort | xargs -r sha256sum | sha256sum | cut -c1-64)"
  echo "harnais_py_sha256 $(cd $W/harnais && find . -path ./.venv -prune -o -type f -name '*.py' -print | sort | xargs sha256sum | sha256sum | cut -c1-64)"
  echo "flux_llm_actifs $(grep ARC3_MAX_ACTIVE_STREAMS scripts/pod/franzen_env.sh | cut -d"'" -f2)"
  nvidia-smi --query-gpu=name,memory.total,driver_version,power.limit --format=csv,noheader; nproc; free -g | head -2
  echo "controle_court $(cat $W/runs/CTLP5.verdict.json)"
  echo "RO: $RO"; echo "P5: $P5"; } > $W/manifeste_abba_porte5.txt
SIG=$(sha256sum $W/manifeste_abba_porte5.txt | cut -c1-64)
j "manifeste écrit ($SIG) ; attente de AUTORISE_P5 contenant ce SHA (revue Codex)"
(while [ ! -f $W/bancs/abba_porte5.FINI ] && [ ! -f $W/bancs/abba_porte5.INCOMPLET ]; do echo "$(date +%s) $(free -m | awk '/Mem:/{print $3}') $(pgrep -fc porte_v5_enfant)"; sleep 60; done >> $W/runs/memoire_p5.txt) &
while [ "$(cat $W/bancs/AUTORISE_P5 2>/dev/null | tr -d '[:space:]')" != "$SIG" ]; do [ -f $W/bancs/STOP_P5 ] && incomplet "STOP avant PR1"; sleep 30; done
for n in $PASSAGES; do
  [ -f $W/bancs/STOP_P5 ] && incomplet "STOP avant $n"
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || incomplet "moins de 4 Go libres avant $n"
  case $n in P5*) a=($P5);; *) a=($RO);; esac
  j "début $n"
  bash scripts/pod/bloc.sh $n "${a[@]}" > $W/runs/$n.log 2>&1 < /dev/null
  code=$?
  verifier_env $n "${a[@]}"
  j "fin $n (code $code)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" ! -name "*_trace*" -print0 | xargs -0 -r gzip -6
  [ $code -eq 0 ] && [ -f $W/runs/$n/FINI ] || incomplet "$n : code $code ou FINI absent"
done
touch $W/bancs/abba_porte5.FINI; j "quatre passages complets — rapatrier puis détruire le pod"
