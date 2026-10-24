import subprocess
import os


class adbManager:
    def __init__(self):
        self.process = None
        self.flag_path = "/tmp/recam_phone_status"


    def check_for_event(self):
            """
            Reads the flag file. If it has content, it resets it 
            and returns True. This avoids the 'Permission Denied' 
            error on os.remove().
            """
            if os.path.exists(self.flag_path):

                if os.path.getsize(self.flag_path) > 0:
                    try:

                        with open(self.flag_path, 'w') as f:
                            pass 
                        return True
                    except PermissionError:

                        print("CRITICAL: Python lacks write permission for the flag file.")
                        return False
            return False

    def get_adb_status(self):
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) <= 1:
            return "no_device"
        if "unauthorized" in lines[1]:
            return "unauthorized"
        if "device" in lines[1]:
            return "authorized"
        return "unknown"

    
    def check_adb(self):
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        return len(lines) >1

    def start_stream(self, device_path, settings=None):
        s = settings or {}
        cmd = [
            "scrcpy",
            "--video-source=camera",
            f"--camera-facing={s.get('camera_facing', 'back')}",
            f"--video-codec={s.get('video_codec', 'h265')}",
            f"--camera-size={s.get('camera_size', '1920x1080')}",
            f"--capture-orientation={s.get('capture_orientation', 0)}",
            f"--v4l2-sink={device_path}",
            "--no-playback",
            "--no-window",
            "--no-control",
            "--no-audio",
        ]

        if s.get("turn_screen_off", False):
            cmd.append("--turn-screen-off")


        curr_env = os.environ.copy()

        # Let the logs print to the terminal so we can see why it exits
        self.process = subprocess.Popen(
            cmd,
            env=curr_env,
            text=True
        )
        return self.process

    def stop_stream(self):
        if self.process:
            self.process.terminate()
            self.process=None