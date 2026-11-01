# Changelog

Dates are UTC. "Production" is the commit serving on our two Sparks at the time.

## 2026-11-01: the repository's new name, and the xgrammar flag in the launch file

- Renamed on GitHub to `DGX-sPLIce-DeepSeek-V4.1-Flash-2xDGX-Spark-2xRTX3090-drafter-x86-offload`, so the name says
  what the build is: DGX sPLIce, two DGX Sparks and the 2x RTX 3090 drafter on the x86 host. The old address,
  `ProprietaryLegal/DeepSeek-V4.1-Flash-2xDGX-Spark-x86-offload`, redirects here for the web page and for `git clone`
  and `git pull`; existing clones need no change. The Hugging Face card keeps its name.
- `offload/launch/dsv41_tp2_offload.sh` now passes `--structured-outputs-config.backend xgrammar` to `vllm serve`, the
  fix for the forced-tool-call known issue that production has run since 2026-10-31. Apart from comments, the launch file
  is now line for line what production runs. `.publication/SOURCE.json` records the change.
- No new measurements: every number in the README and the docs is unchanged.

## 2026-10-31, third update: the tool_choice fix in production, tool-eval-bench, the 131K llama-benchy row

- Fixed in our production: the known issue with `tool_choice` "required" and named tools (HTTP 500). Production
  (`ebc29ed8`) was restarted on 2026-10-31 with `--structured-outputs-config.backend xgrammar` added to its launch file,
  the only change to the serving configuration. Checked after the restart: forced and named tool calls and strict tools
  in `auto` mode work; a `pattern` + `maxLength` schema gets HTTP 400 "not supported by xgrammar", the documented
  trade-off; greedy output is identical to before on 6 prompts, 3 runs each; a 15-minute health watch passed. The README
  entry stays, for other V4.1 vLLM users. The launch file in this repository does not carry the flag yet.
