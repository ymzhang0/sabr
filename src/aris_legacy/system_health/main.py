from src.aris_legacy.system_health.executor import ConsoleExecutor
from src.aris_legacy.system_health.perceptor import SystemPerceptor


def main():
    print("Starting legacy system-health CLI demo... (Ctrl+C to stop)")
    perceptor = SystemPerceptor()
    executor = ConsoleExecutor()
    while True:
        observation = perceptor.perceive()
        executor.execute(type("Action", (), {"name": "no_op", "payload": {"message": observation.raw}})())
        import time

        time.sleep(5)


if __name__ == "__main__":
    main()
