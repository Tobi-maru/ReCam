# ReCam

ReCam repurposes old Android phones as webcams on Linux by combining:

- [`scrcpy`](https://github.com/Genymobile/scrcpy) to read the Android camera stream through ADB
- [`v4l2loopback`](https://github.com/umlaeute/v4l2loopback) to expose that stream as a virtual webcam device (default: `/dev/video9`)

The repository is primarily Python (65.1%) with Shell scripts (34.9%) for system setup and launch.

## Main Features

- Turn an Android phone into a reusable USB webcam source
- Automatic dependency and system setup via `scripts/install.sh`
- Creates and manages a persistent `v4l2loopback` virtual camera (`ReCam`)
- Includes a launcher command (`recam`) with prerequisite checks
- Monitors ADB device connection/auth status and starts streaming automatically

## Requirements / Dependencies

### System and OS

- Linux system with Bash and `systemd`/`udev` support
- Kernel support for `v4l2loopback`

### Runtime dependencies

- Python 3
- `scrcpy`
- `adb` (Android Debug Bridge)
- `v4l2loopback` module (`v4l2loopback-dkms` on some distros)
- `v4l-utils` (`v4l2-ctl`)

### Android device requirements

- Android phone with a working camera
- USB debugging enabled (`Developer options`)
- USB authorization accepted when prompted (`Allow USB debugging`)
- USB cable (stable data cable recommended)

## Setup

### 1) Clone the repository

```bash
git clone https://github.com/Tobi-maru/ReCam.git
cd ReCam
```

### 2) Install dependencies and services (recommended)

Run the installer as root:

```bash
sudo ./scripts/install.sh
```

What it configures:

1. Installs required packages (`scrcpy`, `adb`, `v4l2loopback`, `v4l-utils`, `python3`)
2. Installs udev trigger files (`deploy/ReCam.rules`, `deploy/ReCam-map-triggers.sh`)
3. Installs/enables `recam-loopback.service` to load `v4l2loopback`
4. Verifies `/dev/video9` exists
5. Installs launcher command as `/usr/local/bin/recam`

### 3) Manual dependency setup (if needed)

If you prefer manual setup, install equivalent packages for your distro and load the module:

```bash
sudo modprobe v4l2loopback devices=1 video_nr=9 card_label="ReCam" exclusive_caps=1
```

Verify the virtual webcam exists:

```bash
v4l2-ctl -d /dev/video9 --info
```

### 4) Prepare and connect the phone

1. Enable **Developer options** on Android
2. Enable **USB debugging**
3. Connect phone via USB
4. Approve ADB authorization prompt on phone
5. Verify device visibility:

```bash
adb devices
```

You should see your device listed as `device` (not `unauthorized`).

## Usage

### Start ReCam (recommended)

```bash
recam
```

The launcher checks `python3`, `adb`, `scrcpy`, and `v4l2-ctl`, ensures `/dev/video9` is available, then runs the engine.

### Start without installing launcher

```bash
python3 src/main.py
```

### Use the virtual webcam in apps

In OBS/Discord/Meet/Zoom (Linux clients), select video device:

- `/dev/video9`
- or camera label containing `ReCam`

## Troubleshooting

- **`/dev/video9` not found**
  - Re-run: `sudo ./scripts/install.sh`
  - Or load manually: `sudo modprobe v4l2loopback devices=1 video_nr=9 card_label="ReCam" exclusive_caps=1`

- **ADB shows `unauthorized`**
  - Unlock phone screen
  - Reconnect USB cable
  - Accept USB debugging prompt
  - Retry `adb devices`

- **`scrcpy`/`adb` command missing**
  - Install dependencies, then restart shell/session

- **Camera device not visible in app**
  - Confirm stream is running in terminal
  - Check with `v4l2-ctl -d /dev/video9 --info`
  - Restart the target app after ReCam is started

## Project Structure

- `src/main.py` — Main engine loop and startup checks
- `src/adb_services.py` — ADB status detection and scrcpy stream launch
- `src/v4l2.py` — Virtual camera checks and metadata helpers
- `scripts/install.sh` — Installer for dependencies/services/launcher
- `deploy/` — udev trigger script, udev rules, and loopback systemd service
- `recam` — User-facing launcher command

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a focused feature/fix branch
3. Keep changes minimal and scoped
4. Test your changes locally
5. Open a pull request with clear description and reproduction/validation steps

Please include logs/screenshots when reporting device/driver issues.

## License

This repository currently does **not** include a `LICENSE` file. Until a license is added by the maintainers, usage, modification, and redistribution are not granted by default (all rights reserved).

## Acknowledgements

- [`scrcpy`](https://github.com/Genymobile/scrcpy) for Android device streaming/control
- [`v4l2loopback`](https://github.com/umlaeute/v4l2loopback) for Linux virtual camera devices
