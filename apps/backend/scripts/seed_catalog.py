"""
Seed de catálogos maestros — datos ficticios reproducibles (seed fijo) para
la demo. Borra y vuelve a poblar sedes, trabajadores, productos, códigos de
descuento y transferencias.

Uso (desde apps/backend, con el venv activo):
    python scripts/seed_catalog.py
"""

import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from src.infrastructure.db.base import Base
from src.infrastructure.db.session import SessionLocal, engine
from src.infrastructure.db.catalog.models import (
    SedeModel,
    TrabajadorModel,
    ProductoModel,
    CodigoDescuentoModel,
    TransferenciaModel,
)
from src.domain.catalog import TipoDescuento, Categoria

SEED = 42
random.seed(SEED)
fake = Faker("es_CO")
Faker.seed(SEED)

SEDES = [
    ("TDA-001", "Retail Chain Bogotá Centro", "Bogotá", "Andina"),
    ("TDA-002", "Retail Chain Bogotá Norte", "Bogotá", "Andina"),
    ("TDA-003", "Retail Chain Medellín Poblado", "Medellín", "Andina"),
    ("TDA-004", "Retail Chain Medellín Envigado", "Medellín", "Andina"),
    ("TDA-005", "Retail Chain Cali Norte", "Cali", "Pacífica"),
    ("TDA-006", "Retail Chain Barranquilla", "Barranquilla", "Caribe"),
    ("TDA-007", "Retail Chain Cartagena", "Cartagena", "Caribe"),
    ("TDA-008", "Retail Chain Bucaramanga", "Bucaramanga", "Andina"),
    ("TDA-009", "Retail Chain Pereira", "Pereira", "Andina"),
    ("TDA-010", "Retail Chain Manizales", "Manizales", "Andina"),
    ("TDA-011", "Retail Chain Cúcuta", "Cúcuta", "Andina"),
    ("TDA-012", "Retail Chain Villavicencio", "Villavicencio", "Orinoquía"),
]
SEDES_INACTIVAS = {"TDA-011", "TDA-012"}  # cerradas / en mantenimiento

CARGOS = [
    "Vendedor",
    "Cajero",
    "Supervisor de Tienda",
    "Bodeguero",
    "Gerente de Tienda",
]

CATEGORIA_PREFIJO = {
    Categoria.ELECTRONICA: "ELEC",
    Categoria.ROPA: "ROPA",
    Categoria.HOGAR: "HOGR",
    Categoria.ALIMENTOS: "ALIM",
    Categoria.JUGUETERIA: "JUGU",
    Categoria.DEPORTES: "DEPO",
    Categoria.BELLEZA: "BELL",
}

