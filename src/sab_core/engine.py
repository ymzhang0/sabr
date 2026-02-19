# src/sab_core/engine.py (核心升级)
from sab_core.protocols.perception import Perceptor
from sab_core.protocols.brain import Brain
from sab_core.protocols.executor import Executor
from sab_core.protocols.reporter import Reporter
from sab_core.protocols.memory import Memory
from sab_core.schema.observation import Observation # 🚩 确保导入了这个类
from typing import List, Dict, Any
from sab_core.schema.response import Response

class SABEngine:
    def __init__(
        self, 
        perceptor: Perceptor, 
        brain: Brain,
        executor:Executor, 
        reporters:List[Reporter]=[], 
        memory:Memory=None,
        max_recursions: int = 10,
        enable_reflection: bool = True
        ):

        self._perceptor = perceptor
        self._brain = brain
        self._executor = executor
        self._reporters = reporters
        self._memory = memory  # 🚩 新增 Memory 组件
        self._max_recursions = max_recursions
        self._enable_reflection = enable_reflection
        self._max_history_turns = 15 # Threshold for summarization

    def log(self, message: str, level: str = "INFO"):
        """将调试信息广播给所有绑定的 Reporter"""
        for reporter in self._reporters:
            if hasattr(reporter, 'debug'):
                reporter.debug('> ' + message, level)

    async def run_once(self, intent: str):
        """Agentic loop with error-break and reflection."""
        self.log(f"Starting mission: {intent}", level="INFO")
        observation = self._perceptor.perceive(intent)
        
        current_recursion = 0
        last_result = None
        final_action = None

        while current_recursion < self._max_recursions:

            # 2. M (Retrieve) - 注入对话历史 + 操作历史
            history = self._memory.get_context() if self._memory else []
            action_logs = self._memory.get_action_history() if self._memory else ""
            
            enhanced_observation = Observation(
                source=observation.source,
                raw=observation.raw + "\n\n" + action_logs
            )
            
            # Step 1: Brain Decision
            self.log(f"Cycle {current_recursion + 1}: Thinking...", level="DEBUG")
            action = await self._brain.decide(enhanced_observation, history=history)
            self.log(f"Action selected -> {action.name}", level="DEBUG")
        
            # Step 3: Branching based on Decision
            if action.name == "error_reported":
                final_action = action
                break

            # 🚩 Step 2: Reflection Check
            # If Brain wants to 'say' (finish), we force a reflection turn
            if action.name == "say" and self._enable_reflection:
                # We perform an internal 'Reflection' by augmenting the observation
                reflection_prompt = (
                    f"SYSTEM ALERT: You are about to provide this final response: '{action.payload.get('content')}'\n"
                    f"ORIGINAL INTENT: {intent}\n"
                    "Evaluate if the intent is FULLY satisfied. If not, call a tool to fix it. "
                    "If satisfied, repeat your 'say' action."
                )
                
                # Re-consult the brain with the reflection challenge
                reflected_observation = Observation(
                    source="system:reflector",
                    raw=enhanced_observation.raw + "\n\n" + reflection_prompt
                )
                
                # One-shot reflection decision
                action = await self._brain.decide(reflected_observation, history=history)
                self.log(f"Reflection completed. New Action: {action.name}", level="DEBUG")
            

            # Step 4: Execution (if tool call)
            result = await self._executor.execute(action)
            # 🚩 改进：在循环内记录“中间动作”，供反思参考
            if self._memory:
                self._memory.store_action({
                    "action": action.name,
                    "result_summary": str(result)[:100],
                    "success": True if result else False
                })

            last_result = result
            
            # Step 5: Progress Reporting
            for reporter in self._reporters:
                reporter.emit(observation, action)
            
            # Step 6: Update Observation for next cycle
            observation = Observation(
                source=f"executor:{action.name}",
                raw=f"Execution Result of {action.name}: {str(result)}"
            )
            
            current_recursion += 1

        # Fallback for max recursions
        if not final_action:
            self.log("Max recursions reached. Terminating cycle.", level="WARNING")
            final_action = action # Use the last action as fallback

        # 8. Package Final Response
        response = Response(
            result=last_result,
            content=final_action.payload.get("content", ""),
            suggestions=final_action.suggestions,
            action_name=final_action.name
        )

        # 🚩 # 9. Store final interaction in Memory
        # 记录最终对用户的回复，这是最重要的
        if self._memory:
            self._memory.store({
                "intent": intent,
                "response": response.content,      # 经过反思修正后的最终文案
                "final_action": response.action_name,
                "total_steps": current_recursion   # 可选：记录迭代了多少次才成功
            })
            # 2. Check if compression is needed (30 messages = 15 turns)
            # 🚩 Check for summarization threshold (30 messages = 15 turns)
            history_len = len(self._memory.data.get("history", []))
            if history_len > self._max_history_turns * 2:
                await self._compress_memory(self._memory.data["history"])

        return response # 🚩 返回打包后的数据

    async def _compress_memory(self, history: List[dict]):
        """Use Brain to summarize old history and update long-term recap."""
        self.log("Summarizing long history for optimization...", level="INFO")
        to_summarize = history[:-10] # Summarize all but the last 5 turns
        to_keep = history[-10:]
        
        compress_obs = Observation(
            source="system:summarizer",
            raw=f"Summarize these AiiDA research interactions into a concise recap paragraph: {str(to_summarize)}"
        )
        
        try:
            # Run brain without history to avoid recursion
            summary_action = await self._brain.decide(compress_obs, history=[])
            new_summary = summary_action.payload.get("content", "General research activity.")
            
            old_summary = self._memory.data.get("summary", "")
            self._memory.update_summary(f"{old_summary} {new_summary}".strip(), to_keep)
        except Exception as e:
            self.log(f"Memory compression failed: {e}", level="WARNING")

    async def run_stream(self, intent: str):
        """Yields events: {'type': 'status', 'topic': '...'} or {'type': 'chunk', 'text': '...'}"""
        yield {"type": "status", "topic": "Perceiving context..."}
        observation = self._perceptor.perceive(intent)
        
        current_recursion = 0
        while current_recursion < self._max_recursions:
            history = self._memory.get_context() if self._memory else []
            action_logs = self._memory.get_action_history() if self._memory else ""
            enhanced_obs = Observation(source=observation.source, raw=f"{observation.raw}\n\n{action_logs}")
            
            yield {"type": "status", "topic": f"Thinking (Cycle {current_recursion + 1})..."}
            
            # Start streaming from Brain
            full_text = ""
            async for chunk in self._brain.stream_decide(enhanced_obs, history=history):
                if isinstance(chunk, str):
                    # It's a text chunk
                    full_text += chunk
                    yield {"type": "chunk", "text": chunk}
                else:
                    # It's a function call (terminal for streaming text in this turn)
                    action = Action(name=chunk.name, payload=chunk.args)
                    break
            else:
                # If loop finished normally, parse the full_text as JSON Action
                action = Action.model_validate_json(full_text)

            if action.name in ["say", "error_reported"]:
                yield {"type": "done", "action": action}
                return

            yield {"type": "status", "topic": f"Executing {action.name}..."}
            result = await self._executor.execute(action)
            
            observation = Observation(source=f"executor:{action.name}", raw=str(result))
            current_recursion += 1