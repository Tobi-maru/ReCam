import os 
import subprocess

class v4l2Manager :
    def __init__(self, device_path="/dev/video9"):
        self.device_path = device_path

    def check_placeholder(self):
        if (os.path.exists(self.device_path)):
            return True
        return False

    def get_device_label(self):
        try:
            cmd = ["v4l2-ctl", "-d", self.device_path, "--info"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if "ReCam" in result.stdout:
                return "ReCam"
        except FileNotFoundError:
            return "Unknown (v4l2-ctl missing)"
        return "Unknown Device"


    def is_busy(self):
        cmd = ["fuser", self.device_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def ping(self):
        return os.path.exists(self.device_path)

    def get_info(self):
        return self.device_path
        