import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const SUPABASE_URL = 'https://supgrlinqgxvifijgbns.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1cGdybGlucWd4dmlmaWpnYm5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIzNjA2MjcsImV4cCI6MjA5NzkzNjYyN30.UYaQLXjBnah2YOQs65zrZskYP7Cw4CnGroYUWOrjxqg';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});

export async function requireAuth() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    location.href = '/auth/';
    return false;
  }
  return true;
}