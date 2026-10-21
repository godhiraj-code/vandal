# Resolved by Docker CI job 119232982704 at 2026-10-21T12:53:48Z (head 6b4743a).
FROM mcr.microsoft.com/playwright/python:v1.64.0-noble@sha256:684df257a1fa0ef3fa288239819984008f560e8f8db5b635ee9e2a50cbcd2e23
RUN apt-get update && apt-get install -y --no-install-recommends python3.12-venv && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
# Only owned project files enter the image. Root .dockerignore is allowlist-only.
COPY pyproject.toml README.md LICENSE /package/
COPY vandal /package/vandal/
RUN python -m pip wheel --wheel-dir=/opt/wheels /package pytest-playwright==0.10.0 playwright==1.64.0
COPY study/*.py /opt/study/
RUN useradd --uid 10001 --create-home study
USER 10001:10001
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
CMD ["python", "-m", "study.worker"]
