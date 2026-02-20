sabr/
├── src/
│   └── sab_core/
│       ├── agents/              # 🧠 只存放通用基类
│       │   ├── base.py          # Generic Agent wrapper using PydanticAI
│       │   └── manager.py       # 通用调度逻辑 (不涉及 AiiDA)
│       ├── deps/                # 🔗 核心依赖基类
│       │   └── base.py          # BaseDeps (Generic context, memory, steps)
│       └── schema/              # ✅ 通用契约
│           └── response.py      # Standardized ResultType for any science agent
└── engines/
    └── aiida/                   # 🚩 AiiDA 的所有秘密都在这里
        ├── agents/              # AiiDA 专有的智能体
        │   └── researcher.py    # ResearcherAgent (Inherits from sab_core.base)
        ├── deps.py              # AiiDA-specific context (Inherits from BaseDeps)
        ├── tools/               # 你的原子工具箱 (保留原有的精细分类)
        │   ├── base/
        │   ├── data/
        │   └── ...
        └── schema.py            # AiiDA 领域特有的数据模型 (Nodes, Groups)