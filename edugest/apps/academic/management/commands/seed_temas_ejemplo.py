from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academic import seeds
from apps.academic.models import Asignatura, Tema


class Command(BaseCommand):
    help = (
        "Carga temas y subtemas desde un JSON (por defecto seed_data/temas_ejemplo.json) en un "
        "grado habilitado. Es idempotente. Requiere haber ejecutado antes seed_academico."
    )

    def add_arguments(self, parser):
        seeds.agregar_opcion_archivo(parser, "temas_ejemplo.json")
        seeds.agregar_opcion_grado(parser)

    @transaction.atomic
    def handle(self, *args, **options):
        origen = options["archivo"]
        datos = seeds.leer_json(origen)
        grado = seeds.grado_destino(options["grado"])
        errores = []

        # 1) Validar todo antes de escribir.
        carga = []  # (asignatura, nombre_tema, [subtemas])
        for i, bloque in enumerate(seeds.lista(datos, "asignaturas", origen), start=1):
            nombre_asignatura = seeds.texto(bloque, "asignatura", f"asignaturas[{i}]", errores)
            if not nombre_asignatura:
                continue
            asignatura = Asignatura.objects.filter(nombre=nombre_asignatura).first()
            if asignatura is None:
                raise CommandError(
                    f"No existe la asignatura '{nombre_asignatura}'. Ejecuta primero: seed_academico"
                )
            for j, t in enumerate(seeds.lista(bloque, "temas", f"asignaturas[{i}]"), start=1):
                ubicacion = f"{nombre_asignatura} › temas[{j}]"
                nombre_tema = seeds.texto(t, "nombre", ubicacion, errores)
                subtemas = []
                for k, sub in enumerate(t.get("subtemas") or [], start=1):
                    sub = seeds.texto({"nombre": sub}, "nombre", f"{ubicacion} › subtemas[{k}]", errores)
                    if sub:
                        subtemas.append(sub)
                for nombre in filter(None, [nombre_tema, *subtemas]):
                    seeds.validar_modelo(
                        Tema(grado=grado, asignatura=asignatura, nombre=nombre), ubicacion, errores
                    )
                if nombre_tema:
                    carga.append((asignatura, nombre_tema, subtemas))
        seeds.abortar_si_hay_errores(errores, origen)

        # 2) Guardar.
        nuevos = 0
        for asignatura, nombre_tema, subtemas in carga:
            tema, creado = Tema.objects.get_or_create(
                grado=grado, asignatura=asignatura, padre=None, nombre=nombre_tema
            )
            nuevos += creado
            for nombre_sub in subtemas:
                nuevos += Tema.objects.get_or_create(
                    grado=grado, asignatura=asignatura, padre=tema, nombre=nombre_sub
                )[1]

        self.stdout.write(self.style.SUCCESS(f"Temas nuevos en {grado.nombre}: {nuevos}."))
    