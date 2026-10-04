# AGENTS.md

A pipeline that hunts for bugs in third-party Hypothesis test suites using
[CrossHair](https://github.com/pschanely/CrossHair) through the
[hypothesis-crosshair](https://github.com/pschanely/hypothesis-crosshair)
plugin. Two goals: a trophy list of third-party bugs that **only** the solver
finds, and defects in CrossHair and the plugin found under realistic use.

Read `README.md` for the layout and the design points, and
`docs/backlog.md` for why things are the way they are -- it is the project's
memory, written as each thing was measured.

## Dev setup

```
uv sync --group lint
```

The formatters are pinned in their own group, because black's output changes
between releases and the test matrix reaches back to 3.9, where the resolver
picks an older one. CI lints on a single interpreter with those exact
versions and runs the tests everywhere.

## Checks

Run all four before committing.

```
uv run black --check .      # uv run black . to fix
uv run isort --check-only .
uv run pytest
uv run python -m mutation
```

Mutation suites are the fourth. A test that cannot fail is not a test, so
every module here has a companion suite that breaks the code deliberately
and checks the tests notice. Keep them passing and extend them with the code.

## Conventions

- **Linting**: isort, black (line length 88).
- **Naming and doc strings**: name functions and parameters by what they
  **do**, not by how they are used. Doc strings describe current behaviour
  only -- no history, no litigating decisions.
- **Code comments**: a **very high bar**. Surprising or confusing behaviour
  only. Justify changes in the commit message, never in a comment.
- **Record what you measure**: a number in `docs/backlog.md` beats a claim.
  When a threshold or weight is a guess, say so where it is defined.

## Things this code must keep doing

These are not style preferences. Each cost something to learn.

- **Verdicts come from tier-A runs only.** Observability realizes symbolic
  draws and shifts the search, so it may suggest a further run and may never
  decide one.
- **An inconclusive replay never refutes a finding.** Absence of evidence
  yields `pending_validation`, never `crosshair_false_positive`.
- **A harness repair changes the environment, never the suite.** `Repair`
  has no field that can name a file, so the dangerous repair is
  unrepresentable rather than merely discouraged.
- **Rejecting a candidate needs a fact.** Admitting a dud costs one run;
  rejecting a good project costs findings nobody ever counts. Only an
  absence of property tests rejects. Everything else is a rank.
- **A manifest pins the project, never the toolchain.** The packages a run
  is measuring -- Hypothesis, pytest, CrossHair, the plugin, and everything
  they require -- must stay free to resolve, or the next upgrade cannot be
  installed and the loop measures the previous release forever.

- **No automated writes to third-party repositories.** Not rate-limited, not
  gated: no such path exists. The loop drafts, a human posts.
