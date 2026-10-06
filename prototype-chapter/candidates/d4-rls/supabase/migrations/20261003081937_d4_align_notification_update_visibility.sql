-- NON_FORMAL_D4_PREDECESSOR_CANDIDATE
-- A filtered SDK UPDATE already hid deleted-parent notifications. A controlled
-- no-WHERE/no-RETURNING SQL-role probe showed the UPDATE policy alone did not.
begin;

drop policy notifications_update_read_at_own on public.notifications;
create policy notifications_update_read_at_own
  on public.notifications for update to authenticated
  using (
    (select auth.uid()) = recipient_id
    and (
      post_id is null
      or exists (
        select 1 from public.posts as parent
        where parent.id = notifications.post_id
          and parent.deleted_at is null
      )
    )
  )
  with check (
    (select auth.uid()) = recipient_id
    and (
      post_id is null
      or exists (
        select 1 from public.posts as parent
        where parent.id = notifications.post_id
          and parent.deleted_at is null
      )
    )
  );

commit;
