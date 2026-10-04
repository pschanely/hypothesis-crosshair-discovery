"""Checks harness repair, and the repairs it must be unable to make.

The failure texts here were produced by the corpus rather than written for
the test: a suite whose own configuration names a plugin that is not
installed refuses to start, and says which flags it did not recognize.
"""

import dataclasses
import sys

from discovery.harness import (
    MAX_REPAIRS,
    MODULE_DISTRIBUTIONS,
    PLUGIN_FLAGS,
    Repair,
    declared_names,
    declared_requirements,
    diagnose,
    plan,
)

BENCHMARK = """\
ERROR: usage: python -m pytest [options] [file_or_dir] [file_or_dir] [...]
python -m pytest: error: unrecognized arguments: --benchmark-sort=fullname \
--benchmark-warmup=true --benchmark-warmup-iterations=5 \
--benchmark-group-by=fullname
"""

XDIST = """\
ERROR: usage: python -m pytest [options] [file_or_dir] [file_or_dir] [...]
python -m pytest: error: unrecognized arguments: -n0
  inifile: /home/user/corpus/hyperlink/pytest.ini
  rootdir: /home/user/corpus/hyperlink
"""


def test_a_benchmark_suite_asks_for_the_benchmark_plugin():
    repair = diagnose(BENCHMARK)
    assert repair.packages == ["pytest-benchmark"]
    assert repair.pytest_args == []


def test_an_xdist_suite_installs_the_plugin_and_then_stops_it_working():
    repair = diagnose(XDIST)
    assert repair.packages == ["pytest-xdist"]
    assert repair.pytest_args == ["-n0"], "xdist hides tests from the injected plugin"


def test_an_unfamiliar_failure_yields_no_repair():
    assert diagnose("E   AssertionError: assert 1 == 2") is None
    assert diagnose("") is None


def test_a_missing_import_is_matched_to_its_distribution():
    repair = diagnose("ModuleNotFoundError: No module named 'pytest_benchmark'")
    assert repair.packages == ["pytest-benchmark"]


def test_an_unmapped_missing_import_is_not_guessed_at():
    assert diagnose("ModuleNotFoundError: No module named 'some_private_thing'") is None


#: One collection, five test modules, five different missing dependencies.
#: Produced by provisioning pydantic.
PYDANTIC_IMPORTS = """\
tests/pydantic_core/test_docstrings.py:4: in <module>
    from pytest_examples import CodeExample, EvalExample
E   ModuleNotFoundError: No module named 'pytest_examples'
tests/pydantic_core/validators/test_allow_partial.py:5: in <module>
    from inline_snapshot import snapshot
E   ModuleNotFoundError: No module named 'inline_snapshot'
tests/test_annotated.py:8: in <module>
    import pytz
E   ModuleNotFoundError: No module named 'pytz'
tests/test_docs.py:19: in <module>
    import time_machine
E   ModuleNotFoundError: No module named 'time_machine'
tests/test_generics.py:27: in <module>
    from pytest_mock import MockerFixture
E   ModuleNotFoundError: No module named 'pytest_mock'
"""


def test_every_missing_import_is_installed_in_one_repair():
    """One repair per collection, not one per module.

    A repair is offered once per project, so a suite missing five
    dependencies has to be fixed in a single pass or it escalates having
    installed one of them.
    """
    repair = diagnose(PYDANTIC_IMPORTS, declared={"inline-snapshot"})
    assert repair.packages == [
        "pytest-examples",
        "inline-snapshot",
        "pytz",
        "time-machine",
        "pytest-mock",
    ]


def test_imports_discovered_in_a_later_wave_are_still_installed():
    """An import error hides every later import in the same module.

    pydantic's test_errors.py imports pytest_examples and then
    inline_snapshot; the second is invisible until the first is installed,
    so the repair has to be offered again for what it has not installed yet.
    """
    first = plan(PYDANTIC_IMPORTS, [], {"inline-snapshot"})
    later = "ModuleNotFoundError: No module named 'inline_snapshot'"
    again = plan(later, [first.name], {"inline-snapshot"}, installed=["pytz"])
    assert again is not None and again.packages == ["inline-snapshot"]


def test_a_repeated_repair_installs_only_what_is_missing():
    repair = plan(
        PYDANTIC_IMPORTS,
        ["install-missing-imports"],
        {"inline-snapshot"},
        installed=["pytz", "time-machine", "pytest-examples"],
    )
    assert repair.packages == ["inline-snapshot", "pytest-mock"]


def test_a_repeated_repair_that_adds_nothing_escalates():
    assert (
        plan(
            PYDANTIC_IMPORTS,
            ["install-missing-imports"],
            {"inline-snapshot"},
            installed=[
                "pytest-examples",
                "inline-snapshot",
                "pytz",
                "time-machine",
                "pytest-mock",
            ],
        )
        is None
    )


