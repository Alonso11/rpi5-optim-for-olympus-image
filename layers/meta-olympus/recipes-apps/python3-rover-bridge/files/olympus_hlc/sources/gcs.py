# olympus_hlc/sources/gcs.py — GCSSource: UDP command receiver + TLM forwarder (SRS-013)

import socket
import time

from ..interfaces import CommandSource
from ..csp import CSPPacket
from ..monitors import CommLinkMonitor
from ..config import (
    GCS_BIND_ADDR, GCS_LISTEN_PORT, GCS_REPLY_PORT,
    CSP_ENABLED, CSP_ADDR_HLC, CSP_ADDR_GCS, CSP_PORT_TM, CSP_PORT_CMD, CSP_PORT_HB,
)


class GCSSource(CommandSource):
    """
    Recibe comandos y heartbeats del GCS vía UDP no-bloqueante (SRS-013).

    Con CSP_ENABLED=True (defecto): todos los paquetes están encapsulados en
    CSP con CRC-32 (SRS-001, RF-006).

    Con CSP_ENABLED=False (legado): protocolo ASCII plano para pruebas.

    La dirección del GCS se aprende dinámicamente del primer paquete recibido.
    next_command() es no-bloqueante: retorna None si no hay paquete disponible.
    """

    def __init__(self,
                 bind_addr:   str = GCS_BIND_ADDR,
                 listen_port: int = GCS_LISTEN_PORT,
                 reply_port:  int = GCS_REPLY_PORT):
        self._sock       = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bind_addr, listen_port))
        self._sock.setblocking(False)
        self._reply_port = reply_port
        self._gcs_addr   = None   # (ip, reply_port) — aprendida dinámicamente
        self._last_recv  = time.monotonic()
        self._probe_seq  = 0
        csp_str = "CSP+CRC32" if CSP_ENABLED else "ASCII (legado)"
        print(f"[GCSSource] UDP {bind_addr}:{listen_port} → :{reply_port} [{csp_str}]")

    # ── CommandSource interface ───────────────────────────────────────────────

    def next_command(self, log=None) -> "str | None":
        """
        Intenta leer un paquete UDP del GCS (no-bloqueante).
        Con CSP_ENABLED: decapsula, verifica CRC-32 (RF-006), despacha por puerto.
        Retorna la cadena de comando MSM o None.
        """
        try:
            data, addr = self._sock.recvfrom(512)
        except (BlockingIOError, OSError):
            return None

        if CSP_ENABLED:
            header, payload = CSPPacket.unpack(data)
            if header is None:
                if log:
                    log.warn("COMM",
                             f"CSP CRC-32 inválido — paquete de {addr[0]} descartado "
                             f"(RF-006 integridad comprometida)")
                return None

            self._last_recv = time.monotonic()
            self._gcs_addr  = (addr[0], self._reply_port)

            dport = CSPPacket.dst_port(header)
            if dport == CSP_PORT_CMD:
                return payload.decode("utf-8", errors="replace").strip()
            return None  # CSP_PORT_HB u otro — solo actualiza last_recv
        else:
            self._last_recv = time.monotonic()
            self._gcs_addr  = (addr[0], self._reply_port)
            msg = data.decode("utf-8", errors="replace").strip()
            if msg.startswith("CMD:"):
                return msg[4:]
            return None

    def on_tlm(self, raw_tlm: str) -> None:
        """Reenvía frame TLM al GCS vía UDP (downlink SRS-020)."""
        self.forward_tlm(raw_tlm)

    @property
    def last_recv_time(self) -> float:
        return self._last_recv

    def send_probe(self) -> None:
        """Envía probe de reconexión HB_REQ al GCS (CommLinkMonitor, SRS-013)."""
        if self._gcs_addr is None:
            return
        self._probe_seq += 1
        payload = f"HB_REQ:{self._probe_seq}".encode()
        msg = (CSPPacket.pack(CSP_ADDR_HLC, CSP_ADDR_GCS, CSP_PORT_HB, 0, payload)
               if CSP_ENABLED
               else payload + b"\n")
        try:
            self._sock.sendto(msg, self._gcs_addr)
        except OSError:
            pass

    def make_link_monitor(self) -> CommLinkMonitor:
        """GCSSource es la única fuente que requiere monitoreo de enlace (SRS-013)."""
        return CommLinkMonitor()

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    # ── Métodos internos ──────────────────────────────────────────────────────

    def forward_tlm(self, raw_tlm: str) -> None:
        """Encapsula el TLM en CSP y lo envía al GCS (RF-006)."""
        if self._gcs_addr is None:
            return
        payload = raw_tlm.encode()
        msg = (CSPPacket.pack(CSP_ADDR_HLC, CSP_ADDR_GCS, CSP_PORT_TM, 0, payload)
               if CSP_ENABLED
               else payload + b"\n")
        try:
            self._sock.sendto(msg, self._gcs_addr)
        except OSError:
            pass
