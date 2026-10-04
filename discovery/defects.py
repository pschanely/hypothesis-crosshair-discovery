"""What is already known to be wrong with CrossHair, and whether it still is.

A defect found in one project is found again in every project that exercises
the same code, every night. Without somewhere to remember it, a run reports
the same four things as new for months and stops being worth reading.

The registry is a file in the workspace rather than a table, because a
person adds to it: the loop records what it saw, and a person writes in the
issue it was filed as and anything it learned. A run never removes an entry.

What makes this loop different from the trophy one is that it can close
itself. A verdict is cached under the CrossHair version that produced it, so
a release invalidates every one of them and the next run re-tests every
known defect. A defect that stops reproducing on a newer version is evidence
the fix landed, obtained without asking anyone.

That evidence is only good if the run actually looked. A defect seen in
three projects, two of which the window never reached, has not stopped
reproducing -- it has not been tested. Absence counts only where coverage is
complete and the version has moved, and is reported as unverified otherwise.
"""

import datetime
import json
import os
from dataclasses import asdict, dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .cluster import Signature
from .triage import signature_key

#: Classifier verdicts that make a cluster CrossHair's without triage.
#:
#: A false positive is a failure the clean room did not reproduce, and a
#: crash is the solver failing outright. Both are malfunctions on the
#: pipeline's own evidence. A timeout or a no_signal is not: those say the
#: search was hard, which is a fact about the problem, not a defect.
ATTRIBUTABLE = frozenset({"crosshair_false_positive", "crosshair_crash"})

SUSPECTED = "suspected"

#: Statuses a person writes in. The loop never sets them.
HUMAN_STATUSES = ("filed", "fixed", "wontfix")

REGISTRY_VERSION = 1


@dataclass
class Sighting:
    """One cluster, in one project, on one version."""

    signature: str
    exception_type: str
    frame: str
    message: str
    project: str
    sample: str = ""
    nodeids: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return Signature(self.exception_type, self.frame, self.message).describe()


@dataclass
class Defect:
    """A known CrossHair or plugin defect, and where it has been seen."""

    signature: str
    summary: str = ""
    status: str = SUSPECTED
    first_seen: str = ""
    last_seen: str = ""
    first_version: str = ""
    last_version: str = ""
    #: The version it stopped reproducing on, once a run has looked properly.
    gone_since: str = ""
    projects: List[str] = field(default_factory=list)
    sample: str = ""
    #: Written by a person: where it was filed, and anything learned.
    issue: str = ""
    note: str = ""

    @property
    def present(self) -> bool:
        return not self.gone_since

    def describe(self) -> str:
        where = f"{len(self.projects)} project(s)"
        if self.gone_since:
            return (
                f"{self.signature} gone since {self.gone_since}: {self.summary} "
                f"(seen {self.first_seen} to {self.last_seen}, {where})"
            )
        filed = f" [{self.issue}]" if self.issue else ""
        return (
            f"{self.signature} {self.status}{filed}: {self.summary} "
            f"(since {self.first_seen} on {self.first_version}, {where})"
        )


@dataclass
class Changes:
    """What one run did to the registry."""

    new: List[Defect] = field(default_factory=list)
    still_present: List[Defect] = field(default_factory=list)
    gone: List[Defect] = field(default_factory=list)
    #: Known defects this run did not see, but did not look everywhere for.
    unverified: List[Defect] = field(default_factory=list)

    def describe(self) -> List[str]:
        lines = []
        for defect in self.new:
            lines.append(f"  new      {defect.describe()}")
        for defect in self.gone:
            lines.append(f"  gone     {defect.describe()}")
        for defect in self.still_present:
            lines.append(f"  present  {defect.describe()}")
        if self.unverified:
            lines.append(
                f"  {len(self.unverified)} known defect(s) not looked for in "
                "every project that shows them"
            )
        return lines


def sightings_from(rows: Iterable[dict], project: str) -> List[Sighting]:
    """CrossHair's own failures among the ones a run recorded.

    Read from the store rather than from a finished run's report, because
    the projects that produce the most defects are the slow ones, and those
    are the ones a window is most likely to cut off. A report arrives only
    when a run finishes; these rows are written as each test retires.
    """
    found = []
    for row in rows:
        if str(row.get("verdict")) not in ATTRIBUTABLE:
            continue
        signature = Signature(
            str(row.get("exception") or ""),
            str(row.get("frame") or ""),
            str(row.get("message") or ""),
        )
        found.append(
            Sighting(
                signature=signature_key(signature),
                exception_type=signature.exception_type,
                frame=signature.frame,
                message=signature.message,
                project=project,
                sample=str(row.get("sample") or ""),
                nodeids=[str(row.get("nodeid") or "")],
            )
        )
    return found


def load(path: str) -> List[Defect]:
    """Every defect recorded, or nothing if there is no readable registry."""
    try:
        with open(path) as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(raw, dict) or raw.get("version") != REGISTRY_VERSION:
        return []
    fields = set(Defect.__dataclass_fields__)
    found = []
    for entry in raw.get("defects") or []:
        if isinstance(entry, dict) and entry.get("signature"):
            found.append(Defect(**{k: v for k, v in entry.items() if k in fields}))
    return found


def save(path: str, defects: Sequence[Defect]) -> str:
    """Write the registry, newest sighting first."""
    ordered = sorted(defects, key=lambda d: (d.gone_since != "", d.last_seen))
    with open(path, "w") as handle:
        json.dump(
            {
                "version": REGISTRY_VERSION,
                "defects": [asdict(defect) for defect in ordered],
            },
            handle,
            indent=1,
            sort_keys=True,
        )
    return path


def update(
    defects: Sequence[Defect],
    sightings: Iterable[Sighting],
    *,
    covered: Set[str],
    version: str,
    today: Optional[str] = None,
) -> Tuple[List[Defect], Changes]:
    """Fold a run's sightings into the registry, and say what changed.

    Returns the registry as it now stands and the changes, so the caller
    writes one and reports the other.
    """
    day = today or datetime.date.today().isoformat()
    # Copied, so a caller that keeps the registry it passed in still holds
    # what the run started from rather than what the run concluded.
    known: Dict[str, Defect] = {
        defect.signature: replace(defect, projects=list(defect.projects))
        for defect in defects
    }
    changes = Changes()
    seen_now: Set[str] = set()

    for sighting in sightings:
        defect = known.get(sighting.signature)
        if defect is None:
            defect = Defect(
                signature=sighting.signature,
                summary=sighting.summary,
                first_seen=day,
                first_version=version,
                sample=sighting.sample,
            )
            known[defect.signature] = defect
            changes.new.append(defect)
        elif sighting.signature not in seen_now:
            changes.still_present.append(defect)
        seen_now.add(sighting.signature)
        defect.last_seen = day
        defect.last_version = version
        # It came back, so whatever a previous run concluded was wrong.
        defect.gone_since = ""
        if sighting.project not in defect.projects:
            defect.projects.append(sighting.project)

    for defect in known.values():
        if defect.signature in seen_now or not defect.present:
            continue
        looked_everywhere = set(defect.projects) <= covered
        # On the same version a failure to reproduce says nothing: the search
        # is not reproducible, so only a version that has moved is evidence.
        if looked_everywhere and version and version != defect.last_version:
            defect.gone_since = version
            changes.gone.append(defect)
        else:
            changes.unverified.append(defect)
    return list(known.values()), changes
