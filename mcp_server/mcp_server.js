/**
 * Silver Tier AI Employee - MCP Server
 *
 * This server exposes tools via the Model Context Protocol (MCP),
 * allowing Claude Code to perform external actions like sending emails.
 *
 * MCP servers communicate over stdio (standard input/output),
 * which is how Claude Code connects to them.
 *
 * Tools provided:
 *   - send_email: Send an email via SMTP
 *   - post_linkedin: Post content to LinkedIn
 *   - check_email_config: Verify SMTP connection
 *
 * Usage:
 *   node mcp_server.js
 *
 * Configuration:
 *   Set environment variables for SMTP credentials (see .env.example)
 */

import 'dotenv/config';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import nodemailer from 'nodemailer';

// =============================================================================
// CONFIGURATION
// =============================================================================

// SMTP Configuration - Set these via environment variables for security
// For testing, you can use a service like Ethereal (https://ethereal.email/)
const SMTP_CONFIG = {
  host: process.env.SMTP_HOST || 'smtp.ethereal.email',
  port: parseInt(process.env.SMTP_PORT || '587'),
  secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
  auth: {
    user: process.env.SMTP_USER || '',
    pass: process.env.SMTP_PASS || '',
  },
};

// Default sender email (can be overridden per request)
const DEFAULT_FROM = process.env.SMTP_FROM || 'ai-employee@example.com';

// Enable test mode (logs emails instead of sending)
const TEST_MODE = process.env.TEST_MODE === 'true' || !SMTP_CONFIG.auth.user;

// =============================================================================
// LINKEDIN CONFIGURATION
// =============================================================================

// LinkedIn API credentials - get these from https://developer.linkedin.com/
// 1. Create an app at LinkedIn Developer Portal
// 2. Add "Share on LinkedIn" product
// 3. Generate an OAuth2 access token
const LINKEDIN_CONFIG = {
  accessToken: process.env.LINKEDIN_ACCESS_TOKEN || '',
  personUrn: process.env.LINKEDIN_PERSON_URN || '', // format: "urn:li:person:XXXXXXXX"
};

// LinkedIn test mode if no credentials
const LINKEDIN_TEST_MODE = !LINKEDIN_CONFIG.accessToken || !LINKEDIN_CONFIG.personUrn;


// =============================================================================
// EMAIL TRANSPORT SETUP
// =============================================================================

let transporter = null;

/**
 * Initialize the email transporter.
 * In test mode, creates a test account on Ethereal.
 */
async function initializeTransporter() {
  if (TEST_MODE && !SMTP_CONFIG.auth.user) {
    // Create a test account on Ethereal for testing
    console.error('[MCP] Test mode: Creating Ethereal test account...');
    try {
      const testAccount = await nodemailer.createTestAccount();
      transporter = nodemailer.createTransport({
        host: 'smtp.ethereal.email',
        port: 587,
        secure: false,
        auth: {
          user: testAccount.user,
          pass: testAccount.pass,
        },
      });
      console.error(`[MCP] Test account created: ${testAccount.user}`);
      console.error('[MCP] View sent emails at: https://ethereal.email/');
    } catch (error) {
      console.error('[MCP] Could not create test account, using mock mode');
      transporter = null;
    }
  } else {
    // Use configured SMTP settings
    transporter = nodemailer.createTransport(SMTP_CONFIG);
  }
}


// =============================================================================
// TOOL DEFINITIONS
// =============================================================================

/**
 * List of tools exposed by this MCP server.
 * Each tool has a name, description, and input schema (JSON Schema format).
 */
