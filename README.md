# CPU Monitor Background Service

A lightweight background service for macOS that monitors specific processes for sustained high CPU usage and automatically captures evidence when thresholds are exceeded.

[Medium Blog Post](https://navaneethsen.medium.com/from-manual-screenshots-to-automated-evidence-building-a-smart-macos-cpu-monitor-3b4ada892790)

## Features

- **Individual Process Tracking**: Each process instance tracked separately by PID and command line
- **Dynamic Configuration**: Modify settings without restarting the service
- **Median-Based Detection**: Uses 5-minute median CPU usage to avoid false positives
- **Auto-Start**: Automatically starts at login and runs in background
- **Evidence Collection**: Saves detailed JSON data and text reports when alerts trigger
- **Comprehensive Logging**: Detailed logs with hourly status updates

## Quick Setup

### Prerequisites
- **macOS** with **Python 3.6+** (built-in)
- **No external dependencies** required

### 1. Installation

```bash
cd macos-cpu-monitor
./install_service.sh
```

### 2. Grant Permissions
- Go to **System Preferences** > **Security & Privacy** > **Privacy** > **Accessibility**
- Click the lock icon and enter your password
- Click **+** and add **Python** (`/usr/bin/python3`)
- Ensure Python is checked/enabled

### 3. Verify Installation
```bash
launchctl list | grep com.user.cpumonitor
```

### 4. Uninstall (if needed)
```bash
./uninstall_service.sh
```

## Configuration

### Option 1: JSON Configuration File (Recommended)

Create a `config.json` file for dynamic configuration:

```json
{
  "process_names": [
    "chrome",
    "java",
    "python",
    "suspicious_app"
  ],
  "cpu_threshold": 95.0,
  "check_interval": 30,
  "monitoring_window": 300,
  "evidence_folder": "cpu_evidence",
  "log_file": "cpu_monitor.log"
}
```

**Configuration Parameters:**
- `process_names`: Array of process names to monitor
- `cpu_threshold`: CPU usage percentage threshold (0-100)
- `check_interval`: Seconds between CPU checks
- `monitoring_window`: Time window in seconds for median calculation
- `evidence_folder`: Directory to store evidence files
- `log_file`: Log file path

### Option 2: Direct Script Modification

Edit `run_cpu_anlayser.py`:

```python
PROCESS_NAMES = [
    "abcd_enterprise",
    "silverbullet", 
    "com.xyz.SecurityExtension",
    "suspicious_daemon"
]

CPU_THRESHOLD = 95.0       # Percentage threshold
CHECK_INTERVAL = 30        # Seconds between checks
MONITORING_WINDOW = 300    # 5 minutes for median calculation
```

### Dynamic Configuration Updates

The monitor automatically reloads `config.json` every 60 seconds. You can also use the utility script:

```bash
# Show current configuration
python update_config.py show

# Update CPU threshold to 80%
python update_config.py threshold 80

# Add a new process to monitor
python update_config.py add-process "new_daemon"

# Remove a process from monitoring
python update_config.py remove-process "old_process"
```

## How It Works

### Individual Process Tracking
Each process instance is monitored separately:
- **Unique Identification**: `process_name:pid:full_command`
- **Independent Monitoring**: Each instance has its own CPU threshold monitoring
- **Command Differentiation**: Processes with same name but different arguments tracked separately

**Example**: Multiple Chrome processes are tracked individually:
```
chrome:1234:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer
chrome:1235:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=gpu-process
```

### Monitoring Process
1. **Data Collection**: Every 30 seconds, checks CPU usage of each monitored process
2. **Rolling Window**: Maintains 5-minute rolling windows per process instance
3. **Median Analysis**: Calculates median CPU usage for each process over monitoring window
4. **Alert Trigger**: Triggers when ANY process instance median exceeds threshold

## Evidence and Logs

### File Structure
```
macos-cpu-monitor/
├── config.json                 # Configuration file
├── run_cpu_anlayser.py         # Main script
├── cpu_monitor.log             # Main log file
└── cpu_evidence/               # Evidence folder
    └── 2025/06/19/21/         # Hive partition (yyyy/mm/dd/hh)
        ├── cpu_data_20250619_213511.json
        └── report_20250619_213511.txt
```

### Alert Format
```
HIGH CPU ALERT! Individual process instances exceeding 95.0% median over 300s:
  chrome (PID: 1234): Current: 98.5%, Median: 96.2%
    Command: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer
  java (PID: 5678): Current: 97.1%, Median: 95.8%
    Command: java -Xmx2g -jar myapp.jar --spring.profiles.active=production
```

### Evidence Files
1. **JSON Data** (`cpu_data_YYYYMMDD_HHMMSS.json`):
   - Individual process CPU readings and medians
   - Complete command lines and PIDs
   - Statistical analysis per process instance

2. **Text Report** (`report_YYYYMMDD_HHMMSS.txt`):
   - Human-readable summary with visual indicators
   - Individual process statistics (⚠️ ALERT vs ✅ Normal)
   - 5-minute reading history for each triggering process

## Service Management

### Check Status
```bash
launchctl list | grep com.user.cpumonitor
```

### View Logs
```bash
tail -f cpu_monitor.log
```

### Manual Control
```bash
# Stop service
launchctl unload ~/Library/LaunchAgents/com.user.cpumonitor.plist

# Start service
launchctl load ~/Library/LaunchAgents/com.user.cpumonitor.plist

# Restart service
launchctl unload ~/Library/LaunchAgents/com.user.cpumonitor.plist
launchctl load ~/Library/LaunchAgents/com.user.cpumonitor.plist
```

## Troubleshooting

### Service Won't Start
1. **Check file paths in plist:**
   ```bash
   # Edit plist file to match your actual repository path
   nano com.user.cpumonitor.plist
   # Replace placeholder paths with your actual path
   ```

2. **Verify Python path:**
   ```bash
   which python3
   ```

3. **Check error logs:**
   ```bash
   cat cpu_monitor_stderr.log
   ```

### Permission Issues
- Ensure Python has **Accessibility** permissions in System Preferences
- Check for permission dialog prompts when first running
- Verify write permissions in evidence folder

### Configuration Issues
- JSON syntax must be valid
- CPU threshold must be 0-100
- Time intervals must be positive integers
- Invalid configs will log warnings and use previous valid settings

### Performance Issues
- Increase `check_interval` to reduce CPU usage
- Service runs with low priority (Nice value 10)
- Uses efficient memory management with size-limited rolling windows

## Examples

### Monitoring Multiple Java Applications
```json
{
  "process_names": ["java"],
  "cpu_threshold": 90.0,
  "check_interval": 60
}
```

This will separately track:
- `java:5678:java -Xmx2g -jar app1.jar`
- `java:5679:java -Xmx4g -jar app2.jar --config=prod`

### Security Monitoring
```json
{
  "process_names": [
    "SecurityExtension",
    "suspicious_daemon",
    "crypto_miner"
  ],
  "cpu_threshold": 80.0,
  "check_interval": 15
}
```

## Security Notes

- Runs with user privileges (not root)
- No network connections made
- All data stored locally
- Only monitors specified processes
- Files created with user permissions

---

**Ready to start monitoring!** The service will automatically begin tracking your configured processes and alert you when any individual process instance sustains high CPU usage.
