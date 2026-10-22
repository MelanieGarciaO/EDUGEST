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
    def is_administrador(self):
        return self.role == Role.ADMINISTRADOR

    @property
    def is_docente(self):
        return self.role == Role.DOCENTE

    @property
    def is_representante(self):
        return self.role == Role.REPRESENTANTE
