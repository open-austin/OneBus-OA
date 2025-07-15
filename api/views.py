from django.http import JsonResponse

def test(request):
    return JsonResponse({"message": "API is working!"})