def test_an_unmapped_import_the_project_declares_is_installed():
    text = "ModuleNotFoundError: No module named 'inline_snapshot'"
    assert diagnose(text, declared={"inline-snapshot"}).packages == ["inline-snapshot"]


def test_an_unmapped_import_the_project_does_not_declare_is_left_alone():
    text = "ModuleNotFoundError: No module named 'inline_snapshot'"
    assert diagnose(text, declared={"something-else"}) is None


def test_the_known_mapping_wins_over_a_declaration_that_spells_it_differently():
    """attrs supplies attr; a declaration must not redirect that to PyPI's attr."""
    text = "ModuleNotFoundError: No module named 'attr'"
    assert diagnose(text, declared={"attr"}).packages == ["attrs"]


def test_a_known_import_needs_no_declaration():
    text = "ModuleNotFoundError: No module named 'pytz'"
    assert diagnose(text).packages == ["pytz"]


def test_the_same_distribution_is_not_installed_twice():
    text = (
        "ModuleNotFoundError: No module named 'pytz'\n"
        "ModuleNotFoundError: No module named 'pytz.tzinfo'\n"
    )
    assert diagnose(text).packages == ["pytz"]


def test_a_declaration_is_read_from_several_shapes_of_requirement():
    found = declared_names(
        "\n".join(
            [
                "    'inline-snapshot[black]>=0.4',",
                '    "dirty-equals==0.9",',
                "pytest-mock ; python_version > '3.8'",
                "# a comment naming nothing",
            ]
        )
    )
    assert {"inline-snapshot", "dirty-equals", "pytest-mock"} <= found


def test_a_vendored_subproject_declares_for_the_tests_it_ships(tmp_path):
    """pydantic vendors pydantic-core's tests, which need its dependencies."""
    (tmp_path / "pyproject.toml").write_text("dependencies = ['typing-extensions']")
    nested = tmp_path / "pydantic-core"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("dependencies = ['inline-snapshot']")
    found = declared_requirements(str(tmp_path))
    assert {"typing-extensions", "inline-snapshot"} <= found


def test_a_declaration_two_levels_down_is_another_project_s_business(tmp_path):
    deep = tmp_path / "vendor" / "unrelated"
    deep.mkdir(parents=True)
    (deep / "pyproject.toml").write_text("dependencies = ['should-not-appear']")
    assert "should-not-appear" not in declared_requirements(str(tmp_path))


def test_a_checkout_declaring_nothing_reads_as_nothing(tmp_path):
    assert declared_requirements(str(tmp_path)) == set()


def test_a_configuration_file_that_cannot_be_read_is_skipped(tmp_path):
    (tmp_path / "pyproject.toml").mkdir()
    (tmp_path / "requirements.txt").write_text("dirty-equals==0.9")
    assert declared_requirements(str(tmp_path)) == {"dirty-equals"}


def test_a_token_too_long_to_be_a_distribution_is_not_one():
    assert declared_names("'" + "a" * 200 + "'") == set()


def test_several_plugins_in_one_failure_are_installed_together():
    text = (
        "python -m pytest: error: unrecognized arguments: --cov=pkg "
        "--benchmark-sort=name -n2"
    )
    repair = diagnose(text)
    assert repair.packages == ["pytest-cov", "pytest-benchmark", "pytest-xdist"]
    assert repair.pytest_args == ["-n0"]


def test_a_flag_matches_at_most_one_distribution():
    """The lookup takes the first matching prefix, so none may extend another."""
    for prefix, dist in PLUGIN_FLAGS.items():
        for other, other_dist in PLUGIN_FLAGS.items():
            if prefix is not other and other.startswith(prefix):
                assert dist == other_dist, f"{other} is shadowed by {prefix}"


def test_a_repair_cannot_express_a_change_to_the_suite():
    """The dangerous repair is unrepresentable, not merely discouraged.

    A harness repair that edited a test could turn a failing assertion into a
    passing one, or a passing one into a finding. Nothing here can name a
    file, so no such repair can be built.
    """
    fields = {f.name for f in dataclasses.fields(Repair)}
    assert fields == {"name", "rationale", "packages", "env", "pytest_args"}


def test_a_repair_describes_what_it_changes():
    repair = Repair(
        name="r",
        rationale="why",
        packages=["pytest-cov"],
        env={"K": "v"},
        pytest_args=["-p", "no:cacheprovider"],
    )
    text = repair.describe()
    assert "install pytest-cov" in text and "K=v" in text and "no:cacheprovider" in text


