export function latestPoint(rows, values) {
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] != null && rows[i]) return { time: rows[i].time, value: values[i] };
  }
  return null;
}

export function mergeCandles(existing, incoming, limit = 300) {
  const byTime = new Map();
  for (const candle of [...existing, ...incoming]) {
    if (!candle || !Number.isFinite(Number(candle.time))) continue;
    byTime.set(Number(candle.time), candle);
  }
  return [...byTime.entries()].sort((a,b)=>a[0]-b[0]).slice(-limit).map(([,candle])=>candle);
}