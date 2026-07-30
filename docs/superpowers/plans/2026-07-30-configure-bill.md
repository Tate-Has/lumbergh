# Configure Bill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the user a Settings UI to configure Bill's coding-agent harness and his personality (two presets plus a custom free-text option), persisted in global settings and applied on next summon.

**Architecture:** A `bill` block in `settings.json` (`harness`, `personality`, `customPersonality`). The `bill` bundle module gains additive custom-text support in its render path; `routers/bill.py` reads the configured harness/personality at summon time instead of hardcoding Pi; `routers/settings.py` gains a validated `BillSettings` field (this is what unblocks saving at all today); the frontend adds a "Bill" tab.

**Tech Stack:** Python 3.11+, FastAPI, pydantic, TinyDB (backend); React + TypeScript + Tailwind (frontend); pytest.

## Global Constraints

- No Co-Authored-By / AI-attribution lines in commits.
- Run `./lint.sh` before finishing; fix all errors.
- Backend tests: `cd backend && uv run pytest`.
- Personality presets live on disk as `backend/lumbergh/bill/personality_<key>.md`; the two today are `professional` and `lumbergh`. The default personality key is `professional` (`bill.DEFAULT_PERSONALITY`). The custom key is the literal string `custom`.
- Provider keys are the keys of `lumbergh.providers.PROVIDERS`: `claude-code`, `cursor`, `opencode`, `gemini-cli`, `aider`, `codex`, `pi`. Bill's default harness is `pi`.
- Custom personality is capped at 4000 characters.

---

### Task 1: Custom-text support in the `bill` bundle

**Files:**
- Modify: `backend/lumbergh/bill/__init__.py`
- Test: `backend/lumbergh/tests/test_bill_bundle.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `bill.CUSTOM_PERSONALITY: str` (== `"custom"`).
  - `bill.available_personalities() -> list[str]` — sorted preset keys discovered on disk.
  - `bill.render(personality: str = DEFAULT_PERSONALITY, custom_text: str | None = None) -> str`.
  - `bill.materialize(personality: str = DEFAULT_PERSONALITY, custom_text: str | None = None, home_dir: Path | None = None) -> Path`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/lumbergh/tests/test_bill_bundle.py`:

```python
def test_available_personalities_lists_the_on_disk_presets():
    assert set(bill.available_personalities()) == {"professional", "lumbergh"}


def test_render_uses_custom_text_when_personality_is_custom():
    body = bill.render("custom", custom_text="You are Bill the pirate. Arrr.")
    assert "{{PERSONALITY}}" not in body
    assert "pirate" in body


def test_render_custom_with_blank_text_falls_back_to_default():
    assert bill.render("custom", custom_text="   ") == bill.render("professional")


def test_materialize_writes_custom_personality(tmp_path):
    home = bill.materialize(
        personality="custom", custom_text="Arr matey.", home_dir=tmp_path / "bill"
    )
    assert "Arr matey." in (home / "AGENTS.md").read_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_bundle.py -k "custom or available_personalities" -v`
Expected: FAIL (`available_personalities` not defined; `render()` takes 1 positional arg).

- [ ] **Step 3: Implement the changes**

In `backend/lumbergh/bill/__init__.py`, replace the block from `DEFAULT_PERSONALITY = "professional"` through the end of `render(...)` with:

```python
DEFAULT_PERSONALITY = "professional"
CUSTOM_PERSONALITY = "custom"


def available_personalities() -> list[str]:
    """The preset personality keys shipped on disk (e.g. ``professional``, ``lumbergh``).

    Discovered from the ``personality_*.md`` files so adding a preset needs no code change
    here or in the settings validator that consumes this.
    """
    return sorted(p.stem.removeprefix("personality_") for p in _SRC.glob("personality_*.md"))


def _personality_body(personality: str, custom_text: str | None = None) -> str:
    if personality == CUSTOM_PERSONALITY:
        body = (custom_text or "").strip()
        if body:
            return body
        personality = DEFAULT_PERSONALITY
    path = _SRC / f"personality_{personality}.md"
    if not path.is_file():
        path = _SRC / f"personality_{DEFAULT_PERSONALITY}.md"
    return path.read_text().strip()


def render(personality: str = DEFAULT_PERSONALITY, custom_text: str | None = None) -> str:
    template = (_SRC / "AGENTS.md.template").read_text()
    return template.replace("{{PERSONALITY}}", _personality_body(personality, custom_text))
```

