/**
 * Test script for the email functionality.
 *
 * This script tests the email sending without running the full MCP server.
 * Useful for verifying your SMTP configuration.
 *
 * Usage:
 *   node test_email.js
 */

import nodemailer from 'nodemailer';

async function testEmail() {
  console.log('='.repeat(50));
  console.log('Email Configuration Test');
  console.log('='.repeat(50));
  console.log();

  // Check for environment variables
  const hasConfig = process.env.SMTP_USER && process.env.SMTP_PASS;

  let transporter;
  let testAccount;

  if (hasConfig) {
    // Use configured SMTP
    console.log('Using configured SMTP settings...');
    transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: parseInt(process.env.SMTP_PORT || '587'),
      secure: process.env.SMTP_SECURE === 'true',
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    });
  } else {
    // Create Ethereal test account
    console.log('No SMTP configured. Creating Ethereal test account...');
    console.log();

    try {
      testAccount = await nodemailer.createTestAccount();
      console.log('Test account created:');
      console.log(`  User: ${testAccount.user}`);
      console.log(`  Pass: ${testAccount.pass}`);
      console.log();

      transporter = nodemailer.createTransport({
        host: 'smtp.ethereal.email',
        port: 587,
        secure: false,
        auth: {
          user: testAccount.user,
          pass: testAccount.pass,
        },
      });
    } catch (error) {
      console.error('Failed to create test account:', error.message);
      process.exit(1);
    }
  }

  // Verify connection
  console.log('Verifying SMTP connection...');
  try {
    await transporter.verify();
    console.log('Connection successful!');
    console.log();
  } catch (error) {
    console.error('Connection failed:', error.message);
    process.exit(1);
  }

  // Send test email
  console.log('Sending test email...');
  try {
    const info = await transporter.sendMail({
      from: testAccount ? testAccount.user : process.env.SMTP_FROM,
      to: 'test@example.com',
      subject: 'Silver Tier MCP Server - Test Email',
      text: `This is a test email from the Silver Tier AI Employee MCP Server.

Sent at: ${new Date().toISOString()}

If you received this email, your SMTP configuration is working correctly!`,
      html: `
        <h1>Silver Tier MCP Server</h1>
        <p>This is a test email from the Silver Tier AI Employee MCP Server.</p>
        <p><strong>Sent at:</strong> ${new Date().toISOString()}</p>
        <p>If you received this email, your SMTP configuration is working correctly!</p>
      `,
    });

    console.log('Email sent successfully!');
    console.log(`  Message ID: ${info.messageId}`);

    // Show preview URL for Ethereal
    if (testAccount) {
      const previewUrl = nodemailer.getTestMessageUrl(info);
      console.log();
      console.log('Preview your email at:');
      console.log(`  ${previewUrl}`);
    }

  } catch (error) {
    console.error('Failed to send email:', error.message);
    process.exit(1);
  }

  console.log();
  console.log('='.repeat(50));
  console.log('Test completed successfully!');
  console.log('='.repeat(50));
}

testEmail().catch(console.error);
