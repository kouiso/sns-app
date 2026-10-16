# Gates workflow entry

`task ci:fast` runs the shared entry contracts and every verification phase from
`gates.yml`. It expects Go 1.24, Node 22, Python 3, Bash, embedmd 1.0.0 and the
prototype dependencies to be prepared. The Auth SDK57 phase still uses the
workflow's exact `npm ci --ignore-scripts --no-audit --no-fund` command.

`task ci` also installs embedmd and the prototype dependencies using the same
commands as the workflow. Both tasks run the same candidate, QA, trial and
material checks. They do not replace TruffleHog or the GitHub post-merge and
notification workflows.

For a local PR comparison, set `CI_EVENT_NAME=pull_request` and
`CI_PR_BASE_SHA=<base commit>` before running either task. G4 fails if the base
cannot be resolved. Without a PR context it inspects existing receipts, matching
the push workflow. The checkout must include the base commit and its history.

Individual phases are available as `bash .github/ci/run.sh <phase>`; the workflow
keeps its existing step names and conditions. On an earlier failure, local
execution skips the remaining ordinary phases, continues all material phases
and returns the first failure. The existing gate-step wrapper translates only
exit 3 into an explicit undecided warning. Fixture-only findings stay advisory.
Existing dependency links can be reused; other local directories are never
replaced. No candidate or formal evidence is accepted merely because a CLI
contract test passes.

Run `python3 scripts/ci/test_ci_entry.py` for isolated CLI control tests. These
invoke the real entry and real gate-step wrapper with temporary tool fixtures.
They cover command routing and failures; they do not build an app or validate
material content.
