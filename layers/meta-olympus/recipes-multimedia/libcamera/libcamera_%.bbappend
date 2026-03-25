# Version: v1.2
# Use Raspberry Pi Foundation's libcamera fork which includes the pisp pipeline
# required for RPi5. The upstream meta-openembedded recipe (0.4.0) only has the
# vc4 pipeline and does not detect cameras on RPi5.
SRC_URI = "git://github.com/raspberrypi/libcamera.git;protocol=https;branch=next"
SRCREV = "fe601eb6ffe02922ff980c60621dd79d401d9061"

# Build both vc4 (RPi4) and pisp (RPi5) pipelines
LIBCAMERA_PIPELINES:raspberrypi5 = "rpi/vc4,rpi/pisp"
