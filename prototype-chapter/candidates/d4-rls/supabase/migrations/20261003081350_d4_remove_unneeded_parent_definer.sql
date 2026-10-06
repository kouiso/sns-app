-- NON_FORMAL_D4_PREDECESSOR_CANDIDATE
-- Direct correlated EXISTS was verified in a rolled-back PostgreSQL17.11
-- authenticated-role transaction. Preserve the original applied migration.
begin;

drop policy posts_insert_own_with_active_parents on public.posts;
create policy posts_insert_own_with_active_parents
  on public.posts for insert to authenticated
  with check (
    (select auth.uid()) = author_id
    and deleted_at is null
    and (
      reply_to_post_id is null
      or exists (
        select 1 from public.posts as parent
        where parent.id = posts.reply_to_post_id
          and parent.deleted_at is null
      )
    )
    and (
      repost_of_post_id is null
      or exists (
        select 1 from public.posts as parent
        where parent.id = posts.repost_of_post_id
          and parent.deleted_at is null
      )
    )
  );

drop function private.authenticated_user_can_target_active_post(uuid);

commit;
