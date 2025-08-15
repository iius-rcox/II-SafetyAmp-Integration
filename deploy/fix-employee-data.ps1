#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fix Employee Data Issues for SafetyAmp Integration
    
.DESCRIPTION
    This script helps identify and fix specific employee data issues that cause
    422 errors in the SafetyAmp API integration.
    
.PARAMETER Action
    The action to perform:
    - "list-missing": List employees with missing required fields
    - "list-duplicates": List employees with duplicate data
    - "list-skipped": List employees being skipped due to site mapping issues
    - "validate": Validate all employee data
    
.EXAMPLE
    .\fix-employee-data.ps1 -Action "list-missing"
    .\fix-employee-data.ps1 -Action "list-duplicates"
    .\fix-employee-data.ps1 -Action "validate"
#>

param(
    [string]$Action = "list-missing"
)

Write-Host "👥 Employee Data Fix Tool" -ForegroundColor Cyan
Write-Host "=======================" -ForegroundColor Cyan

# Get pod name
$pods = kubectl get pods -n safety-amp -l app=safety-amp,component=agent -o jsonpath='{.items[0].metadata.name}' 2>$null
if (-not $pods) {
    Write-Host "❌ No SafetyAmp pods found!" -ForegroundColor Red
    return
}

$Pod = $pods
Write-Host "📦 Using pod: $Pod" -ForegroundColor Yellow

function Get-EmployeeData {
    param([string]$PodName)
    
    Write-Host "`n🔍 Fetching employee data..." -ForegroundColor Green
    
    $result = kubectl exec $PodName -n safety-amp -- python -c "
import sys
sys.path.append('/app')

try:
    from services.data_manager import data_manager
    from services.safetyamp_api import SafetyAmpAPI
    api = SafetyAmpAPI()
    # Get employee data via data_manager (users by id)
    employees_by_id = data_manager.get_cached_data_with_fallback(
        "safetyamp_users_by_id",
        lambda: api.get_all_paginated("/api/users", key_field="id"),
        max_age_hours=1,
    ) or {}
    employees = list(employees_by_id.values())
    
    print('EMPLOYEE_DATA_START')
    import json
    print(json.dumps(employees, indent=2))
    print('EMPLOYEE_DATA_END')
    
except Exception as e:
    print(f'Error: {str(e)}')
    print('EMPLOYEE_DATA_END')
"
    
    if ($result -match 'EMPLOYEE_DATA_START(.*?)EMPLOYEE_DATA_END') {
        $jsonData = $matches[1].Trim()
        try {
            return $jsonData | ConvertFrom-Json
        }
        catch {
            Write-Host "❌ Failed to parse employee data: $_" -ForegroundColor Red
            return $null
        }
    } else {
        Write-Host "❌ Failed to get employee data" -ForegroundColor Red
        return $null
    }
}

