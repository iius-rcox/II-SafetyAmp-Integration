#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Monitor SafetyAmp Integration Data Validation and Quality
    
.DESCRIPTION
    This script monitors the data validation improvements and tracks
    data quality metrics for the SafetyAmp integration.
    
.PARAMETER Action
    The monitoring action to perform:
    - "validation-stats": Show validation statistics
    - "error-trends": Show error trend analysis
    - "data-quality": Show data quality metrics
    - "validation-summary": Show comprehensive validation summary
    
.PARAMETER Hours
    Number of hours to analyze (default: 24)
    
.EXAMPLE
    .\monitor-validation.ps1 -Action "validation-stats"
    .\monitor-validation.ps1 -Action "error-trends" -Hours 48
    .\monitor-validation.ps1 -Action "data-quality"
#>

param(
    [string]$Action = "validation-summary",
    [int]$Hours = 24
)

Write-Host "🔍 SafetyAmp Data Validation Monitor" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Get pod name
$pods = kubectl get pods -n safety-amp -l app=safety-amp,component=agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if (-not $pods) {
    Write-Host "❌ No SafetyAmp pods found!" -ForegroundColor Red
    return
}

$Pod = $pods
Write-Host "📦 Using pod: $Pod" -ForegroundColor Yellow

function Get-ValidationStatistics {
    param([string]$PodName, [int]$HoursBack)
    
    Write-Host "`n📊 Validation Statistics (Last $HoursBack hours)" -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Green
    
    $sinceTime = (Get-Date).AddHours(-$HoursBack).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logs = kubectl logs -n safety-amp $PodName --since-time=$sinceTime 2>$null
    
    # Count validation-related log entries
    $validationLogs = $logs | Select-String -Pattern "Validation|validation|Generated|generated|Missing required|Invalid"
    
    $stats = @{
        "Total Validation Logs" = $validationLogs.Count
        "Generated Default Names" = ($logs | Select-String -Pattern "Generated default.*name").Count
        "Generated Emails" = ($logs | Select-String -Pattern "Generated email").Count
        "Missing Required Fields" = ($logs | Select-String -Pattern "Missing required field").Count
        "Invalid Email Formats" = ($logs | Select-String -Pattern "Invalid email format").Count
        "Invalid Phone Formats" = ($logs | Select-String -Pattern "Invalid phone format").Count
        "Validation Errors" = ($logs | Select-String -Pattern "Validation errors").Count
        "Validation Failed" = ($logs | Select-String -Pattern "Validation failed").Count
    }
    
    foreach ($stat in $stats.GetEnumerator()) {
        $color = if ($stat.Value -gt 0) { "Yellow" } else { "Green" }
        Write-Host "  $($stat.Key): $($stat.Value)" -ForegroundColor $color
    }
    
    return $stats
}

function Get-ErrorTrends {
    param([string]$PodName, [int]$HoursBack)
    
    Write-Host "`n📈 Error Trend Analysis (Last $HoursBack hours)" -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Green
    
    $sinceTime = (Get-Date).AddHours(-$HoursBack).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logs = kubectl logs -n safety-amp $PodName --since-time=$sinceTime 2>$null
    
    # Analyze 422 errors over time
    $errors422 = $logs | Select-String -Pattern "422 Client Error" | Select-Object -Last 50
    
    $errorTypes = @{
        "Missing First Name" = 0
        "Missing Last Name" = 0
        "Missing Email" = 0
        "Duplicate Mobile Phone" = 0
        "Duplicate Email" = 0
        "Other 422 Errors" = 0
    }
    
    foreach ($errorEntry in $errors422) {
        if ($errorEntry.Line -match "first_name.*required") {
            $errorTypes["Missing First Name"]++
        }
        if ($errorEntry.Line -match "last_name.*required") {
            $errorTypes["Missing Last Name"]++
        }
        if ($errorEntry.Line -match "email.*required") {
            $errorTypes["Missing Email"]++
        }
        if ($errorEntry.Line -match "mobile phone.*already been taken") {
            $errorTypes["Duplicate Mobile Phone"]++
        }
        if ($errorEntry.Line -match "email.*already been taken") {
            $errorTypes["Duplicate Email"]++
        }
        if ($errorEntry.Line -match "422 Client Error") {
            $errorTypes["Other 422 Errors"]++
        }
    }
    
    Write-Host "`n🔴 422 Error Breakdown:" -ForegroundColor Red
    foreach ($type in $errorTypes.GetEnumerator()) {
        if ($type.Value -gt 0) {
            $color = if ($type.Value -gt 10) { "Red" } elseif ($type.Value -gt 5) { "Yellow" } else { "Green" }
            Write-Host "  $($type.Key): $($type.Value) occurrences" -ForegroundColor $color
        }
    }
    
    # Show recent validation improvements
    $recentValidationLogs = $logs | Select-String -Pattern "Generated.*for employee" | Select-Object -Last 10
    if ($recentValidationLogs) {
        Write-Host "`n✅ Recent Validation Improvements:" -ForegroundColor Green
        foreach ($log in $recentValidationLogs) {
            Write-Host "  $($log.Line)" -ForegroundColor Gray
        }
    }
    
    return $errorTypes
}

