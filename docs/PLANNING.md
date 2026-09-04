# AuditLake — plan del proyecto

> Documento vivo. Lo vamos actualizando a medida que tomamos decisiones. El nombre
> "AuditLake" ya está regado por la infra (contenedores, bucket, DB) así que lo
> adoptamos como nombre del proyecto — hay que cambiar `APP_NAME=Mantis Manager`
> en `apps/backend/.env` por `AuditLake` cuando entremos a código.

## 1. Qué es esto y para qué sirve

Portafolio: demo funcional de un **motor de auditoría de datos por capas**
(bronze → silver → gold), inspirado en el trabajo real de procesar y auditar
facturación de una EPS con Databricks, pero aplicado a un dominio inventado
(cadena de tiendas retail ficticia) para no depender de Spark/Databricks ni de
datos reales.

Lo que se conserva del trabajo real (lo que sí vale la pena mostrarle a un
entrevistador):
- Pipeline por capas con trazabilidad (qué llegó crudo → qué se limpió → qué se
  auditó).
- Motor de reglas: reglas **estáticas** (hardcodeadas, ej. "el total debe
  cuadrar") y reglas **dinámicas** (configurables sin tocar código, ej.
  "descuento máximo por categoría").
- Validación cruzada contra catálogos maestros (empleados, productos, sedes,
  códigos de descuento vigentes).
- Salida de auditoría explicable: qué falló, qué regla, qué severidad.

Lo que se descarta a propósito: Spark/Databricks (no aporta nada a una demo de
portafolio, y cuesta dinero desplegarlo), y datos reales de la EPS (por
confidencialidad y porque el dominio retail se entiende sin contexto médico).

## 2. Decisiones ya tomadas

| Decisión | Elegido | Por qué |
|---|---|---|
| Backend | Todo en Python (FastAPI) | Ya hay una base empezada (`apps/backend`), evita duplicar infraestructura de despliegue con NestJS |
| Frontend | React + Vite | Deploy trivial, ecosistema de tablas/gráficas maduro |
| Repo | Monorepo (`apps/backend` + `apps/frontend`) | Ya está así, no comparten código, no hace falta Nx/Turborepo |
| Procesamiento de datos | Polars, no Pandas | Su API (lazy evaluation, expresiones columnares) se parece conceptualmente a Spark — buen puente narrativo con la experiencia en Databricks. El volumen de datos de la demo es chico así que el rendimiento no es el driver real |
| ETL / motor de reglas | Módulo aislado dentro del mismo servicio backend, ejecutado como background task (threadpool), diseñado para poder aislarse a un worker propio después | No bloquear el API sin pagar por un segundo servicio desde ya |
| Deploy | Capas gratuitas primero; margen de ~$5/mes si el free tier compromete la demo | Prioridad: que el link funcione bien para un reclutador |
| Base de datos | Postgres (ya en docker-compose) | Ya está, y encaja con Neon/Supabase gratis en prod |
| Bronze/silver/gold | Tablas **Delta Lake** en el storage (vía `deltalake`/`delta-rs` + Polars), no tablas Postgres | Es lo que le da autenticidad "estilo Databricks" al proyecto — mismo formato de tabla, sin el cluster de Spark detrás |
| Consulta sobre el lake | DuckDB (`duckdb.sql(...)` directo sobre las tablas Delta) | El backend necesita servir resultados paginados/filtrados al frontend sin cargar todo a memoria ni agregar un motor aparte |
| Re-run de gold | Endpoint separado (`run-gold`) que lee el silver ya guardado + catálogos en vivo, en vez de siempre rehacer bronze→silver→gold | Los catálogos (Postgres) pueden cambiar sin que el excel cambie — gold debe poder re-auditarse sin volver a subir el archivo |
| Contenido de gold | Una fila por (factura, regla), **pase o falle** — no solo violaciones | Permite demostrar explícitamente qué se validó y pasó, no solo lo que falló |
| Stack frontend | React + Vite + TypeScript, Tailwind + **shadcn/ui**, lucide-react (íconos), TanStack Query + TanStack Table, React Router | shadcn/ui no es una dependencia cerrada (componentes que se copian al proyecto, sobre Radix) — se ve profesional sin diseñar desde cero; TanStack Query/Table encajan directo con el polling de estado y la tabla de auditoría que ya estaban planeados |
| Aislar uploads entre visitantes | Sesión anónima por navegador (UUID en localStorage, header `X-Client-Id`) — no login | La demo es pública; sin esto la lista de uploads se mezcla entre visitantes. Login real agrega fricción que no vale la pena para un portafolio — no es control de acceso, solo scoping de lista |
| Validador de columnas | Endpoint aparte (`validate-columns`) que solo lee encabezados, sin correr bronze/silver/gold | Feedback inmediato de "¿este excel tiene la forma correcta?" sin comprometerse a procesar el archivo completo |

