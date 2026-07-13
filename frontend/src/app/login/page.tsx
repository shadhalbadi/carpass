"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("buyer@carpass.om");
  const [password, setPassword] = useState("buyer123");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("buyer");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data =
        mode === "login"
          ? await api.login(email, password)
          : await api.register({ email, password, full_name: fullName, role });
      localStorage.setItem("carpass_token", data.access_token);
      router.push(data.user.role === "agent" ? "/agent" : "/");
    } catch (err: any) {
      setError(err.message || "Auth failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div>
        <h1 className="page-title">{mode === "login" ? "Sign in" : "Create account"}</h1>
        <p className="page-sub">
          Demo: buyer@carpass.om / buyer123 · agent@carpass.om / agent123 · admin@carpass.om / admin123
        </p>
      </div>
      <form onSubmit={onSubmit} className="card space-y-4">
        {mode === "register" && (
          <>
            <div>
              <label className="label">Full name</label>
              <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="buyer">Buyer</option>
                <option value="agent">Clearing agent</option>
                <option value="dealer">Dealer</option>
              </select>
            </div>
          </>
        )}
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="danger-text text-sm">{error}</p>}
        <button className="btn w-full" disabled={loading}>
          {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Register"}
        </button>
      </form>
      <button type="button" className="link text-sm" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Have an account? Sign in"}
      </button>
      <Link href="/" className="block text-sm text-slate-500 hover:text-slate-800">
        ← Back to calculator
      </Link>
    </div>
  );
}
