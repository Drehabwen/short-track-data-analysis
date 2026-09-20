const FIELDS = [
  ['身高', 'cm'],
  ['体重', 'kg'],
  ['BMI', 'kg/m²'],
  ['体脂率', '%'],
  ['骨骼肌量', 'kg'],
  ['去脂体重', 'kg'],
];

export default function BodyCompositionPage() {
  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">身体成分</div>
          <div className="page-desc">训练阶段中的身体组成变化 · 本地数据</div>
        </div>
        <a className="btn btn-secondary" href="/training">补录体重 / 体脂率</a>
      </div>

      <div className="card body-composition-status" style={{ marginBottom: 16 }}>
        <div>
          <div className="card-title">设备数据尚未接入</div>
          <div className="note">拿到机器导出样例后，再建立对应字段、单位换算和异常检查；当前不做通用 OCR 猜测。</div>
        </div>
        <div className="body-composition-status__state">等待设备样例</div>
      </div>

      <div className="grid cols-3">
        {FIELDS.map(([name, unit]) => (
          <div className="card" key={name}>
            <div className="stat-label">{name}</div>
            <div className="stat-number">—</div>
            <div className="note">标准单位：{unit}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title">接入后用于什么</div>
        <p className="note" style={{ margin: 0 }}>
          按运动员和测试日期保存原始结果，查看阶段变化，并与专项体能、训练负荷和成绩进行相关分析。系统只呈现数据关系，不自动给出医学诊断。
        </p>
      </div>
    </div>
  );
}