## 3. Dominio ficticio: "Retail Chain Co."

Catálogos maestros (capa de referencia, se siembran una vez — *seed data*):

- **Sedes**: id, nombre, ciudad, región, fecha_apertura, activa
- **Trabajadores**: id, nombre, sede_id, cargo, fecha_ingreso, activo
- **Productos**: sku, nombre, categoría, precio_lista, costo
- **Códigos de descuento**: código, tipo (%, valor fijo), vigencia_inicio,
  vigencia_fin, sede_aplicable (o global), categorías_aplicables (o
  general), uso_máximo
- **Transferencias** entre sedes: id, producto_sku, sede_origen, sede_destino,
  cantidad, fecha
- **Compradores**: código, nombre — catálogo simple, opcional en la
  factura (ver decisión abajo)

Lo que se sube y se audita (excel de 2 hojas, **facturas multi-ítem** —
decisión 2026-09-03, ver detalle abajo):

- **Cabecera** (`facturas`): número_factura, fecha, sede_id, trabajador_id,
  comprador_id (opcional), método_pago, iva_pct, total_factura.
- **Ítems** (`items`): número_factura (FK a la cabecera), producto_sku,
  cantidad, precio_unitario, código_descuento (opcional), total_item.

**Decisión — facturas multi-ítem, no una fila = una venta (2026-09-03)**:
el modelo original tenía una fila de excel = una venta completa (un solo
producto). Se rediseñó a cabecera + ítems para acercar el demo a un caso
real de retail (una factura con varios productos) y para poder validar
algo que antes el dominio no podía expresar: que el total registrado de
la factura cuadre contra la suma de sus ítems (más IVA) — la misma
reconciliación de totales que se hace en auditoría real de facturación,
ahora con dos niveles (`item_cuadra` por ítem, `factura_total_cuadra` a
nivel de cabecera). Es un cambio que rompe el formato de excel anterior
a propósito — no hay compatibilidad hacia atrás, es un proyecto de
portafolio sin usuarios en producción.

**Decisión — comprador es WARNING, no ERROR (2026-09-03)**: en retail
real, muchas ventas de mostrador no tienen comprador identificado — no
registrar uno no es un error de auditoría. Si se registra un código que
no existe en el catálogo, eso sí es una señal real (dato mal cargado o
comprador no dado de alta), pero sigue siendo WARNING y no ERROR porque
no bloquea la validez de la venta en sí, a diferencia de por ejemplo una
sede o trabajador inexistente.

## 4. Reglas del motor

**Estáticas — implementadas (2026-09-01, rediseñadas a cabecera/ítem
2026-09-03)**: 18 reglas en `domain/rules/engine.py` (9 de cabecera + 9
de ítem). Catálogo completo (nombre exacto, severidad, tipo
endógena/exógena, y qué valida cada una) en `docs/DATA_MODEL.md` § Gold
— no se duplica acá para no desincronizarse. Dos limitaciones conocidas,
a propósito, por alcance/tiempo:
- `item_duplicado_en_factura` (antes `factura_no_duplicada`) solo
  compara **dentro de la misma factura**, no contra auditorías
  anteriores (haría falta una tabla de facturas históricas cross-job).
