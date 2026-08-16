export function pointsHud(points: number): string {
  return `<div class="ns-hud">Session points: <strong>${points}</strong></div>`;
}

export function renderHtml(value: unknown): string {
  if (typeof value === "function") {
    return String((value as () => unknown)() ?? "");
  }
  return String(value ?? "");
}
