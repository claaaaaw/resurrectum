# Resurrectum — 施工计划 v1.0

**文档版本:** 1.2  
**创建日期:** 2026-02-04  
**最后更新:** 2026-02-04  
**状态:** 草案

> **关键设计决策**：
> - 凭证方案：**Presigned URL**（R2 不支持 STS）
> - capsule_id 格式：**owner_fp/uuid**（复合格式）
> - 存储路径：**capsules/{owner_fp}/{uuid}/**（新项目，无需兼容）
> - 压缩方案：**7z 打包**（上传前压缩，节约 60-80% 存储空间）

---

## 目录

1. [架构概述](#1-架构概述)
2. [组件详细设计](#2-组件详细设计)
3. [存储抽象层](#3-存储抽象层)
4. [凭证服务](#4-凭证服务)
5. [客户端优化](#5-客户端优化)
6. [官网设计](#6-官网设计)
7. [安全与防滥用](#7-安全与防滥用)
8. [去中心化演进路径](#8-去中心化演进路径)
9. [实施计划](#9-实施计划)
10. [成本估算](#10-成本估算)

---

## 1. 架构概述

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **客户端优先** | 所有业务逻辑（加密/签名/验证）在客户端执行 |
| **服务端无状态** | 凭证服务无数据库、无 KV、无持久状态 |
| **存储不可信** | E2EE 加密，服务端无法解密数据 |
| **去中心化就绪** | 架构设计便于未来迁移到 IPFS/去中心化存储 |

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完整架构                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              用户（人类 / AI Agent）                         │
│                                    │                                        │
│            ┌───────────────────────┼───────────────────────┐                │
│            │                       │                       │                │
│            ▼                       ▼                       │                │
│  ┌───────────────────┐   ┌───────────────────┐            │                │
│  │   官网 (静态)      │   │   客户端 (CLI)    │            │                │
│  │   ───────────────  │   │   ─────────────    │            │                │
│  │   • 项目介绍       │   │   • 加密/解密      │            │                │
│  │   • 文档           │   │   • 签名/验证      │            │                │
│  │   • 下载链接       │   │   • 凭证缓存 ⭐    │            │                │
│  │   • FAQ           │   │   • Fallback ⭐    │            │                │
│  │                   │   │                    │            │                │
│  │   ⚠️ 零业务逻辑    │   │   ✅ 全部业务逻辑  │            │                │
│  │                   │   │                    │            │                │
│  │ 部署: CF Pages    │   │                    │            │                │
│  └───────────────────┘   └─────────┬──────────┘            │                │
│            │                       │                       │                │
│            │                       │ 签名请求               │                │
│            │                       │ + 凭证缓存 ⭐          │                │
│            │                       ▼                       │                │
│            │             ┌─────────────────────┐           │                │
│            │             │  凭证服务 (无状态)   │           │                │
│            │             │  ─────────────────   │           │                │
│            │             │  • 验证请求签名      │           │                │
│            │             │  • 读 manifest       │           │                │
│            │             │  • Cache API ⭐      │           │                │
│            │             │  • 检查 access 字段  │           │                │
│            │             │  • 生成临时凭证      │           │                │
│            │             │  • Rate Limiting ⭐  │           │                │
│            │             │                     │           │                │
│            │             │  ❌ 无数据库         │           │                │
│            │             │  ❌ 无 KV            │           │                │
│            │             │                     │           │                │
│            │             │ 部署: CF Workers    │           │                │
│            │             └──────────┬──────────┘           │                │
│            │                        │                      │                │
│            │                        │ 临时凭证              │                │
│            │                        ▼                      │                │
│            │             ┌──────────────────────────────────────┐           │
│            │             │         存储端 (R2/S3)               │           │
│            │             │  ────────────────────────────────────  │           │
│            │             │                                      │           │
│            │             │  capsules/{owner_fp}/{capsule_id}/   │           │
│            │             │    ├── manifest.json                 │◄──────────┘
│            │             │    ├── redaction.report.json         │  直接读写
│            │             │    └── blobs/{blob_id}               │ (临时凭证)
│            │             │                                      │
│            │             │  部署: Cloudflare R2                 │
│            │             └──────────────────────────────────────┘
│            │                                                                │
│            │ /health                                                        │
│            └────────────────────────────────────────────────────────────────┘
│                                                                             │
│  ⭐ = 本次施工新增/优化项                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 数据流

```
Export 流程:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 客户端   │───>│ 凭证服务 │───>│ 读manifest│───>│ 发凭证   │
│ 签名请求 │    │ 验签     │    │ (新建跳过)│    │          │
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                     │
┌──────────┐    ┌──────────┐    ┌──────────┐         │
│ 上传完成 │<───│ 直连 R2  │<───│ 客户端   │<────────┘
│          │    │ 上传     │    │ 加密+签名│
└──────────┘    └──────────┘    └──────────┘

Import 流程:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 客户端   │───>│ 凭证服务 │───>│ 读manifest│───>│ 检查     │
│ 签名请求 │    │ 验签     │    │ access   │    │ 权限     │
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                     │
┌──────────┐    ┌──────────┐    ┌──────────┐         │
│ 恢复完成 │<───│ 客户端   │<───│ 直连 R2  │<────────┘
│          │    │ 验签+解密│    │ 下载     │
└──────────┘    └──────────┘    └──────────┘
```

---

## 2. 组件详细设计

### 2.1 组件职责矩阵

| 功能 | 官网 | 客户端 | 凭证服务 | 存储端 |
|------|:----:|:------:|:--------:|:------:|
| 文档展示 | ✅ | - | - | - |
| 密钥生成 | - | ✅ | - | - |
| 加密/解密 | - | ✅ | - | - |
| 签名/验签 | - | ✅ | - | - |
| Manifest 生成 | - | ✅ | - | - |
| 请求签名 | - | ✅ | - | - |
| 凭证缓存 | - | ✅ | - | - |
| 验证请求签名 | - | - | ✅ | - |
| 读取 manifest | - | - | ✅ | ✅ |
| 检查 access | - | - | ✅ | - |
| 生成临时凭证 | - | - | ✅ | - |
| 存储 blobs | - | - | - | ✅ |
| 存储 manifest | - | - | - | ✅ |

### 2.2 身份模型

```
用户身份 = Ed25519 公钥指纹 (sha256, hex, 64字符)

无传统"用户注册"：
1. 客户端本地生成 Ed25519 密钥对 (summon init)
2. 公钥指纹 = sha256(public_key_bytes) → hex 字符串
3. 身份即公钥指纹，无需服务端记录

示例指纹:
  a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890
```

### 2.2.1 capsule_id 格式

```
capsule_id = {owner_fingerprint}/{uuid}

示例:
  a1b2c3d4e5f67890.../01234567-89ab-cdef-0123-456789abcdef
  ├── owner_fingerprint: 64 字符 hex (sha256 of owner public key)
  └── uuid: UUIDv7 格式

设计理由:
- 路径自描述：从 capsule_id 即可知道 owner
- 权限检查高效：无需读取 manifest 即可验证写权限
- 存储隔离：按 owner 分组，便于配额管理
```

### 2.3 访问控制模型

```json
// manifest.json 中的 access 字段
{
  "access": {
    "owner": "ed25519:a1b2c3d4...",
    "readers": [
      "ed25519:e5f6g7h8...",
      "ed25519:i9j0k1l2..."
    ],
    "public": false
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `owner` | string | 所有者公钥指纹，唯一具有写权限 |
| `readers` | string[] | 授权读取者列表（可选） |
| `public` | boolean | 是否公开访问（默认 false） |

权限检查逻辑：
```
read:  owner OR readers[] 包含请求者 OR public=true
write: owner 必须匹配
```

---

## 3. 存储抽象层

### 3.1 现有实现

当前 `src/resurrectum/summon/storage.py` 已有：
- `StorageBackend` Protocol
- `LocalDirBackend` 实现
- `S3Backend` 实现

### 3.2 需要新增：PresignedUrlBackend

> **设计决策**：采用 Presigned URL 方案，客户端通过凭证服务获取签名 URL，然后直接访问 R2。

```python
# src/resurrectum/summon/storage.py

from __future__ import annotations

import time
import json
import urllib.request
import urllib.error
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..sigil.crypto import sign_message, load_signing_key


def base64url_encode(data: bytes) -> str:
    """Base64url 编码（无 padding）"""
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass
class PresignedUrlBackend:
    """
    通过凭证服务获取 Presigned URL 的远程存储后端
    
    工作流程：
    1. 客户端签名请求 → 凭证服务
    2. 凭证服务验证 → 返回 Presigned URLs
    3. 客户端使用 URL 直接访问 R2
    """
    
    credential_service_url: str
    signing_key_path: Path
    
    # URL 缓存
    _url_cache: dict[str, tuple[dict, float]] = field(
        default_factory=dict, repr=False
    )
    _cache_buffer_seconds: float = 300  # 提前 5 分钟刷新
    
    def _get_presigned_urls(
        self, 
        capsule_id: str, 
        action: str,
        blobs: Optional[list[str]] = None
    ) -> dict:
        """获取 Presigned URLs，带缓存"""
        # 注意：write 请求通常不缓存，因为 blobs 列表可能变化
        if action == "read":
            cache_key = f"{capsule_id}:read"
            if cache_key in self._url_cache:
                urls, expires_at = self._url_cache[cache_key]
                if time.time() < expires_at - self._cache_buffer_seconds:
                    return urls
        
        # 请求新的 Presigned URLs
        result = self._request_presigned_urls(capsule_id, action, blobs)
        
        if action == "read":
            self._url_cache[cache_key] = (result["urls"], result["expires_at"])
        
        return result["urls"]
    
    def _request_presigned_urls(
        self, 
        capsule_id: str, 
        action: str,
        blobs: Optional[list[str]] = None
    ) -> dict:
        """向凭证服务请求 Presigned URLs"""
        timestamp = int(time.time())
        message = f"{capsule_id}:{action}:{timestamp}"
        
        signing_key = load_signing_key(self.signing_key_path)
        signature = sign_message(message.encode(), signing_key)
        public_key = signing_key.public_key()
        
        payload = {
            "capsule_id": capsule_id,
            "action": action,
            "timestamp": timestamp,
            "signature": base64url_encode(signature),
            "public_key": base64url_encode(public_key.public_bytes_raw())
        }
        if blobs:
            payload["blobs"] = blobs
        
        req = urllib.request.Request(
            f"{self.credential_service_url}/presign",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise RuntimeError(
                f"Credential service error: {e.code} - {error_body}"
            ) from e
    
    # ============ StorageBackend 协议实现 ============
    
    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        """上传 blob 到 R2"""
        urls = self._get_presigned_urls(capsule_id, "write", blobs=[blob_id])
        url = urls["blobs"].get(blob_id)
        if not url:
            raise RuntimeError(f"No presigned URL for blob: {blob_id}")
        
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/octet-stream")
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed: {resp.status}")
        
        return f"capsules/{capsule_id}/blobs/{blob_id}"
    
    def get_blob(self, ref: str) -> bytes:
        """从 R2 下载 blob"""
        # ref 格式: capsules/{owner_fp}/{uuid}/blobs/{blob_id}
        parts = ref.split("/")
        capsule_id = f"{parts[1]}/{parts[2]}"  # owner_fp/uuid
        blob_id = parts[-1]
        
        urls = self._get_presigned_urls(capsule_id, "read")
        url = urls.get("blobs", {}).get(blob_id)
        if not url:
            raise RuntimeError(f"No presigned URL for blob: {blob_id}")
        
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    
    def has_blob(self, ref: str) -> bool:
        """检查 blob 是否存在"""
        try:
            self.get_blob(ref)
            return True
        except Exception:
            return False
    
    def put_document(self, capsule_id: str, path: str, data: bytes) -> None:
        """上传文档（manifest/report）"""
        urls = self._get_presigned_urls(capsule_id, "write", blobs=[])
        
        # 根据 path 选择对应的 URL
        if path == "manifest.json" or path == "capsule.manifest.json":
            url = urls.get("manifest")
        elif path == "redaction.report.json":
            url = urls.get("redaction_report")
        else:
            raise RuntimeError(f"Unknown document path: {path}")
        
        if not url:
            raise RuntimeError(f"No presigned URL for document: {path}")
        
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed: {resp.status}")
    
    def get_document(self, capsule_id: str, path: str) -> bytes:
        """下载文档"""
        urls = self._get_presigned_urls(capsule_id, "read")
        
        if path == "manifest.json" or path == "capsule.manifest.json":
            url = urls.get("manifest")
        elif path == "redaction.report.json":
            url = urls.get("redaction_report")
        else:
            raise RuntimeError(f"Unknown document path: {path}")
        
        if not url:
            raise RuntimeError(f"No presigned URL for document: {path}")
        
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    
    def list(self, capsule_id: str, prefix: str) -> list[str]:
        """列出指定前缀下的所有对象"""
        urls = self._get_presigned_urls(capsule_id, "read")
        
        if prefix.startswith("blobs"):
            # 返回所有 blob 的 key
            return [
                f"capsules/{capsule_id}/blobs/{blob_id}" 
                for blob_id in urls.get("blobs", {}).keys()
            ]
        
        return []
```

### 3.3 未来扩展：IPFSBackend（v1.1+）

```python
@dataclass
class IPFSBackend:
    """IPFS 存储后端（v1.1+ 实现）"""
    
    ipfs_api_url: str = "http://localhost:5001"
    gateway_url: str = "https://ipfs.io"
    
    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        """上传到 IPFS，返回 CID"""
        # POST /api/v0/add
        ...
        return f"ipfs://{cid}"
    
    def get_blob(self, ref: str) -> bytes:
        """从 IPFS 下载"""
        cid = ref.replace("ipfs://", "")
        # GET from gateway
        ...
```

### 3.4 存储路径约定

```
R2/S3 布局:
capsules/
  {owner_fingerprint}/{uuid}/    # capsule_id = owner_fp/uuid
    manifest.json
    redaction.report.json
    blobs/
      {blob_id}                  # sha256(ciphertext), hex

完整路径示例:
capsules/a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890/01234567-89ab-cdef-0123-456789abcdef/
  ├── manifest.json
  ├── redaction.report.json
  └── blobs/
      ├── abc123def456789...
      └── 789xyz123abc456...

对应的 capsule_id:
  a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890/01234567-89ab-cdef-0123-456789abcdef
```

> **注意**：此路径结构与现有 v1 文档中的 `capsules/{capsule_id}/` 不同。
> 由于是新项目，采用新的路径结构，无需考虑兼容性。

---

## 4. 凭证服务

### 4.1 API 设计

#### 4.1.1 获取 Presigned URLs

> **设计决策**：Cloudflare R2 不支持 AWS STS 风格的临时凭证，因此采用 **Presigned URL** 方案。
> 凭证服务为每个请求生成有时效的签名 URL，客户端直接使用这些 URL 访问 R2。

```
POST /presign
Content-Type: application/json

Request:
{
  "capsule_id": "owner_fp/uuid",
  "action": "read" | "write",
  "blobs": ["blob_id_1", "blob_id_2"],  // 可选，write 时指定要上传的 blob
  "timestamp": 1706000000,
  "signature": "base64url(ed25519_sig)",
  "public_key": "base64url(ed25519_pk)"
}

Response (200) - Read:
{
  "expires_at": 1706003600,
  "urls": {
    "manifest": "https://xxx.r2.cloudflarestorage.com/capsules/.../manifest.json?X-Amz-...",
    "redaction_report": "https://xxx.r2.cloudflarestorage.com/capsules/.../redaction.report.json?X-Amz-...",
    "blobs": {
      "abc123...": "https://xxx.r2.cloudflarestorage.com/capsules/.../blobs/abc123...?X-Amz-..."
    }
  }
}

Response (200) - Write:
{
  "expires_at": 1706003600,
  "urls": {
    "manifest": "https://xxx.r2.cloudflarestorage.com/capsules/.../manifest.json?X-Amz-...",
    "redaction_report": "https://xxx.r2.cloudflarestorage.com/capsules/.../redaction.report.json?X-Amz-...",
    "blobs": {
      "blob_id_1": "https://xxx.r2.cloudflarestorage.com/capsules/.../blobs/blob_id_1?X-Amz-...",
      "blob_id_2": "https://xxx.r2.cloudflarestorage.com/capsules/.../blobs/blob_id_2?X-Amz-..."
    }
  }
}

Errors:
- 400: Invalid request / Invalid JSON
- 401: Invalid signature / Expired timestamp
- 403: Access denied
- 404: Capsule not found (for read action)
```

**Presigned URL 特点**：
- 有效期：1 小时（可配置）
- 每个 URL 只能访问特定对象（安全隔离）
- 客户端直接与 R2 通信，凭证服务不做代理（低延迟）

#### 4.1.2 健康检查

```
GET /health

Response (200):
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": 1706000000
}
```

### 4.2 实现（Cloudflare Workers）

```typescript
// worker/src/index.ts

import { verify } from "@noble/ed25519";
import { AwsClient } from "aws4fetch";  // 用于生成 Presigned URL

interface Env {
  R2: R2Bucket;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
  R2_ACCOUNT_ID: string;
  R2_BUCKET_NAME: string;
}

interface PresignRequest {
  capsule_id: string;           // 格式: owner_fp/uuid
  action: "read" | "write";
  blobs?: string[];             // write 时指定要上传的 blob_id 列表
  timestamp: number;
  signature: string;
  public_key: string;
}

// CORS 配置
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // 处理 CORS 预检请求
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }
    
    const url = new URL(request.url);
    
    // 健康检查
    if (url.pathname === "/health") {
      return Response.json({
        status: "ok",
        version: "1.0.0",
        timestamp: Math.floor(Date.now() / 1000)
      }, { headers: corsHeaders });
    }
    
    // Presigned URL 请求
    if (url.pathname === "/presign" && request.method === "POST") {
      return handlePresign(request, env, ctx);
    }
    
    return new Response("Not Found", { status: 404, headers: corsHeaders });
  }
};

async function handlePresign(
  request: Request, 
  env: Env, 
  ctx: ExecutionContext
): Promise<Response> {
  // 解析请求
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
  
  // 1. 验证 capsule_id 格式
  const idParts = capsule_id.split("/");
  if (idParts.length !== 2) {
    return Response.json(
      { error: "Invalid capsule_id format, expected: owner_fp/uuid" }, 
      { status: 400, headers: corsHeaders }
    );
  }
  const [owner_fp, uuid] = idParts;
  
  // 2. 验证时间戳（防重放，5分钟窗口）
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - timestamp) > 300) {
    return Response.json(
      { error: "Request expired" }, 
      { status: 401, headers: corsHeaders }
    );
  }
  
  // 3. 验证签名
  const message = `${capsule_id}:${action}:${timestamp}`;
  const sig = base64urlDecode(signature);
  const pk = base64urlDecode(public_key);
  
  const valid = await verify(sig, new TextEncoder().encode(message), pk);
  if (!valid) {
    return Response.json(
      { error: "Invalid signature" }, 
      { status: 401, headers: corsHeaders }
    );
  }
  
  // 4. 计算请求者指纹
  const fingerprint = await sha256Hex(pk);
  
  // 5. 检查权限
  if (action === "write") {
    // 写入：owner_fp 必须匹配请求者
    if (owner_fp !== fingerprint) {
      return Response.json(
        { error: "Cannot write to another user's namespace" }, 
        { status: 403, headers: corsHeaders }
      );
    }
  } else {
    // 读取：检查 manifest.access
    const accessAllowed = await checkReadAccess(env, ctx, capsule_id, fingerprint);
    if (!accessAllowed) {
      return Response.json(
        { error: "Access denied" }, 
        { status: 403, headers: corsHeaders }
      );
    }
  }
  
  // 6. 生成 Presigned URLs
  const expiresIn = 3600;  // 1 小时
  const presigner = new R2Presigner(env);
  
  const urls: Record<string, any> = {};
  const prefix = `capsules/${capsule_id}`;
  
  if (action === "read") {
    // 读取：为 manifest 和所有 blobs 生成 GET URL
    urls.manifest = await presigner.presignGet(`${prefix}/manifest.json`, expiresIn);
    urls.redaction_report = await presigner.presignGet(`${prefix}/redaction.report.json`, expiresIn);
    
    // 列出所有 blobs 并生成 URL
    const blobList = await env.R2.list({ prefix: `${prefix}/blobs/` });
    urls.blobs = {};
    for (const obj of blobList.objects) {
      const blobId = obj.key.split("/").pop()!;
      urls.blobs[blobId] = await presigner.presignGet(obj.key, expiresIn);
    }
  } else {
    // 写入：为指定的 blobs 生成 PUT URL
    urls.manifest = await presigner.presignPut(`${prefix}/manifest.json`, expiresIn);
    urls.redaction_report = await presigner.presignPut(`${prefix}/redaction.report.json`, expiresIn);
    
    urls.blobs = {};
    for (const blobId of (blobs || [])) {
      urls.blobs[blobId] = await presigner.presignPut(`${prefix}/blobs/${blobId}`, expiresIn);
    }
  }
  
  return Response.json({
    expires_at: now + expiresIn,
    urls
  }, { headers: corsHeaders });
}

async function checkReadAccess(
  env: Env, 
  ctx: ExecutionContext,
  capsule_id: string, 
  fingerprint: string
): Promise<boolean> {
  // 尝试从 Cache 读取 manifest
  const cacheKey = `https://cache.internal/manifest/${capsule_id}`;
  const cache = caches.default;
  
  let manifestResponse = await cache.match(cacheKey);
  
  if (!manifestResponse) {
    // Cache miss：从 R2 读取
    const object = await env.R2.get(`capsules/${capsule_id}/manifest.json`);
    if (!object) {
      return false;  // Capsule 不存在
    }
    
    const text = await object.text();
    manifestResponse = new Response(text, {
      headers: { "Cache-Control": "max-age=300" }  // 缓存 5 分钟
    });
    
    // 异步写入 Cache
    ctx.waitUntil(cache.put(cacheKey, manifestResponse.clone()));
  }
  
  const manifest = await manifestResponse.json() as any;
  const access = manifest.access || {};
  
  // 检查权限
  if (access.public === true) return true;
  if (access.owner === `ed25519:${fingerprint}`) return true;
  if (access.readers?.includes(`ed25519:${fingerprint}`)) return true;
  
  return false;
}

/**
 * R2 Presigned URL 生成器
 * 使用 aws4fetch 库生成兼容 S3 的签名 URL
 */
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
      aws: { signQuery: true, expiresIn }
    });
    return signed.url;
  }
  
  async presignPut(key: string, expiresIn: number): Promise<string> {
    const url = new URL(`${this.endpoint}/${this.bucket}/${key}`);
    const signed = await this.client.sign(url.toString(), {
      method: "PUT",
      aws: { signQuery: true, expiresIn }
    });
    return signed.url;
  }
}

