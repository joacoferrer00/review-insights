# Plan: Soporte multi-idioma (ES/EN) en el pipeline

## Context

Llega un cliente piloto en EEUU (cadena de supermercados) que requiere todo el entregable en inglés: PDF ejecutivo, dashboard, y outputs del LLM (resúmenes, recomendaciones, evidencia) en inglés.

Hoy el sistema está cableado en español a través de tres capas:
1. **Prompts del LLM**: los archivos `industries/<industry>/prompts/*.md` ya están escritos en inglés, pero tienen menciones hardcodeadas a "Spanish" (ej: `"title": "<max 80 chars, Spanish>"`, `Spanish only. Neutral LATAM, professional but conversational.`).
2. **PDF**: `audit_report.html` tiene ~65 strings hardcodeados en español (headers, KPIs, columnas, badges, CTA, footer).
3. **Dashboard**: `app.py` + `dashboard.py` tienen ~45 strings hardcodeados, más mapeos de sentiment/urgency con keys en español.

Objetivo: agregar un campo `language: es | en` en `clients/<slug>/config.yaml` que controle el idioma de los tres puntos arriba. La taxonomía soporta `label_es` para topics; agregamos `label_en`.

**Out of scope (PR futuro):** la nueva industria `supermarkets` con su taxonomía propia. Este PR habilita la infraestructura; la industria se construye encima.

---

## Decisiones de diseño confirmadas

1. **Prompts**: NO duplicar ni mover. Se mantienen en `industries/<industry>/prompts/*.md`. Reemplazamos las menciones hardcodeadas a "Spanish" por placeholders Jinja2 (`{{ language_name }}`) que se inyectan en runtime desde el config.
2. **PDF/Dashboard**: template único + dict de strings `{lang: {key: value}}` cargado desde YAML en `src/review_insights/i18n/`.
3. **Scope de traducción**: solo `restaurants` recibe `label_en` en la taxonomía. La infraestructura queda lista para gym/peluquerias cuando aparezca un cliente.
4. **Default**: si falta `language` en config.yaml, asumir `es` (backwards-compatible).
5. **Testing**: duplicar un cliente existente (ej. ida o panicafe) con `language: en`, correr `--skip-fetch` reusando los CSVs ya clasificados. Verifica PDF+dashboard+enrichment EN sobre data ya scrapeada. Sin gasto de Apify.

---

## Cambios por capa

### 1. Config (`src/review_insights/config.py`)

- Agregar `language: str = "es"` al dataclass `ClientConfig`
- En `load_client_config()`, leer `raw.get("language", "es")`
- Los prompt paths NO cambian (no hay subcarpeta por idioma)
- Generalizar `load_topic_labels(taxonomy_path)` → `load_topic_labels(taxonomy_path, language="es")`: devuelve `label_<lang>` por topic, fallback a `name` si no existe

### 2. Prompts — parametrización (no se mueven ni duplican)

Reemplazar en los 3 prompts de `industries/restaurants/prompts/`:
- `Spanish only` → `{{ language_name }} only`
- `<max 80 chars, Spanish>` → `<max 80 chars, {{ language_name }}>`
- `Neutral LATAM, professional but conversational` → mantener (es estilo, no idioma) o convertir a `{{ style_note }}` si querés diferenciar tono ES/EN
- Ejemplos hardcodeados como `"text_reference": "tres de las cintas..."` → mantener (son ejemplos de quotes verbatim, no afectan idioma de output)

Los 3 callers que cargan prompts pasan a renderizarlos con Jinja2:
- `src/review_insights/classification/__init__.py` (donde se carga `classification.md`)
- `src/review_insights/reporting/insight_enricher.py:51`
- `src/review_insights/reporting/report_generator.py:64`

Cada uno hace algo como:
```python
from jinja2 import Template
raw = prompt_path.read_text(encoding="utf-8")
system_prompt = Template(raw).render(language_name=LANG_NAMES[cfg.language])
```

Donde `LANG_NAMES = {"es": "Spanish", "en": "English"}` vive en `i18n/__init__.py`.

Aplicar mismo cambio a `industries/gym/prompts/*.md` y `industries/peluquerias/prompts/*.md` para que la infra sea consistente, aunque no las usemos en EN ahora.

### 3. Taxonomía — agregar `label_en` solo a restaurants

Editar `industries/restaurants/taxonomy.yaml`:
```yaml
topics:
  - name: Food Quality
    description: ...
    label_es: Calidad de comida
    label_en: Food quality
  # ... (10 topics en total)
```

Gym y peluquerias quedan como están. Si en el futuro se necesitan, agregar `label_en` cuando corresponda — el `load_topic_labels` ya hace fallback.

