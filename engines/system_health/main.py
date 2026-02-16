from perceptor import SystemPerceptor
from executor import ConsoleExecutor
from sab_core import GeminiBrain, SABEngine
from sab_core.reporters import ConsoleReporter


def main():
    engine = SABEngine(
        perceptor=SystemPerceptor(),
        brain=GeminiBrain(),
        executor=ConsoleExecutor(),
        reporters=[ConsoleReporter()]
    )
    print("Starting CLI Agent... (Ctrl+C to stop)")
    while True:
        engine.run_once()
        import time
        time.sleep(5)

if __name__ == "__main__":
    main()