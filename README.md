# Olympus HLC — RPi5 Yocto Image
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Systems Engineering](https://img.shields.io/badge/Focus-Systems%20Engineering-blue.svg)](#)

Custom Linux image for the **Raspberry Pi 5** built with Yocto (Scarthgap).
Acts as the High-Level Controller (HLC) of the Olympus rover, communicating with
an Arduino Mega 2560 (Low-Level Controller) over UART/USB using the MSM protocol.

## Architecture

```
┌──────────────────────────────────────┐        ┌──────────────────────────────────┐
│  Raspberry Pi 5 (HLC)                │        │  Arduino Mega 2560 (LLC)         │
│                                      │        │                                  │
│  olympus_hlc/ (v3.0)                 │        │  MSM: STB/EXP/AVD/RET/FLT       │
│  ├── HlcEngine (bucle de control)    │        │                                  │
│  ├── VisionSource (YOLOv8n ONNX)     │        │  6 Motors (PWM L298N)            │
│  ├── ManualSource (stdin)            │        │  HC-SR04 D38/D39 (< 200 mm → FAULT) │
│  ├── GCSSource (UDP CSP/CRC-32)      │        │  VL53L0X ToF I2C (< 150 mm → FAULT) │
│  ├── WaypointTracker                 │        │  6 Hall encoders (INT0–INT5)     │
│  ├── EnergyMonitor (4S Li-ion)       │        │                                  │
│  └── OlympusLogger → /var/log/       │        │                                  │
│                                      │        │                                  │
│  rover_bridge.so (Rust/PyO3) ────────┼─ USB ──┼─── USART0 (CDC-ACM 115200 8N1)  │
│  /dev/arduino_mega                   │        │                                  │
│  Cámara CSI IMX219 (CAM0)            │        └──────────────────────────────────┘
└──────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full system overview.

---

## Quick Start

### 1. Clone and set up the environment

```bash
git clone https://github.com/Alonso11/olympus-hlc-rpi5.git
cd olympus-hlc-rpi5
./scripts/setup-env.sh
```

The script automatically clones: poky, meta-raspberrypi, meta-openembedded.

### 2. Build the image

```bash
source layers/poky/oe-init-build-env build
bitbake olympus-image
```

### 3. Flash the microSD

```bash
# Download image from GCP VM
~/deploy-olympus-image.sh

# Flash (requires sudo and bmaptool)
sudo ~/flash-olympus-image.sh
```

See [docs/build-and-deploy.md](docs/build-and-deploy.md) for detailed instructions.

---

## Running the controller

```bash
ssh root@<IP_RPi5>

# Manual mode — send MSM commands from stdin
python3 -m olympus_hlc --mode manual

# Vision mode — obstacle detection via YOLOv8n + CSI camera
python3 -m olympus_hlc --mode vision

# GCS mode — UDP commands from Ground Control Station (CSP/CRC-32, SRS-013)
python3 -m olympus_hlc --mode gcs

# Dry-run (no Arduino required — for testing)
python3 -m olympus_hlc --mode manual --dry-run

# Custom log path
python3 -m olympus_hlc --mode vision --log-path /var/log/olympus/mission.log
```

> The legacy `olympus_controller.py` script (v2.4) is still installed at
> `/usr/bin/olympus_controller.py` for backwards compatibility.

The controller connects to `/dev/arduino_mega` at 115200 baud and manages
the MSM state machine (STB → EXP → AVD/RET → STB). It sends `PING` every 1 s
when idle to keep the Arduino watchdog alive (~2 s timeout → FAULT).

### MSM commands

| Command | Action |
|---------|--------|
| `STB` | Standby — motors stopped |
| `EXP:<l>:<r>` | Explore at speeds 0–100 (e.g. `EXP:80:80`) |
| `AVD:L` / `AVD:R` | Avoidance turn left / right |
| `RET` | Retreat |
| `RST` | Reset → Standby |
| `PING` | Keepalive — resets Arduino watchdog |

---

## What the image includes

| Component | Description |
|-----------|-------------|
| `rover_bridge.so` | Rust/PyO3 module — MSM UART protocol with the Arduino |
| `olympus_hlc/` | HLC package v3.0 (SOLID refactor) — `python3 -m olympus_hlc` |
| `olympus_controller.py` | Legacy HLC controller v2.4 (kept for backwards compat) |
| `olympus_controller.yaml` | Operational config at `/etc/olympus/` (editable without rebuilding) |
| `yolov8n.onnx` | Obstacle detection model (YOLOv8n opset 12, 13 MB) |
| `yolov8n-seg.onnx` | Segmentation model (YOLOv8n-seg opset 12, 14 MB — GNC-REQ-002) |
| `custom-udev-rules` | Stable symlink `/dev/arduino_mega` |
| `wifi-config` | Automatic WiFi connection (wpa_supplicant) |
| `wifi-power-save` | WiFi power saving (systemd oneshot) |
| `resize-rootfs` | rootfs expansion on first boot |
| OpenCV (cv2.dnn) | Computer vision and ONNX inference |
| libcamera | CSI camera support (rpi/pisp pipeline, RPi5) |
| Test scripts | `/usr/bin/test_bridge_interactive.py`, etc. |

---

## Configuration

Operational parameters can be changed on the RPi5 without rebuilding the image:

```bash
nano /etc/olympus/olympus_controller.yaml
```

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ping_interval_s` | 1.0 | PING keepalive interval (s) |
| `tlm_timeout_s` | 5.0 | Link-loss timeout (s) → forces STB |
| `retreat_dist_mm` | 300 | Tactical HLC retreat threshold (mm) |
| `batt_warn_mv` | 14000 | Battery WARN level (3.5 V/cell × 4S) |
| `batt_critical_mv` | 12800 | Battery CRITICAL → force STB (3.2 V/cell × 4S) |
| `vision_conf_min` | 0.5 | Minimum YOLOv8n detection confidence |

---

## Testing on the RPi5

```bash
ssh root@<IP_RPi5>
test_bridge_interactive.py   # Manual MSM command prompt
test_bridge.py               # Automated send/receive test
test_opencv_camera.py        # CSI camera capture + edge detection
test_ultrasonic_rpi.py       # HC-SR04 via RPi5 GPIO (future sensor)
test_rover.py                # Basic rover_bridge smoke test
```

See [docs/testing.md](docs/testing.md) for the full testing guide.

### Live vision debug (SSH pipe)

Stream annotated inference frames from the RPi5 to your PC in real time:

```bash
# On your PC (requires opencv-python, not headless):
pip install opencv-python

# Bbox mode (faster):
ssh root@<IP_RPi5> "python3 /opt/olympus/debug_vision.py --mode bbox" | python3 debug_view.py

# Segmentation mode (shows masks + zone coverage):
ssh root@<IP_RPi5> "python3 /opt/olympus/debug_vision.py --mode seg" | python3 debug_view.py

# Capture N frames only:
ssh root@<IP_RPi5> "python3 /opt/olympus/debug_vision.py --mode seg --frames 20" | python3 debug_view.py
```

`debug_vision.py` runs on the RPi5 and writes length-prefixed JPEGs to stdout.
`debug_view.py` runs locally and displays them with `cv2.imshow`. Press `q` to quit.

The annotated frame shows:
- Vertical zone lines at 33 % / 67 % of frame width (LEFT / CENTER / RIGHT)
- Bounding box of best detection (bbox mode) or green mask overlay (seg mode)
- Zone coverage percentages in the ROI (seg mode)
- Decided MSM command (green = EXP, red = AVD/RET)

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | System overview |
| [docs/rover-bridge.md](docs/rover-bridge.md) | Rust/PyO3 module, API, MSM protocol |
| [docs/yocto-recipes.md](docs/yocto-recipes.md) | meta-olympus recipes and image packages |
| [docs/testing.md](docs/testing.md) | How to test each component |
| [docs/build-and-deploy.md](docs/build-and-deploy.md) | Build and flash the image |
| [docs/decision-log.md](docs/decision-log.md) | Chronological design decision log |

---

## License

This project is distributed under the MIT License. See the LICENSE file for details.

---

## Author

Fabián Alonso Gómez Quesada     
Instituto Tecnológico de Costa Rica (TEC)        
School of Electronics Engineering           
SETEC Lab – Space Systems Laboratory     
