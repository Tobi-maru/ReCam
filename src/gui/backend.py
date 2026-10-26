"""QObject backend bridging the ReCam engine (adb/v4l2 managers) to the QML UI.

Threading model:
- PollingWorker (QThread) owns adbManager/v4l2Manager and performs every
  subprocess call, so the GUI thread never blocks.
- The GUI thread controls the worker through mutex-guarded request flags;
  a QWaitCondition wakes the loop early instead of sleeping a full tick.
- Worker results reach the GUI thread via queued signal connections.
"""

import os
import sys
import time

from PySide6.QtCore import (
    QObject,
    QThread,
    Property,
    Signal,
    Slot,
    QMutex,
    QMutexLocker,
    QWaitCondition,
    QStringListModel,
)

# Make src/ importable whether this runs as a script or a module.
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from adb_services import adbManager
from v4l2 import v4l2Manager
import settings as recam_settings


class PollingWorker(QThread):
    """Port of the main.py 1-second polling loop, runnable off the GUI thread."""

    logLine = Signal(str)
    phoneStatusChanged = Signal(str)
    streamActiveChanged = Signal(bool)
    streamEnded = Signal()
    deviceInfoChanged = Signal(bool, str, bool)  # ready, label, busy
    notify = Signal(str, str)  # title, body

    TICK_MS = 1000
    SLOW_EVERY = 5  # slow device checks run every Nth tick

    def __init__(self, device_path, settings, parent=None):
        super().__init__(parent)
        self.adb = adbManager()
        self.v4l2 = v4l2Manager(device_path)
        self.device_path = device_path

        self._settings = dict(settings)
        self._auto_start = settings.get("auto_start_stream", True)
        self._want_start = False
        self._want_stop = False
        self._quit = False

        self._mutex = QMutex()
        self._cond = QWaitCondition()

        self._waiting_for_auth = False
        self._last_phone_status = None
        self._was_streaming = False
        self._fuser_missing_logged = False

    # --- thread-safe control surface (called from the GUI thread) ---

    def request_start(self):
        with QMutexLocker(self._mutex):
            self._want_start = True
            self._cond.wakeAll()

    def request_stop(self):
        with QMutexLocker(self._mutex):
            self._want_stop = True
            self._cond.wakeAll()

    def request_restart(self):
        with QMutexLocker(self._mutex):
            self._want_stop = True
            self._want_start = True
            self._cond.wakeAll()

    def update_settings(self, settings):
        with QMutexLocker(self._mutex):
            self._settings = dict(settings)
            self._auto_start = settings.get("auto_start_stream", self._auto_start)
            self._cond.wakeAll()

    def shutdown(self):
        with QMutexLocker(self._mutex):
            self._quit = True
            self._cond.wakeAll()

    # --- worker side ---

    def _is_streaming(self):
        return self.adb.process is not None and self.adb.process.poll() is None

    def _emit_liveness(self):
        streaming = self._is_streaming()
        if streaming != self._was_streaming:
            self._was_streaming = streaming
            self.streamActiveChanged.emit(streaming)

    def _emit_phone(self, status):
        if status != self._last_phone_status:
            self._last_phone_status = status
            self.phoneStatusChanged.emit(status)

    def _check_busy(self):
        try:
            return self.v4l2.is_busy()
        except FileNotFoundError:
            if not self._fuser_missing_logged:
                self._fuser_missing_logged = True
                self.logLine.emit(
                    "NOTE: 'fuser' not found — 'in use' indicator disabled."
                )
            return False

    def _startup_check(self, settings, auto_start):
        """Mirror of main.py's startup block."""
        phone = self.adb.get_adb_status()
        self._emit_phone(phone)

        if not auto_start:
            return
        if phone == "authorized":
            self.logLine.emit("Phone already connected and authorized. Starting stream...")
            self.adb.start_stream(self.device_path, settings)
            self._emit_liveness()
        elif phone == "unauthorized":
            self.logLine.emit("Phone connected but NOT authorized. Please check your phone screen.")
            self._waiting_for_auth = True
        elif phone == "no_device":
            self.logLine.emit("No phone detected. Waiting for phone connection...")
        else:
            self.logLine.emit(f"Unknown ADB status: {phone}. Waiting for phone connection...")

    def run(self):
        self.logLine.emit("--- ReCam Engine: Active ---")
        with QMutexLocker(self._mutex):
            settings = dict(self._settings)
            auto_start = self._auto_start
        self._startup_check(settings, auto_start)

        tick = 0
        while True:
            # Snapshot and consume control flags in one critical section so a
            # request arriving mid-snapshot can never be cleared unprocessed.
            with QMutexLocker(self._mutex):
                if self._quit:
                    break
                settings = dict(self._settings)
                auto_start = self._auto_start
                want_start = self._want_start
                want_stop = self._want_stop
                self._want_start = False
                self._want_stop = False

            # --- 1. Liveness ---
            self._emit_liveness()

            # --- 2. Consume the udev hot-plug flag file ---
            has_event = self.adb.check_for_event()

            phone = self.adb.get_adb_status()
            self._emit_phone(phone)

            # --- 3. Manual controls from the GUI ---
            if want_stop and self.adb.process is not None:
                self.logLine.emit("[Manual] Stopping stream...")
                self.adb.stop_stream()
                if want_start:
                    time.sleep(0.5)  # let the old scrcpy release the sink
                self._emit_liveness()

            if want_start and self.adb.process is None:
                if phone == "authorized":
                    self.logLine.emit("[Manual] Starting stream...")
                    self.adb.start_stream(self.device_path, settings)
                    self._emit_liveness()
                else:
                    reason = {
                        "no_device": "no phone connected",
                        "unauthorized": "phone not ADB-authorized (check your phone screen)",
                    }.get(phone, f"phone not ready (status: {phone})")
                    self.logLine.emit(f"[Manual] Cannot start stream: {reason}.")
                    self.notify.emit("ReCam", f"Cannot start stream: {reason}.")

            # --- 4. Auto-start on events / authorization retries ---
            streaming = self._is_streaming()
            if (
                auto_start
                and not streaming
                and (has_event or self._waiting_for_auth)
            ):
                if phone == "authorized":
                    if has_event:
                        self.logLine.emit("[Hardware Event] Phone detected via USB.")
                    self.logLine.emit("ADB Authorized. Starting stream...")
                    self.adb.start_stream(self.device_path, settings)
                    self._waiting_for_auth = False
                    self._emit_liveness()

                elif phone == "unauthorized":
                    if has_event or not self._waiting_for_auth:
                        self.logLine.emit("[Hardware Event] Phone detected via USB.")
                        self.logLine.emit("Waiting for ADB authorization... Please check your phone screen.")
                        self.notify.emit("ReCam", "Check your phone and accept the USB debugging prompt.")
                    self._waiting_for_auth = True

                elif phone == "no_device":
                    if has_event:
                        self.logLine.emit("[Hardware Event] Phone detected via USB.")
                        self.logLine.emit(
                            "ERROR: ADB cannot see the phone. Ensure USB Debugging is ON "
                            "and USB mode is File Transfer/PTP."
                        )
                    self._waiting_for_auth = False
                else:
                    if has_event:
                        self.logLine.emit(f"ERROR: Phone not ready (status: {phone}).")
                    self._waiting_for_auth = False

            # --- 5. Process exit detection ---
            proc = self.adb.process
            if proc is not None and proc.poll() is not None:
                self.logLine.emit(f"[Stream Ended] scrcpy exited (code {proc.returncode}).")
                self.adb.stop_stream()
                self.notify.emit("ReCam", "Stream ended — waiting for reconnection.")
                self.streamEnded.emit()
                self._emit_liveness()

            # --- 6. Slow device checks (every Nth tick) ---
            if tick % self.SLOW_EVERY == 0:
                ready = self.v4l2.ping()
                label = self.v4l2.get_device_label()
                busy = self._check_busy()
                self.deviceInfoChanged.emit(ready, label, busy)
            tick += 1

            # --- 7. Sleep, but wake early on new control requests ---
            with QMutexLocker(self._mutex):
                if self._quit or self._want_start or self._want_stop:
                    continue
                self._cond.wait(self._mutex, self.TICK_MS)

        self.adb.stop_stream()