const TOOLS = [
  {
    name: 'send_email',
    description: `Send an email via SMTP. Requires approval for sensitive communications.

Use this tool to send emails on behalf of the AI Employee.
The email will be sent from the configured SMTP account.

IMPORTANT: This action should be flagged as approval_needed in task files
before execution, as per the Approval_Check_Skill.`,
    inputSchema: {
      type: 'object',
      properties: {
        to: {
          type: 'string',
          description: 'Recipient email address (e.g., "user@example.com")',
        },
        subject: {
          type: 'string',
          description: 'Email subject line',
        },
        body: {
          type: 'string',
          description: 'Email body content (plain text or HTML)',
        },
        from: {
          type: 'string',
          description: 'Sender email address (optional, uses default if not provided)',
        },
        html: {
          type: 'boolean',
          description: 'If true, body is treated as HTML. Default: false (plain text)',
        },
      },
      required: ['to', 'subject', 'body'],
    },
  },
  {
    name: 'post_linkedin',
    description: `Post content to LinkedIn on behalf of the user.

Use this tool to publish professional posts to LinkedIn.
Supports text posts with optional visibility settings.

IMPORTANT: This action ALWAYS requires human approval via the
Approval_Check_Skill before execution.

Setup:
  Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN environment variables.
  Without credentials, runs in test/demo mode (logs post, does not publish).`,
    inputSchema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The post content/text to publish on LinkedIn',
        },
        visibility: {
          type: 'string',
          description: 'Post visibility: "PUBLIC" or "CONNECTIONS". Default: "PUBLIC"',
        },
      },
      required: ['content'],
    },
  },
  {
    name: 'check_email_config',
    description: 'Check if email is properly configured and test the connection.',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
  },
];


// =============================================================================
// TOOL HANDLERS
// =============================================================================

/**
 * Send an email using the configured SMTP transport.
 *
 * @param {Object} params - Email parameters
 * @param {string} params.to - Recipient email address
 * @param {string} params.subject - Email subject
 * @param {string} params.body - Email body
 * @param {string} [params.from] - Sender email (optional)
 * @param {boolean} [params.html] - Treat body as HTML
 * @returns {Object} Result with success status and details
 */
