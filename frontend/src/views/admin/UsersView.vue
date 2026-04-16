<script setup>
import { ref, computed, onMounted } from 'vue'
import client from '../../api/client.js'
import UserAccount from '../../components/UserAccount.vue'

// ── State ──────────────────────────────────────────────────────────────────────
const users    = ref([])
const regions  = ref([])
const loading  = ref(true)
const saving   = ref(false)
const error    = ref(null)
const search   = ref('')

// Modal state: null = closed, 'create' | 'edit'
const modal    = ref(null)
const modalUser = ref(null)   // User being edited

// ── Role config ────────────────────────────────────────────────────────────────
const ROLES = [
  { value: 'admin',    label: 'Администратор' },
  { value: 'operator', label: 'Оператор'      },
  { value: 'reviewer', label: 'Проверяющий'   },
  { value: 'viewer',   label: 'Наблюдатель'   },
]

const ROLE_STYLE = {
  admin:    { bg: '#EDE9FE', color: '#6D28D9' },
  operator: { bg: '#DBEAFE', color: '#1D4ED8' },
  reviewer: { bg: '#D1FAE5', color: '#065F46' },
  viewer:   { bg: '#F3F4F6', color: '#374151' },
}

// ── Form defaults ──────────────────────────────────────────────────────────────
function emptyForm() {
  return {
    username: '', email: '', first_name: '', last_name: '',
    password: '', role: 'viewer', mac_address: '',
    is_active: true, region_ids: [],
  }
}

const form = ref(emptyForm())

// ── Computed ───────────────────────────────────────────────────────────────────
const filteredUsers = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return users.value
  return users.value.filter(u =>
    u.username?.toLowerCase().includes(q) ||
    u.email?.toLowerCase().includes(q) ||
    u.first_name?.toLowerCase().includes(q) ||
    u.last_name?.toLowerCase().includes(q)
  )
})

// ── Load ───────────────────────────────────────────────────────────────────────
async function fetchUsers() {
  try {
    const { data } = await client.get('/admin/users/')
    users.value = data.results ?? data
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка загрузки пользователей'
  }
}

async function fetchRegions() {
  try {
    const { data } = await client.get('/regions/')
    regions.value = (data.results ?? data).filter(r => !r.is_summary)
  } catch { /* non-critical */ }
}

onMounted(async () => {
  await Promise.all([fetchUsers(), fetchRegions()])
  loading.value = false
})

// ── Modal ──────────────────────────────────────────────────────────────────────
function openCreate() {
  form.value = emptyForm()
  modal.value = 'create'
  error.value = null
}

function openEdit(user) {
  form.value = {
    username:    user.username ?? '',
    email:       user.email ?? '',
    first_name:  user.first_name ?? '',
    last_name:   user.last_name ?? '',
    password:    '',
    role:        user.role ?? 'viewer',
    mac_address: user.mac_address ?? '',
    is_active:   user.is_active ?? true,
    region_ids:  user.region_ids ? [...user.region_ids] : [],
  }
  modalUser.value = user
  modal.value = 'edit'
  error.value = null
}

function closeModal() {
  modal.value = null
  modalUser.value = null
  error.value = null
}

function toggleRegion(id) {
  const idx = form.value.region_ids.indexOf(id)
  if (idx === -1) form.value.region_ids.push(id)
  else form.value.region_ids.splice(idx, 1)
}

// ── Save ───────────────────────────────────────────────────────────────────────
async function saveUser() {
  saving.value = true
  error.value = null
  try {
    const payload = {
      username:    form.value.username,
      email:       form.value.email,
      first_name:  form.value.first_name,
      last_name:   form.value.last_name,
      role:        form.value.role,
      mac_address: form.value.mac_address,
      is_active:   form.value.is_active,
      region_ids:  form.value.role === 'viewer' ? form.value.region_ids : [],
    }
    if (modal.value === 'create') {
      payload.password = form.value.password
      const { data } = await client.post('/admin/users/', payload)
      users.value.unshift(data)
    } else {
      if (form.value.password) payload.password = form.value.password
      const { data } = await client.put(`/admin/users/${modalUser.value.id}/`, payload)
      const idx = users.value.findIndex(u => u.id === modalUser.value.id)
      if (idx !== -1) users.value[idx] = data
    }
    closeModal()
  } catch (err) {
    const data = err.response?.data
    if (data && typeof data === 'object') {
      error.value = Object.entries(data)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        .join(' | ')
    } else {
      error.value = data?.detail ?? 'Ошибка сохранения'
    }
  } finally {
    saving.value = false
  }
}

