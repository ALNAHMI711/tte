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
