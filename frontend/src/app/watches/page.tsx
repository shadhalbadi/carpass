"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Combobox } from "@/components/Combobox";
import { api } from "@/lib/api";
import { CAR_MAKES, modelsForMake, yearOptions } from "@/lib/cars";
import { formatOmr } from "@/lib/format";

const YEARS = yearOptions();

export default function WatchesPage() {
  const [watches, setWatches] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "Camry under 7k landed",
    make: "Toyota",
    model: "Camry",
    year_min: "2018",
    max_landed_omr: "7000",
  });

  const modelOptions = useMemo(() => modelsForMake(form.make), [form.make]);

  async function load() {
    try {
      setWatches(await api.listWatches());
      setNotifications(await api.notifications());
    } catch (err: any) {
      setError(err.message + " — login required.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createWatch({
        name: form.name,
        make: form.make,
        model: form.model,
        year_min: Number(form.year_min) || undefined,
        max_landed_omr: Number(String(form.max_landed_omr).replace(/,/g, "")) || undefined,
        sources: [],
      });
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title">Watch alerts</h1>
        <p className="page-sub">Get notified when matching cars appear under your landed-cost target.</p>
      </div>
      {error && <p className="danger-text text-sm">{error}</p>}
      <form onSubmit={onSubmit} className="card grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="label">Name</label>
          <input
            className="input"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </div>
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
          <label className="label">Year min</label>
          <Combobox
            value={form.year_min}
            onChange={(year_min) => setForm({ ...form, year_min })}
            options={YEARS}
            placeholder="Type or select year"
          />
        </div>
        <div>
          <label className="label">Max landed OMR</label>
          <input
            className="input"
            value={form.max_landed_omr}
            onChange={(e) => setForm({ ...form, max_landed_omr: e.target.value })}
            placeholder="e.g. 7,000"
          />
        </div>
        <div className="md:col-span-2">
          <button className="btn">Save watch</button>
        </div>
      </form>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-900">Your watches</h2>
          {watches.map((w) => (
            <div key={w.id} className="surface-inset p-3 text-sm">
              <div className="font-medium text-slate-800">{w.name}</div>
              <div className="text-slate-500">
                {w.make} {w.model} · max {w.max_landed_omr != null ? formatOmr(w.max_landed_omr) : "—"} OMR
              </div>
            </div>
          ))}
        </div>
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-900">Notifications</h2>
          {notifications.map((n) => (
            <div key={n.id} className="surface-inset p-3 text-sm">
              <div className="font-medium text-slate-800">{n.title}</div>
              <div className="text-slate-500">{n.body}</div>
            </div>
          ))}
          {notifications.length === 0 && <p className="text-sm text-slate-500">No notifications yet.</p>}
        </div>
      </div>
    </div>
  );
}
