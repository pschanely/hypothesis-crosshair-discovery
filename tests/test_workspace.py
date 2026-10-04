"""Checks the directory that carries state between containers.

Two things are load-bearing here. A name that arrives from PyPI metadata or
a recorded index becomes a path, so it is checked before it is joined. And a
manifest only counts as read when this code wrote it, because a half-read
manifest would rebuild an environment that was never provisioned.
"""

import json
import os

import pytest

from discovery.manifest import MANIFEST_VERSION, Manifest
from discovery.workspace import (
    CHECKOUTS,
    DATASET_NAME,
    DATASETS,
    MANIFESTS,
    WORKSPACE_ENV,
    Workspace,
    safe_name,
)


@pytest.fixture
def space(tmp_path):
    return Workspace(str(tmp_path)).prepare()


def test_preparing_makes_every_place_things_belong(space):
    for name in (CHECKOUTS, MANIFESTS, DATASETS):
        assert os.path.isdir(space.path(name))


def test_a_manifest_survives_a_write_and_a_read(space):
    stored = Manifest(project="proj", commit="a" * 40, collected=12, pins=["x==1"])
    space.write_manifest(stored)
    assert space.read_manifest("proj") == stored


def test_a_project_with_no_manifest_reads_as_none(space):
    assert space.read_manifest("never-provisioned") is None


def test_an_unreadable_manifest_reads_as_none(space):
    with open(space.manifest_path("proj"), "w") as handle:
        handle.write("{not json")
    assert space.read_manifest("proj") is None


def test_a_manifest_this_code_did_not_write_reads_as_none(space):
    with open(space.manifest_path("proj"), "w") as handle:
        json.dump({"project": "proj", "version": MANIFEST_VERSION + 1}, handle)
    assert space.read_manifest("proj") is None


def test_listing_skips_what_cannot_be_read(space):
    space.write_manifest(Manifest(project="good"))
    with open(space.manifest_path("bad"), "w") as handle:
        handle.write("{")
    assert [m.project for m in space.manifests()] == ["good"]


def test_a_mounted_dataset_is_found(space):
    with open(space.path(DATASETS, DATASET_NAME), "w") as handle:
        handle.write("{}")
    assert space.dataset() == space.path(DATASETS, DATASET_NAME)


def test_a_dataset_that_was_not_mounted_is_absent(space):
    assert space.dataset() is None


@pytest.mark.parametrize(
    "name",
    ["../escape", "/etc/passwd", "owner/repo", "..", ".", "", "  ", "a/../b"],
)
def test_a_name_that_could_point_elsewhere_is_refused(name):
    with pytest.raises(ValueError):
        safe_name(name)


@pytest.mark.parametrize("name", ["pydantic", "owner__repo", "a.b-c_d"])
def test_an_ordinary_name_is_accepted(name):
    assert safe_name(name) == name


def test_paths_refuse_a_name_that_could_point_elsewhere(space):
    for method in (space.checkout_dir, space.manifest_path, space.dataset):
        with pytest.raises(ValueError):
            method("../elsewhere")


def test_a_workspace_comes_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    found = Workspace.from_environment()
    assert found is not None and found.root == str(tmp_path)


def test_an_argument_beats_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path / "ignored"))
    found = Workspace.from_environment(str(tmp_path / "chosen"))
    assert found.root == str(tmp_path / "chosen")


def test_no_workspace_is_configured_without_one(monkeypatch):
    monkeypatch.delenv(WORKSPACE_ENV, raising=False)
    assert Workspace.from_environment() is None


def test_the_store_lives_in_the_workspace(space):
    assert os.path.dirname(space.store_path) == space.root


def _git(repo, *argv):
    import subprocess

    done = subprocess.run(
        ["git", "-C", repo, *argv], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def origin(tmp_path):
    """A repository with two commits, serving arbitrary commits like GitHub."""
    repo = tmp_path / "origin"
    repo.mkdir()
    _git(str(repo), "init", "--quiet", "--initial-branch=main")
    _git(str(repo), "config", "user.email", "test@example.com")
    _git(str(repo), "config", "user.name", "test")
    _git(str(repo), "config", "uploadpack.allowAnySHA1InWant", "true")
    shas = []
    for text in ("first", "second"):
        (repo / "file.txt").write_text(text)
        _git(str(repo), "add", "file.txt")
        _git(str(repo), "commit", "--quiet", "-m", text)
        shas.append(_git(str(repo), "rev-parse", "HEAD"))
    return f"file://{repo}", shas


def test_a_missing_checkout_is_cloned(space, origin):
    url, shas = origin
    found = space.ensure_checkout("proj", url)
    assert found.ready and found.cloned
    assert found.commit == shas[-1] and not found.drifted


def test_an_existing_checkout_is_reused(space, origin):
    url, _ = origin
    space.ensure_checkout("proj", url)
    again = space.ensure_checkout("proj", url)
    assert again.ready and not again.cloned


def test_a_checkout_is_moved_to_the_recorded_commit(space, origin):
    url, shas = origin
    found = space.ensure_checkout("proj", url, commit=shas[0])
    assert found.commit == shas[0] and not found.drifted


def test_a_recorded_commit_that_is_gone_is_reported_as_drift(space, origin):
    url, shas = origin
    found = space.ensure_checkout("proj", url, commit="b" * 40)
    assert found.ready and found.drifted and found.commit == shas[-1]


def test_a_repository_that_cannot_be_cloned_is_reported(space, tmp_path):
    found = space.ensure_checkout("proj", f"file://{tmp_path}/absent")
    assert not found.ready and found.error


def test_a_manifest_restores_its_own_checkout(space, origin):
    url, shas = origin
    stored = Manifest(project="proj", repo_url=url, commit=shas[0])
    space.write_manifest(stored)
    found = space.restore(space.read_manifest("proj"))
    assert found.ready and found.commit == shas[0]


def test_a_manifest_with_no_repository_cannot_restore_one(space):
    found = space.restore(Manifest(project="proj"))
    assert not found.ready and "no repository" in found.error


def test_a_manifest_whose_repository_could_not_be_read_cannot_restore_one(space):
    from discovery.provenance import UNKNOWN

    found = space.restore(Manifest(project="proj", repo_url=UNKNOWN))
    assert not found.ready and "no repository" in found.error
