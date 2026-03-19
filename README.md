# Olympus HLC — RPi5 Yocto Image

Imagen Linux personalizada para la **Raspberry Pi 5** construida con Yocto (scarthgap).
Actúa como High-Level Controller (HLC) del rover Olympus, comunicándose con un
Arduino Mega 2560 (Low-Level Controller) via UART/USB.

## Arquitectura

```
RPi5 (HLC — esta imagen)          Arduino Mega 2560 (LLC)
rover_bridge.so (Rust/PyO3) ──USB──► CommandInterface (USART0)
/dev/arduino_mega                     Motores + Sensores
```

Ver [docs/architecture.md](docs/architecture.md) para el detalle completo.

---

## Inicio Rápido

### 1. Clonar y preparar el entorno

```bash
git clone https://github.com/Alonso11/olympus-hlc-rpi5.git
cd olympus-hlc-rpi5
./scripts/setup-env.sh
```

El script clona automáticamente: poky, meta-raspberrypi, meta-openembedded,
meta-tensorflow-lite y meta-onnxruntime.

### 2. Compilar la imagen

```bash
source layers/poky/oe-init-build-env build
bitbake olympus-image
```

### 3. Flashear la microSD

```bash
# Descargar imagen desde VM GCP
~/deploy-olympus-image.sh

# Flashear (requiere sudo y bmaptool)
sudo ~/flash-olympus-image.sh
```

Ver [docs/build-and-deploy.md](docs/build-and-deploy.md) para instrucciones detalladas.

---

## Qué incluye la imagen

| Componente | Descripción |
|------------|-------------|
| `rover_bridge.so` | Módulo Rust/PyO3 — serial UART + GPIO HC-SR04 |
| `custom-udev-rules` | Symlink estable `/dev/arduino_mega` |
| `wifi-config` | Conexión WiFi automática (wpa_supplicant) |
| `wifi-power-save` | Ahorro energía WiFi (systemd oneshot) |
| `resize-rootfs` | Expansión rootfs en primer arranque |
| OpenCV, TFLite, ONNX | Visión por computadora e inferencia ML |
| libcamera | Soporte cámara CSI |
| Scripts de test | `/usr/bin/test_bridge_interactive.py`, etc. |

---

## Comunicación con el Arduino

```python
import rover_bridge

rover = rover_bridge.Rover("/dev/arduino_mega", 115200)
rover.send_command("F")   # Avanzar
rover.send_command("S")   # Parar
```

Ver [docs/rover-bridge.md](docs/rover-bridge.md) para la API completa.

---

## Testing en la RPi5

```bash
ssh root@<IP_RPi5>
test_bridge_interactive.py   # Control manual interactivo
test_ultrasonic_rpi.py       # Sensor HC-SR04
test_opencv_camera.py        # Cámara CSI
```

Ver [docs/testing.md](docs/testing.md) para la guía completa de pruebas.

---

## Documentación

| Doc | Descripción |
|-----|-------------|
| [docs/architecture.md](docs/architecture.md) | Visión general del sistema |
| [docs/rover-bridge.md](docs/rover-bridge.md) | Módulo Rust/PyO3, API, protocolo |
| [docs/testing.md](docs/testing.md) | Cómo probar cada componente |
| [docs/build-and-deploy.md](docs/build-and-deploy.md) | Compilar y flashear la imagen |

---

Proyecto TFG Olympus 2026.