// ── Deactivate ─────────────────────────────────────────────────────────────────
async function toggleActive(user) {
  try {
    const { data } = await client.patch(`/admin/users/${user.id}/`, {
      is_active: !user.is_active,
    })
    Object.assign(user, data)
  } catch (err) {
    error.value = err.response?.data?.detail ?? 'Ошибка'
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function fullName(u) {
  const name = [u.first_name, u.last_name].filter(Boolean).join(' ')
  return name || '—'
}

function roleStyle(role) {
  return ROLE_STYLE[role] ?? { bg: '#F3F4F6', color: '#374151' }
}

function roleLabel(role) {
  return ROLES.find(r => r.value === role)?.label ?? role
}
</script>

<template>
  <div class="view-page">
    <header class="view-header">
      <h1 class="view-title">Пользователи</h1>
      <div class="header-controls">
        <input
          v-model="search"
          type="search"
          class="search-input"
          placeholder="Поиск по имени, email…"
        />
        <button class="btn-primary" @click="openCreate">+ Создать</button>
      </div>
      <UserAccount />
    </header>

    <div v-if="error && !modal" class="alert-error">{{ error }}</div>

    <div v-if="loading" class="view-loading">Загрузка…</div>

    <div v-else class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Логин</th>
            <th>ФИО</th>
            <th>Email</th>
            <th>Роль</th>
            <th>MAC-адрес</th>
            <th class="th-center">Активен</th>
            <th class="th-center">Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in filteredUsers" :key="u.id" :class="{ 'row-inactive': !u.is_active }">
            <td class="td-id">{{ u.id }}</td>
            <td class="td-mono">{{ u.username }}</td>
            <td>{{ fullName(u) }}</td>
            <td class="td-email">{{ u.email || '—' }}</td>
            <td>
              <span
                class="role-badge"
                :style="{ background: roleStyle(u.role).bg, color: roleStyle(u.role).color }"
              >{{ roleLabel(u.role) }}</span>
            </td>
            <td class="td-mono">{{ u.mac_address || '—' }}</td>
            <td class="td-center">
              <span :class="u.is_active ? 'status-active' : 'status-inactive'">
                {{ u.is_active ? '✓' : '✗' }}
              </span>
            </td>
            <td class="td-center">
              <div class="row-actions">
                <button class="btn-icon" title="Редактировать" @click="openEdit(u)">✏</button>
                <button
                  class="btn-icon"
                  :class="u.is_active ? 'btn-deactivate' : 'btn-activate'"
                  :title="u.is_active ? 'Деактивировать' : 'Активировать'"
                  @click="toggleActive(u)"
                >{{ u.is_active ? '⊘' : '↺' }}</button>
              </div>
            </td>
          </tr>
          <tr v-if="!filteredUsers.length">
            <td colspan="8" class="empty-cell">
              {{ search ? 'Ничего не найдено' : 'Нет пользователей' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="modal" class="modal-backdrop" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2 class="modal-title">
            {{ modal === 'create' ? 'Новый пользователь' : 'Редактировать пользователя' }}
          </h2>
          <button class="modal-close" @click="closeModal">✕</button>
        </div>

        <div class="modal-body">
          <!-- Row 1: username + email -->
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Логин *</label>
              <input v-model="form.username" type="text" class="form-input" autocomplete="off" />
            </div>
            <div class="form-group">
              <label class="form-label">Email</label>
              <input v-model="form.email" type="email" class="form-input" />
            </div>
          </div>

          <!-- Row 2: first_name + last_name -->
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Имя</label>
              <input v-model="form.first_name" type="text" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">Фамилия</label>
              <input v-model="form.last_name" type="text" class="form-input" />
            </div>
          </div>

          <!-- Row 3: password (create only) + role -->
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">
                {{ modal === 'create' ? 'Пароль *' : 'Новый пароль (оставьте пустым)' }}
              </label>
              <input v-model="form.password" type="password" class="form-input" autocomplete="new-password" />
            </div>
            <div class="form-group">
              <label class="form-label">Роль *</label>
              <select v-model="form.role" class="form-select">
                <option v-for="r in ROLES" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
            </div>
          </div>

          <!-- Row 4: MAC + is_active -->
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">MAC-адрес</label>
              <input
                v-model="form.mac_address"
                type="text"
                class="form-input form-mono"
                placeholder="XX:XX:XX:XX:XX:XX"
                maxlength="17"
              />
            </div>
            <div class="form-group form-group--checkbox">
              <label class="checkbox-row">
                <input v-model="form.is_active" type="checkbox" />
                <span>Активен</span>
              </label>
            </div>
          </div>

          <!-- Regions multiselect (viewer only) -->
          <div v-if="form.role === 'viewer'" class="form-group">
            <label class="form-label">Доступные регионы</label>
            <p class="form-hint">Наблюдатель видит только выбранные регионы (RLS)</p>
            <div class="region-grid">
              <label
                v-for="r in regions"
                :key="r.id"
                class="region-check"
                :class="{ selected: form.region_ids.includes(r.id) }"
              >
                <input
                  type="checkbox"
                  :value="r.id"
                  :checked="form.region_ids.includes(r.id)"
                  @change="toggleRegion(r.id)"
                />
                {{ r.name_ru }}
              </label>
            </div>
          </div>

          <div v-if="error" class="alert-error">{{ error }}</div>
        </div>

        <div class="modal-footer">
          <button class="btn-secondary" @click="closeModal">Отмена</button>
          <button class="btn-primary" :disabled="saving" @click="saveUser">
            {{ saving ? 'Сохранение…' : (modal === 'create' ? 'Создать' : 'Сохранить') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.view-page { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; }

.view-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.view-title { font-size: 18px; font-weight: 700; color: var(--color-text); flex: 1; }

.header-controls { display: flex; align-items: center; gap: 10px; }

.search-input {
  padding: 7px 12px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  width: 240px;
  outline: none;
}
.search-input:focus { border-color: var(--color-primary); }

.btn-primary {
  padding: 7px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.btn-primary:disabled { opacity: .6; cursor: default; }

.alert-error {
  margin: 12px 24px;
  padding: 8px 12px;
  background: #FEF2F2;
  color: var(--color-danger);
  border: 1px solid #FECACA;
  border-radius: var(--radius);
  font-size: 13px;
}
.view-loading { padding: 40px; text-align: center; color: var(--color-text-secondary); }

.table-wrap { padding: 16px 24px 24px; overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 13px; background: var(--color-surface); border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
.data-table th {
  background: var(--color-bg);
  padding: 9px 12px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
}
.th-center { text-align: center !important; }
.data-table td { padding: 9px 12px; border-bottom: 1px solid var(--color-border); }
.td-center { text-align: center; }
.td-id    { color: var(--color-text-secondary); font-size: 12px; }
.td-mono  { font-family: monospace; font-size: 12px; }
.td-email { font-size: 12px; color: var(--color-text-secondary); }
.empty-cell { text-align: center; padding: 32px; color: var(--color-text-secondary); }

.row-inactive { opacity: .55; }

.role-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.status-active  { color: var(--color-success); font-weight: 700; font-size: 16px; }
.status-inactive { color: var(--color-danger); font-size: 16px; }

.row-actions { display: flex; gap: 4px; justify-content: center; }

.btn-icon {
  width: 28px;
  height: 28px;
  border: 1.5px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  cursor: pointer;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all .12s;
}
.btn-icon:hover { border-color: var(--color-primary); color: var(--color-primary); }
.btn-deactivate:hover { border-color: var(--color-danger); color: var(--color-danger); }
.btn-activate:hover   { border-color: var(--color-success); color: var(--color-success); }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 16px;
}
.modal {
  background: var(--color-surface);
  border-radius: 12px;
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(0,0,0,.22);
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--color-border);
}
.modal-title { font-size: 16px; font-weight: 700; color: var(--color-primary); }
.modal-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-secondary);
  line-height: 1;
  padding: 2px 6px;
}
.modal-close:hover { color: var(--color-text); }

.modal-body {
  padding: 18px 22px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-row { display: flex; gap: 14px; }
.form-group { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.form-group--checkbox { justify-content: flex-end; padding-bottom: 2px; }
.form-label { font-size: 12px; font-weight: 600; color: var(--color-text-secondary); }
.form-hint  { font-size: 11px; color: var(--color-text-secondary); margin-top: -2px; }
.form-input, .form-select {
  padding: 7px 10px;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  outline: none;
  background: var(--color-surface);
}
.form-input:focus, .form-select:focus { border-color: var(--color-primary); }
.form-mono { font-family: monospace; }

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}

.region-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  padding: 8px;
}
.region-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 4px;
  transition: background .1s;
}
.region-check.selected { background: #EFF6FF; }
.region-check:hover    { background: #F0F7FF; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 22px;
  border-top: 1px solid var(--color-border);
}
.btn-secondary {
  padding: 7px 16px;
  background: none;
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  color: var(--color-text);
}
</style>
