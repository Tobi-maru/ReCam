import subprocess
import os


class adbManager:
    def __init__(self):
        self.process = None

    def check_adb(self):
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        return len(lines) >1

    def start_stream(self, device_path):
        cmd = [
            "scrcpy",
            "--video-source=camera",
            "--camera-facing=back",
            "--video-codec=h265",
            "--camera-size=1920x1080",
            "--capture-orientation=0",
            f"--v4l2-sink={device_path}",
            "--no-playback",
            # "--turn-screen-off"
        ]


        curr_env = os.environ.copy()

        self.process = subprocess.Popen(
            cmd,
            env=curr_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        return self.process

    def stop_stream(self):
        if self.process:
            self.process.terminate()
            self.process=None