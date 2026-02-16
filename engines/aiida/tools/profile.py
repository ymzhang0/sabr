"""
Tools for inspecting the AiiDA profile (database statistics, groups).
"""
import io
from pathlib import Path
from aiida import load_profile, orm
from aiida.orm import Group, Node, QueryBuilder
from aiida.manage.configuration import get_config
from aiida.manage.manager import get_manager

# --- 1. 资源列表工具 (Perceptor 强依赖) ---

def list_system_profiles():
    """
    获取系统中所有 AiiDA Profile 的名称列表。
    (修复了感知器找不到该函数的问题)
    """
    try:
        return [p.name for p in get_config().profiles]
    except Exception as e:
        logger.warning(f"AiiDA config not found or invalid: {e}")
        return []

def list_local_archives():
    """
    扫描当前目录下的 AiiDA 压缩包文件。
    支持 .aiida 和 .zip 格式。
    """
    return [f.name for f in Path('.').glob('*') if f.suffix in ['.aiida', '.zip']]

# --- 2. 环境切换工具 ---

def switch_profile(profile_name: str) -> str:
    """
    切换当前的 AiiDA Profile。
    """
    available = list_system_profiles()
    if profile_name not in available:
        return f"Error: Profile '{profile_name}' not found. Available: {available}"
        
    try:
        load_profile(profile_name, allow_switch=True)
        return f"Successfully switched to profile '{profile_name}'."
    except Exception as e:
        return f"Error switching profile: {e}"

def load_archive_profile(archive_path: str):
    """
    将压缩包作为临时 Profile 加载（主要用于 AiiDA 2.x 的只读探测）。
    """
    try:
        from aiida.storage.sqlite_zip.backend import SqliteZipBackend
        archive_profile = SqliteZipBackend.create_profile(AIIDA_PROFILE_NAME)
        load_profile(archive_profile, allow_switch=True)
        # 这里的实现取决于你的具体环境配置，通常建议直接通过 get_archive_info 探测
        # 如果需要完整加载，通常使用临时存储后端
        return f"Archive profile loading for '{archive_path}' is ready for implementation."
    except Exception as e:
        return f"Error loading archive: {e}"

# --- 3. 深度感知工具 (Unified Map) ---

def inspect_archive(archive_path: str):
    """
    【手动探测器】直接读取 .aiida 压缩包内部的元数据。
    无需 aiida.tools.archive 模块。
    """
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            # AiiDA 存档通常在 metadata.json 或 export_parameters.json 中存储信息
            # 这里的逻辑根据 AiiDA 导出版本的不同可能略有差异
            if 'metadata.json' in zip_ref.namelist():
                with zip_ref.open('metadata.json') as f:
                    meta = json.load(f)
                    # 尝试提取组标签
                    groups = meta.get('export_parameters', {}).get('groups', [])
                    return {
                        "groups": [{"label": g} for g in groups] if groups else [],
                        "version": meta.get('aiida_version', 'unknown')
                    }
        return {"groups": [], "note": "Basic zip scan complete, no metadata found."}
    except Exception as e:
        return {"error": f"Zip inspection failed: {str(e)}"}

def get_unified_source_map(source_id: str, is_archive: bool = False):
    """
    【统一接口】无论是在线数据库还是离线包，返回一致的字典结构。
    """
    result = {"name": source_id, "type": "archive" if is_archive else "profile", "groups": []}

    if is_archive:
        info = inspect_archive(source_id)
        if "error" in info:
            result["error"] = info["error"]
        else:
            result["groups"] = [{"label": g["label"], "count": "N/A"} for g in info["groups"]]
    else:
        try:
            load_profile(source_id, allow_switch=True)
            # 获取最近的 8 个组
            qb = orm.QueryBuilder().append(orm.Group, project=["label", "id", "*"])
            for label, pk, group in qb.all():
                if group.type_string == "core.import": continue
                sample = group.nodes[0] if len(group.nodes) > 0 else None
                result["groups"].append({
                    "label": label,
                    "count": len(group.nodes),
                    "extras": list(sample.base.extras.all.keys())[:5] if sample else []
                })
        except Exception as e:
            result["error"] = str(e)
            
    return result
    
# --- 4. 数据统计工具 ---

def get_statistics(profile_name: str = None):
    """
    获取数据库的高层统计信息。
    """
    if profile_name:
        switch_profile(profile_name)
            
    output = io.StringIO()
    output.write(f"=== Database Stats ({get_manager().get_profile().name}) ===\n")
    
    types = {
        "Calculations": "process.calculation.calcjob.CalcJobNode.",
        "WorkChains": "process.workflow.workchain.WorkChainNode.",
        "Structures": "data.core.structure.StructureData."
    }
    
    for name, node_type in types.items():
        count = QueryBuilder().append(Node, filters={"node_type": {"like": f"{node_type}%"}}).count()
        output.write(f"{name}: {count}\n")
        
    return output.getvalue()

def list_groups(search_string: str = None):
    """
    以 Markdown 表格形式列出所有组，对 AI 非常友好。
    """
    qb = QueryBuilder()
    filters = {"label": {"like": f"%{search_string}%"}} if search_string else {}
    qb.append(Group, project=["label", "id", "*"], filters=filters)
    
    current = get_manager().get_profile().name
    lines = [f"**Groups in Profile: `{current}`**", "", "| PK | Label | Count |", "| :--- | :--- | :--- |"]
    
    for label, pk, group in qb.all():
        if group.type_string == "core.import": continue
        lines.append(f"| {pk} | {label} | {len(group.nodes)} |")
    
    return "\n".join(lines)