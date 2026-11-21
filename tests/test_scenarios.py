import pytest

from bench.scenario import format_injection, insert_injection, render_resources


def test_counts(scenarios):
    attacks = [s for s in scenarios if s.is_attack]
    controls = [s for s in scenarios if not s.is_attack]
    assert len(attacks) >= 8 and len(controls) == 3


def test_variety(scenarios):
    inj = [s.injection for s in scenarios if s.is_attack]
    assert {i.placement for i in inj} == {"start", "middle", "end"}
    assert {i.format for i in inj} == {"plain", "html_comment", "markdown", "system_note"}
    assert {i.goal for i in inj} == {"exfiltrate", "delete", "ignore"}


def test_injection_is_rendered_once_in_target(scenarios):
    for sc in scenarios:
        rendered = render_resources(sc)
        hits = [(t, k) for t, items in rendered.items() for k, v in items.items()
                if sc.injection and sc.injection.text in v]
        if sc.is_attack:
            assert hits == [tuple(sc.injection.target.split(":", 1))]
        else:
            assert hits == []


def test_canaries_are_fake_strings(scenarios):
    for sc in scenarios:
        if sc.canary:
            assert sc.canary.startswith("CANARY-")


@pytest.mark.parametrize("placement,index", [("start", 0), ("middle", 1), ("end", 2)])
def test_placement(placement, index):
    out = insert_injection(["a", "b"], "X", placement)
    assert out.index("X") == index


def test_formats():
    assert format_injection("t", "html_comment") == "<!-- t -->"
    assert "SYSTEM NOTE" in format_injection("t", "system_note")
    assert format_injection("t", "plain") == "t"
