// Version: v1.0
use pyo3::prelude::*;
use serialport;
use std::time::Duration;
use std::io::Write;
use std::sync::Mutex;

#[pyclass]
struct Rover {
    port: Mutex<Box<dyn serialport::SerialPort>>,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: String, baud_rate: u32) -> PyResult<Self> {
        let port = serialport::new(&port_name, baud_rate)
            .timeout(Duration::from_millis(100))
            .open()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error serial al abrir {}: {}", port_name, e)))?;

        // Al abrir el puerto, la mayoría de Arduinos se resetean (DTR).
        // Esperamos 2 segundos para que el bootloader termine y el firmware inicie.
        std::thread::sleep(Duration::from_secs(2));

        Ok(Rover {
            port: Mutex::new(port),
        })
    }

    /// Envía un comando al Arduino y retorna éxito o error
    fn send_command(&self, cmd: String) -> PyResult<String> {
        let mut port = self.port.lock()
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No se pudo bloquear el puerto serie (Mutex error)"))?;

        // Enviamos el comando seguido de un salto de línea (protocolo estándar)
        let formatted_cmd = format!("{}\n", cmd);
        port.write_all(formatted_cmd.as_bytes())
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error escritura: {}", e)))?;
        
        // Aseguramos que se envíe inmediatamente
        port.flush()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error flush: {}", e)))?;

        Ok(format!("Enviado: {}", cmd))
    }
}

#[pymodule]
fn rover_bridge(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rover>()?;
    Ok(())
}
