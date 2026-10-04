"""Checks the registry of known CrossHair defects.

The point of the registry is that a run says what is new. Everything here
is about not lying in one of the two directions: reporting a defect as new
when it has been known for months, or reporting it as gone when the run
never looked.
"""

import json
import sys

from discovery.cli import main as cli_main
from discovery.defects import (
    ATTRIBUTABLE,
    REGISTRY_VERSION,
    SUSPECTED,
    Defect,
    Sighting,
    load,
    save,
    sightings_from,
    update,
)
from discovery.model import Verdict

VERSION = "0.0.111"
NEXT_VERSION = "0.0.112"
TODAY = "2026-10-04"
TOMORROW = "2026-10-05"


def seen(signature="abc123", project="alpha", frame="crosshair/core.py:12"):
    return Sighting(
        signature=signature,
        exception_type="CrossHairInternal",
        frame=frame,
        message="symbolic while not tracing",
        project=project,
        sample="Traceback...",
    )


def report(verdict="crosshair_false_positive", nodeid="t::one", frame="f.py:1"):
    return {
        "classifications": [{"nodeid": nodeid, "verdict": verdict}],
        "clusters": [
            {
                "exception_type": "ValueError",
                "frame": frame,
                "message": "boom",
                "nodeids": [nodeid],
                "sample": "trace",
            }
        ],
    }


def test_a_defect_seen_for_the_first_time_is_new():
    registry, changes = update(
        [], [seen()], covered={"alpha"}, version=VERSION, today=TODAY
    )
    assert [d.signature for d in changes.new] == ["abc123"]
    assert registry[0].first_seen == TODAY and registry[0].first_version == VERSION
    assert registry[0].status == SUSPECTED


def test_a_defect_seen_again_is_not_new():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    _, changes = update(
        registry, [seen()], covered={"alpha"}, version=VERSION, today=TOMORROW
    )
    assert not changes.new and [d.signature for d in changes.still_present] == [
        "abc123"
    ]


def test_a_project_seen_twice_is_listed_once():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    registry, _ = update(
        registry, [seen()], covered={"alpha"}, version=VERSION, today=TOMORROW
    )
    assert registry[0].projects == ["alpha"]


def test_the_same_defect_in_two_projects_is_one_entry():
    registry, changes = update(
        [],
        [seen(project="alpha"), seen(project="beta")],
        covered={"alpha", "beta"},
        version=VERSION,
        today=TODAY,
    )
    assert len(registry) == 1
    assert registry[0].projects == ["alpha", "beta"]
    assert len(changes.new) == 1


def test_a_defect_that_stops_reproducing_on_a_new_version_is_gone():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    registry, changes = update(
        registry, [], covered={"alpha"}, version=NEXT_VERSION, today=TOMORROW
    )
    assert [d.signature for d in changes.gone] == ["abc123"]
    assert registry[0].gone_since == NEXT_VERSION and not registry[0].present


def test_absence_on_the_same_version_proves_nothing():
    """The search is not reproducible, so one quiet run is not a fix."""
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    _, changes = update(
        registry, [], covered={"alpha"}, version=VERSION, today=TOMORROW
    )
    assert not changes.gone and [d.signature for d in changes.unverified] == ["abc123"]


def test_absence_where_the_run_did_not_look_proves_nothing():
    registry, _ = update(
        [],
        [seen(project="alpha"), seen(project="beta")],
        covered={"alpha", "beta"},
        version=VERSION,
        today=TODAY,
    )
    _, changes = update(
        registry, [], covered={"alpha"}, version=NEXT_VERSION, today=TOMORROW
    )
    assert not changes.gone, "beta was never run, so beta's defect was not tested"
    assert len(changes.unverified) == 1


def test_a_defect_that_comes_back_is_present_again():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    registry, _ = update(
        registry, [], covered={"alpha"}, version=NEXT_VERSION, today=TOMORROW
    )
    registry, changes = update(
        registry, [seen()], covered={"alpha"}, version=NEXT_VERSION, today=TOMORROW
    )
    assert registry[0].present and not registry[0].gone_since
    assert [d.signature for d in changes.still_present] == ["abc123"]


def test_a_defect_already_gone_is_not_reported_again():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    registry, _ = update(
        registry, [], covered={"alpha"}, version=NEXT_VERSION, today=TOMORROW
    )
    _, changes = update(
        registry, [], covered={"alpha"}, version="0.0.113", today=TOMORROW
    )
    assert not changes.gone and not changes.unverified


def test_what_a_person_wrote_survives_a_run():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    registry[0].issue = "https://github.com/pschanely/CrossHair/issues/1"
    registry[0].status = "filed"
    registry[0].note = "only with POSSESSIVE_REPEAT"
    registry, _ = update(
        registry, [seen()], covered={"alpha"}, version=VERSION, today=TOMORROW
    )
    assert registry[0].status == "filed" and registry[0].note
    assert registry[0].issue.endswith("/1")


