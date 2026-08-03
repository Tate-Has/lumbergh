"""The spawn → worker brief handoff must be honest: deliver only once the worker
can actually receive the brief, and report success only once it starts on it.

The bug these guard against: a fresh worktree launch shows Claude Code's folder-trust
dialog and takes seconds to boot, so typing the brief immediately drops it into the
booting shell or the trust dialog, yet ``send-keys`` succeeds and spawn reports a
false success. The worker then sits idle forever.
"""

from lumbergh.spawn_delivery import deliver_when_ready

TRUST = """\
 Quick safety check: Is this a project you
 created or one you trust?

 ❯ 1. Yes, I trust this folder
   2. No, exit

 Enter to confirm · Esc to cancel
"""

BOOTING = "Accessing workspace…\n⠋ starting up"

READY = """\
╭───────────────────────────────────────────────╮
│ >                                               │
╰───────────────────────────────────────────────╯
  ? for shortcuts · ⏵⏵ auto mode on
"""


def working(seconds: int) -> str:
    """A working pane animates — the elapsed timer ticks every second."""
    return f"● Reading your brief…\n\n⠋ Working… ({seconds}s · esc to interrupt)\n"


WORKING = [working(s) for s in (1, 2, 3)]

# The #848 failure: the brief landed in the input box and was never submitted. The
# pane changed (the text is on screen) but nothing is running — frozen, 0k context.
PENDING = """\
╭───────────────────────────────────────────────╮
│ > BRIEF                                         │
╰───────────────────────────────────────────────╯
  ? for shortcuts · ⏵⏵ auto mode on      0k (0%)
"""

STARTED = """\
> BRIEF

● Reading your brief…                     12k (6%)
"""

SHELL = "user@host:~/app-worktrees/fix$ "


class Fake:
    """A scripted pane: yields queued snapshots, then repeats the last one.

    ``clock`` only advances when ``sleep`` is called, so timeouts are deterministic.
    """

    def __init__(self, panes, on_enter=None):
        self._panes = list(panes)
        # What the pane becomes once something presses Enter — a pending brief being
        # submitted, which is exactly what the manual recovery for #848 does.
        self.on_enter = list(on_enter) if on_enter else None
        self.sent: list[str] = []
        self.keys: list[str] = []
        # Every tmux ref the delivery addressed, so a brief typed at the wrong window
        # is a test failure rather than a surprise in production.
        self.refs: list[str] = []
        self.t = 0.0

    def capture(self, name):
        self.refs.append(name)
        return self._panes.pop(0) if len(self._panes) > 1 else self._panes[0]

    def send(self, name, text):
        self.refs.append(name)
        self.sent.append(text)
        return True

    def press(self, name, key="Enter"):
        self.refs.append(name)
        self.keys.append(key)
        if self.on_enter is not None:
            self._panes = list(self.on_enter)
            self.on_enter = None
        return True

    def sleep(self, seconds):
        self.t += seconds

    def clock(self):
        return self.t

    def run(self, **kw):
        return deliver_when_ready(
            "w",
            "BRIEF",
            capture=self.capture,
            send=self.send,
            press=self.press,
            sleep=self.sleep,
            clock=self.clock,
            **kw,
        )


def test_happy_path_delivers_once_ready_and_confirms_working():
    fake = Fake([BOOTING, READY, READY, *WORKING])
    result = fake.run()
    assert result.delivered is True
    assert fake.sent == ["BRIEF"]
    assert fake.keys == []  # no trust dialog, no nudges


def test_a_context_readout_above_zero_confirms_on_its_own():
    # A worker that answers fast leaves a frozen pane; its context is the proof.
    fake = Fake([BOOTING, READY, READY, STARTED])
    result = fake.run()
    assert result.delivered is True
    assert fake.keys == []


def test_answers_folder_trust_dialog_before_delivering():
    fake = Fake([TRUST, TRUST, READY, READY, *WORKING])
    result = fake.run()
    assert result.delivered is True
    assert fake.keys == ["Enter"]  # trust accepted exactly once
    assert fake.sent == ["BRIEF"]


