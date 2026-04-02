# olympus_hlc/config.py — Configuration loader and runtime constants
#
# Busca la configuración en orden:
#   1. /etc/olympus/olympus_controller.yaml  (producción — instalado por Yocto)
#   2. configs/olympus_controller.yaml       (desarrollo — junto al paquete)
#
# Si ningún archivo existe o PyYAML no está disponible, todos los parámetros
# usan los valores por defecto definidos aquí.

from pathlib import Path


def _load_config() -> dict:
    candidates = [
        Path("/etc/olympus/olympus_controller.yaml"),
        Path(__file__).parent.parent / "configs" / "olympus_controller.yaml",
    ]
    try:
        import yaml
        for path in candidates:
            if path.exists():
                with open(path) as f:
                    return yaml.safe_load(f) or {}
    except ImportError:
        pass
    return {}


_cfg = _load_config()

# ─── Timing ──────────────────────────────────────────────────────────────────

PING_INTERVAL_S   = float(_cfg.get("ping_interval_s",   1.0))   # Max s entre comandos antes de PING
TLM_WARN_S        = float(_cfg.get("tlm_warn_s",        5.0))   # Sin TLM → advertencia
TLM_RETREAT_S     = float(_cfg.get("tlm_retreat_s",     10.0))  # Sin TLM → RET (SYS-FUN-021)
TLM_STB_S         = float(_cfg.get("tlm_stb_s",         30.0))  # Sin TLM → STB (COMM-REQ-005)
CYCLE_WARN_MS     = int  (_cfg.get("cycle_warn_ms",     1500))  # Umbral ciclo lento (RNF-001)
CYCLE_LOG_PERIOD  = int  (_cfg.get("cycle_log_period",  50))    # Cada N ciclos loguear tiempo
TLM_INTERVAL_WARN_S = float(_cfg.get("tlm_interval_warn_s", 2.0))  # Delta TLMs (SyRS-017)

# ─── Navigation ──────────────────────────────────────────────────────────────

RETREAT_DIST_MM   = int  (_cfg.get("retreat_dist_mm",   300))   # Distancia táctica HLC (SyRS-061)
MAX_WAYPOINTS     = int  (_cfg.get("max_waypoints",     5))     # Últimos N waypoints (SyRS-061)
SLIP_STALL_FRAMES = int  (_cfg.get("slip_stall_frames", 2))     # Frames consecutivos stall → RET (RF-004)

# ─── Energy / Thermal ────────────────────────────────────────────────────────

BATT_WARN_MV      = int  (_cfg.get("batt_warn_mv",      14000)) # 3.5 V/celda × 4S (EPS-REQ-001)
BATT_CRITICAL_MV  = int  (_cfg.get("batt_critical_mv",  12800)) # 3.2 V/celda × 4S → STB
TEMP_WARN_C       = int  (_cfg.get("temp_warn_c",       45))    # °C → advertencia (RNF-004)
TEMP_CRIT_C       = int  (_cfg.get("temp_crit_c",       60))    # °C → Safe Mode (RNF-004)

# ─── Storage ─────────────────────────────────────────────────────────────────

STORAGE_MIN_MB       = int(_cfg.get("storage_min_mb",       50))   # MB libres mínimos (SRS-014)
STORAGE_CHECK_CYCLES = int(_cfg.get("storage_check_cycles", 300))  # Cada N ciclos verificar disco

# ─── Vision ──────────────────────────────────────────────────────────────────

FRAME_WIDTH       = int  (_cfg.get("frame_width",       640))
FRAME_HEIGHT      = int  (_cfg.get("frame_height",      480))
VISION_CONF_MIN   = float(_cfg.get("vision_conf_min",   0.5))   # Confianza mínima
VISION_AREA_MIN   = float(_cfg.get("vision_area_min",   0.05))  # Área mínima bbox
ZONE_LEFT_END     = float(_cfg.get("zone_left_end",     0.33))  # 0–33% → AVD:R
ZONE_RIGHT_START  = float(_cfg.get("zone_right_start",  0.67))  # 67–100% → AVD:L
EXP_SPEED_L       = int  (_cfg.get("exp_speed_l",       40))
EXP_SPEED_R       = int  (_cfg.get("exp_speed_r",       40))

# Segmentation pipeline (GNC-REQ-002)
VISION_MODE       = str  (_cfg.get("vision_mode",       "bbox"))
SEG_MODEL_PATH    = str  (_cfg.get("seg_model_path",
                          "/usr/share/olympus/models/yolov8n-seg.onnx"))
SEG_CONF_MIN      = float(_cfg.get("seg_conf_min",      0.5))
SEG_AREA_MIN      = float(_cfg.get("seg_area_min",      0.03))
SEG_ZONE_MIN      = float(_cfg.get("seg_zone_min",      0.05))
SEG_ROI_TOP       = float(_cfg.get("seg_roi_top",       0.5))

# ─── GCS link (SRS-013, SYS-FUN-021) ─────────────────────────────────────────

GCS_LISTEN_PORT      = int  (_cfg.get("gcs_listen_port",      9000))
GCS_REPLY_PORT       = int  (_cfg.get("gcs_reply_port",       9001))
GCS_BIND_ADDR        = str  (_cfg.get("gcs_bind_addr",        "0.0.0.0"))
GCS_LINK_LOST_S      = float(_cfg.get("gcs_link_lost_s",      10.0))
GCS_RETRY_INTERVAL_S = float(_cfg.get("gcs_retry_interval_s", 5.0))
GCS_MAX_RETRIES      = int  (_cfg.get("gcs_max_retries",      3))

# ─── CSP (SRS-001, RF-006, SyRS-016) ─────────────────────────────────────────

CSP_ADDR_GCS  = int (_cfg.get("csp_addr_gcs",  1))
CSP_ADDR_HLC  = int (_cfg.get("csp_addr_hlc",  2))
CSP_PORT_TM   = int (_cfg.get("csp_port_tm",  10))
CSP_PORT_CMD  = int (_cfg.get("csp_port_cmd", 11))
CSP_PORT_HB   = int (_cfg.get("csp_port_hb",   1))
CSP_ENABLED   = bool(_cfg.get("csp_enabled", True))
