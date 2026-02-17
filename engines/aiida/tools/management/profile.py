"""
Tools for inspecting the AiiDA profile (database statistics, groups).
"""
import os
import io
import json      # 🚩 补上这个
import zipfile   # 🚩 补上这个
from pathlib import Path
from aiida import load_profile, orm
from aiida.orm import Group, Node, QueryBuilder
from aiida.manage.configuration import get_config
from aiida.manage.manager import get_manager
from aiida.storage.sqlite_zip.backend import SqliteZipBackend
# --- 1. 资源列表工具 (Perceptor 强依赖) ---

def ensure_environment(target: str):
    """
    智能切换环境：自动识别是本地 Profile 还是 Archive 文件。
    """
    if not target or target == "(None)":
        return
    
    try:
        # 1. 如果是文件路径且存在
        if os.path.isfile(target) and target.lower().endswith(('.aiida', '.zip')):
            # 🚀 核心修复：将 Archive 文件路径包装成临时 Profile 对象
            archive_profile = SqliteZipBackend.create_profile(filepath=target,)
            load_profile(archive_profile, allow_switch=True)
            print(f"✅ Backend loaded archive as profile: {target}")
        else:
            # 2. 否则按普通 Profile 名称加载
            load_profile(target, allow_switch=True)
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