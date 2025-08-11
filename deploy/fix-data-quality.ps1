#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fix SafetyAmp Integration Data Quality Issues
    
.DESCRIPTION
    This script helps diagnose and fix common data quality issues that cause
    422 errors in the SafetyAmp API integration.
    
.PARAMETER Action
    The action to perform:
    - "analyze": Analyze data quality issues (default)
    - "validate": Validate employee data
    - "cleanup": Clean up duplicate data
    - "report": Generate detailed report
    
.PARAMETER Hours
    Number of hours to analyze (default: 24)
    
.EXAMPLE
    .\fix-data-quality.ps1
    .\fix-data-quality.ps1 -Action "validate" -Hours 48
    .\fix-data-quality.ps1 -Action "report"
#>

param(
    [string]$Action = "analyze",
    [int]$Hours = 24
)

Write-Host "🔧 SafetyAmp Data Quality Fix Tool" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

# Get pod name
$pods = kubectl get pods -n safety-amp -l app=safety-amp,component=agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if (-not $pods) {
    Write-Host "❌ No SafetyAmp pods found!" -ForegroundColor Red
    return
}

$Pod = $pods
Write-Host "📦 Using pod: $Pod" -ForegroundColor Yellow

function Get-ErrorAnalysis {
    param([string]$PodName, [int]$HoursBack)
    
    Write-Host "`n🔍 Analyzing errors from the last $HoursBack hours..." -ForegroundColor Green
    
    $sinceTime = (Get-Date).AddHours(-$HoursBack).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logs = kubectl logs -n safety-amp $PodName --since-time=$sinceTime 2>$null
    
    # Analyze 422 errors
    $errors422 = $logs | Select-String -Pattern "422 Client Error" | Select-Object -Last 100
    
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
    
    Write-Host "`n📊 Error Analysis Summary:" -ForegroundColor Cyan
    foreach ($type in $errorTypes.GetEnumerator()) {
        if ($type.Value -gt 0) {
            $color = if ($type.Value -gt 10) { "Red" } elseif ($type.Value -gt 5) { "Yellow" } else { "Green" }
            Write-Host "  $($type.Key): $($type.Value) occurrences" -ForegroundColor $color
        }
    }
    
    return $errorTypes
}

function Get-DataValidationReport {
    param([string]$PodName)
    
    Write-Host "`n🔍 Generating data validation report..." -ForegroundColor Green
    
    # Execute validation script in the pod
    $result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')

try:
    from sync.sync_employees import EmployeeSync
    from services.safetyamp_api import SafetyAmpAPI
    from utils.data_manager import data_manager
    
    # Initialize components
    cache = data_manager
    api = SafetyAmpAPI()
    
    # Get employee data
    employees = cache.get_employees()
    
    print('VALIDATION_DATA_START')
    
    # Analyze data quality
    total_employees = len(employees)
    missing_first_name = 0
    missing_last_name = 0
    missing_email = 0
    missing_mobile = 0
    duplicate_emails = 0
    duplicate_mobiles = 0
    
    emails = []
    mobiles = []
    
    for emp in employees:
        if not emp.get('first_name'):
            missing_first_name += 1
        if not emp.get('last_name'):
            missing_last_name += 1
        if not emp.get('email'):
            missing_email += 1
        if not emp.get('mobile_phone'):
            missing_mobile += 1
            
        if emp.get('email'):
            emails.append(emp['email'])
        if emp.get('mobile_phone'):
            mobiles.append(emp['mobile_phone'])
    
    # Check for duplicates
    from collections import Counter
    email_counts = Counter(emails)
    mobile_counts = Counter(mobiles)
    
    duplicate_emails = sum(1 for count in email_counts.values() if count > 1)
    duplicate_mobiles = sum(1 for count in mobile_counts.values() if count > 1)
    
    print(f'Total Employees: {total_employees}')
    print(f'Missing First Name: {missing_first_name}')
    print(f'Missing Last Name: {missing_last_name}')
    print(f'Missing Email: {missing_email}')
    print(f'Missing Mobile: {missing_mobile}')
    print(f'Duplicate Emails: {duplicate_emails}')
    print(f'Duplicate Mobiles: {duplicate_mobiles}')
    
    print('VALIDATION_DATA_END')
    
except Exception as e:
    print(f'Error: {str(e)}')
    print('VALIDATION_DATA_END')
"
    
    if ($result -match 'VALIDATION_DATA_START(.*?)VALIDATION_DATA_END') {
        $validationData = $matches[1].Trim()
        Write-Host "`n📋 Data Quality Report:" -ForegroundColor Cyan
        Write-Host $validationData -ForegroundColor White
        return $validationData
    } else {
        Write-Host "❌ Failed to get validation data" -ForegroundColor Red
        return $null
    }
}