Then change the `materialize` signature and its `AGENTS.md` write:

```python
def materialize(
    personality: str = DEFAULT_PERSONALITY,
    custom_text: str | None = None,
    home_dir: Path | None = None,
) -> Path:
```

and inside it:

```python
    (target / "AGENTS.md").write_text(render(personality, custom_text))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_bundle.py -v`
Expected: PASS (all tests, including the pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/bill/__init__.py backend/lumbergh/tests/test_bill_bundle.py
git commit -m "feat(bill): custom personality text in the instruction bundle"
```

---

### Task 2: `BillSettings` model + validation in the settings router

**Files:**
- Modify: `backend/lumbergh/routers/settings.py`
- Test: `backend/lumbergh/tests/test_settings_bill.py` (create)

**Interfaces:**
- Consumes: `bill.available_personalities()`, `bill.CUSTOM_PERSONALITY` (Task 1); `lumbergh.providers.PROVIDERS`.
- Produces:
  - `settings.BillSettings` pydantic model (`personality`, `customPersonality`, `harness`, all `str | None = None`).
  - `SettingsUpdate.bill: BillSettings | None`.
  - `_validate_updates` emits `update_data["bill"]` as a dict of only the provided fields.
  - `_get_defaults()["bill"] == {"harness": "pi", "personality": "professional", "customPersonality": ""}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_settings_bill.py`:

```python
import pytest
from fastapi import HTTPException

from lumbergh.routers.settings import (
    BillSettings,
    SettingsUpdate,
    _get_defaults,
    _validate_updates,
)


def test_defaults_include_a_full_bill_block():
    b = _get_defaults()["bill"]
    assert b == {"harness": "pi", "personality": "professional", "customPersonality": ""}


def test_preset_personality_passes_through():
    data = _validate_updates(SettingsUpdate(bill=BillSettings(personality="lumbergh")))
    assert data["bill"] == {"personality": "lumbergh"}


def test_custom_personality_and_harness_pass_through():
    data = _validate_updates(
        SettingsUpdate(
            bill=BillSettings(personality="custom", customPersonality="arr", harness="claude-code")
        )
    )
    assert data["bill"] == {
        "personality": "custom",
        "customPersonality": "arr",
        "harness": "claude-code",
    }


def test_unknown_personality_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(SettingsUpdate(bill=BillSettings(personality="pirate")))


def test_unknown_harness_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(SettingsUpdate(bill=BillSettings(harness="nope")))


def test_overlong_custom_personality_is_rejected():
    with pytest.raises(HTTPException):
        _validate_updates(
            SettingsUpdate(bill=BillSettings(personality="custom", customPersonality="x" * 4001))
        )


def test_absent_bill_is_not_written():
    data = _validate_updates(SettingsUpdate(showSessionDots=False))
    assert "bill" not in data
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_settings_bill.py -v`
Expected: FAIL (`BillSettings` does not exist; `SettingsUpdate` has no `bill`).

- [ ] **Step 3: Implement the changes**

In `backend/lumbergh/routers/settings.py`:

Add a top-level import beside the existing provider import:

```python
from lumbergh import bill as bill_bundle
```

In `_get_defaults()`, replace the `"bill"` entry with:

```python
        "bill": {"harness": "pi", "personality": "professional", "customPersonality": ""},
```

Add the model (near `AISettings`):

```python
class BillSettings(BaseModel):
    personality: str | None = None
    customPersonality: str | None = None  # noqa: N815 - API field name
    harness: str | None = None
```

Add the field to `SettingsUpdate` (alongside the other optional fields):

```python
    bill: BillSettings | None = None
```

Add a module constant and a validator helper (near `_serialize_ai_update`):

```python
_MAX_CUSTOM_PERSONALITY = 4000


def _validate_bill_update(bill: BillSettings) -> dict:
    """Extract the provided Bill fields, rejecting an unknown personality/harness or
    an over-long custom personality. Only set fields are returned, so a partial update
    deep-merges cleanly over the stored block."""
    data = bill.model_dump(exclude_none=True)

    if "personality" in data:
        valid = set(bill_bundle.available_personalities()) | {bill_bundle.CUSTOM_PERSONALITY}
        if data["personality"] not in valid:
            raise HTTPException(
                status_code=400, detail=f"Unknown personality: {data['personality']}"
            )

    if "harness" in data and data["harness"] not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown agent provider: {data['harness']}")

    if "customPersonality" in data and len(data["customPersonality"]) > _MAX_CUSTOM_PERSONALITY:
        raise HTTPException(
            status_code=400,
            detail=f"Custom personality must be at most {_MAX_CUSTOM_PERSONALITY} characters",
        )

    return data
```

In `_validate_updates`, before the final `return update_data`, add:

```python
    if updates.bill is not None:
        update_data["bill"] = _validate_bill_update(updates.bill)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_settings_bill.py lumbergh/tests/test_settings_question_detection.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/settings.py backend/lumbergh/tests/test_settings_bill.py
git commit -m "feat(settings): validated bill config block (harness + personality)"
```

---

### Task 3: Summon reads the configured harness + personality

**Files:**
- Modify: `backend/lumbergh/routers/bill.py`
- Test: `backend/lumbergh/tests/test_bill_router.py`

**Interfaces:**
- Consumes: `bill.materialize(personality, custom_text)` (Task 1); `settings["bill"]` shape (Task 2); `get_launch_command`.
- Produces:
  - `_harness() -> str` — configured harness or `BILL_PROVIDER`.
  - `_personality() -> tuple[str, str | None]` — `(personality_key, custom_text)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/lumbergh/tests/test_bill_router.py`:

```python
def test_summon_uses_the_configured_harness(client, tmp_path, monkeypatch):
    spawned = {}
    stored = {}
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        bill,
        "create_tmux_session",
        lambda name, workdir, launch_command=None, **kw: spawned.update(  # noqa: ARG005
            launch_command=launch_command
        ),
    )
    monkeypatch.setattr(bill, "_store_session", lambda **kw: stored.update(kw))
    monkeypatch.setattr(bill, "_settings", lambda: {"bill": {"harness": "claude-code"}})

    client.post("/api/bill/summon")
    assert "claude" in spawned["launch_command"]
    assert stored["agent_provider"] == "claude-code"


