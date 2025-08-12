using module ./Output.psm1
using module ./Kube.psm1
# Troubleshooting helpers for fix-* and testing scripts

Set-StrictMode -Version Latest

function Get-NotificationStatusData {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$PodName, [string]$Namespace = 'safety-amp')
    $script = @"
import sys
sys.path.append('/app')
from services.event_manager import event_manager
status = event_manager.error_notifier.get_notification_status()
print('STATUS_START')
import json
print(json.dumps(status, indent=2))
print('STATUS_END')
"@
    $result = kubectl exec $PodName -n $Namespace -- python -c "$script"
    if ($result -match 'STATUS_START(.*?)STATUS_END') {
        return ($matches[1].Trim() | ConvertFrom-Json)
    }
    return $null
}

Export-ModuleMember -Function Get-NotificationStatusData


