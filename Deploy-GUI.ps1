# Windows GUI Deployment Tool for SafetyAmp Integration
# Run this with: powershell.exe -ExecutionPolicy Bypass -File Deploy-GUI.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Create the main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "SafetyAmp Integration - Deployment Tool"
$form.Size = New-Object System.Drawing.Size(500, 550)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(240, 240, 240)

# Add icon if available
try {
    $iconBase64 = "AAABAAEAEBAAAAAAAABoBQAAFgAAACgAAAAQAAAAIAAAAAEACAAAAAAAAAEAAAAAAAAAAAAAAAEAAAAAAAAAAAAA"
    $iconBytes = [Convert]::FromBase64String($iconBase64)
    $stream = New-Object System.IO.MemoryStream($iconBytes, 0, $iconBytes.Length)
    $form.Icon = [System.Drawing.Icon]::FromHandle((New-Object System.Drawing.Bitmap($stream)).GetHicon())
} catch {}

# Title Label
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Location = New-Object System.Drawing.Point(10, 10)
$titleLabel.Size = New-Object System.Drawing.Size(470, 40)
$titleLabel.Text = "SafetyAmp Integration Deployment"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$titleLabel.TextAlign = "MiddleCenter"
$form.Controls.Add($titleLabel)

# Subtitle
$subtitleLabel = New-Object System.Windows.Forms.Label
$subtitleLabel.Location = New-Object System.Drawing.Point(10, 50)
$subtitleLabel.Size = New-Object System.Drawing.Size(470, 20)
$subtitleLabel.Text = "Deploy to Azure Kubernetes Service (AKS)"
$subtitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$subtitleLabel.ForeColor = [System.Drawing.Color]::Gray
$subtitleLabel.TextAlign = "MiddleCenter"
$form.Controls.Add($subtitleLabel)

# Environment Group Box
$envGroupBox = New-Object System.Windows.Forms.GroupBox
$envGroupBox.Location = New-Object System.Drawing.Point(10, 80)
$envGroupBox.Size = New-Object System.Drawing.Size(470, 100)
$envGroupBox.Text = "Environment Selection"
$envGroupBox.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($envGroupBox)

# Environment Radio Buttons
$radioDev = New-Object System.Windows.Forms.RadioButton
$radioDev.Location = New-Object System.Drawing.Point(20, 30)
$radioDev.Size = New-Object System.Drawing.Size(120, 20)
$radioDev.Text = "Development"
$radioDev.Checked = $true
$radioDev.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$envGroupBox.Controls.Add($radioDev)

$radioStaging = New-Object System.Windows.Forms.RadioButton
$radioStaging.Location = New-Object System.Drawing.Point(160, 30)
$radioStaging.Size = New-Object System.Drawing.Size(100, 20)
$radioStaging.Text = "Staging"
$radioStaging.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$envGroupBox.Controls.Add($radioStaging)

$radioProd = New-Object System.Windows.Forms.RadioButton
$radioProd.Location = New-Object System.Drawing.Point(280, 30)
$radioProd.Size = New-Object System.Drawing.Size(100, 20)
$radioProd.Text = "Production"
$radioProd.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$envGroupBox.Controls.Add($radioProd)

# Environment Description
$envDesc = New-Object System.Windows.Forms.Label
$envDesc.Location = New-Object System.Drawing.Point(20, 60)
$envDesc.Size = New-Object System.Drawing.Size(430, 30)
$envDesc.Text = "Cluster: dev-aks | Resource Group: rg_prod | Replicas: 1"
$envDesc.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$envDesc.ForeColor = [System.Drawing.Color]::FromArgb(100, 100, 100)
$envGroupBox.Controls.Add($envDesc)

# Update description when selection changes
$updateEnvDesc = {
    if ($radioDev.Checked) {
        $envDesc.Text = "Cluster: dev-aks | Resource Group: rg_prod | Replicas: 1"
    } elseif ($radioStaging.Checked) {
        $envDesc.Text = "Cluster: dev-aks | Resource Group: rg_prod | Replicas: 2 (shared cluster)"
    } else {
        $envDesc.Text = "Cluster: dev-aks | Resource Group: rg_prod | Replicas: 2 (shared cluster)"
    }
}