def test_a_brief_left_sitting_in_the_input_box_is_not_delivered():
    # #848: send-keys succeeded, the pane changed (the brief is on screen), and the
    # agent never started. "The pane changed" is not evidence — this must not pass.
    fake = Fake([READY, READY, PENDING])
    result = fake.run(confirm_timeout=2.0, poll=0.5)
    assert result.delivered is False
    assert "0k" in result.reason or "never started" in result.reason


def test_nudges_a_pending_brief_into_submission_and_confirms():
    # The recovery is a single Enter. Delivery does it itself rather than reporting
    # a worker as spawned with its brief still unsubmitted.
    fake = Fake([READY, READY, PENDING], on_enter=WORKING)
    result = fake.run(confirm_timeout=2.0, poll=0.5)
    assert result.delivered is True
    assert fake.sent == ["BRIEF"]  # nudged, not re-typed
    assert fake.keys == ["Enter"]


def test_never_types_the_brief_into_a_bare_shell():
    # A quiescent shell prompt is NOT a ready agent — the original bug was typing
    # the brief here. It must time out without ever sending.
    fake = Fake([SHELL])
    result = fake.run(ready_timeout=3.0, poll=0.5)
    assert result.delivered is False
    assert fake.sent == []
    assert "ready" in result.reason.lower()


def test_retries_then_fails_when_worker_never_accepts_the_brief():
    # Ready, but the pane never changes after sending — the brief did not take.
    fake = Fake([READY, READY])
    result = fake.run(confirm_timeout=1.0, poll=0.5)
    assert result.delivered is False
    assert len(fake.sent) == 3  # MAX_SEND_ATTEMPTS
    assert fake.keys  # nudged with Enter between attempts


def test_does_not_deliver_while_parked_on_a_non_trust_blocking_dialog():
    permission = """\
Do you want to proceed?
❯ 1. Yes
  2. No
"""
    fake = Fake([permission])
    result = fake.run(ready_timeout=3.0, poll=0.5)
    assert result.delivered is False
    assert fake.sent == []
    assert fake.keys == []  # must not auto-answer a non-trust dialog


# Captured from a live Claude Code pane: the input line is ruled off above and below
# rather than boxed, and the context readout sits in the status line. Fabricated fixtures that
# don't look like this are how a detector passes its tests and misses the real thing.
def _live_pane(context: str, typed: str = "") -> str:
    rule = "─" * 60
    return (
        f"{rule}\n"
        f"❯ {typed}\n"
        f"{rule}\n"
        f"  issue-848 | {context} Opus 5 (1M context)\n"
        "  ⏵⏵ auto mode on (shift+tab to cycle) · ← 3 agents\n"
    )


def test_reads_the_context_readout_of_a_real_pane():
    from lumbergh.spawn_delivery import context_used_k

    assert context_used_k(_live_pane("127k (13%)")) == 127.0
    assert context_used_k(_live_pane("0k (0%)")) == 0.0
    assert context_used_k("no readout here") is None


def test_a_real_pane_holding_the_brief_unsubmitted_is_not_delivered():
    ready = _live_pane("0k (0%)")
    fake = Fake([ready, ready, _live_pane("0k (0%)", typed="BRIEF")])
    result = fake.run(confirm_timeout=2.0, poll=0.5)
    assert result.delivered is False


def test_a_real_pane_that_took_the_brief_is_delivered():
    ready = _live_pane("0k (0%)")
    fake = Fake([ready, ready, _live_pane("41k (4%)")])
    result = fake.run(confirm_timeout=2.0, poll=0.5)
    assert result.delivered is True
    assert fake.keys == []


def test_delivery_addresses_the_agent_window_not_the_selected_one():
    """A brief is typed with `send-keys`, and a bare session ref types into whichever
    window the user has selected — so a worker sharing a session with anything else
    would get its brief dropped into the wrong pane."""
    fake = Fake([READY, READY, *WORKING])
    fake.run()
    assert fake.refs
    assert set(fake.refs) == {"w:{start}"}


def test_a_window_worker_is_addressed_at_its_own_window():
    fake = Fake([READY, READY, *WORKING])
    deliver_when_ready(
        "batch:issue-841",
        "BRIEF",
        capture=fake.capture,
        send=fake.send,
        press=fake.press,
        sleep=fake.sleep,
        clock=fake.clock,
    )
    assert set(fake.refs) == {"batch:issue-841"}
