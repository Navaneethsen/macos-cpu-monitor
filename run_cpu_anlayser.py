#!/usr/bin/env python3
"""
CPU Monitor - Background process to monitor specific processes and capture evidence
when they consume high CPU usage individually.
"""

import subprocess
import time
import os
import json
from datetime import datetime
from pathlib import Path
import logging
import statistics
from collections import deque

# Configuration
PROCESS_NAMES = [
    "abcd_enterprise",
    "silverbullet", 
    "com.xyz.SecurityExtension",
    "1234daemon",
    "fryGPS"  
    # Add more as needed
]

CPU_THRESHOLD = 95.0  # Percentage threshold
CHECK_INTERVAL = 30   # Seconds between checks
MONITORING_WINDOW = 300  # Seconds (5 minutes) to collect data before checking median
EVIDENCE_FOLDER = "cpu_evidence"
LOG_FILE = "cpu_monitor.log"

# Setup logging - reduced verbosity for background operation
logging.basicConfig(
    level=logging.WARNING,  # Only log warnings and errors by default
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        # Remove StreamHandler for background operation
    ]
)

# Add a separate logger for periodic status updates
status_logger = logging.getLogger('status')
status_logger.setLevel(logging.INFO)
status_handler = logging.FileHandler(LOG_FILE)
status_handler.setFormatter(logging.Formatter('%(asctime)s - STATUS - %(message)s'))
status_logger.addHandler(status_handler)

