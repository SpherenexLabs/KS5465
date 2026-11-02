from ultralytics import YOLO

# COCO IDs: car=2, motorcycle=3, bus=5, truck=7
VEHICLE_CLASSES = {2, 3, 5, 7}
VEHICLE_NAME_KEYWORDS = (
    "car", "truck", "bus", "motor", "bike", "vehicle", "van", "auto", "rickshaw"
)

class VehicleDetector:
    def __init__(self, model_path: str, conf: float = 0.35, imgsz: int = 512):
        self.model = YOLO(model_path)
        self.conf = conf
        self.imgsz = imgsz
        self.class_names = self.model.names if isinstance(self.model.names, dict) else {}

    def _is_vehicle(self, cls_id: int) -> bool:
        # Prefer name-based filtering for custom models. Fall back to COCO IDs.
        name = str(self.class_names.get(cls_id, "")).lower()
        if name:
            return any(k in name for k in VEHICLE_NAME_KEYWORDS)
        return cls_id in VEHICLE_CLASSES

    def detect(self, frame_bgr):
        """
        Returns list of detections:
        [{ "xyxy":[x1,y1,x2,y2], "conf":0.8, "cls":2 }, ...]
        """
        results = self.model.predict(source=frame_bgr, imgsz=self.imgsz, conf=self.conf, verbose=False)
        r = results[0]
        dets = []
        if r.boxes is None:
            return dets

        for b in r.boxes:
            cls = int(b.cls.item())
            conf = float(b.conf.item())
            if not self._is_vehicle(cls):
                continue
            xyxy = b.xyxy[0].tolist()
            name = str(self.class_names.get(cls, ""))
            dets.append({"xyxy": xyxy, "conf": conf, "cls": cls, "name": name})
        return dets
