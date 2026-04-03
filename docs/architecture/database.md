# База данных — Модели и связи

## Схема связей

```
Region (20 ДГД + КГД)
  ├── UserRegion ←→ User (RLS для viewer)
  ├── CompletedInspection (завершённые проверки)
  ├── ActiveInspection (проводимые проверки)
  ├── AppealDecision (обжалования)
  ├── ManualInput (ручные вводы: КБК, штат)
  ├── KPIResult (результат одного KPI)
  └── KPISummary (итог 6 KPI + ранг)
          └── ReportApproval (история утверждений)

ImportJob
  ├── CompletedInspection
  ├── ActiveInspection
  └── AppealDecision

KPIFormula (версионированные конфиги)
  └── KPIResult

User
  ├── UserRegion
  ├── AuditLog
  ├── ImportJob (started_by)
  ├── ManualInput (entered_by)
  └── KPIResult (calculated_by)
```

---

## apps/core

### User
| Поле | Тип | Описание |
|------|-----|---------|
| username | CharField | Логин |
| role | CharField | admin / operator / reviewer / viewer |
| mac_address | CharField | MAC для привязки устройства (может быть пустым) |
| regions | M2M → Region | через UserRegion (только для viewer) |

### UserRegion
| Поле | Тип | Описание |
|------|-----|---------|
| user | FK → User | |
| region | FK → Region | |
| unique_together | (user, region) | |

### AuditLog
| Поле | Тип | Описание |
|------|-----|---------|
| user | FK → User | SET_NULL |
| event | CharField | import / formula_change / kpi_calc / login / logout / export / manual_input / correction / user_mgmt / approval |
| details | JSONField | Детали события |
| ip_address | GenericIPAddressField | |
| mac_address | CharField | |
| created_at | DateTimeField | auto_now_add |

---

## apps/regions

### Region
| Поле | Тип | Описание |
|------|-----|---------|
| code | CharField(4) | '06xx', '62xx', unique |
| name_ru | CharField | Русское название |
| name_kz | CharField | Казахское название |
| name_en | CharField | Английское название |
| is_summary | BooleanField | True только для КГД |
| order | PositiveSmallIntegerField | Порядок сортировки |

---

## apps/etl

### ImportJob
| Поле | Тип | Описание |
|------|-----|---------|
| source | CharField | inis / isna / dgd / appeals |
| status | CharField | pending / running / done / error |
| started_by | FK → User | SET_NULL |
| started_at | DateTimeField | nullable |
| finished_at | DateTimeField | nullable |
| records_total | IntegerField | |
| records_imported | IntegerField | |
| error_message | TextField | |
| params | JSONField | date_from, date_to и др. |

### CompletedInspection
| Поле | Тип | Описание |
|------|-----|---------|
| source | CharField | inis / isna |
| source_id | CharField(100) | ID в источнике |
| import_job | FK → ImportJob | CASCADE |
| region | FK → Region | PROTECT |
| management | CharField | УНА / УКН / ... |
| form_type | CharField | ДФНО / обычная / ... |
| completed_date | DateField | Дата завершения |
| amount_assessed | BigIntegerField | Доначислено (тенге) |
| amount_collected | BigIntegerField | Взыскано (тенге) |
| is_counted | BooleanField | Флаг учёта (KPI 3) |
| is_accepted | BooleanField | Флаг принято (KPI 1, 2) |
| is_anomaly | BooleanField | Помечено оператором |
| raw_data | JSONField | Исходная запись |
| **Индексы** | | (region, management, completed_date), (is_counted, is_accepted) |
| **unique_together** | | (source, source_id) |

### ActiveInspection
| Поле | Тип | Описание |
|------|-----|---------|
| source | CharField | |
| source_id | CharField(100) | |
| import_job | FK → ImportJob | |
| region | FK → Region | |
| management | CharField | |
| case_type | CharField | Тип дела |
| prescription_date | DateField | Дата вручения предписания |
| is_counted | BooleanField | |
| raw_data | JSONField | |
| **unique_together** | | (source, source_id) |

