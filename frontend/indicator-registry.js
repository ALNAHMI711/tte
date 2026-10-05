import { sma, ema, rsi, vwap, atr, macd, adx, stochastic, roc } from "./indicators.js";

const close = candles => candles.map(c => c.close);
export const INDICATOR_REGISTRY = Object.freeze({
  sma20:{id:"sma20",name:"SMA 20",kind:"overlay",calculate:c=>sma(close(c),20)},
  ema20:{id:"ema20",name:"EMA 20",kind:"overlay",calculate:c=>ema(close(c),20)},
  ema50:{id:"ema50",name:"EMA 50",kind:"overlay",calculate:c=>ema(close(c),50)},
  ema100:{id:"ema100",name:"EMA 100",kind:"overlay",calculate:c=>ema(close(c),100)},
  ema200:{id:"ema200",name:"EMA 200",kind:"overlay",calculate:c=>ema(close(c),200)},
  vwap:{id:"vwap",name:"VWAP",kind:"overlay",calculate:vwap},
  rsi14:{id:"rsi14",name:"RSI 14",kind:"oscillator",min:0,max:100,calculate:c=>rsi(close(c),14)},
  atr14:{id:"atr14",name:"ATR 14",kind:"oscillator",calculate:c=>atr(c,14)},
  adx14:{id:"adx14",name:"ADX 14",kind:"oscillator",min:0,max:100,calculate:c=>adx(c,14)},
  stochastic14:{id:"stochastic14",name:"Stochastic 14",kind:"oscillator",min:0,max:100,calculate:c=>stochastic(c,14,3)},
  roc12:{id:"roc12",name:"ROC 12",kind:"oscillator",calculate:c=>roc(close(c),12)},
  macd:{id:"macd",name:"MACD 12/26/9",kind:"oscillator",multi:true,calculate:c=>macd(close(c),12,26,9)}
});
export const INDICATOR_LIST=Object.freeze(Object.values(INDICATOR_REGISTRY));
