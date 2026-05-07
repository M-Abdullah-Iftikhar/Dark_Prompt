from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("terms/", views.legal_terms, name="terms"),
    path("privacy/", views.legal_privacy, name="privacy"),
    path("acceptable-use/", views.legal_aup, name="acceptable_use"),
    path("about/", views.about, name="about"),
    path("changelog/", views.changelog, name="changelog"),
    path("robots.txt",  views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("manifest.webmanifest", views.web_manifest, name="manifest"),
    path("status/", views.status_page, name="status"),
    path("api/status/", views.api_status, name="api_status"),
    # Dev-only preview of the styled 404 — DEBUG=True hides the real one.
    path("404-preview/", views.not_found_view, name="not_found_preview"),
    path("500-preview/", views.server_error_view, name="server_error_preview"),
]
