# 🚦 Smart Traffic AI - Complete Setup Guide

## ✅ **What's Been Fixed**

### 1. **Vehicle Detection** 
- ✓ Lowered YOLO confidence threshold from 0.35 to 0.25 for better detection
- ✓ Fixed detection loop to work when frames are available
- ✓ Added real-time vehicle bounding boxes with labels
- ✓ Different colors for different vehicle types:
  - 🟢 **Green**: Cars
  - 🟣 **Magenta**: Motorcycles/Bikes  
  - 🟠 **Orange**: Buses
  - 🟡 **Yellow**: Trucks

### 2. **Enhanced Dashboard**
- ✓ Vehicle count now highlighted with animated gradient
- ✓ Added live detection status banner with pulse animation
- ✓ Improved visual styling and responsiveness
- ✓ Better mode toggle with instant feedback

### 3. **Camera System**
- ✓ Multiple backend support (DirectShow, Media Foundation, Auto)
- ✓ Auto-retry every 5 seconds if camera disconnects
- ✓ Graceful fallback to placeholder when no camera available
- ✓ Better error messages and diagnostics

---

## 📹 **Camera Not Working? Here's How to Fix It**

### **Option 1: Fix Your Webcam** (Recommended)

#### Step 1: Check Windows Camera Settings
```powershell
# Open camera privacy settings (run in PowerShell):
Start-Process ms-settings:privacy-webcam
```
**Ensure these are turned ON:**
- ✅ "Let apps access your camera"
- ✅ "Let desktop apps access your camera"

#### Step 2: Close All Apps Using Camera
Close these apps if running:
- Microsoft Teams
- Zoom
- Skype
- OBS Studio
- Any browser tabs with camera access

#### Step 3: Restart Camera Service
```powershell
# Run in PowerShell as Administrator:
Restart-Service -Name "FrameServer" -Force
```

#### Step 4: Check Device Manager
```powershell
# Open Device Manager:
Start-Process devmgmt.msc
```
Look under **"Cameras"** or **"Imaging devices"** for yellow warning icons.

#### Step 5: Restart Computer
If all else fails, restart your PC. This usually resolves driver issues.

---

### **Option 2: Use Your Phone as Webcam** (Easiest Alternative)

#### Using DroidCam (Free)
1. **Download DroidCam**:
   - Phone: Get "DroidCam" from Play Store (Android) or App Store (iOS)
   - PC: Download from https://www.dev47apps.com/

2. **Connect**:
   - Open DroidCam on your phone
   - Open DroidCam Client on PC
   - Connect via WiFi (both devices on same network)
   - Note the IP address shown on phone

3. **Configure**:
   - Enter IP address in PC client
   - Click "Start"
   - Your phone is now a webcam!

4. **Restart Server**:
   - The system will automatically detect the DroidCam virtual camera

---

### **Option 3: Use a Video File for Testing**

#### Download a Test Traffic Video
1. Go to: https://pixabay.com/videos/search/traffic/
2. Download any traffic/road video
3. Save it as `traffic.mp4` in your project folder

#### Run with Video File
```powershell
# Set environment variable and run:
$env:VIDEO_FILE="C:\Users\csp\Desktop\KS5465\traffic.mp4"
cd server
py app.py
```

**Note:** Update the path to where you saved your video file.

---

## 🚀 **How to Start the System**

### Start the Server:
```powershell
cd C:\Users\csp\Desktop\KS5465\server
py app.py
```

### Open Dashboard:
Open your browser and go to:
- http://127.0.0.1:5000
- or http://192.168.1.34:5000 (for other devices on your network)

---

## 🎯 **Testing the Detection**

Once the camera is working, you should see:

1. **Video Feed**: Live camera view with orange ROI boxes labeled "Line 1-4"
2. **Vehicle Boxes**: Green/yellow/magenta boxes around detected vehicles
3. **Vehicle Count**: Shows number next to 🚗 icon (should be > 0 when vehicles present)
4. **Density**: Updates from 1-4 based on traffic
5. **Occupancy**: Shows percentage of road filled
6. **Console Logs**: Check terminal for messages like:
   ```
   [DETECTION] Frame: 1280x720, Detected: 3 vehicles
   [RESULT] Line 2: Count=3, Density=2, Occ=8.5%
   ```

