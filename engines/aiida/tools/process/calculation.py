"""
Deep inspection utilities for AiiDA calculation nodes (CalcJob, CalcFunction).
"""
from typing import Union
from aiida import orm
from engines.aiida.tools.base.node import serialize_node

def inspect_calculation(identifier: Union[int, str, orm.ProcessNode]) -> dict:
    """
    Analyze a calculation node in depth, including IO links, repository files, and scheduler metadata.
    
    Args:
        identifier: Node PK, UUID, or a Node instance.
    """
    try:
        # Normalize and resolve the input node.
        if isinstance(identifier, (int, str)):
            node = orm.load_node(identifier)
        else:
            node = identifier

        if not isinstance(node, (orm.CalcJobNode, orm.CalcFunctionNode)):
            return {"error": f"Node {node.pk} is not a calculation node."}

        # 1. Serialize core metadata with shared helpers.
        res = {
            "summary": serialize_node(node),
            "inputs": {},
            "outputs": {},
            "repository_files": []
        }

        # 2. Resolve incoming/outgoing links with unified serialization.
        for link in node.base.links.get_incoming().all():
            res["inputs"][link.link_label] = serialize_node(link.node)
            
        for link in node.base.links.get_outgoing().all():
            res["outputs"][link.link_label] = serialize_node(link.node)

        # 3. Extract repository file names.
        try:
            # Filter out internal AiiDA hidden files.
            files = node.base.repository.list_object_names()
            res["repository_files"] = [f for f in files if not f.startswith('.aiida')]
        except Exception:
            pass

        # 4. CalcJob specialization: include scheduler output metadata.
        if isinstance(node, orm.CalcJobNode):
            res["scheduler_info"] = {
                "remote_workdir": node.get_remote_workdir(),
                "stdout_name": node.get_option('output_filename'),
                "stderr_name": node.get_option('error_filename'),
                "has_retrieved": 'retrieved' in node.outputs
            }

        return res

    except Exception as e:
        return {"error": str(e)}
