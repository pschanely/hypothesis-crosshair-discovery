"""Mutations for one run's phases and its deadline."""

from mutation.runner import Mutation, Suite

SUITE = Suite(
    label="driver",
    module="discovery/driver.py",
    tests=["tests/test_driver.py"],
    mutations=[
        Mutation(
            "the deadline is ignored",
            "        if deadline - now() < MIN_PROJECT_SECONDS:",
            "        if False:",
        ),
        Mutation(
            "a project is started with no time left to finish it",
            "        if deadline - now() < MIN_PROJECT_SECONDS:",
            "        if deadline - now() < 0:",
        ),
        Mutation(
            "projects the deadline cut off are not reported at all",
            "            report.unreached = list(projects[index:])",
            "            pass",
        ),
        Mutation(
            "the project that was cut off is reported as having run",
            "            report.unreached = list(projects[index:])",
            "            report.unreached = list(projects[index + 1 :])",
        ),
        Mutation(
            "a project with no checkout is built anyway",
            "        if not checkout.ready:",
            "        if False:",
        ),
        Mutation(
            "a project that could not be built is tested anyway",
            "        if not built.ready:",
            "        if False:",
        ),
        Mutation(
            "a clean room that could not be built is not needed after all",
            "            if not clean.ready:",
            "            if False:",
        ),
        Mutation(
            "the clean room is built with the plugin in it",
            "                plugin=CLEAN_ROOM,",
            "                plugin=None,",
        ),
        Mutation(
            "the clean room is built but never used",
            "            validation_python = clean.python",
            '            validation_python = ""',
        ),
        Mutation(
            "the pipeline is given unlimited time",
            "            deadline - now(),",
            "            9e9,",
        ),
        Mutation(
            "the tests a pipeline names are counted as one",
            "    if isinstance(value, (list, tuple, dict)):\n        return len(value)",
            "    pass",
        ),
        Mutation(
            "a report that cannot be read fails the run",
            "    except (TypeError, ValueError):\n        return 0",
            "    except KeyboardInterrupt:\n        return 0",
        ),
        Mutation(
            "a cut-off pipeline is killed without what it started",
            "        end_process_group(proc)",
            "        proc.kill()",
        ),
        Mutation(
            "a cut-off run leaves its containers running",
            "        if tested.error:\n            reap_containers(run_id)",
            "        pass",
        ),
        Mutation(
            "an attempt that failed reads as having worked",
            "        return not self.error",
            "        return True",
        ),
        Mutation(
            "verdicts from different projects overwrite each other",
            "                total[name] = total.get(name, 0) + count",
            "                total[name] = count",
        ),
        Mutation(
            "a report is written holding nothing",
            "        json.dump(report.as_dict(), handle, indent=1, sort_keys=True)",
            "        json.dump({}, handle, indent=1, sort_keys=True)",
        ),
        Mutation(
            "what the store recorded is never counted",
            '        for payload in store.verdicts(run_id):\n            name = str(payload.get("verdict"))\n            counted[name] = counted.get(name, 0) + 1',
            "        pass",
        ),
        Mutation(
            "a run's verdicts are read without regard to which run they are",
            "        for payload in store.verdicts(run_id):",
            "        for payload in store.verdicts():",
        ),
        Mutation(
            "every project is given the same run id",
            "    return f\"{project}-{commit[:8] or 'nocommit'}\"[:64]",
            '    return "run"',
        ),
        Mutation(
            "a run id ignores the commit, so a new commit resumes the old run",
            "    return f\"{project}-{commit[:8] or 'nocommit'}\"[:64]",
            '    return f"{project}"[:64]',
        ),
        Mutation(
            "the pipeline is never told to continue a run",
            '    if run_id:\n        argv += ["--resume", run_id]',
            "    pass",
        ),
        Mutation(
            "what the run was configured with never reaches the pipeline",
            "    argv += list(extra)",
            "    pass",
        ),
        Mutation(
            "the pipeline runs unsandboxed",
            '        "--sandbox",\n        "docker",',
            '        "--sandbox",\n        "local",',
        ),
        Mutation(
            "the pipeline runs against whatever python it finds",
            '        "--crosshair-python",\n        python,',
            '        "--crosshair-python",\n        "python",',
        ),
        Mutation(
            "verdicts are not kept",
            '        "--store",\n        store_path,',
            '        "--store",\n        "/dev/null",',
        ),
        Mutation(
            "the image the environment was built in is not the one it runs in",
            '        "--image",\n        image,',
            '        "--image",\n        "python:3.12-slim",',
        ),
        Mutation(
            "a pipeline cut off by the deadline reads as having found nothing",
            '        return PipelineResult(\n            error="the deadline arrived while this project was running"\n        )',
            "        return PipelineResult()",
        ),
        Mutation(
            "a pipeline that says nothing readable reads as having found nothing",
            '        return PipelineResult(error=f"the pipeline reported nothing readable: {detail}")',
            "        return PipelineResult()",
        ),
        Mutation(
            "a pipeline that could not start reads as having found nothing",
            "        return PipelineResult(error=str(exc))",
            "        return PipelineResult()",
        ),
        Mutation(
            "the pipeline's own verdicts are never counted",
            '    for entry in payload.get("classifications") or []:\n        name = str(entry.get("verdict"))\n        counted[name] = counted.get(name, 0) + 1',
            "    pass",
        ),
    ],
)
