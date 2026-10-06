export function latestPoint(rows, values) {
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] != null && rows[i]) return { time: rows[i].time, value: values[i] };
  }
  return null;
}
