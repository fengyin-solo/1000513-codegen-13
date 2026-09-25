<template>
  <section class="page" data-module="verify">
    <header class="page-head">
      <div>
        <h2>验收确认管理</h2>
        <p class="page-desc">维护验收单，围绕验收单号、关联任务、验收项目、验收标准做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记验收单</button>
        <button class="btn" type="button" @click="exportRows">导出验收确认清单</button>
        <button class="btn" type="button" @click="exportDelivery">导出交付清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>验收单号</span>
        <input v-model="filters.keyword" placeholder="按验收单号检索" />
      </label>
      <label class="filter-item">
        <span>关联任务</span>
        <input v-model="filters.task" placeholder="按关联任务检索" />
      </label>
      <label class="filter-item">
        <span>设备编号</span>
        <input v-model="filters.device" placeholder="按设备编号检索" />
      </label>
      <label class="filter-item">
        <span>验收状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="openEdit(row)">编辑</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无验收确认数据，可先登记验收单</td>
        </tr>
      </tbody>
    </table>

    <section v-if="editing" class="panel">
      <div class="panel-head">
        <h3>{{ editing.mode === 'create' ? '登记验收单' : `编辑验收单：${editing.form.验收单号}` }}</h3>
        <button class="btn ghost" type="button" @click="editing = null">收起</button>
      </div>
      <p v-if="editing.locked" class="hint-text">该单据已下发返工或已通过，验收标准与验收结论不可修改。</p>
      <div class="form-grid">
        <label v-for="field in editing.fields" :key="field" class="form-item">
          <span>{{ field }}</span>
          <input
            v-model="editing.form[field]"
            :disabled="editing.locked && (field === '验收标准' || field === '验收结论')"
            :placeholder="`请输入${field}`"
          />
        </label>
      </div>
      <button class="btn primary" type="button" @click="submitEdit">
        {{ editing.mode === 'create' ? '登记' : '保存修改' }}
      </button>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条验收确认记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/verify'
const columns = ["验收单号", "关联任务", "设备编号", "验收项目", "验收标准", "验收结论", "验收人员", "验收日期", "验收状态"]
const actions = ["开始验收", "确认通过", "下发返工"]
const statuses = ["待验收", "验收中", "已通过", "需返工"]
const stats = [{"label": "待验收单据", "value": 0}, {"label": "本月通过数", "value": 0}, {"label": "需返工项数", "value": 0}]
const createFields = ["验收单号", "关联任务", "设备编号", "验收项目"]
const editFields = ["关联任务", "设备编号", "验收项目", "验收标准", "验收结论", "验收人员", "验收日期"]

const rows = ref<Row[]>([])
const total = ref(0)
const noticeMessage = ref('')
const errorMessage = ref('')
const filters = ref({ keyword: '', task: '', device: '', status: '' })
const editing = ref<{
  mode: 'create' | 'edit'
  entryId: number | null
  locked: boolean
  fields: string[]
  form: Record<string, string>
} | null>(null)

function resetFilters() {
  filters.value = { keyword: '', task: '', device: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function exportDelivery() {
  window.open(`${ENDPOINT}/delivery`, '_blank')
}

function openCreate() {
  editing.value = {
    mode: 'create',
    entryId: null,
    locked: false,
    fields: createFields,
    form: { 验收单号: '', 关联任务: '', 设备编号: '', 验收项目: '' },
  }
}

function openEdit(row: Row) {
  const form: Record<string, string> = {}
  for (const field of editFields) {
    form[field] = row[field] ?? ''
  }
  editing.value = {
    mode: 'edit',
    entryId: Number(row.id),
    locked: row.status === '需返工' || row.status === '已通过',
    fields: editFields,
    form: { ...form, 验收单号: row.验收单号 ?? '' },
  }
}

async function submitEdit() {
  if (!editing.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  const { mode, entryId, form } = editing.value
  const values = { ...form }
  delete values.验收单号
  if (mode === 'create') values.验收单号 = form.验收单号
  const url = mode === 'create' ? ENDPOINT : `${ENDPOINT}/${entryId}`
  try {
    const response = await request(url, {
      method: mode === 'create' ? 'POST' : 'PUT',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message || '验收单保存失败')
    noticeMessage.value = payload.message
    editing.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '验收单保存失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '验收确认动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '验收确认操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) query.set(key, value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('验收单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '验收确认列表读取失败'
  }
}

onMounted(reload)
</script>
