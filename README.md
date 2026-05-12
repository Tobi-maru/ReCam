
# ReCam

Repurposing old android phones as webcams using scrcpy and v4l2loopback module.

## Quick Start

1. **Install dependencies and system services:**
   ```bash
   sudo ./scripts/install.sh
   ```

2. **Start the engine:**
   ```bash
   recam
   ```

## Manual Start (without installing launcher)

```bash
python3 src/main.py
```

## Project Structure

- `src/main.py` — Main engine that monitors ADB devices and starts scrcpy
- `src/adb_services.py` — ADB interaction and stream management
- `src/v4l2.py` — v4l2loopback device management
- `scripts/install.sh` — System installation script
- `deploy/` — Systemd services and udev rules
- `config/default.json` — Configuration file
