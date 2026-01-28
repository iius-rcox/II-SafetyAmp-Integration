# System-to-System Field Mappings

## Overview
This document provides a comprehensive mapping of data fields as they flow between source systems (Viewpoint Vista, Microsoft Entra ID, Samsara) and the destination system (SafetyAmp). The integration primarily operates as a unidirectional synchronization from multiple source systems into SafetyAmp.

## System-to-System Field Mappings

### 1. Viewpoint Vista → SafetyAmp (Employee Sync)

#### Employee Basic Information
| **Viewpoint Field** | **SafetyAmp Field** | **Transformation/Notes** |
|---------------------|---------------------|-------------------------|
| `Employee` | `emp_id` | Direct mapping, used as unique identifier |
| `FirstName` | `first_name` | Trimmed whitespace |
| `LastName` | `last_name` | Trimmed whitespace |
| `MiddleName` | `middle_name` | Trimmed whitespace |
| `SortName` | - | Used to construct display name |
| `HireDate` | `hire_date` | ISO format date |
| `TermDate` | - | Used to filter active employees only |
| `Sex` | `gender` | M→1, F→2, normalized |
| `udEmpTitle` | `title_id` | Mapped via title lookup table |
| `PRDept` | `home_site_id` | Complex mapping via department→cluster→site |
| `Job` | `site_id` | Mapped to SafetyAmp site via job lookup |
| `EMail` | `email` | Validated, may be overridden by Entra ID |
| `CellPhone` | `cell_phone` | Cleaned to E.164 format (+1XXXXXXXXXX) |
| `HomePhone` | `home_phone` | Cleaned to E.164 format |
| `WorkPhone` | `work_phone` | Cleaned to E.164 format |
| `Address` | `address` | Direct mapping |
| `City` | `city` | Direct mapping |
| `State` | `state` | Direct mapping |
| `Zip` | `zip_code` | Direct mapping |

#### Calculated/Default Fields
| **Field** | **SafetyAmp Value** | **Source/Logic** |
|-----------|---------------------|------------------|
| `system_access` | `true` | Default for all new users |
| `text_stop` | `true` | Default opt-out from texts |
| `role_id` | Lookup from role_map | Based on role name mapping |
| `created_by` | "system" | Hardcoded |
| `updated_by` | "system" | Hardcoded |

### 2. Microsoft Entra ID (Graph API) → SafetyAmp

#### User Enhancement Data
| **Graph Field** | **SafetyAmp Field** | **Transformation/Notes** |
|-----------------|---------------------|-------------------------|
| `mail` | `email` | Overrides Vista email if present |
| `userPrincipalName` | `email` (fallback) | Used if mail field empty |
| `mobilePhone` | `cell_phone` | Overrides Vista if present, E.164 format |
| `businessPhones[0]` | `work_phone` | First business phone if available |
| `employeeId` | - | Used for matching to Vista Employee ID |

### 3. Viewpoint Vista → SafetyAmp (Department/Cluster Sync)

#### Department Hierarchy
| **Viewpoint Field** | **SafetyAmp Field** | **Transformation/Notes** |
|---------------------|---------------------|-------------------------|
| `udRegion` | `parent_cluster_id` | Creates region-level cluster |
| `PRDept` | `external_code` | Department code |
| `Description` | `name` | "PRDept - Description" format |
| - | `cluster_type_id` | Hardcoded: 1 |
| - | `status` | Hardcoded: 1 (active) |

### 4. Viewpoint Vista → SafetyAmp (Job/Site Sync)

#### Job to Site Mapping
| **Viewpoint Field** | **SafetyAmp Field** | **Transformation/Notes** |
|---------------------|---------------------|-------------------------|
| `Job` | `external_code` | Job number |
| `Description` | `name` | Job description |
| `udJobZip` | `zip_code` | Job location zip |
| `udDepartment` | `cluster_id` | Maps to department cluster |
| `JobStatus` | - | Filter: only active jobs (status=1) |
| - | `created_by` | "system" |
| - | `updated_by` | "system" |

### 5. Viewpoint Vista → SafetyAmp (Title Sync)

#### Title Mapping
| **Viewpoint Field** | **SafetyAmp Field** | **Transformation/Notes** |
|---------------------|---------------------|-------------------------|
| `udEmpTitle` | `name` | Employee title text |
| - | `created_by` | "system" |
| - | `updated_by` | "system" |

### 6. Samsara → SafetyAmp (Vehicle/Asset Sync)

#### Vehicle to Asset Mapping
| **Samsara Field** | **SafetyAmp Field** | **Transformation/Notes** |
|-------------------|---------------------|-------------------------|
| `id` | `serial` | Samsara vehicle ID |
| `name` | `name` | Vehicle identifier |
| `vin` | `model` | Vehicle VIN stored in model field |
| `licensePlate` | `year` | License plate stored in year field |
| `make` | Appended to `name` | "name (make)" format |
| `model` | Appended to `name` | "name (make model)" |
| `year` | Appended to `name` | "name (make model year)" |
| `notes` | - | Parsed for employee ID |
| `tags[].name` | - | Used to determine site/department |

