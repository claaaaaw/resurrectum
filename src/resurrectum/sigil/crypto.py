from __future__ import annotations

import copy
from dataclasses import dataclass
import os
from typing import Any

import rfc8785
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, XChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..utils import base64url_decode, base64url_encode, sha256_hex


class CryptoError(ValueError):
    pass


class SignatureError(CryptoError):
    pass


@dataclass(frozen=True)
class Argon2Params:
    mem_kib: int = 65536
    iterations: int = 3
    parallelism: int = 1
    hash_len: int = 32

    def to_dict(self) -> dict[str, int]:
        return {
            "mem_kib": self.mem_kib,
            "iterations": self.iterations,
            "parallelism": self.parallelism,
            "hash_len": self.hash_len,
        }


def derive_master_key(passphrase: str, salt: bytes, params: Argon2Params) -> bytes:
    if not passphrase:
        raise CryptoError("Passphrase cannot be empty.")
    if len(salt) < 16:
        raise CryptoError("Salt must be at least 16 bytes.")
    if params.hash_len != 32:
        raise CryptoError("Argon2id hash_len must be 32 bytes for v1.")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=params.iterations,
        memory_cost=params.mem_kib,
        parallelism=params.parallelism,
        hash_len=params.hash_len,
        type=Type.ID,
    )


def hkdf_derive_blob_key(master_key: bytes, nonce: bytes, info: str = "capsule:blob") -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=nonce,
        info=info.encode("utf-8"),
    )
    return hkdf.derive(master_key)


def generate_nonce(aead: str) -> bytes:
    if aead == "xchacha20-poly1305":
        return os.urandom(24)
    if aead == "aes-256-gcm":
        return os.urandom(12)
    raise CryptoError(f"Unsupported AEAD: {aead}")


def encrypt_payload(
    plaintext: bytes,
    master_key: bytes,
    aead: str = "xchacha20-poly1305",
    associated_data: bytes | None = None,
) -> tuple[bytes, bytes]:
    nonce = generate_nonce(aead)
    data_key = hkdf_derive_blob_key(master_key, nonce)
    if aead == "xchacha20-poly1305":
        cipher = XChaCha20Poly1305(data_key)
    elif aead == "aes-256-gcm":
        cipher = AESGCM(data_key)
    else:
        raise CryptoError(f"Unsupported AEAD: {aead}")
    ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def decrypt_payload(
    ciphertext: bytes,
    master_key: bytes,
    nonce: bytes,
    aead: str = "xchacha20-poly1305",
    associated_data: bytes | None = None,
) -> bytes:
    data_key = hkdf_derive_blob_key(master_key, nonce)
    if aead == "xchacha20-poly1305":
        cipher = XChaCha20Poly1305(data_key)
    elif aead == "aes-256-gcm":
        cipher = AESGCM(data_key)
    else:
        raise CryptoError(f"Unsupported AEAD: {aead}")
    try:
        return cipher.decrypt(nonce, ciphertext, associated_data)
    except InvalidTag as exc:
        raise CryptoError("Decryption failed: invalid tag or corrupted data") from exc


def blob_id_for_ciphertext(ciphertext: bytes) -> str:
    return sha256_hex(ciphertext)


def canonicalize_manifest_for_signing(manifest: dict[str, Any]) -> bytes:
    payload = copy.deepcopy(manifest)
    payload.pop("signature", None)
    return rfc8785.dumps(payload).encode("utf-8")


def sign_manifest(manifest: dict[str, Any], private_key_pem: bytes) -> dict[str, str]:
    try:
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    except (ValueError, TypeError) as exc:
        raise SignatureError("Invalid PEM format for signing key.") from exc
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise SignatureError("Signing key must be an Ed25519 private key.")
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signer_fingerprint = sha256_hex(public_key)
    sig_bytes = private_key.sign(canonicalize_manifest_for_signing(manifest))
    return {
        "alg": "ed25519",
        "payload_alg": "rfc8785_jcs_without_signature_utf8",
        "public_key": base64url_encode(public_key),
        "signer_fingerprint": signer_fingerprint,
        "sig": base64url_encode(sig_bytes),
    }


def verify_manifest_signature(
    manifest: dict[str, Any],
    trusted_fingerprints: set[str],
) -> None:
    signature = manifest.get("signature")
    if not isinstance(signature, dict):
        raise SignatureError("Manifest missing signature object.")
    public_key_b64 = signature.get("public_key")
    sig_b64 = signature.get("sig")
    signer_fingerprint = signature.get("signer_fingerprint")
    if not isinstance(public_key_b64, str) or not isinstance(sig_b64, str):
        raise SignatureError("Manifest signature is incomplete.")

    public_key_bytes = base64url_decode(public_key_b64)
    expected_fingerprint = sha256_hex(public_key_bytes)
    if signer_fingerprint != expected_fingerprint:
        raise SignatureError("Signer fingerprint mismatch.")
    if expected_fingerprint not in trusted_fingerprints:
        raise SignatureError("Signer is not trusted.")

    public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
    sig_bytes = base64url_decode(sig_b64)
    try:
        public_key.verify(sig_bytes, canonicalize_manifest_for_signing(manifest))
    except InvalidSignature as exc:
        raise SignatureError("Invalid manifest signature.") from exc
