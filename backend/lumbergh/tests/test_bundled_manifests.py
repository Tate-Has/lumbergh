from pathlib import Path

from lumbergh.detect.manifest import load_manifests

MANIFESTS_DIR = Path(__file__).resolve().parents[1] / "detect" / "manifests"


def test_all_bundled_manifests_parse_with_no_dropped_rules():
    manifests = load_manifests(MANIFESTS_DIR)
    ids = {m.id for m in manifests}
    assert {"common", "claude", "pi"} <= ids
    for manifest in manifests:
        assert manifest.rules, f"{manifest.id} has no rules (all dropped as invalid?)"
