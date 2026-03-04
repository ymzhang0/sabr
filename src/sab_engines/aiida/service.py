"""Canonical AiiDA service facade.

Aggregates worker-backed hub state, bridge client accessors, and AI-driven infrastructure parsing.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from google import genai
from loguru import logger

from src.sab_core.config import settings
from src.sab_core.logging_utils import log_event

from .client import (
    AiiDABridgeService,
    BridgeAPIError,
    BridgeConnectionState,
    BridgeOfflineError,
    BridgeResourceCounts,
    BridgeSnapshot,
    bridge_service,
)
from .frontend_bridge import (
    add_nodes_to_group,
    create_group,
    delete_group,
    export_group,
    get_context_nodes,
    get_recent_nodes,
    get_recent_processes,
    list_groups,
    list_group_labels,
    rename_group,
    soft_delete_node,
)
from .hub import AiiDAHub, hub
from .infrastructure_manager import infrastructure_manager


async def parse_infrastructure_via_ai(text: str, ssh_host_details: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Use Gemini to parse raw text into AiiDA Computer/Code configuration.
    """
    api_key = settings.GEMINI_API_KEY
    if api_key == "your-key-here":
        raise HTTPException(status_code=400, detail="Gemini API key not configured")

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": settings.GEMINI_API_VERSION},
    )

    # Fetch available plugins to make the prompt more dynamic if possible
    # For now, we use a generic placeholder instead of hardcoded quantumespresso.pw
    prompt = f"""
    You are an AiiDA infrastructure expert. Parse the following text into a structured JSON for configuring an AiiDA Computer or Code.

    Input Text:
    {text}

    Output format:
    {{
      "type": "computer" | "code" | "both",
      "computer": {{
        "label": "string",
        "hostname": "string",
        "username": "string",
        "description": "string",
        "transport_type": "core.ssh",
        "scheduler_type": "core.direct" | "core.slurm" | "core.pbspro" | "core.lsf",
        "work_dir": "string",
        "mpiprocs_per_machine": number,
        "mpirun_command": "string"
      }},
      "code": {{
        "label": "string",
        "description": "string",
        "default_calc_job_plugin": "string (the AiiDA plugin name, e.g. quantumespresso.pw or vasp.vasp)",
        "remote_abspath": "string"
      }}
    }}

    Return ONLY the raw JSON. No markdown blocks, no explanations. If unknown, omit the key.
    """

    try:
        response = client.models.generate_content(
            model=settings.DEFAULT_MODEL,
            contents=prompt,
        )
        raw_text = response.text.strip()
        # Basic cleanup if model includes markdown code blocks
        if raw_text.startswith("```"):
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            else:
                raw_text = raw_text.split("```")[1].strip()
        
        parsed = json.loads(raw_text)
        
        # Handle explicitly passed SSH Host Details
        if ssh_host_details:
            if not parsed.get("computer"):
                parsed["computer"] = {}
                parsed["type"] = "both" if parsed.get("code") else "computer"
            
            parsed["computer"]["label"] = ssh_host_details.get("alias") or parsed["computer"].get("label")
            
            if ssh_host_details.get("hostname"):
                parsed["computer"]["hostname"] = ssh_host_details.get("hostname")
            if ssh_host_details.get("username"):
                parsed["computer"]["username"] = ssh_host_details.get("username")
            if ssh_host_details.get("proxy_jump"):
                parsed["computer"]["proxy_jump"] = ssh_host_details.get("proxy_jump")
            if ssh_host_details.get("proxy_command"):
                parsed["computer"]["proxy_command"] = ssh_host_details.get("proxy_command")
            if ssh_host_details.get("identity_file"):
                parsed["computer"]["key_filename"] = ssh_host_details.get("identity_file")

        # Merge with presets if it's a computer
        if parsed.get("computer"):
            merge_result = infrastructure_manager.merge_preset(parsed["computer"])
            parsed["computer"] = merge_result.get("config", parsed["computer"])
            parsed["preset_matched"] = merge_result.get("matched", False)
            if parsed["preset_matched"]:
                parsed["preset_domain"] = merge_result.get("domain_pattern", "")
                
        return parsed
    except Exception as error:
        logger.exception(log_event("aiida.service.parse_infrastructure.failed", error=str(error)))
        raise HTTPException(status_code=500, detail=f"AI Parsing failed: {str(error)}") from error


__all__ = [
    "AiiDABridgeService",
    "BridgeConnectionState",
    "BridgeResourceCounts",
    "BridgeSnapshot",
    "bridge_service",
    "AiiDAHub",
    "hub",
    "add_nodes_to_group",
    "create_group",
    "delete_group",
    "export_group",
    "get_context_nodes",
    "get_recent_nodes",
    "get_recent_processes",
    "list_groups",
    "list_group_labels",
    "rename_group",
    "soft_delete_node",
    "parse_infrastructure_via_ai",
]
