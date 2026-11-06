#!/usr/bin/env bash
# SUR LE POD (CW-305) : test plafond « budget ×100 » : 6 niveaux frontière × 3 bras (but, sous_buts, profondeur), 30 000 s,
# sans plafond de nœuds, garde mémoire 8 Go par processus (but, sous_buts) ; G allumé (défaut). Après R0h (GPU libre).
W=/workspace; C=$W/b100_copie; O=$W/runs/b100/x100; mkdir -p $O
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
while [ ! -f $W/bancs/r0gh.FINI ]; do sleep 60; done
j "budget100 : départ, anon $(awk '/^anon /{print int($2/2^30)}' /sys/fs/cgroup/memory.stat) Go"
for g in g50t:1 sk48:2 sp80:4 m0r0:6 tr87:6 dc22:4; do for b in but sous_buts profondeur; do
  n=${g%%:*}; k=${g##*:}
  ( cd $C && nice -n 10 env PYTHONPATH=. CHRYSALIDE_DONNEES=$W/chrysalide3 $W/harnais/.venv/bin/python \
      experiments/instrument/budget100.py $n $k $b 30000 $O/${n}_${k}_$b.json 8 > $O/${n}_${k}_$b.out 2>&1 ) &
done; done
wait; touch $W/bancs/budget100.FINI; j "budget100 fini"
