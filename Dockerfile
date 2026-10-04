# The environment third-party test suites are built and run in.
#
# Nothing of this project is copied in: the orchestrator stays on the host
# and only ever runs commands here, so the image holds an interpreter, uv,
# and nothing else worth attacking. A project needing a compiler to build
# will fail to build and run from its checkout instead.
FROM python:3.12-slim

RUN pip install --no-cache-dir --root-user-action=ignore uv

# The sandbox mounts the image read-only with a tmpfs at /tmp, so every
# cache a tool reaches for has to point there or the tool fails to start.
ENV HOME=/tmp \
    UV_CACHE_DIR=/tmp/uv-cache \
    XDG_CACHE_HOME=/tmp/cache \
    PIP_CACHE_DIR=/tmp/pip-cache \
    PYTHONDONTWRITEBYTECODE=1
