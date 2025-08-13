ARG PY_VERSION=3.11
# Pin to Debian 11 (bullseye) variant to ensure Microsoft ODBC packages are available
ARG BASE_IMAGE=python:${PY_VERSION}-slim-bullseye
ARG SQL_DEBIAN_VERSION=11

FROM ${BASE_IMAGE} AS builder
RUN apt-get update && apt-get install -y gcc g++ unixodbc-dev curl git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM ${BASE_IMAGE}
ARG SQL_DEBIAN_VERSION=11
RUN apt-get update \
    && apt-get install -y gnupg2 curl \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/${SQL_DEBIAN_VERSION}/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && apt-get remove -y unixodbc unixodbc-dev || true \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 mssql-tools18 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY . .
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
ARG APP_CMD="python main.py"
CMD ["/bin/bash", "-lc", "${APP_CMD}"]