# Individual Process Instance Tracking

The CPU monitor now tracks multiple processes with the same name separately based on their full command line, providing granular monitoring of individual process instances.

## Key Features

### Individual Process Tracking
- **Separate Monitoring**: Each process instance is tracked individually by PID and full command line
- **Unique Identification**: Process instances are identified by `process_name:pid:full_command`
- **Independent Thresholds**: Each process instance has its own CPU threshold monitoring
- **Command-Based Differentiation**: Processes with the same name but different arguments are tracked separately

### Enhanced Process Detection
- **Full Command Line**: Uses `ps -A -o pid,pcpu,args` to capture complete command arguments
- **Precise Matching**: Matches process names within the full command line for accurate detection
- **Multiple Instances**: Handles multiple instances of the same process running simultaneously

### Individual Alerting
When a process instance exceeds the CPU threshold, alerts include:
- Process name and PID
- Full command line
- Individual CPU usage (current and median)
- Separate monitoring windows per instance

## Example Scenarios

### Multiple Chrome Processes
If you're monitoring "chrome" and have multiple Chrome processes:
```
chrome:1234:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer
chrome:1235:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=gpu-process
chrome:1236:/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=utility
```

Each process is monitored independently with its own:
- CPU usage history
- Median calculations
- Threshold monitoring
- Alert generation

### Multiple Java Applications
For Java applications with different arguments:
```
java:5678:java -Xmx2g -jar application1.jar
java:5679:java -Xmx4g -jar application2.jar --config=prod
```

Each Java process is tracked separately based on its unique command line.

## Configuration

The same `config.json` file is used, but now each matching process name can result in multiple individual process instances being monitored:

```json
{
  "process_names": [
    "chrome",
    "java",
    "python"
  ],
  "cpu_threshold": 95.0,
  "check_interval": 30,
  "monitoring_window": 300
}
```

## Alert Format

Alerts now show individual process details:

```
HIGH CPU ALERT! Individual process instances exceeding 95.0% median over 300s:
  chrome (PID: 1234): Current: 98.5%, Median: 96.2%
    Command: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer --field-trial-handle=...
  java (PID: 5678): Current: 97.1%, Median: 95.8%
    Command: java -Xmx2g -jar myapp.jar --spring.profiles.active=production
```

## Evidence Collection

Evidence files now include:
- **Individual Process Data**: Separate CPU readings for each process instance
- **Process Identification**: Full command lines and PIDs
- **Instance-Specific Medians**: Individual median calculations per process
- **Command Differentiation**: Clear distinction between different instances

