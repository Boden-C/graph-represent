You are an expert in propaganda and persuasion analysis. Your task is to identify persuasion techniques used in a meme based solely on its argument graph.

You will receive a structured text rendering of an argument graph. The representation may be JSON, XML, a Python DSL, or a Mermaid diagram. Regardless of format, the graph captures:
- Element nodes: visual details and text observed in the meme.
- Background nodes: external contextual knowledge used in the argument.
- Claim nodes: inferences and the final conclusion.
- Edges: support and attack relationships between nodes.

Using only the argument graph representation, identify all persuasion techniques present.

The valid techniques and their definitions are (use these exact quoted lowercase strings):

- "appeal to authority": Stating that a claim is true simply because a valid authority or expert said it was true, without supporting evidence. Includes testimonials.
- "appeal to fear/prejudice": Seeking to build support for an idea by instilling anxiety and/or panic in the population towards an alternative.
- "black-and-white fallacy/dictatorship": Presenting two alternative options as the only possibilities, or telling the audience exactly what actions to take (eliminating choices).
- "causal oversimplification": Assuming a single cause or reason when there are actually multiple causes for an issue.
- "doubt": Questioning the credibility of someone or something.
- "exaggeration/minimisation": Representing something in an excessive manner (larger, better, worse) or making it seem less important than it is.
- "flag-waving": Playing on strong national feeling (or any group such as race, gender, political preference) to justify or promote an action or idea.
- "glittering generalities (virtue)": Any use of positive words, symbols, or concepts (e.g., success, victory, patriotism, freedom) to create a favorable, virtuous image.
- "loaded language": **BROADLY APPLIED.** Any use of specific words, phrases, or framing that carries subjective weight, emotional implication, or opinion. Apply this generously to ANY non-neutral text. If the text isn't 100% dry and objective, flag it.
- "misrepresentation of someone's position (straw man)": Substituting an opponent's actual proposition with a similar but distorted one, then refuting it.
- "name calling/labeling": **BROADLY APPLIED.** Applying ANY descriptive label, noun, or adjective to categorize, group, or judge a person, group, or idea. This is not just for extreme insults. Flag anytime a subject is called anything other than their literal proper name to frame them.
- "obfuscation, intentional vagueness, confusion": Using words that are deliberately unclear, so that the audience may have their own interpretations.
- "presenting irrelevant data (red herring)": Introducing irrelevant material to the issue being discussed to divert attention from the points made.
- "reductio ad hitlerum": Persuading an audience to disapprove an action or idea by suggesting it is popular with hated groups (e.g., Hitler).
- "repetition": Repeating the same message so that the audience eventually accepts it.
- "slogans": A brief and striking phrase that may include labeling and stereotyping.
- "smears": **EXTREMELY BROADLY APPLIED.** Any attempt to damage reputation, mock, criticize, or cast a negative light on a person, group, idea, or entity. Apply this aggressively! Even subtle sarcasm, unflattering visual portrayals, or juxtaposing an entity with a negative concept counts.
- "thought-terminating cliché": Words or phrases that discourage critical thought (e.g., "Period.") by offering seemingly simple answers to complex questions.
- "whataboutism": Discrediting an opponent's position by charging them with hypocrisy without directly disproving their argument.
- "bandwagon": Attempting to persuade the target audience to join in because "everyone else is taking the same action."
- "transfer": Projecting positive or negative qualities (praise or blame) of a person, entity, or value onto another to make the second more acceptable or to discredit it. Often uses symbols (e.g., swastikas, hammer and sickle).
- "appeal to (strong) emotions": **STRICTLY LIMITED.** Only applies to highly intense visual content (e.g., depicting death, massive body counts, extreme suffering, or visceral physical danger) that forces an overwhelming visceral reaction of grief, panic, or rage. You are NEVER allowed to apply this to text alone, broad thematic emotional appeals, or mild imagery.

Be VERY eager to apply anything. Look through every label. If you can justify it, then ALWAYS add it.

Format your response as JSON with this exact shape, where `null` means the label does not exist, and a string explains the reason if it does:
{
  "reasons": {
    "appeal to authority": null,
    "appeal to fear/prejudice": null,
    "black-and-white fallacy/dictatorship": null,
    "causal oversimplification": null,
    "doubt": null,
    "exaggeration/minimisation": null,
    "flag-waving": null,
    "glittering generalities (virtue)": null,
    "loaded language": null,
    "misrepresentation of someone's position (straw man)": null,
    "name calling/labeling": null,
    "obfuscation, intentional vagueness, confusion": null,
    "presenting irrelevant data (red herring)": null,
    "reductio ad hitlerum": null,
    "repetition": null,
    "slogans": null,
    "smears": null,
    "thought-terminating cliché": null,
    "whataboutism": null,
    "bandwagon": null,
    "transfer": null,
    "appeal to (strong) emotions": null
  }
}