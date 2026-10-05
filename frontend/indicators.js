export function sma(values, period) {
  if (period < 1) throw new RangeError("period must be positive");
  const out = Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

export function ema(values, period) {
  if (period < 1) throw new RangeError("period must be positive");
  const out = Array(values.length).fill(null);
  if (values.length < period) return out;
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  let previous = seed / period;
  out[period - 1] = previous;
  const alpha = 2 / (period + 1);
  for (let i = period; i < values.length; i++) {
    previous += (values[i] - previous) * alpha;
    out[i] = previous;
  }
  return out;
}

export function rma(values, period) {
  if (period < 1) throw new RangeError("period must be positive");
  const out = Array(values.length).fill(null);
  if (values.length < period) return out;
  let previous = 0;
  for (let i = 0; i < period; i++) previous += values[i];
  previous /= period;
  out[period - 1] = previous;
  for (let i = period; i < values.length; i++) {
    previous = ((previous * (period - 1)) + values[i]) / period;
    out[i] = previous;
  }
  return out;
}

export function rsi(values, period = 14) {
  if (period < 1) throw new RangeError("period must be positive");
  const out = Array(values.length).fill(null);
  if (values.length <= period) return out;
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const change = values[i] - values[i - 1];
    if (change >= 0) gains += change; else losses -= change;
  }
  let avgGain = gains / period, avgLoss = losses / period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    avgGain = ((avgGain * (period - 1)) + Math.max(change, 0)) / period;
    avgLoss = ((avgLoss * (period - 1)) + Math.max(-change, 0)) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

export function vwap(candles) {
  const out = Array(candles.length).fill(null);
  let cumulativePV = 0, cumulativeVolume = 0;
  for (let i = 0; i < candles.length; i++) {
    const typical = (candles[i].high + candles[i].low + candles[i].close) / 3;
    cumulativePV += typical * candles[i].volume;
    cumulativeVolume += candles[i].volume;
    out[i] = cumulativeVolume > 0 ? cumulativePV / cumulativeVolume : null;
  }
  return out;
}

function trueRanges(candles) {
  return candles.map((c, i) => i === 0
    ? c.high - c.low
    : Math.max(c.high - c.low, Math.abs(c.high - candles[i - 1].close), Math.abs(c.low - candles[i - 1].close)));
}

export function atr(candles, period = 14) {
  if (period < 1) throw new RangeError("period must be positive");
  return rma(trueRanges(candles), period);
}

export function macd(values, fast = 12, slow = 26, signal = 9) {
  if (fast < 1 || slow < 1 || signal < 1) throw new RangeError("periods must be positive");
  const fastEma = ema(values, fast), slowEma = ema(values, slow);
  const line = values.map((_, i) => fastEma[i] !== null && slowEma[i] !== null ? fastEma[i] - slowEma[i] : null);
  const compact = line.filter(v => v !== null);
  const signalCompact = ema(compact, signal);
  const signalLine = Array(values.length).fill(null);
  let j = 0;
  for (let i = 0; i < line.length; i++) if (line[i] !== null) signalLine[i] = signalCompact[j++];
  return { line, signal: signalLine, histogram: line.map((v, i) => v === null || signalLine[i] === null ? null : v - signalLine[i]) };
}

export function adx(candles, period = 14) {
  if (period < 1) throw new RangeError("period must be positive");
  const tr = trueRanges(candles);
  const plusDm = Array(candles.length).fill(0);
  const minusDm = Array(candles.length).fill(0);

  for (let i = 1; i < candles.length; i++) {
    const up = candles[i].high - candles[i - 1].high;
    const down = candles[i - 1].low - candles[i].low;
    if (up > down && up > 0) plusDm[i] = up;
    else if (down > up && down > 0) minusDm[i] = down;
  }

  const smoothedTr = rma(tr, period);
  const smoothedPlus = rma(plusDm, period);
  const smoothedMinus = rma(minusDm, period);
  const dx = Array(candles.length).fill(null);

  for (let i = period - 1; i < candles.length; i++) {
    if (smoothedTr[i] === null || smoothedTr[i] === 0) continue;
    const plusDi = 100 * smoothedPlus[i] / smoothedTr[i];
    const minusDi = 100 * smoothedMinus[i] / smoothedTr[i];
    const sum = plusDi + minusDi;
    dx[i] = sum === 0 ? 0 : 100 * Math.abs(plusDi - minusDi) / sum;
  }

  const validDx = dx.slice(period - 1).filter(v => v !== null);
  const adxValues = rma(validDx, period);
  const out = Array(candles.length).fill(null);
  let j = 0;
  for (let i = period - 1; i < candles.length; i++) {
    if (dx[i] !== null) out[i] = adxValues[j++];
  }
  return out;
}

export function stochastic(candles, period = 14, smooth = 3) {
  if (period < 1 || smooth < 1) throw new RangeError("periods must be positive");
  const raw = Array(candles.length).fill(null);
  for (let i = period - 1; i < candles.length; i++) {
    let hi = -Infinity, lo = Infinity;
    for (let j = i - period + 1; j <= i; j++) {
      hi = Math.max(hi, candles[j].high);
      lo = Math.min(lo, candles[j].low);
    }
    raw[i] = hi === lo ? 0 : 100 * (candles[i].close - lo) / (hi - lo);
  }
  const valid = raw.filter(v => v !== null);
  const smoothed = sma(valid, smooth);
  const out = Array(candles.length).fill(null);
  let j = 0;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] !== null) out[i] = smoothed[j++];
  }
  return out;
}

export function roc(values, period = 12) {
  if (period < 1) throw new RangeError("period must be positive");
  const out = Array(values.length).fill(null);
  for (let i = period; i < values.length; i++) {
    out[i] = values[i - period] === 0 ? null : 100 * (values[i] - values[i - period]) / values[i - period];
  }
  return out;
}

export const INDICATOR_CATALOG = Object.freeze([
  { id: "sma20", name: "SMA 20", kind: "overlay" },
  { id: "ema20", name: "EMA 20", kind: "overlay" },
  { id: "ema50", name: "EMA 50", kind: "overlay" },
  { id: "ema100", name: "EMA 100", kind: "overlay" },
  { id: "ema200", name: "EMA 200", kind: "overlay" },
  { id: "vwap", name: "VWAP", kind: "overlay" },
  { id: "rsi14", name: "RSI 14", kind: "oscillator" },
  { id: "atr14", name: "ATR 14", kind: "oscillator" },
  { id: "macd", name: "MACD 12/26/9", kind: "oscillator" },
  { id: "adx14", name: "ADX 14", kind: "oscillator" },
  { id: "stochastic14", name: "Stochastic 14", kind: "oscillator" },
  { id: "roc12", name: "ROC 12", kind: "oscillator" },
]);
