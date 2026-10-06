-- NON_FORMAL_D4_PREDECESSOR_CANDIDATE
-- This migration is an executable candidate derived from material/05_DB設計書.md
-- and material/06_API設計書.md. It is not an approved D4 contract and does not
-- close B27, U19, U20, or any other Phase 1 decision.

begin;

create schema if not exists private;
revoke all on schema private from public, anon;

create type public.notification_type as enum ('like', 'reply', 'follow', 'repost');

create table public.users (
  id uuid primary key references auth.users (id),
  username varchar(30) unique,
  display_name varchar(50),
  bio varchar(160),
  avatar_url text,
  header_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.posts (
  id uuid primary key,
  author_id uuid not null references public.users (id),
  body varchar(280),
  reply_to_post_id uuid references public.posts (id),
  repost_of_post_id uuid references public.posts (id),
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table public.post_media (
  id uuid primary key,
  post_id uuid not null references public.posts (id),
  url text not null,
  "order" smallint not null
);

create table public.likes (
  user_id uuid not null references public.users (id),
  post_id uuid not null references public.posts (id),
  created_at timestamptz not null,
  primary key (user_id, post_id)
);

create table public.follows (
  follower_id uuid not null references public.users (id),
  followee_id uuid not null references public.users (id),
  created_at timestamptz not null,
  primary key (follower_id, followee_id)
);

create table public.notifications (
  id uuid primary key,
  recipient_id uuid not null references public.users (id),
  actor_id uuid not null references public.users (id),
  type public.notification_type not null,
  post_id uuid references public.posts (id),
  read_at timestamptz,
  created_at timestamptz not null
);

create table public.hashtags (
  id uuid primary key,
  tag varchar(100) not null unique
);

create table public.post_hashtags (
  post_id uuid not null references public.posts (id),
  hashtag_id uuid not null references public.hashtags (id),
  primary key (post_id, hashtag_id)
);

create table public.bookmarks (
  user_id uuid not null references public.users (id),
  post_id uuid not null references public.posts (id),
  created_at timestamptz not null,
  primary key (user_id, post_id)
);

create index posts_author_created_at_idx on public.posts (author_id, created_at desc);
create index posts_reply_to_post_id_idx on public.posts (reply_to_post_id);
create index posts_repost_of_post_id_idx on public.posts (repost_of_post_id);
create index post_media_post_id_idx on public.post_media (post_id);
create index likes_post_id_idx on public.likes (post_id);
create index follows_followee_id_idx on public.follows (followee_id);
create index notifications_recipient_created_at_idx on public.notifications (recipient_id, created_at desc);
create index notifications_actor_id_idx on public.notifications (actor_id);
create index notifications_post_id_idx on public.notifications (post_id);
create index post_hashtags_hashtag_id_idx on public.post_hashtags (hashtag_id);
create index bookmarks_post_id_idx on public.bookmarks (post_id);

alter table public.users enable row level security;
alter table public.posts enable row level security;
alter table public.post_media enable row level security;
alter table public.likes enable row level security;
alter table public.follows enable row level security;
alter table public.notifications enable row level security;
alter table public.hashtags enable row level security;
alter table public.post_hashtags enable row level security;
alter table public.bookmarks enable row level security;

revoke all on table public.users from anon, authenticated;
revoke all on table public.posts from anon, authenticated;
revoke all on table public.post_media from anon, authenticated;
revoke all on table public.likes from anon, authenticated;
revoke all on table public.follows from anon, authenticated;
revoke all on table public.notifications from anon, authenticated;
revoke all on table public.hashtags from anon, authenticated;
revoke all on table public.post_hashtags from anon, authenticated;
revoke all on table public.bookmarks from anon, authenticated;

grant select on table public.users to authenticated;
grant update (username, display_name, bio, avatar_url, header_url) on table public.users to authenticated;

grant select on table public.posts to authenticated;
grant insert (id, author_id, body, reply_to_post_id, repost_of_post_id) on table public.posts to authenticated;

grant select on table public.post_media to authenticated;
grant insert (id, post_id, url, "order") on table public.post_media to authenticated;
grant update (post_id, url, "order") on table public.post_media to authenticated;
grant delete on table public.post_media to authenticated;

grant select, delete on table public.likes to authenticated;
grant insert (user_id, post_id, created_at) on table public.likes to authenticated;
grant select, delete on table public.follows to authenticated;
grant insert (follower_id, followee_id, created_at) on table public.follows to authenticated;
grant select on table public.notifications to authenticated;
grant update (read_at) on table public.notifications to authenticated;
grant select on table public.hashtags to authenticated;
grant insert (id, tag) on table public.hashtags to authenticated;
grant select, insert, delete on table public.post_hashtags to authenticated;
grant select, delete on table public.bookmarks to authenticated;
grant insert (user_id, post_id, created_at) on table public.bookmarks to authenticated;
grant usage on type public.notification_type to authenticated;

create policy users_select_authenticated
  on public.users for select to authenticated
  using (true);

create policy users_update_own
  on public.users for update to authenticated
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

create policy posts_select_active
  on public.posts for select to authenticated
  using (deleted_at is null);

create or replace function private.authenticated_user_can_target_active_post(p_post_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select (select auth.uid()) is not null
    and exists (
      select 1
      from public.posts as p
      where p.id = p_post_id
        and p.deleted_at is null
    );
$$;

revoke all on function private.authenticated_user_can_target_active_post(uuid) from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.authenticated_user_can_target_active_post(uuid) to authenticated;

create policy posts_insert_own_with_active_parents
  on public.posts for insert to authenticated
  with check (
    (select auth.uid()) = author_id
    and deleted_at is null
    and (
      reply_to_post_id is null
      or private.authenticated_user_can_target_active_post(reply_to_post_id)
    )
    and (
      repost_of_post_id is null
      or private.authenticated_user_can_target_active_post(repost_of_post_id)
    )
  );

create policy post_media_select_active_parent
  on public.post_media for select to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = post_media.post_id and p.deleted_at is null
    )
  );

create policy post_media_insert_own_active_post
  on public.post_media for insert to authenticated
  with check (
    exists (
      select 1 from public.posts as p
      where p.id = post_media.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  );

create policy post_media_update_own_active_post
  on public.post_media for update to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = post_media.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  )
  with check (
    exists (
      select 1 from public.posts as p
      where p.id = post_media.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  );

create policy post_media_delete_own_active_post
  on public.post_media for delete to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = post_media.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  );

create policy likes_select_active_parent
  on public.likes for select to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = likes.post_id and p.deleted_at is null
    )
  );