### AppealDecision
| Поле | Тип | Описание |
|------|-----|---------|
| source_id | CharField | unique |
| import_job | FK → ImportJob | |
| region | FK → Region | |
| amount_cancelled | BigIntegerField | Отменённая сумма (тенге) |
| is_counted | BooleanField | |
| completion_date | DateField | Дата завершения акта |
| decision_date | DateField | Дата решения Апелл. комиссии |
| raw_data | JSONField | |

### ManualInput
| Поле | Тип | Описание |
|------|-----|---------|
| region | FK → Region | |
| year | PositiveSmallIntegerField | |
| kbk_share_pct | DecimalField(8,4) | Доля по 4 КБК, % |
| staff_count | PositiveSmallIntegerField | Кол-во сотрудников |
| entered_by | FK → User | SET_NULL |
| entered_at | DateTimeField | auto_now_add |
| **unique_together** | | (region, year) |

---

## apps/kpi

### KPIFormula
| Поле | Тип | Описание |
|------|-----|---------|
| kpi_type | CharField | assessment / collection / avg_assessment / workload / long_inspections / cancelled |
| version | PositiveSmallIntegerField | |
| config | JSONField | Пороги баллов |
| is_active | BooleanField | Только одна активная версия |
| created_by | FK → User | SET_NULL |
| created_at | DateTimeField | |
| **unique_together** | | (kpi_type, version) |
| **Метод** | get_active(kpi_type) | Возвращает активную версию |

**Пример config:**
```json
{
  "thresholds": [
    {"min": 100, "score": 10},
    {"min": 90,  "score": 5},
    {"min": 0,   "score": 0}
  ]
}
```

### KPIResult
| Поле | Тип | Описание |
|------|-----|---------|
| region | FK → Region | |
| kpi_type | CharField | |
| formula | FK → KPIFormula | PROTECT |
| date_from | DateField | |
| date_to | DateField | |
| plan | DecimalField(20,4) | nullable |
| fact | DecimalField(20,4) | nullable |
| percent | DecimalField(8,4) | nullable |
| score | PositiveSmallIntegerField | |
| calc_details | JSONField | Детали для аудита |
| status | CharField | draft / submitted / approved / rejected |
| calculated_by | FK → User | SET_NULL |
| **unique_together** | | (region, kpi_type, date_from, date_to, formula) |

### KPISummary
| Поле | Тип | Описание |
|------|-----|---------|
| region | FK → Region | |
| date_from | DateField | |
| date_to | DateField | |
| score_assessment | PositiveSmallIntegerField | KPI 1 |
| score_collection | PositiveSmallIntegerField | KPI 2 |
| score_avg_assessment | PositiveSmallIntegerField | KPI 3 |
| score_workload | PositiveSmallIntegerField | KPI 4 |
| score_long_inspections | PositiveSmallIntegerField | KPI 5 |
| score_cancelled | PositiveSmallIntegerField | KPI 6 |
| score_total | PositiveSmallIntegerField | Сумма |
| rank | PositiveSmallIntegerField | nullable (None для КГД) |
| status | CharField | draft / submitted / approved / rejected |
| **unique_together** | | (region, date_from, date_to) |

---

## apps/reports

### ReportApproval
| Поле | Тип | Описание |
|------|-----|---------|
| summary | FK → KPISummary | CASCADE |
| action | CharField | submit / approve / reject / recalc |
| actor | FK → User | SET_NULL |
| comment | TextField | Обязателен при reject |
| created_at | DateTimeField | |

---

## Важные правила хранения данных

- **Все суммы** — в тенге, `BigIntegerField`. Конвертировать в млн только для отображения.
- **Суммы в млн:** `amount_tg / 1_000_000`
- **Никогда** не хранить суммы в float — потеря точности.
