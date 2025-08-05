-- Create SQL User for SafetyAmp Integration
-- Run this on SQL Server: inscolvsql.insulationsinc.local

-- Step 1: Create login in master database
USE [master];
GO

CREATE LOGIN [safety-amp-sql-user] 
WITH PASSWORD = '&beL4EUtDSQH#uCxG8A3!^DEx',
DEFAULT_DATABASE = [Viewpoint],
CHECK_EXPIRATION = OFF,
CHECK_POLICY = OFF;
GO

-- Step 2: Create user in Viewpoint database
USE [Viewpoint];
GO

CREATE USER [safety-amp-sql-user] 
FOR LOGIN [safety-amp-sql-user];
GO

-- Step 3: Grant permissions
GRANT SELECT ON [bPREH] TO [safety-amp-sql-user];
GRANT SELECT ON [bJOB] TO [safety-amp-sql-user];
GRANT SELECT ON [bDEPT] TO [safety-amp-sql-user];
GRANT SELECT ON [bJOBCOST] TO [safety-amp-sql-user];
GRANT SELECT ON [INFORMATION_SCHEMA].[TABLES] TO [safety-amp-sql-user];
GRANT SELECT ON [INFORMATION_SCHEMA].[COLUMNS] TO [safety-amp-sql-user];

-- Step 4: Add to datareader role
ALTER ROLE [db_datareader] ADD MEMBER [safety-amp-sql-user];
GO

-- Step 5: Test the connection
SELECT TOP 1 'Connection Test Successful' as TestResult FROM INFORMATION_SCHEMA.TABLES; 