# engines/aiida/tools/submission/builder.py
from aiida.plugins import WorkflowFactory
from aiida.common.exceptions import MissingEntryPointError
import json
from aiida.engine import submit
from aiida import orm

def inspect_workchain_spec(entry_point_name: str):
    """
    检查 WorkChain 的输入定义(Spec)，查看其端口要求和协议支持。
    """
    try:
        WC = WorkflowFactory(entry_point_name)
    except MissingEntryPointError:
        return f"❌ Error: WorkChain '{entry_point_name}' not found."

    has_protocol = hasattr(WC, 'get_builder_from_protocol')
    spec = WC.spec()
    
    # 提取必填和选填项
    required = [f"{k} ({v.valid_type.__name__ if v.valid_type else 'Any'})" 
                for k, v in spec.inputs.items() if v.required]
    
    summary = (
        f"**WorkChain:** `{entry_point_name}`\n"
        f"**Supports Protocols:** {'✅ YES' if has_protocol else '❌ NO'}\n"
        f"**Required Inputs:** {', '.join(required) if required else 'None'}"
    )
    return summary

def draft_workchain_builder(workchain_label: str, structure_pk: int, code_label: str, protocol: str = 'moderate', overrides: dict = None):
    """
    根据协议草拟一个任务 Builder。它不会真正提交，而是返回草案供确认。
    """
    try:
        # 1. 验证资源
        WC = WorkflowFactory(workchain_label)
        if not hasattr(WC, 'get_builder_from_protocol'):
            return "❌ Error: This WorkChain does not support protocols."

        # 2. 模拟构建 (检查参数是否能跑通)
        # 这里我们不需要保存 builder 对象，我们要的是这套参数
        _ = WC.get_builder_from_protocol(
            code=orm.load_code(code_label),
            structure=orm.load_node(structure_pk),
            protocol=protocol,
            overrides=overrides or {}
        )

        # 3. 🚩 重要：返回给 AI 和 UI 确认的结构化数据
        return {
            "status": "DRAFT_READY",
            "workchain": workchain_label,
            "structure_pk": structure_pk,
            "code": code_label,
            "protocol": protocol,
            "overrides": overrides or {},
            "preview": f"Ready to submit {workchain_label} using {protocol} protocol."
        }
        
    except Exception as e:
        return f"❌ Builder Draft Failed: {str(e)}"

def submit_workchain_builder(draft_data: dict):
    """
    接收来自 draft_workchain_builder 的草案数据并执行真正提交。
    """
    try:
        # 直接从草案数据中取值，实现闭环
        wc_name = draft_data.get('workchain')
        struct_pk = draft_data.get('structure_pk')
        code_label = draft_data.get('code')
        protocol = draft_data.get('protocol', 'moderate')
        overrides = draft_data.get('overrides', {})

        # 重新加载 AiiDA 资源
        WorkChain = WorkflowFactory(wc_name)
        builder = WorkChain.get_builder_from_protocol(
            code=orm.load_code(code_label),
            structure=orm.load_node(struct_pk),
            protocol=protocol,
            overrides=overrides
        )
        
        node = submit(builder)
        return f"✅ Success! WorkChain submitted. PK: {node.pk}"
        
    except Exception as e:
        return f"❌ Submission failed: {str(e)}"