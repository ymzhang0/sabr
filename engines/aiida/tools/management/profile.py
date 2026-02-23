"""
Tools for inspecting the AiiDA profile (database statistics, groups).
"""
import os
import io
from pathlib import Path
from aiida import load_profile, orm
from aiida.orm import Group, Node, QueryBuilder, ProcessNode
from aiida.manage.configuration import get_config
from aiida.manage.manager import get_manager
from aiida.storage.sqlite_zip.backend import SqliteZipBackend
from aiida.manage import Profile


# --- 1. Resource-listing tools (required by the perceptor) ---
_CURRENT_MOUNTED_ARCHIVE = None

def ensure_environment(target: str):
    """
    Smart environment switch:
    detect whether `target` is a local profile or an archive file.
    """
    global _CURRENT_MOUNTED_ARCHIVE

    if not target or target == "(None)":
        return

    if target == _CURRENT_MOUNTED_ARCHIVE:
        return

    try:
        # 1. If `target` is an existing archive file path, mount it temporarily.
        if os.path.isfile(target) and target.lower().endswith(('.aiida', '.zip')):
            archive_profile = SqliteZipBackend.create_profile(filepath=target,)
            load_profile(archive_profile, allow_switch=True)
            _CURRENT_MOUNTED_ARCHIVE = target  # Update cache.
            print(f"✅ Backend loaded archive as profile: {target}")
        else:
            # 2. Otherwise treat `target` as a configured profile name.
            load_profile(target, allow_switch=True)
            _CURRENT_MOUNTED_ARCHIVE = None  # Reset archive cache for profile mode.
            print(f"✅ Backend switched to profile: {target}")
    except Exception as e:
        print(f"❌ DEBUG: Failed to switch AiiDA environment: {e}")

def get_default_profile() -> Profile:
    config = get_config()
    return config.get_profile(config.default_profile_name)
    # return load_profile(config.default_profile_name, allow_switch=True)
    
def list_system_profiles():
    """
    Return all configured AiiDA profiles on the current system.
    """
    config = get_config()
    return config.profiles

def list_local_archives():
    """
    Scan the current directory for AiiDA archive files.
    Supported extensions: .aiida and .zip.
    """
    return [f.name for f in Path('.').glob('*') if f.suffix in ['.aiida', '.zip']]

# --- 2. Environment-switching tools ---

def switch_profile(profile: str | Profile) -> str:
    """
    Switch the active AiiDA profile.
    """
    try:
        if isinstance(profile, str):
            load_profile(profile, allow_switch=True)
            return f"Successfully switched to profile '{profile}'."
        load_profile(profile, allow_switch=True)
        return f"Successfully switched to profile '{profile.name}'."
    except Exception as e:
        return f"Error switching profile: {e}"

def load_archive_profile(filepath: str):
    """
    Load an archive as a temporary profile (primarily for AiiDA 2.x read-only inspection).
    """
    try:
        from aiida.storage.sqlite_zip.backend import SqliteZipBackend
        archive_profile = SqliteZipBackend.create_profile(filepath = filepath)
        profile = load_profile(archive_profile, allow_switch=True)
        # Implementation depends on local environment configuration.
        # For metadata-only checks, `get_archive_info` is usually preferred.
        return profile
    except Exception as e:
        raise Warning(f"Error loading archive: {e}")

# --- 3. Deep-perception tools (Unified Map) ---
def get_unified_source_map(target: str):
    """
    Unified resource mapping:
    force environment sync first, then query groups via QueryBuilder.
    """
    ensure_environment(target)
    
    # Include `type` to avoid downstream key assumptions.
    is_arch = target.lower().endswith(('.aiida', '.zip'))
    result = {
        "name": os.path.basename(target), 
        "type": "archive" if is_arch else "profile", 
        "groups": []
    }
    try:
        # Once synchronized, use ORM queries consistently.
        qb = orm.QueryBuilder().append(orm.Group, project=["label", "id"])
        for label, pk in qb.all():
            if "import" in label.lower():
                continue
            result["groups"].append({"label": label, "pk": pk})
    except Exception as e:
        result["error"] = str(e)
    return result

# --- 4. Statistics tools ---

def get_statistics(profile_name: str = None):
    """
    Return high-level database statistics.
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
    List all groups in a markdown table format that is AI-friendly.
    """
    qb = QueryBuilder()
    filters = {"label": {"like": f"%{search_string}%"}} if search_string else {}
    qb.append(Group, project=["label", "id", "*"], filters=filters)
    
    current = get_manager().get_profile().name
    lines = [f"**Groups in Profile: `{current}`**", "", "| PK | Label | Count |", "| :--- | :--- | :--- |"]
    
    for label, pk, group in qb.all():
        if group.type_string == "core.import":
            continue
        lines.append(f"| {pk} | {label} | {len(group.nodes)} |")
    
    return "\n".join(lines)

def get_database_summary():
    """
    Lightweight summary for the UI welcome screen.
    Returns a raw dictionary for UI rendering.
    """
    try:
        n_count = QueryBuilder().append(Node).count()
        p_count = QueryBuilder().append(ProcessNode).count()
        
        # Include failed-process count for quick health checks.
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
    Core query wrapper for recent AiiDA processes.
    Used both as an AI tool and as a controller-side data source.
    """
    qb = QueryBuilder()
    qb.append(ProcessNode, project=['id', 'attributes.process_state', 'attributes.process_label', 'ctime'], tag='process')
    qb.order_by({'process': {'ctime': 'desc'}})
    qb.limit(limit)
    
    results = []
    for pk, state, label, _ctime in qb.all():
        results.append({
            'pk': pk,
            'state': state.value if hasattr(state, 'value') else str(state),
            'label': label or 'Unknown Task'
        })
    return results
