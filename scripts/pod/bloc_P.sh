#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD — bloc P (CW-040, amendement `experiments/arc3/prereg_S2_amendement_P.md`) : perception adaptative
# (image ×10 en découverte, ×4 au calme) dans le harnais de Franzen, 25 jeux publics, 1 passage par répétition.
# Écrit par la session B ; appelé sans argument par scripts/pod/chaine_nuit.sh (session A), qui sert le modèle, borne
# la durée et arrête le pod. Chaque répétition passe par scripts/pod/bloc.sh (mêmes réglages que R0 : franzen_env.sh,
# MULTIMODAL_UPSCALE=10) avec CHRYS_PERCEPTION=1 ; le témoin « sans » est R0.
# Le patch est posé dans /workspace/harnais lui-même : idempotent, éteint par défaut (F-C2 : Franzen inchangé), et le
# bloc FC2 de la chaîne le contrôle ensuite avec le reste.
# GRAINES="1" par défaut : la chaîne de nuit (limite 9 h, ≈ 2 h 15 par bloc) ne tient pas 3 répétitions avec V1, FC2, V2.
# 1 répétition = indicative, sans décision (amendement P) ; GRAINES="1 2 3" quand le budget le permet. Reprise : sauté si FINI.
set -uo pipefail
cd "$(dirname "$0")/../.."
W=/workspace
GRAINES=${GRAINES:-"1"}
[ -d "$W/harnais" ] || { echo "ARRÊT : $W/harnais absent, lancer d'abord scripts/pod/setup_franzen.sh"; exit 1; }
python3 scripts/arc3/patcher_perception.py "$W/harnais" || exit 1
for g in $GRAINES; do
  nom="P_avec_g${g}"
  [ -f "$W/runs/$nom/FINI" ] && { echo "déjà fait : $nom"; continue; }
  bash scripts/pod/bloc.sh "$nom" CHRYS_PERCEPTION=1 CHRYS_PERC_CALME=2 CHRYS_PERC_STAGNATION=5 CHRYS_PERC_BASSE=4 \
    || echo "ÉCHEC $nom (voir $W/runs/$nom)"
done
python3 experiments/T2.3c/resume_bloc_P.py "$W/runs" | tee "$W/runs/bloc_P_resume.txt"
echo "BLOC P TERMINÉ"
