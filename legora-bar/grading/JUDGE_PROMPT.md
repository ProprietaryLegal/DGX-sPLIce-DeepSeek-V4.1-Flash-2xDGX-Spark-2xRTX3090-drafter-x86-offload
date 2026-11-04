# BAR judge instruction (one call per batch)

You are grading a candidate transfer pricing Master File (Freshworks Group, FY2023) against a batch of rubric
criteria. Read the whole candidate file first: {{CANDIDATE_PATH}}
Then read the batch file: {{BATCH_PATH}} (JSON: a list of criteria, each with id, importance, criterion and the
citation/evidence passages from the matter documents that ground it).

Grading guidance (binding, verbatim from the rubric):

> Grade the substance, not the wording or location. A criterion is satisfied whenever the candidate output contains
> the fact or makes the point, regardless of phrasing, ordering, or where it appears (which section, paragraph, or
> heading). Do not require an exact paragraph or section number, an exact quote, or a specific computed form
> (components vs a multiplied total) unless the criterion explicitly makes that citation or figure the graded point.
> Equivalent phrasings and reasonable paraphrases pass.

For each criterion give exactly one verdict:
- PASS: the candidate satisfies the criterion. For a "must not" criterion, PASS means the candidate does not make the
  prohibited statement.
- FAIL: it does not (the point is missing, wrong, contradicted, or a prohibited statement is made).
- UNGRADABLE: only if the criterion cannot be judged from the candidate at all (for example the candidate file is
  empty or truncated before the relevant material). Do not use UNGRADABLE for a point that is simply missing; that
  is FAIL.

The citations tell you what the correct facts are; the candidate does not need to cite them. Judge each criterion
independently. Do not reward length or style.

Output: write one JSON object per line, one line per criterion in the batch, in batch order, and nothing else, to
{{RESULT_PATH}}:
{"id": "R-001", "verdict": "PASS", "reason": "<one line>", "quote": "<short verbatim quote from the candidate, or empty if none applies>"}
The reason is one line. For PASS quote the candidate text that satisfies the criterion. For FAIL quote the wrong or
prohibited text if there is one, otherwise leave quote empty and say what is missing.
