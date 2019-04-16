from django.urls import include, path
from django.contrib.auth.decorators import login_required
from accounts.views import ProfileDetailView

urlpatterns = [
    path('profile/', ProfileDetailView.as_view(), name='profile'),
]
