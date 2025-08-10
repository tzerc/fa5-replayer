import cv2
import serial
import time
import threading
import os
from collections import deque
from datetime import datetime
import numpy as np

class FencingVideoRecorder:
    def __init__(self, serial_port='COM3', baud_rate=9600, camera_index=0):
        # Serial connection to FA5 scoring machine
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.fa5_serial = None
        
        # Video capture
        self.camera = cv2.VideoCapture(camera_index)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        
        # Rolling buffer to store last 60 seconds of video
        self.video_buffer = deque(maxlen=1800)  # 30fps * 60 seconds
        
        # State tracking
        self.last_timer = None
        self.recording_start_time = None
        self.currently_recording = False
        self.last_packet = None
        
        # Threading control
        self.running = False
        self.video_thread = None
        self.serial_thread = None
        
        # Output directory
        self.output_dir = "fencing_clips"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("🤺 Fencing Video Recorder Initialized")
        print(f"📁 Clips will be saved to: {self.output_dir}")
    
    def connect_scoring_machine(self):
        """Connect to FA5 scoring machine via serial"""
        try:
            self.fa5_serial = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print(f"✅ Connected to FA5 on {self.serial_port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to FA5: {e}")
            return False
    
    def parse_favero_packet(self, packet):
        """Parse 10-byte Favero packet and return relevant data"""
        if len(packet) != 10 or packet[0] != 0xFF:
            return None
        
        # Verify checksum
        checksum = sum(packet[:9]) % 256
        if checksum != packet[9]:
            return None
        
        return {
            'right_score': packet[1],
            'left_score': packet[2], 
            'seconds': packet[3],
            'minutes': packet[4],
            'lights': packet[5],
            'matches': packet[6],
            'cards': packet[8]
        }
    
    def detect_clip_events(self, data):
        """Detect start/end of fencing action"""
        current_timer = (data['minutes'] * 60) + data['seconds']
        lights = data['lights']
        hit_detected = lights & 0x0C  # Red (bit 2) or Green (bit 3) lights
        
        # START: Timer counting down (time decreased)
        if (self.last_timer is not None and 
            current_timer < self.last_timer and 
            not self.currently_recording):
            
            self.recording_start_time = time.time()
            self.currently_recording = True
            print(f"⚔️ ACTION STARTED at {data['minutes']}:{data['seconds']:02d}")
        
        # END: Hit detected while recording
        elif hit_detected and self.currently_recording:
            clip_end_time = time.time()
            self.save_video_clip(self.recording_start_time, clip_end_time, data)
            self.currently_recording = False
            
        # TIMEOUT: Timer stopped but no hit (halt called)
        elif (self.last_timer == current_timer and 
              self.currently_recording and 
              time.time() - self.recording_start_time > 15):  # 15 second timeout
            
            clip_end_time = time.time()
            print("⏸️ Action timeout - saving clip anyway")
            self.save_video_clip(self.recording_start_time, clip_end_time, data)
            self.currently_recording = False
        
        self.last_timer = current_timer
    
    def save_video_clip(self, start_time, end_time, score_data):
        """Extract and save video clip from buffer"""
        clip_duration = end_time - start_time
        
        # Add 1 second buffer before and after
        buffer_start = start_time - 1.0
        buffer_end = end_time + 1.0
        
        # Find frames in time range
        clip_frames = []
        for frame, timestamp in self.video_buffer:
            if buffer_start <= timestamp <= buffer_end:
                clip_frames.append(frame)
        
        if len(clip_frames) < 10:  # Need at least 10 frames
            print("❌ Not enough frames for clip")
            return
        
        # Generate filename with timestamp and scores
        now = datetime.now()
        filename = f"clip_{now.strftime('%Y%m%d_%H%M%S')}_L{score_data['left_score']}_R{score_data['right_score']}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save video clip
        height, width = clip_frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(filepath, fourcc, 30.0, (width, height))
        
        for frame in clip_frames:
            out.write(frame)
        
        out.release()
        
        print(f"🎯 CLIP SAVED: {filename} ({clip_duration:.1f}s, {len(clip_frames)} frames)")
        print(f"   Scores - Left: {score_data['left_score']}, Right: {score_data['right_score']}")
        
        # Show lights that triggered save
        lights = score_data['lights']
        light_desc = []
        if lights & 0x04: light_desc.append("RED")
        if lights & 0x08: light_desc.append("GREEN") 
        if lights & 0x01: light_desc.append("Left Off-target")
        if lights & 0x02: light_desc.append("Right Off-target")
        print(f"   Lights: {', '.join(light_desc) if light_desc else 'None'}")
    
    def video_capture_loop(self):
        """Continuous video capture and buffering"""
        print("📹 Video capture started")
        
        while self.running:
            ret, frame = self.camera.read()
            if not ret:
                print("❌ Failed to read from camera")
                break
            
            # Add timestamp overlay
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (255, 255, 255), 2)
            
            # Add recording indicator
            if self.currently_recording:
                cv2.circle(frame, (width - 30, 30), 10, (0, 0, 255), -1)
                cv2.putText(frame, "REC", (width - 65, 35), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (0, 0, 255), 2)
            
            # Store frame with timestamp
            current_time = time.time()
            self.video_buffer.append((frame.copy(), current_time))
            
            # Display live feed (optional)
            height, width = frame.shape[:2]
            display_frame = cv2.resize(frame, (640, 360))  # Smaller for display
            cv2.imshow('Fencing Feed', display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.stop()
                break
    
    def serial_monitoring_loop(self):
        """Monitor FA5 serial data for scoring events"""
        print("📡 Serial monitoring started")
        
        while self.running and self.fa5_serial:
            try:
                if self.fa5_serial.in_waiting >= 10:
                    packet = self.fa5_serial.read(10)
                    data = self.parse_favero_packet(packet)
                    
                    if data and data != self.last_packet:
                        self.detect_clip_events(data)
                        self.last_packet = data
                        
            except Exception as e:
                print(f"❌ Serial error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start the recording system"""
        if not self.connect_scoring_machine():
            print("⚠️ Running without scoring machine (manual mode)")
        
        self.running = True
        
        # Start video capture thread
        self.video_thread = threading.Thread(target=self.video_capture_loop)
        self.video_thread.start()
        
        # Start serial monitoring thread (if connected)
        if self.fa5_serial:
            self.serial_thread = threading.Thread(target=self.serial_monitoring_loop)
            self.serial_thread.start()
        
        print("🚀 Fencing recorder started!")
        print("Press 'q' in video window to quit")
        
        # Manual control for testing without FA5
        if not self.fa5_serial:
            print("\n📝 Manual controls (no FA5 connected):")
            print("  's' - Start recording")
            print("  'e' - End recording") 
            print("  'q' - Quit")
            
            try:
                while self.running:
                    key = input().lower()
                    if key == 's':
                        if not self.currently_recording:
                            self.recording_start_time = time.time()
                            self.currently_recording = True
                            print("⚔️ Manual recording started")
                    elif key == 'e':
                        if self.currently_recording:
                            fake_data = {'left_score': 1, 'right_score': 0, 'lights': 0x04}
                            self.save_video_clip(self.recording_start_time, time.time(), fake_data)
                            self.currently_recording = False
                    elif key == 'q':
                        self.stop()
                        break
            except KeyboardInterrupt:
                self.stop()
    
    def stop(self):
        """Stop the recording system"""
        print("🛑 Stopping recorder...")
        self.running = False
        
        if self.video_thread:
            self.video_thread.join()
        
        if self.serial_thread:
            self.serial_thread.join()
        
        if self.fa5_serial:
            self.fa5_serial.close()
        
        self.camera.release()
        cv2.destroyAllWindows()
        print("✅ Recorder stopped")

def main():
    # Configuration
    SERIAL_PORT = 'COM3'  # Adjust for your system (Linux: '/dev/ttyUSB0')
    CAMERA_INDEX = 0      # Default webcam
    
    # Create and start recorder
    recorder = FencingVideoRecorder(
        serial_port=SERIAL_PORT,
        camera_index=CAMERA_INDEX
    )
    
    try:
        recorder.start()
    except KeyboardInterrupt:
        recorder.stop()

if __name__ == "__main__":
    main()
