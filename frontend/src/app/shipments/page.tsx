"use client";

import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Combobox } from "@/components/Combobox";
import { api } from "@/lib/api";
import { CAR_MAKES, modelsForMake, yearOptions } from "@/lib/cars";
import { formatMoney } from "@/lib/format";

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

function ShipmentsInner() {
  const searchParams = useSearchParams();
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
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerCars, setPickerCars] = useState<any[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [pickerError, setPickerError] = useState("");
  const [pickedCar, setPickedCar] = useState<any>(null);

  const modelOptions = useMemo(() => modelsForMake(form.make), [form.make]);

  // Prefill car details when arriving from Search / listing pages.
  // Prefers listing_id (fetches the full record so VIN etc. come through),
  // falls back to plain query params.
  useEffect(() => {
    const listingId = searchParams.get("listing_id");
    const make = searchParams.get("make");
    const model = searchParams.get("model");
    const year = searchParams.get("year");
    const vin = searchParams.get("vin");
    const origin = searchParams.get("origin_port");
    if (!listingId && !make && !model && !year && !vin) return;

    const applyParams = () =>
      setForm((f) => ({
        ...f,
        make: make || f.make,
        model: model || f.model,
        year: year || f.year,
        vin: vin || "",
        origin_port: origin || f.origin_port,
      }));

    if (listingId) {
      api
        .getListing(Number(listingId))
        .then((item) => {
          setForm((f) => ({
            ...f,
            make: item.make || make || f.make,
            model: item.model || model || f.model,
            year: item.year ? String(item.year) : year || f.year,
            vin: item.vin || vin || "",
            origin_port: item.location || item.country || origin || f.origin_port,
          }));
          setPickedCar(item);
        })
        .catch(applyParams);
    } else {
      applyParams();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function openPicker() {
    setPickerOpen(true);
    if (pickerCars.length) return;
    setPickerLoading(true);
    setPickerError("");
    try {
      const res = await api.searchListings({ live: false, page: 1, page_size: 30 });
      setPickerCars(res.items || []);
      if (!res.items?.length) setPickerError("No saved cars yet — run a Search first, then come back.");
    } catch (err: any) {
      setPickerError(err.message || "Failed to load cars");
    } finally {
      setPickerLoading(false);
    }
  }

  function pickCar(item: any) {
    setForm((f) => ({
      ...f,
      make: item.make || "",
      model: item.model || "",
      year: item.year ? String(item.year) : f.year,
      vin: item.vin || "",
      origin_port: item.location || item.country || f.origin_port,
    }));
    setPickedCar(item);
    setPickerOpen(false);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">My imports</h1>
          <p className="page-sub">Create a shipment, upload docs, and follow milestones.</p>
        </div>
        <button type="button" className="btn" onClick={openPicker}>
          Choose a car to import
        </button>
      </div>
      {error && <p className="danger-text text-sm">{error}</p>}

      {pickerOpen && (
        <section className="card space-y-4 border-blue-300 ring-2 ring-blue-100">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Pick a car</h2>
              <p className="text-sm text-slate-500">Cars from your recent searches — pick one to prefill the import form.</p>
            </div>
            <button type="button" className="btn-secondary !py-1.5 !text-xs" onClick={() => setPickerOpen(false)}>
              Close
            </button>
          </div>
          {pickerLoading && <p className="muted text-sm">Loading cars…</p>}
          {pickerError && <p className="danger-text text-sm">{pickerError}</p>}
          <div className="grid max-h-96 gap-3 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
            {pickerCars.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => pickCar(item)}
                className="card w-full text-left transition hover:border-blue-400 hover:ring-2 hover:ring-blue-100"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-slate-900">
                    {item.year || ""} {item.make} {item.model}
                  </span>
                  <span className="badge-muted shrink-0">{item.source}</span>
                </div>
                <div className="mt-1 text-sm text-slate-500">
                  {formatMoney(item.price, item.currency)} · {item.location || item.country || "—"}
                </div>
                {item.vin && <div className="mt-1 font-mono text-xs text-slate-400">VIN {item.vin}</div>}
              </button>
            ))}
          </div>
        </section>
      )}

      {pickedCar && (
        <p className="text-sm font-medium text-blue-700">
          Importing: {pickedCar.year} {pickedCar.make} {pickedCar.model} — details filled in below. Review and create the
          shipment.
        </p>
      )}

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
              className={`card w-full text-left transition ${selected?.id === s.id ? "border-blue-400 ring-2 ring-blue-100" : "hover:border-slate-300"}`}
            >
              <div className="font-semibold text-slate-900">
                {s.year} {s.make} {s.model}
              </div>
              <div className="font-mono text-sm font-semibold text-blue-700">{s.tracking_code}</div>
              <div className="text-sm text-slate-500">{s.current_milestone}</div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="card space-y-4">
            <h2 className="text-xl font-semibold text-slate-900">Shipment detail</h2>
            <p className="font-mono font-semibold text-blue-700">{selected.tracking_code}</p>
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
                <p className={selected.completeness.is_ready_for_customs ? "text-blue-700" : "text-amber-700"}>
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

export default function ShipmentsPage() {
  return (
    <Suspense fallback={<div className="muted">Loading imports…</div>}>
      <ShipmentsInner />
    </Suspense>
  );
}
