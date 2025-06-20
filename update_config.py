#!/usr/bin/env python3
"""
Configuration Update Script - Utility to modify CPU monitor configuration at runtime
"""

import json
import sys
from pathlib import Path

def load_config(config_path="config.json"):
    """Load current configuration"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config: {e}")
        return None

def save_config(config, config_path="config.json"):
    """Save configuration to file"""
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration updated successfully: {config_path}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def show_current_config(config_path="config.json"):
    """Display current configuration"""
    config = load_config(config_path)
    if config:
        print("Current Configuration:")
        print("=" * 40)
        print(f"Process Names: {', '.join(config['process_names'])}")
        print(f"CPU Threshold: {config['cpu_threshold']}%")
        print(f"Check Interval: {config['check_interval']}s")
        print(f"Monitoring Window: {config['monitoring_window']}s ({config['monitoring_window']//60} minutes)")
        print(f"Evidence Folder: {config['evidence_folder']}")
        print(f"Log File: {config['log_file']}")

def update_threshold(new_threshold, config_path="config.json"):
    """Update CPU threshold"""
    config = load_config(config_path)
    if config:
        config['cpu_threshold'] = float(new_threshold)
        if save_config(config, config_path):
            print(f"CPU threshold updated to {new_threshold}%")

def update_check_interval(new_interval, config_path="config.json"):
    """Update check interval"""
    config = load_config(config_path)
    if config:
        config['check_interval'] = int(new_interval)
        if save_config(config, config_path):
            print(f"Check interval updated to {new_interval}s")

def update_monitoring_window(new_window, config_path="config.json"):
    """Update monitoring window"""
    config = load_config(config_path)
    if config:
        config['monitoring_window'] = int(new_window)
        if save_config(config, config_path):
            print(f"Monitoring window updated to {new_window}s ({new_window//60} minutes)")

def add_process(process_name, config_path="config.json"):
    """Add a process to monitor"""
    config = load_config(config_path)
    if config:
        if process_name not in config['process_names']:
            config['process_names'].append(process_name)
            if save_config(config, config_path):
                print(f"Added process '{process_name}' to monitoring list")
        else:
            print(f"Process '{process_name}' is already being monitored")

def remove_process(process_name, config_path="config.json"):
    """Remove a process from monitoring"""
    config = load_config(config_path)
    if config:
        if process_name in config['process_names']:
            config['process_names'].remove(process_name)
            if save_config(config, config_path):
                print(f"Removed process '{process_name}' from monitoring list")
        else:
            print(f"Process '{process_name}' is not in the monitoring list")

def main():
    """Main function with command line interface"""
    if len(sys.argv) < 2:
        print("CPU Monitor Configuration Update Tool")
        print("=" * 40)
        print("Usage:")
        print("  python update_config.py show                           - Show current config")
        print("  python update_config.py threshold <value>              - Update CPU threshold (%)")
        print("  python update_config.py interval <seconds>             - Update check interval")
        print("  python update_config.py window <seconds>               - Update monitoring window")
        print("  python update_config.py add-process <name>             - Add process to monitor")
        print("  python update_config.py remove-process <name>          - Remove process from monitoring")
        print()
        print("Examples:")
        print("  python update_config.py show")
        print("  python update_config.py threshold 80")
        print("  python update_config.py interval 60")
        print("  python update_config.py window 600")
        print("  python update_config.py add-process 'new_daemon'")
        print("  python update_config.py remove-process 'old_process'")
        return

    command = sys.argv[1].lower()
    config_path = "config.json"

    if command == "show":
        show_current_config(config_path)
    
    elif command == "threshold" and len(sys.argv) >= 3:
        try:
            threshold = float(sys.argv[2])
            if 0 <= threshold <= 100:
                update_threshold(threshold, config_path)
            else:
                print("Error: Threshold must be between 0 and 100")
        except ValueError:
            print("Error: Invalid threshold value")
    
    elif command == "interval" and len(sys.argv) >= 3:
        try:
            interval = int(sys.argv[2])
            if interval > 0:
                update_check_interval(interval, config_path)
            else:
                print("Error: Interval must be greater than 0")
        except ValueError:
            print("Error: Invalid interval value")
    
    elif command == "window" and len(sys.argv) >= 3:
        try:
            window = int(sys.argv[2])
            if window > 0:
                update_monitoring_window(window, config_path)
            else:
                print("Error: Window must be greater than 0")
        except ValueError:
            print("Error: Invalid window value")
    
    elif command == "add-process" and len(sys.argv) >= 3:
        process_name = sys.argv[2]
        add_process(process_name, config_path)
    
    elif command == "remove-process" and len(sys.argv) >= 3:
        process_name = sys.argv[2]
        remove_process(process_name, config_path)
    
    else:
        print("Error: Invalid command or missing arguments")
        print("Use 'python update_config.py' without arguments to see usage")

if __name__ == "__main__":
    main()
