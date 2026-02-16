import sys
from pathlib import Path

# 将根目录加入路径，确保所有的绝对导入 (from examples.aiida...) 都能工作
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# 只负责调用 AiiDA 示例的入口
from engines.aiida.main import main

if __name__ in {"__main__", "__mp_main__"}:
    main()