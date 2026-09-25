<template>
  <section class="page" data-module="template">
    <header class="page-head">
      <div>
        <h2>验收项目模板</h2>
        <p class="page-desc">把常用验收项目与验收标准做成模板；验收单套用后自动带出验收标准与结论建议，换版后旧版仅保留查看。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记模板</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">生效中模板</span>
        <strong class="stat-value">{{ activeCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已停用版本</span>
        <strong class="stat-value">{{ retiredCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">套用失败待处理</span>
        <strong class="stat-value">{{ failures.length }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>模板编号/名称</span>
        <input v-model="filters.keyword" placeholder="按模板编号或名称检索" />
      </label>
      <label class="filter-item">
        <span>模板状态</span>
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
          <td>{{ row['模板编号'] }}</td>
          <td>{{ row['模板名称'] }}</td>
          <td>{{ row['版本号'] }}</td>
          <td>{{ row['条目数'] }}</td>
          <td>{{ row['生效日期'] }}</td>
          <td>
            <span class="tag" :class="row['模板状态'] === '生效中' ? 'active' : 'retired'">{{ row['模板状态'] }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="viewDetail(row)">查看条目</button>
            <template v-if="row['模板状态'] === '生效中'">
              <button class="link" type="button" @click="openUpgrade(row)">换版升级</button>
              <button class="link" type="button" @click="openApply(row)">套用模板</button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无验收模板，可先登记模板</td>
        </tr>
      </tbody>
    </table>

    <section v-if="detail" class="panel">
      <div class="panel-head">
        <h3>{{ detail['模板编号'] }} {{ detail['版本号'] }} · {{ detail['模板名称'] }} 的验收条目</h3>
        <span class="tag" :class="detail['模板状态'] === '生效中' ? 'active' : 'retired'">
          {{ detail['模板状态'] === '生效中' ? '当前生效版本' : '旧版仅保留查看' }}
        </span>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>设备编号</th><th>验收项目</th><th>验收标准</th><th>结论建议</th></tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in detail.items" :key="index">
            <td>{{ item['设备编号'] }}</td>
            <td>{{ item['验收项目'] }}</td>
            <td>{{ item['验收标准'] }}</td>
            <td>{{ item['结论建议'] }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="editing" class="panel">
      <div class="panel-head">
        <h3>{{ editing.mode === 'create' ? '登记验收模板' : `换版升级：${editing.code} ${editing.oldVersion}` }}</h3>
        <button class="btn ghost" type="button" @click="editing = null">收起</button>
      </div>
      <div class="form-grid">
        <label class="form-item">
          <span>模板编号</span>
          <input v-model="editing.form.模板编号" :disabled="editing.mode === 'upgrade'" placeholder="如 TPL-0003" />
        </label>
        <label class="form-item">
          <span>模板名称</span>
          <input v-model="editing.form.模板名称" placeholder="如 信号设备验收模板" />
        </label>
        <label class="form-item">
          <span>版本号</span>
          <input v-model="editing.form.版本号" placeholder="留空自动递增" />
        </label>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>设备编号</th><th>验收项目</th><th>验收标准</th><th>结论建议</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in editing.form.items" :key="index">
            <td><input v-model="item.设备编号" placeholder="如 SIGN-0001" /></td>
            <td><input v-model="item.验收项目" placeholder="如 信号机显示检查" /></td>
            <td><input v-model="item.验收标准" placeholder="验收判定标准" /></td>
            <td><input v-model="item.结论建议" placeholder="留空用默认建议" /></td>
            <td><button class="link" type="button" @click="removeItem(index)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <div class="panel-actions">
        <button class="btn" type="button" @click="addItem">添加条目</button>
        <button class="btn primary" type="button" @click="submitEdit">
          {{ editing.mode === 'create' ? '登记并生效' : '发布新版本' }}
        </button>
      </div>
    </section>

    <section v-if="applying" class="panel">
      <div class="panel-head">
        <h3>套用模板：{{ applying.label }}</h3>
        <button class="btn ghost" type="button" @click="applying = null">收起</button>
      </div>
      <p class="hint-text">按关联任务把模板套用到待验收单据，自动带出验收标准与结论建议；已下发返工的单据不会被覆盖。</p>
      <div class="form-grid">
        <label class="form-item">
          <span>关联任务</span>
          <input v-model="applying.task" placeholder="如 TASK-0003，留空套用全部待验收" />
        </label>
      </div>
      <button class="btn primary" type="button" @click="submitApply">执行套用</button>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>套用失败待处理（{{ failures.length }}）</h3>
        <button v-if="failures.length" class="btn" type="button" @click="retryAll">全部重试</button>
      </div>
      <p class="hint-text">以下验收单未能套用模板，请先到「验收确认」补齐设备编号或验收项目，再回来重试。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>验收单号</th><th>关联任务</th><th>设备编号</th><th>验收项目</th>
            <th>缺失项</th><th>原因说明</th><th>模板版本</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="failure in failures" :key="String(failure['验收单id'])">
            <td>{{ failure['验收单号'] }}</td>
            <td>{{ failure['关联任务'] }}</td>
            <td>{{ failure['设备编号'] || '—' }}</td>
            <td>{{ failure['验收项目'] || '—' }}</td>
            <td><span class="tag warn">{{ failure['缺失项'] }}</span></td>
            <td>{{ failure['原因说明'] }}</td>
            <td>{{ failure['模板编号'] }} {{ failure['模板版本'] }}</td>
            <td><button class="link" type="button" @click="retryOne(failure)">重试</button></td>
          </tr>
          <tr v-if="!failures.length">
            <td colspan="8" class="empty-state">当前没有套用失败的条目</td>
          </tr>
        </tbody>
      </table>
    </section>

    <footer class="page-foot">
      <span>共 {{ total }} 条验收模板记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>
type ItemForm = { 设备编号: string; 验收项目: string; 验收标准: string; 结论建议: string }

const ENDPOINT = '/api/template'
const columns = ['模板编号', '模板名称', '版本号', '条目数', '生效日期', '模板状态']
const statuses = ['生效中', '已停用']

const rows = ref<Row[]>([])
const total = ref(0)
const failures = ref<Row[]>([])
const detail = ref<Row | null>(null)
const noticeMessage = ref('')
const errorMessage = ref('')
const filters = ref({ keyword: '', status: '' })

const editing = ref<{
  mode: 'create' | 'upgrade'
  tplId: number | null
  code: string
  oldVersion: string
  form: { 模板编号: string; 模板名称: string; 版本号: string; items: ItemForm[] }
} | null>(null)

const applying = ref<{ tplId: number; label: string; task: string } | null>(null)

const activeCount = computed(() => rows.value.filter((row) => row['模板状态'] === '生效中').length)
const retiredCount = computed(() => rows.value.filter((row) => row['模板状态'] === '已停用').length)

function blankItem(): ItemForm {
  return { 设备编号: '', 验收项目: '', 验收标准: '', 结论建议: '' }
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.status) query.set('status', filters.value.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('模板列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板列表读取失败'
  }
  await loadFailures()
}

async function loadFailures() {
  try {
    const response = await request(`${ENDPOINT}/apply/failures`)
    if (!response.ok) throw new Error('失败面板读取失败')
    const payload = await response.json()
    failures.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '失败面板读取失败'
  }
}

async function viewDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('模板明细读取失败')
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板明细读取失败'
  }
}

function openCreate() {
  editing.value = {
    mode: 'create',
    tplId: null,
    code: '',
    oldVersion: '',
    form: { 模板编号: '', 模板名称: '', 版本号: '', items: [blankItem()] },
  }
}

async function openUpgrade(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('模板明细读取失败')
    const full = await response.json()
    editing.value = {
      mode: 'upgrade',
      tplId: row.id,
      code: full['模板编号'],
      oldVersion: full['版本号'],
      form: {
        模板编号: full['模板编号'],
        模板名称: full['模板名称'],
        版本号: '',
        items: (full.items ?? []).map((item: Row) => ({
          设备编号: item['设备编号'] ?? '',
          验收项目: item['验收项目'] ?? '',
          验收标准: item['验收标准'] ?? '',
          结论建议: item['结论建议'] ?? '',
        })),
      },
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板明细读取失败'
  }
}

function addItem() {
  editing.value?.form.items.push(blankItem())
}

function removeItem(index: number) {
  editing.value?.form.items.splice(index, 1)
}

async function submitEdit() {
  if (!editing.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  const { mode, tplId, form } = editing.value
  const url = mode === 'create' ? ENDPOINT : `${ENDPOINT}/${tplId}/actions`
  const values = mode === 'create'
    ? { ...form }
    : { action: '换版升级', 版本号: form.版本号, 模板名称: form.模板名称, items: form.items }
  try {
    const response = await request(url, { method: 'POST', body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message || '模板保存失败')
    noticeMessage.value = payload.message
    editing.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板保存失败'
  }
}

function openApply(row: Row) {
  applying.value = { tplId: row.id, label: `${row['模板编号']} ${row['版本号']} · ${row['模板名称']}`, task: '' }
}

async function submitApply() {
  if (!applying.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${applying.value.tplId}/apply`, {
      method: 'POST',
      body: JSON.stringify({ values: { 关联任务: applying.value.task } }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message || '模板套用失败')
    noticeMessage.value = payload.message
    applying.value = null
    await loadFailures()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '模板套用失败'
    await loadFailures()
  }
}

async function retry(entryIds: number[]) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/apply/retry`, {
      method: 'POST',
      body: JSON.stringify({ values: { entry_ids: entryIds } }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message || '重试失败')
    noticeMessage.value = payload.message
    await loadFailures()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重试失败'
  }
}

function retryOne(failure: Row) {
  void retry([Number(failure['验收单id'])])
}

function retryAll() {
  void retry(failures.value.map((failure) => Number(failure['验收单id'])))
}

onMounted(reload)
</script>

<style scoped>
.panel-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
.data-table input {
  width: 100%;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
}
</style>
