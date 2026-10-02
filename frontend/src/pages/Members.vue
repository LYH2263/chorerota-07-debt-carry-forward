<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <p v-if="err" class="err">{{ err }}</p>

    <h2 class="brand" style="font-size:17px;margin-top:18px">成员结余</h2>
    <table class="table">
      <thead>
        <tr><th>成员</th><th>状态</th><th>最近钉账周</th><th class="num">当前余额</th></tr>
      </thead>
      <tbody>
        <tr v-for="m in view.members" :key="m.id">
          <td><strong>{{ m.name }}</strong></td>
          <td class="muted">{{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</td>
          <td class="muted">{{ weekLabel(m.last_week_id) }}{{ m.last_frozen ? ' · 冻结' : '' }}</td>
          <td class="num" :class="fmtBalance(m.current_balance).cls">{{ fmtBalance(m.current_balance).text }}</td>
        </tr>
      </tbody>
    </table>

    <h2 class="brand" style="font-size:17px;margin-top:18px">逐周台账</h2>
    <p class="muted ledger-note">与看板同源于落钉快照；只改现行任务权重不回刷旧周。</p>
    <table class="table">
      <thead>
        <tr>
          <th>周</th><th>成员</th><th class="num">格位</th><th class="num">负载</th>
          <th class="num">均值</th><th class="num">债前</th><th class="num">债后</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(e, i) in view.entries" :key="i">
          <td class="muted">{{ weekLabel(e.week_id) }}{{ e.frozen ? ' · 冻结' : '' }}</td>
          <td>{{ memberName(e.member_id) }}</td>
          <td class="num">{{ e.slots }}</td>
          <td class="num">{{ e.load }}</td>
          <td class="num">{{ fmtNum(e.avg_load) }}</td>
          <td class="num" :class="fmtBalance(e.debt_before).cls">{{ fmtBalance(e.debt_before).text }}</td>
          <td class="num" :class="fmtBalance(e.debt_after).cls">{{ fmtBalance(e.debt_after).text }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!view.entries.length" class="muted">尚无落钉周。</p>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { fmtBalance, fmtNum } from '../format'
const view = ref({ members: [], weeks: [], entries: [] })
const name = ref('')
const err = ref('')
function memberName(id) { return view.value.members.find(m => m.id === id)?.name || '?' }
function weekLabel(id) {
  if (id === null || id === undefined) return '—'
  return view.value.weeks.find(w => w.week_id === id)?.label || ('#' + id)
}
async function load() {
  err.value = ''
  try {
    view.value = await api('/members/debts')
  } catch (e) { err.value = e.message }
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
