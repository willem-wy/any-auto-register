import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Plus, Trash2, RefreshCw, ToggleLeft, ToggleRight, Globe2, ShieldCheck, CircleOff, Activity, Zap, Pencil, FlaskConical, X } from 'lucide-react'

type DynField = {
  key: string
  label: string
  placeholder?: string
  secret?: boolean
  required?: boolean
  options?: string[]
}

type ProxyItem = {
  id: number
  url: string
  region?: string
  is_active: boolean
  success_count: number
  fail_count: number
}

type DynSetting = {
  id: number
  provider_key: string
  enabled: boolean
  config?: Record<string, string>
  auth?: Record<string, string>
  auth_preview?: Record<string, string>
}

const errText = (err: unknown) => (err instanceof Error ? err.message : String(err))

const DYN_FIELDS: Record<string, DynField[]> = {
  api_extract: [
    { key: 'proxy_api_url', label: 'API 提取地址', placeholder: 'https://provider.com/api/get_proxy?key=xxx', required: true },
    { key: 'proxy_protocol', label: '协议', options: ['http', 'https', 'socks5'] },
    { key: 'proxy_username', label: '用户名（可选）' },
    { key: 'proxy_password', label: '密码（可选）', secret: true },
  ],
  rotating_gateway: [
    { key: 'proxy_gateway_url', label: '网关地址', placeholder: 'http://user:pass@gate.example.com:7777', required: true },
  ],
}

const DYN_LABELS: Record<string, string> = {
  api_extract: 'API 提取代理',
  rotating_gateway: '旋转网关代理',
}

const fieldValue = (values: Record<string, string>, field: DynField) =>
  values[field.key] ?? (field.options ? field.options[0] : '')