class CPUMonitor:
    def __init__(self):
        self.evidence_folder = Path(EVIDENCE_FOLDER)
        self.evidence_folder.mkdir(exist_ok=True)
        
        # Data collection for median calculation - separate tracking per process
        self.process_readings = {}  # Dict to store readings per process name
        self.monitoring_start_time = None
        self.max_readings = MONITORING_WINDOW // CHECK_INTERVAL  # Maximum readings to keep
        
        # Track when monitoring window started for each process (non-overlapping windows)
        self.process_window_start = {}
        
        # Initialize deques for each monitored process
        for process_name in PROCESS_NAMES:
            self.process_readings[process_name] = deque()
            self.process_window_start[process_name] = None
        
    def get_process_cpu_usage(self):
        """Get CPU usage for monitored processes using ps command"""
        try:
            # Use ps to get process info: PID, CPU%, Command
            cmd = ["ps", "-A", "-o", "pid,pcpu,comm"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            processes = {}
            process_cpu_totals = {}  # Track total CPU per process type
            
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.strip().split(None, 2)
                if len(parts) >= 3:
                    pid, cpu_percent, command = parts[0], parts[1], parts[2]
                    
                    try:
                        cpu_val = float(cpu_percent)
                        
                        # Check if this process matches any of our monitored names
                        for process_name in PROCESS_NAMES:
                            if process_name.lower() in command.lower():
                                if process_name not in processes:
                                    processes[process_name] = []
                                    process_cpu_totals[process_name] = 0.0
                                
                                processes[process_name].append({
                                    'pid': pid,
                                    'cpu': cpu_val,
                                    'command': command
                                })
                                process_cpu_totals[process_name] += cpu_val
                                break
                                
                    except ValueError:
                        continue
            
            # Ensure all monitored processes have entries (even if 0 CPU)
            for process_name in PROCESS_NAMES:
                if process_name not in process_cpu_totals:
                    process_cpu_totals[process_name] = 0.0
                        
            return processes, process_cpu_totals
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Error getting process info: {e}")
            return {}, {process_name: 0.0 for process_name in PROCESS_NAMES}
    
    def get_detailed_cpu_info(self):
        """Get detailed CPU information using top command"""
        try:
            # Use top to get more detailed CPU info
            cmd = ["top", "-l", "1", "-n", "0"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"Error getting detailed CPU info: {e}")
            return "Error retrieving detailed CPU information"
    
    def take_activity_monitor_screenshot(self, timestamp_str):
        """Screenshots disabled - not reliable when screen is locked"""
        logging.info("Screenshot functionality disabled (not reliable when screen is locked)")
        return None
    
    def save_cpu_data_with_process_medians(self, processes, process_cpu_totals, process_medians, 
                                         triggering_processes, detailed_info, timestamp_str):
        """Save CPU data with individual process median information to JSON file in Hive partition structure"""
        data = {
            'timestamp': timestamp_str,
            'triggering_processes': triggering_processes,
            'process_cpu_totals': process_cpu_totals,
            'process_medians': process_medians,
            'monitoring_window_seconds': MONITORING_WINDOW,
            'processes': processes,
            'detailed_cpu_info': detailed_info,
            'threshold': CPU_THRESHOLD
        }
        
        # Add individual process readings for each triggering process
        for process_name in triggering_processes:
            if process_name in self.process_readings:
                readings = list(self.process_readings[process_name])
                cpu_values = [reading['cpu'] for reading in readings]
                data[f'{process_name}_readings'] = {
                    'cpu_values': cpu_values,
                    'min_cpu': min(cpu_values) if cpu_values else 0,
                    'max_cpu': max(cpu_values) if cpu_values else 0,
                    'avg_cpu': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'readings_count': len(cpu_values)
                }
        
        # Create Hive-style partition path: yyyy/mm/dd/hh
        timestamp_obj = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        partition_path = self.evidence_folder / f"{timestamp_obj.year:04d}" / f"{timestamp_obj.month:02d}" / f"{timestamp_obj.day:02d}" / f"{timestamp_obj.hour:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)
        
        json_path = partition_path / f"cpu_data_{timestamp_str}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logging.info(f"CPU data with process medians saved: {json_path}")
        return str(json_path)
    
    def create_summary_report_with_process_medians(self, processes, process_cpu_totals, process_medians,
                                                 triggering_processes, timestamp_str):
        """Create a human-readable summary report with individual process median information in Hive partition structure"""
        # Create Hive-style partition path: yyyy/mm/dd/hh
        timestamp_obj = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        partition_path = self.evidence_folder / f"{timestamp_obj.year:04d}" / f"{timestamp_obj.month:02d}" / f"{timestamp_obj.day:02d}" / f"{timestamp_obj.hour:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)
        
        report_path = partition_path / f"report_{timestamp_str}.txt"
        
        with open(report_path, 'w') as f:
            f.write(f"CPU Usage Alert Report (Individual Process Monitoring)\n")
            f.write(f"=" * 60 + "\n")
            f.write(f"Timestamp: {timestamp_str}\n")
            f.write(f"Alert triggered by individual process median CPU usage over {MONITORING_WINDOW}s ({MONITORING_WINDOW//60} minutes)\n\n")
            
            f.write("Triggering Processes:\n")
            f.write("-" * 40 + "\n")
            for process_name in triggering_processes:
                median_cpu = process_medians.get(process_name, 0)
                current_cpu = process_cpu_totals.get(process_name, 0)
                f.write(f"{process_name.upper()}:\n")
                f.write(f"  Current CPU: {current_cpu:.1f}%\n")
                f.write(f"  Median CPU: {median_cpu:.1f}%\n")
                f.write(f"  Threshold: {CPU_THRESHOLD}%\n\n")
            
            f.write("All Process Statistics:\n")
            f.write("-" * 40 + "\n")
            for process_name in PROCESS_NAMES:
                median_cpu = process_medians.get(process_name, 0)
                current_cpu = process_cpu_totals.get(process_name, 0)
                status = "⚠️  ALERT" if process_name in triggering_processes else "✅ Normal"
                f.write(f"{process_name.upper()}: Current: {current_cpu:.1f}%, Median: {median_cpu:.1f}% - {status}\n")
            
            f.write(f"\nThreshold: {CPU_THRESHOLD}%\n\n")
            
            # Show detailed readings for triggering processes
            for process_name in triggering_processes:
                if process_name in self.process_readings:
                    readings = list(self.process_readings[process_name])
                    cpu_values = [reading['cpu'] for reading in readings]
                    if cpu_values:
                        f.write(f"{process_name.upper()} - All CPU Readings:\n")
                        f.write("-" * 30 + "\n")
                        for i, cpu_val in enumerate(cpu_values, 1):
                            f.write(f"  Reading {i}: {cpu_val:.1f}%\n")
                        f.write("\n")
            
            f.write("Current Process Details:\n")
            f.write("-" * 30 + "\n")
            
            if processes:
                for process_name, instances in processes.items():
                    if instances:  # Only show processes that are currently running
                        f.write(f"\n{process_name.upper()}:\n")
                        for instance in instances:
                            f.write(f"  PID: {instance['pid']}, CPU: {instance['cpu']}%, Command: {instance['command']}\n")
            else:
                f.write("No monitored processes currently running\n")
        
        logging.info(f"Summary report with process medians saved: {report_path}")
        return str(report_path)
    
    def monitor(self):
        """Main monitoring loop with individual process median-based triggering"""
        status_logger.info(f"Starting CPU monitor for processes: {', '.join(PROCESS_NAMES)}")
        status_logger.info(f"Individual process threshold: {CPU_THRESHOLD}%, Check interval: {CHECK_INTERVAL}s")
        status_logger.info(f"Monitoring window: {MONITORING_WINDOW}s ({MONITORING_WINDOW//60} minutes)")
        status_logger.info(f"Evidence folder: {self.evidence_folder.absolute()}")
        
        self.monitoring_start_time = datetime.now()
        last_status_log = datetime.now()
        status_log_interval = 3600  # Log status every hour
        
        while True:
            try:
                processes, process_cpu_totals = self.get_process_cpu_usage()
                current_time = datetime.now()
                
                # Add current readings to each process's deque with non-overlapping window logic
                for process_name in PROCESS_NAMES:
                    cpu_usage = process_cpu_totals.get(process_name, 0.0)
                    
                    # Initialize window start time if not set
                    if self.process_window_start[process_name] is None:
                        self.process_window_start[process_name] = current_time
                    
                    self.process_readings[process_name].append({
                        'timestamp': current_time,
                        'cpu': cpu_usage
                    })
                    
                    # Remove old readings (keep only readings within current monitoring window)
                    window_start = self.process_window_start[process_name]
                    while (self.process_readings[process_name] and 
                           self.process_readings[process_name][0]['timestamp'] < window_start):
                        self.process_readings[process_name].popleft()
                    
                    # Also limit by max number of readings to prevent memory issues
                    while len(self.process_readings[process_name]) > self.max_readings:
                        self.process_readings[process_name].popleft()
                
                # Check if we have enough data to calculate medians for each process
                process_medians = {}
                triggering_processes = []
                
                for process_name in PROCESS_NAMES:
                    readings = list(self.process_readings[process_name])
                    window_start = self.process_window_start[process_name]
                    
                    # Check if we have completed a full monitoring window
                    window_duration = (current_time - window_start).total_seconds() if window_start else 0
                    
                    if len(readings) >= 3 and window_duration >= MONITORING_WINDOW:
                        # We have a complete monitoring window - calculate median
                        cpu_values = [reading['cpu'] for reading in readings]
                        median_cpu = statistics.median(cpu_values)
                        process_medians[process_name] = median_cpu
                        
                        # Check if this process exceeds threshold
                        if median_cpu >= CPU_THRESHOLD:
                            triggering_processes.append(process_name)
                    else:
                        # Still collecting data for this window
                        if len(readings) > 0:
                            cpu_values = [reading['cpu'] for reading in readings]
                            process_medians[process_name] = statistics.median(cpu_values)
                        else:
                            process_medians[process_name] = 0.0
                
                # Periodic status logging (every hour)
                if (current_time - last_status_log).total_seconds() >= status_log_interval:
                    elapsed_time = (current_time - self.monitoring_start_time).total_seconds()
                    status_msg = f"Status - Runtime: {elapsed_time/3600:.1f}h | "
                    for process_name in PROCESS_NAMES:
                        current_cpu = process_cpu_totals.get(process_name, 0)
                        median_cpu = process_medians.get(process_name, 0)
                        readings_count = len(self.process_readings[process_name])
                        window_start = self.process_window_start[process_name]
                        window_duration = (current_time - window_start).total_seconds() if window_start else 0
                        status_msg += f"{process_name}: {current_cpu:.1f}%/{median_cpu:.1f}% ({readings_count}r, {window_duration:.0f}s) | "
                    status_logger.info(status_msg.rstrip(" | "))
                    last_status_log = current_time
                
                # Trigger alert if any process exceeds threshold
                if triggering_processes:
                    timestamp_str = current_time.strftime("%Y%m%d_%H%M%S")
                    
                    logging.warning(f"HIGH CPU ALERT! Processes exceeding {CPU_THRESHOLD}% median over {MONITORING_WINDOW}s:")
                    for process_name in triggering_processes:
                        median_cpu = process_medians[process_name]
                        current_cpu = process_cpu_totals.get(process_name, 0)
                        logging.warning(f"  {process_name}: Current: {current_cpu:.1f}%, Median: {median_cpu:.1f}%")
                    
                    # Get detailed CPU information
                    detailed_info = self.get_detailed_cpu_info()
                    
                    # Save evidence with individual process information
                    json_path = self.save_cpu_data_with_process_medians(processes, process_cpu_totals, process_medians,
                                                                      triggering_processes, detailed_info, timestamp_str)
                    report_path = self.create_summary_report_with_process_medians(processes, process_cpu_totals, process_medians,
                                                                                triggering_processes, timestamp_str)
                    screenshot_path = self.take_activity_monitor_screenshot(timestamp_str)
                    
                    logging.warning("Evidence captured:")
                    logging.warning(f"  - Data: {json_path}")
                    logging.warning(f"  - Report: {report_path}")
                    if screenshot_path:
                        logging.warning(f"  - Screenshot: {screenshot_path}")
                    
                    # Start fresh monitoring window for triggering processes after capturing evidence
                    for process_name in triggering_processes:
                        self.process_readings[process_name].clear()
                        self.process_window_start[process_name] = current_time
                        logging.info(f"Started new monitoring window for {process_name} at {current_time}")
                    
                    last_status_log = current_time  # Reset status log timer
                
                # Sleep with lower priority to reduce CPU usage
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                status_logger.info("Monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(CHECK_INTERVAL)

def main():
    """Entry point"""
    monitor = CPUMonitor()
    
    # Create evidence folder if it doesn't exist
    if not monitor.evidence_folder.exists():
        monitor.evidence_folder.mkdir(parents=True)
        print(f"Created evidence folder: {monitor.evidence_folder.absolute()}")
    
    print(f"CPU Monitor starting...")
    print(f"Monitoring processes individually: {', '.join(PROCESS_NAMES)}")
    print(f"Individual process threshold: {CPU_THRESHOLD}%")
    print(f"Evidence will be saved to: {monitor.evidence_folder.absolute()}")
    print("Press Ctrl+C to stop")
    
    monitor.monitor()

if __name__ == "__main__":
    main()
