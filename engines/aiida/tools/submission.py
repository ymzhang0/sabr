from aiida.plugins import WorkflowFactory
from aiida.common.exceptions import MissingEntryPointError
import json
from aiida.engine import submit
from aiida import orm

def inspect_workchain(entry_point_name: str):
    """
    检查一个 WorkChain 的输入定义，并判断它是否支持自动协议。
    
    Args:
        entry_point_name (str): 插件名称, e.g. 'quantumespresso.pw.relax'
    """
    try:
        WC = WorkflowFactory(entry_point_name)
    except MissingEntryPointError:
        return f"❌ Error: WorkChain '{entry_point_name}' not found."

    # 1. 检查是否支持 Protocol (这是最关键的)
    has_protocol = hasattr(WC, 'get_builder_from_protocol')
    
    # 2. 获取输入端口信息 (简化版，防止 Token 爆炸)
    spec = WC.spec()
    required_inputs = []
    optional_inputs = []
    
    for key, port in spec.inputs.items():
        info = f"{key} ({port.valid_type.__name__ if port.valid_type else 'Any'})"
        if port.required:
            required_inputs.append(info)
        else:
            optional_inputs.append(info)
            
    summary = f"""
    **WorkChain:** `{entry_point_name}`
    **Docstring:** {WC.__doc__.strip().splitlines()[0] if WC.__doc__ else 'No doc'}
    **Supports Protocols:** {'✅ YES' if has_protocol else '❌ NO'}
    
    **Required Inputs:**
    {', '.join(required_inputs)}
    
    **Common Optional Inputs:**
    {', '.join(optional_inputs[:10])}... (truncated)
    """
    return summary


def draft_generic_builder(workchain_label: str, structure_pk: int, code_label: str, protocol: str = 'moderate', overrides_dict: dict = None):
    """
    通用的 Builder 草拟工具。
    
    Args:
        workchain_label (str): e.g., 'quantumespresso.pw.relax'
        structure_pk (int): 结构 ID
        code_label (str): Code Label
        protocol (str): 'fast', 'moderate', 'precise'
        overrides_dict (dict): 用户想要修改的参数 (e.g. {'kpoints_distance': 0.1})
    """
    try:
        # 1. 加载资源
        WC = WorkflowFactory(workchain_label)
        structure = orm.load_node(structure_pk)
        code = orm.load_code(code_label)
        
        # 2. 检查协议支持
        if not hasattr(WC, 'get_builder_from_protocol'):
            return "❌ This WorkChain does not support 'get_builder_from_protocol'. Automatic drafting failed."

        # 3. 构建 Builder
        # 注意：overrides 需要格外小心，LLM 传进来的 JSON 需要校验
        overrides = overrides_dict or {}
        
        builder = WC.get_builder_from_protocol(
            code=code,
            structure=structure,
            protocol=protocol,
            overrides=overrides
        )
        
    except Exception as e:
        return f"❌ Builder Construction Failed: {str(e)}"

def submit_draft(draft_data: dict):
    """
    根据 UI 传来的草稿数据，真正执行提交。
    
    Args:
        draft_data (dict): 包含 structure_pk, code_label, workchain, protocol, overrides
    
    Returns:
        int: 新提交进程的 PK
    """
    try:
        # 1. 解包数据
        # 注意：这里要跟 draft_generic_builder 返回的字段对应上
        summary = draft_data.get('summary', {})
        
        struct_pk = summary.get('structure_pk')
        code_label = summary.get('code')
        wc_name = summary.get('workchain')
        protocol = summary.get('protocol', 'moderate')
        overrides = summary.get('overrides', {})

        # 2. 加载 AiiDA 资源
        structure = orm.load_node(struct_pk)
        code = orm.load_code(code_label)
        WorkChain = WorkflowFactory(wc_name)

        # 3. 重新构建 Builder (这一步很快)
        # 这样避免了 Pickle Builder 对象的复杂性
        builder = WorkChain.get_builder_from_protocol(
            code=code,
            structure=structure,
            protocol=protocol,
            overrides=overrides
        )
        
        # 4. 真正提交！
        node = submit(builder)
        
        return node.pk
        
    except Exception as e:
        raise RuntimeError(f"Submission failed: {str(e)}")