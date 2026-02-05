# Approval Handler Skill

## Description

This skill **polls the `/Pending_Approval/` directory** for tasks that a human has reviewed and approved. When it finds a task with `approved: true` in its YAML frontmatter, it executes the gated MCP action, moves the task forward, and updates the Dashboard and System Log. It also handles rejected tasks by archiving them to `/Done/`.

This is the **second half** of the human-in-the-loop workflow. The `Approval_Check_Skill` gates tasks into `/Pending_Approval/`; this skill processes them out.

## Position in Reasoning Loop

```
[Human reviews /Pending_Approval/task.md]
    --> Sets approved: true (or status: rejected)

[AI Employee reasoning loop starts]
    --> ** APPROVAL HANDLER (this skill) **
        --> Scan /Pending_Approval/ for changes
        --> approved: true   --> Execute MCP action --> Move to /Done/
        --> status: rejected --> Move to /Done/ (no execution)
        --> neither          --> Skip (still waiting for human)
```

**This skill runs at the START of each reasoning loop cycle**, before planning or executing new tasks.

---

## Trigger Conditions

Run this skill:
- At the beginning of every reasoning loop iteration
- When the user says: "Check approvals", "Process approved tasks", "Handle pending approvals"
- When the scheduler triggers a periodic check
- Manually, when the user indicates they have approved/rejected tasks

---

## Steps

### Step 1: Scan /Pending_Approval/ Directory

```
List all .md files in /Pending_Approval/
If directory is empty or does not exist:
    Log: "No pending approvals to process"
    Exit skill
```

### Step 2: Read Each Task and Check Status

For each file in `/Pending_Approval/`:

1. Parse YAML frontmatter
2. Check the `approved` and `status` fields
3. Classify the task:

| Condition | Classification | Action |
|-----------|---------------|--------|
| `approved: true` | **Approved** | Execute MCP action |
| `status: rejected` | **Rejected** | Archive to /Done/ |
| `approved: false` and `status: pending_approval` | **Waiting** | Skip — still awaiting human decision |

### Step 3A: Handle Approved Tasks

For tasks where `approved: true`:

1. **Read the full task** to extract MCP action details (recipient, subject, body, etc.)

2. **Execute the MCP action**:
   ```
   Call the MCP tool specified in mcp_action[]
   Example: mcp__silver-email__send_email(to, subject, body)
   ```

3. **Update the task YAML**:
   ```yaml
   ---
   status: completed
   approved: true
   approval_needed: true
   completed_at: 2026-02-05 23:30:00
   execution_result: "Success - email sent (ID: abc123)"
   ---
   ```

