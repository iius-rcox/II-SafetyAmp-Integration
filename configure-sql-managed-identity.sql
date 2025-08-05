-- SQL Script to Configure Azure Managed Identity for SafetyAmp Integration
-- Run this script on the SQL Server: inscolvsql.insulationsinc.local
-- 
-- PREREQUISITE: Azure AD authentication must be enabled in SQL Server
-- Run the enable-azure-ad-registry.ps1 script first if needed
-- 
-- EXECUTION ORDER:
-- 1. First run the MASTER database section
-- 2. Then run the VIEWPOINT database section
-- 3. Finally run the verification queries

-- =============================================
-- SECTION 1: MASTER DATABASE (Run First)
-- =============================================
USE [master];
GO

-- Create a login for the managed identity
-- This must be done in the master database
CREATE LOGIN [a2bcb3ce-a89b-43af-804c-e8029e0bafb4] 
FROM EXTERNAL PROVIDER
WITH DEFAULT_DATABASE = [Viewpoint];
GO

-- Verify the login was created
SELECT name, type_desc, is_disabled 
FROM sys.server_principals 
WHERE name = 'a2bcb3ce-a89b-43af-804c-e8029e0bafb4';
GO

-- =============================================
-- SECTION 2: VIEWPOINT DATABASE (Run Second)
-- =============================================
USE [Viewpoint];
GO

-- Create a user in the Viewpoint database
CREATE USER [safety-amp-managed-identity] 
FOR LOGIN [a2bcb3ce-a89b-43af-804c-e8029e0bafb4];
GO

-- Grant necessary permissions to the user
-- Grant access to employee data tables
GRANT SELECT ON [bPREH] TO [safety-amp-managed-identity];
GRANT SELECT ON [bJOB] TO [safety-amp-managed-identity];
GRANT SELECT ON [bDEPT] TO [safety-amp-managed-identity];

-- Grant access to job cost tables (if needed)
GRANT SELECT ON [bJOBCOST] TO [safety-amp-managed-identity];

-- Grant access to system tables for metadata
GRANT SELECT ON [INFORMATION_SCHEMA].[TABLES] TO [safety-amp-managed-identity];
GRANT SELECT ON [INFORMATION_SCHEMA].[COLUMNS] TO [safety-amp-managed-identity];

-- Add user to db_datareader role for read-only access
ALTER ROLE [db_datareader] ADD MEMBER [safety-amp-managed-identity];
GO

-- =============================================
-- SECTION 3: VERIFICATION QUERIES (Run Last)
-- =============================================

-- Check if the user was created in the Viewpoint database
SELECT name, type_desc, authentication_type_desc 
FROM sys.database_principals 
WHERE name = 'safety-amp-managed-identity';

-- Check user permissions and login mapping
SELECT 
    dp.name AS DatabaseUser,
    dp.type_desc AS UserType,
    sp.name AS ServerLogin,
    sp.type_desc AS LoginType
FROM sys.database_principals dp
LEFT JOIN sys.server_principals sp ON dp.sid = sp.sid
WHERE dp.name = 'safety-amp-managed-identity';

-- Check role memberships
SELECT 
    dp.name AS DatabaseUser,
    r.name AS DatabaseRole
FROM sys.database_role_members rm
JOIN sys.database_principals dp ON rm.member_principal_id = dp.principal_id
JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
WHERE dp.name = 'safety-amp-managed-identity';

-- Test a simple query to verify permissions
SELECT TOP 1 'Connection Test Successful' as TestResult FROM INFORMATION_SCHEMA.TABLES; 