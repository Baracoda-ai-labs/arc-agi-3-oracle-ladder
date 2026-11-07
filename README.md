# ARC-AGI-3 oracle ladder — code and data

Companion release of the ARC Prize 2026 Paper Prize submission
**"Where Model-Based Agents Fail on ARC-AGI-3: A Stage-wise Diagnostic Audit"** (PDF: [`paper/Serval_ARC-AGI-3_stagewise_audit.pdf`](paper/Serval_ARC-AGI-3_stagewise_audit.pdf)) — Thomas Serval (NEOMA Business School; Baracoda AI Labs).

- Linked Kaggle submission (ROP5): https://www.kaggle.com/code/thomasserval/arc-agi-3-milestone-2-solution (version 9)
- Licence: MIT-0 for our code (`LICENSE`); third-party components are listed in `NOTICE.md` and are **not** redistributed.
- Status: research code, released as used for the paper (comments and identifiers are mostly in French). It is a snapshot, not a maintained library.

## Where each claim of the paper lives

| Paper | Files |
|---|---|
| Declarative game language (protocol, 17 contracts, read/write sets) | `chrysalide/langue/` (`ontologie_formelle.py`, `theorie_contrats.py`, `roles.py`), `docs/ONTOLOGIE.md` |
| Exact programs of the 20 public games, 4,127/4,127 transitions | `experiments/T3.1/regles/*.json`, `experiments/T3.1/jeux/*.md`, `experiments/T3.1/mesure_exhaustivite.py`, `exhaustivite.json` |
| PuzzleScript interpreter written in the language, 177 games / 38,924 moves | `experiments/ps_langage/` (`construire_interpreteur.py`, `juge_ps.py`, `resultats/`, `report.md`) |
| Proposition 2: independence from read/write sets (24/24 sound, 0/311 false) | `chrysalide/langue/independance.py`, `experiments/meta_modele/independance_mesure.py`, `independance.json` |
| Proposition 1: sufficiency / observed-ambiguity detector (KA59) | `experiments/oracle/suffisance_etat.py`, `suffisance_etat.md` |
| Rung (b′): goal-directed search with exact rules (27/60) and pruning tests | `experiments/G/astar_but.py`, `banc_p0.py`, `p0_but_1000000_300*.json`, `report.md` |
| Rung (a): online engine v4 (perception, transition model, inventor, planner) | `chrysalide/arc3/` (`moteur.py`, `moteur_processus.py`, `porte_v4.py`, `perception*.py`, `logique/`) |
| ROP5 gate (engine child process inside the LLM agent) | `chrysalide/arc3/porte_v5.py`, `porte_v5_enfant.py`, `scripts/arc3/faire_notebook_S.py`, `scripts/pod/controle_porte5.py` |
| RO tools added to Franzen's notebook | `scripts/arc3/patcher_*.py` (`MIT-0 AND Apache-2.0`), `chrysalide/arc3/outils_repl.py` |
| Loss map, fixed-prefix judge, repairs (KA59, SK48, TN36) | `experiments/reparation_blocage/*.py`, `experiments/instrument/` |
| Ladder results: public games (RO = PR1/PR2, ROP5 = P51/P52) and held-out games | `ladder_data/` (`summary.txt` per run; `temoins_rop5_04/cases.csv`) |

## Reproducing

1. Python 3.12 with `uv sync` (see `pyproject.toml`, `uv.lock`); the ARC-AGI-3 games come from the `arc-agi` package and are expected under `experiments/arc3/environment_files/` (not redistributed).
2. Engine and language checks run on CPU in minutes (the engine plays the 20 public games in about 74 s of CPU). Example: `uv run pytest tests -q`.
3. LLM rungs (RO, ROP5) need one large GPU (we used an RTX PRO 6000, about 48 min for 20 games) and the Kaggle notebook inputs; the simplest route is to run the public Kaggle notebook above.

Approximate total compute cost of the project: under 400 EUR of rented GPU; no paid LLM API; no training.
