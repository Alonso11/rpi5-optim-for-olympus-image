# Olympus HLC — RPi5 Yocto Image

Custom Linux image for the **Raspberry Pi 5** built with Yocto (Scarthgap).
Acts as the High-Level Controller (HLC) of the Olympus rover, communicating with
an Arduino Mega 2560 (Low-Level Controller) over UART/USB.

## Architecture

```
RPi5 (HLC — this image)            Arduino Mega 2560 (LLC)
rover_bridge.so (Rust/PyO3) ──USB──► CommandInterface (USART0)
/dev/arduino_mega                      Motors + Sensors
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

## What the image includes

| Component | Description |
|-----------|-------------|
| `rover_bridge.so` | Rust/PyO3 module — UART serial + HC-SR04 GPIO |
| `olympus_controller.py` | Main HLC controller v1.7 (manual + vision modes) |
| `olympus_controller.yaml` | Operational config at `/etc/olympus/` (editable without rebuilding) |
| `yolov8n.onnx` | Obstacle detection model (YOLOv8n opset 12, 13 MB) |
| `custom-udev-rules` | Stable symlink `/dev/arduino_mega` |
| `wifi-config` | Automatic WiFi connection (wpa_supplicant) |
| `wifi-power-save` | WiFi power saving (systemd oneshot) |
| `resize-rootfs` | rootfs expansion on first boot |
| OpenCV (cv2.dnn) | Computer vision and ONNX inference |
| libcamera | CSI camera support (rpi/pisp pipeline, RPi5) |
| Test scripts | `/usr/bin/test_bridge_interactive.py`, etc. |

---

## Arduino communication

```python
import rover_bridge

rover = rover_bridge.Rover("/dev/arduino_mega", 115200)
rover.send_command("F")   # Forward
rover.send_command("S")   # Stop
```

See [docs/rover-bridge.md](docs/rover-bridge.md) for the full API.

---

## Testing on the RPi5

```bash
ssh root@<IP_RPi5>
test_bridge_interactive.py   # Manual interactive control
test_ultrasonic_rpi.py       # HC-SR04 sensor
test_opencv_camera.py        # CSI camera
```

See [docs/testing.md](docs/testing.md) for the full testing guide.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | System overview |
| [docs/rover-bridge.md](docs/rover-bridge.md) | Rust/PyO3 module, API, protocol |
| [docs/yocto-recipes.md](docs/yocto-recipes.md) | meta-olympus recipes and image packages |
| [docs/testing.md](docs/testing.md) | How to test each component |
| [docs/build-and-deploy.md](docs/build-and-deploy.md) | Build and flash the image |
| [docs/decision-log.md](docs/decision-log.md) | Chronological design decision log |

---

Olympus TFG Project 2026.
