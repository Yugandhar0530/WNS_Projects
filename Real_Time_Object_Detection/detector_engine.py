import cv2
from ultralytics import YOLO

DEFAULT_MODEL = "yolov8n.pt"
STREAM_WIDTH = 640


class LiveObjectDetector:
    def __init__(self, model_path=DEFAULT_MODEL, confidence=0.5):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.labels = self.model.names

    def annotate(self, frame):
        results = self.model(frame, conf=self.confidence, verbose=False)
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                score = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                class_id = int(box.cls[0])
                name = self.labels.get(class_id, f"class_{class_id}")
                color = _color_for_label(name)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                caption = f"{name} {score:.2f}"
                cv2.putText(
                    frame,
                    caption,
                    (x1, max(y1 - 8, 18)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )
        return frame


def _color_for_label(label: str):
    seed = sum(ord(c) for c in label)
    return (seed % 200, (seed * 3) % 200, (seed * 7) % 200)


def resize_for_stream(frame, target_width=STREAM_WIDTH):
    height, width = frame.shape[:2]
    if width <= target_width:
        return frame
    scale = target_width / width
    new_size = (target_width, int(height * scale))
    return cv2.resize(frame, new_size)
