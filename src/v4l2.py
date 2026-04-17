import os 

class v4l2Manager :
    def __init__(self, device_path="/dev/video9"):
        self.path = device_path

    def ping(self):
        return os.path.exists(self.path)

    def get_info(self):
        return self.path
        