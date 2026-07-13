"use client";

import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

type ComboboxProps = {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  disabled?: boolean;
  allowCustom?: boolean;
  className?: string;
  name?: string;
  required?: boolean;
};

export function Combobox({
  value,
  onChange,
  options,
  placeholder = "Type or select…",
  disabled,
  allowCustom = true,
  className = "",
  name,
  required,
}: ComboboxProps) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const filtered = useMemo(() => {
    const q = value.trim().toLowerCase();
    if (!q) return options;
    const starts = options.filter((o) => o.toLowerCase().startsWith(q));
    const contains = options.filter(
      (o) => !o.toLowerCase().startsWith(q) && o.toLowerCase().includes(q),
    );
    return [...starts, ...contains];
  }, [options, value]);

  useEffect(() => {
    setHighlight(0);
  }, [filtered, open]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(opt: string) {
    onChange(opt);
    setOpen(false);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, Math.max(filtered.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && open && filtered[highlight]) {
      e.preventDefault();
      pick(filtered[highlight]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <input
        className="input pr-9"
        name={name}
        value={value}
        disabled={disabled}
        required={required}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
      />
      <button
        type="button"
        tabIndex={-1}
        disabled={disabled}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
        aria-label="Toggle options"
        onClick={() => setOpen((o) => !o)}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-40 mt-1.5 max-h-56 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg shadow-slate-200/80"
        >
          {filtered.length === 0 && (
            <li className="px-3 py-2.5 text-sm text-slate-500">
              {allowCustom ? "No matches — keep typing to use a custom value" : "No matches"}
            </li>
          )}
          {filtered.map((opt, i) => (
            <li key={opt}>
              <button
                type="button"
                role="option"
                aria-selected={value === opt}
                className={`block w-full px-3 py-2 text-left text-sm ${
                  i === highlight ? "bg-blue-50 text-blue-900" : "text-slate-700 hover:bg-slate-50"
                }`}
                onMouseEnter={() => setHighlight(i)}
                onClick={() => pick(opt)}
              >
                {opt}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
