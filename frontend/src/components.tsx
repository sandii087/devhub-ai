import { ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Row } from './api'

export const money = (value: unknown) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(value || 0))
export const number = (value: unknown) => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(value || 0))
export const percent = (value: unknown) => `${Number(value || 0).toFixed(1)}%`

export function Loading() { return <div className="grid min-h-64 place-items-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-500">Loading live analytics…</div> }
export function ErrorState({ message }: { message: string }) { return <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"><strong>Couldn’t load this analysis.</strong><br />{message}</div> }
export function EmptyState({ label = 'No matching records' }: { label?: string }) { return <div className="grid min-h-40 place-items-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-500">{label}</div> }

export function StatCard({ label, value, note, tone = 'navy' }: { label: string, value: string, note?: string, tone?: 'navy' | 'mint' | 'coral' | 'amber' }) {
  const tones = { navy: 'bg-navy', mint: 'bg-mint', coral: 'bg-coral', amber: 'bg-amber' }
  return <article className="panel relative overflow-hidden p-5"><div className={`absolute inset-x-0 top-0 h-1 ${tones[tone]}`} /><p className="text-xs font-semibold uppercase tracking-[.11em] text-slate-500">{label}</p><p className="mt-3 text-2xl font-semibold tracking-tight text-ink">{value}</p>{note && <p className="mt-1 text-xs text-slate-500">{note}</p>}</article>
}

export function ChartPanel({ title, subtitle, children, className = '' }: { title: string, subtitle?: string, children: ReactNode, className?: string }) {
  return <section className={`panel p-5 ${className}`}><div className="mb-4"><h3 className="text-sm font-semibold text-ink">{title}</h3>{subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}</div>{children}</section>
}

export function BarMetric({ rows, labelKey, valueKey = 'churn_rate', color = '#0e9384', valueFormat = percent }: { rows: Row[], labelKey: string, valueKey?: string, color?: string, valueFormat?: (value: unknown) => string }) {
  if (!rows.length) return <EmptyState />
  return <div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}><CartesianGrid stroke="#edf0f3" vertical={false} /><XAxis dataKey={labelKey} tick={{ fontSize: 10, fill: '#667085' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: '#667085' }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => valueFormat(value)} contentStyle={{ borderRadius: 8, borderColor: '#e4e7ec', fontSize: 12 }} /><Bar dataKey={valueKey} fill={color} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
}

export function TrendChart({ rows }: { rows: Row[] }) {
  if (!rows.length) return <EmptyState label="No churn events in the selected view" />
  return <div className="h-64"><ResponsiveContainer width="100%" height="100%"><LineChart data={rows} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}><CartesianGrid stroke="#edf0f3" vertical={false} /><XAxis dataKey="month" tick={{ fontSize: 10, fill: '#667085' }} axisLine={false} tickLine={false} minTickGap={22} /><YAxis tick={{ fontSize: 10, fill: '#667085' }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ borderRadius: 8, borderColor: '#e4e7ec', fontSize: 12 }} /><Line type="monotone" dataKey="churned_customers" stroke="#e85d75" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div>
}

export function Pill({ children, type = 'neutral' }: { children: ReactNode, type?: 'neutral' | 'risk' | 'good' }) {
  const className = type === 'risk' ? 'bg-rose-50 text-rose-700' : type === 'good' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'
  return <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${className}`}>{children}</span>
}
