# Recetas Yocto — meta-olympus

Referencia de todas las recetas de la capa `meta-olympus` y los paquetes de upstream
que componen la imagen `olympus-image`.

---

## Árbol de dependencias (simplificado)

```
olympus-image (v1.5)
├── custom-udev-rules          → /etc/udev/rules.d/99-arduino.rules
├── resize-rootfs              → servicio systemd primer arranque
├── wifi-config                → wpa_supplicant + credenciales WiFi
├── wifi-power-save            → power save chip WiFi (systemd)
├── python3-rover-bridge       → HLC completo (Python + Rust + modelos ONNX)
│   ├── rover_bridge.so        (extensión PyO3/Rust — protocolo MSM)
│   ├── olympus_controller.py  (controlador principal v2.2)
│   ├── olympus_controller.yaml (config operacional → /etc/olympus/)
│   ├── test_*.py              (scripts de prueba hardware)
│   ├── yolov8n.onnx           (detección bbox, opset 12, 13 MB — referencia)
│   └── yolov8n-seg.onnx       (segmentación semántica, opset 12, 14 MB — GNC-REQ-002)
├── libpisp                    (ISP pisp RPi5 — requerido por libcamera)
├── libcamera                  (fork RPi Foundation, pipeline rpi/pisp)
├── libcamera-apps             (rpicam-apps HEAD, meson feature types)
├── python3-opencv / numpy / pyserial
├── kernel-modules + kernel-module-cdc-acm
├── linux-firmware-rpidistro-bcm43455
├── wpa-supplicant + iw
├── openssh + openssh-sftp-server
├── v4l-utils
├── cpufrequtils + powertop
└── bash
```

---

## Recetas propias (meta-olympus)

### Imagen

#### `recipes-core/images/olympus-image.bb` — v1.5

Imagen raíz del rover. Hereda `core-image` y añade todos los paquetes necesarios
con `IMAGE_INSTALL:append`.

- Desactiva `x11 wayland vulkan opengl bluetooth` para reducir consumo.
- Activa `wifi` en `DISTRO_FEATURES`.
- Activa `debug-tweaks` (root sin contraseña) y `ssh-server-openssh`.

---

### Apps (recipes-apps)

#### `recipes-apps/python3-rover-bridge/python3-rover-bridge.bb` — v1.4

Receta principal del HLC. Instala en el target:

| Fichero | Destino |
|---------|---------|
| `rover_bridge.so` | `/usr/lib/python3.12/site-packages/` |
| `olympus_controller.py` | `/usr/bin/` |
| `test_bridge.py` | `/usr/bin/` |
| `test_bridge_interactive.py` | `/usr/bin/` |
| `test_ultrasonic_rpi.py` | `/usr/bin/` |
| `test_opencv_camera.py` | `/usr/bin/` |
| `test_rover.py` | `/usr/bin/` |
| `yolov8n.onnx` | `/usr/share/olympus/models/` |
| `yolov8n-seg.onnx` | `/usr/share/olympus/models/` |
| `olympus_controller.yaml` | `/etc/olympus/` |

**Dependencias build:** `python3`, `python3-setuptools-native`, `udev`
**Dependencias runtime:** `python3-core`, `python3-pyserial`, `python3-pyyaml`, `udev`

#### Configuración operacional (`/etc/olympus/olympus_controller.yaml`)

`olympus_controller.py` v2.2 carga parámetros desde este fichero YAML al inicio.
Permite ajustar las siguientes constantes operacionales sin recompilar la imagen:

- **LLC:** `ping_interval_s`, `tlm_warn_s`, `tlm_retreat_s`, `tlm_stb_s`, `cycle_warn_ms`, `cycle_log_period`
- **Navegación:** `retreat_dist_mm`, `max_waypoints`, `slip_stall_frames`
- **Batería:** `batt_warn_mv`, `batt_critical_mv`
- **Velocidades:** `exp_speed_l`, `exp_speed_r` — CALIBRAR EN CAMPO
- **Visión (bbox):** `frame_width`, `frame_height`, `vision_conf_min`, `vision_area_min`, `zone_left_end`, `zone_right_start`
- **Visión (segmentación):** `vision_mode`, `seg_model_path`, `seg_conf_min`, `seg_area_min`, `seg_zone_min`, `seg_roi_top` — CALIBRAR EN CAMPO

Si el fichero no existe o PyYAML no está instalado, el controlador usa los valores
por defecto hardcodeados (idénticos a los del YAML) — sin regresión funcional.

