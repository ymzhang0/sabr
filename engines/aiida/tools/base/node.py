from aiida import orm

def serialize_node(node: orm.Node) -> dict:
    """
    将任何 AiiDA 节点转化为 AI 可读的字典格式。
    处理数据节点(Data)的 Payload 和 进程节点(Process)的状态。
    """
    info = {
        "pk": node.pk,
        "uuid": node.uuid,
        "type": node.node_type.split('.')[-2] if '.' in node.node_type else node.node_type,
        "label": node.label or "N/A",
        "ctime": node.ctime.strftime("%Y-%m-%d %H:%M:%S")
    }

    # 处理数据内容 (原 calculation.py 逻辑)
    if isinstance(node, orm.Dict):
        info["payload"] = node.get_dict()
    elif isinstance(node, orm.StructureData):
        info["payload"] = {"formula": node.get_formula()}
    elif isinstance(node, orm.ProcessNode):
        info["state"] = node.process_state.value
        info["exit_status"] = getattr(node, "exit_status", None)

    return info


def _extract_node_info(node, link_label):
    """Helper to extract info and payload for a Data node."""
    payload = None
    try:
        if isinstance(node, orm.Dict):
            payload = node.get_dict()
        elif isinstance(node, orm.FolderData):
            payload = node.list_object_names()
        elif isinstance(node, orm.StructureData):
            payload = node.get_formula()
        elif isinstance(node, orm.BandsData):
            payload = "BandsStructure"
        elif isinstance(node, orm.Code):
            payload = node.full_label
        elif isinstance(node, (orm.Int, orm.Float, orm.Str, orm.Bool)):
            payload = node.value
        elif isinstance(node, orm.KpointsData):
            try:
                mesh, offset = node.get_kpoints_mesh()
                payload = {
                    "mode": "mesh",
                    "mesh": mesh,
                    "offset": offset
                }
            except Exception:
                # If no mesh, it's a list
                try:
                    kpoints = node.get_kpoints()
                    # Convert numpy array to list for JSON serialization
                    payload = {
                        "mode": "list",
                        "num_points": len(kpoints),
                        "points": kpoints.tolist()
                    }
                except Exception:
                    payload = "Kpoints Data (Unknown format)"
    except Exception:
        payload = "Error loading content"

    return {
        "pk": node.pk,
        "uuid": node.uuid,
        "label": node.label if node.label else link_label,
        "type": node.node_type.split('.')[-2] if '.' in node.node_type else node.node_type,
        "full_type": node.node_type,
        "payload": payload
    }