Argument quality scoring.

Goal: given the argument graph of an argumentative student essay, return one or more scores that reflect the quality of the argument.

Gold answers now come from the Marro/Cabrio/Villata argument-quality dataset. It gives component-level scores for cogency, rhetoric, and reasonableness. The extractor keeps the raw component labels and also builds simple essay-level scores so graph formats can be tested immediately.

Argument graphs (N > 102): https://aclanthology.org/C14-1142.pdf

Argument quality scores (N = 400 matched essays): https://gitlab.com/santimarro/persuasive-essays-argument-quality-dataset

Known gap: `essay212` and `essay213` have normalized graphs but no quality rows in the source score table.
