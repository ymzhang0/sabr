import os
import re
from sab_core.schema.observation import Observation
from engines.aiida.tools import (
    get_unified_source_map, 
    list_system_profiles, 
    list_local_archives
)

class AIIDASchemaPerceptor:
    def perceive(self, intent: str = None) -> Observation:
        target = None
        
        # 1. 路径解析逻辑 (保持原有的深度解析 🚀)
        match = re.search(r"archive '(.+?)'", intent or "")
        if match:
            path_val = match.group(1)
            if path_val != "(None)" and os.path.exists(path_val):
                target = path_val
            else:
                basename = os.path.basename(path_val)
                if os.path.exists(basename):
                    target = basename

        # 2. Profile 名称匹配 (保持原有逻辑 🚀)
        if not target and intent:
            profiles = list_system_profiles() 
            for p in profiles:
                if p in intent:
                    target = p
                    break

        # 3. 构造报告
        user_msg = f"MESSAGE FROM USER: {intent}\n\n" if intent else ""
        
        if target:
            # 💡 这里的调用会触发 profile.py 里的 ensure_environment
            smap = get_unified_source_map(target)
            raw_report = user_msg + self._format_deep_report(smap)
        else:
            raw_report = user_msg + (
                f"### AIIDA RESOURCE OVERVIEW ###\n"
                f"Available Profiles: {list_system_profiles()}\n"
                f"Available Archives: {list_local_archives()}\n"
            )

        return Observation(source="aiida_aware_scanner", raw=raw_report, features={"target": target})
    def _format_deep_report(self, smap):
        """格式化深度扫描报告"""
        if "error" in smap:
            return f"⚠️ Error scanning {smap['name']}: {smap['error']}"
        
        lines = [f"### Source: {smap['name']} ({smap['type'].upper()}) ###"]
        if not smap.get('groups'):
            lines.append("  (No groups detected)")
        else:
            for g in smap['groups']:
                count_str = f"Nodes: {g['count']}" if g.get('count') and g['count'] != "N/A" else "Archive Contents"
                lines.append(f"- Group: '{g['label']}' ({count_str})")
                if g.get('extras'):
                    lines.append(f"  └── Sample Keys: {g['extras']}")
        return "\n".join(lines)