"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const MILESTONES = ["arrived_port", "customs", "released", "delivered"];

export default function AgentPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("Bayan declaration in progress");

  async function load() {
    try {
      setRows(await api.agentShipments());
    } catch (err: any) {
      setError(err.message + " — login as agent@carpass.om / agent123");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function claim(id: number) {
    await api.agentClaim(id);
    await load();
  }

  async function setStatus(id: number, milestone: string) {
    await api.agentStatus(id, { milestone, status_note: note });
    await load();
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title">Clearing agent desk</h1>
        <p className="page-sub">Update customs and port milestones. Clients follow via tracking links.</p>
      </div>
      {error && <p className="danger-text text-sm">{error}</p>}
      <div className="card max-w-xl">
        <label className="label">Status note</label>
        <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="space-y-3">
        {rows.map((s) => (
          <div key={s.id} className="card space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-semibold text-slate-900">
                  {s.year} {s.make} {s.model}
                </div>
                <div className="font-mono text-sm font-semibold text-blue-700">{s.tracking_code}</div>
                <div className="text-sm text-slate-500">Current: {s.current_milestone}</div>
              </div>
              <a className="link text-sm" href={`/track?code=${s.tracking_code}`}>
                Client track link →
              </a>
            </div>
            <div className="flex flex-wrap gap-2">
              {!s.agent_id && (
                <button className="btn-secondary text-xs" onClick={() => claim(s.id)}>
                  Claim
                </button>
              )}
              {MILESTONES.map((m) => (
                <button key={m} className="btn-secondary text-xs" onClick={() => setStatus(s.id, m)}>
                  Mark {m.replaceAll("_", " ")}
                </button>
              ))}
            </div>
          </div>
        ))}
        {rows.length === 0 && !error && (
          <p className="text-sm text-slate-500">No assigned shipments yet. Create one as a buyer, then claim it here.</p>
        )}
      </div>
    </div>
  );
}
