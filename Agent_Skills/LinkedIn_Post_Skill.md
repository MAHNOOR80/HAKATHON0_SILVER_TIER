# LinkedIn Post Skill

## Description

This skill generates professional LinkedIn posts designed to promote consulting services, showcase expertise, and drive inbound business leads. Every post is routed through the **Approval Check gate** (`approval_needed: true`) before publishing — the human always reviews and approves the draft first.

This skill handles the full lifecycle: trigger detection, content generation, task creation with draft, approval gating, and Dashboard visibility.

## Position in Reasoning Loop

```
[Trigger detected]
    --> LinkedIn_Post_Skill generates draft
    --> Task file created in /Needs_Action/ with draft content
    --> Approval_Check_Skill gates it (post_linkedin requires approval)
    --> Task moved to /Pending_Approval/
    --> Dashboard updated with draft preview
    --> STOP — human reviews draft
    --> Human approves (approved: true) or rejects (status: rejected)
    --> Approval_Handler_Skill executes post_linkedin(content) or archives
    --> MCP_Action_Logger_Skill logs result
```

---

## Trigger Conditions

Activate this skill when any of the following occur:

### Manual Triggers
- User says: "Post to LinkedIn", "Create a LinkedIn post", "Promote on LinkedIn"
- User says: "Generate a sales post", "Write a business post"
- A task in `/Needs_Action/` has `mcp_action: ["post_linkedin"]`

### Scheduled Triggers
- Weekly cadence (e.g., every Monday and Thursday)
- After completing a client deliverable (milestone post)
- When the scheduler detects a `linkedin_post` task type is due

### Business Event Triggers
- New service offering added to Company_Handbook
- Client project completed successfully (celebrate wins)
- Industry trend or news relevant to services (thought leadership)
- Portfolio or case study update

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| Post topic or theme | User request, task file, or auto-detected event | Yes |
| Target audience | Company_Handbook, task description, or default (business professionals) | No — defaults apply |
| Tone | Default: professional, approachable | No |
| Hashtags | Auto-generated based on topic | No |
| Call to action | Default: soft CTA | No |

---

## Steps

### Step 1: Identify Post Topic

Determine the content theme from the trigger source:

```
IF user provided a topic:
    Use their topic directly
ELSE IF triggered by business event:
    Extract context from the completed task or event
ELSE IF scheduled:
    Rotate through content pillars:
        1. Service showcase (what we offer)
        2. Expertise/thought leadership (industry insights)
        3. Client success stories (anonymized if needed)
        4. Tips and value content (actionable advice)
        5. Availability/CTA (open for new projects)
```

### Step 2: Generate Post Draft

Compose a LinkedIn post following these guidelines:

**Structure:**
```
[Hook — first 2 lines that appear before "...see more"]

[Body — 3-6 short paragraphs, each 1-2 sentences]

[Call to action — soft, not pushy]

[Hashtags — 3-5 relevant tags]
```

