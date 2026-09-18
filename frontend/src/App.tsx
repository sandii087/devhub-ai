import { useEffect, useMemo, useState } from 'react'
import { api, type Metrics, type Row } from './api'
import { BarMetric, ChartPanel, EmptyState, ErrorState, Loading, Pill, StatCard, TrendChart, money, number, percent } from './components'

type Page = 'Overview' | 'Churn Analytics' | 'Customer Segments' | 'Risk Explorer' | 'Cohort Analysis' | 'Model Performance' | 'Insights' | 'Data Quality'
type ApiData = Record<string, any>

const navigation: { page: Page, icon: string }[] = [
  { page: 'Overview', icon: '◫' }, { page: 'Churn Analytics', icon: '↘' }, { page: 'Customer Segments', icon: '◌' }, { page: 'Risk Explorer', icon: '⌁' },
  { page: 'Cohort Analysis', icon: '▦' }, { page: 'Model Performance', icon: '◈' }, { page: 'Insights', icon: '✦' }, { page: 'Data Quality', icon: '✓' },
]

function useEndpoint<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(Boolean(path))
  useEffect(() => {
    if (!path) return
    let active = true
    setLoading(true); setError('')
    api<T>(path).then((response) => { if (active) setData(response) }).catch((err: Error) => { if (active) setError(err.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [path])
  return { data, error, loading }
}

const getRows = (data: ApiData | null, key: string): Row[] => (data?.[key] || []) as Row[]
const getMetrics = (data: ApiData | null): Metrics => (data?.metrics || {}) as Metrics

function PageIntro({ kicker, title, copy, actions }: { kicker: string, title: string, copy: string, actions?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-mint">{kicker}</p><h1 className="page-title mt-2">{title}</h1><p className="page-copy">{copy}</p></div>{actions}</div>
}

function Overview() {
  const { data, loading, error } = useEndpoint<ApiData>('/overview')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const m = getMetrics(data)
  return <><PageIntro kicker="Executive overview" title="Retention health at a glance" copy="A current snapshot calculated from the cleaned, scored fictional customer dataset." actions={<div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">Analytical snapshot · Sep 2026</div>} />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"><StatCard label="Total customers" value={number(m.total_customers)} note={`${number(m.retained_customers)} currently retained`} /><StatCard label="Churn rate" value={percent(m.churn_rate)} note={`${number(m.churned_customers)} customers churned`} tone="coral" /><StatCard label="At-risk customers" value={number(m.at_risk_customers)} note="Predicted high-risk customers" tone="amber" /><StatCard label="Monthly recurring revenue" value={money(m.mrr)} note="Current customer snapshot" tone="mint" /><StatCard label="Revenue at risk" value={money(m.revenue_at_risk)} note="Expected monthly exposure from risk scores" tone="coral" /><StatCard label="Average satisfaction" value={`${Number(m.average_satisfaction || 0).toFixed(2)} / 5`} note={`${Number(m.average_tenure || 0).toFixed(1)} average months of tenure`} /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-2"><ChartPanel title="Churn events over time" subtitle="Observed churn events by churn month"><TrendChart rows={getRows(data, 'churn_trend')} /></ChartPanel><ChartPanel title="Churn by subscription plan" subtitle="Observed churn rate, not a forecast"><BarMetric rows={getRows(data, 'plan_churn')} labelKey="subscription_plan" /></ChartPanel><ChartPanel title="Churn by contract" subtitle="Contract duration is a useful retention lens"><BarMetric rows={getRows(data, 'contract_churn')} labelKey="contract_type" color="#d97706" /></ChartPanel><ChartPanel title="Portfolio mix" subtitle="Value and model-based risk segments"><BarMetric rows={getRows(data, 'portfolio_segments')} labelKey="portfolio_segment" valueKey="customers" color="#101b31" valueFormat={number} /></ChartPanel></div>
    <section className="panel mt-5 p-5"><div className="flex items-center justify-between"><div><h3 className="text-sm font-semibold text-ink">What to investigate</h3><p className="mt-1 text-xs text-slate-500">Each statement is recalculated from the current data.</p></div><span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-medium text-mint">Live analysis</span></div><div className="mt-4 grid gap-3 lg:grid-cols-2">{getRows(data, 'insights').map((insight) => <div key={String(insight.title)} className="rounded-lg border border-slate-200 p-4"><p className="text-sm font-semibold text-ink">{insight.title}</p><p className="mt-1 text-sm leading-6 text-slate-600">{insight.detail}</p></div>)}</div></section>
  </>
}

function ChurnAnalytics() {
  const [plan, setPlan] = useState('')
  const [region, setRegion] = useState('')
  const query = useMemo(() => `/churn?${new URLSearchParams(Object.fromEntries(Object.entries({ plan, region }).filter(([, value]) => value))).toString()}`, [plan, region])
  const { data, loading, error } = useEndpoint<ApiData>(query)
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const m = getMetrics(data)
  return <><PageIntro kicker="Churn analytics" title="Find the friction behind attrition" copy="Filter the dataset, then compare churn across contracts, tenure, payment, satisfaction, and engagement." actions={<div className="flex flex-wrap gap-2"><select className="control" value={plan} onChange={(e) => setPlan(e.target.value)}><option value="">All plans</option><option>Basic</option><option>Standard</option><option>Premium</option><option>Enterprise</option></select><select className="control" value={region} onChange={(e) => setRegion(e.target.value)}><option value="">All regions</option><option>North</option><option>South</option><option>East</option><option>West</option><option>Central</option></select></div>} />
    <div className="grid gap-4 sm:grid-cols-3"><StatCard label="Customers in view" value={number(m.total_customers)} /><StatCard label="Observed churn" value={percent(m.churn_rate)} tone="coral" /><StatCard label="Expected MRR exposure" value={money(m.revenue_at_risk)} tone="amber" /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-2"><ChartPanel title="Churn trend" subtitle="Events by recorded churn month"><TrendChart rows={getRows(data, 'trend')} /></ChartPanel><ChartPanel title="Churn by plan"><BarMetric rows={getRows(data, 'by_plan')} labelKey="subscription_plan" /></ChartPanel><ChartPanel title="Churn by contract"><BarMetric rows={getRows(data, 'by_contract')} labelKey="contract_type" color="#d97706" /></ChartPanel><ChartPanel title="Churn by tenure"><BarMetric rows={getRows(data, 'by_tenure')} labelKey="tenure_bucket" color="#e85d75" /></ChartPanel><ChartPanel title="Churn by region"><BarMetric rows={getRows(data, 'by_region')} labelKey="region" /></ChartPanel><ChartPanel title="Churn by satisfaction"><BarMetric rows={getRows(data, 'by_satisfaction')} labelKey="satisfaction_score" color="#5b5bd6" /></ChartPanel><ChartPanel title="Churn by payment method"><BarMetric rows={getRows(data, 'by_payment_method')} labelKey="payment_method" color="#d97706" /></ChartPanel><ChartPanel title="Churn by engagement"><BarMetric rows={getRows(data, 'by_engagement')} labelKey="engagement_level" color="#e85d75" /></ChartPanel></div>
  </>
}

function Segments() {
  const { data, loading, error } = useEndpoint<ApiData>('/segments')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const segmentRows = getRows(data, 'segments')
  return <><PageIntro kicker="Customer segmentation" title="Prioritize the right retention moves" copy="Portfolio segments combine a median lifetime-value rule with actual logistic-regression risk probabilities." />
    <div className="grid gap-4 md:grid-cols-2">{segmentRows.map((item) => <section key={String(item.portfolio_segment)} className="panel p-5"><div className="flex items-start justify-between gap-4"><div><h3 className="text-base font-semibold text-ink">{item.portfolio_segment}</h3><p className="mt-1 text-sm text-slate-500">{number(item.customers)} customers · {percent(item.churn_rate)} observed churn</p></div><Pill type={String(item.portfolio_segment).includes('High Risk') ? 'risk' : 'good'}>{String(item.portfolio_segment).includes('High Risk') ? 'Priority' : 'Stable'}</Pill></div><div className="mt-5 grid grid-cols-2 gap-y-4 text-sm"><Metric label="Monthly revenue" value={money(item.revenue)} /><Metric label="Revenue at risk" value={money(item.revenue_at_risk)} /><Metric label="Average tenure" value={`${Number(item.average_tenure).toFixed(1)} mo`} /><Metric label="Satisfaction" value={`${Number(item.average_satisfaction).toFixed(2)} / 5`} /></div></section>)}</div>
    <div className="mt-5"><ChartPanel title="Segment distribution" subtitle="Customer counts by value/risk portfolio"><BarMetric rows={getRows(data, 'distribution')} labelKey="portfolio_segment" valueKey="customers" color="#101b31" valueFormat={number} /></ChartPanel></div>
  </>
}

function Metric({ label, value }: { label: string, value: string }) { return <div><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-1 font-semibold text-ink">{value}</p></div> }

function RiskExplorer() {
  const { data, loading, error } = useEndpoint<ApiData>('/risk')
  const [search, setSearch] = useState('')
  const [riskSegment, setRiskSegment] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const customerPath = `/customers?${new URLSearchParams(Object.fromEntries(Object.entries({ search, risk_segment: riskSegment }).filter(([, value]) => value))).toString()}`
  const customers = useEndpoint<ApiData>(customerPath)
  const detail = useEndpoint<ApiData>(selected ? `/customer/${selected}` : null)
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const m = getMetrics(data)
  const customerItems = getRows(customers.data, 'items')
  return <><PageIntro kicker="Risk explorer" title="Turn likelihood into a retention queue" copy="Risk is a logistic-regression churn probability. Revenue at risk equals monthly charges × that probability." />
    <div className="grid gap-4 sm:grid-cols-3"><StatCard label="High-risk customers" value={number(m.at_risk_customers)} note="Score greater than 0.66" tone="coral" /><StatCard label="Expected monthly exposure" value={money(m.revenue_at_risk)} note="Probability-weighted MRR" tone="amber" /><StatCard label="Total MRR" value={money(m.mrr)} note="Current snapshot" tone="mint" /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-2"><ChartPanel title="Risk distribution" subtitle="Scores grouped into transparent bands"><BarMetric rows={getRows(data, 'distribution')} labelKey="risk_segment" valueKey="customers" color="#e85d75" valueFormat={number} /></ChartPanel><ChartPanel title="Expected revenue exposure by plan"><BarMetric rows={getRows(data, 'by_plan')} labelKey="subscription_plan" valueKey="revenue_at_risk" color="#d97706" valueFormat={money} /></ChartPanel></div>
    <section className="panel mt-5 overflow-hidden"><div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="text-sm font-semibold text-ink">Customer risk queue</h3><p className="mt-1 text-xs text-slate-500">Open a row to review customer context and transparent elevated-risk factors.</p></div><div className="flex gap-2"><input className="control w-44" placeholder="Search ID or city" value={search} onChange={(e) => setSearch(e.target.value)} /><select className="control" value={riskSegment} onChange={(e) => setRiskSegment(e.target.value)}><option value="">All risk bands</option><option>High Risk</option><option>Medium Risk</option><option>Low Risk</option></select></div></div>
      {customers.loading ? <div className="p-5"><Loading /></div> : customers.error ? <div className="p-5"><ErrorState message={customers.error} /></div> : customerItems.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Customer</th><th>Segment</th><th>Plan</th><th>Tenure</th><th>Satisfaction</th><th>Risk score</th><th>Expected MRR risk</th></tr></thead><tbody>{customerItems.map((customer) => <tr key={String(customer.customer_id)} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected(String(customer.customer_id))}><td className="font-medium text-ink">{customer.customer_id}</td><td>{customer.customer_segment}</td><td>{customer.subscription_plan}</td><td>{customer.tenure_months} mo</td><td>{customer.satisfaction_score} / 5</td><td><Pill type={customer.risk_segment === 'High Risk' ? 'risk' : 'neutral'}>{(Number(customer.risk_score) * 100).toFixed(1)}%</Pill></td><td>{money(customer.revenue_at_risk)}</td></tr>)}</tbody></table></div> : <div className="p-5"><EmptyState /></div>}</section>
    {selected && <CustomerModal detail={detail.data} loading={detail.loading} error={detail.error} onClose={() => setSelected(null)} />}
  </>
}

function CustomerModal({ detail, loading, error, onClose }: { detail: ApiData | null, loading: boolean, error: string, onClose: () => void }) {
  const customer = detail?.customer as ApiData | undefined
  return <div className="fixed inset-0 z-30 grid place-items-center bg-slate-950/35 p-4" role="dialog" aria-modal="true"><div className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.12em] text-mint">Customer detail</p><h2 className="mt-1 text-xl font-semibold text-ink">{customer?.customer_id || 'Loading customer'}</h2></div><button className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" onClick={onClose}>Close</button></div>{loading ? <div className="mt-5"><Loading /></div> : error ? <div className="mt-5"><ErrorState message={error} /></div> : customer && <><div className="mt-6 grid gap-4 sm:grid-cols-3"><Metric label="Risk score" value={`${(Number(customer.risk_score) * 100).toFixed(1)}%`} /><Metric label="Risk segment" value={String(customer.risk_segment)} /><Metric label="Expected MRR risk" value={money(customer.revenue_at_risk)} /><Metric label="Subscription" value={`${customer.subscription_plan} · ${customer.contract_type}`} /><Metric label="Tenure" value={`${customer.tenure_months} months`} /><Metric label="Monthly charges" value={money(customer.monthly_charges)} /><Metric label="Engagement" value={`${customer.engagement_level} · ${customer.last_login_days}d since login`} /><Metric label="Support" value={`${customer.support_tickets} tickets`} /><Metric label="Satisfaction" value={`${customer.satisfaction_score} / 5`} /></div><div className="mt-6 rounded-lg bg-slate-50 p-4"><p className="text-sm font-semibold text-ink">Elevated-risk factors</p><ul className="mt-2 space-y-1 text-sm text-slate-600">{((detail?.risk_factors || []) as string[]).map((factor) => <li key={factor}>• {factor}</li>)}</ul></div></>}</div></div>
}

function Cohorts() {
  const { data, loading, error } = useEndpoint<ApiData>('/cohorts')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const rows = getRows(data, 'rows'); const cohorts = ((data?.cohorts || []) as string[]).slice(-12); const periods = (data?.periods || []) as number[]
  const lookup = new Map(rows.map((row) => [`${row.cohort}-${row.period}`, Number(row.retention_rate)]))
  return <><PageIntro kicker="Cohort analysis" title="Retention from signup through month 12" copy="Each cell is calculated from actual synthetic signup and churn dates. Blank cells have not yet had enough elapsed time." />
    <section className="panel overflow-hidden"><div className="border-b border-slate-200 p-5"><h3 className="text-sm font-semibold text-ink">Cohort retention matrix</h3><p className="mt-1 text-xs text-slate-500">Showing the 12 most recent signup cohorts. Darker cells indicate higher retained-customer share.</p></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Cohort</th><th>Size</th>{periods.map((period) => <th key={period}>M{period}</th>)}</tr></thead><tbody>{cohorts.map((cohort) => { const first = rows.find((row) => row.cohort === cohort); return <tr key={cohort}><td className="font-medium text-ink">{cohort}</td><td>{number(first?.cohort_size)}</td>{periods.map((period) => { const rate = lookup.get(`${cohort}-${period}`); return <td key={period}>{rate === undefined ? <span className="text-slate-300">—</span> : <span className="inline-flex min-w-11 justify-center rounded px-1.5 py-1 text-xs font-medium" style={{ backgroundColor: `rgba(14, 147, 132, ${Math.max(.08, rate / 100)})`, color: rate > 72 ? '#ffffff' : '#135c55' }}>{rate.toFixed(0)}%</span>}</td>})}</tr>})}</tbody></table></div></section>
  </>
}

function ModelPerformance() {
  const { data, loading, error } = useEndpoint<ApiData>('/model')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const matrix = (data?.confusion_matrix || []) as number[][]
  return <><PageIntro kicker="Model performance" title="A transparent, baseline churn model" copy="Logistic regression is intentionally used as a readable baseline—not a production-ready claim." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><StatCard label="Accuracy" value={percent(Number(data?.accuracy) * 100)} /><StatCard label="Precision" value={percent(Number(data?.precision) * 100)} /><StatCard label="Recall" value={percent(Number(data?.recall) * 100)} tone="mint" /><StatCard label="F1 score" value={percent(Number(data?.f1) * 100)} /><StatCard label="ROC-AUC" value={percent(Number(data?.roc_auc) * 100)} tone="amber" /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-[.9fr_1.1fr]"><ChartPanel title="Confusion matrix" subtitle="Holdout set predictions; rows are actual, columns are predicted"><div className="grid grid-cols-2 gap-2 text-center text-sm"><div className="rounded-lg bg-slate-100 p-4 text-slate-600">True negatives<strong className="mt-1 block text-xl text-ink">{number(matrix[0]?.[0])}</strong></div><div className="rounded-lg bg-rose-50 p-4 text-rose-700">False positives<strong className="mt-1 block text-xl">{number(matrix[0]?.[1])}</strong></div><div className="rounded-lg bg-amber-50 p-4 text-amber-700">False negatives<strong className="mt-1 block text-xl">{number(matrix[1]?.[0])}</strong></div><div className="rounded-lg bg-emerald-50 p-4 text-emerald-700">True positives<strong className="mt-1 block text-xl">{number(matrix[1]?.[1])}</strong></div></div></ChartPanel><ChartPanel title="Methodology & limitations" subtitle={`${data?.train_rows || 0} training rows · ${data?.test_rows || 0} stratified holdout rows`}><p className="text-sm leading-6 text-slate-600">{data?.methodology}</p><p className="mt-4 text-sm font-semibold text-ink">Why accuracy alone is not enough</p><p className="mt-1 text-sm leading-6 text-slate-600">Churn is a minority outcome, so a model can look accurate while missing customers who are likely to leave. Precision measures how often flagged customers actually churn; recall measures how many churners are found. Both belong alongside ROC-AUC and F1.</p></ChartPanel></div>
    <section className="panel mt-5 p-5"><h3 className="text-sm font-semibold text-ink">Important limitations</h3><ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">{((data?.limitations || []) as string[]).map((item) => <li key={item}>• {item}</li>)}</ul></section>
  </>
}

function Insights() {
  const { data, loading, error } = useEndpoint<ApiData>('/insights')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  return <><PageIntro kicker="Business insights" title="The clearest next questions to answer" copy="Statements are recomputed from the database each time the endpoint is requested, so they stay traceable to this snapshot." /><div className="grid gap-4 lg:grid-cols-2">{getRows(data, 'insights').map((item, index) => <article key={String(item.title)} className="panel p-6"><span className="text-2xl font-semibold text-mint">0{index + 1}</span><h2 className="mt-5 text-lg font-semibold text-ink">{item.title}</h2><p className="mt-2 max-w-xl text-sm leading-7 text-slate-600">{item.detail}</p></article>)}</div></>
}

function DataQuality() {
  const { data, loading, error } = useEndpoint<ApiData>('/data-quality')
  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  const before = (data?.before || {}) as Record<string, any>; const after = (data?.after || {}) as Record<string, any>
  return <><PageIntro kicker="Data quality" title="Controlled imperfections, documented repairs" copy="The synthetic raw data intentionally contains realistic quality issues. This page exposes the exact before/after cleaning process." />
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Rows processed" value={number(before.rows)} /><StatCard label="Rows removed" value={number(data?.rows_removed)} tone="coral" /><StatCard label="Duplicate rows found" value={number(before.duplicate_rows)} tone="amber" /><StatCard label="Clean rows published" value={number(data?.final_clean_row_count)} tone="mint" /></div>
    <div className="mt-5 grid gap-5 xl:grid-cols-2"><ChartPanel title="Validation results" subtitle="Known invalid values before cleaning"><div className="grid grid-cols-2 gap-4 text-sm"><Metric label="Invalid ages" value={number(before.invalid_ages)} /><Metric label="Invalid dates" value={number(before.invalid_dates)} /><Metric label="Invalid charges" value={number(before.invalid_monthly_charges)} /><Metric label="Invalid churn labels" value={number(before.invalid_churn_labels)} /><Metric label="Invalid plans" value={number(before.invalid_plans)} /><Metric label="Invalid regions" value={number(before.invalid_regions)} /></div></ChartPanel><ChartPanel title="Cleaning status" subtitle="The clean output is validated before database load"><div className="grid grid-cols-2 gap-4 text-sm"><Metric label="Remaining invalid ages" value={number(after.invalid_ages)} /><Metric label="Remaining invalid dates" value={number(after.invalid_dates)} /><Metric label="Remaining invalid charges" value={number(after.invalid_monthly_charges)} /><Metric label="Remaining invalid churn labels" value={number(after.invalid_churn_labels)} /><Metric label="Exact duplicates" value={number(after.duplicate_rows)} /><Metric label="Unique customer IDs" value={number(after.rows - after.duplicate_customer_ids)} /></div></ChartPanel></div>
    <section className="panel mt-5 p-5"><h3 className="text-sm font-semibold text-ink">Actions applied</h3><ol className="mt-3 space-y-3 text-sm leading-6 text-slate-600">{((data?.cleaning_actions || []) as string[]).map((action, index) => <li key={action} className="flex gap-3"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-teal-50 text-xs font-semibold text-mint">{index + 1}</span><span>{action}</span></li>)}</ol></section>
  </>
}

function App() {
  const [page, setPage] = useState<Page>('Overview')
  const [menuOpen, setMenuOpen] = useState(false)
  const content: Record<Page, React.ReactNode> = { Overview: <Overview />, 'Churn Analytics': <ChurnAnalytics />, 'Customer Segments': <Segments />, 'Risk Explorer': <RiskExplorer />, 'Cohort Analysis': <Cohorts />, 'Model Performance': <ModelPerformance />, Insights: <Insights />, 'Data Quality': <DataQuality /> }
  return <div className="min-h-screen lg:flex"><aside className={`fixed inset-y-0 left-0 z-20 flex w-64 flex-col bg-navy px-4 py-5 transition-transform lg:sticky lg:translate-x-0 ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}><div className="flex items-center gap-3 px-2"><div className="grid h-9 w-9 place-items-center rounded-lg bg-mint text-base font-bold text-white">C</div><div><p className="font-semibold tracking-tight text-white">ChurnIQ</p><p className="text-xs text-slate-400">Retention intelligence</p></div></div><nav className="mt-9 space-y-1">{navigation.map((item) => <button key={item.page} onClick={() => { setPage(item.page); setMenuOpen(false) }} className={`nav-item ${page === item.page ? 'nav-item-active' : ''}`}><span className="w-4 text-center text-base">{item.icon}</span>{item.page}</button>)}</nav><div className="mt-auto rounded-lg border border-white/10 bg-white/5 p-3"><p className="text-xs font-medium text-slate-300">Synthetic-data project</p><p className="mt-1 text-xs leading-5 text-slate-400">Metrics are calculated locally from the SQLite analytics database.</p></div></aside>{menuOpen && <button aria-label="Close navigation" className="fixed inset-0 z-10 bg-slate-950/25 lg:hidden" onClick={() => setMenuOpen(false)} />}
    <main className="min-w-0 flex-1"><header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-7"><button className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open navigation">☰</button><div className="hidden text-sm text-slate-500 lg:block">Analytics / <span className="font-medium text-ink">{page}</span></div><div className="ml-auto flex items-center gap-3"><span className="hidden rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 sm:block">Data pipeline ready</span><div className="grid h-8 w-8 place-items-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">DA</div></div></header><div className="mx-auto max-w-[1580px] p-4 sm:p-7">{content[page]}</div></main></div>
}

export default App
