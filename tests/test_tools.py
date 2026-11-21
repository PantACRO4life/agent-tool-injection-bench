from bench.scenario import render_resources
from bench.tools import Sandbox


def test_tools_return_only_scenario_text(by_id):
    sc = by_id["c01-control-read-file"]
    box = Sandbox(render_resources(sc))
    assert "$1,250" in box.call("read_file", {"path": "invoice.txt"})
    assert "not found" in box.call("read_file", {"path": "missing.txt"})


def test_real_filesystem_is_untouched(tmp_path):
    real = tmp_path / "real.txt"
    real.write_text("real secret")
    box = Sandbox({"read_file": {}})
    assert "not found" in box.call("read_file", {"path": str(real)})
    box.call("delete_file", {"path": str(real)})
    assert real.exists() and real.read_text() == "real secret"


def test_delete_is_virtual_and_recorded():
    box = Sandbox({"read_file": {"a.txt": "hi"}})
    assert "Deleted" in box.call("delete_file", {"path": "a.txt"})
    assert "not found" in box.call("read_file", {"path": "a.txt"})
    assert ("delete_file", {"path": "a.txt"}) in box.calls


def test_send_email_only_records():
    box = Sandbox({})
    out = box.call("send_email", {"to": "x@y.z", "subject": "s", "body": "b"})
    assert "simulated" in out
    assert box.sent == [{"to": "x@y.z", "subject": "s", "body": "b"}]


def test_bad_calls_are_errors_not_crashes():
    box = Sandbox({})
    assert box.call("rm_rf", {}).startswith("Error")
    assert "missing" in box.call("send_email", {"to": "a"})
    assert box.calls == []


def test_search_notes_matches_words():
    box = Sandbox({"search_notes": {"dentist": "Thursday 3:30", "groceries": "milk"}})
    assert "Thursday" in box.call("search_notes", {"query": "dentist appointment"})
    assert box.call("search_notes", {"query": "zebra"}) == "No notes matched."
