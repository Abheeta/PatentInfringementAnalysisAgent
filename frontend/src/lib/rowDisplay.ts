import { Row } from "../types";

export function toDisplayRowId(rows: Row[], rowId: number): number {
  if (rows.length === 0) return rowId;
  const minId = Math.min(...rows.map((r) => r.id));
  return rowId - minId + 1;
}
