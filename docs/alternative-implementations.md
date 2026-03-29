# Alternativas de Implementación: Arduino Mega + RPi5 HLC

Este documento analiza las alternativas técnicas consideradas para el stack de comunicación
entre el High-Level Controller (RPi5) y el Low-Level Controller (Arduino Mega), comparadas
con la implementación final basada en Rust/PyO3.

---

## 1. Contexto del Diseño Actual

La arquitectura implementada es:

```
RPi5 (Yocto Linux)
└── rover_bridge.so  (Rust/PyO3)
    ├── serialport crate  →  /dev/arduino_mega  (USB, 115200 baud)
    └── rppal crate       →  GPIO 23/24 (HC-SR04 trigger/echo)

Arduino Mega 2560
├── Serial0  (USB)    ←→  RPi5 — comandos F/B/L/R/S + DIST:XXXX\n
└── Serial2  (D16/D17) ←  TF-Luna LiDAR (115200 baud)
```

El protocolo de comandos es ASCII de un byte + newline (`F\n`, `B\n`, `L\n`, `R\n`, `S\n`),
elegido por su simplicidad, capacidad de depuración con `minicom`, y resistencia a corrupción
de bytes (el protocolo es stateless y se recupera inmediatamente de un byte erróneo).

---

## 2. Alternativa: Arduino C/C++ con Librerías Estándar

### 2.1 Parsing de Comandos con la Librería Serial de Arduino

La librería `Serial` de Arduino (clase `HardwareSerial`) es la interfaz estándar para UART en
microcontroladores AVR. El Arduino Mega 2560 expone cuatro puertos UART hardware independientes:
`Serial` (USB/D0-D1), `Serial1` (D18-D19), `Serial2` (D16-D17), `Serial3` (D14-D15) [1].

Un sketch equivalente al protocolo que recibe el Arduino en producción:

```cpp
void setup() {
  Serial.begin(115200);  // USB hacia RPi5
  // configurar pines de motor...
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'F': forward();   break;
      case 'B': backward();  break;
      case 'L': turnLeft();  break;
      case 'R': turnRight(); break;
      case 'S': stopAll();   break;
      // '\n' y '\r' se ignoran implícitamente
    }
  }
}
```

`Serial.read()` retorna `-1` si no hay datos disponibles (no bloqueante), por eso se
antepone `Serial.available() > 0` [2]. El switch sobre un `char` ASCII tiene overhead
prácticamente nulo: un byte en el bus, un lookup, una llamada a función.

> **Nota:** Nuestro protocolo ya sigue este patrón estándar. La diferencia no está en el
> sketch del Arduino sino en el lado RPi5.

### 2.2 HC-SR04 con `NewPing` en el Arduino

La librería `NewPing` es la implementación de referencia para el sensor HC-SR04 en Arduino [3].
Maneja internamente el pulso de trigger de 10 µs y usa `pulseIn()` con timeout para medir
el eco:

```cpp
#include <NewPing.h>

#define TRIG_PIN 22
#define ECHO_PIN 23
#define MAX_DISTANCE 400  // cm — equivale a nuestro cap de 4000 mm

NewPing sonar(TRIG_PIN, ECHO_PIN, MAX_DISTANCE);

void loop() {
  unsigned int dist_mm = sonar.ping() / US_ROUNDTRIP_MM;
  Serial.print("DIST_US:");
  Serial.println(dist_mm);
}
```

**Ventaja técnica real sobre nuestra implementación:** `pulseIn()` en un AVR de 16 MHz sobre
bare-metal tiene resolución de ~4 µs y es determinista. En contraste, nuestro busy-wait en
Rust sobre Linux (`while echo.is_low() { ... }`) está sujeto al scheduler del kernel, que
puede preemptar el hilo e introducir jitter de cientos de microsegundos [4][5].

#### Por qué el HC-SR04 está en el RPi5 y no en el Arduino

Mover el HC-SR04 al Arduino (solución técnicamente superior para timing) requeriría que el
Arduino devuelva las lecturas al RPi5. Sin embargo, el diseño de hardware tiene una restricción:

- `Serial0` (USB) ya está ocupado con comunicación bidireccional RPi5 ↔ Arduino
- `Serial2` (D16/D17) ya está ocupado con el TF-Luna LiDAR

Multiplexar datos de HC-SR04 sobre `Serial0` junto con los comandos de motor complica el
protocolo. La alternativa de usar `Serial1` o `Serial3` como canal dedicado al RPi5 requiere
un cable físico adicional y un level shifter (Arduino 5 V vs RPi5 3.3 V). Por estas
restricciones de hardware, el HC-SR04 se conectó directamente al RPi5, aceptando el jitter
de timing de Linux como trade-off.

### 2.3 TF-Luna con `TFMPlus` en el Arduino

La librería `TFMPlus` parsea el frame binario de 9 bytes del TF-Luna (header `0x59 0x59`,
2 bytes de distancia, 2 bytes de signal strength, checksum) [6][7]:

```cpp
#include <TFMPlus.h>
TFMPlus tfmini;

void setup() {
  Serial.begin(115200);   // hacia RPi5
  Serial2.begin(115200);  // TF-Luna en D16/D17
  tfmini.begin(&Serial2);
}

void loop() {
  int16_t dist, flux, temp;
  if (tfmini.getData(dist, flux, temp)) {
    Serial.print("DIST:");
    Serial.println(dist);  // en cm; TFMPlus retorna cm nativamente
  }
}
```

Sin la librería, el protocolo binario del TF-Luna requiere parseo manual del frame de 9 bytes,
validación del checksum, y manejo de casos borde (frame incompleto, header corrompido).
`TFMPlus` abstrae todo esto. El formato de salida `DIST:XXXX\n` que produce es exactamente el
que nuestro Arduino ya envía al RPi5.

### 2.4 Control de Motores (L298N / BTS7960)

El control directo de motores con L298N usando PWM de Arduino es el enfoque más común en
proyectos de rovers hobbyistas [8]:

```cpp
#define IN1 2
#define IN2 3
#define ENA 6  // PWM

void forward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, 200);  // 78% duty cycle
}
```

Una extensión natural del protocolo actual para soporte de velocidad sería `F:180\n`,
parseado con `strtok()` en el Arduino. Nuestra implementación actual usa velocidad fija
configurada en `setup()`.

La alternativa `AFMotor` (Adafruit Motor Shield V2) comunica con el expansor PWM del shield
via I2C [9], lo que libera pines de Arduino pero añade overhead de ~algunos µs por comando
de motor (irrelevante para velocidades de rover).

---

## 3. Alternativa: pyserial + libgpiod en RPi5 (sin Rust)

En lugar de `rover_bridge.so` (Rust/PyO3), el RPi5 podría usar librerías Python estándar
disponibles en el layer `meta-python` de Yocto:

```python
# rover_bridge.py — equivalente funcional puro Python
import serial
import time
import gpiod  # libgpiod v2 Python bindings

class Rover:
    def __init__(self, port_name: str, baud_rate: int):
        self.ser = serial.Serial(port_name, baud_rate, timeout=1)
        time.sleep(2)  # esperar reset DTR del Arduino
        self._chip = None
        self._trig = None
        self._echo = None

    def send_command(self, cmd: str) -> str:
        self.ser.write(f"{cmd}\n".encode())
        self.ser.flush()
        return f"Enviado: {cmd}"

    def setup_ultrasonic(self, trigger_pin: int, echo_pin: int):
        self._chip = gpiod.Chip("gpiochip4")  # RPi5 usa gpiochip4
        self._trig = self._chip.get_line(trigger_pin)
        self._echo = self._chip.get_line(echo_pin)
        self._trig.request(consumer="rover", type=gpiod.LINE_REQ_DIR_OUT)
        self._echo.request(consumer="rover", type=gpiod.LINE_REQ_DIR_IN)
```

### Comparación directa con la implementación Rust/PyO3

