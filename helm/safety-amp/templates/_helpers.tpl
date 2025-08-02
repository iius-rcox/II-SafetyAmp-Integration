{{/*
Expand the name of the chart.
*/}}
{{- define "safety-amp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "safety-amp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "safety-amp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "safety-amp.labels" -}}
helm.sh/chart: {{ include "safety-amp.chart" . }}
{{ include "safety-amp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "safety-amp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "safety-amp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "safety-amp.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "safety-amp.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the image name
*/}}
{{- define "safety-amp.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.image.registry }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- else }}
{{- printf "%s:%s" .Values.image.repository (.Values.image.tag | default .Chart.AppVersion) }}
{{- end }}
{{- end }}

{{/*
Create environment-specific configuration
*/}}
{{- define "safety-amp.environment" -}}
{{- $env := .Values.global.environment | default "production" }}
{{- if hasKey .Values.environments $env }}
{{- $envConfig := index .Values.environments $env }}
{{- $config := deepCopy .Values | mergeOverwrite $envConfig }}
{{- toJson $config }}
{{- else }}
{{- toJson .Values }}
{{- end }}
{{- end }}

{{/*
Generate the full image pull secrets
*/}}
{{- define "safety-amp.imagePullSecrets" -}}
{{- $pullSecrets := list }}
{{- if .Values.global.imagePullSecrets }}
{{- $pullSecrets = concat $pullSecrets .Values.global.imagePullSecrets }}
{{- end }}
{{- if .Values.image.pullSecrets }}
{{- $pullSecrets = concat $pullSecrets .Values.image.pullSecrets }}
{{- end }}
{{- if $pullSecrets }}
imagePullSecrets:
{{- range $pullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Generate ConfigMap data
*/}}
{{- define "safety-amp.configData" -}}
# Application configuration
LOG_LEVEL: {{ .Values.config.logLevel | quote }}
LOG_FORMAT: {{ .Values.config.logFormat | quote }}
ENVIRONMENT: {{ .Values.config.environment | quote }}

# Performance tuning for 5000 records/hour
SYNC_INTERVAL: {{ .Values.config.syncInterval | quote }}
BATCH_SIZE: {{ .Values.config.batchSize | quote }}
CACHE_TTL_HOURS: {{ .Values.config.cacheTtlHours | quote }}

# API rate limiting
API_RATE_LIMIT_CALLS: {{ .Values.config.apiRateLimit.calls | quote }}
API_RATE_LIMIT_PERIOD: {{ .Values.config.apiRateLimit.period | quote }}

# Retry configuration
MAX_RETRY_ATTEMPTS: {{ .Values.config.maxRetryAttempts | quote }}
RETRY_DELAY_SECONDS: {{ .Values.config.retryDelaySeconds | quote }}

# Health checks
HEALTH_CHECK_PORT: {{ .Values.config.healthCheck.port | quote }}
HEALTH_CHECK_TIMEOUT: {{ .Values.config.healthCheck.timeout | quote }}

# Metrics
METRICS_PORT: {{ .Values.config.metrics.port | quote }}

# Database configuration
DB_POOL_SIZE: {{ .Values.config.database.poolSize | quote }}
DB_MAX_OVERFLOW: {{ .Values.config.database.maxOverflow | quote }}
DB_POOL_TIMEOUT: {{ .Values.config.database.poolTimeout | quote }}
DB_POOL_RECYCLE: {{ .Values.config.database.poolRecycle | quote }}
SQL_AUTH_MODE: {{ .Values.config.database.authMode | quote }}

# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD: {{ .Values.config.circuitBreaker.failureThreshold | quote }}
CIRCUIT_BREAKER_RECOVERY_TIMEOUT: {{ .Values.config.circuitBreaker.recoveryTimeout | quote }}

# External services
SAFETY_AMP_BASE_URL: {{ .Values.externalServices.safetyAmp.baseUrl | quote }}
SAFETY_AMP_TIMEOUT: {{ .Values.externalServices.safetyAmp.timeout | quote }}
SAMSARA_DOMAIN: {{ .Values.externalServices.samsara.domain | quote }}

# Memory profiling
MEMORY_PROFILER_ENABLED: {{ .Values.config.memoryProfiler.enabled | quote }}
MEMORY_PROFILER_INTERVAL: {{ .Values.config.memoryProfiler.interval | quote }}

# Testing configuration
{{- if .Values.testing.enabled }}
TEST_MODE: {{ .Values.testing.testMode | quote }}
SMALL_BATCH_SIZE: {{ .Values.testing.smallBatchSize | quote }}
{{- end }}
{{- end }}

{{/*
Generate secret data from Key Vault
*/}}
{{- define "safety-amp.secretData" -}}
# Azure Key Vault URL
AZURE_KEY_VAULT_URL: {{ printf "https://%s.vault.azure.net/" .Values.keyVault.name | quote }}

# Redis configuration
{{- if .Values.redis.enabled }}
REDIS_HOST: {{ .Values.redis.host | quote }}
REDIS_PORT: {{ .Values.redis.port | quote }}
REDIS_PASSWORD: {{ .Values.redis.password | quote }}
{{- end }}
{{- end }}