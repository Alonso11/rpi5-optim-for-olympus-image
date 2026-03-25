# Load overlays for both supported CSI cameras so either can be connected.
# Each dtoverlay must be on its own line in config.txt — RPI_EXTRA_CONFIG uses
# += which joins with spaces, so we embed newlines via a Python expression.
# camera_auto_detect=0: generic modules (no EEPROM) are not auto-detected;
# explicit dtoverlays are required.
# RPI_EXTRA_CONFIG must be set here (rpi-config scope), not in the image recipe.
RPI_EXTRA_CONFIG += "${@'camera_auto_detect=0\ndtoverlay=imx219\ndtoverlay=ov5647'}"