// ============ 工具函数 ============

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
```

### 4.3 部署配置

```toml
# worker/wrangler.toml

name = "resurrectum-api"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[r2_buckets]]
binding = "R2"
bucket_name = "resurrectum-capsules"

[vars]
R2_ACCOUNT_ID = "your-account-id"
R2_BUCKET_NAME = "resurrectum-capsules"

# 使用 wrangler secret 设置敏感变量
# wrangler secret put R2_ACCESS_KEY_ID
# wrangler secret put R2_SECRET_ACCESS_KEY
```

```json
// worker/package.json
{
  "name": "resurrectum-api",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "tail": "wrangler tail"
  },
  "dependencies": {
    "@noble/ed25519": "^2.0.0",
    "aws4fetch": "^1.0.18"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20240117.0",
    "typescript": "^5.3.0",
    "wrangler": "^3.22.0"
  }
}
```

### 4.4 Rate Limiting 配置

在 Cloudflare Dashboard 中配置：

```yaml
规则名称: Resurrectum API Rate Limit
匹配条件: 
  - URI Path: /presign
限制:
  - 每 IP 每分钟: 60 次
  - 每 IP 每小时: 500 次
动作: 
  - 超限返回 429
```

> **配置路径**：Cloudflare Dashboard → 选择域名 → Security → WAF → Rate limiting rules

---

## 5. 客户端优化

### 5.1 URL 缓存

> **说明**：由于采用 Presigned URL 方案，缓存的是签名 URL 而不是凭证。
> URL 缓存已集成在 `PresignedUrlBackend` 类中（见 3.2 章）。

对于持久化缓存（跨进程复用），可添加文件缓存：

```python
# src/resurrectum/summon/url_cache.py

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PresignedUrlCache:
    """
    Presigned URL 持久化缓存
    
    用于跨进程复用签名 URL，减少对凭证服务的请求
    """
    
    cache_dir: Path = field(
        default_factory=lambda: Path.home() / ".resurrectum" / "cache"
    )
    buffer_seconds: int = 300  # 提前 5 分钟刷新
    
    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _cache_path(self, capsule_id: str) -> Path:
        """获取缓存文件路径"""
        # capsule_id 格式: owner_fp/uuid
        safe_id = capsule_id.replace("/", "_")
        return self.cache_dir / f"urls_{safe_id}.json"
    
    def get(self, capsule_id: str) -> Optional[dict]:
        """从缓存获取 Presigned URLs"""
        path = self._cache_path(capsule_id)
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text())
            expires_at = data.get("expires_at", 0)
            
            if time.time() < expires_at - self.buffer_seconds:
                return data.get("urls")
            
            # 已过期，删除缓存
            path.unlink(missing_ok=True)
            return None
            
        except (json.JSONDecodeError, TypeError, KeyError):
            path.unlink(missing_ok=True)
            return None
    
    def set(self, capsule_id: str, urls: dict, expires_at: int) -> None:
        """写入缓存"""
        path = self._cache_path(capsule_id)
        path.write_text(json.dumps({
            "urls": urls,
            "expires_at": expires_at,
        }))
        # 设置安全权限（跨平台）
        self._set_secure_permissions(path)
    
    def clear(self, capsule_id: Optional[str] = None) -> None:
        """清除缓存"""
        if capsule_id:
            self._cache_path(capsule_id).unlink(missing_ok=True)
        else:
            for path in self.cache_dir.glob("urls_*.json"):
                path.unlink(missing_ok=True)
    
    def _set_secure_permissions(self, path: Path) -> None:
        """跨平台设置安全权限"""
        if os.name != "nt":  # Unix/Linux/macOS
            path.chmod(0o600)
        # Windows: 默认权限已足够安全（用户级别隔离）
