-- ============================================================================
-- AyuTech: consolidated Supabase setup (profile fields, staff, indexes)
-- Run in Supabase Dashboard -> SQL Editor -> New query -> Run.
-- Safe to re-run: every statement is idempotent (IF NOT EXISTS).
-- ============================================================================

-- 1) CUSTOMER PROFILE FIELDS --------------------------------------------------
-- Required for the profile photo / banner / personal info to save.
ALTER TABLE public.customers
  ADD COLUMN IF NOT EXISTS username   TEXT,
  ADD COLUMN IF NOT EXISTS full_name  TEXT,
  ADD COLUMN IF NOT EXISTS birth_date TEXT,
  ADD COLUMN IF NOT EXISTS gender     TEXT,
  ADD COLUMN IF NOT EXISTS phone      TEXT,
  ADD COLUMN IF NOT EXISTS avatar_url TEXT,
  ADD COLUMN IF NOT EXISTS banner_url TEXT;

-- 2) ORDERS: delivery address -------------------------------------------------
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS delivery_address TEXT DEFAULT '';

-- 3) STAFF USERS (login for the POS / admin dashboard) ------------------------
-- If this table already exists, this is a no-op. The backend reads
-- id, name, role, phone, pin_code from it.
CREATE TABLE IF NOT EXISTS public.staff_users (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  role       TEXT NOT NULL DEFAULT 'staff',
  phone      TEXT,
  pin_code   TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3b) Link staff to Supabase Auth (email + password login) --------------------
ALTER TABLE public.staff_users
  ADD COLUMN IF NOT EXISTS auth_user_id UUID,
  ADD COLUMN IF NOT EXISTS email        TEXT,
  ADD COLUMN IF NOT EXISTS active       BOOLEAN NOT NULL DEFAULT TRUE;

-- Legacy PIN logins may have been required; new email/password staff do not.
ALTER TABLE public.staff_users
  ALTER COLUMN pin_code DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_auth_user
  ON public.staff_users (auth_user_id)
  WHERE auth_user_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_email
  ON public.staff_users (lower(email))
  WHERE email IS NOT NULL;

-- 4) PERFORMANCE INDEXES (speed up orders / profile / catalog lookups) --------
CREATE INDEX IF NOT EXISTS idx_orders_customer_id
  ON public.orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_reference
  ON public.orders (order_reference);
CREATE INDEX IF NOT EXISTS idx_orders_checkout_request_id
  ON public.orders (checkout_request_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at
  ON public.orders (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_customers_email
  ON public.customers (email);
CREATE INDEX IF NOT EXISTS idx_products_category
  ON public.products (category);

-- 5) REVIEWS (verified-buyer reviews) -----------------------------------------
-- (Also in add_orders_reviews_addresses.sql - kept here so this file is complete.)
CREATE TABLE IF NOT EXISTS public.reviews (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id    TEXT NOT NULL,
  customer_id   TEXT,
  customer_name TEXT NOT NULL DEFAULT 'Customer',
  rating        INT  NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment       TEXT NOT NULL DEFAULT '',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_product
  ON public.reviews (product_id, created_at DESC);

-- ============================================================================
-- OPTIONAL: default staff logins (change the PINs afterwards!)
-- Uncomment ONLY if your staff_users table is empty.
-- ============================================================================
-- INSERT INTO public.staff_users (name, role, phone, pin_code) VALUES
--   ('Admin', 'admin', '254112323814', '9999'),
--   ('Staff', 'staff', '254700000001', '1234')
-- ON CONFLICT DO NOTHING;
