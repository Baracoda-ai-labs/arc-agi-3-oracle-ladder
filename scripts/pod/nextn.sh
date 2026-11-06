#!/usr/bin/env bash
# SUR LE POD (CW-364, modification du jeudi 22/10) : vitesse du serveur de Franzen, NEXTN 3 étapes (A, référence de Franzen :
# --speculative-num-steps 3, --speculative-num-draft-tokens 4, eagle-topk 1) contre 2 étapes (B : 2, 3, 1 ; règle « jetons = étapes + 1 »
# de la cellule 12 de Franzen). Une seule variable. ABBA par blocs de 8 : A1 B1 B2 A2 | B3 A3 A4 B4, puis A5… (NEXTN_DEBUT = 1er
# indice, défaut 1), jusqu'à bancs/STOP_N (CW-368 : autant de blocs que la nuit permet). Franzen seul (R), 20 jeux, 48 min.
# Le serveur est relancé quand la variante change (franzen_lanceur.py lit SGL_SPEC_STEPS) ; les arguments réels sont relevés dans
# runs/<passage>/serveur_args.txt ; 3 requêtes fixes à température 0 par variante (contrôle de fidélité, runs/nextn_fidelite_<k>.json).
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
anon() { awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat; }
courant=3
serveur() {  # serveur <k> : relance si la variante change
  local k=$1
  if [ "$k" != "$courant" ] || ! curl -sf http://127.0.0.1:8011/health >/dev/null; then
    j "nextn : arrêt du serveur (variante $courant → $k)"
    touch $W/KEEPALIVE
    cp $W/runs/serve.log $W/runs/serve_avant_nextn_$(date -u +%H%M).log 2>/dev/null   # le lanceur peut réécrire serve.log
    pkill -f "sglang" ; sleep 20; pkill -9 -f "sglang" 2>/dev/null; sleep 10   # serveur et ses enfants sglang::*
    (cd $R && SGL_SPEC_STEPS=$k python3 scripts/pod/franzen_lanceur.py > $W/runs/lanceur_nextn_$k.log 2>&1)
    rm -f $W/KEEPALIVE
    curl -sf http://127.0.0.1:8011/health >/dev/null || { j "nextn : serveur $k ABSENT : ARRÊT"; exit 1; }
    courant=$k; j "nextn : serveur prêt (SGL_SPEC_STEPS=$k)"
  fi
  [ -f $W/runs/nextn_fidelite_$k.json ] || python3 - $k <<'PY'
import json, sys, urllib.request
k = sys.argv[1]
out = []
for q in ["Liste les nombres premiers inférieurs à 30.", "Écris une fonction Python qui inverse une chaîne.",
          "Décris en trois phrases une grille 4x4 avec un carré rouge en haut à gauche."]:
    corps = json.dumps({"model": "flashnext", "messages": [{"role": "user", "content": q}], "temperature": 0, "max_tokens": 96,
                        "chat_template_kwargs": {"enable_thinking": False}}).encode()
    rq = urllib.request.Request("http://127.0.0.1:8011/v1/chat/completions", corps, {"Content-Type": "application/json"})
    out.append(json.loads(urllib.request.urlopen(rq, timeout=300).read())["choices"][0]["message"]["content"])
open(f"/workspace/runs/nextn_fidelite_{k}.json", "w").write(json.dumps(out, ensure_ascii=False, indent=1))
PY
}
b=${NEXTN_DEBUT:-1}
while :; do
 for n in A$b B$b B$((b+1)) A$((b+1)) B$((b+2)) A$((b+2)) A$((b+3)) B$((b+3)); do
  [ -f $W/bancs/STOP_N ] && { j "nextn : STOP_N avant $n"; break 2; }
  [ "$(date -u +%s)" -ge "$(date -u -d '2026-10-24 04:50' +%s)" ] && { j "nextn : 24/10 04:50 UTC"; break 2; }
  [ "$(df --output=avail -BG $W | tail -1 | tr -dc 0-9)" -ge 4 ] || { j "nextn : moins de 4 Go libres avant $n"; break 2; }
  case $n in A*) serveur 3;; B*) serveur 2;; esac
  j "nextn : début $n (SGL_SPEC_STEPS=$courant) anon $(anon) Go"
  mkdir -p $W/runs/$n; ps -eo args | grep "[s]glang serve" | head -1 > $W/runs/$n/serveur_args.txt
  cd $R && bash scripts/pod/bloc.sh $n ARC3_SUMMARY_INTERVAL_TOKENS=0 MAX_RUNTIME_MINUTES=48 > $W/runs/$n.log 2>&1 < /dev/null
  j "nextn : fin $n (code $?)"
  find $W/runs/$n -type f \( -name "*.jsonl" -o -name "*.log" \) -size +20k ! -name "*events*" -print0 | xargs -0 -r gzip -6
 done
 b=$((b+4))
done
serveur 3; touch $W/bancs/nextn.FINI; j "nextn fini (serveur remis à 3 étapes)"
