-- =============================================================
-- Supabase Schema for People Enjoyer Backend
-- Run this in your Supabase project: Dashboard → SQL Editor
-- =============================================================

-- 1. Users -------------------------------------------------------
create table if not exists public.users (
    email                   text primary key,
    name                    text,
    avatar                  text,
    bio                     text,
    lat                     double precision,
    lng                     double precision,
    from_currency           text,
    to_currency             text,
    people_finder_live      boolean default false,
    people_search_range_km  double precision,
    last_seen_at            timestamptz,
    created_at              timestamptz default now()
);

-- 2. OTP Store ---------------------------------------------------
create table if not exists public.otp_store (
    key         text primary key,   -- format: "purpose:email"
    otp         text    not null,
    expires_at  timestamptz not null,
    created_at  timestamptz default now()
);

-- Auto-cleanup: delete expired rows (optional; backend also cleans up)
-- You can enable pg_cron in Supabase to run this periodically:
-- delete from public.otp_store where expires_at < now();

-- 3. Messages ----------------------------------------------------
create table if not exists public.messages (
    id          text primary key,   -- format: "msg-<timestamp>-<rand>"
    module      text    not null,   -- "currency" | "people"
    sender      text    not null,
    recipient   text    not null,
    text        text    not null,
    sent_at     timestamptz not null,
    read        boolean default false
);

create index if not exists messages_sender_idx    on public.messages (sender);
create index if not exists messages_recipient_idx on public.messages (recipient);
create index if not exists messages_module_idx    on public.messages (module);

-- 4. Connections -------------------------------------------------
create table if not exists public.connections (
    id          text primary key,   -- format: "email_a::email_b" (sorted)
    from_email  text not null,
    to_email    text not null,
    status      text not null default 'pending',  -- pending | accepted | removed
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

create index if not exists connections_from_idx on public.connections (from_email);
create index if not exists connections_to_idx   on public.connections (to_email);

-- 5. Enjoyer profiles (ProfilePopup) -----------------------------
create table if not exists public.user_enjoyer (
    id bigint generated always as identity primary key,
    name text not null,
    age integer not null,
    bio text,
    is_deactivated boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_enjoyer_photos (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.user_enjoyer(id) on delete cascade,
    photo_url text not null,
    photo_order integer not null,
    created_at timestamptz default now()
);

create index if not exists user_enjoyer_photos_user_idx
    on public.user_enjoyer_photos(user_id);

-- Storage: create bucket "enjoyer-photos" in Supabase Dashboard (public read)
