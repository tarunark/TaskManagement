import json
import win32evtlog
import win32evtlogutil
import win32con
from datetime import datetime, timedelta
from pathlib import Path
import time
import threading
import sys
import os

class ActivityMonitor:
    def __init__(self, log_file="activity_log.json"):
        self.log_file = log_file
        self.events = self.load_events()
        self.last_event_time = self.get_last_event_time()
        self.event_map = {
            4624: "login",      # Successful logon
            4647: "logout",     # User initiated logoff
            4800: "lock",       # Workstation locked
            4801: "unlock",     # Workstation unlocked
            4609: "shutdown",   # System shutdown
            1074: "reboot",     # System has been shutdown/reboot
            6005: "startup",    # Event log service started (after boot)
            6006: "shutdown_log", # Event log service stopped
        }
    
    def load_events(self):
        """Load existing events from JSON file"""
        if Path(self.log_file).exists():
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Warning: Could not read log file. Starting fresh.")
                return []
        return []
    
    def get_last_event_time(self):
        """Get timestamp of the last logged event"""
        if self.events:
            return datetime.fromisoformat(self.events[-1]['timestamp'])
        return None
    
    def save_events(self):
        """Save events to JSON file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.events, f, indent=2)
        except Exception as e:
            print(f"Error saving events: {e}")
    
    def log_event(self, event_type, timestamp=None):
        """Log an event with timestamp"""
        if timestamp is None:
            timestamp = datetime.now()
        
        event = {
            "type": event_type,
            "timestamp": timestamp.isoformat()
        }
        self.events.append(event)
        self.save_events()
        print(f"Logged: {event_type} at {timestamp}")
    
    def check_missed_events(self):
        """Check for missed shutdown/reboot when script starts"""
        if not self.last_event_time:
            return
        
        # Check if there's been a system restart since last event
        server = 'localhost'
        logtype = 'System'
        hand = win32evtlog.OpenEventLog(server, logtype)
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        
        events = win32evtlog.ReadEventLog(hand, flags, 0)
        
        for event in events[:100]:  # Check last 100 system events
            if event.EventID == 6005:  # System startup
                startup_time = event.TimeGenerated
                if startup_time > self.last_event_time:
                    # System was restarted after our last event
                    # Log a shutdown event just before startup
                    shutdown_time = startup_time - timedelta(seconds=30)
                    
                    # Check if we haven't already logged this
                    if not self.is_duplicate("reboot", shutdown_time):
                        print(f"Detected missed reboot at {shutdown_time}")
                        self.log_event("reboot", shutdown_time)
                        self.log_event("startup", startup_time)
                    break
        
        win32evtlog.CloseEventLog(hand)
    
    def monitor(self, stop_event):
        """Monitor Windows event log for activity events"""
        # Check for missed events first
        self.check_missed_events()
        
        server = 'localhost'
        logtype = 'Security'
        hand = win32evtlog.OpenEventLog(server, logtype)
        flags = win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        
        # Also monitor system log for startup/shutdown
        system_hand = win32evtlog.OpenEventLog(server, 'System')
        
        print("Monitoring started. Press Ctrl+C to stop.")
        print("This monitor will track:")
        print("  - Login/Logout events")
        print("  - Lock/Unlock events")
        print("  - Shutdown/Reboot events")
        
        while not stop_event.is_set():
            # Check Security log
            events = win32evtlog.ReadEventLog(hand, flags, 0)
            
            if events:
                for event in events:
                    if event.EventID in self.event_map:
                        event_type = self.event_map[event.EventID]
                        timestamp = event.TimeGenerated
                        
                        if not self.is_duplicate(event_type, timestamp):
                            self.log_event(event_type, timestamp)
            
            # Check System log for startup/shutdown
            system_events = win32evtlog.ReadEventLog(system_hand, flags, 0)
            if system_events:
                for event in system_events:
                    if event.EventID in [6005, 6006, 1074]:
                        event_type = self.event_map.get(event.EventID, "unknown")
                        timestamp = event.TimeGenerated
                        
                        if not self.is_duplicate(event_type, timestamp):
                            self.log_event(event_type, timestamp)
            
            time.sleep(2)  # Check every 2 seconds
        
        win32evtlog.CloseEventLog(hand)
        win32evtlog.CloseEventLog(system_hand)
    
    def is_duplicate(self, event_type, timestamp):
        """Check if event already exists (within 5 second window)"""
        timestamp_str = timestamp.isoformat()
        for event in self.events[-20:]:  # Only check recent events for performance
            if (event['type'] == event_type and 
                abs((datetime.fromisoformat(event['timestamp']) - timestamp).total_seconds()) < 5):
                return True
        return False
    
    def calculate_hours(self, start_date=None, end_date=None):
        """Calculate working hours between login/unlock and logout/lock/shutdown/reboot events"""
        events = sorted(self.events, key=lambda x: x['timestamp'])
        
        if start_date:
            events = [e for e in events if datetime.fromisoformat(e['timestamp']).date() >= start_date]
        if end_date:
            events = [e for e in events if datetime.fromisoformat(e['timestamp']).date() <= end_date]
        
        total_hours = 0
        active_start = None
        sessions = []
        
        for event in events:
            event_time = datetime.fromisoformat(event['timestamp'])
            event_type = event['type']
            
            # Start counting on login, unlock, or startup
            if event_type in ['login', 'unlock', 'startup'] and active_start is None:
                active_start = event_time
            # Stop counting on logout, lock, shutdown, or reboot
            elif event_type in ['logout', 'lock', 'shutdown', 'reboot', 'shutdown_log'] and active_start:
                duration = (event_time - active_start).total_seconds() / 3600
                total_hours += duration
                sessions.append({
                    'start': active_start,
                    'end': event_time,
                    'duration': duration
                })
                active_start = None
        
        # If still active, count until now
        if active_start:
            duration = (datetime.now() - active_start).total_seconds() / 3600
            total_hours += duration
            sessions.append({
                'start': active_start,
                'end': datetime.now(),
                'duration': duration,
                'ongoing': True
            })
        
        return total_hours, sessions
    
    def get_daily_summary(self, date=None):
        """Get summary for a specific day"""
        if date is None:
            date = datetime.now().date()
        
        hours, sessions = self.calculate_hours(start_date=date, end_date=date)
        return {
            "date": date.isoformat(),
            "hours": round(hours, 2),
            "sessions": len(sessions),
            "session_details": [
                {
                    "start": s['start'].strftime('%H:%M:%S'),
                    "end": s['end'].strftime('%H:%M:%S'),
                    "duration": round(s['duration'], 2),
                    "ongoing": s.get('ongoing', False)
                } for s in sessions
            ]
        }
    
    def get_weekly_summary(self, date=None):
        """Get summary for the week containing the given date"""
        if date is None:
            date = datetime.now().date()
        
        # Find Monday of the week
        start_of_week = date - timedelta(days=date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        hours, _ = self.calculate_hours(start_date=start_of_week, end_date=end_of_week)
        
        # Daily breakdown
        daily = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_hours, _ = self.calculate_hours(start_date=day, end_date=day)
            daily[day.strftime('%A (%Y-%m-%d)')] = round(day_hours, 2)
        
        return {
            "week_start": start_of_week.isoformat(),
            "week_end": end_of_week.isoformat(),
            "total_hours": round(hours, 2),
            "daily_breakdown": daily
        }
    
    def show_statistics(self):
        """Display statistics menu"""
        while True:
            print("\n=== Activity Statistics ===")
            print("1. Today's hours")
            print("2. This week's hours")
            print("3. Custom date range")
            print("4. View recent events")
            print("5. Export to CSV")
            print("6. Back to main menu")
            
            choice = input("\nChoose an option: ")
            
            if choice == '1':
                summary = self.get_daily_summary()
                print(f"\nDate: {summary['date']}")
                print(f"Hours worked: {summary['hours']:.2f}")
                print(f"Number of sessions: {summary['sessions']}")
                if summary['session_details']:
                    print("\nSessions:")
                    for i, session in enumerate(summary['session_details'], 1):
                        status = " (ongoing)" if session['ongoing'] else ""
                        print(f"  {i}. {session['start']} - {session['end']}: {session['duration']:.2f}h{status}")
            
            elif choice == '2':
                summary = self.get_weekly_summary()
                print(f"\nWeek: {summary['week_start']} to {summary['week_end']}")
                print(f"Total hours: {summary['total_hours']:.2f}")
                print("\nDaily breakdown:")
                for day, hours in summary['daily_breakdown'].items():
                    print(f"  {day}: {hours:.2f} hours")
            
            elif choice == '3':
                try:
                    start = input("Start date (YYYY-MM-DD): ")
                    end = input("End date (YYYY-MM-DD): ")
                    start_date = datetime.strptime(start, '%Y-%m-%d').date()
                    end_date = datetime.strptime(end, '%Y-%m-%d').date()
                    hours, sessions = self.calculate_hours(start_date, end_date)
                    print(f"\nHours worked from {start} to {end}: {hours:.2f}")
                    print(f"Number of sessions: {len(sessions)}")
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD")
            
            elif choice == '4':
                print("\nRecent events (last 30):")
                for event in self.events[-30:]:
                    print(f"  {event['timestamp']}: {event['type']}")
            
            elif choice == '5':
                self.export_to_csv()
            
            elif choice == '6':
                break
    
    def export_to_csv(self):
        """Export events to CSV file"""
        import csv
        csv_file = self.log_file.replace('.json', '.csv')
        
        try:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Event Type'])
                for event in self.events:
                    writer.writerow([event['timestamp'], event['type']])
            print(f"\nEvents exported to {csv_file}")
        except Exception as e:
            print(f"Error exporting to CSV: {e}")


def create_startup_script():
    """Create a batch file to run this script on startup"""
    script_path = os.path.abspath(__file__)
    batch_content = f'''@echo off
cd /d "{os.path.dirname(script_path)}"
python "{script_path}" --monitor
'''
    
    batch_file = "start_monitor.bat"
    with open(batch_file, 'w') as f:
        f.write(batch_content)
    
    print(f"\nStartup script created: {batch_file}")
    print("To run on startup:")
    print(f"1. Press Win+R, type 'shell:startup', press Enter")
    print(f"2. Copy {batch_file} to the Startup folder")
    print("3. The monitor will start automatically on login")


def main():
    monitor = ActivityMonitor()
    
    # Check if running in monitor mode (from startup)
    if len(sys.argv) > 1 and sys.argv[1] == '--monitor':
        stop_event = threading.Event()
        try:
            monitor.monitor(stop_event)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
        return
    
    while True:
        print("\n=== Windows Activity Monitor ===")
        print("1. Start monitoring (foreground)")
        print("2. View statistics")
        print("3. Create startup script")
        print("4. Exit")
        
        choice = input("\nChoose an option: ")
        
        if choice == '1':
            stop_event = threading.Event()
            monitor_thread = threading.Thread(target=monitor.monitor, args=(stop_event,))
            monitor_thread.start()
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping monitor...")
                stop_event.set()
                monitor_thread.join()
        
        elif choice == '2':
            monitor.show_statistics()
        
        elif choice == '3':
            create_startup_script()
        
        elif choice == '4':
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()