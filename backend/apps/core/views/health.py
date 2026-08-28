from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for the traffic management backend.
    
    Returns:
        Response: JSON response with service status
    """
    return Response({
        "status": "ok",
        "service": "traffic-management-backend"
    })
