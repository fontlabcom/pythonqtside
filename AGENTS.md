---
this_file: AGENTS.md
---

## Owner priority: functional progress first (2026-11-15)

Future agents must make large, swift advances in working functionality. Prioritize visible user problems and useful, coherent feature increments. This instruction sets the work order and supersedes older requirements to complete exhaustive testing or build test infrastructure before ordinary implementation.

Keep packages coherent and compatible. Check shared APIs, imports and lazy aliases, data formats, dependency direction, object ownership and lifetime, installers, launchers and examples. Update affected providers and consumers together; preserve existing supported behavior and avoid dependency cycles.

During implementation, use the smallest meaningful smoke checks and focused regression tests for the changed behavior and affected package boundaries. Detailed testing, exhaustive coverage, broad performance studies and full acceptance matrices can follow in a later testing pass. Do not let test harnesses, sandbox/supervisor design, repeated unchanged suites, evidence machinery or review paperwork become the main project. Build such infrastructure only when a concrete functional defect or necessary safety constraint requires it.

Record deferred checks and known limits plainly. Do not call untested native, installed or published behavior verified. Keep existing mandatory delivery hooks, preservation rules, licence/privacy obligations, repository exclusions and explicit native/publication holds intact. When one action is held, continue other authorized functional work instead of expanding unrelated infrastructure.

Choose the next substantial useful feature or shared fix and carry its affected providers and consumers together. Timebox supporting investigation; once focused checks establish a usable increment, continue functionality work. Queue detailed testing for a later pass with its concrete remaining checks instead of letting test infrastructure displace product delivery.

## Current scope — 2026-11-05

Issue 230 documentation reconciliation is current. Issue 123 remains paused. The qualified Issue 207 isolated candidate is separate from canonical source, installed artifacts, native acceptance and publication. Reconcile that candidate with later work before integration. Issue 210 specifies future architecture; Issue 211 retains unfinished follow-up checks. Retained dated receipts describe their original source and acceptance surface only.

Canonical source inspected for this proposal: `1af6f8bd2d54`. This is a dated source observation, not an installed or native acceptance claim.

Keep inventories and routing matched to actual PythonQt/Echopy captures; never infer native Qt 6 support from standalone PySide6 tests.

Qualify QFileDialog tuple adaptation, overloads, properties, virtuals and ownership in the actual host, plus genuine artifacts and ordinary dependency resolution.

## Organization and checks

`src/pythonqtside/` contains namespace routing and inventory tooling; `examples/` supplies compatibility demonstrations; `tests/` checks routing; `src_docs/md/pythonqt-compatibility.md` defines supported and unsupported behavior.

Prepare a development environment with pytest and a matching Echopy package as described in README, then run `./test.sh` (`uv run --no-sync python -m pytest`). Host-targeted checks use arm64 Python 3.11; the README Python 3.12 environment is for offline development only.

# pythonqtside AGENTS

## Owner priority: functional progress first (2026-11-15)

Future agents must make large, swift advances in working functionality. Prioritize visible user problems and useful, coherent feature increments. This instruction sets the work order and supersedes older requirements to complete exhaustive testing or build test infrastructure before ordinary implementation.

Keep packages coherent and compatible. Check shared APIs, imports and lazy aliases, data formats, dependency direction, object ownership and lifetime, installers, launchers and examples. Update affected providers and consumers together; preserve existing supported behavior and avoid dependency cycles.

During implementation, use the smallest meaningful smoke checks and focused regression tests for the changed behavior and affected package boundaries. Detailed testing, exhaustive coverage, broad performance studies and full acceptance matrices can follow in a later testing pass. Do not let test harnesses, sandbox/supervisor design, repeated unchanged suites, evidence machinery or review paperwork become the main project. Build such infrastructure only when a concrete functional defect or necessary safety constraint requires it.

Record deferred checks and known limits plainly. Do not call untested native, installed or published behavior verified. Keep existing mandatory delivery hooks, preservation rules, licence/privacy obligations, repository exclusions and explicit native/publication holds intact. When one action is held, continue other authorized functional work instead of expanding unrelated infrastructure.

Choose the next substantial useful feature or shared fix and carry its affected providers and consumers together. Timebox supporting investigation; once focused checks establish a usable increment, continue functionality work. Queue detailed testing for a later pass with its concrete remaining checks instead of letting test infrastructure displace product delivery.


## Live font testing in FontLab (owner instruction, 2026-11-10)

Test, verify and edit in the font that is open in FontLab 9. Don't hold back
because the owner might be working on it. Just work in it. If no font is open,
open a VFJ from `~/Desktop` first (File > Open, or `fontlab.flPackage(path)`
and `flWorkspace.instance().addPackage`). Those VFJs are for agents. Add glyphs,
kerning pairs, elements, contours, masters or anything else the test needs,
and save the files when that helps. This replaces older rules that required an
empty FontLab session or forbade editing open fonts. `fl-native.sh --mutating`
now runs with fonts open (`FL_REQUIRE_EMPTY=1` restores the old check). The
serialized lock still applies: one native run at a time. Don't quit or restart
FontLab, and don't close fonts from Python, because that has crashed the host.

