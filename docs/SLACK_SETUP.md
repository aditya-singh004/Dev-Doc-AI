# Slack Bot Setup Guide

This guide walks you through setting up a Slack bot for the AI Documentation Chatbot.

## Prerequisites

- Slack workspace admin access
- n8n instance running (for webhook handling)
- Backend API deployed and accessible

## Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. Enter:
   - **App Name**: `Documentation Bot` (or your preferred name)
   - **Workspace**: Select your workspace
5. Click **Create App**

## Step 2: Configure Bot Permissions

1. In your app settings, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add the following scopes:
   - `app_mentions:read` - Read mentions of the bot
   - `channels:history` - Read messages in public channels
   - `channels:read` - View basic channel info
   - `chat:write` - Send messages
   - `groups:history` - Read messages in private channels
   - `groups:read` - View basic private channel info
   - `im:history` - Read direct messages
   - `im:read` - View basic DM info
   - `im:write` - Send direct messages
   - `users:read` - View user info

## Step 3: Enable Event Subscriptions

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Set **Request URL** to your n8n webhook URL:
   ```
   https://your-n8n-domain.com/webhook/slack-webhook
   ```
4. Wait for Slack to verify the URL (n8n workflow handles the challenge)

### Subscribe to Bot Events

Add these events under **Subscribe to bot events**:

- `app_mention` - When someone mentions your bot
- `message.channels` - Messages in public channels
- `message.groups` - Messages in private channels
- `message.im` - Direct messages to the bot

5. Click **Save Changes**

## Step 4: Install App to Workspace

1. Go to **OAuth & Permissions**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

## Step 5: Get Signing Secret

1. Go to **Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** and copy the value

## Step 6: Configure Environment Variables

Add these to your `.env` file:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
```

## Step 7: Configure n8n Credentials

1. In n8n, go to **Credentials**
2. Create new **Slack OAuth2 API** credential
3. Enter:
   - **Client ID**: From Slack app Basic Information
   - **Client Secret**: From Slack app Basic Information
4. Complete OAuth flow

## Step 8: Test the Integration

1. Invite the bot to a channel:
   ```
   /invite @Documentation Bot
   ```

2. Send a test message:
   ```
   @Documentation Bot How do I authenticate with the API?
   ```

3. The bot should respond with relevant documentation

## Troubleshooting

### Bot Not Responding

1. Check n8n workflow is active
2. Verify webhook URL is correct
3. Check n8n execution logs
4. Ensure backend API is running

### "not_authed" Error

- Verify `SLACK_BOT_TOKEN` is correct
- Reinstall app to workspace

### Challenge Verification Failed

- Ensure n8n workflow handles URL verification
- Check webhook endpoint is publicly accessible

### Rate Limiting

Slack has rate limits. If you hit them:
- Implement message queuing
- Add delays between responses
- Use Slack's retry headers

## Security Best Practices

1. **Verify Requests**: Always verify Slack signing secret
2. **HTTPS Only**: Use HTTPS for all webhooks
3. **Token Security**: Never expose tokens in code
4. **Minimal Scopes**: Only request necessary permissions
5. **Audit Logs**: Monitor bot activity

## Advanced Configuration

### Slash Commands

Add custom slash commands:

1. Go to **Slash Commands**
2. Click **Create New Command**
3. Configure:
   - **Command**: `/docs`
   - **Request URL**: Your n8n webhook
   - **Description**: Search documentation

### Interactive Components

Enable buttons and menus:

1. Go to **Interactivity & Shortcuts**
2. Enable **Interactivity**
3. Set **Request URL** for interactions

### Home Tab

Create a bot home tab:

1. Go to **App Home**
2. Enable **Home Tab**
3. Configure welcome message

## Channel-Specific Behavior

To limit bot to specific channels:

1. Only invite bot to designated channels
2. Or filter by channel ID in n8n workflow
3. Add channel allowlist in backend config
