# Version: v1.4
# Use Raspberry Pi Foundation's libcamera fork which includes the pisp pipeline
# required for RPi5. The upstream meta-openembedded recipe (0.4.0) only has the
# vc4 pipeline and does not detect cameras on RPi5.
SRC_URI = "git://github.com/raspberrypi/libcamera.git;protocol=https;branch=next"
SRCREV = "fe601eb6ffe02922ff980c60621dd79d401d9061"

# Build both vc4 (RPi4) and pisp (RPi5) pipelines.
# LIBCAMERA_PIPELINES is prepended to EXTRA_OECMAKE by the base recipe, but the
# base recipe also hardcodes -Dpipelines=rpi/vc4 -Dipas=rpi/vc4 afterwards.
# Meson uses the last occurrence of a -D flag, so we must append our values to
# ensure they win over the base recipe's hardcoded flags.
EXTRA_OECMAKE:append:raspberrypi5 = " -Dpipelines=rpi/vc4,rpi/pisp -Dipas=rpi/vc4,rpi/pisp"

# Fix: meta-openembedded FILES only covers vc4 IPA. Include pisp IPA module and
# its tuning files so RPi5 cameras are detected by libcamera at runtime.
FILES:${PN} += " \
    ${libdir}/libcamera/ipa/ipa_rpi_pisp.so \
    ${libdir}/libcamera/ipa/ipa_rpi_pisp.so.sign \
    ${datadir}/libcamera/ipa/rpi/pisp/ \
"