### 4. Módulo i18n nuevo (`src/review_insights/i18n/`)

Estructura:
```
src/review_insights/i18n/
  __init__.py          # load_strings(language) -> dict, LANG_NAMES dict
  es.yaml              # strings ES extraídos del código actual
  en.yaml              # mismas keys, en inglés
```

`load_strings(language)` lee el YAML correspondiente y devuelve un dict plano. Si la key falta, fallback a ES.

`es.yaml` contiene las claves para:
- PDF: cover (subtitle, period_label, date_label, prepared_by), section headings (summary, distribution, findings_ranked, benchmark, action_plan), KPI labels, table column headers, priority badges (high/medium/low), CTA box (heading, intro, package_name, bullets, contact_label), QR (heading, caption), footer pattern, period_default
- Dashboard: sidebar (caption_subtitle, label_business, label_data_through, label_total_reviews), tab names (summary, issues, benchmark, action_plan, data), metric cards, section headers, table column renames, multiselect labels, captions, chart axis/legend labels, sentiment display labels (positive/neutral/negative), urgency display labels (high/medium/low), download_button

`en.yaml` es la traducción 1:1.

### 5. PDF — `report_generator.py` + `audit_report.html`

**`report_generator.py`:**
- `render_pdf()` acepta nuevo param `language: str = "es"`
- Cargar strings con `load_strings(language)` al inicio
- Reemplazar `period="últimos meses"` por `strings["period_default"]`
- Formato de fecha por idioma: ES `%d/%m/%Y`, EN `%B %d, %Y`
- Pasar `t=strings` y `language=language` al template render

**`audit_report.html`:**
- Cambiar `<html lang="es">` a `<html lang="{{ language }}">`
- Reemplazar cada string hardcodeado por `{{ t.<key> }}`. Mapeo completo:
  - Cover: `t.subtitle_line1`, `t.subtitle_line2`, `t.label_period`, `t.label_date`, `t.label_prepared_by`
  - Página 2: `t.section_summary`, `t.kpi_reviews`, `t.kpi_rating`, `t.kpi_positive`, `t.kpi_negative`, `t.section_context`, `t.section_findings`, `t.section_recommendations`, `t.section_next_step`
  - Página 3: `t.section_distribution`, `t.chart_sentiment`, `t.chart_topics`
  - Página 4: `t.section_findings_ranked`, descripción → `t.findings_ranked_intro`, columnas (`t.col_num`, `t.col_topic`, `t.col_title`, `t.col_mentions`, `t.col_pct_neg`, `t.col_priority`), badges (`t.badge_high`, `t.badge_medium`, `t.badge_low`)
  - Página 5: `t.section_benchmark`, columnas (`t.col_business`, `t.col_reviews`, `t.col_avg_rating`, `t.col_pct_positive`, `t.col_pct_negative`, `t.col_high_urgency`)
  - Página 6: `t.section_action_plan`, intro → `t.action_plan_intro`, columnas (`t.col_recommended_action`), CTA (`t.cta_heading`, `t.cta_intro`, `t.cta_package`, `t.cta_bullet1/2/3`, `t.cta_contact_label`), QR (`t.qr_heading`, `t.qr_caption`)
  - Footer: `t.footer_page` con interpolación (`"Página {{n}}"` vs `"Page {{n}}"`)

### 6. Dashboard — `app.py` + `dashboard.py`

**`dashboard.py`:**
- Restructurar `SENTIMENT_COLORS` y `URGENCY_COLORS` con **keys canónicos** (`positive`/`neutral`/`negative`, `high`/`medium`/`low`), no display labels en español. Los colores son universales.
- Quitar `SENTIMENT_ES`/`URGENCY_ES`. Reemplazar por funciones que aceptan `strings` dict y devuelven el display label.
- Las funciones `chart_*` aceptan param `strings: dict` para labels de ejes, leyendas, colorbar.

**`app.py`:**
- Cargar `cfg.language` y `strings = load_strings(cfg.language)` después de resolver el config
- Reemplazar cada string hardcodeado por `strings["<key>"]`
- Las opciones de multiselect se construyen desde el dict de display labels
- El filename del Excel también se localiza si tiene texto

### 7. Pipeline — `run_pipeline.py`

- Propagar `cfg.language` a:
  - `load_topic_labels(cfg.taxonomy_path, cfg.language)` en el call a `render_pdf`
  - `render_pdf(..., language=cfg.language)`
- Los callers de prompts (classification, enrichment, exec_summary) reciben `cfg.language` para renderizar el template

