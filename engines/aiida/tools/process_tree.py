from collections import defaultdict, deque
from typing import Dict, Optional, List
from aiida import orm

class ProcessTree:
    """Recursively builds and serializes the AiiDA process provenance tree."""
    def __init__(self, node: ProcessNode, name: str = "ROOT"):
        self.name = name
        self.node = node
        self.children: Dict[str, 'ProcessTree'] = {}

        # 仅 WorkflowNode (如 WorkChain) 具有 .called 属性
        if isinstance(node, WorkflowNode):
            subprocesses = sorted(node.called, key=lambda p: p.ctime)
            counts = defaultdict(int)
            
            for sub in subprocesses:
                # 获取 link_label
                raw_label = sub.base.attributes.all.get("metadata_inputs", {}).get("metadata", {}).get("call_link_label")
                if not raw_label:
                    raw_label = getattr(sub, 'process_label', 'process')
                
                # 唯一化标签 (pw_relax -> pw_relax_1)
                unique_label = f"{raw_label}_{counts[raw_label]}" if counts[raw_label] > 0 else raw_label
                counts[raw_label] += 1
                
                self.children[unique_label] = ProcessTree(sub, name=unique_label)

    def to_dict(self) -> dict:
        """递归转化为字典，供 AI 或 UI 使用"""
        res = {
            "pk": self.node.pk,
            "name": self.name,
            "process_label": getattr(self.node, "process_label", "N/A"),
            "state": self.node.process_state.value if hasattr(self.node, 'process_state') else "N/A",
            "exit_status": getattr(self.node, "exit_status", None),
            "children": [c.to_dict() for c in self.children.values()]
        }
        return res

    def print_tree(self, prefix: str = "", is_last: bool = True):
        connector = "└── " if is_last else "├── "
        state = f" [{self.node.process_state.value}]" if hasattr(self.node, 'process_state') else ""
        print(f"{prefix}{connector}{self.name} (PK: {self.node.pk}){state}")
        
        new_prefix = prefix + ("    " if is_last else "│   ")
        child_list = list(self.children.values())
        for i, child in enumerate(child_list):
            child.print_tree(new_prefix, i == len(child_list) - 1)