- MEASURED, 17:13-17:44 UTC, after the fix: tool-eval-bench 3.0.1.dev7 (`887b537`), Hard Mode, 104 scenarios, seed 42,
  temperature 0, `--parallel 4`: 96 (200/208) at effort max, 92 (192/208) at high. Against the published runs of the
  same scenarios and grading (NVIDIA forum topic 386125), all labelled settings differ: 1 point behind 0rand's 97
  (#271 / #288) and dashtotherock's 97 (#307) at max, a loss; level with bernisse's best run of MiaAI-Lab's 1017 recipe
  (96 with patch 0039, #322) at max and with dashtotherock's 92 at high; 2 points ahead of bernisse's runs without that
  patch (94 at max, 90 at high), within the 1-2 points that batching can move, so not counted as wins.
- MEASURED, 17:45-17:48 UTC: the llama-benchy 0.4.0 standard row at depth 131,072, which the second update left pending:
  pp2048 2,577.94 ± 5.09 t/s, first response 51.81 s; tg32 68.36 ± 18.23 t/s (3 runs). It ran on production after the
  restart; the xgrammar flag changes only structured-output requests, and llama-benchy sends none.
- `v41_suite` tools stays 10/12: the suite was not re-run. Its two failures, the forced-choice requests, have passed in
  production since the fix.
- Hero unchanged: none of the new numbers is a same-protocol win.
- Not in this commit: the raw tool-eval-bench and llama-benchy result files.

## 2026-10-31, second update: the name DGX sPLIce, and new measurements

- Name: the build is now called **DGX sPLIce** (the PLI is Proprietary Legal Intelligence): DeepSeek V4.1 Flash served
  across two DGX Sparks, spliced with an x86 box that drafts tokens for them. The repository name, the model id, image
  digests and file paths are unchanged; `.publication/SOURCE.json` gains a `name` field.
- MEASURED, production `ebc29ed8`, 06:22-07:00 UTC: ports of the other two-Spark builds' own benchmarks (bertholomus's
  `kit_bench`, tonyd2wild's `v41bench`, Elevatormusic's `v41_suite` and `v41_bench`, HeNryous's `fair_bench` and
  three-code needle, jayleaton's tool chains, ToolCall-15), every row labelled same protocol, port or different
  benchmark. Wins: the 315,207-token needle 3/3 with its first token in 124.2 s (HeNryous's v4i image: 152 s for 314K);
  Elevatormusic's ORCHID needle 1.44-1.48x faster than TensorFold; `v41bench` prefill at its 128K target +10.8 %;
  `v41_bench` code at 4 streams 157.2 against TensorFold's 140.3. Losses, listed as plainly: `kit_bench` set b at one
  stream (89.9 / 45.8 / 135.3 code / prose / structured, behind every build that publishes it), `v41bench` aggregate at
  1-4 streams, `v41_suite` single-request decode, prose on `v41_bench`, `fair_bench` beside background prefills (our
  largest gap), decode while answering a long needle, and tool checks (`v41_suite` tools 10/12, jayleaton's chains 10/12
  and 9/12 against 11/12). Tables in the README and `docs/comparison.md`.
- MEASURED, 11:01-11:20 UTC: llama-benchy 0.4.0 from PyPI, unmodified: the standard table at depths 0-65,536 (the
  131,072 row: rerun pending, a benchmark-harness timeout, not a server fault), concurrency at 1 / 2 / 4 streams, and
  PILCOTHINK's grid from NVIDIA forum topic 386574 in api latency mode: prefill +23 to +47 % and decode +12 to +30 %
  against PILCOTHINK's published numbers (same tool; we used a fresh `cache_salt` on every request where PILCOTHINK ran
  with the prefix cache on, and DSpark k = 5 against k = 3).
- README hero: our own absolute numbers (prefill, structured and code at 4 streams, tool-call fidelity) plus the
  llama-benchy result against PILCOTHINK's grid. The MiaAI figures moved to the head-to-head table, labelled port, with
  the losses: code -6.4 % at one stream, prose -18.2 / -15.5 % and thinking-mode prose -12.5 / -12.7 % at one / four
  streams.
- MEASURED: the persistent prefix tier across production restarts, on a synthetic test prompt. Stored at 06:21 UTC,
  two engine restarts, sent again at 10:56 UTC: 4,992 of 5,050 prompt tokens (98.9 %) came from the tier, 2.0 s against
  10.2 s uncached (whole-request wall time).
- MEASURED: a kernel census of a cold 31,633-token prefill on production, profiler overhead 0.08 %: MoE experts 47.5 % of
  the time to first token, norms and elementwise 17.0 %, attention 13.1 %, dense GEMM 13.0 %, all-reduce 6.4 %; every
  line, both ranks and every chunk in `docs/measurements.md`. A 150K census was attempted, but its traces missed 4 of its
  19 chunks, so it is not published.
- Known issue documented: `tool_choice` "required" or a named tool can return HTTP 500 when vLLM has pinned guidance as
  its structured-outputs backend. Workaround: `--structured-outputs-config.backend xgrammar`. Status: fix built and
  tested offline; production install pending.
- Correction: the previous README called the MiaAI sparkDash comparison 'same protocol'. It is a port, because MiaAI's
  prompts are not published, and our Sparks were clocked 100 MHz higher.
- Not in this commit: the ported benchmark scripts and raw result files of the 2026-10-31 runs, and the prefix tier's
  code.

## 2026-10-31: flagship repository

- MEASURED: MiaAI's sparkDash protocol on production `ebc29ed8` (2,300 MHz cap, drafter GPUs at 400 W, 4 sequences, 3
  repeats): prefill 2,606-2,827 tok/s from 4K to 256K; code 110.5 / 192.0 tok/s at 1 / 4 streams; structured 138.3 /
  322.1; prose 66.0 / 130.1; thinking prose 55.9 / 105.3; decode after 128K 61.9; short chat behind a cold 93K prompt
  34.3 s. Raw file in `runs/`, tables in `docs/measurements.md`.
- New `tools/sparkbench.py`, a Python re-implementation of the sparkDash protocol (credited in CREDITS.md).
- README: quality section first (KLD and top-1 against the original model, with both the served weights and HeNryous's),
  a head-to-head with MiaAI-Lab and bertholomus that lists our losses, and a table of other two-Spark builds.
- Corrected: earlier text called the served weights a re-quantization of our own without saying how little of
  HeNryous's build it changes; the README now names HeNryous's weights next to every quality number.
- This repository now carries the full production tree (exported from production `ebc29ed8`), not only an overview and
  configuration examples. The previous README and `config/*.env.example` files are replaced by the real `dsv41.env`,
  `serve.sh` and launcher scripts.
- New `tools/bench.py`: MiaAI-conditions and our-conditions profiles, synthetic prompts, JSON output, `compare` mode;
  `tools/node_watch.py` and `tools/fake_server.py`, with CPU tests.
- New `docs/measurements.md`, `docs/comparison.md`, `docs/architecture.md`, `docs/operations.md`, `CREDITS.md`,
  issue and pull-request templates.
- New `docs/install.md`: the full build in order (cabling, the image by digest, launcher, weights, the x86 host's
  drafter and Engram files and services, `dsv41.env`, first start, checks). README: hero numbers, server limits and
  memory table.
- Not in this commit: the persistent prefix tier's code (`offload/prefixstore/` except the launcher glue). Three of its
  overlay files need a source-side fix and new pins before they can be published byte for byte; it follows in the next
  push. Its measurements are published now. See `docs/publication.md`.

## 2026-10-30: persistent prefix tier bounds raised (production `ebc29ed8`)

- Tier bounds 64 GiB total, 8 GiB per namespace, 30-day expiry.
- MEASURED: 150K prompt TTFT 2.58 s from the tier against 58.59 s cold (6 trials).

## 2026-10-29 to 2026-10-30: persistent prefix tier

- Opt-in per-namespace KV tier on the Sparks' NVMe (patches 0100-0106); untagged requests bypass it.

## 2026-10-28 to 2026-10-29: PP4 sampled drafting

- The drafter proposes from its sampled top-32 with a fixed 5-token window; verifier changes in `offload/pp4_prod/`.

## 2026-10-28: upstream install (production `a0006fc`)

- HeNryous patches 0051, 0064, 0067, 0075, 0085b, 0091; dual RDMA ring; 5 drafts at 3-4 streams; prefill chunk 8192;
  CPU pinning; GPU clock cap 2,300 MHz.
- MEASURED: prompt reading 14-20 % faster in every cell; decode 8 % faster at 4 streams and 24-28 % faster while a
  long prompt is read; single-stream decode unchanged within noise.

## 2026-10-23 to 2026-10-27

- Async round proxy and the two-card NVLink drafter worker in production; KV page packing at 327,680 tokens.
- 2026-10-27: the source of every component published in [dsv41-offload](https://github.com/ProprietaryLegal/dsv41-offload).

## 2026-10-22: offload configurations B and D

- B: Engram tables from x86 RAM over RDMA. D: the drafter on an x86 RTX 3090, freed memory spent on KV (+62 % tokens).

## 2026-10-21

- Served weights switched to the 2.75 bpw legal-weighted re-quantization.
