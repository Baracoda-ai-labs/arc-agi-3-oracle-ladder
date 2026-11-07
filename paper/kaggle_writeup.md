**Thomas Serval** — NEOMA Business School; Baracoda AI Labs · Linked submission: *ARC-AGI-3 Milestone 2 Solution*, ROP5 (version 9) · Code, data and preregistrations: [github.com/Baracoda-ai-labs/arc-agi-3-oracle-ladder](https://github.com/Baracoda-ai-labs/arc-agi-3-oracle-ladder) (MIT-0)

**Full paper (PDF, 9 pages):** [Serval_ARC-AGI-3_stagewise_audit.pdf](https://github.com/Baracoda-ai-labs/arc-agi-3-oracle-ladder/blob/main/paper/Serval_ARC-AGI-3_stagewise_audit.pdf)

![Figure 1. Oracle comparisons on the first three levels of each game: public development (n = 60) and held-out (n = 15).](https://raw.githubusercontent.com/Baracoda-ai-labs/arc-agi-3-oracle-ladder/main/paper/figure1_ladder.png)

## The question
Frontier systems now solve the public ARC-AGI-3 games by writing world models with cloud LLMs (Tycho, Kepler, Twin, AWM). We asked the opposite question in the offline Kaggle setting: when a local model-based agent fails on a new game, *which stage* fails — recognition, transition modelling, goal inference or search — and which repairs actually help? We built a symbolic engine, gated it inside a local LLM agent, submitted the hybrid, and turned the result into a reusable audit. We joined late: everything was built and measured in about five weeks.

## The system
- **LLM agent (RO):** Franzen's public notebook (local quantised Qwen3.8-Flash-Next, SGLang, Python REPL) plus deterministic tools after 40 stagnant actions.
- **Online engine:** perceives objects, learns a transition model from the consequences of its own actions, plans; no LLM, runs on idle CPU cores.
- **Gate (ROP5):** the engine opens at game start and after 40 stagnant actions, in a child process; the parent checks every engine action and hands back a summary.
- **One declarative language:** 17 mechanism contracts with declared read/write sets. Exact programs replay 4,127/4,127 transitions of the 20 public games; an interpreter written in the language replays 177 human-made PuzzleScript games (38,924/38,924 moves), released as a test bed.

## Results
| First three levels | Public dev (/60) | Held-out (/15) |
|---|---:|---:|
| Engine, model learned from play | 12 | 0 |
| Exact rules + goal-directed search (1 M nodes, 300 s) | 27 | — |
| LLM agent (RO) | 39 | 15 |
| Hybrid (ROP5) | 43.5 | 11.5 |

Public games were used for development and are in-sample; out-of-sample evidence is five held-out public games (preregistered runs, disclosed incidental exposure) and Kaggle's hidden set. On Kaggle, ROP5 scored 22.55 against 27.34 and 29.89 for two identical RO submissions; held-out native scores are 45.50 vs 42.98 (no established difference), but ROP5 wins fewer held-out first-three levels (11.5 vs 15).

**1. The symbolic chain breaks at recognition, before any learning.** The engine's 19 held-out openings inside the hybrid stopped at perception (9), structure recognition (9) or defeat (1); no hypothesis was formed. On 104 generated games outside ARC, a version of the chain wins 5 first levels, with the same refusals.

**2. Repairing recognition moves the failure downstream.** Supplying near-perfect recognition of the controlled object raised the chain's consistent theories about 2.3-fold, yet the levels its interventions won did not rise: the new plans diverged from the real game within their first actions.

**3. Exact rules are not enough.** Our best search with source-derived rules wins 27 early levels against 39 for the LLM agent (game-bootstrap 95 % interval of the difference [1, 23.5]); pruning that cuts search nodes by up to 77 % and a 1.66× faster simulator add no solved level.

**4. Gating on stagnation can hurt.** The engine alone finishes the public game G50T (7/7, no LLM token), but on new games it recognised nothing and the hybrid lost levels on cn04 and wa30, with fewer LLM tool calls in the same time.

## Why — checkable properties and a chain model
The language makes three properties checkable game by game: **sufficiency** (two identical represented states with different successors refute the representation — found on KA59), **independence** (non-interfering read/write sets commute: 24/24 predicted, 0 false in 311 checks) and **distinguishability** (theories differ only where they predict differently — the separating move is found on G50T). Two elementary propositions read the whole chain: **P(win) is the product of stage success probabilities**, so improving one stage is invisible while another fails (results 2 and 3); and **a gate pays only if r > c/g**, so a stagnation-triggered gate loses on games the engine rarely recognises (result 4).

## A reusable audit
Record each stage, find a local counter-example, locate the first transformation that loses information, replace only that step with a controlled reference, replay downstream against an exact off-switch control, and classify the outcome as demonstrated defect, intervention-supported cause or open hypothesis. A complete case: a border gauge breaking state identity on two games was found by a sufficiency collision, fixed in two lines, verified action for action with the fix switched off, and cut tn36 level 1 from 75 to 8 actions with no level lost.

## Recommendations
Test recognition outside the design games before tuning an inducer or planner; judge repairs by levels won, not predictions; open a symbolic component only after a recognition test with few false positives; do not expect faster search to replace sub-goal priors. The whole programme cost under 400 EUR of rented GPU, with no paid API and no training.

**Lesson:** a model-based agent should not be optimised downstream until its representation of the environment has been shown to be adequate — check recognition before investing in reasoning.
