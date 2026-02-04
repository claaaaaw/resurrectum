/**
 * Resurrectum Credential Service
 * 
 * Cloudflare Worker that provides presigned URLs for R2 storage access.
 * 
 * Endpoints:
 * - POST /presign - Generate presigned URLs for read/write operations
 * - GET /health   - Health check
 */

import { verify } from "@noble/ed25519";
import { AwsClient } from "aws4fetch";

// ============ Types ============

interface Env {
  R2: R2Bucket;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
  R2_ACCOUNT_ID: string;
  R2_BUCKET_NAME: string;
}

interface PresignRequest {
  capsule_id: string;           // Format: owner_fp/uuid
  action: "read" | "write";
  blobs?: string[];             // For write: list of blob_ids to upload
  timestamp: number;
  signature: string;            // base64url encoded
  public_key: string;           // base64url encoded
}

interface ManifestAccess {
  owner?: string;
  readers?: string[];
  public?: boolean;
}

interface Manifest {
  access?: ManifestAccess;
  [key: string]: unknown;
}

// ============ CORS Configuration ============

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// ============ Main Handler ============

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health") {
      return Response.json(
        {
          status: "ok",
          version: "1.0.0",
          timestamp: Math.floor(Date.now() / 1000),
        },
        { headers: corsHeaders }
      );
    }

    // Presign endpoint
    if (url.pathname === "/presign" && request.method === "POST") {
      return handlePresign(request, env, ctx);
    }

    return new Response("Not Found", { status: 404, headers: corsHeaders });
  },
};

// ============ Presign Handler ============

async function handlePresign(
  request: Request,
  env: Env,
  ctx: ExecutionContext
): Promise<Response> {
  // Parse request body
  let body: PresignRequest;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { error: "Invalid JSON" },
      { status: 400, headers: corsHeaders }
    );
  }

  const { capsule_id, action, blobs, timestamp, signature, public_key } = body;

  // 1. Validate capsule_id format
  const idParts = capsule_id.split("/");
  if (idParts.length !== 2) {
    return Response.json(
      { error: "Invalid capsule_id format, expected: owner_fp/uuid" },
      { status: 400, headers: corsHeaders }
    );
  }
  const [owner_fp, uuid] = idParts;

  // Validate owner_fp is 64 hex chars
  if (!/^[a-f0-9]{64}$/i.test(owner_fp)) {
    return Response.json(
      { error: "Invalid owner fingerprint format" },
      { status: 400, headers: corsHeaders }
    );
  }

  // 2. Validate timestamp (5-minute window for replay protection)
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - timestamp) > 300) {
    return Response.json(
      { error: "Request expired" },
      { status: 401, headers: corsHeaders }
    );
  }

  // 3. Verify signature
  const message = `${capsule_id}:${action}:${timestamp}`;
  const sig = base64urlDecode(signature);
  const pk = base64urlDecode(public_key);

  let valid: boolean;
  try {
    valid = await verify(sig, new TextEncoder().encode(message), pk);
  } catch {
    valid = false;
  }

  if (!valid) {
    return Response.json(
      { error: "Invalid signature" },
      { status: 401, headers: corsHeaders }
    );
  }

  // 4. Calculate requester's fingerprint
  const fingerprint = await sha256Hex(pk);

  // 5. Check permissions
  if (action === "write") {
    // Write: owner_fp must match requester
    if (owner_fp !== fingerprint) {
      return Response.json(
        { error: "Cannot write to another user's namespace" },
        { status: 403, headers: corsHeaders }
      );
    }
  } else {
    // Read: check manifest.access
    const accessAllowed = await checkReadAccess(
      env,
      ctx,
      capsule_id,
      fingerprint
    );
    if (!accessAllowed) {
      return Response.json(
        { error: "Access denied" },
        { status: 403, headers: corsHeaders }
      );
    }
  }

  // 6. Generate presigned URLs
  const expiresIn = 3600; // 1 hour
  const presigner = new R2Presigner(env);

  const urls: Record<string, unknown> = {};
  const prefix = `capsules/${capsule_id}`;

  if (action === "read") {
    // Read: generate GET URLs for manifest and all blobs
    urls.manifest = await presigner.presignGet(
      `${prefix}/capsule.manifest.json`,
      expiresIn
    );
    urls.redaction_report = await presigner.presignGet(
      `${prefix}/redaction.report.json`,
      expiresIn
    );

    // List all blobs and generate URLs
    const blobList = await env.R2.list({ prefix: `${prefix}/blobs/` });
    const blobUrls: Record<string, string> = {};
    for (const obj of blobList.objects) {
      const blobId = obj.key.split("/").pop()!;
      blobUrls[blobId] = await presigner.presignGet(obj.key, expiresIn);
    }
    urls.blobs = blobUrls;
  } else {
    // Write: generate PUT URLs for specified blobs
    urls.manifest = await presigner.presignPut(
      `${prefix}/capsule.manifest.json`,
      expiresIn
    );
    urls.redaction_report = await presigner.presignPut(
      `${prefix}/redaction.report.json`,
      expiresIn
    );

    const blobUrls: Record<string, string> = {};
    for (const blobId of blobs || []) {
      blobUrls[blobId] = await presigner.presignPut(
        `${prefix}/blobs/${blobId}`,
        expiresIn
      );
    }
    urls.blobs = blobUrls;
  }

  return Response.json(
    {
      expires_at: now + expiresIn,
      urls,
    },
    { headers: corsHeaders }
  );
}

