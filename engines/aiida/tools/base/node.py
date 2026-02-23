from aiida import orm

# engines/aiida/tools/base/node.py
from aiida.orm import load_node

def get_node_summary(node_pk: int) -> dict:
    """Return a structured node summary for UI rendering or agent reasoning."""
    try:
        node = load_node(node_pk)
        return {
            "pk": node.pk,
            "type": node.node_type.split('.')[-2] if '.' in node.node_type else node.node_type,
            "ctime": node.ctime.strftime('%Y-%m-%d %H:%M:%S'),
            "label": node.label or "(No Label)",
            "state": getattr(node, 'process_state', 'N/A'),
            "exit_status": getattr(node, 'exit_status', 'N/A'),
            "incoming": len(node.get_incoming().all()),
            "outgoing": len(node.get_outgoing().all()),
            "attributes": node.attributes
        }
    except Exception as e:
        raise RuntimeError(f"Failed to load node {node_pk}: {str(e)}")
        
def serialize_node(node: orm.Node) -> dict:
    """
    Serialize any AiiDA node into an AI-friendly dictionary.
    Handles data-node payloads and process-node runtime status.
    """
    info = {
        "pk": node.pk,
        "uuid": node.uuid,
        "type": node.node_type.split('.')[-2] if '.' in node.node_type else node.node_type,
        "label": node.label or "N/A",
        "ctime": node.ctime.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Handle data payload extraction (ported from earlier calculation helpers).
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
