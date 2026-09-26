# Infrastructure Rules

Applies to `infrastructure/`, `docker-compose.yml`, and CI configuration once they exist. See
`CLAUDE.md` § 7 for the standing no-production-deployment rule this file elaborates.

## Environment separation

```
Development = synthetic data (the LATAM Bank dataset only)
Tests        = synthetic/anonymized data (evaluation/golden_cases/ + sampled dataset)
Evaluation   = approved evaluation data (evaluation/golden_cases/, dataset held-out split)
Production   = enterprise-controlled data — not in scope for this project
```

Never assume a local developer should have access to real customer financial data — there is
none in this project, and no infrastructure here should be built as if there will be.

## Rules

- No production deployment, production database mutation, production credential rotation,
  production IAM change, or infrastructure destruction without explicit user authorization for
  that specific action in that specific request. A development request is never implicit
  authorization for a production action (`CLAUDE.md` § 7).
- Docker Compose is the local development target; there is no staging or production
  environment defined in this repository.
- CI must never require production credentials to run (`prompt.md` § 53) — lint, typecheck,
  unit tests, integration tests (against a local/ephemeral database), and security checks all
  run with no external secrets beyond, at most, a mock-mode LLM configuration.
- `.claude/settings.json` (committed, shared) must never grant blanket permission for
  destructive filesystem operations, production deployments, production database mutations,
  secret access, credential operations, infrastructure destruction, external messaging, or
  financial operations (`CLAUDE.md` § 7; see `.claude/settings.json` itself for the current
  conservative baseline).
- If Terraform or another IaC tool is introduced later, `terraform apply` against anything but
  a local/ephemeral target requires the same explicit-authorization standard as any other
  destructive action.
- Container images are built from pinned dependency versions (once a manifest exists) so a
  build is reproducible; do not float `latest` tags for anything the system depends on for
  correctness.