```

### 5.2 CLI 集成

```python
# src/resurrectum/cli.py

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from .summon.storage import LocalDirBackend, PresignedUrlBackend
from .summon.url_cache import PresignedUrlCache
from .sigil.crypto import generate_keypair, get_fingerprint


@click.group()
def cli():
    """Resurrectum - Soul Immortality for AI Agents"""
    pass


# ============ 身份管理 ============

@cli.command()
@click.option("--output", "-o", default="~/.resurrectum/identity", help="Output path prefix")
def init(output: str):
    """Initialize identity (generate Ed25519 keypair)"""
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    private_key_path = output_path.with_suffix(".key")
    public_key_path = output_path.with_suffix(".pub")
    
    if private_key_path.exists():
        click.echo(f"Identity already exists: {private_key_path}")
        click.echo("Use --output to specify a different path.")
        return
    
    # 生成密钥对
    private_key, public_key = generate_keypair()
    fingerprint = get_fingerprint(public_key)
    
    # 保存密钥
    private_key_path.write_bytes(private_key)
    private_key_path.chmod(0o600)
    
    public_key_path.write_bytes(public_key)
    
    click.echo(f"Identity generated!")
    click.echo(f"  Private key: {private_key_path}")
    click.echo(f"  Public key:  {public_key_path}")
    click.echo(f"  Fingerprint: {fingerprint}")
    click.echo("")
    click.echo("⚠️  IMPORTANT: Back up your private key!")
    click.echo("    If lost, you cannot recover your capsules.")


