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

WORKING = """\
● Reading your brief…

⠋ Working… (3s · esc to interrupt)
"""

SHELL = "user@host:~/app-worktrees/fix$ "


class Fake:
    """A scripted pane: yields queued snapshots, then repeats the last one.

    ``clock`` only advances when ``sleep`` is called, so timeouts are deterministic.
    """

    def __init__(self, panes):
        self._panes = list(panes)
        self.sent: list[str] = []
        self.keys: list[str] = []
        self.t = 0.0

    def capture(self, _name):
        return self._panes.pop(0) if len(self._panes) > 1 else self._panes[0]

    def send(self, _name, text):
        self.sent.append(text)
        return True

    def press(self, _name, key="Enter"):
        self.keys.append(key)
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
    fake = Fake([BOOTING, READY, READY, WORKING])
    result = fake.run()
    assert result.delivered is True
    assert fake.sent == ["BRIEF"]
    assert fake.keys == []  # no trust dialog, no nudges


def test_answers_folder_trust_dialog_before_delivering():
    fake = Fake([TRUST, TRUST, READY, READY, WORKING])
    result = fake.run()
    assert result.delivered is True
    assert fake.keys == ["Enter"]  # trust accepted exactly once
    assert fake.sent == ["BRIEF"]


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
