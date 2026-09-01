import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    const { user_id, password } = await req.json();

    // In a real app we'd verify hashes, but this is the demo login for the SIH prototype
    // We check against the users table in supabase or a simple fallback
    const { data: users, error } = await supabase.from("users").select("*").eq("user_id", user_id);

    if (error || !users || users.length === 0) {
      if (user_id === "HSE001" && password === "HSE@1234") {
        return NextResponse.json({ success: true, token: "demo-token", role: "HSE Officer", user_id });
      }
      return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
    }

    const user = users[0];
    
    // We expect the password to just be "HSE@1234" in the DB for the demo 
    // or if it matches the hash we could verify (skipping hash for this simple demo Node rewrite)
    if (password === user.password_hash || (user_id === "HSE001" && password === "HSE@1234")) {
      return NextResponse.json({ success: true, token: "demo-token-123", role: user.role, user_id: user.user_id });
    }

    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
