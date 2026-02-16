"""
Tool for inspecting AiiDA calculations (CalcJob, CalcFunction).
Exposes methods to get inputs, outputs, and repository content.
"""
from aiida import orm

def get_calculation_io(identifier: int):
    """
    Get the inputs, outputs, and repository content for a calculation node.
    Returns:
        dict: A dictionary containing 'inputs', 'outputs', 'repository'.
              Each is a dictionary of {link_label: info_dict}.
    """
    try:
        node = orm.load_node(identifier)
        
        info = {
            "inputs": {},
            "outputs": {},
            "repository": {}
        }
        
        # 1. Inputs
        incoming = node.base.links.get_incoming()
        for link in incoming.all():
            source = link.node
            if isinstance(source, (orm.Data, orm.FolderData)):
                info["inputs"][link.link_label] = _extract_node_info(source, link.link_label)
                
        # 2. Outputs
        outgoing = node.base.links.get_outgoing()
        for link in outgoing.all():
            target = link.node
            if isinstance(target, (orm.Data, orm.FolderData)):
                info["outputs"][link.link_label] = _extract_node_info(target, link.link_label)
                
        # 3. Repository
        try:
            repo_files = node.base.repository.list_object_names()
            repo_files = [f for f in repo_files if f != ".aiida" and not f.startswith(".aiida/")]
            
            if repo_files:
                info["repository"]["Repository"] = {
                    "pk": node.pk,
                    "uuid": node.uuid,
                    "label": "Repository",
                    "type": "Repository",
                    "full_type": "aiida.orm.nodes.repository.NodeRepository",
                    "payload": repo_files
                }
        except Exception:
            pass
            
        return info
        
    except Exception as e:
        return {"error": str(e)}

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
