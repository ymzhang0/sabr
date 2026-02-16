import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 1. 这一行是关键：它会搜索 .env 文件并把里面的变量注入到 os.environ
load_dotenv()

from loguru import logger

# 强制移除旧配置并添加一个标准输出 sink
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

# 将根目录加入路径，确保所有的绝对导入 (from examples.aiida...) 都能工作
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# 只负责调用 AiiDA 示例的入口
from engines.aiida.main import main

if __name__ in {"__main__", "__mp_main__"}:
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ Warning: GEMINI_API_KEY not found in environment!")
    main()