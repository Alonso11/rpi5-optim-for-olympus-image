# Version: v1.3
# Update libcamera-apps to HEAD of rpicam-apps RPi fork (593f63bf) to match
# the libcamera RPi fork (fe601eb).
#
# The new rpicam-apps changed meson options from bool to feature type.
# meta-raspberrypi still appends the old bool values via EXTRA_OEMESON:append
# — remove them and replace with the correct feature values.
SRCREV = "593f63bf981de1a572bbb46e79e7d8b169e96fae"
SRC_URI = "git://github.com/raspberrypi/rpicam-apps.git;protocol=https;branch=main"

EXTRA_OEMESON:remove = "-Denable_drm=true"
EXTRA_OEMESON:remove = "-Denable_egl=false"
EXTRA_OEMESON:remove = "-Denable_libav=false"
EXTRA_OEMESON:remove = "-Denable_opencv=false"
EXTRA_OEMESON:remove = "-Denable_qt=false"
EXTRA_OEMESON:remove = "-Denable_tflite=false"

EXTRA_OEMESON:append = " \
    -Denable_drm=enabled \
    -Denable_egl=disabled \
    -Denable_libav=disabled \
    -Denable_opencv=disabled \
    -Denable_qt=disabled \
    -Denable_tflite=disabled \
"

# Fix: capture any .so version instead of hardcoding 1.4.2
FILES:${PN} += "${libdir}/rpicam_app.so.*"
