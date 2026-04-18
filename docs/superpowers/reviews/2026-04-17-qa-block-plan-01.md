# QA Block: Plan 01 Scaffolding

Date: 2026-04-17  
Reviewer: Rhea Solis

## Verdict

Blocked. Maya should not execute Plan 01 until the plan is corrected or Iris explicitly records a waiver in the vault.

## Blocking Findings

1. Backend Docker build context is invalid.

   Plan 01 sets the backend Docker build context to `./backend`, but the Dockerfile copies `Cargo.lock` and builds as if it can see the full workspace. In the approved workspace layout, `Cargo.lock` belongs at the repository root, so this Docker build is likely to fail or drift from the local workspace build.

2. Docker Compose omits the proxy promised by the spec and plan.

   Plan 01 says the stack includes `app + db + redis + proxy services`, and the architecture spec requires an Nginx reverse proxy layer. The compose snippet defines only `db`, `redis`, `app`, and `frontend`.

3. Config tests mutate global process environment unsafely.

   The config tests use `std::env::set_var` and `std::env::remove_var` in ordinary tests. Rust tests run concurrently by default, so this can become flaky as the module grows.

## Required Before Unblock

- Fix Docker build context and Dockerfile paths for the root workspace layout, or explicitly make the backend an independent crate and update the plan accordingly.
- Add the proxy service, or explicitly defer proxy setup with vault approval.
- Serialize env-mutating config tests or refactor config loading behind a testable source abstraction.

Vault record: `/mnt/d/Vaults/OfficeVault/02_Projects/RuneChat/09_QA_Block_Plan_01.md`
