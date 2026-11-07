# ARTICLE-RO-5x2 — final prospective protocol, 2 November 2026

**Status: preregistration for the two passages explicitly authorised by Thomas, recorded by Cowork on 2 November at22:10.** This replaces the proposed GEL27/no-RESET experiment. E1 is the sole executor; Codex does not rent, launch or duplicate it. Execution follows this committed protocol and the preflight gates below, without another outcome-dependent approval. Any failed preflight is reported, not silently repaired by changing the scientific configuration.

## 1. Question and tested system

Measure native ARC scores for RO's submitted policy on five held-out games with disclosed incidental exposure, twice under a fixed pod harness. This is a descriptive evaluation of RO, **not** a comparison of repaired versus unrepaired engines, not a new Kaggle submission, and not a causal test of tools. The two runs are repetitions of the same policy, not treatment and control.

Reference notebook: `thomasserval/arc-agi-3-milestone-2-solution`, v7 d00a64a6, native scriptVersionId363160941; completed public scores27.34 and29.89. The pod reproduction uses Franzen10882e33 with the v7 patch sequence: patcher_franzen, patcher_garde, patcher_outils, patcher_faits; `RO_EXACT=1`, `CHRYS_OUTILS=1`, `CHRYS_OUTILS_APRES=40`, `CHRYS_FAITS=0`, `CHRYS_FAITS_APRES=40`, `ARC3_SUMMARY_INTERVAL_TOKENS=0`. No P5, pixel repair, click-colour repair, AMODAL or other experimental branch may be enabled. Clear inherited CHRYS flags before applying the explicit configuration. Unset SGL_VARIANTE and SGL_LORA; require SGL_MAXREQ=10 and SGL_SPEC_STEPS=3, and archive these effective values.

Use the existing `franzen_env.sh` and inference configuration recorded in `docs/article/plan_01/heldout_ro_02/INPUT_MANIFEST.json`: 10 active LLM streams, concurrency configuration25 with only five selected games, model `albucino/Qwen3.8-Flash-Next-W4A16-FP8PLE`, SGLang Pennyroyal environment. Use `MAX_RUNTIME_MINUTES=48` as in the archived ABBA, not the JSON default121. Record the effective value before access. Do not replace the model, temperature, prompt or patch implementation.

“RO exact” here means the authorised pod reproduction of the policy and patch configuration. It is not byte-identical to the complete Kaggle runtime or a claim that server scheduling, game draws and stochastic generation match Kaggle. Report these limitations with the result.

## 2. Population and exposure

Exactly five game prefixes, in fixed selection order: **vc33, tu93, wa30, s5i5, cn04**. Resolve each to exactly one SDK game ID and record the full ID/version. No substitution, extra game or default25-game launch. Two passage labels: **TM1**, then **TM2**. Within each passage the five games are scheduled by the existing concurrent harness; the list does not claim sequential completion.

Historical records disclose source-catalogue access before exclusion, incidental information about cn04, and accidentally generated runs quarantined. Thomas attests that none was used for development or candidate selection. Describe this as **held-out games with disclosed incidental exposure**, never globally never-seen. No reserved observations or game-source contents were read to design this protocol. Ten EV1 evaluation games/301segments remain separate and unopened; do not use them for troubleshooting.

## 3. Quantitative predictions, frozen before observation

These are deliberately coarse **subjective forecasts**, not fitted estimates, confidence intervals or adoption thresholds. They use only the already-known overall RO results, no game-specific information. Assign the same prediction to every game to avoid inventing distinctions:

| Game | Predicted score A | Predicted score B | Predicted two-run mean |
|---|---:|---:|---:|
| cn04 |20|20|20|
| s5i5 |20|20|20|
| tu93 |20|20|20|
| vc33 |20|20|20|
| wa30 |20|20|20|

Prediction: passage mean20/100; passage sum100/500; total across ten scheduled game-runs200/1000; two-passage primary mean20/100. The conservative20 is a planning forecast, not evidence that these games are harder. Zero scores and much larger differences are plausible. No result is required to exceed these predictions to remain reportable. Report mean absolute forecast error over all ten fixed slots, without updating predictions after A.

## 4. Metrics and denominator

Primary endpoint: arithmetic mean of the native per-game ARC scores across the **ten prespecified slots**, equally weighted (five games × two passages). Preserve the native score field, scorecard identifiers and unit; verify from documented harness output that the reported unit is0–100 before aggregating. Do not derive score from levels or an EV1 proxy. If the native scale is different or unavailable, stop aggregation and report the discrepancy rather than invent a conversion.

Report each native score, each game's two-run mean, each passage's five-game mean and sum, the ten-slot mean and sum. “Total” means these explicitly defined sums, not a new official leaderboard metric. Preserve any separate native scorecard aggregate under its original name.

Secondary: levels completed, actions, resets, initialisations, runtime, failure cause, effective resource settings, model and game versions, spend. A scheduled slot without a valid native score contributes **zero to the primary intention-to-run aggregate**, but is separately marked missing/infrastructure failure rather than presented as a native zero. Preserve partial official scores where available; never choose the larger score from retries. All ten slots remain in the denominator, including unstarted B slots if the budget terminates the lot.

Comparisons to Kaggle27.34/29.89 and historical public-game results are descriptive: different populations, schedules and environments. Use already archived public baselines only, with exact populations and exposure declared. No new25-game benchmark is authorised. Do not manufacture a disjoint25-game baseline by adding these five results to the twenty development games; if a historical25-game score included these witnesses, label that overlap. No significance claim or per-action pseudo-replication from two passages.

