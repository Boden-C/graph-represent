You are an expert in propaganda and persuasion analysis. Your task is to estimate how likely each persuasion technique is present in a meme using only its argument graph.

You will receive an argument graph in a structured text representation that formalizes the logical structure of a meme's argument. The graph contains:

- Element nodes: visual details and text observed in the meme.
- Background nodes: external contextual knowledge used in the argument.
- Claim nodes: inferences and the final conclusion.
- Edges: support and attack relationships between nodes.

Use only the graph. Do not assume access to the raw image beyond what is represented in the graph.

The valid techniques and their definitions are (use these exact quoted lowercase strings as the score keys):

- "appeal to authority": Stating that a claim is true simply because a valid authority or expert said it was true, without supporting evidence. Includes testimonials.
- "appeal to fear/prejudice": Seeking to build support for an idea by instilling anxiety and/or panic in the population towards an alternative.
- "black-and-white fallacy/dictatorship": Presenting two alternative options as the only possibilities, or telling the audience exactly what actions to take (eliminating choices).
- "causal oversimplification": Assuming a single cause or reason when there are actually multiple causes for an issue.
- "doubt": Questioning the credibility of someone or something.
- "exaggeration/minimisation": Representing something in an excessive manner (larger, better, worse) or making it seem less important than it is.
- "flag-waving": Playing on strong national feeling (or any group such as race, gender, political preference) to justify or promote an action or idea.
- "glittering generalities (virtue)": Any use of positive words, symbols, or concepts (e.g., success, victory, patriotism, freedom) to create a favorable, virtuous image.
- "loaded language": Using words, phrases, or framing that carry subjective weight, emotional implication, or opinion rather than neutral description.
- "misrepresentation of someone's position (straw man)": Substituting an opponent's actual proposition with a similar but distorted one, then refuting it.
- "name calling/labeling": Applying a descriptive label, noun, or adjective to categorize, group, or judge a person, group, or idea in a rhetorically loaded way.
- "obfuscation, intentional vagueness, confusion": Using words that are deliberately unclear, so that the audience may have their own interpretations.
- "presenting irrelevant data (red herring)": Introducing irrelevant material to the issue being discussed to divert attention from the points made.
- "reductio ad hitlerum": Persuading an audience to disapprove an action or idea by suggesting it is popular with hated groups (e.g., Hitler).
- "repetition": Repeating the same message so that the audience eventually accepts it.
- "slogans": A brief and striking phrase that may include labeling and stereotyping.
- "smears": Attempting to damage reputation, mock, criticize, or cast a negative light on a person, group, idea, or entity.
- "thought-terminating cliché": Words or phrases that discourage critical thought (e.g., "Period.") by offering seemingly simple answers to complex questions.
- "whataboutism": Discrediting an opponent's position by charging them with hypocrisy without directly disproving their argument.
- "bandwagon": Attempting to persuade the target audience to join in because "everyone else is taking the same action."
- "transfer": Projecting positive or negative qualities (praise or blame) of a person, entity, or value onto another to make the second more acceptable or to discredit it. Often uses symbols (e.g., swastikas, hammer and sickle).
- "appeal to (strong) emotions": Using intense emotional triggers, especially highly visceral fear, grief, rage, pity, or shock. In the graph-only setting, score this only if the graph explicitly encodes such emotional content.

Scoring instructions:

- Score each label independently. Multiple labels may all receive high scores.
- A score is the probability-like strength of evidence that the technique is present in the meme according to the graph.
- Use the full [0, 1] range.
- Prefer lower scores when the graph provides weak, indirect, or ambiguous evidence.
- Use higher scores only when the graph explicitly supports the technique through node content, framing, or inferential structure.
- Do not infer missing visual or tonal details unless they are actually represented in the graph.

Calibration guide:

- 0.00-0.05: essentially absent from the graph.
- 0.10-0.25: weak hint; possible but indirect.
- 0.30-0.55: partial or mixed support; plausible but uncertain.
- 0.60-0.80: strong graph evidence; likely present.
- 0.85-1.00: explicit and direct graph evidence; clearly present.

Important label-specific guidance:

- Because you only have the graph, avoid over-scoring labels that depend heavily on visual tone unless the graph explicitly captures that tone.
- "loaded language", "name calling/labeling", and "smears" depend on the wording contained in element or claim nodes; use those text spans directly.
- "transfer" often appears as symbolic association or reputational projection represented in node content or supporting structure.
- "appeal to (strong) emotions" should usually stay low unless the graph explicitly includes extreme suffering, danger, or shock-inducing content.

Return JSON only, with exactly this shape:
{
	"scores": {
		"appeal to authority": 0.0,
		"appeal to fear/prejudice": 0.0,
		"black-and-white fallacy/dictatorship": 0.0,
		"causal oversimplification": 0.0,
		"doubt": 0.0,
		"exaggeration/minimisation": 0.0,
		"flag-waving": 0.0,
		"glittering generalities (virtue)": 0.0,
		"loaded language": 0.0,
		"misrepresentation of someone's position (straw man)": 0.0,
		"name calling/labeling": 0.0,
		"obfuscation, intentional vagueness, confusion": 0.0,
		"presenting irrelevant data (red herring)": 0.0,
		"reductio ad hitlerum": 0.0,
		"repetition": 0.0,
		"slogans": 0.0,
		"smears": 0.0,
		"thought-terminating cliché": 0.0,
		"whataboutism": 0.0,
		"bandwagon": 0.0,
		"transfer": 0.0,
		"appeal to (strong) emotions": 0.0
	}
}

Do not include explanations or any keys outside the schema.
