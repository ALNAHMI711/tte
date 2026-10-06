import test from "node:test";
import assert from "node:assert/strict";
import { sma, ema, rma, rsi, vwap, atr, macd, adx, stochastic, roc } from "../frontend/indicators.js";

const candles = Array.from({length:40},(_,i)=>({time:i+1,open:i+10,high:i+12,low:i+9,close:i+11,volume:100+i}));
const closes = candles.map(c=>c.close);

test("SMA preserves warmup alignment and calculates period average",()=>{
  const x=sma([1,2,3,4],3); assert.deepEqual(x,[null,null,2,3]);
});
test("EMA preserves length and warmup",()=>{
  const x=ema([1,2,3,4,5],3); assert.equal(x.length,5); assert.equal(x[0],null); assert.equal(x[1],null); assert.equal(x[2],2);
});
test("RMA uses Wilder smoothing and preserves warmup alignment",()=>{
  const x=rma([1,2,3,4,5],3);
  assert.deepEqual(x.slice(0,2),[null,null]);
  assert.equal(x[2],2);
  assert.equal(x[3],(2*2+4)/3);
});

test("RSI stays within 0..100 after warmup",()=>{
  const x=rsi(closes,14); assert.equal(x.length,closes.length); assert.ok(x.slice(14).every(v=>v>=0&&v<=100));
});
test("VWAP preserves candle alignment",()=>{
  const x=vwap(candles); assert.equal(x.length,candles.length); assert.ok(x.every(v=>v!==null&&Number.isFinite(v)));
});
test("ATR uses Wilder warmup and remains nonnegative",()=>{
  const x=atr(candles,14);
  assert.equal(x.length,candles.length);
  assert.equal(x.slice(0,13).every(v=>v===null),true);
  assert.ok(x.slice(13).every(v=>v>=0));
});
test("MACD returns aligned line, signal and histogram",()=>{
  const x=macd(closes,12,26,9); assert.equal(x.line.length,closes.length); assert.equal(x.signal.length,closes.length); assert.equal(x.histogram.length,closes.length);
});
test("ADX uses Wilder warmup and stays bounded",()=>{
  const x=adx(candles,14);
  assert.equal(x.length,candles.length);
  assert.equal(x.slice(0,26).every(v=>v===null),true);
  assert.ok(x.slice(27).every(v=>v===null || (v>=0&&v<=100)));
});
test("Stochastic is aligned and bounded",()=>{
  const x=stochastic(candles,14,3); assert.equal(x.length,candles.length); assert.ok(x.slice(16).every(v=>v===null||(v>=0&&v<=100)));
});
test("ROC preserves alignment",()=>{
  const x=roc(closes,12); assert.equal(x.length,closes.length); assert.equal(x.slice(0,12).every(v=>v===null),true);
});


import { latestPoint } from "../frontend/indicator-data.js";

test("latestPoint skips warmup nulls and preserves candle time",()=>{
  assert.deepEqual(latestPoint([{time:1},{time:2},{time:3}], [null, 4, null]), {time:2,value:4});
  assert.equal(latestPoint([{time:1}], [null]), null);
});


test("mergeCandles deduplicates, replaces, sorts, and caps", async () => {
  const { mergeCandles } = await import("../frontend/indicator-data.js");
  const existing = [{time:3,close:30},{time:1,close:10},{time:2,close:20}];
  const incoming = [{time:2,close:25},{time:4,close:40},{time:5,close:50}];
  assert.deepEqual(mergeCandles(existing,incoming,4), [
    {time:2,close:25},{time:3,close:30},{time:4,close:40},{time:5,close:50}
  ]);
});


test("mergeCandle sorts late candles and identifies the latest point", async () => {
  const { mergeCandle } = await import("../frontend/indicator-data.js");
  const a = mergeCandle([{time:1},{time:3}], {time:2}, 300);
  assert.deepEqual(a.rows.map(x=>x.time), [1,2,3]);
  assert.equal(a.isLatest, false);
  const b = mergeCandle(a.rows, {time:4}, 300);
  assert.deepEqual(b.rows.map(x=>x.time), [1,2,3,4]);
  assert.equal(b.isLatest, true);
});


test("indicator warmup points are null until mathematically valid",()=>{
  const m=macd(closes,12,26,9);
  assert.equal(m.line.slice(0,25).every(v=>v===null),true);
  assert.equal(m.signal.slice(0,33).every(v=>v===null),true);
  assert.equal(m.histogram.slice(0,33).every(v=>v===null),true);
  const s=stochastic(candles,14,3);
  assert.equal(s.slice(0,15).every(v=>v===null),true);
  const a=atr(candles,14);
  assert.equal(a.slice(0,13).every(v=>v===null),true);
});

test("calculated indicator values remain finite after warmup",()=>{
  for (const value of [
    ...ema(closes,20).slice(19),
    ...rma(closes,14).slice(13),
    ...rsi(closes,14).slice(14),
    ...vwap(candles),
    ...atr(candles,14).slice(13),
    ...macd(closes).line.slice(25),
    ...adx(candles,14).slice(26),
    ...stochastic(candles,14,3).slice(16),
    ...roc(closes,12).slice(12),
  ]) assert.ok(value === null || Number.isFinite(value));
});


test("indicator registry exposes every catalog entry with aligned output", async () => {
  const { INDICATOR_REGISTRY, INDICATOR_LIST } = await import("../frontend/indicator-registry.js");
  assert.equal(INDICATOR_LIST.length, 12);
  for (const definition of INDICATOR_LIST) {
    assert.equal(INDICATOR_REGISTRY[definition.id], definition);
    const result = definition.calculate(candles);
    if (definition.multi) {
      assert.equal(result.line.length, candles.length);
      assert.equal(result.signal.length, candles.length);
      assert.equal(result.histogram.length, candles.length);
    } else {
      assert.equal(result.length, candles.length);
    }
  }
});


test("drawing restore filters invalid entries and normalizes numeric coordinates", async () => {
  const { DrawingManager } = await import("../frontend/drawings.js");
  assert.ok(typeof DrawingManager === "function");
  const manager = Object.create(DrawingManager.prototype);
  manager.items = [];
  manager.drag = null;
  manager.render = () => {};
  manager.restore([
    { type: "trend", p1: { logical: "1", price: "10.5" }, p2: { logical: 2, price: 11 } },
    { type: "hack", p1: { logical: 1, price: 1 }, p2: { logical: 2, price: 2 } },
    { type: "box", p1: { logical: "bad", price: 1 }, p2: { logical: 2, price: 2 } },
    null,
  ]);
  assert.deepEqual(manager.items, [
    { type: "trend", p1: { logical: 1, price: 10.5 }, p2: { logical: 2, price: 11 } },
  ]);
  assert.equal(manager.drag, null);
});
