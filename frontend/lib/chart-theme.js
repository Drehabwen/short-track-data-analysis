/**
 * “冰面实验记录”科研图表系统。
 * 颜色按语义排序：主序列、恢复、对照、提醒、扩展系列。
 */
export const RESEARCH_PALETTE = [
  '#167D9A',
  '#2B6CB0',
  '#2F8F83',
  '#E07A32',
  '#7566A8',
  '#5B7C8D',
  '#B84A62',
  '#85A33D',
];

export const RESEARCH_THEME = {
  color: RESEARCH_PALETTE,
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily: "'SF Pro Text', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    color: '#334A5E',
    fontSize: 12,
  },
  title: {
    textStyle: { color: '#102A43', fontWeight: 650, fontSize: 15 },
    subtextStyle: { color: '#71879A', fontSize: 11, lineHeight: 17 },
  },
  legend: {
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 18,
    icon: 'circle',
    textStyle: { color: '#52697B', fontSize: 11 },
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: '#B9C8D3' } },
    axisTick: { show: false },
    axisLabel: { color: '#607789', margin: 12 },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#71879A', margin: 10 },
    splitLine: { lineStyle: { color: '#DCE6EC', type: [3, 4] } },
    nameTextStyle: { color: '#607789', padding: [0, 0, 6, 0] },
  },
  line: {
    symbol: 'circle',
    symbolSize: 7,
    showSymbol: true,
    smooth: 0.18,
    lineStyle: { width: 2.4 },
    itemStyle: { borderWidth: 2, borderColor: '#F8FBFC' },
    emphasis: { focus: 'series', lineStyle: { width: 3.2 } },
  },
  bar: {
    barMaxWidth: 34,
    itemStyle: { borderRadius: [5, 5, 1, 1] },
    emphasis: { focus: 'series' },
  },
  scatter: {
    symbolSize: 9,
    itemStyle: { opacity: 0.82, borderColor: '#F8FBFC', borderWidth: 1.5 },
    emphasis: { scale: 1.35, focus: 'series' },
  },
  boxplot: {
    itemStyle: { color: '#DCEFF4', borderColor: '#167D9A', borderWidth: 1.5 },
  },
  tooltip: {
    backgroundColor: 'rgba(15, 38, 57, 0.96)',
    borderColor: 'rgba(255, 255, 255, 0.12)',
    borderWidth: 1,
    textStyle: { color: '#F5FAFC', fontSize: 12, lineHeight: 20 },
    padding: [10, 13],
    extraCssText:
      'border-radius:8px;box-shadow:0 12px 32px rgba(11,31,46,.22);backdrop-filter:blur(10px);',
  },
  dataZoom: {
    borderColor: 'transparent',
    backgroundColor: '#EDF3F6',
    fillerColor: 'rgba(22,125,154,.16)',
    handleStyle: { color: '#167D9A', borderColor: '#167D9A' },
    textStyle: { color: '#607789' },
  },
};

export const BASE_RESEARCH_OPTION = {
  animationDuration: 520,
  animationDurationUpdate: 320,
  animationEasing: 'cubicOut',
  animationEasingUpdate: 'cubicOut',
  aria: {
    enabled: true,
    decal: { show: false },
  },
};