class LogCollector(QObject):
    """Timestamped, capped log shown in the QML log view."""

    MAX_LINES = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStringListModel([])
        self._lines = []

    @Slot(str)
    def append(self, line):
        self._lines.append(f"[{time.strftime('%H:%M:%S')}] {line}")
        if len(self._lines) > self.MAX_LINES:
            self._lines = self._lines[-self.MAX_LINES:]
        self._model.setStringList(self._lines)

    def _get_model(self):
        return self._model

    logModel = Property("QVariant", fget=_get_model, constant=True)


class ReCamBackend(QObject):
    """Everything the QML dashboard binds to."""

    # Notify signals
    phoneStatusChanged = Signal()
    streamActiveChanged = Signal()
    deviceReadyChanged = Signal()
    deviceBusyChanged = Signal()
    deviceLabelChanged = Signal()
    previewEnabledChanged = Signal()
    fatalChanged = Signal()
    cameraFacingChanged = Signal()
    cameraSizeChanged = Signal()
    videoCodecChanged = Signal()
    captureOrientationChanged = Signal()
    turnScreenOffChanged = Signal()
    autoStartChanged = Signal()

    # Forwarded to the tray
    notify = Signal(str, str)
    streamEndedSignal = Signal()

    def __init__(self, settings_path, parent=None):
        super().__init__(parent)
        self._settings_path = settings_path
        self._settings = recam_settings.load(settings_path)

        self._phone_status = "unknown"
        self._stream_active = False
        self._device_ready = False
        self._device_busy = False
        self._device_label = "ReCam"
        self._fatal = ""

        self.log = LogCollector(self)

        probe = v4l2Manager(self._settings["device_path"])
        if not probe.check_placeholder():
            self._fatal = (
                f"Virtual camera {self._settings['device_path']} not found.\n\n"
                "Please run:\n    sudo ./scripts/install.sh"
            )
        else:
            self._device_ready = True

        self.worker = None
        if not self._fatal:
            self.worker = PollingWorker(self._settings["device_path"], self._settings)
            self.worker.logLine.connect(self.log.append)
            self.worker.phoneStatusChanged.connect(self._on_phone_status)
            self.worker.streamActiveChanged.connect(self._on_stream_active)
            self.worker.deviceInfoChanged.connect(self._on_device_info)
            self.worker.notify.connect(self.notify)
            self.worker.streamEnded.connect(self.streamEndedSignal)
            self.worker.start()

    # --- worker → GUI-thread property updates ---

    def _on_phone_status(self, status):
        if status != self._phone_status:
            self._phone_status = status
            self.phoneStatusChanged.emit()

    def _on_stream_active(self, active):
        if active != self._stream_active:
            self._stream_active = active
            self.streamActiveChanged.emit()

    def _on_device_info(self, ready, label, busy):
        if ready != self._device_ready:
            self._device_ready = ready
            self.deviceReadyChanged.emit()
        if label != self._device_label:
            self._device_label = label
            self.deviceLabelChanged.emit()
        if busy != self._device_busy:
            self._device_busy = busy
            self.deviceBusyChanged.emit()

    # --- read-only properties ---

    def _get_phone_status(self):
        return self._phone_status

    phoneStatus = Property(str, fget=_get_phone_status, notify=phoneStatusChanged)

    def _get_stream_active(self):
        return self._stream_active

    streamActive = Property(bool, fget=_get_stream_active, notify=streamActiveChanged)

    def _get_device_ready(self):
        return self._device_ready

    deviceReady = Property(bool, fget=_get_device_ready, notify=deviceReadyChanged)

    def _get_device_busy(self):
        return self._device_busy

    deviceBusy = Property(bool, fget=_get_device_busy, notify=deviceBusyChanged)

    def _get_device_label(self):
        return self._device_label

    deviceLabel = Property(str, fget=_get_device_label, notify=deviceLabelChanged)

    def _get_device_path(self):
        return self._settings["device_path"]

    devicePath = Property(str, fget=_get_device_path, constant=True)

    def _get_fatal(self):
        return self._fatal

    fatalMessage = Property(str, fget=_get_fatal, notify=fatalChanged)

    # --- read-write properties (persisted on applySettings) ---

    def _get_camera_facing(self):
        return self._settings["camera_facing"]

    def _set_camera_facing(self, value):
        if value != self._settings["camera_facing"]:
            self._settings["camera_facing"] = value
            self.cameraFacingChanged.emit()

    cameraFacing = Property(str, fget=_get_camera_facing, fset=_set_camera_facing,
                            notify=cameraFacingChanged)

    def _get_camera_size(self):
        return self._settings["camera_size"]

    def _set_camera_size(self, value):
        if value != self._settings["camera_size"]:
            self._settings["camera_size"] = value
            self.cameraSizeChanged.emit()

    cameraSize = Property(str, fget=_get_camera_size, fset=_set_camera_size,
                          notify=cameraSizeChanged)

    def _get_video_codec(self):
        return self._settings["video_codec"]

    def _set_video_codec(self, value):
        if value != self._settings["video_codec"]:
            self._settings["video_codec"] = value
            self.videoCodecChanged.emit()

    videoCodec = Property(str, fget=_get_video_codec, fset=_set_video_codec,
                          notify=videoCodecChanged)

    def _get_capture_orientation(self):
        return self._settings["capture_orientation"]

    def _set_capture_orientation(self, value):
        if int(value) != self._settings["capture_orientation"]:
            self._settings["capture_orientation"] = int(value)
            self.captureOrientationChanged.emit()

    captureOrientation = Property(int, fget=_get_capture_orientation,
                                  fset=_set_capture_orientation,
                                  notify=captureOrientationChanged)

    def _get_turn_screen_off(self):
        return self._settings["turn_screen_off"]

    def _set_turn_screen_off(self, value):
        if bool(value) != self._settings["turn_screen_off"]:
            self._settings["turn_screen_off"] = bool(value)
            self.turnScreenOffChanged.emit()

    turnScreenOff = Property(bool, fget=_get_turn_screen_off,
                             fset=_set_turn_screen_off,
                             notify=turnScreenOffChanged)

    def _get_auto_start(self):
        return self._settings["auto_start_stream"]

    def _set_auto_start(self, value):
        if bool(value) != self._settings["auto_start_stream"]:
            self._settings["auto_start_stream"] = bool(value)
            self.autoStartChanged.emit()

    autoStart = Property(bool, fget=_get_auto_start, fset=_set_auto_start,
                         notify=autoStartChanged)

    # --- preview toggle: persisted immediately ---

    def _get_preview_enabled(self):
        return self._settings["preview_enabled"]

    def _set_preview_enabled(self, value):
        value = bool(value)
        if value != self._settings["preview_enabled"]:
            self._settings["preview_enabled"] = value
            recam_settings.save(self._settings, self._settings_path)
            self.previewEnabledChanged.emit()

    previewEnabled = Property(bool, fget=_get_preview_enabled,
                              fset=_set_preview_enabled,
                              notify=previewEnabledChanged)

    def _get_log_model(self):
        return self.log._model

    logModel = Property("QVariant", fget=_get_log_model, constant=True)

    # --- slots called from QML ---

    @Slot()
    def startStream(self):
        if self.worker is not None:
            self.worker.request_start()

    @Slot()
    def stopStream(self):
        if self.worker is not None:
            self.worker.request_stop()

    @Slot()
    def applySettings(self):
        recam_settings.save(self._settings, self._settings_path)
        if self.worker is not None:
            self.worker.update_settings(self._settings)
            restarting = self._stream_active
            if restarting:
                self.worker.request_restart()
            self.log.append(
                "Settings applied" + (" — restarting stream." if restarting else ".")
            )

    @Slot()
    def restartWithDefaults(self):
        device_path = self._settings["device_path"]
        self._settings = dict(recam_settings.DEFAULTS)
        self._settings["device_path"] = device_path  # keep the system's configured sink
        recam_settings.save(self._settings, self._settings_path)
        for sig in (self.cameraFacingChanged, self.cameraSizeChanged,
                    self.videoCodecChanged, self.captureOrientationChanged,
                    self.turnScreenOffChanged, self.autoStartChanged):
            sig.emit()
        self.applySettings()
        self.log.append("Settings reset to defaults.")

    # --- lifecycle ---

    def shutdown(self):
        if self.worker is not None:
            self.worker.shutdown()
            if not self.worker.wait(5000):
                self.worker.terminate()
                self.worker.wait(2000)
                if self.worker.adb.process is not None:
                    self.worker.adb.stop_stream()
