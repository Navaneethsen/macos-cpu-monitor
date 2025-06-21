#!/usr/bin/env python3
"""
CPU Monitor - Ultra-lightweight background process to monitor specific processes
and capture evidence when they consume high CPU usage individually.
Optimized for minimal memory usage.
"""

import subprocess
import time
import os
import json
from datetime import datetime
from pathlib import Path
import logging
import statistics
import sys
import gc
from array import array
import weakref

# Memory optimization: Use string interning for frequently used strings
def intern_string(s):
    """Intern strings to reduce memory usage for repeated strings"""
    return sys.intern(str(s))

class ProcessReading:
    """Memory-optimized process reading using __slots__"""
    __slots__ = ('timestamp', 'cpu', 'pid')
    
    def __init__(self, timestamp, cpu, pid):
        self.timestamp = timestamp
        self.cpu = cpu
        self.pid = int(pid)

class CircularBuffer:
    """Memory-efficient circular buffer using array for numeric data"""
    __slots__ = ('_buffer', '_timestamps', '_pids', '_size', '_pos', '_count')
    
    def __init__(self, maxsize):
        self._size = maxsize
        self._buffer = array('f', [0.0] * maxsize)  # float array for CPU values
        self._timestamps = [None] * maxsize
        self._pids = array('i', [0] * maxsize)  # int array for PIDs
        self._pos = 0
        self._count = 0
    
    def append(self, timestamp, cpu, pid):
        """Add reading to circular buffer"""
        self._buffer[self._pos] = float(cpu)
        self._timestamps[self._pos] = timestamp
        self._pids[self._pos] = int(pid)
        self._pos = (self._pos + 1) % self._size
        if self._count < self._size:
            self._count += 1
    
    def get_values(self):
        """Get CPU values as list for median calculation"""
        if self._count == 0:
            return []
        if self._count < self._size:
            return list(self._buffer[:self._count])
        # Buffer is full, return in correct order
        return list(self._buffer[self._pos:]) + list(self._buffer[:self._pos])
    
    def get_recent_values(self, window_seconds, current_time):
        """Get values within time window"""
        if self._count == 0:
            return []
        
        values = []
        cutoff_time = current_time - window_seconds
        
        # Check timestamps in reverse order (most recent first)
        for i in range(self._count):
            idx = (self._pos - 1 - i) % self._size
            if self._timestamps[idx] and self._timestamps[idx] >= cutoff_time:
                values.append(self._buffer[idx])
            else:
                break  # Older entries, stop checking
        
        return values
    
    def clear(self):
        """Clear buffer"""
        self._count = 0
        self._pos = 0
    
    def __len__(self):
        return self._count

def load_config(config_path="config.json"):
    """Load configuration with minimal memory footprint"""
    default_config = {
        "process_names": ["java", "Docker", "Virtual Machine Service for Docker", 
                         "IntelliJ IDEA", "Google Chrome", "Safari"],
        "cpu_threshold": 95.0,
        "check_interval": 10,
        "monitoring_window": 300,
        "evidence_folder": "cpu_evidence",
        "log_file": "cpu_monitor.log"
    }
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        # Intern process names to save memory
        if 'process_names' in config:
            config['process_names'] = [intern_string(name) for name in config['process_names']]
        # Merge with defaults
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Could not load config {config_path}: {e}. Using defaults.")
        default_config['process_names'] = [intern_string(name) for name in default_config['process_names']]
        return default_config

