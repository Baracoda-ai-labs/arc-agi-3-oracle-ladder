#!/usr/bin/env bash
# SUR LE MAC (CW-047) : rapatrie /workspace/runs/<bloc>/ du pod vers runs_pod/<bloc>/ (sans les journaux de requêtes, qui
# restent sur le pod, compressés) et écrit le résumé 5 lignes dans runs_pod/<bloc>/resume.txt.
# Usage : bash scripts/pod/rapatrier_bloc.sh <bloc>. Seule cible : le pod de configs/pod_ssh.txt (liste blanche de guard.sh).
set -uo pipefail
cd "$(dirname "$0")/../.."
b=$1
read -r _ ip port < <(grep -v '^#' configs/pod_ssh.txt | head -1)
mkdir -p "runs_pod/$b"
rsync -az --exclude '*_requests.jsonl*' -e "ssh -p $port -i $HOME/.ssh/id_ed25519" "root@$ip:/workspace/runs/$b/" "runs_pod/$b/"
ssh -p "$port" -i "$HOME/.ssh/id_ed25519" "root@$ip" "python3 /workspace/chrysalide3/scripts/pod/resume_bloc.py /workspace/runs/$b" \
  > "runs_pod/$b/resume.txt"
cat "runs_pod/$b/resume.txt"
