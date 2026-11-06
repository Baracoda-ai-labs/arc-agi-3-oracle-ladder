#!/usr/bin/env bash
# SUR LE POD B : 2ᵉ lot P1-b (CCM-094-B : boucle de correction + surprise ls20 L3 + format), après le 1ᵉʳ.
W=/workspace; T=$W/chrysalide3/experiments/T3.3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/bancs/nord_etapes.txt; }
until grep -q "fin P1-b" $W/bancs/nord_etapes.txt 2>/dev/null; do sleep 30; done
mkdir -p $T/lot1_pod && cp -r $T/resultats_pod.json $T/raw_pod $T/lot1_pod/ 2>/dev/null; cp $W/bancs/creneau_llm.log $T/lot1_pod/ 2>/dev/null
curl -sf http://127.0.0.1:8011/health >/dev/null || { j "serveur absent : 2ᵉ lot sauté"; exit 1; }
j "début P1-b lot 2 (correction + surprise ls20 L3 + format)"
cd $W/chrysalide3 && timeout 4200 env PYTHONPATH=$W/chrysalide3 PY=$W/harnais/.venv/bin/python bash experiments/T3.3/creneau_llm.sh > $W/bancs/creneau_llm2.log 2>&1
j "fin P1-b lot 2 (code $?)"
