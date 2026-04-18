#!/bin/bash
# This script is triggered by udev hardware events

# Create a flag file for the Python Engine to detect
echo "connected" > /tmp/recam_phone_status

# Ensure the file is readable/writable by your normal user
chmod 666 /tmp/recam_phone_status

# Log the event for your own debugging
echo "$(date): Phone plugged in" >> /tmp/recam_debug.log