- `cantidad_dentro_de_transferencias` es un chequeo simplificado (suma
  total histórica, no un balance temporal ordenado por fecha) — se decidió
  así a propósito para no meterse en esa complejidad en esta primera
  vuelta.

**Dinámicas — hecho (fase 7, 2026-09-03)**: configurables desde
`/app/rules` sin tocar código ni redeploy, guardadas en la tabla
Postgres `rule_definitions`. Cubren los dos casos que se habían dejado
planteados acá:
- Descuento máximo permitido por categoría de producto → regla tipo
  UMBRAL, campo `descuento_pct`, `filtro_categoria`.
- Sedes "en mantenimiento" que no deberían tener ventas en un rango de
  fechas → regla tipo VENTANA_EXCLUSION.

**Decisión — DSL tabular propio de dos tipos, no JSONLogic
(2026-09-03)**: se evaluó JSONLogic (`json-logic-py`, más expresivo,
condiciones anidadas AND/OR) contra un DSL tabular fijo (UMBRAL: campo +
operador + valor, con filtros opcionales de categoría/sede;
VENTANA_EXCLUSION: sede + rango de fechas). Se eligió el DSL tabular
por dos razones: (1) se traduce 1:1 a expresiones de Polars
(`domain/rules/dynamic.py`), consistente con que el motor estático ya es
vectorizado — JSONLogic hubiera necesitado su propio evaluador aparte,
fila por fila o traducido a mano; (2) es mucho más fácil de convertir en
un formulario simple (selects) que un árbol lógico genérico, y el
usuario quería poder demostrar "creo una regla desde la UI" en vivo en
una entrevista — la UI importaba tanto como el motor. Las reglas
dinámicas producen filas con el mismo esquema de gold que las 18
estáticas (comparten `construir_resultado()`), así que conviven en la
misma tabla plana y el dashboard/matriz/export ya las soportan sin
cambios de código — solo agregaban por lo que viniera en la columna
`regla`, no por una lista fija de nombres.

## 5. Arquitectura de capas — estilo lakehouse, sin Spark

Bronze, silver y gold viven como **tablas Delta Lake** sobre el mismo
storage S3-compatible (MinIO local / Cloudflare R2 en prod) — no como
tablas de Postgres. Esto se logra sin Spark con:

- **`deltalake`** (bindings de Rust, `delta-rs`) + **Polars**
  (`df.write_delta(path, mode=...)`, `pl.scan_delta(path)`) para leer y
  escribir las tablas Delta.
- **DuckDB** (tiene extensión `delta`) como motor de consulta cuando el
  backend necesita servirle al frontend resultados paginados/filtrados —
  SQL directo sobre el lake (`duckdb.sql("SELECT * FROM delta_scan(...)
  WHERE severity = ?")`), sin mover los datos a otra base ni cargar todo a
  memoria.

Capas, todas bajo `s3://{bucket}/jobs/{job_id}/...`:

- **Bronze**: el excel crudo tal cual se subió (el archivo original) +
  una tabla Delta con los datos volcados sin tipar (todo texto), para
  trazabilidad total. Cero validación acá.
- **Silver**: parseo y tipado (fechas, números), validación **estructural**
  contra el esquema esperado (columnas faltantes, tipos inválidos, nulos en
  campos obligatorios) — filas problemáticas quedan marcadas, no se
  descartan. Acá también se "ingesta" hacia Delta un snapshot de los
  catálogos maestros vigentes al momento de la corrida (sedes, trabajadores,
  productos, descuentos, transferencias), igual que un pipeline real trae
  sus dimensiones desde un sistema transaccional.
- **Gold**: resultado de correr el motor de reglas sobre silver — una fila
  por (factura, regla evaluada), con severidad (INFO/WARNING/ERROR) y
  mensaje. Es lo que el backend expone al frontend vía DuckDB.

**Qué se queda en Postgres** (el "plano de control", no el lake):
- `uploads`/`jobs`: estado del pipeline.
- Catálogos maestros: son datos operacionales/CRUD, su fuente de verdad
  tiene sentido que sea relacional — se snapshot-ean hacia silver en cada
  corrida, no viven como Delta directamente.
