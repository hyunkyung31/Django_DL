from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def health_check(request) :
    return Response({"status" : "ok", "message" : "ANGIO CDSS 백엔드 서버가 정상 작동 중입니다."})