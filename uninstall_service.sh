#!/bin/bash

# CPU Monitor Service Uninstallation Script
# This script removes the CPU monitor background service

set -e

PLIST_FILE="com.user.cpumonitor.plist"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"
SERVICE_NAME="com.user.cpumonitor"

echo "🗑️  Uninstalling CPU Monitor Background Service..."

# Check if service is running and stop it
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo "🛑 Stopping CPU Monitor service..."
    launchctl unload "$LAUNCHAGENTS_DIR/$PLIST_FILE"
    echo "✅ Service stopped"
else
    echo "ℹ️  Service is not currently running"
fi

# Remove the plist file
if [ -f "$LAUNCHAGENTS_DIR/$PLIST_FILE" ]; then
    echo "🗂️  Removing service configuration..."
    rm "$LAUNCHAGENTS_DIR/$PLIST_FILE"
    echo "✅ Configuration file removed"
else
    echo "ℹ️  Configuration file not found"
fi

# Verify removal
if ! launchctl list | grep -q "$SERVICE_NAME"; then
    echo "✅ CPU Monitor service uninstalled successfully!"
    echo ""
    echo "📝 Note: Log files and evidence data have been preserved:"
    echo "   - cpu_monitor.log"
    echo "   - cpu_monitor_stdout.log" 
    echo "   - cpu_monitor_stderr.log"
    echo "   - cpu_evidence/ folder"
    echo ""
    echo "Delete these manually if you no longer need them."
else
    echo "❌ Failed to uninstall service completely"
    echo "You may need to restart your system or manually remove:"
    echo "   $LAUNCHAGENTS_DIR/$PLIST_FILE"
fi