function Show-MissingFields {
    param($Employees)
    
    Write-Host "`n🔴 Employees with Missing Required Fields:" -ForegroundColor Red
    Write-Host "=============================================" -ForegroundColor Red
    
    $missingFirst = @()
    $missingLast = @()
    $missingEmail = @()
    $missingMobile = @()
    
    foreach ($emp in $Employees) {
        if (-not $emp.first_name -or $emp.first_name -eq "") {
            $missingFirst += $emp
        }
        if (-not $emp.last_name -or $emp.last_name -eq "") {
            $missingLast += $emp
        }
        if (-not $emp.email -or $emp.email -eq "") {
            $missingEmail += $emp
        }
        if (-not $emp.mobile_phone -or $emp.mobile_phone -eq "") {
            $missingMobile += $emp
        }
    }
    
    if ($missingFirst.Count -gt 0) {
        Write-Host "`n📝 Missing First Names ($($missingFirst.Count) employees):" -ForegroundColor Yellow
        foreach ($emp in $missingFirst | Select-Object -First 10) {
            Write-Host "  ID: $($emp.id), Name: $($emp.last_name), Email: $($emp.email)" -ForegroundColor Gray
        }
        if ($missingFirst.Count -gt 10) {
            Write-Host "  ... and $($missingFirst.Count - 10) more" -ForegroundColor Gray
        }
    }
    
    if ($missingLast.Count -gt 0) {
        Write-Host "`n📝 Missing Last Names ($($missingLast.Count) employees):" -ForegroundColor Yellow
        foreach ($emp in $missingLast | Select-Object -First 10) {
            Write-Host "  ID: $($emp.id), Name: $($emp.first_name), Email: $($emp.email)" -ForegroundColor Gray
        }
        if ($missingLast.Count -gt 10) {
            Write-Host "  ... and $($missingLast.Count - 10) more" -ForegroundColor Gray
        }
    }
    
    if ($missingEmail.Count -gt 0) {
        Write-Host "`n📝 Missing Emails ($($missingEmail.Count) employees):" -ForegroundColor Yellow
        foreach ($emp in $missingEmail | Select-Object -First 10) {
            Write-Host "  ID: $($emp.id), Name: $($emp.first_name) $($emp.last_name)" -ForegroundColor Gray
        }
        if ($missingEmail.Count -gt 10) {
            Write-Host "  ... and $($missingEmail.Count - 10) more" -ForegroundColor Gray
        }
    }
    
    if ($missingMobile.Count -gt 0) {
        Write-Host "`n📝 Missing Mobile Phones ($($missingMobile.Count) employees):" -ForegroundColor Yellow
        foreach ($emp in $missingMobile | Select-Object -First 10) {
            Write-Host "  ID: $($emp.id), Name: $($emp.first_name) $($emp.last_name), Email: $($emp.email)" -ForegroundColor Gray
        }
        if ($missingMobile.Count -gt 10) {
            Write-Host "  ... and $($missingMobile.Count - 10) more" -ForegroundColor Gray
        }
    }
    
    Write-Host "`n💡 Recommendations:" -ForegroundColor Cyan
    Write-Host "  - Fix missing data in your source system" -ForegroundColor Yellow
    Write-Host "  - Consider implementing data validation rules" -ForegroundColor Yellow
    Write-Host "  - Generate missing emails using: firstname.lastname@company.com" -ForegroundColor Yellow
    Write-Host "  - Use default values for missing names if appropriate" -ForegroundColor Yellow
}

function Show-DuplicateData {
    param($Employees)
    
    Write-Host "`n🔄 Employees with Duplicate Data:" -ForegroundColor Red
    Write-Host "=================================" -ForegroundColor Red
    
    # Group by email
    $emailGroups = $Employees | Group-Object email | Where-Object { $_.Count -gt 1 -and $_.Name -ne "" }
    $mobileGroups = $Employees | Group-Object mobile_phone | Where-Object { $_.Count -gt 1 -and $_.Name -ne "" }
    
    if ($emailGroups.Count -gt 0) {
        Write-Host "`n📧 Duplicate Emails ($($emailGroups.Count) groups):" -ForegroundColor Yellow
        foreach ($group in $emailGroups | Select-Object -First 5) {
            Write-Host "  Email: $($group.Name)" -ForegroundColor Gray
            foreach ($emp in $group.Group) {
                Write-Host "    ID: $($emp.id), Name: $($emp.first_name) $($emp.last_name)" -ForegroundColor Gray
            }
        }
        if ($emailGroups.Count -gt 5) {
            Write-Host "  ... and $($emailGroups.Count - 5) more email groups" -ForegroundColor Gray
        }
    }
    
    if ($mobileGroups.Count -gt 0) {
        Write-Host "`n📱 Duplicate Mobile Phones ($($mobileGroups.Count) groups):" -ForegroundColor Yellow
        foreach ($group in $mobileGroups | Select-Object -First 5) {
            Write-Host "  Mobile: $($group.Name)" -ForegroundColor Gray
            foreach ($emp in $group.Group) {
                Write-Host "    ID: $($emp.id), Name: $($emp.first_name) $($emp.last_name), Email: $($emp.email)" -ForegroundColor Gray
            }
        }
        if ($mobileGroups.Count -gt 5) {
            Write-Host "  ... and $($mobileGroups.Count - 5) more mobile groups" -ForegroundColor Gray
        }
    }
    
    if ($emailGroups.Count -eq 0 -and $mobileGroups.Count -eq 0) {
        Write-Host "✅ No duplicate data found!" -ForegroundColor Green
    } else {
        Write-Host "`n💡 Recommendations:" -ForegroundColor Cyan
        Write-Host "  - Identify which employee should keep the duplicate data" -ForegroundColor Yellow
        Write-Host "  - Update or remove duplicate data in your source system" -ForegroundColor Yellow
        Write-Host "  - Consider merging duplicate employee records" -ForegroundColor Yellow
    }
}