# ============ 导出/导入 ============

@cli.command()
@click.option("--workspace", "-w", default=".", help="Workspace path")
@click.option("--out", "-o", required=True, help="Output path (local) or 'remote'")
@click.option("--passphrase", default="prompt", help="Passphrase: prompt | env:VAR | file:PATH")
@click.option("--signing-key", required=True, help="Ed25519 signing key: file:PATH")
@click.option("--credential-service", 
              default="https://api.resurrectum.dev", 
              envvar="RESURRECTUM_CREDENTIAL_SERVICE",
              help="Credential service URL")
@click.option("--dry-run", is_flag=True, help="Only generate redaction report")
def export(workspace, out, passphrase, signing_key, credential_service, dry_run):
    """Export workspace to encrypted capsule"""
    from .summon.capsule import export_capsule
    
    workspace_path = Path(workspace).resolve()
    signing_key_path = Path(signing_key.replace("file:", "")).expanduser()
    
    # 选择后端
    if out == "remote":
        backend = PresignedUrlBackend(
            credential_service_url=credential_service,
            signing_key_path=signing_key_path,
        )
        click.echo(f"Using remote storage: {credential_service}")
    else:
        out_path = Path(out).resolve()
        backend = LocalDirBackend(root=out_path)
        click.echo(f"Using local storage: {out_path}")
    
    # 获取密码
    if passphrase == "prompt":
        passphrase_value = click.prompt("Passphrase", hide_input=True)
    elif passphrase.startswith("env:"):
        import os
        passphrase_value = os.environ.get(passphrase[4:], "")
    elif passphrase.startswith("file:"):
        passphrase_value = Path(passphrase[5:]).read_text().rstrip("\n\r")
    else:
        passphrase_value = passphrase
    
    # 执行导出
    result = export_capsule(
        workspace=workspace_path,
        backend=backend,
        passphrase=passphrase_value,
        signing_key_path=signing_key_path,
        dry_run=dry_run,
    )
    
    click.echo(f"Capsule ID: {result.capsule_id}")
    if dry_run:
        click.echo("Dry run complete. See redaction report.")
    else:
        click.echo(f"Export complete. {result.artifact_count} artifacts.")


