import json
from aiida import orm
from aiida.orm import Group, QueryBuilder

def inspect_group(group_name: str, limit: int = 20):
    """
    Analyze a specific Group. Returns detailed properties (attributes & extras) for all nodes in the group.
    Use this to "check a group", "inspect a batch", or "see results" of a calculation set.
    
    Args:
        group_name (str): The exact name/label of the group.
        limit (int): Max number of nodes to return (default 20).
    """

    report = [f"=== Analysis for Group: {group_name} ==="]
    
    # Check if group exists at least
    # Check if group exists
    if not Group.collection.find(filters={"label": group_name}):
        # Try finding similar groups
        similar = Group.collection.find(filters={"label": {"like": f"%{group_name}%"}})
        if similar:
            names = [g.label for g in similar]
            return f"Error: Group '{group_name}' not found. Did you mean one of these?\n" + "\n".join([f"- {n}" for n in names])
        return f"Error: Group '{group_name}' not found."
    
    group = Group.collection.get(label=group_name)
    nodes = group.nodes

    if not len(nodes):
        return f"Group '{group_name}' contains no Nodes."

    report.append(f"Found {len(nodes)} (showing top {limit}):")

    for node in nodes[:limit]:
        attrs = node.base.attributes.all
        # Extras are also useful often
        extras = node.base.extras.all
        
        # Serialize to string
        try:
            attrs_str = json.dumps(attrs, default=str)
            extras_str = json.dumps(extras, default=str)
        except Exception:
            attrs_str = str(attrs)
            extras_str = str(extras)

        report.append(f"PK={node.pk} | Attributes={attrs_str} | Extras={extras_str}")

    return "\n".join(report)

def fetch_group_nodes(group_name: str, limit: int = 100):
    """
    Fetch raw list of nodes in a group for UI.
    Returns: List[Dict].
    """
    if not Group.collection.find(filters={"label": group_name}):
        return []

    group = Group.collection.get(label=group_name)
    nodes = group.nodes
    
    # Sort by ctime desc
    # nodes is a list, sort it? or just take top
    # group.nodes returns list.
    
    return [
        {
            "pk": n.pk,
            "uuid": n.uuid,
            "label": n.label if n.label else n.node_type.split('.')[-2],
            "type": n.node_type,
            "process_label": getattr(n, "process_label", "N/A"),
            "exit_status": getattr(n, "exit_status", None),
            "ctime": n.ctime,
            'mtime': n.mtime,
            "state": getattr(n, "process_state", "N/A")
        }
        for n in nodes[:limit]
    ]

def _build_group_tree(groups_data: list):
    """
    Parse flat group list into a nested tree based on slash-separated labels.
    Structure: {'part': {'__data__': group_dict_or_None, '__children__': {...}}}
    """
    tree = {}
    for g in groups_data:
        parts = g['label'].split('/')
        current = tree
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {"__data__": None, "__children__": {}}
            
            # If this is the execution path for this group, assign data
            if i == len(parts) - 1:
                current[part]["__data__"] = g
            
            current = current[part]["__children__"]
    return tree

def fetch_group_processes(group_label: str, limit: int = 20, exclude_import: bool = True):
    """
    Fetch WorkChainNodes from a specific group.
    """
    qb = QueryBuilder()
    qb.append(Group, filters={"label": group_label}, tag="group")
    qb.append(orm.WorkChainNode, with_group="group", 
             project=["id", "label", "process_type", "ctime", "mtime", "attributes.process_label", "attributes.process_state", "attributes.exit_status"])
    qb.order_by({orm.WorkChainNode: {"ctime": "desc"}})
    if limit:
        qb.limit(limit)

    return qb.all()
    


def create_group(group_label: str):
    """
    Create a new Group with the given label.
    Returns: Success message or Error string.
    """
    try:
        from aiida.orm import Group
        if Group.collection.find(filters={"label": group_label}):
            return f"Error: Group '{group_label}' already exists."
        
        group = Group(label=group_label)
        group.store()
        return f"Success: Created group '{group_label}' (PK={group.pk})"
    except Exception as e:
        return f"Error creating group: {e}"
