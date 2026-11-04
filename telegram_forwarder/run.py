"""
run.py - Auto-restart wrapper for bot.py
Keeps the bot alive by restarting it automatically after any crash or disconnect.
"""
import subprocess
import sys
import time
import os

def main():
    print("=== Bot Auto-Restart Wrapper ===")
    print("The bot will restart automatically if it crashes or loses connection.")
    print("Press Ctrl+C to fully stop.\n")

    restart_count = 0

    while True:
        restart_count += 1
        print(f"--- Starting bot (attempt #{restart_count}) ---")

        try:
            # Run bot.py using the same Python interpreter
            result = subprocess.run(
                [sys.executable, "-u", "bot.py"],
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            exit_code = result.returncode
        except KeyboardInterrupt:
            print("\nStopped by user. Goodbye!")
            break
        except Exception as e:
            print(f"Unexpected error launching bot: {e}")
            exit_code = -1

        print(f"\nBot stopped (exit code: {exit_code}).")

        # Short wait before restarting to avoid hammering Telegram on repeated failures
        wait_seconds = 15
        print(f"Waiting {wait_seconds} seconds before restarting...\n")
        try:
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            print("\nStopped by user. Goodbye!")
            break

if __name__ == "__main__":
    main()
