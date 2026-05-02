You are scoring argument quality from an argument graph only.

Target score:
- `strength_of_argument` on a normalized 0.0 to 1.0 scale.

Return JSON only with exactly this shape:
{
  "scores": {
    "strength_of_argument": 0.0
  },
  "rationale": "short explanation grounded only in the graph"
}

Requirements:
- `rationale` is required.
- Use only graph structure and node content.
- Do not use outside knowledge.
- If uncertain, still return one best estimate.
