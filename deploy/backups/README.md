# Deployment backups

This folder holds legacy backup and temporary deployment YAMLs that were moved from the project root during reorganization.

- `backup-deployment-*.yaml` – Snapshots from `rollout-validation.ps1` (when run from project root)
- `deployment-patch.yaml`, `safety-amp-deployment-fixed.yaml`, `temp-deployment.yaml` – Ad-hoc deployment patches
- `networkpolicy-*.yaml` – Network policy backups

**Note:** New backups from `deploy/rollout-validation.ps1` are still written to the current working directory when the script runs.
