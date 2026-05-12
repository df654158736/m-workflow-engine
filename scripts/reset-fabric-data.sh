#!/usr/bin/env bash
# reset-fabric-data.sh — 清理数据编织/Pipeline/关系探查全部测试数据，用于重新跑 E2E 流程
#
# 用法:
#   ./scripts/reset-fabric-data.sh                     # 清当前项目（从 config.local.yaml 读 project_id）
#   ./scripts/reset-fabric-data.sh <project_id>        # 清指定项目
#   ./scripts/reset-fabric-data.sh --all               # 清所有项目（慎用）
#
# 清理范围（三个数据库）:
#   web_app       — fabric_task / compare_result / field_mapping / pipeline 管理 / 绑定 / 关系探查 / 活动 / 对齐规则
#   data_plane    — Plane F pipelines / versions / executions / execution_log
#   control_plane — ontology_schema（按 namespace=project_id）
#
# 环境变量:
#   DB_HOST      默认 192.168.2.60
#   DB_USER      默认 dagster
#   DB_PASSWORD  默认 dagster

set -euo pipefail

DB_HOST="${DB_HOST:-192.168.2.60}"
DB_USER="${DB_USER:-dagster}"
DB_PASSWORD="${DB_PASSWORD:-dagster}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 解析参数
if [[ "${1:-}" == "--all" ]]; then
    MODE="all"
    PROJECT_ID=""
elif [[ -n "${1:-}" ]]; then
    MODE="project"
    PROJECT_ID="$1"
else
    MODE="project"
    CONFIG="$PROJECT_ROOT/config.local.yaml"
    if [[ ! -f "$CONFIG" ]]; then
        echo "❌ config.local.yaml 未找到，请指定 project_id 或使用 --all"
        exit 1
    fi
    PROJECT_ID=$(grep 'project_id:' "$CONFIG" | awk '{print $2}')
    if [[ -z "$PROJECT_ID" ]]; then
        echo "❌ 无法从 config.local.yaml 读取 project_id"
        exit 1
    fi
fi

psql_run() {
    local db="$1"; shift
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$db" "$@" 2>&1
}

psql_cmd() {
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$1" -t -c "$2" 2>/dev/null
}

echo "🧹 数据编织全量清理工具"
echo "   DB: $DB_HOST  模式: $MODE"
[[ "$MODE" == "project" ]] && echo "   项目: $PROJECT_ID"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. data_plane — Plane F pipelines
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "📦 [1/3] 清理 data_plane (Plane F)..."
if [[ "$MODE" == "all" ]]; then
    psql_run data_plane -c "TRUNCATE pipeline_execution_log, pipeline_executions, pipeline_versions, pipelines CASCADE;" | grep -E 'TRUNCATE|ERROR'
else
    psql_run data_plane <<SQL | grep -E 'DELETE|ERROR|BEGIN|COMMIT'
BEGIN;
DELETE FROM pipeline_execution_log WHERE pipeline_id IN (SELECT pipeline_id FROM pipelines WHERE project_id = '${PROJECT_ID}');
DELETE FROM pipeline_executions    WHERE pipeline_id IN (SELECT pipeline_id FROM pipelines WHERE project_id = '${PROJECT_ID}');
DELETE FROM pipeline_versions      WHERE pipeline_id IN (SELECT pipeline_id FROM pipelines WHERE project_id = '${PROJECT_ID}');
DELETE FROM pipelines              WHERE project_id = '${PROJECT_ID}';
COMMIT;
SQL
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. web_app — fabric 全家桶
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "📦 [2/3] 清理 web_app..."
if [[ "$MODE" == "all" ]]; then
    psql_run web_app <<SQL | grep -E 'TRUNCATE|ERROR|BEGIN|COMMIT'
BEGIN;
TRUNCATE fabric_pipeline_audit_log, fabric_pipeline_run, fabric_pipeline_watermark,
         fabric_pipeline_schedule, fabric_pipeline_settings, fabric_pipeline_trigger,
         fabric_pipeline_retry_policy CASCADE;
TRUNCATE ontology_type_pipeline_binding CASCADE;
TRUNCATE fabric_link_type_approval, fabric_discovered_relation, fabric_relation_scan CASCADE;
TRUNCATE fabric_activity CASCADE;
TRUNCATE fabric_alignment_rule CASCADE;
TRUNCATE fabric_field_mapping CASCADE;
TRUNCATE fabric_compare_result CASCADE;
TRUNCATE fabric_task CASCADE;
COMMIT;
SQL
else
    psql_run web_app <<SQL | grep -E 'DELETE|ERROR|BEGIN|COMMIT'
