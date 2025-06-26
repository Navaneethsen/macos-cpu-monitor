# CPU Monitor Background Service

A lightweight background service for macOS that monitors specific processes for sustained high CPU usage and automatically captures evidence when thresholds are exceeded.

[Medium Blog Post](https://navaneethsen.medium.com/from-manual-screenshots-to-automated-evidence-building-a-smart-macos-cpu-monitor-3b4ada892790)

## Features

- **Background Operation**: Runs silently in the background with minimal CPU usage
- **Auto-Start**: Automatically starts at login
- **Window-Based Detection**: Uses configurable monitoring windows to detect sustained high CPU usage
- **Configurable Percentile Analysis**: Uses configurable percentiles (P10, P25, P50, etc.) to avoid false positives
- **JSON Configuration**: All settings configurable via `config.json`
- **Comprehensive Evidence**: Captures detailed JSON data, minimal reports, and full reports when alerts trigger
- **Memory Optimized**: Ultra-lightweight design with circular buffers and minimal memory footprint
- **Partitioned Storage**: Evidence stored in Hive-style partitions (year/month/day/hour)

## Quick Start

### Prerequisites

- **Python 3.6+**: The script uses f-strings and pathlib (built into Python 3.6+)
- **macOS**: Designed specifically for macOS
- **No external dependencies**: Uses only Python standard library modules

### Installation

1. **Configure monitoring settings:**
   ```bash
   # Edit config.json to customize your monitoring
   nano config.json
   ```

2. **Install the service:**
   ```bash
   cd macos-cpu-monitor
   ./install_service.sh
   ```

3. **Verify installation:**
   ```bash
   launchctl list | grep com.user.cpumonitor
   ```

### Uninstallation

```bash
./uninstall_service.sh
```

## Configuration

All configuration is managed through `config.json`:

```json
{
  "process_names": [
    "abcd_enterprise",
    "silverbullet", 
    "com.xyz.SecurityExtension",
    "1234daemon",
    "fryGPS"  
    ... # Add more as needed
  ],
  "cpu_threshold": 95.0,
  "check_interval": 10,
  "monitoring_window": 600,
  "percentile": 10,
  "evidence_folder": "cpu_evidence",
  "log_file": "cpu_monitor.log"
}
```

### Configuration Parameters

- **`process_names`**: List of process names to monitor (partial matches, case-insensitive)
- **`cpu_threshold`**: CPU percentage threshold (default: 95.0%)
- **`check_interval`**: Seconds between CPU checks (default: 10 seconds)
- **`monitoring_window`**: Window duration in seconds for analysis (default: 600 = 10 minutes)
- **`percentile`**: Percentile to use for threshold detection (default: 10 = P10)
- **`evidence_folder`**: Directory for storing evidence files
- **`log_file`**: Main log file name

### Dynamic Configuration Updates

Use the included configuration update tool:

```bash
# Show current configuration
python update_config.py show

# Update CPU threshold
python update_config.py threshold 80

# Update monitoring window (in seconds)
python update_config.py window 900

# Update percentile (1-99)
python update_config.py percentile 25

# Update check interval
python update_config.py interval 15

# Add a process to monitor
python update_config.py add-process "new_daemon"

# Remove a process from monitoring
python update_config.py remove-process "old_process"
```

## How It Works

### Window-Based Monitoring

1. **Sample Collection**: Every 10 seconds (configurable), collect CPU usage for all monitored processes
2. **Global Window**: Maintain a monitoring window (default: 10 minutes) for each process
3. **Window Completion**: When a monitoring window completes, evaluate all processes
4. **Percentile Analysis**: Calculate the configured percentile (default: P10) for CPU usage during the window
5. **Threshold Check**: Alert if percentile value exceeds the CPU threshold
6. **Evidence Generation**: Create reports only when processes exceed thresholds
7. **Window Reset**: Reset monitoring windows and continue

### Percentile Explanation

- **P10 (default)**: Alerts when CPU > threshold for 90% of the monitoring window
- **P25**: Alerts when CPU > threshold for 75% of the monitoring window  
- **P50 (median)**: Alerts when CPU > threshold for 50% of the monitoring window
- **P75**: Alerts when CPU > threshold for 25% of the monitoring window

Lower percentiles = more strict monitoring (sustained high usage required)

### Memory Optimization

- **Circular Buffers**: Fixed-size buffers using Python arrays for CPU values
- **String Interning**: Reduces memory usage for repeated process names
- **Minimal Data Structures**: Uses `__slots__` and optimized data types
- **Garbage Collection**: Periodic cleanup to maintain low memory footprint

## File Structure

```
macos-cpu-monitor/
├── run_cpu_anlayser.py          # Main monitoring script
├── config.json                  # Configuration file
├── update_config.py             # Configuration update utility
├── com.user.cpumonitor.plist    # LaunchAgent configuration
├── install_service.sh           # Installation script
├── uninstall_service.sh         # Uninstallation script
├── README.md                    # This file
├── cpu_monitor.log              # Main log file
├── cpu_monitor_stdout.log       # Standard output log
├── cpu_monitor_stderr.log       # Error log
└── cpu_evidence/                # Evidence folder (Hive partition structure)
    └── 2025/                    # Year
        └── 06/                  # Month
            └── 26/              # Day
                └── 13/          # Hour
                    ├── cpu_data_20250626_131045.json      # Minimal JSON data
                    ├── report_20250626_131045.txt         # Summary report
                    └── full_report_20250626_131045.txt    # Detailed report
```

## Evidence Files

When an alert triggers, three types of files are created:

### 1. JSON Data (`cpu_data_YYYYMMDD_HHMMSS.json`)
Minimal JSON with essential data:
```json
{
  "ts": "20250626_131045",
  "alert": ["1234daemon"],
  "medians": {"1234daemon": 97.2, "abcdaemon_enterprise": 45.1},
  "window": 600,
  "threshold": 95.0,
  "processes": {"1234daemon": 2, "abcdaemon_enterprise": 1},
  "top_info": "..."
}
```

### 2. Summary Report (`report_YYYYMMDD_HHMMSS.txt`)
Human-readable summary:
```
CPU Alert: 20250626_131045
Threshold: 95.0%
Window: 600s

Alerts:
  1234daemon: 97.2% (2 instances)

All processes:
  1234daemon: 2 instances, 97.2%
  abcdaemon_enterprise: 1 instances, 45.1%
```

### 3. Full Report (`full_report_YYYYMMDD_HHMMSS.txt`)
Comprehensive report with:
- Configuration details
- Alerting process details with PIDs and commands
- All monitored processes status
- System information from `top`
- Historical data analysis (min, max, average, median, P95)

## Service Management

### Check Service Status
```bash
launchctl list | grep com.user.cpumonitor
```

### View Live Logs
```bash
tail -f cpu_monitor.log
```

### Manual Start/Stop
```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.user.cpumonitor.plist

# Start
launchctl load ~/Library/LaunchAgents/com.user.cpumonitor.plist
```

### Generate Immediate Report
```bash
# Generate a full report with current system state
python run_cpu_anlayser.py -f
```

## Performance Optimization

The service is optimized for minimal system impact:

- **Low Priority**: Runs with `Nice` value of 10 (lower priority)
- **Background Process**: Marked as background type in LaunchAgent
- **Memory Efficient**: Uses circular buffers and optimized data structures
- **Minimal Logging**: Only logs warnings/errors and periodic status
- **Configurable Intervals**: Adjustable check frequency
- **Garbage Collection**: Periodic memory cleanup

## Monitoring Examples

### Example 1: Strict Monitoring (P10)
```json
{
  "cpu_threshold": 95.0,
  "monitoring_window": 600,
  "percentile": 10
}
```
Alerts when CPU > 95% for 90% of 10 minutes (9 minutes of high usage)

### Example 2: Balanced Monitoring (P25)
```json
{
  "cpu_threshold": 90.0,
  "monitoring_window": 300,
  "percentile": 25
}
```
Alerts when CPU > 90% for 75% of 5 minutes (3.75 minutes of high usage)

### Example 3: Sensitive Monitoring (P50)
```json
{
  "cpu_threshold": 80.0,
  "monitoring_window": 180,
  "percentile": 50
}
```
Alerts when CPU > 80% for 50% of 3 minutes (1.5 minutes of high usage)

## Troubleshooting

### Service Won't Start
1. Check service status:
   ```bash
   launchctl list | grep com.user.cpumonitor
   ```

2. Check error logs:
   ```bash
   cat cpu_monitor_stderr.log
   ```

3. Test manual execution:
   ```bash
   python3 run_cpu_anlayser.py
   ```

### Configuration Issues
1. Validate JSON syntax:
   ```bash
   python -m json.tool config.json
   ```

2. Check configuration:
   ```bash
   python update_config.py show
   ```

### No Alerts Generated
1. Check if processes are running:
   ```bash
   ps aux | grep "process_name"
   ```

2. Lower the percentile for more sensitive detection:
   ```bash
   python update_config.py percentile 50
   ```

3. Check monitoring window completion in logs

### High Memory Usage
- Reduce monitoring window duration
- Increase check interval
- Reduce number of monitored processes

## Security Considerations

- The service runs with user privileges (not root)
- All files are created with user permissions
- No network connections are made
- Only monitors specified processes
- Evidence stored locally with proper permissions

## Advanced Usage

### Custom Process Lists
Add security tools, development environments, or system processes:
```bash
python update_config.py add-process "Docker Desktop"
python update_config.py add-process "IntelliJ IDEA"
python update_config.py add-process "Google Chrome"
```

### Multiple Monitoring Profiles
Create different configurations for different scenarios:
- Development: Higher thresholds, shorter windows
- Production: Lower thresholds, longer windows
- Security: Very strict monitoring with P5 percentile

### Integration with Other Tools
The JSON evidence files can be easily integrated with:
- Log aggregation systems (ELK, Splunk)
- Monitoring dashboards (Grafana)
- Alerting systems (PagerDuty, Slack)
- Security tools (SIEM systems)

## Support

For issues or questions:
1. Check the log files first: `tail -f cpu_monitor.log`
2. Verify service status: `launchctl list | grep com.user.cpumonitor`
3. Test configuration: `python update_config.py show`
4. Generate test report: `python run_cpu_anlayser.py -f`
5. Check manual execution: `python3 run_cpu_anlayser.py`