$radioDev.Add_CheckedChanged($updateEnvDesc)
$radioStaging.Add_CheckedChanged($updateEnvDesc)
$radioProd.Add_CheckedChanged($updateEnvDesc)

# Deployment Options Group Box
$optionsGroupBox = New-Object System.Windows.Forms.GroupBox
$optionsGroupBox.Location = New-Object System.Drawing.Point(10, 190)
$optionsGroupBox.Size = New-Object System.Drawing.Size(470, 120)
$optionsGroupBox.Text = "Deployment Options"
$optionsGroupBox.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($optionsGroupBox)

# Image Tag Label and TextBox
$tagLabel = New-Object System.Windows.Forms.Label
$tagLabel.Location = New-Object System.Drawing.Point(20, 30)
$tagLabel.Size = New-Object System.Drawing.Size(80, 20)
$tagLabel.Text = "Image Tag:"
$tagLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($tagLabel)

$tagTextBox = New-Object System.Windows.Forms.TextBox
$tagTextBox.Location = New-Object System.Drawing.Point(110, 28)
$tagTextBox.Size = New-Object System.Drawing.Size(150, 20)
$tagTextBox.Text = "latest"
$tagTextBox.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($tagTextBox)

# Checkboxes
$buildCheckBox = New-Object System.Windows.Forms.CheckBox
$buildCheckBox.Location = New-Object System.Drawing.Point(20, 60)
$buildCheckBox.Size = New-Object System.Drawing.Size(200, 20)
$buildCheckBox.Text = "Build Docker Image"
$buildCheckBox.Checked = $true
$buildCheckBox.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($buildCheckBox)

$infraCheckBox = New-Object System.Windows.Forms.CheckBox
$infraCheckBox.Location = New-Object System.Drawing.Point(20, 85)
$infraCheckBox.Size = New-Object System.Drawing.Size(200, 20)
$infraCheckBox.Text = "Deploy Infrastructure"
$infraCheckBox.Checked = $true
$infraCheckBox.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($infraCheckBox)

$monitoringCheckBox = New-Object System.Windows.Forms.CheckBox
$monitoringCheckBox.Location = New-Object System.Drawing.Point(240, 60)
$monitoringCheckBox.Size = New-Object System.Drawing.Size(200, 20)
$monitoringCheckBox.Text = "Deploy Monitoring"
$monitoringCheckBox.Checked = $true
$monitoringCheckBox.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($monitoringCheckBox)

$dryRunCheckBox = New-Object System.Windows.Forms.CheckBox
$dryRunCheckBox.Location = New-Object System.Drawing.Point(240, 85)
$dryRunCheckBox.Size = New-Object System.Drawing.Size(200, 20)
$dryRunCheckBox.Text = "Dry Run (Preview Only)"
$dryRunCheckBox.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$optionsGroupBox.Controls.Add($dryRunCheckBox)

# Status Text Box
$statusGroupBox = New-Object System.Windows.Forms.GroupBox
$statusGroupBox.Location = New-Object System.Drawing.Point(10, 320)
$statusGroupBox.Size = New-Object System.Drawing.Size(470, 130)
$statusGroupBox.Text = "Deployment Status"
$statusGroupBox.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($statusGroupBox)

$statusTextBox = New-Object System.Windows.Forms.TextBox
$statusTextBox.Location = New-Object System.Drawing.Point(10, 25)
$statusTextBox.Size = New-Object System.Drawing.Size(450, 95)
$statusTextBox.Multiline = $true
$statusTextBox.ScrollBars = "Vertical"
$statusTextBox.ReadOnly = $true
$statusTextBox.Font = New-Object System.Drawing.Font("Consolas", 8)
$statusTextBox.BackColor = [System.Drawing.Color]::Black
$statusTextBox.ForeColor = [System.Drawing.Color]::Lime
$statusGroupBox.Controls.Add($statusTextBox)

# Progress Bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(10, 460)
$progressBar.Size = New-Object System.Drawing.Size(470, 23)
$progressBar.Style = "Continuous"
$form.Controls.Add($progressBar)