def test_a_repair_that_would_install_nothing_new_is_not_offered_again():
    first = plan(BENCHMARK)
    assert first is not None
    repeat = plan(BENCHMARK, applied=[first.name], installed=first.packages)
    assert repeat is None, "a repeat installing the same packages would loop"


def test_a_repair_with_nothing_to_install_is_not_offered_again():
    text = "7 deselected in 0.2s"
    first = plan(text)
    assert first.pytest_args == ["-m", ""] and not first.packages
    assert plan(text, applied=[first.name]) is None


def test_repairs_stop_after_the_budget():
    assert plan(BENCHMARK, applied=["a"] * MAX_REPAIRS) is None
    assert plan(BENCHMARK, applied=["a"] * (MAX_REPAIRS - 1)) is not None


def test_every_mapped_module_names_an_installable_distribution():
    """The table is an allowlist, so every entry must be usable as given."""
    for module, dist in MODULE_DISTRIBUTIONS.items():
        assert module.isidentifier(), module
        assert dist and not set(dist) & set(" \t;&|<>$`"), dist


def test_a_flags_value_is_not_reported_as_a_flag():
    """A project may write ``addopts`` with spaces, so argparse echoes values."""
    repair = diagnose(
        "python -m pytest: error: unrecognized arguments: "
        "--benchmark-sort fullname --benchmark-warmup true"
    )
    assert repair.packages == ["pytest-benchmark"]
    assert "fullname" not in repair.rationale
    assert "--benchmark-sort" in repair.rationale


def _broken_project(tmp_path, addopts):
    (tmp_path / "pytest.ini").write_text(f"[pytest]\naddopts = {addopts}\n")
    (tmp_path / "test_a.py").write_text(
        "from hypothesis import given, strategies as st\n\n"
        "@given(st.integers())\n"
        "def test_a(n):\n"
        "    assert n == n\n"
    )
    return [
        "--project",
        str(tmp_path),
        "--crosshair-python",
        sys.executable,
        "--sandbox",
        "local",
        "--run-root",
        str(tmp_path / "runs"),
    ]


def test_a_repairable_collection_failure_reports_the_repair(tmp_path, capsys):
    from discovery.cli import main

    assert main(_broken_project(tmp_path, "--benchmark-sort=fullname")) == 3
    err = capsys.readouterr().err
    assert "install pytest-benchmark" in err
    assert "collection failed" in err


def test_an_unrepairable_collection_failure_asks_for_a_person(tmp_path, capsys):
    from discovery.cli import main

    assert main(_broken_project(tmp_path, "--no-such-plugin-flag")) == 2
    assert "needs a person" in capsys.readouterr().err


DESELECTED = "7 deselected, 2 warnings in 0.23s\n"

COLLECT_ERRORS = """\
ERROR tests/integrations/wsgi/test_wsgi.py
ERROR tests/test_client.py - sentry_sdk.integrations.DidNotEnable: executing is not installed
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
"""


def test_a_project_that_deselects_its_own_property_tests_is_overridden():
    """virtualenv sets addopts = -m 'not property', so none of them run."""
    repair = diagnose(DESELECTED)
    assert repair.pytest_args == ["-m", ""]
    assert repair.packages == []


def test_a_partly_deselected_run_is_left_alone():
    """Tests that ran are a working harness, whatever else was filtered out."""
    assert diagnose("7 passed, 2 deselected in 1.5s") is None


def test_a_missing_marker_names_the_plugin_that_registers_it():
    repair = diagnose(
        "INTERNALERROR> Failed: 'thread_unsafe' not found in `markers` configuration"
    )
    assert repair.packages == ["pytest-run-parallel"]


def test_an_unknown_marker_is_not_guessed_at():
    assert (
        diagnose("Failed: 'bespoke_marker' not found in `markers` configuration")
        is None
    )


def test_modules_that_cannot_be_imported_are_skipped_not_installed():
    repair = diagnose(COLLECT_ERRORS)
    assert repair.packages == []
    assert repair.pytest_args == [
        "--ignore=tests/integrations/wsgi/test_wsgi.py",
        "--ignore=tests/test_client.py",
    ]
    assert "test_client.py" in repair.rationale, "an ignored module must be named"


def test_a_collection_error_from_crosshair_is_never_skipped():
    """Skipping it would hide the defect the pipeline exists to find."""
    text = (
        "ERROR tests/test_a.py - crosshair.util.CrossHairInternal: boom\n"
        "!!! Interrupted: 1 errors during collection !!!\n"
    )
    assert diagnose(text) is None


def test_a_known_test_dependency_is_installed_rather_than_skipped():
    repair = diagnose("E   ModuleNotFoundError: No module named 'dirty_equals'")
    assert repair.packages == ["dirty-equals"]
    assert repair.pytest_args == []
