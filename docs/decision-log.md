# Registro de Decisiones — Rover Olympus HLC (RPi5)

Historial cronológico de decisiones de diseño, cambios de arquitectura y correcciones
relevantes del repositorio `olympus-hlc-rpi5`. Derivado del historial de commits desde
el inicio del proyecto.

---

## Semana 1 — Fundación del proyecto (8–9 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-08 | Crear repositorio `olympus-hlc-rpi5` como proyecto contenedor Yocto | Separar HLC (RPi5) del LLC (Arduino) en repos independientes para claridad de responsabilidades |
| 2026-03-09 | Adoptar Yocto Scarthgap como base del sistema operativo | LTS, soporte oficial para RPi5 con meta-raspberrypi, reproducibilidad del build |
| 2026-03-09 | Crear `meta-olympus` como capa personalizada dentro del repo | Mantener todas las customizaciones del proyecto en un único lugar versionado |
| 2026-03-09 | Habilitar WiFi (`meta-openembedded/meta-networking`) | Acceso SSH remoto para desarrollo sin monitor; la RPi5 estará embebida en el rover |
| 2026-03-09 | Activar UART en `local.conf` (`enable_uart=1`) | Comunicación con Arduino Mega via serial |
| 2026-03-09 | Deshabilitar Bluetooth (`dtoverlay=disable-bt`) | Bluetooth comparte el UART principal; desactivarlo libera el puerto para el Arduino |
| 2026-03-09 | Agregar script de ahorro de energía WiFi | El rover opera con batería — reducir consumo de la radio WiFi cuando está idle |
| 2026-03-09 | Reestructurar como proyecto contenedor con `layers/` y `build/` separados | Convención Yocto estándar; permite añadir capas externas sin mezclarlas con meta-olympus |

---

## Semana 2 — rover_bridge: PyO3 + UART (10–11 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-10 | Implementar `rover_bridge` en Rust con PyO3 en lugar de Python puro | El control de motores requiere bajo jitter; Rust garantiza tiempos deterministas. Python puede llamar al .so con overhead mínimo |
| 2026-03-10 | Separar lógica de control Rust del binding PyO3 en módulos distintos | Permite unit tests del core Rust sin PyO3; el binding solo expone la interfaz Python |
| 2026-03-10 | Usar `/dev/ttyACM0` como puerto serie inicial | Puerto por defecto del Arduino Mega via USB (CDC-ACM); evita hardcodear `ttyUSB0` que puede cambiar |
| 2026-03-10 | Actualizar PyO3 a v0.22 con la Bound API | PyO3 0.22 cambia la API de referencias — necesario para compilar sin warnings en Scarthgap |
| 2026-03-10 | Habilitar SSH con `debug-tweaks` y `ssh-server-openssh` | Acceso root sin contraseña para desarrollo rápido; se eliminará en producción |
| 2026-03-10 | Agregar reglas udev para symlink `/dev/arduino_mega` | Puerto estable independiente del orden de detección USB; todos los scripts usan esta ruta |
| 2026-03-10 | Habilitar auto-resize del rootfs en primer arranque | La imagen Yocto genera una partición fija; el rover usa SD de 128 GB — expandir para logs/datos |
| 2026-03-10 | Optimizar espacio SD (`IMAGE_ROOTFS_EXTRA_SPACE = 4 GB`, `OVERHEAD_FACTOR = 1.5`) | Dejar margen para modelos ONNX, logs y datos de sensores sin quedarse sin espacio |
| 2026-03-10 | Cambiar `python3-base` → `python3-core` en IMAGE_INSTALL | `python3-base` no existe en Scarthgap; el paquete correcto es `python3-core` |
| 2026-03-10 | Corregir sintaxis en `bblayers.conf` (backslashes redundantes) | Bitbake fallaba al parsear la lista de layers |
| 2026-03-11 | Vender (vendor) todas las dependencias Rust para el build offline | Yocto no tiene acceso a internet durante `do_compile`; `cargo vendor` genera un tarball con todos los crates |
| 2026-03-11 | Bajar `Cargo.lock` de versión 4 a versión 3 | La versión de cargo en Scarthgap no soporta formato v4 de lockfile |
| 2026-03-11 | Eliminar dependencia `log` no usada | Reducir el tarball vendor; `log` no se usaba en el código |
| 2026-03-11 | Configurar variables de cross-compilación explícitas para PyO3 | PyO3 usa un build script que detecta Python; en cross-compile Yocto la detección automática falla — hay que pasarle `PYO3_CROSS_LIB_DIR` y `PYTHON_SYS_EXECUTABLE` manualmente |
| 2026-03-11 | Incluir crates de windows en el vendor aunque el target sea ARM | PyO3 incluye código condicional para Windows que el compilador necesita aunque nunca se ejecute |
| 2026-03-11 | Refactorizar recipe a `python3native` environment | Necesario para que bitbake encuentre el intérprete Python correcto durante el build de extensiones nativas |
| 2026-03-11 | Añadir tool interactiva `test_bridge_interactive.py` | Permite enviar comandos manuales al Arduino via el bridge para depuración sin escribir código |

