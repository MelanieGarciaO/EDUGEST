from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academic import seeds
from apps.academic.models import Asignatura, Grado


class Command(BaseCommand):
    help = (
        "Carga grados y asignaturas desde un JSON (por defecto seed_data/academico.json). "
        "Es idempotente: lo que ya existe no se duplica ni se modifica."
    )

    def add_arguments(self, parser):
        seeds.agregar_opcion_archivo(parser, "academico.json")

    @transaction.atomic
    def handle(self, *args, **options):
        origen = options["archivo"]
        datos = seeds.leer_json(origen)
        errores = []

        grados = []
        for i, g in enumerate(seeds.lista(datos, "grados", origen), start=1):
            ubicacion = f"grados[{i}]"
            nombre = seeds.texto(g, "nombre", ubicacion, errores)
            orden = g.get("orden") if isinstance(g, dict) else None
            if not isinstance(orden, int) or isinstance(orden, bool):
                errores.append(f"{ubicacion}: «orden» debe ser un número entero.")
                continue
            if nombre:
                seeds.validar_modelo(Grado(nombre=nombre, orden=orden), ubicacion, errores)
                grados.append((orden, nombre))

        asignaturas = []
        for i, nombre in enumerate(seeds.lista(datos, "asignaturas", origen), start=1):
            nombre = seeds.texto({"nombre": nombre}, "nombre", f"asignaturas[{i}]", errores)
            if nombre:
                seeds.validar_modelo(Asignatura(nombre=nombre), f"asignaturas[{i}]", errores)
                asignaturas.append(nombre)

        if len({o for o, _ in grados}) != len(grados):
            errores.append("grados: hay órdenes repetidos.")
        seeds.abortar_si_hay_errores(errores, origen)

        grados_nuevos = sum(
            Grado.objects.get_or_create(orden=orden, defaults={"nombre": nombre})[1]
            for orden, nombre in grados
        )
        asignaturas_nuevas = sum(
            Asignatura.objects.get_or_create(nombre=nombre)[1] for nombre in asignaturas
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Grados nuevos: {grados_nuevos}. Asignaturas nuevas: {asignaturas_nuevas}."
            )
        )
