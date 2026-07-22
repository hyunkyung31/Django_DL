from django.contrib import admin
from django.urls import path
from api.views import health_check


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check), # 테스트용 API 엔드포인트
]
