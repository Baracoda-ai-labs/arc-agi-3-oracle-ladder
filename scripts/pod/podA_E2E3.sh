#!/usr/bin/env bash
# SUR LE POD A (CW-170) : après F14 g1, F14 g2-g3 SUSPENDUS (marqueurs FINI « suspendu », lus par apres_H.sh) ; puis E2E3
# = V1 (boucle à étages) + films, mêmes 5 jeux, 60 min par jeu, serveur Flash-Next relancé à 10 requêtes comme E2E1/E2E2.
W=/workspace; R=$W/chrysalide3
j() { echo "$(date '+%d/%m %H:%M') $*" | tee -a $W/runs/chaine_etapes.txt; }
for g in 2 3; do mkdir -p $W/runs/F14_g$g && echo "suspendu (CW-170) : pod A réaffecté à E2E3" > $W/runs/F14_g$g/FINI; done
until [ -f $W/runs/F14/FINI ] || [ -f $W/runs/F14/ARRET ]; do sleep 30; done
sleep 120   # laisse apres_H.sh constater F14_g2/g3 « déjà faits » et finir
for p in $(pgrep -f "sglang serve"); do kill "$p"; done; sleep 20   # serveur à 14 requêtes → relancé à 10 par bloc.sh
unset SGL_MAXREQ
$W/harnais/.venv/bin/python -c "import clingo" 2>/dev/null || uv pip install -q --python $W/harnais/.venv/bin/python "clingo>=5.8.2"
python3 $R/scripts/arc3/patcher_franzen.py $W/harnais > /dev/null && j "harnais repatché (films, boucle)"
j "début E2E3 (V1 + films), pod A"
cd $R && bash scripts/pod/bloc.sh E2E3 CHRYS_MOTEUR=1 CHRYS_TUTO=1 CHRYS_MOTEUR_CLE=1 CHRYS_BOUCLE=1 MAX_RUNTIME_MINUTES=60 -- '["ls20","sk48","sp80","ft09","tr87"]'
j "fin E2E3 (code $?)"