Para modificar un parámetro en la RPi5 sin reflashear:
```bash
# Editar el fichero de config
nano /etc/olympus/olympus_controller.yaml
# Reiniciar el servicio (o volver a lanzar el script)
systemctl restart olympus-controller  # si está como servicio systemd
```

El binario `rover_bridge.so` se compila desde el crate Rust con PyO3 durante
`do_compile`. Expone a Python las funciones de comunicación UART con el MSM del
Arduino Mega (`send_command`, `recv_tlm`) y métodos GPIO para sensor futuro.

---

### Conectividad (recipes-connectivity)

#### `recipes-connectivity/wifi-config/wifi-config.bb`

- Instala `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` (modo 0600).
- Habilita `wpa_supplicant@wlan0.service` en systemd para autoconexión.
- **Nota:** El archivo contiene placeholders. Editar antes del primer arranque:
  ```
  ssid="TU_SSID_AQUI"
  psk="TU_PASSWORD_AQUI"
  ```

#### `recipes-connectivity/wifi-power-save/wifi-power-save.bb`

- Instala `wifi-power-save.sh` que ejecuta `iw dev wlan0 set power_save on`.
- Servicio systemd `wifi-power-save.service` que lo lanza tras `wpa_supplicant@wlan0`.
- Reduce consumo del chip WiFi BCM43455 en reposo.

---

### Core (recipes-core)

#### `recipes-core/custom-udev-rules/custom-udev-rules.bb`

- Instala `/etc/udev/rules.d/99-arduino.rules`.
- Crea symlink `/dev/arduino_mega` para el Arduino Mega con tres VID/PID:
  - Atmel 16U2 (Arduino Mega original): `2341:0042`
  - CH340/CH341 (clones genéricos): `1a86:7523`
  - Fallback genérico USB serial: `ttyACM*` / `ttyUSB*`
- Permisos `0666` (lectura/escritura sin sudo).

---

### Soporte (recipes-support)

#### `recipes-support/resize-rootfs/resize-rootfs.bb` — v1.1

- Instala `resize-rootfs.sh` y su unidad systemd `resize-rootfs.service`.
- En el **primer arranque** expande la partición rootfs al tamaño completo de la SD.
- Guarda bandera en `/var/lib/misc/resize-rootfs.done` para no ejecutarse más.
- **Dependencias:** `parted`, `e2fsprogs-resize2fs`.

#### `recipes-support/opencv/opencv_%.bbappend`

- Activa `BUILD_opencv_dnn=ON` en la compilación de OpenCV.
- **Necesario** para que `cv2.dnn.readNetFromONNX()` funcione en `olympus_controller.py`.
- `meta-oe` desactiva el módulo DNN por defecto; este append lo habilita.

---

### Kernel (recipes-kernel)

#### `recipes-kernel/linux/linux-raspberrypi_%.bbappend` — v1.5

Añade dos fragmentos de configuración del kernel:

**`powersave.cfg`** — Gobernador de CPU:
```
CONFIG_CPU_FREQ_DEFAULT_GOV_POWERSAVE=y
CONFIG_CPU_IDLE=y
CONFIG_TICKLESS_IDLE=y
```

**`camera.cfg`** — DMA-BUF heap (requerido por rpicam-apps en RPi5):
```
CONFIG_DMABUF_HEAPS=y
CONFIG_DMABUF_HEAPS_SYSTEM=y
CONFIG_DMABUF_HEAPS_CMA=y
```
Sin `CONFIG_DMABUF_HEAPS_CMA`, el dispositivo `/dev/dma_heap/linux,cma` no existe
y `rpicam-still` falla con timeout en el pisp-fe.

---

### BSP (recipes-bsp)

#### `recipes-bsp/bootfiles/rpi-config_%.bbappend`

Modifica `config.txt` en el target:

- Fuerza `camera_auto_detect=0` (meta-raspberrypi lo vuelve a poner en 1 — hay
  un `do_install:append` con `sed` que lo elimina y añade `=0` al final).
- Añade overlays explícitos de sensores CSI:
  ```
  dtoverlay=imx219,cam0   ← IMX219 genérica en CAM0 (conector derecho)
  dtoverlay=ov5647,cam1   ← OV5647 en CAM1 (conector izquierdo, si está presente)
  ```
- **Razón:** Las cámaras de terceros sin EEPROM no son detectadas automáticamente.

