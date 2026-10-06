import { HistogramSeries } from "https://unpkg.com/lightweight-charts@5.2.1/dist/lightweight-charts.production.mjs";

export function alignedSeries(rows, values) {
  return rows.map((row, index) => values[index] == null ? null : { time: row.time, value: values[index] }).filter(Boolean);
}

export function renderIndicator(chart, registry, id, rows, lineFactory) {
  if (id === "none" || !rows.length) return [];
  const definition = registry[id];
  if (!definition) return [];
  const result = definition.calculate(rows);
  const created = [];
  if (definition.multi) {
    created.push(lineFactory(alignedSeries(rows, result.line), 1, { title: "MACD" }));
    created.push(lineFactory(alignedSeries(rows, result.signal), 1, { title: "Signal" }));
    const histogram = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false, base: 0 }, 1);
    histogram.setData(alignedSeries(rows, result.histogram));
    created.push(histogram);
    return created;
  }
  created.push(lineFactory(alignedSeries(rows, result), definition.kind === "oscillator" ? 1 : 0, { title: definition.name, ...(definition.min != null ? { autoscaleInfoProvider: () => ({ priceRange: { minValue: definition.min, maxValue: definition.max } }) } : {}) }));
  return created;
}
