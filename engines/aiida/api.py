from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from aiida.orm import load_node
from aiida.common import NotExistent

# Import your existing atomic tools logic
from engines.aiida.tools import get_database_summary, get_recent_processes

# Define the router for AiiDA specific operations
router = APIRouter(prefix="/aiida", tags=["AiiDA Operations"])

@router.get("/summary")
async def api_get_database_summary() -> Dict[str, Any]:
    """
    Retrieve quick statistics of the current AiiDA database.
    Used by the frontend welcome screen.
    """
    try:
        # Calls the existing logic in engines/aiida/tools/
        stats = get_database_summary()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch summary: {str(e)}")

@router.get("/processes")
async def api_get_recent_processes(limit: int = Query(5, ge=1, le=20)) -> List[Dict[str, Any]]:
    """
    Fetch recent process states for the UI Ticker.
    Allows the frontend to monitor calculation progress in real-time.
    """
    try:
        processes = get_recent_processes(limit=limit)
        return processes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch processes: {str(e)}")

@router.get("/nodes/{pk}")
async def api_get_node_details(pk: int) -> Dict[str, Any]:
    """
    Fetch comprehensive details for a specific AiiDA node.
    Used when a user clicks on a Node ID in the chat or insight view.
    """
    try:
        node = load_node(pk)
        
        # Serialize node details for frontend rendering
        details = {
            "pk": node.pk,
            "uuid": node.uuid,
            "label": node.label,
            "type": node.node_type,
            "ctime": str(node.ctime),
            "mtime": str(node.mtime),
            "attributes": node.base.attributes.all,
            "extras": node.base.extras.all
        }
        
        # Add input/output summary if it's a process node
        if hasattr(node, 'get_incoming'):
            details["incoming"] = [{"label": link.link_label, "pk": link.node.pk} 
                                  for link in node.base.links.get_incoming()]
        
        return details
        
    except NotExistent:
        raise HTTPException(status_code=404, detail=f"Node {pk} not found in database.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))