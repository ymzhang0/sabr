import os
import re
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

        # 1. 路径解析优化：从意图中提取被引号包裹的路径
        # 匹配格式: archive 'C:\Users\...' 
        match = re.search(r"archive '(.+?)'", intent or "")
        
        if match:
            path_val = match.group(1)
            # 如果路径在本地真实存在，则直接作为目标，无需拷贝
            if path_val != "(None)" and os.environ.get('PATH_EXISTS', os.path.exists(path_val)):
                target = path_val
                is_archive = target.lower().endswith(('.aiida', '.zip'))
            else:
                # 兼容逻辑：尝试在当前目录下找文件名
                basename = os.path.basename(path_val)
                if os.path.exists(basename):
                    target = basename
                    is_archive = target.lower().endswith(('.aiida', '.zip'))

        # 2. 如果没有路径，则尝试匹配 Profile 名称
        if not target and intent:
            # 这里调用的是文件开头导入的全局函数
            profiles = list_system_profiles() 
            for p in profiles:
                if p in intent:
                    target = p
                    break

        # 3. 构造报告
        user_msg = f"MESSAGE FROM USER: {intent}\n\n" if intent else ""
        
        if target:
            # 调用全局导入的工具
            smap = get_unified_source_map(target, is_archive)
            raw_report = user_msg + self._format_deep_report(smap)
        else:
            # 🚩 删除了这里的局部 import 语句，直接使用全局导入的函数
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