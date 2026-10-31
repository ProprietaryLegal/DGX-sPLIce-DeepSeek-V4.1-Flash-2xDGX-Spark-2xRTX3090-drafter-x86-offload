# Comparison with other DGX Spark recipes

Other public recipes serve DeepSeek-V4.1-Flash-1017 on two DGX Sparks. Each is good work and each publishes its own
numbers. This page lists what each one measured and under which conditions, with sources, and says which of DGX sPLIce's
numbers were measured the same way. Numbers below are quoted from each project's README or model card as of 2026-10-31; follow
the links for their current versions.

## sparkDash port numbers

On 2026-10-31 we ran MiaAI's sparkDash protocol (commit `b96244a2`, re-implemented in
[tools/sparkbench.py](../tools/sparkbench.py) with sparkDash's own lab prompts) on production `ebc29ed8`: both Sparks at a
2,300 MHz cap, drafter GPUs at a 400 W cap, 4 sequences, 3 repeats
([full tables](measurements.md#sparkdash-protocol-2026-10-31), raw
[JSON](../runs/2026-10-31-sparkdash-protocol-ebc29ed8.json)). Label: **port**. MiaAI's repository does not record which
prompts its run sent, so these rows share sparkDash's method but possibly not its prompts; the clock (2,300 against
2,200 MHz) and the hardware (our x86 host and 2 RTX 3090s) also differ.

| Total tok/s | 1 stream | 2 streams | 3 streams | 4 streams |
|-|-|-|-|-|
| prose T=0, ours / MiaAI | 66.0 / **80.7** | 90.5 / **110.6** | 112.4 / **133.6** | 130.1 / **154.0** |
| code T=0, ours / MiaAI | 110.5 / **118.1** | 147.9 / **149.4** | **174.8** / 171.0 | **192.0** / 166.1 |
| prose T=0.7 thinking, ours / MiaAI | 55.9 / **63.9** | 72.0 / **93.3** | 90.8 / **107.8** | 105.3 / **120.6** |

| Prefill tok/s | 4K | 8K | 16K | 32K | 64K | 128K | 256K |
|-|-|-|-|-|-|-|-|
| ours | **2,826.5** | **2,812.7** | **2,605.6** | **2,667.2** | **2,641.3** | **2,650.3** | **2,617.9** |
| MiaAI (sparkDash) | 2,105.9 | 2,152.0 | 2,154.8 | 2,153.6 | 2,136.2 | 2,077.1 | 2,065.0 |
| bertholomus (own tool) | | 2,439 | | 2,568 | 2,550 | 2,523 | |

The short-request test follows bertholomus's published design (a short chat sent 1 s behind a cold 93,335-token
prompt): our short chat's first token came after 34.3 s, bertholomus's after 38.6 s.

## The other builds' own benchmarks, 2026-10-31

On 2026-10-31, 06:22-07:00 UTC, we ran ports of the other builds' published benchmarks on production `ebc29ed8` (439
requests): both Sparks at a 2,300 MHz clock cap, drafter GPUs at a 400 W cap (325 W in production), `max-num-seqs` 4,
context limit 327,680, DSpark sampled drafting with a fixed window of 5. Every request carried a fresh `cache_salt` and
a unique first line, so no prefix cache helped. Each "theirs" number is quoted from the file and commit in the source
table below; we computed only the delta, (ours - theirs) / theirs. For time rows a negative delta means we are faster.
The labels are the README's ([definitions](../README.md#the-other-builds-own-benchmarks-run-on-dgx-splice)): **same
protocol** (our port of their script, with their prompts and parameters; the only deviations are the unique first line
and the fresh cache salt), **port** (a re-implementation whose prompts are not published, or a port that deviates in a
way that matters, named in the row) and **different benchmark** (another benchmark of the same quantity; an indication
only). The ported scripts and the raw result files of these runs are not in this repository yet.

