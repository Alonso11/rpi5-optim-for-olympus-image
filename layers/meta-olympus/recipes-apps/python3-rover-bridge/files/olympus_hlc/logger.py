# olympus_hlc/logger.py — Structured logger with ISO-8601 timestamps (SRS-061)

import datetime
import logging
import logging.handlers
import os


class OlympusLogger:
    """
    Logger estructurado con timestamps ISO-8601 (SRS-061, CDH-REQ-002).
    Escribe a stdout y a LOG_PATH con rotación automática por tamaño.

    Política de rotación (CDH-REQ-002 — ~2 h de retención mínima):
      _MAX_BYTES    = 5 MB  → ~3–4 h de logs a ciclo 1 s
      _BACKUP_COUNT = 1     → hlc.log + hlc.log.1 ≈ 7–8 h en disco

    Si el archivo no es accesible, continúa solo con stdout sin abortar.
    """

    DEFAULT_LOG_PATH = "/var/log/olympus/hlc.log"
    _MAX_BYTES       = 5_000_000
    _BACKUP_COUNT    = 1

    def __init__(self, log_path: str = DEFAULT_LOG_PATH):
        self._handler = None
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self._handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self._MAX_BYTES,
                backupCount=self._BACKUP_COUNT,
                encoding="utf-8",
            )
            self._handler.setFormatter(logging.Formatter("%(message)s"))
        except OSError as e:
            print(f"[Logger] Warning: no se puede abrir {log_path}: {e} — solo stdout")

    # ── escritura interna ────────────────────────────────────────────────────

    def _write(self, level: str, component: str, msg: str) -> None:
        ts   = datetime.datetime.now().isoformat(timespec="milliseconds")
        line = f"[{ts}] [{level:<5}] [{component:<7}] {msg}"
        print(line)
        if self._handler:
            self._handler.emit(logging.makeLogRecord({"msg": line}))

    # ── API pública ──────────────────────────────────────────────────────────

    def info(self, component: str, msg: str) -> None:
        self._write("INFO", component, msg)

    def warn(self, component: str, msg: str) -> None:
        self._write("WARN", component, msg)

    def log_transition(self, from_state, to_state, reason: str,
                       warn: bool = False) -> None:
        """Auditoría de transición de estado MSM (SRS-061)."""
        level = "WARN" if warn else "INFO"
        self._write(level, "MSM",
                    f"{from_state.value} → {to_state.value}  [{reason}]")

    def log_cmd(self, cmd: str, kind: str, data) -> None:
        """Log del comando enviado y la respuesta del Arduino."""
        resp = f"{data}" if data else kind.upper()
        self._write("INFO", "CMD", f"{cmd:<16} → {kind}:{resp}" if data
                    else f"{cmd:<16} → {kind}")

    def log_tlm(self, tlm) -> None:
        """Log compacto del frame TLM recibido (SyRS-030)."""
        self._write("INFO", "TLM",
                    f"{tlm.safety:<6} stall={tlm.stall_mask:06b} "
                    f"batt={tlm.batt_mv}mV/{tlm.batt_ma}mA "
                    f"dist={tlm.dist_mm}mm t={tlm.tick_ms}ms")

    def log_energy(self, level, batt_mv: int) -> None:
        """Log de cambio de nivel de energía (EPS-REQ-001)."""
        lvl_str = level.value if hasattr(level, "value") else str(level)
        msg = f"batería {batt_mv} mV — nivel {lvl_str}"
        if lvl_str == "CRITICAL":
            self._write("ERROR", "EPS", msg)
        elif lvl_str == "WARN":
            self._write("WARN",  "EPS", msg)
        else:
            self._write("INFO",  "EPS", msg)

    def log_cycle(self, cycle_ms: float) -> None:
        """Log periódico de tiempo de ciclo (RNF-001)."""
        self._write("DEBUG", "CYCLE", f"{cycle_ms:.1f} ms")

    def log_link_event(self, event: str, detail: str = "") -> None:
        """Auditoría de evento de enlace GCS (SRS-013, §7.3.8)."""
        warn  = event in ("link_lost", "reconnect_attempt_failed",
                          "max_retries_exceeded")
        level = "WARN" if warn else "INFO"
        msg   = f"GCS link event={event}" + (f" — {detail}" if detail else "")
        self._write(level, "COMM", msg)

    def close(self) -> None:
        """
        Cierra el log garantizando escritura física (SYS-FUN-050).
        Secuencia: flush → fsync → close.
        """
        if self._handler:
            try:
                self._handler.flush()
                if hasattr(self._handler, "stream") and self._handler.stream:
                    os.fsync(self._handler.stream.fileno())
            except OSError:
                pass
            self._handler.close()
            self._handler = None
