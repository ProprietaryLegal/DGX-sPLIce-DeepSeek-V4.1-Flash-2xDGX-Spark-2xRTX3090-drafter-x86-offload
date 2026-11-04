# DGX sPLIce: DeepSeek-V4.1-Flash on 2x DGX Spark + 2x RTX 3090 drafter, x86 offload

[![proprietarylegal.ai](https://img.shields.io/badge/proprietarylegal.ai-website-0B3D91)](https://proprietarylegal.ai) [![PLI Labs](https://img.shields.io/badge/PLI%20Labs-research-1F6FEB)](https://proprietarylegal.ai/labs.html) [![Hugging Face](https://img.shields.io/badge/Hugging%20Face-card-FFD21E)](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-2xDGX-Spark-x86-offload) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE) [![Hardware: 2x DGX Spark + x86](https://img.shields.io/badge/hardware-2x%20DGX%20Spark%20%2B%20x86%20offload-76B900)](#requirements) [![Raw data: runs/](https://img.shields.io/badge/raw%20data-runs%2F-555555)](runs/)

Built by **Nick Mermiges, Esq.**, founder of [PLI Labs](https://proprietarylegal.ai/labs.html) · [proprietarylegal.ai](https://proprietarylegal.ai)

DGX sPLIce (the PLI is Proprietary Legal Intelligence) is our name for this build: DeepSeek V4.1 Flash served across two DGX Sparks, spliced with an x86 box that drafts tokens for them.

DeepSeek-V4.1-Flash-1017 (EXL3, 2.75 bpw) served by vLLM across two NVIDIA DGX Spark / GB10 nodes in tensor parallel. A third,
ordinary x86 machine does two jobs for them: it holds the Engram tables in RAM and serves them over RDMA, and it runs the
DSpark speculative drafter on a pair of RTX 3090s. The memory this frees on the Sparks goes to KV cache, a pool of 1,934,490
tokens. A persistent prefix tier on the Sparks' NVMe lets a long prompt be read back after a restart instead of prefilled
again.

<table>
<tr>
<td align="center"><h2>2,606&#8209;2,827</h2>tok/s prefill<br><sub>4K to 256K-token prompts</sub></td>
<td align="center"><h2>322</h2>tok/s structured output<br><sub>4 streams; 138 at one</sub></td>
<td align="center"><h2>192</h2>tok/s code<br><sub>4 streams</sub></td>
<td align="center"><h2>+23&#8209;47&nbsp;%</h2>prefill on llama-benchy<br><sub>against PILCOTHINK's published grid, same tool; decode +12&#8209;30&nbsp;%</sub></td>
<td align="center"><h2>95.9&nbsp;%</h2>top-1 agreement with the original<br><sub>real tool-call turns, KLD 0.018</sub></td>
</tr>
</table>

<sub>sparkDash protocol re-implemented in <a href="tools/sparkbench.py">tools/sparkbench.py</a>, production commit <code>ebc29ed8</code>, 2026-10-31, both Sparks at a 2,300 MHz clock cap, 3 repeats, median. Raw file: <a href="runs/2026-10-31-sparkdash-protocol-ebc29ed8.json">runs/</a>. llama-benchy: 0.4.0 from PyPI, unmodified, api latency mode, 2026-10-31; PILCOTHINK's grid from NVIDIA forum topic 386574, post 5. Quality: sudoingX's <code>p4_kld.py</code> panel, agentic domain.</sub>

- **95.9 % top-1 agreement with the original model on real tool-call turns** (KLD 0.018; weights by HeNryous).
  <sub>p4_kld, sudoingX's panel, agentic domain, 2026-10-21 · [quality](#quality)</sub>
- **Prefill 2,606-2,827 tok/s from 4K to 256K tokens**; a 256K prompt's first token in 100 s.
  <sub>sparkDash protocol, 2,300 MHz, commit `ebc29ed8`, 2026-10-31 · [prefill ladder](docs/measurements.md#prefill-ladder)</sub>
- **322 tok/s of structured output at 4 streams**, 138 tok/s at one.
  <sub>sparkDash "structured" prompt, T=0, 400 tokens, 3 reps · [decode cells](docs/measurements.md#decode-cells-sparkdash)</sub>
- **192 tok/s of code at 4 streams** on sparkDash's code prompts. On Elevatormusic's own `v41_bench`, same protocol,
  code at 4 streams is 157.2 tok/s against TensorFold's 140.3, level with HeNryous's vLLM builds.
  <sub>sparkDash code prompts, T=0, thinking off, 400 tokens, 3 reps · [decode cells](docs/measurements.md#decode-cells-sparkdash) · [their benchmarks](#the-other-builds-own-benchmarks-run-on-dgx-splice)</sub>
- **llama-benchy 0.4.0 on PILCOTHINK's published grid**: prefill +23 to +47 % and decode +12 to +30 % (pp2048
  1,883-2,518 tok/s against 1,420-1,749; tg 49.6-56.5 against 42.0-44.2). Same tool and grid, in api latency mode, in
  which 0.4.0 and PILCOTHINK's 0.4.1.dev1 measure alike. What still differs: every request here carried a fresh
  `cache_salt`, so the prefix cache never helped us, while PILCOTHINK ran with it on; DSpark k = 5 here, k = 3 there.
  <sub>production `ebc29ed8`, 2026-10-31, 11:01-11:20 UTC · [llama-benchy](#llama-benchy-040)</sub>
- **On the other builds' own benchmarks, same protocol**: a 315,207-token needle prompt answered 3 of 3 with its first
  token in 124.2 s (HeNryous: 152 s for 314K, on its older v4i image); Elevatormusic's ORCHID needle 1.44-1.48x faster
  than TensorFold; tonyd2wild's v41bench prefill at its 128K target +10.8 % over TensorFold TP2.
  <sub>production `ebc29ed8`, 2026-10-31 · [their benchmarks](#the-other-builds-own-benchmarks-run-on-dgx-splice)</sub>
- **Long prompts survive a restart**: a 150K-token prompt comes back from the NVMe tier in 2.58 s instead of 58.6 s of
  prefill; in production, the first request after a restart read 95.1 % of its 107,821-token prompt from the tier, and a
  5,050-token synthetic prompt stored before two engine restarts came back after them with 4,992 tokens (98.9 %) from the
  tier, in 2.0 s against 10.2 s uncached. The tier's code follows in the next push ([why](docs/publication.md#prefix-tier-code)); the measurements are
  here now.
  <sub>2026-10-30 test store, 6 trials; 2026-10-31 production counts and synthetic reload · [prefix tier](docs/measurements.md#persistent-prefix-tier-2026-10-30-and-2026-10-31-production-ebc29ed8)</sub>

We also lose on several rows, and the [head-to-head](#head-to-head) and
[their benchmarks](#the-other-builds-own-benchmarks-run-on-dgx-splice) list them: single-stream decode on most of the
other builds' own benchmarks (kit_bench, v41bench, v41_suite), prose and thinking-mode decode (also against MiaAI on
our sparkDash port), decode after a 128K
prompt, a short request behind a long prompt or beside background prefills (our largest gap),
[tool-eval-bench](#tool-eval-bench-301) at effort max by 1 point (96 against 97), streams beyond 4, and contexts beyond
327,680. Forced tool calls had a [known issue](#known-issues), fixed in our production on 2026-10-31.

**Image:** `ghcr.io/henryous/deepseek-v41-1017-dgx-spark:v5` (linux/arm64,
`sha256:8fc2c99a3562e99d81d2a05b8345d12726def0a027410d14d0eb0763de8309e4`), unmodified; `start.sh` stages our overlays
from this checkout and mounts them read-only. **Install:** [docs/install.md](docs/install.md), step by step. **Numbers:**
[docs/measurements.md](docs/measurements.md). **Raw data:** [runs/](runs/).

This repository is DGX sPLIce as it runs in production: every number we measured on it, the tools that measured them,
the raw result files and the code for every piece. Two things are not in this commit yet: the prefix tier's code, which
follows in the next push, and the ported suites and raw files behind the 2026-10-31 runs of the other builds' own
benchmarks (llama-benchy and tool-eval-bench are public and were run unmodified; their raw files are not in this commit
either). Issues, measurements on your own hardware and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

**Hugging Face:** [card](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-2xDGX-Spark-x86-offload) ·
[served weights](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-LegalWeighted-DGX-Spark) ·
[collection](https://huggingface.co/collections/ProprietaryLegal/deepseek-v41-flash-on-2x-dgx-spark-x86-offload-6adab604a517b426ded3916e)
· **Research archive:** [dsv41-offload](https://github.com/ProprietaryLegal/dsv41-offload) (every experiment branch)

<!-- pli:blurb:start -->

> Published by [PLI Labs](https://proprietarylegal.ai/labs.html), the open research arm of [Proprietary Legal Intelligence](https://proprietarylegal.ai). PLI builds AI systems around a legal organization's own work product, combining retrieval, staged workflows, validation, and attorney review. Visit [proprietarylegal.ai](https://proprietarylegal.ai) to explore our work and discuss what your organization needs.

<!-- pli:blurb:end -->

## Quality

How closely the quantized weights follow the original DeepSeek-V4.1-Flash-1017, measured with sudoingX's `p4_kld.py`
(DeepSeek's reference implementation run over the original checkpoint and over the quant, teacher-forced on the same
tokens). KLD is KL(original || quant), lower is better; top-1 is the share of positions where both pick the same token.
The weights are **HeNryous's** 2.75 bpw EXL3 build; we serve a legal-weighted allocation of it that re-encodes 1,414 of
its 15,360 routed experts at the same total size, and both columns are shown.

| Test (scored assistant positions) | Served: legal-weighted allocation | [HeNryous 2.75 bpw](https://huggingface.co/HeNryous/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-DGX-Spark) `86f85253` |
|-|-|-|
| **real tool-call turns**: sudoingX's general panel, agentic domain (24 multi-turn conversations with tool definitions, calls and results) | 0.0184 / **95.88 %** | 0.0183 / **95.91 %** |
| sudoingX's general panel, all 199 conversations, 8 domains | 0.0204 / 95.91 % | 0.0201 / 95.96 % |
| our legal panel, 210 sequences (replies sampled from a quant, which favours quants slightly) | 0.0303 / 96.85 % | 0.0329 / 96.70 % |

What the other builds publish, on their own test sets (not directly comparable with the rows above):

| Build | Tool-call turns | General text |
|-|-|-|
| [bertholomus](https://huggingface.co/bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-2.5bpw), EXL3 2.52 bpw | KL 0.5948 / 79.43 % (own set, full vocabulary) | short rows 0.1305 / 92.01 % |
| [MiaAI-Lab](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks), EAQ v1.1 2.9 bpw | not published | not published (indexer-selection agreement 403,560 of 403,560 rows) |
| [sudoingX](https://github.com/sudoingX/dgx-spark-deepseek-v41) v2.0, EXL3 2.8 bpw | KLD **0.0175** on the same panel as ours, closer than ours | 0.0198 / 95.94 %, same panel |

Our KLD keeps the original's top-128 tokens plus a tail bucket, so it is a lower bound; bertholomus scores the full
vocabulary. A same-test run of bertholomus's and MiaAI's weights on our panels is in progress; until then the
[same-test table](docs/measurements.md#quality-kl-divergence-against-the-original-model) says "pending". These numbers
measure the weights. Speculative decoding does not change them at temperature 0 as far as the engine's identity tests
show, and we claim nothing beyond those tests.

## Legal agent task: Legora BAR public tax case

[Legora's BAR](https://legora.com/bar) public case ([legora-oss/legora-bar-tax-case](https://github.com/legora-oss/legora-bar-tax-case))
asks for a full transfer pricing Master File for the Freshworks Group, FY2023, from a 72-file matter folder of about 1.33 M
tokens, graded on 175 expert-written criteria. One run on this build (2026-11-04, thinking on at effort 50, our open
agent harness, a Claude Opus 5.5 judge using the rubric's own grading guidance):

| | Passed | Score |
|-|-|-|
| All 175 criteria, unweighted | **129 / 175** | **73.7 %** |
| Importance-weighted (high 3, medium 2, low 1) | 315 / 421 | 74.8 % |
| High-importance criteria | 60 / 74 | 81.1 % |

The run took 112 turns and 27.7 minutes, with 87,596 output tokens and no tool errors. The one independent public
table for this case ([Overfitting Dicta](https://overfittingdicta.com/)) has the frontier models at 48.0-71.4 % unweighted
(Opus 5.5 Xhigh at 125 / 175). It uses a different, unnamed harness and judge, so read that as "in the same range", not as a ranking.
Per-theme scores, the misses, the comparison table and its caveats, the harness, every verdict, the model's Master File
and the full transcript are in [docs/legora-bar.md](docs/legora-bar.md) and [`legora-bar/`](legora-bar/).

## Head-to-head

Three builds of DeepSeek-V4.1-Flash-1017 on two DGX Sparks, every metric any of them publishes. MiaAI's numbers come
from its [sparkDash](https://github.com/MiaAI-Lab/sparkDash) dashboard, ours from [tools/sparkbench.py](tools/sparkbench.py),
a re-implementation of sparkDash `b96244a2` with sparkDash's own lab prompts. MiaAI's repository does not record which
prompts its run sent, so these rows are labelled **port**: the same method, possibly not the same prompts. Our Sparks
also ran at a 2,300 MHz clock cap, MiaAI's at 2,200 MHz. No port row is counted as a true win. bertholomus
uses its own prompt sets, so its decode rows are **not comparable** with either here; its own benchmark, run on DGX
sPLIce with the same protocol, is in the [next section](#the-other-builds-own-benchmarks-run-on-dgx-splice).

Our conditions for every row: production `ebc29ed8`, 2026-10-31, both Sparks at a 2,300 MHz clock cap, drafter GPUs at a
400 W cap (325 W in production; they drew 22-112 W in the samples taken), `max-num-seqs` 4, 3 repeats, median.

| Metric | **DGX sPLIce** | [MiaAI-Lab](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks) | [bertholomus](https://huggingface.co/bertholomus/DeepSeek-V4.1-Flash-TensorFold-TP2-2xGB10) v0.7.3 | Basis |
|-|-|-|-|-|
| engine, weights | vLLM 0.31.1.dev0 + overlays, EXL3 2.75 bpw | TensorFold, EAQ 2.9 bpw | TensorFold, EXL3 2.52 bpw (~185 GB) | |
| extra hardware | x86 host, 2 x RTX 3090 | none | none | |
| GPU clock cap | 2,300 MHz | 2,200 MHz | not stated | |
| prefill 4K / 8K / 16K | **2,827 / 2,813 / 2,606** | 2,106 / 2,152 / 2,155 | - / 2,439 / - | port (sparkDash) |
| prefill 32K / 64K / 128K / 256K | **2,667 / 2,641 / 2,650 / 2,618** | 2,154 / 2,136 / 2,077 / 2,065 | 2,568 / 2,550 / 2,523 / - | port (sparkDash) |
| 256K prompt, first token | **100.4 s** | 127.1 s | - | port (sparkDash) |
| code T=0, 1 / 2 / 3 / 4 streams, total | 110.5 / 147.9 / **174.8 / 192.0** | **118.1 / 149.4** / 171.0 / 166.1 | 1 stream 112.7 (set b, 384 tokens) | port (sparkDash) |
| prose T=0, 1 / 2 / 3 / 4 streams, total | 66.0 / 90.5 / 112.4 / 130.1 | **80.7 / 110.6 / 133.6 / 154.0** | 1 stream 67.5 (set b) | port (sparkDash) |
| prose T=0.7 thinking on, 1-4 streams | 55.9 / 72.0 / 90.8 / 105.3 | **63.9 / 93.3 / 107.8 / 120.6** | not published | port (sparkDash) |
| structured T=0, 1 / 4 streams | 138.3 / **322.1** | not published | 1 stream **159.5** (set b) | not comparable |
| 4 streams, mixed set, total | prose 130.1, code 192.0 | see above | 134.0 (set b) | not comparable |
| 8 streams | not supported (4 max) | not published | **168.3** sustained | |
| TTFT, 1 stream: prose / code / thinking | 146 / 215 / 221 ms | **133 / 213 / 214 ms** | - | port (sparkDash) |
| decode after a 128K prompt, 1 stream | 61.9 (sparkDash prose) | not published | **99.2** (median of 3 own prompts) | not comparable |
| short chat behind a cold 93K prompt, first token | 34.3 s | **3.84 s** (different test: 8 s into a 70K prompt) | 38.6 s | same design with bertholomus |
| longest context per request | 327,680 | 524,288 | **1,048,576** | |
| tool-call turns, top-1 vs original | **95.9 %** | not published | 79.4 % | different test sets |

Against MiaAI on the sparkDash port, with the delta, (ours - MiaAI) / MiaAI (label: **port**; 2,300 against 2,200 MHz):

| sparkDash row | DGX sPLIce | MiaAI 1017 | Delta |
|-|-|-|-|
| code T=0, 1 / 2 / 3 / 4 streams | 110.5 / 147.9 / 174.8 / 192.0 | 118.1 / 149.4 / 171.0 / 166.1 | -6.4 / -1.0 / +2.2 / +15.6 % |
| prose T=0, 1 / 4 streams | 66.0 / 130.1 | 80.7 / 154.0 | -18.2 / -15.5 % |
| prose T=0.7 thinking on, 1 / 4 streams | 55.9 / 105.3 | 63.9 / 120.6 | -12.5 / -12.7 % |
| prefill 4K to 256K | 2,606-2,827 | 2,065-2,155 | +21 to +34 % |
| 256K prompt, first token | 100.4 s | 127.1 s | 21 % less time |

**Where we lose.** On the sparkDash port, prose decode at T=0 is 18.2 % behind MiaAI at one stream (66.0 against
80.7) and 15.5 % at four; thinking-mode prose is 12.5 % behind at one stream and 12.7 % at four (22.8 % at two); code
is 6.4 % behind at one stream and 1.0 % at two. Decode after a 128K prompt is
far below bertholomus's figure (different prompts, but the gap is large). On prose the drafter has 2.1-2.3 of its 5
drafted tokens accepted per round, against 4.2-4.5 on code and 4.96 on structured output
([decode cells](docs/measurements.md#decode-cells-sparkdash)). A short request sent behind a long cold prompt
gets its first token only when the long prefill is almost done (34 s against 35 s for the long prompt); MiaAI's engine
lets such a request in early. We serve at
most 4 streams and 327,680 tokens; bertholomus serves 8 streams and 1M tokens. We have not run 1M context. Our
sparkDash single-stream figures (110.5 code, 66.0 prose) are not a ranking: on bertholomus's kit_bench set b, the
benchmark most builds publish, we measure 89.9 code and 45.8 prose and trail every build that publishes it
([next section](#the-other-builds-own-benchmarks-run-on-dgx-splice)).

**Where we are ahead** (port or different prompts, so not counted as true wins). Prefill at every size from 4K to
256K, by 21-34 % over MiaAI (port) and 4-15 % over bertholomus (different prompts) at the sizes each publishes (even our uncorrected prompt / TTFT rates are higher). Code at 3 and 4
streams (+2 % and +16 % over MiaAI, port).
Tool-call fidelity against bertholomus, the other build here that publishes it, with the caveat that the test sets
differ; sudoingX's 2.8 bpw pack is slightly closer than ours on our own panel. Structured output reaches 322 tok/s at 4
streams, a row neither other build publishes.

Every cell, every repeat, TTFT, acceptance per draft round, deep-context decode and the clock and temperature log:
[docs/measurements.md](docs/measurements.md#sparkdash-protocol-2026-10-31). The raw file:
[runs/2026-10-31-sparkdash-protocol-ebc29ed8.json](runs/2026-10-31-sparkdash-protocol-ebc29ed8.json). Sources and
conditions for every other build's number: [docs/comparison.md](docs/comparison.md).

## The other builds' own benchmarks, run on DGX sPLIce

On 2026-10-31 we ported the benchmarks most of the other two-Spark builds publish (kit_bench, v41bench, v41_suite,
v41_bench, fair_bench, their needle tests and tool checks) and ran them on production `ebc29ed8` (06:22-07:00 UTC, 439
requests). Conditions: both Sparks at a 2,300 MHz clock cap, drafter GPUs at a 400 W cap (325 W
in production), `max-num-seqs` 4, context limit 327,680, DSpark sampled drafting with a fixed window of 5. Every request
carried a fresh `cache_salt` and a unique first line, so no prefix cache helped. Their numbers are quoted as each build
published them, from its README, results file or forum post at the commit named in
[docs/comparison.md](docs/comparison.md#the-other-builds-own-benchmarks-2026-10-31); we computed only the delta, (ours -
theirs) / theirs. For time rows a negative delta means we are faster.

- **same protocol**: our port of their script, with their prompts and parameters; the only deviations are the unique
  first line and the fresh cache salt.
- **port**: a re-implementation of a protocol whose prompts are not published, or a port that deviates in a way that
  matters (named in the row).
- **different benchmark**: another benchmark of the same quantity; an indication only.
- **settings differ**: the same tool and grid, with server or run settings that differ (named in the row).

**Where we win** (same protocol, margin outside noise):

| Benchmark | DGX sPLIce | Theirs | Delta | Label |
|-|-|-|-|-|
| HeNryous 3-code needle (10 / 50 / 90 % depth), 315,207-token prompt | 3/3, first token 124.2 s (2,538 tok/s) | HeNryous image v4i: 314K, 3/3, 152 s (2,066 tok/s) | 18.3 % less time, +22.8 % rate | same protocol; their older image |
| Elevatormusic `v41_suite` ORCHID needle, request time at 64K / 200K | 24.3 / 76.3 s | TensorFold 35.9 / 109.8 s | 1.48x / 1.44x faster | same protocol |
| tonyd2wild `v41bench` prefill, 128K target (186,792 tokens) | 2,265.7 tok/s | tonyd2wild TensorFold TP2 2,044.4; Blackwellboy 1,891.2 | +10.8 % / +19.8 % | same protocol; at 64K +3.0 %, at 32K a tie |
| Elevatormusic `v41_bench`, code, 4 streams, aggregate (per request) | 157.2 (42.0) tok/s | TensorFold 140.3 (36.8) | +12.0 % (+14.1 %) | same protocol; level with HeNryous 154.0 and v5 155.9 |
| Elevatormusic `v41_suite` cold prefill, 32K | 2,246.9 tok/s | 2,100 | +7.0 % | same protocol |

Level with the others: Elevatormusic's structured-output group 6/6 (strict `json_schema` 8/8 with thinking off and on),
its reasoning and no-leak checks, and `v41bench` per-stream speed at 4 streams (41.38 against tonyd2wild's 41.39).
On tool-eval-bench (settings differ) we are level with bernisse's best run of MiaAI-Lab's 1017 recipe at effort max (96)
and with dashtotherock at effort high (92); see [tool-eval-bench](#tool-eval-bench-301).

**Where we lose** (stated as plainly as the wins):

| Benchmark | DGX sPLIce | Theirs | Delta | Label |
|-|-|-|-|-|
| HeNryous `fair_bench`: foreground decode beside 1 / 2 background prefills | 10.1 / 5.5 tok/s | HeNryous ~29 / ~23; 58.5 / 59.1 on v22 | -65 / -76 %; -83 / -91 % against v22 | port: shorter background requests, and only the first of 3 repeats overlapped them. Our largest gap |
| `fair_bench` foreground alone, 600 tokens | 45.2 tok/s | 55.9 (v20), 57.2 (v22) | -19.1 / -20.9 % | port |
| bertholomus `kit_bench` set b, 1 stream: code / prose / structured | 89.9 / 45.8 / 135.3 | bertholomus v0.7.3 112.7 / 67.5 / 159.5; sudoingX v2.0 103.9 / 57.9 / 144.0; Blackwellboy 103.79 / 58.84 / 144.55; HeNryous v20 99.5 / 55.3 / 138.9; Elevatormusic 98.6 / 56.8 / 139.7 | code -8.8 to -20.2 %, prose -17.3 to -32.2 %, structured -2.6 to -15.2 % | same protocol |
| `kit_bench` set b aggregate: 2 streams / 4 streams / 4 streams sustained 90 s | 67.6 / 100.4 / 115.4 | 77.7-95.3 / 116.7-134.0 / 120.0-151.8 | -13.0 to -29.1 % / -13.9 to -25.1 % / -3.8 to -24.0 % | same protocol, our 2 repeats against their median of 9 |
| tonyd2wild `v41bench` aggregate, 1 / 2 / 3 / 4 streams | 62.9 / 83.4 / 107.7 / 129.0 | 73.1 / 106.0 / 123.7 / 135.8 | -13.9 / -21.4 / -12.9 / -5.0 %; first token 17-47 % later | same protocol |
| `v41bench` prefill, 8K target (11,611 tokens) | 1,973.3 tok/s | 2,180.2 | -9.5 % | same protocol |
| Elevatormusic `v41_suite`, 1 request: prose / code / prose thinking / code thinking | 45.9 / 87.1 / 46.9 / 64.7 | TensorFold 56.8 / 92.2 / 54.2 / 71.6 | -19.3 / -5.5 / -13.5 / -9.6 % | same protocol |
| Elevatormusic `v41_bench`, prose, 2 / 3 / 4 streams; code, 1 stream | 54.9 / 68.9 / 73.9; 73.4 | TensorFold 73.5 / 82.3 / 94.4; 94.1 | -25.3 / -16.3 / -21.7 %; -22.0 % | same protocol; its aggregate includes the first-token wait, and one of our two 1-stream code repeats waited 1.9 s |
| decode while answering a needle, after 131K / 315K tokens | 44.2 / 38.2 tok/s | after 128-131K: bertholomus 99.2, sudoingX 81.3, HeNryous v20 73.7, jayleaton 64.9 | -32 to -55 % | different benchmark |
| tool calls: Elevatormusic `v41_suite` tools group | 10/12 | 12/12 | -2 | same protocol; the two failures are the forced-choice cases of the [known issue](#known-issues). The same two requests have passed in production since the 2026-10-31 fix; the suite was not re-run, so the score stays 10/12 |
| tool calls: jayleaton `chains.py`, thinking off / effort high | 10/12 / 9/12 | 11/12 (their earlier run) | -1 / -2 points | same protocol; retry-after-error scores 0 in both modes |
| tool-eval-bench 3.0.1 Hard Mode, 104 scenarios, effort max | 96 (200/208) | 0rand, forum 386125 #271 / #288: 97 (202/208); dashtotherock, #307: 97 (202/208) | -1 point | settings differ: `--parallel 8` there, 4 here; #288 at temperature 0.6. [Details](#tool-eval-bench-301) |
| longest needle | 315,207 tokens, 3/3 (our 327,680 limit) | bertholomus 1,039,836, 3/3; MiaAI 1017 479,012, 3/3 | | a configuration limit |

Draft acceptance explains part of the single-stream gap: on kit_bench's prose prompt the drafter has 1.19 of its 5
tokens accepted per round, against 2.14 on sparkDash's prose prompt (kit_bench code 3.31, structured 5.0). No other
build publishes its kit_bench acceptance, so we cannot yet say how much of the gap is the drafter and how much the base
decode. HeNryous's v21 and v22 `fair_bench` numbers come from scheduler patches (0031, priority-aware prefill
throttling, plus 0073 and 0074) that we do not run; with chunked prefill at 8,192 tokens, every foreground decode step
here waits on a background chunk.

One row is withheld, in both directions: our `v41_suite` cold 8K prefill read 1,522.6 tok/s (HeNryous v12: 2,470), but
that request waited about 2 s before its first token that the same pass's 8,167-token needle (2,586.9 tok/s) did not.
It is not counted until the delay is explained. Every table, source and commit, plus the different-benchmark prefill
rows: [docs/comparison.md](docs/comparison.md#the-other-builds-own-benchmarks-2026-10-31).

## tool-eval-bench 3.0.1

[tool-eval-bench](https://github.com/SeraphimSerapis/tool-eval-bench) (TEB), SeraphimSerapis's tool-calling benchmark
and the tool-calling score most often posted for this model on two Sparks, at `3.0.1.dev7+g887b537` (main; 3.0.1 has no
tag or PyPI release), run unmodified against production (`ebc29ed8` plus the xgrammar flag of the
[known issue](#known-issues)) on 2026-10-31, 17:13-17:44 UTC: Hard Mode, 104 scenarios / 208 points, seed 42,
temperature 0, thinking on, `max_tokens` 16384 (the tool's default), `--parallel 4` (our server runs at most 4 streams).
Same clock, power and request rules as the sections above: every one of its 688 requests carried a fresh `cache_salt`
and a unique first line, and every one was answered with HTTP 200. Each scenario scores pass 2, partial 1 or fail 0; the
score is points / 208 x 100.

| Effort | DGX sPLIce | Pass / partial / fail | Lowest category |
|-|-|-|-|
| max | **96** (200/208) | 98 / 4 / 2 | Autonomous Planning 67 % |
| high | **92** (192/208) | 93 / 6 / 5 | Safety & Boundaries 85 % |

The published runs with the same 104 scenarios and the same grading code (unchanged from v3.0.1.dev6 to `887b537`), all
in [NVIDIA forum topic 386125](https://forums.developer.nvidia.com/t/386125):

| Their run | Theirs | DGX sPLIce | Delta | Label |
|-|-|-|-|-|
| 0rand, TensorFold, posts #271 and #288, v3.0.1.dev6, effort max | 97 (202/208) | 96 (200/208) | **-1** | settings differ: `--parallel 8` there; #288 at temperature 0.6 |
| dashtotherock, 0rand's code (main_0rand branch), post #307, effort max | 97 (202/208) | 96 (200/208) | **-1** | settings differ: `--parallel 8` there |
| dashtotherock, post #307, effort high | 92 | 92 (192/208) | level | settings differ: `--parallel 8` there |
| bernisse, MiaAI-Lab's 1017 recipe with patch 0039, post #322, v3.0.1.dev7, effort max | 96 (200/208) | 96 (200/208) | level | settings differ: `--parallel 1` there; the same seed, Hard Mode, temperature 0 and `max_tokens` 16384 |
| bernisse, the same recipe without that patch, post #322, effort max / high | 94 (196/208) / 90 (187/208) | 96 / 92 | +2 / +2 | settings differ: `--parallel 1` there |

At temperature 0 the `--parallel` setting mostly changes timing, but a different batch can move a greedy token now and
then, so 1-2 points is within the noise between these runs. We still list the 1-point deficit at effort max as a loss,
and we do not count the 2-point leads as wins. The older TEB 2.x posts (88-97 scenarios) are a different benchmark, so
PILCOTHINK's 92 (179/194, TEB 2.8.1, [forum topic 386574](https://forums.developer.nvidia.com/t/386574), post 1) is not
set against these runs. Re-scored on those 97 scenario ids, ours read 96 (187/194) at max and 94 (182/194) at high, but
32 of the 97 scenario files and the shared grading helpers changed in 3.0, so that is an indication only. TEB's safety
gate flags scenario TC-92 (tenant isolation with same-named resources) in both runs, and TC-98 (multi-hop prompt
injection) at high; PILCOTHINK's post carries the same TC-92 warning.

## llama-benchy 0.4.0

[llama-benchy](https://github.com/eugr/llama-benchy) 0.4.0 from PyPI, pinned and run unmodified against production
`ebc29ed8` on 2026-10-31, 11:01-11:20 UTC (154 requests; same clock, power and request rules as the section above, at
most 4 in flight). Values are mean ± std over 3 runs as llama-benchy reports them. Its pp rate counts the depth tokens
too: (depth + 2,048) / estimated prompt time.

Standard table (pp2048 / tg32, one stream, `--latency-mode generation --no-cache`):

| Depth | pp2048 t/s | time to first response | tg32 t/s |
|-|-|-|-|
| 0 | 2,161.11 ± 15.93 | 1.12 s | 47.36 ± 7.47 |
| 4,096 | 2,625.76 ± 12.20 | 2.52 s | 50.25 ± 9.53 |
| 8,192 | 2,488.00 ± 2.68 | 4.29 s | 49.53 ± 4.27 |
| 16,384 | 2,512.40 ± 25.28 | 7.51 s | 52.55 ± 8.35 |
| 32,768 | 2,542.76 ± 9.23 | 13.87 s | 59.92 ± 4.21 |
| 65,536 | 2,495.40 ± 47.12 | 27.27 s | 55.72 ± 7.05 |
| 131,072 | 2,577.94 ± 5.09 | 51.81 s | 68.36 ± 18.23 |

The 131,072 row's first attempt hit a benchmark-harness timeout, not a server fault; it was rerun at 17:45-17:48 UTC
(11 requests) on production after its restart with the xgrammar flag ([known issues](#known-issues)), while the other
rows come from the 11:01 UTC run before it. The flag changes only structured-output requests, and llama-benchy sends none.

Concurrency (pp2048 / tg128 at 1, 2 and 4 streams, `--latency-mode generation --no-cache`). tg is the aggregate; the
per-request tg and the aggregate peak are in parentheses:

| Depth | 1 stream: pp / tg | 2 streams: pp / tg | 4 streams: pp / tg |
|-|-|-|-|
| 0 | 2,146.99 / 52.39 | 2,042.72 / 67.71 (36.37; peak 88.33) | 2,283.97 / 90.47 (26.62; peak 124.67) |
| 4,096 | 2,615.40 / 59.10 | 2,422.16 / 45.90 (32.56; peak 88.00) | 2,438.02 / 41.29 (18.93; peak 127.33) |
| 8,192 | 2,474.86 / 54.61 | 2,391.81 / 32.65 (26.54; peak 84.67) | 2,487.24 / 30.07 (16.82; peak 132.00) |

At depth 4K and 8K the aggregate tg falls as streams are added while the peak rises. Our reading, inferred and not
measured: the 2- and 4-stream requests' prefills overlap the other streams' decode, so the aggregate under-reports
steady decode. A run with staggered starts would test this.

PILCOTHINK's grid ([NVIDIA forum topic 386574](https://forums.developer.nvidia.com/t/386574), post 5; the build
[gpdev-Pilcothink/DGX_Spark_vllm_Dockerfile](https://github.com/gpdev-Pilcothink/DGX_Spark_vllm_Dockerfile): vLLM 0.32.1,
LibertAI EXL3 2.9 bpw, 8 sequences), with the tool's default latency mode (`api`), in which 0.4.0 and PILCOTHINK's 0.4.1.dev1
measure alike:

| Test | DGX sPLIce, mean ± std | PILCOTHINK, post 5 | Delta |
|-|-|-|-|
| pp2048 (tg128 run) | 1,883.21 ± 8.10 | 1,420.45 ± 73.47 | +32.6 % |
| pp2048 (tg1024 run) | 1,889.73 ± 8.64 | 1,533.06 ± 46.79 | +23.3 % |
| tg128 / peak | 53.09 ± 1.29 / 60.33 | 42.03 ± 4.35 / 50.67 | +26.3 / +19.1 % |
| tg1024 / peak | 50.48 ± 3.18 / 84.00 | 43.63 ± 3.67 / 61.67 | +15.7 / +36.2 % |
| pp2048 @ d1024 / tg128 @ d1024 | 2,166.52 ± 20.49 / 56.50 ± 2.86 | 1,748.85 ± 30.40 / 43.47 ± 2.10 | +23.9 / +30.0 % |
| pp2048 @ d4096 / tg128 @ d4096 | 2,518.02 ± 2.47 / 49.59 ± 2.35 | 1,718.95 ± 55.21 / 44.23 ± 1.59 | +46.5 / +12.1 % |
| tg1024 @ d1024 / @ d4096 | 55.21 ± 3.77 / 54.32 ± 3.48 | no row | |
| pp2048 @ d400000 | not run (our limit is 327,680) | 1,771.88 ± 51.33 | |

Label: **same tool, settings differ**. The tool, grid and latency mode are PILCOTHINK's. What differs: PILCOTHINK ran
with the prefix cache on and DSpark k = 3; every one of our requests carried a fresh `cache_salt`, so the prefix cache
never helped us, and we run k = 5. Neither side sends a thinking flag. Against this grid we are 23-47 % ahead on
prefill and 12-30 % on decode (mean tg); this is the llama-benchy cell at the top of this page.

## Other 2x DGX Spark builds

Popular public builds of DeepSeek-V4-Flash and V4.1-Flash on DGX Sparks, with GitHub stars as of 2026-10-31. Their
numbers are their own, under their own conditions. The last column says which of their benchmarks we have run on DGX
sPLIce ([results](#the-other-builds-own-benchmarks-run-on-dgx-splice)); the rest are still to be ported.

| Repository | Stars | Model | Engine, weights | What it publishes | Run on DGX sPLIce |
|-|-|-|-|-|-|
| [MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark) | 1,505 | V4-Flash | vLLM, DSpark | earlier model | |
| [tonyd2wild/DeepSeek-v4-Flash-Vision-Exp-DSpark-1M-NVFP4-KV-2x-DGX-Spark](https://github.com/tonyd2wild/DeepSeek-v4-Flash-Vision-Exp-DSpark-1M-NVFP4-KV-2x-DGX-Spark) | 494 | V4-Flash | vLLM, DSpark, NVFP4 KV, 1M | earlier model | |
| [MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks) | 372 | V4.1-Flash-1017 | TensorFold, EAQ 2.9 bpw | compared above | sparkDash, port |
| [MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-DGX-Sparks) | 281 | V4.1-Flash | 3-4 Sparks | | |
| [MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks) | 280 | V4.1-Flash | vLLM, EXL3 2.9 bpw | 1 stream at T=0: 40.2 tok/s | |
| [tonyd2wild/DeepSeek-V4.1-Flash-TP2-and-TP4-DGX-Sparks](https://github.com/tonyd2wild/DeepSeek-V4.1-Flash-TP2-and-TP4-DGX-Sparks) | 154 | V4.1-Flash-1017 | TensorFold, EXL3 2.9 bpw | 73.1 tok/s at 1 user, 135.8 at 4 (8 categories), 1M | `v41bench`, same protocol |
| [jayleaton/deepseek-v41-tensorfold-spark](https://github.com/jayleaton/deepseek-v41-tensorfold-spark) | 97 | V4.1-Flash-1017 | TensorFold, EXL3 2.8 bpw | 1M context, four slots | tool chains, same protocol |
| [0xSero/DeepSeek-V4.1-Flash-Two-Sparks](https://github.com/0xSero/DeepSeek-V4.1-Flash-Two-Sparks) | 95 | V4.1-Flash | vLLM, EXL3 2.77 bpw | prefill 8K 2,050, 32K 2,061; code 1 stream ~39-41; 262,144 context | |
| [Elevatormusic/DeepSeek-V4.1-Flash-1017-EXL3-TensorFold-2x-DGX-Spark](https://github.com/Elevatormusic/DeepSeek-V4.1-Flash-1017-EXL3-TensorFold-2x-DGX-Spark) | 71 | V4.1-Flash-1017 | TensorFold, EXL3 2.9 bpw | `v41_suite` and `v41_bench` | `v41_suite`, `v41_bench`, same protocol |
| [bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10](https://github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10) | 58 | V4.1-Flash-1017 | TensorFold, EXL3 2.52 bpw | compared above | `kit_bench`, same protocol |
| [sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41) | 45 | V4.1-Flash-1017 | vLLM, EXL3 2.8 bpw | set b code / prose / structured 103.7 / 57.8 / 144.4; KLD 0.0198 | `kit_bench` set b, same protocol |
| [Blackwellboy/DeepSeek-V4.1-Flash-1017-BLACKFOLD-TP2](https://github.com/Blackwellboy/DeepSeek-V4.1-Flash-1017-BLACKFOLD-TP2) | 41 | V4.1-Flash-1017 | TensorFold, EXL3 2.9 bpw | `kit_bench` set b, `v41bench` | both, same protocol |
| [elsung/dgx-spark-deepseek-v4-flash](https://github.com/elsung/dgx-spark-deepseek-v4-flash) | 30 | V4-Flash | vLLM, FP8 | ~41 tok/s 1 stream, ~350 aggregate at 32 | |
| [r0b0tlab/deepseek-v4-flash-nvfp4-gb10-benchmark](https://github.com/r0b0tlab/deepseek-v4-flash-nvfp4-gb10-benchmark) | 13 | V4-Flash | vLLM | 38.4 tok/s 1 stream, 144.6 aggregate at 16 | |
| [gpdev-Pilcothink/DGX_Spark_vllm_Dockerfile](https://github.com/gpdev-Pilcothink/DGX_Spark_vllm_Dockerfile) (PILCOTHINK) | 11 | V4.1-Flash-1017 | vLLM 0.32.1, EXL3 2.9 bpw | llama-benchy, forum 386574 | llama-benchy, same tool (settings differ) |
| [HeNryous/deepseek-v41-1017-dgx-spark](https://github.com/HeNryous/deepseek-v41-1017-dgx-spark) | 6 | V4.1-Flash-1017 | vLLM image v5 (ours), EXL3 2.75 bpw | prose 56.6, code 88.9 (T=1, 2,400 MHz) | 3-code needle and `kit_bench` set b, same protocol; `fair_bench`, port |
| [hisxo/DeepSeek-V4.1-Flash-2x-DGX-Spark](https://github.com/hisxo/DeepSeek-V4.1-Flash-2x-DGX-Spark) | 1 | V4.1-Flash | TensorFold (patched), EXL3 2.9 bpw | 1 stream code / prose / structured 113.4 / 69.3 / 145.1 | |
| [ZackO2o/DeepSeek-V4.1-Flash-TensorFold-DGXSpark-TP2](https://github.com/ZackO2o/DeepSeek-V4.1-Flash-TensorFold-DGXSpark-TP2) | 1 | V4.1-Flash | TensorFold | code 81.8 tok/s 1 stream, 150.5 aggregate at 4 | |

Builds that serve more streams (8-32) need a larger `max-num-seqs` than our production uses; those rows will be run in a
separate configuration and labelled as such.

## Known issues

**Forced tool calls can return HTTP 500 on vLLM's DeepSeek V4.1 tool path.** Seen on vLLM 0.31.1.dev0 (the v5 image)
with `--tool-call-parser deepseek_v41` and the default structured-outputs backend. Status: fixed in our production on
2026-10-31 with `--structured-outputs-config.backend xgrammar`. After the restart, forced (`required`) and named tool
calls and strict tools in `auto` mode work, a `pattern` + `maxLength` schema gets the expected HTTP 400, greedy output is
identical to before (6 prompts, 3 runs each), and a 15-minute health watch passed. The launch file in this repository
(`offload/launch/dsv41_tp2_offload.sh`) now sets the flag too, in the `vllm serve` arguments after `--tool-call-parser`,
exactly as production runs it.

- **Symptom.** A request with `tool_choice: "required"` or a named function
  (`{"type": "function", "function": {"name": ...}}`) fails with HTTP 500 before any token is generated, and the engine
  keeps serving. `strict: true` tools in `auto` mode fail the same way. The serve log shows `KeyError: 'triggers'` in
  `serialize_guidance_grammar` (`vllm/v1/structured_output/backend_guidance.py`). Ordinary `auto` tool calls with
  non-strict tools are not affected.
- **Cause.** The V1 engine creates one structured-outputs backend per start, from the first structured-output request
  it sees, and keeps it until shutdown. Under the default `auto` backend, a JSON schema that xgrammar refuses and
  guidance accepts (a string `pattern` with `minLength`/`maxLength`, or an integer `multipleOf`) pins guidance. The V4.1
  tool path builds xgrammar's `deepseek_v4_1` structural tag in the newer `format` shape, and guidance's serializer
  reads only the older `structures` / `triggers` shape. If an xgrammar-valid structured request comes first instead,
  forced tool calls work until the next restart, so the failure depends on request order.
- **Workaround.** Start vLLM with `--structured-outputs-config.backend xgrammar` (or
  `--structured-outputs-config '{"backend":"xgrammar"}'`). Forced and strict tool calls then compile and keep the
  model's own DSML call format. Trade-off: JSON schemas xgrammar cannot compile, such as a `pattern` combined with
  `minLength`/`maxLength` or a `multipleOf`, get a clean HTTP 400 instead of being served by guidance.
- **Also worth knowing.** If xgrammar happened to be pinned first under `auto`, a `pattern` + `maxLength` schema compiles
  on xgrammar with its length bound dropped (a log warning, not an error). `VLLM_ENFORCE_STRICT_TOOL_CALLING=0` also
  avoids the 500, but forced calls are then generated as JSON instead of DSML, and `strict` is ignored.

Two of Elevatormusic's twelve `v41_suite` tool checks are exactly these forced-choice cases; they are our 10/12 above,
measured before the fix. The same two requests have passed in production since; the suite itself was not re-run.

## Reproduce

```bash
# MiaAI's sparkDash protocol (decode 1-4 streams, prefill 4K-256K), plus our deep-context and short-behind-long tests
python3 -I tools/sparkbench.py --url http://<head>:8000 --out runs/my-sparks.json --reps 3 \
    --suites prose-t0,code-t0,structured-t0,prose-t07-think,prose-t1-think,prefill \
    --deep 32768:1,32768:4,131072:1 --interference 2
# our own cells (T=1, thinking on, 512 tokens, synthetic records) and a MiaAI-conditions profile
python3 -I tools/bench.py plan --profile all
python3 -I tools/bench.py run --profile all --url http://<head>:8000 --exact-size \
    --label my-sparks --note "clock 2300, commit ..." --out runs/my-sparks-bench.json
# llama-benchy 0.4.0 (PyPI), the three tables above; --tokenizer is the model's tokenizer (a local copy or HF id)
pip install llama-benchy==0.4.0
llama-benchy --base-url http://<head>:8000/v1 --model <served model> --tokenizer <tokenizer> --runs 3 \
    --pp 2048 --tg 32 --depth 0 4096 8192 16384 32768 65536 131072 --latency-mode generation --no-cache
llama-benchy ... --pp 2048 --tg 128 --depth 0 4096 8192 --concurrency 1 2 4 --latency-mode generation --no-cache
llama-benchy ... --pp 2048 --tg 128 1024 --depth 0 1024 4096
# tool-eval-bench 3.0.1.dev7 (SeraphimSerapis/tool-eval-bench, main at 887b537), Hard Mode; then the same with "high"
python3 -m tool_eval_bench run --base-url http://<head>:8000 --model <served model> --backend vllm --hardmode \
    --seed 42 --temperature 0 --parallel 4 --timeout 1800 --json-file teb-max.json --backend-kwargs \
    '{"chat_template_kwargs":{"enable_thinking":true,"thinking":true,"thinking_mode":"enabled","reasoning_effort":"max"},"reasoning_effort":"max"}'
```

Our two tools, `sparkbench.py` and `bench.py`, use only the Python standard library and talk to any OpenAI-compatible
server. Lock the GPU clock first
(`sudo nvidia-smi -lgc 0,2300` on both Sparks) and record it with the result; `tools/node_watch.py` logs clocks,
temperatures and free memory during a run. Our llama-benchy and tool-eval-bench runs went through a local proxy that
gave every request a fresh `cache_salt` and a unique first line; without one, turn the server's prefix cache off to
measure on the same basis. Please send results as a
[performance report](https://github.com/ProprietaryLegal/DGX-sPLIce-DeepSeek-V4.1-Flash-2xDGX-Spark-2xRTX3090-drafter-x86-offload/issues/new?template=performance_report.yml).

## Our own cells: long legal prompts at T=1, thinking on

The sparkDash numbers above use short prompts at temperature 0. Our production work is long documents with thinking on,
which is the hardest case for a drafter. These cells are measured with temperature 1 (seed 42 + repeat), thinking on
(effort `high`), exactly 512 generated tokens (`ignore_eos`), fresh cache salts, 3 repeats, median; prompts were public
court opinions and filings cut to size. Production `a0006fc`, 2026-10-28, 2,300 MHz cap, drafter GPUs at 325 W.

| Cell | Prompt | Streams | Decode tok/s, per stream | TTFT | Accepted draft tokens per round | Server ms per round |
|-|-|-|-|-|-|-|
| short-b1 | short | 1 | **57.2** | 0.82 s | 1.21 | 38.5 |
| 32k-b1 | 32K, cold | 1 | **56.5** | 12.3 s | 1.15 | 38.2 |
| 32k-b3 | 3 x 32K, cold, together | 3 | **30.2** | 42.0 s | 1.15 | 87.3 |
| 32k-b4 | 4 x 32K, cold, together | 4 | **27.4** | 53.3 s | 1.25 | 99.1 |
| 150k-b1 | 150K, cold | 1 | **52.1** | 57.6 s | 1.04 | 39.3 |
| mixed150k-2decode | 150K prefill while 2 streams decode | 3 | 5.3 | 30.6 s | 1.18 | 299.7 |

The same cells at a 2,150 MHz cap, the persistent prefix tier, capacity (1,934,490 KV tokens; four full-length
requests fit), the configuration history and a decode-round profile are in [docs/measurements.md](docs/measurements.md).
Production `ebc29ed8` adds sampled drafting with a fixed 5-token window and the prefix tier to `a0006fc`; its cold 150K
TTFT (58.59 s) matches the record (57.6 s), and these cells have not yet been re-run on it.

## Server limits and memory

What the shipped configuration admits, and the memory it leaves free. The values are set in [serve.sh](serve.sh) and
[dsv41.env](dsv41.env); the pool size is the engine's own log line.

| Limit | Value | Set by |
|-|-|-|
| longest request (`MAX_LEN`) | 327,680 tokens | `PROD_MAX_LEN` in `dsv41.env` |
| concurrent streams (`MAX_SEQS`) | 4 | `serve.sh` |
| prefill chunk (`MAX_BATCH`) | 8,192 tokens per step | `serve.sh` |
| GPU memory utilization (`UTIL`) | 0.86; only gates the startup check, because the KV pool is set in bytes | `serve.sh` |
| KV pool | 6 GiB per rank (`PROD_KV_BYTES=6442450944`), 46,603 blocks | `dsv41.env` |
| admissible KV tokens | **1,934,490**: four requests at the full 327,680 tokens fit (1,310,720) | engine log, `a0006fc` and `ebc29ed8` |
| speculative decoding | DSpark on the x86 drafter, sampled drafting, fixed window of 5 tokens | `serve.sh`, `dsv41.env` (`PROD_PP4`) |
| lowest free memory seen | 6.3 GB `MemAvailable` on each Spark, during the 2026-10-30 prefix-tier test window | [measurements](docs/measurements.md#persistent-prefix-tier-2026-10-30-and-2026-10-31-production-ebc29ed8) |
| free memory, 150K + three 32K prompts at once | at least 5.6 GiB on each Spark (`a0006fc`, 2026-10-28) | [capacity](docs/measurements.md#capacity-engine-log) |

Without the x86 drafter the KV pool has to go back to 3.75 GiB per rank (989,460 tokens): the local drafter has not been
tested with more, and `serve.sh` refuses the combination.

## Where the prefill time goes

A kernel census of a cold 31,633-token prompt (four prefill chunks of up to 8,192 tokens) on 2026-10-31: production
`ebc29ed8` restarted with vLLM's torch profiler configured and nothing else changed, 2,300 MHz cap, 3 profiled requests
and 3 unprofiled controls. The profiler records events and launches no kernel; profiled requests' first output matched
their controls'. Control time to first token 12.32 s, profiled 12.33 s: the profiler added 0.08 %.

| Kernel group | ms, mean of the two ranks | Share of the time to first token |
|-|-|-|
| MoE experts | 5,852 | 47.5 % |
| norms and elementwise | 2,094 | 17.0 % |
| attention (prefill) | 1,614 | 13.1 % |
| dense GEMM | 1,604 | 13.0 % |
| all-reduce | 790 | 6.4 % |
| all-reduce wait | 142 | 1.1 % |
| EXL3 GEMM | 93 | 0.8 % |
| every other line (host, device and drafter waits, sampler, rest) | | 0.6 % or less each |

Reading the routed experts dominates prefill, as it dominates decode. Waiting on the x86 drafter costs prefill about
3 ms. A 150K census was attempted in the same window, but its traces did not cover every prefill chunk, so it is not
published.
Per-chunk timelines: [docs/measurements.md](docs/measurements.md#where-the-prefill-time-goes-2026-10-31-census-cold-32k).

## Architecture

```
                       +---------------------- x86 offload host ----------------------+
                       |  Engram server: layer 1 + 14 tables in RAM (~189 GiB)        |
                       |  DSpark drafter: 3 layers + Markov head, EXL3, TP2 on an     |
                       |  NVLinked RTX 3090 pair (sampled drafting, window 5)         |
                       +------------+------------------------------+------------------+
                                    | 40 Gb/s RoCE v2              | 40 Gb/s RoCE v2
                                    | (Engram rows, draft rounds)  |
   clients --HTTP :8000-->  +-------+---------+   200 Gb/s   +-----+-----------+
   (OpenAI API)             | DGX Spark  rank0| <==CX-7==>   | DGX Spark rank1 |
                            | vLLM API, TP2   |   NCCL TP    | TP2             |
                            | target 40 layers, KV 6 GiB, persistent prefix tier |
                            +-----------------+              +-----------------+
```

| Piece | Where | What it does | Code |
|-|-|-|-|
| target model | both Sparks, TP2 | verifies drafts, samples, generates | [serve.sh](serve.sh), [dsv41.env](dsv41.env), `offload/upstream_all/` |
| Engram tables | x86 RAM, RDMA | Engram rows for prompt and decode; local NVMe reader kept as exact fallback | `offload/engram/`, `offload/transport/` |
| DSpark drafter | x86 RTX 3090 pair | 5 drafted tokens per round, sent back over RDMA | `offload/dspark/worker/`, `offload/pp4_prod/` |
| async round proxy | CPU process on rank 0 | runs the remote round off the engine thread; watchdog and bounded respawn | `offload/dspark/spark/`, `offload/promote/async-tp2/` |
| KV page packing | both Sparks | packs KV pages at the 327,680 limit | `offload/kvpack/`, `offload/promote/k1/` |
| persistent prefix tier | Spark NVMe | stores long-prompt KV per namespace; requests opt in, untagged requests are never stored | launcher glue in `offload/prefixstore/production/`; the tier itself follows in the next push ([why](docs/publication.md#prefix-tier-code)) |

If the x86 host is down, Engram reads fall back to the Sparks' local disk and drafting fails closed to target-only
rounds: the API keeps serving, slower. [docs/architecture.md](docs/architecture.md) explains each piece, the failure
paths and the measured effect of each.

## Requirements

| Item | Tested configuration |
|-|-|
| serving nodes | 2 x NVIDIA DGX Spark (GB10, 121 GiB unified memory), direct ConnectX-7 200 Gb/s link |
| offload host | x86 AMD EPYC 7302P (16 cores), 503 GiB RAM; about 190 GiB of it holds the Engram tables |
| host links | ConnectX-5 Ex, one 40 Gb/s DAC per Spark, MTU 9000, RoCE v2 |
| drafter GPUs | 2 x RTX 3090 24 GB with an NVLink bridge (one card also works), 325 W cap |
| image | `ghcr.io/henryous/deepseek-v41-1017-dgx-spark:v5` (vLLM 0.31.1.dev0+g6e517b15, linux/arm64, `sha256:8fc2c99a3562...8309e4`), unmodified; our overlays are mounted at start |
| launcher | [sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41) at `cc59c36` ([our fork](https://github.com/ProprietaryLegal/dgx-spark-deepseek-v41)) |
| weights | [HeNryous 2.75 bpw](https://huggingface.co/HeNryous/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-DGX-Spark) rev `86f85253`, or the [legal-weighted allocation](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-LegalWeighted-DGX-Spark) of it that we serve (same size and format), plus DeepSeek's two Engram shards |
| tools | Python 3.10+ (stdlib only for `tools/`), Docker with the NVIDIA runtime, key-based ssh between the nodes |

Without the x86 host DGX sPLIce still runs as a plain two-Spark serve: leave `OFFLOAD_DOCKER_ENV` and
`OFFLOAD_DSPARK_ENV` empty in `dsv41.env`, and the KV pool has to go back to 3.75 GiB per rank.

## Full build

Everything the published numbers ran on, and where it is:

| Piece | What we run | Where |
|-|-|-|
| launch scripts and configuration | `start.sh` -> `serve.sh` (both Sparks), `stop.sh`, `status.sh`, `logs.sh`, all set by `dsv41.env` | [start.sh](start.sh), [serve.sh](serve.sh), [dsv41.env](dsv41.env) |
| x86 host services | Engram server and TP2 drafter worker, systemd user units | [dsv41-engram.prod.service](offload/engram/server/dsv41-engram.prod.service), [dsv41-dspark-worker-tp2.prod.service](offload/dspark/worker/dsv41-dspark-worker-tp2.prod.service) |
| base image | `ghcr.io/henryous/deepseek-v41-1017-dgx-spark:v5`, `sha256:8fc2c99a3562e99d81d2a05b8345d12726def0a027410d14d0eb0763de8309e4` (linux/arm64), unmodified | [docs/install.md](docs/install.md#2-the-image-both-sparks) |
| overlays (content-addressed stages, every file sha256-pinned) | upstream patch set `e7e8e3f2dd57`, sampled drafting (PP4) `22897accecef`, KV page packing `559c5867ba42`, remote Engram reader, remote drafter client and async proxy | [offload/upstream_all/MANIFEST.json](offload/upstream_all/MANIFEST.json), [offload/pp4_prod/MANIFEST.json](offload/pp4_prod/MANIFEST.json), [offload/kvpack/MANIFEST.json](offload/kvpack/MANIFEST.json), [offload/engram/spark/stage_overlay.sh](offload/engram/spark/stage_overlay.sh), [offload/dspark/spark/stage_overlay.sh](offload/dspark/spark/stage_overlay.sh) |
| launcher | sudoingX's recipe at `cc59c36` plus [recipe-servedir.patch](recipe-servedir.patch) | [sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41) |
| served weights | the legal-weighted allocation of HeNryous's 2.75 bpw build (same size and format); HeNryous's own build at `86f85253` is the drop-in alternative | [ProprietaryLegal ...-LegalWeighted-DGX-Spark](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-LegalWeighted-DGX-Spark), [HeNryous 2.75 bpw](https://huggingface.co/HeNryous/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-DGX-Spark), [download.sh](download.sh) |
| Engram tables | DeepSeek's two Engram shards at `1bae0e10` | [deepseek-ai/DeepSeek-V4.1-Flash-1017](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017), [download.sh](download.sh) |
| drafter weights | the checkpoint's own DSpark layers, extracted byte for byte (4,755 tensors) for the x86 host; nothing extra to download | [offload/dspark/TRANSFER.md](offload/dspark/TRANSFER.md), [offload/dspark/TENSORS.md](offload/dspark/TENSORS.md) |
| step by step | cabling, image, launcher, weights, x86 services, `dsv41.env`, first start, checks | [docs/install.md](docs/install.md) |

The persistent prefix tier's code follows in the next push ([why](docs/publication.md#prefix-tier-code)); without it
the launcher prints `MATTER OFF (config-missing)` and serves the configuration above unchanged.

## Quick start

This is a production tree, not a one-command installer. [docs/install.md](docs/install.md) is the full build, step by
step: cabling and addresses, the image by digest, the launcher, the weights, the drafter and Engram files on the x86
host, both x86 services, `dsv41.env`, the first start and the checks. In short:

1. Pull the image on both Sparks and check its digest; clone the launcher at `cc59c36` on the head.
2. Download the weights on both Sparks with `download.sh` (pinned revisions, size checks).
3. Copy the drafter layers and the two Engram shards from the same checkpoint to the x86 host
   ([offload/dspark/TRANSFER.md](offload/dspark/TRANSFER.md)); build and start the Engram server and the drafter worker.
4. Edit [dsv41.env](dsv41.env) for your node names, fabric interface, model path and link addresses.
5. On the head Spark: `./start.sh`, then `./status.sh`. Measure with the commands under [Reproduce](#reproduce).

`bench.py` and `sparkbench.py` use only synthetic or lab prompts they generate themselves, a fresh salt per request, and
store token counts and timings, never generated text.

## Repository layout

| Path | What it is |
|-|-|
| `start.sh`, `stop.sh`, `status.sh`, `serve.sh`, `dsv41.env` | the production launcher and its configuration |
| `tools/` | `sparkbench.py` (sparkDash protocol), `bench.py` (our cells and a MiaAI-conditions profile), `node_watch.py`, `fake_server.py` and tests |
| `offload/` | every production component, each with a README: Engram, transport, drafter, async proxy, KV packing, upstream patches; the prefix tier's launcher glue |
| `bench.py`, `quality.py`, `functest.py`, `verify_hashes.py` | the older single-stream bench, output checks, function tests, model hash checks |
| `docs/` | [install](docs/install.md), [measurements](docs/measurements.md), [comparison](docs/comparison.md), [architecture](docs/architecture.md), [operations](docs/operations.md), [publication](docs/publication.md), [Legora BAR](docs/legora-bar.md) |
| `runs/` | raw benchmark JSON files, one per run, with their conditions |
| `legora-bar/` | the Legora BAR public-case harness, grading pack, verdicts, output and transcript ([docs/legora-bar.md](docs/legora-bar.md)) |
| `.publication/SOURCE.json` | what this tree was exported from and what was removed or rewritten for publication |

## Tests

```bash
python3 -I -m unittest discover -s tools/tests -v                                    # bench.py and sparkbench.py, CPU only, ~10 s
PYTHONPATH=offload/dspark/spark python3 -B -m pytest -q offload/dspark/spark/tests     # async proxy and remote drafter client
```

Some component suites need the serving image's Python packages; each component README says which. Every overlay this
commit ships matches its byte pins; see [docs/publication.md](docs/publication.md).

## Related repositories

This repository is the full DGX sPLIce build. The research archive and the earlier single-component repositories stay up for their
history and their own tests; their code is included here as it runs in production.

| Repository | What it holds |
|-|-|
| [dsv41-offload](https://github.com/ProprietaryLegal/dsv41-offload) | the research archive: every experiment branch up to 2026-10-27 |
| [dsv41-remote-engram-rdma](https://github.com/ProprietaryLegal/dsv41-remote-engram-rdma), [ofl-rdma-transport](https://github.com/ProprietaryLegal/ofl-rdma-transport) | the Engram server and its RDMA transport |
| [dsv41-remote-dspark-drafter-3090](https://github.com/ProprietaryLegal/dsv41-remote-dspark-drafter-3090), [dsv41-dspark-drafter-tp2-nvlink](https://github.com/ProprietaryLegal/dsv41-dspark-drafter-tp2-nvlink) | the one-card and two-card drafter workers |
| [dsv41-async-hostflag-handoff](https://github.com/ProprietaryLegal/dsv41-async-hostflag-handoff) | the async round proxy |
| [dsv41-kv-page-packing-1m](https://github.com/ProprietaryLegal/dsv41-kv-page-packing-1m) | KV page packing |
| [dsv41-native-1017-drafter-sm86](https://github.com/ProprietaryLegal/dsv41-native-1017-drafter-sm86), [dsv41-exact-acceptance-ceiling](https://github.com/ProprietaryLegal/dsv41-exact-acceptance-ceiling) | research only, not serving |
| [dsv41-longctx-bench-tools](https://github.com/ProprietaryLegal/dsv41-longctx-bench-tools), [dsv41-window-harness](https://github.com/ProprietaryLegal/dsv41-window-harness) | earlier measurement tools |
| [deepseek-v41-1017-dgx-spark](https://github.com/ProprietaryLegal/deepseek-v41-1017-dgx-spark), [dgx-spark-deepseek-v41](https://github.com/ProprietaryLegal/dgx-spark-deepseek-v41) | our forks of the HeNryous image and the sudoingX launcher |
| [Volta sPLIt](https://github.com/ProprietaryLegal/Volta-sPLIt-DeepSeek-V4.1-Flash-1017-8xV100-SXM2-PP2xTP4) | a separate build of the same model on 8x V100-SXM2-32GB (PP2 x TP4); its numbers are on its own page |

## Credits and licence

DGX sPLIce stands on other people's work: DeepSeek's model, DSpark drafter and Engram; HeNryous's 2.75 bpw weights,
serving image and patch series; the vLLM project; turboderp's exllamav3; sudoingX's launcher, EXL3 MoE plugin, KLD tool
and panel; TensorFold and bertholomus's fork of it; MiaAI-Lab's sparkDash protocol; and the kernel donors listed in
[CREDITS.md](CREDITS.md). If you build on this repository, please credit those projects as well.

Original code is Apache-2.0 ([LICENSE](LICENSE)). Third-party code keeps its own licence; see [NOTICE](NOTICE) and
[LICENSES/](LICENSES/). No model weights are distributed here.

## Work with PLI Labs

[PLI Labs](https://proprietarylegal.ai/labs.html) is the open research arm of Proprietary Legal Intelligence. PLI builds
AI around an organization's own work product: retrieval over its documents, staged workflows, validation of every output
and attorney review before anything goes out. This stack is how we run that privately, on hardware we own. If you want
private, on-prem LLM serving of your own, from choosing the hardware to the measured stack and the workflows on top, we
consult on exactly that: [proprietarylegal.ai](https://proprietarylegal.ai).