- `rule_definitions`: las reglas dinámicas configurables desde el frontend.

Complejidad que esto agrega (a tener presente): hay que aprender la API de
`deltalake`/Polars para escribir/leer contra un endpoint S3-compatible
(configurar `storage_options` para MinIO local vs R2 en prod), y sumar
`deltalake` + `duckdb` como dependencias nuevas. Si en algún momento se
vuelve muy pesado para el tiempo disponible, la salida de emergencia es
degradar silver/gold a tablas Postgres normales sin tocar el resto del
diseño (bronze en storage crudo se mantiene igual de cualquier forma).

## 6. Backend — estado actual y piezas a construir

> La organización del código (`domain/infrastructure/api`) está documentada
> en `ARCHITECTURE.md` — esta sección es sobre qué funcionalidad existe, no
> sobre cómo está estructurada.

**Ya existe y funciona** (`api/uploads/` + `infrastructure/db/uploads/` +
`infrastructure/storage/`): flujo de upload con URL presignada a MinIO
(`POST /uploads/request-upload-url` → el frontend sube el excel directo a
MinIO con esa URL, sin pasar por el backend) + registro en Postgres con
estados `REQUESTED → UPLOADED → PROCESSING → COMPLETED/FAILED` (los estados
ya existen en el enum de `domain/uploads.py`, falta usarlos todos). Settings
vía `.env` + pydantic-settings, engine de SQLAlchemy, cliente de MinIO que
autocrea el bucket. Es genuinamente reusable tal cual para bronze — **no
hace falta reiniciar el backend**, se sigue construyendo desde ahí.

**Limpieza ya hecha** (2026-09-01):
- Arreglado bug en `services.py` (bloque duplicado al final que rompía el
  import).
- Borrado `shared/container.py`: era un contenedor de inyección de
  dependencias que nunca se conectó — el router usa `UploadService(db)`
  directo, y el container llamaba `UploadService(minio, repository)` con una
  firma que no coincidía. Código muerto e inconsistente, mejor eliminarlo
  que mantenerlo confundiendo.
- Congelado `apps/backend/requirements.txt` (no existía) desde el venv
  actual: fastapi, sqlalchemy, psycopg, minio, pydantic-settings, uvicorn.
  Falta agregar `polars`, `deltalake`, `duckdb`, `fastexcel` (leer xlsx),
  `xlsxwriter` (generar el xlsx de demo), `faker` cuando entremos a esas
  piezas.
- Reorganizado de "package by feature" a capas (`domain/infrastructure/api`)
  — detalle y razones en `ARCHITECTURE.md`.
- Probado el flujo de upload end-to-end con `docker-compose up` (request URL
  → PUT a MinIO → confirm → status → list) — funciona. Dos ajustes de
  entorno en el camino: Postgres de este proyecto movido al puerto **5433**
  (5432 lo ocupa otro proyecto local, `siniestros-db-local`) en
  `docker-compose.yml`/`.env`; instalado `psycopg[binary]` en vez de
  `psycopg` puro (necesita `libpq` del sistema, que no está en esta
  máquina Windows).

**Catálogos maestros — hecho** (2026-09-01): `domain/catalog.py` (enums
`TipoDescuento`, `Categoria`) + `infrastructure/db/catalog/` (modelos
SQLAlchemy con FK reales entre sí + repositorio) + `scripts/seed_catalog.py`
(Faker, seed fijo `42`, reproducible — borra y repuebla). Usa códigos
legibles como llave primaria (`TDA-001`, `EMP-0042`, `ELEC-0007`,
`VERANO2026`), no UUIDs — son justo los que van a aparecer como columnas
foráneas en el Excel de ventas, igual que los códigos internos de
medicamentos/procedimientos en la EPS. Sembrado: 12 sedes (2 inactivas),
90 trabajadores (~8% inactivos), 70 productos en 7 categorías, 15 códigos
de descuento (mezcla de vigentes/vencidos/futuros, globales/por sede — a
propósito, para que el motor de reglas tenga qué detectar), 250
transferencias entre sedes.

