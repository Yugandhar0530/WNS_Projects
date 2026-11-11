import argparse
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from detector_core import TrafficVisionMonitor

FRAME_SIZE = (640, 480)
PREVIEW_EVERY_N = 5
PROGRESS_EVERY_N = 50


def open_capture(source):
    if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        return cv2.VideoCapture(int(source))
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")
    return cv2.VideoCapture(str(path))


def process_video(source, output_path, show_preview=True, conf=0.5):
    monitor = TrafficVisionMonitor(conf_threshold=conf)
    cap = open_capture(source)

    if not cap.isOpened():
        print(f"Could not open video source: {source}")
        return

    fps = max(int(cap.get(cv2.CAP_PROP_FPS)) or 25, 1)
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, FRAME_SIZE)

    frame_idx = 0
    class_totals = {}
    preview_frames = []

    print(f"\nSource: {source}")
    print(f"Writing annotated video to: {output_path}\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame_idx += 1
        frame = cv2.resize(frame, FRAME_SIZE)

        detections = monitor.infer_frame(frame)
        for det in detections:
            name = det["class_name"]
            class_totals[name] = class_totals.get(name, 0) + 1

        frame = monitor.render_detections(frame, detections)
        cv2.putText(
            frame,
            f"Frame {frame_idx}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

        writer.write(frame)

        if show_preview and frame_idx % PREVIEW_EVERY_N == 0:
            preview_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if frame_idx % PROGRESS_EVERY_N == 0:
            print(f"Processed {frame_idx} frames...")

    print("\n" + "=" * 48)
    print(f"Frames processed: {frame_idx}")
    print("=" * 48)
    for name, count in sorted(class_totals.items()):
        print(f"  {name}: {count}")
    print("=" * 48)
    print(f"\nSaved: {output_path}\n")

    cap.release()
    writer.release()

    if show_preview and preview_frames:
        print("Opening preview window...")
        _play_preview(preview_frames)


def _play_preview(frames_rgb):
    fig, ax = plt.subplots(figsize=(10, 7))

    def on_tick(i):
        ax.clear()
        ax.imshow(frames_rgb[i])
        ax.set_title(
            f"Live detection preview (sample frame {i * PREVIEW_EVERY_N})",
            fontsize=12,
        )
        ax.axis("off")

    FuncAnimation(
        fig,
        on_tick,
        frames=len(frames_rgb),
        interval=120,
        repeat=False,
    )
    plt.tight_layout()
    plt.show()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Intelligent Traffic Monitoring — YOLOv8 vehicle and pedestrian detection"
    )
    parser.add_argument(
        "--source",
        "-s",
        default="sample_traffic.mp4",
        help="Video file path, or camera index (e.g. 0 for webcam)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="outputs/annotated_traffic.mp4",
        help="Path for annotated output video",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="Minimum detection confidence (0–1)",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Skip matplotlib preview; only write output file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    process_video(
        args.source,
        args.output,
        show_preview=not args.no_preview,
        conf=args.conf,
    )
