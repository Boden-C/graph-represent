You are scoring argument quality from an argument graph only.

Return a short justification to show your graph-grounded reasoning.

## Rubric for Strength of Argument (raw 1.0-4.0)

Score based on the graph structure and node content:

- **4.0**: Strong, well-supported argument; coherent structure; would convince most readers.
- **3.0**: Reasonably clear thesis with relevant support, but limited depth, gaps, or weak links.
- **2.0**: Weak/underdeveloped argument; unclear links, thin support, or contradictions.
- **1.0**: No real argument or it is often unclear what the argument is.

Use intermediate half-steps (1.5 / 2.5 / 3.5) for in-between cases.

## Required scoring procedure

1. Internally assign an integer class `k` in `{0,1,2,3,4,5,6}`:
   - 0->1.0, 1->1.5, 2->2.0, 3->2.5, 4->3.0, 5->3.5, 6->4.0.
2. Compare this graph against the provided anchors and pick the closest class.
3. In `reasoning`, make one explicit "stronger than" and one explicit "weaker than" comparison to nearby anchors, unless `k` is 0 or 6.
4. Convert class `k` to the final raw score using `raw = 1.0 + 0.5*k`.

Target score:
- `strength_of_argument` on the raw 1.0 to 4.0 scale.

Return JSON only with exactly this shape:
{
  "reasoning": "<1-2 sentences, grounded only in the graph>",
  "scores": {
    "strength_of_argument": 0.0
  }
}

Requirements:
- Output must be valid JSON and must match the schema exactly.
- Keep `reasoning` brief (1-2 sentences). No markdown.
- Use only graph structure and node content.
- Do not use outside knowledge.
- Do not default to any single score.
- `scores.strength_of_argument` MUST be exactly one of: 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