@cli.command("import")
@click.option("--from", "from_", required=True, help="Capsule ID or path")
@click.option("--to", required=True, help="Target workspace path")
@click.option("--passphrase", default="prompt", help="Passphrase: prompt | env:VAR | file:PATH")
@click.option("--trusted-signer", required=True, help="Fingerprint or file:PATH")
@click.option("--credential-service",
              default="https://api.resurrectum.dev",
              envvar="RESURRECTUM_CREDENTIAL_SERVICE",
              help="Credential service URL")
@click.option("--overwrite", is_flag=True, help="Overwrite existing files")
def import_(from_, to, passphrase, trusted_signer, credential_service, overwrite):
    """Import workspace from encrypted capsule"""
    from .summon.capsule import import_capsule
    
    # ... 类似 export 的实现
    click.echo("Import complete.")


# ============ 缓存管理 ============

@cli.group()
def cache():
    """Manage URL cache"""
    pass


@cache.command("clear")
@click.option("--capsule-id", help="Clear specific capsule cache")
def cache_clear(capsule_id: str | None):
    """Clear cached presigned URLs"""
    url_cache = PresignedUrlCache()
    url_cache.clear(capsule_id)
    click.echo("Cache cleared.")


@cache.command("info")
def cache_info():
    """Show cache status"""
    url_cache = PresignedUrlCache()
    files = list(url_cache.cache_dir.glob("urls_*.json"))
    
    if not files:
        click.echo("No cached URLs.")
        return
    
    click.echo(f"Cached URLs: {len(files)}")
    for f in files:
        try:
            data = json.loads(f.read_text())
            expires = data.get("expires_at", 0)
            remaining = int(expires - time.time())
            status = "valid" if remaining > 0 else "expired"
            capsule_id = f.stem.replace("urls_", "").replace("_", "/")
            click.echo(f"  {capsule_id}: {status} ({remaining}s)")
        except Exception:
            click.echo(f"  {f.stem}: corrupted")


# ============ 入口点 ============

def main():
    cli()


if __name__ == "__main__":
    main()
```

### 5.3 7z 压缩优化

> **设计目标**：在上传前将所有文件打包为 7z 格式，显著节约存储空间（尤其对文本类文件）。

#### 5.3.1 压缩工作流

```
Export 流程（带压缩）:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 扫描     │───>│ 过滤     │───>│ 打包 7z  │───>│ 加密     │───>│ 上传     │
│ workspace│    │ 排除项   │    │ 压缩     │    │ 签名     │    │ 单个blob │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘

Import 流程（带解压）:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 下载     │───>│ 验签     │───>│ 解密     │───>│ 解压 7z  │
│ blob     │    │ 解密     │    │ 数据     │    │ 还原文件 │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

#### 5.3.2 Manifest 扩展

```json
{
  "spec_version": "v1",
  "schema_version": "1.1.0",
  "capsule_id": "owner_fp/uuid",
  "compression": {
    "enabled": true,
    "algorithm": "7z",
    "level": 9,
    "original_size_bytes": 1234567,
    "compressed_size_bytes": 345678,
    "compression_ratio": 0.28
  },
  "artifacts": [...],
  "blobs": [
    {
      "blob_id": "sha256_of_encrypted_7z",
      "is_archive": true,
      "archive_format": "7z"
    }
  ]
}
```

#### 5.3.3 实现

```python
# src/resurrectum/summon/compression.py

from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False


@dataclass(frozen=True)
class CompressionOptions:
    """压缩选项"""
    enabled: bool = True
    algorithm: str = "7z"
    level: int = 9  # 0-9, 9 = 最大压缩
    
    def __post_init__(self):
        if self.enabled and not HAS_7Z:
            raise RuntimeError(
                "py7zr is required for 7z compression. "
                "Install with: pip install py7zr"
            )


@dataclass
class CompressionResult:
    """压缩结果"""
    archive_data: bytes
    original_size: int
    compressed_size: int
    file_count: int
    
    @property
    def compression_ratio(self) -> float:
        if self.original_size == 0:
            return 1.0
        return self.compressed_size / self.original_size


def compress_files(
    workspace: Path,
    file_paths: list[str],
    options: CompressionOptions,
) -> CompressionResult:
    """
    将文件压缩为 7z 格式
    
    Args:
        workspace: 工作区根目录
        file_paths: 相对路径列表
        options: 压缩选项
    
    Returns:
        CompressionResult 包含压缩后的数据
    """
    if not options.enabled:
        raise ValueError("Compression is disabled")
    
    original_size = 0
    buffer = io.BytesIO()
    
    # 使用 py7zr 创建 7z 压缩包
    with py7zr.SevenZipFile(buffer, mode="w") as archive:
        # 设置压缩级别
        archive.set_encoded_header_mode(True)
        
        for rel_path in file_paths:
            full_path = workspace / rel_path
            if full_path.is_file():
                file_data = full_path.read_bytes()
                original_size += len(file_data)
                # 添加到压缩包，保持相对路径结构
                archive.writestr(file_data, rel_path)
    
    archive_data = buffer.getvalue()
    
    return CompressionResult(
        archive_data=archive_data,
        original_size=original_size,
        compressed_size=len(archive_data),
        file_count=len(file_paths),
    )


def decompress_archive(
    archive_data: bytes,
    target_dir: Path,
    expected_files: Optional[list[str]] = None,
) -> list[str]:
    """
    解压 7z 压缩包
    
    Args:
        archive_data: 压缩数据
        target_dir: 解压目标目录
        expected_files: 预期文件列表（用于验证）
    
    Returns:
        解压出的文件路径列表
    """
    buffer = io.BytesIO(archive_data)
    extracted_files = []
    
    with py7zr.SevenZipFile(buffer, mode="r") as archive:
        # 获取所有文件名
        names = archive.getnames()
        
        # 可选：验证文件列表
        if expected_files is not None:
            expected_set = set(expected_files)
            actual_set = set(names)
            if expected_set != actual_set:
                missing = expected_set - actual_set
                extra = actual_set - expected_set
                raise ValueError(
                    f"Archive content mismatch. "
                    f"Missing: {missing}, Extra: {extra}"
                )
        
        # 解压所有文件
        archive.extractall(path=target_dir)
        extracted_files = names
    
    return extracted_files


def estimate_compression_ratio(sample_data: bytes) -> float:
    """
    估算压缩率（用于 dry-run 预估）
    
    基于小样本快速估算，不实际压缩全部数据
    """
    if len(sample_data) < 1024:
        return 0.5  # 小文件默认估算
    
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, mode="w") as archive:
        archive.writestr(sample_data[:min(len(sample_data), 65536)], "sample")
    
    compressed = len(buffer.getvalue())
    original = min(len(sample_data), 65536)
    return compressed / original if original > 0 else 1.0
```

