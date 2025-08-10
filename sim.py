import serial
import time
import threading
import random
from dataclasses import dataclass
from typing import Optional

@dataclass
class FencingState:
    left_score: int = 0
    right_score: int = 0
    minutes: int = 3
    seconds: int = 0
    lights: int = 0  # Bit field for lights
    matches: int = 1
    cards: int = 0
    timer_running: bool = False

class FA5Simulator:
    def __init__(self, virtual_port_name='FENCING_SIM'):
        self.state = FencingState()
        self.running = False
        self.thread = None
        
        # Create virtual serial ports (Windows: use com0com, Linux: socat)
        self.sim_port = None
        self.client_port_name = None
        
        print("🤺 FA5 Scoring Machine Simulator")
        print("📡 This simulates a real FA5 sending data packets")
    
    def create_packet(self) -> bytes:
        """Create a 10-byte FA5 packet from current state"""
        packet = bytearray(10)
        
        # Byte 0: Start marker (always 0xFF)
        packet[0] = 0xFF
        
        # Byte 1: Right fencer score
        packet[1] = self.state.right_score
        
        # Byte 2: Left fencer score  
        packet[2] = self.state.left_score
        
        # Byte 3: Seconds
        packet[3] = self.state.seconds
        
        # Byte 4: Minutes
        packet[4] = self.state.minutes
        
        # Byte 5: Light states
        packet[5] = self.state.lights
        
        # Byte 6: Matches and priority
        packet[6] = self.state.matches
        
        # Byte 7: Always 0x00
        packet[7] = 0x00
        
        # Byte 8: Penalty cards
        packet[8] = self.state.cards
        
        # Byte 9: Checksum (sum of bytes 0-8 mod 256)
        packet[9] = sum(packet[:9]) % 256
        
        return bytes(packet)
    
    def print_packet_info(self, packet: bytes):
        """Print human-readable packet information"""
        print(f"📦 Packet: {' '.join(f'{b:02X}' for b in packet)}")
        print(f"   Timer: {self.state.minutes}:{self.state.seconds:02d}")
        print(f"   Scores: L{self.state.left_score} - R{self.state.right_score}")
        
        # Decode lights
        lights = self.state.lights
        light_status = []
        if lights & 0x01: light_status.append("Left White")
        if lights & 0x02: light_status.append("Right White") 
        if lights & 0x04: light_status.append("RED (Left Hit)")
        if lights & 0x08: light_status.append("GREEN (Right Hit)")
        if lights & 0x10: light_status.append("Right Yellow")
        if lights & 0x20: light_status.append("Left Yellow")
        
        print(f"   Lights: {', '.join(light_status) if light_status else 'None'}")
        print()
    
    def start_timer(self):
        """Start the bout timer"""
        self.state.timer_running = True
        print("🟢 Timer started - ACTION BEGINS!")
    
    def stop_timer(self):
        """Stop the bout timer"""
        self.state.timer_running = False
        print("🔴 Timer stopped")
    
    def simulate_hit(self, fencer: str, hit_type: str = "valid"):
        """Simulate a hit by a fencer"""
        if fencer.lower() == "left":
            if hit_type == "valid":
                self.state.lights = 0x04  # Red light (bit 2)
                self.state.left_score += 1
                print("⚔️ LEFT FENCER HIT! (Red light)")
            else:  # off-target
                self.state.lights = 0x01  # Left white light (bit 0)
                print("⚪ Left fencer off-target")
        
        elif fencer.lower() == "right":
            if hit_type == "valid":
                self.state.lights = 0x08  # Green light (bit 3)  
                self.state.right_score += 1
                print("⚔️ RIGHT FENCER HIT! (Green light)")
            else:  # off-target
                self.state.lights = 0x02  # Right white light (bit 1)
                print("⚪ Right fencer off-target")
    
    def simulate_double_hit(self):
        """Simulate both fencers hitting simultaneously"""
        self.state.lights = 0x0C  # Both red and green (bits 2+3)
        # In sabre, usually one gets the point based on right-of-way
        if random.choice([True, False]):
            self.state.left_score += 1
            print("⚔️⚔️ DOUBLE HIT! Left fencer gets point (right-of-way)")
        else:
            self.state.right_score += 1  
            print("⚔️⚔️ DOUBLE HIT! Right fencer gets point (right-of-way)")
    
    def clear_lights(self):
        """Clear all lights (rearm)"""
        self.state.lights = 0
        print("💡 Lights cleared (rearm)")
    
    def tick_timer(self):
        """Advance timer by one second"""
        if self.state.timer_running:
            if self.state.seconds > 0:
                self.state.seconds -= 1
            elif self.state.minutes > 0:
                self.state.minutes -= 1
                self.state.seconds = 59
            else:
                # Time expired
                self.state.timer_running = False
                print("⏰ TIME EXPIRED!")
    
    def reset_bout(self):
        """Reset for new bout"""
        self.state = FencingState()
        print("🔄 Bout reset")
    
    def run_simulation_loop(self, output_file: str = None):
        """Run the main simulation sending packets"""
        print(f"🚀 Starting FA5 simulation...")
        
        if output_file:
            # Write to file for testing
            with open(output_file, 'wb') as f:
                while self.running:
                    packet = self.create_packet()
                    f.write(packet)
                    f.flush()
                    
                    self.print_packet_info(packet)
                    self.tick_timer()
                    time.sleep(1)  # Send packet every second
        else:
            # Just print packets for debugging
            while self.running:
                packet = self.create_packet()
                self.print_packet_info(packet)
                self.tick_timer()
                time.sleep(1)
    
    def start(self, output_file: str = None):
        """Start the simulator"""
        self.running = True
        self.thread = threading.Thread(target=self.run_simulation_loop, args=(output_file,))
        self.thread.start()
        
    def stop(self):
        """Stop the simulator"""
        self.running = False
        if self.thread:
            self.thread.join()

