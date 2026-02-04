# Resurrectum — Security & Threat Model v1 (OpenClaw-only)

**Audience:** AI engineers / security reviewers

**v1 scope:** Security properties and threat model for OpenClaw-only Resurrectum v1.

## 0. Executive summary
Resurrectum v1 assumes **untrusted remote storage** and provides security via:

## Related docs
- Architecture overview: `02-ARCHITECTURE.md`
- Normative Machine Layer contracts: `03-SCHEMAS.md`
- Redaction boundary (normative): `07-REDACTION-POLICY.md`
- CLI behavior (normative): `04-CLI-SPEC.md`
- Conformance tests: `08-CONFORMANCE-TESTS.md`
- **E2EE** encryption (AEAD) for all exported payloads by default
- **Ciphertext-addressed blobs** (`blob_id = sha256(ciphertext_bytes)`) to avoid plaintext correlation
- **Manifest signing (required v1)** to ensure provenance and prevent silent substitution
- **Strict redaction policy** to prevent exporting secrets/PII by default

## 1. Assets to protect
- Agent continuity state (OpenClaw files): memory/persona/ops/project summaries
- Secrets embedded in files (API keys, tokens, cookies)
- User PII (names, addresses, identifiers) possibly present in logs
- Provenance: "who produced this capsule" and "has it been tampered with"

## 2. Adversary model
Assume attacker can:
- Read all remote-stored objects (blobs + documents)
- Modify / replace / replay old blobs and manifests
- Delete objects or partially withhold them
- Observe access patterns (which blob_ids requested)

Assume attacker cannot:
- Break modern cryptography (AEAD, Argon2id, Ed25519)
- Compromise the local machine at export time (if local is compromised, all bets are off)

## 3. Out of scope (v1)
- Protection against a fully compromised client device.
- TEEs / remote execution attestation.
- Preventing a collaborator who already decrypted data from copying it.

## 4. Security properties (v1 requirements)
### 4.1 Confidentiality
- All artifact payloads MUST be encrypted (AEAD); `include_plaintext` refers to unredacted bytes, not unencrypted storage.
- Manifest and redaction report MUST NOT contain secret values.
  - Recording Argon2id parameters + salt is required and does not violate confidentiality.
 - AEAD nonces MUST be unique per blob and generated with a CSPRNG.

### 4.2 Integrity
- Every blob MUST be verified by ciphertext hash (`blob_id`).
- Decrypted plaintext MUST be verified by `plaintext_hash` for deterministic restore.

### 4.3 Authenticity / provenance
- Manifest MUST be signed (**Ed25519, v1 locked**).
- Implementations MUST verify signature (over RFC 8785 JCS bytes; see `03-SCHEMAS.md`) before decrypt/restore.
- **Trust model (v1):** verifiers MUST pin/trust the expected signer (fingerprint or key file). Do not accept “any embedded public key” by default.

### 4.4 Safe defaults
- Default policy is strict/fail-closed.
- Forbidden findings MUST block export unless explicit override flag is provided.

## 5. Key management (v1)
### 5.1 Key source
- **Passphrase → Argon2id → Master Key (MK)** (v1 required)
  - Argon2id parameters and salt are stored in the manifest to ensure interoperability.

### 5.1.1 Recommended Argon2id parameters (v1)
Baseline defaults (tune up if hardware allows):
- `mem_kib`: `65536` (64 MiB)
- `iterations`: `3`
- `parallelism`: `1`
- `hash_len`: `32`

Implementations MUST record the actual parameters and salt used in the manifest.

### 5.2 Signing key source / operational model (v1)
- Export requires access to an Ed25519 **signing private key** provided out-of-band (e.g., `--signing-key file:PATH`).
- The capsule embeds the corresponding public key and its fingerprint in the manifest.
- Verification requires the operator/runtime to pin/trust the expected signer identity (fingerprint or key file). This prevents “anyone can mint a capsule” attacks.

### 5.2.1 Signing key generation (recommended)
Use Ed25519 keys in PKCS8 PEM format:
- `openssl genpkey -algorithm Ed25519 -out capsule-signing.key`
- `openssl pkey -in capsule-signing.key -pubout -out capsule-signing.pub`

Fingerprint = `sha256(raw_public_key_bytes)` (lowercase hex). The exporter SHOULD compute this from the public key file to avoid user error.

### 5.2 Recommendations
- Encourage long passphrases; enforce minimum length.
- Allow environment/file-based passphrase injection for automation, but warn.
- Never store passphrase or MK in capsule.

### 5.3 Recovery
- If passphrase is lost, capsule is unrecoverable (expected).
- Provide guidance: password manager, offline recovery phrase (future).

## 6. Redaction boundary (security boundary)
The redaction policy defines what becomes **canonical revived state**.
- If excluded/redacted, it is not part of the revived agent.
- This is intentional to avoid "reviving secrets" into environments where they should not exist.
Note: `include_plaintext` means unredacted bytes; encryption is still required in v1.

## 7. Common attacks & mitigations
- **Storage reads** → mitigated by E2EE
- **Blob substitution / tampering** → ciphertext hash check + signed manifest
- **Rollback attacks** (serve older manifest) → manifest `created_at` + (future) lineage `parents[]` + application policy
- **Metadata leakage** (file paths reveal info) → consider optional path encryption in future; v1 accepts path leakage inside manifest but avoids secret values
- **Secret exfiltration via findings** → findings must never include raw secret substrings

## 8. Deletion semantics
- The system MUST NOT claim global deletion on untrusted/distributed systems.
- For IPFS (future), only promise: unpin + rotate keys for future data.

## 9. Security checklist for implementers
- [ ] AEAD encryption used for all payloads
- [ ] blob_id derived from ciphertext bytes
- [ ] manifest signature verified before restore
- [ ] strict redaction policy enforced by default
- [ ] redaction report contains no secret substrings
- [ ] conformance tests cover tamper, wrong passphrase, forbidden findings
- [ ] manifest records Argon2id parameters + salt and fixed HKDF info
