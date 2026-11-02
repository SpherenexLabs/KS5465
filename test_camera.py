import cv2

print("Testing camera access...")
print("\nTrying different camera indices:")

for i in range(3):
    print(f"\n--- Camera Index {i} ---")
    
    # Try with DirectShow
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✓ SUCCESS: Camera {i} works with DirectShow!")
            print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")
            cap.release()
            break
        cap.release()
    
    # Try without DirectShow
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"✓ SUCCESS: Camera {i} works with default backend!")
            print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")
            cap.release()
            break   
        cap.release()
    
    print(f"✗ Camera index {i} not available")

print("\n--- Test Complete ---")
