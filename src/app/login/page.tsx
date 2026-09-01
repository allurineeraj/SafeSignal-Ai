"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
  const [userId, setUserId] = useState("HSE001");
  const [password, setPassword] = useState("HSE@1234");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, password })
      });
      
      if (!res.ok) throw new Error("Invalid credentials");
      
      const data = await res.json();
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", data.user_id);
      localStorage.setItem("role", data.role);
      
      router.push("/hse");
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-20">
      <div className="glass-card p-8 space-y-6">
        <h2 className="text-2xl font-bold text-center">HSE Officer Login</h2>
        
        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm text-slate-300">User ID</label>
            <input 
              type="text" 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 outline-none focus:border-blue-500"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
            />
          </div>
          
          <div className="space-y-2">
            <label className="text-sm text-slate-300">Password</label>
            <input 
              type="password" 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 outline-none focus:border-blue-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          {error && <p className="text-red-400 text-sm">{error}</p>}
          
          <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium p-3 rounded-lg transition-colors">
            Sign In
          </button>
        </form>
      </div>
    </div>
  );
}
