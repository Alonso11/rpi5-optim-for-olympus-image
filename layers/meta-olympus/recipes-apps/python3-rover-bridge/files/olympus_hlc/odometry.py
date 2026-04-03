# olympus_hlc/odometry.py — Odometría diferencial (RNF-003)
#
# Calcula la pose estimada (x, y, theta) del rover a partir de los
# acumuladores de encoders recibidos en cada frame TLM del LLC.
#
# Modelo: tracción diferencial de 6 ruedas agrupadas en dos lados.
#   - enc_left  = suma de conteos FL + CL + RL  (3 ruedas izquierdas)
#   - enc_right = suma de conteos FR + CR + RR  (3 ruedas derechas)
#
# Cinemática (velocidades medias de cada lado):
#   d_left  = (Δenc_left  / (3 * TICKS_PER_REV)) * 2π * WHEEL_RADIUS_MM
#   d_right = (Δenc_right / (3 * TICKS_PER_REV)) * 2π * WHEEL_RADIUS_MM
#   d_center = (d_left + d_right) / 2
#   dθ = (d_right - d_left) / WHEEL_BASE_MM
#   x  += d_center * cos(θ + dθ/2)
#   y  += d_center * sin(θ + dθ/2)
#   θ  += dθ
#
# Todas las distancias en mm, ángulos en radianes.
# Los valores de TICKS_PER_REV, WHEEL_RADIUS_MM y WHEEL_BASE_MM son TBD
# (ver config.py y LLC config.rs) — calibrar en campo antes de usar.

import math
from . import config


class OdometryTracker:
    """
    Integra deltas de encoders frame a frame para estimar la pose del rover.

    Estado interno: (x_mm, y_mm, theta_rad) referenciado al origen del boot.
    """

    def __init__(self) -> None:
        self.x_mm:      float = 0.0
        self.y_mm:      float = 0.0
        self.theta_rad: float = 0.0

        # Últimos acumuladores recibidos (para calcular deltas).
        # None indica "primer frame — solo inicializar referencia".
        self._last_enc_left:  float = float("nan")
        self._last_enc_right: float = float("nan")

        # Factor de conversión: ticks → mm de desplazamiento (por lado)
        # Un lado tiene 3 encoders acumulados, por eso se divide entre 3.
        ticks_per_rev = config.TICKS_PER_REV
        wheel_radius  = config.WHEEL_RADIUS_MM
        self._mm_per_tick = (2.0 * math.pi * wheel_radius) / (3.0 * ticks_per_rev)
        self._wheel_base  = float(config.WHEEL_BASE_MM)

    def update(self, enc_left: int, enc_right: int) -> None:
        """
        Actualiza la pose con los acumuladores del frame TLM más reciente.
        Debe llamarse una vez por frame TLM válido (≈1 s).
        El primer frame sólo inicializa los acumuladores de referencia.
        """
        if math.isnan(self._last_enc_left):
            self._last_enc_left  = float(enc_left)
            self._last_enc_right = float(enc_right)
            return

        d_left  = (enc_left  - self._last_enc_left)  * self._mm_per_tick
        d_right = (enc_right - self._last_enc_right) * self._mm_per_tick

        self._last_enc_left  = float(enc_left)
        self._last_enc_right = float(enc_right)

        d_center = (d_left + d_right) / 2.0
        d_theta  = (d_right - d_left) / self._wheel_base

        self.x_mm      += d_center * math.cos(self.theta_rad + d_theta / 2.0)
        self.y_mm      += d_center * math.sin(self.theta_rad + d_theta / 2.0)
        self.theta_rad += d_theta

    def pose(self) -> tuple[float, float, float]:
        """Retorna (x_mm, y_mm, theta_rad) respecto al origen del boot."""
        return (self.x_mm, self.y_mm, self.theta_rad)

    def reset(self) -> None:
        """Resetea la pose y los acumuladores de referencia."""
        self.x_mm      = 0.0
        self.y_mm      = 0.0
        self.theta_rad = 0.0
        self._last_enc_left  = float("nan")
        self._last_enc_right = float("nan")
