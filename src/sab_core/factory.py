# src/sab_core/factory.py
import importlib
import sys
import os
from .config import settings
def get_engine_instance():
    # 🚩 强行将当前根目录加入路径，防止找不到 engines 文件夹
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    engine_name = "aiida" # 假设从 settings 读取
    
    # 🚩 注意这里的路径：必须是 'engines.aiida.factory'
    module_path = f"engines.{engine_name}.factory"
    
    try:
        module = importlib.import_module(module_path)
        return module.create_engine()
    except ImportError as e:
        # 如果报错里提到了 AiiDA 内的其它包，说明是官方库没安
        raise RuntimeError(f"模块导入失败。请检查 {module_path} 是否存在，或是否缺少依赖: {e}")

def load_ui_package():
    """
    动态加载当前引擎的 UI 套件：包含布局(layout)和控制器(controller)。
    """
    engine_name = settings.ENGINE_TYPE
    try:
        # 1. 加载布局
        layout_mod = importlib.import_module(f"engines.{engine_name}.ui.layout")
        # 2. 加载控制器类
        controller_mod = importlib.import_module(f"engines.{engine_name}.ui.controller")
        
        # 假设控制器类名遵循约定，如 RemoteAiiDAController
        # 或者在 controller.py 里统一叫 UIController
        return layout_mod.create_layout, controller_mod.RemoteAiiDAController
    except Exception as e:
        raise RuntimeError(f"无法加载引擎 {engine_name} 的 UI 套件: {e}")