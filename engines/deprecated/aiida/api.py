# engines/aiida/api.py
from fastapi import APIRouter, HTTPException
from .tools import get_database_summary, get_recent_processes
from aiida.orm import load_node

router = APIRouter(prefix="/aiida", tags=["AiiDA"])

@router.get("/summary")
async def api_get_summary():
    return get_database_summary()

@router.get("/processes")
async def api_get_processes(limit: int = 5):
    return get_recent_processes(limit=limit)

@router.get("/nodes/{pk}")
async def api_get_node(pk: int):
    try:
        node = load_node(pk)
        # 返回精简后的节点信息，用于 UI 渲染
        return {
            "pk": node.pk,
            "label": node.label,
            "type": node.node_type,
            "attributes": node.base.attributes.all,
            "ctime": str(node.ctime)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))