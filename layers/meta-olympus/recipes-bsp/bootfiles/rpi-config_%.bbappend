# Load overlays for both supported CSI cameras so either can be connected.
# RPi5 detects at runtime which sensor is present on the CSI port.
# - IMX219: RPi Camera v2 and generics
# - OV5647: RPi Camera v1 and generics
# RPI_EXTRA_CONFIG must be set here (rpi-config scope), not in the image recipe.
RPI_EXTRA_CONFIG += "dtoverlay=imx219"
RPI_EXTRA_CONFIG += "dtoverlay=ov5647"