// ============ Access Control ============

async function checkReadAccess(
  env: Env,
  ctx: ExecutionContext,
  capsule_id: string,
  fingerprint: string
): Promise<boolean> {
  // Try to read manifest from cache
  const cacheKey = `https://cache.internal/manifest/${capsule_id}`;
  const cache = caches.default;

  let manifestResponse = await cache.match(cacheKey);

  if (!manifestResponse) {
    // Cache miss: read from R2
    const object = await env.R2.get(
      `capsules/${capsule_id}/capsule.manifest.json`
    );
    if (!object) {
      return false; // Capsule doesn't exist
    }

    const text = await object.text();
    manifestResponse = new Response(text, {
      headers: { "Cache-Control": "max-age=300" }, // Cache for 5 minutes
    });

    // Async write to cache
    ctx.waitUntil(cache.put(cacheKey, manifestResponse.clone()));
  }

  const manifest = (await manifestResponse.json()) as Manifest;
  const access = manifest.access || {};

  // Check permissions
  if (access.public === true) return true;
  if (access.owner === `ed25519:${fingerprint}`) return true;
  if (access.readers?.includes(`ed25519:${fingerprint}`)) return true;

  // Owner fingerprint check (from capsule_id)
  const [owner_fp] = capsule_id.split("/");
  if (owner_fp === fingerprint) return true;

  return false;
}

// ============ R2 Presigner ============

class R2Presigner {
  private client: AwsClient;
  private endpoint: string;
  private bucket: string;

  constructor(env: Env) {
    this.client = new AwsClient({
      accessKeyId: env.R2_ACCESS_KEY_ID,
      secretAccessKey: env.R2_SECRET_ACCESS_KEY,
      service: "s3",
      region: "auto",
    });
    this.endpoint = `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;
    this.bucket = env.R2_BUCKET_NAME;
  }

  async presignGet(key: string, expiresIn: number): Promise<string> {
    const url = new URL(`${this.endpoint}/${this.bucket}/${key}`);
    const signed = await this.client.sign(url.toString(), {
      method: "GET",
      aws: { signQuery: true, expiresIn },
    });
    return signed.url;
  }

  async presignPut(key: string, expiresIn: number): Promise<string> {
    const url = new URL(`${this.endpoint}/${this.bucket}/${key}`);
    const signed = await this.client.sign(url.toString(), {
      method: "PUT",
      aws: { signQuery: true, expiresIn },
    });
    return signed.url;
  }
}

// ============ Utility Functions ============

function base64urlDecode(s: string): Uint8Array {
  const base64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(base64 + padding);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

async function sha256Hex(data: Uint8Array): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(hash)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