**Pipeline bronze — hecho** (2026-09-01): `domain/pipeline/bronze.py`
(`to_bronze()`, pura — recibe los bytes del excel, devuelve un
`DataFrame` de Polars con **todas** las columnas como texto, sin tipar ni
validar nada) + `infrastructure/storage/lake.py` (`write_delta()` /
`read_delta()`, Polars + `deltalake` contra el bucket S3-compatible,
`storage_options` con `AWS_ALLOW_HTTP`/`AWS_S3_ALLOW_UNSAFE_RENAME` para
que funcione contra MinIO) + `api/audits/` (`POST /audits/{id}/run`
dispara el pipeline en background vía `BackgroundTasks` sin bloquear la
respuesta; `GET /audits/{id}/bronze` para consultar el resultado).
Probado end-to-end: excel de 3 filas → tabla Delta real en `jobs/{id}/bronze/`
(con su `_delta_log/` — se verificó que es Delta de verdad, no un parquet
suelto). El archivo crudo vive aparte, en `jobs/{id}/upload/{filename}` —
`upload/bronze/silver/gold` quedan como hermanos al mismo nivel (ver
convención de rutas en `ARCHITECTURE.md`). `UploadModel` ahora guarda
`object_name` explícito (antes se reconstruía la ruta a mano en dos sitios).
`scripts/make_sample_excel.py` genera un excel de prueba mínimo con
códigos reales del catálogo — no es el generador sintético de la fase 5
(ese inyecta errores a propósito), solo un fixture para probar el pipeline
a mano. `scripts/inspect_delta.py <object_key>` para leer cualquier tabla
Delta desde la terminal sin pasar por la API.

**Pipeline silver — hecho** (2026-09-01; rediseñado a cabecera/ítem
2026-09-03, ver esa entrada más abajo): `domain/ventas.py` (esquema de
`Factura`/`ItemFactura`: `MetodoPago` + columnas requeridas/opcionales —
documentado en detalle en `docs/DATA_MODEL.md`) + `domain/pipeline/silver.py`
(`to_silver_facturas()`/`to_silver_items()`, puras — tipan cada columna,
marcan filas inválidas en `_errores`/`_es_valida` sin descartarlas; si
faltan columnas obligatorias por completo lanzan `SilverSchemaError` en
vez de intentarlo fila por fila).
Encadenado en `AuditService.run_pipeline` (bronze → silver); nuevo
`GET /audits/{id}/silver`. Probado con datos rotos a propósito (factura
vacía, fecha inválida, cantidad negativa/no entera, método de pago
inventado) — cada error se detecta individualmente y la fila queda
marcada, no descartada. Esas pruebas ahora son código real en
`apps/backend/tests/` (`pytest`, 18 tests) — correr con
`python -m pytest -v` desde `apps/backend`, ver `ARCHITECTURE.md` § Tests.

**Pipeline gold — hecho** (2026-09-01; motor rediseñado a 18 reglas
cabecera/ítem 2026-09-03): `domain/rules/{types,engine}.py` (catálogo
completo en `docs/DATA_MODEL.md`) +
`domain/pipeline/gold.py` (delgado, solo orquesta) +
`infrastructure/db/catalog/snapshot.py` (catálogos de Postgres → Polars).
`AuditService.run_gold` separado de `run_pipeline` a propósito — lee el
silver ya guardado + catálogos en vivo, así se puede re-auditar sin
resubir el excel (ver tabla de decisiones §2). Nuevos
`POST /audits/{id}/run-gold` y `GET /audits/{id}/gold`. Solo al terminar
gold se marca `UploadStatus.COMPLETED`. Probado end-to-end: el motor
detectó una inconsistencia real en el excel de prueba (un empleado
puesto a mano en la sede equivocada) — se corrigió el fixture, no la
regla, buena señal de que el motor funciona.

