from aiida import orm
from engines.aiida.tools.process.process_tree import ProcessTree

def inspect_workchain(node: orm.WorkChainNode) -> dict:
    """分析工作流的调用树。"""
    tree = ProcessTree(node)
    return {
        "provenance_tree": tree.to_dict(),
        "report": "Call get_process_log for reports"
    }