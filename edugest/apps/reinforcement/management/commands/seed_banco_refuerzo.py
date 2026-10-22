from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academic import seeds
from apps.academic.models import Asignatura, Tema
from apps.reinforcement.models import RecursoRefuerzo

CAMPOS = ("nivel", "estrategia", "titulo", "instrucciones")


class Command(BaseCommand):
    help = (
        "Carga recursos del banco de refuerzo desde un JSON (por defecto "
        "seed_data/banco_refuerzo.json) en un grado habilitado. Es idempotente. Requiere haber "
        "ejecutado antes seed_academico y seed_temas_ejemplo."
    )

    def add_arguments(self, parser):
        seeds.agregar_opcion_archivo(parser, "banco_refuerzo.json")
        seeds.agregar_opcion_grado(parser)

    @transaction.atomic
    def handle(self, *args, **options):
        origen = options["archivo"]
        datos = seeds.leer_json(origen)
        grado = seeds.grado_destino(options["grado"])
        errores = []

        # 1) Validar todo antes de escribir (niveles, estrategias, longitudes y duración
        #    se comprueban con las reglas del propio modelo).
        carga = []  # (tema, {campos})
        for i, bloque in enumerate(seeds.lista(datos, "temas", origen), start=1):
            nombre_asignatura = seeds.texto(bloque, "asignatura", f"temas[{i}]", errores)
            nombre_tema = seeds.texto(bloque, "tema", f"temas[{i}]", errores)
            if not (nombre_asignatura and nombre_tema):
                continue
            asignatura = Asignatura.objects.filter(nombre=nombre_asignatura).first()
            tema = (
                Tema.objects.filter(grado=grado, asignatura=asignatura, nombre=nombre_tema).first()
                if asignatura
                else None
            )
            if tema is None:
                raise CommandError(
                    f"No existe el tema '{nombre_tema}' de {nombre_asignatura} en {grado.nombre}. "
                    "Ejecuta primero: seed_academico y seed_temas_ejemplo"
                )
            for j, r in enumerate(seeds.lista(bloque, "recursos", f"temas[{i}]"), start=1):
                ubicacion = f"{nombre_tema} › recursos[{j}]"
                valores = {c: seeds.texto(r, c, ubicacion, errores) for c in CAMPOS}
                valores["duracion_minutos"] = r.get("duracion_minutos") if isinstance(r, dict) else None
                if None in (valores[c] for c in CAMPOS):
                    continue
                seeds.validar_modelo(RecursoRefuerzo(tema=tema, **valores), ubicacion, errores)
                carga.append((tema, valores))
        seeds.abortar_si_hay_errores(errores, origen)

        # 2) Guardar. Si el recurso ya existe (mismo tema y título) no se modifica.
        nuevos = 0
        for tema, valores in carga:
            titulo = valores.pop("titulo")
            nuevos += RecursoRefuerzo.objects.get_or_create(
                tema=tema, titulo=titulo, defaults=valores
            )[1]

        self.stdout.write(self.style.SUCCESS(f"Recursos nuevos en {grado.nombre}: {nuevos}."))