**Generador sintético — hecho** (2026-09-01; reescrito para facturas
multi-ítem 2026-09-03): `domain/demo/generator.py` (`generar_ventas()`,
pura salvo el uso de `random`/`date.today()` con `seed`/`hoy` opcionales
para tests deterministas) construye facturas (1-5 ítems cada una, con
productos elegidos sin reemplazo por factura) contra los catálogos
reales sembrados, e inyecta con probabilidad `error_rate` **una**
violación por factura desde un pool de 26 mutadores (14 de cabecera + 12
de ítem) — uno por cada regla de silver/gold, con el mismo nombre exacto
(`sede_existe`, `item_cuadra`, etc.) para poder comparar "lo inyectado"
contra "lo que gold detectó" después de subir el archivo. Soporta hasta
50,000 facturas por llamada (`facturas` en el request, tope validado en
el schema) — el hot path por factura no llama a Polars (todo
precomputado una vez en `_Prepared` dentro del generador). `POST /demo/generate-excel`
(`api/demo/`) sube el excel a `demo/` en el bucket (no crea un registro de
upload — eso lo decide el usuario subiéndolo por el flujo normal) y
devuelve una URL de descarga prefirmada + el detalle de qué se inyectó.

Dos bugs reales que salieron al validar el generador contra datos
sembrados de verdad (no del generador en sí, de las piezas de abajo):
- `codigo_descuento_vigente` comparaba contra "hoy" en vez de contra la
  fecha de la venta — corregido en el generador.
- `cantidad_dentro_de_transferencias` disparaba en el 74% de filas
  *limpias* porque solo 250 transferencias cubrían de verdad ~25% de las
  840 combinaciones sede×producto posibles — corregido en
  `scripts/seed_catalog.py` (ahora hay una transferencia base garantizada
  por cada combinación, 840 + 200 extra).
- Bonus: `codigo_descuento_existe` fallaba para filas sin ningún
  descuento cuando el valor era `""` en vez de `null` — el excel real
  nunca llega así (una celda vacía se lee como `null`), pero el motor
  debía tratarlos igual de todas formas, según lo documentado en
  `DATA_MODEL.md`. Corregido en `domain/rules/engine.py`.

Nota honesta (documentada en el propio generador): el conteo de errores
inyectados es una aproximación por lo bajo — algunas mutaciones causan
cascadas lógicas reales en otras reglas (ej. una sede inexistente también
hace fallar `trabajador_pertenece_a_sede`), así que gold puede detectar
más violaciones de las que el generador contó. Verificado end-to-end
varias veces: cada discrepancia rastreada resultó ser una cascada real,
no un bug.

**Consulta paginada de gold vía DuckDB — hecho** (2026-09-02):
`infrastructure/storage/duckdb_query.py` (`query_gold()`, `summary_gold()`)
corre SQL real contra la tabla Delta de gold — `GET /audits/{id}/gold/query`
(filtros `severidad`/`regla`/`sede_codigo`/`paso` + `limit`/`offset`) y
`GET /audits/{id}/gold/summary` (conteo por regla/severidad/paso, para
poblar filtros en el frontend). Probado contra 750,000 filas (50,000
facturas × 15 reglas): agregación en 0.74s, página filtrada en 0.06s.
Detalle importante: la extensión `delta` de DuckDB **no** respeta las
variables legacy `SET s3_endpoint=...` — intenta resolver credenciales vía
IMDS (metadata service de EC2) si no hay un `CREATE SECRET` configurado, y
eso truena contra MinIO local. Hay que usar `CREATE SECRET` (mecanismo
actual de DuckDB), no las `SET s3_*` de siempre.

Bonus de este trabajo: al consultar gold con SQL real aparecieron filas
con `paso = null` (ni true ni false) en `codigo_descuento_vigente` —
`fecha` inválida (ya marcada por silver) + un código de descuento real
hacía que la comparación de vigencia diera `null` en vez de caer a algún
lado. Corregido en `domain/rules/engine.py` con el mismo patrón de guardas
que ya usaban `fecha_no_futura`/`fecha_posterior_a_apertura`.

Falta (todo lo demás):
- Reglas **dinámicas** (JSONLogic/DSL + tabla `rule_definitions`
  editable desde frontend) — fase 7, ver §4.
