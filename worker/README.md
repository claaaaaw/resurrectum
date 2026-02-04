# Resurrectum Credential Service

Cloudflare Worker that provides presigned URLs for R2 storage access.

## Setup

### Prerequisites

1. Cloudflare account with Workers and R2 enabled
2. Node.js >= 18
3. Wrangler CLI: `npm install -g wrangler`

### Configuration

1. Create R2 bucket:
   ```bash
   wrangler r2 bucket create resurrectum-capsules
   ```

2. Update `wrangler.toml` with your account ID:
   ```toml
   [vars]
   R2_ACCOUNT_ID = "your-account-id"
   ```

3. Create R2 API Token (Dashboard > R2 > Manage R2 API Tokens):
   - Permissions: Object Read & Write
   - Scope: Specific bucket (resurrectum-capsules)

4. Set secrets:
   ```bash
   wrangler secret put R2_ACCESS_KEY_ID
   wrangler secret put R2_SECRET_ACCESS_KEY
   ```

## Development

```bash
# Install dependencies
npm install

# Run local development server
npm run dev
```

## Deployment

```bash
# Deploy to production
npm run deploy

# View logs
npm run tail
```

## API Endpoints

### POST /presign

Generate presigned URLs for read/write operations.

**Request:**
```json
{
  "capsule_id": "owner_fp/uuid",
  "action": "read" | "write",
  "blobs": ["blob_id_1", "blob_id_2"],
  "timestamp": 1706000000,
  "signature": "base64url(ed25519_sig)",
  "public_key": "base64url(ed25519_pk)"
}
```

**Response (Read):**
```json
{
  "expires_at": 1706003600,
  "urls": {
    "manifest": "https://...",
    "redaction_report": "https://...",
    "blobs": {
      "abc123...": "https://..."
    }
  }
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": 1706000000
}
```

## Security

- Request signatures are verified using Ed25519
- Timestamps have a 5-minute window for replay protection
- Write operations require owner fingerprint match
- Read operations check manifest.access permissions
- Presigned URLs expire after 1 hour

## Rate Limiting

Configure in Cloudflare Dashboard:
- Path: `/presign`
- Limit: 60 requests/minute per IP
- Limit: 500 requests/hour per IP
