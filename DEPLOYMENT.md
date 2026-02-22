# Deployment

## 1) Deployment strategy

RepoClinic is a CLI-first workload with deterministic scanning and optional model-backed branch analysis. The practical production baseline is a containerized deployment with persistent storage for artifacts and SQLite state.

## 2) Viable deployment targets

### A) Single VM with Docker (recommended baseline)

Use when operating a small team or internal service:

- Host RepoClinic container
- Mount persistent directories for artifacts and SQLite DB
- Optionally run local Langfuse (`docker-compose.langfuse.yml`) on the same VM

Suitable for AWS EC2, GCP Compute Engine, or Azure Virtual Machines.

### B) Managed container platform

Use when centralized operations are required:

- AWS ECS/Fargate
- Azure Container Apps
- Google Cloud Run jobs (for bounded run durations)
- Render/Fly.io worker-style workloads for smaller usage profiles

For this mode, persist artifacts to object storage and move state from SQLite to managed databases if horizontal scaling is needed.

## 3) Baseline production checklist

- Use image built from repository `Dockerfile`.
- Inject secrets via platform secret manager (not in committed files).
- Mount persistent volume for artifact output.
- Restrict outbound network egress to required endpoints only.
- Configure CPU/memory based on repository size profile.
- Keep tool versions pinned and roll updates through controlled image releases.

## 4) Langfuse in production

- `LANGFUSE_HOST` should target your deployed Langfuse endpoint.
- `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` should be provisioned per environment.
- For self-hosted Langfuse, prefer managed Postgres/ClickHouse/Redis/Blob storage for durability.

## 5) Example release flow

1. Run local verification (`make check` and representative CLI runs).
2. Build image (`make docker-build`).
3. Push image to registry.
4. Deploy to target environment with environment-specific secret injection.
5. Run post-deploy smoke test (`healthcheck`, one small analyze run, artifact validation).
