# Stability and UX Maintenance Implementation Plan

> Execute with test-driven-development and subagent-driven-development. User approved fixing the reproduced issues and continuing exploratory testing on 2026-10-22. Preserve the original delivery folder; implement in the GitHub checkout on a maintenance branch.

**Goal:** Correct inconsistent scoring, narrow-screen layouts, blank inputs, configuration and AI request handling; test and document further bugs and usability limits.

**Architecture:** Keep FastAPI routers and the existing React five-step flow. Share backend scoring/configuration helpers rather than duplicating rules. Preserve the blue/gold visual identity; introduce reusable responsive layout classes. Invalidate dependent outputs when user inputs or the selected job change, and retain report state when navigating between steps.

**Tech Stack:** FastAPI, Pydantic, React 18, Vite 5, pytest, HTTPX, Playwright.

## Backend task

- [x] Add failing offline tests for fixed-weight scoring and invalid scores, root-directory data loading, model status/key privacy, whitespace input rejection and JSON text preservation.
- [x] Run tests and record the reproduced failures before implementation.
- [x] Implement shared backend configuration and score normalization; use the canonical score for report context and exports.
- [x] Reject blank required input, align provider status with actual selection, remove returned key fragments.
- [x] Offload synchronous AI calls from async request handlers; verify concurrent basic endpoints remain responsive using controlled test responses.
- [x] Run backend regression tests with network-free model substitutes; summarize remaining risks.

## Frontend task

- [x] Add browser regressions that fail on pure whitespace, 390px and 320px layouts, stale downstream state after editing, and lost report state on navigation.
- [x] Verify the failures against the old code.
- [x] Implement trimmed form validation; adapt header, navigation, forms, grids, report actions and graph layouts for narrow screens.
- [x] Reset dependent results after editing upstream information or changing target jobs; retain report state in the parent and keep visited steps reachable.
- [x] Display structured validation errors and partial report failures, and surface polishing errors rather than swallowing them.
- [x] Run browser regressions with saved fictional model responses, build the frontend, then test the repaired backend with the full local data and limited real DeepSeek calls.

## Verification and synchronization

- [x] Add reproducible development test commands and GitHub Actions for backend checks and frontend build.
- [x] Record actual checks, confirmed remaining bugs, and experience limits. Keep credentials/full delivery data/generated artifacts outside commits.
- [x] Obtain independent review, resolve actionable findings, and rerun affected checks.
- [ ] Commit and push the maintenance branch and provide an updated pull request covering the final implementation.
