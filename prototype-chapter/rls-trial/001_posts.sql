-- Discardable local trial, not a production migration or P1 decision.
-- Owner access is tested through PostgREST using ordinary user JWTs.
CREATE TABLE public.trial_posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id uuid NOT NULL REFERENCES auth.users(id),
  body varchar(280) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
ALTER TABLE public.trial_posts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.trial_posts FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.trial_posts TO authenticated;
-- DELETE privilege is deliberately present in this trial: no DELETE policy
-- must still prevent physical deletion. Production grants remain undecided.
CREATE POLICY trial_read ON public.trial_posts FOR SELECT TO authenticated
  USING (deleted_at IS NULL);
CREATE POLICY trial_insert ON public.trial_posts FOR INSERT TO authenticated
  WITH CHECK (author_id = (SELECT auth.uid()));
CREATE POLICY trial_update ON public.trial_posts FOR UPDATE TO authenticated
  USING (author_id = (SELECT auth.uid()))
  WITH CHECK (author_id = (SELECT auth.uid()));