## Milestones and delivery

Read [PLAN.md](PLAN.md), [TODO.md](TODO.md) and [WORK.md](WORK.md) before work.
Make the smallest complete MVP for one named acceptance task. Find all callers,
tests, fixtures, exports and documentation first. Use graph impact before source
symbol edits; confirm stale or unknown graph results against current source.
Keep product work in isolated successors and preserve the owner's checkout.

Run this repository's exact checks and the unchanged 80% gate for each complete
changed production module. Use an independent review before a milestone commit.
Under the current owner task, commit and push reviewed, passing milestones;
verify remote heads rather than inferring delivery from local tracking refs.
Before main integration, reconcile concurrent work and all consumers, run graph
change analysis and repeat the required acceptance on the combined source.

Before removing obsolete branches or files, prove integration, retain recoverable
unique work and check fresh owner/worktree attachments. Preserve sealed reports,
licences, archives and private data. Do not rewrite history by implication.
Remove verified completed work from PLAN/TODO and record scoped evidence in
CHANGELOG. Keep implemented-only native/artifact checks open in TODO. Issue 123
remains paused; no instruction here authorizes driving the owner's FontLab,
installing into its user folder or publishing a site.

## Private source/build-only documentation

Author pages under `src_docs/md` and use the separate hash-locked docs environment with `sh src_docs/build.sh`. Generated `docs` is immutable output. The main workflow qualifies direct source/output lineage and full ignored-output parity. Twelve private P/L operations remain owner-held; no Pages request or permission belongs here. Preserve runtime sources and native boundaries.

## Integration rounds

After each round of important changes, integrate it into `main` and upstream:
fetch `origin/main`, build the change on top of it in an isolated branch or
worktree, and resolve conflicts by keeping both our work and teammates' work.
Never discard upstream commits, and never force-push. Run the repository's
checks on the merged result, then push to `origin main`. Record the change in
CHANGELOG.md, move verified-solved TODO.md items into CHANGELOG.md, update
PLAN.md, and continue with the next TODO.md item until the list is clear.
`install.vfpy` is shared: keep it byte-identical in every installer repository.

## Agent workflow (Issue 250, 2026-11-10)

- Plan with `superpowers:subagent-driven-development`: one fresh implementer per task, a separate read-only reviewer, then the controller runs the gates and commits.
- Send bulk, well-specified work to Codex via the `codex-delegate` skill (`node ~/.agents/skills/codex-delegate/scripts/relay.mjs --brief BRIEF --cd WORKTREE`, in the background). Use `claude-delegate` or `cursor-delegate` for second opinions or independent lanes. Delegates never commit, push or tag.
- Work in a fresh worktree of `origin/main` on the workspace data volume; never pull, switch or reset the owner checkout. Merge `origin/main` again before pushing, keep both sides' CHANGELOG/PLAN/TODO entries, rerun the full suite, lint and graph change analysis, push through the pre-push hook where one is installed (never force), verify the remote SHA and the CI run where a workflow is configured. Held private Pages operations (workspace D41) stay held.
- Release: tag the next semver above the latest tag and publish a GitHub release. Install released, gated packages into `~/Library/Application Support/FontLab/FontLab 9/` and test live in FontLab 9. This owner route (Issue 250) supersedes, for released packages only, every older line in this guide that forbids installing into the FontLab user folder or its site-packages, owner-managed editable installs, or starting FontLab for a live test (the owner's canonical editable checkouts themselves stay owner-managed): record the previous installed distribution first so it can be restored, and never touch FontLab preferences (owner fonts and documents: see live font editing below); native work goes through the workspace `verification/issue-104/fl-native.sh` gate.
- Documents: CHANGELOG holds verified completed work; TODO only open or to-verify items; PLAN the major remaining changes; WORK.md the current round only (older WORK bytes are archived on the owner's workspace data volume, not public).
- Native defects: issues at github.com/fontlab/fl; fixes as pull requests to fontlab/Proteus, fontlab/FontGate or fontlab/pyfontgate. Never commit to the local C++ snapshot.
- Older "work directly" or "no delegation" lines in this guide are superseded by this section (Issue 250).
- Live font editing (owner, 2026-11-10; workspace D44): test, verify and edit the font open in FontLab 9, and do not stop because the owner might be working in it. Open a VFJ from `~/Desktop` first (those files are for agents), then add glyphs, kerning pairs, elements, contours, masters or whatever the test needs, and save them freely. This supersedes, for live testing, every older line here that forbids mutating owner fonts or documents or requires owned fixtures only. FontLab preferences, Output folders and global update queues stay untouched. Keep the serialized host lock (`fl-native.sh`, one native run at a time; `--mutating` now allows open fonts); do not quit or restart FontLab and do not close fonts from Python, which has crashed the host.