async function handleSendEmail(params) {
  const { to, subject, body, from = DEFAULT_FROM, html = false } = params;

  // Validate required parameters
  if (!to || !subject || !body) {
    return {
      success: false,
      error: 'Missing required parameters: to, subject, and body are required',
    };
  }

  // Validate email format (basic check)
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(to)) {
    return {
      success: false,
      error: `Invalid email address format: ${to}`,
    };
  }

  // Build the email message
  const mailOptions = {
    from: from,
    to: to,
    subject: subject,
    [html ? 'html' : 'text']: body,
  };

  // If no transporter (mock mode), just log the email
  if (!transporter) {
    console.error('[MCP] Mock mode - Email would be sent:');
    console.error(JSON.stringify(mailOptions, null, 2));
    return {
      success: true,
      mode: 'mock',
      message: 'Email logged (mock mode - no SMTP configured)',
      details: mailOptions,
    };
  }

  try {
    // Send the email
    const info = await transporter.sendMail(mailOptions);

    // Build response
    const result = {
      success: true,
      messageId: info.messageId,
      to: to,
      subject: subject,
    };

    // If using Ethereal, include preview URL
    if (info.messageId && TEST_MODE) {
      const previewUrl = nodemailer.getTestMessageUrl(info);
      if (previewUrl) {
        result.previewUrl = previewUrl;
        console.error(`[MCP] Preview URL: ${previewUrl}`);
      }
    }

    console.error(`[MCP] Email sent successfully to ${to}`);
    return result;

  } catch (error) {
    console.error(`[MCP] Email send failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
      code: error.code,
    };
  }
}


/**
 * Post content to LinkedIn using the REST API.
 *
 * @param {Object} params - Post parameters
 * @param {string} params.content - The text content to post
 * @param {string} [params.visibility] - "PUBLIC" or "CONNECTIONS"
 * @returns {Object} Result with success status and details
 */
async function handlePostLinkedin(params) {
  const { content, visibility = 'PUBLIC' } = params;

  // Validate content
  if (!content || content.trim().length === 0) {
    return {
      success: false,
      error: 'Missing required parameter: content cannot be empty',
    };
  }

  // LinkedIn has a ~3000 character limit for posts
  if (content.length > 3000) {
    return {
      success: false,
      error: `Post content too long: ${content.length} characters (max 3000)`,
    };
  }

  // Validate visibility
  const validVisibility = ['PUBLIC', 'CONNECTIONS'];
  const vis = visibility.toUpperCase();
  if (!validVisibility.includes(vis)) {
    return {
      success: false,
      error: `Invalid visibility "${visibility}". Must be PUBLIC or CONNECTIONS`,
    };
  }

  // ---- TEST/DEMO MODE ----
  if (LINKEDIN_TEST_MODE) {
    console.error('[MCP] LinkedIn test mode - Post would be published:');
    console.error(`[MCP]   Content: ${content.substring(0, 100)}...`);
    console.error(`[MCP]   Visibility: ${vis}`);
    console.error(`[MCP]   Length: ${content.length} chars`);

    const demoPostId = `demo-${Date.now()}`;
    return {
      success: true,
      mode: 'test',
      message: 'LinkedIn post logged (test mode — no API credentials configured)',
      postId: demoPostId,
      postUrl: `https://www.linkedin.com/feed/update/${demoPostId}`,
      content: content.substring(0, 200) + (content.length > 200 ? '...' : ''),
      visibility: vis,
      characterCount: content.length,
      note: 'Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN for live posting',
    };
  }

  // ---- LIVE MODE ----
  try {
    // LinkedIn UGC Post API payload
    const postBody = {
      author: LINKEDIN_CONFIG.personUrn,
      lifecycleState: 'PUBLISHED',
      specificContent: {
        'com.linkedin.ugc.ShareContent': {
          shareCommentary: {
            text: content,
          },
          shareMediaCategory: 'NONE',
        },
      },
      visibility: {
        'com.linkedin.ugc.MemberNetworkVisibility': vis,
      },
    };

    const response = await fetch('https://api.linkedin.com/v2/ugcPosts', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LINKEDIN_CONFIG.accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify(postBody),
    });

    if (!response.ok) {
      const errorBody = await response.text();
      console.error(`[MCP] LinkedIn API error: ${response.status} - ${errorBody}`);
      return {
        success: false,
        error: `LinkedIn API error: ${response.status}`,
        details: errorBody,
      };
    }

    const data = await response.json();
    const postId = data.id || 'unknown';

    console.error(`[MCP] LinkedIn post published successfully: ${postId}`);
    return {
      success: true,
      mode: 'live',
      postId: postId,
      postUrl: `https://www.linkedin.com/feed/update/${postId}`,
      visibility: vis,
      characterCount: content.length,
    };

  } catch (error) {
    console.error(`[MCP] LinkedIn post failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
    };
  }
}


/**
 * Check email configuration and connection status.
 *
 * @returns {Object} Configuration status and details
 */
async function handleCheckEmailConfig() {
  const config = {
    testMode: TEST_MODE,
    smtpHost: SMTP_CONFIG.host,
    smtpPort: SMTP_CONFIG.port,
    hasCredentials: !!SMTP_CONFIG.auth.user,
    defaultFrom: DEFAULT_FROM,
  };

  // Test connection if transporter exists
  if (transporter) {
    try {
      await transporter.verify();
      config.connectionStatus = 'connected';
      config.message = 'SMTP connection verified successfully';
    } catch (error) {
      config.connectionStatus = 'error';
      config.message = `Connection failed: ${error.message}`;
    }
  } else {
    config.connectionStatus = 'mock';
    config.message = 'Running in mock mode (no SMTP configured)';
  }

  return config;
}


// =============================================================================
// MCP SERVER SETUP
// =============================================================================

/**
 * Create and configure the MCP server.
 */
function createServer() {
  const server = new Server(
    {
      name: 'silver-tier-mcp-server',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Handler for listing available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: TOOLS,
    };
  });

  // Handler for executing tools
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    console.error(`[MCP] Tool called: ${name}`);
    console.error(`[MCP] Arguments: ${JSON.stringify(args)}`);

    try {
      let result;

      switch (name) {
        case 'send_email':
          result = await handleSendEmail(args);
          break;

        case 'post_linkedin':
          result = await handlePostLinkedin(args);
          break;

        case 'check_email_config':
          result = await handleCheckEmailConfig();
          break;

        default:
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({ error: `Unknown tool: ${name}` }),
              },
            ],
            isError: true,
          };
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };

    } catch (error) {
      console.error(`[MCP] Error executing tool ${name}: ${error.message}`);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: error.message }),
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}


// =============================================================================
// MAIN ENTRY POINT
// =============================================================================

async function main() {
  console.error('='.repeat(50));
  console.error('Silver Tier AI Employee - MCP Server');
  console.error('='.repeat(50));

  // Initialize email transporter
  await initializeTransporter();

  // Create the MCP server
  const server = createServer();

  // Connect via stdio transport (how Claude Code communicates)
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('[MCP] Server running on stdio');
  console.error('[MCP] Available tools: send_email, post_linkedin, check_email_config');
  console.error('[MCP] Waiting for requests...');
}

// Run the server
main().catch((error) => {
  console.error(`[MCP] Fatal error: ${error.message}`);
  process.exit(1);
});
