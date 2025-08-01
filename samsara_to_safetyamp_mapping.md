# Samsara to SafetyAmp Asset Integration Mapping

## Overview
This document outlines the field mapping between Samsara vehicles and SafetyAmp assets for integration purposes.

## Field Mapping Analysis

### ✅ Direct Mappings (Available in Samsara)

| SafetyAmp Asset Field | Samsara Vehicle Field | Notes |
|----------------------|----------------------|-------|
| `name` | `name` | Vehicle display name (e.g., "Unit 719 - II95 - Rodney Benoit") |
| `model` | `model` | Vehicle model (e.g., "F-150", "2500") |
| `serial` | `serial` | Samsara device serial number |
| `description` | `notes` | Vehicle notes/description |
| `created_at` | `createdAtTime` | Vehicle creation timestamp |
| `updated_at` | `updatedAtTime` | Vehicle last update timestamp |

### 🔄 Derived Mappings (Can be constructed)

| SafetyAmp Asset Field | Samsara Source | Construction Logic |
|----------------------|----------------|-------------------|
| `code` | `licensePlate` | Use license plate as asset code |
| `asset_type_id` | Fixed value | Use SafetyAmp vehicle asset type ID: 3183 |
| `status` | `vehicleRegulationMode` | Map "regulated" → 1, "unregulated" → 0 (numeric status) |
| `current_user` | `staticAssignedDriver.name` | Assigned driver name |
| `current_user_id` | `staticAssignedDriver.id` | Assigned driver ID |

### 📍 Location Mapping (Site-based)

| SafetyAmp Asset Field | Samsara Source | Logic |
|----------------------|----------------|-------|
| `site` | `tags` | Extract site from department tags |
| `site_id` | `tags` | Map department tag ID to SafetyAmp site ID |
| `location` | `tags` | Use department name as location |

### ❌ Missing Fields (Need Defaults/Logic)

| SafetyAmp Asset Field | Default/Logic |
|----------------------|---------------|
| `asset_type_id` | Use fixed value: 3183 (vehicle asset type) |
| `created_by` | Use system user or API user |
| `deleted_at` | NULL (not deleted) |
| `location_id` | Map from site_id |
| `updated_by` | Use system user or API user |

## Sample Data Analysis

### Vehicle Record Example:
```json
{
  "id": "281474989342699",
  "name": "Unit 719 - II95 - Rodney Benoit",
  "make": "FORD",
  "model": "F-150",
  "year": "2018",
  "licensePlate": "C788223",
  "vin": "1FTEX1CP4JKD77856",
  "serial": "G8JD7UB9UR",
  "notes": "",
  "vehicleRegulationMode": "regulated",
  "staticAssignedDriver": {
    "id": "52337118",
    "name": "Rodney Benoit"
  },
  "tags": [
    {
      "id": "4667615",
      "name": "Department 95 - NOLA"
    }
  ],
  "createdAtTime": "2024-02-27T18:04:29Z",
  "updatedAtTime": "2024-12-10T17:34:27Z"
}
```

### Mapped SafetyAmp Asset:
```json
{
  "name": "Unit 719 - II95 - Rodney Benoit",
  "model": "F-150",
  "serial": "G8JD7UB9UR",
  "description": "",
  "code": "C788223",
     "asset_type_id": 3183,
  "status": 1,
  "current_user": "Rodney Benoit",
  "current_user_id": "52337118",
  "site": "Department 95 - NOLA",
  "site_id": 4667615,
  "location": "Department 95 - NOLA",
  "created_at": "2024-02-27T18:04:29Z",
  "updated_at": "2024-12-10T17:34:27Z"
}
```

## Integration Recommendations

### 1. Asset Type Management
- Create a "Vehicle" asset category in SafetyAmp
- Create asset types for each make/model combination
- Map Samsara vehicles to appropriate asset types

### 2. Site/Location Mapping
- Extract department information from Samsara tags
- Map department tags to SafetyAmp sites
- Use department name as location identifier

### 3. User Assignment
- Map `staticAssignedDriver` to SafetyAmp user records
- Handle cases where driver doesn't exist in SafetyAmp
- Create placeholder users if needed

### 4. Status Mapping
- `regulated` → `active`
- `unregulated` → `inactive`
- Handle other regulation modes as needed

### 5. Data Synchronization
- Use `updatedAtTime` for incremental syncs
- Track last sync timestamp
- Handle deleted vehicles (mark as deleted in SafetyAmp)

## Implementation Steps

1. **Create SafetyAmp Asset Types**
   - Vehicle category
   - Make/model combinations

2. **Map Sites/Departments**
   - Extract department tags from Samsara
   - Create corresponding SafetyAmp sites

3. **User Mapping**
   - Map Samsara drivers to SafetyAmp users
   - Handle missing users

4. **Asset Creation/Update Logic**
   - Transform Samsara vehicle data
   - Apply field mappings
   - Handle required vs optional fields

5. **Sync Strategy**
   - Full sync for initial load
   - Incremental sync based on `updatedAtTime`
   - Handle deletions and status changes

## Field Priority

### High Priority (Required for Asset Creation)
- `name` (from Samsara `name`)
- `serial` (from Samsara `serial`)
- `asset_type_id` (fixed value: 3183)

### Medium Priority (Important for Asset Management)
- `model` (from Samsara `model`)
- `code` (from Samsara `licensePlate`)
- `status` (from Samsara `vehicleRegulationMode`)
- `current_user` (from Samsara `staticAssignedDriver`)

### Low Priority (Nice to Have)
- `description` (from Samsara `notes`)
- `site` (from Samsara `tags`)
- `location` (from Samsara `tags`)

## SafetyAmp API Documentation Insights

Based on the official SafetyAmp API documentation, we can see:

### Required Fields for Asset Creation:
- **`name`** - Asset name (required)
- **`site_id`** - Site ID (required)
- **`asset_type_id`** - Asset type ID (required)

### Status Values:
- **`0`** = Decommissioned
- **`1`** = Active

### Asset Structure:
- All assets must belong to an asset group (asset_type)
- All asset groups must belong to a category
- The site an asset is connected to must match the site for its group

## Real SafetyAmp Asset Example Analysis

Based on an actual SafetyAmp vehicle asset, we can see:

### Key Insights:
- **Status**: Uses numeric values (1 = active, 0 = inactive)
- **Code**: Can be unit numbers (e.g., "957") or license plates
- **Description**: Contains detailed vehicle info (year, make, model, color)
- **Model**: Can be placeholder values or actual model names
- **Serial**: Can be null for some assets
- **Site**: Full nested object with complete site details
- **User IDs**: Uses SafetyAmp internal user IDs (e.g., "pqY8z")

### Example SafetyAmp Asset:
```json
{
  "id": 20374,
  "code": "957",
  "name": "Unit 957",
  "description": "2022 Chevrolet Silverado LTZ Z71 Color: Silver",
  "site_id": 5145,
  "status": 1,
  "serial": null,
  "model": "1234567890",
  "asset_type_id": 3183,
  "current_user_id": "pqY8z"
}
```

## Notes

- **80 vehicles** available in Samsara
- **18 fields** per vehicle record
- **Department-based organization** via tags
- **Driver assignment** via `staticAssignedDriver`
- **Regulation status** via `vehicleRegulationMode`
- **Timestamps** for sync tracking
- **SafetyAmp uses numeric status codes** (1=active, 0=inactive) 