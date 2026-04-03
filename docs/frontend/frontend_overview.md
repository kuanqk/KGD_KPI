# Frontend — Vue 3 SPA

---

## Стек

- **Vue 3** + Composition API
- **Pinia** — state management
- **Vue Router** — навигация
- **Axios** — HTTP клиент с JWT interceptors
- **Leaflet.js** — карта Казахстана (GeoJSON)
- **Chart.js** — графики KPI
- **Vite** — сборка

---

## Структура

```
frontend/src/
├── api/
│   └── client.js          # Axios + auto-refresh JWT при 401
├── stores/
│   └── auth.js            # Pinia: login, logout, роль, пользователь
├── router/
│   └── index.js           # Роуты + route guards по роли
├── views/
│   ├── LoginView.vue
│   ├── DashboardView.vue  # Карта + рейтинг
│   ├── KPIDetailView.vue  # Детали KPI + Chart.js
│   ├── CompareView.vue    # Сравнение двух периодов
│   ├── ImportView.vue     # Оператор: ETL
│   ├── DataEditorView.vue # Оператор: редактирование флагов
│   ├── FormulasView.vue   # Оператор: версии формул
│   ├── CalculateView.vue  # Оператор: запуск расчёта
│   ├── ManualInputView.vue# Оператор: КБК и штат
│   ├── ApprovalView.vue   # Проверяющий: утверждение
│   ├── HistoryView.vue    # История отчётов
│   └── admin/
│       ├── UsersView.vue      # Администратор: пользователи
│       ├── AuditLogsView.vue  # Администратор: логи
│       └── ETLMonitorView.vue # Администратор: мониторинг ETL
├── components/
│   ├── KPIScoreCard.vue   # Карточка одного KPI
│   ├── KPITable.vue       # Таблица с сортировкой
│   └── KPIChart.vue       # Chart.js обёртка
└── utils/
    └── kpi.js             # KPI_TYPES, KPI_COLORS, KPI_MAX константы
```

---

## Роуты и доступ

| Путь | Компонент | Роли |
|------|-----------|------|
| `/login` | LoginView | Все |
| `/dashboard` | DashboardView | Все (RLS) |
| `/kpi/:type` | KPIDetailView | Все (RLS) |
| `/compare` | CompareView | Все (RLS) |
| `/import` | ImportView | operator |
| `/data` | DataEditorView | operator |
| `/formulas` | FormulasView | operator |
| `/calculate` | CalculateView | operator |
| `/manual-input` | ManualInputView | operator |
| `/approve` | ApprovalView | reviewer |
| `/history` | HistoryView | operator, reviewer, viewer |
| `/admin/users` | UsersView | admin |
| `/admin/logs` | AuditLogsView | admin |
| `/admin/etl` | ETLMonitorView | admin |

---

## Карта Казахастана

- **Leaflet.js** + GeoJSON (`frontend/public/kz-regions.geojson`)
- 20 регионов с центроидами (Point features, keyed по коду ДГД)
- Цветовая индикация: зелёный ≥80б, жёлтый 50–79б, красный <50б, серый = нет данных
- Клик по маркеру → `/kpi/:regionCode`
- RLS: viewer видит только свои регионы подсвеченными

---

## Auth Store (Pinia)

```javascript
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()

auth.login({ username, password })
auth.logout()
auth.user     // текущий пользователь
auth.role     // 'admin' | 'operator' | 'reviewer' | 'viewer'
auth.isAdmin  // computed
```

---

## API Client

```javascript
import api from '@/api/client'

// JWT автоматически добавляется к заголовкам
// При 401 — автоматический refresh токена
const { data } = await api.get('/kpi/summary/')
```

---

## Сборка и запуск

```bash
cd frontend
npm install
npm run dev      # разработка (Vite dev server)
npm run build    # production сборка → dist/
```

В Docker: `make build` пересобирает frontend контейнер.
