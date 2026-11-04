# Support Insights agents

The [package AGENTS.md](https://github.com/etl-craft/etl-craft/blob/main/AGENTS.md) applies.
Read its local copy at ../etl-craft/AGENTS.md before changing this project.
A package defect is fixed in etl-craft in its own package PR, never worked around here.
Use TMPDIR=$HOME/.cache/etl-craft/tests/tmp-codex, at most two test workers,
and one suite at a time. Do not run the package service stack while k3d is up.
Every pod needs memory requests and limits. Keep idle services' requests low;
keep Trino's request near its limit. Pods must have verified LimitedSwap enabled.
