import cv2
from ultralytics import YOLO

TRAFFIC_CLASS_IDS = {
    0: "person",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

BOX_COLORS = {
    "person": (255, 128, 0),
    "car": (0, 200, 0),
    "motorcycle": (0, 255, 255),
    "bus": (255, 0, 255),
    "truck": (0, 165, 255),
}


class TrafficVisionMonitor:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.5):
        print("Loading detection model...")
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.class_map = TRAFFIC_CLASS_IDS
        print("Model ready.")

    def infer_frame(self, frame):
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        found = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                label = self.class_map.get(cls_id, f"object_{cls_id}")
                found.append(
                    {
                        "bbox": (x1, y1, x2, y2),
                        "confidence": conf,
                        "class_name": label,
                    }
                )

        return found

    @staticmethod
    def render_detections(frame, detections):
        for item in detections:
            x1, y1, x2, y2 = item["bbox"]
            name = item["class_name"]
            conf = item["confidence"]
            color = BOX_COLORS.get(name, (0, 255, 0))

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            caption = f"{name} {conf:.2f}"
            cv2.putText(
                frame,
                caption,
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        return frame
