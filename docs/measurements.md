# Measurements

Every number in this file is MEASURED on the hardware described in the README unless a row says otherwise. Each
section gives the date, the production commit, the GPU clock and the request settings. Where a number is another
project's, the section says so and links its source.

| Section | What it holds |
|-|-|
| [sparkDash protocol, 2026-10-31](#sparkdash-protocol-2026-10-31) | MiaAI's sparkDash tests on DGX sPLIce: decode at 1-4 streams, every repeat, prefill 4K-256K, deep-context decode, a short request behind a long prompt, clocks and temperatures |
| [Quality: KL divergence against the original model](#quality-kl-divergence-against-the-original-model) | KLD and top-1 agreement by domain, both panels, both weight sets |
| [Speed record, 2026-10-28](#speed-record-2026-10-28-production-a0006fc) | our own cells: temperature 1, thinking on, 512 tokens, court-opinion prompts up to 150K |
| [Persistent prefix tier](#persistent-prefix-tier-2026-10-30-and-2026-10-31-production-ebc29ed8) | reload of a long prompt from NVMe, fault cases, reloads after production restarts |
| [Where the prefill time goes](#where-the-prefill-time-goes-2026-10-31-census-cold-32k) | kernel census of a cold 32K prompt on production: every line, both ranks, every chunk |
| [The other builds' own benchmarks](comparison.md#the-other-builds-own-benchmarks-2026-10-31) | kit_bench, v41bench, v41_suite, v41_bench, fair_bench, needles and tool checks run on DGX sPLIce, 2026-10-31 (in comparison.md) |
| [llama-benchy 0.4.0](../README.md#llama-benchy-040) | the standard, concurrency and PILCOTHINK-grid tables, 2026-10-31 (in the README) |
| [tool-eval-bench 3.0.1](../README.md#tool-eval-bench-301) | Hard Mode at effort max and high against the published runs, 2026-10-31 (in the README) |
| [Capacity](#capacity-engine-log), [configuration history](#configuration-history-2026-10-22-and-2026-10-23) and [decode profile](#where-the-decode-time-goes-2026-10-26-profile-2150-mhz) | what each offload piece changed, and where a decode round's time goes |

## sparkDash protocol, 2026-10-31

**Conditions, for every table in this section:** production commit `ebc29ed8`, served weights the
[legal-weighted allocation](https://huggingface.co/ProprietaryLegal/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-LegalWeighted-DGX-Spark)
of HeNryous's 2.75 bpw EXL3 build (same size and format), both Sparks locked at a 2,300 MHz GPU clock cap (SM
2,275-2,281 MHz observed), drafter GPUs (2 x RTX 3090) at a 400 W power cap for the pass (production runs them at 325 W),
`--max-num-seqs 4`, context limit 327,680, chunked prefill 8,192, remote Engram and remote drafter on, 3 repeats per
decode cell. Protocol: [MiaAI-Lab/sparkDash](https://github.com/MiaAI-Lab/sparkDash) commit `b96244a2`, re-implemented
in [tools/sparkbench.py](../tools/sparkbench.py). Pass 2026-10-31 03:51:47Z to 04:09:39Z UTC; production served nothing
else (the window script checked 30 s of zero running requests first). Raw file:
[runs/2026-10-31-sparkdash-protocol-ebc29ed8.json](../runs/2026-10-31-sparkdash-protocol-ebc29ed8.json).

Clocks and heat: GPU temperature 57-58 °C at the start and 70-74 °C at the end of the pass, SM clock 2,275-2,281 MHz
in every sample, no hardware or thermal slowdown flag, and the heat guard (88 °C on 3 samples in a row) never tripped.
The drafter cards drew 22 W idle and 108-112 W at the end-of-pass sample, well under either power cap, so the 400 W
cap is not expected to have changed the numbers; this was not tested separately.

### How sparkDash measures

- **Decode wave:** N streams released together, the lab prompt for the type, `max_tokens` = `min_tokens` = 400 with
  `ignore_eos`, `top_p` 1, after a 32-token warm-up request. Prose: one hash-map explanation prompt (each stream gets a
  unique first line). Code: one different Python task per stream. Structured: "Count from 1 to 200", numbers only.
- **Per-stream tok/s** = (completion tokens - 1) / (last token time - first token time). **Total tok/s** = all decoded
  tokens of the wave / (latest last token - earliest first token).
- **Accepted per round** = accepted draft tokens / draft rounds from the server's `/metrics` counters around the wave.
  The drafter proposes k = 5 tokens a round, so a round emits 1 + accepted tokens.
- **Prefill:** a salted random-word prompt of the target size, 8 generated tokens, temperature 0, thinking off; rate =
  (prompt - cached tokens) / (TTFT - overhead), where the overhead is the median TTFT of three 16-token prompts
  (207.9 ms in this pass), capped at half the TTFT. Repeats: 3 up to 32K, 2 up to 128K, 1 above; the median-rate sample
  is reported. The uncorrected rate (prompt / TTFT) is shown beside it.
- In this file, a cell's **total** and **per stream** are medians over its 3 repeats, **TTFT** is the median over every
  stream of every repeat, and **accepted per round** pools the 3 repeats.

### Decode cells (sparkDash)

| Suite | Streams | Total tok/s | Per stream tok/s | TTFT | Accepted per round (k = 5) |
|-|-|-|-|-|-|
| prose, T=0, thinking off | 1 | 66.0 | 66.0 | 146 ms | 2.14 |
| | 2 | 90.5 | 45.9 | 266 ms | 2.13 |
| | 3 | 112.4 | 39.4 | 388 ms | 2.25 |
| | 4 | 130.1 | 33.8 | 344 ms | 2.21 |
| code, T=0, thinking off | 1 | 110.5 | 110.5 | 215 ms | 4.22 |
| | 2 | 147.9 | 76.6 | 335 ms | 4.40 |
| | 3 | 174.8 | 61.5 | 508 ms | 4.47 |
| | 4 | **192.0** | 52.4 | 600 ms | 4.39 |
| structured, T=0, thinking off | 1 | **138.3** | 138.3 | 111 ms | 4.96 |
| | 2 | 201.3 | 104.7 | 204 ms | 4.96 |
| | 3 | 276.0 | 96.8 | 385 ms | 4.96 |
| | 4 | **322.1** | 85.2 | 404 ms | 4.96 |
| prose, T=0.7, thinking on | 1 | 55.9 | 55.9 | 221 ms | 1.60 |
| | 2 | 72.0 | 37.2 | 401 ms | 1.66 |
| | 3 | 90.8 | 32.6 | 579 ms | 1.73 |
| | 4 | 105.3 | 27.9 | 543 ms | 1.66 |
| prose, T=1, thinking on (our addition) | 1 | 54.8 | 54.8 | 214 ms | 1.55 |
| | 2 | 73.0 | 37.4 | 322 ms | 1.62 |
| | 3 | 86.5 | 31.1 | 620 ms | 1.59 |
| | 4 | 100.4 | 27.4 | 679 ms | 1.64 |

Every request generated exactly 400 tokens; 0 errors in 60 waves. Structured output accepts almost every draft (4.96
of 5), which is why it decodes fastest; prose at T=0 accepts about 2.2, and thinking at T=0.7 or 1 about 1.6.

Every repeat (total tok/s, then each stream's rate):

| Suite | Streams | Repeat 1 | Repeat 2 | Repeat 3 |
|-|-|-|-|-|
| prose T=0 | 1 | 66.0 (66.0) | 66.1 (66.1) | 65.7 (65.7) |
| prose T=0 | 2 | 90.5 (46.5 / 46.4) | 90.7 (46.5 / 45.3) | 87.0 (44.6 / 43.8) |
| prose T=0 | 3 | 122.9 (41.0 / 42.1 / 43.0) | 109.5 (41.6 / 37.3 / 39.3) | 112.4 (39.1 / 37.5 / 38.5) |
| prose T=0 | 4 | 123.2 (33.3 / 31.4 / 30.8 / 33.9) | 138.5 (35.8 / 36.9 / 35.5 / 37.2) | 130.1 (33.1 / 33.3 / 34.3 / 34.3) |
| code T=0 | 1 | 110.9 (110.9) | 110.5 (110.5) | 109.4 (109.4) |
| code T=0 | 2 | 147.0 (75.6 / 77.7) | 148.6 (75.6 / 77.8) | 147.9 (75.3 / 77.5) |
| code T=0 | 3 | 172.4 (58.9 / 62.1 / 61.3) | 174.8 (61.4 / 63.0 / 60.3) | 177.3 (63.5 / 62.9 / 64.6) |
| code T=0 | 4 | 193.7 (52.1 / 52.4 / 55.3 / 51.2) | 189.6 (49.1 / 51.1 / 53.1 / 51.1) | 192.0 (52.3 / 52.9 / 54.6 / 49.5) |
| structured T=0 | 1 | 138.3 (138.3) | 137.2 (137.2) | 138.4 (138.4) |
| structured T=0 | 2 | 198.9 (102.4 / 104.6) | 204.2 (103.8 / 106.0) | 201.3 (103.6 / 105.7) |
| structured T=0 | 3 | 276.0 (94.8 / 97.8 / 97.8) | 276.0 (94.8 / 97.8 / 97.8) | 257.4 (91.8 / 89.8 / 88.5) |
| structured T=0 | 4 | 321.6 (82.9 / 84.0 / 86.8 / 86.8) | 322.1 (83.0 / 84.2 / 86.9 / 86.9) | 345.3 (88.9 / 91.7 / 91.7 / 91.7) |
| prose T=0.7 thinking | 1 | 55.9 (55.9) | 56.2 (56.2) | 51.1 (51.1) |
| prose T=0.7 thinking | 2 | 71.1 (36.6 / 36.4) | 72.0 (36.9 / 37.5) | 76.4 (39.2 / 42.6) |
| prose T=0.7 thinking | 3 | 88.5 (31.4 / 36.2 / 30.2) | 94.0 (32.9 / 32.3 / 33.6) | 90.8 (31.1 / 30.2 / 32.0) |
| prose T=0.7 thinking | 4 | 105.6 (28.3 / 27.5 / 27.1 / 28.6) | 101.3 (27.9 / 25.3 / 26.0 / 26.3) | 105.3 (26.9 / 27.1 / 30.2 / 30.5) |
| prose T=1 thinking | 1 | 50.8 (50.8) | 54.8 (54.8) | 55.2 (55.2) |
| prose T=1 thinking | 2 | 73.0 (36.5 / 38.2) | 77.1 (38.5 / 42.9) | 72.3 (37.8 / 36.2) |
| prose T=1 thinking | 3 | 86.5 (32.2 / 31.3 / 29.6) | 90.9 (30.3 / 31.9 / 31.6) | 84.9 (29.5 / 29.4 / 31.5) |
| prose T=1 thinking | 4 | 99.1 (27.1 / 25.4 / 25.8 / 30.2) | 100.4 (25.8 / 28.0 / 27.1 / 28.6) | 108.6 (27.9 / 28.4 / 28.5 / 28.2) |

### Prefill ladder

| Target | Prompt tokens | Samples, tok/s | Reported (median) | Uncorrected (prompt / TTFT) | TTFT |
|-|-|-|-|-|-|
| 4K | 4,119 | 2,820.8 / 2,836.3 / 2,826.5 | **2,826.5** | 2,473.6 | 1.67 s |
| 8K | 8,213 | 2,821.0 / 2,812.7 / 2,808.2 | **2,812.7** | 2,625.8 | 3.13 s |
| 16K | 16,405 | 2,742.1 / 2,502.8 / 2,605.6 | **2,605.6** | 2,522.3 | 6.50 s |
| 32K | 32,789 | 2,667.2 / 2,670.0 / 2,659.0 | **2,667.2** | 2,622.9 | 12.50 s |
| 64K | 65,555 | 2,641.3 / 2,660.4 | **2,641.3** | 2,619.3 | 25.03 s |
| 128K | 131,091 | 2,650.3 / 2,659.5 | **2,650.3** | 2,639.2 | 49.67 s |
| 256K | 262,167 | 2,617.9 | **2,617.9** | 2,612.5 | 100.35 s |

Cached tokens were 0 in every sample. The 64K-256K rows have 2, 2 and 1 samples, as the protocol prescribes. Even the
uncorrected rates are above every other two-Spark build's published prefill (see the README's head-to-head).

### Deep-context decode

A prose decode wave (T=0, thinking off, 400 tokens) after a filler context of the given size; the context is filled
first and the wave then reuses it from the prefix cache.

| Context | Streams | Total tok/s | Per stream tok/s | TTFT after the fill | Cached tokens | Fill TTFT | Accepted per round |
|-|-|-|-|-|-|-|-|
| 32K | 1 | 63.9 | 63.9 | 433 ms | 32,640 | 12.4 s | 2.17 |
| 32K | 4 | 127.4 | 34.8 / 31.9 / 34.8 / 34.8 | 440-1,186 ms | 32,640 each | 12.4-12.6 s | 2.31 |
| 128K | 1 | 61.9 | 61.9 | 626 ms | 130,944 | 49.6 s | 2.08 |

One wave per cell. Decode loses 3 % from no context to 32K and 6 % to 128K at one stream.

### Short request behind a long prompt

The design bertholomus publishes: a cold 93,335-token prompt, then a short chat (64 tokens) sent 1 s later. Idle, the
short chat's first token takes 200 ms.

| Run | Long prompt tokens | Long prompt TTFT | Short chat TTFT | Short chat decode |
|-|-|-|-|-|
| 1 | 93,354 | 35.34 s | 34.33 s | 78.4 tok/s |
| 2 | 93,353 | 35.35 s | 34.35 s | 79.2 tok/s |

The short request waits for almost the whole long prefill. This is a real weakness of the current scheduler settings
(chunked prefill 8,192, up to 4 sequences); MiaAI's TensorFold recipe interleaves a late short request into a long prefill
(3.84 s in its own, different test).

## Quality: KL divergence against the original model

**Method.** sudoingX's `p4_kld.py` ([sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41),
Apache-2.0) runs DeepSeek's reference implementation over the **original** DeepSeek-V4.1-Flash-1017 checkpoint and over
each quantized build, teacher-forced on the same token sequences, and reports at every scored (assistant) position the
mean KL(original || quantized) and top-1 agreement (both models' most likely token is the same). Our runs keep the
original's top-128 tokens plus one tail bucket, so each KLD is a lower bound on the full-vocabulary value. The numbers
measure the **weights**; the serving engine and speculative decoding do not enter. Speculative decoding is lossless at
temperature 0 only to the extent the engine's identity tests show; we claim nothing beyond them.

Panels:

- **general panel**: sudoingX's 199 conversations of native DeepSeek-V4.1-Flash answers in 8 domains. Its **agentic**
  domain is 24 multi-turn conversations with tool definitions, tool calls and tool results, so it measures real
  tool-call turns.
- **legal panel**: ours, 210 sequences in 7 families (held out). Its replies were sampled from the HeNryous quant, not
  from the original model, which slightly favours quants (stated next to every legal number). Its "tools" family is
  structured JSON answers to a schema, not tool calling.

Weights: **served** = the legal-weighted allocation we serve (1,414 of 15,360 routed experts re-encoded at the same total
size); **HeNryous** = [HeNryous/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-DGX-Spark](https://huggingface.co/HeNryous/DeepSeek-V4.1-Flash-1017-EXL3-2.75bpw-DGX-Spark)
`86f85253`, the build `download.sh` fetches and the served weights start from. Measured 2026-10-21.

| Panel | KLD, served | KLD, HeNryous | Top-1, served | Top-1, HeNryous | KLD p99, served / HeNryous |
|-|-|-|-|-|-|
| general, all positions | 0.0204 | 0.0201 | 95.91 % | 95.96 % | 0.2831 / 0.2849 |
| legal, all positions (replies from a quant) | 0.0303 | 0.0329 | 96.85 % | 96.70 % | 0.6125 / 0.6628 |

General panel by domain:

| Domain | KLD, served | KLD, HeNryous | Top-1, served | Top-1, HeNryous |
|-|-|-|-|-|
| **agentic (tool calls)** | 0.0184 | 0.0183 | **95.88 %** | **95.91 %** |
| chat | 0.0475 | 0.0482 | 93.21 % | 93.14 % |
| code | 0.0129 | 0.0125 | 96.59 % | 96.62 % |
| knowledge | 0.0390 | 0.0382 | 93.51 % | 93.61 % |
| long | 0.0258 | 0.0258 | 95.97 % | 96.10 % |
| math | 0.0164 | 0.0152 | 95.88 % | 95.90 % |
| multilingual | 0.0607 | 0.0601 | 94.00 % | 94.05 % |
| writing | 0.0502 | 0.0514 | 93.40 % | 93.66 % |

Legal panel by family (replies sampled from a quant):

| Family | KLD, served | KLD, HeNryous | Top-1, served | Top-1, HeNryous |
|-|-|-|-|-|
| authority | 0.0245 | 0.0269 | 96.21 % | 95.94 % |
| drafting | 0.0333 | 0.0379 | 96.63 % | 96.46 % |
| extraction | 0.0180 | 0.0173 | 98.77 % | 98.69 % |
| general | 0.1174 | 0.1216 | 91.82 % | 91.82 % |
| hallucination | 0.0253 | 0.0285 | 96.38 % | 96.04 % |
| preservation | 0.0157 | 0.0152 | 98.49 % | 98.37 % |
| structured JSON answers | 0.0072 | 0.0079 | 99.25 % | 99.42 % |

Our HeNryous figures on the general panel match sudoingX's published figures for the same build (0.0201 / 95.96 %,
agentic 0.0183). The legal-panel figures here come from a different panel revision than the one quoted on the served weights'
card (0.0274 -> 0.0249).

Other builds' published quality numbers (their own test sets unless stated; not directly comparable):

| Build | What it publishes |
|-|-|
| sudoingX v2.0, EXL3 2.8 bpw | same general panel: 0.0198 / 95.94 %, agentic KLD **0.0175** (closer than ours); no per-domain top-1 |
| bertholomus, EXL3 2.52 bpw | own 122-row set, full vocabulary: short rows 0.1305 / 92.01 %, tool calls 0.5948 / 79.43 %, long rows 0.2876 / 87.07 % |
| MiaAI-Lab, EAQ v1.1 2.9 bpw | no KLD, top-1 or tool-call numbers; indexer-selection agreement 403,560 of 403,560 rows at 16K-32K |

**Same-test comparison: pending.** We are scoring bertholomus's 2.5 bpw weights (`b8054f70`) and MiaAI's EAQ v1.1 2.9 bpw
weights on our two panels with the same tool. Results will replace this table:

| Panel | Served (ours) | bertholomus 2.5 bpw | MiaAI EAQ 2.9 bpw |
|-|-|-|-|
| general, KLD / top-1 | 0.0204 / 95.91 % | pending | pending |
| agentic (tool calls), KLD / top-1 | 0.0184 / 95.88 % | pending | pending |
| legal, KLD / top-1 | 0.0303 / 96.85 % | pending | pending |

## How the court-opinion cells were measured

These rules apply to the speed record below and to `tools/bench.py`.

- **Cold prompts.** Each request carries a fresh random `cache_salt` and a unique first line, so it cannot reuse another
  request's prefix cache; the server's `cached_tokens` is checked to be 0.
- **TTFT** is the time from sending the request to the first streamed token (reasoning or answer text).
- **Decode tok/s** is per stream: `(completion_tokens - 1) / (time of last token - time of first token)`. It excludes
  the prompt pass. This is the same definition MiaAI's `tools/bench.py` uses.
- **Accepted draft tokens per round** and **server ms per round** come from the engine's `/metrics` counters, read
  before and after each group (`spec_decode_num_accepted_tokens / spec_decode_num_drafts`).
- **Medians.** Each cell's value is the median over its repeats; n is stated.
- **Exact length.** Our cells generate exactly 512 tokens (`ignore_eos`), so every request does the same amount of
  decoding regardless of what the model would have said.
- **Integrity.** A cell counts only if the server had no other traffic: `tools/bench.py` waits for zero running and
  waiting requests before each group and checks afterwards that the `/metrics` token counters moved by exactly what
  it sent.

## Speed record, 2026-10-28 (production `a0006fc`)

Conditions: commit `a0006fc` (the upstream-install release: patches 0051, 0064, 0067, 0075, 0085b, 0091, dual RDMA ring,
5 draft tokens at 3-4 streams, prefill chunk 8192, CPU pinning), remote Engram and remote drafter on, KV 6 GiB per rank,
context limit 327,680, 4 sequences, served weights the legal-weighted allocation of the HeNryous 2.75 bpw build, drafter
GPUs at 325 W. Temperature 1 with seed 42 + repeat, top_p 1, thinking on with effort `high`, 512
tokens (`ignore_eos`), priority 10, fresh cache salts (cached 0 checked). n = 3 per cell per pass. Prompts: public court
opinions and filings (CourtListener / RECAP), cut to the cell size. Production served nothing else during the runs.

Two passes on the same running engine (no restart), one at each clock cap:

| Cell | Metric | 2,150 MHz cap (SM ~2,125 under load) | 2,300 MHz cap (SM 2,268-2,281 under load) |
|-|-|-|-|
| short-b1 | decode tok/s | 57.75 | 57.24 |
| short-b1 | accepted per round | 1.250 | 1.207 |
| short-b1 | server ms per round | 38.84 | 38.54 |
| short-b1 | TTFT s | 0.781 | 0.816 |
| 32k-b1 | decode tok/s | 50.85 | 56.51 |
| 32k-b1 | accepted per round | 0.909 | 1.154 |
| 32k-b1 | server ms per round | 37.57 | 38.19 |
| 32k-b1 | TTFT s | 12.68 | 12.34 |
| 32k-b3 | decode tok/s, per stream | 31.36 | 30.21 |
| 32k-b3 | accepted per round | 1.193 | 1.146 |
| 32k-b3 | server ms per round | 90.47 | 87.31 |
| 32k-b3 | TTFT s | 43.11 | 42.03 |
| 32k-b4 | decode tok/s, per stream | 27.22 | 27.45 |
| 32k-b4 | accepted per round | 1.235 | 1.246 |
| 32k-b4 | server ms per round | 100.44 | 99.07 |
| 32k-b4 | TTFT s | 54.69 | 53.33 |
| 150k-b1 | decode tok/s | 54.33 | 52.11 |
| 150k-b1 | accepted per round | 1.125 | 1.036 |
| 150k-b1 | server ms per round | 39.51 | 39.32 |
| 150k-b1 | TTFT s | 59.13 | 57.63 |
| mixed150k-2decode | decode tok/s, per stream | 5.17 | 5.30 |
| mixed150k-2decode | accepted per round | 1.209 | 1.177 |
| mixed150k-2decode | server ms per round | 309.8 | 299.7 |
| mixed150k-2decode | TTFT s | 31.29 | 30.65 |

Against the previous production (`596ba1c`, an archive of 5-38 repeats over 3-8 engine starts at 2,150 MHz), the
release read prompts 14-20 % faster in every cell (cold 32K 14.8 -> 12.3-12.7 s, cold 150K 69.1 -> 57.6-59.1 s),
decoded 24-28 % faster in the mixed cell and about 8 % faster at 4 streams, and left single-stream decode unchanged within
noise. Server ms per round rose 8-12 % at 3-4 streams because each round now verifies up to 5 drafts per stream instead
of 4; per-stream decode did not fall.

Caveats: n = 3; acceptance at temperature 1 varies by about ±11 % between engine starts, so differences in the
accepted-per-round rows below that size are noise.

## Persistent prefix tier, 2026-10-30 and 2026-10-31 (production `ebc29ed8`)

Conditions: the production engine with the tier on (bounds 64 GiB, 8 GiB per namespace, 30-day expiry), pointed at a
separate test store; clock cap 2,300 MHz. A 150K-token prompt, 6 trials. A "reload" trial sends a prompt whose KV was
stored in an earlier trial and is no longer in GPU memory.

| | median | max |
|-|-|-|
| cold TTFT (nothing cached) | 58.59 s | |
| reload TTFT (read from NVMe) | 2.583 s | 4.254 s |
| speed-up of the first token | 22.66 x | |

Fault cases (a corrupted CRC, a corrupted sidecar file, a truncated block file) each fell back to recomputing the prompt:
one `load_failed` each, no tokens lost, correct output. Lowest `MemAvailable` during the window: 6.3 GB on each Spark.
Requests opt in to storage with a namespace tag; untagged requests are not stored and skip the tier entirely (patch 0106).

First reload after a restart in production, 2026-10-31: on the first request after an engine restart (GPU prefix cache
empty), 102,528 of the request's 107,821 prompt tokens (95.1 %) were read back from the NVMe tier instead of being
prefilled again, with 0 read misses. Counts only: it was private traffic, so no timing or content is published.

Reload across production restarts, 2026-10-31, on a synthetic test prompt: a 5,050-token prompt, tagged for storage, was
sent at 06:21 UTC with nothing cached (0 cached tokens; 10.2 s). Production then restarted twice: into the profiler
configuration of the [prefill census](#where-the-prefill-time-goes-2026-10-31-census-cold-32k) and back at 09:27 UTC.
At 10:56 UTC the same prompt was sent again: 4,992 of its 5,050 prompt tokens (98.9 %) came from the persistent tier,
and the request took 2.0 s, with 0 refused requests and 0 retries. Both requests ran with thinking off and at most 256
output tokens; the times are whole-request wall times, not times to first token.

## Capacity (engine log)

KV pool 6 GiB per rank (46,603 blocks). The engine admits 1,934,490 tokens, the same on `a0006fc` and `ebc29ed8`, so
four requests at the full 327,680-token limit fit (1,310,720). On `a0006fc` (2026-10-28), a 150K prompt plus three 32K
prompts sent at once all completed, with at least 5.6 GiB free on each Spark.

## Configuration history (2026-10-22 and 2026-10-23)

These are from the earlier configurations and are kept for the record; they used 1,500-token budgets and the clock of
the time, so they are not comparable with the 512-token cells above.

| Configuration | What changed | Measured effect |
|-|-|-|
| A, stock | everything on the Sparks | KV 989,460 tokens; short stream 55.96 tok/s; cold 32K TTFT 15.53 s; cold 150K TTFT 73.62 s |
| B | Engram tables served from x86 RAM over RDMA | cold TTFT 5.4 % / 5.7 % faster at 32K / 150K; outputs identical |
| D | B + drafter on an x86 RTX 3090, freed memory spent on KV (6 GiB per rank) | KV 1,604,926 tokens (+62 %); four concurrent 300K requests fit; single-stream decode 3-9 % slower with synchronous rounds |
| D-async, two-card | the remote round runs in a separate CPU process; the drafter runs on an NVLinked RTX 3090 pair | step p50 37.1 vs 39.6 ms (short) and 39.6 vs 41.2 ms (32K) against one-card synchronous D, 3.9-6.5 % lower; TTFT at parity; 0 watchdog fires |

RDMA link probes (2026-10-22, 64 MiB transfers): one link about 39.2 Gb/s; both links together 78.38 Gb/s.

## Where the decode time goes (2026-10-26 profile, 2,150 MHz)

A profiled engine (both-rank mean, ms per verify round; profiling itself slows the round slightly) on the configuration
of the time:

| Part of a round | 1 stream (short / 32K / 150K) | 4 streams, 32K |
|-|-|-|
| whole round | 38.2-39.6 ms | 76.4 ms |
| routed + shared experts | 15.2-15.6 ms (39-41 %) | 44.8 ms (59 %) |
| dense projections | 5.7-6.0 ms (15 %) | 10.1 ms (13 %) |
| L2 prefetch, not overlapped | 5.8-6.1 ms (15-16 %) | 4.1 ms (5 %) |
| attention | 2.2-2.3 ms (5.8 %) | 4.0 ms (5.2 %) |
| waiting for the remote drafter, including rank 1's broadcast wait | 2.78-2.95 ms (7.0-7.7 %) | 4.05 ms |
| all-reduce (intrinsic + rank wait) | 1.6-1.8 ms | 3.4 ms |
| Engram | 0.02 ms | 0.03 ms |

Reading the routed experts' weights dominates, and more so as streams are added. The remote drafter's share is small.

## Where the prefill time goes (2026-10-31 census, cold 32K)

Conditions: production `ebc29ed8` restarted with vLLM's torch profiler configured and nothing else changed (the profiler
records events and launches no kernel), both Sparks at a 2,300 MHz cap, chunked prefill 8,192. One cold 31,633-token
prompt, prefilled in four chunks (3 x 8,188 and 7,069 tokens), temperature 0, a fresh cache salt on every request and 0
cached tokens. Three profiled requests (1 output token) alternated with three unprofiled controls (512 output tokens);
every profiled request's first output piece matched the controls'. Median time to first token: controls 12,319.25 ms,
profiled 12,328.52 ms, so the profiler added 9.3 ms (0.08 %), all of it on host-side lines.

Each line is kernel time on one rank, the median of the three profiled requests; "both ranks" is the mean of the two
ranks, and the share is of the controls' median time to first token. "Corrected" takes the profiler's own 9.3 ms out of
the host-side lines.

| Line | both ranks, ms | corrected ms | share | rank 0 ms | rank 1 ms |
|-|-|-|-|-|-|
| MoE experts | 5,852.2 | 5,852.2 | 47.5 % | 5,854.4 | 5,850.0 |
| norms and elementwise | 2,094.2 | 2,094.2 | 17.0 % | 2,118.2 | 2,070.2 |
| attention (prefill) | 1,613.7 | 1,613.7 | 13.1 % | 1,614.9 | 1,612.6 |
| dense GEMM | 1,604.3 | 1,604.3 | 13.0 % | 1,604.9 | 1,603.7 |
| all-reduce | 789.7 | 789.7 | 6.4 % | 780.6 | 798.9 |
| all-reduce wait | 141.7 | 141.7 | 1.1 % | 145.7 | 137.6 |
| EXL3 GEMM | 93.0 | 93.0 | 0.8 % | 94.0 | 91.9 |
| outside the engine steps | 80.9 | 74.6 | 0.6 % | | |
| other kernels | 59.4 | 59.4 | 0.5 % | 57.2 | 61.7 |
| device wait | 21.2 | 21.2 | 0.2 % | 21.1 | 21.3 |
| waiting on the x86 drafter | 2.8 | 2.8 | 0.0 % | 5.5 | 0.0 |
| host gap | 3.0 | 0.0 | 0.0 % | 3.3 | 2.7 |
| sampler, unrecorded waits | 0.0 | 0.0 | 0.0 % | 0.0 | 0.0 |

Rank imbalance: the two ranks' all-reduce waits for each other add up to 0.28 s (2.3 % of the time to first token).
That is the most that matching the slower rank to the faster one could save; it sits inside the all-reduce wait line
above, not on top of it.

Per-chunk timeline of the median profiled request (the second of three), rank 0 / rank 1, ms:

| Chunk | tokens | prompt end | period | busy | MoE | EXL3 | dense GEMM | attention | all-reduce | all-reduce wait | norms, elementwise | host gap | all-reduces |
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
| 0 | 8,188 | 8,188 | 3141/3139 | 3132/3132 | 1498/1496 | 20/20 | 413/417 | 402/403 | 208/210 | 28/29 | 547/538 | 3/3 | 41 |
| 1 | 8,188 | 16,376 | 3139/3139 | 3133/3134 | 1482/1477 | 20/20 | 415/419 | 418/422 | 200/203 | 36/37 | 548/539 | 0/0 | 41 |
| 2 | 8,188 | 24,564 | 3153/3153 | 3146/3148 | 1502/1477 | 20/19 | 414/422 | 417/427 | 200/204 | 33/42 | 547/539 | 0/0 | 41 |
| 3 | 7,069 | 31,633 | 2816/2816 | 2809/2808 | 1372/1375 | 34/34 | 356/349 | 364/368 | 175/181 | 21/29 | 474/460 | 0/0 | 81 |

In the first profiled request, chunk 1 took 3,754 ms instead of about 3,140: rank 0's MoE kernels took 2,018 ms against
rank 1's 1,512, and rank 1 waited 613 ms in all-reduce. That request's time to first token, 13.05 s, is the high one of
the three (12.33 and 12.30 s for the others); the other two requests have no such chunk.

A 150K census (19 chunks) was attempted in the same window. Two traced requests covered chunks 0-14 between them and the
third capture was skipped, so chunks 15-18 have no trace; no 150K census is published.