| Build | Commit or post | Quoted from |
|-|-|-|
| [bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10](https://github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10) | `503b64e` (README v0.7.3) | README.md:60-74 |
| [sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41) | `f8f20b3` (release v2.0) | README.md:36-56 and :115-122, BENCHMARKS.md:246-254 |
| [Blackwellboy/DeepSeek-V4.1-Flash-1017-BLACKFOLD-TP2](https://github.com/Blackwellboy/DeepSeek-V4.1-Flash-1017-BLACKFOLD-TP2) | `d905cf0` | results/raw/kitbench-decode_b.json, kitbench-conc_b.json, tony-v41bench-parsed.json |
| [HeNryous/deepseek-v41-1017-dgx-spark](https://github.com/HeNryous/deepseek-v41-1017-dgx-spark) | `3820717` | README.md:127-131, :218-227 and :258-261 |
| HeNryous's build on the NVIDIA forum (renek) | [topic 386295](https://forums.developer.nvidia.com/t/386295), posts 1, 3 and 14 | the posts |
| [Elevatormusic/DeepSeek-V4.1-Flash-1017-EXL3-TensorFold-2x-DGX-Spark](https://github.com/Elevatormusic/DeepSeek-V4.1-Flash-1017-EXL3-TensorFold-2x-DGX-Spark) | `6fae084` | README.md:29-31, :193-202 and :232-242 |
| [tonyd2wild/DeepSeek-V4.1-Flash-TP2-and-TP4-DGX-Sparks](https://github.com/tonyd2wild/DeepSeek-V4.1-Flash-TP2-and-TP4-DGX-Sparks) | `74ac013` | its TP2 `v41bench` results, README.md:264-265 |
| [jayleaton/deepseek-v41-tensorfold-spark](https://github.com/jayleaton/deepseek-v41-tensorfold-spark) | `391d677` | README.md:49-52, ZIG-RESULTS.md:25-49 |
| [ZackO2o/DeepSeek-V4.1-Flash-TensorFold-DGXSpark-TP2](https://github.com/ZackO2o/DeepSeek-V4.1-Flash-TensorFold-DGXSpark-TP2) | `b9ead89` | README.md:46-54 |
| [MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks) | `0e7d421` | README "Performance" |

The scripts we ported: bertholomus's `kit_bench.py`, tonyd2wild's `bench/v41bench.py` (prompt set v1), Elevatormusic's
`tests/v41_suite.py` and `tests/v41_bench.py`, HeNryous's `bench/fair_bench.py` and three-code needle, and jayleaton's
`chains.py`, each at the commit above.

### kit_bench (bertholomus): greedy, thinking off

Label: same protocol. Set a ends at 512 tokens; set b ends at 384 tokens, with 9 repeats per prompt and the median
taken. Our 2- and 4-stream rows are means of 2 repeats against their medians of 9.

| Row | DGX sPLIce | Theirs | Delta |
|-|-|-|-|
| set a, 1 stream: code / prose / structured | 80.23 / 40.87 / 99.31 | bertholomus v0.7.3: 106.0 / 60.5 / 118.3 | -24.3 / -32.4 / -16.1 % |
| set a, 1 stream | same | sudoingX launch build v3: 86.6 / 54.2 / 103.7 | -7.4 / -24.6 / -4.2 % |
| set b, 1 stream: code / prose / structured | 89.88 / 45.75 / 135.25 | bertholomus v0.7.3: 112.7 / 67.5 / 159.5 | -20.2 / -32.2 / -15.2 % |
| set b, 1 stream | same | sudoingX v2.0, boot 1: 103.9 / 57.9 / 144.0 | -13.5 / -21.0 / -6.1 % |
| set b, 1 stream | same | Blackwellboy: 103.79 / 58.84 / 144.55 | -13.4 / -22.2 / -6.4 % |
| set b, 1 stream | same | HeNryous v20: 99.5 / 55.3 / 138.9 | -9.7 / -17.3 / -2.6 % |
| set b, 1 stream | same | Elevatormusic: 98.6 / 56.8 / 139.7 | -8.8 / -19.5 / -3.2 % |
| set b, 2 streams, aggregate | 67.56 | bertholomus 95.3; HeNryous v20 77.7; Elevatormusic 81.5; Blackwellboy 82.78 (median of 81.01 / 84.54) | -29.1 / -13.0 / -17.1 / -18.4 % |
| set b, 4 streams, aggregate | 100.43 | bertholomus 134.0; HeNryous v20 122.3; Elevatormusic 116.7; Blackwellboy 118.05 (median of 112.33 / 123.77) | -25.1 / -17.9 / -13.9 / -14.9 % |
| set b, 4 streams sustained 90 s | 115.44 | bertholomus 151.8; HeNryous v20 129.1; Elevatormusic 120.0 | -24.0 / -10.6 / -3.8 % |

sudoingX's README gives two v2.0 set b results: boot 1 (103.9 / 57.9 / 144.0, README.md:36-46), used above, and a
release-gate session beside TensorFold `8e0966e2` (103.7 / 57.8 / 144.4, README.md:52-56), which the
[sudoingX section](#sudoingx) below and the README's build table quote. Against the release-gate figures the deltas are
-13.3 / -20.8 / -6.3 %.

Draft tokens accepted per round in set b: code 3.31, prose 1.19, structured 5.0 (of 5). On sparkDash's prompts the same
server accepts 4.22 on code and 2.14 on prose. No other build publishes its kit_bench acceptance, so we cannot yet say
how much of the gap is the drafter and how much the base decode.

### v41bench (tonyd2wild): prompt set v1, T=0, thinking off

Label: same protocol. v41bench's prefill rate is prompt tokens divided by total request time, for us and for them
alike.

| Row | DGX sPLIce | tonyd2wild, TensorFold TP2 | Delta | Blackwellboy | Delta |
|-|-|-|-|-|-|
| 1 stream: aggregate / per stream / first token | 62.89 / 74.50 / 352 ms | 73.08 / 84.16 / 243 ms | -13.9 / -11.5 / +44.7 % | 75.89 aggregate | -17.1 % |
| 2 streams | 83.38 / 50.99 / 537 ms | 106.04 / 62.81 / 366 ms | -21.4 / -18.8 / +46.8 % | 106.58 | -21.8 % |
| 3 streams | 107.73 / 44.95 / 636 ms | 123.7 / 49.3 / 487 ms | -12.9 / -8.8 / +30.6 % | 127.95 | -15.8 % |
| 4 streams | 128.96 / 41.38 / 715 ms | 135.75 / 41.39 / 612 ms | -5.0 / 0.0 / +16.9 % | 135.91 | -5.1 % |
| 1 stream, per stream, coding | 109.27 | 105.63 | +3.4 % | 112.99 | -3.3 % |
| 1 stream, per stream, prose | 49.64 | 55.43 | -10.4 % | 65.1 | -23.7 % |
| 1 stream, per stream, narrative | 38.87 | 61.6 | -36.9 % | | |
| prefill, 8K target (11,611 tokens) | 1,973.3 | 2,180.2 | -9.5 % | 1,765.5 | +11.8 % |
| prefill, 32K target (46,829 tokens) | 2,201.3 | 2,199.5 | +0.1 % | 1,981.2 | +11.1 % |
| prefill, 64K target (93,355 tokens) | 2,199.1 | 2,135 | +3.0 % | 1,960.1 | +12.2 % |
| prefill, 128K target (186,792 tokens) | **2,265.7** | 2,044.4 | **+10.8 %** | 1,891.2 | **+19.8 %** |

### v41_suite (Elevatormusic)

Label: same protocol. Our values are medians of 3 suite runs; Elevatormusic's are medians of 6.

| Row | DGX sPLIce | Elevatormusic, TensorFold | Delta | Other |
|-|-|-|-|-|
| decode, prose, thinking off | 45.85 | 56.8 | -19.3 % | HeNryous v12 56.0: -18.1 % |
| decode, code, thinking off | 87.12 | 92.2 | -5.5 % | HeNryous v12 91.1: -4.4 % |
| decode, prose, thinking on | 46.90 | 54.2 | -13.5 % | |
| decode, code, thinking on | 64.74 | 71.6 | -9.6 % | |
| cold prefill, 8K | 1,522.6 tok/s, withheld | 562 (the first request after a start, not comparable) | | HeNryous v12 2,470 |
| cold prefill, 32K | **2,246.9** tok/s | 2,100 | **+7.0 %** | |
| ORCHID needle at 64K, request time | **24.27 s** | 35.9 s | **1.48x faster** | |
| ORCHID needle at 200K, request time | **76.29 s** | 109.8 s | **1.44x faster** | |
| schema group | 6/6 (strict `json_schema` 5/5 thinking off and 3/3 thinking on; `json_object`; choice; regex; prompt-only 5/5) | 32/32 for the whole suite | parity |
| reasoning group and no-leak check | all pass | pass | parity |
| tools group | 10/12 (`tool_choice_required` and `tool_choice_named` fail) | 12/12 | -2; see [known issues](../README.md#known-issues) (fixed since; not re-run) |

The 8K cold-prefill row is withheld in both directions: that request waited about 2 s before its first token, which the
same pass's 8,167-token needle (2,586.9 tok/s) did not. It is not counted until the delay is explained.

### v41_bench (Elevatormusic): aggregate includes the first-token wait, 2 repeats

Label: same protocol. HeNryous's figures are image v12 at 2,400 MHz with the same script (topic 386295, post 14).

| Streams | Prose: DGX sPLIce | TensorFold | Delta | HeNryous v12 | Delta | Code: DGX sPLIce | TensorFold | Delta | HeNryous v12 | Delta |
|-|-|-|-|-|-|-|-|-|-|-|
| 1 | 40.94 | 29.6 (includes a 7.3 s first-token wait) | +38.3 %, not a real win | | | 73.37 (one repeat waited 1.9 s) | 94.1 | -22.0 % | | |
| 2 | 54.93 | 73.5 | -25.3 % | 71.5 | -23.2 % | 112.23 | 106.6 | +5.3 % | 117.0 | -4.1 % |
| 3 | 68.85 | 82.3 | -16.3 % | 85.1 | -19.1 % | 124.30 | 124.3 | 0.0 % | 135.4 | -8.2 % |
| 4 | 73.94 | 94.4 | -21.7 % | 95.3 | -22.4 % | **157.18** | 140.3 | **+12.0 %** | 154.0 | +2.1 % |

At 4 streams, code per request is 42.00 against TensorFold's 36.8 (+14.1 %). Against Elevatormusic's release 1.1.0 gate
run (one pass) we are at -25.5 % on prose (73.94 against 99.3) and +7.9 % on code (157.18 against 145.7); against
HeNryous's image v5 at 2,000 MHz, +0.8 % on code (155.9). The bench's cold-prefix stage took 16.4 s for 32,958 tokens
and 13.7 s for 33,030; no other build publishes that stage alone.

### fair_bench (HeNryous): foreground decode beside background prefills

Label: port. Our background requests differ from HeNryous's: about 240,000 random characters with 16 output tokens,
against 60K-token prompts with 400, so each background request ends right after its prefill. Only the first of our
three repeats overlapped the background; repeats 2 and 3 ran alone, so the recorded medians with background (47.62 and
45.18 tok/s) are invalid and the table uses repeat 1.

| Case | DGX sPLIce | HeNryous | Delta |
|-|-|-|-|
| foreground alone, 600 tokens | 45.24 (median of 43.69 / 46.18 / 45.24) | 55.9 (v20), 57.2 (v22) | -19.1 / -20.9 % |
| beside 1 background prefill | 10.11 tok/s, first token 5.58 s, longest gap 5.57 s | ~29 (headline); 31.3 (gaps 3.4-4.9 s) on v20 at cadence 24; 58.5 (1.4 s) on v22 | -65 / -67.7 / -82.7 % |
| beside 2 background prefills | 5.51 tok/s, first token 2.14 s, longest gap 2.12 s | ~23; 22.5 (3.7-3.8 s) on v20; 59.1 (1.3-2.4 s) on v22 | -76.0 / -75.5 / -90.7 % |

This is our largest gap. HeNryous's v21 and v22 numbers come from scheduler patches (0031, priority-aware prefill
throttling, plus 0073 and 0074) that we do not run. With chunked prefill at 8,192 tokens, every foreground decode step
here shares the GPU with a background chunk, so the foreground waits on every token; the same cause makes a short chat
behind a cold 93K prompt wait 34.3 s ([head-to-head](../README.md#head-to-head)).

### Needles and long-prompt prefill

The 315K row is the same protocol: HeNryous's three-code needle (codes at 10, 50 and 90 % depth). The other prefill
rows compare our needle prompts' rate (prompt tokens over time to first token) with other builds' prefill benchmarks on
other texts (kit_bench's fixed-words text, sparkDash, their own needle documents), so they are labelled different
benchmark.

| Row | DGX sPLIce | Theirs | Delta | Label |
|-|-|-|-|-|
| 315,207-token prompt, 3/3 found | first token 124.2 s, 2,538.0 tok/s | HeNryous image v4i: 314K, 3/3, 152 s, 2,066 tok/s | 18.3 % less time, +22.8 % rate | same protocol |
| same | | HeNryous's first forum post (topic 386295, post 1): 314K in 170 s, 1,845 tok/s | +37.6 % rate | same protocol |
| same | | tonyd2wild: 300K needle in 152.8 s (about 1,963 tok/s); 1M needle at 1,559 tok/s | +29.3 % rate | different benchmark |
| same | | ZackO2o: 325,889 tokens at 1,899 tok/s | +33.6 % rate | different benchmark |
| 263,077-token prompt, 3/3 | 2,531.5 tok/s | MiaAI 1017: 256K at 2,065.0 (sparkDash prefill) | +22.6 % | different benchmark; our sparkDash port gave 2,612.5 at 262K |
| 131,250-token prompt, 3/3 | 2,560.9 | bertholomus 128K 2,523; jayleaton Zig 131K 2,496; HeNryous v20 2,149; Elevatormusic 1,989 (kit_bench client) | +1.5 / +2.6 / +19.2 / +28.8 % | different benchmark |
| 32,697-token prompt, 3/3 | 2,575.1 | bertholomus 2,568; jayleaton Zig 2,686; sudoingX 2,061; HeNryous v20 2,164; Elevatormusic 2,179 | +0.3 / -4.1 / +24.9 / +19.0 / +18.2 % | different benchmark |
| 8,167-token prompt, 3/3 | 2,586.9 | bertholomus 2,439; sudoingX 2,055; HeNryous v20 2,165; Elevatormusic 2,166 | +6.1 / +25.9 / +19.5 / +19.4 % | different benchmark |
| decode while answering, after 8K / 32K / 131K / 262K / 315K | 54.26 / 44.74 / 44.22 / 48.07 / 38.18 | after 128K: bertholomus 99.2, sudoingX 81.3, HeNryous v20 73.7; after 131K: jayleaton 64.9; sudoingX after 8K / 32K: 83.9 / 85.7 | -55.4 / -45.6 / -40.0 / -31.9 % at 128-131K | different benchmark; we decode about 256 tokens of the needle answer |
| longest needle | 315,207 tokens, 3/3 (our 327,680 limit) | bertholomus 1,039,836, 3/3; MiaAI 1017 479,012, 3/3; HeNryous 449K and 478K | | a configuration limit |

Reading the cold-prefill rows:

- On the needle text we are level with the two fastest TensorFold builds (bertholomus and jayleaton's Zig build, within
  -4 % to +6 %).
- From 8K to 131K we are 18-29 % ahead of the vLLM builds (sudoingX, HeNryous) and of Elevatormusic, on a different
  prompt text.
- At 300K and above, where only HeNryous, tonyd2wild and ZackO2o publish, we are 23-34 % ahead of their latest figures
  (38 % against HeNryous's first forum post).

The kit_bench prefill rows can become same protocol once our port gains kit_bench's `prefill` mode.

### Tool calls

| Check | DGX sPLIce | Theirs | Label |
|-|-|-|-|
| ToolCall-15 (TC-01 to TC-15, the core of SeraphimSerapis's tool-eval-bench `887b537`), thinking off | 28/30 (TC-03 failed) | no build publishes a ToolCall-15-only score | port: a subset of that benchmark |
| ToolCall-15, reasoning effort low | 30/30 | | port |
| jayleaton `chains.py`, thinking off | 10/12 (retry-after-error 0) | 11/12, an earlier run on a different weights build; its current build reports chains 6/6, counted per scenario | same protocol |
| jayleaton `chains.py`, effort high | 9/12 (retry-after-error 0, edit-config 1) | 11/12, the same earlier run | same protocol |
| Elevatormusic `v41_suite` tools group | 10/12 (`tool_choice_required` and `tool_choice_named` fail) | 12/12 | same protocol |
| tool-eval-bench 3.0.1 Hard Mode in full (104 scenarios), effort max / high, 2026-10-31 after the tool_choice fix | 96 (200/208) / 92 (192/208) | max: 0rand 97 (forum 386125 #271 / #288), dashtotherock 97 (#307), bernisse on MiaAI-Lab's 1017 recipe 96 with patch 0039 and 94 without (#322); high: dashtotherock 92, bernisse 90 | settings differ (`--parallel` 8 or 1 there, 4 here); see the [README](../README.md#tool-eval-bench-301) |

The two `v41_suite` failures are the forced-choice error in the README's [known issues](../README.md#known-issues). Both
requests have passed in production since the 2026-10-31 fix; the suite was not re-run.

### sparkDash (MiaAI)

The sparkDash rows are at the [top of this page](#sparkdash-port-numbers), labelled port.

## Published numbers and their conditions

### MiaAI-Lab, TensorFold engine

Source: [MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks)
(Apache-2.0), README "Performance" and `docs/measurements.md`.

Conditions: TensorFold (Zig engine), EAQ 2.9 bpw weights, both GPUs capped at 2,200 MHz, `CONTEXT=524288`, up to 4
streams, drafts on, "real prose and code prompts", numbers as reported by sparkDash. The head also ran a desktop and
about 18 small containers.

| Decode tok/s | 1 stream | 2 streams | 3 streams | 4 streams |
|-|-|-|-|-|
| prose, T=0, thinking off | 80.7 (TTFT 133 ms) | 110.6 total, 56.0 each | 133.6 total, 45.4 each | 154.0 total, 39.9 each |
| prose, T=0.7, thinking on | 63.9 (TTFT 214 ms) | 93.3 total, 48.6 each | 107.8 total, 38.0 each | 120.6 total, 32.0 each |
| code, T=0, thinking off | 118.1 (TTFT 213 ms) | 149.4 total, 76.4 each | 171.0 total, 58.8 each | 166.1 total, 45.0 each |

Prefill: 2,105.9 / 2,152.0 / 2,154.8 / 2,153.6 / 2,136.2 / 2,077.1 / 2,065.0 tok/s at 4K / 8K / 16K / 32K / 64K / 128K /
256K-token prompts (TTFT 2.13 s to 127.13 s). Its own `tools/bench.py` (temperature 0, thinking off, random-word prompts)
reads lower decode, 55-61 tok/s at one stream; the README attributes the gap to the prompts, since a drafter accepts
fewer tokens on random words.

### sudoingX

Source: [sudoingX/dgx-spark-deepseek-v41](https://github.com/sudoingX/dgx-spark-deepseek-v41) (Apache-2.0), README.

Conditions: vLLM with its patch series and EXL3 MoE plugin (`dsv41-serve:v5`), its own EXL3 2.8 bpw build (v2.0),
`kit_bench.py` set b: one stream, greedy, thinking off, 384-token replies, a 64-token warm-up, then 9 repeats per
prompt, median. DSpark on with k = 5 and per-round depth. Same-box comparison against TensorFold on alternating boots.

| tok/s, median of 9 | code | prose | structured |
|-|-|-|-|
| TensorFold `8e0966e2`, same setup | 97.7 | 57.5 | 140.4 |
| sudoingX v2.0 | 103.7 | 57.8 | 144.4 |

Quality (README, `p4_kld.py` on its 199-conversation panel): v2.0 KLD 0.0198 / top-1 95.94 %, agentic domain KLD
0.0175; HeNryous 2.75 bpw 0.0201 / 95.96 %, agentic 0.0183. We use the same tool and panel; our figures for the
HeNryous build match these.

### HeNryous

Source: [HeNryous/deepseek-v41-1017-dgx-spark](https://github.com/HeNryous/deepseek-v41-1017-dgx-spark) (Apache-2.0), README.

Conditions: vLLM image v5 (the image this repository serves), EXL3 2.75 bpw, Elevatormusic's TensorFold test scripts
(`tests/v41_suite.py` speed group, `tests/v41_bench.py`) unchanged, temperature 1 and top_p 1, medians of three suite
runs or two bench runs.

| tok/s, median | v5, 2,000 MHz | v5, 2,400 MHz | v12, 2,400 MHz |
|-|-|-|-|
| prose, 1 stream (suite) | 54.6 | 56.6 | 56.0 |
| code, 1 stream (suite) | 91.5 | 88.9 | 91.1 |
| prose, aggregate 2 / 3 / 4 streams (bench) | 71.9 / 85.3 / 94.4 | not clean (thermal cap) | 71.5 / 85.1 / 95.3 |
| code, aggregate 2 / 3 / 4 streams (bench) | 112.6 / 136.1 / 155.9 | not clean (thermal cap) | 117.0 / 135.4 / 154.0 |
| prefill, cold 8K | 2,203 | | 2,470 |
| decode with thinking on, prose / code (suite) | 52.8 / 78.8 | 54.6 / 59.2 | 52.2 / 64.6 |

Its README notes that single-stream code at T=1 moves by up to ±10 % between runs.

### bertholomus, TensorFold engine

Source: [bertholomus/DeepSeek-V4.1-Flash-TensorFold-TP2-2xGB10](https://huggingface.co/bertholomus/DeepSeek-V4.1-Flash-TensorFold-TP2-2xGB10)
(model card, v0.7.3, 2026-10-24; recipe [bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10](https://github.com/bertholomus/deepseek-v4.1-tensorfold-tp2-2xgb10),
Apache-2.0) and the weights card [bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-2.5bpw](https://huggingface.co/bertholomus/DeepSeek-V4.1-Flash-1017-EXL3-2.5bpw)
(revision `b8054f70`).

Conditions: TensorFold branch `deepseek-v41-zig-tp2`, EXL3 2.5 bpw routed experts (2.52 bpw overall, about 185 GB),
`--context 1048576 --parallel 8`, a shared window of 2,097,152 positions, greedy, DSpark drafting, median of 3 unless
noted, its own prompt sets a and b. Clock not stated.

| Row | tok/s |
|-|-|
| decode, set a (512 tokens): code / prose / structured | 106.0 / 60.5 / 118.3 |
| decode, set b (384 tokens): code / prose / structured | 112.7 / 67.5 / 159.5 |
| 2 / 4 streams, set b, aggregate (median of 9) | 95.3 / 134.0 |
| 4 / 8 streams sustained 90 s, set b, aggregate | 151.8 / 168.3 |
| prefill 8K / 32K / 64K / 128K | 2,439 / 2,568 / 2,550 / 2,523 |
| prefill 93,335 tokens | 2,364 |
| decode after a 128K prompt (three fixed prompts: 53.5 / 114.4 / 99.2) | 99.2 |
| short chat 1 s behind a cold 93,335-token prompt, first token | 38.6 s |

Quality (weights card): KL(original || quant) over the full vocabulary and top-1 agreement on its own 122-row set
(294,481 tokens): short rows 0.1305 / 92.01 %, long rows 0.2876 / 87.07 %, wiki 0.1558 / 87.41 %; by kind, code
0.0494 / 95.22 %, math 0.1425 / 91.51 %, prose 0.1254 / 91.77 %, creative 0.0623 / 91.09 %, tool calls 0.5948 /
79.43 %. Gates: 1M-context needles 3/3, tool calls 16/16, structured output 11/11.

### DGX sPLIce (this repository)

sparkDash port rows and the other builds' own benchmarks: above. Our own conditions (temperature 1, thinking on, 512 tokens, court-opinion prompts up to
150K): [measurements.md](measurements.md#speed-record-2026-10-28-production-a0006fc). Quality on sudoingX's panel:
0.0204 / 95.91 % (served), agentic 0.0184 / 95.88 %; see [measurements.md](measurements.md#quality-kl-divergence-against-the-original-model).

## Why numbers from different protocols cannot be ranked

| Factor | Effect |
|-|-|
| temperature and thinking | greedy decoding without thinking lets a drafter accept far more tokens than T=1 with reasoning text; MiaAI's own rows show 80.7 (T=0, off) against 63.9 (T=0.7, on) |
| prompt content | code drafts better than prose; random words draft worst (MiaAI: 55-61 against 80.7) |
| output length | a natural end stops at different points; a fixed 512 or 384 tokens measures a fixed amount of decoding |
| GPU clock cap | 2,000 to 2,400 MHz across the recipes; the two ranks wait for the slower GPU |
| extra hardware | DGX sPLIce uses an x86 host and two RTX 3090s; the others use the two Sparks only |
| weights | 2.52, 2.75, 2.8 and 2.9 bpw builds with different calibration |
| context limit | 327,680 here, 524,288 for MiaAI, 1,048,576 for bertholomus; it changes the memory left for KV and the engine's scheduling |

## How to measure the same conditions

`tools/sparkbench.py` runs sparkDash's protocol with sparkDash's own lab prompts (from its `src/shared/llmPrompts.js`)
against any OpenAI-compatible server, so its numbers follow the method of MiaAI's sparkDash table (which prompts
MiaAI's run sent is not recorded):

```bash
python3 -I tools/sparkbench.py --url http://<head>:<port> --out runs/<recipe>-<date>.json --reps 3 \
    --suites prose-t0,code-t0,structured-t0,prose-t07-think,prefill --deep 32768:1,131072:1 --interference 2
```

`tools/bench.py` is our own tool. `--profile ours` runs the cells in measurements.md on synthetic records instead of
court opinions; `--profile mia` approximates MiaAI's headline conditions on synthetic prompts fixed by `--seed` (512
tokens at most, natural end allowed), so its absolute numbers differ from sparkDash's. For a server that does not accept
vLLM's `cache_salt` or `priority` fields, add `--no-cache-salt` or `--no-priority`; every prompt still starts with a
unique line, so the prefix cache cannot be hit.

```bash
python3 -I tools/bench.py run --profile all --url http://<head>:<port> --exact-size \
    --label <recipe>-<date> --note "<engine, commit, clock>" --out runs/<recipe>-<date>.json
python3 -I tools/bench.py compare runs/<ours>.json runs/<recipe>-<date>.json
```

Lock and record the GPU clock (`tools/node_watch.py` logs it) and state it with the result. We have ported
bertholomus's `kit_bench` sets a and b, tonyd2wild's `v41bench`, Elevatormusic's `v41_suite` and `v41_bench`,
HeNryous's `fair_bench` and three-code needle, jayleaton's tool chains and ToolCall-15
([results](#the-other-builds-own-benchmarks-2026-10-31)); the ported scripts and their raw files are not in this
repository yet. Still to port: 8-32 stream sweeps and 1M needles (we serve at most 327,680 tokens). For llama-benchy
and tool-eval-bench, which are public and were run unmodified, see the README
([llama-benchy](../README.md#llama-benchy-040), [tool-eval-bench](../README.md#tool-eval-bench-301)). If you maintain
one of these recipes and want a number corrected or a condition stated differently, please open an issue.
