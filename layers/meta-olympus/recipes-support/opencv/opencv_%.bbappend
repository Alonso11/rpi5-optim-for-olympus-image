# Enable the dnn module required by olympus_controller.py (cv2.dnn.readNetFromONNX).
# meta-oe disables dnn by default; protobuf is already built so this adds
# only the dnn module itself with no extra dependencies.
EXTRA_OECMAKE:append = " -DBUILD_opencv_dnn=ON"
