---
name: dinorefurb-work-protocol
description: Carry out evidence-based game restoration under the Refurbished Dinosaurs work protocol, including research, clean-room implementation, project tracking, headless original-game probes, and upstream defect reporting. Use in restorations following dinorefurb.com standards or when explicitly requested.
---

# Refurbished Dinosaurs work protocol

Follow the [work protocol](https://dinorefurb.com/work-protocol/), its methodology and documentation standard. This skill guides execution; the protocol defines the detailed rules. Respect the user's task scope and repository instructions, including stricter restrictions on running originals or publishing changes.

## Read the project before choosing work

Read `AGENTS.md`, the applicable repository skills, the session's handover, current plan/stage, runtime capabilities and relevant specification entries. For a goal, read its condition, claimed areas, exclusions and handover. Check the branch and working tree and run the repository's documentation check.

Use the repository's pinned copies in `docs/upstream/` for the protocol, methodology and documentation standard. Follow section links and read only the relevant sections; do not reread sections already loaded. Assume the pinned copies are current; do not refresh them from the website during ordinary work. If absent, obtain the authoritative documents and record their provenance before relying on details. The protocol prevails over an inconsistent template or procedure skill; report the inconsistency upstream.

Keep sessions on one side of the clean room:

- Research reads the original and records independently worded findings in the spec. Research tooling may read the original.
- Implementation works from spec entries alone. Do not open decompiler listings, debugger logs, research notes, the research queue or research-goal files. Use a fresh session when moving from research to implementation; do not carry original-code knowledge into implementation.
- A tooling batch supports the session's side. Each batch is research, implementation or tooling, never a mixture.

## Stages and working records

Work through Intake, Runtime access, Survey, Slices and Audit. Use the full protocol's exit criteria, not an informal completion estimate. Later work can start early but cannot close its stage before earlier stages close.

- Intake identifies eligibility, owned editions, latest official patch, analysis build/manifest and sources.
- Runtime access tests actual capabilities per build and per part: launch/state setup, keyboard, mouse, memory/breakpoints, patched saves, frames, sound, recordings and isolated emulated calls. Record tools, versions, attempts and limits in `docs/RUNTIME.md`; do not infer one capability from another.
- Survey accounts for the whole installation and media, manifests and formats, known screens/rules, function inventories and area queues before deep subsystem work.
- Slices deliver playable vertical increments with reachable parity targets. The first provides a fixture-driven headless rebuild runner.
- Audit accounts for functions, parity gaps, remaining queue items and reports according to the protocol.

Keep findings in `spec/` first. Working records point to those findings and describe current work, rather than duplicating findings or history:

| Record | Purpose |
| --- | --- |
| `docs/IMPLEMENTATION-PLAN.md` | Scope, stage, ordered slices/exit criteria, risks and owner questions |
| `queue/AREA.md` | Open research questions grouped by Static, Emulated call, Agent run, Live session, Source, Blocked |
| `docs/RUNTIME.md` | Validated capabilities, exact commands, retained paths, versions and limits |
| `docs/live-sessions/NAME.md` | Open requests with status, queue items, duration and script; delete after evidence is recorded |
| `docs/reports/R-NNN.md` | Untriaged testing reports or reports waiting for missing information |
| `docs/HANDOVER.md` | Current gate, unfinished work, blockers and next IDs outside a goal; at most 200 lines |
| `docs/goals/NAME.md` | Goal condition, side, claimed areas, exclusions, dead ends and its own current handover |
| `docs/DECISIONS.md`, `deviations/` | Owner decisions and departures from the original |

Keep files within the protocol's 1,000-line limit and use its prescribed split/archive conventions. Record local tool paths and pitfalls in `docs/GHIDRA.md` or `docs/DEVELOPMENT.md`.

## Execute bounded, evidence-driven batches

Choose work using the protocol's Order of work and the current slice/goal. A queue item asks one independently answerable question, cites entries, defines what settles it and names the blocked slice or `none`. Create an `unknown` entry before queuing behavior with no entry. Allocate stable IDs from `Next ID:`; never reuse them. Record failed attempts under `Tried:` with finding IDs, and blockers under `Waiting on:`. Retry with new evidence or a changed approach. Close an item by recording its answer in the spec and deleting it in the same batch.

For research, state competing readings and seek evidence that could rule each out. Preserve unresolved alternatives and what would disprove them. Prefer static executable/data analysis, then isolated emulated calls, before full-game runs. A complete static reading can establish code-decided behavior without a full-game run. Partial readings remain supported with explicit remaining questions. Timing, OS, interrupts and hardware effects need appropriate runtime evidence. Apply the documentation standard's exact status rules.

For implementation, build only what the spec says. A missing answer becomes an Open question or an `unknown` entry, a partial parity row and a `Spec gap:` note; a placeholder cites its entry. Do not invent behavior. Put decisions in the rules layer over serializable state and inputs, with presentation consuming those decisions. Test every documented branch and relevant arithmetic widths, intermediate/shared state, continuation, save/restore and replay behavior. Synthetic spec tests do not constitute original-game evidence or validate parity. Production code cites the rules, formats, screens and bugs it implements, rather than findings or experiments. Follow the full implementation section for citation repair and superseded entries.

Keep spec confidence, implementation completeness and parity validation separate. Validate parity only with qualifying original evidence or original files as the standard permits. Report mapping coverage, citation coverage and complete readings separately, with inventory revision, function counts/body bytes and unresolved denominator gaps.

Each finished batch is reviewable in one sitting and ends in one commit or repository-prescribed pull request, with documentation and fast gates passing. Use `Spec:` for affected entries, `Parity:` for changed parity statuses, and `Queue:` only for closed items. Regenerate `PARITY.md` and `spec/index/` after merging their inputs instead of resolving generated conflicts manually; respect repositories that generate only on main.

## Original-game probes with rust-dos

Use **rust-dos for headless debugging against the original games**. Follow the probe approach in [template PR #116](https://github.com/kibertoad/refurbished-dinosaurs-template/pull/116), especially the project's `docs/WINDOWS-PROBES.md`, `docs/ANALYSIS-OUTPUTS.md` and runtime-access procedure. Consult the actual pinned emulator/session API before adapting commands. The PR's tested baseline was rust-dos 1.7.2 and `dinorefurb-dosbox-session` 0.9.0; record versions validated for this project rather than treating that baseline as permanently current.

Full-game runs still require a prior recorded static attempt for the question, except initial runtime-capability discovery. A headless emulator does not exempt a full-game run from ownership and locking rules. Respect standing owner authorization already recorded for validated probes; do not ask again for each probe within that scope.

1. Preserve owner-supplied originals. Prepare isolated ignored copies, apply the official patch and reconcile runtime executable hashes/lengths with the analysis build and actual Ghidra import bytes. Retain an immutable patched seed, writable working image and configuration/hash manifest. Derive hardware and disk geometry from this setup; mount media read-only.
2. Acquire the machine-wide run lock by exclusive creation, using the project/session lock helper. Default paths are `C:\ProgramData\refurbished-dinosaurs\run.lock` and `/var/tmp/refurbished-dinosaurs/run.lock`, overridden consistently by `REFURBISHED_DINOSAURS_RUN_LOCK`. Record repository/session and process identities. If held, choose work needing no run. Never casually remove another session's lock; follow the full protocol's abandoned-lock procedure if applicable.
3. Launch an owned hidden process/job, headless and muted, with a localhost debugger on an ephemeral port and deterministic fixed-cycle execution. Verify the binary digest and server capabilities. Version the actual preparation/probe scripts and record commands, environment, configuration and request/reply journals. For booted Windows, use an appropriate runner with boot/state gates; do not feed a Windows EXE to a DOS readiness-marker target or monkeypatch installed tooling.
4. Resume once, retain the returned operation ID and observe that same operation until stopped or the bounded observation budget fails. Do not issue a second resume because a request times out. Gate actions on an actual state or native breakpoint, not arbitrary sleeps or elapsed emulated time alone.
5. Validate input delivery. Windows guests need PS/2 relative mouse movement; test movement, buttons and keyboard separately. For PE addresses use linear addressing and pagewalk in the stopped CR3; verify resident pages, split reads at boundaries and account for loader changes. Unmapped/cold memory alone does not show a fingerprint mismatch.
6. Watch/write only addresses supported by format fields or evidenced glossary meanings. Writes require a paused/quiescent state, state-sequence guard, expected old bytes and readback. Record each setup write.
7. Save after queued input is delivered. Retain checkpoint state, all boot-disk sidecars, hashes, media/hardware paths and expected stop/frame. Validate same-process and second-process restores with strict matching/file checks, restored instruction/time/state/frame and deliberate hardware-mismatch refusal.
8. Validate actual game launch, each input device, memory reads, breakpoints, frames and restore independently. Repeat bounded actions from the same checkpoint. Menu access does not prove gameplay; frames do not prove sound; checkpoints are not patched native saves. Record each capability and its limits in `docs/RUNTIME.md`.
9. In `finally`, export evidence, request graceful quit, wait, stop only this runner's child if needed, close its job and release only its acquired lock. Outside an authorized live session, never attach to, control or stop another process.

Research probes record gameplay RNG seeds and every draw by rule ID, bound and result, enabling rebuild replay and first-divergence checks. A deterministic checkpoint alone is not the protocol's RNG trace or parity comparison. Keep original memory/code/media local and ignored; committed fixtures use neutral format field paths/glossary names and rule IDs, without original addresses or bytes. Follow Recorded runs for repeatability, multiple seeds and divergence investigations.

Isolated function calls use the protocol's Unicorn harness in `tools/emu/`, not a full-game rust-dos run. They need no game run lock. Check input hashes, real relocations/import mappings and explicit stubs; unknown services/ports fail closed. Cover branches and numeric edges, record assumptions and do not claim hardware/timing effects from CPU-only tests.

## Retain evidence and finish sessions

Put bounded headless output in dedicated ignored per-run directories with provenance, ownership, active markers and reproduction metadata. Review success/failure markers; record findings and regeneration instructions durably and commit them before deleting consumed output. Preserve originals, canonical analysis projects, current validated checkpoints with sidecars, durable captures and unresolved evidence. Delete only reviewed owned targets after absolute-path/child-root and link/junction checks. Never recursively clear mixed analysis, game, artifact or temp roots or delete by age/extension alone.

At session end, finish the required gates, stop owned processes, release owned locks and rewrite the appropriate current handover. Preserve unfinished work explicitly; do not hide it in a passing batch. Follow goal claim/branch coordination and stop rules when an explicitly requested long-running goal is active; do not start goals or agents merely because this skill is loaded. Honor the session's push/PR authorization and repository policy.

## Report shared defects upstream

**Every identified gap or bug in shared tooling, the documentation standard, the work protocol or general project setup must be reported as a GitHub issue.** A local workaround, queue item or handover note does not replace the upstream report. This skill authorizes filing those scoped defect reports when invoked; it does not authorize unrelated messages or changes.

| Defect belongs to | Issue destination |
| --- | --- |
| Work protocol, methodology, documentation standard, or their published guidance | [refurbished-dinosaurs](https://github.com/kibertoad/refurbished-dinosaurs/issues) |
| Shared toolkit commands, validators, libraries or tooling behavior | [refurbished-dinosaurs-toolkit](https://github.com/kibertoad/refurbished-dinosaurs-toolkit/issues) |
| General project setup, scaffold/configuration, bootstrap or template procedures rather than shared tooling | [refurbished-dinosaurs-template](https://github.com/kibertoad/refurbished-dinosaurs-template/issues) |
| Emulation behavior or debugger/emulator defects discovered while using rust-dos | [kibertoad/rust-dos](https://github.com/kibertoad/rust-dos/issues) |

Check existing issues to avoid duplicates; link an existing matching issue and add new evidence where appropriate. Report observed versus expected behavior, minimal reproduction, versions/build fingerprints, affected commands or document sections, consequences and any workaround. Distinguish suspected emulator defects from confirmed causes. Exclude copyrighted original bytes, media, credentials and private paths; provide scripts, neutral observations and hashes instead. Cross-link reports only when separate components have distinct actionable defects.

File through an available authenticated GitHub tool or CLI and record the issue URL in the relevant local record. If authentication, network or permissions prevent filing, prepare a complete issue draft, retain the destination and blocker, and explicitly tell the user it remains unfiled. Never claim a draft was reported.
