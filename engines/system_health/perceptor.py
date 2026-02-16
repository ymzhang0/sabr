import psutil
from sab_core.schema.observation import Observation

class SystemPerceptor:
    def perceive(self) -> Observation:
        cpu = psutil.cpu_percent(interval=0.1)
        return Observation(
            source="system",
            features={"cpu_usage": cpu},
            raw=f"CPU usage is at {cpu}%"
        )