# (nombre, costo, precio_lista) — costo siempre menor, margen positivo
PRODUCTOS_POR_CATEGORIA = {
    Categoria.ELECTRONICA: [
        ("Audífonos Bluetooth", 89000, 180000),
        ("Parlante Portátil", 60000, 140000),
        ("Cargador USB-C 20W", 25000, 60000),
        ("Smartwatch Deportivo", 150000, 320000),
        ("Televisor 43 pulgadas", 900000, 1600000),
        ("Power Bank 10000mAh", 40000, 90000),
        ("Mouse Inalámbrico", 20000, 45000),
        ("Teclado Mecánico", 80000, 160000),
        ("Cámara Web HD", 55000, 110000),
        ("Router WiFi", 70000, 150000),
    ],
    Categoria.ROPA: [
        ("Camiseta Algodón", 18000, 45000),
        ("Pantalón Jean", 55000, 120000),
        ("Chaqueta Impermeable", 90000, 190000),
        ("Vestido Casual", 60000, 130000),
        ("Tenis Urbanos", 85000, 180000),
        ("Sudadera con Capota", 50000, 110000),
        ("Medias Deportivas x3", 12000, 28000),
        ("Gorra", 15000, 35000),
        ("Correa de Cuero", 20000, 48000),
        ("Bufanda", 18000, 40000),
    ],
    Categoria.HOGAR: [
        ("Juego de Sábanas Doble", 45000, 95000),
        ("Lámpara de Mesa", 35000, 75000),
        ("Set de Ollas x5", 120000, 250000),
        ("Cortinas Blackout", 60000, 130000),
        ("Organizador Plástico", 20000, 45000),
        ("Aspiradora de Mano", 90000, 180000),
        ("Set de Toallas", 40000, 85000),
        ("Difusor de Aromas", 30000, 65000),
        ("Silla Plegable", 55000, 110000),
        ("Espejo Decorativo", 65000, 130000),
    ],
    Categoria.ALIMENTOS: [
        ("Café Premium 500g", 18000, 32000),
        ("Chocolate de Mesa 250g", 8000, 16000),
        ("Panela Orgánica x6", 10000, 20000),
        ("Aceite de Oliva 500ml", 22000, 42000),
        ("Pasta Integral 500g", 5000, 10000),
        ("Miel de Abejas 350g", 15000, 28000),
        ("Granola Artesanal 400g", 14000, 26000),
        ("Té Verde x20", 9000, 18000),
        ("Snack Mix Frutos Secos", 12000, 24000),
        ("Salsa Picante Artesanal", 11000, 22000),
    ],
    Categoria.JUGUETERIA: [
        ("Muñeca Articulada", 45000, 95000),
        ("Carro a Control Remoto", 70000, 150000),
        ("Rompecabezas 500 piezas", 30000, 60000),
        ("Set de Bloques de Construcción", 55000, 120000),
        ("Peluche Grande", 40000, 85000),
        ("Juego de Mesa Familiar", 50000, 100000),
        ("Pelota Saltarina", 15000, 32000),
        ("Kit de Plastilina", 20000, 42000),
        ("Cometa", 12000, 26000),
        ("Set de Pintura Infantil", 25000, 50000),
    ],
    Categoria.DEPORTES: [
        ("Balón de Fútbol", 45000, 95000),
        ("Pesas 5kg (par)", 60000, 130000),
        ("Colchoneta de Yoga", 35000, 75000),
        ("Guantes de Boxeo", 55000, 115000),
        ("Bicicleta Urbana", 650000, 1200000),
        ("Cuerda para Saltar", 15000, 32000),
        ("Casco de Ciclismo", 70000, 145000),
        ("Botella Térmica Deportiva", 25000, 50000),
        ("Banda de Resistencia", 18000, 38000),
        ("Bolso Deportivo", 40000, 85000),
    ],
    Categoria.BELLEZA: [
        ("Shampoo Reparador 400ml", 22000, 42000),
        ("Crema Facial Hidratante", 35000, 70000),
        ("Perfume 100ml", 90000, 190000),
        ("Set de Brochas de Maquillaje", 45000, 95000),
        ("Protector Solar FPS 50", 30000, 60000),
        ("Labial Mate", 18000, 38000),
        ("Secador de Cabello", 60000, 125000),
        ("Aceite Corporal", 25000, 52000),
        ("Kit de Manicure", 32000, 65000),
        ("Desodorante Roll-On", 10000, 22000),
    ],
}

# (codigo, tipo, valor, dias_inicio_desde_hoy, dias_fin_desde_hoy, sede_codigo, uso_maximo)
# Deliberadamente hay códigos vencidos, futuros, globales, por sede, y uno
# vencido + de una sede inactiva — para que el motor de reglas tenga qué
# detectar más adelante.
CODIGOS_DESCUENTO = [
    ("BIENVENIDA10", TipoDescuento.PORCENTAJE, 10, -365, 365, None, None),
    ("VERANO2026", TipoDescuento.PORCENTAJE, 15, -60, 30, None, 500),
    ("BLACKFRIDAY", TipoDescuento.PORCENTAJE, 30, -200, -170, None, 1000),
    ("NAVIDAD2025", TipoDescuento.PORCENTAJE, 20, -250, -220, None, None),
    ("FLASH50K", TipoDescuento.VALOR_FIJO, 50000, -10, 20, None, 200),
    ("REAPERTURA_BOG", TipoDescuento.PORCENTAJE, 25, -30, 15, "TDA-001", 100),
    ("MEDELLIN_VIP", TipoDescuento.PORCENTAJE, 12, -90, 90, "TDA-003", None),
    ("CALI_ANIVERSARIO", TipoDescuento.VALOR_FIJO, 30000, -5, 10, "TDA-005", 150),
    ("PROXIMO2027", TipoDescuento.PORCENTAJE, 20, 60, 120, None, None),
    ("ENVIGADO15", TipoDescuento.PORCENTAJE, 15, -15, 45, "TDA-004", 80),
    ("CARIBE_FIESTA", TipoDescuento.PORCENTAJE, 18, -20, 40, "TDA-006", None),
    ("CARTAGENA_VERANO", TipoDescuento.VALOR_FIJO, 20000, -30, 30, "TDA-007", 300),
    ("MADRUGON", TipoDescuento.PORCENTAJE, 40, -3, 3, None, 50),
    ("FIDELIDAD5", TipoDescuento.PORCENTAJE, 5, -365, 365, None, None),
    ("CUCUTA20", TipoDescuento.VALOR_FIJO, 15000, -100, -50, "TDA-011", 100),
]


