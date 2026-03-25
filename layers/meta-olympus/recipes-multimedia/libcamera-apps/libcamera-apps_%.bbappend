# Version: v1.2
# Update libcamera-apps to HEAD of rpicam-apps RPi fork (593f63bf) to match
# the libcamera RPi fork (fe601eb). The meta-raspberrypi recipe pins to 1.4.2
# which uses the old libcamera API (AeLocked, string vs string_view).
#
# The new rpicam-apps also changed meson options from bool (true/false) to
# feature (enabled/disabled/auto) — override EXTRA_OEMESON accordingly.
SRCREV = "593f63bf981de1a572bbb46e79e7d8b169e96fae"
SRC_URI = "git://github.com/raspberrypi/rpicam-apps.git;protocol=https;branch=main"

EXTRA_OEMESON = " \
    -Dneon_flags=arm64 \
    -Denable_drm=enabled \
    -Denable_egl=disabled \
    -Denable_libav=disabled \
    -Denable_opencv=disabled \
    -Denable_qt=disabled \
    -Denable_tflite=disabled \
"

# Fix: capture any .so version instead of hardcoding 1.4.2
FILES:${PN} += "${libdir}/rpicam_app.so.*"
