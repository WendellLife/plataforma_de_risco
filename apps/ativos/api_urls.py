from rest_framework.routers import DefaultRouter

from .api import MachineViewSet

router = DefaultRouter()
router.register("machines", MachineViewSet, basename="machine")

urlpatterns = router.urls
