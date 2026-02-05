# Silver Tier MCP Server

Model Context Protocol (MCP) server for the AI Employee, providing external action capabilities.

## Tools Available

| Tool | Description |
|------|-------------|
| `send_email` | Send emails via SMTP |
| `check_email_config` | Verify email configuration |

## Quick Start

### 1. Install Dependencies

```bash
cd mcp_server
npm install
```

### 2. Configure SMTP (Optional)

For testing, the server automatically creates an [Ethereal](https://ethereal.email/) test account.

For production, copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your SMTP credentials
```

**Gmail Setup:**
1. Enable 2-Factor Authentication
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the App Password (not your regular password)

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-16-char-app-password
SMTP_FROM=your-email@gmail.com
```

### 3. Test Email Configuration

```bash
npm test
# or
node test_email.js
```

This sends a test email and shows a preview URL if using Ethereal.

### 4. Start the Server

```bash
npm start
# or
node mcp_server.js
```

## Connecting to Claude Code

Add this server to your Claude Code MCP configuration:

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "silver-tier-email": {
      "command": "node",
      "args": ["C:\\Hakathon0_ai_employee\\Silver\\mcp_server\\mcp_server.js"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your-email@gmail.com",
        "SMTP_PASS": "your-app-password",
        "SMTP_FROM": "your-email@gmail.com"
      }
    }
  }
}
```

### macOS/Linux

Edit `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "silver-tier-email": {
      "command": "node",
      "args": ["/path/to/Silver/mcp_server/mcp_server.js"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your-email@gmail.com",
        "SMTP_PASS": "your-app-password"
      }
    }
  }
}
```

### Claude Code CLI

For Claude Code CLI, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "silver-tier-email": {
      "command": "node",
      "args": ["C:\\Hakathon0_ai_employee\\Silver\\mcp_server\\mcp_server.js"]
    }
  }
}
```

## Tool Usage

### send_email

Send an email:

```json
{
  "to": "recipient@example.com",
  "subject": "Hello from AI Employee",
  "body": "This is a test email.",
  "html": false
}
```

Parameters:
- `to` (required): Recipient email address
- `subject` (required): Email subject line
- `body` (required): Email content
- `from` (optional): Sender address (uses default if omitted)
- `html` (optional): Set to `true` for HTML emails

### check_email_config

Check configuration status:

```json
{}
```

Returns connection status and configuration details.

## Integration with AI Employee

This MCP server integrates with the Silver Tier workflow:

1. Tasks with `mcp_action: ["send_email"]` are flagged by `Approval_Check_Skill`
2. Flagged tasks move to `/Pending_Approval/`
3. After approval, the AI Employee can call `send_email` via MCP
4. Results are logged to `System_Log.md`

## Troubleshooting

### "Cannot find module" Error
```bash
npm install
```

### Connection Timeout
- Check firewall settings
- Verify SMTP host and port
- Try port 465 with `SMTP_SECURE=true`

### Authentication Failed
- For Gmail: Use App Password, not regular password
- Verify credentials in `.env`

### Test Mode
Set `TEST_MODE=true` to log emails without sending:
```env
TEST_MODE=true
```

## Security Notes

- Never commit `.env` files with real credentials
- Use App Passwords for Gmail (not your main password)
- The `Approval_Check_Skill` should gate all email actions
- Review emails in `/Pending_Approval/` before authorizing
