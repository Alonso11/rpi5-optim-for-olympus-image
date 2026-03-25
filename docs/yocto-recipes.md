# Recetas Yocto — meta-olympus

Referencia de todas las recetas de la capa `meta-olympus` y los paquetes de upstream
que componen la imagen `olympus-image`.

---

## Árbol de dependencias (simplificado)

```
olympus-image
├── custom-udev-rules          → /etc/udev/rules.d/99-arduino.rules
├── resize-rootfs              → servicio systemd primer arranque
├── wifi-config                → wpa_supplicant + credenciales WiFi
├── wifi-power-save            → desactiva power-save del chip WiFi
├── python3-rover-bridge       → HLC completo (Python + Rust + modelo ONNX)
│   ├── rover_bridge.so        (extensión PyO3/Rust — UART MSM)
│   ├── olympus_controller.py  (lógica principal + visión)
│   ├── rover_protocol.py      (codificación de comandos MSM)
│   └── yolov8n.onnx           (modelo YOLOv8n opset 12)
├── libcamera                  (fork RPi Foundation, pipeline rpi/pisp)
├── libcamera-apps             (rpicam-apps HEAD, meson feature types)
├── python3-opencv / numpy / pyserial / pillow / pip
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

#### `recipes-core/images/olympus-image.bb` — v1.2

Imagen raíz del rover. Hereda `core-image` y añade todos los paquetes necesarios
con `IMAGE_INSTALL:append`.

- Desactiva `x11 wayland vulkan opengl bluetooth` para reducir consumo.
- Activa `wifi` en `DISTRO_FEATURES`.
- Activa `debug-tweaks` (root sin contraseña) y `ssh-server-openssh`.

---

### Apps (recipes-apps)

#### `recipes-apps/python3-rover-bridge/python3-rover-bridge.bb`

Receta principal del HLC. Instala en el target:

| Fichero | Destino |
|---------|---------|
| `rover_bridge.so` | `/usr/lib/python3.x/site-packages/` |
| `olympus_controller.py` | `/usr/bin/olympus_controller.py` |
| `rover_protocol.py` | `/usr/bin/rover_protocol.py` |
| `yolov8n.onnx` | `/usr/share/olympus/models/yolov8n.onnx` |

**Dependencias:** `python3-opencv`, `python3-numpy`, `python3-pyserial`

El binario `rover_bridge.so` se compila desde el crate Rust `rover_bridge`
(con PyO3) durante el `do_compile`. Expone a Python las funciones UART de
comunicación con el MSM del Arduino Mega.

---

#### `recipes-apps/rover-hlc-backup/rover-hlc.bb` *(no incluida en la imagen)*

Versión antigua del HLC como binario Rust puro. Hereda `cargo`. Instala
`rover-hlc` en `/usr/bin`. Reemplazada por `python3-rover-bridge`.

---

#### `recipes-apps/rust-raspi-uart/rust-raspi-uart.bb` *(no incluida en la imagen)*

Prototipo inicial de comunicación UART Rust → Arduino. Hereda `cargo`. Instala
`rust-raspi-uart` en `/usr/bin`. Fue el primer prototipo antes de la
arquitectura PyO3. Conservada como referencia.

---

### Conectividad (recipes-connectivity)

#### `recipes-connectivity/wifi-config/wifi-config.bb`

- Instala `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` con las credenciales
  de red del rover.
- Habilita `wpa_supplicant@wlan0.service` en systemd para autoconexión al arranque.

#### `recipes-connectivity/wifi-power-save/wifi-power-save.bb`

- Instala `wifi-power-save.sh` que ejecuta `iw dev wlan0 set power_save off`.
- Servicio systemd `wifi-power-save.service` que lo lanza tras `network-online.target`.
- Reduce la latencia de la conexión WiFi del rover.

---

### Core (recipes-core)

#### `recipes-core/custom-udev-rules/custom-udev-rules.bb`

- Instala `/etc/udev/rules.d/99-arduino.rules`.
- Crea el symlink `/dev/arduino_mega` apuntando al `ttyACM` del Arduino Mega
  identificado por VID/PID USB (Atmel/FTDI).
- Evita que el número de dispositivo cambie entre reinicios.

---

### Soporte (recipes-support)

#### `recipes-support/resize-rootfs/resize-rootfs.bb`

- Instala `resize-rootfs.sh` y su unidad systemd.
- En el **primer arranque** expande automáticamente la partición rootfs al
  tamaño completo de la microSD.
- **Dependencias:** `parted`, `e2fsprogs`.

---

### Kernel (recipes-kernel)

#### `recipes-kernel/linux/linux-raspberrypi_%.bbappend`

Añade `powersave.cfg` como fragmento de configuración del kernel:

```
CONFIG_CPU_FREQ_GOV_POWERSAVE=y
```

Activa el gobernador de frecuencia `powersave` para reducir consumo energético
del rover en operación continua.

---

### Multimedia (recipes-multimedia)

#### `recipes-multimedia/libcamera/libcamera_%.bbappend` — v1.2

Reemplaza el origen de libcamera. La receta upstream de `meta-openembedded`
(versión 0.4.0) solo incluye el pipeline `rpi/vc4` (RPi4) y no detecta cámaras
en RPi5.

```bitbake
SRC_URI = "git://github.com/raspberrypi/libcamera.git;protocol=https;branch=next"
SRCREV  = "fe601eb6ffe02922ff980c60621dd79d401d9061"
LIBCAMERA_PIPELINES:raspberrypi5 = "rpi/vc4,rpi/pisp"
```

El pipeline `rpi/pisp` es obligatorio en RPi5 para detectar cámaras CSI
(ej. IMX219).

#### `recipes-multimedia/libcamera-apps/libcamera-apps_%.bbappend` — v1.3

Actualiza `libcamera-apps` al HEAD del fork `rpicam-apps` de RPi Foundation.

**Motivos:**
1. La versión `1.4.2` de meta-raspberrypi usa la API antigua de libcamera
   (símbolos `AeLocked`, conversión `string_view`) incompatible con el fork RPi.
2. El nuevo `rpicam-apps` cambió las opciones meson de tipo bool a feature type
   (`enabled`/`disabled`), pero meta-raspberrypi aún pasa los valores bool.

**Solución:**
- `EXTRA_OEMESON:remove` para eliminar cada opción bool antigua.
- `EXTRA_OEMESON:append` para añadir las opciones feature correctas.
- `FILES:${PN}` ampliado para incluir los nuevos paths de plugins y assets.

```bitbake
SRCREV = "593f63bf981de1a572bbb46e79e7d8b169e96fae"
SRC_URI = "git://github.com/raspberrypi/rpicam-apps.git;protocol=https;branch=main"
```

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
| `python3-core` | meta-openembedded | Intérprete Python 3 |
| `python3-pyserial` | meta-openembedded | UART desde Python (fallback) |
| `python3-numpy` | meta-openembedded | Procesamiento numérico |
| `python3-opencv` | meta-openembedded | Visión por computadora + cv2.dnn (inferencia ONNX) |
| `python3-pillow` | meta-openembedded | Manipulación de imágenes |
| `python3-pip` | meta-openembedded | Instalación de paquetes en desarrollo |
| `libcamera` | meta-openembedded (sobrescrita) | Soporte cámara CSI con pipeline pisp |
| `libcamera-apps` | meta-openembedded (sobrescrita) | `rpicam-hello`, `rpicam-still`, etc. |
| `v4l-utils` | meta-openembedded | Diagnóstico de cámara (`v4l2-ctl`) |
| `libudev` | poky | udev runtime para serialport |
| `openssh` | poky | SSH para desarrollo remoto |
| `openssh-sftp-server` | poky | SFTP para transferencia de ficheros |
| `bash` | poky | Shell interactivo |
| `cpufrequtils` | meta-openembedded | Control de frecuencia CPU |
| `powertop` | meta-openembedded | Análisis de consumo energético |

---

## Configuración de cámara (fuera de Yocto)

La detección de cámaras IMX219 de terceros (sin EEPROM) requiere añadir
manualmente en `/boot/config.txt` del target:

```
dtoverlay=imx219
```

Sin este overlay el kernel detecta el sensor en dmesg pero libcamera reporta
`No cameras available`.
