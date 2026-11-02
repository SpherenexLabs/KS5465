# Smart Traffic - Flask + YOLOv8

## Setup
1. Clone repository.
2. Create Python venv:
   python -m venv venv
   source venv/bin/activate   # windows: venv\Scripts\activate

3. Install requirements:
   pip install -r requirements.txt

4. Add model:
   Put your yolov8 `.pt` file into `models/yolov8n.pt`.
   (You can download yolov8n.pt from Ultralytics assets or use your trained `best.pt`.)

5. Add Firebase Admin SDK:
   - In Firebase Console -> Project Settings -> Service accounts -> Generate new private key.
   - Save the JSON file as `serviceAccountKey.json` in project root.
   - Ensure the Realtime Database URL in `app.py` matches your RTDB URL.

6. Start server:
   python app.py
   (or) python -m flask run — if using standard flask (we use socketio run in app.py)

7. Open: http://127.0.0.1:5000

## Notes
- You can change the camera source in app.py (detection_loop source param).
- For Raspberry Pi or Jetson, use proper opencv builds and consider lowering imgsz (e.g., 416) or using yolov8n for speed.
- If using public web or cloud server, secure Firebase credentials properly.