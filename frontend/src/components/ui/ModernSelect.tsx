"use client";

import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type SelectOption = { value: string; label: string };

export function ModernSelect({
  name,
  options,
  value,
  defaultValue = "",
  onValueChange,
  placeholder = "Choose an option",
  disabled = false,
  required = false
}: {
  name?: string;
  options: SelectOption[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
}) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const currentValue = value ?? internalValue;
  const selected = options.find((option) => option.value === currentValue);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const form = rootRef.current?.closest("form");
    const reset = () => {
      if (value === undefined) setInternalValue(defaultValue);
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    form?.addEventListener("reset", reset);
    return () => {
      document.removeEventListener("mousedown", close);
      form?.removeEventListener("reset", reset);
    };
  }, [defaultValue, value]);

  function choose(nextValue: string) {
    if (value === undefined) setInternalValue(nextValue);
    onValueChange?.(nextValue);
    setOpen(false);
  }

  return (
    <div className={`modern-select ${open ? "open" : ""} ${disabled ? "disabled" : ""}`} ref={rootRef}>
      {name && <select className="modern-native-proxy" name={name} value={currentValue} onChange={() => undefined} required={required} disabled={disabled} tabIndex={-1} aria-hidden="true">{!options.some((option) => option.value === "") && <option value="" />}{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select>}
      <button type="button" className="modern-control" onClick={() => !disabled && setOpen((current) => !current)} disabled={disabled} aria-expanded={open} aria-haspopup="listbox" aria-required={required}>
        <span className={selected ? "" : "placeholder"}>{selected?.label || placeholder}</span>
        <ChevronDown size={19} />
      </button>
      {open && (
        <div className="modern-options" role="listbox">
          {options.map((option) => (
            <button type="button" role="option" aria-selected={option.value === currentValue} className={option.value === currentValue ? "selected" : ""} key={option.value} onClick={() => choose(option.value)}>
              <span>{option.label}</span>
              {option.value === currentValue && <Check size={19} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
