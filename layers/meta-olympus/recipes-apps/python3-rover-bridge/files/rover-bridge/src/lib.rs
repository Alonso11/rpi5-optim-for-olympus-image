use pyo3::prelude::*;
use serialport;
use std::time::Duration;
use std::io::Write;

#[pyclass]
struct Rover {
    port_name: String,
    baud_rate: u32,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: String, baud_rate: u32) -> Self {
        Rover { port_name, baud_rate }
    }

    /// Envía un comando al Arduino y retorna éxito o error
    fn send_command(&self, cmd: String) -> PyResult<String> {
        let mut port = serialport::new(&self.port_name, self.baud_rate)
            .timeout(Duration::from_millis(100))
            .open()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error serial: {}", e)))?;

        let formatted_cmd = format!("{}\n", cmd);
        port.write_all(formatted_cmd.as_bytes())
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error escritura: {}", e)))?;

        Ok(format!("Enviado a {}: {}", self.port_name, cmd))
    }
}

#[pymodule]
fn rover_bridge(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rover>()?;
    Ok(())
}
