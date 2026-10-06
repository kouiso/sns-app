-- Candidate for the disposable trial only; not the adopted API contract.
-- A narrowly scoped RPC avoids exposing deleted rows via SELECT policies.
CREATE FUNCTION public.trial_soft_delete(target_id uuid)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE affected integer;
BEGIN
  UPDATE public.trial_posts SET deleted_at = now()
    WHERE id = target_id AND author_id = auth.uid() AND deleted_at IS NULL;
  GET DIAGNOSTICS affected = ROW_COUNT;
  RETURN affected;
END;
$$;
REVOKE ALL ON FUNCTION public.trial_soft_delete(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.trial_soft_delete(uuid) TO authenticated;