---

## Semana 2 — Sensor ultrasónico HC-SR04 en rover_bridge (16 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-16 | Añadir `rppal` como dependencia para GPIO de RPi5 | `rppal` es la librería estándar de Rust para GPIO/I2C/SPI en RPi; alternativa a `wiringpi` (abandonado) |
| 2026-03-16 | Implementar `setup_ultrasonic` / `get_ultrasonic_distance` en rover_bridge via GPIO RPi5 | Diseño original: HC-SR04 conectado a GPIO de la RPi5 para capa táctica HLC |
| 2026-03-16 | Usar `Mutex<Option<OutputPin>>` para los pines del HC-SR04 | Permite inicialización lazy (el sensor es opcional); `Mutex` porque PyO3 requiere `Send + Sync` en `#[pyclass]` |
| 2026-03-16 | Añadir script `test_ultrasonic_rpi.py` | Validar el sensor en GPIO RPi5 antes de integrarlo al controlador principal |
| 2026-03-16 | Bajar Cargo.lock a v3 nuevamente tras añadir rppal | Añadir rppal regeneró el lockfile a v4 — volver a v3 para compatibilidad Yocto |

---

## Semana 2 — Cámara CSI + OpenCV (16–18 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-16 | Añadir `libcamera`, `libcamera-apps`, `v4l-utils` a la imagen | Soporte oficial de cámara CSI en RPi5 con el stack moderno (libcamera reemplaza a raspicam) |
| 2026-03-16 | Añadir `python3-opencv` a la imagen | Framework de visión por computadora para procesamiento de frames de la cámara CSI |
| 2026-03-16 | Añadir `python3-numpy` a la imagen | Dependencia de OpenCV; no estaba incluida explícitamente y causaba import errors |
| 2026-03-16 | Usar `cv2.VideoCapture(0, cv2.CAP_V4L2)` en lugar de picamera | libcamera expone la cámara CSI como dispositivo V4L2; más portable y compatible con OpenCV |
| 2026-03-16 | Eliminar `rpi-camera-board` de `local.conf` | El overlay `rpi-camera-board` no existe en meta-raspberrypi Scarthgap; `camera_auto_detect=1` es suficiente |
| 2026-03-16 | Eliminar `libcamera-v4l2` de IMAGE_INSTALL | El paquete correcto es `libcamera` — `libcamera-v4l2` no existe como paquete separado en Scarthgap |
| 2026-03-16 | Crear `libcamera-apps_%.bbappend` para corregir FILES | La recipe upstream de `libcamera-apps` hardcodeaba `rpicam_app.so.1.4.2`; el bbappend usa wildcard `rpicam_app.so.*` para ser agnóstico a la versión |
| 2026-03-16 | Agregar `test_opencv_camera.py` — captura frame + Canny edge detection | Test mínimo para verificar que la cámara CSI abre, captura y que OpenCV procesa el frame |
| 2026-03-17 | Añadir `meta-tensorflow-lite` y `meta-onnxruntime` a `bblayers.conf` | Plan inicial de usar modelos de ML en la RPi5 para detección de obstáculos |
| 2026-03-18 | Corregir nombre del paquete: `python3-onnxruntime` → `onnxruntime` | La recipe en meta-onnxruntime define el paquete como `onnxruntime` sin el prefijo `python3-` |
| 2026-03-18 | Intentar añadir `python3-tensorflow-lite` y fallar por dependencia Fortran | TFLite requiere compilar BLAS/LAPACK que necesitan Fortran; demasiado complejo para el scope del TFG |
| 2026-03-18 | Eliminar `python3-tensorflow-lite` de la imagen, mantener solo `onnxruntime` | TFLite descartado por complejidad de build; ONNX Runtime cubre el caso de uso con menor fricción |
| 2026-03-18 | Migrar `wifi-power-save` de `init.d` → `systemd` | Scarthgap usa systemd por defecto; el script init.d no se ejecutaba en la imagen final |
| 2026-03-18 | Añadir guard one-shot a `resize-rootfs` | Sin el guard, el script de resize se ejecutaba en cada arranque intentando expandir una partición ya expandida |
| 2026-03-18 | Añadir `LAYERDEPENDS` a `layer.conf` | Bitbake fallaba al resolver dependencias entre capas — declarar `LAYERDEPENDS` hace explícitas las dependencias de meta-olympus |
| 2026-03-18 | Crear documentación completa: `architecture.md`, `rover-bridge.md`, `testing.md`, `build-and-deploy.md` | El proyecto creció en complejidad — documentar la arquitectura, protcolo y procedimientos antes de seguir |
| 2026-03-18 | Revertir `rust-raspi-uart` de IMAGE_INSTALL | Era un binario de prueba temprano (comunicación UART básica sin PyO3); reemplazado completamente por rover_bridge |