- Tabla `jobs` (o reusar `uploads` con más estados) para que el frontend
  haga polling de progreso más granular que solo
  REQUESTED→UPLOADED→PROCESSING→COMPLETED/FAILED.

## 7. Frontend — stack y pantallas

**Stack** (ver tabla de decisiones §2): React + Vite + TypeScript, Tailwind
+ shadcn/ui (Radix, preset Nova — Lucide + Geist), TanStack Query, React
Router. `TanStack Table` instalada pero sin usar todavía — la tabla de gold
pagina en el servidor, no le hacía falta; queda lista para cuando una
tabla necesite ordenar en memoria de verdad.

**Pantallas — hecho** (2026-09-02):
1. **Landing** (`pages/landing-page.tsx`, ruta `/`): explica el proyecto —
   qué es, de dónde viene la idea (motores de reglas reales de auditoría
   de datos transaccionales de alto volumen, reimaginados sin Spark ni
   datos reales — copy genérico a propósito, ver decisión de portafolio
   más abajo), el patrón de capas, cómo valida una regla
   (endógena/exógena), el stack. CTA a `/app`.
2. **Home** (`pages/home-page.tsx`, ruta `/app`): generar excel sintético
   (facturas + error_rate) o subir uno propio — ambos caen al mismo flujo
   `request-upload-url → PUT → confirm`. Lista de uploads recientes con
   polling (`refetchInterval`), **scoped a la sesión anónima** (ver abajo).
3. **Detalle del job** (`pages/job-detail-page.tsx`, ruta `/jobs/:id`):
   chequeo rápido de columnas apenas se sube (`components/app/column-check.tsx`,
   `GET /uploads/{id}/validate-columns` — no corre bronze/silver/gold, solo
   compara encabezados). Un botón corre bronze→silver→gold completo,
   esperando de verdad a que cada capa exista (mismo arreglo que ya tenía
   `viewer.html`). Pestañas bronze/silver (preview simple) y gold
   (`components/app/gold-table.tsx`, filtros + paginación real contra
   `GET /audits/{id}/gold/query` + `/gold/summary`).

**Sesión anónima por navegador — hecho** (2026-09-02): sin login. El
frontend genera un UUID en el primer load (`lib/session.ts`, localStorage)
y lo manda como header `X-Client-Id` en cada request
(`lib/api.ts`). El backend filtra `GET /uploads/` por ese ID — cada
visitante de la demo pública ve solo lo suyo. Sin header (curl, scripts,
`viewer.html`) cae a un bucket `"anonymous"` compartido, no rompe nada
existente. Es scoping de lista para UX, **no** control de acceso: con el
`upload_id` exacto, cualquiera sigue pudiendo consultar ese job por los
demás endpoints — suficiente para una demo, no para datos sensibles.

**Tema morado** — hecho (2026-09-02): mismo shadcn/ui, solo se
recolorearon los tokens `primary`/`ring`/`accent`/`sidebar`/`chart` a un
violeta (`oklch(~0.5-0.7 ~0.2 292)`) en `index.css`, claro y oscuro.
Fondos y texto se quedan neutros a propósito — el acento aparece en
botones/foco/estados destacados, no en todas partes.

Probado en navegador de verdad (Playwright): sin errores de consola, carga
contra datos reales (750,000 filas de gold, 50,000 facturas), filtros y
paginación correctos, build de producción limpio, flujo completo desde la
landing hasta gold verificado clic a clic.

**Modo oscuro + i18n** — hecho (2026-09-02): botón en el header togglea
la clase `.dark` (`lib/theme.tsx`, `ThemeProvider`/`useTheme`), persiste
en `localStorage` y un script inline en `index.html` la aplica antes de
que React monte (evita el flash de tema incorrecto). En paralelo, un
i18n propio y liviano (sin `react-i18next`: `i18n/translations.ts` +
`lib/i18n.tsx`, contexto + interpolación `{placeholder}`) traduce toda
la UI estática (landing, home, detalle de job) a inglés por defecto,
con español disponible vía otro botón en el header; el locale también
se persiste en `localStorage`. Decisión explícita: los datos que genera
el backend (nombres de reglas, mensajes de gold, códigos de catálogo)
se quedan en español a propósito — es el idioma real del dominio
ficticio, no texto de interfaz.