#### Driver Assignment
| **Samsara Field** | **SafetyAmp Field** | **Logic** |
|-------------------|---------------------|-----------|
| `staticAssignedDriver.id` | `user_id` | Mapped via driver notes → employee ID |
| `staticAssignedDriver.name` | - | Used for logging/debugging |

#### Vehicle Status
| **Samsara Value** | **SafetyAmp Field** | **Transformation** |
|-------------------|---------------------|-------------------|
| Tag: "regulated" | `status` | 1 (regulated) |
| Tag: "unregulated" | `status` | 0 (unregulated) |
| - | `asset_type_id` | Default: 3183 or site-specific |
| - | `site_id` | Default: 5145 or tag-based |

### 7. SafetyAmp → Viewpoint (No Direct Sync)
*Note: The system is primarily unidirectional from source systems to SafetyAmp. No data flows back to Viewpoint.*

## Data Flow Summary

### Primary Data Sources:
1. **Viewpoint Vista** (Source of Truth):
   - Employee master data
   - Department structure
   - Job/project information
   - Title definitions

2. **Microsoft Entra ID** (Enhancement):
   - Current email addresses
   - Phone number updates
   - User authentication status

3. **Samsara** (Fleet Data):
   - Vehicle information
   - Driver assignments
   - Regulation status

### Data Destination:
**SafetyAmp** receives all synchronized data as:
- Users (employees)
- Site Clusters (departments)
- Sites (jobs/projects)
- User Titles (job titles)
- Assets (vehicles)

### Key Transformation Rules:
1. **Phone Numbers**: All converted to E.164 format (+1XXXXXXXXXX)
2. **Gender**: Text (M/F) → Numeric (1/2)
3. **Dates**: Converted to ISO format
4. **Employee-Site Mapping**: Complex hierarchy traversal (Employee → Job → Department → Cluster → Site)
5. **Validation**: Required fields enforced, invalid data logged but not sent
6. **Fallback Strategy**: Strip problematic fields on initial failure, retry with minimal payload

## Sync Order and Dependencies

The synchronization follows a specific order to maintain referential integrity:

1. **Departments** → Creates cluster hierarchy
2. **Jobs** → Creates sites under clusters
3. **Titles** → Creates title definitions
4. **Employees** → Creates users referencing sites/titles
5. **Vehicles** → Creates assets referencing sites/users

## Data Validation Rules

### Required Fields by Entity Type

#### Employee (User)
- `first_name` - Required, non-empty
- `last_name` - Required, non-empty
- `email` - Required, valid email format
- `emp_id` - Required, unique identifier

#### Department (Cluster)
- `name` - Required
- `external_code` - Required for mapping
- `parent_cluster_id` - Required for hierarchy

#### Job (Site)
- `external_code` - Required (job number)
- `name` - Required
- `cluster_id` - Required for department association

#### Vehicle (Asset)
- `serial` - Required (Samsara ID)
- `name` - Required
- `asset_type_id` - Required
- `site_id` - Required

### Validation Transformations

#### Phone Number Cleaning
- Remove all non-numeric characters
- Add +1 country code if not present
- Validate 10-digit US format
- Convert to E.164: +1XXXXXXXXXX

#### Email Validation
- Lowercase conversion
- Format validation (contains @ and domain)
- Domain verification
- Removal of invalid characters

#### Gender Normalization
- "M", "Male", "m" → 1
- "F", "Female", "f" → 2
- Other/Unknown → null

## Error Handling Strategies

### Validation Failures
1. Log detailed validation errors with field specifics
2. Skip record if required fields missing
3. Increment error counters for monitoring

### API Failures
1. **422 Unprocessable Entity**:
   - Log failing fields
   - Attempt fallback creation without problematic fields
   - Common issues: duplicate email, invalid phone format

2. **429 Too Many Requests**:
   - Exponential backoff retry
   - Maximum 60-second wait
   - Respect rate limits (60 calls/61 seconds for SafetyAmp)

3. **Connection Failures**:
   - Circuit breaker activation after 5 consecutive failures
   - 30-second recovery timeout
   - Degraded mode operation continues

### Data Quality Issues
1. **Missing Site/Cluster Mapping**:
   - Skip employee record
   - Log skip reason
   - Continue processing other records

2. **Duplicate Detection**:
   - Use `emp_id` as primary key
   - Update existing records rather than create
   - Field-level diff for minimal API calls

## Performance Considerations

### Caching Strategy
- 4-hour TTL for API responses
- Redis primary, file-based fallback
- In-memory Vista data during sync cycle
- Cache refresh on data modifications

### Batch Processing
- Default batch size: 500 records
- Configurable via BATCH_SIZE environment variable
- Pagination for large result sets
- Connection pooling (8 + 15 overflow)