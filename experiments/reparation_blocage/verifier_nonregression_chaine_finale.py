"""Compare causalement les décisions finales aux films de victoires archivées.
Aucun SDK : les observations injectées sont exclusivement des preuves sur traces.
"""

import argparse
import json
import signal
import time
from pathlib import Path

import numpy as np
from boucle_agent_integree import empreintes
from chaine_agent_integree import AgentIntegre
from issues_observees import issue_sdk

R = Path(__file__).parent
CAS = {
    "ar25": "multijeux_nuit_integre1/ar25/N1/partie",
    "ka59": "freinage_commun_ka59_1/reel/N1/partie",
}


def sauver(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=int))


def verifier(nom, sortie):
    source = R / "runs" / CAS[nom]
    with np.load(source.with_suffix(".npz")) as archive:
        images = archive["images"].copy()
        rows = json.loads(source.with_suffix(".json").read_text())["rows"]
        films = [archive[f"film_{i + 1}"].copy() for i in range(len(rows))]
    actions = [r["action"] for r in rows]
    issues = [issue_sdk(r["state"], r["levels_completed"], 0) for r in rows]
    out = sortie / nom
    out.mkdir(parents=True, exist_ok=False)
    hashes = empreintes()
    sauver(out / "sources.json", hashes)
    debut = time.monotonic()
    a = AgentIntegre(images[:9], actions[:8], films[:8], issues[:8])
    comparisons = []
    statut = "incomplet"

    def timeout(_sig, _frame):
        raise TimeoutError("Budget archive 60s")

    old = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        for n in range(8, len(actions)):
            folder = out / f"decision_{n:03d}"
            folder.mkdir()
            prefix = folder / "prefixe"
            # Aucun fichier transmis au moteur/proposeur ne contient le suffixe.
            np.savez_compressed(
                prefix.with_suffix(".npz"), images=images[: n + 1], **{f"film_{i + 1}": films[i] for i in range(n)}
            )
            sauver(prefix.with_suffix(".json"), {"rows": [{"action": act} for act in actions[:n]]})
            d = a.decider([1, 2, 3, 4, 6], folder, prefix, secondes=min(30, 60 - (time.monotonic() - debut)))
            sauver(folder / "decision.json", d)
            identique = bool(d.get("actions")) and d["actions"][0] == actions[n]
            comparisons.append(
                {
                    "coup": n + 1,
                    "action_predite": d.get("actions"),
                    "action_archive": actions[n],
                    "identique": identique,
                    "prefixe_actions": n,
                    "prefixe_images": n + 1,
                    "prefixe_films": n,
                }
            )
            if not identique:
                statut = "premiere_difference"
                break
            # Jamais présenté comme une nouvelle exécution ou victoire SDK.
            observation = a.observer(actions[n], images[n + 1], films[n], issues[n])
            sauver(folder / "observation_sur_trace.json", {"verification": "trace_archivee_sans_SDK", "observation": observation})
        else:
            statut = "decisions_identiques_jusqua_issue_archivee"
    except TimeoutError:
        statut = "budget_archive"
    except (ValueError, KeyError, TypeError, IndexError, RuntimeError, OSError, AssertionError) as e:
        statut = "erreur"
        sauver(out / "erreur.json", {"erreur": repr(e)})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    bilan = {
        "cas": nom,
        "statut": statut,
        "verification": "traces_uniquement",
        "nouvelles_actions_reelles": 0,
        "nouvelles_victoires_reelles": 0,
        "decisions_comparees": len(comparisons),
        "actions_identiques": sum(x["identique"] for x in comparisons),
        "issue_archivee": issues[-1],
        "secondes": time.monotonic() - debut,
        "sources_inchangees": hashes == empreintes(hashes),
        "comparaisons": comparisons,
    }
    sauver(out / "bilan.json", bilan)
    print(json.dumps({k: v for k, v in bilan.items() if k != "comparaisons"}), flush=True)
    return bilan


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--cas", choices=CAS, required=True)
    args = ap.parse_args()
    verifier(args.cas, args.sortie)
