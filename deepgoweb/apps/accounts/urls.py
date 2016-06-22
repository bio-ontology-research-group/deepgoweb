from django.conf.urls import include, url
from django.contrib.auth.decorators import login_required
from accounts.views import ProfileDetailView

urlpatterns = [
    url(r'^profile/$', ProfileDetailView.as_view(), name='profile'),
]
