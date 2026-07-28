from lumbergh.idle_detector import SessionState, classify_overrides

CLAUDE_COMMAND_APPROVAL = """\
● I'll run the tests now.

╭─ Bash command ───────────────────────────────╮
│ pytest -q                                     │
╰───────────────────────────────────────────────╯

Do you want to proceed?
❯ 1. Yes
  2. Yes, and don't ask again for pytest commands
  3. No, and tell Claude what to do differently (esc)
"""

CLAUDE_PLAN_APPROVAL = """\
● Here is my plan:
  1. Add the state
  2. Wire the frontend

Would you like to proceed?
❯ 1. Yes, and auto-accept edits
  2. Yes, and manually approve edits
  3. No, keep planning
"""

CLAUDE_QUESTION_MENU = """\
● Which database should we use?

  Choose an option:
❯ Postgres
  SQLite
  MySQL

(Use arrow keys to navigate · enter to select · esc to cancel)
"""

PI_TRUST_PROMPT = """\
pi wants to run a command:

    rm -rf build/

Do you want to proceed?
❯ 1. Yes
  2. No
"""

CLAUDE_IDLE = """\
● Done — all tests pass.

╭───────────────────────────────────────────────╮
│ >                                               │
╰───────────────────────────────────────────────╯
  ? for shortcuts
"""

CLAUDE_WORKING = """\
● Running the test suite…

⠋ Testing… (12s · esc to interrupt)
"""

MODEL_PICKER = """\
Select model
❯ 1. Claude Opus 4.8
  2. Claude Sonnet 5

enter to select · enter to set as default · esc to cancel
"""

SCROLLBACK_MENTIONS_YES = """\
● I asked whether you approve of the approach and you said yes.
  Now continuing with the implementation.

╭───────────────────────────────────────────────╮
│ >                                               │
╰───────────────────────────────────────────────╯
"""

# The agent is actively WORKING but its streamed output quotes an approval
# prompt (e.g. an agent editing this very detector). The live working spinner
# is the bottom-most chrome, so it is not blocked.
WORKING_QUOTING_APPROVAL = """\
● Here's the detection rule I'm wiring in:

    Do you want to proceed?
    ❯ 1. Yes
      2. No

  Now hooking it into classify_overrides…

✻ Baking… (12s · esc to interrupt)
"""

# The agent is IDLE at its input box; the approval text is up in scrollback and
# the live mode footer (shift+tab to cycle) is the bottom-most chrome.
IDLE_WITH_APPROVAL_IN_SCROLLBACK = """\
● I explained the "Do you want to proceed?" dialog and its
  ❯ 1. Yes / 2. No option block.

──────────────────────────────────────────────
❯
──────────────────────────────────────────────
  ⏵⏵ auto mode on (shift+tab to cycle) · ← 3 agents
"""


def test_command_approval_is_blocked():
    assert classify_overrides(CLAUDE_COMMAND_APPROVAL) == SessionState.BLOCKED


def test_plan_approval_is_blocked():
    assert classify_overrides(CLAUDE_PLAN_APPROVAL) == SessionState.BLOCKED


def test_structured_question_menu_is_blocked():
    assert classify_overrides(CLAUDE_QUESTION_MENU) == SessionState.BLOCKED


def test_pi_trust_prompt_is_blocked():
    assert classify_overrides(PI_TRUST_PROMPT) == SessionState.BLOCKED


def test_idle_pane_is_not_blocked():
    assert classify_overrides(CLAUDE_IDLE) is None


def test_working_pane_is_not_blocked():
    assert classify_overrides(CLAUDE_WORKING) is None


def test_model_picker_is_not_blocked():
    assert classify_overrides(MODEL_PICKER) is None


def test_scrollback_mention_of_yes_is_not_blocked():
    assert classify_overrides(SCROLLBACK_MENTIONS_YES) is None


def test_working_pane_quoting_an_approval_is_not_blocked():
    assert classify_overrides(WORKING_QUOTING_APPROVAL) is None


def test_idle_pane_with_approval_in_scrollback_is_not_blocked():
    assert classify_overrides(IDLE_WITH_APPROVAL_IN_SCROLLBACK) is None