---

## Semana 3 — Integración MSM en rover_bridge (24 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-24 | Cambiar `port_name: String` → `port_name: &str` en `Rover::new()` | `&str` evita una copia innecesaria; PyO3 0.22 soporta `&str` directamente desde Python |
| 2026-03-24 | Añadir `#[pyo3(signature = (port_name="/dev/arduino_mega", baud_rate=115200))]` | Usar el symlink udev estable como default en lugar de `ttyACM0`; portabilidad entre sistemas |
| 2026-03-24 | Corregir `&port_name` → `port_name` en `serialport::new()` | `port_name` ya es `&str` — añadir `&` creaba `&&str` que no implementa `From<&&str>` para serialport |
| 2026-03-24 | Reescribir `send_command` para leer respuesta MSM (PONG/ACK/TLM/ERR) | El protocolo MSM v1.0 requiere leer la respuesta del Arduino; la versión anterior solo escribía y retornaba inmediatamente |
| 2026-03-24 | Timeout de 300 ms en `send_command` para la lectura de respuesta | La MSM del Arduino responde en <20 ms en condiciones normales; 300 ms da margen sin bloquear demasiado |
| 2026-03-24 | Documentar `setup_ultrasonic` / `get_ultrasonic_distance` como métodos `[FUTURO]` | El HC-SR04 físico está en el Arduino (D38/D39), no en GPIO RPi5; estos métodos son para un segundo sensor futuro |

---

## Decisiones de arquitectura transversales

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-16 | HC-SR04 en Arduino (D38/D39), no en GPIO RPi5 | El HC-SR04 actúa como capa de emergencia hardware (<200 mm → FAULT inmediato); más fiable en el LLC que en el HLC Python |
| 2026-03-18 | `meta-onnxruntime` declarado en bblayers.conf pero capa no clonada | Pendiente: `cv2.dnn` (incluido en python3-opencv) puede cargar modelos ONNX directamente, eliminando la necesidad de meta-onnxruntime |
| 2026-03-24 | Decidir usar `cv2.dnn` + YOLOv8n ONNX en lugar de onnxruntime | `meta-onnxruntime` no está clonado en el repo; `cv2.dnn` está disponible via `python3-opencv` ya instalado |
| 2026-03-24 | Diseñar `olympus_controller.py` con flag `--mode vision\|manual` | Separar fuente de comandos (modelo vs operador) del pipeline MSM permite validar el sistema sin depender del modelo ONNX |
| 2026-03-24 | Patrón Strategy para `CommandSource` (VisionSource / ManualSource) | Un solo loop principal envía comandos MSM independientemente de su origen; facilita testing y futuras fuentes (red, ROS, etc.) |

---

## Semana 3 — Limpieza de dependencias ML (24 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-24 | Eliminar `onnxruntime` de `IMAGE_INSTALL` en `olympus-image.bb` | `meta-onnxruntime` no está clonado; `cv2.dnn` (incluido en python3-opencv) carga modelos ONNX directamente |
| 2026-03-24 | Eliminar `meta-tensorflow-lite` y `meta-onnxruntime` de `bblayers.conf` | Las layers no existen en el repo — bitbake falla al no encontrar los directorios |

---

## Semana 3 — Modelo ONNX + cámara CSI (24–25 mar 2026)

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-24 | Exportar `yolov8n.pt` → `yolov8n.onnx` con ultralytics (opset 12, 12.3 MB) | opset 12 es el máximo compatible con `cv2.dnn`; el modelo nano es el más ligero para inferencia en CPU |
| 2026-03-24 | Empaquetar `yolov8n.onnx` en la imagen via `python3-rover-bridge.bb` | Instala en `/usr/share/olympus/models/yolov8n.onnx` — ruta hardcodeada en `olympus_controller.py` |
| 2026-03-25 | Añadir `dtoverlay=imx219` a `config.txt` para cámara IMX219 de terceros | Las cámaras de terceros no tienen EEPROM — `camera_auto_detect=1` no las detecta; hay que forzar el overlay |
| 2026-03-25 | Cambiar SRC_URI de libcamera al fork de Raspberry Pi Foundation (fe601eb) | El paquete `libcamera_0.4.0` de meta-openembedded solo incluye el pipeline `rpi/vc4` (RPi4). RPi5 requiere `rpi/pisp` que solo está en el fork RPi. Sin pisp, `libcamera-hello --list-cameras` devuelve vacío aunque `dmesg` detecte el sensor (Error -121 en I2C no era el problema real) |
| 2026-03-25 | Descartado TF-Luna para el TFG | Requeriría USART2 (D16/D17) en el firmware Arduino y añadir capa táctica a la MSM; complejidad no justificada para el alcance del TFG. Queda documentado como trabajo futuro |

