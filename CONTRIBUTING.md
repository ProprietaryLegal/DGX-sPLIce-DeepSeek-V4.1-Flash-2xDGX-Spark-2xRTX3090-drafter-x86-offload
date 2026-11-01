# Contributing

Bug reports, measurements on other hardware, corrections to our numbers or credits, and pull requests are all welcome.

## Reporting a bug

Open a [bug report](https://github.com/ProprietaryLegal/DGX-sPLIce-DeepSeek-V4.1-Flash-2xDGX-Spark-2xRTX3090-drafter-x86-offload/issues/new?template=bug_report.yml).
Include the commit you run, which components are on (remote Engram, remote drafter, async, prefix tier), the engine
log lines around the failure and the output of `./status.sh`. Please remove addresses, host names and anything from
your prompts that you would not post publicly.

## Reporting a measurement

Run `tools/bench.py` and attach its JSON file to a
[performance report](https://github.com/ProprietaryLegal/DGX-sPLIce-DeepSeek-V4.1-Flash-2xDGX-Spark-2xRTX3090-drafter-x86-offload/issues/new?template=performance_report.yml).
The JSON holds token counts and timings only, never prompt or generated text. State the GPU clock cap and what else
ran on the machines. Numbers measured on another recipe are just as welcome: the point is same-conditions comparisons.

A number goes into the README or `docs/measurements.md` only if it is MEASURED, with its date, commit, clock and
conditions. Estimates and projections stay out of the results tables.

## Pull requests

- One change per pull request, with the reason in the description.
- Run the CPU tests you touched: `python3 -I -m unittest discover -s tools/tests` for `tools/`, and each component's
  suite (its README says how).
- A change to serving behaviour needs a before-and-after measurement with `tools/bench.py` on GB10 hardware, or a clear
  statement that it has none yet; we can run it on ours.
- Keep third-party code under its own licence and keep its SPDX and attribution headers; add new sources to
  [CREDITS.md](CREDITS.md) and [NOTICE](NOTICE).
- Do not add prompts, outputs, logs or caches from real use. Benchmarks use the synthetic prompts `tools/bench.py`
  generates.

By contributing you agree that your contribution is licensed under Apache-2.0, like the rest of the original code.