---

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `src/review_insights/config.py` | Agregar `language` al dataclass, generalizar `load_topic_labels` |
| `src/review_insights/classification/__init__.py` | Renderizar prompt con Jinja2 inyectando `language_name` |
| `src/review_insights/reporting/insight_enricher.py` | Idem |
| `src/review_insights/reporting/report_generator.py` | Idem + aceptar `language`, cargar strings, parametrizar render, formato de fecha |
| `src/review_insights/reporting/templates/audit_report.html` | Reemplazar ~65 strings por `{{ t.X }}` |
| `src/review_insights/reporting/dashboard.py` | Restructurar maps por keys canónicos, aceptar `strings` en chart builders |
| `app.py` | Reemplazar ~45 strings por lookups en `strings` |
| `run_pipeline.py` | Propagar `cfg.language` a `load_topic_labels`, `render_pdf`, y a los renderers de prompts |
| `industries/restaurants/taxonomy.yaml` | Agregar `label_en` a cada topic (10 entries) |
| `industries/restaurants/prompts/{classification,enrichment,exec_summary}.md` | Reemplazar menciones a "Spanish" por `{{ language_name }}` |
| `industries/gym/prompts/*.md`, `industries/peluquerias/prompts/*.md` | Mismo cambio para consistencia (6 archivos) |

## Archivos a crear

- `src/review_insights/i18n/__init__.py`
- `src/review_insights/i18n/es.yaml`
- `src/review_insights/i18n/en.yaml`

## Archivos a mover

Ninguno.

---

## Funciones existentes a reutilizar

- `load_topic_labels` en `src/review_insights/config.py:122` — generalizar con `language` param
- `ClientConfig` en `src/review_insights/config.py:25` — extender dataclass
- `render_pdf` en `src/review_insights/reporting/report_generator.py:147` — ya tiene precedente de agregar params (`topic_labels`)
- Jinja2 ya está como dependencia (lo usa el HTML); reutilizar para renderizar prompts

---

## Orden de implementación

1. Capa de config: `language` field, `load_topic_labels(language)`
2. Módulo i18n: crear `src/review_insights/i18n/` con `__init__.py`, `es.yaml`, `en.yaml`
3. Parametrizar prompts (find-replace en 9 archivos) + renderizar con Jinja2 en los 3 callers
4. Taxonomía restaurants: agregar `label_en` a los 10 topics
5. PDF: parametrizar `audit_report.html` y `report_generator.py`
6. Dashboard: parametrizar `dashboard.py` y `app.py`
7. Pipeline: propagar `cfg.language` en `run_pipeline.py`
8. Verificación end-to-end
9. Commit

---

## Verificación

1. **Backwards compatibility (crítico):**
   ```
   python run_pipeline.py --client ida --skip-fetch
   ```
   IDA no tiene `language` en su config. Debe generar PDF y dashboard exactamente igual que antes. Comparar PDF nuevo contra el existente en `clients/ida/outputs/reports/`.

2. **Flujo EN end-to-end sin Apify:**
   - Duplicar `clients/panicafe/` → `clients/panicafe_en/` (o agregar `language: en` temporalmente a un cliente y revertir)
   - Copiar los JSONs de `0_input/` y los CSVs ya clasificados
   - Cambiar el config a `language: en`
   - `python run_pipeline.py --client panicafe_en --skip-fetch`
   - Verificar:
     - PDF: headers, KPIs, columnas, badges, CTA, footer en inglés. Topics traducidos a `label_en`. Fecha formato `Month DD, YYYY`. `<html lang="en">`.
     - Recomendaciones del LLM en inglés (porque el prompt renderizado dijo "English only")
     - Dashboard local `streamlit run app.py -- --client panicafe_en`: todo en inglés, sentiment options dicen "Positive/Neutral/Negative"

3. **Grep de strings residuales:**
   - Buscar `[áéíóúñ]` en archivos `.py` y `.html` modificados; cualquier match es un string olvidado.

---

## Riesgos y mitigaciones

- **Strings olvidados**: hardcodes residuales. Mitigación: grep de tildes/eñes después de la implementación.
- **LLM ignora la instrucción de idioma**: improbable con gemini-2.5-flash-lite pero posible. Mitigación: prompt explícito con `{{ language_name }} only` y retry x3 ya existente.
- **Drift entre `es.yaml` y `en.yaml`**: futuro cambio de string en el PDF requiere update sincronizado. Aceptable para 2 idiomas. Si crece, considerar validación automática (no en este PR).
- **Date format en EN bajo Windows locale**: `%B` puede salir en idioma del sistema si no se setea locale. Para EN, usar `date.today().strftime("%B %d, %Y")` con Python — `%B` es siempre el nombre del mes en inglés porque el default locale de Python es C/POSIX, salvo que se setee otro.
