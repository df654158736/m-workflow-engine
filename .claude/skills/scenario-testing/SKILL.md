---
name: scenario-testing
description: 端到端业务场景测试。用户写 YAML 场景描述，Claude 生成测试数据、脚本、执行并报告。
trigger: 用户提到"场景测试"、"端到端测试"、"e2e"、"scenario"、"全链路测试"
---

# 场景化测试

## 目录结构

```
tests/scenarios/
├── SC-{NNN}-{name}.yaml           ← 用户写的场景描述
├── data/                           ← 测试数据
│   ├── SC-{NNN}-*.sql
│   ├── SC-{NNN}-*.json
│   └── SC-{NNN}-*.csv
├── generated/                      ← Claude 生成的测试脚本
│   └── test_SC_{NNN}.py
└── results/
    └── SC-{NNN}-{date}.json
```

---

## 场景描述格式（用户编写）

```yaml
# tests/scenarios/SC-001-user-batch-import.yaml

id: SC-001
scenario: "用户批量导入"
description: |
  验证从文件上传到数据入库的全链路
priority: P0
modules_involved: [backend, frontend]

preconditions:
  services:
    - name: backend
      health: http://localhost:8000/health
  data_setup:
    - type: sql
      file: data/SC-001-init.sql

steps:
  - id: step-1
    name: "上传用户文件"
    method: POST
    url: /api/users/batch
    body_file: data/SC-001-users.json
    expect:
      status: 200
      json:
        imported_count: ">= 50"

  - id: step-2
    name: "查询导入结果"
    method: GET
    url: /api/users?batch_id={step-1.response.batch_id}
    expect:
      status: 200

teardown:
  - type: sql
    file: data/SC-001-cleanup.sql
```

---

## Claude 工作流程

1. **读取场景 YAML** — 解析前置条件、步骤、断言
2. **生成测试数据** — 根据 data_setup 生成 SQL/JSON fixtures
3. **生成测试脚本** — 输出 `generated/test_SC_{NNN}.py`（pytest）
4. **执行测试** — 运行并收集结果
5. **输出报告** — 保存到 `results/SC-{NNN}-{date}.json`

---

## 运行测试

```bash
# 运行单个场景
pytest tests/scenarios/generated/test_SC_001.py -v

# 运行所有 P0 场景
pytest tests/scenarios/generated/ -v -m "p0"
```

---

## 涉及的服务端口

<!-- TODO: 填写你的实际服务端口 -->

| 服务 | 端口 | 健康检查 |
|------|------|---------|
| Backend (FastAPI) | 8000 | `/health` |
| Frontend (React dev) | 3000 | — |
