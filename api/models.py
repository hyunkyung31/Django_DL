from django.db import models

class Doctor(models.Model):
    doctor_id = models.CharField(max_length=20, primary_key=True)
    password = models.CharField(max_length=128)
    doctor_name = models.CharField(max_length=50)
    department = models.CharField(max_length=50)
    hospital_name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    email = models.CharField(max_length=100)
    created_at = models.DateTimeField()

    class Meta :
        db_table = "doctors"
        managed = False

    def __str__(self):
        return f'{self.doctor_id} ({self.doctor_name})'

class Patient(models.Model):
    patient_id = models.CharField(max_length=50, primary_key=True)
    primary_doctor_id = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    kakao_id = models.CharField(max_length=100, null=True, blank=True)
    social_provider = models.CharField(max_length=20, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    dataset_patient_id = models.CharField(max_length=20)
    patient_name = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, null=True, blank=True)
    age = models.IntegerField()
    history_score = models.IntegerField(null=True, blank=True)
    ecg_result = models.CharField(max_length=50, null=True, blank=True)
    risk_factors_count = models.IntegerField(null=True, blank=True)
    troponin_t_level = models.FloatField(null=True, blank=True)
    underlying_diseases = models.JSONField(null=True, blank=True)
    chief_complaint = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "patients"
        managed = False

    def __str__(self):
        return f"{self.patient_id} ({self.patient_name})"