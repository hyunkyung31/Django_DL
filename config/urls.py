from django.contrib import admin
from django.urls import path
from api.views import (
    health_check,
    me,
    login,
    doctor_list,
    patient_list,
    patient_detail,
    patient_search,
    ai_predict,
    ai_gradcam,
    ai_image_analyze,
    media_local,
    media_gcs,
    patient_media_upload,
)
from rest_framework_simplejwt.views import(
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check),
    path("api/login/", login),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/", me),
    path("api/doctors/", doctor_list),
    path("api/patients/", patient_list),
    path("api/patients/search/", patient_search),
    path("api/patients/<str:patient_id>/media/", patient_media_upload),
    path("api/patients/<str:patient_id>/", patient_detail),
    path("api/media/local/", media_local),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/ai/predict/", ai_predict),
    path("api/ai/gradcam/", ai_gradcam),
    path("api/ai/image-analyze/", ai_image_analyze),
    path("api/media/gcs/", media_gcs),
]
