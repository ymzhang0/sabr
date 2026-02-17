import json
from aiida import orm
from aiida.orm import Log, QueryBuilder, ProcessNode, WorkflowNode, CalcJobNode
from engines.aiida.tools.process.calculation import inspect_calculation
from engines.aiida.tools.process.workchain import inspect_workchain

def inspect_process(identifier: str) -> str:
    """
    统一入口：根据节点类型自动路由到 calculation 或 workchain 的详细分析。
    """
    try:
        node = orm.load_node(identifier)
        if not isinstance(node, ProcessNode):
            return f"Error: {identifier} is not a ProcessNode."

        # 1. 基础汇总
        report = {
            "summary": {
                "pk": node.pk,
                "type": node.node_type.split('.')[-2],
                "state": node.process_state.value,
                "exit_status": getattr(node, "exit_status", None),
            },
            "logs": get_process_log(node.pk)
        }

        # 2. 逻辑分发：Calculation 关注 IO/仓库，WorkChain 关注树
        if isinstance(node, CalcJobNode):
            report.update(inspect_calculation(node))
        elif isinstance(node, WorkflowNode):
            report.update(inspect_workchain(node))

        return json.dumps(report, indent=2, default=str)
    except Exception as e:
        return f"Error inspecting process: {str(e)}"

def get_process_log(pk: int) -> str:
    """抓取混合日志：WorkChain Report 或 CalcJob Stderr。"""
    node = orm.load_node(pk)
    log_lines = []
    
    qb = QueryBuilder().append(Log, filters={'objpk': pk}, project=['message', 'time'])
    if qb.count() > 0:
        log_lines.append("--- Reports ---")
        for msg, t in qb.order_by({Log: {'time': 'asc'}}).all():
            log_lines.append(f"[{t.strftime('%H:%M:%S')}] {msg}")

    if isinstance(node, CalcJobNode) and 'retrieved' in node.outputs:
        stderr = node.get_scheduler_stderr()
        if stderr: log_lines.append(f"--- Stderr ---\n{stderr[-2000:]}")

    return "\n".join(log_lines) or "No logs found."

def fetch_recent_processes(limit: int = 15):
    """获取最近任务供感知器使用。"""
    qb = QueryBuilder().append(
        ProcessNode, 
        project=["id", "attributes.process_label", "attributes.process_state", "ctime"],
        limit=limit
    ).order_by({ProcessNode: {"ctime": "desc"}})
    
    return [{"PK": pk, "Label": lb, "State": st, "Time": ct.strftime("%m-%d %H:%M")} 
            for pk, lb, st, ct in qb.all()]