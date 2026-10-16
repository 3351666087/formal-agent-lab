# Office relocation workflow model

The relocation advances through six ordered phases; the project succeeds when `records_shipped` becomes true. Each task completes one phase and can be used only when the previous phase is reached and none of its blocking policies is in force.

**Phases in order**: project_kickoff -> site_survey -> access_badges -> floor_access -> archive_access -> records_shipped (goal: records_shipped)

**Policies** (each policy in force blocks the tasks listed against it):
- registry_locked: copy_from_registry
- archive_approval: query_archive_index
- courier_a_tracking: ship_via_courier_a
- visitor_log_off: review_visitor_log
- mail_scanning: invite_contractor
- corridor_partition: use_service_corridor
- terminal_maintenance: reuse_legacy_terminal
- courier_b_inspection: ship_via_courier_b
- backup_isolated: read_backup_copy
- staff_training: invite_contractor
- remote_pass_mfa: use_remote_pass
- gate_inspection: reuse_legacy_terminal

**Policies in force**: none

**Tasks**:
- `reuse_legacy_terminal` — completes project_kickoff (after start); blocked by terminal_maintenance, gate_inspection
- `invite_contractor` — completes project_kickoff (after start); blocked by mail_scanning, staff_training
- `walkthrough_survey` — completes site_survey (after project_kickoff); blocked by (nothing)
- `copy_from_registry` — completes access_badges (after site_survey); blocked by registry_locked
- `review_visitor_log` — completes access_badges (after site_survey); blocked by visitor_log_off
- `use_service_corridor` — completes floor_access (after access_badges); blocked by corridor_partition
- `use_remote_pass` — completes floor_access (after access_badges); blocked by remote_pass_mfa
- `query_archive_index` — completes archive_access (after floor_access); blocked by archive_approval
- `read_backup_copy` — completes archive_access (after floor_access); blocked by backup_isolated
- `ship_via_courier_a` — completes records_shipped (after archive_access); blocked by courier_a_tracking
- `ship_via_courier_b` — completes records_shipped (after archive_access); blocked by courier_b_inspection

## Question
With no policies in force, what is the minimum number of tasks needed to ship the records (records_shipped)? Count every task, including the final one.
