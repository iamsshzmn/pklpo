-- Bootstrap application DB user and database
-- Safe to run multiple times

-- Create/alter login role
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pklpo_user') THEN
    CREATE ROLE pklpo_user LOGIN PASSWORD 'strongpassword';
  ELSE
    ALTER ROLE pklpo_user WITH LOGIN PASSWORD 'strongpassword';
  END IF;
END $$;

-- Create database if it does not exist (must be outside of DO/transaction)
SELECT 'CREATE DATABASE pklpo OWNER pklpo_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'pklpo');
\gexec

-- Ensure ownership/privileges even if DB existed
ALTER DATABASE pklpo OWNER TO pklpo_user;
GRANT ALL PRIVILEGES ON DATABASE pklpo TO pklpo_user;
