from lumbergh import bill


def test_render_substitutes_the_professional_preamble():
    body = bill.render("professional")
    assert "{{PERSONALITY}}" not in body
    assert "TPS" not in body


def test_render_substitutes_the_lumbergh_preamble():
    body = bill.render("lumbergh")
    assert "{{PERSONALITY}}" not in body
    assert body != bill.render("professional")


def test_render_falls_back_to_professional_for_an_unknown_personality():
    assert bill.render("pirate") == bill.render("professional")


def test_instructions_treat_an_idle_unseen_overseer_as_a_delivered_chunk():
    """The bug this guards: Bill woke on a finished overseer, saw it idle (no
    DELIVERED/FAILED outcome — overseers don't emit one), judged it "still working,"
    and sat on the report instead of relaying it. The bundle must tell him idle+unseen
    is a delivered chunk to report, and that state comes from the row, not read text."""
    body = " ".join(bill.render("professional").lower().split())
    assert "unseen" in body
    assert "delivered a chunk" in body
    assert "never infer state from `lb read`" in body


def test_materialize_creates_the_full_home(tmp_path):
    home = bill.materialize(home_dir=tmp_path / "bill")
    assert (home / "AGENTS.md").is_file()
    assert (home / "CLAUDE.md").resolve() == (home / "AGENTS.md").resolve()
    assert (home / "preferences.md").is_file()
    assert (home / "briefs").is_dir()
    assert (home / "reports").is_dir()


def test_materialize_refreshes_agents_md_but_never_preferences(tmp_path):
    home = bill.materialize(home_dir=tmp_path / "bill")
    (home / "preferences.md").write_text("I hate mocks.\n")
    (home / "AGENTS.md").write_text("clobbered\n")
    (home / "briefs" / "w-a.md").write_text("do the thing\n")

    bill.materialize(personality="lumbergh", home_dir=home)

    assert (home / "preferences.md").read_text() == "I hate mocks.\n"
    assert (home / "briefs" / "w-a.md").read_text() == "do the thing\n"
    assert "clobbered" not in (home / "AGENTS.md").read_text()
    assert (home / "AGENTS.md").read_text() == bill.render("lumbergh")


def test_materialize_is_idempotent(tmp_path):
    home = bill.materialize(home_dir=tmp_path / "bill")
    first = (home / "AGENTS.md").read_text()
    bill.materialize(home_dir=home)
    assert (home / "AGENTS.md").read_text() == first


def test_bundle_forbids_writing_code_and_merging():
    body = bill.render("professional")
    lowered = body.lower()
    assert "never write project code" in lowered
    assert "never merge" in lowered
    assert "lb fleet --wait" in body
    assert "lb spawn" in body


def test_bundle_documents_reading_a_workers_terminal_and_state():
    # Without these, a worker looks merely "idle" while it is actually parked on a
    # trust dialog, and Bill has no lb way to see it — so he reaches for raw tmux.
    body = bill.render("professional")
    assert "--source pane" in body
    assert "lb state" in body


def test_personality_never_leaks_into_the_brief_template():
    professional = bill.render("professional")
    flair = bill.render("lumbergh")
    marker = "## Brief template"
    assert professional.split(marker)[1] == flair.split(marker)[1]


def test_bundle_never_asks_bill_to_name_a_file_after_an_unknown_session():
    body = bill.render("professional")
    assert "<session>" not in body
    assert "--name <slug>" in body
    assert "briefs/<slug>.md" in body


def test_a_flavoured_personality_forbids_itself_in_worker_facing_text():
    """The brief *template* is pinned identical across personalities, but Bill writes brief
    *bodies* freehand. Nothing told him the voice was for the user only, so an Office-Space
    persona would leak flavor into text a worker or a tool reads literally."""
    flair = bill.render("lumbergh").lower()
    assert "never let it into a brief" in flair
    for audience in ("prompt to a worker", "tool will read"):
        assert audience in flair


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
