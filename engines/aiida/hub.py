# engines/aiida/hub.py
from aiida import load_profile
from aiida.manage import Profile
from loguru import logger
from .tools import get_default_profile, list_system_profiles, get_recent_processes, load_archive_profile
from pathlib import Path
from pydantic import BaseModel, ConfigDict
import shutil
import os

# 🚩 定义 UI 显示模型
class ProfileItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: str = None
    path: Path | None = None
    object: Profile | None= None

def _force_purge_pid_locks():
    """
    暴力清理所有 Profile 的 PID 锁。
    在 Windows 开发环境下，这是防止 WinError 183 的最稳妥办法。
    """
    access_root = Path.home() / ".aiida" / "access"
    if access_root.exists():
        try:
            # 遍历 access 下的所有子目录 (test, test_dislocation 等)
            for profile_dir in access_root.iterdir():
                if profile_dir.is_dir():
                    # 尝试删除该目录下的所有文件
                    for f in profile_dir.glob("*"):
                        try:
                            os.remove(f)
                        except:
                            pass 
            logger.debug("🧹 All access PID locks purged.")
        except Exception as e:
            logger.debug(f"Lock purge skipped: {e}")

class AiiDAHub:
    """
    AiiDA 引擎的后台状态中心。
    它只被主框架在启动时调用，保持 AiiDA 环境的活性。
    """
    def __init__(self):
        # 🚩 核心池：{ "name": { "type": "system"|"imported", "path": "...", "object": ProfileInstance } }
        self._ALL_PROFILES: dict[str, ProfileItem] = {}
        self._CURRENT_PROFILE = None

    def start(self):
        logger.info(f"🚀 [AiiDA Hub] Initializing backend environment: {self.current_profile}")
        # _force_purge_pid_locks()
        try:
            self._CURRENT_PROFILE = get_default_profile().name
            for p in list_system_profiles():
                self._ALL_PROFILES[p.name] = ProfileItem(
                    type= "configured",
                    path= None,
                    object= p
                    )
                
            logger.success(f"✅ [AiiDA Hub] Hub started with {len(self._ALL_PROFILES)} system profiles.")
        except Exception as e:
            logger.error(f"❌ [AiiDA Hub] Failed to initialize: {e}")

    @property
    def current_profile(self):
        return self._CURRENT_PROFILE
    
    def _clear_access_locks(self, profile_name: str):
        """
        更激进的清理逻辑
        """
        import shutil
        import os
        from pathlib import Path
        
        # AiiDA 的 access 目录通常在 ~/.aiida/access/
        access_dir = Path.home() / ".aiida" / "access" / profile_name
        
        if access_dir.exists():
            try:
                # 在 Windows 上，有时候直接 rmtree 会因为文件被占用失败
                # 我们可以尝试遍历并删除所有 .pid 和 .tmp 文件

                for lock_file in access_dir.glob("*"):
                    try:
                        os.remove(lock_file)
                    except:
                        pass
                shutil.rmtree(access_dir, ignore_errors=True)
                logger.debug(f"✅ [AiiDA Hub] Access directory: {str(access_dir)} cleaned.")
            except Exception as e:
                logger.error(f"❌ [AiiDA Hub] Could not fully clear locks for {profile_name}: {e}")

    def switch_profile(self, name: str):
        if not name in self._ALL_PROFILES:
            logger.warning(f"⚠️ [AiiDA Hub] {name} not found in registred profiles")
        # 🚩 核心保护：检查当前 AiiDA 环境是否已经加载了目标 Profile
        if name == self.current_profile:
            logger.info(f"✨ [AiiDA Hub] Profile '{name}' is already active, skipping load.")
            self.current_profile = name # 确保 UI 状态一致
            return
        # self._clear_access_locks(name)
        profileitem = self._ALL_PROFILES[name]
        logger.warning(f"🔄 [AiiDA Hub] Switching context: {self.current_profile} -> {name}")
        if profileitem.type == 'configured':
            load_profile(self._ALL_PROFILES[name].object, allow_switch=True)
        elif profileitem.type == 'imported':
            load_archive_profile(filepath = str(profileitem.path))

        self._CURRENT_PROFILE = name

    def import_archive(self, path: Path):
        """
        将 Profile 实例添加到 Hub 的资源池中。
        如果名字冲突，自动寻找可用的序号后缀（如 _1, _2）。
        """
        base_name = path.stem
        unique_name = base_name
        counter = 1

        # 🚩 核心逻辑：检查撞名
        # 只要 unique_name 已经存在于 _ALL_PROFILES 键值中，就继续递增
        while unique_name in self._ALL_PROFILES:
            unique_name = f"{base_name}_{counter}"
            counter += 1

        # 如果发生了重命名，我们记录一下日志
        if unique_name != base_name:
            logger.warning(f"⚠️ [AiiDA Hub] Collision detected: Renaming profile '{base_name}' -> '{unique_name}' for UI display.")

        # 存入资源池
        # 这里的 object 是 AiiDA 的 Profile 实例
        self._ALL_PROFILES[unique_name] = ProfileItem(
                type= "imported",
                path= path,
                object= None
                )

        logger.success(f"✅ [AiiDA Hub] {unique_name} registred.")
        
        return unique_name # 返回最终确定的名字，方便后续操作

    def get_display_list(self):
        """给 API 用的格式化输出"""
        return [
            [name, name + " (imported)" if meta.type=='imported' else name, (name == self.current_profile)]
            for name, meta in self._ALL_PROFILES.items()
        ]
# 单例化，供 API 层调用状态
hub = AiiDAHub()