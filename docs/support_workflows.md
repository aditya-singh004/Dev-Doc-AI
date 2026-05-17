# Support and Debug Workflows

This document captures practical support answers for the Developer Documentation AI Assistant.

## End-to-end Slack query flow

When the chatbot is set up for the quick query path, the message flow is:

1. A user sends a message in Slack.
2. Slack sends the event payload to the n8n webhook.
3. The n8n workflow cleans the incoming message and checks `DDA_USE_AGENT`.
4. When `DDA_USE_AGENT=false` or unset, n8n sends the request to `POST /api/v1/query`.
5. The FastAPI backend cleans the query, retrieves relevant documentation from the vector index, and generates an answer.
6. The backend returns a JSON response with `answer`, `sources`, and timing metadata.
7. n8n formats the response as Slack blocks and posts it back to the same channel and thread.

To make this work end-to-end:

- Import and activate `n8n/workflow.json`.
- Configure Slack OAuth credentials in n8n.
- Set the Slack event subscription URL to the n8n webhook.
- Make sure the chatbot service is reachable from n8n at `http://chatbot:8000`.
- Set `DDA_USE_AGENT=false` if you want Slack traffic to hit `/api/v1/query` instead of `/api/v1/agent/run`.

## API authentication in the sample docs

The sample API documentation uses API key authentication.

The documented format is:

```http
Authorization: Bearer YOUR_API_KEY
```

Clients should include the API key in the `Authorization` header on every API request.

## Meaning of common support errors

### `UNAUTHORIZED`

This means the request is missing a valid API key or the key is invalid.

First troubleshooting steps:

1. Check that the `Authorization` header is present.
2. Verify the header uses the format `Bearer YOUR_API_KEY`.
3. Confirm the API key is active and was copied correctly.
4. Make sure the client is not sending an empty or expired key.

### `RATE_LIMITED`

This means the client has sent too many requests in the current rate limit window.

The sample docs describe these limits:

- 100 requests per minute for the free tier
- 1000 requests per minute for the pro tier

First troubleshooting steps:

1. Inspect the returned rate limit headers.
2. Check whether the client is retrying too aggressively.
3. Wait for the reset window before sending more requests.
4. Add backoff or request throttling if the client is bursting traffic.

## Clearing a specific user's conversation memory

Use the backend memory reset endpoint:

```http
DELETE /api/v1/memory/{user_id}
```

This clears the stored conversation history for one user in the in-memory conversation store.

Reset memory during support or debug workflows when:

1. Old chat context is causing confusing answers.
2. You want to reproduce an issue from a clean state.
3. A user switches topics and stale context is polluting follow-up responses.
4. You are testing retrieval behavior and do not want prior assistant messages affecting the result.

For agent-specific state, clear working memory separately with:

```http
DELETE /api/v1/agent/working-memory?user_id={user_id}
```

or

```http
DELETE /api/v1/agent/working-memory?agent_session_id={agent_session_id}
```
