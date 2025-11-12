from django.db import models

class Driver(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.name