**Writing Rules:**
- **Hook**: Lead with a bold statement, question, or insight — this is what appears in the feed preview
- **Line breaks**: Use single-line paragraphs for readability (LinkedIn wraps densely)
- **Tone**: Professional but human — avoid corporate jargon, sound like a real person
- **Length**: 800-1300 characters (LinkedIn sweet spot for engagement)
- **No emojis** unless the user explicitly requests them
- **CTA**: End with a soft call to action (DM me, link in comments, let's connect) — never hard-sell
- **Hashtags**: 3-5 relevant tags at the end, mix of broad (#Business) and niche (#FreelanceConsulting)

### Step 3: Create Task File

Create a task file in `/Needs_Action/` with the draft embedded:

```yaml
---
type: linkedin_post
status: pending
priority: medium
created_at: <timestamp>
related_files: []
approval_needed: true
approved: false
mcp_action: ["post_linkedin"]
post_topic: "<topic summary>"
content_pillar: "service_showcase | thought_leadership | client_success | tips_value | availability"
---
```

**Task body contains the full draft:**

```markdown
# LinkedIn Post: <Topic>

## Draft Content

<the generated post text goes here — this is what will be published>

## Post Metadata

- **Content Pillar:** Service Showcase
- **Target Audience:** Business professionals, potential clients
- **Estimated Read Time:** < 1 min
- **Character Count:** ~1000

## Approval Notes

- Review the draft for accuracy and tone
- Edit the Draft Content section directly if changes are needed
- Set `approved: true` in the YAML to publish
- Set `status: rejected` to discard
```

### Step 4: Approval Gate (Automatic)

The `Approval_Check_Skill` will intercept this task because `mcp_action` contains `post_linkedin`:

1. YAML updated: `status: pending_approval`
2. Task moved to `/Pending_Approval/task_linkedin_<topic>.md`
3. Dashboard updated with draft preview

**The post is NOT published at this point.**

### Step 5: Update Dashboard

Add the draft to the **Pending Approval** section and a preview to **Recent Actions**:

**Pending Approval table:**
```markdown
| LinkedIn Post: <Topic> | post_linkedin | <timestamp> | Draft ready | [[Pending_Approval/task_linkedin_<topic>.md]] |
```

### Step 6: Log the Draft

Add entry to `System_Log.md`:
```
| <timestamp> | LinkedIn Draft | Generated LinkedIn post draft: "<Topic>" — moved to Pending_Approval for review |
```

### Step 7: Await Human Decision

The skill's work is done. The human will:
- Open the task in `/Pending_Approval/`
- Read the draft
- Optionally edit the Draft Content section
- Set `approved: true` to publish, or `status: rejected` to discard

### Step 8: Execution (Handled by Approval_Handler_Skill)

When approved, the `Approval_Handler_Skill`:
1. Reads the draft content from the task file
2. Calls `post_linkedin(content)` via MCP
3. Logs the result via `MCP_Action_Logger_Skill`
4. Moves task to `/Done/`

---

## Content Templates

### Template 1: Service Showcase

```
Most businesses don't need a full-time hire for <skill area>.

They need someone who can step in, deliver results, and keep things moving.

That's exactly what I do. I help <target audience> with <specific services> — without the overhead of a full team.

Here's what that looks like in practice:
- <Deliverable 1>
- <Deliverable 2>
- <Deliverable 3>

If you're looking for <outcome>, let's talk. DM me or check the link in my profile.

#Freelance #Consulting #Business #<IndustryTag>
```

### Template 2: Thought Leadership

```
<Bold claim or surprising insight about the industry>

I've been working with <audience type> for <timeframe>, and here's what I keep seeing:

<Observation 1 — the problem>

<Observation 2 — why it persists>

<Observation 3 — what actually works>

The companies that get this right are the ones investing in <your service area>.

What's your experience? I'd love to hear different perspectives.

#<Industry> #<Skill> #Leadership #Business
```

### Template 3: Client Success (Anonymized)

```
A recent client came to me with a challenge:
<Brief problem statement — 1 sentence>

Within <timeframe>, we:
- <Result 1>
- <Result 2>
- <Result 3>

The key wasn't <common misconception>. It was <your actual approach>.

If your team is dealing with something similar, I'm happy to share what worked. Reach out anytime.

#CaseStudy #Consulting #<IndustryTag> #Results
```

### Template 4: Tips and Value

```
<Number> things I wish I knew earlier about <topic>:

1. <Tip — short, punchy>
2. <Tip — counterintuitive or non-obvious>
3. <Tip — actionable and specific>

The biggest one? Number <X>. It changed how I approach every project.

Save this for later. And if you want to go deeper on any of these, my DMs are open.

#Tips #<Skill> #Freelance #Business
```

### Template 5: Availability / CTA

```
I'm taking on new projects for <month/quarter>.

Here's what I specialize in:
- <Service 1>
- <Service 2>
- <Service 3>

If you need <outcome> without <common pain point>, let's connect.

I keep my client roster small so every project gets full attention.

DM me or comment below — happy to chat about what you're working on.

#OpenForBusiness #Freelance #Consulting #<IndustryTag>
```

---

## MCP Action Specification

```
Tool:       post_linkedin
Parameters: { content: "<full post text>" }
Gate:       approval_needed: true (ALWAYS — no exceptions)
```

**Note:** The `post_linkedin` MCP tool is not yet implemented in the MCP server. When it becomes available, it should accept a `content` string and return `{ success: boolean, postId: string, postUrl: string }`. Until then, approved posts will be flagged for manual publishing and the draft content is available in the task file.

---

## Scheduling Cadence

Recommended posting schedule for consistent LinkedIn presence:

| Day | Content Pillar | Goal |
|-----|---------------|------|
| Monday | Service Showcase | Start the week visible |
| Thursday | Thought Leadership / Tips | Mid-week engagement peak |
| (Optional) Friday | Client Success / Availability | End-of-week reflection |

The scheduler can trigger this skill automatically. Each generated draft still requires human approval.

---

## Integration with Other Skills

| Skill | Relationship |
|-------|-------------|
| `Approval_Check_Skill` | **Always gates** this skill's output — `post_linkedin` is in the sensitive actions list |
| `Approval_Handler_Skill` | Executes `post_linkedin` after human approves the draft |
| `MCP_Action_Logger_Skill` | Logs the MCP result after post is published |
| `Plan_Tasks_Skill` | Can include LinkedIn posts in execution plans (Batch 2: Needs Approval) |

---

## Example: Full Workflow

### 1. Trigger
User says: "Create a LinkedIn post promoting my consulting services"

### 2. Skill generates task file

`/Needs_Action/task_linkedin_consulting_services.md`:
```yaml
---
type: linkedin_post
status: pending
priority: medium
created_at: 2026-02-05 23:45:00
related_files: []
approval_needed: true
approved: false
mcp_action: ["post_linkedin"]
post_topic: "Consulting services promotion"
content_pillar: "service_showcase"
---

# LinkedIn Post: Consulting Services Promotion

## Draft Content

Most businesses don't need another full-time hire.

They need someone who can step in, deliver results, and move on — without the overhead.

That's what I do. I help small and mid-size teams with strategy, execution, and the kind of hands-on work that actually moves the needle.

Here's what working together looks like:
- Clear deliverables from day one
- Direct communication, no layers of management
- Flexible engagement — project-based or ongoing

If your team is stretched thin and you need senior-level support without a long-term commitment, let's talk.

DM me or visit the link in my profile to learn more.

#Freelance #Consulting #Business #SmallBusiness

## Post Metadata

- **Content Pillar:** Service Showcase
- **Target Audience:** Business owners, hiring managers, startup founders
- **Character Count:** 687
- **Estimated Read Time:** < 1 min

## Approval Notes

- Review the draft for accuracy and tone
- Edit the Draft Content section directly if changes are needed
- Set `approved: true` in the YAML to publish
- Set `status: rejected` to discard
```

### 3. Approval Check gates it

Task moved to `/Pending_Approval/task_linkedin_consulting_services.md`
Dashboard updated:
```
| LinkedIn Post: Consulting Services | post_linkedin | 2026-02-05 23:45 | Draft ready | [[Pending_Approval/task_linkedin_consulting_services.md]] |
```

### 4. Human reviews and approves

User opens file, reads draft, sets `approved: true`

### 5. Approval Handler executes

```
post_linkedin(content: "Most businesses don't need another full-time hire...")
```

Result logged, task moved to `/Done/`.

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `default_tone` | professional | professional, casual, bold, thought-leader |
| `max_hashtags` | 5 | Maximum hashtags per post |
| `char_target` | 1000 | Target character count for post body |
| `content_rotation` | true | Rotate through content pillars on schedule |
| `include_cta` | true | Include a call-to-action in every post |
| `cta_style` | soft | soft (DM me), medium (link in profile), direct (book a call) |

---

## Guardrails

- **Never publish without approval** — `post_linkedin` is always gated
- **No client names** unless explicitly authorized — use anonymized success stories
- **No pricing** in public posts — keep commercial details to DMs
- **No negative commentary** about competitors or clients
- **No confidential business data** — review draft for accidental disclosure
- **Factual claims only** — do not fabricate metrics, testimonials, or results
- Company_Handbook Rule 2 applies: no irreversible public action without confirmation

---

## Notes

- This skill generates drafts only — it never posts directly
- The human has full editorial control before anything goes live
- Drafts can be edited directly in the Markdown file before approving
- If the `post_linkedin` MCP tool is not yet available, the approved draft is preserved in `/Done/` for manual posting
- Pair with a content calendar for consistent posting rhythm
- Track engagement manually and feed insights back into future drafts
