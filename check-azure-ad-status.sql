-- SQL Script to Check Azure AD Authentication Status
-- Run this on your SQL Server: inscolvsql.insulationsinc.local

-- =============================================
-- CHECK 1: SQL Server Version and Edition
-- =============================================
SELECT 
    @@VERSION as SQLServerVersion,
    SERVERPROPERTY('Edition') as Edition,
    SERVERPROPERTY('ProductLevel') as ProductLevel;

-- =============================================
-- CHECK 2: Authentication Mode
-- =============================================
SELECT 
    name as SettingName,
    value as SettingValue,
    value_in_use as CurrentValue
FROM sys.configurations 
WHERE name IN ('authentication mode', 'mixed mode authentication');

-- =============================================
-- CHECK 3: Check for Azure AD Login Support
-- =============================================
-- This will show if Azure AD logins exist
SELECT 
    name,
    type_desc,
    is_disabled,
    create_date
FROM sys.server_principals 
WHERE type_desc IN ('EXTERNAL_LOGIN', 'EXTERNAL_GROUP')
ORDER BY type_desc, name;

-- =============================================
-- CHECK 4: Check for Azure AD Authentication Provider
-- =============================================
-- Check if the Azure AD authentication provider is registered
SELECT 
    name,
    type_desc,
    is_disabled
FROM sys.server_principals 
WHERE name LIKE '%Azure%' OR name LIKE '%AD%';

-- =============================================
-- CHECK 5: Check SQL Server Configuration
-- =============================================
-- Check if Azure AD authentication is enabled
SELECT 
    name,
    value,
    value_in_use,
    description
FROM sys.configurations 
WHERE name LIKE '%azure%' OR name LIKE '%ad%' OR name LIKE '%authentication%';

-- =============================================
-- CHECK 6: Check for Azure AD Provider DLL
-- =============================================
-- This checks if the Azure AD authentication provider is available
SELECT 
    name,
    type_desc,
    is_disabled
FROM sys.server_principals 
WHERE type_desc = 'EXTERNAL_LOGIN';

-- =============================================
-- CHECK 7: Test Azure AD Login Creation
-- =============================================
-- This will attempt to create a test Azure AD login (will fail if not supported)
-- Comment out the lines below if you don't want to test this
/*
BEGIN TRY
    CREATE LOGIN [test-azure-ad-login] 
    FROM EXTERNAL PROVIDER;
    PRINT 'Azure AD authentication is supported!';
    DROP LOGIN [test-azure-ad-login];
END TRY
BEGIN CATCH
    PRINT 'Azure AD authentication is NOT supported: ' + ERROR_MESSAGE();
END CATCH
*/ 