class CPUMonitor:
    """Ultra-lightweight CPU monitor with minimal memory usage"""
    __slots__ = ('config_path', 'config_last_modified', 'process_readings', 
                 'process_window_start', 'config', 'process_names', 'cpu_threshold',
                 'check_interval', 'monitoring_window', 'evidence_folder', 'log_file',
                 'max_readings', '_process_name_cache', '_weak_refs')
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config_last_modified = 0
        
        # Use circular buffers for memory efficiency
        self.process_readings = {}
        self.process_window_start = {}
        
        # Cache for process name matching to avoid repeated string operations
        self._process_name_cache = {}
        
        # Weak references to avoid memory leaks
        self._weak_refs = weakref.WeakSet()
        
        self.reload_config()
        self._initialize_buffers()
    
    def reload_config(self):
        """Reload configuration with memory optimization"""
        try:
            current_modified = os.path.getmtime(self.config_path)
            if current_modified > self.config_last_modified:
                self.config = load_config(self.config_path)
                self.config_last_modified = current_modified
                
                # Use interned strings for process names
                self.process_names = tuple(intern_string(name) for name in self.config["process_names"])
                self.cpu_threshold = float(self.config["cpu_threshold"])
                self.check_interval = int(self.config["check_interval"])
                self.monitoring_window = int(self.config["monitoring_window"])
                self.evidence_folder = Path(self.config["evidence_folder"])
                self.evidence_folder.mkdir(exist_ok=True)
                self.log_file = self.config["log_file"]
                
                # Calculate buffer size (add small buffer for safety)
                self.max_readings = (self.monitoring_window // self.check_interval) + 5
                
                # Clear cache when config changes
                self._process_name_cache.clear()
                
                logging.info(f"Configuration reloaded from {self.config_path}")
                return True
        except (OSError, FileNotFoundError):
            pass
        return False
    
    def _initialize_buffers(self):
        """Initialize circular buffers for each process"""
        for process_name in self.process_names:
            if process_name not in self.process_readings:
                self.process_readings[process_name] = CircularBuffer(self.max_readings)
                self.process_window_start[process_name] = None
    
    def _match_process_name(self, command):
        """Optimized process name matching with caching"""
        # Use cache to avoid repeated string operations
        if command in self._process_name_cache:
            return self._process_name_cache[command]
        
        command_lower = command.lower()
        for process_name in self.process_names:
            if process_name.lower() in command_lower:
                self._process_name_cache[command] = process_name
                return process_name
        
        self._process_name_cache[command] = None
        return None
    
    def get_process_cpu_usage(self):
        """Get CPU usage with minimal memory allocation"""
        try:
            # Use the original working ps command
            result = subprocess.run(
                ["ps", "-A", "-o", "pid,pcpu,args"],  # Original working format
                capture_output=True, text=True, check=True, timeout=10
            )
            
            processes = {}
            current_time = time.time()
            
            # Early exit if no output
            if not result.stdout.strip():
                return processes, current_time
            
            # Process only lines that might contain our monitored processes
            lines = result.stdout.split('\n')[1:]  # Skip header
            monitored_lower = [name.lower() for name in self.process_names]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Quick check if line contains any monitored process name
                line_lower = line.lower()
                if not any(proc in line_lower for proc in monitored_lower):
                    continue
                
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    try:
                        pid, cpu_str, command = parts
                        cpu_val = float(cpu_str)
                        
                        # Skip very low CPU to save memory (allow small values for monitoring)
                        if cpu_val < 0.1:
                            continue
                        
                        # Check if this matches any monitored process
                        process_name = self._match_process_name(command)
                        if process_name:
                            if process_name not in processes:
                                processes[process_name] = []
                            
                            processes[process_name].append({
                                'pid': int(pid),
                                'cpu': cpu_val,
                                'command': intern_string(command)
                            })
                            
                    except (ValueError, IndexError):
                        continue
            
            return processes, current_time
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logging.error(f"Error getting process info: {e}")
            # Try fallback command if main command fails
            try:
                result = subprocess.run(
                    ["ps", "aux"],  # Simple fallback
                    capture_output=True, text=True, check=True, timeout=3
                )
                # Process fallback output (simplified)
                processes = {}
                current_time = time.time()
                for line in result.stdout.split('\n')[1:]:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 11:  # ps aux format
                            try:
                                cpu_val = float(parts[2])
                                if cpu_val >= 0.1:  # Only processes with some CPU
                                    command = ' '.join(parts[10:])
                                    process_name = self._match_process_name(command)
                                    if process_name:
                                        if process_name not in processes:
                                            processes[process_name] = []
                                        processes[process_name].append({
                                            'pid': int(parts[1]),
                                            'cpu': cpu_val,
                                            'command': intern_string(command[:50])  # Limit length
                                        })
                            except (ValueError, IndexError):
                                continue
                return processes, current_time
            except:
                logging.error("Fallback ps command also failed")
                return {}, time.time()
    
    def get_detailed_cpu_info(self):
        """Get minimal CPU info to reduce memory usage"""
        try:
            # Get only essential CPU info
            result = subprocess.run(
                ["top", "-l", "1", "-n", "5", "-o", "cpu"],  # Top 5 CPU processes only
                capture_output=True, text=True, check=True, timeout=5
            )
            # Return only first 1000 characters to limit memory usage
            return result.stdout[:1000]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "CPU info unavailable"
    
    def save_cpu_data_minimal(self, processes, process_medians, triggering_processes, 
                             detailed_info, timestamp_str):
        """Save minimal CPU data to reduce file size and memory usage"""
        # Create minimal data structure
        data = {
            'ts': timestamp_str,  # Shorter key names
            'alert': list(triggering_processes),
            'medians': {k: round(v, 1) for k, v in process_medians.items()},  # Round to save space
            'window': self.monitoring_window,
            'threshold': self.cpu_threshold,
            'processes': {k: len(v) for k, v in processes.items()},  # Just count instances
            'top_info': detailed_info[:500]  # Limit size
        }
        
        # Create partition path
        timestamp_obj = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        partition_path = (self.evidence_folder / f"{timestamp_obj.year:04d}" / 
                         f"{timestamp_obj.month:02d}" / f"{timestamp_obj.day:02d}" / 
                         f"{timestamp_obj.hour:02d}")
        partition_path.mkdir(parents=True, exist_ok=True)
        
        json_path = partition_path / f"cpu_data_{timestamp_str}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, separators=(',', ':'))  # Compact JSON
        
        return str(json_path)
    
    def create_minimal_report(self, processes, process_medians, triggering_processes, timestamp_str):
        """Create minimal report to save disk space"""
        timestamp_obj = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        partition_path = (self.evidence_folder / f"{timestamp_obj.year:04d}" / 
                         f"{timestamp_obj.month:02d}" / f"{timestamp_obj.day:02d}" / 
                         f"{timestamp_obj.hour:02d}")
        partition_path.mkdir(parents=True, exist_ok=True)
        
        report_path = partition_path / f"report_{timestamp_str}.txt"
        
        with open(report_path, 'w') as f:
            f.write(f"CPU Alert: {timestamp_str}\n")
            f.write(f"Threshold: {self.cpu_threshold}%\n")
            f.write(f"Window: {self.monitoring_window}s\n\n")
            
            f.write("Alerts:\n")
            for process_name in triggering_processes:
                median = process_medians.get(process_name, 0)
                count = len(processes.get(process_name, []))
                f.write(f"  {process_name}: {median:.1f}% ({count} instances)\n")
            
            f.write(f"\nAll processes:\n")
            for process_name in self.process_names:
                if process_name in processes:
                    count = len(processes[process_name])
                    median = process_medians.get(process_name, 0)
                    f.write(f"  {process_name}: {count} instances, {median:.1f}%\n")
        
        return str(report_path)
    
    def monitor(self):
        """Ultra-lightweight monitoring loop"""
        logging.info(f"Starting lightweight CPU monitor for {len(self.process_names)} processes")
        
        last_status_log = time.time()
        last_config_check = time.time()
        status_interval = 300  # 5 minutes
        config_interval = 120   # 2 minutes
        
        # Force garbage collection to start clean
        gc.collect()
        
        while True:
            try:
                current_time = time.time()
                
                # Check config less frequently to save CPU
                if current_time - last_config_check >= config_interval:
                    self.reload_config()
                    last_config_check = current_time
                
                processes, timestamp = self.get_process_cpu_usage()
                
                # Update readings for each process
                for process_name, instances in processes.items():
                    if process_name not in self.process_readings:
                        self.process_readings[process_name] = CircularBuffer(self.max_readings)
                        self.process_window_start[process_name] = timestamp
                    
                    # Use highest CPU instance for this process
                    max_cpu = max(instance['cpu'] for instance in instances)
                    max_pid = next(instance['pid'] for instance in instances 
                                 if instance['cpu'] == max_cpu)
                    
                    self.process_readings[process_name].append(timestamp, max_cpu, max_pid)
                    
                    # Initialize window start if needed
                    if self.process_window_start[process_name] is None:
                        self.process_window_start[process_name] = timestamp
                
                # Calculate medians and check thresholds
                process_medians = {}
                triggering_processes = []
                
                for process_name in self.process_names:
                    if process_name in self.process_readings:
                        buffer = self.process_readings[process_name]
                        window_start = self.process_window_start[process_name]
                        
                        if window_start and (timestamp - window_start) >= self.monitoring_window:
                            # Get values within monitoring window
                            values = buffer.get_recent_values(self.monitoring_window, timestamp)
                            
                            if len(values) >= 3:  # Need minimum readings
                                median_cpu = statistics.median(values)
                                process_medians[process_name] = median_cpu
                                
                                if median_cpu >= self.cpu_threshold:
                                    triggering_processes.append(process_name)
                            else:
                                process_medians[process_name] = 0.0
                        else:
                            # Still in monitoring window
                            values = buffer.get_values()
                            if values:
                                process_medians[process_name] = statistics.median(values)
                            else:
                                process_medians[process_name] = 0.0
                
                # Handle alerts
                if triggering_processes:
                    timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S")
                    
                    logging.warning(f"CPU ALERT: {len(triggering_processes)} processes over {self.cpu_threshold}%")
                    for process_name in triggering_processes:
                        median = process_medians[process_name]
                        count = len(processes.get(process_name, []))
                        logging.warning(f"  {process_name}: {median:.1f}% ({count} instances)")
                    
                    # Save minimal evidence
                    detailed_info = self.get_detailed_cpu_info()
                    json_path = self.save_cpu_data_minimal(processes, process_medians, 
                                                         triggering_processes, detailed_info, timestamp_str)
                    report_path = self.create_minimal_report(processes, process_medians, 
                                                           triggering_processes, timestamp_str)
                    
                    logging.warning(f"Evidence: {json_path}, {report_path}")
                    
                    # Reset monitoring windows for alerting processes
                    for process_name in triggering_processes:
                        self.process_readings[process_name].clear()
                        self.process_window_start[process_name] = timestamp
                    
                    last_status_log = current_time
                
                # Periodic status (less frequent)
                if current_time - last_status_log >= status_interval:
                    active_count = sum(len(instances) for instances in processes.values())
                    logging.info(f"Status: {active_count} active processes monitored")
                    last_status_log = current_time
                    
                    # Force garbage collection periodically
                    gc.collect()
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logging.info("Monitor stopped")
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(self.check_interval)

def main():
    """Lightweight entry point"""
    # Setup minimal logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler("cpu_monitor.log")]
    )
    
    monitor = CPUMonitor()
    
    print(f"Lightweight CPU Monitor starting...")
    print(f"Processes: {len(monitor.process_names)}")
    print(f"Threshold: {monitor.cpu_threshold}%")
    print(f"Interval: {monitor.check_interval}s")
    print(f"Window: {monitor.monitoring_window}s")
    print("Press Ctrl+C to stop")
    
    monitor.monitor()

if __name__ == "__main__":
    main()
