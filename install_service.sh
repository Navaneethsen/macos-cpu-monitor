#!/bin/bash

# CPU Monitor Service Installation Script
# This script installs the CPU monitor as a background service that starts at login

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_FILE="com.user.cpumonitor.plist"
LAUNCHAGENTS_DIR="$HOME/Library/LaunchAgents"
SERVICE_NAME="com.user.cpumonitor"

echo "🔧 Installing CPU Monitor Background Service..."
echo "Script directory: $SCRIPT_DIR"

# Create LaunchAgents directory if it doesn't exist
if [ ! -d "$LAUNCHAGENTS_DIR" ]; then
    echo "📁 Creating LaunchAgents directory..."
    mkdir -p "$LAUNCHAGENTS_DIR"
fi

# Stop the service if it's already running
echo "🛑 Stopping existing service (if running)..."
launchctl unload "$LAUNCHAGENTS_DIR/$PLIST_FILE" 2>/dev/null || true

# Copy the plist file to LaunchAgents
echo "📋 Installing service configuration..."
cp "$SCRIPT_DIR/$PLIST_FILE" "$LAUNCHAGENTS_DIR/"

# Set proper permissions
chmod 644 "$LAUNCHAGENTS_DIR/$PLIST_FILE"

# Make the Python script executable
chmod +x "$SCRIPT_DIR/run_cpu_anlayser.py"

# Load the service
echo "🚀 Starting CPU Monitor service..."
launchctl load "$LAUNCHAGENTS_DIR/$PLIST_FILE"

# Verify the service is loaded
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo "✅ CPU Monitor service installed and started successfully!"
    echo ""
    echo "📊 Service Details:"
    echo "   - Service Name: $SERVICE_NAME"
    echo "   - Config File: $LAUNCHAGENTS_DIR/$PLIST_FILE"
    echo "   - Working Directory: $SCRIPT_DIR"
    echo "   - Log Files:"
    echo "     • Main Log: $SCRIPT_DIR/cpu_monitor.log"
    echo "     • Stdout: $SCRIPT_DIR/cpu_monitor_stdout.log"
    echo "     • Stderr: $SCRIPT_DIR/cpu_monitor_stderr.log"
    echo "   - Evidence Folder: $SCRIPT_DIR/cpu_evidence/"
    echo ""
    echo "🔍 Monitor Status:"
    echo "   - The service will automatically start at login"
    echo "   - It runs in the background with low CPU priority"
    echo "   - Status updates are logged every 5 minutes"
    echo "   - Alerts trigger when median CPU > 95% over 5 minutes"
    echo ""
    echo "📝 Management Commands:"
    echo "   - Check status: launchctl list | grep $SERVICE_NAME"
    echo "   - Stop service: launchctl unload $LAUNCHAGENTS_DIR/$PLIST_FILE"
    echo "   - Start service: launchctl load $LAUNCHAGENTS_DIR/$PLIST_FILE"
    echo "   - View logs: tail -f $SCRIPT_DIR/cpu_monitor.log"
else
    echo "❌ Failed to start CPU Monitor service"
    echo "Check the logs for more information:"
    echo "   - $SCRIPT_DIR/cpu_monitor_stderr.log"
    exit 1
fi
