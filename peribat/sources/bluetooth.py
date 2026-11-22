"""Battery level of paired Bluetooth devices, as Windows exposes it."""
from __future__ import annotations

import json
import logging
import subprocess
from typing import List

from ..kinds import guess_kind
from ..model import Reading

KEY = "bluetooth"
LABEL = "Bluetooth"
INTERVAL = 120  # seconds between scans; starting PowerShell is the expensive part

log = logging.getLogger(__name__)

# DEVPKEY_Bluetooth_Battery = {104EA319-6EE2-4701-BD47-8DDBF425BBE5}, 2
_SCRIPT = r"""
$key = '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2'
$out = @()
Get-PnpDevice -PresentOnly | Where-Object {
    $_.InstanceId -like 'BTHENUM\DEV_*' -or $_.InstanceId -like 'BTHLE\DEV_*'
} | ForEach-Object {
    $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName $key -ErrorAction SilentlyContinue
    if ($p -and $null -ne $p.Data) {
        $out += [pscustomobject]@{ name = $_.FriendlyName; level = [int]$p.Data }
    }
}
@($out) | ConvertTo-Json -Compress
"""


def parse(output: str) -> List[Reading]:
    """Turn the script's JSON output into readings."""
    text = output.strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    best = {}
    for item in data:
        name = item.get("name") or "Bluetooth device"
        level = int(item.get("level", -1))
        if 0 <= level <= 100:
            best[name] = max(best.get(name, 0), level)  # one device can list several nodes
    return [Reading(n, lvl, False, guess_kind(n), KEY) for n, lvl in best.items()]


def scan() -> List[Reading]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
        capture_output=True, text=True, timeout=30,
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
    return parse(result.stdout)
