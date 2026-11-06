#!/usr/bin/env bash
# SUR LE POD (CW-307) : bras « profondeur » (< 1 Go) sur les 7 autres niveaux frontière, 30 000 s, copie figée b100_copie.
W=/workspace; C=$W/b100_copie; O=$W/runs/b100/x100; mkdir -p $O
for g in ka59:4 ls20:4 re86:5 lf52:3 sc25:5 su15:4 bp35:2; do
  n=${g%%:*}; k=${g##*:}
  ( cd $C && nice -n 10 env PYTHONPATH=. CHRYSALIDE_DONNEES=$W/chrysalide3 $W/harnais/.venv/bin/python \
      experiments/instrument/budget100.py $n $k profondeur 30000 $O/${n}_${k}_profondeur.json 4 > $O/${n}_${k}_profondeur.out 2>&1 ) &
done
wait; touch $W/bancs/profondeur7.FINI
