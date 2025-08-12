#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test Error Notification System
    
.DESCRIPTION
    This script tests the error notification system by triggering error notifications
    and checking the notification status.
#>

param(
    [switch]$Force,
    [switch]$Status,
    [switch]$Cleanup
)

Import-Module "$PSScriptRoot/modules/Output.psm1" -Force
Import-Module "$PSScriptRoot/modules/Kube.psm1" -Force

# Use Get-SafetyAmpPod from Kube module directly

function Test-ErrorNotification {
    param([string]$PodName)
    
        Write-ColorOutput "`n🧪 Testing Error Notification System..." -Color Magenta
    
    try {
        # Test 1: Check notification status
        Write-ColorOutput "`n📊 Checking notification status..." -Color Cyan
        $status_result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

status = event_manager.error_notifier.get_notification_status()
print('NOTIFICATION_STATUS_START')
import json
print(json.dumps(status, indent=2))
print('NOTIFICATION_STATUS_END')
"
        
        if ($status_result -match 'NOTIFICATION_STATUS_START(.*?)NOTIFICATION_STATUS_END') {
            $status_data = $matches[1].Trim() | ConvertFrom-Json
            Write-ColorOutput "✅ Notification Status:" -Color Green
            Write-ColorOutput "  Total Errors (Last Hour): $($status_data.total_errors_last_hour)" -Color Cyan
            Write-ColorOutput "  Should Send Notification: $($status_data.should_send_notification)" -Color Cyan
            Write-ColorOutput "  Last Notification: $($status_data.last_notification_sent)" -Color Cyan
            
            if ($status_data.error_breakdown) {
                Write-ColorOutput "  Error Breakdown:" -Color Cyan
                foreach ($error_type in $status_data.error_breakdown.GetEnumerator()) {
                    Write-ColorOutput "    $($error_type.Key): $($error_type.Value)" -Color Cyan
                }
            }
        }
        
        # Test 2: Force send notification if requested
        if ($Force) {
            Write-ColorOutput "`n📧 Forcing error notification..." -Color Cyan
            $force_result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

# Log a test error
event_manager.log_error(
    error_type='test_error',
    entity_type='test',
    entity_id='test_123',
    error_message='This is a test error for notification testing',
    error_details={'test': True, 'timestamp': 'test'},
    source='test_script'
)

# Send notification
result = event_manager.send_hourly_notification()
print('FORCE_NOTIFICATION_RESULT_START')
print(result)
print('FORCE_NOTIFICATION_RESULT_END')
"
            
            if ($force_result -match 'FORCE_NOTIFICATION_RESULT_START(.*?)FORCE_NOTIFICATION_RESULT_END') {
                $force_data = $matches[1].Trim()
                if ($force_data -eq "True") {
                    Write-ColorOutput "✅ Test notification sent successfully!" -Color Green
                } else {
                    Write-ColorOutput "⚠️  Test notification not sent (no errors or already sent recently)" -Color Yellow
                }
            }
        }
        
        # Test 3: Check error log
        Write-ColorOutput "`n📋 Checking error log..." -Color Cyan
        $log_result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

recent_errors = event_manager.error_notifier.get_errors_since(hours=24)
print('ERROR_LOG_START')
import json
print(json.dumps(recent_errors, indent=2))
print('ERROR_LOG_END')
"
        
        if ($log_result -match 'ERROR_LOG_START(.*?)ERROR_LOG_END') {
            $log_data = $matches[1].Trim() | ConvertFrom-Json
            Write-ColorOutput "✅ Error Log (Last 24 hours):" -Color Green
            Write-ColorOutput "  Total Errors: $($log_data.Count)" -Color Cyan
            
            if ($log_data.Count -gt 0) {
                Write-ColorOutput "  Recent Errors:" "Info"
                foreach ($errorItem in $log_data[0..2]) {  # Show first 3 errors
                    $timestamp = [datetime]::Parse($errorItem.timestamp).ToString("HH:mm:ss")
                    Write-ColorOutput "    [$timestamp] $($errorItem.error_type) - $($errorItem.entity_type) $($errorItem.entity_id)" -Color Cyan
                    Write-ColorOutput "      Message: $($errorItem.error_message)" -Color Yellow
                }
            }
        }
        
    }
    catch {
        Write-ColorOutput "❌ Error testing notification system: $_" -Color Red
    }
}

function Get-NotificationStatus {
    param([string]$PodName)
    
    Write-ColorOutput "`n📊 Error Notification Status" "Header"
    
    try {
        $status_result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

status = event_manager.error_notifier.get_notification_status()
print('STATUS_START')
import json
print(json.dumps(status, indent=2))
print('STATUS_END')
"
        
        if ($status_result -match 'STATUS_START(.*?)STATUS_END') {
            $status_data = $matches[1].Trim() | ConvertFrom-Json
            Write-ColorOutput "✅ Status Retrieved Successfully" "Success"
            Write-ColorOutput "  Errors in Last Hour: $($status_data.total_errors_last_hour)" "Info"
            Write-ColorOutput "  Should Send Notification: $($status_data.should_send_notification)" "Info"
            Write-ColorOutput "  Last Notification: $($status_data.last_notification_sent)" "Info"
        }
    }
    catch {
        Write-ColorOutput "❌ Error getting status: $_" "Error"
    }
}

function Remove-OldErrors {
    param([string]$PodName)
    
    Write-ColorOutput "`n🧹 Cleaning up old errors..." "Header"
    
    try {
        $cleanup_result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')
from services.event_manager import event_manager

# Clean up errors older than 7 days
event_manager.error_notifier.cleanup_old_errors(days=7)
print('CLEANUP_COMPLETE')
"
        
        if ($cleanup_result -match 'CLEANUP_COMPLETE') {
            Write-ColorOutput "✅ Cleanup completed successfully" "Success"
        }
    }
    catch {
        Write-ColorOutput "❌ Error during cleanup: $_" "Error"
    }
}

# Main execution
Write-ColorOutput "🔍 SafetyAmp Error Notification Tester" "Header"

$pod = Get-SafetyAmpPod
if (-not $pod) {
    Write-ColorOutput "❌ No SafetyAmp pods found running" "Error"
    exit 1
}

Write-ColorOutput "📦 Using pod: $pod" "Info"

if ($Status) {
    Get-NotificationStatus -PodName $pod
}
elseif ($Cleanup) {
    Remove-OldErrors -PodName $pod
}
else {
    Test-ErrorNotification -PodName $pod
}

Write-ColorOutput "`n✅ Testing completed!" "Success"
