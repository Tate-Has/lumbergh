import pytest

from lumbergh.question_detector import (
    DEFAULT_TIMEOUT,
    Verdict,
    build_prompt,
    detect,
    parse_verdict,
)


class _StubProvider:
    def __init__(self, response="", *, raises=None, delay=0.0):
        self.response = response
        self.raises = raises
        self.delay = delay
        self.prompts: list[str] = []

    async def complete(self, prompt):
        self.prompts.append(prompt)
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        if self.raises:
            raise self.raises
        return self.response

    async def health_check(self):
        return True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("YES: needs a database choice", True),
        ("yes", True),
        ("YES", True),
        ("  Yes: which branch?  ", True),
        ("**YES**: pick an option", True),
        ("NO", False),
        ("no", False),
        ("No, it just finished the task.", False),
        ("", False),
        ("I'm not sure what you mean", False),
        ("The agent is done and waiting silently.", False),
    ],
)
def test_parse_verdict(raw, expected):
    assert parse_verdict(raw).waiting is expected


def test_parse_verdict_extracts_reason():
    v = parse_verdict("YES: waiting for a database choice")
    assert v.waiting is True
    assert "database" in v.reason.lower()
    assert len(v.reason) <= 120


def test_parse_verdict_no_has_empty_reason():
    assert parse_verdict("NO").reason == ""


def test_build_prompt_strips_ansi_and_bounds_tail():
    noisy = "\x1b[32mgreen\x1b[0m line\n" + "\n".join(f"line {i}" for i in range(200))
    prompt = build_prompt(noisy)
    assert "\x1b[" not in prompt
    # The most recent line must survive; very old lines must be dropped.
    assert "line 199" in prompt
    assert "line 0" not in prompt


def test_build_prompt_trims_trailing_blank_lines():
    prompt = build_prompt("Which database?\n\n\n\n")
    assert "Which database?" in prompt


def test_build_prompt_strips_ui_chrome():
    pane = (
        "Done. All tests pass.\n"
        "╭────────────────────────────╮\n"
        "│ >                          │\n"
        "╰────────────────────────────╯\n"
        "  ? for shortcuts\n"
    )
    prompt = build_prompt(pane)
    assert "Done. All tests pass." in prompt
    assert "? for shortcuts" not in prompt
    assert "╭" not in prompt


async def test_detect_short_circuits_on_all_chrome_pane():
    provider = _StubProvider("YES: spurious")
    pane = "╭──────────╮\n│ >        │\n╰──────────╯\n  ? for shortcuts\n"
    verdict = await detect(pane, provider)
    assert verdict.waiting is False
    assert provider.prompts == [], "provider must not be called for an all-chrome pane"


async def test_detect_returns_waiting_on_yes():
    provider = _StubProvider("YES: choose a database")
    verdict = await detect("Which database should I use?", provider)
    assert verdict.waiting is True
    assert provider.prompts, "provider was called"


async def test_detect_fails_safe_on_provider_error():
    provider = _StubProvider(raises=RuntimeError("ollama down"))
    verdict = await detect("anything", provider)
    assert verdict == Verdict(False, "")


async def test_detect_fails_safe_on_timeout():
    provider = _StubProvider("YES: too late", delay=0.2)
    verdict = await detect("anything", provider, timeout=0.01)
    assert verdict.waiting is False


def test_default_timeout_is_reasonable():
    assert 5 <= DEFAULT_TIMEOUT <= 60