def test_summon_renders_a_custom_personality(client, tmp_path, monkeypatch):
    monkeypatch.setattr("lumbergh.routers.sessions.get_live_sessions", dict)
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(
        bill,
        "_settings",
        lambda: {"bill": {"personality": "custom", "customPersonality": "You are Bill the pirate."}},
    )

    client.post("/api/bill/summon")
    assert "pirate" in (tmp_path / "bill" / "AGENTS.md").read_text()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -k "configured_harness or custom_personality" -v`
Expected: FAIL (harness still hardcoded to `pi`; custom text not passed to `materialize`).

- [ ] **Step 3: Implement the changes**

In `backend/lumbergh/routers/bill.py`, replace the existing `_personality` helper:

```python
def _personality() -> tuple[str, str | None]:
    b = _settings().get("bill", {}) or {}
    return b.get("personality") or bill_bundle.DEFAULT_PERSONALITY, b.get("customPersonality")


def _harness() -> str:
    return (_settings().get("bill", {}) or {}).get("harness") or BILL_PROVIDER
```

In `summon()`, replace the materialize line:

```python
    personality, custom_text = _personality()
    workdir = bill_bundle.materialize(personality, custom_text)
```

Replace the launch-command + binary-check block so it uses the configured harness:

```python
    from lumbergh.providers import get_launch_command

    harness = _harness()
    launch_command = get_launch_command(harness, _settings().get("defaultAgent"))

    binary = _harness_binary(launch_command)
    if binary and shutil.which(binary) is None:
        raise _fail(
            "harness",
            f"the `{harness}` harness binary `{binary}` is not installed",
            f"install `{binary}`, then summon Bill again",
            workdir=str(workdir),
        )
