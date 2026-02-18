2. 输入框“呼吸感知” (Input Pill ↔ Brain Status)
输入框不应该只是一个文本框，它应该是引擎状态的延伸。
. 动态上下文建议卡片 (Suggestion Grid ↔ Archive State)
目前建议卡片是静态的。当用户切换不同的 AiiDA 档案时，建议卡片应该感知档案内容并自动刷新。

联动逻辑：当 select_archive 触发时，Perceptor 提取该档案的特征（例如：主元素是 Si、包含大量的 WorkChain、或者包含错误节点）。

丝滑体现：用户刚选好档案，下方的建议卡片就从“显示统计信息”变成了“查看 Si 的能带结构”或“分析失败的任务”。

2. 输入框“呼吸感知” (Input Pill ↔ Brain Status)
输入框不应该只是一个文本框，它应该是引擎状态的延伸。

联动逻辑：当 Brain 正在“思考”或 Executor 正在“查询数据库”时，输入框的边框或背景色产生微弱的呼吸灯效果（利用 CSS Animation）。

丝滑体现：不需要看那个转圈的 Spinner，用户通过输入框的视觉反馈就能感知到 AI 正在“用力”处理数据。

代码思路：通过 Reporter 修改 input-pill 的 CSS 类名，触发 .breathing-border 动画。

3. 数据“锚点”联动 (Chat Area ↔ Insight Markdown)
这是最硬核的联动。当 AI 在回复中提到某个 Node ID (比如 Node 1234) 时，侧边栏的 Insight 区域自动滚动并高亮该节点的详细信息。

联动逻辑：AI 回复包含特定格式的 ID -> 触发 UI 事件 -> 修改 debug_log 的内容或高亮某一行。

丝滑体现：用户点击聊天气泡里的 ID，侧边栏就像“详情页”一样立即展示对应的数据，无需手动搜索。

4. 自动“迎宾”与档案概览 (Archive Switch ↔ Welcome Screen)
切换档案不应只是通知一下，而应是一次视觉上的环境重置。

联动逻辑：档案切换成功后，Welcome Screen 的大标题不再是 "Hi, where should we start?"，而是变成该档案的缩略报告（例如："Loaded Si-Crystal Archive: 52 nodes found"）。

丝滑体现：通过这种反馈，用户能瞬间确认系统已经完全加载并理解了新数据。

5. 交互式执行器预览 (Executor ↔ Input)
当 AI 准备执行一个耗时的 AiiDA 任务时，在发送按钮旁弹出一个微型预览窗口。

联动逻辑：Brain 生成 Action 后，先不执行，而是在 UI 上显示“即将查询 500 个节点，是否继续？”。

丝滑体现：这种“确认-执行”的反馈链条能极大增加用户对系统的信任感。