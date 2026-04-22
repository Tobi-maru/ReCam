from adb_services import adbManager
from v4l2 import v4l2Manager
import time
import sys

def main():
    v4l2 = v4l2Manager()
    adb = adbManager()

    print("--- ReCam Dev Boot ---")

    print("--- ReCam Engine: Active ---")

    # 1. Pre-flight Check: Is the placeholder ready?
    if not v4l2.check_placeholder():
        print("ERROR: /dev/video9 placeholder not found.")
        print("Please run: sudo ./install.sh")
        sys.exit(1)

    print(f"Placeholder /dev/video9 is active ({v4l2.get_device_label()})")

    # --- Startup Check: Detect an already-connected device ---
    print("Checking for already-connected device...")
    startup_status = adb.get_adb_status()
    waiting_for_auth = False

    if startup_status == "authorized":
        print("Phone already connected and authorized. Starting stream...")
        adb.start_stream(v4l2.device_path)
    elif startup_status == "unauthorized":
        print("Phone connected but NOT authorized. Please check your phone screen.")
        waiting_for_auth = True
    elif startup_status == "no_device":
        print("No phone detected. Waiting for phone connection...")
    else:
        print(f"Unknown ADB status: {startup_status}. Waiting for phone connection...")

    try:
        while True:
            # Check if a process is ALREADY running
            is_streaming = adb.process is not None and adb.process.poll() is None

            has_event = adb.check_for_event()

            # 2. Event Detection: Look for events or retry authorization if we AREN'T streaming
            if not is_streaming and (has_event or waiting_for_auth):
                status = adb.get_adb_status()
                
                if status == "authorized":
                    if has_event: print("\n[Hardware Event] Phone detected via USB.")
                    print("ADB Authorized. Starting stream...")
                    adb.start_stream(v4l2.device_path)
                    waiting_for_auth = False
                    
                elif status == "unauthorized":
                    if has_event or not waiting_for_auth:
                        print("\n[Hardware Event] Phone detected via USB.")
                        print("Waiting for ADB authorization... Please check your phone screen.")
                    waiting_for_auth = True
                    
                elif status == "no_device":
                    if has_event:
                        print("\n[Hardware Event] Phone detected via USB.")
                        print("ERROR: ADB cannot see the phone. Ensure USB Debugging is ON and USB mode is File Transfer/PTP.")
                    waiting_for_auth = False
                else:
                    if has_event:
                        print(f"ERROR: Phone not ready (status: {status}).")
                    waiting_for_auth = False

            # 3. Process Monitoring: If it WAS running but just stopped
            if adb.process is not None and adb.process.poll() is not None:
                print("\n[Stream Ended] Process exited.")
                adb.stop_stream()
                adb.process = None # Reset the handle!
                print("Waiting for re-connection...")

            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nEngine stopped by user.")
    
    finally :
        adb.stop_stream()
        print("Stream stopped safely.")

if __name__ == "__main__":
    main()