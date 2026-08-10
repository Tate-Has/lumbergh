# Artifact read paths — a remote Bill can read back what it dispatched

Item 1 of `lumbergh-changes-for-hermes.md`, the blocking one.

## The problem

Hermes holds the Bill role from `hermesbox` and reaches Lumbergh only over HTTP.
`85c4070` gave it `lb brief write` and `lb prefs read/add`, so it can file a brief and
spawn a worker. It cannot read anything back. The loop is one-way: it asks for work and
never learns what came of it.

Two things are missing, and they are different in kind:

1. **No read verbs.** `lb brief write` landed without its `read`/`list` half, and reports
   have neither. A fleet row carries only slug, kind, state and outcome.
2. **No machine-readable shape.** A scout's deliverable is prose, and its `DELIVERED:`
   line is prose about where that prose is. Nothing in either can be acted on
   programmatically.

`lb brief read` matters more than it looks. A babysat session is `/clear`ed every refresh
cycle, and Hermes runs a fresh session per wake on purpose — a transcript is history, not
now. Both mean intent has to be re-readable rather than remembered.

## What already works

The report *path* is already contracted, contrary to the brief's framing:
`_brief_delivery` (`routers/bill.py:757`) tells every scout to write
`~/.config/lumbergh/bill/reports/<name>.md`, where `<name>` is the task name. What is
uncontracted is the `DELIVERED:` line and the report's internal shape.

## Design

### `lumbergh/bill/artifacts.py`

One new module holding the frontmatter shape and the reads over `briefs/` and `reports/`.
It sits beside `bill/__init__.py` — which stays the bundle/materialize module — for the
same reason `SLUG` lives there: both sides of the protocol need it, and the server's jail
and the client's check must never disagree about what they are.

```python
CONFIDENCE = ("high", "medium", "low")

def validate(actionable, done_when, confidence) -> str | None   # error text, or None
def render_frontmatter(actionable, done_when, open_questions, confidence) -> str
def parse(text) -> tuple[dict, str]                              # (frontmatter, body)
def write_report(name, body, ...) -> Path
def listing(kind) -> list[dict]                                  # "briefs" | "reports"
def read_artifact(kind, name) -> dict | None
```

The backend has no YAML dependency and does not gain one for four known keys.
`render_frontmatter` emits a fixed block; `parse` reads only `actionable`, `done_when`,
`open_questions` and `confidence` from between the first two `---` lines, ignores anything
else, and returns `({}, whole_text)` for a file with no block. A hand-written report still
reads — it just reports nothing structured.

### Frontmatter

```yaml
---
actionable: true
done_when: retry shim removed, suite green 10x
open_questions:
  - which env does CI use?
confidence: high
---
```

Field rules, enforced at write time:

| field | rule |
| --- | --- |
| `actionable` | bool, required |
| `confidence` | required, one of `high` / `medium` / `low` |
| `done_when` | required when `actionable` is true; optional otherwise |
| `open_questions` | optional, defaults to `[]` |

`done_when` is conditional because a "nothing to do here" report has no done-when, and a
required field that must be invented is a field that lies.

`open_questions` is the field that closes the user's feedback loop. A scout that has read
the code knows precisely which detail was missing; that list becomes the clarifying
question Hermes asks the user, instead of Hermes guessing what to ask. The skill says so
explicitly, because the difference between a specific unanswerable question and a vague
one is the whole value of the field.

### Enforcement: `lb report write`

Nothing validates a file a scout writes with its own file tools. So the scout files its
report *through* the CLI, and the server renders the frontmatter block — the same
reasoning as `POST /api/bill/preferences`, which stamps the date and formats the bullet
rather than trusting a caller that `AGENTS.md` merely asks to format it. The shape then
holds however weak the model driving it is, and a scout that is not on this host works
unchanged.

### Endpoints — all on `/api/bill`

| route | purpose |
| --- | --- |
| `POST /report` | `{name, body, actionable, done_when, open_questions, confidence}` → validate, render, write `reports/<slug>.md`. Returns `{path, name, bytes}`. |
| `GET /report?name=` | `{name, path, exists, frontmatter, body}` |
| `GET /reports` | `{reports: [{name, path, bytes, modified, actionable, confidence, open_questions}]}` |
| `GET /brief?name=` | `{name, path, exists, body}` |
| `GET /briefs` | `{briefs: [{name, path, bytes, modified}]}` |

Same slug jail and the same `_fail(stage, error, help)` shape as `POST /brief`. `GET
/brief` co-exists with the existing `POST /brief` on one path. A report body that already
opens with `---` is refused at `stage: "body"` rather than double-wrapped.

`GET /reports` carries the frontmatter fields, not just names: it lets a remote Bill
triage the whole directory in one call and fetch only the bodies that matter.

### CLI

```
lb report write --name <slug> [--file <path>|-] --actionable yes|no
                [--done-when "<text>"] [--open-question "<q>"]... --confidence high|medium|low
lb report read <slug> [--json]
lb report list [--json]
lb brief read <slug> [--json]
lb brief list [--json]
```

`--open-question` is repeatable through the parser's existing `_REPEATABLE_FLAGS`. The
body comes from `--file` or stdin, reusing `brief.py`'s `_body_from` — lifted to a shared
helper, since it is the same logic and a tty on stdin has to be refused the same way.
`--actionable` and `--confidence` are checked client-side against the same constants the
server uses, so a typo costs no round trip and the two can never disagree.

`--json` on the read verbs prints `{"frontmatter": {...}, "body": "..."}`. Without it,
`render_object` for the frontmatter and `render_block` for the prose, matching `lb prefs
read`.

### What the scout is told

`_brief_delivery` stops naming a path and names the command:

> Write your report with `lb report write --name <name> --actionable yes|no --done-when
> "…" --confidence high|medium|low` (add `--open-question "…"` for each detail you needed
> and could not determine), body on stdin. Finish with exactly one line:
> `DELIVERED: report <name>` or `FAILED: <reason>`.

`scout/SKILL.md` gains a matching **Report** section explaining what each field means.

The `report ` prefix on the `DELIVERED:` line is what makes the outcome column
self-describing: a bare slug is ambiguous against `ship`'s `DELIVERED: <sha>` /
`<pr-url>` in the same column, and a path is meaningless to a Bill that cannot open it.

The path drops out of the contract entirely. The scout never writes one; Hermes never
learns one.

## Testing

Red-green, mirroring `test_bill_router.py` and `test_lb_brief_cli.py`:

- `artifacts`: render → parse round-trip, the no-frontmatter fallback, `validate`'s
  conditional `done_when` rule and the `confidence` enum.
- router: write/read/list for both kinds, the slug jail, the `---`-in-body refusal, and a
  missing artifact returning `exists: false` rather than a 404.
- CLI: the flag surface, `--json` output, exit 2 on a bad `--confidence`, and the stdin
  body path.

## Out of scope

Items 2 (agent token coverage of `/api/bill`) and 3 (context on the fleet row) of
`lumbergh-changes-for-hermes.md`. Item 2 needs a decision on approach before it is
written.
