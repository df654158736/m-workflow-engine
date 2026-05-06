#!/usr/bin/env python3
"""启动工作流引擎 Demo 服务。

用法:
    python run.py             # 按 config.yaml 配置启动
    STANDALONE=1 python run.py  # 强制单机模式
    STANDALONE=0 python run.py  # 强制完整模式
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from backend.server import main

if __name__ == "__main__":
    main()
