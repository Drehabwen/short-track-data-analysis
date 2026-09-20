'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts';
import { BASE_RESEARCH_OPTION, RESEARCH_THEME } from '../lib/chart-theme';

/**
 * ECharts 封装：本地 echarts 包，不依赖任何 CDN。
 * 注册统一品牌主题，保持全站图表风格一致。
 */

if (typeof window !== 'undefined') {
  echarts.registerTheme('research', RESEARCH_THEME);
}

/**
 * 用法：<Chart option={...} height="320px" />
 */
export default function Chart({
  option,
  height = '320px',
  className = '',
  loading = false,
  empty = false,
  emptyText = '暂无可分析数据',
  ariaLabel,
}) {
  const ref = useRef(null);
  const chartRef = useRef(null);
  const resolvedOption = useMemo(() => {
    if (!option) return null;
    return echarts.util.merge(echarts.util.clone(BASE_RESEARCH_OPTION), option, true);
  }, [option]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, 'research', { renderer: 'canvas' });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (chartRef.current && resolvedOption && !empty) {
      chartRef.current.setOption(resolvedOption, true);
    }
  }, [resolvedOption, empty]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (loading) {
      chartRef.current.showLoading('default', {
        text: '正在整理数据…',
        color: '#167D9A',
        textColor: '#52697B',
        maskColor: 'rgba(248, 251, 252, 0.78)',
      });
    } else {
      chartRef.current.hideLoading();
    }
  }, [loading]);

  const label =
    ariaLabel || option?.title?.text || option?.series?.[0]?.name || '科研数据图表';

  return (
    <div className={`research-chart ${className}`.trim()} style={{ height }}>
      <div ref={ref} className="research-chart__canvas" role="img" aria-label={label} />
      {empty && <div className="research-chart__empty">{emptyText}</div>}
    </div>
  );
}