def interactive_simulation():
    """Interactive mode to manually control the simulator"""
    sim = FA5Simulator()
    
    print("\n🎮 Interactive FA5 Simulator")
    print("Commands:")
    print("  start - Start timer")
    print("  stop - Stop timer") 
    print("  left - Left fencer valid hit")
    print("  right - Right fencer valid hit")
    print("  leftoff - Left fencer off-target")
    print("  rightoff - Right fencer off-target")
    print("  double - Double hit")
    print("  clear - Clear lights")
    print("  reset - Reset bout")
    print("  auto - Run automatic bout simulation")
    print("  quit - Exit")
    print()
    
    while True:
        try:
            cmd = input("FA5> ").strip().lower()
            
            if cmd == "quit" or cmd == "q":
                break
            elif cmd == "start":
                sim.start_timer()
            elif cmd == "stop":
                sim.stop_timer()
            elif cmd == "left":
                sim.simulate_hit("left", "valid")
            elif cmd == "right":
                sim.simulate_hit("right", "valid")
            elif cmd == "leftoff":
                sim.simulate_hit("left", "off-target")
            elif cmd == "rightoff":
                sim.simulate_hit("right", "off-target")
            elif cmd == "double":
                sim.simulate_double_hit()
            elif cmd == "clear":
                sim.clear_lights()
            elif cmd == "reset":
                sim.reset_bout()
            elif cmd == "auto":
                run_automatic_bout(sim)
            elif cmd == "packet":
                packet = sim.create_packet()
                sim.print_packet_info(packet)
            else:
                print("❌ Unknown command")
                
        except KeyboardInterrupt:
            break
    
    print("👋 Simulator stopped")

def run_automatic_bout(sim: FA5Simulator):
    """Run a realistic automatic bout simulation"""
    print("\n🤖 Running automatic bout simulation...")
    
    # Reset and start
    sim.reset_bout()
    time.sleep(1)
    
    print("En garde... Ready... Fence!")
    sim.start_timer()
    
    # Simulate a realistic bout with multiple exchanges
    exchanges = [
        (3, "left", "valid"),      # Left hits after 3 seconds
        (2, "clear", None),        # Clear lights
        (4, "right", "off-target"), # Right off-target
        (1, "clear", None),        # Clear
        (5, "double", None),       # Double hit
        (2, "clear", None),        # Clear
        (6, "right", "valid"),     # Right scores
        (3, "clear", None),        # Clear
        (4, "left", "valid"),      # Left scores
        (2, "stop", None),         # Halt
    ]
    
    for delay, action, target in exchanges:
        time.sleep(delay)
        
        if action == "left":
            sim.simulate_hit("left", target)
        elif action == "right":
            sim.simulate_hit("right", target)
        elif action == "double":
            sim.simulate_double_hit()
        elif action == "clear":
            sim.clear_lights()
        elif action == "stop":
            sim.stop_timer()
    
    print("🏁 Automatic bout simulation complete!")

def create_test_data_file():
    """Create a binary file with test FA5 packets for debugging"""
    filename = "fa5_test_data.bin"
    
    sim = FA5Simulator()
    packets = []
    
    # Create various test scenarios
    scenarios = [
        # Timer counting down
        (3, 0, 0, 0, 0),  # 3:00, no lights
        (2, 59, 0, 0, 0), # 2:59, no lights  
        (2, 58, 0, 0, 0), # 2:58, no lights
        
        # Left fencer hits
        (2, 57, 1, 0, 0x04), # Red light, left scores
        (2, 57, 1, 0, 0x00), # Lights cleared
        
        # Right fencer hits  
        (2, 55, 1, 1, 0x08), # Green light, right scores
        (2, 55, 1, 1, 0x00), # Lights cleared
        
        # Double hit
        (2, 50, 2, 1, 0x0C), # Both lights
        (2, 50, 2, 1, 0x00), # Cleared
    ]
    
    with open(filename, 'wb') as f:
        for minutes, seconds, left_score, right_score, lights in scenarios:
            sim.state.minutes = minutes
            sim.state.seconds = seconds  
            sim.state.left_score = left_score
            sim.state.right_score = right_score
            sim.state.lights = lights
            
            packet = sim.create_packet()
            f.write(packet)
            packets.append(packet)
    
    print(f"📁 Created test data file: {filename}")
    print(f"   Contains {len(packets)} packets ({len(packets) * 10} bytes)")
    
    return filename

def main():
    print("🤺 FA5 Simulator - Choose mode:")
    print("1. Interactive mode (manual control)")
    print("2. Create test data file")
    print("3. Automatic bout simulation")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        interactive_simulation()
    elif choice == "2":
        create_test_data_file()
    elif choice == "3":
        sim = FA5Simulator()
        run_automatic_bout(sim)
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()