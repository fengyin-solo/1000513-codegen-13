<template>
  <section class="page" data-module="verify-template">
    <header class="page-head">
      <div>
        <h2>验收项目模板</h2>
        <p class="page-desc">把常用验收项目、验收标准与结论建议沉淀成模板版本；新版生效后旧版仅保留查看，生效版本可按关联任务套用到待验收单据。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">新建模板版本</button>
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
        <span>模板名称</span>
        <input v-model="keyword" placeholder="按模板名称检索" />
      </label>
      <label class="filter-item">
        <span>版本状态</span>
        <select v-model="status">
          <option value="">全部</option>
          <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th>模板名称</th>
          <th>版本号</th>
          <th>关联任务</th>
          <th>验收项目数</th>
          <th>生效日期</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td>{{ row['模板名称'] }}</td>
          <td>{{ row['版本号'] }}</td>
          <td>{{ row['适用任务'] || '—' }}</td>
          <td>{{ (row.items || []).length }}</td>
          <td>{{ row['生效日期'] || '—' }}</td>
          <td><span class="badge" :class="statusClass(row['状态'])">{{ row['状态'] }}</span></td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看</button>
            <button
              v-if="row['状态'] !== '已停用'"
              class="link"
              type="button"
              @click="openScope(row)"
            >改关联任务</button>
            <button
              v-if="row['状态'] !== '生效中'"
              class="link"
              type="button"
              :disabled="row['状态'] === '已停用'"
              @click="activate(row)"
            >{{ row['状态'] === '已停用' ? '旧版只读' : '生效此版' }}</button>
            <button
              v-if="row['状态'] === '生效中'"
              class="link"
              type="button"
              @click="openApply(row)"
            >按任务套用</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="7" class="empty-state">暂无模板，可先新建模板版本</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 个模板版本（旧版停用后只保留查看）</span>
      <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'" class="toast-line">{{ message }}</span>
    </footer>

    <!-- 模板明细 / 新建 -->
    <div v-if="detail" class="modal-mask" @click.self="closeModal">
      <div class="modal">
        <h3>{{ detail.mode === 'create' ? '新建模板版本' : `模板明细 · ${detail['模板名称']}/${detail['版本号']}` }}</h3>
        <template v-if="detail.mode === 'create'">
          <div class="form-grid">
            <label>
              <span>模板名称 *</span>
              <input v-model="detail['模板名称']" placeholder="如：信号设备验收模板" />
            </label>
            <label>
              <span>版本号 *</span>
              <input v-model="detail['版本号']" placeholder="如：V3" />
            </label>
          </div>
          <label class="form-row">
            <span>关联任务（多个用顿号分隔，留空表示不按任务限定）</span>
            <input v-model="detail['适用任务']" placeholder="如：TASK-20260901、TASK-20260902" />
          </label>
          <div class="panel-head">
            <h3>验收项目与标准 *</h3>
            <button class="btn" type="button" @click="addItem">新增一条</button>
          </div>
          <div v-for="(item, index) in detail.items" :key="index" class="item-editor">
            <div class="form-grid">
              <label>
                <span>验收项目</span>
                <input v-model="item['验收项目']" placeholder="如：道岔转换试验" />
              </label>
              <label>
                <span>适用设备类别</span>
                <select v-model="item['适用设备类别']">
                  <option value="">不分类（任务级项目）</option>
                  <option v-for="c in categoryOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
                </select>
              </label>
            </div>
            <label class="form-row">
              <span>验收标准</span>
              <textarea v-model="item['验收标准']" rows="2" placeholder="套用时原样带入验收单，下发返工后也不会被覆盖"></textarea>
            </label>
            <div class="panel-head">
              <label style="flex:1">
                <span>结论建议</span>
                <input v-model="item['结论建议']" placeholder="默认：建议通过" />
              </label>
              <button class="btn ghost" type="button" @click="removeItem(index)">删除</button>
            </div>
          </div>
        </template>
        <template v-else>
          <ul class="detail-list">
            <li><span class="k">关联任务</span><span class="v">{{ detail['适用任务'] || '不限定' }}</span></li>
            <li><span class="k">生效日期</span><span class="v">{{ detail['生效日期'] || '—' }}</span></li>
            <li><span class="k">版本状态</span><span class="v">{{ detail['状态'] }}</span></li>
          </ul>
          <table class="data-table" style="margin-top:10px">
            <thead><tr><th>验收项目</th><th>设备类别</th><th>验收标准</th><th>结论建议</th></tr></thead>
            <tbody>
              <tr v-for="(item, i) in detail.items" :key="i">
                <td>{{ item['验收项目'] }}</td>
                <td>{{ categoryLabel(item['适用设备类别']) }}</td>
                <td>{{ item['验收标准'] }}</td>
                <td>{{ item['结论建议'] }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeModal">{{ detail.mode === 'create' ? '取消' : '关闭' }}</button>
          <button v-if="detail.mode === 'create'" class="btn primary" type="button" @click="submitCreate">保存模板</button>
        </div>
      </div>
    </div>

    <!-- 修改关联任务 -->
    <div v-if="scopeTarget" class="modal-mask" @click.self="scopeTarget = null">
      <div class="modal" style="width:480px">
        <h3>调整关联任务 · {{ scopeTarget['模板名称'] }}/{{ scopeTarget['版本号'] }}</h3>
        <p class="muted">生效版本的验收项目与标准不可改；这里只能维护套用时匹配的关联任务。</p>
        <label class="form-row">
          <span>关联任务（多个用顿号分隔）</span>
          <input v-model="scopeText" placeholder="如：TASK-20260903" />
        </label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="scopeTarget = null">取消</button>
          <button class="btn primary" type="button" @click="submitScope">保存</button>
        </div>
      </div>
    </div>

    <!-- 按任务套用 -->
    <div v-if="applyTarget" class="modal-mask" @click.self="applyTarget = null">
      <div class="modal" style="width:520px">
        <h3>按任务套用 · {{ applyTarget['模板名称'] }}/{{ applyTarget['版本号'] }}</h3>
        <p class="muted">仅「待验收」状态的关联任务可套用；套用时把验收标准与结论建议复制进验收单，之后换版不影响已生成单据。</p>
        <label class="form-row">
          <span>关联任务编号 *</span>
          <input v-model="applyTaskCode" placeholder="如：TASK-20260903" list="task-options" />
        </label>
        <datalist id="task-options">
          <option v-for="t in taskOptions" :key="t" :value="t"></option>
        </datalist>
        <div v-if="applyResult" class="panel" style="margin-top:8px">
          <p :class="applyResult['套用成功'] ? 'ok-text' : 'error-text'" style="margin:4px 0">
            成功 {{ applyResult['套用成功'] }} 条，失败 {{ applyResult['套用失败'] }} 条
          </p>
          <p v-if="applyResult['套用失败']" class="muted">失败条目已在验收确认页「套用失败」面板列出，修正后可在那里重试。</p>
        </div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="applyTarget = null">关闭</button>
          <button class="btn primary" type="button" @click="submitApply">开始套用</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type TemplateRow = Record<string, any>

const ENDPOINT = '/api/verify-templates'
const statusOptions = ['待生效', '生效中', '已停用']
const categoryOptions = [
  { value: 'signal', label: '信号机' },
  { value: 'switch', label: '转辙机（道岔）' },
  { value: 'track', label: '轨道电路' },
  { value: 'interlock', label: '联锁设备' },
  { value: 'atp', label: '列车防护' },
]

const rows = ref<TemplateRow[]>([])
const total = ref(0)
const keyword = ref('')
const status = ref('')
const message = ref('')
const messageOk = ref(true)
const detail = ref<TemplateRow | null>(null)
const scopeTarget = ref<TemplateRow | null>(null)
const scopeText = ref('')
const applyTarget = ref<TemplateRow | null>(null)
const applyTaskCode = ref('')
const applyResult = ref<Record<string, any> | null>(null)
const taskOptions = ref<string[]>(['TASK-20260901', 'TASK-20260902', 'TASK-20260903'])

const stats = ref([
  { label: '生效中版本', value: 0 },
  { label: '待生效版本', value: 0 },
  { label: '历史版本（只读）', value: 0 },
])

function statusClass(value: string): string {
  if (value === '生效中') return 'active'
  if (value === '已停用') return 'retired'
  return 'pending'
}

function categoryLabel(value: string): string {
  return categoryOptions.find((c) => c.value === value)?.label ?? '不分类'
}

function notify(text: string, ok = true) {
  message.value = text
  messageOk.value = ok
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  void reload()
}

async function reload() {
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (status.value) query.set('status', status.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('模板列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    stats.value[0].value = rows.value.filter((r) => r['状态'] === '生效中').length
    stats.value[1].value = rows.value.filter((r) => r['状态'] === '待生效').length
    stats.value[2].value = rows.value.filter((r) => r['状态'] === '已停用').length
  } catch (error) {
    notify(error instanceof Error ? error.message : '模板列表读取失败', false)
  }
}

function openDetail(row: TemplateRow) {
  detail.value = { ...JSON.parse(JSON.stringify(row)), mode: 'view' }
}

function openCreate() {
  detail.value = reactive({
    mode: 'create',
    '模板名称': '',
    '版本号': '',
    '适用任务': '',
    items: [{ '验收项目': '', '适用设备类别': '', '验收标准': '', '结论建议': '建议通过' }],
  })
}

function addItem() {
  if (!detail.value) return
  ;(detail.value.items as any[]).push({ '验收项目': '', '适用设备类别': '', '验收标准': '', '结论建议': '建议通过' })
}

function removeItem(index: number) {
  detail.value?.items.splice(index, 1)
}

function closeModal() {
  detail.value = null
}

async function submitCreate() {
  if (!detail.value) return
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          '模板名称': detail.value['模板名称'],
          '版本号': detail.value['版本号'],
          '适用任务': detail.value['适用任务'],
          items: detail.value.items,
        },
      }),
    })
    const payload = await response.json()
    if (!payload.ok) throw new Error(payload.message)
    notify(payload.message)
    detail.value = null
    await reload()
  } catch (error) {
    notify(error instanceof Error ? error.message : '模板创建失败', false)
  }
}

