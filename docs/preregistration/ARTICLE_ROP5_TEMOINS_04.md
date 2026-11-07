# ARTICLE-ROP5-5x2 — preregistration, 4 November 2026 (Cowork; Thomas approval 4 Nov 17:30)

**Question.** Does the linked submission ROP5 (RO + gate P5, score variant) lose or gain on the five held-out games relative to RO measured with the same pod protocol (ARTICLE_RO_TEMOINS_03, attempt 2, ten-slot mean 42.98)?

**System.** Identical to ARTICLE_RO_TEMOINS_02/03 (Franzen 10882e33, v7 patch sequence, same model `albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE` at MODEL_REVISION c6af9fee, weights fingerprint d1b06032, 10 streams, 48 min per passage, native RESET) **plus exactly the P5 settings of the public ABBA P5 arms and of the ROP5 v9 submission**: CHRYS_PORTE5=1, STRICT=0, CHRYS_STAGNATION_COUPS=40, HISTORIQUE_FIDELE=1, other P5 parameters as in manifest dd5c3ef8 / package 9fd51b30. E1 records the effective flags in the manifest before any game; any difference from ROP5 v9 is a deviation to report.

**Population and order.** vc33, tu93, wa30, s5i5, cn04; passages TM1, TM2; fresh run directories; no memory carried between passages.

**Predictions (frozen before rental).**
1. Ten-slot mean of native scores ≤ 42.98 (the gate does not improve on held-out games). Point forecast: 38/100.
2. Levels attributed to the engine (actions played by the P5 child that end with a level change) on the held-out games: 0 in both passages.
3. The engine opens on every game at start (motif « depart ») and at least once more in at least 3 of 5 games per passage.
Comparison with RO attempt 2 is descriptive (different day and instance); report per game and the ten-slot difference without a significance claim.

**Metric, denominator, failures.** As in 02 §4: native per-game scores, ten slots, missing slots count zero in the primary aggregate and are reported separately. Secondary: levels, actions, engine openings, engine actions, engine-attributed levels (from P5 traces), runtime.

**Execution and cost.** E1 sole executor, garde v2 (ad54a1a0 or later, unchanged thresholds logic): gameplay stop 6.5 USD, full stop and self-destruction 7.0 USD, abort if no game manifest 2 h after rental, heartbeat relayed to BATTEMENT_TEMOINS.txt, self-destruction after retrieval. Ceiling 7 USD from existing credit (11.05 USD), no top-up. One attempt; no relaunch of failed slots; if setup fails before any game, report and stop (a new decision by Thomas is required for another attempt).

**Reporting.** ≤ 80 lines, CSV per slot, spend, deviations; Cowork integrates into the paper whatever the outcome.
