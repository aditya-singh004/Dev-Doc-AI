# Sample API Documentation

This is a sample documentation file to test the chatbot. Replace this with your actual documentation.

## Authentication

### API Keys

All API requests require authentication using an API key. Include your API key in the request header:

```
Authorization: Bearer YOUR_API_KEY
```

### Getting an API Key

1. Log in to the developer portal
2. Navigate to Settings > API Keys
3. Click "Generate New Key"
4. Copy and securely store your key

**Important**: API keys should never be shared or committed to version control.

## Endpoints

### GET /api/users

Retrieve a list of users.

**Parameters:**
- `limit` (optional): Maximum number of users to return (default: 20)
- `offset` (optional): Number of users to skip (default: 0)

**Response:**
```json
{
  "users": [
    {
      "id": "user_123",
      "name": "John Doe",
      "email": "john@example.com"
    }
  ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

### POST /api/users

Create a new user.

**Request Body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "developer"
}
```

**Response:**
```json
{
  "id": "user_456",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "developer",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request body is missing required fields",
    "details": {
      "missing_fields": ["email"]
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing API key |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

## Rate Limiting

API requests are limited to:
- 100 requests per minute for free tier
- 1000 requests per minute for pro tier

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Webhooks

### Setting Up Webhooks

1. Go to Settings > Webhooks
2. Click "Add Webhook"
3. Enter your endpoint URL
4. Select events to subscribe to
5. Save and copy the signing secret

### Verifying Webhook Signatures

All webhook payloads include a signature header:

```
X-Webhook-Signature: sha256=abc123...
```

Verify using HMAC-SHA256 with your signing secret.

## SDK Examples

### Python

```python
from myapi import Client

client = Client(api_key="YOUR_API_KEY")

# Get users
users = client.users.list(limit=10)

# Create user
new_user = client.users.create(
    name="John Doe",
    email="john@example.com"
)
```

### JavaScript

```javascript
import { MyAPIClient } from 'myapi-sdk';

const client = new MyAPIClient({ apiKey: 'YOUR_API_KEY' });

// Get users
const users = await client.users.list({ limit: 10 });

// Create user
const newUser = await client.users.create({
  name: 'John Doe',
  email: 'john@example.com'
});
```

## Support

For additional help:
- Email: support@example.com
- Documentation: https://docs.example.com
- Status Page: https://status.example.com
