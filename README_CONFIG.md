# CPU Monitor Configuration System

The CPU monitor now supports dynamic configuration through a JSON configuration file that can be modified at runtime without restarting the service.

## Configuration File
If you want to monitor specific processes, set CPU thresholds, and adjust monitoring parameters dynamically, you can create a `config.json` file as shown below. This allows you to customize the monitoring behavior without needing to stop or restart the launchd service.

The configuration has the following structure:

```json
{
  "process_names": [
    // List of process names to monitor
  ],
  "cpu_threshold": 95.0,
  "check_interval": 30,
  "monitoring_window": 300,
  "evidence_folder": "cpu_evidence",
  "log_file": "cpu_monitor.log"
}
```

## Configuration Parameters

- **process_names**: Array of process names to monitor
- **cpu_threshold**: CPU usage percentage threshold (0-100)
- **check_interval**: Seconds between CPU checks
- **monitoring_window**: Time window in seconds for median calculation
- **evidence_folder**: Directory to store evidence files
- **log_file**: Log file path

## Dynamic Configuration Updates

The CPU monitor checks for configuration changes every 60 seconds and automatically reloads the configuration without requiring a restart.

### Manual Configuration Updates

You can modify the `config.json` file directly or use the provided utility script:

```bash
# Show current configuration
python update_config.py show

# Update CPU threshold to 80%
python update_config.py threshold 80

# Update check interval to 60 seconds
python update_config.py interval 60

# Update monitoring window to 10 minutes (600 seconds)
python update_config.py window 600

# Add a new process to monitor
python update_config.py add-process "new_daemon"

# Remove a process from monitoring
python update_config.py remove-process "old_process"
```

## How It Works

1. **Startup**: The monitor loads the initial configuration from `config.json`
2. **Runtime Monitoring**: Every 60 seconds, the monitor checks if `config.json` has been modified
3. **Automatic Reload**: If changes are detected, the configuration is reloaded automatically
4. **Process Tracking**: New processes are added to monitoring, existing data is preserved
5. **Logging**: Configuration changes are logged for audit purposes


## Example Workflow

1. **Start the monitor**: The service reads the initial configuration
2. **Monitor processes**: CPU monitoring begins with configured settings
3. **Update threshold**: Use `python update_config.py threshold 75` to lower the alert threshold
4. **Add new process**: Use `python update_config.py add-process "suspicious_app"` to monitor a new process
5. **Verify changes**: The monitor automatically picks up changes within 60 seconds
6. **Check logs**: Configuration reload events are logged in the monitor log file

## Configuration Validation

The system includes validation to ensure:
- CPU threshold is between 0-100%
- Time intervals are positive integers
- Process names are valid strings
- File paths are accessible
- JSON syntax is correct

Invalid configurations will log warnings and continue using the previous valid configuration.

## Integration with launchd

The launchd service will automatically use the latest configuration without requiring:
- Service restart
- Plist file modification
- Manual intervention

This makes it ideal for production environments where you need to adjust monitoring parameters based on changing system conditions or new security requirements.