```

In the `_store_session(...)` call inside `summon()`, change the provider field:

```python
            agent_provider=harness,
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS (including the pre-existing `test_summon_refuses_when_the_harness_binary_is_missing`, which still finds `pi` in the message via the default harness).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): summon honors the configured harness and personality"
```

---

### Task 4: Frontend "Bill" settings tab

**Files:**
- Create: `frontend/src/components/BillSettings.tsx`
- Modify: `frontend/src/components/SettingsModal.tsx`

**Interfaces:**
- Consumes: GET `/api/settings` returns `bill: { harness, personality, customPersonality }` and `agentProviders`; PATCH accepts a `bill` object (Task 2).
- Produces: a new `BillSettings` React component and modal wiring.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/BillSettings.tsx`:

```tsx
interface Props {
  harness: string
  onHarnessChange: (value: string) => void
  agentProviders: Record<string, { label: string }>
  personality: string
  onPersonalityChange: (value: string) => void
  customPersonality: string
  onCustomPersonalityChange: (value: string) => void
}

const PRESETS: { id: string; label: string; description: string }[] = [
  {
    id: 'professional',
    label: 'Professional',
    description: 'Direct, brief, factual. Leads with outcomes and never pads a report.',
  },
  {
    id: 'lumbergh',
    label: 'Bill Lumbergh',
    description: 'The bit — "if you could go ahead and…". A light garnish over real reports.',
  },
  {
    id: 'custom',
    label: 'Custom',
    description: 'Write your own personality preamble.',
  },
]

export default function BillSettings({
  harness,
  onHarnessChange,
  agentProviders,
  personality,
  onPersonalityChange,
  customPersonality,
  onCustomPersonalityChange,
}: Props) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm text-text-tertiary mb-1">Harness</label>
        <select
          value={harness}
          onChange={(e) => onHarnessChange(e.target.value)}
          className="w-full px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50 text-sm"
        >
          {Object.entries(agentProviders).map(([key, provider]) => (
            <option key={key} value={key}>
              {provider.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-text-muted mt-1">The coding agent Bill runs as.</p>
      </div>

      <div>
        <label className="block text-sm text-text-tertiary mb-2">Personality</label>
        <div className="space-y-2">
          {PRESETS.map((preset) => (
            <label
              key={preset.id}
              className="flex items-start gap-2 text-sm cursor-pointer"
            >
              <input
                type="radio"
                name="bill-personality"
                value={preset.id}
                checked={personality === preset.id}
                onChange={() => onPersonalityChange(preset.id)}
                className="mt-1"
              />
              <span>
                <span className="text-text-secondary">{preset.label}</span>
                <span className="block text-xs text-text-muted">{preset.description}</span>
              </span>
            </label>
          ))}
        </div>
        {personality === 'custom' && (
          <textarea
            value={customPersonality}
            onChange={(e) => onCustomPersonalityChange(e.target.value)}
            rows={5}
            maxLength={4000}
            placeholder="You are Bill, the user's engineering manager. …&#10;&#10;This voice is for you and no one else — it never reaches a worker or a tool."
            className="w-full mt-2 px-3 py-2 bg-input-bg text-text-primary rounded-[var(--radius-lg)] border border-input-border focus:outline-none focus:border-action/50 text-sm font-mono"
          />
        )}
      </div>

      <p className="text-xs text-text-muted">Changes apply the next time Bill is summoned.</p>
    </div>
  )
}
```

