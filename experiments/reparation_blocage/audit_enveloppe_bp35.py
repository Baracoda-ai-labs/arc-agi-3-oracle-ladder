import argparse
import json
from pathlib import Path

from enveloppe_contacts import analyser
from interventions_elargies import InterventionsElargies
from perception_hierarchique import decomposer
from preflight_interventions_bp35 import charger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    out = ap.parse_args().sortie
    out.mkdir(parents=True, exist_ok=False)
    _m, h, cs, z, _rows, _known = charger()
    model = InterventionsElargies(z["images"][1], h, cs, [3, 4, 6], horizon=8, scene_factory=lambda im, m: decomposer(im, m)[0])
    result = analyser(model)
    (out / "rapport.json").write_text(json.dumps(result, indent=2, default=int))
    print(json.dumps({k: v for k, v in result.items() if k not in ("aretes", "separateurs")}, default=int))


if __name__ == "__main__":
    main()