---

## 🔧 **Advanced: Adjust Detection Settings**

### Change ROI Zones
Edit `server/app.py`, function `get_rois()` (around line 123):
```python
def get_rois(w, h):
    # Adjust these values to match your camera angle
    y = 0.18 * h      # Start height (18% from top)
    hh = 0.68 * h     # ROI height (68% of frame)
    return [
        {"id": 1, "x": 0.00*w, "y": y, "ww": 0.25*w, "hh": hh},  # Lane 1
        {"id": 2, "x": 0.25*w, "y": y, "ww": 0.25*w, "hh": hh},  # Lane 2
        {"id": 3, "x": 0.50*w, "y": y, "ww": 0.25*w, "hh": hh},  # Lane 3
        {"id": 4, "x": 0.75*w, "y": y, "ww": 0.25*w, "hh": hh},  # Lane 4
    ]
```

### Adjust Detection Confidence
Edit `server/app.py`, line 34:
```python
detector = VehicleDetector(MODEL_PATH, conf=0.25)  # Lower = more detections, higher = fewer false positives
```

### Adjust Density Thresholds
Edit `server/app.py`, function `density_from_count_occ()` (around line 139):
```python
def density_from_count_occ(count, occpct):
    if count == 0 and occpct < 2:
        return 1  # No traffic
    if count <= 2 and occpct < 12:
        return 2  # Low traffic
    if count <= 5 and occpct < 28:
        return 3  # Moderate traffic
    return 4      # Heavy traffic
```

---

## 📊 **Dashboard Features**

### Mode Toggle
- **AUTO Mode** (⚡ Blue): System automatically controls signals based on traffic
- **MANUAL Mode** (⚙️ Red): You manually control signals

### Manual Controls (Only in MANUAL mode)
- **Signal Buttons**: Force GREEN, YELLOW, or RED
- **Lane Buttons**: Override which lane gets priority

### Analytics Chart
- Real-time graphs showing:
  - Density (1-4 scale)
  - Vehicle Count
  - Occupancy Percentage

---

## 🐛 **Troubleshooting**

### "No camera detected" but I have a webcam
- Check if camera LED is on (another app might be using it)
- Try replugging USB camera
- Check USB cable/port
- Update camera drivers in Device Manager

### Detection shows 0 vehicles even with traffic visible
- Check terminal for `[DETECTION]` messages
- Verify YOLO model file exists: `server/models/best.pt`
- Try lowering confidence threshold in code
- Adjust ROI zones to match your camera angle

### Server crashes or Firebase errors
- Check internet connection
- Verify Firebase credentials in `index.html`
- Check `firebase_admin_rtdb.py` configuration

### Video feed is black/gray
- This is the placeholder - camera not detected
- Follow "Camera Not Working" steps above
- Or use video file method

---

## 📝 **System Requirements**

- **OS**: Windows 10/11
- **Python**: 3.8+
- **RAM**: 4GB minimum (8GB recommended for YOLO)
- **Camera**: USB webcam, built-in laptop camera, or phone via DroidCam
- **Internet**: Required for Firebase real-time database
- **Browser**: Chrome, Firefox, or Edge (latest version)

---

## ✨ **What's New in This Version**

1. **Better Vehicle Detection**: Reduced false negatives with lower confidence threshold
2. **Visual Feedback**: See exactly what's being detected with colored bounding boxes
3. **Improved UI**: Modern gradient effects and live status indicators
4. **Robust Camera Handling**: Auto-retry and better error messages
5. **Debug Logging**: See detection results in realtime console output
6. **Video File Support**: Test without a physical camera

---

## 🆘 **Need Help?**

If you're still having issues:

1. **Check the terminal output** for specific error messages
2. **Take a screenshot** of the error
3. **Note what you've tried** from this guide
4. Share these details for faster troubleshooting

---

**Last Updated**: February 27, 2026  
**Version**: 2.0 - Enhanced Detection & UI
