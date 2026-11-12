import cv2
from flask import Flask, Response, jsonify, render_template

from detector_engine import LiveObjectDetector, resize_for_stream

app = Flask(__name__)

CONFIDENCE = 0.5
CAMERA_INDEX = 0
HOST = "0.0.0.0"
PORT = 5001

print("Loading YOLO model...")
detector = LiveObjectDetector(confidence=CONFIDENCE)
print("Model ready.")


def mjpeg_stream():
    capture = cv2.VideoCapture(CAMERA_INDEX)
    if not capture.isOpened():
        yield b""
        return

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            frame = resize_for_stream(frame)
            frame = detector.annotate(frame)
            encoded, buffer = cv2.imencode(".jpg", frame)
            if not encoded:
                continue
            chunk = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n"
            )
    finally:
        capture.release()


@app.route("/")
def home():
    return render_template("index.html", confidence=CONFIDENCE)


@app.route("/video_feed")
def video_feed():
    return Response(
        mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/status")
def status():
    return jsonify(
        {
            "model": "yolov8n",
            "confidence_threshold": CONFIDENCE,
            "camera_index": CAMERA_INDEX,
        }
    )


if __name__ == "__main__":
    print(f"Open http://127.0.0.1:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
