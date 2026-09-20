'use client';

/**
 * 图表解读提示：每个图表下方一行"怎么看"的人话解读（简洁）。
 * 用法：<Hint text="柱子越长 = 有氧能力越强" />
 */
export default function Hint({ text }) {
  if (!text) return null;
  return (
    <div className="chart-hint">
      <span className="chart-hint-tag">解读</span>
      <span>{text}</span>
    </div>
  );
}
