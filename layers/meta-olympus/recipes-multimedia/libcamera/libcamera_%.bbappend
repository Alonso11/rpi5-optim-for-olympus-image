# Version: v1.5
# Use Raspberry Pi Foundation's libcamera fork which includes the pisp pipeline
# required for RPi5. The upstream meta-openembedded recipe (0.4.0) only has the
# vc4 pipeline and does not detect cameras on RPi5.
SRC_URI = "git://github.com/raspberrypi/libcamera.git;protocol=https;branch=next"
SRCREV = "fe601eb6ffe02922ff980c60621dd79d401d9061"

# Build both vc4 (RPi4) and pisp (RPi5) pipelines.
# meta-raspberrypi defines PACKAGECONFIG[raspberrypi] = "-Dpipelines=rpi/vc4
# -Dipas=rpi/vc4 ..." and activates it for all rpi machines. PACKAGECONFIG
# flags are expanded into EXTRA_OECMAKE last, so they override any :append.
# Additionally, PACKAGECONFIG uses commas as field separators so we cannot
# encode "rpi/vc4,rpi/pisp" inside a PACKAGECONFIG value.
# Fix: remove the raspberrypi PACKAGECONFIG and inject our flags via
# EXTRA_OECMAKE directly (no commas involved in the expansion path).
PACKAGECONFIG:remove = "raspberrypi"
EXTRA_OECMAKE:append = " -Dpipelines=rpi/vc4,rpi/pisp -Dipas=rpi/vc4,rpi/pisp -Dcpp_args=-Wno-unaligned-access"

# Fix: meta-openembedded FILES only covers vc4 IPA. Include pisp IPA module and
# its tuning files so RPi5 cameras are detected by libcamera at runtime.
FILES:${PN} += " \
    ${libdir}/libcamera/ipa/ipa_rpi_pisp.so \
    ${libdir}/libcamera/ipa/ipa_rpi_pisp.so.sign \
    ${datadir}/libcamera/ipa/rpi/pisp/ \
"