function Show-Recommendations {
    param($ErrorTypes, $ValidationData)
    
    Write-Host "`n💡 Recommendations:" -ForegroundColor Cyan
    Write-Host "===================" -ForegroundColor Cyan
    
    if ($ErrorTypes["Missing First Name"] -gt 0) {
        Write-Host "`n🔴 Missing First Names ($($ErrorTypes['Missing First Name']) errors):" -ForegroundColor Red
        Write-Host "  - Check your source system for employees with missing first names" -ForegroundColor Yellow
        Write-Host "  - Consider using a default value or skipping these records" -ForegroundColor Yellow
        Write-Host "  - Review data import process to ensure first_name is always populated" -ForegroundColor Yellow
    }
    
    if ($ErrorTypes["Missing Last Name"] -gt 0) {
        Write-Host "`n🔴 Missing Last Names ($($ErrorTypes['Missing Last Name']) errors):" -ForegroundColor Red
        Write-Host "  - Check your source system for employees with missing last names" -ForegroundColor Yellow
        Write-Host "  - Consider using a default value or skipping these records" -ForegroundColor Yellow
        Write-Host "  - Review data import process to ensure last_name is always populated" -ForegroundColor Yellow
    }
    
    if ($ErrorTypes["Missing Email"] -gt 0) {
        Write-Host "`n🔴 Missing Emails ($($ErrorTypes['Missing Email']) errors):" -ForegroundColor Red
        Write-Host "  - Check your source system for employees with missing email addresses" -ForegroundColor Yellow
        Write-Host "  - Consider generating email addresses from name if possible" -ForegroundColor Yellow
        Write-Host "  - Review data import process to ensure email is always populated" -ForegroundColor Yellow
    }
    
    if ($ErrorTypes["Duplicate Mobile Phone"] -gt 0) {
        Write-Host "`n🔴 Duplicate Mobile Phones ($($ErrorTypes['Duplicate Mobile Phone']) errors):" -ForegroundColor Red
        Write-Host "  - Identify employees with duplicate mobile phone numbers" -ForegroundColor Yellow
        Write-Host "  - Decide which record should keep the phone number" -ForegroundColor Yellow
        Write-Host "  - Update or remove duplicate phone numbers in source system" -ForegroundColor Yellow
    }
    
    if ($ErrorTypes["Duplicate Email"] -gt 0) {
        Write-Host "`n🔴 Duplicate Emails ($($ErrorTypes['Duplicate Email']) errors):" -ForegroundColor Red
        Write-Host "  - Identify employees with duplicate email addresses" -ForegroundColor Yellow
        Write-Host "  - Decide which record should keep the email address" -ForegroundColor Yellow
        Write-Host "  - Update or remove duplicate emails in source system" -ForegroundColor Yellow
    }
    
    Write-Host "`n🔄 General Recommendations:" -ForegroundColor Green
    Write-Host "  - Implement data validation before sending to SafetyAmp API" -ForegroundColor Yellow
    Write-Host "  - Add retry logic with exponential backoff for rate limiting" -ForegroundColor Yellow
    Write-Host "  - Consider implementing a data quality dashboard" -ForegroundColor Yellow
    Write-Host "  - Review and update site mappings for missing departments" -ForegroundColor Yellow
}

# Main execution
switch ($Action.ToLower()) {
    "analyze" {
        $errorTypes = Get-ErrorAnalysis -PodName $Pod -HoursBack $Hours
        $validationData = Get-DataValidationReport -PodName $Pod
        Show-Recommendations -ErrorTypes $errorTypes -ValidationData $validationData
    }
    "validate" {
        Get-DataValidationReport -PodName $Pod
    }
    "report" {
        $errorTypes = Get-ErrorAnalysis -PodName $Pod -HoursBack $Hours
        $validationData = Get-DataValidationReport -PodName $Pod
        
        Write-Host "`n📄 Detailed Report:" -ForegroundColor Cyan
        Write-Host "=================" -ForegroundColor Cyan
        Write-Host "Generated: $(Get-Date)" -ForegroundColor Gray
        Write-Host "Pod: $Pod" -ForegroundColor Gray
        Write-Host "Analysis Period: $Hours hours" -ForegroundColor Gray
        
        Show-Recommendations -ErrorTypes $errorTypes -ValidationData $validationData
    }
    default {
        Write-Host "❌ Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available actions: analyze, validate, report" -ForegroundColor Yellow
        return
    }
}

Write-Host "`n✅ Data quality analysis complete!" -ForegroundColor Green
