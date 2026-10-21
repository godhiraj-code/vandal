FROM mcr.microsoft.com/playwright/python:v1.64.0-noble
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
