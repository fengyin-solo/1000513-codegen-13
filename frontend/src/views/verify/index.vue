<template>
  <section class="page" data-module="verify">
    <header class="page-head">
      <div>
        <h2>验收确认管理</h2>
        <p class="page-desc">验收单套用模板后自动带出验收标准与结论建议；确认通过的单据可导出交付清单。下发返工不改动标准，整改后走「返修复检」。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/verify-template">管理验收项目模板</RouterLink>
        <button class="btn primary" type="button" @click="exportDelivery">导出交付清单</button>
        <button class="btn" type="button" @click="exportRows">导出全量清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <!-- 套用失败面板：单独列出没套用成功的条目 -->
    <div class="panel" v-if="failures.length">
      <div class="panel-head">
        <h3>套用失败条目（{{ failures.length }}）<span class="muted">　改完设备/模板后点重试，成功即自动补建验收单</span></h3>
        <button class="btn ghost" type="button" @click="loadFailures">刷新</button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>关联任务</th>
            <th>设备编号</th>
            <th>验收项目</th>
            <th>缺失类型</th>
            <th>缺失说明</th>
            <th>模板版本</th>
            <th>已重试</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in failures" :key="String(f.id)">
            <td>{{ f['关联任务'] }}</td>
            <td>{{ f['设备编号'] || '—' }}</td>
            <td>{{ f['验收项目'] }}</td>
            <td><span class="badge danger">{{ f['缺失类型'] }}</span></td>
            <td>{{ f['缺失说明'] }}</td>
            <td>{{ f['模板版本'] }}</td>
            <td>{{ f['重试次数'] }} 次</td>
            <td class="row-actions">
              <button class="link" type="button" @click="retryFailure(f)">重试</button>
              <button class="link" type="button" @click="dismissFailure(f)">清除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>验收单号</span>
        <input v-model="keyword" placeholder="按验收单号检索" />
      </label>
      <label class="filter-item">
        <span>关联任务</span>
        <input v-model="task" placeholder="按任务编号过滤" />
      </label>
      <label class="filter-item">
        <span>验收状态</span>
        <select v-model="status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '验收状态'">
              <span class="badge" :class="statusBadge(row.status)">{{ row.status }}</span>
            </template>
            <template v-else-if="column === '验收标准'">
              <span :title="String(row[column] ?? '')">{{ row[column] || '—' }}</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <template v-for="action in availableActions(row)" :key="action">
              <button class="link" type="button" @click="runAction(action, row)">{{ action }}</button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无验收单，可到模板页按关联任务套用生成</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条验收记录</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'" class="toast-line">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/verify'
const columns = ['验收单号', '关联任务', '设备编号', '验收项目', '验收标准', '验收结论', '结论建议', '模板版本', '验收人员', '验收日期', '验收状态']
const statuses = ['待验收', '验收中', '需返工', '已通过']

const rows = ref<Row[]>([])
const failures = ref<Row[]>([])
const total = ref(0)
const message = ref('')
const messageOk = ref(true)
const keyword = ref('')
const task = ref('')
const status = ref('')

const statCards = ref([
  { label: '待验收单据', value: 0 },
  { label: '验收中单据', value: 0 },
  { label: '已通过（可交付）', value: 0 },
  { label: '需返工项数', value: 0 },
])

function statusBadge(value: string): string {
  if (value === '已通过') return 'active'
  if (value === '需返工') return 'danger'
  if (value === '验收中') return 'pending'
  return ''
}

function availableActions(row: Row): string[] {
  // 按状态给动作，保持老流程「开始验收 → 确认通过 / 下发返工」，返工后可复检
  if (row.status === '待验收') return ['开始验收']
  if (row.status === '验收中') return ['确认通过', '下发返工']
  if (row.status === '需返工') return ['返修复检']
  return []
}

function notify(text: string, ok = true) {
  message.value = text
  messageOk.value = ok
}

function resetFilters() {
  keyword.value = ''
  task.value = ''
  status.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function exportDelivery() {
  // 交付清单只含确认通过的单据，CSV 可直接用 Excel 打开
  window.open(`${ENDPOINT}/delivery/export`, '_blank')
}

async function runAction(action: string, row: Row) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message)
    notify(payload.message)
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    notify(error instanceof Error ? error.message : '验收动作执行失败', false)
  }
}

async function reload() {
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (task.value) query.set('task', task.value)
  if (status.value) query.set('status', status.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('验收单列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    notify(error instanceof Error ? error.message : '验收单列表读取失败', false)
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const data = await response.json()
    statCards.value[0].value = data['待验收单据'] ?? 0
    statCards.value[1].value = data['验收中单据'] ?? 0
    statCards.value[2].value = data['已通过单据'] ?? 0
    statCards.value[3].value = data['需返工项数'] ?? 0
  } catch {
    // 统计失败不阻塞列表
  }
}

async function loadFailures() {
  try {
    const response = await request('/api/verify-templates/failures/list')
    if (!response.ok) return
    const payload = await response.json()
    failures.value = payload.items ?? []
  } catch {
    // 失败面板加载失败不影响主列表
  }
}

async function retryFailure(row: Row) {
  try {
    const response = await request(`/api/verify-templates/failures/${row.id}/retry`, { method: 'POST' })
    const payload = await response.json()
    notify(payload.message, payload.ok)
    await Promise.all([loadFailures(), reload(), loadStats()])
  } catch (error) {
    notify(error instanceof Error ? error.message : '重试失败', false)
    await loadFailures()
  }
}

async function dismissFailure(row: Row) {
  try {
    const response = await request(`/api/verify-templates/failures/${row.id}`, { method: 'DELETE' })
    const payload = await response.json()
    notify(payload.message, payload.ok)
    await loadFailures()
  } catch (error) {
    notify('清除失败记录失败', false)
  }
}

onMounted(() => Promise.all([reload(), loadStats(), loadFailures()]))
</script>
