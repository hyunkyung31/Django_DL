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

class Examination(models.Model):
    exam_id = models.IntegerField(primary_key=True)
    patient_id = models.CharField(max_length=50)
    vessel_type = models.CharField(max_length=20)
    video_path = models.CharField(max_length=255)
    key_frame_path = models.CharField(max_length=255)
    class Meta:
        db_table = "examinations"
        managed = False
    def __str__(self):
        return f"{self.exam_id} ({self.patient_id})"
class AIResult(models.Model):
    exam_id = models.IntegerField(primary_key=True)
    confirming_doctor_id = models.CharField(max_length=50, null=True, blank=True)
    has_lesion = models.BooleanField()
    severity_class = models.CharField(max_length=50)
    confidence_score = models.FloatField()
    ai_bbox_data = models.JSONField(null=True, blank=True)
    gradcam_path = models.CharField(max_length=255, null=True, blank=True)
    heart_score = models.IntegerField(null=True, blank=True)
    mace_risk_percent = models.FloatField(null=True, blank=True)
    doctor_opinion = models.TextField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    class Meta:
        db_table = "ai_results"
        managed = False
    def __str__(self):
        return f"AIResult({self.exam_id})"

class Bookmark(models.Model):
    id = models.BigAutoField(primary_key=True)
    doctor_id = models.CharField(max_length=20)
    patient_id = models.CharField(max_length=50, null=True, blank=True)
    exam_id = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=200)
    note = models.TextField(null=True, blank=True)
    frame_number = models.IntegerField(null=True, blank=True)
    bbox_data = models.JSONField()
    snapshot_path = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "bookmarks"
        managed = False

    def __str__(self):
        return f"Bookmark({self.id}, {self.title})"


class EMRSignOff(models.Model):
    id = models.BigAutoField(primary_key=True)
    patient_id = models.CharField(max_length=50, db_index=True)
    doctor_id = models.CharField(max_length=20, db_index=True)
    finalized = models.BooleanField(default=False)
    final_result = models.TextField(blank=True, default="")
    ai_result = models.JSONField(null=True, blank=True)
    emr_transmitted = models.BooleanField(default=False)
    transmitted_at = models.DateTimeField(null=True, blank=True)
    report_ready = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emr_signoffs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"EMRSignOff({self.id}, {self.patient_id}, {self.doctor_id})"
