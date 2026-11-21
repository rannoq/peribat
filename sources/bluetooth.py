"""Battery levels of paired Bluetooth devices, as exposed by Windows."""
import json
import subprocess

# DEVPKEY_Bluetooth_Battery
PS_SCRIPT = r"""
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


def read():
    """Return a list of (name, level_percent, charging, kind_or_None)."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_SCRIPT],
            capture_output=True, text=True, timeout=30,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        raw = res.stdout.strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        best = {}
        for d in data:
            name = d.get("name") or "Bluetooth device"
            lvl = int(d.get("level", -1))
            if 0 <= lvl <= 100:
                best[name] = max(best.get(name, 0), lvl)
        return [(n, l, False, None) for n, l in best.items()]
    except Exception:
        return []