BEGIN;

-- Pipeline 管理（通过 binding 找项目相关的 pipeline_id）
DELETE FROM fabric_pipeline_audit_log    WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_pipeline_run          WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_pipeline_watermark    WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_pipeline_schedule     WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_pipeline_settings     WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_pipeline_retry_policy WHERE pipeline_id IN (SELECT pipeline_id FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}');

-- 也清 task.plane_f_pipeline_id 关联的旧数据
DELETE FROM fabric_pipeline_audit_log    WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);
DELETE FROM fabric_pipeline_run          WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);
DELETE FROM fabric_pipeline_watermark    WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);
DELETE FROM fabric_pipeline_schedule     WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);
DELETE FROM fabric_pipeline_settings     WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);
DELETE FROM fabric_pipeline_retry_policy WHERE pipeline_id IN (SELECT plane_f_pipeline_id FROM fabric_task WHERE project_id = '${PROJECT_ID}' AND plane_f_pipeline_id IS NOT NULL);

DELETE FROM fabric_pipeline_trigger WHERE project_id = '${PROJECT_ID}';

-- 绑定
DELETE FROM ontology_type_pipeline_binding WHERE project_id = '${PROJECT_ID}';

-- 关系探查
DELETE FROM fabric_link_type_approval  WHERE project_id = '${PROJECT_ID}';
DELETE FROM fabric_discovered_relation WHERE project_id = '${PROJECT_ID}';
DELETE FROM fabric_relation_scan       WHERE project_id = '${PROJECT_ID}';

-- 活动日志 + 对齐规则
DELETE FROM fabric_activity       WHERE project_id = '${PROJECT_ID}';
DELETE FROM fabric_alignment_rule WHERE project_id = '${PROJECT_ID}';

-- 核心数据（先子后父）
DELETE FROM fabric_field_mapping  WHERE task_id IN (SELECT id FROM fabric_task WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_compare_result WHERE task_id IN (SELECT id FROM fabric_task WHERE project_id = '${PROJECT_ID}');
DELETE FROM fabric_task           WHERE project_id = '${PROJECT_ID}';

-- 兜底：清理所有无主的 pipeline 记录（pipeline_id 在 data_plane 已不存在的孤儿）
DELETE FROM fabric_pipeline_audit_log;
DELETE FROM fabric_pipeline_run;
DELETE FROM fabric_pipeline_watermark;
DELETE FROM fabric_pipeline_retry_policy;

COMMIT;
SQL
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. control_plane — ontology_schema
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "📦 [3/3] 清理 control_plane (ontology_schema)..."
if [[ "$MODE" == "all" ]]; then
    psql_cmd control_plane "DELETE FROM ontology_schema;"
else
    psql_cmd control_plane "DELETE FROM ontology_schema WHERE namespace = '${PROJECT_ID}';"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 验证
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "✅ 清理完成！验证："
psql_cmd web_app "
SELECT 'fabric_task' as tbl, count(*) FROM fabric_task
UNION ALL SELECT 'compare_result', count(*) FROM fabric_compare_result
UNION ALL SELECT 'field_mapping', count(*) FROM fabric_field_mapping
UNION ALL SELECT 'pipeline_binding', count(*) FROM ontology_type_pipeline_binding
UNION ALL SELECT 'pipeline_run', count(*) FROM fabric_pipeline_run
UNION ALL SELECT 'pipeline_audit', count(*) FROM fabric_pipeline_audit_log
UNION ALL SELECT 'link_approval', count(*) FROM fabric_link_type_approval
UNION ALL SELECT 'relation_scan', count(*) FROM fabric_relation_scan
ORDER BY 1;
"
echo "data_plane.pipelines:$(psql_cmd data_plane "SELECT count(*) FROM pipelines WHERE deleted = false;" 2>/dev/null || echo ' 0')"
echo "control_plane.schema:$(psql_cmd control_plane "SELECT count(*) FROM ontology_schema${PROJECT_ID:+ WHERE namespace = '${PROJECT_ID}'};" 2>/dev/null || echo ' 0')"
