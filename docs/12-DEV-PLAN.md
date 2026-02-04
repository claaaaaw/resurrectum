# Resurrectum — Dev Plan v1 (OpenClaw-only)

**Audience:** AI engineers / 项目负责人  
**v1 scope:** OpenClaw-only，严格遵循 Machine Layer 规范。  
**Status:** Draft

## 0. 目标
在 v1 范围内交付一个可实现、可验证、可审计的 Resurrectum 工具链，满足规范中的安全、兼容性与可用性要求。

## 1. 范围与前提
- v1 仅覆盖 OpenClaw 现有工作区布局，不修改现有文件格式。
- 规范优先级：Machine Layer（schemas/examples/conformance）高于人类文档。
- 交付必须满足严格默认策略、签名验证、加密与可验证恢复。

## 2. 关键规范依赖
- `03-SCHEMAS.md` 作为数据契约与签名规范来源。
- `04-CLI-SPEC.md` 作为 CLI 行为与退出码规范来源。
- `07-REDACTION-POLICY.md` 作为默认策略与报告规范来源。
- `08-CONFORMANCE-TESTS.md` 作为验收测试清单来源。

## 3. 里程碑与模块划分
每个模块包含交付物与验收条件，按依赖顺序推进。

### M1：规范落地与数据模型
**模块 A：工程基座与依赖选型**
- 交付物
- 工程结构与基础依赖
- JSON Schema 校验库、RFC8785 JCS 实现、Argon2id/AEAD/HKDF/Ed25519 依赖
- 验收
- 能加载并校验 `schemas/v1/*.schema.json`

**模块 B：Machine Layer 数据模型与校验**
- 交付物
- `capsule.manifest.json`、`redaction.report.json`、`restore.report.json` 的读写与校验
- `x_` 扩展字段处理规则
- 验收
- 示例文件可通过 schema 校验

### M2：安全边界与核心密码学
**模块 C：Redaction 策略与检测器**
- 交付物
- OpenClaw allowlist + denylist
- 探测器实现（API key/JWT/私钥/ cookie 等）
- `--dry-run` 仅生成 `redaction.report.json`
- 验收
- 报告不包含原始敏感值，决策覆盖全部候选文件

**模块 D：加密与签名**
- 交付物
- AEAD 加密、Argon2id 派生、HKDF、Ed25519 签名与验证
- `blob_id = sha256(ciphertext)` 与 RFC8785 JCS bytes-to-sign
- 验收
- 签名/解密失败可被严格拒绝

### M3：存储与导入导出流程
**模块 E：后端接口与本地后端**
- 交付物
- Storage 接口与 Local Dir 后端
- 原子写策略与写入顺序
- 验收
- 输出布局符合 `05-STORAGE-BACKENDS.md`

**模块 F：导出/导入/校验流程**
- 交付物
- `export/import/validate` 核心流程与退出码
- 严格模式与 `--dry-run` 语义
- 验收
- CLI 行为与 `04-CLI-SPEC.md` 一致

### M4：兼容性与扩展后端
**模块 G：恢复报告与兼容性处理**
- 交付物
- `restore.report.json` 输出
- 默认不覆盖与 `--overwrite` 行为
- 版本兼容处理（`spec_version`）
- 验收
- 与 `09-MIGRATION-COMPAT.md` 规则一致

**模块 H：S3/MinIO 后端**
- 交付物
- S3 兼容写入/读取与一致性处理
- 验收
- 对象布局与 `05-STORAGE-BACKENDS.md` 一致

### M5：验收与文档一致性
**模块 I：Conformance Tests + CI**
- 交付物
- Round-trip、严格策略、干跑、篡改检测、错误口令、信任签名等测试
- CI 运行与报告
- 验收
- 满足 `08-CONFORMANCE-TESTS.md` 全部必测项

**模块 J：文档与示例一致性**
- 交付物
- 示例文件与规范一致性检查
- 使用说明与最小工作流
- 验收
- 示例可被 schema 校验与测试套件验证

## 4. 交付物清单
- CLI：`openclaw summon export/import/validate`
- Machine Layer 文档与 schema 校验
- Redaction 策略与报告
- 加密、签名与验证
- Local Dir 后端
- S3/MinIO 后端
- Conformance Tests + CI
- 示例与使用说明

## 5. 验收标准（统一）
- 严格模式下 Forbidden 命中必须阻断导出。
- Manifest 必须签名，且必须验证通过后再解密恢复。
- `blob_id` 必须由密文哈希计算，且所有引用一致。
- `--dry-run` 不生成 manifest 与 blobs，仅输出 report。
- Import 必须在验证签名与哈希后恢复文件。

## 6. 风险与缓解
- 风险：JCS 实现不一致导致签名不可互通。
- 缓解：使用权威 RFC8785 实现，并以 conformance 测试锁定。
- 风险：红线文件误导出。
- 缓解：默认严格策略 + denylist + 探测器覆盖 + 纯报告 dry-run。
- 风险：后端一致性影响读取。
- 缓解：在 backend 层加入重试与回读验证。

## 7. 排期建议（模板）
- Week 1-2：M1
- Week 3-4：M2
- Week 5-6：M3
- Week 7：M4
- Week 8：M5

## 8. 变更管理
- 任何与 v1 锁定决策冲突的变更，记录于 `11-OPEN-QUESTIONS.md` 并移入 v1.1+ 或 v2 讨论。

## 9. 后续扩展（非 v1）
- Chunking、lineage、IPFS 冷备、路径加密等，参见 `10-ROADMAP.md`。
