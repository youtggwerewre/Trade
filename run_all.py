"""
Runs signal_bot.py and news_bot.py together in one terminal.

- Restarts either bot automatically if it crashes.
- If a bot fails 3 times quickly in a row (within 10s each time), stops
  retrying it and prints a message instead of looping forever — that
  pattern almost always means a bad .env value, not a transient error.
- Ctrl+C stops both cleanly.
"""
import subprocess
import sys
import time
import signal

BOTS = ["signal_bot.py", "news_bot.py"]
MAX_QUICK_FAILS = 3
QUICK_FAIL_WINDOW = 10  # seconds


def start(bot):
    print(f"[{bot}] starting…")
    return subprocess.Popen([sys.executable, bot])


def main():
    procs = {bot: start(bot) for bot in BOTS}
    start_times = {bot: time.time() for bot in BOTS}
    fail_counts = {bot: 0 for bot in BOTS}
    dead = set()

    def shutdown(*_):
        print("\nStopping all bots…")
        for bot, p in procs.items():
            if p.poll() is None:
                p.terminate()
        for p in procs.values():
            p.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(2)
            for bot in BOTS:
                if bot in dead:
                    continue
                p = procs[bot]
                ret = p.poll()
                if ret is None:
                    continue  # still running fine

                ran_for = time.time() - start_times[bot]
                print(f"[{bot}] exited (code {ret}) after {ran_for:.0f}s")

                fail_counts[bot] = fail_counts[bot] + 1 if ran_for < QUICK_FAIL_WINDOW else 0

                if fail_counts[bot] >= MAX_QUICK_FAILS:
                    print(f"[{bot}] failed {MAX_QUICK_FAILS}x quickly in a row — not restarting. "
                          f"Check its .env values / the error output above.")
                    dead.add(bot)
                    continue

                print(f"[{bot}] restarting in 5s…")
                time.sleep(5)
                procs[bot] = start(bot)
                start_times[bot] = time.time()

            if len(dead) == len(BOTS):
                print("All bots stopped. Exiting.")
                break
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
