'use client';

import { useState } from 'react';

/**
 * 指标解读指南：可折叠面板，展示每个指标的计算逻辑与解读方向。
 * 用法：<Guide rows={[{ name, calc, read, dir, color? }]} title="指标解读指南" />
 */
export default function Guide({ rows = [], title = '指标解读指南' }) {
  const [open, setOpen] = useState(false);
  if (!rows.length) return null;
  return (
    <div className={`guide ${open ? 'open' : ''}`}>
      <button className="guide-toggle" onClick={() => setOpen(!open)}>
        {open ? '▾' : '▸'} {title}（{rows.length} 项 · 计算逻辑与解读）
      </button>
      {open && (
        <div className="guide-body">
          <table className="data-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>计算逻辑</th>
                <th>解读方向</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                    {r.name}
                    {r.color && <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: r.color, marginLeft: 6 }} />}
                  </td>
                  <td>{r.calc}</td>
                  <td>{r.read}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