## 5. RESET, state, repetitions and feedback

The native Franzen RESET-after-defeat behavior is explicitly authorised as part of the actual policy. Keep and count it; do not modify RO to implement the earlier no-RESET proposal. This authorisation does not permit launching a third passage, rerunning a failed slot externally, or probing the games during setup. Native agent tool calls and retry behavior stay as in the frozen harness; any external recovery that would replay a slot is prohibited.

Fresh run directories and new agent histories for B; retain only the usual same-game memory within a passage. No persistent game memory, generated functions or facts from A are imported into B. The inference service may remain loaded between passages with its normal cache behavior, recorded as an environmental condition. No seed claim unless the unchanged harness actually accepts and applies one; do not add a seed implementation now.

E1 may monitor resource health and completion. No prompts, frames, intermediate scores or strategy advice are sent to authors or used to alter B. Both passages have identical frozen policy/settings. Operational failure may stop the lot but never trigger tuning. Detailed outcomes are released together after completion or definitive stop.

## 6. Setup and manifest gates before first game

The original `setup_franzen.sh` calls `make` for all games. **Do not execute that block.** A preparation-only copy is supplied at `docs/article/plan_01/heldout_ro_02/setup_franzen_no_game_init.sh`, syntax-checked without running it. The copy requires MODEL_REVISION and passes it as --revision to the download. Copy it under `scripts/pod/` in the isolated pod project so its relative paths remain valid. The sole change from the recorded original removes game discovery/initialisation; policy code is unchanged. Obtain environment artifacts without executing game constructors or inspecting their code; the first game initialisation belongs to passage A. If the SDK cannot prepare this without extra initialisation, report the obstacle before consuming a slot.

Before game access, E1 archives: full Franzen commit, patcher/input hashes checked against INPUT_MANIFEST, resulting harness Python manifest, model revision/config/tokenizer/weight fingerprints, runtime versions, hardware and effective configuration, full five game IDs, pristine output directories and resource watchdog settings. Pin the download to the previously used immutable model revision retrieved from archived manifests; if it cannot be established, report this before launching and do not call the runtime identical. No floating upgrade or strategy change after A. A manifest append recording resolved infrastructure identifiers is permitted before game access; it is not permission to change the declared model/configuration.

`bloc.sh` supports extra env/apres hooks: require them absent for both passage names. Pass the explicit five-game list with `JALON=1`; a default population is prohibited. Verify P5 and experimental flags absent/off. Verify model-server health without making a game. Do not run archived ABBA scripts themselves: they launch other populations/arms.

## 7. Cost, resource stops and cleanup

Thomas authorises **at most10 USD total incremental cost**, using existing Vast credit only, instance plus volume destroyed at the end. No automatic top-up. Cowork's later message permits Cowork to discuss a minimal manual credit addition if needed; it does **not** raise this test's10USD ceiling or authorise E1/Codex payment.

E1 estimate from past ABBA: approximately50minutes per passage at2.806USD/hour plus approximately1hour shared setup. Expected compute subtotal approximately7.5USD; bandwidth, storage, setup variation and teardown reserve must fit within10USD. This is an estimate, not a quote. E1 checks the actual all-in offer before rental and declines if the two passages cannot plausibly fit. No reuse/restart of the destroyed historical pod.

Budget monitoring begins at allocation, includes setup/idle/storage, and does not rely on model activity. Reserve at least1USD for retrieval/cleanup: stop gameplay at9USD accrued or projected accrued plus cleanup, whichever comes first. Do not start B unless remaining time/cost at the accepted rate covers its50minute outer window plus cleanup. Cap each passage externally at50minutes from harness launch (48minute native game allowance plus2minutes shutdown margin). Budget stop takes precedence. Kill only the owned run process group on timeout; preserve logs and partial scores. Record any score invalidation caused by termination.

E1 must establish an independent timeout/budget watchdog and destruction path before first game, with maximum rental duration derived from the actual total hourly charges and10USD cap, including teardown margin. If billing cannot be bounded or monitored, do not rent. No concurrent heavy Mac SDK lot, no second GPU instance, no other experiment. E1 sends coordination notices at allocation/start and at verified destruction, with instance/volume IDs, cost and terminal state; no secrets.

Rapatriate logs/manifests/results promptly, then destroy both instance and chargeable volume after success, failure or abort. Verify destruction in provider state; stopping the process or shutting down the OS is not destruction. No retained chargeable volume for later tests.

## 8. Reporting and authority

E1 executes only this lot after citing the committed preregistration ref in the coordination file and confirming preflight. Report at most80lines plus machine-readable table/manifests: predictions, all ten slots, primary and secondary summaries, spend, deviations, resets, exposure statement and verified cleanup. No external publication or new Kaggle submission is authorised. Preserve failed outcomes and do not alter this preregistration after results; any amendment must be dated and identify whether observations had begun.

This experiment can measure prospective scores of the declared pod reproduction. It cannot establish a causal gain from G1 repairs absent from RO, a new private leaderboard score, or generality from five selected games. Final article updates must preserve that distinction.

### Static preflight review

A second agent reviewed the protocol against E1’s `e1_temoins/scripts/pod/temoins_ro.sh`. Before freeze, passage labels and game-list order were aligned to TM1/TM2 and the E1 list; SGL override constraints and missing input hashes were added. The E1 launcher itself does not implement the required external timeout, billing monitor or provider destruction. These remain E1 preflight responsibilities, not controls already demonstrated by this review. `AUTORISE_TM1` is created by E1 only after these gates are satisfied; PREREG_SHA is the commit carrying this file. MINUTES_PAR_JEU=48.
