from django.contrib import admin
from django.urls import path
from api.views import health_check, me, login, patient_list
from rest_framework_simplejwt.views import(
    TokenObtainPairView,
    TokenRefreshView,
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check), # 테스트용 API 엔드포인트
    path("api/login/", login), # 의사 MySql로그인
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/", me),
    path("api/patients/", patient_list),
]
