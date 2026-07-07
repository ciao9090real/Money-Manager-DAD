"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { formatDateValue, parseDateValue } from "../../lib/formatting";

export function ModernDateInput({
  name,
  value,
  defaultValue = "",
  onValueChange,
  required = false,
  placeholder = "Choose a date"
}: {
  name: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  required?: boolean;
  placeholder?: string;
}) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const currentValue = value ?? internalValue;
  const selectedDate = currentValue ? parseDateValue(currentValue) : null;
  const [visibleMonth, setVisibleMonth] = useState(() => selectedDate || new Date());

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

  function selectDate(date: Date) {
    const nextValue = formatDateValue(date);
    if (value === undefined) setInternalValue(nextValue);
    onValueChange?.(nextValue);
    setVisibleMonth(date);
    setOpen(false);
  }

  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const firstCell = new Date(year, month, 1 - new Date(year, month, 1).getDay());
  const days = Array.from({ length: 42 }, (_, index) => new Date(firstCell.getFullYear(), firstCell.getMonth(), firstCell.getDate() + index));

  return (
    <div className={`modern-date ${open ? "open" : ""}`} ref={rootRef}>
      <input className="modern-native-proxy" name={name} value={currentValue} onChange={() => undefined} required={required} tabIndex={-1} aria-hidden="true" />
      <button type="button" className="modern-control" onClick={() => { setVisibleMonth(selectedDate || new Date()); setOpen((current) => !current); }} aria-expanded={open} aria-haspopup="dialog" aria-required={required}>
        <span className={selectedDate ? "" : "placeholder"}>{selectedDate ? selectedDate.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : placeholder}</span>
        <CalendarDays size={19} />
      </button>
      {open && (
        <div className="calendar-popover" role="dialog" aria-label="Choose a date">
          <div className="calendar-heading">
            <strong>{visibleMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong>
            <span>
              <button type="button" onClick={() => setVisibleMonth(new Date(year, month - 1, 1))} aria-label="Previous month"><ChevronLeft size={21} /></button>
              <button type="button" onClick={() => setVisibleMonth(new Date(year, month + 1, 1))} aria-label="Next month"><ChevronRight size={21} /></button>
            </span>
          </div>
          <div className="calendar-weekdays">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-days">
            {days.map((day) => {
              const dayValue = formatDateValue(day);
              const isSelected = dayValue === currentValue;
              const isToday = dayValue === formatDateValue(new Date());
              return <button type="button" key={dayValue} className={`${day.getMonth() !== month ? "outside" : ""} ${isSelected ? "selected" : ""} ${isToday ? "today" : ""}`} onClick={() => selectDate(day)}>{day.getDate()}</button>;
            })}
          </div>
          <button type="button" className="calendar-today" onClick={() => selectDate(new Date())}>Today</button>
        </div>
      )}
    </div>
  );
}