| Dimensión | Rust/PyO3 (`rover_bridge.so`) | pyserial + python3-gpiod |
|---|---|---|
| Dependencias en imagen | `rover_bridge.so` (recipe custom) | `python3-pyserial` + `python3-gpiod` (meta-python / meta-oe) |
| Complejidad de recipe | Alta: `inherit cargo`, 46 crates vendoreados, cross-compile | Trivial: `inherit python3native`, instalar archivos `.py` |
| Thread safety | Rust `Mutex<>` enforced en compile-time | Manual con `threading.Lock` en Python |
| Jitter HC-SR04 | Userspace Linux (Rust busy-wait) | Userspace Linux (Python busy-wait) — **equivalente** |
| Latencia serial | Idéntica — I/O bound, no CPU bound [10] | Idéntica |
| Iteración en desarrollo | `bitbake` 5–30 min por cambio Rust | Editar `.py` + `scp` al target, inmediato |
| Riesgo de mantenimiento | PyO3 API cambia entre versiones de Rust | API pyserial estable, bien documentada |
| Issue conocido | Symlink glob frágil en `do_configure:prepend` | Eliminado |

> **Observación importante:** La recipe actual ya incluye `python3-pyserial` como dependencia
> de runtime (`RDEPENDS:${PN} += "python3-core python3-pyserial udev"`). pyserial ya está
> en el target; el módulo Rust añade complejidad sin eliminar esa dependencia.

### GPIO en RPi5: libgpiod vs RPi.GPIO

`RPi.GPIO` fue diseñado para el chip BCM2835 de los modelos anteriores de Raspberry Pi.
El RPi5 usa el chip RP1 como controlador GPIO, lo que hace que `RPi.GPIO` tenga soporte
limitado o experimental en esta plataforma [11]. La alternativa correcta para RPi5 es
`libgpiod`, la interfaz estándar del kernel Linux para GPIO desde el userspace [12].
`python3-gpiod` (bindings Python para libgpiod v2) está disponible en `meta-oe`.

---

## 4. Alternativas de Protocolo Completo (Descartadas)

### 4.1 ROS 1 / rosserial

`rosserial` permite que el Arduino publique y suscriba a topics ROS directamente [13].
El Arduino corre el nodo rosserial; el RPi5 corre `rosserial_python` como bridge serie-ROS.

**Razón de descarte:**
- Requiere instalación completa de ROS (múltiples daemons, `roscore`, parameter server)
- ROS 1 está en EOL desde mayo 2025
- Overhead de 3–8 ms por mensaje vs nuestro ~2 ms total (dominado por tiempo de wire a 115200 baud)
- Complejidad de integración en imagen Yocto es alta

### 4.2 micro-ROS (ROS 2)

micro-ROS es el equivalente ROS 2 para microcontroladores, usando DDS como middleware [14].

**Razón de descarte:**
- El Arduino Mega 2560 (AVR ATmega2560, 8-bit) **no está en la lista oficial de hardware
  soportado** por micro-ROS, que apunta a chips ARM Cortex-M (ESP32, Teensy 4.x, STM32).
- Requeriría reemplazar el Arduino Mega con hardware diferente.

### 4.3 Firmata / pyfirmata

El protocolo Firmata convierte el Arduino en un dispositivo de I/O remoto: el Arduino corre
`StandardFirmata` (sin sketch custom) y toda la lógica vive en el RPi5 en Python [15].

**Razón de descarte:**
- Firmata expone pines GPIO y ADC crudos, sin primitivas para timing de HC-SR04 ni parseo
  del frame binario del TF-Luna
- Un custom FirmataExtension para `pulseIn()` añade más complejidad que simplemente usar
  el protocolo ASCII directo
- Elimina el valor del Arduino como microcontrolador con timing determinista

---

## 5. Análisis de Latencia

Para el caso de uso de un rover de control a velocidades moderadas:

| Operación | Latencia estimada |
|---|---|
| Wire time de `F\n` a 115200 baud (2 bytes × 10 bits) | ~174 µs |
| Kernel UART write RPi5 (pyserial o Rust, ambos usan driver kernel) | < 1 ms |
| Arduino `loop()` polling `Serial.available()` a 16 MHz | ~algunos µs |
| **Latencia total comando motor** | **~2–5 ms** |
| Wire time de `DIST:1234\n` (10 bytes) | ~870 µs |
| **Latencia total lectura LiDAR** | **~3–6 ms** |