4. **Move to /Done/**:
   ```
   Source: /Pending_Approval/[task].md
   Target: /Done/[task].md
   ```

5. **Update Dashboard.md**:
   - Remove the task from the **Pending Approval** table
   - Add the task to the **Completed Tasks** table
   - Note: "Approved and executed"

6. **Log to System_Log.md**:
   ```
   | 2026-02-05 23:30 | Approval Executed | Task "Send Summary Email" approved — send_email executed successfully (ID: abc123) |
   ```

7. **Log the MCP action** via `MCP_Action_Logger_Skill` conventions:
   ```
   | 2026-02-05 23:30 | MCP Action | send_email to client@example.com: Success (ID: abc123) |
   ```

### Step 3B: Handle Rejected Tasks

For tasks where `status: rejected`:

1. **Update the task YAML**:
   ```yaml
   ---
   status: rejected
   approved: false
   completed_at: 2026-02-05 23:30:00
   ---
   ```

2. **Move to /Done/**:
   ```
   Source: /Pending_Approval/[task].md
   Target: /Done/[task].md
   ```

3. **Update Dashboard.md**:
   - Remove the task from the **Pending Approval** table
   - Add to **Completed Tasks** with note: "Rejected by user — not executed"

4. **Log to System_Log.md**:
   ```
   | 2026-02-05 23:30 | Approval Rejected | Task "Send Summary Email" rejected by user — MCP action not executed |
   ```

### Step 3C: Handle Waiting Tasks

For tasks still waiting (`approved: false`, `status: pending_approval`):
- **Do nothing** — the task stays in `/Pending_Approval/`
- Optionally log a reminder if `awaiting_approval_since` is older than 24 hours:
  ```
  | 2026-02-06 23:00 | Approval Reminder | Task "Send Summary Email" has been awaiting approval for 24+ hours |
  ```

### Step 4: Handle Execution Failures

If the MCP action fails after approval:

1. **Do NOT move to /Done/** — keep in `/Pending_Approval/`
2. **Update YAML**:
   ```yaml
   ---
   status: execution_failed
   execution_result: "Error: SMTP connection refused"
   retry_count: 1
   ---
   ```
3. **Log the failure**:
   ```
   | 2026-02-05 23:30 | Execution Failed | Task "Send Summary Email" approved but send_email failed: SMTP connection refused |
   ```
4. **Update Dashboard** Pending Approval table with status note: "Approved - execution failed"
5. The user can review the error and re-trigger by resetting `status: pending_approval`

---

## Example: Full Approval Cycle

### 1. Task arrives in /Pending_Approval/ (set by Approval_Check_Skill)

`/Pending_Approval/task_send_client_summary.md`:
```yaml
---
type: external_communication
status: pending_approval
priority: medium
created_at: 2026-02-05 22:00:00
related_files: ["Inbox/client_notes.txt"]
approval_needed: true
approved: false
mcp_action: ["send_email"]
approval_reason: "send_email requires human approval before execution"
awaiting_approval_since: 2026-02-05 23:00:00
---

# Send Summary Email to Client

## Email Details
- **To:** client@example.com
- **Subject:** Your Project Notes Summary
- **Body:** Here is a summary of your project notes...
```

### 2. Human approves (edits the file)

User changes one line in the YAML:
```yaml
approved: true
```

### 3. Approval Handler detects and executes

- Reads task, sees `approved: true`
- Calls `mcp__silver-email__send_email(to: "client@example.com", subject: "Your Project Notes Summary", body: "...")`
- On success: updates YAML, moves to `/Done/`, updates Dashboard and Log

### 4. Final state in /Done/

`/Done/task_send_client_summary.md`:
```yaml
---
type: external_communication
status: completed
priority: medium
created_at: 2026-02-05 22:00:00
completed_at: 2026-02-05 23:30:00
related_files: ["Inbox/client_notes.txt"]
approval_needed: true
approved: true
mcp_action: ["send_email"]
execution_result: "Success - email sent (ID: abc123)"
---
```

---

## Dashboard Integration

The **Pending Approval** section in `Dashboard.md` is the user's primary view:

```markdown
## Pending Approval

| Task | Action | Flagged | Status | Location |
|------|--------|---------|--------|----------|
| Send Client Summary | send_email | 2026-02-05 23:00 | Awaiting | [[Pending_Approval/task_send_client_summary.md]] |
```

After processing, the row is removed and the task appears under **Completed Tasks**.

---

## Integration with Other Skills

| Skill | Relationship |
|-------|-------------|
| `Approval_Check_Skill` | Gates tasks INTO `/Pending_Approval/` — this skill processes them OUT |
| `Plan_Tasks_Skill` | Plans flag tasks needing approval as "Batch 2: Needs Approval" |
| `MCP_Action_Logger_Skill` | This skill logs MCP actions after successful execution |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `/Pending_Approval/` does not exist | Create it, log "No pending approvals" |
| Task YAML is malformed | Skip task, log warning, leave file in place |
| MCP action fails | Keep in `/Pending_Approval/`, update YAML with error, log failure |
| Task has no `mcp_action` field | Skip task, log warning |
| Multiple `mcp_action` entries | Execute all in order; if any fails, stop and report |
| Task is older than 48 hours without decision | Log a stale-approval reminder |

---

## Notes

- This skill never executes an MCP action unless `approved: true` is explicitly set by the human
- The human's edit of the YAML file is the **only** authorization path
- If execution fails, the task remains in `/Pending_Approval/` for re-review
- Rejected tasks are archived cleanly with no MCP side effects
- Always check for approvals before starting new work in the reasoning loop
