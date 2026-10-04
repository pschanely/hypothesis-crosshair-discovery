"""Mutations for the registry of known CrossHair defects."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="defects",
    module="discovery/defects.py",
    tests=["tests/test_defects.py", "tests/test_driver.py"],
    mutations=[
        Mutation(
            "a known defect is reported as new every run",
            "        defect = known.get(sighting.signature)",
            "        defect = None",
        ),
        Mutation(
            "a defect seen again is not reported at all",
            "        elif sighting.signature not in seen_now:\n            changes.still_present.append(defect)",
            "        elif False:\n            pass",
        ),
        Mutation(
            "the same defect in two projects is two entries",
            "        if sighting.project not in defect.projects:\n            defect.projects.append(sighting.project)",
            "        defect.projects.append(sighting.project)",
        ),
        Mutation(
            "absence is called a fix without looking everywhere",
            "        looked_everywhere = set(defect.projects) <= covered",
            "        looked_everywhere = True",
        ),
        Mutation(
            "absence on the same version is called a fix",
            "        if looked_everywhere and version and version != defect.last_version:",
            "        if looked_everywhere:",
        ),
        Mutation(
            "a defect that was not seen is quietly forgotten",
            "        else:\n            changes.unverified.append(defect)",
            "        else:\n            pass",
        ),
        Mutation(
            "a defect that came back is still recorded as gone",
            '        defect.gone_since = ""\n        if sighting.project not in defect.projects:',
            "        if sighting.project not in defect.projects:",
        ),
        Mutation(
            "a defect already gone is reported gone again every run",
            "        if defect.signature in seen_now or not defect.present:",
            "        if defect.signature in seen_now:",
        ),
        Mutation(
            "the registry a caller passed in is changed under it",
            "        defect.signature: replace(defect, projects=list(defect.projects))\n        for defect in defects",
            "        defect.signature: defect\n        for defect in defects",
        ),
        Mutation(
            "what a person wrote is overwritten by the run",
            "        defect.last_seen = day",
            '        defect.last_seen = day\n        defect.status = SUSPECTED\n        defect.issue = ""',
        ),
        Mutation(
            "a timeout counts as a defect",
            'ATTRIBUTABLE = frozenset({"crosshair_false_positive", "crosshair_crash"})',
            'ATTRIBUTABLE = frozenset(\n    {"crosshair_false_positive", "crosshair_crash", "crosshair_timeout"}\n)',
        ),
        Mutation(
            "a trophy counts as a defect",
            '    attributed = {\n        str(entry.get("nodeid"))\n        for entry in payload.get("classifications") or []\n        if str(entry.get("verdict")) in ATTRIBUTABLE\n    }',
            '    attributed = {\n        str(entry.get("nodeid")) for entry in payload.get("classifications") or []\n    }',
        ),
        Mutation(
            "a cluster no verdict attributes is recorded anyway",
            "        if not attributed.intersection(nodeids):\n            continue",
            "        if False:\n            continue",
        ),
        Mutation(
            "two different failures share one signature",
            '        signature = Signature(\n            str(group.get("exception_type") or ""),\n            str(group.get("frame") or ""),\n            str(group.get("message") or ""),\n        )',
            '        signature = Signature("", "", "")',
        ),
        Mutation(
            "the cluster's exception type is read from the wrong key",
            '            str(group.get("exception_type") or ""),',
            '            str(group.get("exception") or ""),',
        ),
        Mutation(
            "a cluster's tests are read from the wrong key",
            '        nodeids = [str(n) for n in group.get("nodeids") or []]',
            '        nodeids = [str(n) for n in group.get("tests") or []]',
        ),
        Mutation(
            "a classification's verdict is read from the wrong key",
            '        if str(entry.get("verdict")) in ATTRIBUTABLE',
            '        if str(entry.get("category")) in ATTRIBUTABLE',
        ),
        Mutation(
            "clusters are read from the wrong key",
            '    for group in payload.get("clusters") or []:',
            '    for group in payload.get("failures") or []:',
        ),
        Mutation(
            "a registry written by other code is read anyway",
            '    if not isinstance(raw, dict) or raw.get("version") != REGISTRY_VERSION:\n        return []',
            "    if not isinstance(raw, dict):\n        return []",
        ),
        Mutation(
            "an entry with no signature is loaded as a defect",
            '        if isinstance(entry, dict) and entry.get("signature"):',
            "        if isinstance(entry, dict):",
        ),
        Mutation(
            "a registry that cannot be read raises instead of reading as empty",
            "    except (OSError, ValueError):\n        return []",
            "    except OSError:\n        return []",
        ),
        Mutation(
            "a defect that is gone still sorts with the live ones",
            '    ordered = sorted(defects, key=lambda d: (d.gone_since != "", d.last_seen))',
            "    ordered = sorted(defects, key=lambda d: d.last_seen)",
        ),
        Mutation(
            "the version a defect was first seen on is not recorded",
            "                first_version=version,",
            '                first_version="",',
        ),
    ],
)
