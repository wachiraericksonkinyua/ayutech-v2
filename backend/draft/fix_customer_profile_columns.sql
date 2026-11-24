-- ============================================================================
-- AyuTech: FIX for "relation customer_profiles does not exist"
--
-- The application stores customer profile details in public.customers.
-- There is NO table named customer_profiles - any query referencing it is wrong.
--
--   Backend reads/writes: supabase.table("customers")  (app/routers/auth.py)
--
-- This script is idempotent: safe to run multiple times.
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- ============================================================================

-- 1) Make sure the real profile table exists (no-op if it already does). ------
CREATE TABLE IF NOT EXISTS public.customers (
  id         UUID PRIMARY KEY,
  email      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) Add every profile column the app expects, if missing. -------------------
--    phone is TEXT so it keeps leading zeros / country code as entered.
--    addresses is JSONB because the app sends a JSON array.
ALTER TABLE public.customers
  ADD COLUMN IF NOT EXISTS username   TEXT,
  ADD COLUMN IF NOT EXISTS full_name  TEXT,
  ADD COLUMN IF NOT EXISTS gender     TEXT,
  ADD COLUMN IF NOT EXISTS phone      TEXT,
  ADD COLUMN IF NOT EXISTS avatar_url TEXT,
  ADD COLUMN IF NOT EXISTS banner_url TEXT,
  ADD COLUMN IF NOT EXISTS addresses  JSONB DEFAULT '[]'::jsonb;

-- 3) birth_date must be DATE. -------------------------------------------------
--    If the column is missing, create it as DATE. If it already exists as TEXT
--    (older migration), normalise the values and convert it to DATE in place.
ALTER TABLE public.customers
  ADD COLUMN IF NOT EXISTS birth_date DATE;

DO $$
DECLARE
  col_type TEXT;
BEGIN
  SELECT data_type
    INTO col_type
    FROM information_schema.columns
   WHERE table_schema = 'public'
     AND table_name   = 'customers'
     AND column_name  = 'birth_date';

  IF col_type IS NOT NULL AND col_type <> 'date' THEN
    -- Blank / invalid legacy values become NULL instead of failing the cast.
    ALTER TABLE public.customers
      ALTER COLUMN birth_date TYPE DATE
      USING (
        CASE
          WHEN birth_date IS NULL THEN NULL
          WHEN trim(birth_date::text) = '' THEN NULL
          WHEN trim(birth_date::text) ~ '^\d{4}-\d{2}-\d{2}$'
            THEN trim(birth_date::text)::date
          ELSE NULL
        END
      );
  END IF;
END $$;

-- 4) Helpful indexes. ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_customers_email ON public.customers (email);

-- 5) Sanity check - should list the profile columns above. --------------------
-- SELECT column_name, data_type
--   FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'customers'
--  ORDER BY ordinal_position;
