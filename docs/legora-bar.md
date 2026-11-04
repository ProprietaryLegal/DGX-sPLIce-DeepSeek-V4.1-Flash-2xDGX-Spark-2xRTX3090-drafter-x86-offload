# Legora BAR public tax case on DGX sPLIce

Legora's [BAR](https://legora.com/bar) (Benchmark for Agentic Reasoning) grades models on long legal tasks against
expert-written rubrics. One case is public, [legora-oss/legora-bar-tax-case](https://github.com/legora-oss/legora-bar-tax-case)
(Apache-2.0, commit `f5032cb`). The task is to draft a transfer pricing Master File for the Freshworks Group for the
financial year ended 31 December 2023 from a 72-file matter folder (17 docx, 40 pdf, 3 pptx and 12 xlsx). The folder
holds about 1.33 M tokens of extracted text, so it does not fit in one prompt and the model has to work through file tools.
The rubric has 175 graded criteria, each high, medium or low importance.

We ran the case once on this build (DeepSeek-V4.1-Flash-1017, the served legal-weighted 2.75 bpw EXL3 allocation, the
production server) on 2026-11-04. The results, the agent harness, the grading pack and every output file are in
[`legora-bar/`](../legora-bar/).

## Result

| | Passed | Score |
|-|-|-|
| **All 175 criteria, unweighted** (one point per pass) | **129 / 175** | **73.7 %** |
| **Importance-weighted** (high 3, medium 2, low 1; 421 points) | 315 / 421 | **74.8 %** |
| High-importance criteria | 60 / 74 | 81.1 % |
| Medium-importance criteria | 66 / 98 | 67.3 % |
| Low-importance criteria | 3 / 3 | 100 % |
| Ungradable | 0 | |

By rubric theme (the theme grouping is from the rubric file):

| Theme | Passed |
|-|-|
| 1. Template hygiene and scope | 6 / 6 |
| 2. Group perimeter, structure and workforce | 23 / 37 |
| 3. Business context and functional analysis | 20 / 22 |
| 4. Intangibles, DEMPE and agreements | 17 / 21 |
| 5. Transfer pricing policy and results | 20 / 27 |
| 6. Financing and treasury | 10 / 19 |
| 7. Financial data | 10 / 11 |
| 8. Tax positions | 3 / 10 |
| 9. Negative space: statements the master file must not make | 17 / 18 |
| 10. Hedging guards: established facts stated without confirmation flags | 3 / 4 |

The high-importance misses (14 of 74), in the judge's words, are in
[`legora-bar/results/sparks-r1/grades.jsonl`](../legora-bar/results/sparks-r1/grades.jsonl). They cluster in three places:

- **Tax positions.** The model missed the India tax examination in the 10-K's tax note and wrote that no audits were ongoing
  (R-136, R-139). It asserted that no APA had ever been applied for, which hid the India APA application (R-132). Its
  Country-by-Country Reporting threshold test used FY2023 revenue instead of the preceding year's (R-133 to R-135).
- **FY2024 documents read as FY2023 facts.** It used FY2024 patent figures (R-057). It also gave Natero Ireland
  functions taken from the FY2024 organisation chart (R-150, R-031b).
- **Treasury facts stated as certain.** It stated as fact things the record leaves open: guarantees, letters of credit,
  captive insurance and undrawn facilities. It did not flag them for Group Treasury to confirm (R-118b, R-118c, R-119),
  and it did not reconcile two cash figures (R-109).

The run itself:

| | |
|-|-|
| Outcome | FINISHED: the model called `finish()` |
| Turns / tool calls | 112 / 168: read_file 45, search 32, write_section 79, read_draft 6, list_files 4, save_note 1, finish 1; 0 tool errors, 0 malformed arguments |
| Wall time | 1,663 s (27.7 min) of generation, plus 245 s waiting for the shared server to go idle |
| Tokens | 7.93 M prompt (7.63 M served from the prefix cache), 87,596 output, of which 20,552 reasoning |
| Largest prompt | 102,895 tokens (the harness budget is 131,072; older tool outputs were elided 147 times) |
| Output | a 180,767-character Master File in 60 sections: [`master_file.md`](../legora-bar/results/sparks-r1/master_file.md) |

## How this compares with other models

Legora publishes BAR scores only for its private case set, run inside its own agent harness. It publishes no scores for
this public case. One independent site, [Overfitting Dicta](https://overfittingdicta.com/), runs the public Freshworks
case and publishes unweighted pass counts out of 175. Its best result for each model, as of 2026-11-04, with our run
added in the row marked "this build":

| Model | Passed | Rate |
|-|-|-|
| **DeepSeek-V4.1-Flash-1017, 2.75 bpw, this build** (our harness and judge, one run) | **129 / 175** | **73.7 %** |
| Opus 5.5 (Xhigh) | 125 / 175 | 71.4 % |
| Sonnet 5.5 (Max) | 122 / 175 | 69.7 % |
| Fable 5.1 (High) | 119 / 175 | 68.0 % |
| Grok 4.7 (Xhigh) | 118 / 175 | 67.4 % |
| Muse Wonder 1.0 (High) | 114 / 175 | 65.1 % |
| Gemini 4 Argon (High) | 111 / 175 | 63.4 % |
| Kimi K3.1 Pro (Max) | 107 / 175 | 61.1 % |
| Kimi K3 (Max) | 99 / 175 | 56.6 % |
| GPT-6 Astra (Xhigh) | 98 / 175 | 56.0 % |
| GPT-6.1 Sol (High) | 95 / 175 | 54.3 % |
| Muse Spark 1.3 (Max) | 95 / 175 | 54.3 % |
| Mistral Large 4 (High) | 92 / 175 | 52.6 % |
| Gemini 3.8 Flash (High) | 84 / 175 | 48.0 % |

**This is not a controlled comparison.** Read the table as "in the same range as the frontier models on this case", not
as a ranking:

- **Different harness.** Overfitting Dicta does not say which agent harness or judge it uses. Ours is the harness
  published here, with a Claude judge. A more lenient or stricter judge alone could move a score by several criteria.
- **One run.** Legora runs each case three times. We ran it once (seed 1, temperature 1.0), and one run of a long
  agentic task can easily vary by a few criteria.
- **Same grading rule.** Our judge used the rubric's own grading guidance verbatim: grade the substance, not the wording
  or location. Each verdict comes with a one-line reason and a quote from the candidate, so any grade can be checked
  by hand.

## Method

**Matter extraction** ([`extract_matter.py`](../legora-bar/harness/extract_matter.py)). Every input file is converted to
text once, with page, slide, sheet and section anchors. Docx keeps tables, headers, footers and comments, and the
template's instruction text is marked as such. Xlsx gives every sheet as a table with its formulas. Pptx gives slide text
and notes. Eighteen scanned PDFs with no text layer were OCR'd with `ocrmypdf` first.

**Agent harness** ([`legbar_agent.py`](../legora-bar/harness/legbar_agent.py), version `legbar-agent-1`, sha256
`a3a7327deb50…`, identical to the file that ran).
- It talks to any OpenAI-compatible chat server with tool calling.
- Tools: `list_files`, `read_file` (paged, at most 16,000 characters a read), `search`, `save_note`/`read_notes`,
  `write_section`/`read_draft` and `finish`.
- The system prompt is a neutral agent instruction plus the case's `prompt.md`, verbatim. The model never sees the rubric.
- Notes and the draft are kept outside the context. When the prompt would exceed the budget, the oldest tool outputs are
  replaced by one-line stubs.
- Thinking is on at reasoning effort 50 (the model card's setting), temperature 1.0, top_p 1.0, seed 1. The settings
  used were: context budget 131,072 tokens, `max_tokens` 16,384 per turn, at most 300 turns, and a 5-hour wall limit.
- Every request is reconstructible from the transcript: `--replay` rebuilds any turn's exact request body and checks its
  sha256.
- The run ends as exactly one of FINISHED, TIMEOUT, CONTEXT_EXHAUSTED or ERROR. There are no retries.
- `--gate dgx` (wait until our shared server is idle before each request) needs a site-specific file that is not
  published. Use the default `--gate none`.

**Grading** ([`build_grading_pack.py`](../legora-bar/harness/build_grading_pack.py),
[`JUDGE_PROMPT.md`](../legora-bar/grading/JUDGE_PROMPT.md), [`merge_grades.py`](../legora-bar/harness/merge_grades.py)).
- The rubric is parsed into [`criteria.jsonl`](../legora-bar/grading/criteria.jsonl): 175 criteria (74 high, 98 medium,
  3 low), each with its citations.
- Claude Opus 5.5 (as a Claude Code subagent) graded them in 12 batches of about 15. It read the whole candidate file
  and gave each criterion PASS, FAIL or UNGRADABLE, with a reason and a quote.
- The merge script computes the unweighted count and the weighted percentage shown above.

## Files

| Path | What it is |
|-|-|
| `legora-bar/harness/` | the extraction, agent, grading-pack and merge scripts |
| `legora-bar/grading/` | the judge instruction and the parsed rubric |
| `legora-bar/results/sparks-r1/master_file.md` | the model's Master File, unedited |
| `legora-bar/results/sparks-r1/grades.jsonl` | 175 verdicts with reasons and quotes |
| `legora-bar/results/sparks-r1/score.json` | the totals, by importance and by theme |
| `legora-bar/results/sparks-r1/run.json` | run settings, token counts and outcome; the server address is replaced by `<head>` |
| `legora-bar/results/sparks-r1/transcript.jsonl.gz` | every request and response of the run |

## Reproduce

```bash
git clone https://github.com/legora-oss/legora-bar-tax-case case            # f5032cb
python3 legora-bar/harness/extract_matter.py --help                          # needs pymupdf, python-docx/lxml, python-pptx, openpyxl, tokenizers
python3 -I legora-bar/harness/legbar_agent.py --base-url http://<head>:8000/v1 \
  --model DeepSeek-V4.1-Flash-1017-EXL3-Spark-TP2 --label my-run \
  --matter matter --task case/prompt.md --runs runs --tokenizer /opt/dsv41/tokenizer/tokenizer.json \
  --ctx-budget 131072 --max-tokens 16384 --max-turns 300 --wall-s 18000 --seed 1 \
  --read-max-chars 16000 --keep-recent 6 --elide-to 0.6 --request-timeout 1800
python3 -I legora-bar/harness/build_grading_pack.py --help                   # then grade each batch with JUDGE_PROMPT.md
python3 -I legora-bar/harness/merge_grades.py --help
```

The Freshworks case is © its authors under Apache-2.0. The matter documents are not copied here; clone them from the
link above. `legora-bar/grading/criteria.jsonl` is the case's rubric, parsed, with its citations, under the same licence.
