from django.views.generic import TemplateView
from django.views.generic.simple import redirect_to
from django.core.urlresolvers import reverse_lazy

from django.conf.urls import patterns, url

from layerindex.views import EditProfileFormView

urlpatterns = patterns('',
    url(r'^$', redirect_to, {'url' : reverse_lazy('about', args=())},
        name='frontpage'),
    url(r'^profile/$',
        EditProfileFormView.as_view(
        template_name='layerindex/profile.html'),
        name="profile"),
    url(r'^about/$',
        TemplateView.as_view(
        template_name='rrs/about.html'),
        name="about"),
)