export default function Proxies() {
  const [proxies, setProxies] = useState<ProxyItem[]>([])
  const [newProxy, setNewProxy] = useState('')
  const [region, setRegion] = useState('')
  const [checking, setChecking] = useState(false)

  const [dynList, setDynList] = useState<DynSetting[]>([])
  const [dynKey, setDynKey] = useState('api_extract')
  const [dynValues, setDynValues] = useState<Record<string, string>>({})
  const [dynId, setDynId] = useState<number | null>(null)
  const [dynEnabled, setDynEnabled] = useState(true)
  const [dynBusy, setDynBusy] = useState(false)
  const [dynMsg, setDynMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const load = () => apiFetch('/proxies').then(setProxies)
  const loadDyn = () => apiFetch('/provider-settings?provider_type=proxy').then(setDynList)

  useEffect(() => { load(); loadDyn() }, [])

  const resetDynForm = () => {
    setDynId(null)
    setDynKey('api_extract')
    setDynValues({})
    setDynEnabled(true)
    setDynMsg(null)
  }

  const pickDynKey = (key: string) => {
    setDynKey(key)
    setDynValues({})
    setDynMsg(null)
  }

  const setDynField = (key: string, value: string) =>
    setDynValues(prev => ({ ...prev, [key]: value }))

  const buildDynPayload = (key: string, values: Record<string, string>, id: number | null, enabled: boolean) => {
    const config: Record<string, string> = {}
    const auth: Record<string, string> = {}
    for (const field of DYN_FIELDS[key] || []) {
      const value = fieldValue(values, field).trim()
      if (field.secret) auth[field.key] = value
      else config[field.key] = value
    }
    return {
      id: id ?? undefined,
      provider_type: 'proxy',
      provider_key: key,
      display_name: '',
      auth_mode: '',
      enabled,
      is_default: false,
      config,
      auth,
      metadata: {},
    }
  }

  const validateDyn = (key: string, values: Record<string, string>) => {
    const missing = (DYN_FIELDS[key] || [])
      .filter(field => field.required && !fieldValue(values, field).trim())
      .map(field => field.label)
    return missing.length ? `请填写：${missing.join('、')}` : ''
  }

  const saveDyn = async () => {
    const error = validateDyn(dynKey, dynValues)
    if (error) { setDynMsg({ ok: false, text: error }); return }
    setDynBusy(true); setDynMsg(null)
    try {
      await apiFetch('/provider-settings', {
        method: dynId ? 'PUT' : 'POST',
        body: JSON.stringify(buildDynPayload(dynKey, dynValues, dynId, dynEnabled)),
      })
      resetDynForm()
      loadDyn()
      setDynMsg({ ok: true, text: '已保存' })
    } catch (err) {
      setDynMsg({ ok: false, text: errText(err) })
    } finally {
      setDynBusy(false)
    }
  }

  const testDyn = async () => {
    const error = validateDyn(dynKey, dynValues)
    if (error) { setDynMsg({ ok: false, text: error }); return }
    setDynBusy(true); setDynMsg(null)
    try {
      const payload = buildDynPayload(dynKey, dynValues, null, true)
      const result = await apiFetch('/provider-settings/test', {
        method: 'POST',
        body: JSON.stringify({
          provider_type: 'proxy',
          provider_key: payload.provider_key,
          config: payload.config,
          auth: payload.auth,
        }),
      })
      setDynMsg({ ok: !!result.ok, text: result.ok ? result.message : `失败：${result.error}` })
    } catch (err) {
      setDynMsg({ ok: false, text: errText(err) })
    } finally {
      setDynBusy(false)
    }
  }

  const editDyn = (setting: DynSetting) => {
    setDynId(setting.id)
    setDynKey(setting.provider_key)
    setDynValues({ ...(setting.config || {}), ...(setting.auth || {}) })
    setDynEnabled(setting.enabled)
    setDynMsg(null)
  }

  const toggleDyn = async (setting: DynSetting) => {
    const values = { ...(setting.config || {}), ...(setting.auth || {}) }
    await apiFetch('/provider-settings', {
      method: 'PUT',
      body: JSON.stringify(buildDynPayload(setting.provider_key, values, setting.id, !setting.enabled)),
    })
    loadDyn()
  }

  const delDyn = async (id: number) => {
    await apiFetch(`/provider-settings/${id}`, { method: 'DELETE' })
    if (dynId === id) resetDynForm()
    loadDyn()
  }

  const add = async () => {
    if (!newProxy.trim()) return
    const lines = newProxy.trim().split('\n').map(l => l.trim()).filter(Boolean)
    if (lines.length > 1) {
      await apiFetch('/proxies/bulk', {
        method: 'POST',
        body: JSON.stringify({ proxies: lines, region }),
      })
    } else {
      await apiFetch('/proxies', {
        method: 'POST',
        body: JSON.stringify({ url: lines[0], region }),
      })
    }
    setNewProxy('')
    load()
  }

  const del = async (id: number) => {
    await apiFetch(`/proxies/${id}`, { method: 'DELETE' })
    load()
  }

  const toggle = async (id: number) => {
    await apiFetch(`/proxies/${id}/toggle`, { method: 'PATCH' })
    load()
  }

  const check = async () => {
    setChecking(true)
    await apiFetch('/proxies/check', { method: 'POST' })
    setTimeout(() => { load(); setChecking(false) }, 3000)
  }

  const activeCount = proxies.filter((item) => item.is_active).length
  const totalSuccess = proxies.reduce((sum, item) => sum + Number(item.success_count || 0), 0)
  const totalFail = proxies.reduce((sum, item) => sum + Number(item.fail_count || 0), 0)
  const metricCards = [
    { label: '代理数', value: proxies.length, icon: Globe2, tone: 'text-[var(--accent)]' },
    { label: '启用', value: activeCount, icon: ShieldCheck, tone: 'text-emerald-400' },
    { label: '成功次数', value: totalSuccess, icon: Activity, tone: 'text-[var(--accent)]' },
    { label: '失败次数', value: totalFail, icon: CircleOff, tone: 'text-red-400' },
  ]

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden p-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-semibold text-[var(--text-primary)]">代理</div>
            <Badge variant="default">总量 {proxies.length}</Badge>
            <Badge variant="secondary">活跃 {activeCount}</Badge>
          </div>
          <Button variant="outline" size="sm" onClick={check} disabled={checking}>
            <RefreshCw className={`h-4 w-4 mr-1.5 ${checking ? 'animate-spin' : ''}`} />
            检测全部
          </Button>
        </div>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map(({ label, value, icon: Icon, tone }) => (
          <Card key={label} className="bg-transparent">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--text-muted)]">{label}</div>
                <div className="mt-1.5 text-xl font-semibold tracking-[-0.03em] text-[var(--text-primary)]">{value}</div>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-soft)] bg-[var(--chip-bg)]">
                <Icon className={`h-5 w-5 ${tone}`} />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,330px)_minmax(0,1fr)]">
        <Card className="bg-[var(--bg-pane)]/60">
          <div className="space-y-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-[var(--text-muted)]">新增</div>
              <div className="mt-1 text-sm font-medium text-[var(--text-primary)]">添加代理或批量导入</div>
            </div>
            <textarea
              value={newProxy}
              onChange={e => setNewProxy(e.target.value)}
              placeholder="http://user:pass@host:port"
              rows={8}
              className="control-surface control-surface-mono resize-none"
            />
            <input
              value={region}
              onChange={e => setRegion(e.target.value)}
              placeholder="地区标签 (如 US, SG)"
              className="control-surface"
            />
            <div className="rounded-lg border border-[var(--border-soft)] bg-[var(--bg-pane)]/45 px-3.5 py-2.5 text-xs leading-5 text-[var(--text-secondary)]">
              支持单条代理直接录入，也支持多行批量导入。地区标签会一起写入，用于后续筛选和出入口识别。
            </div>
            <Button onClick={add} className="w-full">
              <Plus className="h-4 w-4 mr-1.5" />
              添加到代理池
            </Button>
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="border-b border-[var(--border)] px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
            代理列表
          </div>
        <div className="glass-table-wrap">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--text-muted)]">
              <th className="px-4 py-2.5 text-left">代理地址</th>
              <th className="px-4 py-2.5 text-left">地区</th>
              <th className="px-4 py-2.5 text-left">成功/失败</th>
              <th className="px-4 py-2.5 text-left">状态</th>
              <th className="px-4 py-2.5 text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {proxies.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8">
                  <div className="empty-state-panel">当前代理池为空，可以先从左侧输入一个或批量导入。</div>
                </td>
              </tr>
            )}
            {proxies.map(p => (
              <tr key={p.id} className="border-b border-[var(--border)]/40 hover:bg-[var(--bg-hover)]/70">
                <td className="px-4 py-2.5 font-mono text-xs text-[var(--text-secondary)]">{p.url}</td>
                <td className="px-4 py-2.5 text-[var(--text-muted)]">{p.region || '-'}</td>
                <td className="px-4 py-2.5">
                  <span className="text-emerald-400">{p.success_count}</span>
                  <span className="text-[var(--text-muted)]"> / </span>
                  <span className="text-red-400">{p.fail_count}</span>
                </td>
                <td className="px-4 py-2.5">
                  <Badge variant={p.is_active ? 'success' : 'danger'}>
                    {p.is_active ? '活跃' : '禁用'}
                  </Badge>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <button onClick={() => toggle(p.id)} className="table-action-btn">
                      {p.is_active ? <ToggleRight className="mr-1.5 h-4 w-4" /> : <ToggleLeft className="mr-1.5 h-4 w-4" />}
                      {p.is_active ? '停用' : '启用'}
                    </button>
                    <button onClick={() => del(p.id)} className="table-action-btn table-action-btn-danger">
                      <Trash2 className="mr-1.5 h-4 w-4" />
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        </Card>
      </div>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-[var(--accent)]" />
            <div className="text-sm font-medium text-[var(--text-primary)]">动态代理（注册自动轮换出口 IP）</div>
          </div>
          <Badge variant={dynList.some(item => item.enabled) ? 'success' : 'secondary'}>
            {dynList.some(item => item.enabled) ? '已启用' : '未启用'}
          </Badge>
        </div>

        <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,330px)_minmax(0,1fr)]">
          <div className="space-y-3">
            <div className="flex gap-2">
              {Object.keys(DYN_FIELDS).map(key => (
                <button
                  key={key}
                  onClick={() => pickDynKey(key)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    dynKey === key
                      ? 'border-[var(--accent)] bg-[var(--chip-bg)] text-[var(--text-primary)]'
                      : 'border-[var(--border-soft)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
                  }`}
                >
                  {DYN_LABELS[key] || key}
                </button>
              ))}
            </div>

            {(DYN_FIELDS[dynKey] || []).map(field => (
              <div key={field.key} className="space-y-1">
                <div className="text-[11px] text-[var(--text-muted)]">
                  {field.label}
                  {field.required && <span className="ml-1 text-red-400">*</span>}
                </div>
                {field.options ? (
                  <select
                    value={fieldValue(dynValues, field)}
                    onChange={e => setDynField(field.key, e.target.value)}
                    className="control-surface"
                  >
                    {field.options.map(option => <option key={option} value={option}>{option}</option>)}
                  </select>
                ) : (
                  <input
                    type={field.secret ? 'password' : 'text'}
                    value={fieldValue(dynValues, field)}
                    onChange={e => setDynField(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    className={`control-surface ${field.secret ? '' : 'control-surface-mono'}`}
                  />
                )}
              </div>
            ))}

            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={dynEnabled}
                onChange={e => setDynEnabled(e.target.checked)}
                className="h-3.5 w-3.5 accent-[var(--accent)]"
              />
              保存后立即启用（注册任务优先使用动态代理，每账号取 1 个出口 IP）
            </label>

            {dynMsg && (
              <div className={`rounded-lg border px-3 py-2 text-xs leading-5 ${
                dynMsg.ok
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border-red-500/30 bg-red-500/10 text-red-300'
              }`}
              >
                {dynMsg.text}
              </div>
            )}

            <div className="flex items-center gap-2">
              <Button onClick={saveDyn} disabled={dynBusy} className="flex-1">
                {dynId ? <Pencil className="h-4 w-4 mr-1.5" /> : <Plus className="h-4 w-4 mr-1.5" />}
                {dynId ? '更新配置' : '保存配置'}
              </Button>
              <Button variant="outline" onClick={testDyn} disabled={dynBusy}>
                <FlaskConical className={`h-4 w-4 mr-1.5 ${dynBusy ? 'animate-pulse' : ''}`} />
                测试
              </Button>
              {dynId && (
                <Button variant="ghost" onClick={resetDynForm} disabled={dynBusy}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          <div className="space-y-2">
            {dynList.length === 0 && (
              <div className="empty-state-panel">
                尚未配置动态代理。注册任务会回退到左侧静态代理池；配置并启用后，每次注册会自动从动态代理取一个新出口 IP。
              </div>
            )}
            {dynList.map(setting => (
              <div
                key={setting.id}
                className="rounded-lg border border-[var(--border-soft)] bg-[var(--bg-pane)]/45 px-3.5 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{DYN_LABELS[setting.provider_key] || setting.provider_key}</Badge>
                    <Badge variant={setting.enabled ? 'success' : 'danger'}>
                      {setting.enabled ? '已启用' : '已停用'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => editDyn(setting)} className="table-action-btn">
                      <Pencil className="mr-1.5 h-4 w-4" />
                      编辑
                    </button>
                    <button onClick={() => toggleDyn(setting)} className="table-action-btn">
                      {setting.enabled ? <ToggleRight className="mr-1.5 h-4 w-4" /> : <ToggleLeft className="mr-1.5 h-4 w-4" />}
                      {setting.enabled ? '停用' : '启用'}
                    </button>
                    <button onClick={() => delDyn(setting.id)} className="table-action-btn table-action-btn-danger">
                      <Trash2 className="mr-1.5 h-4 w-4" />
                      删除
                    </button>
                  </div>
                </div>
                <div className="mt-2 space-y-1 font-mono text-xs text-[var(--text-secondary)]">
                  {Object.entries({ ...(setting.config || {}), ...(setting.auth_preview || {}) }).map(([key, value]) => (
                    <div key={key} className="truncate">
                      <span className="text-[var(--text-muted)]">{key}: </span>
                      {String(value || '-')}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )
}