Falta: **reglas dinámicas** (opcional, fase 2 del frontend) — pantalla
para ver/editar umbrales y volver a procesar sin re-subir.

## 8. Datos sintéticos

Script Python (Faker + numpy) que:
- Siembra los catálogos maestros una sola vez (fixtures fijos, reproducibles
  con seed).
- Genera excels de ventas parametrizables: filas, rango de fechas,
  `error_rate` (probabilidad de violar cada regla a propósito), para poder
  mostrar en la demo "sube este excel con 10% de errores" y "este otro
  limpio".

## 9. Deploy (capas gratuitas primero)

- **Frontend**: Vercel (gratis).
- **Backend**: Render free web service (o Fly.io) — se duerme tras
  inactividad, aceptable para demo de portafolio con una nota de "puede
  tardar ~30s en despertar".
- **Postgres**: Neon (gratis, sin el límite de 90 días que tiene el Postgres
  free de Render).
- **Storage**: Cloudflare R2 (10GB gratis, API compatible con S3/MinIO —
  no hay un adapter por proveedor: el mismo `infrastructure/storage/
  lake.py` (`deltalake`/Polars) y `minio_client.py` (SDK `minio`) sirven
  local y en prod, cambiando solo variables de entorno). **Verificado
  (2026-09-04)**: escritura + lectura de una tabla Delta real (confirmando
  `_delta_log/` con un commit `WRITE` genuino, `delta-rs:py-1.6.3`) y
  subida/descarga/URL-prefirmada de objetos, corriendo el código real de
  la app (no un script aparte) contra un bucket R2 de prueba. Encontrado
  en el camino: `secure=False` estaba hardcodeado en `minio_client.py` y
  `lake.py` armaba el endpoint siempre con `http://` — ambos asumían
  HTTP, y R2 es HTTPS-only. Corregido agregando dos settings nuevos
  (`MINIO_SECURE: bool`, default `False` = comportamiento local actual;
  `MINIO_REGION: str`, default `"us-east-1"`) — en prod contra R2 basta
  con `MINIO_SECURE=true` y `MINIO_REGION=auto`. Ya no es la pieza menos
  probada del plan de deploy.
- **Fallback si el cold-start del free tier arruina la primera impresión**:
  VPS barato (DigitalOcean/Hetzner ~$5/mes) corriendo el `docker-compose.yml`
  que ya existe casi tal cual — reusa toda la infra que ya armaste, sin
  cold starts, y justifica el gasto si de verdad ayuda a conseguir trabajo.

## 10. Fases sugeridas

1. ✅ Arreglar `services.py`, terminar el flujo de upload end-to-end (subir →
   confirmar → ver estado).
2. ✅ Catálogos maestros + seed data.
3. ✅ Capa bronze + silver (parseo/tipado, sin reglas de negocio aún).
4. ✅ Motor de reglas estáticas + capa gold + endpoint para consultar resultados.
5. ✅ Generador de excels sintéticos con `error_rate`.
6. ✅ Frontend: subir/generar, ver progreso, ver tabla de auditoría, matriz
   resumen, detalle de factura, dashboard ejecutivo, export de facturas
   problemáticas a excel (ver §7) — creció bastante más allá del alcance
   original de la fase, incluyendo el rediseño a facturas multi-ítem (§3).
7. ✅ Reglas dinámicas editables desde el frontend (`/app/rules`, DSL
   tabular propio, ver §4).
8. Deploy en capas gratuitas, ajustar si hace falta el VPS de $5.

## 11. Abierto / por decidir más adelante

- `item_duplicado_en_factura` y `cantidad_dentro_de_transferencias` tienen
  alcance limitado a propósito (ver §4) — revisar si vale la pena
  profundizarlas antes del deploy final, o dejarlas así y ser explícito
  sobre la limitación en la demo/README.
- Nombre final del proyecto para el portafolio (ahora mismo: AuditLake).
