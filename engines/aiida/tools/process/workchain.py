from aiida import orm
from engines.aiida.tools.process.process_tree import ProcessTree

def inspect_workchain(node: orm.WorkChainNode) -> dict:
    """Analyze the provenance call tree of a workchain."""
    tree = ProcessTree(node)
    return {
        "provenance_tree": tree.to_dict(),
        "report": "Call get_process_log for reports"
    }
