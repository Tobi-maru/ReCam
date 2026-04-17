from adb_services import adbManager
from v4l2 import v4l2Manager
import time

def main():
    v4l2 = v4l2Manager()
    adb = adbManager()

    print("--- ReCam Dev Boot ---")

    if not v4l2.ping():
        print("Error: /dev/video9 not found. Did you run modprobe?")
        return

    if not adb.check_adb():
        print("Error: No phone detected via ADB.")
        return

    print("Starting stream... Press Ctrl+C to stop.")
    try:
        adb.start_stream(v4l2.get_info())
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        adb.stop_stream()
        print("\nStream stopped safely.")

if __name__ == "__main__":
    main()