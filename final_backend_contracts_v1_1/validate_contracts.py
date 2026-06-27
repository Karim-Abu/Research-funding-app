from __future__ import annotations

import collections
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent

FILES = {
    "agents": "agents_v1_1.yaml",
    "tools": "tools_v1_1.yaml",
    "controls": "controls.yaml",
    "requirements": "requirements.yaml",
    "schemas": "schema_catalog.yaml",
    "rules": "innosuisse_innovation_project_v1_1.yaml",
    "run_state": "run_state_v1_1.yaml",
    "policy": "data_policy_v1_1.yaml",
    "openapi": "openapi-v1_1.yaml",
}


def load_yaml(name: str) -> Any:
    with (ROOT / FILES[name]).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def pattern_matches(pattern: str, value: str) -> bool:
    return value.startswith(pattern[:-1]) if pattern.endswith(".*") else pattern == value


def collect_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                refs.append(item)
            else:
                refs.extend(collect_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(collect_refs(item))
    return refs


def main() -> int:
    docs = {key: load_yaml(key) for key in FILES}
    agents = docs["agents"]
    tools = docs["tools"]
    controls = docs["controls"]
    requirements = docs["requirements"]
    schemas = docs["schemas"]
    rules = docs["rules"]
    run_state = docs["run_state"]
    openapi = docs["openapi"]

    errors: list[str] = []
    warnings: list[str] = []

    profile_ids = {p["profile_id"] for p in agents["profiles"]}
    group_ids = {g["group_id"] for g in agents["execution_groups"]}
    tool_ids = {t["tool_id"] for t in tools["tools"]}
    control_ids = {c["control_id"] for c in controls["controls"]}
    schema_ids = {s["schema_id"] for s in schemas["schemas"]}
    requirement_ids = {r["requirement_id"] for r in requirements["requirements"]}
    field_by_id = {f["field_id"]: f for f in rules["portal_fields"]}
    model_keys = set(agents["model_catalog"])

    for profile in agents["profiles"]:
        profile_id = profile["profile_id"]
        if profile.get("execution_group") not in group_ids:
            errors.append(f"{profile_id}: unknown execution_group {profile.get('execution_group')}")
        for tool_id in profile.get("allowed_tools", []):
            if tool_id not in tool_ids:
                errors.append(f"{profile_id}: unknown tool {tool_id}")
        for control_id in profile.get("controls", []):
            if control_id not in control_ids:
                errors.append(f"{profile_id}: unknown control {control_id}")
        for schema_id in (profile.get("input_schema"), profile.get("output_schema")):
            if schema_id not in schema_ids:
                errors.append(f"{profile_id}: unknown schema {schema_id}")
        for model_key in ("primary", "fallback", "optional_candidate"):
            value = profile.get("model", {}).get(model_key)
            if value and value not in model_keys:
                errors.append(f"{profile_id}: unknown model key {value}")
        for field_id in profile.get("allowed_field_selectors", {}).get("field_ids", []):
            if field_id not in field_by_id:
                errors.append(f"{profile_id}: unknown field {field_id}")
            elif profile["agent_id"] == "A2" and not field_by_id[field_id].get("agent_writable"):
                errors.append(f"{profile_id}: A2 field is not agent_writable: {field_id}")

    tool_by_id = {t["tool_id"]: t for t in tools["tools"]}
    for tool in tools["tools"]:
        tool_id = tool["tool_id"]
        for control_id in tool.get("required_controls", []):
            if control_id not in control_ids:
                errors.append(f"{tool_id}: unknown control {control_id}")
        for schema_id in (tool.get("input_schema"), tool.get("output_schema")):
            if schema_id not in schema_ids:
                errors.append(f"{tool_id}: unknown schema {schema_id}")
        for sensitivity in tool.get("allowed_sensitivity", []):
            if sensitivity not in {"public", "internal", "confidential"}:
                errors.append(f"{tool_id}: non-canonical sensitivity {sensitivity}")
        if tool.get("network_access") != "none" and any(caller != "orchestrator" for caller in tool.get("callers", [])):
            errors.append(f"{tool_id}: network tool has non-orchestrator caller")

    for profile in agents["profiles"]:
        for tool_id in profile.get("allowed_tools", []):
            tool = tool_by_id[tool_id]
            if not any(pattern_matches(pat, profile["profile_id"]) for pat in tool.get("allowed_agent_profiles", [])):
                errors.append(f"permission mismatch: {profile['profile_id']} -> {tool_id}")

    for item in rules["official_core_rules"] + rules["portal_quality_gates"]:
        if item.get("requirement_id") not in requirement_ids:
            errors.append(f"{item['rule_id']}: missing requirement reference")

    for field in rules["portal_fields"]:
        for key in ("field_kind", "support_mode", "agent_writable", "structured_data_path"):
            if key not in field:
                errors.append(f"{field['field_id']}: missing {key}")

    node_ids = {node["node_id"] for node in run_state["nodes"]}
    if set(run_state["stages"]) != node_ids:
        errors.append("run stages and node IDs differ")
    for node in run_state["nodes"]:
        for tool_id in node.get("tools", []):
            if tool_id not in tool_ids:
                errors.append(f"run node {node['node_id']}: unknown tool {tool_id}")
        for profile_id in node.get("profiles", []):
            if profile_id not in profile_ids:
                errors.append(f"run node {node['node_id']}: unknown profile {profile_id}")

    component_schemas = openapi["components"]["schemas"]
    component_parameters = openapi["components"].get("parameters", {})
    for ref in collect_refs(openapi):
        if ref.startswith("#/components/schemas/") and ref.rsplit("/", 1)[-1] not in component_schemas:
            errors.append(f"OpenAPI unresolved schema ref: {ref}")
        if ref.startswith("#/components/parameters/") and ref.rsplit("/", 1)[-1] not in component_parameters:
            errors.append(f"OpenAPI unresolved parameter ref: {ref}")

    operation_ids: list[str] = []
    for path, item in openapi["paths"].items():
        path_vars = set(re.findall(r"{([^}]+)}", path))
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            operation_ids.append(operation["operationId"])
            declared = {p.get("name") for p in operation.get("parameters", []) if p.get("in") == "path"}
            if path_vars != declared:
                errors.append(f"{method.upper()} {path}: path parameters {path_vars} != declared {declared}")

    duplicates = [key for key, count in collections.Counter(operation_ids).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate operationId values: {duplicates}")

    machine_files = [
        "agents_v1_1.yaml",
        "tools_v1_1.yaml",
        "data_policy_v1_1.yaml",
        "run_state_v1_1.yaml",
        "openapi-v1_1.yaml",
    ]
    for filename in machine_files:
        text = (ROOT / filename).read_text(encoding="utf-8")
        if "internal_with_public_confirmed_query" in text:
            errors.append(f"{filename}: contains non-canonical sensitivity")

    if "/api/v1/runs/{run_id}/rechecks" not in openapi["paths"]:
        errors.append("OpenAPI: targeted recheck endpoint missing")
    if "recheck_required" not in component_schemas["ReviewPackage"]["properties"]:
        errors.append("OpenAPI: ReviewPackage.recheck_required missing")

    print(f"Validated {len(FILES)} YAML/OpenAPI documents")
    print(f"Profiles: {len(profile_ids)} | Tools: {len(tool_ids)} | Controls: {len(control_ids)} | Schemas: {len(schema_ids)}")
    print(f"Requirements: {len(requirement_ids)} | Portal fields: {len(field_by_id)} | API operations: {len(operation_ids)}")
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("PASS: no cross-registry errors detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
