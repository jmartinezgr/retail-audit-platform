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

## 3. Dominio ficticio: "Retail Chain Co."

Catálogos maestros (capa de referencia, se siembran una vez — *seed data*):

- **Sedes**: id, nombre, ciudad, región, fecha_apertura, activa
- **Trabajadores**: id, nombre, sede_id, cargo, fecha_ingreso, activo
- **Productos**: sku, nombre, categoría, precio_lista, costo
- **Códigos de descuento**: código, tipo (%, valor fijo), vigencia_inicio,
  vigencia_fin, sede_aplicable (o global), uso_máximo
- **Transferencias** entre sedes: id, producto_sku, sede_origen, sede_destino,
  cantidad, fecha

Lo que se sube y se audita (el "excel de ventas"):

- Ventas / facturas: número_factura, fecha, sede_id, trabajador_id,
  producto_sku, cantidad, precio_unitario, código_descuento (opcional),
  total, método_pago

## 4. Reglas del motor (ejemplos concretos)

**Estáticas** (van en código, son el "core" del negocio):
- El producto debe existir en el catálogo maestro.
- El trabajador debe existir, estar activo y pertenecer a la sede de la
  venta.
- `cantidad * precio_unitario - descuento = total` (la factura debe cuadrar).
- El precio unitario vendido no puede ser menor al costo (margen negativo)
  sin una regla dinámica que lo autorice explícitamente.
- No hay número de factura duplicado.
- La fecha de venta no es futura ni anterior a la apertura de la sede.
- La cantidad vendida de un SKU en una sede no excede lo que hay disponible
  según las transferencias registradas hacia esa sede (chequeo cruzado
  simple de inventario).

**Dinámicas** (configurables desde el frontend, sin tocar código):
- El código de descuento debe estar vigente en la fecha de venta y
  aplicable a esa sede.
- Descuento máximo permitido por categoría de producto (umbral editable).
- Lista de sedes "en mantenimiento" que no deberían tener ventas en un rango
  de fechas.

Para las dinámicas, usar algo tipo **JSONLogic** (`json-logic-py`) o un
DSL propio muy simple (condición → severidad → mensaje) guardado en Postgres,
editable desde el frontend. Esto es lo que hace que la demo se sienta
"configurable" sin meter un lenguaje de reglas complejo.

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

Falta (todo lo demás), y dónde va cada cosa según `ARCHITECTURE.md`:
- `domain/pipeline/` — funciones puras `bronze()`, `silver()`, `gold()`
  (reciben/devuelven `DataFrame`s de Polars); `infrastructure/storage/lake.py`
  hace la lectura/escritura real contra Delta, para poder testear el
  pipeline sin storage ni HTTP.
- `domain/rules/` — motor de reglas: reglas estáticas en código + reglas
  dinámicas cargadas de una tabla `rule_definitions` (JSONLogic o DSL
  propio, leída vía `infrastructure/db/`).
- Tabla `jobs` (o reusar `uploads` con más estados): REQUESTED → UPLOADED →
  PROCESSING → COMPLETED/FAILED, para que el frontend haga polling de
  progreso.
- `api/demo/generate-excel` — endpoint que genera un excel sintético de
  ventas con un parámetro `error_rate` que inyecta a propósito violaciones
  de cada regla (para que la demo se explique sola: "genera un excel,
  súbelo, mira los errores que detectó").

## 7. Frontend — pantallas

1. **Subir excel**: drag & drop, o botón "generar excel de ejemplo" con
   slider de `% de errores a inyectar` y `# de filas`.
2. **Progreso del job**: polling simple sobre `/uploads/{id}/status`.
3. **Resultado de auditoría**: tabla filtrable/paginada por severidad, tipo
   de regla, sede — con la fila original y por qué falló.
4. **Reglas dinámicas** (opcional, fase 2): pantalla para ver/editar los
   umbrales de las reglas dinámicas y volver a procesar sin re-subir.

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
- **Storage**: Cloudflare R2 (10GB gratis, API compatible con S3/MinIO — el
  mismo cliente `boto3`/`minio` sirve local y en prod, solo cambia el
  endpoint; `deltalake`/Polars también apuntan a R2 vía `storage_options`
  S3-compatible, solo hay que probar que las escrituras Delta funcionen ahí
  antes de confiar en el plan — es la pieza menos probada de todas).
- **Fallback si el cold-start del free tier arruina la primera impresión**:
  VPS barato (DigitalOcean/Hetzner ~$5/mes) corriendo el `docker-compose.yml`
  que ya existe casi tal cual — reusa toda la infra que ya armaste, sin
  cold starts, y justifica el gasto si de verdad ayuda a conseguir trabajo.

## 10. Fases sugeridas

1. Arreglar `services.py`, terminar el flujo de upload end-to-end (subir →
   confirmar → ver estado).
2. Catálogos maestros + seed data.
3. Capa bronze + silver (parseo/tipado, sin reglas de negocio aún).
4. Motor de reglas estáticas + capa gold + endpoint para consultar resultados.
5. Generador de excels sintéticos con `error_rate`.
6. Frontend: subir, ver progreso, ver tabla de auditoría.
7. Reglas dinámicas editables (si alcanza el tiempo).
8. Deploy en capas gratuitas, ajustar si hace falta el VPS de $5.

## 11. Abierto / por decidir más adelante

- ¿Reglas dinámicas con JSONLogic o un DSL propio más simple? (JSONLogic es
  la opción segura, ya madura).
- Confirmar que `deltalake` escribe/lee sin problemas contra Cloudflare R2
  (S3-compatible) antes de comprometerse con esa ruta de deploy — probar
  temprano, no dejarlo para el final.
- Nombre final del proyecto para el portafolio (ahora mismo: AuditLake).