async function activate(row: TemplateRow) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}/activate`, { method: 'POST' })
    const payload = await response.json()
    notify(payload.message, payload.ok)
    if (payload.ok) await reload()
  } catch (error) {
    notify('生效操作失败', false)
  }
}

function openScope(row: TemplateRow) {
  scopeTarget.value = row
  scopeText.value = row['适用任务'] || ''
}

async function submitScope() {
  if (!scopeTarget.value) return
  try {
    const response = await request(`${ENDPOINT}/${scopeTarget.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ values: { '适用任务': scopeText.value } }),
    })
    const payload = await response.json()
    notify(payload.message, payload.ok)
    scopeTarget.value = null
    await reload()
  } catch (error) {
    notify('关联任务更新失败', false)
  }
}

function openApply(row: TemplateRow) {
  applyTarget.value = row
  applyTaskCode.value = (row['适用任务'] || '').split('、')[0] || ''
  applyResult.value = null
}

async function submitApply() {
  if (!applyTarget.value) return
  try {
    const response = await request(`${ENDPOINT}/apply`, {
      method: 'POST',
      body: JSON.stringify({ template_id: applyTarget.value.id, task_code: applyTaskCode.value }),
    })
    const payload = await response.json()
    notify(payload.message, payload.ok)
    applyResult.value = payload.entry
  } catch (error) {
    notify(error instanceof Error ? error.message : '套用失败', false)
  }
}

onMounted(reload)
</script>
