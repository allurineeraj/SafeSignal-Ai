import { createClient } from "@supabase/supabase-js";

function getCleanEnv(name: string): string {
  const val = process.env[name] || "";
  return val.trim().replace(/^["']|["']$/g, "");
}

const supabaseUrlRaw =
  getCleanEnv("NEXT_PUBLIC_SUPABASE_URL") ||
  getCleanEnv("SUPABASE_URL") ||
  getCleanEnv("SUPABASE_PROJECT_URL");

const supabaseKeyRaw =
  getCleanEnv("SUPABASE_SECRET_KEY") ||
  getCleanEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY") ||
  getCleanEnv("SUPABASE_ANON_KEY") ||
  getCleanEnv("SUPABASE_SERVICE_ROLE_KEY") ||
  getCleanEnv("SUPABASE_KEY");

const isValidUrl = Boolean(supabaseUrlRaw && /^https?:\/\//i.test(supabaseUrlRaw));
const finalUrl = isValidUrl ? supabaseUrlRaw : "https://placeholder.supabase.co";
const finalKey = supabaseKeyRaw || "placeholder_key";

if (!isValidUrl || !supabaseKeyRaw) {
  console.warn(
    "[Supabase Client] Warning: Missing or invalid Supabase URL/Key environment variables. Database operations may fail until credentials are configured in Vercel settings."
  );
}

export const supabase = createClient(finalUrl, finalKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
});