def test_updating_does_not_change_the_registry_it_was_given():
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    before = registry[0].last_seen
    update(registry, [seen()], covered={"alpha"}, version=VERSION, today=TOMORROW)
    assert registry[0].last_seen == before


def test_a_registry_survives_a_write_and_a_read(tmp_path):
    registry, _ = update([], [seen()], covered={"alpha"}, version=VERSION, today=TODAY)
    where = save(str(tmp_path / "defects.json"), registry)
    assert load(where) == registry


def test_a_registry_that_is_not_there_reads_as_empty(tmp_path):
    assert load(str(tmp_path / "absent.json")) == []


def test_a_registry_this_code_did_not_write_reads_as_empty(tmp_path):
    where = tmp_path / "defects.json"
    where.write_text('{"version": 99, "defects": [{"signature": "x"}]}')
    assert load(str(where)) == []


def test_a_registry_that_cannot_be_parsed_reads_as_empty(tmp_path):
    where = tmp_path / "defects.json"
    where.write_text("{not json")
    assert load(str(where)) == []


def test_an_entry_with_no_signature_is_not_a_defect(tmp_path):
    where = tmp_path / "defects.json"
    where.write_text(
        '{"version": %d, "defects": [{"summary": "no key"}]}' % REGISTRY_VERSION
    )
    assert load(str(where)) == []


def test_a_false_positive_is_crosshairs_without_anyone_triaging_it():
    found = sightings_from(report("crosshair_false_positive"), "alpha")
    assert len(found) == 1 and found[0].project == "alpha"


def test_a_crash_is_crosshairs_too():
    assert len(sightings_from(report("crosshair_crash"), "alpha")) == 1


def test_a_trophy_is_not_crosshairs():
    assert sightings_from(report("trophy_candidate"), "alpha") == []


def test_a_timeout_is_a_hard_search_not_a_defect():
    assert sightings_from(report("crosshair_timeout"), "alpha") == []
    assert "crosshair_timeout" not in ATTRIBUTABLE


def test_a_cluster_no_verdict_attributes_is_left_alone():
    payload = report("crosshair_crash", nodeid="t::one")
    payload["clusters"][0]["nodeids"] = ["t::other"]
    assert sightings_from(payload, "alpha") == []


def test_two_projects_failing_the_same_way_share_a_signature():
    one = sightings_from(report("crosshair_crash"), "alpha")[0]
    two = sightings_from(report("crosshair_crash"), "beta")[0]
    assert one.signature == two.signature


def test_failing_differently_does_not_share_a_signature():
    one = sightings_from(report("crosshair_crash", frame="a.py:1"), "alpha")[0]
    two = sightings_from(report("crosshair_crash", frame="b.py:2"), "alpha")[0]
    assert one.signature != two.signature


def test_a_report_with_nothing_in_it_sights_nothing():
    assert sightings_from({}, "alpha") == []


def test_a_gone_defect_sorts_after_a_present_one(tmp_path):
    """Whatever the dates say: what still reproduces is what matters."""
    present = Defect(signature="here", last_seen=TOMORROW)
    gone = Defect(signature="gone", last_seen=TODAY, gone_since=NEXT_VERSION)
    where = save(str(tmp_path / "d.json"), [gone, present])
    assert [d.signature for d in load(where)] == ["here", "gone"]


ALWAYS_FAILS = """\
from hypothesis import given, strategies as st


@given(st.integers())
def test_boom(n):
    assert n != n
"""


def test_the_reader_matches_what_the_pipeline_actually_writes(tmp_path, capsys):
    """Pins this against the real producer, not against a payload written here.

    Every key read below is one the pipeline chose; a rename there would
    otherwise leave the registry silently finding nothing for good.
    """
    (tmp_path / "test_boom.py").write_text(ALWAYS_FAILS)
    assert (
        cli_main(
            [
                "--project",
                str(tmp_path),
                "--crosshair-python",
                sys.executable,
                "--sandbox",
                "local",
                "--run-root",
                str(tmp_path / "runs"),
                "--no-telemetry-tier",
                "--baseline-seeds",
                "1",
                "--baseline-max-examples",
                "1",
                "--crosshair-max-examples",
                "1",
                "--crosshair-timeout",
                "30",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["clusters"], "a failing property should cluster"
    for entry in payload["classifications"]:
        entry["verdict"] = "crosshair_crash"
    found = sightings_from(payload, "alpha")
    assert len(found) == 1
    assert found[0].exception_type == "AssertionError"
    assert found[0].frame and found[0].signature and found[0].sample


def test_every_attributable_name_is_a_verdict_the_pipeline_can_report():
    assert ATTRIBUTABLE <= {verdict.value for verdict in Verdict}
