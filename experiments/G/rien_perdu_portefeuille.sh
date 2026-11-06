#!/bin/zsh
# [G] CW-429 : « rien perdu » du portefeuille dans le moteur : moteur seul (experiments/moteur_seul/banc.py), 20 jeux
# publics hors témoins, CHRYS_PORTEFEUILLE_G=0 contre =1, 10 min par partie, graine 0, 4 parties à la fois (nice 10).
cd "$(dirname "$0")/../.."
D=experiments/G/rien_perdu
mkdir -p $D
JEUX=($(ls experiments/T3.1/regles/*.json | xargs -n1 basename | sed 's/.json//' | grep -v _ | grep -v -E '^(vc33|tu93|wa30|s5i5|cn04)$'))
taches=()
for j in $JEUX; do for f in 0 1; do taches+=("$j:$f"); done; done
print -l $taches | xargs -P 4 -I{} zsh -c 'j=${1%:*}; f=${1#*:}; CHRYS_PORTEFEUILLE_G=$f PYTHONPATH=. nice -n 10 .venv/bin/python experiments/moteur_seul/banc.py $j moteur experiments/G/rien_perdu/${j}_pf$f.json 10 0 > experiments/G/rien_perdu/${j}_pf$f.log 2>&1' _ {}
echo FINI > $D/FINI
