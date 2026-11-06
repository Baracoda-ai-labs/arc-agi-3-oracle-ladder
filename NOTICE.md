# Third-party components

Everything in this repository is released under MIT-0 (`LICENSE`), except as stated here.

| Component | Licence | Source | Use here |
|---|---|---|---|
| Daniel Franzen's ARC-AGI-3 solution | Apache-2.0 (`LICENSE-APACHE-2.0`) | github.com/da-fr/arc-agi-3-solution, revision 10882e33 | Base of the submitted Kaggle notebook. **Not included.** It is fetched by `scripts/pod/setup_franzen.sh` and modified by `scripts/arc3/patcher_*.py`; those patchers quote short fragments of it and are therefore `MIT-0 AND Apache-2.0`, our modifications being marked as required by Apache-2.0 §4(b). |
| Tufa Labs "Duck" harness | no licence file upstream | github.com/Tufalabs/duck-harness | **Not included.** `chrysalide/arc3/duck.py` is a clean-room reimplementation under MIT-0. |
| ARC-AGI-3 games, PuzzleScript games, model weights, Python dependencies | their own licences | ARC Prize Foundation; PuzzleScript authors; see `pyproject.toml` / `uv.lock` and the Kaggle notebook inputs | **Not redistributed.** Scripts that need the game files expect them under `experiments/arc3/environment_files/` (from the `arc-agi` package). |
