#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
# SUR LE POD, appelé par bloc.sh à la fin de FC2 (CW-051) : bloc H « historique long » sur le criblage de 10 jeux de B,
# ARC3_CONTEXT_DRAIN_TOKENS 58 Ki → 72 Ki, fenêtre inchangée ; comparé à R0 restreint aux mêmes jeux.
# Ne part que si (1) l'amendement H est présent (scellé par B), (2) le coût cumulé estimé, H compris, reste ≤ 40 €.
cd "$(dirname "$0")/../.."
W=/workspace
journal() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
[ -f experiments/arc3/prereg_S2_amendement_H.md ] || { journal "H sauté : amendement H absent"; exit 0; }
DEBUT_POD=$(date -d "2026-10-17 11:50 UTC" +%s)   # pod migré démarré vers 13 h 50 heure de Paris (CW-044)
heures=$(( ($(date +%s) - DEBUT_POD) / 60 ))
cout=$(python3 -c "print(round(($heures / 60 + 2.4) * 2.52 * 0.86, 1))")   # + ≈ 2 h 25 pour H, 2,52 $/h, 0,86 €/$
python3 -c "import sys; sys.exit(0 if $cout <= 40 else 1)" || { journal "H sauté : coût estimé $cout € > 40 €"; exit 0; }
journal "début H (coût cumulé estimé $cout €)"
bash scripts/pod/bloc.sh H ARC3_CONTEXT_DRAIN_TOKENS=73728 -- '["bp35","lf52","ka59","ls20","re86","sp80","dc22","sc25","tr87","m0r0"]'   # criblage révisé après R0 (B, 17/10)
journal "fin H (code $?)"
