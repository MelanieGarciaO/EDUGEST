"""Hora actual del servidor (zona horaria del proyecto). Aparte para poder simularla en las pruebas."""
 
from django.utils import timezone
 
 
def hora_actual():
    return timezone.localtime().time()
