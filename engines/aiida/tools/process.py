"""
Unified Process Tool for AiiDA.
Handles WorkChains, Calculations, and Provenance Trees.
"""
from collections import defaultdict
from typing import Union, Dict, Any
import json
from aiida import orm
from aiida.orm import Log, QueryBuilder, ProcessNode, WorkflowNode, CalcJobNode
from engines.aiida.tools.process_tree import ProcessTree

# --- AI 核心接口 (The Hub) ---

def inspect_process(identifier: str) -> str: # 🚩 将 Union[str, int] 改为 str
    """
    Inspect an AiiDA process (WorkChain or Calculation).
    Args:
        identifier (str): The PK (as string) or UUID of the process.
    """
    try:
        # load_node 能够自动处理字符串格式的数字 PK
        node = orm.load_node(identifier)

        if not isinstance(node, ProcessNode):
            return f"Error: Node {identifier} is a {type(node)}, not a ProcessNode."

        # 1. 构建调用树
        tree = ProcessTree(node)
        
        # 2. 获取针对性日志
        logs = get_process_log(node.pk)
        
        # 3. 组装综合报告
        report = {
            "summary": {
                "pk": node.pk,
                "uuid": node.uuid,
                "type": node.node_type.split('.')[-2],
                "label": node.label,
                "state": node.process_state.value if hasattr(node, 'process_state') else "N/A",
                "exit_status": getattr(node, "exit_status", None),
                "exit_message": getattr(node, "exit_message", None),
            },
            "provenance_tree": tree.to_dict(),
            "logs": logs,
            "attributes": node.base.attributes.all,
        }
        
        # 针对 CalcJob 的特化信息
        if isinstance(node, CalcJobNode):
            report["summary"]["is_calcjob"] = True
            report["files"] = node.list_objects()

        return json.dumps(report, indent=2, default=str)
    except Exception as e:
        return f"Error inspecting process '{identifier}': {str(e)}"

def get_process_log(pk: int) -> str:
    """
    获取进程的混合日志：
    - 如果是 WorkChain：抓取内部 report 消息
    - 如果是 CalcJob：抓取调度器 stderr
    """
    try:
        node = orm.load_node(pk)
        log_lines = []

        # 1. 尝试抓取 WorkChain 的 Report (来自 Log 表)
        qb = QueryBuilder().append(Log, filters={'objpk': pk}, project=['message', 'time'])
        if qb.count() > 0:
            log_lines.append("--- WorkChain Reports ---")
            for msg, time in qb.order_by({Log: {'time': 'asc'}}).all():
                log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

        # 2. 尝试抓取 CalcJob 的调度器错误
        if isinstance(node, CalcJobNode) and 'retrieved' in node.outputs:
            stderr = node.get_scheduler_stderr()
            if stderr:
                log_lines.append("--- Scheduler Stderr ---")
                log_lines.append(stderr[-2000:]) # 仅截取最后2000字，防止 Token 爆炸

        return "\n".join(log_lines) if log_lines else "No detailed logs found."
    except Exception as e:
        return f"Could not retrieve logs: {e}"

def fetch_recent_processes(limit: int = 15):
    """获取最近任务列表，常用于感知器提供全局上下文。"""
    qb = QueryBuilder().append(
        ProcessNode, 
        project=["id", "attributes.process_label", "attributes.process_state", "ctime"],
        limit=limit
    ).order_by({ProcessNode: {"ctime": "desc"}})
    
    results = []
    for pk, label, state, ctime in qb.all():
        results.append({
            "PK": pk, "Label": label, "State": state, 
            "Created": ctime.strftime("%m-%d %H:%M")
        })
    return results