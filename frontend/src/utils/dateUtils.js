export function formatToIST(dateStr) {
  if (!dateStr) return "-";
  let s = String(dateStr).trim();
  // If no timezone indicator is present, assume UTC as stored by backend
  if (!s.endsWith("Z") && !s.includes("+") && !s.slice(10).includes("-")) {
    s += "Z";
  }
  const d = new Date(s);
  if (isNaN(d.getTime())) return String(dateStr);
  return d.toLocaleString("en-US", {
    timeZone: "Asia/Kolkata",
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true
  }) + " IST";
}

export function formatToISTTime(dateStr) {
  if (!dateStr) return "";
  let s = String(dateStr).trim();
  if (!s.endsWith("Z") && !s.includes("+") && !s.slice(10).includes("-")) {
    s += "Z";
  }
  const d = new Date(s);
  if (isNaN(d.getTime())) return String(dateStr);
  return d.toLocaleTimeString("en-US", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true
  });
}

export function formatToISTDate(dateStr) {
  if (!dateStr) return "-";
  let s = String(dateStr).trim();
  if (!s.endsWith("Z") && !s.includes("+") && !s.slice(10).includes("-")) {
    s += "Z";
  }
  const d = new Date(s);
  if (isNaN(d.getTime())) return String(dateStr);
  return d.toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric"
  });
}

export function getTodayISTDateString() {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  });
  return formatter.format(now); // "YYYY-MM-DD"
}

export function formatScheduleDisplay(dateStr) {
  if (!dateStr) return null;
  let s = String(dateStr).trim();
  let d;
  if (!s.endsWith("Z") && !s.includes("+") && !s.slice(10).includes("-")) {
    const clean = s.replace(" ", "T");
    const iso = clean.length === 16 ? `${clean}:00+05:30` : `${clean}+05:30`;
    d = new Date(iso);
  } else {
    d = new Date(s);
  }
  if (isNaN(d.getTime())) return { formattedDate: String(dateStr), countdown: "", isFuture: false };

  const formattedDate = d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true
  }) + " IST";

  const now = Date.now();
  const diffMs = d.getTime() - now;
  let countdown = "";
  if (diffMs > 0) {
    const mins = Math.round(diffMs / 60000);
    if (mins < 60) {
      countdown = `in ~${mins}m`;
    } else {
      const hours = Math.floor(mins / 60);
      const remMins = mins % 60;
      if (hours < 24) {
        countdown = `in ~${hours}h ${remMins > 0 ? `${remMins}m` : ""}`;
      } else {
        const days = Math.round(hours / 24);
        countdown = `in ~${days}d`;
      }
    }
  } else {
    countdown = "Triggering shortly";
  }

  return { formattedDate, countdown, isFuture: diffMs > 0 };
}
