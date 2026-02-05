# MCP Action Logger Skill

## Description

This skill logs all MCP tool executions to the Dashboard.md under "Recent Actions". After any MCP action (send_email, post_linkedin, etc.) succeeds or fails, the AI Employee must update the Dashboard to maintain a complete audit trail.

## Trigger Conditions

Execute this skill **immediately after** any MCP tool call completes:
- `send_email` — success or failure
- `check_email_config` — success or failure
- Any future MCP tools added to the system

## Inputs

- MCP tool name that was called
- MCP tool parameters (to, subject, etc.)
- Result from MCP tool (success/failure, messageId, error)
- Current timestamp

## Steps

### Step 1: Capture MCP Result

After calling an MCP tool, capture:
```
tool_name: "send_email"
target: "recipient@example.com"
status: "success" or "failed"
details: messageId or error message
timestamp: current datetime
```

### Step 2: Format Dashboard Entry

Create a table row for Recent Actions:
```markdown
| <timestamp> | <tool_name> | <target> | <status> | <notes> |
```

**Examples:**
```markdown
| 2026-02-05 22:45 | send_email | user@example.com | Success | MessageId: abc123 |
| 2026-02-05 22:46 | send_email | bad@invalid | Failed | Invalid email format |
```

### Step 3: Update Dashboard.md

1. Read Dashboard.md
2. Find the "Recent Actions" table
3. Remove the placeholder row if present (`_No recent actions_`)
4. Insert new row at the top of the table (after header)
5. Save Dashboard.md

### Step 4: Log to System_Log.md

Also add an entry to System_Log.md:
```markdown
| <timestamp> | MCP Action | <tool_name> to <target>: <status> |
```

## Code Pattern for AI Employee

After every MCP tool call, follow this pattern:

```
1. Call MCP tool (e.g., send_email)
2. Capture result
3. IF success:
   - Update Dashboard.md Recent Actions: Success
   - Update System_Log.md
4. IF failure:
   - Update Dashboard.md Recent Actions: Failed + error
   - Update System_Log.md with error details
5. Report result to user
```

## Example Workflow

### User Request
"Send an email to john@example.com with subject 'Weekly Report'"

### AI Employee Actions
```
1. Check Approval_Check_Skill → send_email requires approval
2. If approved, call MCP send_email tool
3. Receive result: { success: true, messageId: "abc-123" }
4. Update Dashboard.md:
   | 2026-02-05 22:50 | send_email | john@example.com | Success | Weekly Report - ID: abc-123 |
5. Update System_Log.md:
   | 2026-02-05 22:50 | MCP Action | send_email to john@example.com: Success |
6. Report to user: "Email sent successfully to john@example.com"
```

## Dashboard Recent Actions Format

The Recent Actions table in Dashboard.md should show the 10 most recent MCP actions:

```markdown
## Recent Actions

| Timestamp | Action | Target | Status | Notes |
|-----------|--------|--------|--------|-------|
| 2026-02-05 23:00 | send_email | alice@co.com | Success | Project update |
| 2026-02-05 22:45 | send_email | bob@test.com | Success | Meeting invite |
| 2026-02-05 22:30 | check_email_config | - | Success | SMTP verified |
```

## Cleanup Rule

Keep only the 10 most recent actions in Dashboard.md. Older entries are preserved in System_Log.md for full audit history.

## Notes

- **Always log**, even if the action failed
- Include enough detail to understand what happened
- The target field should be anonymized if containing sensitive data
- This skill runs automatically — no user trigger needed
- Complements Approval_Check_Skill (approval happens before, logging happens after)