#### 5.3.4 集成到 capsule.py

```python
# src/resurrectum/summon/capsule.py 修改

from .compression import (
    CompressionOptions,
    CompressionResult,
    compress_files,
    decompress_archive,
    HAS_7Z,
)


@dataclass(frozen=True)
class ExportOptions:
    workspace: Path
    backend: StorageBackend
    passphrase: str | None
    signing_key_pem: bytes | None
    policy: RedactionPolicy
    aead: str = "xchacha20-poly1305"
    argon2_params: Argon2Params = Argon2Params()
    strict: bool = True
    dry_run: bool = False
    # 新增：压缩选项
    compression: CompressionOptions = CompressionOptions()


def export_capsule(options: ExportOptions) -> tuple[str, dict[str, Any]]:
    """导出 capsule（带可选 7z 压缩）"""
    capsule_id = str(uuidv7())
    report = options.policy.scan_workspace(options.workspace)
    report["capsule_id"] = capsule_id

    if options.strict and any(
        decision["class"] == "forbidden" 
        for decision in report["decisions"]
    ):
        _write_redaction_report(options.backend, capsule_id, report)
        raise PolicyViolationError("Forbidden findings detected.")

    if options.dry_run:
        _write_redaction_report(options.backend, capsule_id, report)
        return capsule_id, report

    if not options.passphrase or not options.signing_key_pem:
        raise CapsuleError("Passphrase and signing key required.")

    master_salt = _random_salt()
    master_key = derive_master_key(
        options.passphrase, master_salt, options.argon2_params
    )

    # 收集要包含的文件
    included_files = [
        d["path"] for d in report["decisions"] 
        if d["decision"] != "exclude"
    ]

    artifacts: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []
    compression_info: dict[str, Any] = {"enabled": False}

    if options.compression.enabled and included_files:
        # === 7z 压缩模式 ===
        compress_result = compress_files(
            workspace=options.workspace,
            file_paths=included_files,
            options=options.compression,
        )
        
        # 加密压缩后的数据
        nonce, ciphertext = encrypt_payload(
            compress_result.archive_data, 
            master_key, 
            options.aead
        )
        blob_id = blob_id_for_ciphertext(ciphertext)
        ref = options.backend.put_blob(capsule_id, blob_id, ciphertext)
        
        # 单个 blob 条目（压缩包）
        blobs.append({
            "blob_id": blob_id,
            "ciphertext_hash": blob_id,
            "ciphertext_size_bytes": len(ciphertext),
            "nonce": base64url_encode(nonce),
            "storage": {"backend": _backend_name(options.backend), "ref": ref},
            "is_archive": True,
            "archive_format": "7z",
        })
        
        # artifacts 仍然列出所有文件（用于元数据）
        for decision in report["decisions"]:
            if decision["decision"] == "exclude":
                continue
            rel_path = decision["path"]
            full_path = options.workspace / rel_path
            payload = full_path.read_bytes()
            artifacts.append({
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "mode": decision["decision"],
                "plaintext_hash": sha256_hex(payload),
                "size_bytes": len(payload),
                "blob_id": blob_id,  # 所有文件指向同一个 blob
            })
        
        compression_info = {
            "enabled": True,
            "algorithm": options.compression.algorithm,
            "level": options.compression.level,
            "original_size_bytes": compress_result.original_size,
            "compressed_size_bytes": compress_result.compressed_size,
            "compression_ratio": round(compress_result.compression_ratio, 4),
        }
    else:
        # === 原有逻辑：每文件单独加密 ===
        for decision in report["decisions"]:
            if decision["decision"] == "exclude":
                continue
            rel_path = decision["path"]
            full_path = options.workspace / rel_path
            payload = full_path.read_bytes()
            plaintext_hash = sha256_hex(payload)
            nonce, ciphertext = encrypt_payload(payload, master_key, options.aead)
            blob_id = blob_id_for_ciphertext(ciphertext)
            ref = options.backend.put_blob(capsule_id, blob_id, ciphertext)
            blobs.append({
                "blob_id": blob_id,
                "ciphertext_hash": blob_id,
                "ciphertext_size_bytes": len(ciphertext),
                "nonce": base64url_encode(nonce),
                "storage": {"backend": _backend_name(options.backend), "ref": ref},
            })
            artifacts.append({
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "mode": decision["decision"],
                "plaintext_hash": plaintext_hash,
                "size_bytes": len(payload),
                "blob_id": blob_id,
            })

    manifest = build_manifest(
        capsule_id=capsule_id,
        aead=options.aead,
        salt=master_salt,
        params=options.argon2_params,
        artifacts=artifacts,
        blobs=blobs,
        policy_version=options.policy.policy_version,
        compression=compression_info,  # 新增
    )
    manifest["signature"] = sign_manifest(manifest, options.signing_key_pem)

    _write_redaction_report(options.backend, capsule_id, report)
    _write_manifest(options.backend, capsule_id, manifest)
    return capsule_id, manifest
```

#### 5.3.5 CLI 参数

```python
# CLI export 命令新增参数

@cli.command()
@click.option("--workspace", "-w", default=".", help="Workspace path")
@click.option("--out", "-o", required=True, help="Output path or 'remote'")
@click.option("--passphrase", default="prompt", help="Passphrase source")
@click.option("--signing-key", required=True, help="Ed25519 signing key")
# 新增压缩选项
@click.option("--compress/--no-compress", default=True, 
              help="Enable 7z compression (default: enabled)")
@click.option("--compression-level", type=click.IntRange(0, 9), default=9,
              help="Compression level 0-9 (default: 9 = max)")
def export(workspace, out, passphrase, signing_key, compress, compression_level):
    """Export workspace to encrypted capsule"""
    
    compression_opts = CompressionOptions(
        enabled=compress,
        algorithm="7z",
        level=compression_level,
    )
    
    # ... 其余逻辑
```

#### 5.3.6 依赖

