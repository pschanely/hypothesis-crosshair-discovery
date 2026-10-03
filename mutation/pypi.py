"""Mutations for the PyPI prefilter."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="pypi",
    module="discovery/pypi.py",
    tests=["tests/test_pypi.py"],
    mutations=[
        Mutation(
            "a package with no wheel reads as pure python",
            "        if not self.wheel_tags:\n            return None",
            "        if not self.wheel_tags:\n            return True",
        ),
        Mutation(
            "any wheel at all reads as pure python",
            '        return self.wheel_tags == {"any"}',
            '        return "any" in self.wheel_tags',
        ),
        Mutation(
            "an unknown build scores the same as a pure one",
            '        points += PREFILTER_WEIGHTS["pure_python"] / 2',
            '        points += PREFILTER_WEIGHTS["pure_python"]',
        ),
        Mutation(
            "an array dependency costs nothing",
            '    if not facts.opaque_dependencies:\n        points += PREFILTER_WEIGHTS["no_opaque_dependency"]',
            '    if True:\n        points += PREFILTER_WEIGHTS["no_opaque_dependency"]',
        ),
        Mutation(
            "a version marker stays part of the dependency name",
            '    for separator in (";", "[", "(", "=", "<", ">", "!", "~", " ", "#"):',
            '    for separator in (";",):',
        ),
        Mutation(
            "an extras bracket stays part of the dependency name",
            '    for separator in (";", "[", "(", "=", "<", ">", "!", "~", " ", "#"):',
            '    for separator in ("=", "<", ">"):',
        ),
        Mutation(
            "the tracker url is taken before the source url",
            "    for url in preferred + rest:",
            "    for url in rest + preferred:",
        ),
        Mutation(
            "a page about a repository is cloned as if it were one",
            "        if segment.lower() in NON_REPO_SEGMENTS:\n            break",
            "        if False:\n            break",
        ),
        Mutation(
            "a .git suffix is kept",
            '    if trimmed.endswith(".git"):\n        trimmed = trimmed[: -len(".git")]',
            "    if False:\n        pass",
        ),
        Mutation(
            "the home page is ignored",
            '    for key in ("home_page", "download_url"):\n        if info.get(key):\n            rest.append(info[key])',
            "    for key in ():\n        if info.get(key):\n            rest.append(info[key])",
        ),
        Mutation(
            "a url on any host counts as a repository",
            "        if isinstance(url, str) and any(host in url for host in VCS_HOSTS):",
            "        if isinstance(url, str):",
        ),
        Mutation(
            "a package with nowhere to clone is kept",
            "    clonable = [facts for facts in every if facts.repo_url]",
            "    clonable = list(every)",
        ),
        Mutation(
            "the budget drops packages permanently rather than cutting a line",
            "    return unique[:budget] if budget else unique",
            "    return unique[:budget]",
        ),
        Mutation(
            "downloads outrank fitness",
            "    clonable.sort(key=lambda facts: (-score(facts), -facts.downloads, facts.name))",
            "    clonable.sort(key=lambda facts: (-facts.downloads, -score(facts)))",
        ),
        Mutation(
            "the cache is ignored and a request is made anyway",
            "    if cached and os.path.exists(cached):",
            "    if False:",
        ),
        Mutation(
            "two packages from one repository are cloned twice",
            "        seen.setdefault(facts.repo_url, facts)",
            "        seen[facts.repo_url] = facts",
        ),
        Mutation(
            "deduplication keeps the worst package for a repository",
            "    for facts in clonable:\n        seen.setdefault(facts.repo_url, facts)",
            "    for facts in reversed(clonable):\n        seen[facts.repo_url] = facts",
        ),
        Mutation(
            "the budget is applied before deduplication",
            "    unique = list(seen.values())\n    return unique[:budget] if budget else unique",
            "    return list(seen.values())",
        ),
    ],
)
