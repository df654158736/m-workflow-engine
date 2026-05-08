# PRD Template: {Feature Name}

> **Version**: 1.0
> **Author**: {Author Name}
> **Date**: YYYY-MM-DD
> **Status**: Draft | Review | Approved | Deprecated

---

## 1. Overview

### 1.1 Problem Statement

{清晰描述要解决的问题，包括：}
- 当前痛点是什么？
- 影响了哪些用户/场景？
- 为什么现在需要解决？

### 1.2 Proposed Solution

{简要描述提出的解决方案，1-2 段即可}

### 1.3 Goals & Non-Goals

#### Goals
- {Goal 1}
- {Goal 2}

#### Non-Goals
- {明确不在本次范围内的内容}
- {避免范围蔓延}

---

## 2. User Stories

### Story 1: {角色} 需要 {功能}

**As a** {用户角色},
**I want to** {期望的功能},
**So that** {获得的价值}。

#### Acceptance Criteria

1. WHEN {条件} THEN THE System SHALL {行为}
2. WHEN {条件} THEN THE System SHALL {行为}
3. IF {异常条件} THEN THE System SHALL {异常处理}

### Story 2: ...

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | {功能需求描述} | P0/P1/P2 | {备注} |
| FR-002 | {功能需求描述} | P0/P1/P2 | {备注} |

### 3.2 Non-Functional Requirements

| ID | Requirement | Metric | Target |
|----|-------------|--------|--------|
| NFR-001 | Performance | Response time | < 100ms |
| NFR-002 | Availability | Uptime | 99.9% |
| NFR-003 | Scalability | Concurrent users | 10,000 |

---

## 4. Data & API

### 4.1 Data Model Changes

{描述需要新增/修改的数据模型}

```json
{
  "new_field": "description"
}
```

### 4.2 API Changes

{描述新增/修改的 API}

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/xxx | 创建 xxx |
| GET | /api/v1/xxx/{id} | 获取 xxx |

---

## 5. UX Design

### 5.1 User Flow

```
Step 1 → Step 2 → Step 3 → Done
```

### 5.2 Wireframes

{链接到设计稿或嵌入图片}

---

## 6. Dependencies

### 6.1 Internal Dependencies

| Dependency | Team/Plane | Status | Notes |
|------------|------------|--------|-------|
| {Module A} | {Team/Module} | Required | {说明} |
| {Module B} | {Team/Module} | Required | {说明} |

### 6.2 External Dependencies

| Dependency | Provider | Status |
|------------|----------|--------|
| {外部服务} | {提供方} | {状态} |

---

## 7. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {风险描述} | High/Medium/Low | High/Medium/Low | {缓解措施} |

---

## 8. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| {指标名} | {当前值} | {目标值} | {如何测量} |

---

## 9. Timeline

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Design Review | YYYY-MM-DD | ⬜ |
| Development Start | YYYY-MM-DD | ⬜ |
| Testing Complete | YYYY-MM-DD | ⬜ |
| Release | YYYY-MM-DD | ⬜ |

---

## 10. Open Questions

- [ ] {待确认的问题 1}
- [ ] {待确认的问题 2}

---

## Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | {Author} | Initial version |

---

## Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| {术语} | {定义} |

### B. References

- {相关文档链接}
- {参考资料}
