-- SQL Script to Configure Standard SQL User for SafetyAmp Integration
-- Run this script on the SQL Server: inscolvsql.insulationsinc.local
-- 
-- This creates a standard SQL user with the credentials stored in Azure Key Vault
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

-- Create a SQL login for SafetyAmp integration
-- Password: &beL4EUtDSQH#uCxG8A3!^DEx
CREATE LOGIN [safety-amp-sql-user] 
WITH PASSWORD = '&beL4EUtDSQH#uCxG8A3!^DEx',
DEFAULT_DATABASE = [Viewpoint],
CHECK_EXPIRATION = OFF,
CHECK_POLICY = OFF;
GO

-- Verify the login was created
SELECT name, type_desc, is_disabled 
FROM sys.server_principals 
WHERE name = 'safety-amp-sql-user';
GO

-- =============================================
-- SECTION 2: VIEWPOINT DATABASE (Run Second)
-- =============================================
USE [Viewpoint];
GO

-- Create a user in the Viewpoint database
CREATE USER [safety-amp-sql-user] 
FOR LOGIN [safety-amp-sql-user];
GO

-- Grant necessary permissions to the user
-- Grant access to employee data tables
GRANT SELECT ON [bPREH] TO [safety-amp-sql-user];
GRANT SELECT ON [bJOB] TO [safety-amp-sql-user];
GRANT SELECT ON [bDEPT] TO [safety-amp-sql-user];

-- Grant access to job cost tables (if needed)
GRANT SELECT ON [bJOBCOST] TO [safety-amp-sql-user];

-- Grant access to system tables for metadata
GRANT SELECT ON [INFORMATION_SCHEMA].[TABLES] TO [safety-amp-sql-user];
GRANT SELECT ON [INFORMATION_SCHEMA].[COLUMNS] TO [safety-amp-sql-user];

-- Add user to db_datareader role for read-only access
ALTER ROLE [db_datareader] ADD MEMBER [safety-amp-sql-user];
GO

-- =============================================
-- SECTION 3: VERIFICATION QUERIES (Run Last)
-- =============================================

-- Check if the user was created in the Viewpoint database
SELECT name, type_desc, authentication_type_desc 
FROM sys.database_principals 
WHERE name = 'safety-amp-sql-user';

-- Check user permissions and login mapping
SELECT 
    dp.name AS DatabaseUser,
    dp.type_desc AS UserType,
    sp.name AS ServerLogin,
    sp.type_desc AS LoginType
FROM sys.database_principals dp
LEFT JOIN sys.server_principals sp ON dp.sid = sp.sid
WHERE dp.name = 'safety-amp-sql-user';

-- Check role memberships
SELECT 
    dp.name AS DatabaseUser,
    r.name AS DatabaseRole
FROM sys.database_role_members rm
JOIN sys.database_principals dp ON rm.member_principal_id = dp.principal_id
JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
WHERE dp.name = 'safety-amp-sql-user';

-- Test a simple query to verify permissions
SELECT TOP 1 'Connection Test Successful' as TestResult FROM INFORMATION_SCHEMA.TABLES; 