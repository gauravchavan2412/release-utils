"""Pipeline step numbers and shared detail strings for the monthly release flow."""

# Ordered steps (see run_monthly_release.py)
STEP_CLEAN_GENERATED = 1
STEP_GENERATE_INPUT_JSON = 2
STEP_FETCH_TICKET_CHANGES = 3
STEP_CREATE_LINEAR_TICKET = 4

# Step 4 — strings written to StepResult.detail (consumed by pipeline._final_status_line)
LINEAR_TICKET_DETAIL_CREATED = "created in Linear"
LINEAR_TICKET_DETAIL_DRY_RUN = "dry-run only — not created in Linear"
LINEAR_TICKET_DETAIL_SKIPPED = "skipped — not created in Linear"
