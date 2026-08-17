from rest_framework.routers import DefaultRouter

from .api import ClientViewSet, PersonViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("people", PersonViewSet, basename="person")

urlpatterns = router.urls