---

## Semana 3 — Debugging cámara CSI IMX219 en RPi5 (25 mar 2026)

### Problema: pisp-fe /dev/video4 dequeue timeout (1 segundo)

La cámara era detectada por I2C y libcamera configuraba todo el pipeline correctamente,
pero `rpicam-still` fallaba siempre con `Camera frontend has timed out!`.

**Diagnóstico paso a paso:**

| Síntoma | Causa | Fix |
|---|---|---|
| `libcamera-hello` sin cámaras | Faltaban pisp IPA files en el paquete | `FILES` en `libcamera_%.bbappend` ampliado con `ipa_rpi_pisp.so` y `pisp/` tuning dir |
| `camera_auto_detect=1` en config.txt después de build | `meta-raspberrypi` añade su propio `RPI_EXTRA_CONFIG` con `=1` después del nuestro | `do_install:append` con `find + sed` para eliminar todas las ocurrencias y añadir `=0` al final |
| `/dev/dma_heap/linux,cma` no existe | `CONFIG_DMABUF_HEAPS_CMA` no habilitado | `camera.cfg` kernel fragment con los tres `CONFIG_DMABUF_HEAPS*=y` |
| Conflicto de formatos 640x480 vs 1640x1232 | `dtoverlay=ov5647` cargado en el mismo puerto que `imx219` | Eliminar `dtoverlay=ov5647` del `RPI_EXTRA_CONFIG` |
| Timeout persiste pese a todo lo anterior | `dtoverlay=imx219` (sin parámetro) configura **CAM1** (conector izquierdo, CSI0/1f00128000/i2c@80000), pero la cámara está en **CAM0** (conector derecho, CSI1/1f00110000/i2c@88000) | `dtoverlay=imx219,cam0` |

### Mapa de conectores RPi5

| Conector | Etiqueta RPi5 | dtoverlay param | CSI addr | I2C adapter |
|---|---|---|---|---|
| Derecho (desde arriba) | CAM0 | `cam0` | `1f00110000` | i2c@88000 |
| Izquierdo (desde arriba) | CAM1 | `cam1` (default) | `1f00128000` | i2c@80000 |

La numeración es contra-intuitiva: CAM0 es el conector de la derecha.

### Detección automática sin EEPROM

Con `camera_auto_detect=0` no es posible para módulos genéricos. La solución es cargar
un overlay por puerto, dejando que el kernel haga probe de ambos:

```
dtoverlay=imx219,cam0
dtoverlay=ov5647,cam1
```

Libcamera detecta automáticamente cuál está físicamente conectado.

### Estado final

- IMX219 genérico en CAM0 → **30 fps estable** con `rpicam-still` y `test_opencv_camera.py`.
- `olympus_controller.py --mode vision` falla solo por falta de Arduino (rover_bridge), no por la cámara.

| Decisión | Motivo |
|---|---|
| `dtoverlay=imx219,cam0` como overlay por defecto en `rpi-config_%.bbappend` | CAM0 es el conector donde está montada la cámara en el rover |
| Documentar ambos overlays para detección automática | Permite conectar IMX219 o OV5647 en el puerto correcto sin cambiar config |

---

## Pendiente (al 25 mar 2026)

| Tarea | Bloqueante | Prioridad |
|---|---|---|
| ~~Limpiar `onnxruntime` de IMAGE_INSTALL y `bblayers.conf`~~ | ✅ Hecho | — |
| ~~Exportar YOLOv8n a ONNX~~ | ✅ Hecho | — |
| ~~Implementar `olympus_controller.py` (manual + vision)~~ | ✅ Hecho | — |
| ~~PR `feature/msm-main-integration` → `debug` en LLC repo~~ | ✅ PR #1 abierto | — |
| ~~Verificar cámara IMX219 con rpicam-still~~ | ✅ 30 fps estable en CAM0 | — |
| ~~Verificar test_opencv_camera.py~~ | ✅ Funciona | — |
| Rebuild Yocto con `dtoverlay=imx219,cam0` (fix ya en recipe) | Requiere build en GCP VM | Media |
| Flash firmware LLC al Arduino y probar protocolo MSM | Sin hardware conectado | Alta (bloqueante) |
| Probar `olympus_controller.py --mode vision` con Arduino conectado | Flash LLC pendiente | Alta |
