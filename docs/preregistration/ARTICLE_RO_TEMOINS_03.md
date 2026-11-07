# ARTICLE-RO-5x2, attempt 2 — amendment to ARTICLE_RO_TEMOINS_02 (13911e5e), 3 November 2026

**Author: Cowork (Thomas decision 3 Nov 17:09: Cowork replaces Codex for protocol work; E1 remains sole pod executor).** Written before any attempt-2 rental. Everything in ARTICLE_RO_TEMOINS_02 below applies unchanged except the points listed here.

## A1. Attempt 1 declared
Attempt 1 (instance 58918610, 3 Nov 04:45–12:20 UTC) failed during setup: network interruption while building the SGLang bundle, then a resumed build refused to re-patch a half-patched bundle (`environ.py`, build failed at line 1504). No model server started, no game was opened, no manifest was written; all ten slots of attempt 1 are recorded as *missing (infrastructure)*. The executor session then lost authentication and the idle instance accrued 11.55 USD before manual destruction. Attempt 1 is reported in the paper as a failed execution, with its cost.

## A2. Why a second attempt is not a re-roll
No game was played, so no outcome was observed; repeating the setup cannot select on results. Predictions (20/100 per slot, ten-slot mean 20), population, order (vc33, tu93, wa30, s5i5, cn04), metric, denominator, RESET policy and policy configuration are **identical** to 02 and frozen. Attempt 2 is the only further attempt: whatever happens, there is no attempt 3 for the paper.

## A3. Execution changes (infrastructure only)
1. Setup always starts from an empty bundle workspace (no resumption of a partial build); at most two clean build attempts.
2. Independent on-pod watchdog: gameplay stop at 7.0 USD accrued, full stop at 7.5 USD, abort if no game manifest 2 h after rental; heartbeat line every 15 min; instance self-destruction (or stop as fallback) at the full-stop threshold or after results are retrieved, so that billing ends even if the executor session dies.
3. Total ceiling for attempt 2: **8 USD**, existing credit only, no top-up, instance and any volume destroyed and verified in the provider console.
4. Executor reports in the coordination file at rental, start of TM1, end of TM2, retrieval, destruction (with exact spend).

## A4. Analysis
Unchanged from 02 §4. Attempt-1 slots are reported separately and excluded from the attempt-2 ten-slot aggregate; both are shown in the paper's failure accounting.