create policy likes_insert_own_active_parent
  on public.likes for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and exists (
      select 1 from public.posts as p
      where p.id = likes.post_id and p.deleted_at is null
    )
  );

create policy likes_delete_own_active_parent
  on public.likes for delete to authenticated
  using (
    (select auth.uid()) = user_id
    and exists (
      select 1 from public.posts as p
      where p.id = likes.post_id and p.deleted_at is null
    )
  );

create policy follows_select_authenticated
  on public.follows for select to authenticated
  using (true);

create policy follows_insert_own
  on public.follows for insert to authenticated
  with check ((select auth.uid()) = follower_id);

create policy follows_delete_own
  on public.follows for delete to authenticated
  using ((select auth.uid()) = follower_id);

create policy notifications_select_own
  on public.notifications for select to authenticated
  using (
    (select auth.uid()) = recipient_id
    and (
      post_id is null
      or exists (
        select 1 from public.posts as p
        where p.id = notifications.post_id and p.deleted_at is null
      )
    )
  );

create policy notifications_update_read_at_own
  on public.notifications for update to authenticated
  using ((select auth.uid()) = recipient_id)
  with check ((select auth.uid()) = recipient_id);

create policy hashtags_select_authenticated
  on public.hashtags for select to authenticated
  using (true);

create policy hashtags_insert_authenticated
  on public.hashtags for insert to authenticated
  with check ((select auth.uid()) is not null);

create policy post_hashtags_select_active_parent
  on public.post_hashtags for select to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = post_hashtags.post_id and p.deleted_at is null
    )
  );

create policy post_hashtags_insert_own_active_post
  on public.post_hashtags for insert to authenticated
  with check (
    exists (
      select 1 from public.posts as p
      where p.id = post_hashtags.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  );

create policy post_hashtags_delete_own_active_post
  on public.post_hashtags for delete to authenticated
  using (
    exists (
      select 1 from public.posts as p
      where p.id = post_hashtags.post_id
        and p.author_id = (select auth.uid())
        and p.deleted_at is null
    )
  );

create policy bookmarks_select_own_active_parent
  on public.bookmarks for select to authenticated
  using (
    (select auth.uid()) = user_id
    and exists (
      select 1 from public.posts as p
      where p.id = bookmarks.post_id and p.deleted_at is null
    )
  );

create policy bookmarks_insert_own_active_parent
  on public.bookmarks for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and exists (
      select 1 from public.posts as p
      where p.id = bookmarks.post_id and p.deleted_at is null
    )
  );

create policy bookmarks_delete_own_active_parent
  on public.bookmarks for delete to authenticated
  using (
    (select auth.uid()) = user_id
    and exists (
      select 1 from public.posts as p
      where p.id = bookmarks.post_id and p.deleted_at is null
    )
  );

create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.users (id) values (new.id);
  return new;
end;
$$;

revoke all on function private.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

create or replace function private.soft_delete_owned_post(p_post_id uuid)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  affected_rows integer;
begin
  if (select auth.uid()) is null then
    return false;
  end if;

  update public.posts
  set deleted_at = now()
  where id = p_post_id
    and author_id = (select auth.uid())
    and deleted_at is null;

  get diagnostics affected_rows = row_count;
  return affected_rows = 1;
end;
$$;

revoke all on function private.soft_delete_owned_post(uuid) from public, anon;
grant execute on function private.soft_delete_owned_post(uuid) to authenticated;

create or replace function public.soft_delete_post(p_post_id uuid)
returns boolean
language sql
security invoker
set search_path = ''
as $$
  select private.soft_delete_owned_post(p_post_id);
$$;

revoke all on function public.soft_delete_post(uuid) from public, anon;
grant execute on function public.soft_delete_post(uuid) to authenticated;

comment on schema private is
  'NON_FORMAL_D4_PREDECESSOR_CANDIDATE: non-exposed helpers; not an approved D4 contract.';
comment on function public.soft_delete_post(uuid) is
  'NON_FORMAL_D4_PREDECESSOR_CANDIDATE: the only authenticated posts mutation after insert.';

commit;