```toml
# pyproject.toml 新增依赖

[project.optional-dependencies]
compression = [
    "py7zr>=0.20.0",
]

# 或者作为默认依赖
[project]
dependencies = [
    "py7zr>=0.20.0",
    # ... 其他依赖
]
```

#### 5.3.7 压缩效果预估

| 文件类型 | 典型压缩率 | 说明 |
|---------|-----------|------|
| Markdown (.md) | 15-25% | 文本类压缩效果最佳 |
| JSON | 10-20% | 结构化文本 |
| Python (.py) | 20-30% | 代码文件 |
| 已压缩文件 | 95-100% | 几乎无压缩收益 |

**预估存储节省**：对于典型的 AI Agent 工作区（主要是文本文件），预计可节省 **60-80%** 存储空间。

---

### 5.4 Fallback 机制（v1.1+）

```python
# src/resurrectum/summon/storage.py

@dataclass
class FallbackBackend:
    """带 Fallback 的存储后端（v1.1+）"""
    
    primary: StorageBackend
    fallback: Optional[StorageBackend] = None
    
    def get_blob(self, ref: str) -> bytes:
        try:
            return self.primary.get_blob(ref)
        except Exception as e:
            if self.fallback:
                logger.warning(f"Primary failed, trying fallback: {e}")
                return self.fallback.get_blob(ref)
            raise
    
    # ... 其他方法类似
```

---

## 6. 官网设计

### 6.1 技术栈

| 选项 | 优点 | 缺点 | 推荐 |
|------|------|------|:----:|
| **Astro** | 快速、静态优先、MD 支持好 | 生态较新 | ⭐ |
| VitePress | Vue 生态、文档专用 | 定制稍复杂 | |
| Hugo | 极快构建 | Go 模板学习曲线 | |

### 6.2 站点结构

```
resurrectum.dev/
├── /                    # 首页 - 项目介绍
├── /docs/               # 文档 - 从 docs/*.md 构建
│   ├── /docs/quickstart/
│   ├── /docs/architecture/
│   ├── /docs/cli/
│   └── /docs/security/
├── /download/           # 下载
│   ├── PyPI 链接
│   ├── GitHub Releases
│   └── 安装命令
├── /faq/                # 常见问题
└── /status/             # 状态页
    └── 调用 /health API
```

### 6.3 部署

```yaml
# .github/workflows/deploy-site.yml

name: Deploy Site

on:
  push:
    branches: [main]
    paths:
      - 'site/**'
      - 'docs/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
      
      - name: Build
        working-directory: site
        run: |
          npm ci
          npm run build
      
      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          projectName: resurrectum
          directory: site/dist
```

---

## 7. 安全与防滥用

### 7.1 安全检查清单

| 检查项 | 状态 | 说明 |
|--------|:----:|------|
| E2EE 加密 | ✅ | 现有 v1 已实现 |
| Manifest 签名 | ✅ | 现有 v1 已实现 |
| 请求签名验证 | 🆕 | 凭证服务实现 |
| 时间戳防重放 | 🆕 | 5 分钟窗口 |
| Rate Limiting | 🆕 | CF 配置 |
| 临时凭证 | 🆕 | 1 小时有效期 |
| 路径限制 | 🆕 | 凭证只能访问特定 prefix |

### 7.2 Rate Limiting 策略

```yaml
层级限制:
  1. IP 层面:
     - /credentials: 60/分钟, 500/小时
     - /health: 无限制

  2. 公钥层面 (未来):
     - 每公钥每天: 1000 次凭证请求
     - 每公钥存储配额: 10GB (可调)
```

### 7.3 不实现的安全措施

| 措施 | 原因 |
|------|------|
| KV 配额跟踪 | 违背"无状态"原则 |
| PoW 工作量证明 | 增加用户摩擦，过度设计 |
| 邮箱验证 | 违背去中心化身份原则 |

---

## 8. 去中心化演进路径

### 8.1 阶段规划

```
Phase 1 (v1.0) - 当前
┌─────────────────────────────────────────┐
│  客户端 → 凭证服务 → R2               │
│  中心化凭证 + 托管存储                  │
└─────────────────────────────────────────┘
     │
     │ 添加 IPFS 后端
     ▼
Phase 2 (v1.1) - 混合存储
┌─────────────────────────────────────────┐
│  客户端 → 凭证服务 → R2 + IPFS        │
│  中心化凭证 + 混合存储                  │
│  公开 capsule 可直接 IPFS 访问          │
└─────────────────────────────────────────┘
     │
     │ 添加 IPNS/链上索引
     ▼
Phase 3 (v2.0) - 完全去中心化
┌─────────────────────────────────────────┐
│  客户端 → IPFS + DHT/链上索引          │
│  无凭证服务，完全 P2P                    │
│  访问控制通过加密实现                    │
└─────────────────────────────────────────┘
```

### 8.2 Manifest 加密（为 Phase 3 准备）

在 v1.1 预留字段：

```json
{
  "schema_version": "1.1",
  "manifest_encryption": {
    "algorithm": "x25519-xchacha20-poly1305",
    "recipients": [
      {
        "public_key": "base64url(x25519_pk)",
        "encrypted_key": "base64url(encrypted_data_key)"
      }
    ]
  },
  "access": { ... },
  "artifacts": [ ... ]
}
```

### 8.3 IPFS 集成设计（v1.1）

```python
@dataclass
class IPFSBackend:
    """IPFS 存储后端"""
    
    api_url: str = "http://localhost:5001"
    gateway_url: str = "https://ipfs.io"
    pin_service: Optional[str] = None  # Pinata/Infura
    
    def put_blob(self, capsule_id: str, blob_id: str, data: bytes) -> str:
        """上传到 IPFS"""
        import requests
        
        files = {"file": data}
        resp = requests.post(f"{self.api_url}/api/v0/add", files=files)
        result = resp.json()
        cid = result["Hash"]
        
        # 可选：pin 到远程服务
        if self.pin_service:
            self._pin_remote(cid)
        
        return f"ipfs://{cid}"
    
    def get_blob(self, ref: str) -> bytes:
        """从 IPFS 下载"""
        import requests
        
        cid = ref.replace("ipfs://", "")
        
        # 尝试本地网关
        try:
            resp = requests.get(
                f"{self.api_url}/api/v0/cat?arg={cid}",
                timeout=10
            )
            if resp.ok:
                return resp.content
        except:
            pass
        
        # 回退到公共网关
        resp = requests.get(f"{self.gateway_url}/ipfs/{cid}", timeout=30)
        resp.raise_for_status()
        return resp.content
```

---

## 9. 实施计划

### 9.1 里程碑

```
M1: 核心基础 (2 周)
├── [ ] CredentialedS3Backend 实现
├── [ ] 凭证缓存实现
├── [ ] CLI 集成
└── [ ] 本地测试通过

M2: 凭证服务 (1 周)
├── [ ] Worker 代码实现
├── [ ] R2 存储桶配置
├── [ ] Rate Limiting 配置
└── [ ] 部署到 Cloudflare

M3: 集成测试 (1 周)
├── [ ] 端到端测试
├── [ ] 性能测试
├── [ ] 安全审查
└── [ ] 文档更新

M4: 官网 (1 周)
├── [ ] Astro 项目初始化
├── [ ] 文档迁移
├── [ ] 部署到 CF Pages
└── [ ] 域名配置

M5: 发布 (1 周)
├── [ ] PyPI 发布
├── [ ] GitHub Release
├── [ ] 公告
└── [ ] 监控配置
```

