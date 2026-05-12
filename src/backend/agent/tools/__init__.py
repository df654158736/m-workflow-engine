"""Agent Tools — 导入即注册。"""

from backend.agent.tools.validate_dag import validate_dag
from backend.agent.tools.list_tools import list_available_tools
from backend.agent.tools.check_compatibility import check_output_compatibility
from backend.agent.tools.list_functions import list_available_functions
from backend.agent.tools.query_schema import query_table_schema
from backend.agent.tools.estimate_cost import estimate_cost
from backend.agent.tools.search_workflows import search_similar_workflows
from backend.agent.tools.memory_tools import save_to_memory, recall_memory
from backend.agent.tools.datasource_tools import list_datasources, scan_table_columns
from backend.agent.tools.ontology_tools import list_object_types, create_object_type, ai_infer_properties
from backend.agent.tools.fabric_tools import create_fabric_task, trigger_ai_analysis, get_field_mappings, generate_pipeline, submit_pipeline
from backend.agent.tools.interaction_tools import ask_user_choice
from backend.agent.tools.skill_tools import get_skill_detail, set_skill_loader