def reset_catalog(db) -> None:
    db.query(TransferenciaModel).delete()
    db.query(CodigoDescuentoModel).delete()
    db.query(TrabajadorModel).delete()
    db.query(ProductoModel).delete()
    db.query(SedeModel).delete()
    db.commit()


def seed_sedes(db) -> list[str]:
    codigos = []
    for codigo, nombre, ciudad, region in SEDES:
        apertura = date.today() - timedelta(days=random.randint(200, 2500))
        db.add(
            SedeModel(
                codigo=codigo,
                nombre=nombre,
                ciudad=ciudad,
                region=region,
                fecha_apertura=apertura,
                activa=codigo not in SEDES_INACTIVAS,
            )
        )
        codigos.append(codigo)
    db.commit()
    return codigos


def seed_trabajadores(db, sede_codigos: list[str], total: int = 90) -> list[str]:
    codigos = []
    for i in range(1, total + 1):
        codigo = f"EMP-{i:04d}"
        ingreso = date.today() - timedelta(days=random.randint(10, 1800))
        db.add(
            TrabajadorModel(
                codigo=codigo,
                nombre=fake.name(),
                sede_codigo=random.choice(sede_codigos),
                cargo=random.choice(CARGOS),
                fecha_ingreso=ingreso,
                activo=random.random() > 0.08,  # ~8% inactivos
            )
        )
        codigos.append(codigo)
    db.commit()
    return codigos


def seed_productos(db) -> list[str]:
    skus = []
    for categoria, productos in PRODUCTOS_POR_CATEGORIA.items():
        prefijo = CATEGORIA_PREFIJO[categoria]
        for idx, (nombre, costo, precio_lista) in enumerate(productos, start=1):
            sku = f"{prefijo}-{idx:04d}"
            db.add(
                ProductoModel(
                    sku=sku,
                    nombre=nombre,
                    categoria=categoria.value,
                    precio_lista=precio_lista,
                    costo=costo,
                )
            )
            skus.append(sku)
    db.commit()
    return skus


def seed_codigos_descuento(db) -> None:
    for codigo, tipo, valor, dias_inicio, dias_fin, sede_codigo, uso_maximo in CODIGOS_DESCUENTO:
        db.add(
            CodigoDescuentoModel(
                codigo=codigo,
                tipo=tipo.value,
                valor=valor,
                vigencia_inicio=date.today() + timedelta(days=dias_inicio),
                vigencia_fin=date.today() + timedelta(days=dias_fin),
                sede_codigo=sede_codigo,
                uso_maximo=uso_maximo,
            )
        )
    db.commit()


def seed_transferencias(
    db, sede_codigos: list[str], skus: list[str], extra: int = 200
) -> None:
    """Una transferencia base por cada (sede, producto) para que la regla
    'cantidad_dentro_de_transferencias' tenga con qué comparar en toda
    combinación, no solo en las que le tocaron al azar - más `extra`
    transferencias puramente aleatorias encima, para variar montos."""
    for sede in sede_codigos:
        for sku in skus:
            origen = random.choice([s for s in sede_codigos if s != sede])
            db.add(
                TransferenciaModel(
                    id=str(uuid.uuid4()),
                    producto_sku=sku,
                    sede_origen_codigo=origen,
                    sede_destino_codigo=sede,
                    cantidad=random.randint(20, 150),
                    fecha=date.today() - timedelta(days=random.randint(0, 180)),
                )
            )

    for _ in range(extra):
        origen, destino = random.sample(sede_codigos, 2)
        db.add(
            TransferenciaModel(
                id=str(uuid.uuid4()),
                producto_sku=random.choice(skus),
                sede_origen_codigo=origen,
                sede_destino_codigo=destino,
                cantidad=random.randint(5, 200),
                fecha=date.today() - timedelta(days=random.randint(0, 180)),
            )
        )
    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        reset_catalog(db)
        sede_codigos = seed_sedes(db)
        trabajador_codigos = seed_trabajadores(db, sede_codigos)
        skus = seed_productos(db)
        seed_codigos_descuento(db)
        seed_transferencias(db, sede_codigos, skus)

        print(f"Sedes: {len(sede_codigos)}")
        print(f"Trabajadores: {len(trabajador_codigos)}")
        print(f"Productos: {len(skus)}")
        print(f"Códigos de descuento: {len(CODIGOS_DESCUENTO)}")
        print(f"Transferencias: {len(sede_codigos) * len(skus)} base + 200 extra")
        print("Seed completado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