function Show-SkippedEmployees {
    param([string]$PodName)
    
    Write-Host "`n⏭️ Employees Being Skipped:" -ForegroundColor Red
    Write-Host "===========================" -ForegroundColor Red
    
    $sinceTime = (Get-Date).AddHours(-2).ToString("yyyy-MM-ddTHH:mm:ssZ")
    $logs = kubectl logs -n safety-amp $PodName --since-time=$sinceTime 2>$null
    
    $skippedLogs = $logs | Select-String -Pattern "Skipped employee.*Reason: No matching site"
    
    if ($skippedLogs) {
        Write-Host "`n🏢 Employees skipped due to missing site mappings:" -ForegroundColor Yellow
        foreach ($log in $skippedLogs | Select-Object -First 10) {
            if ($log.Line -match "Skipped employee (\d+) - Reason: No matching site for (.+)") {
                $empId = $matches[1]
                $siteInfo = $matches[2]
                Write-Host "  Employee ID: $empId, Site Info: $siteInfo" -ForegroundColor Gray
            }
        }
        if ($skippedLogs.Count -gt 10) {
            Write-Host "  ... and $($skippedLogs.Count - 10) more" -ForegroundColor Gray
        }
        
        Write-Host "`n💡 Recommendations:" -ForegroundColor Cyan
        Write-Host "  - Review site mappings in your configuration" -ForegroundColor Yellow
        Write-Host "  - Add missing department/site mappings" -ForegroundColor Yellow
        Write-Host "  - Consider creating default site mappings" -ForegroundColor Yellow
    } else {
        Write-Host "✅ No employees being skipped due to site mapping issues!" -ForegroundColor Green
    }
}

function Show-DataValidation {
    param($Employees)
    
    Write-Host "`n✅ Employee Data Validation Summary:" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    
    $total = $Employees.Count
    $valid = 0
    $issues = @()
    
    foreach ($emp in $Employees) {
        $hasIssues = $false
        $empIssues = @()
        
        if (-not $emp.first_name -or $emp.first_name -eq "") {
            $hasIssues = $true
            $empIssues += "Missing first_name"
        }
        if (-not $emp.last_name -or $emp.last_name -eq "") {
            $hasIssues = $true
            $empIssues += "Missing last_name"
        }
        if (-not $emp.email -or $emp.email -eq "") {
            $hasIssues = $true
            $empIssues += "Missing email"
        }
        
        if ($hasIssues) {
            $issues += "ID: $($emp.id) - $($empIssues -join ', ')"
        } else {
            $valid++
        }
    }
    
    Write-Host "  Total Employees: $total" -ForegroundColor White
    Write-Host "  Valid Records: $valid" -ForegroundColor Green
    Write-Host "  Records with Issues: $($total - $valid)" -ForegroundColor Red
    Write-Host "  Validation Rate: $([math]::Round(($valid / $total) * 100, 1))%" -ForegroundColor $(if (($valid / $total) -gt 0.9) { "Green" } elseif (($valid / $total) -gt 0.7) { "Yellow" } else { "Red" })
    
    if ($issues.Count -gt 0) {
        Write-Host "`n📋 Sample Issues:" -ForegroundColor Yellow
        foreach ($issue in $issues | Select-Object -First 5) {
            Write-Host "  $issue" -ForegroundColor Gray
        }
        if ($issues.Count -gt 5) {
            Write-Host "  ... and $($issues.Count - 5) more" -ForegroundColor Gray
        }
    }
}

# Main execution
$employees = Get-EmployeeData -PodName $Pod

if (-not $employees) {
    Write-Host "❌ Failed to retrieve employee data" -ForegroundColor Red
    return
}

switch ($Action.ToLower()) {
    "list-missing" {
        Show-MissingFields -Employees $employees
    }
    "list-duplicates" {
        Show-DuplicateData -Employees $employees
    }
    "list-skipped" {
        Show-SkippedEmployees -PodName $Pod
    }
    "validate" {
        Show-DataValidation -Employees $employees
    }
    default {
        Write-Host "❌ Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available actions: list-missing, list-duplicates, list-skipped, validate" -ForegroundColor Yellow
        return
    }
}

Write-Host "`n✅ Employee data analysis complete!" -ForegroundColor Green
