"""
专精于 AiiDA 计算节点 (CalcJob, CalcFunction) 的深度审查工具。
"""
from typing import Union
from aiida import orm
from engines.aiida.tools.base.node import serialize_node

def inspect_calculation(identifier: Union[int, str, orm.ProcessNode]) -> dict:
    """
    深入分析计算节点的输入输出、仓库文件以及调度状态。
    
    Args:
        identifier: 节点的 PK, UUID 或 Node 对象。
    """
    try:
        # 统一加载节点
        if isinstance(identifier, (int, str)):
            node = orm.load_node(identifier)
        else:
            node = identifier

        if not isinstance(node, (orm.CalcJobNode, orm.CalcFunctionNode)):
            return {"error": f"Node {node.pk} is not a calculation node."}

        # 1. 基础信息序列化 (调用通用工具)
        res = {
            "summary": serialize_node(node),
            "inputs": {},
            "outputs": {},
            "repository_files": []
        }

        # 2. 解析输入输出链接 (使用统一的 serialize_node)
        for link in node.base.links.get_incoming().all():
            res["inputs"][link.link_label] = serialize_node(link.node)
            
        for link in node.base.links.get_outgoing().all():
            res["outputs"][link.link_label] = serialize_node(link.node)

        # 3. 提取仓库文件列表
        try:
            # 过滤掉 AiiDA 内部隐藏文件
            files = node.base.repository.list_object_names()
            res["repository_files"] = [f for f in files if not f.startswith('.aiida')]
        except Exception:
            pass

        # 4. CalcJob 特化：获取调度器输出位置信息
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