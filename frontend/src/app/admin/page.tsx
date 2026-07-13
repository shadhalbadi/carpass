"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AdminPage() {
  const [fees, setFees] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [crawlResult, setCrawlResult] = useState<any>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setFees(await api.adminFees());
      setRoutes(await api.adminRoutes());
    } catch (err: any) {
      setError(err.message + " — login as admin@carpass.om / admin123");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runCrawl() {
    try {
      setCrawlResult(await api.adminCrawl());
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Admin</h1>
          <p className="page-sub">Fee tables, shipping routes, and crawler controls.</p>
        </div>
        <button className="btn" onClick={runCrawl}>
          Run demo crawl
        </button>
      </div>
      {error && <p className="danger-text text-sm">{error}</p>}
      {crawlResult && (
        <pre className="card overflow-auto text-xs text-slate-700">{JSON.stringify(crawlResult, null, 2)}</pre>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card space-y-1">
          <h2 className="mb-3 font-semibold text-slate-900">Fee table</h2>
          {fees.map((f) => (
            <div
              key={f.id}
              className="flex items-center justify-between gap-3 border-b border-slate-100 py-3 text-sm last:border-0"
            >
              <div>
                <div className="font-medium text-slate-800">{f.label}</div>
                <div className="text-slate-500">{f.key}</div>
              </div>
              <div className="font-mono text-slate-800">
                {f.value} {f.unit}
              </div>
            </div>
          ))}
        </div>
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-900">Shipping routes</h2>
          {routes.map((r) => (
            <div key={r.id} className="surface-inset p-3 text-sm">
              <div className="font-medium text-slate-800">
                {r.origin_country} · {r.origin_port} → {r.dest_port}
              </div>
              <div className="mt-1 text-slate-500">
                {r.mode.toUpperCase()} ${r.min_usd}-{r.max_usd} + inland ${r.inland_usd} · {r.transit_days_min}-
                {r.transit_days_max} days
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
