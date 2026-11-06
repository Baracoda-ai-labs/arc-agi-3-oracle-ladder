#!/usr/bin/env bash
# SUR LE MAC (CW-408, Thomas « Oui » 22/10 : pod prolongé du 25 au 30/10, 12 h par jour). Relance matinale du pod arrêté le soir.
# Usage : bash scripts/pod/reveil_mac.sh etat     → état du pod (lecture seule)
#         bash scripts/pod/reveil_mac.sh reveil   → reprend le pod (1 GPU), attend SSH, met à jour configs/pod_ssh.txt (même pod,
#                                                    port relevé), relance l'installation idempotente, le serveur et l'arrêt du soir.
# Clé : ~/.runpod/config.toml (déjà présente), passée en en-tête Authorization, jamais dans l'URL ni dans un journal.
set -euo pipefail
POD=okm0nd2f3e4jc5
R=$(cd "$(dirname "$0")/../.." && pwd)
J=$R/runs_pod/reveil.log
CLE=$(sed -n "s/^apikey *= *['\"]\{0,1\}\([^'\"]*\).*/\1/p" ~/.runpod/config.toml)
gql() { curl -sf -H "Content-Type: application/json" -H "Authorization: Bearer $CLE" \
          -d "$(python3 -c 'import json,sys; print(json.dumps({"query": sys.argv[1]}))' "$1")" https://api.runpod.io/graphql; }
etat() { gql "query { pod(input: {podId: \"$POD\"}) { id desiredStatus lastStatusChange costPerHr gpuCount
                runtime { uptimeInSeconds ports { ip isIpPublic publicPort privatePort type } } } }"; }
case "${1:-etat}" in
  etat) etat | python3 -m json.tool ;;
  reveil)
    echo "$(date '+%d/%m %H:%M') reveil : reprise demandée" >> "$J"
    gql "mutation { podResume(input: {podId: \"$POD\", gpuCount: 1}) { id desiredStatus } }" >> "$J" || {
      echo "$(date '+%d/%m %H:%M') reveil : ÉCHEC de la reprise (GPU indisponible ?)" >> "$J"; exit 1; }
    for _ in $(seq 60); do  # jusqu'à 30 min
      P=$(etat | python3 -c 'import json,sys
r = json.load(sys.stdin)["data"]["pod"].get("runtime") or {}
p = [x for x in r.get("ports") or [] if x["privatePort"] == 22 and x["isIpPublic"]]
print(p[0]["ip"], p[0]["publicPort"]) if p else print("")' 2>/dev/null || true)
      [ -n "$P" ] && break; sleep 30
    done
    [ -n "$P" ] || { echo "$(date '+%d/%m %H:%M') reveil : pas de port SSH après 30 min" >> "$J"; exit 1; }
    set -- $P; IP=$1; PORT=$2
    sed -i '' "s/^chrysalide-arc3 .*/chrysalide-arc3 $IP $PORT/" "$R/configs/pod_ssh.txt"
    echo "$(date '+%d/%m %H:%M') reveil : SSH $IP:$PORT (pod_ssh.txt mis à jour)" >> "$J"
    for _ in $(seq 20); do ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -p "$PORT" root@"$IP" true 2>/dev/null && break; sleep 15; done
    ssh -p "$PORT" root@"$IP" 'cd /workspace/chrysalide3 && nohup bash scripts/pod/demarrage_jour.sh > /workspace/runs/demarrage_jour.log 2>&1 < /dev/null &'
    echo "$(date '+%d/%m %H:%M') reveil : demarrage_jour.sh lancé" >> "$J" ;;
esac
