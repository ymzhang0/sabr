from collections import defaultdict, deque
from typing import Dict, Optional, List
from aiida import orm

class ProcessTree:
    def __init__(self, aiida_node: orm.ProcessNode, name: str = "ROOT"):
        self.name = name
        self.node = aiida_node
        self.children: Dict[str, 'ProcessTree'] = {}

        # 仅 WorkflowNode (WorkChain) 拥有 subprocesses
        if isinstance(aiida_node, orm.WorkflowNode):
            subprocesses = sorted(aiida_node.called, key=lambda p: p.ctime)
            
            # 记录标签出现次数，用于唯一化
            counts = defaultdict(int)
            
            for sub in subprocesses:
                # 尝试获取 link_label
                try:
                    # 优先从属性获取调用标签
                    raw_label = sub.base.attributes.all.get("metadata_inputs", {}).get("metadata", {}).get("call_link_label")
                    if not raw_label:
                        raw_label = getattr(sub, 'process_label', 'process')
                except Exception:
                    raw_label = "node"

                # 唯一化处理：如果重复则加后缀 _0, _1...
                unique_label = f"{raw_label}_{counts[raw_label]}" if counts[raw_label] > 0 else raw_label
                counts[raw_label] += 1
                
                # 递归构建
                self.children[unique_label] = ProcessTree(sub, name=unique_label)

    def __getitem__(self, key: str):
        return self.children[key]

    def __getattr__(self, name: str):
        if name in self.children:
            return self.children[name]
        raise AttributeError(f"No child named '{name}'")

    def to_dict(self) -> dict:
        """统一的序列化方法，合并之前两个文件的重复逻辑"""
        return {
            "pk": self.node.pk,
            "uuid": self.node.uuid,
            "label": self.name,
            "process_label": getattr(self.node, "process_label", "N/A"),
            "type": self.node.node_type.split('.')[-2],
            "state": self.node.process_state.value if hasattr(self.node, 'process_state') else "N/A",
            "exit_status": getattr(self.node, "exit_status", None),
            "children": [child.to_dict() for child in self.children.values()]
        }

    def print_tree(self, prefix: str = "", is_last: bool = True):
        connector = "└── " if is_last else "├── "
        state = f" [{self.node.process_state.value}]" if hasattr(self.node, 'process_state') else ""
        print(f"{prefix}{connector}{self.name} (PK: {self.node.pk}){state}")
        
        new_prefix = prefix + ("    " if is_last else "│   ")
        child_list = list(self.children.values())
        for i, child in enumerate(child_list):
            child.print_tree(new_prefix, i == len(child_list) - 1)