-- AyuTech: order tracking, saved addresses & product reviews migration
-- Run this in the Supabase SQL editor (Dashboard > SQL > New query).

-- 1) Orders: delivery address recorded at checkout (used by phone tracking)
ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS delivery_address TEXT DEFAULT '';

-- 2) Product reviews (verified buyers)
CREATE TABLE IF NOT EXISTS public.reviews (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id   TEXT NOT NULL,
  customer_id  TEXT,
  customer_name TEXT NOT NULL DEFAULT 'Customer',
  rating       INT  NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment      TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reviews_product
  ON public.reviews (product_id, created_at DESC);

-- Allow the anon/publishable key (used by the app) to read & insert reviews
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'reviews_anon_read'
  ) THEN
    CREATE POLICY reviews_anon_read ON public.reviews
      FOR SELECT TO anon USING (true);
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'reviews_anon_insert'
  ) THEN
    CREATE POLICY reviews_anon_insert ON public.reviews
      FOR INSERT TO anon WITH CHECK (true);
  END IF;
END $$;