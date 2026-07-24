from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
def health_check(request) :
    return Response({"status" : "ok", "message" : "ANGIO CDSS 백엔드 서버가 정상 작동 중입니다."})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request) :
    user = request.user
    return Response({
        "id" : user.id,
        "username" : user.username,
        "email" : user.email,
    })