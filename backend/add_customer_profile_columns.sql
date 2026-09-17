-- Add customer profile fields for the AyuTech profile settings page.
-- Run this in the Supabase SQL editor for your project.
--
-- NOTE: the profile table is public.customers (there is no customer_profiles).
-- If you hit "relation customer_profiles does not exist", you were targeting the
-- wrong table - use public.customers (or run fix_customer_profile_columns.sql).

alter table public.customers
  add column if not exists username   text,
  add column if not exists full_name  text,
  add column if not exists birth_date date,
  add column if not exists gender     text,
  add column if not exists phone      text,
  add column if not exists avatar_url text,
  add column if not exists banner_url text,
  add column if not exists addresses  jsonb default '[]'::jsonb;

-- Optional: keep the username unique so it can be used as a public handle.
-- (Requires all existing rows to have distinct usernames before enabling.)
-- create unique index if not exists customers_username_uidx on public.customers (username);