# Deploy Button
$deployButton = New-Object System.Windows.Forms.Button
$deployButton.Location = New-Object System.Drawing.Point(140, 495)
$deployButton.Size = New-Object System.Drawing.Size(100, 35)
$deployButton.Text = "Deploy"
$deployButton.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$deployButton.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$deployButton.ForeColor = [System.Drawing.Color]::White
$deployButton.FlatStyle = "Flat"
$deployButton.Cursor = "Hand"
$form.Controls.Add($deployButton)

# Cancel Button
$cancelButton = New-Object System.Windows.Forms.Button
$cancelButton.Location = New-Object System.Drawing.Point(250, 495)
$cancelButton.Size = New-Object System.Drawing.Size(100, 35)
$cancelButton.Text = "Cancel"
$cancelButton.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$cancelButton.BackColor = [System.Drawing.Color]::LightGray
$cancelButton.FlatStyle = "Flat"
$cancelButton.Cursor = "Hand"
$form.Controls.Add($cancelButton)

# Deploy Button Click Event
$deployButton.Add_Click({
    $deployButton.Enabled = $false
    $statusTextBox.Clear()
    $progressBar.Value = 0

    # Determine environment
    $environment = if ($radioDev.Checked) { "dev" } `
                  elseif ($radioStaging.Checked) { "staging" } `
                  else { "prod" }

    $tag = $tagTextBox.Text
    if ([string]::IsNullOrWhiteSpace($tag)) { $tag = "latest" }

    # Build command arguments
    $args = @("-Environment", $environment, "-Tag", $tag)
    if (-not $buildCheckBox.Checked) { $args += "-SkipBuild" }
    if (-not $infraCheckBox.Checked) { $args += "-SkipInfra" }
    if ($dryRunCheckBox.Checked) { $args += "-DryRun" }

    $statusTextBox.AppendText("Starting deployment to $environment environment...`r`n")
    $statusTextBox.AppendText("Image tag: $tag`r`n")
    $statusTextBox.AppendText("=======================================`r`n")

    # Simulate deployment steps (replace with actual deployment script call)
    $steps = @(
        "Checking Azure authentication...",
        "Getting AKS cluster credentials...",
        "Building Docker image...",
        "Pushing to Azure Container Registry...",
        "Deploying infrastructure components...",
        "Deploying SafetyAmp application...",
        "Applying environment configurations...",
        "Deploying monitoring stack...",
        "Waiting for rollout completion...",
        "Verifying deployment health..."
    )

    $stepCount = $steps.Count
    $currentStep = 0

    foreach ($step in $steps) {
        $currentStep++
        $progressBar.Value = ($currentStep / $stepCount) * 100
        $statusTextBox.AppendText("[$currentStep/$stepCount] $step`r`n")
        $statusTextBox.Refresh()
        $form.Refresh()
        Start-Sleep -Milliseconds 500  # Simulate work

        # Skip some steps based on checkboxes
        if (-not $buildCheckBox.Checked -and $step -like "*Docker*") {
            $statusTextBox.AppendText("  [SKIPPED]`r`n")
        } elseif (-not $infraCheckBox.Checked -and $step -like "*infrastructure*") {
            $statusTextBox.AppendText("  [SKIPPED]`r`n")
        } elseif (-not $monitoringCheckBox.Checked -and $step -like "*monitoring*") {
            $statusTextBox.AppendText("  [SKIPPED]`r`n")
        } else {
            $statusTextBox.AppendText("  [OK]`r`n")
        }
    }

    $progressBar.Value = 100
    $statusTextBox.AppendText("`r`n=======================================`r`n")
    $statusTextBox.AppendText("DEPLOYMENT COMPLETED SUCCESSFULLY!`r`n")
    $statusTextBox.AppendText("`r`nNext steps:`r`n")
    $statusTextBox.AppendText("• kubectl get pods -n safety-amp`r`n")
    $statusTextBox.AppendText("• kubectl logs -f deploy/safety-amp-agent -n safety-amp`r`n")

    [System.Windows.Forms.MessageBox]::Show(
        "Deployment completed successfully!`n`nYour application is now running on AKS.",
        "Deployment Success",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )

    $deployButton.Enabled = $true
})

# Cancel Button Click Event
$cancelButton.Add_Click({
    $form.Close()
})

# Show the form
$form.ShowDialog()

