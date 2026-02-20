"""
Tools for inspecting the AiiDA profile (database statistics, groups).
"""
import os
import io
import json      # 🚩 补上这个
import zipfile   # 🚩 补上这个
from pathlib import Path
from aiida import load_profile, orm
from aiida.orm import Group, Node, QueryBuilder, ProcessNode, Node
from aiida.manage.configuration import get_config
from aiida.manage.manager import get_manager
from aiida.storage.sqlite_zip.backend import SqliteZipBackend

# 🚩 增加一个内存缓存，记录当前加载的 Archive 路径
_CURRENT_MOUNTED_ARCHIVE = None

# --- 1. 资源列表工具 (Perceptor 强依赖) ---

def ensure_environment(target: str):
    """
    智能切换环境：自动识别是本地 Profile 还是 Archive 文件。
    """
    global _CURRENT_MOUNTED_ARCHIVE

    if not target or target == "(None)":
        return

    if target == _CURRENT_MOUNTED_ARCHIVE:
        return

    try:
        # 1. 如果是文件路径且存在
        if os.path.isfile(target) and target.lower().endswith(('.aiida', '.zip')):
            # 🚀 核心修复：将 Archive 文件路径包装成临时 Profile 对象
            archive_profile = SqliteZipBackend.create_profile(filepath=target,)
            load_profile(archive_profile, allow_switch=True)
            _CURRENT_MOUNTED_ARCHIVE = target # 更新缓存
            print(f"✅ Backend loaded archive as profile: {target}")
        else:
            # 2. 否则按普通 Profile 名称加载
            load_profile(target, allow_switch=True)
            _CURRENT_MOUNTED_ARCHIVE = None # 切换回普通 Profile
            print(f"✅ Backend switched to profile: {target}")
    except Exception as e:
        print(f"❌ DEBUG: Failed to switch AiiDA environment: {e}")

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

def load_archive_profile(filepath: str):
    """
    将压缩包作为临时 Profile 加载（主要用于 AiiDA 2.x 的只读探测）。
    """
    try:
        from aiida.storage.sqlite_zip.backend import SqliteZipBackend
        archive_profile = SqliteZipBackend.create_profile(filepath = filepath)
        load_profile(archive_profile, allow_switch=True)
        # 这里的实现取决于你的具体环境配置，通常建议直接通过 get_archive_info 探测
        # 如果需要完整加载，通常使用临时存储后端
        return f"Archive profile loading for '{filepath}' is ready for implementation."
    except Exception as e:
        return f"Error loading archive: {e}"

# --- 3. 深度感知工具 (Unified Map) ---
def get_unified_source_map(target: str):
    """
    统一资源映射逻辑：先强制同步环境，再用 QueryBuilder 读取。
    """
    ensure_environment(target)
    
    # 🚩 修复 KeyError: 增加 'type' 键
    is_arch = target.lower().endswith(('.aiida', '.zip'))
    result = {
        "name": os.path.basename(target), 
        "type": "archive" if is_arch else "profile", 
        "groups": []
    }
    try:
        # 环境一旦同步，统一使用 ORM 查询
        qb = orm.QueryBuilder().append(orm.Group, project=["label", "id"])
        for label, pk in qb.all():
            if "import" in label.lower(): continue
            result["groups"].append({"label": label, "pk": pk})
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

def get_database_summary():
    """
    专门为 UI 迎宾界面设计的快速统计工具。
    返回原始数据字典，供 UI 使用。
    """
    try:
        n_count = QueryBuilder().append(Node).count()
        p_count = QueryBuilder().append(ProcessNode).count()
        
        # 还可以顺便统计一下失败的任务
        failed_count = orm.QueryBuilder().append(
            ProcessNode, 
            filters={'exit_status': {'!==': 0}}
        ).count()

        return {
            "status": "success",
            "node_count": n_count,
            "process_count": p_count,
            "failed_count": failed_count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_recent_processes(limit: int = 5):
    """
    🚩 核心：封装 AiiDA 数据库查询逻辑。
    这个函数既可以给 AI 当 Tool 用，也可以给 Controller 当内部数据源用。
    """
    qb = QueryBuilder()
    qb.append(ProcessNode, project=['id', 'attributes.process_state', 'attributes.process_label', 'ctime'], tag='process')
    qb.order_by({'process': {'ctime': 'desc'}})
    qb.limit(limit)
    
    results = []
    for pk, state, label, ctime in qb.all():
        results.append({
            'pk': pk,
            'state': state.value if hasattr(state, 'value') else str(state),
            'label': label or 'Unknown Task'
        })
    return results