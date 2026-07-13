"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Combobox } from "@/components/Combobox";
import { api } from "@/lib/api";
import { CAR_MAKES, modelsForMake, yearOptions } from "@/lib/cars";

const DOC_TYPES = [
  "bill_of_lading",
  "auction_invoice",
  "certificate_of_origin",
  "insurance",
  "customs_declaration",
  "export_yard_photo",
  "other",
];

const MILESTONES = ["purchased", "export_yard", "on_vessel", "arrived_port", "customs", "released", "delivered"];
const YEARS = yearOptions();

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    make: "Toyota",
    model: "Camry",
    year: "2019",
    vin: "4T1B11HK5KU123456",
    vessel_name: "HOEGH TARGET",
    origin_port: "Houston",
    bill_of_lading: "BL-OM-99821",
  });
  const [docType, setDocType] = useState("bill_of_lading");
  const [verifyResult, setVerifyResult] = useState<any>(null);

  const modelOptions = useMemo(() => modelsForMake(form.make), [form.make]);

  async function load() {
    try {
      const rows = await api.myShipments();
      setShipments(rows);
    } catch (err: any) {
      setError(err.message + " — please login as buyer.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createShipment(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const created = await api.createShipment({
        ...form,
        year: Number(form.year),
      });
      await load();
      setSelected(created);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function onUpload(file: File | null) {
    if (!file || !selected) return;
    try {
      await api.uploadDocument(selected.id, file, docType);
      const refreshed = await api.getShipment(selected.id);
      setSelected(refreshed);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function bumpMilestone(milestone: string) {
    if (!selected) return;
    const updated = await api.updateMilestone(selected.id, { milestone, status_note: `Moved to ${milestone}` });
    setSelected(updated);
    await load();
  }

  async function runPhotoVerify() {
    if (!selected) return;
    const result = await api.verifyPhotos(selected.id, ["https://example.com/camry1.jpg"]);
    setVerifyResult(result);
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title">My imports</h1>
        <p className="page-sub">Create a shipment, upload docs, and follow milestones.</p>
      </div>
      {error && <p className="danger-text text-sm">{error}</p>}

      <form onSubmit={createShipment} className="card grid gap-4 md:grid-cols-3">
        <div>
          <label className="label">Make</label>
          <Combobox
            value={form.make}
            onChange={(make) => {
              const models = modelsForMake(make);
              setForm({
                ...form,
                make,
                model: models.some((m) => m.toLowerCase() === form.model.toLowerCase()) ? form.model : "",
              });
            }}
            options={CAR_MAKES}
            placeholder="Type or select make"
          />
        </div>
        <div>
          <label className="label">Model</label>
          <Combobox
            value={form.model}
            onChange={(model) => setForm({ ...form, model })}
            options={modelOptions}
            placeholder="Type or select model"
            disabled={!form.make.trim()}
          />
        </div>
        <div>
          <label className="label">Year</label>
          <Combobox
            value={form.year}
            onChange={(year) => setForm({ ...form, year })}
            options={YEARS}
            placeholder="Type or select year"
          />
        </div>
        {(
          [
            ["vin", "VIN"],
            ["vessel_name", "Vessel name"],
            ["origin_port", "Origin port"],
            ["bill_of_lading", "Bill of lading"],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <label className="label">{label}</label>
            <input
              className="input"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </div>
        ))}
        <div className="md:col-span-3">
          <button className="btn">Create shipment</button>
        </div>
      </form>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          {shipments.map((s) => (
            <button
              key={s.id}
              onClick={async () => setSelected(await api.getShipment(s.id))}
              className={`card w-full text-left transition ${selected?.id === s.id ? "border-teal-400 ring-2 ring-teal-100" : "hover:border-slate-300"}`}
            >
              <div className="font-semibold text-slate-900">
                {s.year} {s.make} {s.model}
              </div>
              <div className="font-mono text-sm font-semibold text-teal-700">{s.tracking_code}</div>
              <div className="text-sm text-slate-500">{s.current_milestone}</div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="card space-y-4">
            <h2 className="text-xl font-semibold text-slate-900">Shipment detail</h2>
            <p className="font-mono font-semibold text-teal-700">{selected.tracking_code}</p>
            <div className="flex flex-wrap gap-2">
              {MILESTONES.map((m) => (
                <button key={m} className="btn-secondary text-xs" onClick={() => bumpMilestone(m)}>
                  {m.replaceAll("_", " ")}
                </button>
              ))}
            </div>
            <div>
              <label className="label">Upload document</label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <input type="file" onChange={(e) => onUpload(e.target.files?.[0] || null)} />
              </div>
            </div>
            <div className="space-y-2 text-sm">
              {(selected.documents || []).map((d: any) => (
                <div key={d.id} className="surface-inset p-2">
                  <div className="font-medium text-slate-800">
                    {d.doc_type} — {d.filename}
                  </div>
                  {d.warnings?.length > 0 && <div className="text-amber-700">{d.warnings.join("; ")}</div>}
                </div>
              ))}
            </div>
            {selected.completeness && (
              <div className="surface-inset p-3 text-sm">
                <p>Missing: {selected.completeness.missing.join(", ") || "none"}</p>
                <p className={selected.completeness.is_ready_for_customs ? "text-teal-700" : "text-amber-700"}>
                  {selected.completeness.is_ready_for_customs ? "Customs-ready" : "Not ready"}
                </p>
              </div>
            )}
            <button className="btn-secondary" onClick={runPhotoVerify}>
              Verify export-yard photos
            </button>
            {verifyResult && (
              <pre className="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                {JSON.stringify(verifyResult, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
