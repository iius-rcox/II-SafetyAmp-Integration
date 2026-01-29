ARG PY_VERSION=3.11
# Use Debian 12 (bookworm) - Microsoft ODBC packages are available
# See: https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
ARG BASE_IMAGE=python:${PY_VERSION}-slim-bookworm
ARG SQL_DEBIAN_VERSION=12

FROM ${BASE_IMAGE} AS builder
RUN apt-get update && apt-get install -y gcc g++ unixodbc-dev curl git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Pin setuptools>=78.1.1 and wheel>=0.46.2 to fix CVE-2024-6345, CVE-2025-47273, CVE-2026-24049
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip "setuptools>=78.1.1" "wheel>=0.46.2" \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM ${BASE_IMAGE}
ARG SQL_DEBIAN_VERSION=12

# Install Microsoft ODBC Driver 18 for SQL Server
# See: https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
RUN apt-get update \
    && apt-get install -y --no-install-recommends gnupg2 curl apt-transport-https ca-certificates \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/${SQL_DEBIAN_VERSION}/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 mssql-tools18 libgssapi-krb5-2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade system packages to fix remaining vulnerabilities
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade system Python packages to fix CVE-2026-24049 (wheel) and CVE-2026-23949 (jaraco.context in setuptools)
RUN pip install --no-cache-dir --upgrade "pip>=24.0" "setuptools>=79.0.0" "wheel>=0.46.2"

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY . .

RUN useradd --create-home --shell /bin/bash app \
    && mkdir -p /app/output/changes /app/output/errors /app/output/logs \
    && chown -R app:app /app

USER app

ENV PATH="/opt/venv/bin:/opt/mssql-tools18/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "main.py"]
