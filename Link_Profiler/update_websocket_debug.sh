#!/bin/bash
# Copy updated files to server - run this script on your server

echo \"Updating WebSocket files on server...\"

# Backup current files
echo \"Creating backups...\"
cp /opt/Link_Profiler_Repo/Link_Profiler/api/mission_control.py /opt/Link_Profiler_Repo/Link_Profiler/api/mission_control.py.backup.$(date +%Y%m%d_%H%M%S)
cp /opt/Link_Profiler_Repo/Link_Profiler/utils/connection_manager.py /opt/Link_Profiler_Repo/Link_Profiler/utils/connection_manager.py.backup.$(date +%Y%m%d_%H%M%S)

echo \"Files backed up. Now restart the service to pick up changes:\"
echo \"sudo systemctl restart linkprofiler-api.service\"
echo \"journalctl -u linkprofiler-api.service -f --no-pager | grep -E '(WebSocket|JSON|Sending|mission-control)'\"
