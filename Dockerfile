# syntax=docker/dockerfile:1.7

FROM golang:1.22.5-bookworm AS osv_builder
ARG OSV_SCANNER_VERSION=v1.9.0
RUN go install github.com/google/osv-scanner/cmd/osv-scanner@${OSV_SCANNER_VERSION}

FROM python:3.12.6-slim-bookworm

ARG UV_VERSION=0.10.4
ARG SEMGREP_VERSION=1.101.0
ARG BANDIT_VERSION=1.7.10
ARG RIPGREP_VERSION=13.0.0-4+b2

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        ripgrep=${RIPGREP_VERSION} \
    && rm -rf /var/lib/apt/lists/*

COPY --from=osv_builder /go/bin/osv-scanner /usr/local/bin/osv-scanner

RUN pip install --no-cache-dir \
      uv==${UV_VERSION} \
      semgrep==${SEMGREP_VERSION} \
      bandit==${BANDIT_VERSION}

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config

RUN uv sync --frozen --no-dev

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/app/.venv/bin/python", "-m", "repoclinic", "healthcheck", "--quiet"]

ENTRYPOINT ["/app/.venv/bin/python", "-m", "repoclinic"]
CMD ["--help"]
