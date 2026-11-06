#!/usr/bin/env bash
# SUR LE POD : lance un banc CPU d'une autre session (CW-120 : délester le Mac) sous les garde-fous de CCM-097-A.
# Usage : bash scripts/pod/lancer_lot.sh <nom> <commande…>   (exécutée dans /workspace/chrysalide3)
# Garde-fous : nice 19, 1 fil BLAS, ulimit -v 6 Go PAR PROCESSUS, et un gardien qui tue le lot si la mémoire anonyme du
# conteneur dépasse 150 Go (le serveur SGLang passe avant). Journal : /workspace/bancs/<nom>.log ; fin : <nom>.FINI (code).
cd "$(dirname "$0")/../.."
nom=$1; shift
LOT_VMEM_KO=${LOT_VMEM_KO:-6000000}   # mémoire virtuelle par processus (Ko) ; 16 Go pour les bancs P0 à 1 000 000 nœuds
L=/workspace/bancs; mkdir -p $L
cat > $L/$nom.cmd <<FIN
cd /workspace/chrysalide3
ulimit -v ${LOT_VMEM_KO:-6000000}
export PYTHONPATH=/workspace/chrysalide3:/workspace/pylib:\${PYTHONPATH:-} OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PATH=/workspace/harnais/.venv/bin:\$PATH nice -n 19 $*
echo "code \$?" > $L/$nom.FINI
FIN
rm -f $L/$nom.FINI
setsid nohup bash $L/$nom.cmd > $L/$nom.log 2>&1 < /dev/null &
pid=$!
setsid nohup bash -c "while kill -0 $pid 2>/dev/null; do
  a=\$(grep -E '^anon ' /sys/fs/cgroup/memory.stat | cut -d' ' -f2)
  if [ \"\$a\" -gt 150000000000 ]; then pkill -g \$(ps -o pgid= $pid | tr -d ' '); echo \"\$(date) $nom tué : anon=\$a\" >> $L/gardien.log; fi
  sleep 10; done" > /dev/null 2>&1 < /dev/null &
echo "$nom lancé (pid $pid)"
