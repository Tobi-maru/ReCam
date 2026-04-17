import subprocess


class adbManager:
    def __init__(self):
        self.process = None

    def check_adb(self):
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        return len(lines) >1

    def start_stream(self,device_path):
        cmd =["scrcpy",
        "--video-source=camera",
        f"--v4l2-sink={device_path}",
        "--no-playback",
        "--turn-screen-off",
        "--camera-size=1920x1080"]

        self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.process

    def stop_stream(self):
        if self.process:
            self.process.terminate()
            self.process=None