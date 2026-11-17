from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    DOCENTE = "DOCENTE", "Docente"
    REPRESENTANTE = "REPRESENTANTE", "Representante"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email):
        # El inicio de sesión no distingue mayúsculas de minúsculas en el correo.
        return self.get(email__iexact=email)

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        if extra_fields.get("role") not in Role.values:
            raise ValueError("Debes indicar un rol válido.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # Con password=None deja la contraseña inutilizable.
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMINISTRADOR)
        extra_fields.setdefault("must_change_password", False)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario del sistema. Solo existen cuentas para docentes, representantes y
    administradores; el estudiante NO es un usuario (se modelará en la app academic).
    """

    email = models.EmailField("correo electrónico", unique=True)
    first_name = models.CharField("nombres", max_length=150)
    last_name = models.CharField("apellidos", max_length=150)
    role = models.CharField("rol", max_length=20, choices=Role.choices, db_index=True)

    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al admin de Django", default=False)

    # Las cuentas las crea el administrador con una contraseña temporal;
    # mientras este indicador esté activo el usuario solo puede cambiar su contraseña.
    must_change_password = models.BooleanField("debe cambiar la contraseña", default=True)
    # Vencimiento de la contraseña temporal de bienvenida (2 horas). Si el usuario intenta
    # ingresar con ella ya vencida, el sistema le envía una nueva. Nulo = sin vencimiento.
    clave_temporal_expira_en = models.DateTimeField("la clave temporal vence el", null=True, blank=True)

    # Aceptación de los términos de uso y de la política de privacidad (LOPDP). Se guarda la
    # versión aceptada: si la institución publica una versión nueva, se vuelve a pedir.
    terminos_version = models.CharField("versión de términos aceptada", max_length=20, blank=True)
    terminos_aceptados_en = models.DateTimeField("términos aceptados el", null=True, blank=True)

    date_joined = models.DateTimeField("fecha de registro", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def clave_temporal_vencida(self):
        return bool(
            self.must_change_password
            and self.clave_temporal_expira_en
            and self.clave_temporal_expira_en <= timezone.now()
        )

    @property
    def is_administrador(self):
        return self.role == Role.ADMINISTRADOR

    @property
    def is_docente(self):
        return self.role == Role.DOCENTE

    @property
    def is_representante(self):
        return self.role == Role.REPRESENTANTE


class CodigoRecuperacion(models.Model):
    """
    Credencial de un solo uso que el sistema envía por correo. Solo se guarda su hash (como
    una contraseña): ni la base de datos ni el admin la conocen. Caduca y admite pocos intentos.

    - RECUPERACION: código OTP de 6 dígitos de «¿Olvidaste tu contraseña?».
    - CAMBIO_CLAVE: clave temporal que se pide desde el Perfil para cambiar la contraseña.
      NO reemplaza la contraseña actual: si no se usa, vence y todo sigue igual.
    """

    class Tipo(models.TextChoices):
        RECUPERACION = "RECUPERACION", "Código para recuperar la contraseña"
        CAMBIO_CLAVE = "CAMBIO_CLAVE", "Clave temporal para cambiar la contraseña"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="codigos_recuperacion")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.RECUPERACION, db_index=True)
    codigo_hash = models.CharField(max_length=128)
    expira_en = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
    usado_en = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "código de recuperación"
        verbose_name_plural = "códigos de recuperación"

    @property
    def vigente(self):
        return self.usado_en is None and self.expira_en > timezone.now()


class EnvioAcceso(models.Model):
    """
    Cola de envío de las contraseñas temporales de bienvenida (intermediario de la
    importación masiva). Importar solo registra a los usuarios y los pone en esta cola; un
    proceso aparte toma un envío a la vez, genera la clave temporal en ese momento (no se
    guarda en ningún lado) y la manda por correo a un ritmo controlado, con reintentos.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "En cola"
        ENVIANDO = "ENVIANDO", "Enviando"
        ENVIADO = "ENVIADO", "Enviado"
        ERROR = "ERROR", "No se pudo enviar"
        CANCELADO = "CANCELADO", "Cancelado"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="envios_acceso")
    lote = models.CharField("lote de importación", max_length=36, db_index=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    programado_en = models.DateTimeField("enviar desde", default=timezone.now, db_index=True)
    tomado_en = models.DateTimeField(null=True, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    ultimo_error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["programado_en", "id"]
        verbose_name = "envío de acceso"
        verbose_name_plural = "cola de envíos de acceso"

    def __str__(self):
        return f"{self.usuario} · {self.get_estado_display()}"
