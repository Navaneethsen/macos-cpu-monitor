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

def load_config(config_path="config.json"):
    """Load configuration from JSON file with fallback defaults"""
    default_config = {
        "process_names": [
            "java",
            "Docker", 
            "Virtual Machine Service for Docker",
            "IntelliJ IDEA",
            "Google Chrome",
            "Safari",
        ],
        "cpu_threshold": 95.0,
        "check_interval": 30,
        "monitoring_window": 300,
        "evidence_folder": "cpu_evidence",
        "log_file": "cpu_monitor.log"
    }
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Could not load config file {config_path}: {e}. Using defaults.")
        return default_config

# Load initial configuration
config = load_config()
PROCESS_NAMES = config["process_names"]
CPU_THRESHOLD = config["cpu_threshold"]
CHECK_INTERVAL = config["check_interval"]
MONITORING_WINDOW = config["monitoring_window"]
EVIDENCE_FOLDER = config["evidence_folder"]
LOG_FILE = config["log_file"]

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
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config_last_modified = 0
        
        # Data collection for median calculation - separate tracking per individual process instance
        self.process_readings = {}  # Dict to store readings per process instance (keyed by PID or command)
        self.monitoring_start_time = None
        
        # Track when monitoring window started for each process instance (non-overlapping windows)
        self.process_window_start = {}
        
        # Track active process instances by command
        self.active_processes = {}  # Dict to track currently running process instances
        
        # Load configuration and initialize process tracking
        self.reload_config()
        self.initialize_process_tracking()
    
    def reload_config(self):
        """Reload configuration if file has been modified"""
        try:
            current_modified = os.path.getmtime(self.config_path)
            if current_modified > self.config_last_modified:
                self.config = load_config(self.config_path)
                self.config_last_modified = current_modified
                
                # Update instance variables
                self.process_names = self.config["process_names"]
                self.cpu_threshold = self.config["cpu_threshold"]
                self.check_interval = self.config["check_interval"]
                self.monitoring_window = self.config["monitoring_window"]
                self.evidence_folder = Path(self.config["evidence_folder"])
                self.evidence_folder.mkdir(exist_ok=True)
                self.log_file = self.config["log_file"]
                
                # Recalculate max readings
                self.max_readings = self.monitoring_window // self.check_interval
                
                # Update process tracking for new/removed processes
                self.update_process_tracking()
                
                logging.info(f"Configuration reloaded from {self.config_path}")
                return True
        except (OSError, FileNotFoundError):
            pass
        return False
    
    def initialize_process_tracking(self):
        """Initialize tracking for all configured processes"""
        for process_name in self.process_names:
            if process_name not in self.process_readings:
                self.process_readings[process_name] = deque()
                self.process_window_start[process_name] = None
    
    def update_process_tracking(self):
        """Update process tracking when configuration changes"""
        # Add new processes
        for process_name in self.process_names:
            if process_name not in self.process_readings:
                self.process_readings[process_name] = deque()
                self.process_window_start[process_name] = None
                logging.info(f"Added monitoring for new process: {process_name}")
        
        # Remove processes no longer in config (optional - keep data for now)
        # This preserves historical data for processes that might be temporarily removed
        processes_to_remove = []
        for process_name in self.process_readings:
            if process_name not in self.process_names:
                processes_to_remove.append(process_name)
        
        for process_name in processes_to_remove:
            logging.info(f"Process {process_name} removed from monitoring (data preserved)")
        
    def get_process_cpu_usage(self):
        """Get CPU usage for monitored processes using ps command, tracking each instance separately"""
        try:
            # Use ps to get process info: PID, CPU%, Command with full command line
            cmd = ["ps", "-A", "-o", "pid,pcpu,args"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            individual_processes = {}  # Track each process instance separately
            process_groups = {}  # Group processes by name for compatibility
            
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                parts = line.strip().split(None, 2)
                if len(parts) >= 3:
                    pid, cpu_percent, full_command = parts[0], parts[1], parts[2]
                    
                    try:
                        cpu_val = float(cpu_percent)
                        
                        # Check if this process matches any of our monitored names
                        for process_name in self.process_names:
                            if process_name.lower() in full_command.lower():
                                # Create unique key for this process instance
                                process_key = f"{process_name}:{pid}:{full_command}"
                                
                                # Track individual process instance
                                individual_processes[process_key] = {
                                    'pid': pid,
                                    'cpu': cpu_val,
                                    'command': full_command,
                                    'process_name': process_name
                                }
                                
                                # Also group by process name for compatibility
                                if process_name not in process_groups:
                                    process_groups[process_name] = []
                                
                                process_groups[process_name].append({
                                    'pid': pid,
                                    'cpu': cpu_val,
                                    'command': full_command,
                                    'process_key': process_key
                                })
                                break
                                
                    except ValueError:
                        continue
            
            # Update active processes tracking
            self.active_processes = individual_processes
                        
            return process_groups, individual_processes
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Error getting process info: {e}")
            return {}, {}
    
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
            'monitoring_window_seconds': self.monitoring_window,
            'processes': processes,
            'detailed_cpu_info': detailed_info,
            'threshold': self.cpu_threshold
        }
        
        # Add individual process readings for each triggering process
        for process_key in triggering_processes:
            if process_key in self.process_readings:
                readings = list(self.process_readings[process_key])
                cpu_values = [reading['cpu'] for reading in readings]
                # Use a safe key name for the data
                safe_key = str(process_key).replace(':', '_').replace('/', '_').replace(' ', '_')[:50]
                data[f'{safe_key}_readings'] = {
                    'cpu_values': cpu_values,
                    'min_cpu': min(cpu_values) if cpu_values else 0,
                    'max_cpu': max(cpu_values) if cpu_values else 0,
                    'avg_cpu': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'readings_count': len(cpu_values),
                    'process_key': process_key
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
    
    def create_summary_report_with_process_medians(self, processes, individual_processes, process_medians,
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
            f.write(f"Alert triggered by individual process median CPU usage over {self.monitoring_window}s ({self.monitoring_window//60} minutes)\n\n")
            
            f.write("Triggering Processes:\n")
            f.write("-" * 40 + "\n")
            for process_key in triggering_processes:
                median_cpu = process_medians.get(process_key, 0)
                # Extract process info from individual_processes
                process_info = individual_processes.get(process_key, {})
                current_cpu = process_info.get('cpu', 0) if isinstance(process_info, dict) else 0
                
                # Extract process name from the key
                process_name = process_key.split(':')[0] if ':' in process_key else process_key
                f.write(f"{process_name.upper()}:\n")
                f.write(f"  Current CPU: {current_cpu:.1f}%\n")
                f.write(f"  Median CPU: {median_cpu:.1f}%\n")
                f.write(f"  Threshold: {self.cpu_threshold}%\n\n")
            
            f.write("All Process Statistics:\n")
            f.write("-" * 40 + "\n")
            # Group process instances by name for summary
            process_summary = {}
            for process_key, median_cpu in process_medians.items():
                process_name = process_key.split(':')[0] if ':' in process_key else process_key
                if process_name not in process_summary:
                    process_summary[process_name] = {'medians': [], 'current': [], 'alerting': False}
                process_summary[process_name]['medians'].append(median_cpu)
                
                # Get current CPU if available
                current_cpu = individual_processes.get(process_key, {}).get('cpu', 0)
                process_summary[process_name]['current'].append(current_cpu)
                
                # Check if any instance is alerting
                if process_key in triggering_processes:
                    process_summary[process_name]['alerting'] = True
            
            for process_name in self.process_names:
                if process_name in process_summary:
                    summary = process_summary[process_name]
                    avg_median = sum(summary['medians']) / len(summary['medians'])
                    avg_current = sum(summary['current']) / len(summary['current'])
                    status = "⚠️  ALERT" if summary['alerting'] else "✅ Normal"
                    instance_count = len(summary['medians'])
                    f.write(f"{process_name.upper()}: {instance_count} instances, Avg Current: {avg_current:.1f}%, Avg Median: {avg_median:.1f}% - {status}\n")
                else:
                    f.write(f"{process_name.upper()}: No active instances - ✅ Normal\n")
            
            f.write(f"\nThreshold: {self.cpu_threshold}%\n\n")
            
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
        status_logger.info(f"Starting CPU monitor for processes: {', '.join(self.process_names)}")
        status_logger.info(f"Individual process threshold: {self.cpu_threshold}%, Check interval: {self.check_interval}s")
        status_logger.info(f"Monitoring window: {self.monitoring_window}s ({self.monitoring_window//60} minutes)")
        status_logger.info(f"Evidence folder: {self.evidence_folder.absolute()}")
        
        self.monitoring_start_time = datetime.now()
        last_status_log = datetime.now()
        last_config_check = datetime.now()
        status_log_interval = 3600  # Log status every hour
        config_check_interval = 60  # Check config every minute
        
        while True:
            try:
                # Check for config changes periodically
                if (datetime.now() - last_config_check).total_seconds() >= config_check_interval:
                    if self.reload_config():
                        status_logger.info(f"Config reloaded - New settings: processes={len(self.process_names)}, threshold={self.cpu_threshold}%, interval={self.check_interval}s, window={self.monitoring_window}s")
                    last_config_check = datetime.now()
                
                process_groups, individual_processes = self.get_process_cpu_usage()
                current_time = datetime.now()
                
                # Track each individual process instance separately
                for process_key, process_info in individual_processes.items():
                    cpu_usage = process_info['cpu']
                    
                    # Initialize window start time if not set
                    if process_key not in self.process_window_start or self.process_window_start[process_key] is None:
                        self.process_window_start[process_key] = current_time
                    
                    if process_key not in self.process_readings:
                        self.process_readings[process_key] = deque()
                    
                    self.process_readings[process_key].append({
                        'timestamp': current_time,
                        'cpu': cpu_usage,
                        'pid': process_info['pid'],
                        'command': process_info['command'],
                        'process_name': process_info['process_name']
                    })
                    
                    # Remove old readings (keep only readings within current monitoring window)
                    window_start = self.process_window_start[process_key]
                    while (self.process_readings[process_key] and 
                           self.process_readings[process_key][0]['timestamp'] < window_start):
                        self.process_readings[process_key].popleft()
                    
                    # Also limit by max number of readings to prevent memory issues
                    while len(self.process_readings[process_key]) > self.max_readings:
                        self.process_readings[process_key].popleft()
                
                # Check if we have enough data to calculate medians for each individual process instance
                process_medians = {}
                triggering_processes = []
                
                # Check each individual process instance
                for process_key, readings_deque in self.process_readings.items():
                    if not readings_deque:
                        continue
                        
                    readings = list(readings_deque)
                    window_start = self.process_window_start.get(process_key)
                    
                    # Check if we have completed a full monitoring window
                    window_duration = (current_time - window_start).total_seconds() if window_start else 0
                    
                    if len(readings) >= 3 and window_duration >= self.monitoring_window:
                        # We have a complete monitoring window - calculate median
                        cpu_values = [reading['cpu'] for reading in readings]
                        median_cpu = statistics.median(cpu_values)
                        process_medians[process_key] = median_cpu
                        
                        # Check if this individual process instance exceeds threshold
                        if median_cpu >= self.cpu_threshold:
                            triggering_processes.append(process_key)
                    else:
                        # Still collecting data for this window
                        if len(readings) > 0:
                            cpu_values = [reading['cpu'] for reading in readings]
                            process_medians[process_key] = statistics.median(cpu_values)
                        else:
                            process_medians[process_key] = 0.0
                
                # Periodic status logging (every hour)
                if (current_time - last_status_log).total_seconds() >= status_log_interval:
                    elapsed_time = (current_time - self.monitoring_start_time).total_seconds()
                    status_msg = f"Status - Runtime: {elapsed_time/3600:.1f}h | Active processes: {len(individual_processes)} | "
                    
                    # Count active processes by name
                    process_counts = {}
                    for process_info in individual_processes.values():
                        process_name = process_info.get('process_name', 'Unknown')
                        process_counts[process_name] = process_counts.get(process_name, 0) + 1
                    
                    for process_name, count in process_counts.items():
                        status_msg += f"{process_name}: {count} instances | "
                    
                    status_logger.info(status_msg.rstrip(" | "))
                    last_status_log = current_time
                
                # Trigger alert if any individual process instance exceeds threshold
                if triggering_processes:
                    timestamp_str = current_time.strftime("%Y%m%d_%H%M%S")
                    
                    logging.warning(f"HIGH CPU ALERT! Individual process instances exceeding {self.cpu_threshold}% median over {self.monitoring_window}s:")
                    for process_key in triggering_processes:
                        median_cpu = process_medians[process_key]
                        # Get current CPU from active processes
                        current_cpu = individual_processes.get(process_key, {}).get('cpu', 0)
                        process_info = individual_processes.get(process_key, {})
                        pid = process_info.get('pid', 'N/A')
                        command = process_info.get('command', 'N/A')
                        process_name = process_info.get('process_name', 'N/A')
                        
                        logging.warning(f"  {process_name} (PID: {pid}): Current: {current_cpu:.1f}%, Median: {median_cpu:.1f}%")
                        logging.warning(f"    Command: {command}")
                    
                    # Get detailed CPU information
                    detailed_info = self.get_detailed_cpu_info()
                    
                    # Save evidence with individual process information
                    json_path = self.save_cpu_data_with_process_medians(process_groups, individual_processes, process_medians,
                                                                      triggering_processes, detailed_info, timestamp_str)
                    report_path = self.create_summary_report_with_process_medians(process_groups, individual_processes, process_medians,
                                                                                triggering_processes, timestamp_str)
                    screenshot_path = self.take_activity_monitor_screenshot(timestamp_str)
                    
                    logging.warning("Evidence captured:")
                    logging.warning(f"  - Data: {json_path}")
                    logging.warning(f"  - Report: {report_path}")
                    if screenshot_path:
                        logging.warning(f"  - Screenshot: {screenshot_path}")
                    
                    # Start fresh monitoring window for triggering process instances after capturing evidence
                    for process_key in triggering_processes:
                        self.process_readings[process_key].clear()
                        self.process_window_start[process_key] = current_time
                        process_info = individual_processes.get(process_key, {})
                        process_name = process_info.get('process_name', 'Unknown')
                        pid = process_info.get('pid', 'N/A')
                        logging.info(f"Started new monitoring window for {process_name} (PID: {pid}) at {current_time}")
                    
                    last_status_log = current_time  # Reset status log timer
                
                # Sleep with lower priority to reduce CPU usage
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                status_logger.info("Monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(self.check_interval)

def main():
    """Entry point"""
    monitor = CPUMonitor()
    
    # Create evidence folder if it doesn't exist
    if not monitor.evidence_folder.exists():
        monitor.evidence_folder.mkdir(parents=True)
        print(f"Created evidence folder: {monitor.evidence_folder.absolute()}")
    
    print(f"CPU Monitor starting...")
    print(f"Monitoring processes individually: {', '.join(monitor.process_names)}")
    print(f"Individual process threshold: {monitor.cpu_threshold}%")
    print(f"Check interval: {monitor.check_interval}s")
    print(f"Monitoring window: {monitor.monitoring_window}s ({monitor.monitoring_window//60} minutes)")
    print(f"Evidence will be saved to: {monitor.evidence_folder.absolute()}")
    print(f"Configuration file: {monitor.config_path}")
    print("Press Ctrl+C to stop")
    
    monitor.monitor()

if __name__ == "__main__":
    main()