function Get-DataQualityMetrics {
    param([string]$PodName)
    
    Write-Host "`n📋 Data Quality Metrics" -ForegroundColor Green
    Write-Host "=======================" -ForegroundColor Green
    
    # Execute data quality analysis in the pod
    $result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')

try:
    from utils.data_validator import validator
    from utils.data_manager import data_manager
    
    # Initialize cache
    cache = data_manager
    
    # Get employee data
    employees = cache.get_employees()
    
    print('DATA_QUALITY_START')
    
    # Analyze data quality
    total_employees = len(employees)
    missing_first_name = 0
    missing_last_name = 0
    missing_email = 0
    invalid_emails = 0
    invalid_phones = 0
    
    for emp in employees:
        if not emp.get('first_name'):
            missing_first_name += 1
        if not emp.get('last_name'):
            missing_last_name += 1
        if not emp.get('email'):
            missing_email += 1
        elif emp.get('email'):
            # Basic email validation
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, emp['email']):
                invalid_emails += 1
        
        # Phone validation
        for phone_field in ['mobile_phone', 'work_phone']:
            phone = emp.get(phone_field)
            if phone:
                cleaned = re.sub(r'\D', '', str(phone))
                if len(cleaned) < 10:
                    invalid_phones += 1
    
    print(f'Total Employees: {total_employees}')
    print(f'Missing First Name: {missing_first_name}')
    print(f'Missing Last Name: {missing_last_name}')
    print(f'Missing Email: {missing_email}')
    print(f'Invalid Emails: {invalid_emails}')
    print(f'Invalid Phones: {invalid_phones}')
    
    # Calculate quality scores
    if total_employees > 0:
        name_quality = ((total_employees - missing_first_name - missing_last_name) / (total_employees * 2)) * 100
        email_quality = ((total_employees - missing_email - invalid_emails) / total_employees) * 100
        overall_quality = (name_quality + email_quality) / 2
        
        print(f'Name Quality Score: {name_quality:.1f}%')
        print(f'Email Quality Score: {email_quality:.1f}%')
        print(f'Overall Quality Score: {overall_quality:.1f}%')
    
    print('DATA_QUALITY_END')
    
except Exception as e:
    print(f'Error: {str(e)}')
    print('DATA_QUALITY_END')
"
    
    if ($result -match 'DATA_QUALITY_START(.*?)DATA_QUALITY_END') {
        $qualityData = $matches[1].Trim()
        Write-Host "`n📊 Current Data Quality:" -ForegroundColor Cyan
        Write-Host $qualityData -ForegroundColor White
        return $qualityData
    } else {
        Write-Host "❌ Failed to get data quality metrics" -ForegroundColor Red
        return $null
    }
}

function Show-ValidationSummary {
    param([string]$PodName, [int]$HoursBack)
    
    Write-Host "`n📄 Comprehensive Validation Summary" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host "Generated: $(Get-Date)" -ForegroundColor Gray
    Write-Host "Pod: $PodName" -ForegroundColor Gray
    Write-Host "Analysis Period: $HoursBack hours" -ForegroundColor Gray
    
    # Get all metrics
    $validationStats = Get-ValidationStatistics -PodName $PodName -HoursBack $HoursBack
    $errorTrends = Get-ErrorTrends -PodName $PodName -HoursBack $HoursBack
    $dataQuality = Get-DataQualityMetrics -PodName $PodName
    
    Write-Host "`n💡 Validation Improvements Summary:" -ForegroundColor Green
    Write-Host "===================================" -ForegroundColor Green
    
    if ($validationStats["Generated Default Names"] -gt 0) {
        Write-Host "✅ Auto-generated missing names: $($validationStats['Generated Default Names'])" -ForegroundColor Green
    }
    
    if ($validationStats["Generated Emails"] -gt 0) {
        Write-Host "✅ Auto-generated missing emails: $($validationStats['Generated Emails'])" -ForegroundColor Green
    }
    
    if ($validationStats["Validation Errors"] -gt 0) {
        Write-Host "⚠️  Validation errors detected: $($validationStats['Validation Errors'])" -ForegroundColor Yellow
    }
    
    if ($errorTrends["Missing First Name"] -gt 0 -or $errorTrends["Missing Last Name"] -gt 0 -or $errorTrends["Missing Email"] -gt 0) {
        Write-Host "🔴 Still have missing required fields in source data" -ForegroundColor Red
    }
    
    Write-Host "`n🚀 Recommendations:" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan
    
    if ($validationStats["Missing Required Fields"] -gt 0) {
        Write-Host "  - Fix missing required fields in source system" -ForegroundColor Yellow
    }
    
    if ($validationStats["Invalid Email Formats"] -gt 0) {
        Write-Host "  - Review email format validation in source system" -ForegroundColor Yellow
    }
    
    if ($validationStats["Invalid Phone Formats"] -gt 0) {
        Write-Host "  - Review phone number format validation in source system" -ForegroundColor Yellow
    }
    
    Write-Host "  - Continue monitoring validation improvements" -ForegroundColor Yellow
    Write-Host "  - Consider implementing source-side data validation" -ForegroundColor Yellow
}

# Main execution
switch ($Action.ToLower()) {
    "validation-stats" {
        Get-ValidationStatistics -PodName $Pod -HoursBack $Hours
    }
    "error-trends" {
        Get-ErrorTrends -PodName $Pod -HoursBack $Hours
    }
    "data-quality" {
        Get-DataQualityMetrics -PodName $Pod
    }
    "validation-summary" {
        Show-ValidationSummary -PodName $Pod -HoursBack $Hours
    }
    default {
        Write-Host "❌ Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available actions: validation-stats, error-trends, data-quality, validation-summary" -ForegroundColor Yellow
        return
    }
}

Write-Host "`n✅ Validation monitoring complete!" -ForegroundColor Green
