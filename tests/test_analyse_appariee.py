import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "aa", Path(__file__).resolve().parents[1] / "experiments/arc3/analyse_appariee.py")
aa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aa)


def bloc(d, scores, coups_par_tour, appels=0, duree_s=3600):
    (d / "run" / "artifacts").mkdir(parents=True)
    games = [{"game_id": f"{j}-abc", "score": s, "levels_completed": s / 10, "total_levels": 6} for j, s in scores.items()]
    (d / "run" / "evaluation.json").write_text(json.dumps({"games": games}))
    for j in scores:
        ev = []
        for t in range(1, 4):
            code = "x = 1\n" + "chrys_aller(['RIGHT'])\n" * appels
            ev.append({"type": "analysis", "analysis_step": t,
                       "transcript": f"--- analysis_step={t} | 10:0{t}:00 | tool-agent ---\n[SYSTEM PROMPT]\nUse chrys_aller(pas) "
                                     f"to move.\n[ASSISTANT]\n<parameter=code>\n{code}</parameter>"})
            ev += [{"type": "action", "action_name": "ACTION4", "analysis_step": t} for _ in range(coups_par_tour)]
        ev.append({"type": "action", "action_name": "RESET", "analysis_step": 4})
        (d / "run" / "artifacts" / f"{j}-abc_p0_events.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    (d / "util.csv").write_text(f"# cpu.max=1\nt\tgpu\n0\t90\n{duree_s}\t95\n")


def test_comparaison_appariee(tmp_path):
    bloc(tmp_path / "R0", {"ls20": 10.0, "ft09": 0.0, "vc33": 5.0}, 2)
    bloc(tmp_path / "V2p", {"ls20": 12.0, "ft09": 0.0}, 1, appels=2, duree_s=1800)
    ref, rh = aa.lire_bloc(tmp_path / "R0")
    b, bh = aa.lire_bloc(tmp_path / "V2p")
    assert ref["ls20"]["coups"] == 6 and ref["ls20"]["tours"] == 3 and rh == 1.0
    assert b["ls20"]["chrys_aller"] == 6 and b["ls20"]["tours_outil"] == 3  # la consigne hors code ne compte pas
    assert ref["ls20"]["chrys_aller"] == 0
    md = aa.comparer(ref, rh, b, bh, "V2p")
    assert "1 mieux, 1 égaux, 1 moins bien" in md  # vc33 absent de V2p = RHAE 0 (population entière)
    assert "tours/heure : 9 -> 12 (+33 %)" in md
    assert "| vc33 | 5.00 | 0.00 | -5.00 |" in md
