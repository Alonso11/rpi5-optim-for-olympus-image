# rover_bridge — Módulo Rust/PyO3

## Descripción

`rover_bridge` es una extensión nativa de Python escrita en Rust y compilada como
librería dinámica (`.so`). Expone la clase `Rover` que encapsula la comunicación
serial con el Arduino Mega siguiendo el protocolo MSM del ICD LLC.

Se instala en `/usr/lib/python3.12/site-packages/rover_bridge.so`.

---

## Versión actual

`lib.rs` — **v1.5**

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| FFI Python ↔ Rust | PyO3 0.22 |
| Comunicación serial | serialport 4.x |
| GPIO RPi5 (futuro) | rppal 0.22 |
| Build offline | crates vendoreados |

---

## API Python

### `Rover(port_name="/dev/arduino_mega", baud_rate=115200)`

Abre el puerto serial y espera 2 segundos para el reset del Arduino (DTR).

```python
import rover_bridge

rover = rover_bridge.Rover("/dev/arduino_mega", 115200)
```

---

### `rover.send_command(cmd: str) -> str`

Envía un comando MSM al Arduino (agrega `\n` automáticamente).
Lee la respuesta hasta `\n` con timeout de 300 ms.
Si el frame leído empieza por `TLM:` es telemetría asíncrona — se descarta
y se sigue leyendo.

**Retorna:** la respuesta ASCII del Arduino sin `\n` ni `\r`.

**Excepciones:**
- `IOError` — error de escritura o lectura serial
- `TimeoutError` — no llegó respuesta en 300 ms

```python
resp = rover.send_command("PING")   # → "PONG"
resp = rover.send_command("STB")    # → "ACK:STB"
resp = rover.send_command("EXP:80:80")  # → "ACK:EXP"
```

---

### `rover.recv_tlm() -> str | None`

Lee hasta una línea del puerto sin enviar comando (timeout 50 ms).
Retorna el frame si empieza por `"TLM:"`, `None` en cualquier otro caso.

Llamar al inicio de cada ciclo del loop para drenar los frames TLM asíncronos
emitidos por el firmware (~1 s). No bloquea el loop principal.

```python
raw = rover.recv_tlm()
if raw:
    # raw == "TLM:NORMAL:000000:12340ms:11800mV:..."
    tlm = TlmFrame.parse(raw)
```

---

### `rover.setup_ultrasonic(trigger_pin: int, echo_pin: int) -> str` [FUTURO]

Configura pines GPIO de la RPi5 para un segundo HC-SR04.
**NOTA:** El HC-SR04 activo del rover está en el Arduino (D38/D39).
Este método es para un sensor secundario en GPIO RPi5 (no instalado aún).

```python
rover.setup_ultrasonic(23, 24)
# Retorna: "Ultrasonico configurado: Trig=23, Echo=24"
```

---

### `rover.get_ultrasonic_distance() -> float | None` [FUTURO]

Mide distancia desde el HC-SR04 configurado en GPIO RPi5.
Requiere llamar `setup_ultrasonic` primero.
Retorna distancia en mm (rango válido: 20–4000 mm) o `None` si fuera de rango.

---

## Protocolo MSM

```
RPi5 (HLC)                     Arduino Mega (LLC)
     │                               │
     │── "STB\n" ─────────────────►  │
     │◄─ "ACK:STB\n" ─────────────── │
     │                               │
     │── "EXP:80:80\n" ───────────►  │
     │◄─ "ACK:EXP\n" ─────────────── │
     │                               │
     │   (sin comandos ~1 s)         │── "TLM:NORMAL:...\n" ──► recv_tlm()
     │                               │
     │── "PING\n" ─────────────────► │
     │◄─ "PONG\n" ─────────────────── │
```

- Formato ASCII, terminador `\n`
- Baud rate: 115 200 bps 8N1
- El Arduino emite TLM de forma asíncrona cada ~1 s
- `send_command` descarta frames TLM intercalados y espera el ACK real
- `recv_tlm` tiene timeout de 50 ms para no bloquear el loop

---

## Implementación Rust (estructura)

```rust
#[pyclass]
struct Rover {
    port:               Mutex<Box<dyn serialport::SerialPort>>,
    ultrasonic_trigger: Mutex<Option<OutputPin>>,  // GPIO futuro
    ultrasonic_echo:    Mutex<Option<InputPin>>,   // GPIO futuro
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: &str, baud_rate: u32) -> PyResult<Self> { ... }

    fn send_command(&self, cmd: String) -> PyResult<String> { ... }
    fn recv_tlm(&self) -> PyResult<Option<String>> { ... }

    // [FUTURO] HC-SR04 en GPIO RPi5
    fn setup_ultrasonic(&self, trigger_pin: u8, echo_pin: u8) -> PyResult<String> { ... }
    fn get_ultrasonic_distance(&self) -> PyResult<Option<f64>> { ... }
}
```

Todos los recursos de hardware están protegidos con `Mutex<T>` para seguridad
frente a accesos concurrentes (GIL de Python liberado durante I/O).

---

## Build en Yocto

La receta `python3-rover-bridge.bb` compila el módulo en modo offline:

```bash
# Variables de compilación cruzada para PyO3
CARGO_OFFLINE = "1"
PYO3_CROSS = "1"
PYO3_CROSS_PYTHON_VERSION = "3.12"
PYO3_CROSS_LIB_DIR = "${STAGING_LIBDIR}"
```

El binario resultante se instala como `rover_bridge.so` en el directorio
site-packages de Python 3.12.
