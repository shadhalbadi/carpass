"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

const STEPS = ["purchased", "export_yard", "on_vessel", "arrived_port", "customs", "released", "delivered"];

function TrackInner() {
  const searchParams = useSearchParams();
  const [code, setCode] = useState("");
  const [shipment, setShipment] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadCode(value: string) {
    setLoading(true);
    setError("");
    try {
      const data = await api.track(value.trim());
      setShipment(data);
    } catch (err: any) {
      setError(err.message);
      setShipment(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const q = searchParams.get("code");
    if (q) {
      setCode(q.toUpperCase());
      loadCode(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await loadCode(code);
  }

  const currentIdx = shipment ? STEPS.indexOf(shipment.current_milestone) : -1;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title">Track shipment</h1>
        <p className="page-sub">Vessel position and milestone pipeline until your car reaches Oman.</p>
      </div>
      <form onSubmit={onSubmit} className="card flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="label" htmlFor="track-code">
            Tracking code
          </label>
          <input
            id="track-code"
            className="input"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="CP-XXXXXXXX"
          />
        </div>
        <button className="btn shrink-0" disabled={loading}>
          {loading ? "Loading…" : "Track"}
        </button>
      </form>
      {error && <p className="danger-text">{error}</p>}

      {shipment && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="card space-y-5">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">
                {shipment.year} {shipment.make} {shipment.model}
              </h2>
              <p className="mt-1 font-mono text-sm font-semibold text-teal-700">{shipment.tracking_code}</p>
            </div>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-slate-500">VIN</dt>
                <dd className="mt-0.5 font-medium">{shipment.vin || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Vessel</dt>
                <dd className="mt-0.5 font-medium">{shipment.vessel_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Origin</dt>
                <dd className="mt-0.5 font-medium">{shipment.origin_port || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">ETA</dt>
                <dd className="mt-0.5 font-medium">
                  {shipment.eta ? new Date(shipment.eta).toLocaleString() : "—"}
                </dd>
              </div>
            </dl>
            <ol className="space-y-2">
              {STEPS.map((step, idx) => (
                <li
                  key={step}
                  className={`rounded-xl border px-3 py-2.5 text-sm ${
                    idx <= currentIdx
                      ? "border-teal-200 bg-teal-50 text-teal-900"
                      : "border-slate-200 text-slate-400"
                  }`}
                >
                  {idx + 1}. {step.replaceAll("_", " ")}
                </li>
              ))}
            </ol>
          </div>
          <div className="card space-y-4">
            <h3 className="font-semibold text-slate-900">Live map</h3>
            {shipment.vessel_lat != null && shipment.vessel_lon != null ? (
              <>
                <div className="relative h-72 overflow-hidden rounded-xl border border-slate-200 bg-[radial-gradient(circle_at_center,#ccfbf188,transparent_55%),linear-gradient(#f8fafc,#e2e8f0)]">
                  <div
                    className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-600 shadow-md"
                    style={{
                      left: `${((shipment.vessel_lon + 180) / 360) * 100}%`,
                      top: `${((90 - shipment.vessel_lat) / 180) * 100}%`,
                    }}
                    title="Vessel"
                  />
                  <div
                    className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-500"
                    style={{ left: `${((56.625 + 180) / 360) * 100}%`, top: `${((90 - 24.492) / 180) * 100}%` }}
                    title="Sohar"
                  />
                  <div className="absolute bottom-2 left-2 rounded-md bg-white/90 px-2 py-1 text-xs text-slate-600">
                    Teal = vessel · Amber = Sohar
                  </div>
                </div>
                <p className="text-sm text-slate-500">
                  Position: {shipment.vessel_lat.toFixed(4)}, {shipment.vessel_lon.toFixed(4)}
                  {shipment.vessel_updated_at && ` · updated ${new Date(shipment.vessel_updated_at).toLocaleString()}`}
                </p>
              </>
            ) : (
              <p className="text-sm text-slate-500">Vessel position available once the shipment is on vessel.</p>
            )}
            {shipment.completeness && (
              <div className="surface-inset p-3 text-sm">
                <p className="font-medium text-slate-800">Document readiness</p>
                <p className={shipment.completeness.is_ready_for_customs ? "text-teal-700" : "text-amber-700"}>
                  {shipment.completeness.is_ready_for_customs ? "Ready for customs" : "Missing documents"}
                </p>
                {shipment.completeness.missing?.length > 0 && (
                  <p className="text-slate-500">Missing: {shipment.completeness.missing.join(", ")}</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function TrackPage() {
  return (
    <Suspense fallback={<div className="muted">Loading tracker…</div>}>
      <TrackInner />
    </Suspense>
  );
}