### 9.2 详细任务清单

#### P0 - 阻塞性任务

| 任务 | 文件 | 预估 | 状态 |
|------|------|------|:----:|
| 实现 PresignedUrlBackend | `src/resurrectum/summon/storage.py` | 4h | ⬜ |
| 实现 PresignedUrlCache | `src/resurrectum/summon/url_cache.py` | 1h | ⬜ |
| CLI 实现（init/export/import/cache） | `src/resurrectum/cli.py` | 4h | ⬜ |
| 凭证服务 Worker 实现 | `worker/src/index.ts` | 4h | ⬜ |
| manifest.access 字段 schema | `docs/schemas/v1/capsule.manifest.schema.json` | 1h | ⬜ |
| capsule_id 格式变更 | 多处 | 2h | ⬜ |

#### P1 - 重要任务

| 任务 | 文件 | 预估 | 状态 |
|------|------|------|:----:|
| Worker Cache API 集成 | `worker/src/index.ts` | 已包含 | ✅ |
| Worker CORS 支持 | `worker/src/index.ts` | 已包含 | ✅ |
| CF Rate Limiting 配置 | Dashboard | 0.5h | ⬜ |
| 端到端测试 | `tests/e2e/` | 4h | ⬜ |
| 更新架构文档 | `docs/02-ARCHITECTURE.md` | 2h | ⬜ |

#### P2 - 可延后任务

| 任务 | 文件 | 预估 | 状态 |
|------|------|------|:----:|
| 官网 Astro 项目 | `site/` | 8h | ⬜ |
| FallbackBackend | `src/resurrectum/summon/storage.py` | 2h | ⬜ |
| IPFSBackend 骨架 | `src/resurrectum/summon/storage.py` | 2h | ⬜ |
| manifest_encryption 预留字段 | `docs/schemas/` | 1h | ⬜ |

### 9.3 文件变更清单

```
新增文件:
├── src/resurrectum/summon/url_cache.py       # Presigned URL 缓存
├── worker/                                    # 凭证服务 (Presigned URL)
│   ├── src/index.ts
│   ├── wrangler.toml
│   ├── package.json
│   └── tsconfig.json
├── site/                                      # 官网 (P2)
│   ├── astro.config.mjs
│   ├── src/pages/
│   └── ...
└── docs/13-CONSTRUCTION-PLAN.md              # 本文档

修改文件:
├── src/resurrectum/summon/storage.py         # 添加 PresignedUrlBackend
├── src/resurrectum/cli.py                    # 完整 CLI 实现
├── src/resurrectum/sigil/crypto.py           # 添加 generate_keypair, get_fingerprint
├── docs/02-ARCHITECTURE.md                   # 更新架构说明
├── docs/03-SCHEMAS.md                        # 添加 access 字段, capsule_id 格式
├── docs/05-STORAGE-BACKENDS.md               # 添加 Presigned URL 后端说明
└── pyproject.toml                            # 添加 click 依赖
```

### 9.4 关键设计决策记录

| 决策 | 选项 | 结果 | 理由 |
|------|------|------|------|
| 凭证方案 | STS / Presigned URL / 代理 | **Presigned URL** | R2 不支持 STS，代理增加延迟 |
| capsule_id 格式 | uuid / owner_fp/uuid | **owner_fp/uuid** | 便于权限检查，路径自描述 |
| 存储路径 | 兼容旧版 / 全新 | **全新** | 新项目无历史包袱 |
| URL 缓存 | 内存 / 文件 | **两者** | 内存用于进程内，文件用于跨进程 |

---

## 10. 成本估算

### 10.1 Cloudflare 成本（推荐方案）

| 服务 | 免费额度 | 超出价格 | 预估月成本 |
|------|---------|---------|-----------|
| Pages | 无限 | - | $0 |
| Workers | 100k/天 | $0.50/百万 | $0 |
| R2 存储 | 10GB | $0.015/GB | $0-15 |
| R2 Class A | 1M/月 | $4.50/百万 | $0 |
| R2 Class B | 10M/月 | $0.36/百万 | $0 |
| 域名 | - | ~$10/年 | ~$1 |

**1000 用户场景预估**: ~$15/月

### 10.2 与 AWS 对比

| 服务 | AWS 成本 | CF 成本 |
|------|---------|---------|
| 静态托管 | S3 + CloudFront ~$5 | $0 |
| 函数 | Lambda + API GW ~$10 | $0 |
| 存储 1TB | S3 ~$23 | R2 ~$15 |
| 出站流量 100GB | ~$9 | $0 |
| **总计** | ~$47/月 | ~$15/月 |

---

## 附录

### A. 域名规划

```
resurrectum.dev
├── resurrectum.dev              → 官网 (CF Pages)
│   ├── /docs/                   → 文档
│   ├── /download/               → 下载
│   └── /status/                 → 状态页
│
├── api.resurrectum.dev          → 凭证服务 (CF Workers)
│   ├── /health                  → 健康检查
│   └── /presign                 → Presigned URL 生成
│
└── (未来)
    ├── ipfs.resurrectum.dev     → IPFS 网关
    └── _dnslink.resurrectum.dev → IPNS 记录
```

### B. 环境变量

```bash
# 客户端环境变量
RESURRECTUM_PASSPHRASE=...                    # 加密密码（可选，也可用 prompt/file:）
RESURRECTUM_SIGNING_KEY=~/.resurrectum/identity.key  # 签名私钥路径
RESURRECTUM_CREDENTIAL_SERVICE=https://api.resurrectum.dev  # 凭证服务 URL

# 凭证服务 (Cloudflare Secrets)
# 设置方式: wrangler secret put <NAME>
R2_ACCOUNT_ID=...           # Cloudflare 账户 ID
R2_ACCESS_KEY_ID=...        # R2 API Token 的 Access Key
R2_SECRET_ACCESS_KEY=...    # R2 API Token 的 Secret Key
R2_BUCKET_NAME=resurrectum-capsules  # R2 存储桶名称
```

### B.1 Cloudflare R2 配置步骤

```bash
# 1. 创建 R2 存储桶
wrangler r2 bucket create resurrectum-capsules

# 2. 创建 R2 API Token (Dashboard > R2 > Manage R2 API Tokens)
#    - 权限: Object Read & Write
#    - 范围: 指定存储桶

# 3. 设置 Worker Secrets
wrangler secret put R2_ACCESS_KEY_ID
wrangler secret put R2_SECRET_ACCESS_KEY

# 4. 部署 Worker
cd worker
npm install
wrangler deploy
```

### C. 参考文档

- [Cloudflare R2 文档](https://developers.cloudflare.com/r2/)
- [Cloudflare Workers 文档](https://developers.cloudflare.com/workers/)
- [Ed25519 签名](https://ed25519.cr.yp.to/)
- [现有架构文档](./02-ARCHITECTURE.md)
- [CLI 规范](./04-CLI-SPEC.md)
- [安全威胁模型](./06-SECURITY-THREAT-MODEL.md)

---

**文档结束**

> 本文档应随实施进展持续更新。
