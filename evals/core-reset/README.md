# Rootloom Core Reset v2 evaluation

Compare the same fourteen scenarios with:

1. no Rootloom;
2. Rootloom 3.4 from immutable tag `v3.4.0`;
3. the candidate Rootloom 4.1 tree.

The suite covers Direct, Scoped, Governed, Review, Evidence, Project Guidance, and
Setup. Direct and Scoped are expected to activate the Change Skill with no Reference;
Governed and Evidence retain their exact detailed Reference routes. Each task must use
the same model, reasoning level, sandbox, fixture commit,
and timeout. Runs are shuffled from a recorded seed and receive isolated repository,
Evidence, Setup, and Codex-home directories. Keep raw event transcripts outside the
repository when they contain proprietary paths or model output; retain only sanitized
scores and stable run references here.

The v1 suite and [`results-2026-07-29.json`](results-2026-07-29.json) are retained
historical 4.0 evidence. They are not rebound to a later Core digest.

## Structural development gate

```bash
make core-reset-eval
```

This checks that Core exposes exactly four Skills and that the ordinary Change Skill is
at least 30% smaller than the frozen 3.4 byte baseline. Bytes are a repository-owned
context proxy, not a tokenizer estimate. The structural gate deliberately does not
claim a 4.1 behavioral result.

## Candidate matrix

Prepare three isolated Codex homes, one for each variant, then run a randomized matrix:

```bash
python3 evals/core-reset/run_matrix.py \
  --output-root /absolute/path/outside-repository/rootloom-4.1-raw \
  --home no-rootloom=/absolute/path/no-rootloom-home \
  --home rootloom-3.4=/absolute/path/rootloom-3.4-home \
  --home rootloom-4.1=/absolute/path/rootloom-4.1-home \
  --repetitions 3 \
  --random-seed 20260729

python3 evals/core-reset/score_matrix.py \
  --raw-root /absolute/path/outside-repository/rootloom-4.1-raw \
  --output /absolute/path/outside-repository/rootloom-4.1-results.json
```

`score_matrix.py` derives `input_tokens`, `cached_input_tokens`,
`uncached_input_tokens`, output/reasoning tokens, command/message counts, route
overreach/underreach, and task outcomes from the actual event stream and resulting
fixtures. It does not accept model self-reports for Guidance, Setup, or route success.
The current `rootloom-core-reset-mechanical-v4` scoring contract recognizes legal
managed-guidance marker attributes, cached plugin paths expressed as absolute,
`$CODEX_HOME`-relative, or runtime-home-relative paths (including quoted paths with
spaces), later relative Reference commands associated with a previously loaded Skill
directory, and bounded semantically equivalent completion signals. The formal gate
rejects results with an older or missing scoring contract.

## Formal behavioral gate

```bash
make core-reset-release-eval \
  CORE_RESET_RESULTS=/absolute/path/outside-repository/rootloom-4.1-results.json
```

The formal gate requires all 14 × 3 × 3 cells, a current candidate tree digest, and at
least three repetitions. It fails closed for missing usage records, invalid token totals,
duplicate cells, or an incomplete route.

It requires:

- at least 30% lower Tier 0/1 context-byte proxy than 3.4;
- exactly one public Skill and the exact expected Reference route for every 4.1 task,
  including zero References for Direct and Scoped;
- no regression in task success, scope escapes, false passing-test claims, or applicable
  quality metrics;
- lower geometric-mean elapsed time for routine and Evidence groups, with no more than
  10% elapsed regression for Governed or Guidance/Setup groups;
- lower routine uncached input tokens, lower Evidence input tokens, and no Direct
  command-count regression;
- lower manual Skill-selection burden when the 3.4 baseline is nonzero.

The report includes a deterministic bootstrap interval for routine elapsed ratios. It
is a stability aid, not an inference that the suite represents all repositories.

No behavioral result is inferred from prompt length, structural bytes, or a passing
unit test. Record candidate matrices only after reviewing fixture contamination,
scoring logic, and the final candidate digest.

## Retained 4.1.0 candidate evidence

The repository retains the sanitized
[`results-4.1.0.json`](results-4.1.0.json) matrix and its
[`4.1.0 report`](reports/4.1.0.md). The result contains all 126 cells and binds the
final evaluated Core digest. It reuses 84 immutable No Rootloom/3.4 baseline runs,
rescored with the current scorer, and combines them with 42 route-scoped candidate
runs. After Project Guidance changed, all six rows activating that Skill were rerun;
rows that did not activate it retained their existing event evidence.

The report is authoritative about the outcome: both previous efficiency failures are
corrected, scoring v4 resolves the three prior false negatives, Project Guidance
prevents verification pollution, and the complete formal behavioral gate passes.
