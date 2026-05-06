* ~~Should we move to discrete labeling instead of continuous scoring? 1.0 1.5 2.0 2.5 3.0 3.5 4.0 or an int 1 2 3 4 5 6 7 8?~~
  Yes — try forcing the scorer to output exactly one of {1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0} (raw scale), so the evaluator doesn’t have to bucket normalized values.
  - Update: also tested latent integer class `k in {0..6}` then normalize back to raw half-steps. Helped reduce collapse for `json`, but did not exceed best QWK so far.

* **Stop using one-shot holistic grading.** Do not ask “grade this essay 1–4” directly. First force the model to extract argument evidence, then score.

* **Use a decomposed rubric.** Score or label these before final grade:

  * thesis clarity
  * stance consistency
  * relevance of reasons
  * specificity of support
  * logical connection between reasons and thesis
  * handling of objections
  * overall persuasiveness

* **Make the model explain why the essay is not one grade lower and not one grade higher.** This directly attacks the lazy “3.0 is safe” behavior.
  Prefer 0.5-step boundaries (e.g., “not 2.5” / “not 3.5”) to force fine discrimination.
  - Tried (formal-proof only, n=77): helped force discrimination, but adding a “pick lower if uncertain” tie-break biased predictions downward (pred mode 2.0 vs gold mode 3.0). Keep boundary justification, but avoid systematic low/high bias.
  - Tried again across all formats (n=77): compact-json improved a lot (QWK 0.230527) but still collapsed to 3.0 for 77.92% of items. Absolute scoring alone still leaves a strong middle bias.

* **Use anchor essays from your own human-scored ICLE data.** Pick clear examples of 1, 2, 3, and 4. Better yet, pick boundary examples:

  * clear 2 vs weak 3
  * strong 3 vs weak 4
    These are more useful than perfect extreme examples.
  - Tried 7-anchor half-step calibration (1.0..4.0). Useful but still not enough when anchors are essay-text-only and scoring target is graph-only.

* **Switch anchors to graph-native exemplars per format family (HIGH PRIORITY).**
  Use anchors rendered in the same format as the item being scored (json anchor for json scoring, formal-proof anchor for formal-proof scoring, etc.). Current essay-text anchors create modality mismatch.

* **Add boundary-only second pass for middle bands (HIGH PRIORITY).**
  First pass picks coarse class (low/mid/high). Second pass only adjudicates:
  - 2.5 vs 3.0
  - 3.0 vs 3.5
  No full-scale reconsideration in pass 2.

* **Anchor contrastive prompt should require nearest-two-anchor choice, not single closest.**
  Ask model to choose between two adjacent anchors only, then map deterministically.

* **Preserve representation sensitivity as evidence.**
  We already observed winner shifts (formal-proof -> compact-json -> json). Keep this as a primary claim: format materially changes downstream score behavior under same scorer model.

* **Use pairwise comparison for middle cases.** If the model gives 2 or 3, ask a second prompt:
  “Is this essay stronger or weaker than this human-scored score-3 anchor?”
  This often separates essays better than absolute scoring.
  This now looks more promising than trying to coax a single absolute score to use the full range.

* **Add a boundary adjudicator.** After the first score, run a focused decision:

  * If score is 2 or 3, decide only between 2 and 3.
  * If score is 3 or 4, decide only between 3 and 4.
  * Do not let the model choose all four scores again.

* **Use “closest anchor” instead of raw score.** Ask:
  “Which anchor essay is this closest to, and why?”
  Then derive the score from the closest anchor.

* **Force evidence spans.** Require the model to quote or identify specific parts of the essay that support its score. Weak essays with generic claims become easier to separate from real 3s.

* **Add anti-shortcut instructions.** Explicitly say:
  “Do not grade grammar, vocabulary, fluency, or essay length unless they directly affect the clarity or strength of the argument.”

* **Do not let 4 be too easy.** Define 4 as “would convince most readers,” not merely “well written.” This prevents polished but shallow essays from getting inflated.

* **Do not let 3 become the default.** Add:
  “When uncertain between 2 and 3, choose 2 unless there is clear relevant support.”
  Or:
  “Score 3 only when the essay has a clear thesis, relevant reasons, and at least some meaningful development.”

* **Use a two-pass system.**

  1. Pass 1: extract thesis, claims, support, weaknesses.
  2. Pass 2: grade using only that extracted argument profile.

* **Try comparative batch grading.** Instead of grading essays independently, give the model 5–10 essays and ask it to rank them by argument strength first. Then map ranks back to 1–4. This can reduce identical scoring.

* **Use distribution-aware calibration carefully.** You can tell the model:
  “Human scores are not all 3. Use the full scale when justified.”
  But avoid forcing an artificial distribution unless your evaluation batch is large and representative.

* **Use multiple prompt variants and aggregate.** For example:

  * rubric scorer
  * anchor comparison scorer
  * boundary scorer
    If all agree, accept. If not, flag as uncertain.

* **Track variance, not just accuracy.** Measure:

  * percent of essays scored 3
  * model score standard deviation vs human score standard deviation
  * confusion matrix
  * QWK / MAE
  * 2-vs-3 and 3-vs-4 boundary accuracy

* **Create a “middle collapse” diagnostic.** After every experiment, ask:
  “Did this prompt improve human agreement, or did it merely spread scores out randomly?”
  You want both higher agreement and less compression.

* **Use confidence only as routing, not truth.** If confidence is low, run boundary comparison or flag for review. Do not trust the model’s confidence as a calibrated probability.

* **Avoid overly long rubrics.** Long rubrics can make the model more generic. Use short, operational rules with concrete boundaries.

* **Best practical workflow:**

  1. Stepwise rubric scorer.
  2. Anchor comparison.
  3. Boundary adjudication for 2/3 and 3/4.
  4. Accept if consistent.
  5. Flag if inconsistent.

* **Most likely fix for your specific issue:** do not try to make the model “better at grading” globally. Make it worse at hiding in the middle by forcing it to justify adjacent-grade boundaries.