Ninguna alternativa de protocolo introduce latencia significativa para un rover operando
a velocidades donde update rates de 10–50 Hz son suficientes. La latencia dominante al
arrancar es el delay de 2 segundos por reset DTR del Arduino al abrir el puerto serie.

---

## 6. Conclusión

El enfoque estándar para un proyecto de estas características hubiera sido:

- **Arduino Mega:** sketch C++ con `NewPing` (HC-SR04) + `TFMPlus` (TF-Luna) + switch de comandos ASCII
- **RPi5 (Yocto):** `python3-pyserial` + `python3-gpiod`, sin módulo Rust

La decisión de usar Rust/PyO3 fue motivada por demostrar integración Rust-Python vía FFI
(relevante en el contexto académico del TFG) y por las garantías de thread safety en
compile-time. Sin embargo, para el perfil de uso real del rover (loop de control secuencial,
single-threaded), estas ventajas no aportan beneficio operacional concreto.

La restricción de hardware que determinó el diseño del HC-SR04 (un solo canal USB UART
disponible para RPi5 ↔ Arduino, sin pines RX/TX libres dedicados) hace que su ubicación
en el RPi5 GPIO sea la decisión correcta dentro de las restricciones del sistema, aceptando
el jitter de timing de Linux como trade-off conocido.

---

## Referencias

[1] Arduino, "Serial — Arduino Reference," https://www.arduino.cc/en/Reference/serial

[2] Arduino, "Serial.read() — Arduino Reference," https://www.arduino.cc/reference/en/language/functions/communication/serial/read/

[3] T. Newberry, "NewPing Library — Arduino Reference," https://www.arduino.cc/reference/en/libraries/newping/

[4] K. Boone, "Using the HC-SR04 ultrasonic range sensor on the Raspberry Pi," Kevin Boone's Web Site, https://kevinboone.me/pi-hcsr04.html

[5] Raspberry Pi Forums, "Troubles with HC-SR04 ultrasonic module on Raspberry Pi," https://forums.raspberrypi.com/viewtopic.php?t=248775

[6] B. Ryerson, "TFMini-Plus Arduino Library," GitHub, https://github.com/budryerson/TFMini-Plus

[7] Benewake, "Develop Routine of TF-Luna in Arduino," Benewake Co. Ltd., https://cdn.webshopapp.com/shops/304271/files/333438293/develop-routine-of-tf-luna-in-arduino.pdf

[8] HowToMechatronics, "Arduino DC Motor Control Tutorial — L298N PWM H-Bridge," https://howtomechatronics.com/tutorials/arduino/arduino-dc-motor-control-tutorial-l298n-pwm-h-bridge/

[9] Adafruit, "Adafruit Motor Shield V2 — Using DC Motors," Adafruit Learning System, https://learn.adafruit.com/adafruit-motor-shield/using-dc-motors

[10] pyserial Developers, "pyserial — Python Serial Port Extension," GitHub, https://github.com/pyserial/pyserial

[11] Raspberry Pi Ltd., "Raspberry Pi 5 — GPIO and the RP1 chip," Raspberry Pi Documentation, https://www.raspberrypi.com/documentation/computers/raspberry-pi-5.html

[12] Linux Kernel, "GPIO Descriptor Consumer Interface," The Linux Kernel documentation, https://www.kernel.org/doc/html/latest/driver-api/gpio/consumer.html

[13] M. Amin, "How to Use Arduino with Robot Operating System (ROS)," Maker Pro, https://maker.pro/arduino/tutorial/how-to-use-arduino-with-robot-operating-system-ros

[14] micro-ROS, "micro-ROS for ROS 2 on Microcontrollers," Robotics Knowledgebase, https://roboticsknowledgebase.com/wiki/interfacing/microros-for-ros2-on-microcontrollers/

[15] The Robotics Back-End, "Control Arduino with Python and pyfirmata from Raspberry Pi," https://roboticsbackend.com/control-arduino-with-python-and-pyfirmata-from-raspberry-pi/
