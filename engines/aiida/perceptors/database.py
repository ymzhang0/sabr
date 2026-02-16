from sab_core.schema.observation import Observation
from engines.aiida.tools.profile import (
    get_unified_source_map, 
    list_system_profiles, 
    list_local_archives
)

class AIIDASchemaPerceptor:
    """AiiDA Resource Perceptor: Switches between Profile and Archive based on intent."""
    
    def perceive(self, intent: str = None) -> Observation:
        target = None
        is_archive = False

        # 1. 意图解析 (保持你原来的逻辑)
        if intent and (".aiida" in intent or ".zip" in intent):
            archives = list_local_archives()
            for arch in archives:
                if arch in intent:
                    target = arch
                    is_archive = True
                    break
        
        if not target and intent:
            profiles = list_system_profiles()
            for p in profiles:
                if p in intent:
                    target = p
                    break

        # --- 核心修改点：保留用户的话 ---
        # 即使我们解析出了 target，也要把原始的指令留给 AI 看
        user_context = f"MESSAGE FROM USER: {intent}\n\n" if intent else ""

        # 2. 执行感知
        if target:
            smap = get_unified_source_map(target, is_archive)
            # 把用户指令和深度报告拼在一起
            raw_report = user_context + self._format_deep_report(smap)
        else:
            profiles = list_system_profiles()
            archives = list_local_archives()
            # 把用户指令和概览信息拼在一起
            raw_report = user_context + (
                f"### AIIDA RESOURCE OVERVIEW ###\n"
                f"Available Profiles: {profiles}\n"
                f"Available Archives: {archives}\n"
                f"Hint: Select an archive from the sidebar or type 'Inspect [name]' to see details."
            )

        return Observation(
            source="aiida_aware_scanner", 
            features={"target": target, "is_archive": is_archive}, # 把特征也存一下，方便之后扩展
            raw=raw_report
        )

    def _format_deep_report(self, smap):
        if "error" in smap:
            return f"⚠️ Error scanning {smap['name']}: {smap['error']}"
        
        lines = [f"### Source: {smap['name']} ({smap['type'].upper()}) ###"]
        if not smap['groups']:
            lines.append("  (No groups detected)")
        for g in smap['groups']:
            count_str = f"Nodes: {g['count']}" if g['count'] != "N/A" else "Archive Contents"
            lines.append(f"- Group: '{g['label']}' ({count_str})")
            if g.get('extras'):
                lines.append(f"  └── Sample Keys: {g['extras']}")
        return "\n".join(lines)