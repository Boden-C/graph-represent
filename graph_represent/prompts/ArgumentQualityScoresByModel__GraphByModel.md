You are evaluating the quality of an argumentative student essay using only its argument graph.

Return JSON with a `scores` object. Use numeric values from 0.0 to 1.0.

Use these score names:
- cogency_mean
- rhetoric_strategy_rate
- reasonableness_counterargument_mean
- reasonableness_rebuttal_mean
- overall_quality_mean

Meaning:
- cogency_mean: how well the graph's claims are supported by relevant reasons.
- rhetoric_strategy_rate: how often the argument uses a clear persuasive strategy instead of plain assertion.
- reasonableness_counterargument_mean: how well counterarguments are represented and handled.
- reasonableness_rebuttal_mean: how well rebuttals answer the counterarguments.
- overall_quality_mean: your overall estimate from the graph.

Use the graph structure, support/attack relations, and node texts. Do not assume facts outside the graph. If a score is not relevant, still return it with your best graph-only estimate.