- [ ] **Step 2: Wire it into the modal**

In `frontend/src/components/SettingsModal.tsx`:

Add the import near the other tab imports:

```tsx
import BillSettings from './BillSettings'
```

Extend the `Settings` interface:

```tsx
  bill?: { harness?: string; personality?: string; customPersonality?: string }
```

Change the `TabId` type:

```tsx
type TabId = 'general' | 'bill' | 'ai' | 'cloud' | 'security'
```

Add state (near `defaultAgent`):

```tsx
  const [billHarness, setBillHarness] = useState('pi')
  const [billPersonality, setBillPersonality] = useState('professional')
  const [billCustomPersonality, setBillCustomPersonality] = useState('')
```

In `fetchSettings`, after the `agentProviders` line, load the bill block:

```tsx
      if (data.bill?.harness) setBillHarness(data.bill.harness)
      if (data.bill?.personality) setBillPersonality(data.bill.personality)
      if (data.bill?.customPersonality != null)
        setBillCustomPersonality(data.bill.customPersonality)
```

In `handleSubmit`, add to the payload (near `payload.defaultAgent`):

```tsx
      payload.bill = {
        harness: billHarness,
        personality: billPersonality,
        customPersonality: billCustomPersonality,
      }
```

Add the tab to the `tabs` array (after `general`):

```tsx
    { id: 'bill', label: 'Bill' },
```

Add the tab body (after the `general` block):

```tsx
            {activeTab === 'bill' && (
              <BillSettings
                harness={billHarness}
                onHarnessChange={setBillHarness}
                agentProviders={agentProviders}
                personality={billPersonality}
                onPersonalityChange={setBillPersonality}
                customPersonality={billCustomPersonality}
                onCustomPersonalityChange={setBillCustomPersonality}
              />
            )}
```

- [ ] **Step 3: Typecheck / build the frontend**

Run: `cd frontend && npm run build`
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/BillSettings.tsx frontend/src/components/SettingsModal.tsx
git commit -m "feat(bill): Settings tab for Bill's harness and personality"
```

---

### Task 5: Lint, full suite, manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Lint**

Run: `./lint.sh`
Expected: exits 0 (auto-fixes applied and staged as needed).

- [ ] **Step 2: Full backend suite**

Run: `cd backend && uv run pytest`
Expected: PASS.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Start the app (`./bootstrap.sh` or the two `start.sh` scripts), open Settings → **Bill**, set harness to Claude Code and personality to Custom with a short preamble, Save. Confirm `~/.config/lumbergh/settings.json` shows the `bill` block. Summon Bill and confirm `~/.config/lumbergh/bill/AGENTS.md` begins with your custom text and his session launches the chosen harness.

- [ ] **Step 4: Commit any lint fixups**

```bash
git add -A
git commit -m "chore(bill): lint fixups for Bill config" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage:**
- Data model (`bill` block) → Tasks 2 (defaults + validation), 3 (read), 4 (write).
- `bill/__init__.py` additive custom support → Task 1.
- `routers/bill.py` harness/personality/stored-provider → Task 3.
- `routers/settings.py` `BillSettings` + validation → Task 2.
- Frontend Bill tab (harness select, personality presets + custom textarea, apply-on-summon note) → Task 4.
- Testing (bundle, settings, router) → Tasks 1–3; full suite + lint → Task 5.
- Out-of-scope items (restart plumbing, per-project config, nudge tuning, preset text to frontend) → not implemented, matching the spec.

**Placeholder scan:** none — every step has concrete code or an exact command.

**Type consistency:** `render`/`materialize` custom_text param, `available_personalities`, `CUSTOM_PERSONALITY`, `BillSettings` field names (`personality`/`customPersonality`/`harness`), and the `bill` payload/`Settings` interface shape all match across Tasks 1–4.