**Mapa de conectores RPi5:**

| Conector | Etiqueta | dtoverlay param | Nota |
|----------|----------|-----------------|------|
| Derecho (desde arriba) | CAM0 | `cam0` | Cámara instalada en el rover |
| Izquierdo (desde arriba) | CAM1 | `cam1` (default) | Libre |

---

### Libs (recipes-libs)

#### `recipes-libs/libpisp/libpisp_1.3.0.bb`

- Biblioteca de sintonización ISP para el pipeline `rpi/pisp` de RPi5.
- Fuente: `git://github.com/raspberrypi/libpisp.git` (commit pinneado).
- Build: Meson + pkgconfig.
- **Dependencias:** nlohmann-json, boost.
- Requerida por `libcamera_%.bbappend` cuando se usa el pipeline pisp.

---

### Multimedia (recipes-multimedia)

#### `recipes-multimedia/libcamera/libcamera_%.bbappend` — v1.5

Reemplaza el origen de libcamera con el fork de RPi Foundation:

```bitbake
SRC_URI = "git://github.com/raspberrypi/libcamera.git;protocol=https;branch=next"
SRCREV  = "fe601eb6ffe02922ff980c60621dd79d401d9061"
```

**Cambios clave:**
- Inyecta pipelines `rpi/vc4,rpi/pisp` (meta-oe solo incluye `rpi/vc4`).
- Añade archivos IPA y tuning del pisp en `FILES`.
- Añade `v4l2-compat.so` para soporte OpenCV via LD_PRELOAD.
- Añade `libpisp` como dependencia.
- Suprime warning `-Wno-unaligned-access` en ARM.

**Por qué:** Sin el pipeline `rpi/pisp`, `rpicam-hello --list-cameras` devuelve
vacío en RPi5 aunque el sensor sea detectado por I2C.

#### `recipes-multimedia/libcamera-apps/libcamera-apps_%.bbappend` — v1.3

Actualiza `libcamera-apps` al HEAD del fork `rpicam-apps` de RPi Foundation:

```bitbake
SRC_URI = "git://github.com/raspberrypi/rpicam-apps.git;protocol=https;branch=main"
SRCREV  = "593f63bf981de1a572bbb46e79e7d8b169e96fae"
```

**Cambios clave:**
- Convierte opciones meson de bool a feature type (`enabled`/`disabled`).
- Amplía `FILES` con wildcard `rpicam_app.so.*` (versión independiente).
- Desactiva backends innecesarios: egl, libav, opencv, qt, tflite.

---

## Paquetes de upstream incluidos en la imagen

| Paquete | Capa | Propósito |
|---------|------|-----------|
| `packagegroup-core-boot` | poky | Init system, busybox, base del rootfs |
| `kernel-modules` | meta-raspberrypi | Módulos del kernel RPi5 |
| `kernel-module-cdc-acm` | meta-raspberrypi | USB→serial para Arduino Mega |
| `wpa-supplicant` | meta-networking | Daemon WiFi |
| `iw` | meta-networking | Configuración de interfaz WiFi |
| `linux-firmware-rpidistro-bcm43455` | meta-raspberrypi | Firmware chip WiFi RPi5 (CYW43455) |
| `python3-core` | meta-openembedded | Intérprete Python 3.12 |
| `python3-pyserial` | meta-openembedded | UART desde Python (usado por test_rover.py) |
| `python3-pyyaml` | meta-openembedded | Carga `olympus_controller.yaml` al arrancar |
| `python3-numpy` | meta-openembedded | Procesamiento numérico (OpenCV) |
| `python3-opencv` | meta-openembedded | Visión + cv2.dnn (inferencia ONNX) |
| `libpisp` | meta-olympus | ISP RPi5 (pipeline pisp) |
| `libcamera` | meta-olympus (override) | Soporte cámara CSI con pipeline pisp |
| `libcamera-apps` | meta-olympus (override) | `rpicam-still`, `rpicam-hello`, etc. |
| `v4l-utils` | meta-openembedded | Diagnóstico de cámara (`v4l2-ctl`) |
| `libudev` | poky | udev runtime para serialport |
| `openssh` | poky | SSH para desarrollo remoto |
| `openssh-sftp-server` | poky | SFTP para transferencia de ficheros |
| `bash` | poky | Shell interactivo |
| `cpufrequtils` | meta-openembedded | Control de frecuencia CPU |
| `powertop` | meta-openembedded | Análisis de consumo energético |
