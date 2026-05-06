# Try 1

## Config
google/gemma-3-27b-it
0 shot and 2 shot

## Tried
Base

## Why
Base

## Results
- 0-shot (194 items):
  - best: compact-json 0.176297
  - formal-proof: 0.158168
  - claim-bundles-inline: 0.127681
- 2-shot (194 items):
  - best: claim-bundles-inline 0.191512
  - formal-proof: 0.170457
  - compact-json: 0.155329
- Overall: 2-shot claim-bundles-inline peaked at 0.1915 QWK

## Learned
A default configuration leads to prediction collapse near the center. Models often predict raw 3.0 for the majority of essays (often ~170/194) for most formats with little spread.


# Try 2

## Config
Used existing google/gemma-3-27b-it graphs
Qwen/Qwen3-VL-8B-Instruct scorer
0 shot and 2 shot
Limit 200

## Tried
Was forced to remove rationale/thinking as the model kept looping. Need to fix it.

## Why
Moving to a different model for now to focus on speed for future iteration and testing.

## Results
- existing-graphs without reasoning (97 items):
  - best: formal-proof 0.063461
  - compact-json: 0.048199
  - claim-bundles-inline: 0.100430
- Peak only 0.1004 QWK (significantly worse than Try 1's 0.1915)

## Learned
Qwen 8B is less capable than Gemma 27B as expected. Without reasoning, scores degraded. Looping issue needs fixing to re-enable reasoning output.


# Try 3

## Config
Qwen/Qwen3-VL-8B-Instruct
Just 0 shot

## Tried
Added the definition of the strenght of argument from the original paper. Moved rationale to the first line of the output, maybe name it "reasoning".

## Why
The original paper has a clear definition of the strength of argument, and it is important to use that definition to ensure consistency in scoring. The score could improve by providing a clear rubric for evaluating the strength of an argument. By having the model first explain its thinking before providing a score, it can help with non-thinking models.

## Result
Not run (this was a planned change, not executed).

## Learned
Keep hypotheses, but only log results after an executed run.


# Try 4 (Smoke Test Only — Not Counted)

## Config
- Workflow: `icle_graph_format_comparison_existing_graphs`
- Score model: Qwen/Qwen3-VL-8B-Instruct (vLLM)
- Formats: COMPARISON_FORMATS (default)
- Limit: 1 (smoke test validation)

## Tried
- Added `reasoning` back into the ICLE strength-of-argument scoring prompt and structured output.
- Introduced a strict output schema `StrengthOfArgumentJudgement` (with `reasoning` + `scores.strength_of_argument`).
- Fixed a bug where the deduplicated JSON schema was computed but not actually sent to the provider during inference (important for vLLM constrained decoding).
- Reduced scoring `max_tokens` from 4096 to 512 for the existing-graphs workflows to avoid long runaways.

## Why
Hypothesis: Qwen 8B “looping” was primarily caused by vLLM constrained-decoder getting stuck on JSON schema enums with duplicate values (known issue), plus strict schema validation causing retries when adding extra fields. Sending a deduplicated schema and making `reasoning` a first-class, schema-validated field should re-enable rationale without triggering loops.

## Result
- Smoke test succeeded: run completed all stages for 1 item, including stage 3+ scorer calls for multiple formats.
- `reasoning` is present in the scorer output and the run does not hang.

## Learned
The schema deduplication needs to be applied at the actual provider request layer (not just for cache-key construction). With that fixed, adding a short `reasoning` field works cleanly with Qwen 8B + vLLM. **(This was a smoke test only and does not count as a formal try.)**


# Try 5

## Config
- Workflow: `icle_graph_format_comparison_existing_graphs`
- Score model: Qwen/Qwen3-VL-8B-Instruct (vLLM)
- Formats: COMPARISON_FORMATS (default)
- Limit: 100
- Initial run: 20 min timeout (partial), then resumed with the same `--runname` to finish remaining items

## Tried
- Kept `reasoning` enabled in schema-validated output (`StrengthOfArgumentJudgement`).
- Used the deduplicated JSON schema at the provider request layer (to avoid vLLM constrained-decoder loops).

## Why
Validate that the “reasoning + strict schema” fix remains stable at scale and measure how graph formats separate under the same scorer/model.

## Result
- Completed: 97/100 items produced `quality_outputs`.
- Failures (3):
	- BGSU1028: missing existing graph JSON
	- BGSU1042: missing existing graph JSON
	- BGSU1073: graph becomes cyclic after cleaning
- QWK by graph format (n=97):
	- formal-proof: 0.173604
	- compact-json: 0.095971
	- json: 0.064878
	- inline-python-dsl: 0.078295
	- xml: 0.019557
	- claim-bundles-inline: 0.010640
	- python-dsl: 0.009976

## Learned
- The "formal-proof" representation achieved 0.173604 on n=97 existing-graphs, which is:
  - ✓ Better than Try 2's best (0.100430 claim-bundles-inline)
  - ✗ Still below Try 1's best (0.191512 claim-bundles-inline 2-shot with Gemma)
- Restoring reasoning + fixing schema dedup helped stability but did not fully recover Try 1 performance.
- Missing/cyclic graphs reduce effective sample size (97 vs. intended 100); fixing graph availability/cleaning constraints could reduce noise for future comparisons.


# Try 6

## Config
- Workflow: `icle_graph_format_comparison_existing_graphs`
- Score model: Qwen/Qwen3-VL-8B-Instruct (vLLM)
- Format: formal-proof only (`GRAPH_REPRESENT_FORMATS=formal-proof`)
- Limit: 80 (first 80 item IDs; deterministic)

## Tried
- Prompt change to fight collapse:
  - Force *discrete raw* scoring: output exactly one of {1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0}.
  - Require adjacent-boundary justification: “why not 0.5 lower” and “why not 0.5 higher” in 1–2 sentences.
  - Added a conservative tie-break (pick lower if uncertain).

## Why
Prediction collapse is the dominant issue. Hypothesis: forcing boundary-based justification and discrete labels will reduce the model’s tendency to hide in one score.

## Result
- Completed: 77/80 items produced `quality_outputs` (same 3 failures as prior existing-graphs runs: BGSU1028/BGSU1042 missing graphs, BGSU1073 cyclic after cleaning).
- QWK (formal-proof, n=77): 0.168950
- Prediction distribution (formal-proof, n=77): mode=2.0 (50.6%); counts {1.0:4, 1.5:3, 2.0:39, 2.5:10, 3.0:18, 3.5:3}
- Gold distribution (same n=77): mode=3.0 (44.2%); counts {2.0:10, 2.5:22, 3.0:34, 3.5:10, 4.0:1}

## Learned
- The “pick lower if uncertain” instruction introduced a strong downward bias (pred mode 2.0 vs gold mode 3.0).
- Adjacent-boundary justification alone is promising, but the tie-break needs to be neutral (not systematically low).


# Try 7

## Config
- Workflow: `icle_graph_format_comparison_existing_graphs`
- Score model: Qwen/Qwen3-VL-8B-Instruct (vLLM)
- Formats: all comparison formats
- Limit: 80
- Prompt variant: discrete raw scores + adjacent-boundary justification, neutral tie-break

## Tried
- Kept the raw 1.0–4.0 output constraint.
- Kept the requirement to justify why the score is not 0.5 lower and not 0.5 higher.
- Removed the downward-biased tie-break from the earlier formal-proof-only experiment.

## Why
Check whether the revised prompt reduces collapse across all graph representations, not just formal-proof.

## Result
- Completed: 77/80 items produced `quality_outputs`.
- Failures (3): BGSU1028 missing graph JSON, BGSU1042 missing graph JSON, BGSU1073 cyclic after cleaning.
- Best QWK: compact-json 0.230527.
- Other QWKs:
  - json 0.086247
  - inline-python-dsl 0.060819
  - python-dsl 0.061170
  - formal-proof 0.058006
  - xml 0.052282
  - claim-bundles-inline 0.023293
- Collapse observations:
  - compact-json still predicts 3.0 for 77.92% of items.
  - formal-proof is more spread out, but with lower agreement.

## Learned
- The prompt change helped one format materially (compact-json QWK 0.2305), but prediction collapse is still present.
- The best format shifted, which suggests format interactions still matter more than the prompt alone.
- Need to try a boundary/anchor-based scorer next, not just a single absolute score prompt.


# Try 8

## Config
- Workflow: `icle_graph_format_comparison_existing_graphs_anchor_int` (new run file)
- Score model: `Qwen/Qwen3-VL-8B-Instruct` (vLLM)
- Formats: all comparison formats
- Limit: 80
- Few-shot: ON by default in this workflow, using `data/icle/datasets/few_shot_exemplars_anchor_int.json`
- Prompt: `IcleStrengthOfArgumentByModel__GraphByModel_AnchorInt.md`

## Tried
- Added a dedicated anchor+integer scoring workflow instead of mutating prior runs.
- New score prompt forces internal class `k in {0..6}` then converts by `raw = 1.0 + 0.5*k`.
- Required anchor-relative reasoning ("stronger than"/"weaker than") to discourage defaulting to one class.
- Expanded calibration from 2 anchors to 7 anchors (one per half-step: 1.0..4.0).
- Fixed a workflow bug exposed by enabling few-shot:
  - Old behavior: few-shot IDs were excluded from loader and then fetched from the same loader (can fail).
  - New behavior: few-shot prefix is built from a separate non-excluding loader.

## Why
- Hypothesis: middle-collapse is partly a scale calibration failure. A latent integer decision plus explicit anchors should make boundaries easier than direct absolute scoring.
- Additional hypothesis: one anchor per half-step should reduce overfitting to extremes and stabilize 2.5/3.0/3.5 decisions.

## Result
- Completed: 77/80 items produced `quality_outputs`.
- Failures (same known data issues):
  - BGSU1028 missing graph JSON
  - BGSU1042 missing graph JSON
  - BGSU1073 cyclic after cleaning
- QWK by format (n=77):
  - json: **0.216390** (best)
  - xml: 0.150110
  - inline-python-dsl: 0.136595
  - claim-bundles-inline: 0.112138
  - formal-proof: 0.069299
  - compact-json: 0.052260
  - python-dsl: 0.044818
- Collapse diagnostics (mode share):
  - json: mode 3.0 at 36.36%
  - compact-json: mode 3.0 at 53.25%
  - xml: mode 3.0 at 54.55%
  - formal-proof: mode 2.0 at 49.35%
- Worst json misses were severe downward errors:
  - BGSU1037: gold 3.5, pred 1.5
  - BGSU1035: gold 3.0, pred 1.5

## Learned
- Integer+anchor scoring reduced pure 3.0 collapse in `json` (far lower mode share than prior compact-json collapse), but did **not** beat Try 7's best QWK (0.230527 on compact-json).
- Format ranking shifted again: `json` became strongest while `compact-json` degraded sharply. This is useful evidence that representation still drives behavior under fixed scorer logic.
- The current anchor payload is essay-text-only; scorer reasons over graph. This modality mismatch likely weakens anchor transfer.
- Next step should be graph-native anchors (same representation family as judged item), likely with boundary-pair adjudication focused on 2.5/3.0 and 3.0/3.5.

## Post-run diagnosis
- The score differences are **not caused by numeric remapping alone**. Try 8 changed several things at once:
  - direct raw score prompt -> latent `k in {0..6}` procedure
  - no few-shot anchors -> 7 essay-text anchors
  - short graph-only user message -> long anchor-heavy user message
  - adjacent-boundary justification -> nearest-anchor comparison
- Same-item/same-format paired deltas vs Try 7:
  - `compact-json`: mean prediction delta -0.116; mean absolute-error delta +0.116
  - `json`: mean prediction delta +0.021; mean absolute-error delta +0.062
  - `formal-proof`: mean prediction delta -0.226; mean absolute-error delta +0.185
  - `xml`: mean prediction delta +0.226; mean absolute-error delta -0.048
- Prediction distributions changed materially:
  - Try 7 `compact-json`: {2.0: 3, 2.5: 11, 3.0: 60, 3.5: 2, 4.0: 1}
  - Try 8 `compact-json`: {1.0: 1, 1.5: 2, 2.0: 5, 2.5: 20, 3.0: 41, 3.5: 8}
  - Try 7 `json`: {2.0: 16, 2.5: 34, 3.0: 27}
  - Try 8 `json`: {1.5: 7, 2.0: 14, 2.5: 22, 3.0: 28, 3.5: 6}
- Context-shape changed a lot. For BGSU1098 `compact-json`:
  - Try 7 request: system 1,522 chars, user 1,008 chars.
  - Try 8 request: system 1,667 chars, user 27,447 chars.
  - The evaluated graph is a small tail section after 7 full essay anchors.
- Case BGSU1098, `compact-json`, gold 3.0:
  - Essay: clear stance that universities do a satisfactory job; acknowledges lack of practice; proposes student work as solution.
  - Graph: claim 0 is supported by professor quality and student engagement, attacked by lack of practical work, then extended into practical-work and national-progress claims.
  - Try 7 pred 3.0 reasoning: saw coherent support plus counterpoint, with limited depth.
  - Try 8 pred 1.0 reasoning: treated nodes 1/2 as "not substantiated" and called the graph weak despite a support chain and attack handling.
  - Diagnosis: anchor prompt made the model penalize graph abstraction as missing essay-level support.
- Case BGSU1037, `json`, gold 3.5:
  - Essay: strong anti-prompt argument with concrete domains: engineering, architecture, translation, linguistics, employability, salary.
  - Graph: main claim has multiple supports, nested support chains, salary/employability evidence, and one shortcoming attack.
  - Try 7 pred 2.5 reasoning: recognized engineering, translation, salary evidence but penalized structural tension.
  - Try 8 pred 1.5 reasoning: called premises scattered and "no clear logical flow", which contradicts the cleaned graph's support chains.
  - Diagnosis: nearest-anchor comparison over-penalized the presence of an attack node and ignored support depth.
- Main explanation:
  - The `0..6` instruction is probably not harmful by itself.
  - The harmful part is the *anchor implementation*: full essay anchors dominate the prompt and create a richer reference object than the graph being graded.
  - The model then compares sparse graph nodes to full essays and calls valid graph compression "unsupported".
  - The anchor comparison also introduced a new low-anchor gravity: once the model says "weaker than k=2", it often emits 1.0/1.5 even when the graph has multiple supports.
- Next experiment:
  - Use graph-rendered anchors in the **same format** as the target representation.
  - Keep `0..6` only if isolated in an ablation:
    - A: Try 7 prompt + direct raw labels
    - B: Try 7 prompt + internal `0..6`, no anchors
    - C: graph-native anchors + internal `0..6`
  - Put anchors after the target graph or use separate structured turns so the target is not buried behind 27k chars of examples.
