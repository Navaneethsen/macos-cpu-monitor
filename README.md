# CPU Monitor Background Service

A lightweight background service for macOS that monitors specific processes for sustained high CPU usage and automatically captures evidence when thresholds are exceeded.

[Medium Blog Post](https://navaneethsen.medium.com/from-manual-screenshots-to-automated-evidence-building-a-smart-macos-cpu-monitor-3b4ada892790)


## Features

- **Background Operation**: Runs silently in the background with minimal CPU usage
- **Auto-Start**: Automatically starts at login
- **Median-Based Detection**: Uses 5-minute median CPU usage to avoid false positives from temporary spikes
- **Data-Only Evidence**: Captures detailed JSON and text reports (screenshots disabled for locked screen compatibility)
- **Comprehensive Logging**: Detailed logs with hourly status updates
- **Evidence Collection**: Saves JSON data and text reports when alerts trigger

## Quick Start

### Prerequisites

- **Python 3.6+**: The script uses f-strings and pathlib (built into Python 3.6+)
- **macOS**: Designed specifically for macOS with Activity Monitor integration
- **No external dependencies**: Uses only Python standard library modules

### Installation

1. **Update file paths in the plist configuration:**
   - Open `com.user.cpumonitor.plist` in a text editor
   - Update all file paths to match your actual repository location
   - Replace `/<root_folder>/macos-cpu-monitor/` with your actual path
   - Example: If you downloaded to `/Users/yourname/Downloads/macos-cpu-monitor/`, update all paths accordingly

2. **Grant Python permissions:**
   - Go to **System Preferences** > **Security & Privacy** > **Privacy**
   - Select **Accessibility** from the left sidebar
   - Click the lock icon and enter your password
   - Click the **+** button and add **Python** (usually located at `/usr/bin/python3`)
   - Ensure Python is checked/enabled in the list
   - This allows Python to control Activity Monitor for screenshots

3. **Install the service:**
   ```bash
   cd macos-cpu-monitor
   ./install_service.sh
   ```

4. **Verify installation:**
   ```bash
   launchctl list | grep com.user.cpumonitor
   ```

### Uninstallation

```bash
./uninstall_service.sh
```

## Configuration

### Monitored Processes

Edit `run_cpu_anlayser.py` to modify the `PROCESS_NAMES` list:

```python
PROCESS_NAMES = [
    "abcd_enterprise",
    "silverbullet", 
    "com.xyz.SecurityExtension",
    "1234daemon",
    "fryGPS"  
    ... # Add more as needed
]
```

### Thresholds and Timing

```python
CPU_THRESHOLD = 95.0       # Percentage threshold for median CPU usage
CHECK_INTERVAL = 30        # Seconds between CPU checks
MONITORING_WINDOW = 300    # Seconds (5 minutes) for median calculation
```

## How It Works

1. **Data Collection**: Every 30 seconds, the service checks CPU usage of each monitored process individually
2. **Rolling Window**: Maintains separate 5-minute rolling windows for each process
3. **Median Analysis**: Calculates median CPU usage for each process over the monitoring window
4. **Alert Trigger**: Triggers when ANY individual process median exceeds threshold (default: 95%)
5. **Evidence Capture**:
   - Saves detailed JSON data with per-process statistics
   - Creates human-readable report showing which processes triggered the alert
   - Captures system CPU information using `top` command

## File Structure

```
macos-cpu-monitor/
├── run_cpu_anlayser.py          # Main monitoring script
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
            └── 19/              # Day
                └── 21/          # Hour
                    ├── cpu_data_20250619_213511.json
                    └── report_20250619_213511.txt
```

## Log Files

### Main Log (`cpu_monitor.log`)
- Startup messages
- Hourly status updates
- Alert notifications
- Error messages

### Evidence Files
When an alert triggers, files are created in Hive partition structure (yyyy/mm/dd/hh):

1. **JSON Data** (`cpu_data_YYYYMMDD_HHMMSS.json`):
   - Current and median CPU usage per process
   - All individual readings for triggering processes
   - Statistical analysis (min, max, average)
   - Process details and PIDs
   - System CPU information from `top` command

2. **Text Report** (`report_YYYYMMDD_HHMMSS.txt`):
   - Human-readable summary with visual indicators
   - Individual process statistics (⚠️ ALERT vs ✅ Normal)
   - Complete 5-minute reading history for triggering processes
   - Current process details with PIDs and commands

## Service Management

### Check Service Status
```bash
launchctl list | grep com.user.cpumonitor
```

### View Live Logs
```bash
tail -f macos_cpu_anlayser/cpu_monitor.log
```

### Manual Start/Stop
```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.user.cpumonitor.plist

# Start
launchctl load ~/Library/LaunchAgents/com.user.cpumonitor.plist
```

### Force Restart
```bash
launchctl unload ~/Library/LaunchAgents/com.user.cpumonitor.plist
launchctl load ~/Library/LaunchAgents/com.user.cpumonitor.plist
```

## Performance Optimization

The service is optimized for minimal system impact:

- **Low Priority**: Runs with `Nice` value of 10 (lower priority)
- **Background Process**: Marked as background type in LaunchAgent
- **Reduced Logging**: Only logs warnings/errors and hourly status
- **Efficient Memory**: Uses deque for rolling window with size limits
- **I/O Throttling**: Low priority I/O operations

## Troubleshooting

### Service Won't Start
1. Check permissions:
   ```bash
   ls -la ~/Library/LaunchAgents/com.user.cpumonitor.plist
   ```

2. Check error logs:
   ```bash
   cat macos-cpu-monitor/cpu_monitor_stderr.log
   ```

3. Verify Python path:
   ```bash
   which python3
   ```

### No Screenshots or Screenshots Show Desktop Only
- **Ensure Python has accessibility permissions:**
  - Go to System Preferences > Security & Privacy > Privacy > Accessibility
  - Add Python (`/usr/bin/python3`) to the list and enable it
  - You may also need to add Terminal if running the script from Terminal
- **Check for permission prompts:**
  - macOS may show permission dialogs when the script first tries to control Activity Monitor
  - Look for system dialogs asking for accessibility permissions
- **Verify Activity Monitor behavior:**
  - Test manually: Open Activity Monitor, press `Ctrl+Cmd+F` to enter full screen
  - If this doesn't work, Activity Monitor may not support full screen on your macOS version
- **Alternative screenshot methods:**
  - If full screen doesn't work, the script will still capture the desktop
  - Check the log files for AppleScript errors that might indicate permission issues

### Plist File Path Issues
1. **Update plist file paths before installation:**
   ```bash
   # Edit the plist file to match your actual path
   nano com.user.cpumonitor.plist
   # Replace all instances of the placeholder path with your actual path
   ```

2. **Common path locations:**
   - Downloaded to Desktop: `/Users/yourusername/Desktop/macos-cpu-monitor/`
   - Downloaded to Downloads: `/Users/yourusername/Downloads/macos-cpu-monitor/`
   - Cloned to home: `/Users/yourusername/macos-cpu-monitor/`

3. **Verify paths are correct:**
   ```bash
   # Check if the Python script exists at the path specified in plist
   ls -la /path/to/your/macos-cpu-monitor/run_cpu_anlayser.py
   ```

### High CPU Usage
- Increase `CHECK_INTERVAL` to reduce frequency
- Check if other processes are interfering

### Missing Evidence
- Verify write permissions in the evidence folder
- Check available disk space

## Security Considerations

- The service runs with user privileges (not root)
- All files are created with user permissions
- No network connections are made
- Only monitors specified processes
- Screenshots are stored locally

## Customization

### Adding New Processes
Add process names to the `PROCESS_NAMES` list. Use partial matches (case-insensitive).

### Changing Alert Behavior
Modify the `monitor()` method to customize:
- Alert frequency
- Evidence collection
- Notification methods

### Custom Reports
Extend the `create_summary_report_with_median()` method for additional data.

## Support

For issues or questions:
1. Check the log files first
2. Verify service status with `launchctl list`
3. Test manual execution: `python3 run_cpu_anlayser.py`
